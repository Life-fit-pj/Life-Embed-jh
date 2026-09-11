"""행정동 표를 다룬다. master_dataset_v3 · 시설 5표 · 세대원수 · 시세.

칸 이름을 밖에서 받는 함수가 셋이라(region_densities·region_one·column_percentile)
속성이 아니라 .c["이름"] 으로 간다 — 교안 5-1 이론 2.
"""

from sqlalchemy import func, select, update

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
)


#             (Table,   구 칸,   동 칸,     시설명 칸,    분류 칸)
FACILITY_TABLES = {
    "문화시설": (문화시설, "자치구", "행정동명", "문화시설명", "문화분류"),
    "의료기관": (의료,     "자치구", "행정동",   "시설명",     "기관구분"),
    "학원":     (학원,     "자치구", "행정동",   "학원명",     "분야명"),
    "공원":     (공원,     "구",     "행정동",   "공원명",     "공원구분"),
    "점포":     (점포,     "구",     "행정동",   "이름",       "시설유형"),
}

# 슬라이더 7개 지표에 안 들어간 칸들. 화면이 "그 밖의 여건" 으로 보여준다
EXTRA_COLUMNS = (
    "쓰레기통_밀도", "거주안정성_점수", "이동률_퍼센트",
    "지하철역_수", "경찰관서_수", "소방관서_수",
    "소음_주간_구", "소음_야간_구", "초미세먼지_구", "재해위험지구_구",
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
        .where(func.trim(master.c["구"]) == gu.strip(),
               func.trim(master.c["행정동명"]).in_(dong_variants(dong)))
    )
    row = db.execute(stmt).mappings().first()
    return dict(row) if row else None


def _in_dong(t, gu_col, dong_col, gu, dong):
    """시설 함수 셋이 똑같이 쓰는 WHERE. 한 곳에 둔다"""
    return (func.trim(t.c[gu_col]) == gu.strip(),
            func.trim(t.c[dong_col]).in_(dong_variants(dong)))


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
        .where(func.trim(master.c["구"]) == gu.strip(),
               func.trim(master.c["행정동명"]).in_(dong_variants(dong)))
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



