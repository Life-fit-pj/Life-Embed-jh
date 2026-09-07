"""모델이 실제 DB 와 맞나. 1단계 확인용.

2단계에서 app/db.py 가 생기면 그걸 쓰도록 위쪽 세 줄만 고친다.
"""

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.core.config import DB_PATH
from app.models.chunk import KbChunk, MemberChunk
from app.models.customer import Customer
from app.models.history import AdminLog, AnalysisChat, ChatHistory, Like, SearchHistory
from app.models.preference import Preference

engine = create_engine(f"sqlite:///{DB_PATH}")
Session = sessionmaker(bind=engine)

# (모델, 실제로 들어 있어야 할 줄 수) — 0 은 "표는 있는데 비어 있다"
EXPECTED = [
    (Customer, 100),
    (Preference, 100),
    (MemberChunk, 900),
    (KbChunk, 9000),
    (Like, 0),
    (SearchHistory, 0),
    (ChatHistory, 0),
    (AnalysisChat, 0),
    (AdminLog, 0),
]


@pytest.mark.parametrize("model,expected", EXPECTED, ids=lambda v: getattr(v, "__name__", v))
def test_모델이_실제_표와_맞는다(model, expected):
    db = Session()
    try:
        assert db.query(func.count()).select_from(model).scalar() == expected
    finally:
        db.close()


def test_한글_칸을_이름으로_꺼낼_수_있다():
    """INDICATORS 로 도는 코드가 3단계에서 그대로 돌아갈지 미리 본다."""
    from app.core.config import INDICATORS

    db = Session()
    try:
        row = db.query(Preference).filter(Preference.customer_id == "C001").first()
        assert row is not None
        assert all(getattr(row, ind) is not None for ind in INDICATORS)
    finally:
        db.close()


def test_벡터가_1536바이트다():
    """LargeBinary 로 적은 게 맞는지. Text 로 적었으면 여기서 깨진다."""
    db = Session()
    try:
        chunk = db.query(MemberChunk).first()
        assert isinstance(chunk.vector, bytes)
        assert len(chunk.vector) == 384 * 4
    finally:
        db.close()
