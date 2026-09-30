"""Claude 가 채팅 중에 고를 수 있는 도구 목록이다.

전부 chat_service.build_context() 가 지금 쓰는 함수를 그대로 부른다 —
시설(facility_counts·facility_categories), 시세(region_price_lines), 생활 여건(region_extras). 다른 점은 5개 동네
데이터를 전부 미리 채워 넣는 대신, plan 노드가 필요하다고 고른 동네·항목만 그때 조회한다는 것이다.
"""

from app.engine.housing import region_price_lines
from app.repositories.regions import facility_counts, facility_categories, region_extras

TOOLS = {
    "get_facility_counts": facility_counts,
    "get_facility_categories": facility_categories,
    "get_region_prices": region_price_lines,
    "get_living_conditions": region_extras,
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

TOOL_SPECS = [
    {
        "name": "get_facility_counts",
        "description": (
            "행정동 하나의 시설 종류별 개수를 센다 (문화시설·의료기관·학원·공원·점포). "
            "\"학원 몇 개야\", \"병원 있어?\" 같은 질문에 쓴다."
        ),
        "input_schema": _DONG_INPUT,
    },
    {
        "name": "get_facility_categories",
        "description": (
            "시설 종류 하나(문화시설·의료기관·학원·공원·점포)의 세부 분류별 개수를 센다. "
            "\"영어학원 몇 곳\", \"어떤 병원이 많아\" 같은 세부 질문에 쓴다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gu": {"type": "string", "description": "자치구 이름, 예: 강남구"},
                "dong": {"type": "string", "description": "행정동 이름, 예: 역삼1동"},
                "kind": {
                    "type": "string",
                    "enum": ["문화시설", "의료기관", "학원", "공원", "점포"],
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
]


def run_tool(name, arguments):
    """Claude 가 고른 도구를 실제로 실행한다."""
    return TOOLS[name](**arguments)
