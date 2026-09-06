"""행정동 표를 다루는 SQL. 지표 · 시설 · 백분위 · 시세."""

from app.core.db import dicts, one            # 실행기는 core 에서 가져온다
from app.domain.dong import dong_variants
from app.tables.members import _run_update    # 공용 쓰기 헬퍼. members 에 있다


# ── 프로젝트 전용 조회 함수 ─────────────────────────────

def region_densities(columns):
    """행정동별 밀도 칸들을 꺼낸다. (08번에서 쓰던 것)

    칸 이름을 밖에서 받는 이유 —
    어떤 밀도 칸을 쓸지는 08번의 INDICATOR_COLUMNS 가 정한다.
    조회 계층은 "무엇을 쓸지" 를 정하지 않고 "꺼내주기만" 한다
    """
    quoted = ", ".join(f'"{c}"' for c in columns)
    return dicts(f'SELECT 구, 행정동명, {quoted} FROM master_dataset_v3')


# ── 행정동 관리자 조회 (app/features/admin.py 가 쓴다) ──────────────

def region_list():
    """master_dataset_v3 의 구, 행정동명 427개"""
    return dicts("SELECT 구, 행정동명 FROM master_dataset_v3 ORDER BY 구, 행정동명")


def region_one(gu, dong, columns):
    """행정동 하나의 지정한 칸들만 꺼낸다"""
    names = dong_variants(dong)
    marks = ", ".join("?" * len(names))
    quoted = ", ".join(f'"{c}"' for c in columns)

    rows = dicts(
        f'SELECT 구, 행정동명, {quoted} FROM master_dataset_v3 '
        f'WHERE TRIM(구) = ? AND TRIM(행정동명) IN ({marks})',
        (gu.strip(), *names),
    )
    return rows[0] if rows else None


# ── 시설 조회 ──────────────────────────────────
# 전처리 파일마다 칸 이름이 제각각이라 여기서 한 번에 정리한다.
#   (표 이름, 구 칸, 동 칸, 시설명 칸, 분류 칸)
FACILITY_TABLES = {
    "문화시설": ("문화시설_개별_행정동매칭", "자치구", "행정동명", "문화시설명", "문화분류"),
    "의료기관": ("의료_전처리", "자치구", "행정동", "시설명", "기관구분"),
    "학원":     ("학원_전처리", "자치구", "행정동", "학원명", "분야명"),
    "공원":     ("서울시_25개구_도시공원정보_통합_행정동포함", "구", "행정동", "공원명", "공원구분"),
    "점포":     ("대규모점포_전통시장_통합_최종", "구", "행정동", "이름", "시설유형"),
}


def facilities(gu, dong, kind=None, limit=10):
    """행정동 하나의 시설 목록을 꺼낸다.

    kind 를 주면 그 종류만, 안 주면 전부 돌려준다.
    돌려주는 모양: {"문화시설": [{"name":..., "category":...}, ...], ...}
    """
    targets = FACILITY_TABLES if kind is None else {kind: FACILITY_TABLES[kind]}
    names = dong_variants(dong)
    marks = ", ".join("?" * len(names))
    result = {}
    
    for label, (table, gu_col, dong_col, name_col, cat_col) in targets.items():
        rows = dicts(
            f'SELECT "{name_col}" AS name, "{cat_col}" AS category '
            f'FROM "{table}" '
            f'WHERE TRIM("{gu_col}") = ? AND TRIM("{dong_col}") IN ({marks}) '
            f'LIMIT ?',
            (gu.strip(), *names, limit),
        )
        if rows:
            result[label] = rows
    
    return result


def region_extras(gu, dong):
    """슬라이더 7개 지표에 안 들어간 생활 여건 정보를 꺼낸다.

    구 단위 값(소음·미세먼지 등)도 함께 돌려주지만,
    화면에 표시할 때 반드시 "OO구 평균" 임을 밝혀야 한다.
    행정동 값인 척하면 25개 값으로 수렴하는 문제를 숨기게 된다
    """
    names = dong_variants(dong)
    marks = ", ".join("?" * len(names))

    rows = dicts(
        'SELECT 쓰레기통_밀도, 거주안정성_점수, 이동률_퍼센트, '
        '       지하철역_수, 경찰관서_수, 소방관서_수, '
        '       소음_주간_구, 소음_야간_구, 초미세먼지_구, 재해위험지구_구 '
        'FROM master_dataset_v3 '
        f'WHERE TRIM(구) = ? AND TRIM(행정동명) IN ({marks})',
        (gu.strip(), *names),
    )
    if not rows:
        return {}

    row = rows[0]

    # 세대원수는 별도 표에 있다
    hh = dicts(
        'SELECT 평균가구원수, "1인_비율" '
        'FROM "행정동별_세대원수_전처리" '
        f'WHERE TRIM(구) = ? AND TRIM(행정동명) IN ({marks})',
        (gu.strip(), *names),
    )
    if hh:
        row.update(hh[0])

    # 밀도 원값(12.3개/km²)은 사용자에게 감이 오지 않는다.
    # "상위 12%" 처럼 다른 동네와 비교한 위치로 바꾼다.
    #
    # 화면에는 "보행 편의" 로 표시한다 —
    # 쓰레기통 개수로 "깨끗하다" 를 말하면 측정하지 않은 것을 주장하게 된다.
    # 우리가 아는 건 "버릴 곳을 찾기 쉽다" 까지다
    row["보행편의_백분위"] = column_percentile("쓰레기통_밀도", row.get("쓰레기통_밀도"))

    return row


def facility_counts(gu, dong):
    """행정동 하나의 시설 종류별 개수를 센다."""
    names = dong_variants(dong)
    marks = ", ".join("?" * len(names))    
    counts = {}
    
    for label, (table, gu_col, dong_col, _, _) in FACILITY_TABLES.items():
        n = one(
            f'SELECT COUNT(*) FROM "{table}" '
            f'WHERE TRIM("{gu_col}") = ? AND TRIM("{dong_col}") IN ({marks})',
            (gu.strip(), *names),
        )[0]
        if n:
            counts[label] = n
    return counts


def facility_categories(gu, dong, kind="학원", top=8):
    """시설 종류 하나의 분류별 개수를 전부 센다.

    facilities() 는 표본만 가져오므로 그걸로 분류를 세면 숫자가 왜곡된다.
    "영어학원 몇 곳" 같은 질문에 답하려면 전체를 세야 한다
    """
    if kind not in FACILITY_TABLES:
        return []

    table, gu_col, dong_col, _, cat_col = FACILITY_TABLES[kind]
    names = dong_variants(dong)
    marks = ", ".join("?" * len(names))

    return dicts(
        f'SELECT "{cat_col}" AS category, COUNT(*) AS n '
        f'FROM "{table}" '
        f'WHERE TRIM("{gu_col}") = ? AND TRIM("{dong_col}") IN ({marks}) '
        f'  AND "{cat_col}" IS NOT NULL AND TRIM("{cat_col}") != \'\' '
        f'GROUP BY "{cat_col}" ORDER BY n DESC LIMIT ?',
        (gu.strip(), *names, top),
    )
    
    
def column_percentile(column, value, invert=False):
    """어떤 칸의 값 하나가 427개 동 중 백분위 몇인지 계산한다.

    밀도 원값(12.3개/km²)은 사용자에게 의미가 없다.
    "상위 30%" 처럼 다른 동네와 비교한 위치로 바꿔야 읽힌다
    invert=True 면 "낮을수록 높은 점수"로 뒤집는다 (시세처럼 작을수록 좋은 지표용)

    이름에 "column" 이 붙은 이유 —
    app/engine/recommend.py 의 to_percentile 은 427개를 한꺼번에 받는 배치용이고,
    이쪽은 칸 이름과 값 하나를 받는 단건용이다. 둘 다 필요하지만 이름이 같으면
    어느 쪽을 고쳐야 하는지 헷갈린다 (dong_variants 사본 사고와 같은 구조).
    동점 처리 규칙은 recommend.py 와 반드시 같아야 한다 — 두 값이 화면에서
    똑같이 "상위 N%" 로 나란히 표시되기 때문이다.
    """
    if value is None:
        return None

    total = one('SELECT COUNT(*) FROM master_dataset_v3')[0]
    below = one(
        f'SELECT COUNT(*) FROM master_dataset_v3 WHERE "{column}" < ?',
        (value,),
    )[0]
    same = one(
        f'SELECT COUNT(*) FROM master_dataset_v3 WHERE "{column}" = ?',
        (value,),
    )[0]

    rank = below + (same - 1) / 2        # 동점 그룹의 평균 순위 — recommend.py 와 같은 규칙
    pct = round(rank / (total - 1) * 100)

    return 100 - pct if invert else pct


def region_price_detail(gu, dong, bldg, deal):
    """시세_지역별_전처리 표에서 신뢰등급·거래건수·분포처럼
    master_dataset_v3엔 없는 상세 정보를 꺼낸다.

    master_dataset_v3의 24개 시세 칼럼엔 그 조합의 중앙값만 있다. 표본이 몇 건인지,
    자치구·법정동 단위로 대체된 값인지(출처), 상하위 25~75% 분포가 얼마인지는
    이 표에만 남아 있다.

    동 이름 표기가 갈리는 문제(예: '신당제5동')는 dong_variants()로 그대로 재사용한다.
    """
    names = dong_variants(dong)
    marks = ", ".join("?" * len(names))

    rows = dicts(
        'SELECT 거래건수, 신뢰등급, 출처, 면적_중앙값, '
        '       매매가, 매매가_25, 매매가_75, 보증금, 보증금_25, 보증금_75, 월임대료 '
        'FROM 시세_지역별_전처리 '
        f'WHERE TRIM(자치구명) = ? AND TRIM(지역명) IN ({marks}) '
        '      AND 건물용도 = ? AND 거래유형 = ?',
        (gu.strip(), *names, bldg, deal),
    )
    return rows[0] if rows else None


def update_region(gu, dong, patch, allowed):
    """행정동 표기가 갈릴 수 있으니 region_one 과 같은 방식으로 dong_variants 를 쓴다"""
    names = dong_variants(dong)
    marks = ", ".join("?" * len(names))
    where_sql = f'TRIM(구) = ? AND TRIM(행정동명) IN ({marks})'
    return _run_update("master_dataset_v3", where_sql, (gu.strip(), *names), patch, allowed)


# 자치구 이름 전부 (중복 없이)
def gu_names():
    return [r["구"] for r in dicts("SELECT DISTINCT 구 FROM master_dataset_v3")]


# 행정동 이름 전부 (중복 없이)
def dong_names():
    return [r["행정동명"] for r in dicts("SELECT DISTINCT 행정동명 FROM master_dataset_v3")]
