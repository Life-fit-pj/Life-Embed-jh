"""Claude 에게 묻고 답을 받는다. anthropic SDK 를 직접 부른다.

LangChain(ChatAnthropic) 을 걷어내면서 부르는 모양도 함수 하나로 줄였다 —
    옛     get_llm(max_tokens=300).invoke(messages).content
    지금   ask(messages, max_tokens=300)

messages 는 옛 모양을 그대로 받는다: [("system", 지시문), ("human", 질문)].
부르는 쪽 7곳이 프롬프트를 만드는 코드는 한 줄도 안 고치려는 것이다.
튜플을 SDK 모양으로 바꾸는 번역은 이 파일 안에서만 일어난다(이론 8).
"""

from anthropic import Anthropic

from app.core.config import API_KEY, MODEL

client = Anthropic(api_key=API_KEY)


def ask(messages, max_tokens=800):
    """Claude 의 답을 글자 그대로 돌려준다.

    messages 는 ("system"|"human", 글) 튜플 목록이거나 글 한 개다 —
    survey.py 와 fix_member_persona.py 가 글 한 개를 그냥 넘긴다
    """
    if isinstance(messages, str):
        messages = [("human", messages)]

    system = "\n\n".join(text for role, text in messages if role == "system")
    turns = [
        {"role": "user", "content": text}
        for role, text in messages
        if role != "system"
    ]

    reply = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=turns,
    )
    return reply.content[0].text

