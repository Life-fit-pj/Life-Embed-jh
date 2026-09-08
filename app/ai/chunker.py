"""
할 일 : 긴 텍스트를 임베딩 모델이 받아들일 수 있는 길이로 쪼갠다.

부르는 쪽이 둘이고, 둘이 똑같이 쪼개야 한다 —
  pipeline/chunk.py      적재. kb_persona.csv 와 nemotron.csv 를 통째로
  app/engine/resync.py   관리자가 방금 고친 한 명만 다시

두 곳에 각자 넣으면 한쪽만 고치고 다른 쪽을 빠뜨린다. 그러면 쌓인 벡터와
새로 만든 벡터가 다른 규칙으로 잘려 같은 기준으로 비교할 수 없게 된다
(app/ai/embedder.py 가 임베딩 부르는 자리를 한 곳에 모은 것과 같은 이유).

왜 필요한가 —
임베딩 모델은 받는 길이에 상한이 있고, 넘으면 에러 없이 조용히 뒷부분이
잘린다(silent truncation). 지금 모델(text-embedding-3-small)의 상한은
8,191 토큰이라 예전 e5-small(512)보다 훨씬 넉넉하고, 지금 데이터
(kb_persona.csv)는 실측 문장 최대 166자라 어차피 걸릴 일이 없다.
그래도 회원가입 서술형 입력처럼 길이를 통제할 수 없는 텍스트가 들어올 수
있으므로 미리 대비해둔다. 모델을 바꾸면 MAX_LENGTH 를 다시 본다
"""

import re

from app.core.config import CHUNK_COLUMNS, MIN_LENGTH

# 토큰 수를 정확히 재려면 임베딩 모델의 tokenizer 가 필요한데,
# 그러려면 무거운 모델을 청킹 단계에서부터 올려야 한다.
# 대신 글자 수로 넉넉하게 안전 마진을 두고 근사한다.
# (한국어는 토큰:글자 비율이 문장마다 달라서 딱 맞추기 어렵다 - 여유 있게 잡는 게 안전)
MAX_LENGTH = 350

# 문장이 끝나는 지점(. ! ?) 뒤에 공백이 오면 그 자리에서 나눈다
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

KB_KEYS = ("uuid", "district")
MEMBER_KEYS = ("customer_id",)      # ← 값이 하나일 때 쉼표를 빼면 튜플이 아니다

def split_long_text(text, max_length=MAX_LENGTH):
    """긴 텍스트를 max_length 글자 이하 조각 여러 개로 쪼갠다.

    1단계 — 문장 단위로 나눈다. 문장 하나가 max_length 안이면 그대로 둔다.
    2단계 — 마침표가 없어서 문장이 안 나뉘는 경우(사용자가 마침표 없이
            길게 이어 쓴 경우), 그 조각만 글자 수로 강제로 잘라낸다.

    반환값은 항상 리스트다. text가 짧으면 [text] 하나짜리 리스트로 온다.
    """
    text = text.strip()
    if len(text) <= max_length:
        return [text]

    pieces = []
    for sentence in _SENTENCE_END.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) <= max_length:
            pieces.append(sentence)
        else:
            # 문장 분리로도 못 줄인 조각 -> 글자 수로 강제 분할
            for i in range(0, len(sentence), max_length):
                pieces.append(sentence[i:i + max_length])

    return pieces


def make_chunks(rows, keep):
    """페르소나 한 명을 칸별 청크로 쪼갠다.

    keep 은 청크마다 베껴 담을 칸 이름들. KB_KEYS 또는 MEMBER_KEYS 를 준다.
    """
    chunks = []

    for row in rows:
        for column in CHUNK_COLUMNS:
            text = (row.get(column) or "").strip()

            if len(text) < MIN_LENGTH:
                continue

            for piece in split_long_text(text):
                if len(piece) < MIN_LENGTH:
                    continue

                chunk = {name: row[name] for name in keep}
                chunk["category"] = column
                chunk["text"] = piece
                chunks.append(chunk)

    return chunks


if __name__ == "__main__":
    short = "짧은 문장입니다."
    print(f"짧은 텍스트 -> {split_long_text(short)}")

    long_with_dots = "첫 번째 문장입니다. " + "두 번째 문장은 아주 길게 이어집니다. " * 20 + "마지막 문장."
    result = split_long_text(long_with_dots)
    print(f"마침표 있는 긴 텍스트({len(long_with_dots)}자) -> {len(result)}개 조각, 길이: {[len(p) for p in result]}")

    long_no_dots = "마침표가 하나도 없이 계속 이어서 쓰는 사용자의 답변이라고 가정하고 만든 예시 텍스트 " * 15
    result2 = split_long_text(long_no_dots)
    print(f"마침표 없는 긴 텍스트({len(long_no_dots)}자) -> {len(result2)}개 조각, 길이: {[len(p) for p in result2]}")
