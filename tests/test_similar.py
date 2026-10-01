"""기준 동네와의 닮음. 순수 계산이라 DB 를 안 읽는다."""

import numpy as np

from app.engine.recommend import nearest_base

# 동네 넷 · 지표 둘. 0번과 1번은 거의 같고, 2번은 정반대, 3번은 중간이다
SCORES = {"녹지": np.array([10.0, 12.0, 90.0, 40.0]), "교육": np.array([80.0, 78.0, 20.0, 60.0])}


def test_기준_동네_자신은_100이다():
    sim, _ = nearest_base(SCORES, [0])
    assert sim[0] == 100


def test_점수가_가까운_동네가_더_닮았다():
    sim, _ = nearest_base(SCORES, [0])
    assert sim.tolist() == [100.0, 98.0, 30.0, 75.0]


def test_기준이_여럿이면_가장_가까운_하나와_견준다():
    sim, nearest = nearest_base(SCORES, [0, 2])
    assert nearest.tolist() == [0, 0, 2, 0]
    assert sim[2] == 100          # 평균을 냈다면 0번도 2번도 100 이 못 된다
