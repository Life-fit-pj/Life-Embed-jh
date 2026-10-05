"""모델이 실제 DB 와 맞나.

2단계부터 app/db.py 의 SessionLocal 을 쓴다.
테스트가 자기 engine 을 만들지 않는다 — 그러면 "테스트는 통과하는데
실제 코드는 다른 DB 를 본다" 가 생길 수 있다.
"""

import pytest
import math
import numpy as np
from sqlalchemy import Float, func, inspect

from app.db import SessionLocal, engine
from app.models.chunk import Chunk
from app.models.customer import Customer
from app.models.history import AdminLog, AnalysisChat, ChatHistory, Like, SearchHistory, UserLogin
from app.models.preference import Preference
from app.core.config import ACTIVITY_COLUMN, EMBED_DIMENSION, INDICATORS


# 고정 데이터 — 파이프라인이 CSV 에서 넣은 몫만 센다. 다시 적재하기 전까지 줄 수가 안 변한다.
# 여기서 숫자가 틀리면 데이터가 유실된 것이므로 정확히 대조한다.
# 표 전체를 세지 않는다 — 가입 · 관리자 저장으로 회원(C101~) · 선호도 행 · 회원 조각이 늘어난다.
# 전체를 세면 "앱을 쓰면 깨지는 테스트" 가 된다(2026-10-05, C107 의 선호도 행이 생기며 실제로 깨졌다)
LOADED = "C100"             # 적재로 들어온 마지막 회원 번호
LOADED_CHUNK = (Chunk.source == "kb") | (Chunk.source_id <= LOADED)      # kb 전부 + 적재된 회원의 조각
FIXED = [
    (Customer, Customer.customer_id <= LOADED, 100),
    (Preference, Preference.customer_id <= LOADED, 100),
    (Chunk, LOADED_CHUNK, 9900),          # member 900 + kb 9,000
]

# 기록용 표 — 서버를 켜서 검색 한 번만 해도 늘어난다.
# 줄 수를 단언하면 "앱을 쓰면 깨지는 테스트" 가 되고, 그런 테스트는 곧 무시당한다.
GROWING = [Like, SearchHistory, ChatHistory, AnalysisChat, AdminLog, UserLogin]

ALL_MODELS = [model for model, _, _ in FIXED] + GROWING


@pytest.mark.parametrize("model,loaded,expected", FIXED, ids=[model.__name__ for model, _, _ in FIXED])
def test_적재된_몫은_줄_수가_맞는다(model, loaded, expected):
    db = SessionLocal()
    try:
        rows = db.query(func.count()).select_from(model).filter(loaded)
        if model is Chunk:      # 활동 조각은 관리자가 저장할 때마다 늘어난다 — 고정 데이터가 아니다
            rows = rows.filter(Chunk.category != ACTIVITY_COLUMN)
        assert rows.scalar() == expected
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


def test_가중치_칸은_모델도_DB도_실수다():
    """4.5 를 저장하면 4.5 로 읽혀야 한다 — 어느 한쪽만 정수여도 오류 없이 4 로 깎인다.

    모델이 Integer 면 SQLAlchemy 가 저장할 때 값에 ::INTEGER 를 붙여 보내고,
    DB 칸이 정수면 DB 가 깎는다. pipeline.schema 를 다시 돌린 뒤에도 실수인지 여기서 본다.
    실패하면 정수로 남은 칸의 이름이 찍힌다.
    """
    names = [*INDICATORS, *(f"{name}_초기" for name in INDICATORS)]

    model = Preference.__table__.c
    assert [n for n in names if not isinstance(model[n].type, Float)] == []

    actual = {c["name"]: c["type"] for c in inspect(engine).get_columns("user_preferences")}
    assert [n for n in names if not isinstance(actual[n], Float)] == []


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
            db.query(Chunk.source, func.count()).filter(Chunk.category != ACTIVITY_COLUMN, LOADED_CHUNK)
            .group_by(Chunk.source).all()
        )
        assert counts == {"member": 900, "kb": 9000}
    finally:
        db.close()
