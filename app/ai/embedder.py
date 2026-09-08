"""문장을 벡터로 바꾼다. 지금은 e5-small 이 내 컴퓨터 안에서 돈다(API 아님).

LangChain(HuggingFaceEmbeddings) 껍데기를 벗기고 sentence-transformers 를 직접 부른다.
모델도 차원도 그대로다 — 6단계에서 OpenAI 로 갈아 끼울 때 이 파일만 고친다.

지연 로딩(_model 을 처음 부를 때 만든다)을 쓰는 이유 —
모델을 올리는 데 몇 초 걸린다. import 하는 순간 올라가면
그 모듈을 쓰지 않는 파일까지 느려진다.
"""

from sentence_transformers import SentenceTransformer

from app.core.config import EMBED_MODEL

_model = None


def get_model():
    """무거우니 한 번만 올린다. 서버가 뜰 때 미리 부르면 첫 검색이 안 느리다."""
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def embed_documents(texts):
    """여러 글을 한 번에 벡터로. 파이썬 리스트로 돌려준다.

    ★ 두 줄은 LangChain 이 대신 해 주던 것이라 반드시 옮겨 적어야 한다 —
      ① 줄바꿈 -> 공백. langchain_huggingface 가 encode 앞에서 하던 일이다
      ② normalize_embeddings=True. 벡터 길이를 1 로 맞춰야 곱하기만으로 유사도가 나온다
    """
    texts = [text.replace("\n", " ") for text in texts]
    vectors = get_model().encode(texts, normalize_embeddings=True)
    return vectors.tolist()


def embed_query(text):
    """글 하나를 벡터로."""
    return embed_documents([text])[0]


def to_passage(text):
    """저장할 문서에 붙이는 접두사.

    e5 계열 모델의 규칙이다. 저장할 때와 검색할 때 접두사가 다르다.
    6단계에서 OpenAI 로 가면 이 둘은 지운다 — 거기선 접두사가 잡음이 된다
    """
    return f"passage: {text}"


def to_query(text):
    """검색할 질문에 붙이는 접두사."""
    return f"query: {text}"
