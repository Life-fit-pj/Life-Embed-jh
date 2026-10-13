"""도구 선택 잣대의 채점(score)만 본다. Claude 는 안 부른다."""

from pipeline.golden_tools import NONE, instability, score


def _row(expected, got, member=True):
    return {"expected": set(expected), "got": set(got), "member": member}


def test_정확_일치와_도구_불필요():
    s = score([
        _row([], []),
        _row([], ["get_region_prices"]),
        _row(["get_region_prices"], ["get_region_prices"]),
        _row(["get_facility_counts"], ["get_facility_categories"]),
    ])
    assert s["exact"] == 0.5
    assert s["no_tool"] == 0.5
    assert s["per_tool"]["get_region_prices"] == {"precision": 0.5, "recall": 1.0, "tp": 1, "fp": 1, "fn": 0}
    assert s["confusion"] == {(NONE, "get_region_prices"): 1,
                              ("get_facility_counts", "get_facility_categories"): 1}


def test_비회원의_회원_전용_도구만_오용으로_센다():
    s = score([
        _row([], ["people_like_me"], member=False),
        _row(["people_like_me"], ["people_like_me"], member=True),
    ])
    assert s["member_misuse"] == 1


def test_빠진_도구는_없음으로_간다():
    s = score([_row(["get_facility_counts", "get_region_prices"], ["get_region_prices"])])
    assert s["confusion"] == {("get_facility_counts", NONE): 1}
    assert s["per_tool"]["get_facility_counts"]["recall"] == 0.0


def test_흔들림():
    a = [_row([], ["x"]), _row([], [])]
    b = [_row([], ["x"]), _row([], ["y"])]
    assert instability(a, b) == 0.5


def test_신뢰구간은_평균을_감싼다():
    s = score([_row([], [])] * 7 + [_row([], ["get_region_prices"])] * 3)
    lo, hi = s["exact_ci"]
    assert lo <= s["exact"] <= hi
