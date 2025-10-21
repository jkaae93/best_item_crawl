# 📁 data/ 폴더

카테고리 정보 캐시 저장 폴더

## 파일 구조

```
data/
├── README.md                 # 이 파일
└── category.json             # 베스트 카테고리 캐시 (75개 조합)
```

## category.json

W컨셉 베스트 페이지의 모든 카테고리 조합을 저장합니다.

### 구조

```json
[
  {
    "depth1_code": "ALL",
    "depth1_name": "전체",
    "depth2_code": "ALL",
    "depth2_name": "전체"
  },
  {
    "depth1_code": "10101",
    "depth1_name": "의류",
    "depth2_code": "ALL",
    "depth2_name": "전체"
  },
  {
    "depth1_code": "10101",
    "depth1_name": "의류",
    "depth2_code": "10101201",
    "depth2_name": "아우터"
  }
  ...
]
```

### 총 75개 카테고리 조합

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

## 🔄 자동 업데이트

### 작동 방식

1. **정상 모드 실행**:
   ```bash
   python3 scripts/wconcept_best_export.py
   ```
   - W컨셉 베스트 페이지 방문
   - `__NEXT_DATA__.bestCategories` 추출
   - 기존 `category.json`과 diff 비교
   - 변경 시 자동 업데이트

2. **빠른 모드 실행** (권장):
   ```bash
   python3 scripts/wconcept_best_export.py --skip-category-update
   ```
   - `category.json` 파일만 사용
   - Playwright 건너뛰기 (빠름)
   - 캐시 없으면 자동으로 정상 모드 실행

### 업데이트 로그 예시

```
✅ bestCategories 발견: 10개 depth1 카테고리
🎯 총 75개 카테고리 조합 추출
✓ 카테고리 변경 없음 (동일: 75개)
```

또는 변경 시:
```
🔄 카테고리 변경 감지: 75개 → 78개
💾 카테고리 저장 완료: 78개 → data/category.json
✅ 카테고리 캐시 업데이트 완료
```

## ⚙️ 수동 관리

필요시 JSON 파일을 직접 편집할 수 있습니다:

```bash
# 1. category.json 편집 (VSCode 등)
# 2. JSON 형식 검증
python3 -m json.tool data/category.json

# 3. Git 커밋
git add data/category.json
git commit -m "Update category list"
git push
```

## ⚠️ 주의사항

- ✅ Git으로 버전 관리됨
- ✅ GitHub Actions에서 자동 사용
- ⚠️ JSON 형식 유지 필수
- ⚠️ `depth1_code`, `depth2_code`는 W컨셉 API 스펙과 일치해야 함
- ⚠️ 잘못된 카테고리 코드 사용 시 데이터 수집 실패 가능

## 📋 카테고리 확인

현재 등록된 카테고리 확인:

```bash
cat data/category.json | python3 -m json.tool | grep "depth1_name"
```

카테고리 개수 확인:

```bash
cat data/category.json | python3 -c "import sys, json; print(f'총 {len(json.load(sys.stdin))}개 카테고리')"
```
