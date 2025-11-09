#!/usr/bin/env python3
"""
HACIE 브랜드 주간/월간 통계 리포트 생성
"""

import json
import csv
import os
import re
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
from collections import defaultdict
import statistics
from zoneinfo import ZoneInfo


class HacieReportGenerator:
    """HACIE 통계 리포트 생성기"""
    
    def __init__(self, output_dir: Path = None):
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / 'output'
        self.output_dir = output_dir
    
    @staticmethod
    def _get_product_key(product: Dict) -> Optional[str]:
        """상품을 대표할 고유 키 추출"""
        return (
            product.get('상품URL')
            or product.get('productUrl')
            or product.get('상품ID')
            or product.get('productId')
            or product.get('상품명')
            or product.get('productName')
        )

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[date]:
        """문자열을 날짜 객체로 변환"""
        if not date_str:
            return None

        for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _is_earlier_date(candidate: Optional[date], current: Optional[date]) -> bool:
        """두 날짜 중 앞선 날짜인지 확인"""
        if candidate is None:
            return False
        if current is None:
            return True
        return candidate < current

    @staticmethod
    def _parse_int_value(value) -> Optional[int]:
        """숫자 형태 문자열을 정수로 변환"""
        if value in (None, ''):
            return None
        try:
            return int(str(value).replace(',', '').strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_price(value: Optional[int]) -> str:
        """가격 문자열 포맷"""
        if value is None:
            return "N/A"
        try:
            return f"₩{int(value):,}"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def _format_date_label(value: Optional[date]) -> str:
        """리포트 출력용 날짜 문자열"""
        if not value:
            return "-"
        return value.strftime('%Y-%m-%d')

    def _extract_price_from_product(self, product: Optional[Dict]) -> Optional[int]:
        """상품 데이터에서 가격 정보 추출"""
        if not product:
            return None
        return self._parse_int_value(product.get('가격') or product.get('salePrice'))

    @staticmethod
    def _parse_discount_value(value) -> Optional[float]:
        """값을 퍼센트 숫자(float)로 변환"""
        if value in (None, '', '-', 'N/A'):
            return None

        if isinstance(value, (int, float)):
            number = float(value)
        else:
            text = str(value).strip()
            if not text:
                return None

            cleaned = re.sub(r"[^0-9.\-]", "", text)
            if not cleaned or cleaned in ('-', '.', '-.'):
                return None

            try:
                number = float(cleaned)
            except ValueError:
                return None

        if number < 0:
            return None

        if number <= 1:
            number *= 100

        return number

    @classmethod
    def _normalize_discount_value(cls, value) -> Optional[str]:
        """표준화된 할인율 문자열 반환"""
        number = cls._parse_discount_value(value)
        if number is None:
            return None

        rounded = round(number, 1)
        if abs(rounded - round(rounded)) < 1e-6:
            rounded = round(rounded)
        return f"{rounded:g}%"

    def _extract_discount_from_product(self, product: Optional[Dict]) -> Optional[str]:
        """상품 데이터에서 할인율 추출"""
        if not product:
            return None

        keys = (
            '할인율',
            'discountRate',
            'discount_rate',
            'saleRate',
            'sale_rate',
            'discountRateText',
            'saleRateText',
            'discountText',
            'discount_rate_text',
        )

        for key in keys:
            if key not in product:
                continue
            normalized = self._normalize_discount_value(product.get(key))
            if normalized:
                return normalized

        return None

    @staticmethod
    def _format_discount(discount: Optional[str]) -> str:
        """할인율 표시 형식"""
        if discount in (None, '', '-'):  # 빈 값 처리
            return "0%"

        value = str(discount).strip()
        normalized = HacieReportGenerator._normalize_discount_value(value)
        if normalized:
            return normalized

        cleaned = value.replace('%', '')
        if cleaned:
            return f"{cleaned}%"
        return "0%"

    def _resolve_entry_discount(self, entry: Dict) -> Optional[str]:
        """집계 엔트리에서 표시용 할인율 추출"""
        candidates = [entry.get('discount')]

        best_record = entry.get('best_record') or {}
        candidates.extend([
            best_record.get('할인율'),
            best_record.get('discountRate'),
            best_record.get('discount_rate'),
        ])

        for record in entry.get('records', []):
            candidates.append(record.get('discount'))

        for candidate in candidates:
            normalized = self._normalize_discount_value(candidate)
            if normalized:
                return normalized

        return None

    @staticmethod
    def _compose_category(depth1: Optional[str], depth2: Optional[str], separator: str = " - ") -> str:
        """상/하위 카테고리 결합"""
        name1 = (depth1 or '').strip()
        name2 = (depth2 or '').strip()

        if name1 and name2 and name1.lower() == name2.lower():
            name2 = ''

        parts: List[str] = []
        if name1:
            parts.append(name1)
        if name2:
            parts.append(name2)

        if parts:
            return separator.join(parts)
        return "N/A"

    def _relative_path_string(self, target_path: Optional[Path], current_dir: Path) -> Optional[str]:
        """현재 리포트 디렉터리 기준 상대 경로 계산"""
        if not target_path:
            return None

        try:
            relative = os.path.relpath(target_path, current_dir)
        except ValueError:
            return None

        relative = relative.replace(os.sep, '/')
        if not relative.startswith('.') and not relative.startswith('/'):
            relative = f"./{relative}"
        return relative

    def _format_link(self, label: str, target_path: Optional[Path], current_dir: Path) -> str:
        """마크다운 링크 생성"""
        relative = self._relative_path_string(target_path, current_dir)
        if not relative:
            return "-"
        return f"[{label}]({relative})"

    def _resolve_daily_markdown_path(self, source_csv: Optional[str]) -> Optional[Path]:
        """CSV 파일 경로에서 일일 리포트 마크다운 경로 추정"""
        if not source_csv:
            return None

        csv_path = Path(source_csv)
        if not csv_path.is_absolute():
            csv_path = self.output_dir / csv_path

        md_name = csv_path.name.replace('wconcept_best_', '일일_요약_').replace('.csv', '.md')
        return csv_path.parent / md_name

    def _resolve_weekly_markdown_path(self, year: int, month: int, week_num: int) -> Path:
        """주간 리포트 마크다운 경로 추정"""
        base_dir = self.output_dir / str(year) / f"{month:02d}"
        filename = f"{year}년_{month:02d}월_{week_num}주차_통계.md"
        return base_dir / filename

    def _price_display_from_entry(self, entry: Dict) -> str:
        """집계된 상품 정보에서 표시용 가격 문자열 산출"""
        price_str = self._format_price(entry.get('price'))
        if price_str != "N/A":
            return price_str

        best_record = entry.get('best_record') or {}
        raw_price = best_record.get('가격') or best_record.get('salePrice')
        parsed_price = self._parse_int_value(raw_price)
        if parsed_price is not None:
            return self._format_price(parsed_price)
        return raw_price if raw_price else "N/A"

    def _price_value_from_entry(self, entry: Dict) -> str:
        """CSV용 숫자 가격 값 산출"""
        price_value = entry.get('price')
        if price_value is not None:
            return str(price_value)

        best_record = entry.get('best_record') or {}
        raw_price = best_record.get('가격') or best_record.get('salePrice')
        parsed_price = self._parse_int_value(raw_price)
        if parsed_price is not None:
            return str(parsed_price)
        return raw_price or ''

    def _aggregate_product_performance(self, products: List[Dict]) -> Dict[str, Dict]:
        """상품별 최고 순위 및 기록일 집계"""
        aggregated: Dict[str, Dict] = {}

        for product in products:
            key = self._get_product_key(product)
            if not key:
                continue

            rank_raw = product.get('순위') or product.get('rank')
            try:
                rank = int(str(rank_raw).strip())
            except (TypeError, ValueError):
                continue

            record_date = self._parse_date(product.get('날짜') or product.get('date'))

            entry = aggregated.get(key)

            if entry is None:
                entry = {
                    'name': product.get('상품명') or product.get('productName', 'N/A'),
                    'url': product.get('상품URL') or product.get('productUrl', ''),
                    'category_depth1': product.get('depth1_카테고리') or product.get('depth1_name', ''),
                    'category_depth2': product.get('depth2_카테고리') or product.get('depth2_name', ''),
                    'price': self._extract_price_from_product(product),
                    'discount': self._extract_discount_from_product(product),
                    'sale_tag': product.get('세일태그', ''),
                    'info_tags': product.get('정보태그', ''),
                    'review_count': self._parse_int_value(product.get('리뷰수', 0)),
                    'heart_count': self._parse_int_value(product.get('찜수', 0)),
                    'review_score': float(product.get('리뷰평점', 0)) if product.get('리뷰평점') else 0.0,
                    'is_today_delivery': product.get('당일배송', 'N'),
                    'best_rank': rank,
                    'best_rank_date': record_date,
                    'best_record': product,
                    'best_source_csv': product.get('__source_csv__'),
                    'records': []
                }
                aggregated[key] = entry

            entry['records'].append({
                'rank': rank,
                'date': record_date,
                'source_csv': product.get('__source_csv__'),
                'discount': self._extract_discount_from_product(product),
                'price': self._extract_price_from_product(product),
                'product': product
            })

            best_rank = entry['best_rank']
            best_date = entry['best_rank_date']

            if rank < best_rank or (rank == best_rank and self._is_earlier_date(record_date, best_date)):
                entry['name'] = product.get('상품명') or product.get('productName', 'N/A')
                entry['url'] = product.get('상품URL') or product.get('productUrl', '')
                entry['category_depth1'] = product.get('depth1_카테고리') or product.get('depth1_name', '')
                entry['category_depth2'] = product.get('depth2_카테고리') or product.get('depth2_name', '')
                entry['price'] = self._extract_price_from_product(product)
                entry['discount'] = self._extract_discount_from_product(product) or entry.get('discount')
                entry['best_rank'] = rank
                entry['best_rank_date'] = record_date
                entry['best_record'] = product
                entry['best_source_csv'] = product.get('__source_csv__')

        return aggregated

    def find_csv_files(self, start_date: datetime, end_date: datetime) -> List[Path]:
        """날짜 범위 내의 CSV 파일 찾기 (각 날짜별 최신 파일만)"""
        csv_files = []
        
        current_date = start_date
        while current_date <= end_date:
            year = current_date.strftime('%Y')
            month = current_date.strftime('%m')
            day = current_date.strftime('%d')
            
            # yyyy/MM/dd 폴더 구조
            date_folder = self.output_dir / year / month / day
            
            if date_folder.exists():
                # 해당 날짜의 모든 CSV 파일 찾기
                day_csv_files = list(date_folder.glob('wconcept_best_*.csv'))
                
                if day_csv_files:
                    # 파일명으로 정렬하여 가장 최신(시간이 가장 늦은) 파일만 선택
                    # 파일명 형식: wconcept_best_yyMMdd_HHMMSS.csv
                    # 파일명 순으로 정렬하면 자동으로 시간순 정렬됨
                    latest_file = sorted(day_csv_files, reverse=True)[0]
                    csv_files.append(latest_file)
            
            current_date += timedelta(days=1)
        
        return sorted(csv_files)
    
    def parse_csv(self, csv_file: Path) -> List[Dict]:
        """CSV 파일 파싱"""
        products = []
        try:
            source_csv_path = str(csv_file.relative_to(self.output_dir))
        except ValueError:
            source_csv_path = str(csv_file)
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                total_rows = 0
                hacie_rows = 0
                
                for row in reader:
                    total_rows += 1
                    row_data = dict(row)
                    row_data['__source_csv__'] = source_csv_path
                    
                    # 브랜드명 필드
                    brand_name = row_data.get('브랜드명') or row_data.get('brandName') or ''
                    
                    # HACIE 브랜드 필터링
                    if brand_name and ('HACIE' in brand_name.upper() or '하시에' in brand_name):
                        products.append(row_data)
                        hacie_rows += 1
                    else:
                        # 브랜드 필드 없으면 상품명에서 확인
                        product_name = row_data.get('상품명') or row_data.get('productName') or ''
                        if product_name and ('HACIE' in product_name.upper() or '하시에' in product_name):
                            products.append(row_data)
                            hacie_rows += 1
                
                print(f"📊 CSV 통계: 전체 {total_rows}개 행, HACIE 제품 {hacie_rows}개 발견")
                
                if total_rows == 0:
                    print("⚠️ CSV 파일에 데이터 행이 없습니다 (헤더만 존재)")
                    
        except Exception as e:
            print(f"❌ CSV 파싱 에러 ({csv_file}): {e}")
            import traceback
            traceback.print_exc()
        
        return products
    
    def generate_weekly_report(self, year: int, month: int, week_num: int) -> Optional[Dict[str, str]]:
        """주간 리포트 생성"""
        # 해당 주의 날짜 범위 계산 (월요일 시작)
        first_day = datetime(year, month, 1)
        first_week_start = first_day - timedelta(days=first_day.weekday())
        start_date = first_week_start + timedelta(weeks=week_num - 1)
        end_date = start_date + timedelta(days=6)
        
        csv_files = self.find_csv_files(start_date, end_date)
        
        if not csv_files:
            return None
        
        # 데이터 수집
        all_products = []
        daily_stats = {}
        file_links = []
        
        for csv_file in csv_files:
            products = self.parse_csv(csv_file)
            all_products.extend(products)

            # 날짜별 통계
            try:
                year_dir = int(csv_file.parent.parent.parent.name)
                month_dir = int(csv_file.parent.parent.name)
                day_dir = int(csv_file.parent.name)
                file_date = date(year_dir, month_dir, day_dir)
            except (AttributeError, ValueError):
                file_date = self._parse_date(products[0].get('날짜') if products else None) or start_date.date()

            daily_stats[file_date] = len(products)

            # GitHub 링크 생성
            relative_path = csv_file.relative_to(self.output_dir)
            github_link = f"https://github.com/kaae/best_item_crawl/blob/master/output/{relative_path}"
            file_links.append((file_date, csv_file.name, github_link))
        
        # 통계 계산
        total_products = len(all_products)
        total_days = len(csv_files)
        avg_per_day = total_products / total_days if total_days > 0 else 0
        
        # 카테고리별 집계
        category_stats = defaultdict(lambda: {'count': 0, 'ranks': [], 'depth': ()})
        for product in all_products:
            # CSV 필드명 매핑
            depth1 = (product.get('depth1_카테고리') or product.get('depth1_name') or 'N/A').strip()
            depth2 = (product.get('depth2_카테고리') or product.get('depth2_name') or '').strip()
            cat_key = (depth1, depth2)
            category_stats[cat_key]['count'] += 1
            category_stats[cat_key]['depth'] = cat_key
            try:
                # CSV 필드명 매핑
                rank = int(product.get('순위') or product.get('rank', 999))
                category_stats[cat_key]['ranks'].append(rank)
            except:
                pass
        
        # 상품별 최고 순위 집계
        product_performance = self._aggregate_product_performance(all_products)

        # 리포트 저장 디렉터리
        report_dir = self.output_dir / str(year) / f"{month:02d}"

        # 베스트 순위 상품
        top_products = sorted(
            product_performance.values(),
            key=lambda x: (x['best_rank'], x['best_rank_date'] or date.max)
        )[:10]
        
        # 리포트 생성
        report = f"""# 📊 HACIE 브랜드 주간 통계 리포트

**기간:** {start_date.strftime('%Y년 %m월 %d일')} ~ {end_date.strftime('%Y년 %m월 %d일')} ({year}년 {month}월 {week_num}주차)

## 📈 주간 요약

- **총 발견 상품:** {total_products}개
- **분석 일수:** {total_days}일
- **일평균 상품 수:** {avg_per_day:.1f}개

## 📅 일별 통계

| 날짜 | 발견 상품 수 |
|------|------------:|
"""
        
        for record_date, count in sorted(daily_stats.items()):
            report += f"| {record_date.strftime('%m월 %d일')} | {count}개 |\n"
        
        report += f"""
## 🏆 카테고리별 통계

| 카테고리 | 발견 횟수 | 평균 순위 | 최고 순위 |
|---------|--------:|--------:|--------:|
"""
        
        for cat_key, stats in sorted(category_stats.items(), key=lambda x: -x[1]['count'])[:10]:
            cat_name = self._compose_category(*(stats.get('depth') or cat_key))
            count = stats['count']
            ranks = stats['ranks']
            avg_rank = statistics.mean(ranks) if ranks else 0
            best_rank = min(ranks) if ranks else 0
            report += f"| {cat_name} | {count}회 | {avg_rank:.1f}위 | {best_rank}위 |\n"
        
        report += f"""
## 🌟 주간 베스트 TOP 10

| 순위 | 최고 순위 | 달성일 | 상품명 | 카테고리 | 가격 | 할인율 | 세일 | 리뷰 | 찜 | 평점 | 링크 |
|:----:|---------:|:------:|--------|---------|-----:|------:|-----|----:|---:|:---:|:----:|
"""

        for idx, product in enumerate(top_products, 1):
            name = product.get('name', 'N/A')
            url = product.get('url', '')
            category = self._compose_category(product.get('category_depth1'), product.get('category_depth2'))

            if len(name) > 40:
                name = name[:40] + '...'
            if url and url.startswith('http'):
                name = f"[{name}]({url})"

            price_str = self._price_display_from_entry(product)
            best_rank = product.get('best_rank')
            best_rank_text = f"{best_rank}위" if best_rank is not None else "-"
            best_date_text = self._format_date_label(product.get('best_rank_date'))
            discount_value = self._resolve_entry_discount(product)
            discount_text = self._format_discount(discount_value)
            
            # 추가 정보
            sale_tag = product.get('sale_tag', '-')
            review_count = product.get('review_count', 0)
            heart_count = product.get('heart_count', 0)
            review_score = product.get('review_score', 0.0)
            
            review_str = f"{review_count}" if review_count and review_count > 0 else "-"
            heart_str = f"{heart_count}" if heart_count and heart_count > 0 else "-"
            score_str = f"{review_score:.1f}" if review_score and review_score > 0 else "-"
            
            daily_md_path = self._resolve_daily_markdown_path(product.get('best_source_csv'))
            link_markdown = self._format_link('일일 리포트', daily_md_path, report_dir)

            report += f"| {idx} | {best_rank_text} | {best_date_text} | {name} | {category} | {price_str} | {discount_text} | {sale_tag} | {review_str} | {heart_str} | {score_str} | {link_markdown} |\n"
        
        report += f"""
## 💡 주간 인사이트

### 성과 분석
"""
        
        # 자동 인사이트 생성
        if avg_per_day >= 10:
            report += "- ✅ **우수한 성과**: 일평균 10개 이상의 HACIE 상품이 베스트 순위에 진입했습니다.\n"
        elif avg_per_day >= 5:
            report += "- ✔️ **양호한 성과**: 일평균 5개 이상의 상품이 베스트 진입을 유지하고 있습니다.\n"
        else:
            report += "- ⚠️ **개선 필요**: 베스트 진입 상품 수가 감소했습니다. 마케팅 강화가 필요합니다.\n"
        
        # 카테고리 인사이트
        if category_stats:
            top_category_key, top_category_stats = max(category_stats.items(), key=lambda x: x[1]['count'])
            top_category_name = self._compose_category(*(top_category_stats.get('depth') or top_category_key))
            report += f"- 🎯 **주력 카테고리**: {top_category_name} ({top_category_stats['count']}회 진입)\n"
        
        # 리뷰/찜 통계
        products_with_reviews = [p for p in product_performance.values() if p.get('review_count', 0) > 0]
        if products_with_reviews:
            avg_reviews = sum(p.get('review_count', 0) for p in products_with_reviews) / len(products_with_reviews)
            avg_hearts = sum(p.get('heart_count', 0) for p in products_with_reviews) / len(products_with_reviews)
            report += f"- 💬 **평균 리뷰 수**: {avg_reviews:.0f}개 | 평균 찜 수: {avg_hearts:.0f}개\n"
        
        # 세일 태그 통계
        sale_tag_counts = {}
        for p in all_products:
            sale_tag = p.get('세일태그', '')
            if sale_tag and sale_tag != '-':
                sale_tag_counts[sale_tag] = sale_tag_counts.get(sale_tag, 0) + 1
        if sale_tag_counts:
            top_sale = max(sale_tag_counts.items(), key=lambda x: x[1])
            report += f"- 🏷️ **주요 세일**: {top_sale[0]} ({top_sale[1]}건)\n"
        
        report += f"""
### 추천 액션
- 주간 베스트 상품 SNS 공유
- 성과 좋은 카테고리 집중 마케팅
- 저조한 카테고리 프로모션 검토

---

## 📎 참고 데이터 파일

| 날짜 | 파일명 |
|------|--------|
"""
        
        for record_date, filename, link in sorted(file_links):
            report += f"| {record_date.strftime('%m월 %d일')} | [{filename}]({link}) |\n"
        
        report += f"""
---

*생성 일시: {datetime.now(ZoneInfo("Asia/Seoul")).strftime('%Y-%m-%d %H:%M:%S')} KST*  
*데이터 출처: W컨셉 베스트 페이지*
"""
        
        # CSV 생성
        csv_data = []
        
        # 1. 일별 통계
        for record_date, count in sorted(daily_stats.items()):
            csv_data.append({
                '유형': '일별통계',
                '날짜': record_date.strftime('%Y-%m-%d'),
                '상품수': count,
                '카테고리': '',
                '평균순위': '',
                '최고순위': '',
                '상품명': ''
            })
        
        # 2. 카테고리별 통계
        for cat_key, stats in sorted(category_stats.items(), key=lambda x: -x[1]['count']):
            cat_name = self._compose_category(*(stats.get('depth') or cat_key))
            ranks = stats['ranks']
            avg_rank = statistics.mean(ranks) if ranks else 0
            best_rank = min(ranks) if ranks else 0
            
            csv_data.append({
                '유형': '카테고리통계',
                '날짜': '',
                '상품수': stats['count'],
                '카테고리': cat_name,
                '평균순위': f"{avg_rank:.1f}",
                '최고순위': str(best_rank),
                '상품명': ''
            })
        
        # 3. TOP 상품
        for idx, product in enumerate(top_products, 1):
            depth1 = product.get('category_depth1') or ''
            depth2 = product.get('category_depth2') or ''
            category = self._compose_category(depth1, depth2)
            best_rank = product.get('best_rank')
            best_date_text = self._format_date_label(product.get('best_rank_date'))
            discount_value = self._resolve_entry_discount(product)
            daily_md_path = self._resolve_daily_markdown_path(product.get('best_source_csv'))
            link_path = self._relative_path_string(daily_md_path, report_dir) or ''

            csv_data.append({
                '유형': f'TOP{idx}',
                '날짜': '',
                '상품수': '',
                '카테고리': category,
                '평균순위': '',
                '최고순위': str(best_rank) if best_rank is not None else '',
                '기록일': best_date_text,
                '가격': self._price_value_from_entry(product),
                '할인율': self._format_discount(discount_value),
                '세일태그': product.get('sale_tag', ''),
                '리뷰수': str(product.get('review_count', 0)),
                '찜수': str(product.get('heart_count', 0)),
                '평점': f"{product.get('review_score', 0):.1f}" if product.get('review_score', 0) > 0 else '',
                '상품명': product.get('name', 'N/A'),
                '링크': link_path
            })
        
        # CSV 문자열 생성
        if csv_data:
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=['유형', '날짜', '상품수', '카테고리', '평균순위', '최고순위', '기록일', '가격', '할인율', '세일태그', '리뷰수', '찜수', '평점', '상품명', '링크'])
            writer.writeheader()
            writer.writerows(csv_data)
            csv_content = output.getvalue()
        else:
            csv_content = ""
        
        return {
            'markdown': report,
            'csv': csv_content
        }
    
    def generate_daily_report(self, csv_file_path: Path) -> Optional[Dict[str, str]]:
        """일일 리포트 생성"""
        if not csv_file_path.exists():
            print(f"❌ CSV 파일이 존재하지 않습니다: {csv_file_path}")
            return None
        
        # CSV 파일 파싱
        try:
            products = self.parse_csv(csv_file_path)
            hacie_count = len(products)
            print(f"✓ CSV 파싱 완료: {hacie_count}개의 HACIE 상품 발견")
        except Exception as e:
            print(f"❌ CSV 파싱 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        # 파일 정보 추출
        csv_name = csv_file_path.name
        
        # GitHub 링크 생성
        try:
            relative_path = csv_file_path.relative_to(self.output_dir)
            github_link = f"https://github.com/kaae/best_item_crawl/blob/master/output/{relative_path}"
        except:
            github_link = None
        
        # 현재 시각 (KST)
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        kst_time = now.strftime('%Y-%m-%d %H:%M:%S')
        
        # 리포트 생성
        if github_link:
            csv_file_text = f"[`{csv_name}`]({github_link})"
        else:
            csv_file_text = f"`{csv_name}`"
        
        report = f"""# 📊 일일 요약

**분석 시각:** {kst_time} KST  
**데이터 파일:** {csv_file_text}  
**발견된 HACIE 상품:** {hacie_count}개

---

## 📋 상위 10개 상품

"""
        
        if hacie_count > 0:
            # 테이블 헤더
            report += """| 순위 | 카테고리 | 상품명 | 가격 | 할인율 | 세일태그 | 리뷰 | 찜 | 평점 | 배송 |
|:----:|---------|--------|-----:|------:|---------|-----:|----:|:----:|:----:|
"""
            
            # 상위 10개 상품
            for idx, product in enumerate(products[:10], 1):
                rank = product.get('순위') or product.get('rank', '-')
                category = product.get('depth2_카테고리') or product.get('depth2_name', '-')
                name = product.get('상품명') or product.get('productName', '-')
                url = product.get('상품URL') or product.get('productUrl', '')
                
                # 상품명 길이 제한
                if len(name) > 50:
                    name = name[:50] + '...'
                
                # 상품명에 링크 추가
                if url and url.startswith('http'):
                    name = f"[{name}]({url})"
                
                # 가격 포맷팅
                try:
                    price = int(product.get('가격') or product.get('salePrice', 0))
                    price_str = f"₩{price:,}"
                except:
                    price_str = product.get('가격') or product.get('salePrice', '-')
                
                # 할인율 포맷팅
                discount = product.get('할인율') or product.get('discountRate', '')
                discount_str = self._format_discount(discount) if discount else '-'
                
                # 추가 정보
                sale_tag = product.get('세일태그', '-')
                info_tags = product.get('정보태그', '')
                if info_tags:
                    tags_list = info_tags.split(',')[:2]
                    sale_tag = f"{sale_tag}<br>{'·'.join(tags_list)}" if sale_tag != '-' else '·'.join(tags_list)
                
                review_cnt = product.get('리뷰수', 0)
                heart_cnt = product.get('찜수', 0)
                review_score = product.get('리뷰평점', '')
                is_today = product.get('당일배송', 'N')
                
                # 리뷰수, 찜수 포맷팅
                try:
                    review_cnt = int(review_cnt) if review_cnt else 0
                    heart_cnt = int(heart_cnt) if heart_cnt else 0
                except:
                    review_cnt = 0
                    heart_cnt = 0
                
                review_str = f"{review_cnt}" if review_cnt > 0 else "-"
                heart_str = f"{heart_cnt}" if heart_cnt > 0 else "-"
                score_str = f"{review_score}" if review_score else "-"
                delivery_str = "당일" if is_today == 'Y' else "-"
                
                report += f"| {rank} | {category} | {name} | {price_str} | {discount_str} | {sale_tag} | {review_str} | {heart_str} | {score_str} | {delivery_str} |\n"
            
            # 전체 상품 목록
            report += f"""
---

## 📦 전체 HACIE 상품 목록

<details>
<summary>펼쳐서 보기 (전체 {hacie_count}개)</summary>

| 순위 | 카테고리 | 상품명 | 가격 | 할인율 | 세일태그 | 리뷰 | 찜 | 평점 | 배송 |
|:----:|---------|--------|-----:|------:|---------|-----:|----:|:----:|:----:|
"""
            
            # 전체 목록
            for product in products:
                rank = product.get('순위') or product.get('rank', '-')
                category = product.get('depth2_카테고리') or product.get('depth2_name', '-')
                name = product.get('상품명') or product.get('productName', '-')
                url = product.get('상품URL') or product.get('productUrl', '')
                
                # 상품명 길이 제한
                if len(name) > 60:
                    name = name[:60] + '...'
                
                # 상품명에 링크 추가
                if url and url.startswith('http'):
                    name = f"[{name}]({url})"
                
                # 가격 포맷팅
                try:
                    price = int(product.get('가격') or product.get('salePrice', 0))
                    price_str = f"₩{price:,}"
                except:
                    price_str = product.get('가격') or product.get('salePrice', '-')
                
                # 할인율 포맷팅
                discount = product.get('할인율') or product.get('discountRate', '')
                discount_str = self._format_discount(discount) if discount else '-'
                
                # 추가 정보
                sale_tag = product.get('세일태그', '-')
                info_tags = product.get('정보태그', '')
                if info_tags:
                    tags_list = info_tags.split(',')[:2]
                    sale_tag = f"{sale_tag}<br>{'·'.join(tags_list)}" if sale_tag != '-' else '·'.join(tags_list)
                
                review_cnt = product.get('리뷰수', 0)
                heart_cnt = product.get('찜수', 0)
                review_score = product.get('리뷰평점', '')
                is_today = product.get('당일배송', 'N')
                
                # 리뷰수, 찜수 포맷팅
                try:
                    review_cnt = int(review_cnt) if review_cnt else 0
                    heart_cnt = int(heart_cnt) if heart_cnt else 0
                except:
                    review_cnt = 0
                    heart_cnt = 0
                
                review_str = f"{review_cnt}" if review_cnt > 0 else "-"
                heart_str = f"{heart_cnt}" if heart_cnt > 0 else "-"
                score_str = f"{review_score}" if review_score else "-"
                delivery_str = "당일" if is_today == 'Y' else "-"
                
                report += f"| {rank} | {category} | {name} | {price_str} | {discount_str} | {sale_tag} | {review_str} | {heart_str} | {score_str} | {delivery_str} |\n"
            
            report += "\n</details>\n"
        else:
            report += "\n**HACIE 상품이 발견되지 않았습니다.**\n"
        
        # 푸터
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            line_count = sum(1 for _ in f)
        
        report += f"""
---

**📈 분석 정보**
- 총 데이터 행 수: {line_count} 줄
- CSV 파일: {csv_file_text}
- 생성 시각: {kst_time} KST

*자동 생성 by GitHub Actions*
"""
        
        return {
            'markdown': report,
            'csv': ''
        }
    
    def generate_monthly_report(self, year: int, month: int) -> Optional[Dict[str, str]]:
        """월간 리포트 생성"""
        # 해당 월의 모든 데이터
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year, 12, 31)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)
        
        csv_files = self.find_csv_files(start_date, end_date)
        
        if not csv_files:
            return None
        
        # 데이터 수집
        all_products = []
        daily_stats = {}
        file_links = []
        
        for csv_file in csv_files:
            products = self.parse_csv(csv_file)
            all_products.extend(products)
            
            file_date = f"{csv_file.parent.parent.parent.name}/{csv_file.parent.parent.name}/{csv_file.parent.name}"
            daily_stats[file_date] = len(products)
            
            # GitHub 링크 생성
            relative_path = csv_file.relative_to(self.output_dir)
            github_link = f"https://github.com/kaae/best_item_crawl/blob/master/output/{relative_path}"
            file_links.append((file_date, csv_file.name, github_link))
        
        # 통계 계산
        total_products = len(all_products)
        total_days = len(csv_files)
        avg_per_day = total_products / total_days if total_days > 0 else 0
        
        # 주별 통계
        weekly_stats = defaultdict(lambda: {'products': 0, 'days': 0})
        for date_str, count in daily_stats.items():
            date_obj = datetime.strptime(date_str, '%Y/%m/%d')
            week_num = (date_obj.day - 1) // 7 + 1
            weekly_stats[week_num]['products'] += count
            weekly_stats[week_num]['days'] += 1
        
        # 카테고리별 집계
        category_stats = defaultdict(lambda: {'count': 0, 'ranks': [], 'prices': [], 'depth': ()})
        for product in all_products:
            # CSV 필드명 매핑
            depth1 = (product.get('depth1_카테고리') or product.get('depth1_name') or 'N/A').strip()
            depth2 = (product.get('depth2_카테고리') or product.get('depth2_name') or '').strip()
            cat_key = (depth1, depth2)
            category_stats[cat_key]['count'] += 1
            category_stats[cat_key]['depth'] = cat_key
            try:
                # CSV 필드명 매핑
                rank = int(product.get('순위') or product.get('rank', 999))
                category_stats[cat_key]['ranks'].append(rank)
            except:
                pass
            try:
                # CSV 필드명 매핑
                price_val = product.get('가격') or product.get('salePrice', 0)
                price = int(price_val) if price_val else 0
                category_stats[cat_key]['prices'].append(price)
            except:
                pass
        
        # 상품별 최고 순위 집계
        product_performance = self._aggregate_product_performance(all_products)

        # 월간 베스트 상품
        top_products = sorted(
            product_performance.values(),
            key=lambda x: (x['best_rank'], x['best_rank_date'] or date.max)
        )[:20]

        # 주별 베스트 상품 후보
        weekly_product_best = defaultdict(list)
        for entry in product_performance.values():
            weekly_candidates: Dict[int, Dict] = {}
            for record in entry.get('records', []):
                record_date = record.get('date')
                if not record_date or record_date.year != year or record_date.month != month:
                    continue

                week_index = (record_date.day - 1) // 7 + 1
                current = weekly_candidates.get(week_index)
                if current is None or record['rank'] < current['rank'] or (
                    record['rank'] == current['rank'] and self._is_earlier_date(record_date, current['date'])
                ):
                    weekly_candidates[week_index] = record

            for week_index, record in weekly_candidates.items():
                product_snapshot = record.get('product') or entry.get('best_record')
                weekly_entry = {
                    'name': entry.get('name', 'N/A'),
                    'url': entry.get('url', ''),
                    'category_depth1': entry.get('category_depth1'),
                    'category_depth2': entry.get('category_depth2'),
                    'price': record.get('price') if record.get('price') is not None else entry.get('price'),
                    'discount': record.get('discount') or entry.get('discount'),
                    'best_rank': record.get('rank'),
                    'best_rank_date': record.get('date'),
                    'best_record': product_snapshot,
                    'best_source_csv': record.get('source_csv') or entry.get('best_source_csv')
                }
                weekly_product_best[week_index].append(weekly_entry)
        
        # 리포트 생성
        month_name = f"{year}년 {month}월"

        if all_products:
            monthly_avg_rank_value = statistics.mean(
                [int(p.get('순위') or p.get('rank', 999)) for p in all_products]
            )
            monthly_avg_rank_text = f"{monthly_avg_rank_value:.1f}위"
        else:
            monthly_avg_rank_value = None
            monthly_avg_rank_text = "데이터 없음"

        report = f"""# 📊 HACIE 브랜드 월간 통계 리포트

**분석 기간:** {month_name} ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})

## 📈 월간 요약

- **총 발견 상품:** {total_products}개
- **분석 일수:** {total_days}일
- **일평균 상품 수:** {avg_per_day:.1f}개
- **월 평균 순위:** {monthly_avg_rank_text}

## 📅 주별 추이

| 주차 | 발견 상품 수 | 일평균 | 추이 |
|:----:|------------:|-------:|:----:|
"""
        
        prev_avg = None
        for week in sorted(weekly_stats.keys()):
            stats = weekly_stats[week]
            products = stats['products']
            days = stats['days']
            avg = products / days if days > 0 else 0
            
            # 추이 표시
            if prev_avg is not None:
                if avg > prev_avg * 1.1:
                    trend = "📈"
                elif avg < prev_avg * 0.9:
                    trend = "📉"
                else:
                    trend = "➡️"
            else:
                trend = "➡️"
            
            report += f"| {week}주차 | {products}개 | {avg:.1f}개 | {trend} |\n"
            prev_avg = avg
        
        report += f"""
## 🏆 카테고리별 월간 통계

| 순위 | 카테고리 | 진입 횟수 | 평균 순위 | 평균 가격 |
|:----:|---------|--------:|--------:|--------:|
"""
        
        sorted_categories = sorted(category_stats.items(), key=lambda x: -x[1]['count'])
        for idx, (cat_key, stats) in enumerate(sorted_categories[:15], 1):
            cat_name = self._compose_category(*(stats.get('depth') or cat_key))
            count = stats['count']
            ranks = stats['ranks']
            prices = stats['prices']
            
            avg_rank = statistics.mean(ranks) if ranks else 0
            avg_price = statistics.mean(prices) if prices else 0
            
            report += f"| {idx} | {cat_name} | {count}회 | {avg_rank:.1f}위 | ₩{int(avg_price):,} |\n"
        
        report_dir = self.output_dir / str(year) / f"{month:02d}"

        report += f"""
## 🌟 월간 베스트 TOP 20

| 순위 | 최고 순위 | 달성일 | 상품명 | 카테고리 | 가격 | 할인율 | 세일 | 리뷰 | 찜 | 평점 | 링크 |
|:----:|---------:|:------:|--------|---------|-----:|------:|-----|----:|---:|:---:|:----:|
"""

        for idx, product in enumerate(top_products, 1):
            name = product.get('name', 'N/A')
            url = product.get('url', '')
            depth1 = product.get('category_depth1') or ''
            depth2 = product.get('category_depth2') or ''
            category = self._compose_category(depth1, depth2)
            if len(category) > 25:
                category = category[:25] + '...'

            if len(name) > 40:
                name = name[:40] + '...'
            if url and url.startswith('http'):
                name = f"[{name}]({url})"

            price_str = self._price_display_from_entry(product)
            best_rank = product.get('best_rank')
            best_rank_text = f"{best_rank}위" if best_rank is not None else "-"
            best_date_text = self._format_date_label(product.get('best_rank_date'))
            discount_value = self._resolve_entry_discount(product)
            discount_text = self._format_discount(discount_value)
            
            # 추가 정보
            sale_tag = product.get('sale_tag', '-')
            review_count = product.get('review_count', 0)
            heart_count = product.get('heart_count', 0)
            review_score = product.get('review_score', 0.0)
            
            review_str = f"{review_count}" if review_count and review_count > 0 else "-"
            heart_str = f"{heart_count}" if heart_count and heart_count > 0 else "-"
            score_str = f"{review_score:.1f}" if review_score and review_score > 0 else "-"
            
            daily_md_path = self._resolve_daily_markdown_path(product.get('best_source_csv'))
            link_markdown = self._format_link('일일 리포트', daily_md_path, report_dir)

            report += f"| {idx} | {best_rank_text} | {best_date_text} | {name} | {category} | {price_str} | {discount_text} | {sale_tag} | {review_str} | {heart_str} | {score_str} | {link_markdown} |\n"
        
        if weekly_product_best:
            report += """
## 🗓️ 주별 베스트 TOP 5
"""

            for week_index in sorted(weekly_product_best.keys()):
                week_products = sorted(
                    weekly_product_best[week_index],
                    key=lambda x: (x['best_rank'], x['best_rank_date'] or date.max)
                )[:5]

                if not week_products:
                    continue

                weekly_md_path = self._resolve_weekly_markdown_path(year, month, week_index)
                weekly_link = self._format_link('주간 리포트', weekly_md_path, report_dir)

                report += f"""
### {week_index}주차 베스트 5

| 순위 | 최고 순위 | 달성일 | 상품명 | 카테고리 | 가격 | 할인율 | 세일 | 리뷰 | 찜 | 평점 | 링크 |
|:----:|---------:|:------:|--------|---------|-----:|------:|-----|----:|---:|:---:|:----:|
"""

                for idx, week_product in enumerate(week_products, 1):
                    name = week_product.get('name', 'N/A')
                    url = week_product.get('url', '')
                    depth1 = week_product.get('category_depth1') or ''
                    depth2 = week_product.get('category_depth2') or ''
                    category = self._compose_category(depth1, depth2)
                    if len(category) > 25:
                        category = category[:25] + '...'

                    if len(name) > 40:
                        name = name[:40] + '...'
                    if url and url.startswith('http'):
                        name = f"[{name}]({url})"

                    best_rank = week_product.get('best_rank')
                    best_rank_text = f"{best_rank}위" if best_rank is not None else "-"
                    best_date_text = self._format_date_label(week_product.get('best_rank_date'))
                    price_str = self._price_display_from_entry(week_product)
                    discount_text = self._format_discount(self._resolve_entry_discount(week_product))
                    
                    # 추가 정보
                    week_sale_tag = week_product.get('sale_tag', '-')
                    week_review_count = week_product.get('review_count', 0)
                    week_heart_count = week_product.get('heart_count', 0)
                    week_review_score = week_product.get('review_score', 0.0)
                    
                    week_review_str = f"{week_review_count}" if week_review_count and week_review_count > 0 else "-"
                    week_heart_str = f"{week_heart_count}" if week_heart_count and week_heart_count > 0 else "-"
                    week_score_str = f"{week_review_score:.1f}" if week_review_score and week_review_score > 0 else "-"

                    report += f"| {idx} | {best_rank_text} | {best_date_text} | {name} | {category} | {price_str} | {discount_text} | {week_sale_tag} | {week_review_str} | {week_heart_str} | {week_score_str} | {weekly_link} |\n"

        report += f"""
## 💡 월간 인사이트

### 📊 전체 성과 분석
"""
        
        # 성과 평가
        if avg_per_day >= 15:
            grade = "S"
            comment = "탁월한 성과! HACIE 브랜드가 베스트 페이지에서 강력한 존재감을 보였습니다."
        elif avg_per_day >= 10:
            grade = "A"
            comment = "우수한 성과! 안정적으로 베스트 순위를 유지하고 있습니다."
        elif avg_per_day >= 5:
            grade = "B"
            comment = "양호한 성과! 일부 카테고리에서 개선의 여지가 있습니다."
        else:
            grade = "C"
            comment = "개선 필요! 마케팅 전략 재검토가 필요합니다."
        
        report += f"""
- **월간 평가:** {grade}등급
- **종합 의견:** {comment}
- **분석 일수:** {total_days}일 ({total_days / 30 * 100:.0f}% 커버리지)

### 🎯 카테고리 분석
"""
        
        if category_stats:
            top_3_categories = sorted_categories[:3]
            report += "\n**강점 카테고리:**\n"
            for cat_key, stats in top_3_categories:
                cat_name = self._compose_category(*(stats.get('depth') or cat_key))
                avg_rank = statistics.mean(stats['ranks']) if stats['ranks'] else 0
                report += f"- **{cat_name}**: {stats['count']}회 진입, 평균 {avg_rank:.1f}위\n"
        
        report += f"""
### 💰 가격대 분석
"""
        
        all_prices = [int(p.get('salePrice', 0)) for p in all_products if p.get('salePrice')]
        if all_prices:
            avg_price = statistics.mean(all_prices)
            median_price = statistics.median(all_prices)
            min_price = min(all_prices)
            max_price = max(all_prices)
            
            report += f"""
- **평균 가격:** ₩{int(avg_price):,}
- **중간 가격:** ₩{int(median_price):,}
- **가격 범위:** ₩{int(min_price):,} ~ ₩{int(max_price):,}

"""
        
        report += f"""### 📌 다음 달 액션 플랜

**지속 강화**
- 성과 좋은 카테고리 재고 확보
- 베스트 상품 프로모션 강화
- 고객 리뷰 수집 및 활용

**개선 필요**
- 저조한 카테고리 신상품 기획
- 가격 정책 재검토
- 계절별 마케팅 전략 수립

**신규 시도**
- 인플루언서 협업 확대
- 라이브 커머스 진행
- 패키지 상품 기획

---

## 📎 참고 데이터 파일

| 날짜 | 파일명 |
|------|--------|
"""
        
        for date, filename, link in sorted(file_links):
            report += f"| {date} | [{filename}]({link}) |\n"
        
        report += f"""
---

*생성 일시: {datetime.now(ZoneInfo("Asia/Seoul")).strftime('%Y-%m-%d %H:%M:%S')} KST*  
*데이터 출처: W컨셉 베스트 페이지 ({total_days}일간 데이터)*
"""
        
        # CSV 생성
        csv_data = []
        
        # 1. 주별 통계
        for week, stats in sorted(weekly_stats.items()):
            products = stats['products']
            days = stats['days']
            avg = products / days if days > 0 else 0
            
            csv_data.append({
                '유형': f'{week}주차',
                '기간': f'{week}주차',
                '상품수': products,
                '일평균': f"{avg:.1f}",
                '카테고리': '',
                '평균순위': '',
                  '평균가격': '',
                  '최고순위': '',
                  '기록일': '',
                  '가격': '',
                  '할인율': '',
                  '상품명': '',
                  '링크': ''
            })
        
        # 2. 카테고리별 통계
        for cat_key, stats in sorted_categories[:15]:
            cat_name = self._compose_category(*(stats.get('depth') or cat_key))
            count = stats['count']
            ranks = stats['ranks']
            prices = stats['prices']
            
            avg_rank = statistics.mean(ranks) if ranks else 0
            avg_price = statistics.mean(prices) if prices else 0
            
            csv_data.append({
                '유형': '카테고리통계',
                '기간': '',
                '상품수': count,
                '일평균': '',
                '카테고리': cat_name,
                '평균순위': f"{avg_rank:.1f}",
                  '평균가격': f"{int(avg_price):,}",
                  '최고순위': '',
                  '기록일': '',
                  '가격': '',
                  '할인율': '',
                  '상품명': '',
                  '링크': ''
            })
        
        # 3. TOP 상품
        for idx, product in enumerate(top_products, 1):
            name = product.get('name', 'N/A')
            depth1 = product.get('category_depth1') or ''
            depth2 = product.get('category_depth2') or ''
            category = self._compose_category(depth1, depth2)
            best_rank = product.get('best_rank')
            best_date_text = self._format_date_label(product.get('best_rank_date'))
            price_value = self._price_value_from_entry(product)
            discount_value = self._resolve_entry_discount(product)
            daily_md_path = self._resolve_daily_markdown_path(product.get('best_source_csv'))
            link_path = self._relative_path_string(daily_md_path, report_dir) or ''
            
            csv_data.append({
                '유형': f'TOP{idx}',
                '기간': '',
                '상품수': '',
                '일평균': '',
                '카테고리': category,
                '평균순위': '',
                '평균가격': '',
                '최고순위': str(best_rank) if best_rank is not None else '',
                '기록일': best_date_text,
                '가격': price_value,
                '할인율': self._format_discount(discount_value),
                '세일태그': product.get('sale_tag', ''),
                '리뷰수': str(product.get('review_count', 0)),
                '찜수': str(product.get('heart_count', 0)),
                '평점': f"{product.get('review_score', 0):.1f}" if product.get('review_score', 0) > 0 else '',
                '상품명': name,
                '링크': link_path
            })

        # 4. 주별 베스트 TOP5
        for week_index in sorted(weekly_product_best.keys()):
            week_products = sorted(
                weekly_product_best[week_index],
                key=lambda x: (x['best_rank'], x['best_rank_date'] or date.max)
            )[:5]

            weekly_md_path = self._resolve_weekly_markdown_path(year, month, week_index)
            weekly_link_path = self._relative_path_string(weekly_md_path, report_dir) or ''

            for idx, week_product in enumerate(week_products, 1):
                depth1 = week_product.get('category_depth1') or ''
                depth2 = week_product.get('category_depth2') or ''
                category = self._compose_category(depth1, depth2)
                best_rank = week_product.get('best_rank')
                best_date_text = self._format_date_label(week_product.get('best_rank_date'))

                csv_data.append({
                    '유형': f'{week_index}주차_TOP{idx}',
                    '기간': f'{week_index}주차',
                    '상품수': '',
                    '일평균': '',
                    '카테고리': category,
                    '평균순위': '',
                    '평균가격': '',
                    '최고순위': str(best_rank) if best_rank is not None else '',
                    '기록일': best_date_text,
                    '가격': self._price_value_from_entry(week_product),
                    '할인율': self._format_discount(self._resolve_entry_discount(week_product)),
                    '세일태그': week_product.get('sale_tag', ''),
                    '리뷰수': str(week_product.get('review_count', 0)),
                    '찜수': str(week_product.get('heart_count', 0)),
                    '평점': f"{week_product.get('review_score', 0):.1f}" if week_product.get('review_score', 0) > 0 else '',
                    '상품명': week_product.get('name', 'N/A'),
                    '링크': weekly_link_path
                })
        
        # CSV 문자열 생성
        if csv_data:
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=['유형', '기간', '상품수', '일평균', '카테고리', '평균순위', '평균가격', '최고순위', '기록일', '가격', '할인율', '세일태그', '리뷰수', '찜수', '평점', '상품명', '링크'])
            writer.writeheader()
            writer.writerows(csv_data)
            csv_content = output.getvalue()
        else:
            csv_content = ""
        
        return {
            'markdown': report,
            'csv': csv_content
        }


def main():
    """메인 함수"""
    import sys
    
    generator = HacieReportGenerator()
    
    if len(sys.argv) < 2:
        print("사용법:")
        print("  일일 리포트: python generate_reports.py daily CSV_FILE_PATH OUTPUT_FILE_PATH")
        print("  주간 리포트: python generate_reports.py weekly YYYY MM WEEK")
        print("  월간 리포트: python generate_reports.py monthly YYYY MM")
        sys.exit(1)
    
    report_type = sys.argv[1]
    
    if report_type == 'daily':
        if len(sys.argv) < 4:
            print("사용법: python generate_reports.py daily CSV_FILE_PATH OUTPUT_FILE_PATH")
            sys.exit(1)
        
        csv_file_path = Path(sys.argv[2])
        output_file_path = Path(sys.argv[3])
        
        print(f"📄 CSV 파일 경로: {csv_file_path}")
        print(f"📝 출력 파일 경로: {output_file_path}")
        
        # CSV 파일 존재 및 내용 확인
        if not csv_file_path.exists():
            print(f"❌ CSV 파일을 찾을 수 없습니다: {csv_file_path}")
            sys.exit(1)
        
        # CSV 파일 크기 확인
        file_size = csv_file_path.stat().st_size
        print(f"📊 CSV 파일 크기: {file_size} bytes")
        
        if file_size == 0:
            print("⚠️ CSV 파일이 비어있습니다.")
        
        try:
            result = generator.generate_daily_report(csv_file_path)
            
            if result:
                # 출력 디렉토리 생성
                output_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 마크다운 저장
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    f.write(result['markdown'])
                print(f"✓ 일일 리포트 생성 완료: {output_file_path}")
            else:
                print("❌ 리포트 생성 실패: 데이터가 없습니다.")
                sys.exit(1)
        except Exception as e:
            print(f"❌ 리포트 생성 중 예외 발생: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    elif report_type == 'weekly':
        year = int(sys.argv[2])
        month = int(sys.argv[3])
        week = int(sys.argv[4])
        
        result = generator.generate_weekly_report(year, month, week)
        
        if result:
            # 저장 폴더
            output_dir = generator.output_dir / str(year) / f"{month:02d}"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            base_filename = f"{year}년_{month:02d}월_{week}주차_통계"
            
            # 마크다운 저장
            md_file = output_dir / f"{base_filename}.md"
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(result['markdown'])
            print(f"✓ 주간 리포트(MD) 생성: {md_file}")
            
            # CSV 저장
            csv_file = output_dir / f"{base_filename}.csv"
            with open(csv_file, 'w', encoding='utf-8') as f:
                f.write(result['csv'])
            print(f"✓ 주간 리포트(CSV) 생성: {csv_file}")
        else:
            print("✗ 데이터가 없습니다.")
    
    elif report_type == 'monthly':
        year = int(sys.argv[2])
        month = int(sys.argv[3])
        
        result = generator.generate_monthly_report(year, month)
        
        if result:
            # 저장 폴더
            output_dir = generator.output_dir / str(year) / f"{month:02d}"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            base_filename = f"{year}년_{month:02d}월_월간통계"
            
            # 마크다운 저장
            md_file = output_dir / f"{base_filename}.md"
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(result['markdown'])
            print(f"✓ 월간 리포트(MD) 생성: {md_file}")
            
            # CSV 저장
            csv_file = output_dir / f"{base_filename}.csv"
            with open(csv_file, 'w', encoding='utf-8') as f:
                f.write(result['csv'])
            print(f"✓ 월간 리포트(CSV) 생성: {csv_file}")
        else:
            print("✗ 데이터가 없습니다.")


if __name__ == '__main__':
    main()

