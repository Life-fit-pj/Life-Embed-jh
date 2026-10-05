"""프롬프트를 Claude 에게 가는 글 그대로 찍는다 — 자리표시를 채운 뒤의 최종 글이다.

실행:  py -m tools.show_prompts              # 목록 (이름 · 글자 수 · 하는 일)
       py -m tools.show_prompts EXPLAIN      # 이름에 그 말이 들어간 프롬프트의 글 전체
       py -m tools.show_prompts all          # 일곱 개 전부

고치기 전후를 견줄 때 쓴다 — 고치기 전에 `py -m tools.show_prompts all > before.txt`, 고친 뒤 `> after.txt`, 두 파일을 비교한다.
공통 규칙(app/prompts/common.py)을 고쳤으면 어느 프롬프트들이 같이 바뀌었는지가 여기서 보인다.
Claude 도 DB 도 안 부른다.
"""

import sys

from app.prompts import admin, chat, search

PROMPTS = {
    "search.WEIGHTS_PROMPT": (search.WEIGHTS_PROMPT, "검색어 → 가중치"),
    "search.EXPLAIN_PROMPT": (search.EXPLAIN_PROMPT, "추천 결과 → 설명문"),
    "search.REGION_PROMPT": (search.REGION_PROMPT, "동네 하나(핀) → 설명문"),
    "chat.PLAN_PROMPT": (chat.PLAN_PROMPT, "채팅 — 도구를 쓸지 고르기"),
    "chat.ANSWER_PROMPT": (chat.ANSWER_PROMPT, "채팅 — 답하기"),
    "admin.ANALYSIS_PROMPT": (admin.ANALYSIS_PROMPT, "관리자 분석"),
    "admin.SUGGEST_PROMPT": (admin.SUGGEST_PROMPT, "회원 성향 제안"),
}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")      # Windows 콘솔(cp949)에서 못 찍는 글자로 죽지 않게
    want = sys.argv[1] if len(sys.argv) > 1 else ""

    if not want:
        for name, (text, job) in PROMPTS.items():
            print(f"{name:<24} {len(text):>5}자   {job}")
        return

    picked = {name: pair for name, pair in PROMPTS.items() if want == "all" or want.lower() in name.lower()}
    if not picked:
        print(f"'{want}' 이 들어간 프롬프트가 없다. 고를 수 있는 것 — {', '.join(PROMPTS)}")
        return
    for name, (text, job) in picked.items():
        print(f"===== {name} — {job} ({len(text)}자) =====")
        print(text)
        print()


if __name__ == "__main__":
    main()
