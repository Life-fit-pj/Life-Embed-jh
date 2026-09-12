"""옛 이름을 지키는 다리. 실제 내용은 app/repositories/member_repository.py 에 있다.

부르는 쪽이 이 이름으로 import 하고 있어서 아직 못 지운다 —
  app/engine/weights.py     member_weights
  app/features/search.py    member_weights
  app/features/admin.py     조회·수정 대부분
  app/features/analysis.py  집계
  app/features/auth.py      customer_ids
  app/features/privacy.py   customer_names
  Life-Web/services/engine.py 22행  customer_one

8단계에서 부르는 쪽을 repositories 로 바꾸면서 이 파일을 지운다.

_run_update 는 4단계에서 없앴다 — regions 가 ORM 으로 옮겨 가면서
(app/repositories/region_repository.py 의 update_region) 부르는 곳이 사라졌다.
"""

from app.db import SessionLocal
from app.repositories import member_repository as repo


def _run(fn, *args, **kwargs):
    """세션을 열고 fn(db, *args) 를 부른 뒤 반드시 닫는다.

    옛 함수들은 db 를 인자로 안 받았다. 그 모양을 지켜야 부르는 쪽을
    안 고칠 수 있으므로, 세션을 여기서 열고 닫는다.
    """
    db = SessionLocal()
    try:
        return fn(db, *args, **kwargs)
    finally:
        db.close()


# ── 프로젝트 전용 조회 함수 ─────────────────────────────

def member_weights(customer_ids):
    return _run(repo.member_weights, customer_ids)


# ── 회원 관리자 조회 (app/features/admin.py 가 쓴다) ──────────────

def customer_list():
    return _run(repo.customer_list)


def customer_one(customer_id):
    return _run(repo.customer_one, customer_id)


def customer_preferences(customer_id):
    return _run(repo.customer_preferences, customer_id)


def customer_preferences_initial(customer_id):
    return _run(repo.customer_preferences_initial, customer_id)


def customer_persona(customer_id):
    return _run(repo.customer_persona, customer_id)


# ── 회원 관리자 수정 (app/features/admin.py 가 쓴다) ──────────────

def update_customer(customer_id, patch, allowed):
    return _run(repo.update_customer, customer_id, patch, allowed)


def update_preferences(customer_id, patch, allowed):
    return _run(repo.update_preferences, customer_id, patch, allowed)


def insert_customer(customer_id, patch, allowed):
    return _run(repo.insert_customer, customer_id, patch, allowed)


def insert_preferences(customer_id, patch, allowed):
    return _run(repo.insert_preferences, customer_id, patch, allowed)


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


def indicator_spread(name):
    return _run(repo.indicator_spread, name)


def indicator_drift(name):
    return _run(repo.indicator_drift, name)


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
