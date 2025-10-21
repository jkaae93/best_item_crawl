# 🏆 W컨셉 HACIE 브랜드 순위 자동 추적 시스템

W컨셉(Wconcept) 베스트 페이지에서 **HACIE (하시에)** 브랜드의 순위를 자동으로 추적하고 분석하는 시스템입니다.

## 📊 주요 기능

### 자동 데이터 수집
- ✅ **일일 추적**: 매일 오전 8시 (KST)
- ✅ **주간 리포트**: 매주 월요일 오전 8시 (지난 주 월~일 데이터 분석)
- ✅ **월간 리포트**: 매월 1일 오전 8시 (전월 전체 데이터 분석)

### 체계적인 데이터 관리
- ✅ `yyyy/MM/dd` 폴더 구조로 자동 정리
- ✅ CSV 원본 데이터 + 분석 리포트 자동 생성
- ✅ Git 자동 커밋 및 이력 관리
- ✅ GitHub Actions 아티팩트 보관

### 마케팅 인사이트
- ✅ 카테고리별 성과 분석
- ✅ 주간/월간 추이 분석
- ✅ 베스트 상품 TOP 순위
- ✅ 실행 가능한 마케팅 제안

## 📁 폴더 구조

```
output/
├── 2025/
│   ├── 10/
│   │   ├── 21/
│   │   │   ├── wconcept_best_20251021_0800_KST.csv     # 원본 데이터
│   │   │   └── 일일_요약.md                             # 일일 요약
│   │   ├── 22/
│   │   │   ├── wconcept_best_20251022_0800_KST.csv
│   │   │   └── 일일_요약.md
│   │   ├── 2025년_10월_1주차_통계.md                    # 주간 리포트
│   │   ├── 2025년_10월_2주차_통계.md
│   │   └── 2025년_10월_월간통계.md                      # 월간 리포트 (다음 달 1일 생성)
│   └── 11/
│       ├── 01/
│       └── 2025년_11월_1주차_통계.md
└── README.md
```

## 🔄 자동 실행 스케줄

| 작업 | 실행 시간 | 분석 기간 | 파일명 |
|------|---------|---------|--------|
| 일일 추적 | 매일 08:00 KST | 당일 | `yyyy/MM/dd/wconcept_best_*.csv` |
| 일일 요약 | 매일 08:00 KST | 당일 | `yyyy/MM/dd/일일_요약.md` |
| 주간 리포트 | 월요일 08:00 KST | 지난 주 월~일 | `yyyy/MM/yyyy년_MM월_N주차_통계.md` |
| 월간 리포트 | 1일 08:00 KST | 전월 1일~말일 | `yyyy/MM/yyyy년_MM월_월간통계.md` |

## 🚀 빠른 시작

### GitHub에서 데이터 확인

1. **저장소 방문**
   ```
   https://github.com/[사용자명]/best_item_crawl
   ```

2. **최신 데이터 확인**
   - `output/2025/10/21/` 폴더로 이동
   - `일일_요약.md` 파일 클릭 (마크다운은 바로 읽기 가능)
   - `wconcept_best_*.csv` 다운로드 (Excel로 분석)

3. **주간/월간 리포트**
   - `output/2025/10/` 폴더에서 리포트 확인
   - `*주차_통계.md`: 주간 분석
   - `*월간통계.md`: 월간 종합 분석

### 로컬 실행 (개발자용)

```bash
# 1. 의존성 설치
pip install -r requirements.txt
playwright install chromium

# 2. 일일 크롤링 실행
python3 scripts/wconcept_best_export.py

# 3. 주간 리포트 생성
python3 scripts/generate_reports.py weekly 2025 10 3

# 4. 월간 리포트 생성
python3 scripts/generate_reports.py monthly 2025 10
```

## 📊 데이터 구조

### CSV 파일 컬럼

| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| `depth1_code` | 메인 카테고리 코드 | `10101` |
| `depth1_name` | 메인 카테고리명 | `의류` |
| `depth2_code` | 서브 카테고리 코드 | `10101201` |
| `depth2_name` | 서브 카테고리명 | `아우터` |
| `rank` | 순위 (작을수록 높음) | `5` |
| `brandName` | 브랜드명 | `HACIE` |
| `productName` | 상품명 | `울 블렌드 코트` |
| `salePrice` | 판매가 | `298000` |
| `discountRate` | 할인율 | `15` |
| `productUrl` | 상품 URL | `https://...` |

### 리포트 종류

**1. 일일 요약** (`일일_요약.md`)
- 당일 발견된 HACIE 상품 수
- TOP 5 상품 목록
- 간단한 요약

**2. 주간 통계** (`yyyy년_MM월_N주차_통계.md`)
- 주간 총 발견 상품 수 / 일평균
- 일별 추이
- 카테고리별 통계
- 주간 베스트 TOP 10
- 자동 인사이트 및 추천 액션

**3. 월간 통계** (`yyyy년_MM월_월간통계.md`)
- 월간 총 발견 상품 수 / 일평균
- 주별 추이 (1주차 ~ 4-5주차)
- 카테고리별 월간 통계
- 월간 베스트 TOP 20
- 가격대 분석
- 성과 평가 (S/A/B/C 등급)
- 다음 달 액션 플랜

## 🎯 마케팅 활용 가이드

### 일일 활용

**매일 오전 9시경**
1. GitHub 저장소 또는 이메일 알림 확인
2. `output/yyyy/MM/dd/일일_요약.md` 확인
3. TOP 순위 상품 SNS 공유
4. 신규 진입 상품 주목

### 주간 활용

**매주 월요일**
1. 주간 리포트 확인 (`*주차_통계.md`)
2. 주간 성과 회의 자료로 활용
3. 성과 좋은 카테고리 집중 마케팅
4. 저조한 카테고리 개선 방안 논의

### 월간 활용

**매월 첫째 주**
1. 월간 리포트 확인 (`*월간통계.md`)
2. 경영진 보고 자료 작성
3. 다음 달 마케팅 전략 수립
4. 상품 기획팀과 데이터 공유

## ⚙️ GitHub Actions 설정

### 초기 설정 (1회만)

1. **저장소 푸시**
   ```bash
   git add .
   git commit -m "feat: Add HACIE tracking system"
   git push origin main
   ```

2. **Actions 권한 설정**
   - GitHub 저장소 → Settings → Actions → General
   - Workflow permissions: **"Read and write permissions"** 선택
   - "Allow GitHub Actions to create and approve pull requests" 체크

3. **알림 설정 (선택사항)**
   - 저장소 우측 상단 "Watch" → "Custom"
   - "Commits" 체크
   - 매일 커밋 시 이메일 수신

### 수동 실행

필요시 언제든 수동으로 실행 가능:

1. Actions 탭 클릭
2. 원하는 워크플로우 선택:
   - **Track HACIE Daily Rankings**: 일일 추적
   - **Generate Weekly Report**: 주간 리포트
   - **Generate Monthly Report**: 월간 리포트
3. "Run workflow" 버튼 클릭

## 📈 Excel 활용 팁

### CSV 파일 분석

```
1. CSV 다운로드 → Excel 열기
2. "데이터" → "필터" 활성화
3. rank 컬럼 오름차순 정렬
4. depth1_name 필터로 카테고리별 확인
```

### 주간 추이 분석

```
1. 7일간 CSV 파일 모두 다운로드
2. Excel "파워 쿼리"로 합치기
3. 날짜별 순위 변화 그래프 생성
```

### 피벗 테이블 활용

```
1. 전체 데이터 선택
2. "삽입" → "피벗 테이블"
3. 행: depth1_name, depth2_name
4. 값: rank (평균)
```

## 🔔 커밋 메시지 형식

### 일일 추적
```
📊 HACIE 일일 순위 추적 (2025.10.21)

- 발견 상품: 15개
- 분석 시각: 2025년 10월 21일 08시
- 파일: output/2025/10/21/

자동 생성 by GitHub Actions
```

### 주간 리포트
```
📊 주간 리포트 생성: 2025년 10월 3주차

- 분석 기간: 지난 주 월요일 ~ 일요일
- 생성 일시: 2025년 10월 21일
- 자동 생성: GitHub Actions (Weekly Report)
```

### 월간 리포트
```
📈 월간 리포트 생성: 2025년 10월

- 총 발견 상품: 425개
- 일평균: 14.2개
- 생성 일시: 2025년 11월 01일
- 자동 생성: GitHub Actions (Monthly Report)
```

## 📊 주요 카테고리 코드

| 코드 | 이름 | 서브 카테고리 수 |
|------|------|:----------------:|
| ALL | 전체 | - |
| 10101 | 의류 | 12개 |
| 10102 | 가방 | 10개 |
| 10103 | 신발 | 11개 |
| 10104 | 액세서리 | 9개 |
| 10107 | 뷰티 | 8개 |
| 10108 | 라이프 | 5개 |

전체 카테고리 목록: [`tmp_wconcept_best_categories.json`](tmp_wconcept_best_categories.json)

## 🛠️ 스크립트 설명

| 파일 | 용도 |
|------|------|
| `scripts/wconcept_best_export.py` | 메인 크롤링 스크립트 (Playwright) |
| `scripts/generate_reports.py` | 주간/월간 리포트 생성 |
| `scripts/extract_best_categories.py` | 카테고리 구조 추출 |
| `scripts/log_utils.py` | 로깅 유틸리티 |

## ❓ 문제 해결

**Q1. 데이터가 업데이트 안 돼요**
→ Actions 탭에서 워크플로우 실행 상태 확인

**Q2. CSV 파일이 비어있어요**
→ 해당 날짜에 HACIE 상품이 베스트 200위 안에 없었을 수 있습니다

**Q3. 주간/월간 리포트가 생성 안 돼요**
→ 데이터가 충분하지 않을 수 있습니다 (최소 3일 이상 필요)

**Q4. 폴더 구조를 변경하고 싶어요**
→ `.github/workflows/track-hacie-daily.yml` 파일 수정

**Q5. 다른 브랜드도 추적하고 싶어요**
→ `scripts/wconcept_best_export.py`의 `ALLOWED_BRANDS` 수정

## 🔗 관련 링크

- [W컨셉 베스트 페이지](https://display.wconcept.co.kr/rn/best)
- [GitHub Actions 문서](https://docs.github.com/en/actions)
- [Playwright 문서](https://playwright.dev/python/)

## 📝 라이선스

MIT License

## 🤝 기여

이슈 및 풀 리퀘스트 환영합니다!

---

**Made with ❤️ for HACIE Brand Analytics**

*최종 업데이트: 2025-10-21*
