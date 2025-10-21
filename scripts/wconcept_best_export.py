#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
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

ALLOWED_BRANDS = ["하시에", "HACIE"]


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

    # bestCategories.category1DepthList 구조 처리 (Next.js __NEXT_DATA__)
    best_categories = categories_json.get("bestCategories", {})
    if best_categories and isinstance(best_categories, dict):
        category1_depth_list = best_categories.get("category1DepthList", [])
        
        if category1_depth_list and isinstance(category1_depth_list, list):
            print(f"   🎯 bestCategories 발견: {len(category1_depth_list)}개 depth1")
            
            for depth1_item in category1_depth_list:
                if not isinstance(depth1_item, dict):
                    continue
                
                d1_code = str(depth1_item.get("depth1Code", ""))
                d1_name = str(depth1_item.get("depth1Name", ""))
                
                # category2DepthList에서 depth2 추출 (null일 수도 있음)
                category2_depth_list = depth1_item.get("category2DepthList")
                
                # category2DepthList가 null인 경우 (최상위 전체)
                if category2_depth_list is None and d1_code == "ALL":
                    pairs.append(CategoryPair(d1_code, d1_name, "ALL", "전체"))
                elif category2_depth_list and isinstance(category2_depth_list, list):
                    # 일반적인 경우: depth2 목록 순회
                    for depth2_item in category2_depth_list:
                        if not isinstance(depth2_item, dict):
                            continue
                        
                        d2_code = str(depth2_item.get("depth2Code", ""))
                        d2_name = str(depth2_item.get("depth2Name", ""))
                        
                        if d1_code and d2_code:
                            pairs.append(CategoryPair(d1_code, d1_name, d2_code, d2_name))
    
    # lnbInfo 구조 처리 (Next.js initialData - 대체 방법)
    if not pairs:
        lnb_info = categories_json.get("lnbInfo", [])
        if lnb_info and isinstance(lnb_info, list):
            for depth1_group in lnb_info:
                if not isinstance(depth1_group, dict):
                    continue
                
                # depth1 정보
                d1_code = str(depth1_group.get("largeCategory") or depth1_group.get("depth1Code") or "")
                d1_name = str(depth1_group.get("mediumName") or depth1_group.get("mediumKorName") or depth1_group.get("depth1Name") or "")
                
                # categoryDetail이나 subCategories에서 depth2 추출
                sub_categories = depth1_group.get("categoryDetail", []) or depth1_group.get("subCategories", [])
                
                for depth2_item in sub_categories:
                    if not isinstance(depth2_item, dict):
                        continue
                        
                    d2_code = str(depth2_item.get("middleCategory") or depth2_item.get("depth2Code") or "")
                    d2_name = str(depth2_item.get("categoryName") or depth2_item.get("depth2Name") or "")
                    
                    if d1_code and d2_code:
                        pairs.append(CategoryPair(d1_code, d1_name, d2_code, d2_name))
    
    # 기존 로직: bestCategories 키 찾기 (재귀 검색)
    if not pairs:
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
    """베스트 페이지에서 __NEXT_DATA__를 통해 카테고리 추출"""
    
    pairs: List[CategoryPair] = []
    captured_headers: Dict[str, str] = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="ko-KR", timezone_id="Asia/Seoul")
        page = context.new_page()

        def on_response(response):
            nonlocal captured_headers
            url = response.url
            
            # 상품 API에서 헤더 추출
            if CATEGORY_ENDPOINT_SUBSTR in url:
                try:
                    req = response.request
                    headers = req.headers or {}
                    captured_headers = {k.lower(): v for k, v in headers.items()}
                except Exception:
                    pass

        page.on("response", on_response)
        
        print("🔍 베스트 페이지에서 __NEXT_DATA__ 추출...")
        
        try:
            page.goto(BEST_PAGE_URL, wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_timeout(2000)
            
            # __NEXT_DATA__에서 bestCategories 추출
            next_data = page.evaluate("""
                () => {
                    const nextDataScript = document.getElementById('__NEXT_DATA__');
                    if (nextDataScript && nextDataScript.textContent) {
                        try {
                            const data = JSON.parse(nextDataScript.textContent);
                            const initialData = data?.props?.pageProps?.initialData;
                            
                            if (initialData && initialData.bestCategories) {
                                return initialData.bestCategories;
                            }
                        } catch (e) {
                            console.error('Parse error:', e);
                        }
                    }
                    return null;
                }
            """)
            
            if next_data and next_data.get('category1DepthList'):
                cat1_list = next_data.get('category1DepthList', [])
                print(f"✅ bestCategories 발견: {len(cat1_list)}개 depth1 카테고리")
                
                # 카테고리 파싱
                pairs = extract_category_pairs({"bestCategories": next_data})
                print(f"🎯 총 {len(pairs)}개 카테고리 조합 추출")
            else:
                print("⚠️ bestCategories를 찾을 수 없습니다")
                    
        except Exception as e:
            print(f"⚠️ 페이지 로드 실패: {e}")

        context.close()
        browser.close()
    
    # 실패 시 W컨셉의 주요 카테고리 하드코딩
    if not pairs:
        print("⚠️ 카테고리 동적 추출 실패, 하드코딩된 카테고리 사용")
        pairs = [
            # 1. 의류 - 12개
            CategoryPair("10102", "의류", "10102101", "아우터"),
            CategoryPair("10102", "의류", "10102201", "원피스"),
            CategoryPair("10102", "의류", "10102202", "상의"),
            CategoryPair("10102", "의류", "10102203", "하의"),
            CategoryPair("10102", "의류", "10102204", "셔츠/블라우스"),
            CategoryPair("10102", "의류", "10102205", "니트/스웨터"),
            CategoryPair("10102", "의류", "10102206", "세트"),
            CategoryPair("10102", "의류", "10102207", "스커트"),
            CategoryPair("10102", "의류", "10102208", "티셔츠"),
            CategoryPair("10102", "의류", "10102209", "팬츠"),
            CategoryPair("10102", "의류", "10102210", "점프수트"),
            CategoryPair("10102", "의류", "10102211", "데님"),
            # 2. 슈즈 - 6개
            CategoryPair("10103", "슈즈", "10103101", "스니커즈"),
            CategoryPair("10103", "슈즈", "10103102", "플랫/로퍼"),
            CategoryPair("10103", "슈즈", "10103103", "샌들/슬리퍼"),
            CategoryPair("10103", "슈즈", "10103104", "힐/펌프스"),
            CategoryPair("10103", "슈즈", "10103105", "부츠/워커"),
            CategoryPair("10103", "슈즈", "10103106", "슬립온"),
            # 3. 가방 - 7개
            CategoryPair("10104", "가방", "10104101", "숄더백"),
            CategoryPair("10104", "가방", "10104102", "크로스백"),
            CategoryPair("10104", "가방", "10104103", "토트백"),
            CategoryPair("10104", "가방", "10104104", "클러치"),
            CategoryPair("10104", "가방", "10104105", "백팩"),
            CategoryPair("10104", "가방", "10104106", "에코백"),
            CategoryPair("10104", "가방", "10104107", "캐리어"),
            # 4. 액세서리 - 8개
            CategoryPair("10105", "액세서리", "10105101", "주얼리"),
            CategoryPair("10105", "액세서리", "10105102", "시계"),
            CategoryPair("10105", "액세서리", "10105103", "모자"),
            CategoryPair("10105", "액세서리", "10105104", "벨트"),
            CategoryPair("10105", "액세서리", "10105105", "양말"),
            CategoryPair("10105", "액세서리", "10105106", "헤어"),
            CategoryPair("10105", "액세서리", "10105107", "선글라스"),
            CategoryPair("10105", "액세서리", "10105108", "스카프"),
            # 5. 뷰티 - 6개
            CategoryPair("10106", "뷰티", "10106101", "스킨케어"),
            CategoryPair("10106", "뷰티", "10106102", "메이크업"),
            CategoryPair("10106", "뷰티", "10106103", "바디케어"),
            CategoryPair("10106", "뷰티", "10106104", "헤어케어"),
            CategoryPair("10106", "뷰티", "10106105", "향수"),
            CategoryPair("10106", "뷰티", "10106106", "네일"),
            # 6. 라이프 - 4개
            CategoryPair("10107", "라이프", "10107101", "리빙"),
            CategoryPair("10107", "라이프", "10107102", "테크"),
            CategoryPair("10107", "라이프", "10107103", "식품"),
            CategoryPair("10107", "라이프", "10107104", "문구"),
            # 7. 맨즈 - 6개
            CategoryPair("10108", "맨즈", "10108101", "의류"),
            CategoryPair("10108", "맨즈", "10108102", "슈즈"),
            CategoryPair("10108", "맨즈", "10108103", "가방"),
            CategoryPair("10108", "맨즈", "10108104", "액세서리"),
            CategoryPair("10108", "맨즈", "10108105", "뷰티"),
            CategoryPair("10108", "맨즈", "10108106", "스포츠"),
            # 8. 키즈 - 4개
            CategoryPair("10109", "키즈", "10109101", "의류"),
            CategoryPair("10109", "키즈", "10109102", "슈즈"),
            CategoryPair("10109", "키즈", "10109103", "가방"),
            CategoryPair("10109", "키즈", "10109104", "액세서리"),
            # 9. 스포츠 - 5개
            CategoryPair("10110", "스포츠", "10110101", "의류"),
            CategoryPair("10110", "스포츠", "10110102", "슈즈"),
            CategoryPair("10110", "스포츠", "10110103", "가방"),
            CategoryPair("10110", "스포츠", "10110104", "액세서리"),
            CategoryPair("10110", "스포츠", "10110105", "용품"),
            # 10. 언더웨어 - 3개
            CategoryPair("10111", "언더웨어", "10111101", "여성"),
            CategoryPair("10111", "언더웨어", "10111102", "남성"),
            CategoryPair("10111", "언더웨어", "10111103", "홈웨어"),
        ]
        print(f"📋 하드코딩된 카테고리 {len(pairs)}개 사용 (depth1: 10개)")

    # Prepare base headers for subsequent API calls
    base_headers = {
        "content-type": "application/json",
        "origin": "https://display.wconcept.co.kr",
        "referer": "https://display.wconcept.co.kr/rn/best",
        "user-agent": captured_headers.get("user-agent", "Mozilla/5.0"),
    }
    
    return None, pairs, base_headers


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


def filter_products_by_brand(products: List[Dict[str, Any]], allowed_brands: List[str]) -> List[Dict[str, Any]]:
    if not products:
        return []
    allowed_exact_korean = {b.strip() for b in allowed_brands if b.strip() and not b.strip().isascii()}
    allowed_english_casefold = {b.strip().casefold() for b in allowed_brands if b.strip() and b.strip().isascii()}

    filtered: List[Dict[str, Any]] = []
    for p in products:
        brand = pick_brand(p).strip()
        if not brand:
            continue
        if brand in allowed_exact_korean:
            filtered.append(p)
            continue
        if brand.casefold() in allowed_english_casefold:
            filtered.append(p)
    return filtered


def fetch_products_for_category_page(
    headers: Dict[str, str],
    cat: CategoryPair,
    page_no: int,
    page_size: int,
    max_retries: int = 3,
) -> Tuple[List[Dict[str, Any]], Any]:
    payload = {
        "custNo": "0",
        "domain": "WOMEN",
        "genderType": "all",
        "dateType": "daily",
        "ageGroup": "all",
        "depth1Code": cat.depth1_code if cat.depth1_code != "ALL" else "",
        "depth2Code": cat.depth2_code if cat.depth2_code != "ALL" else "",
        "pageSize": page_size,
        "pageNo": page_no,
    }
    
    last_error = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(PRODUCT_ENDPOINT, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            products = extract_products_list(data)
            return products, data
        except requests.exceptions.HTTPError as e:
            last_error = e
            if e.response.status_code >= 500 and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                time.sleep(wait_time)
                continue
            raise
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise
    
    raise last_error if last_error else Exception("Unknown error")


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
    headers = ["날짜", "시간", "depth1_카테고리", "depth2_카테고리", "순위", "상품명", "가격"]
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

    try:
        api_key, categories, base_headers = get_api_key_and_categories()
    except Exception as e:
        print(f"❌ 카테고리 및 API 키 수집 중 오류 발생: {e}")
        raise

    kst_now = datetime.now(KST)
    date_str = kst_now.strftime("%Y-%m-%d")
    time_str = kst_now.strftime("%H:%M")

    rows: List[List[Any]] = []

    page_size = max(1, int(args.page_size))
    max_pages = max(0, int(args.max_pages))

    # bestCategories에 이미 ALL > 전체, depth1 > ALL이 모두 포함되어 있음
    # 추가 작업 없이 바로 사용
    print(f"🔍 총 {len(categories)}개 카테고리 조합 수집 시작...")
    
    # 모든 카테고리에서 HACIE 제품 수집
    hacie_found_per_category = {}
    
    for cat in categories:
        try:
            print(f"  📂 {cat.depth1_name or cat.depth1_code} > {cat.depth2_name or cat.depth2_code}")
            products = fetch_all_products_for_category(
                base_headers, cat, page_size=page_size, max_pages=max_pages
            )
        except Exception as e:
            print(f"     ❌ 오류: {e}")
            continue
        
        filtered = filter_products_by_brand(products, ALLOWED_BRANDS)
        
        # 카테고리별 HACIE 발견 카운트
        cat_key = f"{cat.depth1_name or cat.depth1_code} > {cat.depth2_name or cat.depth2_code}"
        hacie_found_per_category[cat_key] = len(filtered)
        
        if filtered:
            print(f"     ✅ HACIE {len(filtered)}개 발견")
        
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
    
    # 카테고리별 HACIE 발견 통계 출력
    print(f"\n📊 카테고리별 HACIE 제품 발견 현황:")
    for cat_key, count in sorted(hacie_found_per_category.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  {cat_key}: {count}개")

    if not rows:
        # Write empty CSV with headers for traceability
        out = write_csv([], output_dir)
        print(f"✅ CSV 생성 완료 (데이터 없음): {out}")
        return

    out = write_csv(rows, output_dir)
    print(f"✅ CSV 생성 완료: {out}")
    print(f"📊 총 {len(rows)}개 상품 수집됨")


if __name__ == "__main__":
    main()
