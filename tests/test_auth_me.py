"""회원 본인 조회(/auth/me) — 토큰 없으면 거절, 가입 전이면 404, 활동 성향은 안 보인다.

DB 도 Supabase 도 Claude 도 안 쓴다 — 토큰 확인 · 조회를 가짜로 바꿔 끼운다.
"""

from fastapi.testclient import TestClient

import app.api.auth as auth_api
import app.services.auth_service as auth_service
from app.main import app

client = TestClient(app, raise_server_exceptions=False)
LONG = "가" * 30      # MIN_LENGTH(20) 를 넘는 글


def _login_as(supabase_id: str) -> None:
    app.dependency_overrides[auth_api._supabase_id] = lambda: supabase_id


def teardown_function():
    app.dependency_overrides.clear()


def test_토큰이_없으면_안_받는다():
    assert client.get("/auth/me").status_code == 422          # Authorization 헤더가 필수다


def test_가입_전이면_404(monkeypatch):
    _login_as("u-new")
    monkeypatch.setattr(auth_service, "login_with_supabase", lambda uid: None)
    assert client.get("/auth/me").status_code == 404


def test_본인_정보에_활동_성향은_없다(monkeypatch):
    _login_as("u-107")
    monkeypatch.setattr(auth_service, "login_with_supabase", lambda uid: "C107")
    monkeypatch.setattr(auth_service, "customer_one", lambda cid: {"customer_id": cid, "name": "홍길동"})
    monkeypatch.setattr(auth_service, "customer_persona", lambda cid: {"travel_persona": LONG, "activity_persona": LONG})
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["customer_id"] == "C107"
    assert r.json()["persona"] == {"travel_persona": LONG}
