# Last updated: 2026-09-08
"""지금 동작을 파일로 굳힌다. 리팩터링을 시작하기 전에 한 번만 돌린다.

실행: py -m tests.make_golden      (Life-Embed-jh 안에서)

이미 golden/ 에 파일이 있으면 덮어쓰지 않는다.
사진을 다시 찍는 것은 "정답을 바꾸는 것"이므로, 일부러 지워야만 되게 한다.
"""

import json
from pathlib import Path

GOLDEN = Path(__file__).parent / "golden"

# 가중치 3벌. 순위가 확실히 갈리도록 서로 다른 방향으로 고른다.
# 전부 "보통(3)"만 쓰면 지표를 잘못 섞어도 순위가 안 변해서 못 잡는다.
CASES = {
    "보통":   {"녹지": 3, "안전": 3, "교통": 3, "상권": 3, "의료": 3, "교육": 3, "문화": 3},
    "육아":   {"녹지": 5, "안전": 5, "교통": 2, "상권": 2, "의료": 4, "교육": 5, "문화": 1},
    "직장인": {"녹지": 1, "안전": 3, "교통": 5, "상권": 5, "의료": 2, "교육": 1, "문화": 4},
}

# 임베딩 사진용 고정 문장. 절대 바꾸지 않는다 — 바꾸면 4단계 비교가 무의미해진다.
SENTENCE = "조용한 동네에서 아이 키우기 좋은 곳"


def snap_recommend():
    """가중치 -> TOP 5. LLM 을 안 부르므로 몇 번을 돌려도 같은 답이 나온다."""
    from app.services.search_service import recommend_by_weights

    return {
        label: [[r["name"], r["total"]] for r in recommend_by_weights(weights, top_k=5)]
        for label, weights in CASES.items()
    }


def snap_embed():
    """같은 문장이 같은 숫자가 되나.

    6단계에서 OpenAI 로 갈아 끼우며 다시 찍었다 — 차원이 384 에서 1536 이 됐고,
    e5 전용이던 질문 접두사도 사라졌다(이론 9).
    """
    from app.ai.embedder import embed_query

    vector = embed_query(SENTENCE)

    return {
        "문장": SENTENCE,
        "차원": len(vector),
        "앞5개": [round(value, 6) for value in vector[:5]],
    }


def snap_tables():
    """조회 함수가 무엇을 어떤 모양으로 돌려주나. 3단계에서 이것을 본다."""
    from app.repositories.chunks import member_chunk_count
    from app.repositories.members import member_weights

    return {
        "member_chunk_count": member_chunk_count(),
        "member_weights": member_weights(["C001", "C002"]),
    }


def snap_chunks():
    """청크 9,900개의 텍스트. 5단계에서 파이프라인을 새로 짠 뒤 이것과 맞춘다.

    텍스트를 통째로 담으면 파일이 1.3MB 가 된다. 사람이 못 읽는 파일은
    골든으로 쓸모가 적으므로, 개수 + 해시(지문)만 담는다.
    한 글자만 달라져도 해시가 완전히 달라지므로 비교에는 충분하다.
    """
    import hashlib

    from app.repositories.chunks import kb_chunks, member_chunks

    def fingerprint(rows, key):
        # 정렬해서 담는다 — 새 파이프라인이 다른 순서로 넣어도 통과해야 한다.
        # 순서까지 맞추라고 하면 "텍스트는 같은데 실패"가 나서 경보가 무뎌진다.
        texts = sorted(f'{row[key]}|{row["category"]}|{row["text"]}' for row in rows)
        joined = "\n".join(texts).encode("utf-8")
        return {"개수": len(texts), "해시": hashlib.sha256(joined).hexdigest()[:16]}

    return {
        "member": fingerprint(member_chunks(), "customer_id"),
        "kb": fingerprint(kb_chunks(), "uuid"),
    }


SNAPS = {
    "recommend": snap_recommend,
    "embed": snap_embed,
    "tables": snap_tables,
    "chunks": snap_chunks,
}


def main():
    GOLDEN.mkdir(exist_ok=True)

    for name, snap in SNAPS.items():
        path = GOLDEN / f"{name}.json"
        if path.exists():
            print(f"  {name}.json  이미 있음 -> 건너뜀 (다시 찍으려면 파일을 지운다)")
            continue

        path.write_text(
            json.dumps(snap(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  {name}.json  저장")


if __name__ == "__main__":
    main()
