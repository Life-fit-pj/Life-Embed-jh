"""
to_percentile([0, 0, 0, 5, 10])               -> [ 25.  25.  25.  75. 100.]
to_percentile([0, 0, 0, 5, 10], invert=True)  -> [ 75.  75.  75.  25.   0.]
to_percentile([1, 2, 3])                      -> [  0.  50. 100.]
"""
"""백분위 변환. 동점 처리가 깨지면 TOP 5 순위가 조용히 바뀐다."""

import numpy as np

from app.engine.recommend import to_percentile


def test_동점은_같은_점수를_받는다():
    got = to_percentile(np.array([0.0, 0.0, 0.0, 5.0, 10.0]))
    assert got.tolist() == [25.0, 25.0, 25.0, 75.0, 100.0]


def test_invert_는_방향을_뒤집는다():
    got = to_percentile(np.array([0.0, 0.0, 0.0, 5.0, 10.0]), invert=True)
    assert got.tolist() == [75.0, 75.0, 75.0, 25.0, 0.0]


def test_동점이_없으면_고르게_퍼진다():
    got = to_percentile(np.array([1.0, 2.0, 3.0]))
    assert got.tolist() == [0.0, 50.0, 100.0]
