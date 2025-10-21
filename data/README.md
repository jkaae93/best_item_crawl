# 📁 data/ 폴더

카테고리 정보 및 메타데이터 저장 폴더

## 파일 구조

```
data/
├── best_categories.json          # 베스트 카테고리 정보 (버전 관리)
└── category_version_log.json     # 카테고리 버전 변경 이력
```

## best_categories.json

W컨셉 베스트 페이지의 카테고리 구조 정보

**구조:**
```json
{
  "metadata": {
    "version": 1,
    "hash": "abc123...",
    "updated_at": "2025-10-21T08:00:00+09:00",
    "updated_at_kst": "2025년 10월 21일 08시 00분",
    "total_categories": 10,
    "changes": {...}
  },
  "category1DepthList": [...]
}
```

## category_version_log.json

카테고리 변경 이력

**구조:**
```json
{
  "versions": [
    {
      "version": 1,
      "timestamp": "2025-10-21T08:00:00+09:00",
      "old_hash": "...",
      "new_hash": "...",
      "changes": {...}
    }
  ]
}
```

## 사용 방법

### 카테고리 저장/업데이트

```bash
python3 scripts/manage_categories.py save tmp_wconcept_best_categories.json
```

### 변경사항 확인

```bash
python3 scripts/manage_categories.py check tmp_wconcept_best_categories.json
```

### 버전 히스토리 확인

```bash
python3 scripts/manage_categories.py history 10
```

## 자동 관리

GitHub Actions가 자동으로 관리합니다:
- 변경사항이 있을 때만 커밋
- 버전 번호 자동 증가
- 변경 이력 자동 기록

