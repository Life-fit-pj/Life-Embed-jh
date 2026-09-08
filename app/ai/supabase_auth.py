"""Supabase Auth 토큰 검증.

JWT 서명 규칙을 우리가 다시 구현하지 않는다 — Supabase 의 GoTrue 서버(/auth/v1/user)에
토큰을 그대로 들려 보내 물어보고, 그 서버가 유효한지/누구인지를 답해 준다.
"""

import json
import urllib.error
import urllib.request

from app.core.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL


def verify_token(access_token: str) -> dict | None:
    """access_token 이 유효하면 {"id": ..., "email": ...}, 아니면 None."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            body = json.load(res)
    except urllib.error.HTTPError:
        return None
    return {"id": body["id"], "email": body.get("email")}
