"""Claude 가 채팅 중에 고를 수 있는 도구 목록이다.

facility_counts·facility_categories 는 app/repositories/regions.py(다리)를 그대로
부른다 — chat_service.build_context() 가 지금 쓰는 함수와 같다. 다른 점은 5개 동네
데이터를 전부 미리 채워 넣는 대신, plan 노드가 필요하다고 고른 동네·항목만 그때 조회한다는 것이다.
"""

from app.repositories.regions import facility_counts, facility_categories

TOOLS = {
    "get_facility_counts": facility_counts,
    "get_facility_categories": facility_categories,
}

TOOL_SPECS = [
    {
        "name": "get_facility_counts",
        "description": (
            "행정동 하나의 시설 종류별 개수를 센다 (문화시설·의료기관·학원·공원·점포). "
            "\"학원 몇 개야\", \"병원 있어?\" 같은 질문에 쓴다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gu": {"type": "string", "description": "자치구 이름, 예: 강남구"},
                "dong": {"type": "string", "description": "행정동 이름, 예: 역삼1동"},
            },
            "required": ["gu", "dong"],
        },
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
]


def run_tool(name, arguments):
    """Claude 가 고른 도구를 실제로 실행한다."""
    return TOOLS[name](**arguments)
