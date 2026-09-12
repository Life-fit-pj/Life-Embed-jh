"""app/ai/supabase_auth.py 가 가짜 토큰을 실제로 거부하나.

실행: py -m pytest tests/test_supabase_auth.py -v
Supabase GoTrue 서버를 실제로 한 번 부른다(무료·부작용 없음).
"""

from app.ai.supabase_auth import verify_token


def test_가짜_토큰은_거부된다():
    assert verify_token("이건-진짜-토큰이-아니다") is None
