"""Claude 가 채팅 중에 고를 수 있는 도구 목록이다.

조회 도구 넷은 동네 하나를 읽는 함수를 부른다 —
시설(facility_counts·facility_categories), 시세(region_price_lines), 생활 여건(region_extras).
chat_context.build_context() 가 5개 동네 재료를 전부 미리 채워 넣는 것과 달리, plan 노드가 필요하다고 고른 동네·항목만 그때 조회한다.

rerank_by_focus 하나만 성격이 다르다 — 동네를 조회하는 게 아니라 순위를 다시 매긴다.
"학원 많은 쪽으로 다시 보면?" 처럼 추천 기준을 좁히는 말을, 화면을 늘리지 않고 채팅으로 받는 길이다.
"""

import inspect
import re

import numpy as np

from app.core.config import INDICATORS
from app.engine.housing import region_price_lines
from app.engine.recommend import FOCUS_COLUMNS, FOCUS_HINT, focus_label, nearest_base
from app.engine.weights import find_members_like, indicator_weights
from app.repositories.members import customer_homes, members_near_weights
from app.repositories.region_repository import FACILITY_TABLES
from app.repositories.regions import facility_counts, facility_categories, region_extras
from app.services.history_service import get_likes
from app.engine.ranking import get_ready, recommend_by_weights

# "학원 많은 쪽으로 다시" 는 그 지표를 중시한다는 말이다. 원래 보통(3)이었어도 최댓값으로 올린다 —
# 안 올리면 세부를 바꿔도 가중치가 낮아 순위가 거의 안 움직인다
FOCUS_WEIGHT = 5


def rerank_by_focus(weights, indicator, sub):
    """지금 가중치는 그대로 두고, 지표 하나를 그 안의 한 칸(교육 → 학원)으로만 봤을 때의 TOP 5.

    weights 는 Claude 가 아니라 채팅 상태(화면에 떠 있는 추천의 가중치)가 넣어 준다 — run_tool 참고.
    가격 조건·자치구 제한은 채팅 요청에 안 실려 와서 반영하지 못한다. 그 사실을 결과에 같이 적어
    Claude 가 답할 때 밝히게 한다
    """
    if sub not in FOCUS_COLUMNS.get(indicator, {}):
        return {"오류": f"그 조합은 없습니다. 고를 수 있는 것 — {FOCUS_HINT}"}

    weights = indicator_weights(weights)
    weights[indicator] = max(weights[indicator], FOCUS_WEIGHT)
    top = recommend_by_weights(weights, top_k=5, focus={indicator: sub})
    return {
        "기준": f"{indicator} 점수를 '{sub}' 하나로만 보고 서울 427개 동을 다시 줄 세움",
        "안_반영된_것": "가격 조건(건물유형·예산)과 자치구 제한",
        "순위": [
            {"순위": rank, "동네": r["name"], "종합": r["total"], f"{focus_label(indicator, sub)} 백분위": r["scores"][focus_label(indicator, sub)]}
            for rank, r in enumerate(top, start=1)
        ],
    }

# Claude 에게 보이는 종류 이름. 표 이름(FACILITY_TABLES 의 키)과 다르게 보여야 할 때만 적는다.
# "학교" 만 보이면 유치원 질문이 '학원' 으로 갔다(2026-10-01 실측 3/3). 이름에 유치원이 보여야 고른다 —
# kind 의 설명에 "유치원은 학교다"라고 적는 것으로는 안 고쳐졌다. 표 이름은 그대로 둔다(결과 라벨로 웹·채팅에 나간다)
_KIND_LABELS = {"학교": "학교·유치원"}
_KIND_OF_LABEL = {label: kind for kind, label in _KIND_LABELS.items()}


def _facility_categories(gu, dong, kind):
    """Claude 가 고른 종류 이름(학교·유치원)을 표 이름(학교)으로 바꿔 조회한다"""
    return facility_categories(gu, dong, _KIND_OF_LABEL.get(kind, kind))

# 웹은 로그인하면 기기 번호를 회원 번호("C107")로 바꿔 보낸다 — Life-Web state.js 의 isLoggedIn() 과 같은 규칙
MEMBER_ID = re.compile(r"C\d+")
LOGIN_FIRST = {"오류": "로그인한 회원만 쓸 수 있는 기능입니다. 로그인한 뒤 다시 물어 달라고 안내하세요"}


def _is_member(anon_id):
    """로그인한 회원인가 — 번호가 회원 번호 꼴("C107")인가"""
    return bool(MEMBER_ID.fullmatch(anon_id or ""))


def _similar_places(places, what, regions):
    """기준 동네들("구 동")과 지표 점수가 닮은 동네 — 지금 추천된 곳 중 가장 닮은 곳과, 추천 밖에서 가장 닮은 다섯 곳.

    what 은 기준 동네가 무엇인지의 설명이다. 결과의 "기준" 에 실어 Claude 가 답 첫머리에 밝히게 한다
    """
    r = get_ready()
    names, index = r["names"], r["index"]                             # index 는 "구 동" -> 자리 번호
    base = [index[n] for n in dict.fromkeys(places) if n in index]
    if not base:
        return {"오류": "기준으로 삼을 동네를 찾지 못했습니다"}

    sim, nearest = nearest_base(r["scores"], base)

    def row(i):
        return {"동네": names[i], "닮음": round(float(sim[i])), "가장_닮은_기준_동네": names[nearest[i]]}

    now = [index[n] for n in ((x.get("name") or "").replace("서울특별시 ", "") for x in regions or []) if n in index]
    now.sort(key=lambda i: -sim[i])
    skip = set(base) | set(now)
    others = [int(i) for i in np.argsort(-sim) if int(i) not in skip][:5]
    return {
        "기준": f"{what}({', '.join(names[i] for i in base)})를 참고했다. 그 동네들과 지표 {len(INDICATORS)}개({'·'.join(INDICATORS)}) 점수가 "
                "가장 닮은 순으로 뽑았다. 닮음 100 = 똑같음. 답할 때 이 기준을 맨 먼저 밝히고, 지금 추천 중 가장 닮은 곳과 "
                "추천 밖에서 닮은 동네를 둘 다 '닮은 곳'으로 소개한다",
        "안_반영된_것": "시세와 가격 조건",
        "지금_추천_중_가장_닮은_곳": row(now[0]) if now else None,
        "지금_추천_나머지의_닮음": {names[i]: round(float(sim[i])) for i in now[1:]},
        "추천_밖에서_닮은_동네": [row(i) for i in others],
    }


def similar_to_my_likes(anon_id, regions):
    """내가 좋아요 누른 동네와 닮은 동네. anon_id 와 regions 는 Claude 가 아니라 채팅 상태가 넣어 준다(FROM_STATE)"""
    if not _is_member(anon_id):
        return LOGIN_FIRST
    places = [f"{like['gu']} {like['dong']}" for like in get_likes(anon_id)]
    if not places:
        return {"오류": "좋아요를 누른 동네가 없어 견줄 기준이 없습니다. 마음에 드는 동네에 좋아요를 누른 뒤 다시 묻도록 안내하세요"}
    return _similar_places(places, "회원님이 좋아요를 누른 동네", regions)


def people_like_me(anon_id, regions, weights):
    """나와 닮은 회원들이 실제로 사는 동네와 닮은 동네.

    닮은 회원은 페르소나(가입 설문)로 찾는다 — 관리자 화면과 같은 engine 함수다. 페르소나가 없는 회원은
    빈손으로 돌려보내지 않고, 지금 검색의 가중치와 선호 가중치가 가까운 회원으로 대신 찾은 뒤 프로필을 채우라고 권한다
    """
    if not _is_member(anon_id):
        return LOGIN_FIRST
    ids = [cid for cid, _ in find_members_like(anon_id) or []]      # 닮은 순. 자기 자신은 빠져 있다
    what, tip = "회원님과 성향이 닮은 분 {n}명이 실제로 사는 동네", None
    if not ids:
        ids = members_near_weights(indicator_weights(weights), exclude=anon_id)
        what = "회원님과 비슷한 조건을 중시하는 분 {n}명이 실제로 사는 동네"
        tip = ("가입 설문(프로필)이 비어 있어 성향 대신 지금 검색의 가중치로 찾았다. 답 끝에, 프로필을 채우면 "
               "성향이 닮은 회원을 기준으로 더 정확히 볼 수 있다고 한 문장으로 권한다")
    home = customer_homes(ids) if ids else {}                       # 그 다섯 명의 구·동만 읽는다
    places = [home[cid] for cid in ids if cid in home]
    if not places:
        return {"오류": "닮은 회원을 찾지 못했습니다. 좋아요를 누른 동네가 있으면 그 동네와 닮은 곳은 볼 수 있다고 안내하세요"}
    result = _similar_places(places, what.format(n=len(places)), regions)
    return {**result, "안내": tip} if tip else result


TOOLS = {
    "get_facility_counts": facility_counts,
    "get_facility_categories": _facility_categories,
    "get_region_prices": region_price_lines,
    "get_living_conditions": region_extras,
    "rerank_by_focus": rerank_by_focus,
    "similar_to_my_likes": similar_to_my_likes,
    "people_like_me": people_like_me,
}

# 도구가 Claude 의 인자 말고 채팅 상태에서 받는 값. 적힌 순서대로 맨 앞 인자로 들어간다.
# Claude 는 이 값들을 모른다(가중치·누가 묻는지·화면의 동네) — run_tool 이 채워 넣는다
FROM_STATE = {
    "rerank_by_focus": ("weights",),
    "similar_to_my_likes": ("anon_id", "regions"),
    "people_like_me": ("anon_id", "regions", "weights"),
}

# gu·dong 두 칸만 받는 도구가 셋이라 모양을 한 번만 적는다
_DONG_INPUT = {
    "type": "object",
    "properties": {
        "gu": {"type": "string", "description": "자치구 이름, 예: 강남구"},
        "dong": {"type": "string", "description": "행정동 이름, 예: 역삼1동"},
    },
    "required": ["gu", "dong"],
}

# 조회 도구가 아는 시설 종류 — "문화시설, 의료기관, 학원, 공원, 점포, 학교·유치원". 표 목록(FACILITY_TABLES)에서 만든다.
# 여기 글자로 적어 두면 표를 더할 때 도구 설명만 옛 목록으로 남는다
FACILITY_KINDS = [_KIND_LABELS.get(kind, kind) for kind in FACILITY_TABLES]
_KINDS_TEXT = ", ".join(FACILITY_KINDS)      # '·' 로 이으면 "학교·유치원" 이 두 종류로 읽힌다

TOOL_SPECS = [
    {
        "name": "get_facility_counts",
        "description": (
            f"행정동 하나의 시설 종류별 개수를 센다 ({_KINDS_TEXT}). "
            "\"학원 몇 개야\", \"병원 있어?\", \"학교 몇 곳이야\" 같은 질문에 쓴다."
        ),
        "input_schema": _DONG_INPUT,
    },
    {
        "name": "get_facility_categories",
        "description": (
            f"시설 종류 하나({_KINDS_TEXT})의 세부 분류별 개수를 센다. '학교·유치원' 은 유치원·초등학교·중학교·고등학교로 갈린다. "
            "\"영어학원 몇 곳\", \"어떤 병원이 많아\", \"유치원 있어?\" 같은 세부 질문에 쓴다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gu": {"type": "string", "description": "자치구 이름, 예: 강남구"},
                "dong": {"type": "string", "description": "행정동 이름, 예: 역삼1동"},
                "kind": {
                    "type": "string",
                    "enum": FACILITY_KINDS,
                    "description": "어떤 시설 종류의 세부 분류를 볼지",
                },
            },
            "required": ["gu", "dong", "kind"],
        },
    },
    {
        "name": "get_region_prices",
        "description": (
            "행정동 하나의 주택 시세 중앙값을 건물유형(아파트·연립다세대·단독다가구·오피스텔)별 "
            "매매·전세·월세로 준다. 신뢰등급·거래건수도 붙는다. "
            "\"전세 얼마야\", \"여기 비싸?\", \"아파트 매매가\" 같은 질문에 쓴다."
        ),
        "input_schema": _DONG_INPUT,
    },
    {
        "name": "get_living_conditions",
        "description": (
            "행정동 하나의 생활 여건(소음·미세먼지 같은 구 단위 평균, 거주안정성, "
            "평균 가구원수·1인가구 비율, 보행편의 백분위)을 준다. "
            "\"시끄러워?\", \"1인 가구 많아?\", \"오래 사는 동네야?\" 같은 질문에 쓴다."
        ),
        "input_schema": _DONG_INPUT,
    },
    {
        "name": "rerank_by_focus",
        "description": (
            "지금 추천 조건은 그대로 두고, 지표 하나를 그 안의 한 가지로만 봤을 때의 서울 TOP 5 를 다시 뽑는다. "
            "\"학원 많은 쪽으로 다시 보면?\", \"지하철 기준으로는 어디야?\" 처럼 추천 기준을 좁혀 "
            f"다시 묻는 질문에 쓴다. 고를 수 있는 조합 — {FOCUS_HINT}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "indicator": {"type": "string", "enum": list(FOCUS_COLUMNS), "description": "어느 지표를 좁힐지"},
                "sub": {
                    "type": "string",
                    "enum": sorted({sub for subs in FOCUS_COLUMNS.values() for sub in subs}),
                    "description": "그 지표 안에서 콕 집을 한 가지. 위 조합에 있는 짝만 된다",
                },
            },
            "required": ["indicator", "sub"],
        },
    },
    {
        "name": "similar_to_my_likes",
        "description": (
            "사용자가 좋아요(찜)를 누른 동네를 기준으로 지표 점수가 닮은 동네를 찾는다. 지금 추천된 동네들이 각각 얼마나 닮았는지와, "
            "추천 밖에서 서울 전체로 가장 닮은 다섯 곳을 준다. 질문에 좋아요·찜이라는 말이 있을 때만 쓴다 — "
            "\"내가 좋아요 누른 동네랑 비슷한 곳은?\", \"찜한 곳이랑 비교하면 어때?\""
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "people_like_me",
        "description": (
            "사용자와 닮은 회원들이 실제로 사는 동네를 기준으로 지표 점수가 닮은 동네를 찾는다. 지금 추천된 동네들이 각각 얼마나 닮았는지와, "
            "추천 밖에서 서울 전체로 가장 닮은 다섯 곳을 준다. "
            "\"나 같은 사람들은 보통 어디를 골라?\", \"나랑 비슷한 사람들은 어디 살아?\" 같은 질문에 쓴다"
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


# 로그인한 회원에게만 보여 줄 도구. 로그아웃이면 Claude 에게 아예 안 보여 준다 — 예전 다섯 개만 보고 전처럼 답한다
MEMBER_TOOLS = {"similar_to_my_likes", "people_like_me"}


def tool_specs(anon_id):
    """Claude 에게 보여 줄 도구 목록. 로그인 안 했으면 회원 전용 도구를 뺀다"""
    if _is_member(anon_id):
        return TOOL_SPECS
    return [spec for spec in TOOL_SPECS if spec["name"] not in MEMBER_TOOLS]


def run_tool(name, arguments, state=None):
    """Claude 가 고른 도구를 실제로 실행한다. state 는 채팅 상태 — FROM_STATE 에 적힌 값만 그 도구에 넣는다.

    도구 이름과 인자는 Claude 가 쓴 것이라 믿지 않는다. 없는 도구·안 맞는 인자면 죽지 않고
    {"오류": …} 를 결과로 돌려준다 — generate 가 그걸 보고 "그건 볼 수 없다"고 답한다(채팅 프롬프트 ANSWER_PROMPT 의 규칙 4)
    """
    tool = TOOLS.get(name)
    if tool is None:
        return {"오류": f"'{name}' 이라는 도구는 없습니다"}

    args = tuple((state or {}).get(key) for key in FROM_STATE.get(name, ()))
    try:
        inspect.signature(tool).bind(*args, **arguments)      # 부르기 전에 인자가 맞는지만 본다
    except TypeError as e:
        return {"오류": f"도구 인자가 맞지 않습니다 — {e}"}
    return tool(*args, **arguments)
