"""관리자 화면이 쓰는 창구. 회원·행정동 조회와 수정, 대시보드 집계.
옛 경로에는 다리가 남아 있다 — Life-Web 이 그 이름을 쓰기 때문이다.
"""

import json

from app.ai import vector_store
from app.core.config import INDICATORS, CHUNK_COLUMNS, MIN_LENGTH
from app.engine.recommend import INDICATOR_COLUMNS
from app.engine.resync import resync_member
from app.engine.weights import find_similar_members
from app.services import search_service, region_service, privacy_service
from app.repositories.chunks import member_chunk_count, persona_lengths, replace_member_chunks
from app.repositories.history import (
    write_admin_log,
    admin_log_count, admin_log_recent, like_count,
    list_likes, list_search_history, list_chat_history,
    delete_activity, delete_logins_by_customer,
)
from app.repositories.members import (
    customer_list, customer_one, customer_preferences, customer_preferences_initial,
    customer_persona, customer_ids, customer_count,
    update_customer, update_preferences,
    insert_customer, insert_preferences, delete_customer,
    indicator_averages, age_group_counts, gender_counts,
    join_month_counts, home_city_counts, deal_type_counts,
)
from app.repositories.regions import (
    region_list, region_one, column_percentile, region_count,
    gu_count, region_gu_counts,
    update_region as db_update_region,
)


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
    """회원 한 명 = 기본정보 + 희망조건(현재/가입시) + 페르소나 9칸 + 활동(좋아요/검색/채팅)

    preferences_initial 은 가입 때 받은 값이다. 관리자가 고쳐도 안 바뀐다 —
    화이트리스트(PREFERENCE_FIELDS)가 INDICATORS 7개뿐이라 `_초기` 칸은
    수정 대상에 아예 안 들어간다

    활동 3종은 anon_id 를 키로 쌓이는데, 로그인한 회원은 anon_id 자리가
    customer_id 로 덮어써져 있으므로(services/engine.py의 로그인 처리) 여기서
    같은 customer_id 로 그대로 조회하면 이 회원 몫만 걸러진다. 로그인 전(임시
    UUID로 활동했을 때) 기록은 안 잡힌다 — 로그인해야 그 뒤로 이 사람 것이 된다.
    """
    customer = customer_one(customer_id)
    if customer is None:
        return None
    return {
        "customer": customer,
        "preferences": customer_preferences(customer_id) or {},
        "preferences_initial": customer_preferences_initial(customer_id) or {},
        "persona": customer_persona(customer_id),
        "likes": list_likes(customer_id),
        "searches": list_search_history(customer_id),
        "chats": list_chat_history(customer_id),
    }


def list_members():
    """회원 100명 목록"""
    return customer_list()


def get_region(gu: str, dong: str) -> dict | None:
    """행정동 하나의 지표 12개 + 427개 동 중 백분위 + 좋아요 수. 없으면 None

    좋아요는 likes 표에 (구, 행정동명) 글자 그대로 쌓인다. 화면이 추천 결과에서
    받은 이름을 그대로 되돌려 보내므로 지금은 철자가 어긋나지 않는다.
    ⚠ 받은 gu/dong 이 아니라 row 에서 읽은 정식 이름으로 센다 —
      region_one() 이 dong_variants() 로 표기 변형을 흡수해 찾아 주기 때문이다
    """
    row = region_one(gu, dong, REGION_FIELDS)
    if row is None:
        return None
    likes = like_count(row["구"], row["행정동명"])
    return {
        "구": row["구"],
        "행정동명": row["행정동명"],
        "likes": likes,
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

    search_service._ready = None
    region_service._cache.clear()
    privacy_service.reset()          # 이름이 바뀌었을 수 있다


def clear_caches() -> dict:
    """바깥(서버)이 부를 수 있는 공개 창구. 관리자가 버튼으로 직접 비울 때 쓴다."""
    _clear_caches()
    return {"ok": True, "cache_warm": False}


# 회원수정
def update_member(customer_id, patch):
    if customer_one(customer_id) is None:   # 존재 확인은 이 한 줄로 충분 — get_member() 는 7번 왕복한다
        return None
    _validate(patch)                     # 없는 회원 확인(404) 다음, 저장 전

    update_customer(customer_id, patch, CUSTOMER_FIELDS)
    update_preferences(customer_id, patch, PREFERENCE_FIELDS)

    persona_patch = {k: v for k, v in patch.items() if k in PERSONA_FIELDS}
    if persona_patch:
        row = dict(customer_persona(customer_id))   # 지금 9칸 전부
        row.update(persona_patch)                   # 바뀐 칸만 덮어쓰기
        row["customer_id"] = customer_id            # resync 가 요구하는 칸
        resync_member(customer_id, row)             # 벡터 재생성

    write_admin_log("member", customer_id, patch)
    _clear_caches()
    return get_member(customer_id)


def _next_customer_id() -> str:
    """지금 있는 가장 큰 번호 + 1. 'C105' 다음은 'C106'.

    C101~C105 처럼 로그인만 발급된 빈 계정도 번호를 이미 썼으므로
    그대로 이어서 쓴다 — 번호를 비워 두지 않는다.
    """
    nums = [int(cid[1:]) for cid in customer_ids() if cid[1:].isdigit()]
    return f"C{max(nums, default=0) + 1:03d}"


def create_member(payload: dict) -> dict:
    """회원 한 명을 손으로 새로 만든다. update_member 와의 차이는 딱 하나 —

    거긴 "이미 있는 행을 고친다(UPDATE)"고 여긴 "행 자체가 없다(INSERT)"는 전제다.
    페르소나를 하나라도 받으면 그 자리에서 청킹 + 임베딩까지 끝낸다
    (resync_member 재사용 — 900개를 다시 만들지 않고 이 한 명 몫만 만드는
    '증분 임베딩'이 이미 그 함수 안에 있다)
    """
    _validate(payload)     # 나이·가중치 범위는 기존 규칙을 그대로 쓴다

    # 20자 미만 페르소나는 make_chunks() 가 조용히 버린다 —
    # 여기서 먼저 막아야 "썼는데 왜 안 잡히지"가 안 생긴다
    persona_patch = {k: v for k, v in payload.items()
                      if k in PERSONA_FIELDS and (v or "").strip()}
    too_short = {k: f"{MIN_LENGTH}자 이상 써야 벡터가 만들어진다 (지금 {len(v.strip())}자)"
                 for k, v in persona_patch.items() if len(v.strip()) < MIN_LENGTH}
    if too_short:
        raise InvalidPatch(too_short)

    customer_id = _next_customer_id()
    insert_customer(customer_id, payload, CUSTOMER_FIELDS)

    # 가중치를 하나라도 받았으면 '_초기' 칸도 같은 값으로 같이 채운다 —
    # 방금 가입한 회원은 "지금 값"과 "가입 때 값"이 아직 같아야 정상이다
    indicator_patch = {k: v for k, v in payload.items() if k in PREFERENCE_FIELDS}
    if indicator_patch:
        pref_row = dict(indicator_patch)
        pref_row.update({f"{k}_초기": v for k, v in indicator_patch.items()})
        insert_preferences(customer_id, pref_row, tuple(pref_row.keys()))

    if persona_patch:
        row = {k: persona_patch.get(k, "") for k in PERSONA_FIELDS}
        row["customer_id"] = customer_id
        resync_member(customer_id, row)   # ← 청킹 + 임베딩 + 저장

    write_admin_log("member", customer_id, payload)
    _clear_caches()
    return get_member(customer_id)


def delete_member(customer_id: str) -> bool:
    """회원 탈퇴 — customers·user_preferences·member 청크·로그인 계정·활동 기록을 전부 지운다.

    없는 회원이면 False. anon_id 로 쌓인 활동(likes·search_history·chat_history)은
    로그인한 회원의 경우 anon_id 가 customer_id 로 덮어써져 있으므로 같은 값으로 지운다
    (get_member() 의 활동 조회와 짝이 맞아야 한다).
    """
    if customer_one(customer_id) is None:   # 존재 확인은 이 한 줄로 충분 — get_member() 는 7번 왕복한다
        return False

    replace_member_chunks(customer_id, [])   # 벡터도 같이 지운다
    vector_store.invalidate("member")
    delete_logins_by_customer(customer_id)
    delete_activity(customer_id)
    delete_customer(customer_id)

    write_admin_log("member", customer_id, {"action": "탈퇴"})
    _clear_caches()
    return True


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
    return search_service.recommend_by_weights(dict(prefs), top_k=5)




def similar_members(customer_id: str, top_k: int = 5) -> list | None:
    """이 회원과 페르소나가 비슷한 회원들. 자기 자신은 뺀다."""
    persona = customer_persona(customer_id)
    if not persona:
        return None

    # persona 칸을 대표로 쓰고, 비어 있으면 있는 칸 아무거나 하나
    query = persona.get("persona") or next(iter(persona.values()), "")
    if not query:
        return []

    # 자기 자신이 반드시 1등으로 걸리므로 한 명 더 받아서 뺀다
    # 벡터는 vector_store 가 들고 있다 — get_ready() 에서 뺐다(7-7절)
    ranked = find_similar_members(query, top_k=top_k + 1)

    out = []
    for cid, (score, category, text) in ranked:     # ← 튜플 안에 튜플이라 이렇게 푼다
        if cid == customer_id:
            continue
        out.append({
            "customer_id": cid,
            "score": round(score, 3),
            "category": category,
            "text": privacy_service.mask_text(text)[:120],                   # 가린 뒤에 자른다
        })

    return out[:top_k]


def health() -> dict:
    """일할 준비가 됐나. 나쁜 상태도 '정상적으로' 보고하는 게 이 함수의 일이다."""

    try:
        regions = region_count()
        members = customer_count()
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
        "cache_warm": search_service._ready is not None,   # 캐시가 채워져 있나
        "error": error,
    }


def privacy_preview(customer_id: str) -> dict | None:
    """이 회원의 페르소나 9칸을 원본과 가린 것으로 나란히 준다.

    무엇이 '안' 가려지는지 눈으로 확인하는 용도다. 아무것도 안 고친다.
    """
    persona = customer_persona(customer_id)
    if not persona:
        return None

    masked = {name: privacy_service.mask_text(text) for name, text in persona.items()}
    changed = sum(1 for name in persona if persona[name] != masked[name])
    # 결과가 `0`이면 아무것도 안 가려졌다는 뜻
    
    return {"raw": persona, "masked": masked, "changed": changed}

# ── 대시보드 ─────────────────────────────────────
# 관리자 첫 화면에 뿌릴 숫자들. 화면이 표를 여덟 번 부르는 대신
# 여기서 한 번에 세서 한 덩어리로 넘긴다.
# 모든 항목은 {"label": ..., "value": ...} 목록으로 통일한다 —
# 그래야 화면 쪽 차트 함수 하나로 전부 그릴 수 있다.

def to_pairs(rows) -> list:
    """(이름, 개수) 두 칸짜리 결과를 label/value 목록으로 바꾼다.

    SQL 은 tables/ 가 맡고 여기는 모양만 바꾼다 — 예전 pairs() 는 SQL 문자열을
    인자로 받아서, 표 이름이 창구에 남고 tables 가 쿼리 조립기가 되고 있었다
    """
    return [{"label": str(a), "value": b} for a, b in rows]


def recent_logs(limit: int = 8) -> list:
    """관리자 수정 이력 최근 몇 건. 무엇을 고쳤는지 칸 이름까지 보여 준다."""
    rows = admin_log_recent(limit)
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

    ages = to_pairs(age_group_counts())
    for a in ages:
        a["label"] = f"{a['label']}대"

    genders = to_pairs(gender_counts())
    for g in genders:
        g["label"] = {"M": "남성", "F": "여성"}.get(g["label"], g["label"])

    # 7지표 평균 — 회원들이 무엇을 중요하게 꼽았는지. 칸 이름은 config 것을 그대로 쓴다
    weights = [
        {"label": name, "value": round(value, 2) if value is not None else 0}
        for name, value in indicator_averages().items()
    ]

    return {
        **base,
        "counts": {
            "members":  base["members"],
            "regions":  base["regions"],
            "gu":       gu_count(),
            "chunks":   member_chunk_count(),
            "edits":    admin_log_count(),
        },
        "charts": {
            "joins":     to_pairs(join_month_counts()),
            "ages":      ages,
            "genders":   genders,
            "weights":   weights,
            "memberGu":  to_pairs(home_city_counts()),
            "regionGu":  to_pairs(region_gu_counts()),
            "dealType":  to_pairs(deal_type_counts()),
            "persona":   to_pairs(persona_lengths()),
        },
        "recent": recent_logs(8),
    }
