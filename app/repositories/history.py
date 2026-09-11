"""옛 이름을 지키는 다리. 실제 내용은 app/repositories/history_repository.py 에 있다.

⚠ user_login 셋만 옛 SQL 그대로 여기 남아 있다 — ORM 다리를 안 거치고
   app/core/db.py 의 실행기를 곧장 쓴다. 표 자체는 4-A 에서 모델이 생겼다
   (app/models/history.py 의 UserLogin).

   ensure_* 6개는 지웠다. "쓸 때 표를 만든다" 는 SQLite 시절 습관이고,
   Postgres 에서는 서비스 코드가 DDL 을 던질 자리가 아니다. 표를 세우는 일은
   pipeline/schema.py 끝의 Base.metadata.create_all() 이 한 번에 한다.

부르는 쪽 —
  app/features/admin.py     집계·관리자로그
  app/features/analysis.py  분석대화·집계
  app/features/auth.py      user_login 계열
  Life-Web/services/engine.py 20행  add_like · remove_like · add_search_history ·
                                    list_search_history · add_chat_history · list_chat_history
"""

from app.core.db import dicts, one, run                 # user_login 전용
from app.db import SessionLocal
from app.repositories import history_repository as repo


def _run(fn, *args, **kwargs):
    db = SessionLocal()
    try:
        return fn(db, *args, **kwargs)
    finally:
        db.close()


# => 좋아요

def add_like(anon_id, gu, dong):
    return _run(repo.add_like, anon_id, gu, dong)


def remove_like(anon_id, gu, dong):
    return _run(repo.remove_like, anon_id, gu, dong)



def list_likes(anon_id):
    return _run(repo.list_likes, anon_id)


# => 검색

def add_search_history(anon_id, query):
    return _run(repo.add_search_history, anon_id, query)


def list_search_history(anon_id, limit=20):
    return _run(repo.list_search_history, anon_id, limit)


# => 채팅

def add_chat_history(anon_id, question, answer):
    return _run(repo.add_chat_history, anon_id, question, answer)


def list_chat_history(anon_id, limit=20):
    return _run(repo.list_chat_history, anon_id, limit)


# => 관리자 수정 이력

def write_admin_log(target: str, target_id: str, patch: dict) -> None:
    return _run(repo.write_admin_log, target, target_id, patch)


# ══ 여기부터 옛 SQL 그대로 (user_login) ══════════════
# 이 셋만 ORM 다리를 안 거치고 app/core/db.py 의 실행기를 곧장 쓴다

# => 로그인

def create_login(customer_id, login_id, password):
    """로그인 계정 발급."""
    run(
        "INSERT INTO user_login (customer_id, login_id, password) "
        "VALUES (:customer_id, :login_id, :password)",
        {"customer_id": customer_id, "login_id": login_id, "password": password},
    )


def get_login_row(login_id):
    """login_id 하나의 계정 정보. 없으면 None. 로그인 시 "아이디가 아예 없는지"와
    "비번이 틀렸는지"를 구분해야 즉석 발급이 가능해서 find_login 대신 이걸 쓴다."""
    row = one(
        "SELECT customer_id, password FROM user_login WHERE login_id = :login_id",
        {"login_id": login_id},
    )
    return {"customer_id": row[0], "password": row[1]} if row else None


# 로그인이 이미 붙어 있는 회원 번호
def login_customer_ids():
    return [r["customer_id"] for r in dicts("SELECT customer_id FROM user_login")]


# ── 집계 (관리자 대시보드·분석이 쓴다) ──────────────────
# 두 칸짜리 결과는 (이름, 개수) 튜플 목록으로 돌려준다

def like_count(gu, dong):
    return _run(repo.like_count, gu, dong)


def like_region_counts(limit=15):
    return _run(repo.like_region_counts, limit)


def search_count():
    return _run(repo.search_count)


def top_searches(top=20):
    return _run(repo.top_searches, top)


def chat_count():
    return _run(repo.chat_count)


def admin_log_count():
    return _run(repo.admin_log_count)


def admin_log_recent(limit=8):
    return _run(repo.admin_log_recent, limit)


# ── 분석 대화 (app/features/analysis.py 가 쓴다) ────────

def add_analysis_chat(question, answer, facts_json, created_at):
    return _run(repo.add_analysis_chat, question, answer, facts_json, created_at)


def list_analysis_chat(limit=50):
    return _run(repo.list_analysis_chat, limit)


def analysis_chat_one(chat_id):
    return _run(repo.analysis_chat_one, chat_id)


def delete_analysis_chat(chat_id):
    return _run(repo.delete_analysis_chat, chat_id)