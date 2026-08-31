from app.core.db import customer_list, customer_one, customer_preferences, customer_persona, region_list, region_one
from app.engine.recommend import INDICATOR_COLUMNS

# {"녹지": ["공원_밀도"], "안전": ["CCTV_밀도", "경찰관서_밀도"], ...} 를 펼쳐서
# ("공원_밀도", "CCTV_밀도", "경찰관서_밀도", ...) 12개로 만든다
REGION_FIELDS = tuple(c for cols in INDICATOR_COLUMNS.values() for c in cols)

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