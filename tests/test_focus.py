"""세부 강조 — 순위는 콕 집은 칸으로 매기고, 나가는 점수에는 지표 점수를 그대로 둔 채 세부 점수를 따로 싣는다."""

import numpy as np

from app.engine.recommend import apply_focus, focus_label, focus_scores

SCORES = {"교통": np.array([60.0, 40.0]), "교육": np.array([50.0, 50.0])}
COLUMNS = {"버스정류장_밀도": np.array([99.0, 10.0]), "지하철역_밀도": np.array([21.0, 70.0])}


def test_세부_점수는_이름표를_달고_따로_나온다():
    out = focus_scores(COLUMNS, {"교통": "버스"})
    assert list(out) == ["교통(버스)"] == [focus_label("교통", "버스")]
    assert out["교통(버스)"].tolist() == [99.0, 10.0]


def test_없는_짝은_싣지_않는다():
    assert focus_scores(COLUMNS, {"교통": "택시", "없는지표": "버스"}) == {}
    assert focus_scores(COLUMNS, None) == {}


def test_순위용_점수만_바뀌고_원본은_그대로다():
    ranked = apply_focus(SCORES, COLUMNS, {"교통": "버스"})
    assert ranked["교통"].tolist() == [99.0, 10.0]          # 순위는 버스만 본다
    assert SCORES["교통"].tolist() == [60.0, 40.0]          # 준비물은 안 건드린다
