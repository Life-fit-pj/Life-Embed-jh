"""member_repository.py 를 세션 없이 부르는 창구.

member_repository 의 함수는 db 세션을 첫 인자로 받는다. 서비스·엔진 층은 세션을 몰라도
되도록, 여기서 _run() 이 세션을 열고 닫아 준다.
"""

from app.db import SessionLocal
from app.repositories import member_repository as repo


def _run(fn, *args, **kwargs):
    """세션을 열고 fn(db, *args) 를 부른 뒤 반드시 닫는다."""
    db = SessionLocal()
    try:
        return fn(db, *args, **kwargs)
    finally:
        db.close()


# ── 프로젝트 전용 조회 함수 ─────────────────────────────

def member_weights(customer_ids):
    return _run(repo.member_weights, customer_ids)


def members_near_weights(weights, top_k=5, exclude=None):
    return _run(repo.members_near_weights, weights, top_k, exclude)


# ── 회원 관리자 조회 (app/services/admin_service.py 가 쓴다) ──────────────

def customer_list():
    return _run(repo.customer_list)


def customer_one(customer_id):
    return _run(repo.customer_one, customer_id)


def customer_homes(customer_ids):
    return _run(repo.customer_homes, customer_ids)


def customer_preferences(customer_id):
    return _run(repo.customer_preferences, customer_id)


def customer_preferences_initial(customer_id):
    return _run(repo.customer_preferences_initial, customer_id)


def customer_persona(customer_id):
    return _run(repo.customer_persona, customer_id)


# ── 회원 관리자 수정 (app/services/admin_service.py 가 쓴다) ──────────────

def update_customer(customer_id, patch, allowed):
    return _run(repo.update_customer, customer_id, patch, allowed)


def update_preferences(customer_id, patch, allowed):
    return _run(repo.update_preferences, customer_id, patch, allowed)


def insert_customer(customer_id, patch, allowed):
    return _run(repo.insert_customer, customer_id, patch, allowed)


def insert_preferences(customer_id, patch, allowed):
    return _run(repo.insert_preferences, customer_id, patch, allowed)


def delete_customer(customer_id):
    return _run(repo.delete_customer, customer_id)


def customer_names():
    return _run(repo.customer_names)


def customer_ids():
    return _run(repo.customer_ids)


# ── 집계 (관리자 대시보드·분석이 쓴다) ──────────────────

def customer_count():
    return _run(repo.customer_count)


def preference_count():
    return _run(repo.preference_count)


def has_initial_columns():
    return _run(repo.has_initial_columns)


def indicator_averages():
    return _run(repo.indicator_averages)


def indicator_spreads():
    return _run(repo.indicator_spreads)


def indicator_drifts():
    return _run(repo.indicator_drifts)


def age_group_counts():
    return _run(repo.age_group_counts)


def gender_counts():
    return _run(repo.gender_counts)


def join_month_counts():
    return _run(repo.join_month_counts)


def home_city_counts():
    return _run(repo.home_city_counts)


def work_city_counts(limit=15):
    return _run(repo.work_city_counts, limit)


def deal_type_counts():
    return _run(repo.deal_type_counts)
