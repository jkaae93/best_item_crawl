feat: HACIE 브랜드 자동 순위 추적 시스템 구축

## 주요 기능

### 자동화 시스템
- 일일 순위 추적 (매일 08:00 KST)
- 주간 리포트 생성 (월요일 08:00 KST, 지난 주 월~일)
- 월간 리포트 생성 (매월 1일 08:00 KST, 전월 데이터)

### 데이터 관리
- yyyy/MM/dd 폴더 구조로 체계적 정리
- 마크다운(MD) + CSV 이중 형식 제공
- 카테고리 버전 관리 (해시 기반 변경 감지)
- Git 자동 커밋 및 이력 관리

### 리포트 종류
- 일일 요약: 당일 HACIE 상품 현황
- 주간 통계: 7일간 추이 분석, TOP 10
- 월간 통계: 전월 종합 분석, TOP 20, 성과 평가

## 구조

### GitHub Actions
- track-hacie-daily.yml: 일일 추적
- weekly-report.yml: 주간 리포트
- monthly-report.yml: 월간 리포트

### 스크립트
- wconcept_best_export.py: 메인 크롤링 (Playwright)
- generate_reports.py: 주간/월간 리포트 생성 (MD + CSV)
- manage_categories.py: 카테고리 버전 관리
- extract_best_categories.py: 카테고리 추출 유틸리티
- log_utils.py: 로깅

### 데이터 폴더
- data/: 카테고리 정보 (버전 관리)
- output/: 결과 데이터 (yyyy/MM/dd 구조)

## 삭제된 파일
- 임시 파일: tmp_*, runtime_*
- 디버그 파일: debug_*
- 테스트 파일: test_*
- 중복 워크플로우: wconcept-best-export.yml
- 청크 파일 폴더: all_chunks/, tmp_chunks/, tmp_chunks_all/

## API 정보
- 엔드포인트: POST https://gw-front.wconcept.co.kr/display/api/best/v1
- 브랜드: HACIE (하시에)

## 다음 단계
1. GitHub Settings에서 Actions 권한 설정 필요
2. 내일부터 자동 실행 시작
3. 월요일에 첫 주간 리포트 생성
4. 다음 달 1일에 첫 월간 리포트 생성

