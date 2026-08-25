"""
할 일 : 가중치 7개로 427개 행정동의 점수를 매겨 TOP 5 를 뽑는다

밀도값은 단위가 제각각이라 그대로 곱하면 안 된다.
모든 칸을 백분위(0~100, 427개 동 중 몇 등인가)로 바꾼 뒤 가중합한다.
"""

import numpy as np

from core.db import region_densities

INDICATOR_COLUMNS = {
    "녹지" : ["공원_밀도"],
    "안전" : ["CCTV_밀도","경찰관서_밀도"],
    "교통": ["버스정류장_밀도", "지하철역_밀도"],
    "상권": ["점포_밀도", "대형점포_밀도"],
    "의료": ["의료기관_밀도"],
    "교육": ["학교_밀도", "학원_밀도"],
    "문화": ["문화시설_밀도", "도서관_밀도"],
}

def load_regions():
    """427개 동의 이름과, 매핑에 쓰이는 밀도 칸들을 꺼낸다."""
    # 매핑에 등장하는 칸을 전부 모은다 (중복 없이, 순서 유지)
    cols = []
    for cs in INDICATOR_COLUMNS.values():
        for c in cs:
            if c not in cols:
                cols.append(c)

    rows = region_densities(cols)
    
    names = [f"{r['구']} {r['행정동명']}" for r in rows]
    
    # 칸별 값 묶음. values["공원_밀도"] = 427개 숫자 배열
    values = {}
    for c in cols:
        values[c] = np.array([r[c] or 0 for r in rows], dtype="float64")
    
    return names, values

def to_percentile(values) :
    """숫자 묶음을 0~100 백분위로 바꾼다.

    "427개 동 중 몇 등인가" 를 점수로 만드는 것이다.
    가장 낮은 동이 0점, 가장 높은 동이 100점.

    argsort 를 두 번 쓰는 이유 —
    첫 번째 argsort 는 "작은 것부터 몇 번째 위치인지" 를 준다.
    거기에 다시 argsort 를 하면 "각 값이 몇 등인지" 로 뒤집힌다.
    """
    order = values.argsort().argsort()
    return order / (len(values) - 1) * 100

def build_scores(values):
    """밀도 칸들을 7개 지표 점수(0~100)로 바꾼다.

    칸이 여러 개인 지표는 각각 백분위로 바꾼 뒤 평균낸다.
    (안전 = CCTV 백분위와 경찰관서 백분위의 평균)
    """
    scores = {}
    
    for indicator, cols in INDICATOR_COLUMNS.items():
        parts = [to_percentile(values[c]) for c in cols]
        scores[indicator] = sum(parts) / len(parts)
    
    return scores

def build_relative(scores):
    """각 동네에서 지표가 '특기'인 정도를 만든다.

    (그 지표 점수) - (그 동네 7개 지표의 평균)
    양수면 그 동네의 강점, 음수면 약점이다.

    왜 필요한가 —
    절대점수 가중합은 "골고루 높은 동네"가 항상 이긴다.
    신당제5동은 교육이 60점(자기 평균보다 -21)인데도
    "애들 학원" 검색에서 1위였다. 특기를 봐야 한다.
    """
    keys = list(scores)
    stacked = np.stack([scores[k] for k in keys])
    region_mean = stacked.mean(axis=0)      # 동네별 자기 평균
    
    return {k: scores[k] - region_mean for k in keys}


def recommend(names, scores, relative, weights, top_k=5, mix=0.5, sharpen=6):
    """가중치 차이를 증폭해서 중시 지표가 순위를 주도하게 한다.

    가중치 4.4 vs 3.0 은 비율로 1.5배뿐이라, 7개를 다 더하면
    중시 지표가 전체의 20% 밖에 안 된다. 순위를 못 바꾼다.
    그래서 평균(3.0)에서 벗어난 만큼을 지수로 증폭한다.
    """
    # 평균 대비 편차를 지수로 키운다. 4.4 -> 크게, 2.6 -> 아주 작게
    mean_w = sum(weights.values()) / len(weights)
    amp = {k: (w / mean_w) ** sharpen for k, w in weights.items()}

    total_weight = sum(amp.values())
    total = np.zeros(len(names))
    for k, w in amp.items():
        combined = scores[k] * mix + (relative[k] + 50) * (1 - mix)
        total += combined * w
    total /= total_weight

    top = total.argsort()[::-1][:top_k]
    return [(names[i], float(total[i])) for i in top]


if __name__ == "__main__" :
    names, values = load_regions()
    scores = build_scores(values)
    relative = build_relative(scores)
    
    # 07번에서 나왔던 실제 가중치로 시험해본다
    tests = {
        "애들 학원 보내기 좋은 곳":
            {"녹지": 3.3, "안전": 3.1, "교통": 2.6, "상권": 3.2,
             "의료": 3.0, "교육": 4.4, "문화": 2.6},
        "병원이 가깝고 할머니를 모시고 살기 좋은 곳":
            {"녹지": 3.3, "안전": 3.1, "교통": 2.8, "상권": 3.1,
             "의료": 4.6, "교육": 2.4, "문화": 2.7},
        "멀지 않은 거리에 백화점이 있는 곳":
            {"녹지": 3.1, "안전": 3.2, "교통": 2.6, "상권": 4.9,
             "의료": 3.1, "교육": 2.8, "문화": 2.9},
    }
    
    for query, weights in tests.items():
        print(f"검색어: {query}")
        for rank, (name, score) in enumerate(recommend(names, scores, relative, weights), start=1):
            print(f"   {rank}위 {name:20s} {score:.1f}점")
        print()