"""모델이 실제 DB 와 맞나.

2단계부터 app/db.py 의 SessionLocal 을 쓴다.
테스트가 자기 engine 을 만들지 않는다 — 그러면 "테스트는 통과하는데
실제 코드는 다른 DB 를 본다" 가 생길 수 있다.
"""

import pytest
import math
import numpy as np
from sqlalchemy import func

from app.db import SessionLocal
from app.models.chunk import Chunk
from app.models.customer import Customer
from app.models.history import AdminLog, AnalysisChat, ChatHistory, Like, SearchHistory, UserLogin
from app.models.preference import Preference
from app.core.config import EMBED_DIMENSION


# 고정 데이터 — 파이프라인을 다시 돌리기 전까지 줄 수가 안 변한다.
# 여기서 숫자가 틀리면 데이터가 유실된 것이므로 정확히 대조한다.
FIXED = [
    (Customer, 104),
    (Preference, 102),
    (Chunk, 9914),          # member 900 + kb 9,000
]

# 기록용 표 — 서버를 켜서 검색 한 번만 해도 늘어난다.
# 줄 수를 단언하면 "앱을 쓰면 깨지는 테스트" 가 되고, 그런 테스트는 곧 무시당한다.
GROWING = [Like, SearchHistory, ChatHistory, AnalysisChat, AdminLog, UserLogin]

ALL_MODELS = [model for model, _ in FIXED] + GROWING


@pytest.mark.parametrize("model,expected", FIXED, ids=lambda v: getattr(v, "__name__", v))
def test_고정_표는_줄_수가_맞는다(model, expected):
    db = SessionLocal()
    try:
        assert db.query(func.count()).select_from(model).scalar() == expected
    finally:
        db.close()


@pytest.mark.parametrize("model", ALL_MODELS, ids=lambda v: v.__name__)
def test_모델의_칸_이름이_실제_표와_맞는다(model):
    """COUNT(*) 는 칸 이름을 하나도 안 본다. 오타가 나도 통과한다.

    db.query(model) 은 모델에 적은 칸을 전부 SELECT 하므로,
    줄이 하나도 없는 표에서도 없는 칸을 부르면 OperationalError 가 난다.
    기록용 표를 검사하는 방법이 이것이다 — 개수 말고 모양을 본다.
    """
    db = SessionLocal()
    try:
        db.query(model).limit(1).all()
    finally:
        db.close()



def test_한글_칸을_이름으로_꺼낼_수_있다():
    """INDICATORS 로 도는 코드가 3단계에서 그대로 돌아갈지 미리 본다."""
    from app.core.config import INDICATORS

    db = SessionLocal()
    try:
        row = db.query(Preference).filter(Preference.customer_id == "C001").first()
        assert row is not None
        assert all(getattr(row, ind) is not None for ind in INDICATORS)
    finally:
        db.close()


def test_임베딩이_1536개다():
    """Text 에 JSON 으로 담은 게 맞는지. 옛 이진 칸으로 남아 있으면 여기서 깨진다.

    길이만 보지 않고 길이가 1 인지도 본다 — weights.py 의 `vectors @ q` 가
    그걸 전제로 돌기 때문이다(6-11절)
    """
    db = SessionLocal()
    try:
        vector = db.query(Chunk).first().embedding

        assert len(vector) == EMBED_DIMENSION
        assert math.isclose(float(np.linalg.norm(vector)), 1.0, abs_tol=1e-3)
    finally:
        db.close()


def test_chunks_는_source_로_나뉜다():
    """합계 9,900 만 세면 source 가 전부 한쪽으로 쏠려도 통과한다."""
    db = SessionLocal()
    try:
        counts = dict(
            db.query(Chunk.source, func.count()).group_by(Chunk.source).all()
        )
        assert counts == {"member": 914, "kb": 9000}
    finally:
        db.close()
