"""설문 답변을 Claude 에게 채점시키는 창구.

프롬프트를 만드는 쪽(Life-Web/services/persona_type.py)과 LLM 을 부르는 쪽을
나눈 이유 — 문항·프롬프트는 화면 쪽 관심사고, LLM 키와 모델은 엔진 쪽 관심사다.
"""
from app.adapters.llm import get_llm


def score_survey(prompt: str) -> str:
    """프롬프트를 받아 Claude 의 답을 글자 그대로 돌려준다.

    JSON 파싱은 안 한다 — 그건 문항을 아는 쪽(persona_type)이 할 일이다.
    """
    if not prompt:
        return ""
    return get_llm(max_tokens=500).invoke(prompt).content.strip()