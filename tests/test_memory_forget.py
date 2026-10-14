"""채팅창 띠의 ✕ — 기억 하나만 지우기(services/chat_service.forget). DB 는 딕셔너리로 바꿔 끼운다."""

from app.engine.memory import empty
from app.services import chat_service

C = "C001"


def _fake_db(monkeypatch, memory):
    db = {C: memory}
    monkeypatch.setattr(chat_service, "get_memory", lambda cid: db.get(cid))
    monkeypatch.setattr(chat_service, "save_memory", lambda cid, m: db.__setitem__(cid, m))
    monkeypatch.setattr(chat_service, "delete_memory", lambda cid: db.pop(cid, None))
    return db


def test_목록_칸은_그_값_하나만_지운다(monkeypatch):
    db = _fake_db(monkeypatch, {**empty(), "deal_type": "전세", "avoid": ["언덕", "유흥가"], "updated_at": "x"})
    chat_service.forget(C, "avoid", "언덕")
    assert db[C] == {**empty(), "deal_type": "전세", "avoid": ["유흥가"]}


def test_한_칸_칸은_비운다(monkeypatch):
    db = _fake_db(monkeypatch, {**empty(), "deal_type": "전세", "budget_manwon": 30000})
    chat_service.forget(C, "budget_manwon")
    assert db[C] == {**empty(), "deal_type": "전세"}


def test_남은_게_없으면_줄째_지운다(monkeypatch):
    db = _fake_db(monkeypatch, {**empty(), "commute": "판교"})
    chat_service.forget(C, "commute")
    assert C not in db


def test_칸이_없으면_모두_지운다(monkeypatch):
    db = _fake_db(monkeypatch, {**empty(), "commute": "판교", "avoid": ["언덕"]})
    chat_service.forget(C)
    assert C not in db
