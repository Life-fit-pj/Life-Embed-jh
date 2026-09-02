from app.core.db import (
    customer_list, customer_one, customer_preferences, customer_persona, region_list, region_one,
    update_customer, update_preferences, update_region as db_update_region,
    column_percentile, write_admin_log, ensure_admin_log, dicts, one,
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
    from app.features import pipeline_api, region_explain, privacy
    pipeline_api._ready = None
    region_explain._cache.clear()
    privacy.reset()          # 이름이 바뀌었을 수 있다


def clear_caches() -> dict:
    """바깥(서버)이 부를 수 있는 공개 창구. 관리자가 버튼으로 직접 비울 때 쓴다."""
    _clear_caches()
    return {"ok": True, "cache_warm": False}


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
        from app.features.privacy import mask_text          # 함수 안 import
        out.append({
            "customer_id": cid,
            "score": round(score, 3),
            "category": category,
            "text": mask_text(text)[:120],                   # 가린 뒤에 자른다
        })

    return out[:top_k]


def health() -> dict:
    """일할 준비가 됐나. 나쁜 상태도 '정상적으로' 보고하는 게 이 함수의 일이다."""
    from app.features import pipeline_api

    try:
        from app.core.db import one
        regions = one("SELECT COUNT(*) FROM master_dataset_v3")[0]
        members = one("SELECT COUNT(*) FROM customers")[0]
        ok = regions > 0 and members > 0
        error = None
    except Exception as e:
        regions = members = 0
        ok = False
        error = str(e)

    return {
        "ok": ok,
        "regions": regions,
        "members": members,
        "cache_warm": pipeline_api._ready is not None,   # 캐시가 채워져 있나
        "error": error,
    }


def privacy_preview(customer_id: str) -> dict | None:
    """이 회원의 페르소나 9칸을 원본과 가린 것으로 나란히 준다.

    무엇이 '안' 가려지는지 눈으로 확인하는 용도다. 아무것도 안 고친다.
    """
    persona = customer_persona(customer_id)
    if not persona:
        return None

    from app.features.privacy import mask_text          # 함수 안 import

    masked = {name: mask_text(text) for name, text in persona.items()}
    changed = sum(1 for name in persona if persona[name] != masked[name])
    # 결과가 `0`이면 아무것도 안 가려졌다는 뜻
    
    return {"raw": persona, "masked": masked, "changed": changed}

# ── 대시보드 ─────────────────────────────────────
# 관리자 첫 화면에 뿌릴 숫자들. 화면이 표를 여덟 번 부르는 대신
# 여기서 한 번에 세서 한 덩어리로 넘긴다.
# 모든 항목은 {"label": ..., "value": ...} 목록으로 통일한다 —
# 그래야 화면 쪽 차트 함수 하나로 전부 그릴 수 있다.

def _pairs(sql, params=()) -> list:
    """(이름, 개수) 두 칸짜리 SELECT 결과를 label/value 목록으로 바꾼다."""
    cur = get_con().execute(sql, params)
    return [{"label": str(a), "value": b} for a, b in cur.fetchall()]


def recent_logs(limit: int = 8) -> list:
    """관리자 수정 이력 최근 몇 건. 무엇을 고쳤는지 칸 이름까지 보여 준다."""
    import json
    ensure_admin_log()
    rows = dicts(
        "SELECT target, target_id, patch, changed_at FROM admin_log "
        "ORDER BY log_id DESC LIMIT ?", (limit,),
    )
    out = []
    for r in rows:
        try:
            fields = list(json.loads(r["patch"]).keys())
        except (ValueError, TypeError):
            fields = []
        out.append({
            "target": r["target"],
            "target_id": r["target_id"],
            "fields": fields[:6],          # 화면에 다 못 넣는다. 개수는 아래 total 로
            "field_count": len(fields),
            "changed_at": r["changed_at"],
        })
    return out


def dashboard() -> dict:
    """관리자 첫 화면 한 판.

    health() 가 "지금 일할 수 있나"라면 이쪽은 "무엇이 얼마나 들어 있나"다.
    DB 가 깨져 있어도 화면은 떠야 하므로 실패는 예외 대신 error 로 담아 보낸다.
    """
    base = health()
    if not base["ok"]:
        return {**base, "counts": {}, "charts": {}, "recent": []}

    ensure_admin_log()      # 한 번도 수정 안 한 새 DB 에는 이 표가 아직 없다

    ages = _pairs(
        "SELECT CAST(age / 10 AS INT) * 10, COUNT(*) FROM customers "
        "WHERE age IS NOT NULL GROUP BY 1 ORDER BY 1"
    )
    for a in ages:
        a["label"] = f"{a['label']}대"

    genders = _pairs("SELECT gender, COUNT(*) FROM customers GROUP BY 1 ORDER BY 1")
    for g in genders:
        g["label"] = {"M": "남성", "F": "여성"}.get(g["label"], g["label"])

    # 7지표 평균 — 회원들이 무엇을 중요하게 꼽았는지. 칸 이름은 config 것을 그대로 쓴다
    cols = ", ".join(f'AVG("{name}")' for name in INDICATORS)
    row = one(f"SELECT {cols} FROM user_preferences") or ()
    weights = [
        {"label": name, "value": round(value, 2) if value is not None else 0}
        for name, value in zip(INDICATORS, row)
    ]

    persona = _pairs(
        "SELECT category, CAST(AVG(LENGTH(text)) AS INT) FROM member_chunk GROUP BY 1 ORDER BY 2 DESC"
    )
    chunks = one("SELECT COUNT(*) FROM member_chunk")[0]

    return {
        **base,
        "counts": {
            "members":  base["members"],
            "regions":  base["regions"],
            "gu":       one("SELECT COUNT(DISTINCT 구) FROM master_dataset_v3")[0],
            "chunks":   chunks,
            "edits":    one("SELECT COUNT(*) FROM admin_log")[0],
        },
        "charts": {
            "joins":     _pairs(
                "SELECT substr(joined_at, 1, 7), COUNT(*) FROM customers "
                "WHERE joined_at IS NOT NULL AND joined_at <> '' GROUP BY 1 ORDER BY 1"
            ),
            "ages":      ages,
            "genders":   genders,
            "weights":   weights,
            "memberGu":  _pairs(
                "SELECT city, COUNT(*) FROM customers WHERE city IS NOT NULL "
                "GROUP BY 1 ORDER BY 2 DESC, 1"
            ),
            "regionGu":  _pairs(
                "SELECT 구, COUNT(*) FROM master_dataset_v3 GROUP BY 1 ORDER BY 2 DESC, 1"
            ),
            "dealType":  _pairs(
                'SELECT "거래형태", COUNT(*) FROM user_preferences '
                'WHERE "거래형태" IS NOT NULL AND "거래형태" <> \'\' GROUP BY 1 ORDER BY 2 DESC'
            ),
            "persona":   persona,
        },
        "recent": recent_logs(8),
    }
