"""history_repository.py 를 세션 없이 부르는 창구.

history_repository 의 함수는 db 세션을 첫 인자로 받는다. 서비스·엔진 층은 세션을 몰라도
되도록, 여기서 _run() 이 세션을 열고 닫아 준다.
"""

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

def write_admin_log(target: str, target_id: str, patch: dict) -> str:
    return _run(repo.write_admin_log, target, target_id, patch)


# => 로그인
# 4단계에서 ORM 으로 옮겼다. 실제 내용은 history_repository.py 의 UserLogin 쪽에 있다

def create_login(customer_id, login_id, password):
    """login_id 자리 선점. 이미 있으면 False(signup() 의 중복 방지)."""
    return _run(repo.create_login, customer_id, login_id, password)


def update_login_customer(login_id, customer_id):
    """선점해 둔 자리에 실제 customer_id 를 채운다."""
    return _run(repo.update_login_customer, login_id, customer_id)


def delete_login(login_id):
    """선점만 하고 회원 생성에 실패했을 때 자리를 반납한다."""
    return _run(repo.delete_login, login_id)


def delete_logins_by_customer(customer_id):
    """회원 탈퇴 — 이 customer_id 에 붙은 로그인 계정을 전부 지운다."""
    return _run(repo.delete_logins_by_customer, customer_id)


def delete_activity(anon_id):
    """회원 탈퇴 — 좋아요·검색·채팅 기록을 지운다."""
    return _run(repo.delete_activity, anon_id)


def get_login_row(login_id):
    """login_id 하나의 계정 정보. 없으면 None. 로그인 시 "아이디가 아예 없는지"와
    "비번이 틀렸는지"를 구분해야 즉석 발급이 가능해서 find_login 대신 이걸 쓴다."""
    return _run(repo.get_login_row, login_id)


# 로그인이 이미 붙어 있는 회원 번호
def login_customer_ids():
    return _run(repo.login_customer_ids)


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


def admin_logs_of(target, target_id, since=""):
    return _run(repo.admin_logs_of, target, target_id, since)


def last_change_times(target, field):
    return _run(repo.last_change_times, target, field)


def member_searches():
    return _run(repo.member_searches)


# ── 분석 대화 (app/services/analysis_service.py 가 쓴다) ────────

def add_analysis_chat(question, answer, facts_json, created_at):
    return _run(repo.add_analysis_chat, question, answer, facts_json, created_at)


def list_analysis_chat(limit=50):
    return _run(repo.list_analysis_chat, limit)


def analysis_chat_one(chat_id):
    return _run(repo.analysis_chat_one, chat_id)


def delete_analysis_chat(chat_id):
    return _run(repo.delete_analysis_chat, chat_id)


# => AI 사용량 (관리자 대시보드)

def ai_usage_by_user(since):
    return _run(repo.ai_usage_by_user, since)


def ai_usage_by_day(since):
    return _run(repo.ai_usage_by_day, since)


# => 장기 메모리

def get_memory(customer_id):
    return _run(repo.get_memory, customer_id)


def save_memory(customer_id, memory):
    return _run(repo.save_memory, customer_id, memory)


def delete_memory(customer_id):
    return _run(repo.delete_memory, customer_id)
