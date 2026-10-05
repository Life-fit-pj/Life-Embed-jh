"""행정동 표를 다룬다. master_dataset_v3 · 시설 6표(학교 포함) · 세대원수 · 시세.

칸 이름을 밖에서 받는 함수가 셋이라(region_densities·region_one·column_percentile)
속성이 아니라 .c["이름"] 으로 간다 — 교안 5-1 이론 2.
"""

from sqlalchemy import Float, cast, func, select, tuple_, update

from app.domain.dong import dong_variants
from app.models.region import (
    t_master_dataset_v3 as master,
    t_행정동별_세대원수_전처리 as 세대원수,
    t_시세_지역별_전처리 as 시세,
    t_문화시설_개별_행정동매칭 as 문화시설,
    t_의료_전처리 as 의료,
    t_학원_전처리 as 학원,
    t_서울시_25개구_도시공원정보_통합_행정동포함 as 공원,
    t_대규모점포_전통시장_통합_최종 as 점포,
    t_학교_행정동매칭 as 학교,
)


#             (Table,   구 칸,   동 칸,     시설명 칸,    분류 칸)
FACILITY_TABLES = {
    "문화시설": (문화시설, "자치구", "행정동명", "문화시설명", "문화분류"),
    "의료기관": (의료,     "자치구", "행정동",   "시설명",     "기관구분"),
    "학원":     (학원,     "자치구", "행정동",   "학원명",     "분야명"),
    "공원":     (공원,     "구",     "행정동",   "공원명",     "공원구분"),
    "점포":     (점포,     "구",     "행정동",   "이름",       "시설유형"),
    # 2023년 학교 표. 분류 칸이 학교급(유치원·초등학교·중학교·고등학교…)이다.
    # 표를 등록한 것만으로는 채팅이 유치원에 답하지 못했다 — Claude 가 종류를 '학원' 으로 골랐다.
    # Claude 에게 보이는 이름은 tools.py 의 _KIND_LABELS 가 "학교·유치원" 으로 바꿔 보여 준다(2026-10-01)
    "학교":     (학교,     "구",     "행정동",   "학교",       "학교급"),
}

# 슬라이더 7개 지표에 안 들어간 칸들. 화면이 "그 밖의 여건" 으로 보여준다
EXTRA_COLUMNS = (
    "쓰레기통_밀도", "거주안정성_점수", "이동률_퍼센트",
    "지하철역_수", "경찰관서_수", "소방관서_수",
    "소음_주간_구", "소음_야간_구", "초미세먼지_구", "재해위험지구_구",
    # ↓ /facilities 의 extras 로 나가는 원본 개수. 프론트(reason.js)·chat_service 는 특정 키만
    #   골라 읽으므로 칸이 늘어도 안 깨진다 — schemas/regions.py:17 이 그래서 dict 다.
    #   학교_수 는 뺐다 — master 의 값은 10년치(쌍문제4동 129)라 틀리고, 맞는 값(2023년 10)은
    #   recommend.load_regions() 의 counts 로 /recommend 가 내보낸다(2026-09-30)
    "공원_수", "CCTV_수", "버스정류장_수", "대형점포_수", "점포_수",
    "의료기관_수", "학원_수", "문화시설_수", "도서관_수",
)


# master_dataset_v3 엔 중앙값만 있다. 표본 수·신뢰등급·분위는 이 표에만 있다
PRICE_COLUMNS = (
    "거래건수", "신뢰등급", "출처", "면적_중앙값",
    "매매가", "매매가_25", "매매가_75",
    "보증금", "보증금_25", "보증금_75", "월임대료",
)


def region_densities(db, columns):
    stmt = select(master.c["구"], master.c["행정동명"], *[master.c[c] for c in columns])
    return [dict(r) for r in db.execute(stmt).mappings()]


def region_one(db, gu, dong, columns):
    stmt = (
        select(master.c["구"], master.c["행정동명"], *[master.c[c] for c in columns])
        .where(*_in_dong(master, "구", "행정동명", gu, dong))
    )
    row = db.execute(stmt).mappings().first()
    return dict(row) if row else None


def _in_dong(t, gu_col, dong_col, gu, dong):
    """(구, 동) 한 곳을 찾는 WHERE. 표기 변형(dong_variants)과 공백까지 여기서 흡수한다 — 동을 찾는 함수는 전부 이걸 쓴다"""
    return (func.trim(t.c[gu_col]) == gu.strip(),
            func.trim(t.c[dong_col]).in_(dong_variants(dong)))


def _in_places(t, gu_col, dong_col, places):
    """(구, 동) 여러 곳을 한 번에 찾는 WHERE 와, 표에 적힌 표기를 요청한 (구, 동)으로 되돌리는 사전.

    _in_dong() 의 여러 곳 판이다 — 표기 변형과 공백을 같은 규칙으로 흡수한다.
    표마다 동 이름 표기가 달라서, 찾은 줄이 어느 요청의 것인지는 이 사전으로 되짚는다
    """
    back = {(gu.strip(), variant): (gu, dong) for gu, dong in places for variant in dong_variants(dong)}
    return tuple_(func.trim(t.c[gu_col]), func.trim(t.c[dong_col])).in_(list(back)), back


def region_rows(db, places, columns):
    """master 에서 여러 동네의 칸을 한 번에. {(구, 동): {칸: 값}} — region_one() 의 여러 곳 판이다"""
    where, back = _in_places(master, "구", "행정동명", places)
    stmt = select(func.trim(master.c["구"]), func.trim(master.c["행정동명"]), *[master.c[c] for c in columns]).where(where)
    return {back[(gu, dong)]: dict(zip(columns, values)) for gu, dong, *values in db.execute(stmt)}


def facilities(db, gu, dong, kind=None, limit=10):
    targets = FACILITY_TABLES if kind is None else {kind: FACILITY_TABLES[kind]}
    result = {}
    for label, (t, gu_col, dong_col, name_col, cat_col) in targets.items():
        stmt = (
            select(t.c[name_col].label("name"), t.c[cat_col].label("category"))
            .where(*_in_dong(t, gu_col, dong_col, gu, dong))
            .limit(limit)
        )
        rows = [dict(r) for r in db.execute(stmt).mappings()]
        if rows:
            result[label] = rows
    return result


def park_areas(db):
    """공원 하나하나의 (구, 행정동, 면적㎡, 위도, 경도). 녹지 점수(공원 면적 비율)의 재료다.

    공원면적 칸이 Text 라 숫자로 바꿔야 한다. 두 줄이 '34,050.70' 처럼 쉼표를 품고 있어서
    (2026-09-29 확인) 쉼표를 떼고 cast 한다 — 안 떼면 그 두 줄이 조용히 빠진다.
    1,917줄을 한 번에 가져온다 — 동마다 쿼리하면 427번이 된다(N+1).
    """
    area = cast(func.replace(공원.c["공원면적"], ",", ""), Float)
    stmt = select(공원.c["구"], 공원.c["행정동"], area, 공원.c["위도"], 공원.c["경도"]).where(공원.c["공원면적"].isnot(None))
    return [(gu, dong, float(a), lat, lon) for gu, dong, a, lat, lon in db.execute(stmt).all() if a is not None]


def dong_coords(db):
    """행정동 중심 좌표. {(구, 동): (위도, 경도)}. 시세 표가 행정동별로 들고 있어 거기서 꺼낸다."""
    stmt = (
        select(시세.c["자치구명"], 시세.c["지역명"], 시세.c["위도"], 시세.c["경도"])
        .where(시세.c["지역종류"] == "행정동")
        .distinct()
    )
    return {(gu, dong): (lat, lon) for gu, dong, lat, lon in db.execute(stmt).all() if lat and lon}


def school_level_counts(db):
    """행정동 코드·학교급별 학교 수(2023년). [(행정동코드, 학교급, n)]. 교육 점수와 화면 개수, 학교급 파생 칸의 재료다.

    학교_행정동매칭 = 원본 2023년 학교 2,144개에 최근접 참조점으로 행정동을 붙인 표(2026-09-30).
    master 의 학교_수·학교_밀도 는 10년치가 섞여 약 10배다. 행정동코드가 빈 줄은 어느 동에도 못 넣으니 뺀다.
    동의 전체 학교 수는 따로 세지 않는다 — 학교급별 값을 더하면 된다(같은 표를 두 번 읽지 않는다)
    """
    stmt = (
        select(학교.c["행정동코드"], 학교.c["학교급"], func.count())
        .where(학교.c["행정동코드"].isnot(None), 학교.c["행정동코드"] != "")
        .group_by(학교.c["행정동코드"], 학교.c["학교급"])
    )
    return [(code, level, int(n)) for code, level, n in db.execute(stmt).all()]


def column_percentile(db, column, value, invert=False):
    if value is None:
        return None

    col = master.c[column]
    total, below, same = db.execute(
        select(func.count(),
               func.count().filter(col < value),
               func.count().filter(col == value))
        .select_from(master)
    ).one()

    rank = below + (same - 1) / 2        # 동점 평균 순위 — recommend.py 와 같은 규칙
    pct = round(rank / (total - 1) * 100)
    return 100 - pct if invert else pct


def update_region(db, gu, dong, patch, allowed):
    """patch 중 allowed 에 있는 칸만 고친다. 고친 칸 수를 돌려준다"""
    values = {master.c[name]: patch[name] for name in patch if name in allowed}
    if not values:
        return 0

    db.execute(
        update(master)
        .where(*_in_dong(master, "구", "행정동명", gu, dong))
        .values(values)
    )
    db.commit()
    return len(values)
  

# ── 행정동 관리자 조회 ──────────────────────────────

def region_list(db):
    """master_dataset_v3 의 구, 행정동명 427개"""
    stmt = (
        select(master.c["구"], master.c["행정동명"])
        .order_by(master.c["구"], master.c["행정동명"])
    )
    return [dict(r) for r in db.execute(stmt).mappings()]


# ── 시설 집계 ──────────────────────────────────

def facility_counts(db, gu, dong):
    """행정동 하나의 시설 종류별 개수를 센다."""
    counts = {}

    for label, (t, gu_col, dong_col, _, _) in FACILITY_TABLES.items():
        n = db.execute(
            select(func.count())
            .select_from(t)
            .where(*_in_dong(t, gu_col, dong_col, gu, dong))
        ).scalar()
        if n:
            counts[label] = n

    return counts


def facility_categories(db, gu, dong, kind="학원", top=8):
    """시설 종류 하나의 분류별 개수를 전부 센다.

    facilities() 는 표본만 가져오므로 그걸로 분류를 세면 숫자가 왜곡된다.
    "영어학원 몇 곳" 같은 질문에 답하려면 전체를 세야 한다
    """
    if kind not in FACILITY_TABLES:
        return []

    t, gu_col, dong_col, _, cat_col = FACILITY_TABLES[kind]
    cat = t.c[cat_col]
    n = func.count().label("n")

    stmt = (
        select(cat.label("category"), n)
        .where(*_in_dong(t, gu_col, dong_col, gu, dong),
               cat.isnot(None), func.trim(cat) != "")
        .group_by(cat)
        .order_by(n.desc())
        .limit(top)
    )
    return [dict(r) for r in db.execute(stmt).mappings()]


def facility_breakdown(db, places):
    """여러 동네의 시설을 종류 · 분류별로 센다. {(구, 동): {종류: {분류: 개수}}} — 분류가 빈 줄은 None 아래 모인다.

    facility_counts() · facility_categories() 를 동네마다 · 종류마다 부르면 5곳에 60번이다 — 표마다 한 번, 여섯 번에 센다.
    종류의 전체 개수는 분류별 값을 더하면 된다. 한 곳도 없는 종류는 그 동네의 사전에 안 들어간다
    """
    out = {place: {} for place in places}
    for label, (t, gu_col, dong_col, _, cat_col) in FACILITY_TABLES.items():
        where, back = _in_places(t, gu_col, dong_col, places)
        gu, dong, cat = func.trim(t.c[gu_col]), func.trim(t.c[dong_col]), t.c[cat_col]
        for g, d, c, n in db.execute(select(gu, dong, cat, func.count()).where(where).group_by(gu, dong, cat)):
            key = c if c is not None and c.strip() else None
            by_cat = out[back[(g, d)]].setdefault(label, {})
            by_cat[key] = by_cat.get(key, 0) + int(n)
    return out


def category_counts(db, kind):
    """시설 종류 하나의 (구, 동, 분류, 개수) 전부. 세부 강조의 파생 칸 재료다.

    facility_categories() 는 동 하나만 세고, 이건 427동을 한 번에 센다 — 동마다 부르면 427번 쿼리(N+1)
    """
    t, gu_col, dong_col, _, cat_col = FACILITY_TABLES[kind]
    stmt = (
        select(t.c[gu_col], t.c[dong_col], t.c[cat_col], func.count())
        .group_by(t.c[gu_col], t.c[dong_col], t.c[cat_col])
    )
    return [(gu, dong, cat, int(n)) for gu, dong, cat, n in db.execute(stmt).all() if gu and dong and cat]


# ── 생활 여건 ──────────────────────────────────


def region_extras(db, gu, dong):
    """슬라이더 7개 지표에 안 들어간 생활 여건 정보를 꺼낸다.

    구 단위 값(소음·미세먼지 등)도 함께 돌려주지만,
    화면에 표시할 때 반드시 "OO구 평균" 임을 밝혀야 한다.
    행정동 값인 척하면 25개 값으로 수렴하는 문제를 숨기게 된다
    """
    stmt = (
        select(*[master.c[c] for c in EXTRA_COLUMNS])
        .where(*_in_dong(master, "구", "행정동명", gu, dong))
    )
    first = db.execute(stmt).mappings().first()
    if first is None:
        return {}

    row = dict(first)

    # 세대원수는 별도 표에 있다.
    # ★ "1인_비율" 은 숫자로 시작해서 파이썬 속성이 될 수 없다 — .c["이름"] 이라야 한다(5-1)
    hh = db.execute(
        select(세대원수.c["평균가구원수"], 세대원수.c["1인_비율"])
        .where(*_in_dong(세대원수, "구", "행정동명", gu, dong))
    ).mappings().first()
    if hh:
        row.update(hh)

    # 밀도 원값(12.3개/km²)은 사용자에게 감이 오지 않는다.
    # "상위 12%" 처럼 다른 동네와 비교한 위치로 바꾼다.
    #
    # 화면에는 "보행 편의" 로 표시한다 —
    # 쓰레기통 개수로 "깨끗하다" 를 말하면 측정하지 않은 것을 주장하게 된다.
    # 우리가 아는 건 "버릴 곳을 찾기 쉽다" 까지다
    #
    # ★ db 를 넘긴다. 세션을 새로 열지 않는다 — 한 요청이 한 세션을 쓴다
    row["보행편의_백분위"] = column_percentile(db, "쓰레기통_밀도", row.get("쓰레기통_밀도"))

    return row


# ── 시세 ──────────────────────────────────────


def region_price_detail(db, gu, dong, bldg, deal):
    """시세_지역별_전처리 에서 master_dataset_v3 엔 없는 상세 정보를 꺼낸다.

    ★ 이 표만 칸 이름이 다르다 — 구가 아니라 자치구명, 행정동명이 아니라 지역명이다.
      _in_dong() 이 칸 이름을 인자로 받는 덕에 그대로 쓸 수 있다
    """
    stmt = (
        select(*[시세.c[c] for c in PRICE_COLUMNS])
        .where(*_in_dong(시세, "자치구명", "지역명", gu, dong),
               시세.c["건물용도"] == bldg,
               시세.c["거래유형"] == deal)
    )
    row = db.execute(stmt).mappings().first()
    return dict(row) if row else None


def region_price_details(db, gu, dong):
    """동네 하나의 시세 상세 전부. {(건물용도, 거래유형): {칸: 값}}.

    region_price_detail() 을 조합마다 부르면 12번이다(N+1) — 한 번에 가져와 부르는 쪽이 골라 쓴다.
    같은 조합이 두 줄이면 먼저 온 것을 쓴다(region_price_detail 의 .first() 와 같은 규칙)
    """
    stmt = (
        select(시세.c["건물용도"], 시세.c["거래유형"], *[시세.c[c] for c in PRICE_COLUMNS])
        .where(*_in_dong(시세, "자치구명", "지역명", gu, dong))
    )
    details = {}
    for r in db.execute(stmt).mappings():
        details.setdefault((r["건물용도"], r["거래유형"]), {c: r[c] for c in PRICE_COLUMNS})
    return details


def region_price_details_many(db, places):
    """여러 동네의 시세 상세. {(구, 동): {(건물용도, 거래유형): {칸: 값}}} — region_price_details() 의 여러 곳 판이다"""
    where, back = _in_places(시세, "자치구명", "지역명", places)
    stmt = select(func.trim(시세.c["자치구명"]), func.trim(시세.c["지역명"]), 시세.c["건물용도"], 시세.c["거래유형"],
                  *[시세.c[c] for c in PRICE_COLUMNS]).where(where)
    out = {place: {} for place in places}
    for gu, dong, bldg, deal, *values in db.execute(stmt):
        out[back[(gu, dong)]].setdefault((bldg, deal), dict(zip(PRICE_COLUMNS, values)))
    return out


def region_bundle(db, places, columns):
    """여러 동네의 시설(종류 · 분류별 개수) · master 의 칸 · 시세 상세를 한 세션에서 읽는다. 채팅의 재료다.

    동네마다 따로 읽으면 5곳에 83번 왕복이다(2026-10-05 실측 4.4초). 표마다 한 번씩 여덟 번에 끝낸다
    """
    if not places:
        return {"facilities": {}, "rows": {}, "prices": {}}
    return {
        "facilities": facility_breakdown(db, places),
        "rows": region_rows(db, places, columns),
        "prices": region_price_details_many(db, places),
    }


# ── 이름 목록 ──────────────────────────────────

def gu_names(db):
    """자치구 이름 전부 (중복 없이)"""
    return [gu for (gu,) in db.execute(select(master.c["구"]).distinct())]


def dong_names(db):
    """행정동 이름 전부 (중복 없이)"""
    return [dong for (dong,) in db.execute(select(master.c["행정동명"]).distinct())]


# ── 집계 (관리자 대시보드가 쓴다) ──────────────────────

def region_count(db):
    """행정동이 몇 개 있나. 427 이 정상이다."""
    return db.execute(select(func.count()).select_from(master)).scalar()


def gu_count(db):
    """자치구가 몇 개 있나. 25 가 정상이다."""
    return db.execute(select(func.count(master.c["구"].distinct()))).scalar()


def region_gu_counts(db):
    """자치구별 행정동 개수. (자치구, 개수) 목록.

    ★ 여기만 딕셔너리가 아니라 튜플이다 — 옛 query() 자리라서 그렇다(5-8 ⓐ)
    """
    total = func.count()
    stmt = (
        select(master.c["구"], total)
        .group_by(master.c["구"])
        .order_by(total.desc(), master.c["구"])
    )
    return [tuple(r) for r in db.execute(stmt)]



