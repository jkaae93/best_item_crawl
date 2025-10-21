#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
BEST_PAGE_URL = (
    "https://display.wconcept.co.kr/rn/best?displayCategoryType=ALL&displaySubCategoryType=ALL&gnbType=Y"
)
# 페이지가 최초로 호출하는 상품 API를 관찰하여 카테고리 힌트를 확보한다
CATEGORY_ENDPOINT_SUBSTR = "/display/api/best/v1/product"
PRODUCT_ENDPOINT = "https://gw-front.wconcept.co.kr/display/api/best/v1/product"

KEYWORDS = ["하시에", "hacie"]


@dataclass(frozen=True)
class CategoryPair:
    depth1_code: str
    depth1_name: str
    depth2_code: str
    depth2_name: str


def find_key_recursive(obj: Any, key: str) -> List[Any]:
    results: List[Any] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                results.append(v)
            results.extend(find_key_recursive(v, key))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(find_key_recursive(item, key))
    return results


def iter_dicts(obj: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from iter_dicts(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_dicts(item)


def extract_category_pairs(categories_json: Dict[str, Any]) -> List[CategoryPair]:
    pairs: List[CategoryPair] = []

    # Prefer explicit key if present
    candidate_arrays = find_key_recursive(categories_json, "bestCategories")
    if not candidate_arrays:
        candidate_arrays = find_key_recursive(categories_json, "categories")

    for arr in candidate_arrays:
        if not isinstance(arr, list):
            continue
        for group in arr:
            if not isinstance(group, dict):
                continue
            d1_code = str(
                group.get("depth1Code")
                or group.get("depth1Cd")
                or group.get("d1Code")
                or group.get("code")
                or ""
            )
            d1_name = str(
                group.get("depth1Name")
                or group.get("d1Name")
                or group.get("name")
                or ""
            )
            if not d1_code:
                # Try to find a depth1 code in any nested object
                for d in iter_dicts(group):
                    cand = d.get("depth1Code") or d.get("depth1Cd") or d.get("d1Code")
                    if cand:
                        d1_code = str(cand)
                        d1_name = str(d.get("depth1Name") or d.get("d1Name") or d.get("name") or d1_name)
                        break

            # Collect all depth2 entries under this group
            for d in iter_dicts(group):
                d2_code = d.get("depth2Code") or d.get("depth2Cd") or d.get("d2Code")
                if not d2_code:
                    continue
                d2_name = str(d.get("depth2Name") or d.get("d2Name") or d.get("name") or "")
                if d1_code:
                    pairs.append(
                        CategoryPair(
                            depth1_code=str(d1_code),
                            depth1_name=d1_name,
                            depth2_code=str(d2_code),
                            depth2_name=d2_name,
                        )
                    )

    # Deduplicate by (d1, d2)
    unique: Dict[Tuple[str, str], CategoryPair] = {}
    for p in pairs:
        key = (p.depth1_code, p.depth2_code)
        if key not in unique and p.depth1_code and p.depth2_code:
            unique[key] = p
    return list(unique.values())


def get_api_key_and_categories(timeout_ms: int = 25000) -> Tuple[str, List[CategoryPair], Dict[str, str]]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="ko-KR", timezone_id="Asia/Seoul")
        page = context.new_page()

        api_key: Optional[str] = None
        captured_headers: Dict[str, str] = {}
        seed_products: Optional[List[Dict[str, Any]]] = None

        def on_response(response):
            nonlocal api_key, captured_headers, seed_products
            url = response.url
            if CATEGORY_ENDPOINT_SUBSTR in url and seed_products is None:
                # 상품 응답을 받아 리스트 구조를 확보한다
                try:
                    data = response.json()
                except Exception:
                    data = None
                if isinstance(data, dict):
                    seed_products = extract_products_list(data)
                # 요청 헤더에서 x-api-key 등도 함께 확보 (없어도 동작할 수 있음)
                try:
                    req = response.request
                    headers = req.headers or {}
                    captured_headers = {k.lower(): v for k, v in headers.items()}
                    api_key = (
                        captured_headers.get("x-api-key")
                        or captured_headers.get("x-api_key")
                        or captured_headers.get("x-apikey")
                    )
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            page.goto(BEST_PAGE_URL, wait_until="networkidle", timeout=timeout_ms)
            # Give a moment for any late XHR
            page.wait_for_timeout(1000)
        except PlaywrightTimeoutError:
            # Try DOMContentLoaded fallback
            page.goto(BEST_PAGE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(1500)

        context.close()
        browser.close()

    # api-key 는 없을 수 있다 (현재 제품 API는 공개 호출 허용됨)
    # 카테고리 목록은 seed 상품 응답에서 유추하거나, 최소 기본값으로 대체한다
    pairs: List[CategoryPair] = []
    if seed_products:
        for prod in seed_products:
            d1 = str(
                prod.get("depth1Code")
                or prod.get("d1Code")
                or prod.get("categoryDepth1Code")
                or ""
            )
            d2 = str(
                prod.get("depth2Code")
                or prod.get("d2Code")
                or prod.get("categoryDepth2Code")
                or ""
            )
            d1n = str(
                prod.get("depth1Name")
                or prod.get("d1Name")
                or prod.get("categoryDepth1Name")
                or ""
            )
            d2n = str(
                prod.get("depth2Name")
                or prod.get("d2Name")
                or prod.get("categoryDepth2Name")
                or ""
            )
            if d1 and d2:
                pairs.append(CategoryPair(d1, d1n, d2, d2n))
    # 대표 카테고리 기본값 (요청 예시 기반)
    if not pairs:
        pairs = [
            CategoryPair("10102", "의류", "10102203", "하의"),
        ]

    # Prepare base headers for subsequent API calls
    base_headers = {
        "content-type": "application/json",
        "origin": "https://display.wconcept.co.kr",
        "referer": "https://display.wconcept.co.kr/rn/best",
        "user-agent": captured_headers.get("user-agent", "Mozilla/5.0"),
    }
    if api_key:
        base_headers["x-api-key"] = api_key
    return api_key, pairs, base_headers


def extract_products_list(obj: Any) -> List[Dict[str, Any]]:
    # Try common keys first
    for key in ("products", "productList", "list", "items", "bestProducts"):
        vals = find_key_recursive(obj, key)
        for v in vals:
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    # Common Wconcept best API shape: { data: { content: [...] } }
    if isinstance(obj, dict):
        data = obj.get("data")
        if isinstance(data, dict):
            content = data.get("content")
            if isinstance(content, list) and content and isinstance(content[0], dict):
                return content
    # Fallback: return any list of dicts containing 'productName' like fields
    candidates = find_key_recursive(obj, "productName")
    if candidates:
        # If 'productName' values exist, try to traverse back to lists (not trivial here); fallback below
        pass
    # As safest fallback, scan for any list of dicts with expected keys
    def has_product_shape(d: Dict[str, Any]) -> bool:
        keys = set(k.lower() for k in d.keys())
        return any(k in keys for k in ("productname", "name", "brandname"))

    lists: List[List[Dict[str, Any]]] = []
    for v in find_key_recursive(obj, "data") + find_key_recursive(obj, "result") + [obj]:
        if isinstance(v, list) and v and isinstance(v[0], dict) and has_product_shape(v[0]):
            lists.append(v)
    if lists:
        return lists[0]
    return []


def pick_price(product: Dict[str, Any]) -> Optional[int]:
    # Try common price fields
    for key in ("salePrice", "finalPrice", "price", "discountPrice", "sale_price"):
        if key in product and isinstance(product[key], (int, float, str)):
            try:
                return int(float(str(product[key]).replace(",", "")))
            except Exception:
                continue
    return None


def pick_name(product: Dict[str, Any]) -> str:
    for key in ("productName", "name", "goodsName", "title"):
        if key in product and product[key]:
            return str(product[key])
    return ""


def pick_brand(product: Dict[str, Any]) -> str:
    for key in ("brandName", "brand", "brand_name"):
        if key in product and product[key]:
            return str(product[key])
    return ""


def pick_rank(idx: int, product: Dict[str, Any]) -> int:
    for key in ("rank", "ranking", "bestOrder", "exposeOrder", "order"):
        if key in product:
            try:
                return int(product[key])
            except Exception:
                continue
    return idx + 1


def filter_products(products: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    if not products:
        return []
    pattern = re.compile("(" + "|".join(re.escape(k) for k in keywords) + ")", re.IGNORECASE)
    filtered: List[Dict[str, Any]] = []
    for p in products:
        name = pick_name(p)
        brand = pick_brand(p)
        text = f"{name} {brand}".strip()
        if pattern.search(text):
            filtered.append(p)
    return filtered


def fetch_products_for_category_page(
    headers: Dict[str, str],
    cat: CategoryPair,
    page_no: int,
    page_size: int,
) -> Tuple[List[Dict[str, Any]], Any]:
    payload = {
        "custNo": "0",
        "domain": "WOMEN",
        "genderType": "all",
        "dateType": "daily",
        "ageGroup": "all",
        "depth1Code": cat.depth1_code,
        "depth2Code": cat.depth2_code,
        "pageSize": page_size,
        "pageNo": page_no,
    }
    resp = requests.post(PRODUCT_ENDPOINT, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    products = extract_products_list(data)
    return products, data


def _infer_has_next_page(
    response_json: Any, current_page_no: int, page_size: int, last_page_count: int
) -> bool:
    # Try to infer pagination from common fields present in the response body
    def _dig(obj: Any) -> List[Dict[str, Any]]:
        dicts: List[Dict[str, Any]] = []
        if isinstance(obj, dict):
            dicts.append(obj)
            for v in obj.values():
                dicts.extend(_dig(v))
        elif isinstance(obj, list):
            for item in obj:
                dicts.extend(_dig(item))
        return dicts

    for d in _dig(response_json):
        # Explicit boolean flags
        for key in ("hasNext", "hasNextPage", "hasMore", "next"):
            val = d.get(key)
            if isinstance(val, bool):
                return val

        # Total pages
        total_pages = d.get("totalPages") or d.get("lastPage") or d.get("pages")
        if isinstance(total_pages, int) and total_pages > 0:
            return current_page_no < total_pages

        # Total count
        total_count = d.get("totalCount") or d.get("totalElements") or d.get("count")
        if isinstance(total_count, int) and total_count >= 0:
            return (current_page_no * page_size) < total_count

    # Fallback: if we received a full page, assume there might be a next page
    return last_page_count >= page_size


def fetch_all_products_for_category(
    headers: Dict[str, str],
    cat: CategoryPair,
    page_size: int = 200,
    max_pages: int = 0,
) -> List[Dict[str, Any]]:
    collected: List[Dict[str, Any]] = []
    current_page = 1
    while True:
        products, res_json = fetch_products_for_category_page(
            headers, cat, page_no=current_page, page_size=page_size
        )
        if not products:
            break
        collected.extend(products)

        # Stop if we've reached the configured page limit (0 means unlimited)
        if max_pages and current_page >= max_pages:
            break

        has_next = _infer_has_next_page(
            response_json=res_json,
            current_page_no=current_page,
            page_size=page_size,
            last_page_count=len(products),
        )
        if not has_next:
            break
        current_page += 1

    return collected


def write_csv(rows: List[List[Any]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(KST)
    filename = f"wconcept_best_{now.strftime('%Y%m%d_%H%M')}_KST.csv"
    out_path = output_dir / filename
    headers = ["날짜", "시간", "메인 카테고리", "서브 카테고리", "순위", "상품명", "가격"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Export Wconcept best products filtered by keyword to CSV")
    parser.add_argument("--output-dir", default="output", help="CSV 출력 디렉터리")
    parser.add_argument("--page-size", type=int, default=200, help="페이지당 상품 수 (기본 200)")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="최대 페이지 수 (0=제한 없음, 자동 종료)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    api_key, categories, base_headers = get_api_key_and_categories()

    kst_now = datetime.now(KST)
    date_str = kst_now.strftime("%Y-%m-%d")
    time_str = kst_now.strftime("%H:%M")

    rows: List[List[Any]] = []

    page_size = max(1, int(args.page_size))
    max_pages = max(0, int(args.max_pages))

    for cat in categories:
        try:
            products = fetch_all_products_for_category(
                base_headers, cat, page_size=page_size, max_pages=max_pages
            )
        except Exception:
            continue
        filtered = filter_products(products, KEYWORDS)
        for idx, p in enumerate(filtered):
            rank = pick_rank(idx, p)
            name = pick_name(p)
            price = pick_price(p)
            rows.append(
                [
                    date_str,
                    time_str,
                    cat.depth1_name or cat.depth1_code,
                    cat.depth2_name or cat.depth2_code,
                    rank,
                    name,
                    price if price is not None else "",
                ]
            )

    if not rows:
        # Write empty CSV with headers for traceability
        out = write_csv([], output_dir)
        print(f"CSV 생성 완료 (데이터 없음): {out}")
        return

    out = write_csv(rows, output_dir)
    print(f"CSV 생성 완료: {out}")


if __name__ == "__main__":
    main()
