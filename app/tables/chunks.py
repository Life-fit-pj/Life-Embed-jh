"""임베딩 청크 표를 다루는 SQL. 회원 청크와 지식베이스 청크를 꺼낸다."""

from app.core.db import dicts      # 실행기는 core 에서 가져온다


def member_chunks():
    """회원 청크와 벡터를 전부 꺼낸다. (07번에서 쓰던 것)"""
    return dicts(
        "SELECT customer_id, category, text, vector FROM member_chunk"
    )


def kb_chunks():
    """지식베이스 청크와 벡터를 전부 꺼낸다. (09번에서 쓸 것)"""
    return dicts(
        "SELECT chunk_id, uuid, district, category, text, vector FROM kb_chunk"
    )