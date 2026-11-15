"""장기 메모리 — 채팅에서 말한 거주 선호를 뽑고, 합치고, 다음 대화에 실을 글로 줄인다.

extract()          질문 하나 -> 선호 dict (Claude 1번, Structured Outputs)
merge()            지금까지 기억한 것 + 새로 뽑은 것 -> 합친 것. 말하지 않은 칸은 옛 값을 지킨다
to_prompt_line()   기억 -> 답변 프롬프트에 실을 한 줄. 칸마다 길이·개수 상한이 있어 MEMORY_CHARS 를 넘지 않는다(tests/test_memory.py)

DB 는 모른다 — 읽고 쓰는 일은 services/chat_service.py 가 repositories 로 한다.
"""

from app.ai.llm import ask_json
from app.core.config import INDICATORS
from app.prompts.memory import EXTRACT_PROMPT

DEAL_TYPES = ["매매", "전세", "월세"]
MEMORY_CHARS = 200        # 답변 프롬프트에 싣는 기억의 상한. 기억이 질문보다 커지면 답이 기억에 끌려간다
LIST_LIMIT = 5            # 목록 칸 하나에 남기는 개수. 오래 쓰면 avoid 가 끝없이 늘어난다

FIELDS = ("budget_manwon", "deal_type", "commute", "priorities", "avoid")

SCHEMA = {
    "type": "object",
    "properties": {
        "budget_manwon": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "deal_type": {"anyOf": [{"type": "string", "enum": DEAL_TYPES}, {"type": "null"}]},
        "commute": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "priorities": {"type": "array", "items": {"type": "string", "enum": INDICATORS}},
        "avoid": {"type": "array", "items": {"type": "string"}},
    },
    "required": list(FIELDS),
    "additionalProperties": False,
}


def empty():
    return {"budget_manwon": None, "deal_type": None, "commute": None, "priorities": [], "avoid": []}


def clean(raw):
    """Claude 답이든 DB 값이든 같은 모양으로 맞춘다. 모양이 틀린 칸은 비운다(믿지 않는다)"""
    raw = raw or {}
    out = empty()
    budget = raw.get("budget_manwon")
    if isinstance(budget, int) and not isinstance(budget, bool) and budget > 0:
        out["budget_manwon"] = budget
    if raw.get("deal_type") in DEAL_TYPES:
        out["deal_type"] = raw["deal_type"]
    if isinstance(raw.get("commute"), str) and raw["commute"].strip():
        out["commute"] = raw["commute"].strip()[:30]
    out["priorities"] = [p for p in dict.fromkeys(raw.get("priorities") or []) if p in INDICATORS][:LIST_LIMIT]
    out["avoid"] = [a.strip()[:20] for a in dict.fromkeys(raw.get("avoid") or [])
                    if isinstance(a, str) and a.strip()][:LIST_LIMIT]
    return out


def is_empty(memory):
    return clean(memory) == empty()


def extract(question):
    """질문 하나에서 사용자가 직접 말한 선호만 뽑는다"""
    return clean(ask_json([("system", EXTRACT_PROMPT), ("human", question)], SCHEMA))


def merge(old, new):
    """새로 말한 칸만 덮는다. 목록은 새 것을 앞에 두고 합친다(오래된 것이 LIST_LIMIT 밖으로 밀려난다)"""
    old, new = clean(old), clean(new)
    out = {k: new[k] if new[k] is not None else old[k] for k in ("budget_manwon", "deal_type", "commute")}
    for k in ("priorities", "avoid"):
        out[k] = list(dict.fromkeys(new[k] + old[k]))[:LIST_LIMIT]
    return clean(out)


def _money(manwon):
    eok, rest = divmod(manwon, 10000)
    return f"{eok}억 {rest:,}만원".replace(" 0만원", "") if eok else f"{rest:,}만원"


def to_prompt_line(memory):
    """기억 -> "예산 3억 · 전세 · 통근 강남역 · 중요 교육, 안전 · 피함 언덕". 비었으면 빈 글자"""
    m = clean(memory)
    parts = []
    if m["budget_manwon"]:
        parts.append(f"예산 {_money(m['budget_manwon'])}")
    if m["deal_type"]:
        parts.append(m["deal_type"])
    if m["commute"]:
        parts.append(f"통근 {m['commute']}")
    if m["priorities"]:
        parts.append(f"중요 {', '.join(m['priorities'])}")
    if m["avoid"]:
        parts.append(f"피함 {', '.join(m['avoid'])}")
    return " · ".join(parts)
