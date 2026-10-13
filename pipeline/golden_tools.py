"""채팅 도구 선택 잣대 — 질문마다 "골라야 할 도구"를 적어 두고 Planner 가 맞게 고르는지 센다.

실행:  py -m pipeline.golden_tools          # data/golden/tool_select.csv 전부
       py -m pipeline.golden_tools --twice  # 두 번 돌려 흔들림(같은 문항이 다른 도구)까지 본다

왜 답변을 안 보나 — 도구를 잘못 고르면 답이 아무리 좋아도 근거가 틀린다. 여기서는 plan 한 단계만 잰다.
도구는 실행하지 않는다 — 고른 이름만 모은다. 그래서 DB 를 안 읽는다.

왜 tests/ 가 아닌가 — 돈이 든다. 60문항이면 한 바퀴에 Claude 60번, --twice 면 120번이다.
돈이 드는 검사는 자동으로 돌리지 않는다. 사람이 원할 때 돌리고 숫자를 docs/ 에 기록한다.

측정 경로 = 실제 경로 — chat_plan_node() 를 그대로 부른다. 도구 목록도 tool_specs() 그대로라
비회원에게는 회원 전용 도구가 아예 안 보인다. 그래도 오용 건수를 세는 것은 그 장치가 빠지는 날을 잡기 위해서다.
같은 도구가 동네마다 여러 번 불려도(비교 질문) 도구 이름의 집합으로 본다.
"""

import random
import sys
import time
from collections import Counter

from app.core.config import DATA_DIR
from app.graph.nodes import chat_plan_node
from app.tools.tools import MEMBER_TOOLS, TOOL_SPECS
from pipeline.io import read_csv, save_csv

GOLDEN = DATA_DIR / "golden" / "tool_select.csv"    # 문항. 사람이 적는다
LAST_RUN = DATA_DIR / "golden" / "last_tools.csv"   # 마지막 실행의 문항별 결과. 덮어쓴다

# 채팅 화면에 떠 있는 추천 다섯 곳. 문항이 이 동네 이름으로 묻는다
REGIONS = [{"name": f"서울특별시 {n}"} for n in
           ("강남구 대치1동", "노원구 중계1동", "마포구 서교동", "송파구 잠실3동", "성동구 성수1가1동")]
MEMBER_ID, GUEST_ID = "C001", "eval-guest"          # 회원 번호 꼴("C001")이어야 회원 도구가 보인다
NONE = "(없음)"


def _split(cell):
    """'a;b' -> {'a', 'b'}. 빈 칸이면 빈 집합"""
    return {x.strip() for x in (cell or "").split(";") if x.strip()}


def plan(question, member):
    """질문 하나를 실제 plan 노드에 넣고 고른 도구 이름의 집합을 돌려준다"""
    state = {"question": question, "regions": REGIONS, "history": [], "path": [],
             "anon_id": MEMBER_ID if member else GUEST_ID}
    return {call["name"] for call in chat_plan_node(state)["tool_calls"]}


def bootstrap_ci(hits, n_boot=2000, seed=0):
    """0/1 목록의 평균에 대한 95% 부트스트랩 구간"""
    rng = random.Random(seed)
    n = len(hits)
    means = sorted(sum(rng.choices(hits, k=n)) / n for _ in range(n_boot))
    return means[int(n_boot * 0.025)], means[int(n_boot * 0.975) - 1]


def score(rows):
    """문항별 결과(expected·got 집합, member) -> 지표 사전. LLM 을 안 부른다 — tests/ 가 이것을 지킨다"""
    exact = [int(r["expected"] == r["got"]) for r in rows]
    no_tool = [int(not r["got"]) for r in rows if not r["expected"]]

    per_tool = {}
    for spec in TOOL_SPECS:
        t = spec["name"]
        tp = sum(t in r["expected"] and t in r["got"] for r in rows)
        fp = sum(t not in r["expected"] and t in r["got"] for r in rows)
        fn = sum(t in r["expected"] and t not in r["got"] for r in rows)
        per_tool[t] = {
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "tp": tp, "fp": fp, "fn": fn,
        }

    # 틀린 문항에서 "빠진 도구 -> 대신 고른 도구". 한쪽이 비면 (없음)
    confusion = Counter()
    for r in rows:
        if r["expected"] == r["got"]:
            continue
        missed, extra = r["expected"] - r["got"], r["got"] - r["expected"]
        for m in missed or {NONE}:
            for e in extra or {NONE}:
                confusion[(m, e)] += 1

    return {
        "n": len(rows),
        "exact": sum(exact) / len(rows),
        "exact_ci": bootstrap_ci(exact),
        "no_tool": sum(no_tool) / len(no_tool) if no_tool else None,
        "member_misuse": sum(not r["member"] and bool(r["got"] & MEMBER_TOOLS) for r in rows),
        "per_tool": per_tool,
        "confusion": confusion,
    }


def instability(first, second):
    """두 바퀴에서 고른 도구가 다른 문항의 비율"""
    return sum(a["got"] != b["got"] for a, b in zip(first, second)) / len(first)


def run_all(save_to=None):
    _, rows = read_csv(GOLDEN)
    results = []
    try:
        for row in rows:
            member = row["member"] == "1"
            t0 = time.time()
            got = plan(row["question"], member)
            r = {"question": row["question"], "member": member,
                 "expected": _split(row["expected_tools"]), "got": got, "sec": round(time.time() - t0, 1)}
            results.append(r)
            # 이모지를 안 쓴다 — Windows 콘솔(cp949)에서 UnicodeEncodeError 로 죽는다
            mark = "O" if r["expected"] == got else "X"
            print(f"{mark} {row['question'][:28]:<28} 기대 {';'.join(sorted(r['expected'])) or NONE:<40} -> "
                  f"{';'.join(sorted(got)) or NONE}")
    finally:
        if save_to and results:
            save_csv([{**r, "expected": ";".join(sorted(r["expected"])), "got": ";".join(sorted(r["got"]))}
                      for r in results], save_to)
    return results


def report(s):
    lo, hi = s["exact_ci"]
    print(f"\n정확 일치율   {s['exact']:.1%}  (95% CI {lo:.1%} ~ {hi:.1%}, n={s['n']})")
    print(f"도구 불필요 정답률  {s['no_tool']:.1%}")
    print(f"회원 전용 도구 오용  {s['member_misuse']}건  <- 0 이어야 한다")
    print("\n도구                       precision  recall   (tp/fp/fn)")
    for name, m in s["per_tool"].items():
        p = "-" if m["precision"] is None else f"{m['precision']:.0%}"
        rc = "-" if m["recall"] is None else f"{m['recall']:.0%}"
        print(f"{name:<26} {p:>9}  {rc:>6}   ({m['tp']}/{m['fp']}/{m['fn']})")
    if s["confusion"]:
        print("\n혼동 (기대 -> 실제)")
        for (m, e), k in s["confusion"].most_common():
            print(f"  {m} -> {e}: {k}")


def main():
    first = run_all(save_to=LAST_RUN)
    report(score(first))

    if "--twice" in sys.argv:
        print("\n-- 두 번째 실행 (흔들림 확인) --")
        second = run_all()
        print(f"\n2회 실행 불일치율  {instability(first, second):.1%}  <- 0 에 가까울수록 재기 좋은 잣대다")


if __name__ == "__main__":
    main()
