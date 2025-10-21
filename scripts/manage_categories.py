#!/usr/bin/env python3
"""
W컨셉 베스트 카테고리 버전 관리
변경사항이 있을 때만 업데이트하고 커밋
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from zoneinfo import ZoneInfo


class CategoryVersionManager:
    """카테고리 버전 관리 시스템"""
    
    def __init__(self, base_dir: Path = None):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        
        self.base_dir = base_dir
        self.categories_file = base_dir / 'data' / 'best_categories.json'
        self.version_log = base_dir / 'data' / 'category_version_log.json'
        
        # 폴더 생성
        self.categories_file.parent.mkdir(parents=True, exist_ok=True)
    
    def calculate_hash(self, data: Dict) -> str:
        """
        카테고리 데이터의 해시값 계산
        
        Args:
            data: 카테고리 데이터
            
        Returns:
            SHA256 해시값
        """
        # 버전 정보를 제외한 순수 카테고리 데이터만 해시 계산
        if 'category1DepthList' in data:
            category_data = data['category1DepthList']
        else:
            category_data = data
        
        # JSON 문자열로 변환 (정렬하여 일관성 유지)
        json_str = json.dumps(category_data, sort_keys=True, ensure_ascii=False)
        
        # SHA256 해시 계산
        hash_obj = hashlib.sha256(json_str.encode('utf-8'))
        return hash_obj.hexdigest()
    
    def load_current_categories(self) -> Optional[Dict]:
        """현재 저장된 카테고리 로드"""
        if not self.categories_file.exists():
            return None
        
        try:
            with open(self.categories_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"카테고리 로드 실패: {e}")
            return None
    
    def save_categories(self, new_data: Dict, force: bool = False) -> Dict[str, any]:
        """
        카테고리 저장 (변경사항이 있을 때만)
        
        Args:
            new_data: 새로운 카테고리 데이터
            force: 강제 저장 여부
            
        Returns:
            결과 딕셔너리 (changed, old_hash, new_hash, version)
        """
        # 현재 데이터 로드
        current_data = self.load_current_categories()
        
        # 새 데이터 해시 계산
        new_hash = self.calculate_hash(new_data)
        
        # 기존 데이터가 있으면 비교
        if current_data and not force:
            old_hash = current_data.get('metadata', {}).get('hash', '')
            
            if old_hash == new_hash:
                # 변경사항 없음
                return {
                    'changed': False,
                    'old_hash': old_hash,
                    'new_hash': new_hash,
                    'version': current_data.get('metadata', {}).get('version', 1),
                    'message': '카테고리 변경사항 없음'
                }
        
        # 버전 번호 증가
        if current_data:
            version = current_data.get('metadata', {}).get('version', 0) + 1
            old_hash = current_data.get('metadata', {}).get('hash', '')
        else:
            version = 1
            old_hash = ''
        
        # 메타데이터 추가
        kst = ZoneInfo("Asia/Seoul")
        now = datetime.now(kst)
        
        metadata = {
            'version': version,
            'hash': new_hash,
            'updated_at': now.isoformat(),
            'updated_at_kst': now.strftime('%Y년 %m월 %d일 %H시 %M분'),
            'total_categories': len(new_data.get('category1DepthList', [])),
        }
        
        # 변경사항 분석
        changes = self.analyze_changes(current_data, new_data)
        metadata['changes'] = changes
        
        # 저장할 데이터 구성
        save_data = {
            'metadata': metadata,
            'category1DepthList': new_data.get('category1DepthList', new_data)
        }
        
        # 파일 저장
        with open(self.categories_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        # 버전 로그 업데이트
        self.update_version_log(version, old_hash, new_hash, changes, now)
        
        return {
            'changed': True,
            'old_hash': old_hash,
            'new_hash': new_hash,
            'old_version': version - 1 if version > 1 else 0,
            'new_version': version,
            'changes': changes,
            'message': f'카테고리 업데이트 (v{version})'
        }
    
    def analyze_changes(self, old_data: Optional[Dict], new_data: Dict) -> Dict:
        """
        카테고리 변경사항 분석
        
        Args:
            old_data: 기존 데이터
            new_data: 새 데이터
            
        Returns:
            변경사항 딕셔너리
        """
        if not old_data:
            return {
                'type': 'initial',
                'description': '초기 카테고리 생성'
            }
        
        old_categories = old_data.get('category1DepthList', [])
        new_categories = new_data.get('category1DepthList', new_data if isinstance(new_data, list) else [])
        
        # 카테고리 코드별로 매핑
        old_map = {cat['depth1Code']: cat for cat in old_categories}
        new_map = {cat['depth1Code']: cat for cat in new_categories}
        
        old_codes = set(old_map.keys())
        new_codes = set(new_map.keys())
        
        # 추가/삭제/수정 감지
        added = new_codes - old_codes
        removed = old_codes - new_codes
        common = old_codes & new_codes
        
        modified = []
        for code in common:
            old_cat = old_map[code]
            new_cat = new_map[code]
            
            # 이름 변경
            if old_cat.get('depth1Name') != new_cat.get('depth1Name'):
                modified.append({
                    'code': code,
                    'type': 'name_changed',
                    'old': old_cat.get('depth1Name'),
                    'new': new_cat.get('depth1Name')
                })
            
            # 상품 수 변경 (10% 이상 차이)
            old_count = old_cat.get('depth1Count', 0)
            new_count = new_cat.get('depth1Count', 0)
            if old_count > 0 and abs(new_count - old_count) / old_count > 0.1:
                modified.append({
                    'code': code,
                    'type': 'count_changed',
                    'name': new_cat.get('depth1Name'),
                    'old': old_count,
                    'new': new_count,
                    'change_percent': ((new_count - old_count) / old_count * 100)
                })
            
            # 서브 카테고리 변경
            old_subs = old_cat.get('category2DepthList', [])
            new_subs = new_cat.get('category2DepthList', [])
            
            if old_subs and new_subs:
                old_sub_codes = {s.get('depth2Code') for s in old_subs}
                new_sub_codes = {s.get('depth2Code') for s in new_subs}
                
                added_subs = new_sub_codes - old_sub_codes
                removed_subs = old_sub_codes - new_sub_codes
                
                if added_subs or removed_subs:
                    modified.append({
                        'code': code,
                        'type': 'subcategory_changed',
                        'name': new_cat.get('depth1Name'),
                        'added_subs': len(added_subs),
                        'removed_subs': len(removed_subs)
                    })
        
        return {
            'type': 'update',
            'added_categories': [new_map[code]['depth1Name'] for code in added],
            'removed_categories': [old_map[code]['depth1Name'] for code in removed],
            'modified_categories': modified,
            'summary': f"추가 {len(added)}개, 삭제 {len(removed)}개, 수정 {len(modified)}개"
        }
    
    def update_version_log(self, version: int, old_hash: str, new_hash: str, changes: Dict, timestamp: datetime):
        """버전 로그 업데이트"""
        # 기존 로그 로드
        if self.version_log.exists():
            with open(self.version_log, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
        else:
            log_data = {'versions': []}
        
        # 새 버전 추가
        log_entry = {
            'version': version,
            'timestamp': timestamp.isoformat(),
            'timestamp_kst': timestamp.strftime('%Y년 %m월 %d일 %H시 %M분'),
            'old_hash': old_hash[:8],  # 앞 8자리만
            'new_hash': new_hash[:8],
            'changes': changes
        }
        
        log_data['versions'].append(log_entry)
        
        # 최근 100개만 유지
        if len(log_data['versions']) > 100:
            log_data['versions'] = log_data['versions'][-100:]
        
        # 저장
        with open(self.version_log, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
    
    def get_version_history(self, limit: int = 10) -> List[Dict]:
        """버전 히스토리 조회"""
        if not self.version_log.exists():
            return []
        
        with open(self.version_log, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        
        versions = log_data.get('versions', [])
        return versions[-limit:] if limit else versions
    
    def generate_change_report(self, changes: Dict) -> str:
        """변경사항 리포트 생성"""
        report = "# 카테고리 변경사항 리포트\n\n"
        
        if changes['type'] == 'initial':
            report += "## ✨ 초기 카테고리 생성\n\n"
            return report
        
        report += f"## 📊 변경 요약\n\n{changes['summary']}\n\n"
        
        if changes.get('added_categories'):
            report += "### ➕ 추가된 카테고리\n\n"
            for cat in changes['added_categories']:
                report += f"- {cat}\n"
            report += "\n"
        
        if changes.get('removed_categories'):
            report += "### ➖ 삭제된 카테고리\n\n"
            for cat in changes['removed_categories']:
                report += f"- {cat}\n"
            report += "\n"
        
        if changes.get('modified_categories'):
            report += "### 🔄 수정된 카테고리\n\n"
            for mod in changes['modified_categories']:
                if mod['type'] == 'name_changed':
                    report += f"- **{mod['code']}**: 이름 변경 `{mod['old']}` → `{mod['new']}`\n"
                elif mod['type'] == 'count_changed':
                    sign = "📈" if mod['new'] > mod['old'] else "📉"
                    report += f"- {sign} **{mod['name']}**: 상품 수 {mod['old']:,}개 → {mod['new']:,}개 ({mod['change_percent']:+.1f}%)\n"
                elif mod['type'] == 'subcategory_changed':
                    report += f"- **{mod['name']}**: 서브카테고리 변경 (추가 {mod['added_subs']}개, 삭제 {mod['removed_subs']}개)\n"
            report += "\n"
        
        return report


def main():
    """메인 함수"""
    import sys
    
    manager = CategoryVersionManager()
    
    if len(sys.argv) < 2:
        print("사용법:")
        print("  저장: python manage_categories.py save <json_file>")
        print("  확인: python manage_categories.py check <json_file>")
        print("  히스토리: python manage_categories.py history [limit]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'save':
        if len(sys.argv) < 3:
            print("JSON 파일 경로를 지정하세요")
            sys.exit(1)
        
        json_file = Path(sys.argv[2])
        
        if not json_file.exists():
            print(f"파일이 없습니다: {json_file}")
            sys.exit(1)
        
        # JSON 로드
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 저장
        result = manager.save_categories(data)
        
        print(f"✓ {result['message']}")
        
        if result['changed']:
            print(f"  - 버전: v{result['old_version']} → v{result['new_version']}")
            print(f"  - 해시: {result['old_hash'][:8]} → {result['new_hash'][:8]}")
            print(f"  - 변경사항: {result['changes']['summary']}")
            
            # 변경 리포트 생성
            report = manager.generate_change_report(result['changes'])
            report_file = manager.categories_file.parent / 'category_changes.md'
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"  - 리포트: {report_file}")
        else:
            print(f"  - 현재 버전: v{result['version']}")
            print(f"  - 해시: {result['new_hash'][:8]}")
    
    elif command == 'check':
        if len(sys.argv) < 3:
            print("JSON 파일 경로를 지정하세요")
            sys.exit(1)
        
        json_file = Path(sys.argv[2])
        
        if not json_file.exists():
            print(f"파일이 없습니다: {json_file}")
            sys.exit(1)
        
        # 새 데이터 로드
        with open(json_file, 'r', encoding='utf-8') as f:
            new_data = json.load(f)
        
        new_hash = manager.calculate_hash(new_data)
        
        # 현재 데이터 로드
        current_data = manager.load_current_categories()
        
        if current_data:
            old_hash = current_data.get('metadata', {}).get('hash', '')
            version = current_data.get('metadata', {}).get('version', 0)
            
            if old_hash == new_hash:
                print(f"✓ 변경사항 없음 (v{version}, {old_hash[:8]})")
                sys.exit(0)
            else:
                print(f"✓ 변경사항 있음")
                print(f"  - 현재: v{version} ({old_hash[:8]})")
                print(f"  - 새로운: {new_hash[:8]}")
                sys.exit(1)
        else:
            print(f"✓ 초기 카테고리 ({new_hash[:8]})")
            sys.exit(1)
    
    elif command == 'history':
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        
        history = manager.get_version_history(limit)
        
        if not history:
            print("버전 히스토리가 없습니다.")
            return
        
        print(f"최근 {len(history)}개 버전 히스토리:\n")
        
        for entry in reversed(history):
            print(f"v{entry['version']} - {entry['timestamp_kst']}")
            print(f"  해시: {entry['old_hash']} → {entry['new_hash']}")
            print(f"  변경: {entry['changes'].get('summary', entry['changes'].get('description', 'N/A'))}")
            print()


if __name__ == '__main__':
    main()

