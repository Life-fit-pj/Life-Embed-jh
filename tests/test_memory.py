"""장기 메모리의 순수 규칙(engine/memory.py)과 평가 채점(pipeline/golden_memory.py). Claude 도 DB 도 안 부른다."""

from app.engine.memory import (
    LIST_LIMIT, MEMORY_CHARS, SCHEMA, FIELDS, clean, empty, is_empty, merge, to_prompt_line,
)
from pipeline.golden_memory import field_ok, score


def test_스키마는_칸을_전부_요구하고_다른_칸을_막는다():
    # Structured Outputs 는 required 에 없는 칸을 빼먹을 수 있고, additionalProperties 가 열려 있으면 칸을 지어낸다
    assert set(SCHEMA["required"]) == set(FIELDS) == set(SCHEMA["properties"])
    assert SCHEMA["additionalProperties"] is False


def test_말하지_않은_값은_비어_있다():
    m = clean({"deal_type": "전세"})
    assert m == {**empty(), "deal_type": "전세"}
    assert is_empty({}) and is_empty(None)


def test_모양이_틀린_값은_믿지_않고_비운다():
    m = clean({"budget_manwon": "3억", "deal_type": "반전세", "priorities": ["교육", "학군", "교육"],
               "avoid": ["", 3, "언덕"], "commute": "   "})
    assert m == {**empty(), "priorities": ["교육"], "avoid": ["언덕"]}
    assert clean({"budget_manwon": True})["budget_manwon"] is None
    assert clean({"budget_manwon": -5})["budget_manwon"] is None


def test_합칠_때_새로_말한_칸만_덮는다():
    old = {"budget_manwon": 30000, "deal_type": "전세", "commute": "강남역", "priorities": ["교육"], "avoid": ["언덕"]}
    new = {"budget_manwon": 40000, "priorities": ["안전"]}
    m = merge(old, new)
    assert m["budget_manwon"] == 40000
    assert m["deal_type"] == "전세" and m["commute"] == "강남역"
    assert m["priorities"] == ["안전", "교육"]
    assert m["avoid"] == ["언덕"]


def test_목록은_새_것부터_상한까지만():
    old = {"avoid": [f"옛{i}" for i in range(LIST_LIMIT)]}
    m = merge(old, {"avoid": ["새것"]})
    assert m["avoid"][0] == "새것" and len(m["avoid"]) == LIST_LIMIT


def test_주입_글은_짧고_읽을_수_있다():
    line = to_prompt_line({"budget_manwon": 35000, "deal_type": "전세", "commute": "강남역",
                           "priorities": ["교육", "안전"], "avoid": ["언덕"]})
    assert line == "예산 3억 5,000만원 · 전세 · 통근 강남역 · 중요 교육, 안전 · 피함 언덕"
    assert to_prompt_line({"budget_manwon": 30000}) == "예산 3억"
    assert to_prompt_line({"budget_manwon": 5000}) == "예산 5,000만원"
    assert to_prompt_line(None) == ""


def test_주입_길이_상한():
    # 칸마다 길이·개수 상한(clean)까지 꽉 채운 최악의 경우도 MEMORY_CHARS 안에 든다
    huge = {"budget_manwon": 99999, "deal_type": "매매", "commute": "가" * 30,
            "priorities": ["녹지", "안전", "교통", "상권", "의료"], "avoid": [f"{'나' * 19}{i}" for i in range(5)]}
    assert len(to_prompt_line(huge)) <= MEMORY_CHARS


def test_평가_채점():
    assert field_ok("commute", "강남역", "강남 역")
    assert not field_ok("commute", None, "강남역")
    assert field_ok("avoid", ["언덕"], ["가파른 언덕"])
    assert not field_ok("avoid", [], ["언덕"])
    want = {**empty(), "deal_type": "전세"}
    s = score([{"want": want, "got": {**want, "commute": "판교"}}])
    assert s["made_up"] == 1
    assert s["field_acc"] == 4 / 5
    assert s["per_field"]["deal_type"] == 1.0
