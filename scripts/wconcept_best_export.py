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
CATEGORY_ENDPOINT_SUBSTR = "/display/api/best/v1/product"
PRODUCT_ENDPOINT = "https://gw-front.wconcept.co.kr/display/api/best/v1/product"
CATEGORY_CACHE_FILE = Path(__file__).parent.parent / "data" / "category.json"

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


def load_cached_categories() -> Optional[List[CategoryPair]]:
    """data/category.json에서 캐시된 카테고리 로드"""
    if not CATEGORY_CACHE_FILE.exists():
        return None
    
    try:
        with CATEGORY_CACHE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        pairs = []
        for item in data:
            pairs.append(CategoryPair(
                depth1_code=item["depth1_code"],
                depth1_name=item["depth1_name"],
                depth2_code=item["depth2_code"],
                depth2_name=item["depth2_name"]
            ))
        
        print(f"📂 캐시된 카테고리 로드: {len(pairs)}개 (from {CATEGORY_CACHE_FILE})")
        return pairs
    except Exception as e:
        print(f"⚠️ 캐시 로드 실패: {e}")
        return None


def save_categories_to_cache(pairs: List[CategoryPair]) -> None:
    """카테고리를 data/category.json에 저장"""
    CATEGORY_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    data = []
    for p in pairs:
        data.append({
            "depth1_code": p.depth1_code,
            "depth1_name": p.depth1_name,
            "depth2_code": p.depth2_code,
            "depth2_name": p.depth2_name
        })
    
    with CATEGORY_CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 카테고리 저장 완료: {len(pairs)}개 → {CATEGORY_CACHE_FILE}")


def categories_are_different(old_pairs: List[CategoryPair], new_pairs: List[CategoryPair]) -> bool:
    """두 카테고리 목록이 다른지 비교"""
    if len(old_pairs) != len(new_pairs):
        return True
    
    old_set = {(p.depth1_code, p.depth2_code) for p in old_pairs}
    new_set = {(p.depth1_code, p.depth2_code) for p in new_pairs}
    
    return old_set != new_set


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
    
    # 새로 추출한 카테고리와 캐시 비교
    if pairs:
        cached_pairs = load_cached_categories()
        
        if cached_pairs is None:
            # 캐시 없음 - 새로 저장
            save_categories_to_cache(pairs)
            print("✨ 최초 카테고리 캐시 생성")
        elif categories_are_different(cached_pairs, pairs):
            # 카테고리 변경됨
            print(f"🔄 카테고리 변경 감지: {len(cached_pairs)}개 → {len(pairs)}개")
            save_categories_to_cache(pairs)
            print("✅ 카테고리 캐시 업데이트 완료")
        else:
            print(f"✓ 카테고리 변경 없음 (동일: {len(pairs)}개)")
    
    # 동적 추출 실패 시 캐시 사용
    if not pairs:
        print("⚠️ 카테고리 동적 추출 실패, 캐시 로드 시도...")
        cached_pairs = load_cached_categories()
        if cached_pairs:
            pairs = cached_pairs
        else:
            print("❌ 캐시도 없음! 스크립트를 종료합니다.")
            raise Exception("카테고리를 가져올 수 없습니다. 네트워크를 확인하거나 수동으로 data/category.json을 생성하세요.")

    # Prepare base headers for subsequent API calls
    base_headers = {
        "accept": "*/*",
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/json; charset=utf-8",
        "display-api-key": "VWmkUPgs6g2fviPZ5JQFQ3pERP4tIXv/J2jppLqSRBk=",
        "devicetype": "PC",
        "membergrade": "8",
        "birthdate": "",
        "profileseqno": "",
        "origin": "https://display.wconcept.co.kr",
        "referer": "https://display.wconcept.co.kr/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": captured_headers.get("user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"),
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
    # finalPrice 우선 (최종가)
    for key in ("finalPrice", "salePrice", "price", "discountPrice", "sale_price", "customerPrice"):
        if key in product and isinstance(product[key], (int, float, str)):
            try:
                return int(float(str(product[key]).replace(",", "")))
            except Exception:
                continue
    return None


def pick_name(product: Dict[str, Any]) -> str:
    for key in ("itemName", "productName", "name", "goodsName", "title"):
        if key in product and product[key]:
            return str(product[key])
    return ""


def pick_brand(product: Dict[str, Any]) -> str:
    # 한글 브랜드명 우선
    for key in ("brandNameKr", "brandNameKor", "brandKr"):
        if key in product and product[key]:
            return str(product[key])
    # 영문 브랜드명
    for key in ("brandNameEn", "brandNameEng", "brandEn", "brandName", "brand", "brand_name"):
        if key in product and product[key]:
            return str(product[key])
    return ""


def pick_rank(idx: int, product: Dict[str, Any]) -> int:
    """순위 추출 - 원래 순위(_original_rank) 우선 사용"""
    # 필터링 전 저장된 원래 순위 사용
    if '_original_rank' in product:
        return int(product['_original_rank'])
    
    # API 응답에서 순위 필드 확인
    for key in ("rank", "ranking", "bestOrder", "exposeOrder", "order"):
        if key in product:
            try:
                return int(product[key])
            except Exception:
                continue
    
    # 마지막 fallback: 현재 인덱스 + 1
    return idx + 1


def pick_url(product: Dict[str, Any]) -> str:
    """상품 URL 추출"""
    # landingUrl 또는 직접 URL 필드
    for key in ("landingUrl", "productUrl", "url", "link", "itemUrl"):
        if key in product and product[key]:
            url = str(product[key])
            if url.startswith("http"):
                return url
            elif url.startswith("/"):
                return f"https://www.wconcept.co.kr{url}"
    
    # itemCd, productNo로 URL 생성
    item_cd = product.get("itemCd") or product.get("productNo") or product.get("itemNo") or product.get("goodsNo")
    if item_cd:
        return f"https://www.wconcept.co.kr/product/{item_cd}"
    
    return ""


def filter_products_by_brand(products: List[Dict[str, Any]], allowed_brands: List[str]) -> List[Dict[str, Any]]:
    """브랜드로 필터링하고 원래 순위(인덱스) 저장"""
    if not products:
        return []
    allowed_exact_korean = {b.strip() for b in allowed_brands if b.strip() and not b.strip().isascii()}
    allowed_english_casefold = {b.strip().casefold() for b in allowed_brands if b.strip() and b.strip().isascii()}

    filtered: List[Dict[str, Any]] = []
    for idx, p in enumerate(products):
        brand = pick_brand(p).strip()
        if not brand:
            continue
        
        # 원래 순위(배열 인덱스 + 1) 저장
        # API 응답에 순위 필드가 없으므로 배열 순서가 곧 순위
        if '_original_rank' not in p:
            p['_original_rank'] = idx + 1
        
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


def write_csv(rows: List[List[Any]], output_dir: Path, timestamp: datetime) -> Tuple[Path, str]:
    """CSV 파일 작성 및 타임스탬프 반환"""
    # KST 기준 날짜별 폴더 생성: output/YYYY/MM/DD/
    year = timestamp.strftime('%Y')
    month = timestamp.strftime('%m')
    day = timestamp.strftime('%d')
    date_dir = output_dir / year / month / day
    date_dir.mkdir(parents=True, exist_ok=True)
    
    # 파일명: yyMMdd_hhmmss.csv
    time_suffix = timestamp.strftime('%y%m%d_%H%M%S')
    filename = f"wconcept_best_{time_suffix}.csv"
    out_path = date_dir / filename
    
    headers = ["날짜", "시간", "브랜드명", "depth1_카테고리", "depth2_카테고리", "순위", "상품명", "가격", "상품URL"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    
    return out_path, time_suffix


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
    parser.add_argument(
        "--skip-category-update",
        action="store_true",
        help="카테고리 업데이트 건너뛰고 캐시만 사용 (빠름)",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="테스트 모드: 처음 3개 카테고리만 수집",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # 카테고리 로드
    if args.skip_category_update:
        # 빠른 모드: 캐시 우선 사용
        print("⚡ 빠른 모드: 캐시된 카테고리 우선 사용")
        categories = load_cached_categories()
        
        if not categories:
            # 캐시 없음 - Playwright로 추출
            print("📂 캐시 없음, Playwright로 카테고리 추출 시도...")
            try:
                api_key, categories, base_headers = get_api_key_and_categories()
            except Exception as e:
                print(f"❌ 카테고리 수집 실패: {e}")
                raise
        else:
            # 캐시 사용 - 헤더만 설정
            base_headers = {
                "accept": "*/*",
                "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "content-type": "application/json; charset=utf-8",
                "display-api-key": "VWmkUPgs6g2fviPZ5JQFQ3pERP4tIXv/J2jppLqSRBk=",
                "devicetype": "PC",
                "membergrade": "8",
                "birthdate": "",
                "profileseqno": "",
                "origin": "https://display.wconcept.co.kr",
                "referer": "https://display.wconcept.co.kr/",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            }
    else:
        # 정상 모드: Playwright로 카테고리 업데이트
        try:
            api_key, categories, base_headers = get_api_key_and_categories()
        except Exception as e:
            print(f"❌ 카테고리 수집 중 오류: {e}")
            raise

    kst_now = datetime.now(KST)
    date_str = kst_now.strftime("%Y-%m-%d")
    time_str = kst_now.strftime("%H:%M")

    rows: List[List[Any]] = []

    page_size = max(1, int(args.page_size))
    max_pages = max(0, int(args.max_pages))

    # 테스트 모드인 경우 카테고리 제한
    test_categories = categories[:3] if args.test_mode else categories
    
    if args.test_mode:
        print(f"🧪 테스트 모드: {len(test_categories)}개 카테고리만 수집")
    else:
        print(f"🔍 총 {len(test_categories)}개 카테고리 조합 수집 시작...")
    
    # 모든 카테고리에서 HACIE 제품 수집
    hacie_found_per_category = {}
    
    for cat in test_categories:
        try:
            print(f"  📂 {cat.depth1_name or cat.depth1_code} > {cat.depth2_name or cat.depth2_code}")
            products = fetch_all_products_for_category(
                base_headers, cat, page_size=page_size, max_pages=max_pages
            )
            print(f"     📦 총 {len(products)}개 상품 수집됨")
            
            # 디버깅: 첫 3개 상품의 브랜드 출력
            if products and args.test_mode:
                for idx, p in enumerate(products[:3]):
                    brand = pick_brand(p)
                    name = pick_name(p)
                    print(f"       #{idx+1}: {brand} - {name[:30]}")
                    
        except Exception as e:
            print(f"     ❌ 오류: {e}")
            continue
        
        filtered = filter_products_by_brand(products, ALLOWED_BRANDS)
        
        # 카테고리별 HACIE 발견 카운트
        cat_key = f"{cat.depth1_name or cat.depth1_code} > {cat.depth2_name or cat.depth2_code}"
        hacie_found_per_category[cat_key] = len(filtered)
        
        if filtered:
            print(f"     ✅ HACIE {len(filtered)}개 발견")
            for idx, p in enumerate(filtered[:3]):
                name = pick_name(p)
                rank = pick_rank(idx, p)
                print(f"       - {rank}위: {name[:40]}")
        
        for idx, p in enumerate(filtered):
            rank = pick_rank(idx, p)
            brand = pick_brand(p)
            name = pick_name(p)
            price = pick_price(p)
            url = pick_url(p)
            rows.append(
                [
                    date_str,
                    time_str,
                    brand,
                    cat.depth1_name or cat.depth1_code,
                    cat.depth2_name or cat.depth2_code,
                    rank,
                    name,
                    price if price is not None else "",
                    url,
                ]
            )
    
    # 카테고리별 HACIE 발견 통계 출력
    print(f"\n📊 카테고리별 HACIE 제품 발견 현황:")
    for cat_key, count in sorted(hacie_found_per_category.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  {cat_key}: {count}개")

    if not rows:
        # Write empty CSV with headers for traceability
        out, time_suffix = write_csv([], output_dir, kst_now)
        print(f"✅ CSV 생성 완료 (데이터 없음): {out}")
        print(f"⏰ 타임스탬프: {time_suffix}")
        return

    out, time_suffix = write_csv(rows, output_dir, kst_now)
    print(f"✅ CSV 생성 완료: {out}")
    print(f"📊 총 {len(rows)}개 상품 수집됨")
    print(f"⏰ 타임스탬프: {time_suffix}")


if __name__ == "__main__":
    main()
