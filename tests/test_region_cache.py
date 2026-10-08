"""핀 설명 캐시 — 같은 동네·검색어라도 가중치·점수가 다르면 다시 만든다. DB 도 Claude 도 안 쓴다."""

import app.services.region_service as rs


def test_가중치가_다르면_다시_만든다(monkeypatch):
    calls = []
    monkeypatch.setattr(rs, "region_explain", lambda *a, **k: calls.append(a) or "설명")
    monkeypatch.setattr(rs, "_cache", {})
    rs.region_explain_cached("강남구", "역삼1동", "조용한", weights={"녹지": 5.0}, scores={"녹지": 90})
    rs.region_explain_cached("강남구", "역삼1동", "조용한", weights={"녹지": 1.0}, scores={"녹지": 20})
    assert len(calls) == 2


def test_같으면_한_번만_만든다(monkeypatch):
    calls = []
    monkeypatch.setattr(rs, "region_explain", lambda *a, **k: calls.append(a) or "설명")
    monkeypatch.setattr(rs, "_cache", {})
    for _ in range(2):
        rs.region_explain_cached("강남구", "역삼1동", "조용한", weights={"녹지": 5.0}, scores={"녹지": 90})
    assert len(calls) == 1


def test_꽉_차면_비운다(monkeypatch):
    monkeypatch.setattr(rs, "region_explain", lambda *a, **k: "설명")
    monkeypatch.setattr(rs, "_cache", {})
    monkeypatch.setattr(rs, "CACHE_LIMIT", 3)
    for i in range(4):
        rs.region_explain_cached("강남구", "역삼1동", f"검색어{i}")
    assert len(rs._cache) == 1          # 셋이 찬 뒤 넷째가 들어올 때 비우고 하나만 남는다
