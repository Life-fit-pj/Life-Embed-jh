"""
임베딩 모델과 LLM 을 여기서만 만든다.

LangChain 어댑터를 쓰는 이유 —
모델을 바꿀 때 이 파일 한 곳만 고치면 된다.
지금은 Claude + e5-small 이지만, 나중에 다른 모델로 실험할 때
weights.py 나 explain.py 를 건드리지 않아도 된다.

지연 로딩(_embedder 를 처음 부를 때 만든다)을 쓰는 이유 —
모델을 올리는 데 몇 초 걸린다. import 하는 순간 올라가면
그 모듈을 쓰지 않는 파일까지 느려진다.
서버로 갈 때는 시작할 때 한 번 불러 두고 계속 재사용한다.
"""

from langchain_anthropic import ChatAnthropic
from langchain_huggingface import HuggingFaceEmbeddings

from core.config import API_KEY, EMBED_MODEL, MODEL

_embedder = None
_llm = None


def get_embedder() :
    """문장을 벡터로 바꾸는 모델. 무거우니 한 번만 올린다."""
    global _embedder
    if _embedder is None :
        _embedder = HuggingFaceEmbeddings(
            model_name = EMBED_MODEL,
            # 벡터 길이를 1로 맞춘다. 그래야 곱하기만으로 유사도가 나온다.
            # LangChain 은 이 옵션을 자동으로 켜 주지 않는다
            encode_kwargs = {"normalize_embeddings" : True},
            show_progress = False,       #진행 막대
        )
    return _embedder


def get_llm(max_tokens=800) :
    """Claude. max_tokens 가 다르면 새로 만든다."""
    return ChatAnthropic(
        model = MODEL,
        api_key = API_KEY,
        max_tokens = max_tokens,
    )


def to_passage(text) :
    """저장할 문서에 붙이는 접두사.

    e5 계열 모델의 규칙이다. LangChain 이 자동으로 붙여 주지 않으므로
    우리가 직접 붙인다. 저장할 때와 검색할 때 접두사가 다르다
    """
    return f"passage: {text}"


def to_query(text) :
    """검색할 질문에 붙이는 접두사."""
    return f"query: {text}"


if __name__ == "__main__":
    emb = get_embedder()
    v = emb.embed_query(to_query("산책 좋아하는 사람"))
    print(f"✅ 벡터 길이: {len(v)}")          # 384 여야 함

    llm = get_llm(max_tokens=100)
    print(f"✅ LLM 응답: {llm.invoke('안녕이라고만 답해').content}")


