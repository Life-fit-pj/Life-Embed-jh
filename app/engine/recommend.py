"""
할 일 : 가중치 7개로 427개 행정동의 점수를 매겨 TOP 5 를 뽑는다

밀도값은 단위가 제각각이라 그대로 곱하면 안 된다.
모든 칸을 백분위(0~100, 427개 동 중 몇 등인가)로 바꾼 뒤 가중합한다.
"""

import numpy as np

from app.repositories.regions import region_densities
from app.engine.housing import DEAL_COLUMNS

INDICATOR_COLUMNS = {
    "녹지" : ["공원_밀도"],
    "안전" : ["CCTV_밀도","경찰관서_밀도"],
    "교통": ["버스정류장_밀도", "지하철역_밀도"],
    "상권": ["점포_밀도", "대형점포_밀도"],
    "의료": ["의료기관_밀도"],
    "교육": ["학교_밀도", "학원_밀도"],
    "문화": ["문화시설_밀도", "도서관_밀도"],
}


# 화면이 "공원 5개 · CCTV 120대" 처럼 보여줄 **원본 개수**.
# 밀도(INDICATOR_COLUMNS)는 순위를 매기는 값이고, 이쪽은 근거로 보여주는 값이다.
#
# ★ 여기 적힌 칸은 Life-Web/services/typespot.py 의 BLURB_COLS 와 짝이다.
#   한쪽만 고치면 카드 문구가 조용히 빈다 — 그래서 서로를 주석으로 가리켜 둔다.
#
# 같은 표(master_dataset_v3)의 같은 427행을 읽는 한 번의 쿼리에 칸만 더하는 것이라
# 비용이 사실상 0 이다(실측: 12칸 342ms → 24칸 342ms)
COUNT_COLUMNS = [
    "공원_수", "CCTV_수", "경찰관서_수", "지하철역_수", "버스정류장_수",
    "대형점포_수", "점포_수", "의료기관_수", "학교_수", "학원_수",
    "문화시설_수", "도서관_수",
]


def load_regions():
    """427개 동의 이름과, 밀도 칸·개수 칸을 꺼낸다.

    한 번의 쿼리로 둘을 같이 가져온다 — 순위에 쓸 밀도와, 화면 근거로 쓸 개수다.
    돌려주는 것 셋: names · values(밀도, numpy) · counts(개수, 동네별 dict)
    """
    # 매핑에 등장하는 칸을 전부 모은다 (중복 없이, 순서 유지)
    cols = []
    for cs in INDICATOR_COLUMNS.values():
        for c in cs:
            if c not in cols:
                cols.append(c)

    rows = region_densities(cols + COUNT_COLUMNS)
    
    names = [f"{r['구']} {r['행정동명']}" for r in rows]
    
    # 밀도는 계산용이라 numpy 배열로
    values = {}
    for c in cols:
        values[c] = np.array([r[c] or 0 for r in rows], dtype="float64")
    
    # 개수는 그대로 보여줄 값이라 동네별 딕셔너리로.
    # 이름으로 찾을 일이 많아 리스트가 아니라 {동네이름: {칸: 값}} 이다
    counts = {
        name: {c: row[c] for c in COUNT_COLUMNS}
        for name, row in zip(names, rows)
    }

    return names, values, counts


def to_percentile(values, invert=False) :
    """숫자 묶음을 0~100 백분위로 바꾼다.
    같은 값은 반드시 같은 점수를 받아야 한다.
    """
    order = values.argsort()
    rank = np.empty(len(values), dtype="float64")
    rank[order] = np.arange(len(values))        # 각 값이 몇 등인지

    # 동점끼리는 순위 평균을 공유한다 (0곳인 275개 동은 전부 같은 점수)
    for value in np.unique(values):
        same = values == value
        rank[same] = rank[same].mean()

    pct = rank / (len(values) - 1) * 100

    return 100 - pct if invert else pct


INDICATOR_INVERT = {"시세"}   # 이 지표들은 낮을수록 좋다


def build_scores(values):
    """밀도 칸들을 7개 지표 점수(0~100)로 바꾼다.

    칸이 여러 개인 지표는 각각 백분위로 바꾼 뒤 평균낸다.
    (안전 = CCTV 백분위와 경찰관서 백분위의 평균)
    """
    scores = {}
    
    for indicator, cols in INDICATOR_COLUMNS.items():
        invert = indicator in INDICATOR_INVERT
        parts = [to_percentile(values[c], invert=invert) for c in cols]
        scores[indicator] = sum(parts) / len(parts)

    return scores


# ── 목표가 없을 때(접근 A) 시세를 8번째 신호로 쓰기 위한 재료 ──────────────
# INDICATOR_COLUMNS 에는 안 넣는다 — build_relative() 의 "동네 자기 평균" 기준선이
# housing 이 있는 요청에도 영향을 받게 되는 부작용이 있어서, 별도로 분리해서 계산한다.

# "4개 건물유형 × 3개 거래유형" 각각의 "예산" 칼럼(매매가/전세보증금/월세) = 12개.
# DEAL_COLUMNS 를 그대로 재사용한다 — 새로 정의할 필요가 없다
PRICE_COLUMNS = [cols["예산"] for cols in DEAL_COLUMNS.values()]


def load_price_values(rows):
    """시세 칼럼은 결측을 0이 아니라 그 칼럼의 중앙값으로 채운다.

    기존 7개 지표(밀도)는 결측=0이 맞다("그 동엔 진짜 0개"라는 뜻). 하지만 시세 칼럼의
    결측은 "그 조합(예: 오피스텔+매매) 매물 자체가 없어 시세를 못 구했다"는 뜻이지
    "공짜"가 아니다. 0으로 채우면 invert=True 계산에서 가장 저렴한 동네로 둔갑해
    엉뚱하게 1등으로 뽑힐 수 있다. 중앙값으로 채우면 최소한 "평범한 동네"로 취급된다.
    """
    values = {}
    for c in PRICE_COLUMNS:
        raw = [r[c] for r in rows]
        known = [v for v in raw if v is not None]
        fallback = float(np.median(known)) if known else 0.0
        values[c] = np.array([v if v is not None else fallback for v in raw], dtype="float64")
    return values


def build_price_score(values):
    """12개 컬럼(4건물유형×3거래유형)의 평균 백분위. 낮을수록 높은 점수.

    build_scores()/build_relative() 에는 안 섞는다 — 섞으면 housing 이 있는 요청
    (목표가가 명시된 검색)에서도 relative 기준선이 8개짜리로 바뀌어 기존 추천 결과가
    미묘하게 달라지기 때문이다.
    """
    parts = [to_percentile(values[c], invert=True) for c in PRICE_COLUMNS]
    return sum(parts) / len(parts)


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