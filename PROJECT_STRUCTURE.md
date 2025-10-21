# 📁 프로젝트 구조

W컨셉 HACIE 브랜드 순위 자동 추적 시스템

## 디렉토리 구조

```
best_item_crawl/
├── .github/
│   └── workflows/
│       ├── track-hacie-daily.yml      # 일일 순위 추적 (매일 08:00 KST)
│       ├── weekly-report.yml          # 주간 리포트 (월요일 08:00 KST)
│       └── monthly-report.yml         # 월간 리포트 (매월 1일 08:00 KST)
│
├── data/                               # 카테고리 정보 저장
│   ├── best_categories.json           # 베스트 카테고리 (버전 관리)
│   ├── category_version_log.json      # 카테고리 변경 이력
│   └── README.md
│
├── output/                             # 추적 결과 저장 (Git 커밋)
│   ├── 2025/
│   │   ├── 10/
│   │   │   ├── 21/
│   │   │   │   ├── wconcept_best_*.csv         # 원본 데이터
│   │   │   │   └── 일일_요약.md                # 일일 요약
│   │   │   ├── 22/
│   │   │   ├── 2025년_10월_1주차_통계.md       # 주간 (마크다운)
│   │   │   ├── 2025년_10월_1주차_통계.csv      # 주간 (CSV)
│   │   │   ├── 2025년_10월_월간통계.md         # 월간 (마크다운)
│   │   │   └── 2025년_10월_월간통계.csv        # 월간 (CSV)
│   │   └── 11/
│   └── README.md
│
├── scripts/                            # 실행 스크립트
│   ├── __init__.py
│   ├── wconcept_best_export.py        # 메인 크롤링 (Playwright)
│   ├── generate_reports.py            # 주간/월간 리포트 생성
│   ├── manage_categories.py           # 카테고리 버전 관리
│   ├── extract_best_categories.py     # 카테고리 추출 유틸리티
│   └── log_utils.py                   # 로깅 유틸리티
│
├── .gitignore                          # Git 제외 파일
├── README.md                           # 프로젝트 설명서
├── PROJECT_STRUCTURE.md                # 이 파일
└── requirements.txt                    # Python 의존성
```

## 주요 컴포넌트

### GitHub Actions (3개)

1. **track-hacie-daily.yml** - 일일 추적
   - 실행: 매일 08:00 KST
   - 기능: 
     - W컨셉 베스트 크롤링
     - HACIE 상품 필터링
     - `output/yyyy/MM/dd/` 폴더에 저장
     - 일일 요약 생성
     - Git 커밋

2. **weekly-report.yml** - 주간 리포트
   - 실행: 매주 월요일 08:00 KST
   - 기간: 지난 주 월~일 (7일)
   - 생성: 마크다운 + CSV
   - 위치: `output/yyyy/MM/yyyy년_MM월_N주차_통계.*`

3. **monthly-report.yml** - 월간 리포트
   - 실행: 매월 1일 08:00 KST
   - 기간: 전월 1일~말일
   - 생성: 마크다운 + CSV
   - 위치: `output/yyyy/MM/yyyy년_MM월_월간통계.*`

### Python 스크립트 (5개)

1. **wconcept_best_export.py** (17KB)
   - 메인 크롤링 스크립트
   - Playwright 사용
   - API 자동 감청
   - CSV 생성

2. **generate_reports.py** (19KB)
   - 주간/월간 리포트 생성
   - 마크다운 + CSV 동시 생성
   - 자동 인사이트 생성

3. **manage_categories.py** (15KB)
   - 카테고리 버전 관리
   - 해시 기반 변경 감지
   - 변경 이력 추적

4. **extract_best_categories.py** (10KB)
   - HTML에서 카테고리 추출
   - Next.js 데이터 파싱
   - 유틸리티

5. **log_utils.py** (2KB)
   - 로깅 설정
   - 예외 처리

## 데이터 흐름

### 일일 추적
```
GitHub Actions (매일 08:00)
  ↓
wconcept_best_export.py
  ↓ Playwright로 크롤링
W컨셉 베스트 API
  ↓ HACIE 필터링
output/yyyy/MM/dd/wconcept_best_*.csv
  ↓ 요약 생성
output/yyyy/MM/dd/일일_요약.md
  ↓ Git 커밋
저장소에 자동 푸시
```

### 주간 리포트
```
GitHub Actions (월요일 08:00)
  ↓
generate_reports.py weekly
  ↓ 지난 7일 데이터 수집
output/yyyy/MM/dd/*.csv
  ↓ 통계 분석
주간 리포트 (MD + CSV)
  ↓ Git 커밋
저장소에 자동 푸시
```

### 월간 리포트
```
GitHub Actions (매월 1일 08:00)
  ↓
generate_reports.py monthly
  ↓ 전월 전체 데이터 수집
output/yyyy/MM/*.csv
  ↓ 종합 분석
월간 리포트 (MD + CSV)
  ↓ Git 커밋
저장소에 자동 푸시
```

### 카테고리 관리
```
베스트 페이지 HTML
  ↓
extract_best_categories.py
  ↓ 카테고리 추출
JSON 데이터
  ↓
manage_categories.py
  ↓ 해시 비교
변경 있음? → data/best_categories.json 업데이트 + 커밋
변경 없음? → 기존 파일 사용
```

## 파일 크기

| 파일 | 크기 | 용도 |
|------|------|------|
| wconcept_best_export.py | 17KB | 메인 로직 |
| generate_reports.py | 19KB | 리포트 생성 |
| manage_categories.py | 15KB | 카테고리 관리 |
| extract_best_categories.py | 10KB | 유틸리티 |
| log_utils.py | 2KB | 로깅 |

## Git 커밋 패턴

### 일일 추적
```
📊 HACIE 일일 순위 추적 (2025.10.21)

- 발견 상품: 15개
- 분석 시각: 2025년 10월 21일 08시
- 파일: output/2025/10/21/
```

### 주간 리포트
```
📊 주간 리포트 생성: 2025년 10월 3주차

- 분석 기간: 지난 주 월요일 ~ 일요일
- 생성 일시: 2025년 10월 21일
```

### 월간 리포트
```
📈 월간 리포트 생성: 2025년 10월

- 총 발견 상품: 425개
- 일평균: 14.2개
- 생성 일시: 2025년 11월 01일
```

### 카테고리 업데이트
```
🔄 카테고리 업데이트 (v2)

- 추가: 1개 카테고리
- 수정: 3개 카테고리
- 해시: abc123 → def456
```

## 의존성

```txt
requests==2.32.3        # HTTP 요청
playwright==1.55.0      # 브라우저 자동화
```

## 용량 추정

### 일일 데이터
- CSV: ~5KB/일
- 요약: ~2KB/일
- **월간 약 210KB**

### 월간 누적 (1년)
- 일일 데이터: ~2.5MB
- 주간 리포트: ~100KB
- 월간 리포트: ~50KB
- **연간 약 3MB**

## 정리 규칙

### 자동 삭제 (.gitignore)
- `tmp_*` - 임시 파일
- `debug_*` - 디버그 파일
- `test_*` - 테스트 파일
- `.vscode/`, `.idea/` - IDE 설정
- `__pycache__/` - Python 캐시

### 영구 보존
- `output/` - 모든 결과 데이터
- `data/` - 카테고리 정보
- `.github/workflows/` - CI/CD 설정
- `scripts/` - 핵심 스크립트

## 유지보수

### 정기 점검
- **매주**: Actions 실행 상태 확인
- **매월**: 저장소 용량 확인
- **분기**: 오래된 데이터 압축 고려

### 문제 해결
- Actions 탭에서 로그 확인
- 워크플로우 재실행 가능
- 수동 스크립트 실행 가능

---

*최종 정리 일자: 2025-10-21*

