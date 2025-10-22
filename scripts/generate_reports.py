#!/usr/bin/env python3
"""
HACIE 브랜드 주간/월간 통계 리포트 생성
"""

import json
import csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict
import statistics


class HacieReportGenerator:
    """HACIE 통계 리포트 생성기"""
    
    def __init__(self, output_dir: Path = None):
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / 'output'
        self.output_dir = output_dir
    
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
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 브랜드명 필드
                    brand_name = row.get('브랜드명') or row.get('brandName') or ''
                    
                    # HACIE 브랜드 필터링
                    if brand_name and ('HACIE' in brand_name.upper() or '하시에' in brand_name):
                        products.append(row)
                    else:
                        # 브랜드 필드 없으면 상품명에서 확인
                        product_name = row.get('상품명') or row.get('productName') or ''
                        if product_name and ('HACIE' in product_name.upper() or '하시에' in product_name):
                            products.append(row)
        except Exception as e:
            print(f"CSV 파싱 에러 ({csv_file}): {e}")
        
        return products
    
    def generate_weekly_report(self, year: int, month: int, week_num: int) -> Optional[Dict[str, str]]:
        """주간 리포트 생성"""
        # 해당 주의 날짜 범위 계산
        # 월요일 기준
        first_day = datetime(year, month, 1)
        
        # 해당 월의 N주차 계산
        start_date = first_day + timedelta(weeks=week_num - 1)
        end_date = start_date + timedelta(days=6)
        
        # 실제 월 범위 체크
        if start_date.month != month:
            start_date = first_day
        if end_date.month != month:
            # 월말까지
            next_month = datetime(year, month + 1, 1) if month < 12 else datetime(year + 1, 1, 1)
            end_date = next_month - timedelta(days=1)
        
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
            file_date = csv_file.parent.name
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
        category_stats = defaultdict(lambda: {'count': 0, 'ranks': []})
        for product in all_products:
            # CSV 필드명 매핑
            depth1 = product.get('depth1_카테고리') or product.get('depth1_name', 'N/A')
            depth2 = product.get('depth2_카테고리') or product.get('depth2_name', 'N/A')
            cat_key = f"{depth1} > {depth2}"
            category_stats[cat_key]['count'] += 1
            try:
                # CSV 필드명 매핑
                rank = int(product.get('순위') or product.get('rank', 999))
                category_stats[cat_key]['ranks'].append(rank)
            except:
                pass
        
        # 베스트 순위 상품
        top_products = sorted(all_products, key=lambda x: int(x.get('순위') or x.get('rank', 999)))[:10]
        
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
        
        for date_str, count in sorted(daily_stats.items()):
            date_obj = datetime.strptime(date_str, '%d')
            report += f"| {date_obj.strftime('%m월 %d일')} | {count}개 |\n"
        
        report += f"""
## 🏆 카테고리별 통계

| 카테고리 | 발견 횟수 | 평균 순위 | 최고 순위 |
|---------|--------:|--------:|--------:|
"""
        
        for cat_name, stats in sorted(category_stats.items(), key=lambda x: -x[1]['count'])[:10]:
            count = stats['count']
            ranks = stats['ranks']
            avg_rank = statistics.mean(ranks) if ranks else 0
            best_rank = min(ranks) if ranks else 0
            report += f"| {cat_name} | {count}회 | {avg_rank:.1f}위 | {best_rank}위 |\n"
        
        report += f"""
## 🌟 주간 베스트 TOP 10

| 순위 | 상품명 | 카테고리 | 평균가 |
|:----:|--------|---------|-------:|
"""
        
        for idx, product in enumerate(top_products[:10], 1):
            # CSV 필드명 매핑
            name = product.get('상품명') or product.get('productName', 'N/A')
            url = product.get('상품URL') or product.get('productUrl', '')
            category = product.get('depth2_카테고리') or product.get('depth2_name', 'N/A')
            
            # 상품명 길이 제한 및 링크 추가
            if len(name) > 40:
                name = name[:40] + '...'
            if url and url.startswith('http'):
                name = f"[{name}]({url})"
            
            # 가격 포맷팅
            try:
                price_val = product.get('가격') or product.get('salePrice', 0)
                price = int(price_val) if price_val else 0
                price_str = f"₩{price:,}"
            except:
                price_str = "N/A"
            
            report += f"| {idx} | {name} | {category} | {price_str} |\n"
        
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
            top_category = max(category_stats.items(), key=lambda x: x[1]['count'])
            report += f"- 🎯 **주력 카테고리**: {top_category[0]} ({top_category[1]['count']}회 진입)\n"
        
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
        
        for date, filename, link in sorted(file_links):
            report += f"| {date}일 | [{filename}]({link}) |\n"
        
        report += f"""
---

*생성 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} KST*  
*데이터 출처: W컨셉 베스트 페이지*
"""
        
        # CSV 생성
        csv_data = []
        
        # 1. 일별 통계
        for date_str, count in sorted(daily_stats.items()):
            csv_data.append({
                '유형': '일별통계',
                '날짜': date_str,
                '상품수': count,
                '카테고리': '',
                '평균순위': '',
                '최고순위': '',
                '상품명': ''
            })
        
        # 2. 카테고리별 통계
        for cat_name, stats in sorted(category_stats.items(), key=lambda x: -x[1]['count']):
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
        for idx, product in enumerate(top_products[:10], 1):
            # CSV 필드명 매핑
            depth2 = product.get('depth2_카테고리') or product.get('depth2_name', 'N/A')
            rank = product.get('순위') or product.get('rank', '')
            name = product.get('상품명') or product.get('productName', 'N/A')
            
            csv_data.append({
                '유형': f'TOP{idx}',
                '날짜': '',
                '상품수': '',
                '카테고리': depth2,
                '평균순위': rank,
                '최고순위': '',
                '상품명': name
            })
        
        # CSV 문자열 생성
        if csv_data:
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=['유형', '날짜', '상품수', '카테고리', '평균순위', '최고순위', '상품명'])
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
            return None
        
        # CSV 파일 파싱
        products = self.parse_csv(csv_file_path)
        hacie_count = len(products)
        
        # 파일 정보 추출
        csv_name = csv_file_path.name
        
        # GitHub 링크 생성
        try:
            relative_path = csv_file_path.relative_to(self.output_dir)
            github_link = f"https://github.com/kaae/best_item_crawl/blob/master/output/{relative_path}"
        except:
            github_link = None
        
        # 현재 시각
        now = datetime.now()
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
            report += """| 순위 | 카테고리 | 상품명 | 가격 |
|:----:|---------|--------|-----:|
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
                
                report += f"| {rank} | {category} | {name} | {price_str} |\n"
            
            # 전체 상품 목록
            report += f"""
---

## 📦 전체 HACIE 상품 목록

<details>
<summary>펼쳐서 보기 (전체 {hacie_count}개)</summary>

| 순위 | 카테고리 | 상품명 | 가격 |
|:----:|---------|--------|-----:|
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
                
                report += f"| {rank} | {category} | {name} | {price_str} |\n"
            
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
        category_stats = defaultdict(lambda: {'count': 0, 'ranks': [], 'prices': []})
        for product in all_products:
            # CSV 필드명 매핑
            depth1 = product.get('depth1_카테고리') or product.get('depth1_name', 'N/A')
            depth2 = product.get('depth2_카테고리') or product.get('depth2_name', 'N/A')
            cat_key = f"{depth1} > {depth2}"
            category_stats[cat_key]['count'] += 1
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
        
        # 월간 베스트 상품
        top_products = sorted(all_products, key=lambda x: int(x.get('순위') or x.get('rank', 999)))[:20]
        
        # 리포트 생성
        month_name = f"{year}년 {month}월"
        
        report = f"""# 📊 HACIE 브랜드 월간 통계 리포트

**분석 기간:** {month_name} ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})

## 📈 월간 요약

- **총 발견 상품:** {total_products}개
- **분석 일수:** {total_days}일
- **일평균 상품 수:** {avg_per_day:.1f}개
- **월 평균 순위:** {statistics.mean([int(p.get('순위') or p.get('rank', 999)) for p in all_products]):.1f}위

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
        for idx, (cat_name, stats) in enumerate(sorted_categories[:15], 1):
            count = stats['count']
            ranks = stats['ranks']
            prices = stats['prices']
            
            avg_rank = statistics.mean(ranks) if ranks else 0
            avg_price = statistics.mean(prices) if prices else 0
            
            report += f"| {idx} | {cat_name} | {count}회 | {avg_rank:.1f}위 | ₩{int(avg_price):,} |\n"
        
        report += f"""
## 🌟 월간 베스트 TOP 20

| 순위 | 상품명 | 카테고리 | 가격 | 할인율 |
|:----:|--------|---------|-----:|------:|
"""
        
        for idx, product in enumerate(top_products[:20], 1):
            # CSV 필드명 매핑
            name = product.get('상품명') or product.get('productName', 'N/A')
            url = product.get('상품URL') or product.get('productUrl', '')
            depth1 = product.get('depth1_카테고리') or product.get('depth1_name', '')
            depth2 = product.get('depth2_카테고리') or product.get('depth2_name', '')
            category = f"{depth1} > {depth2}"[:25]
            
            # 상품명 길이 제한 및 링크 추가
            if len(name) > 40:
                name = name[:40] + '...'
            if url and url.startswith('http'):
                name = f"[{name}]({url})"
            
            # 가격 포맷팅
            try:
                price_val = product.get('가격') or product.get('salePrice', 0)
                price = int(price_val) if price_val else 0
                price_str = f"₩{price:,}"
            except:
                price_str = "N/A"
            
            discount = product.get('discountRate', '0')
            
            report += f"| {idx} | {name} | {category} | {price_str} | {discount}% |\n"
        
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
            for cat_name, stats in top_3_categories:
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

*생성 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} KST*  
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
                '상품명': ''
            })
        
        # 2. 카테고리별 통계
        for cat_name, stats in sorted_categories[:15]:
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
                '상품명': ''
            })
        
        # 3. TOP 상품
        for idx, product in enumerate(top_products[:20], 1):
            # CSV 필드명 매핑
            name = product.get('상품명') or product.get('productName', 'N/A')
            depth1 = product.get('depth1_카테고리') or product.get('depth1_name', '')
            depth2 = product.get('depth2_카테고리') or product.get('depth2_name', '')
            category = f"{depth1} > {depth2}"
            rank = product.get('순위') or product.get('rank', '')
            
            try:
                price_val = product.get('가격') or product.get('salePrice', 0)
                price = int(price_val) if price_val else 0
                price_str = str(price)
            except:
                price_str = "0"
            
            csv_data.append({
                '유형': f'TOP{idx}',
                '기간': '',
                '상품수': '',
                '일평균': '',
                '카테고리': category,
                '평균순위': rank,
                '평균가격': price_str,
                '상품명': name
            })
        
        # CSV 문자열 생성
        if csv_data:
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=['유형', '기간', '상품수', '일평균', '카테고리', '평균순위', '평균가격', '상품명'])
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
        
        result = generator.generate_daily_report(csv_file_path)
        
        if result:
            # 출력 디렉토리 생성
            output_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 마크다운 저장
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(result['markdown'])
            print(f"✓ 일일 리포트 생성: {output_file_path}")
        else:
            print("✗ 데이터가 없습니다.")
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

