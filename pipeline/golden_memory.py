"""장기 메모리 잣대 — 대화마다 "기억해야 할 선호"를 적어 두고, 칸 단위로 몇 개 맞는지 센다.

실행:  py -m pipeline.golden_memory

대화 하나는 회원이 보낸 질문 몇 개다(turns 칸, " | " 로 나눔). 실제 경로와 같이 질문마다
extract() 로 뽑고 merge() 로 합친 마지막 기억을 정답과 견준다. DB 에는 쓰지 않는다.

지표
  칸 일치율       (대화 × 칸 5개) 중 맞은 칸의 비율 + 95% 부트스트랩 구간(대화 단위로 다시 뽑는다)
  칸별 일치율     예산 · 거래유형 · 통근지 · 중요 지표 · 기피 조건
  지어낸 칸       정답이 빈 칸인데 무언가를 채운 수 — "말하지 않은 값은 추측하지 않는다" 를 잰다. 0 이어야 한다

왜 tests/ 가 아닌가 — Claude 를 질문마다 1번 부른다(지금 문항으로 25번). 돈이 드는 검사는 사람이 돌린다.
"""

import random

from app.core.config import DATA_DIR
from app.engine.memory import FIELDS, clean, empty, extract, merge
from pipeline.io import read_csv

GOLDEN = DATA_DIR / "golden" / "memory.csv"


def _list(cell):
    return [x.strip() for x in (cell or "").split(";") if x.strip()]


def expected(row):
    """CSV 한 줄 -> 정답 기억 (memory 모양)"""
    return clean({
        "budget_manwon": int(row["budget_manwon"]) if row["budget_manwon"].strip() else None,
        "deal_type": row["deal_type"].strip() or None,
        "commute": row["commute"].strip() or None,
        "priorities": _list(row["priorities"]),
        "avoid": _list(row["avoid"]),
    })


def _norm(text):
    return (text or "").replace(" ", "")


def field_ok(field, want, got):
    """칸 하나가 맞았나. 글로 적는 칸(통근지·기피)은 표기 차이("강남역"/"강남")를 봐준다"""
    if field == "commute":
        if not want or not got:
            return want == got
        return _norm(want) in _norm(got) or _norm(got) in _norm(want)
    if field == "avoid":
        if len(want) != len(got):
            return False
        return all(any(_norm(w) in _norm(g) or _norm(g) in _norm(w) for g in got) for w in want)
    if field == "priorities":
        return set(want) == set(got)
    return want == got


def score(rows):
    """[{"want": memory, "got": memory}] -> 지표. Claude 를 안 부른다 — tests/test_memory.py 가 지킨다"""
    per_conv = [[field_ok(f, r["want"][f], r["got"][f]) for f in FIELDS] for r in rows]
    made_up = sum(1 for r in rows for f in FIELDS if r["want"][f] in (None, []) and r["got"][f] not in (None, []))

    rng = random.Random(0)
    means = sorted(sum(sum(c) for c in sample) / (len(sample) * len(FIELDS))
                   for sample in (rng.choices(per_conv, k=len(per_conv)) for _ in range(2000)))
    return {
        "n": len(rows),
        "field_acc": sum(map(sum, per_conv)) / (len(rows) * len(FIELDS)),
        "field_acc_ci": (means[50], means[1949]),
        "per_field": {f: sum(c[i] for c in per_conv) / len(rows) for i, f in enumerate(FIELDS)},
        "made_up": made_up,
    }


def run_one(turns):
    memory = empty()
    for question in turns:
        memory = merge(memory, extract(question))
    return memory


def main():
    _, rows = read_csv(GOLDEN)
    results = []
    for row in rows:
        turns = [t.strip() for t in row["turns"].split("|") if t.strip()]
        r = {"want": expected(row), "got": run_one(turns)}
        results.append(r)
        bad = [f for f in FIELDS if not field_ok(f, r["want"][f], r["got"][f])]
        # 이모지를 안 쓴다 — Windows 콘솔(cp949)에서 UnicodeEncodeError 로 죽는다
        print(f"{'O' if not bad else 'X'} {row['turns'][:40]:<40} 틀린 칸 {bad or '-'}")
        if bad:
            print(f"    기대 {r['want']}\n    실제 {r['got']}")

    s = score(results)
    lo, hi = s["field_acc_ci"]
    print(f"\n칸 일치율  {s['field_acc']:.1%}  (95% CI {lo:.1%} ~ {hi:.1%}, 대화 {s['n']}개 × 칸 {len(FIELDS)}개)")
    for f, acc in s["per_field"].items():
        print(f"  {f:<14} {acc:.0%}")
    print(f"지어낸 칸  {s['made_up']}개  <- 0 이어야 한다")


if __name__ == "__main__":
    main()
