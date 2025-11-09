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
best_item_crawl/
├── data/
│   ├── category.json                  # 카테고리 캐시 (75개 조합)
│   └── README.md
├── output/
│   ├── 2025/
│   │   ├── 10/
│   │   │   ├── 21/
│   │   │   │   ├── wconcept_best_20251021_0800_KST.csv     # 원본 데이터
│   │   │   │   └── 일일_요약.md                             # 일일 요약
│   │   │   ├── 22/
│   │   │   │   ├── wconcept_best_20251022_0800_KST.csv
│   │   │   │   └── 일일_요약.md
│   │   │   ├── 2025년_10월_1주차_통계.md                    # 주간 리포트
│   │   │   ├── 2025년_10월_2주차_통계.md
│   │   │   └── 2025년_10월_월간통계.md                      # 월간 리포트
│   │   └── 11/
│   │       ├── 01/
│   │       └── 2025년_11월_1주차_통계.md
│   └── README.md
├── scripts/
│   ├── wconcept_best_export.py        # 메인 크롤링
│   ├── generate_reports.py            # 리포트 생성
│   └── ...
└── requirements.txt
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
   https://github.com/kaae/best_item_crawl
   ```

2. **최신 데이터 확인**
   - `output/2025/10/21/` 폴더로 이동
   - `일일_요약.md` 파일 클릭 (마크다운은 바로 읽기 가능)
   - `wconcept_best_*.csv` 다운로드 (Excel로 분석)

3. **주간/월간 리포트**
   - `output/2025/10/` 폴더에서 리포트 확인
   - `*주차_통계.md`: 주간 분석 + 참고 데이터 파일 링크
   - `*월간통계.md`: 월간 종합 분석 + 참고 데이터 파일 링크

### 로컬 실행 (개발자용)

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 일일 크롤링 실행 (빠른 모드 - 권장)
python3 scripts/wconcept_best_export.py --skip-category-update

# 3. 일일 크롤링 실행 (카테고리 업데이트 포함)
python3 scripts/wconcept_best_export.py

# 4. 테스트 실행 (3개 카테고리만)
python3 scripts/wconcept_best_export.py --skip-category-update --test-mode

# 5. 주간 리포트 생성 (슬랙 알림 포함)
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
python3 scripts/generate_reports.py weekly 2025 10 3

# 6. 월간 리포트 생성 (슬랙 알림 포함)
python3 scripts/generate_reports.py monthly 2025 10

# 7. 일일 리포트 생성
python3 scripts/generate_reports.py daily output/2025/10/21/wconcept_best_*.csv output/2025/10/21/일일_요약.md
```

## 📊 데이터 구조

### CSV 파일 컬럼

| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| `날짜` | 수집 날짜 | `2025-10-21` |
| `시간` | 수집 시간 | `08:00` |
| `depth1_카테고리` | 메인 카테고리명 | `의류` |
| `depth2_카테고리` | 서브 카테고리명 | `아우터` |
| `순위` | 베스트 순위 | `13` |
| `상품명` | 상품명 | `CASHMERE COLLAR LIGHT DOWN JACKET` |
| `가격` | 최종 판매가 | `114988` |

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
- **참고 데이터 파일 링크** (클릭 가능)
- 자동 인사이트 및 추천 액션

**3. 월간 통계** (`yyyy년_MM월_월간통계.md`)
- 월간 총 발견 상품 수 / 일평균
- 주별 추이 (1주차 ~ 4-5주차)
- 카테고리별 월간 통계
- 월간 베스트 TOP 20
- 가격대 분석
- 성과 평가 (S/A/B/C 등급)
- **참고 데이터 파일 링크** (클릭 가능)
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

3. **슬랙 알림 설정 (선택사항)**
   - 슬랙 워크스페이스에서 Incoming Webhook 생성:
     1. https://api.slack.com/apps 접속
     2. "Create New App" → "From scratch"
     3. "Incoming Webhooks" 활성화
     4. "Add New Webhook to Workspace"
     5. 알림 받을 채널 선택
     6. Webhook URL 복사 (예: `https://hooks.slack.com/services/...`)
   
   - GitHub 저장소 → Settings → Secrets and variables → Actions
   - "New repository secret" 클릭
   - Name: `SLACK_WEBHOOK_URL`
   - Secret: 복사한 Webhook URL 붙여넣기
   - "Add secret" 클릭
   
   **알림 내용:**
   - ✅ 주간 리포트 생성 성공 시 슬랙 알림
   - ✅ 월간 리포트 생성 성공 시 슬랙 알림
   - 🚨 모든 리포트 생성 실패 시 슬랙 알림

4. **이메일 알림 설정 (선택사항)**
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

## 📊 주요 카테고리

### 수집 범위 (총 75개 카테고리 조합)

| Depth1 | 이름 | Depth2 개수 |
|--------|------|:-----------:|
| ALL | 전체 | 1개 |
| 10101 | 의류 | 13개 (전체 포함) |
| 10102 | 가방 | 10개 (전체 포함) |
| 10103 | 신발 | 11개 (전체 포함) |
| 10104 | 액세서리 | 9개 (전체 포함) |
| 10107 | 뷰티 | 9개 (전체 포함) |
| 10108 | 라이프 | 6개 (전체 포함) |
| 10109 | 키즈 | 7개 (전체 포함) |
| 10106 | 레저 | 5개 (전체 포함) |
| 10105 | 해외브랜드 | 5개 (전체 포함) |

**전체 카테고리 목록**: [`data/category.json`](data/category.json)

### 카테고리 자동 업데이트

- 매 실행 시 W컨셉 베스트 페이지에서 최신 카테고리 추출
- `data/category.json`과 비교하여 변경 시 자동 업데이트
- `--skip-category-update` 옵션으로 캐시만 사용 가능 (빠름)

## 🛠️ 스크립트 설명

| 파일 | 용도 |
|------|------|
| `scripts/wconcept_best_export.py` | 메인 크롤링 스크립트 |
| `scripts/generate_reports.py` | 주간/월간 리포트 생성 (Python 표준 라이브러리만 사용) |
| `scripts/extract_best_categories.py` | 카테고리 구조 추출 (참고용) |
| `scripts/manage_categories.py` | 카테고리 관리 유틸리티 (참고용) |
| `data/category.json` | 카테고리 캐시 (자동 생성/업데이트) |

### 주요 옵션

| 옵션 | 설명 | 사용 예시 |
|------|------|----------|
| `--skip-category-update` | Playwright 건너뛰고 캐시만 사용 (빠름) | `--skip-category-update` |
| `--test-mode` | 처음 3개 카테고리만 테스트 | `--test-mode` |
| `--max-pages N` | 카테고리당 최대 N페이지 수집 | `--max-pages 2` |
| `--page-size N` | 페이지당 상품 수 | `--page-size 200` |

## ❓ 문제 해결

**Q1. 데이터가 업데이트 안 돼요**
→ Actions 탭에서 워크플로우 실행 상태 확인

**Q2. CSV 파일이 비어있어요**
→ 해당 날짜에 HACIE 상품이 베스트에 없었을 수 있습니다

**Q3. 주간/월간 리포트가 생성 안 돼요**
→ 데이터가 충분하지 않을 수 있습니다 (최소 3일 이상 필요)

**Q4. 500 에러가 발생해요**
→ 일시적인 서버 에러입니다. 재시도 로직이 자동으로 작동합니다.

**Q5. 카테고리를 수동으로 업데이트하고 싶어요**
→ `--skip-category-update` 옵션 없이 실행하면 자동 업데이트됩니다.

**Q6. 다른 브랜드도 추적하고 싶어요**
→ `scripts/wconcept_best_export.py`의 `ALLOWED_BRANDS` 수정

**Q7. 더 빠르게 실행하고 싶어요**
→ `--skip-category-update` 옵션 사용 (Playwright 건너뛰기)

**Q8. 슬랙 알림이 오지 않아요**
→ GitHub Secrets에 `SLACK_WEBHOOK_URL`이 올바르게 설정되었는지 확인하세요

**Q9. 슬랙 알림을 비활성화하고 싶어요**
→ GitHub Secrets에서 `SLACK_WEBHOOK_URL`을 삭제하면 알림이 비활성화됩니다

## 🔧 기술 스택

- **Python 3.10+**: 메인 스크립트
- **Playwright**: 웹 스크래핑 (선택적 - 카테고리 업데이트 시만)
- **Requests**: HTTP API 호출
- **GitHub Actions**: 자동 실행 (Docker 컨테이너)
- **Docker**: `mcr.microsoft.com/playwright/python:v1.55.0-jammy`

### 성능 최적화

- ✅ **캐시 시스템**: `data/category.json`으로 Playwright 실행 최소화
- ✅ **Docker 이미지**: Playwright 사전 설치로 빠른 실행
- ✅ **재시도 로직**: 일시적 API 에러 자동 복구
- ✅ **Git 충돌 방지**: 자동 fetch/merge/push 재시도

## 🔗 관련 링크

- [W컨셉 베스트 페이지](https://display.wconcept.co.kr/rn/best)
- [GitHub Actions 문서](https://docs.github.com/en/actions)
- [Playwright Python](https://playwright.dev/python/)

## 📝 라이선스

MIT License

## 🤝 기여

이슈 및 풀 리퀘스트 환영합니다!

---

**Made with ❤️ for HACIE Brand Analytics**

*최종 업데이트: 2025-10-22*
