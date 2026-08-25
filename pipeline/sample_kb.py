""" 
이 파이썬 파일이 하는 일 : LLM의 네모트론 기반 지식베이스 쌓기용 데이터 추출 (서울 구당 100명 총 2,500명 한정)
"""

#=================================
# 0. 준비
#=================================


import csv
import gzip     # 압축 파일을 그대로 읽게 해주는 파이썬 기본 모듈
import random
from collections import defaultdict

from core.config import DATA_DIR
from core.io import save_csv

# 구마다 몇 명씩 뽑을지. 최소 구(중구)가 2,539명이라 100명은 여유 있다
PER_DISTRICT = 100

SEED = 42       # 매번 같은 표본이 뽑히게 고정한다

SOURCE = DATA_DIR / "seoul_persona_full.csv.gz"
OUTPUT = DATA_DIR / "kb_persona.csv"


#=================================
# 1. 구 별 100명씩 인원 맞추기
#=================================

def sample_by_district(path, per_district = PER_DISTRICT, seed = SEED) :
    """구마다 per_district 명씩 뽑는다.
    
    구별 인원이 송파구 12,479명 ~ 중구 2,539명으로 4.9배 차이난다.
    무작위로 뽑으면 인구 비례로 뽑혀서 검색 결과가 큰 구에 쏠린다.
    그래서 구마다 같은 수로 맞춘다.
    """
    random.seed(seed)
    
    buckets = defaultdict(list)
    
    print(f"⏳ {path.name} 읽는 중... (18.5만 줄, 1~2분)")
    
    # gzip.open 에 "rt" 를 주면 압축을 풀면서 글자로 읽어준다
    with gzip.open(path, "rt", encoding = "utf-8-sig", newline = "") as f :
        for row in csv.DictReader(f):
            buckets[row["district"]].append(row)
    
    print(f"✅ {sum(len(v) for v in buckets.values()):,}명 · {len(buckets)}개 구")
    print()
    
    picked = []
    for district, rows in sorted(buckets.items()):
        chosen = random.sample(rows, min(per_district, len(rows)))      #random.sample(목록, 개수) : 목록에서 중복 없이 무작위로 그 개수만큼 꺼냄
        picked.extend(chosen)           # min(per_district, len(rows)) : 혹시 100명보다 적은 구가 있어도 에러 안 나게 하는 방어용도
        print(f"   💬 {district:14s} {len(rows):6,d}명 중 {len(chosen)}명")
    
    return picked

#if __name__ == "__main__":
#    picked = sample_by_district(SOURCE)
#    print()
#    print(f"✅ 표본 {len(picked):,}명")

if __name__ == "__main__" :
    picked = sample_by_district(SOURCE)
    print()
    print(f"✅ 표본 {len(picked):,}명")
    print()
    save_csv(picked, OUTPUT)








