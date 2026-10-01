"""
할 일 : 가중치 7개로 427개 행정동의 점수를 매겨 TOP 5 를 뽑는다

밀도값은 단위가 제각각이라 그대로 곱하면 안 된다.
모든 칸을 백분위(0~100, 427개 동 중 몇 등인가)로 바꾼 뒤 가중합한다.
"""

import numpy as np

from app.domain.dong import dong_variants
from app.repositories.regions import (
    category_counts, dong_coords, park_areas, region_densities, school_level_counts,
)
from app.engine.housing import DEAL_COLUMNS

INDICATOR_COLUMNS = {
    "녹지" : ["공원면적비율"],
    "안전" : ["CCTV_밀도","경찰관서_밀도"],
    "교통": ["버스정류장_밀도", "지하철역_밀도"],
    "상권": ["점포_밀도", "대형점포_밀도"],
    "의료": ["의료기관_밀도"],
    "교육": ["학교_밀도_2023", "학원_밀도"],
    "문화": ["문화시설_밀도", "도서관_밀도"],
}

# master 표에 없고 load_regions() 가 계산해 넣는 칸. 관리자 화면이 이걸 보고 표에서 읽을 칸과 가른다 — 빠지면 KeyError
DERIVED_COLUMNS = {"공원면적비율", "학교_밀도_2023"}

# INDICATOR_COLUMNS 의 칸 중 실제로 master 표에 있는 것 (중복 없이, 순서 유지).
# load_regions() 가 읽고, 관리자 화면(admin_service.REGION_FIELDS)이 보여주고·고친다 — 두 곳이 같은 목록을 써야 한다
DB_COLUMNS = [c for c in dict.fromkeys(c for cs in INDICATOR_COLUMNS.values() for c in cs) if c not in DERIVED_COLUMNS]

def _hint(columns):
    """{"교육": {"학원": …, "학교": …}, …} → "교육: 학원/학교, …". 프롬프트와 도구 설명에 싣는 허용 목록 글"""
    return ", ".join(f"{ind}: {'/'.join(subs)}" for ind, subs in columns.items())


# 세부 강조 — 지표 안의 한 가지("학원", "지하철")를 그 지표의 칸 하나로 잇는다. 유일한 정의처.
# 값은 values 에 있는 칸 이름이어야 한다 — INDICATOR_COLUMNS 의 칸이거나 load_regions() 가 만드는 파생 칸("종류:분류_밀도").
# 글자 하나 틀리면 apply_focus 가 조용히 무시한다. 분류 이름은 DB 의 원본 표기 그대로다(2026-10-01 확인).
# 키는 사용자가 말할 법한 낱말이다. 새 세부를 열 땐 여기 한 줄 — 채팅 도구의 고를 수 있는 목록이 여기서 만들어진다
FOCUS_COLUMNS = {
    "교육": {"학원": "학원_밀도", "학교": "학교_밀도_2023",
            "유치원": "학교:유치원_밀도", "초등학교": "학교:초등학교_밀도",
            "중학교": "학교:중학교_밀도", "고등학교": "학교:고등학교_밀도",
            "보습학원": "학원:입시.검정 및 보습_밀도", "독서실": "학원:독서실_밀도"},
    "교통": {"지하철": "지하철역_밀도", "버스": "버스정류장_밀도"},
    "안전": {"CCTV": "CCTV_밀도", "경찰": "경찰관서_밀도"},
    "상권": {"시장": "점포:전통시장_밀도", "가게": "점포_밀도",       # '시장' 은 전통시장 265곳만. 대형점포_밀도 는 백화점·마트까지 든 점포 표 전체다
            "대형점포": "대형점포_밀도", "대형마트": "점포:대형마트_밀도",
            "백화점": "점포:백화점_밀도", "쇼핑몰": "점포:복합쇼핑몰_밀도"},
    "문화": {"도서관": "도서관_밀도", "문화시설": "문화시설_밀도",
            "공연장": "문화시설:공연시설_밀도", "전시관": "문화시설:전시시설_밀도"},
    "의료": {"병원": "의료기관:병원_밀도", "의원": "의료기관:의원_밀도"},
    "녹지": {"큰공원": "공원:근린공원_밀도", "놀이터": "공원:어린이공원_밀도"},
}

# 채팅 도구(rerank_by_focus) 설명에 싣는 허용 목록 — "교육: 학원/학교/유치원/…, 교통: 지하철/버스, …"
FOCUS_HINT = _hint(FOCUS_COLUMNS)

# 검색 프롬프트(weights.py 규칙 8)가 아는 세부는 처음 열 개로 얼려 둔다 — 세부를 더 여는 것은 채팅에만 반영한다.
# 검색 프롬프트는 모든 검색이 읽고 한 번에 일곱 가지를 시키는 자리라, 목록이 길어지면 넓은 질문에 세부를 찍을 위험이 커진다.
# 여기를 고치면 SUB_HINT 가 달라져 검색 프롬프트 글자가 바뀐다 — 프롬프트를 손볼 때 같이 정한다(이슈 10)
_SEARCH_SUBS = {
    "교육": ("학원", "학교"),
    "교통": ("지하철", "버스"),
    "안전": ("CCTV", "경찰"),
    "상권": ("시장", "가게"),
    "문화": ("도서관", "문화시설"),
}
SUB_COLUMNS = {ind: {sub: FOCUS_COLUMNS[ind][sub] for sub in subs} for ind, subs in _SEARCH_SUBS.items()}
SUB_HINT = _hint(SUB_COLUMNS)


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


BIG_PARK_M2 = float("inf")  # 분배 끔(=A). 골든셋 녹지 A 3/4 · B+ 1/4 · C 1/4(2026-09-30, data/golden/README.md).
                            # mix 조정(로드맵 2-7) 뒤 1_000_000 으로 다시 켜서 잰다 — 그래서 분배 코드는 남긴다
SPREAD_KM = 1.5             # + 동 자기 반지름 √(면적/π). 실제 경계로 채점: 진짜 이웃 96% 포착(3.0 은 정밀도 27% 로 너무 넓음)


def _dong_index(names):
    """(구, 동 표기 변형) → names 의 자리. 시설 표의 동 표기(시흥4동)가 master(시흥제4동)와 달라 dong_variants 로 잇는다"""
    index = {}
    for i, name in enumerate(names):
        gu, dong = name.split(" ", 1)
        for v in dong_variants(dong):
            index[(gu, v)] = i
    return index


def build_green_ratio(names, area_m2, parks, coords, cap=1.0):
    """동별 공원 면적 비율 = (그 동 공원 면적 합) ÷ (동 면적). 427개 배열, cap 에서 자른다.

    개수 밀도는 60% 가 어린이공원(평균 1,600㎡)이라 "놀이터 밀도"였다(2026-09-29 실측).
    BIG_PARK_M2 이상 공원(불암산 5.3km² → 중계본동 244%)은 동 면적까지만 자기 동에 넣고,
    넘치는 만큼은 SPREAD_KM 반경 안 이웃에 면적 비례로 나눈다. 이웃이 없으면 초과분은 버린다.
    """
    index = _dong_index(names)

    # 동 중심 좌표를 names 순서의 배열로 (없는 동은 nan → 반경 계산에서 자동 제외)
    lat = np.full(len(names), np.nan)
    lon = np.full(len(names), np.nan)
    for (gu, dong), (la, lo) in coords.items():
        i = index.get((gu, dong.strip()))
        if i is not None:
            lat[i], lon[i] = la, lo

    total = np.zeros(len(names))
    for gu, dong, area, plat, plon in parks:
        i = index.get((gu, (dong or "").strip()))
        if i is None:
            continue
        if area < BIG_PARK_M2 or plat is None or plon is None:
            total[i] += area
            continue
        # 동 안에 다 들어가는 공원(올림픽공원 1.45km²)까지 나누면 그 동이 희석된다 — 넘치는 만큼만 이웃에
        keep = min(area, area_m2[i])
        total[i] += keep
        excess = area - keep
        d = np.sqrt(((lat - plat) * 111.0) ** 2 + ((lon - plon) * 88.0) ** 2)   # km (위도 1도≈111, 경도 1도≈88)
        reach = SPREAD_KM + np.sqrt(area_m2 / 1e6 / np.pi)
        near = np.where((d <= reach) & (np.arange(len(names)) != i))[0]       # 자기 동은 이미 찼다
        if excess > 0 and len(near) > 0:
            total[near] += excess * area_m2[near] / area_m2[near].sum()

    ratio = total / np.maximum(area_m2, 1.0)     # 면적 0 인 동이 있어도 0 으로 나누지 않는다
    return np.minimum(ratio, cap)


def load_regions():
    """427개 동의 이름과, 밀도 칸·개수 칸을 꺼낸다.

    한 번의 쿼리로 둘을 같이 가져온다 — 순위에 쓸 밀도와, 화면 근거로 쓸 개수다.
    돌려주는 것 셋: names · values(밀도, numpy) · counts(개수, 동네별 dict)
    """
    rows = region_densities(DB_COLUMNS + COUNT_COLUMNS + ["면적_m2", "면적_km2", "행정동ID_8자리"])   # 면적은 분모, 코드는 학교 표와 잇는 열쇠
    names = [f"{r['구']} {r['행정동명']}" for r in rows]

    def column(key):
        """rows 의 한 칸을 numpy 배열로. 빈 값은 0"""
        return np.array([r[key] or 0 for r in rows], dtype="float64")

    # 밀도는 계산용이라 numpy 배열로. 계산된 칸(DERIVED_COLUMNS)은 표에 없어 아래에서 만든다
    values = {c: column(c) for c in DB_COLUMNS}

    coords = dong_coords() if np.isfinite(BIG_PARK_M2) else {}     # 큰 공원 분배가 꺼져 있으면(inf) 좌표를 안 쓴다 — 안 읽는다
    values["공원면적비율"] = build_green_ratio(names, column("면적_m2"), park_areas(), coords)

    # 학교는 2023년 학교 표로 센다(행정동 코드로 잇는다). master 의 학교_수·학교_밀도 는 10년치가 섞여 약 10배다.
    # 한 코드를 여러 줄이 쓰면(신설동·용두동이 11060810 — 2009년 용신동 통합, 경계 데이터가 없어 못 가른다) 줄 수로 나눈다
    area_km2 = np.maximum(column("면적_km2"), 0.01)
    rows_of_code = {}
    for i, r in enumerate(rows):
        rows_of_code.setdefault(r["행정동ID_8자리"], []).append(i)

    def add_by_code(arr, code, n):
        """코드 code 의 개수 n 을 그 코드를 쓰는 줄들에 나눠 더한다"""
        for i in rows_of_code.get(code, ()):
            arr[i] += n / len(rows_of_code[code])

    # 학교급별로 한 번만 읽는다. 동의 전체 학교 수는 그 합이고, 학교급 하나하나는 세부 강조용 파생 칸이 된다
    school_n = np.zeros(len(names))
    for code, level, n in school_level_counts():
        add_by_code(school_n, code, n)
        add_by_code(values.setdefault(f"학교:{level}_밀도", np.zeros(len(names))), code, n)
    values["학교_밀도_2023"] = school_n / area_km2

    # 분류별 파생 칸 — "학원:입시.검정 및 보습_밀도" 처럼 "종류:분류_밀도" 이름으로. 세부 강조(FOCUS_COLUMNS)가 가리킨다.
    # ':' 가 든 이름은 master 칸과 절대 안 겹치고, 아래에서 파생 칸만 골라 면적으로 나누는 표시가 된다.
    # INDICATOR_COLUMNS 에 없으니 관리자 화면(REGION_FIELDS)엔 안 들어간다 — build_column_scores 가 백분위로 만든다
    index = _dong_index(names)
    for kind in ("학원", "의료기관", "문화시설", "점포", "공원"):
        for gu, dong, cat, n in category_counts(kind):
            i = index.get((gu, dong.strip()))
            if i is not None:
                values.setdefault(f"{kind}:{cat}_밀도", np.zeros(len(names)))[i] += n
    for col in values:
        if ":" in col:
            values[col] /= area_km2

    # 개수는 화면에 그대로 보여줄 값이라 {동네이름: {칸: 값}}.
    # 학교_수 는 2023년 값으로 덮는다 — 웹 typespot.py 카드가 이 키를 읽는다
    counts = {
        name: {**{c: row[c] for c in COUNT_COLUMNS}, "학교_수": round(n)}
        for name, row, n in zip(names, rows, school_n)
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


def build_column_scores(values):
    """칸 하나하나의 백분위. {칸 이름: 427개 배열}. build_scores() 의 재료이자, 세부 강조가 지표 평균 대신 꺼내 쓰는 값.

    invert 는 지표 기준(INDICATOR_INVERT)을 따른다 — 시세처럼 낮을수록 좋은 지표의 칸도 같이 뒤집힌다
    """
    scores = {}
    for indicator, cols in INDICATOR_COLUMNS.items():
        invert = indicator in INDICATOR_INVERT
        for c in cols:
            scores[c] = to_percentile(values[c], invert=invert)
    # 파생 칸(INDICATOR_COLUMNS 밖, 이름에 ':')도 세부로 쓸 수 있게 전부 백분위로
    for c in values:
        if c not in scores:
            scores[c] = to_percentile(values[c])
    return scores


def build_scores(column_scores):
    """칸별 백분위를 7개 지표 점수(0~100)로 묶는다. 칸이 여러 개인 지표는 평균낸다.
    (안전 = CCTV 백분위와 경찰관서 백분위의 평균). 백분위 계산은 build_column_scores() 한 곳에서만 한다
    """
    return {
        indicator: sum(column_scores[c] for c in cols) / len(cols)
        for indicator, cols in INDICATOR_COLUMNS.items()
    }


def apply_focus(scores, column_scores, focus):
    """세부 강조를 반영한 지표 점수. 새 딕셔너리를 돌려준다 — 원본 scores 는 안 건드린다.

    focus 예: {"교육": "학원"} → 교육 점수 = (학교·학원 평균) 대신 학원_밀도 의 백분위.
    준비물(get_ready)은 모든 요청이 같이 쓰므로, 여기서 복사본을 만들지 않으면
    한 요청의 세부 강조가 다음 요청까지 남는다
    """
    out = dict(scores)
    for indicator, sub in (focus or {}).items():
        col = FOCUS_COLUMNS.get(indicator, {}).get(sub)
        if col in column_scores:
            out[indicator] = column_scores[col]
    return out


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
    names, values, _ = load_regions()
    scores = build_scores(build_column_scores(values))
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