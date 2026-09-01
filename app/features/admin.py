from app.core.db import (
    customer_list, customer_one, customer_preferences, customer_persona, region_list, region_one,
    update_customer, update_preferences, update_region as db_update_region,
)
from app.core.config import INDICATORS, CHUNK_COLUMNS
from app.engine.recommend import INDICATOR_COLUMNS
from app.engine.resync import resync_member
from app.core.db import get_con


# {"녹지": ["공원_밀도"], "안전": ["CCTV_밀도", "경찰관서_밀도"], ...} 를 펼쳐서
# ("공원_밀도", "CCTV_밀도", "경찰관서_밀도", ...) 12개로 만든다
REGION_FIELDS = tuple(c for cols in INDICATOR_COLUMNS.values() for c in cols)

# 화이트리스트
CUSTOMER_FIELDS = ("name", "gender", "age", "phone", "email",
                    "city", "city_dong", "work_city", "work_dong")
PREFERENCE_FIELDS = tuple(INDICATORS)
PERSONA_FIELDS = tuple(CHUNK_COLUMNS)
# REGION_FIELDS 는 이미 위에 있음


def get_member(customer_id):
    """회원 한 명 = 기본정보 + 희망조건 + 페르소나 9칸"""
    customer = customer_one(customer_id)
    if customer is None:
        return None
    return {
        "customer": customer,
        "preferences": customer_preferences(customer_id) or {},
        "persona": customer_persona(customer_id),
    }


def list_members():
    """회원 100명 목록"""
    return customer_list()


def get_region(gu, dong):
    """행정동 하나의 지표 12개. 없으면 None"""
    return region_one(gu, dong, REGION_FIELDS)


def list_regions():
    """행정동 427개 목록"""
    return region_list()


# 캐시비우기
def _clear_caches():
    from app.features import pipeline_api, region_explain
    pipeline_api._ready = None
    region_explain._cache.clear()


# 회원수정
def update_member(customer_id, patch):
    if get_member(customer_id) is None:
        return None

    update_customer(customer_id, patch, CUSTOMER_FIELDS)
    update_preferences(customer_id, patch, PREFERENCE_FIELDS)

    persona_patch = {k: v for k, v in patch.items() if k in PERSONA_FIELDS}
    if persona_patch:
        row = dict(customer_persona(customer_id))   # ① 지금 9칸 전부
        row.update(persona_patch)                    # ② 바뀐 칸만 덮어쓰기
        row["customer_id"] = customer_id              # ③ resync 가 요구하는 칸
        resync_member(get_con(), customer_id, row)    # ④ 벡터 재생성

    _clear_caches()
    return get_member(customer_id)


# 행정동 수정
def update_region(gu, dong, patch):
    if get_region(gu, dong) is None:
        return None
    db_update_region(gu, dong, patch, REGION_FIELDS)
    _clear_caches()
    return get_region(gu, dong)
