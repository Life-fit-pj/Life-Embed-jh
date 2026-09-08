"""7단계 전후로 검색 경로가 같은 답을 내는지 보려고 찍는 임시 사진.

골든 넷은 이 경로를 안 본다(7-0절). 그래서 이 단계 동안만 쓰는 사진을 따로 찍는다.
8단계가 끝나면 지운다.

LLM 을 부르는 함수는 담지 않는다 — ask_claude 는 같은 질문에도 답이 달라져서
"바뀐 것"과 "원래 흔들리는 것"을 못 가린다.

찍기:  py -m tools.snap_search > tools/search_before.txt
대조:  py -m tools.snap_search > tools/search_after.txt
       Compare-Object (Get-Content tools/search_before.txt) (Get-Content tools/search_after.txt)
"""

from app.engine.explain import find_cases
from app.engine.weights import find_similar_members

QUERIES = [
    "조용한 동네에서 아이 키우기 좋은 곳",
    "야근이 잦아서 교통이 편한 곳",
    "카페와 전시가 많은 동네",
]


def main():
    for query in QUERIES:
        print(f"[{query}]")

        for cid, (score, category, _) in find_similar_members(query):
            print(f"  member {cid} {score:.4f} {category}")

        for case in find_cases(query):
            print(f"  kb     {case['district']} {case['score']:.4f} {case['category']}")

        print()


if __name__ == "__main__":
    main()
