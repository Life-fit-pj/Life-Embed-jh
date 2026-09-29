"""검색 품질 잣대 — 검색어마다 "나와야 할 동네"를 적어 두고 몇 개 맞는지 센다.

실행:  py -m pipeline.golden_search          # data/golden/search.csv 전부
       py -m pipeline.golden_search --twice  # 두 번 돌려 흔들림(같은 문항이 다른 답)까지 본다

왜 설명문을 안 보나 — LLM 답은 매번 달라서, 흔들리는 것을 재면 실패가 신호가 못 된다.
흔들리지 않는 것은 "어느 동네가 TOP 5 에 들었나"다. 그것만 센다(hit@5).
설명문은 "기대단어가 들어 있나"만 본다(hint) — 근거 지표가 실렸는지 확인하는 보조 지표다.

왜 tests/ 가 아닌가 — 문항마다 Claude 2번 · 임베딩 3번이 나간다.
돈이 드는 검사는 자동으로 돌리지 않는다. 사람이 원할 때 돌리고 숫자를 기록한다.

측정 경로 = 실제 경로 — search() 를 그대로 부른다. 여기서 좋아졌는데 화면은 그대로인 일이 없게.
"""

import sys
import time

from app.core.config import DATA_DIR
from app.domain.dong import dong_variants
from app.engine.explain import find_cases
from app.engine.weights import find_similar_members
from app.services.search_service import search
from pipeline.io import read_csv, save_csv

GOLDEN = DATA_DIR / "golden" / "search.csv"       # 문항. 사람이 적는다
LAST_RUN = DATA_DIR / "golden" / "last_run.csv"   # 마지막 실행의 문항별 결과. 덮어쓴다

TOP_K = 5   # search() 의 기본값과 같아야 한다 — 다르면 여기서 맞아도 화면에선 틀린다


def _split(cell):
    """'대치1동|중계1동' -> ['대치1동', '중계1동']. 빈 칸이면 []"""
    return [x.strip() for x in (cell or "").split("|") if x.strip()]


def _dong(name):
    """'강남구 대치1동' -> '대치1동'. regions[*]['name'] 이 이 모양이다(explain.py 165행)"""
    return name.split(" ", 1)[-1]


def _hit(expected, got):
    """기대 동네 중 하나라도 TOP 5 에 있나. 표기 변형(고덕제1동/고덕1동)은 같은 것으로 본다"""
    got_set = {v for g in got for v in dong_variants(g)}
    return any(any(v in got_set for v in dong_variants(e)) for e in expected)


def run_one(row):
    """문항 하나를 실제 경로로 돌려 결과 한 줄을 만든다."""
    t0 = time.time()
    result = search(row["검색어"], top_k=TOP_K)
    elapsed = time.time() - t0

    got = [_dong(r["name"]) for r in result["regions"]]
    expected = _split(row["기대동네"])
    words = _split(row.get("기대단어"))

    # 같은 persona_query 로 유사 회원·사례를 다시 뽑아 점수 분포를 본다 — 임계값의 근거가 된다.
    # search() 안에서 이미 한 번 뽑았지만 점수를 돌려주지 않아 여기서 한 번 더 부른다(임베딩 2번)
    pq = result["persona_query"]
    member_scores = [score for _, (score, _, _) in find_similar_members(pq)]
    case_scores = [c["score"] for c in find_cases(pq)]

    return {
        "검색어": row["검색어"],
        "기대동네": row["기대동네"],
        "TOP5": "|".join(got),
        "hit": int(_hit(expected, got)),
        "hint": "" if not words else int(all(w in result["explanation"] for w in words)),
        "회원점수_최저": round(min(member_scores), 3) if member_scores else "",
        "사례점수_최저": round(min(case_scores), 3) if case_scores else "",
        "초": round(elapsed, 1),
    }


def run_all():
    """문항 전부. 문항별 한 줄씩 찍고 합계를 돌려준다."""
    _, rows = read_csv(GOLDEN)
    results = [run_one(row) for row in rows]

    # 이모지를 안 쓴다 — Windows 콘솔(cp949)에서 UnicodeEncodeError 로 죽는다(main.py 가 겪은 것)
    for r in results:
        mark = "O" if r["hit"] else "X"
        print(f"{mark} {r['검색어'][:22]:<22} 기대 {r['기대동네']:<18} -> {r['TOP5']}   ({r['초']}초)")

    hits = sum(r["hit"] for r in results)
    hinted = [r["hint"] for r in results if r["hint"] != ""]
    print()
    print(f"hit@{TOP_K}  {hits}/{len(results)}"
          + (f"   hint {sum(hinted)}/{len(hinted)}" if hinted else ""))

    floors = sorted(r["회원점수_최저"] for r in results if r["회원점수_최저"] != "")
    if floors:
        print(f"유사 회원 5명 중 최저 점수 — 가장 낮은 문항 {floors[0]} · 중앙값 {floors[len(floors) // 2]}")
    return results


def main():
    if not GOLDEN.exists():
        print(f"{GOLDEN} 가 없다. 교안 STEP 1 대로 먼저 만든다")
        return

    first = run_all()
    save_csv(first, LAST_RUN)

    if "--twice" in sys.argv:
        print("\n-- 두 번째 실행 (흔들림 확인) --")
        second = run_all()
        same = sum(a["TOP5"] == b["TOP5"] for a, b in zip(first, second))
        print(f"\nTOP5 가 두 번 다 같은 문항: {same}/{len(first)}  <- {len(first)} 에 가까울수록 재기 좋은 잣대다")


if __name__ == "__main__":
    main()
