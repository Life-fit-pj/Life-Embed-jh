"""프롬프트와 재료의 짝 — 프롬프트가 이름으로 가리키는 것이, 그것을 만들거나 읽는 코드에 실제로 있나.

프롬프트는 "`## 사용자가 원한 가격` 절이 있으면 금액을 말하라"처럼 재료의 제목 · 키를 가리켜 지시한다.
한쪽만 고치면 그 규칙이 조용히 안 먹는다 — 오류도 없고 다른 테스트도 통과한다. 그래서 짝을 여기 적어 두고 지킨다.
DB 도 Claude 도 안 쓴다. 글자만 본다.

새 짝이 생기면(프롬프트에 재료의 이름을 새로 적으면) PAIRS 에 한 줄을 더한다.
"""

import inspect
import re

from app.engine import chat_context, explain, housing, weights
from app.prompts import admin, chat, search
from app.prompts.common import PRICE_AMOUNT_RULE, PRICE_DIRECTION_RULE, PRICE_FIT_RULE, PRICE_SCORE_RULE
from app.services import activity_service, analysis_service
from app.tools import tools

PROMPTS = {
    "search.WEIGHTS_PROMPT": search.WEIGHTS_PROMPT,
    "search.EXPLAIN_PROMPT": search.EXPLAIN_PROMPT,
    "search.REGION_PROMPT": search.REGION_PROMPT,
    "chat.ANSWER_PROMPT": chat.ANSWER_PROMPT,
    "chat.PLAN_PROMPT": chat.PLAN_PROMPT,
    "admin.ANALYSIS_PROMPT": admin.ANALYSIS_PROMPT,
    "admin.SUGGEST_PROMPT": admin.SUGGEST_PROMPT,
}

# (프롬프트 이름, 프롬프트가 가리키는 글자, 그 글자를 만들거나 읽는 코드)
PAIRS = [
    # 검색어 → 가중치: 프롬프트가 약속한 JSON 의 키를 ask_claude() 가 그 이름으로 읽는다
    *[("search.WEIGHTS_PROMPT", f'"{key}"', weights.ask_claude)
      for key in ("persona_query", "건물유형", "거래유형", "예산", "보증금", "지역", "미지원_조건", "가격대", "세부")],
    # 설명문 둘: 재료의 제목과 시세 한 줄의 낱말
    ("search.EXPLAIN_PROMPT", "## 사용자가 원한 가격", housing.price_head_lines),
    ("search.EXPLAIN_PROMPT", "참고 시세", housing.price_head_lines),
    ("search.EXPLAIN_PROMPT", "조건 일치도", housing.price_fit_line),
    ("search.EXPLAIN_PROMPT", "목표보다", housing.price_gap_text),
    ("search.EXPLAIN_PROMPT", "참고 사례", explain.build_context),
    ("search.REGION_PROMPT", "## 사용자가 원한 가격", housing.price_head_lines),
    ("search.REGION_PROMPT", "참고 시세", housing.price_head_lines),
    ("search.REGION_PROMPT", "조건 일치도", housing.price_fit_line),
    # 채팅: 재료 줄의 머리와, 도구가 돌려주는 사전의 키
    ("chat.ANSWER_PROMPT", "생활여건", chat_context._region_block),
    ("chat.ANSWER_PROMPT", "동네 전체 중앙값", chat_context._region_block),
    ("chat.ANSWER_PROMPT", '"순위"', tools.rerank_by_focus),
    ("chat.ANSWER_PROMPT", '"기준"', tools.rerank_by_focus),
    ("chat.ANSWER_PROMPT", '"안_반영된_것"', tools.rerank_by_focus),
    ("chat.ANSWER_PROMPT", '"오류"', tools.run_tool),
    ("chat.PLAN_PROMPT", "rerank_by_focus", tools),
    # 관리자: 재료의 제목 · 집계의 키 · 답의 JSON 키
    ("admin.ANALYSIS_PROMPT", "집계 자료", analysis_service.ask),
    ("admin.ANALYSIS_PROMPT", "비어있는_이유", analysis_service),
    ("admin.SUGGEST_PROMPT", "지난번에 정리한 성향", activity_service._material),
    ("admin.SUGGEST_PROMPT", '"성향"', activity_service._parse),
    ("admin.SUGGEST_PROMPT", '"가중치"', activity_service._parse),
]


def test_프롬프트가_가리키는_이름이_재료에_있다():
    """깨지면 — 프롬프트나 재료 중 한쪽의 이름만 바뀐 것이다. 찍힌 줄의 양쪽을 같이 고친다"""
    broken = []
    for name, token, maker in PAIRS:
        where = getattr(maker, "__qualname__", None) or maker.__name__
        if token not in PROMPTS[name]:
            broken.append(f"{name} 에 {token} 이 없다")
        if token not in inspect.getsource(maker):
            broken.append(f"{where} 에 {token} 이 없다 ({name} 이 가리킨다)")
    assert broken == []


def test_자리표시가_남아_있지_않다():
    """__이름__ 이 남아 있으면 끼우는 줄이 빠진 것이다 — Claude 가 그 글자를 그대로 받는다"""
    left = {name: re.findall(r"__[A-Z_]+__", text) for name, text in PROMPTS.items()}
    assert {name: found for name, found in left.items() if found} == {}


def test_가격_규칙은_두_설명문에_글자까지_같이_들어_있다():
    """추천 설명문과 동네 설명문이 시세를 다르게 읽지 않게 — 한쪽에서만 빠지면 그쪽이 "시세 85점"을 "비싸다"로 읽는다"""
    for rule in (PRICE_FIT_RULE, PRICE_SCORE_RULE):
        assert rule in search.EXPLAIN_PROMPT and rule in search.REGION_PROMPT


def test_시세_방향_규칙은_채팅에도_같은_글자로_들어_있다():
    """채팅만 시세를 반대로 읽지 않게. 금액 규칙은 채팅에 안 들어간다 — 채팅 재료에는 '## 사용자가 원한 가격' 절이 없다"""
    assert PRICE_DIRECTION_RULE in chat.ANSWER_PROMPT
    assert PRICE_AMOUNT_RULE not in chat.ANSWER_PROMPT
    assert "__PRICE_DIRECTION_RULE__" not in chat.ANSWER_PROMPT      # 자리표시가 안 채워진 채 나가면 Claude 가 그 글자를 본다


def test_시세_규칙은_방향과_금액을_빈_줄_하나로_이은_것이다():
    """나누기 전의 PRICE_SCORE_RULE 과 글자가 같아야 검색 설명문 둘의 프롬프트가 안 바뀐다"""
    assert PRICE_SCORE_RULE == PRICE_DIRECTION_RULE + "\n\n" + PRICE_AMOUNT_RULE
    assert PRICE_SCORE_RULE.count("\n\n") == 1
