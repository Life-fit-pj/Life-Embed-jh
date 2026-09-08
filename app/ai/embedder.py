"""문장을 벡터로 바꾼다. 6단계부터는 OpenAI 가 계산해서 돌려준다.

5단계까지는 e5-small 이 내 컴퓨터 안에서 돌았다. 바뀐 것 넷 —
  모델    intfloat/multilingual-e5-small  ->  text-embedding-3-small
  차원    384  ->  1536
  접두사  passage:/query: 를 붙였다  ->  안 붙인다 (e5 계열 전용 규칙이었다)
  정규화  우리가 normalize_embeddings=True 로 켰다  ->  OpenAI 가 길이 1 로 준다

지연 로딩(get_model)이 사라진 이유 —
올릴 모델이 없다. 계산은 OpenAI 쪽에서 하고 우리는 결과만 받는다.

수업(rag-basic-master/app/ai/embedder.py)과 같은 모양이다.
"""

from openai import OpenAI

from app.core.config import EMBED_MODEL, OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def embed_documents(texts):
    """글 여러 개를 한 번에 벡터로. 하나씩 부르는 것보다 훨씬 빠르다."""
    reply = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in reply.data]


def embed_query(text):
    """글 하나를 벡터로."""
    return embed_documents([text])[0]
