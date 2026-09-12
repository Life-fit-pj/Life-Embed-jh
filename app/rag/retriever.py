"""검색어를 받아 뜻이 가까운 것을 찾아온다. RAG 의 R(Retrieval) 이다.

직접 확인해 보기:
    py -m app.rag.retriever kb "조용한 동네에서 아이 키우는 사람"
    py -m app.rag.retriever member "야근이 잦고 교통을 중요하게 보는 사람"

하는 일은 두 줄이다 —
    1. 질문을 벡터로 바꾼다      app/ai/embedder.py
    2. 그 벡터와 가까운 것을 찾는다  app/ai/vector_store.py

옛 pipeline/search_kb.py 가 하던 일이 여기로 왔다(7-9절).
"""

import sys

from app.ai import vector_store
from app.ai.embedder import embed_query


def retrieve(source, query, top_k=5):
    """뜻이 가까운 청크 top_k. [(행, 점수)]"""
    return vector_store.search(source, embed_query(query), top_k)


def retrieve_people(source, query, top_k=5):
    """사람 단위로 top_k. [(id, 점수, 행)]"""
    return vector_store.search_people(source, embed_query(query), top_k)


def main():
    if len(sys.argv) < 3:
        print('사용법: py -m app.rag.retriever [member|kb] "질문"')
        return

    source, query = sys.argv[1], sys.argv[2]

    print(f'질문: "{query}"   갈래: {source}')
    print()
    for rank, (row, score) in enumerate(retrieve(source, query), start=1):
        print(f"  {rank}. {score:.3f}  [{row['category']}] {row['text'][:60]}...")


if __name__ == "__main__":
    main()
