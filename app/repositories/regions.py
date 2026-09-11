"""옛 이름을 지키는 다리. 실제 내용은 app/repositories/region_repository.py 에 있다.

부르는 쪽 —
  app/engine/          explain · housing · recommend      region_densities · region_price_detail
  app/features/regions.py                                 facilities · facility_counts · region_extras
  app/services/        admin · chat · privacy · region · search
  Life-Web                                                HTTP 로 app/api/ 를 거쳐 들어온다

세션을 여기서 열고 닫는다 — chunks.py · members.py 와 같은 모양이다(교안 5-3-0).
"""

from app.db import SessionLocal
from app.repositories import region_repository as repo


def _run(fn, *args, **kwargs):
    """세션을 열고 fn(db, *args) 를 부른 뒤 반드시 닫는다."""
    db = SessionLocal()
    try:
        return fn(db, *args, **kwargs)
    finally:
        db.close()


# ── 프로젝트 전용 조회 ─────────────────────────────

def region_densities(columns):
    return _run(repo.region_densities, columns)


# ── 행정동 관리자 조회 ──────────────────────────────

def region_list():
    return _run(repo.region_list)


def region_one(gu, dong, columns):
    return _run(repo.region_one, gu, dong, columns)


# ── 시설 조회 ──────────────────────────────────

def facilities(gu, dong, kind=None, limit=10):
    return _run(repo.facilities, gu, dong, kind, limit)


def facility_counts(gu, dong):
    return _run(repo.facility_counts, gu, dong)


def facility_categories(gu, dong, kind="학원", top=8):
    return _run(repo.facility_categories, gu, dong, kind, top)


# ── 생활 여건 · 백분위 · 시세 ─────────────────────────

def region_extras(gu, dong):
    return _run(repo.region_extras, gu, dong)


def column_percentile(column, value, invert=False):
    return _run(repo.column_percentile, column, value, invert)


def region_price_detail(gu, dong, bldg, deal):
    return _run(repo.region_price_detail, gu, dong, bldg, deal)


# ── 쓰기 ──────────────────────────────────────

def update_region(gu, dong, patch, allowed):
    return _run(repo.update_region, gu, dong, patch, allowed)


# ── 이름 목록 ──────────────────────────────────

def gu_names():
    return _run(repo.gu_names)


def dong_names():
    return _run(repo.dong_names)


# ── 집계 (관리자 대시보드가 쓴다) ──────────────────────

def region_count():
    return _run(repo.region_count)


def gu_count():
    return _run(repo.gu_count)


def region_gu_counts():
    return _run(repo.region_gu_counts)
