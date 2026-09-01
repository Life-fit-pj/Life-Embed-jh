from app.core.db import (
    customer_list, customer_one, customer_preferences, customer_persona, region_list, region_one,
    update_customer, update_preferences, update_region as db_update_region,
    column_percentile, write_admin_log,
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

# 값 규칙 — (최솟값, 최댓값). 칸 이름은 config 에서 오므로 여기 또 안 적는다
RULES = {"age": (0, 120)}
RULES.update({name: (1, 5) for name in INDICATORS})       # 가중치 7개는 전부 1~5
RULES.update({name: (0, None) for name in REGION_FIELDS}) # 밀도는 음수가 될 수 없다


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


def get_region(gu: str, dong: str) -> dict | None:
    """행정동 하나의 지표 12개 + 427개 동 중 백분위. 없으면 None"""
    row = region_one(gu, dong, REGION_FIELDS)
    if row is None:
        return None
    return {
        "구": row["구"],
        "행정동명": row["행정동명"],
        "values": {name: row[name] for name in REGION_FIELDS},
        "percentiles": {name: column_percentile(name, row[name]) for name in REGION_FIELDS},
    }


def list_regions():
    """행정동 427개 목록"""
    return region_list()


class InvalidPatch(Exception):
    """값이 규칙에 안 맞을 때. 라우터가 422 로 바꾼다."""
    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__(str(errors))


def _validate(patch: dict) -> None:
    """규칙에 어긋나는 칸을 모아서 한 번에 알린다."""
    errors = {}
    for name, value in patch.items():
        if name not in RULES or value is None or value == "":
            continue
        low, high = RULES[name]
        try:
            number = float(value)
        except (TypeError, ValueError):
            errors[name] = "숫자여야 한다"
            continue
        if number < low:
            errors[name] = f"{low} 이상이어야 한다"
        elif high is not None and number > high:
            errors[name] = f"{low}~{high} 사이여야 한다"
    if errors:
        raise InvalidPatch(errors)


# 캐시비우기
def _clear_caches():
    from app.features import pipeline_api, region_explain
    pipeline_api._ready = None
    region_explain._cache.clear()


# 회원수정
def update_member(customer_id, patch):
    if get_member(customer_id) is None:
        return None
    _validate(patch)                     # ★ 없는 회원 확인(404) 다음, 저장 전

    update_customer(customer_id, patch, CUSTOMER_FIELDS)
    update_preferences(customer_id, patch, PREFERENCE_FIELDS)

    persona_patch = {k: v for k, v in patch.items() if k in PERSONA_FIELDS}
    if persona_patch:
        row = dict(customer_persona(customer_id))   # ① 지금 9칸 전부
        row.update(persona_patch)                    # ② 바뀐 칸만 덮어쓰기
        row["customer_id"] = customer_id              # ③ resync 가 요구하는 칸
        resync_member(get_con(), customer_id, row)    # ④ 벡터 재생성

    write_admin_log("member", customer_id, patch)
    _clear_caches()
    return get_member(customer_id)


# 행정동 수정
def update_region(gu, dong, patch):
    if get_region(gu, dong) is None:
        return None
    _validate(patch) 
    
    db_update_region(gu, dong, patch, REGION_FIELDS)
    write_admin_log("region", f"{gu} {dong}", patch)
    _clear_caches()
    return get_region(gu, dong)

def preview_member(customer_id):
    """이 회원의 희망조건으로 추천 TOP 5를 뽑아본다. 아무것도 안 고친다."""
    prefs = customer_preferences(customer_id)
    if prefs is None:
        return None
    from app.features.pipeline_api import recommend_by_weights   # ← 함수 안 import
    return recommend_by_weights(dict(prefs), top_k=5)




def similar_members(customer_id: str, top_k: int = 5) -> list | None:
    """이 회원과 페르소나가 비슷한 회원들. 자기 자신은 뺀다."""
    persona = customer_persona(customer_id)
    if not persona:
        return None

    # persona 칸을 대표로 쓰고, 비어 있으면 있는 칸 아무거나 하나
    query = persona.get("persona") or next(iter(persona.values()), "")
    if not query:
        return []

    from app.features.pipeline_api import get_ready          # 함수 안 import (5-2와 같은 이유)
    from app.engine.weights import find_similar_members

    r = get_ready()
    # 자기 자신이 반드시 1등으로 걸리므로 한 명 더 받아서 뺀다
    ranked = find_similar_members(
        query, r["member_rows"], r["member_vectors"], top_k=top_k + 1
    )

    out = []
    for cid, (score, category, text) in ranked:     # ← 튜플 안에 튜플이라 이렇게 푼다
        if cid == customer_id:
            continue
        out.append({
            "customer_id": cid,
            "score": round(score, 3),
            "category": category,
            "text": text[:120],
        })
    return out[:top_k]
