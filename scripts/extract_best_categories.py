#!/usr/bin/env python3
"""
W컨셉 베스트 페이지에서 bestCategories 데이터 추출
"""

import re
import json
from pathlib import Path

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def fetch_best_page_html() -> str:
    """
    W컨셉 베스트 페이지 HTML을 가져옵니다.
    
    Returns:
        HTML 문자열
    """
    if not REQUESTS_AVAILABLE:
        raise ImportError("requests 모듈이 필요합니다. pip install requests를 실행하세요.")
    
    url = 'https://display.wconcept.co.kr/rn/best'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text


def extract_next_data_from_html(html_content: str) -> dict:
    """
    Next.js 페이지에서 __NEXT_DATA__ 추출
    
    Args:
        html_content: HTML 문자열
        
    Returns:
        Next.js 데이터 딕셔너리
    """
    # <script id="__NEXT_DATA__"> 태그에서 JSON 추출
    pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
    match = re.search(pattern, html_content, re.DOTALL)
    
    if match:
        try:
            json_str = match.group(1)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 에러: {e}")
    
    return None


def extract_from_script_tags(html_content: str) -> dict:
    """
    <script> 태그에서 self.__next_f.push 데이터 추출
    
    Args:
        html_content: HTML 문자열
        
    Returns:
        추출된 데이터
    """
    # self.__next_f.push 패턴 찾기
    pattern = r'self\.__next_f\.push\(\[(.*?)\]\)'
    matches = re.findall(pattern, html_content, re.DOTALL)
    
    all_data = []
    for match in matches:
        try:
            # JSON 배열 파싱
            data = json.loads(f'[{match}]')
            all_data.append(data)
        except:
            continue
    
    # 모든 데이터에서 bestCategories 찾기
    for data_item in all_data:
        if len(data_item) > 1 and isinstance(data_item[1], str):
            # 문자열 안에서 bestCategories 찾기
            if 'bestCategories' in data_item[1]:
                # JSON 문자열 파싱 시도
                try:
                    # 이스케이프된 JSON 처리
                    json_str = data_item[1]
                    # bestCategories 부분만 추출
                    start = json_str.find('"bestCategories":')
                    if start != -1:
                        # 간단한 파싱: 중괄호 매칭
                        brace_count = 0
                        in_string = False
                        escape = False
                        
                        for i in range(start, len(json_str)):
                            char = json_str[i]
                            
                            if escape:
                                escape = False
                                continue
                                
                            if char == '\\':
                                escape = True
                                continue
                            
                            if char == '"' and not escape:
                                in_string = not in_string
                            
                            if not in_string:
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        # bestCategories 전체 추출
                                        categories_str = json_str[start:i+1]
                                        # "bestCategories": {...} 형태를 {..."bestCategories": {...}} 형태로 변환
                                        full_json = '{' + categories_str + '}'
                                        parsed = json.loads(full_json)
                                        return parsed.get('bestCategories')
                except Exception as e:
                    print(f"파싱 중 에러: {e}")
                    continue
    
    return None


def extract_best_categories_from_html(html_path: str = None, html_content: str = None) -> dict:
    """
    HTML에서 bestCategories 데이터 추출
    
    Args:
        html_path: HTML 파일 경로 (선택)
        html_content: HTML 문자열 (선택)
        
    Returns:
        bestCategories 데이터
    """
    if html_path:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    
    if not html_content:
        return None
    
    # 방법 1: __NEXT_DATA__ 스크립트에서 추출
    next_data = extract_next_data_from_html(html_content)
    if next_data:
        try:
            props = next_data.get('props', {})
            page_props = props.get('pageProps', {})
            initial_data = page_props.get('initialData', {})
            if 'bestCategories' in initial_data:
                return initial_data['bestCategories']
        except:
            pass
    
    # 방법 2: self.__next_f.push에서 추출
    categories = extract_from_script_tags(html_content)
    if categories:
        return categories
    
    return None


def find_network_requests(html_content: str) -> list:
    """
    HTML에서 네트워크 요청 URL 패턴 찾기
    
    Args:
        html_content: HTML 문자열
        
    Returns:
        발견된 URL 리스트
    """
    patterns = [
        r'https://[^"\'<>\s]+wconcept[^"\'<>\s]*',
        r'/api/[^"\'<>\s]+',
    ]
    
    urls = set()
    for pattern in patterns:
        matches = re.findall(pattern, html_content)
        urls.update(matches)
    
    return sorted(list(urls))


def main():
    """메인 함수"""
    print("=" * 80)
    print("W컨셉 베스트 페이지 분석")
    print("=" * 80)
    
    # 저장된 파일이 있으면 사용, 없으면 새로 가져오기
    html_file = Path(__file__).parent.parent / 'tmp_chunks' / 'category_example.html'
    
    if html_file.exists():
        print(f"\n[1] 저장된 HTML 파일 사용: {html_file}")
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    else:
        print("\n[1] W컨셉 베스트 페이지 가져오는 중...")
        try:
            html_content = fetch_best_page_html()
            print("✓ 페이지를 성공적으로 가져왔습니다.")
            
            # 임시 저장
            output_dir = Path(__file__).parent.parent / 'tmp_chunks'
            output_dir.mkdir(exist_ok=True)
            
            temp_file = output_dir / 'best_page_fetched.html'
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"✓ HTML 저장: {temp_file}")
        except Exception as e:
            print(f"✗ 페이지 가져오기 실패: {e}")
            return
    
    # bestCategories 추출
    print("\n[2] bestCategories 데이터 추출...")
    categories = extract_best_categories_from_html(html_content=html_content)
    
    if categories:
        print("✓ bestCategories 데이터를 찾았습니다!")
        
        category_list = categories.get('category1DepthList', [])
        print(f"\n1차 카테고리 개수: {len(category_list)}")
        
        # 결과 저장
        output_file = Path(__file__).parent.parent / 'tmp_wconcept_best_categories.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(categories, f, ensure_ascii=False, indent=2)
        print(f"✓ 저장 완료: {output_file}")
        
        # 카테고리 미리보기
        print("\n카테고리 구조:")
        for i, cat in enumerate(category_list[:5], 1):
            name = cat.get('depth1Name', 'N/A')
            code = cat.get('depth1Code', 'N/A')
            count = cat.get('depth1Count', 0)
            depth2_list = cat.get('category2DepthList') or []
            
            print(f"\n{i}. {name} ({code})")
            print(f"   - 상품 수: {count:,}개")
            print(f"   - 2차 카테고리: {len(depth2_list)}개")
            
            if depth2_list:
                for j, subcat in enumerate(depth2_list[:3], 1):
                    sub_name = subcat.get('depth2Name', 'N/A')
                    sub_count = subcat.get('depth2Count', 0)
                    print(f"     {j}) {sub_name}: {sub_count:,}개")
                
                if len(depth2_list) > 3:
                    print(f"     ... 외 {len(depth2_list) - 3}개")
        
        if len(category_list) > 5:
            print(f"\n... 외 {len(category_list) - 5}개 카테고리")
    else:
        print("✗ bestCategories 데이터를 찾지 못했습니다.")
        
        # 디버깅: 네트워크 요청 URL 확인
        print("\n[3] 관련 URL 패턴 검색...")
        urls = find_network_requests(html_content)
        
        if urls:
            print(f"✓ {len(urls)}개의 URL을 찾았습니다:")
            for url in urls[:15]:
                print(f"  - {url}")
            if len(urls) > 15:
                print(f"  ... 외 {len(urls) - 15}개")
        else:
            print("✗ 관련 URL을 찾지 못했습니다.")
    
    print("\n" + "=" * 80)
    print("분석 완료")
    print("=" * 80)


if __name__ == '__main__':
    main()

