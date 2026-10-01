"""Claude 가 채팅 중에 고를 수 있는 도구 목록이다.

조회 도구 넷은 chat_service.build_context() 가 지금 쓰는 함수를 그대로 부른다 —
시설(facility_counts·facility_categories), 시세(region_price_lines), 생활 여건(region_extras). 다른 점은 5개 동네
데이터를 전부 미리 채워 넣는 대신, plan 노드가 필요하다고 고른 동네·항목만 그때 조회한다는 것이다.

rerank_by_focus 하나만 성격이 다르다 — 동네를 조회하는 게 아니라 순위를 다시 매긴다.
"학원 많은 쪽으로 다시 보면?" 처럼 추천 기준을 좁히는 말을, 화면을 늘리지 않고 채팅으로 받는 길이다.
"""

import inspect

from app.core.config import INDICATORS
from app.engine.housing import region_price_lines
from app.engine.recommend import FOCUS_COLUMNS, FOCUS_HINT
from app.repositories.region_repository import FACILITY_TABLES
from app.repositories.regions import facility_counts, facility_categories, region_extras
from app.services.search_service import recommend_by_weights

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

    weights = {k: float((weights or {}).get(k, 3)) for k in INDICATORS}     # 지표 7개만. 다른 키가 섞이면 recommend() 가 죽는다
    weights[indicator] = max(weights[indicator], FOCUS_WEIGHT)
    top = recommend_by_weights(weights, top_k=5, focus={indicator: sub})
    return {
        "기준": f"{indicator} 점수를 '{sub}' 하나로만 보고 서울 427개 동을 다시 줄 세움",
        "안_반영된_것": "가격 조건(건물유형·예산)과 자치구 제한",
        "순위": [
            {"순위": rank, "동네": r["name"], "종합": r["total"], f"{indicator}({sub}) 백분위": r["scores"][indicator]}
            for rank, r in enumerate(top, start=1)
        ],
    }


TOOLS = {
    "get_facility_counts": facility_counts,
    "get_facility_categories": facility_categories,
    "get_region_prices": region_price_lines,
    "get_living_conditions": region_extras,
    "rerank_by_focus": rerank_by_focus,
}

# 화면 상태(지금 가중치)를 같이 받아야 하는 도구. Claude 는 이 값을 모른다 — run_tool 이 채워 넣는다
NEEDS_WEIGHTS = {"rerank_by_focus"}

# gu·dong 두 칸만 받는 도구가 셋이라 모양을 한 번만 적는다
_DONG_INPUT = {
    "type": "object",
    "properties": {
        "gu": {"type": "string", "description": "자치구 이름, 예: 강남구"},
        "dong": {"type": "string", "description": "행정동 이름, 예: 역삼1동"},
    },
    "required": ["gu", "dong"],
}

# 조회 도구가 아는 시설 종류 — "문화시설·의료기관·학원·공원·점포·학교". 표 목록(FACILITY_TABLES)에서 만든다.
# 여기 글자로 적어 두면 표를 더할 때 도구 설명만 옛 목록으로 남는다
FACILITY_KINDS = list(FACILITY_TABLES)
_KINDS_TEXT = "·".join(FACILITY_KINDS)

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
            f"시설 종류 하나({_KINDS_TEXT})의 세부 분류별 개수를 센다. 학교는 학교급(유치원·초등학교·중학교·고등학교)으로 갈린다. "
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
]


def run_tool(name, arguments, weights=None):
    """Claude 가 고른 도구를 실제로 실행한다. weights 는 지금 화면의 추천 가중치 — 필요한 도구에만 넣는다.

    도구 이름과 인자는 Claude 가 쓴 것이라 믿지 않는다. 없는 도구·안 맞는 인자면 죽지 않고
    {"오류": …} 를 결과로 돌려준다 — generate 가 그걸 보고 "그건 볼 수 없다"고 답한다(SYSTEM_PROMPT 규칙 4)
    """
    tool = TOOLS.get(name)
    if tool is None:
        return {"오류": f"'{name}' 이라는 도구는 없습니다"}

    args = (weights,) if name in NEEDS_WEIGHTS else ()
    try:
        inspect.signature(tool).bind(*args, **arguments)      # 부르기 전에 인자가 맞는지만 본다
    except TypeError as e:
        return {"오류": f"도구 인자가 맞지 않습니다 — {e}"}
    return tool(*args, **arguments)
