""" SQLite 조회 기능을 여기 모아둔다.

    pipeline/ 은 DB 를 만들고 채우는 역할,
    이 파일은 이미 만들어진 표에서 데이터를 꺼내는 역할만 한다.

    나중에 다른 DB 로 바꾸더라도 이 파일만 고치면 되도록 분리해 둔다.
"""

import sqlite3
import threading

from app.core.config import DB_PATH, INDICATORS
from app.domain.dong import dong_variants
# 연결을 스레드마다 따로 만든다.
#
# SQLite 연결 하나를 여러 스레드가 동시에 쓰면 내부 상태가 엉켜
# "bad parameter or other API misuse" 가 난다.
# FastAPI 는 요청마다 다른 스레드에서 처리하므로 이 문제가 드러난다.
# threading.local() 은 스레드별로 따로 보관되는 저장소다
_local = threading.local()


def get_con():
    """이 스레드 전용 연결을 돌려준다. 없으면 만든다."""
    if not hasattr(_local, "con"):
        _local.con = sqlite3.connect(DB_PATH, check_same_thread=False)
    return _local.con


def query(sql, params=()):
    """여러 줄을 튜플 목록으로 돌려준다."""
    return get_con().execute(sql, params).fetchall()


def one(sql, params=()):
    """한 줄만 돌려준다. 없으면 None."""
    return get_con().execute(sql, params).fetchone()


def dicts(sql, params=()):
    """칸 이름이 붙은 딕셔너리 목록으로 돌려준다.

    query 는 ('종로구', '청운효자동', 0.5) 처럼 튜플이라
    r[0], r[1] 처럼 위치로 꺼내야 한다.
    칸 순서가 바뀌면 조용히 잘못된 값을 읽게 된다.

    dicts 는 r["행정동명"] 처럼 이름으로 꺼낼 수 있다.
    특히 Claude 에게 데이터를 넘길 때는 칸 이름이 있어야
    LLM 이 무엇을 보고 있는지 알 수 있다.
    """
    cur = get_con().execute(sql, params)
    columns = [c[0] for c in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


# ── 프로젝트 전용 조회 함수 ─────────────────────────────


def member_chunks():
    """회원 청크와 벡터를 전부 꺼낸다. (07번에서 쓰던 것)"""
    return dicts(
        "SELECT customer_id, category, text, vector FROM member_chunk"
    )


def member_weights(customer_ids):
    """회원들의 가중치 7개를 꺼낸다.

    IN (?, ?, ?) 형태를 사람 수만큼 만들어야 하므로
    물음표 개수를 동적으로 맞춘다.
    """
    if not customer_ids:
        return []
    
    marks = ", ".join("?" * len(customer_ids))
    cols = ", ".join(INDICATORS)

    return dicts(
        f"SELECT customer_id, {cols} FROM user_preferences "
        f"WHERE customer_id IN ({marks})",
        tuple(customer_ids),
    )

def region_densities(columns):
    """행정동별 밀도 칸들을 꺼낸다. (08번에서 쓰던 것)

    칸 이름을 밖에서 받는 이유 —
    어떤 밀도 칸을 쓸지는 08번의 INDICATOR_COLUMNS 가 정한다.
    조회 계층은 "무엇을 쓸지" 를 정하지 않고 "꺼내주기만" 한다
    """
    quoted = ", ".join(f'"{c}"' for c in columns)
    return dicts(f'SELECT 구, 행정동명, {quoted} FROM master_dataset_v3')


def kb_chunks():
    """지식베이스 청크와 벡터를 전부 꺼낸다. (09번에서 쓸 것)"""
    return dicts(
        "SELECT chunk_id, uuid, district, category, text, vector FROM kb_chunk"
    )


def customer_list():
    """회원 목록. 화면 왼쪽 목록에 쓴다. 목록엔 다 필요 없으니 몇 칸만"""
    return dicts("SELECT customer_id, name, age, city, city_dong FROM customers ORDER BY customer_id")


def customer_one(customer_id):
    """customers 표에서 회원 한 명. 없으면 None"""
    rows = dicts("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
    return rows[0] if rows else None


def customer_preferences(customer_id):
    """user_preferences 표에서 한 명의 가중치 7개. 없으면 None"""
    cols = ", ".join(INDICATORS)
    rows = dicts(
        f"SELECT {cols} FROM user_preferences WHERE customer_id = ?",
        (customer_id,),
    )
    return rows[0] if rows else None


def customer_persona(customer_id):
    """member_chunk 에서 회원 한 명의 페르소나 9칸을 {category: text} 로 되돌린다"""
    rows = dicts(
        "SELECT category, text FROM member_chunk WHERE customer_id = ?",
        (customer_id,),
    )
    return {r["category"]: r["text"] for r in rows}


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


def dong_variants(dong):
    """행정동 이름의 표기 변형을 만든다.

    통계청은 '고덕제1동', 일상 표기는 '고덕1동' 이다.
    전처리 파일마다 어느 쪽을 쓰는지 다르므로 둘 다 시도한다.

    단순 치환은 위험하다.
      '홍제제1동' → '홍제1동'  (정상)
      '홍제1동'   → '홍1동'    (오류)
    그래서 '제' 를 없애는 방향으로만 만들고, 반대는 만들지 않는다
    """
    base = str(dong).strip()
    out = {base}
    
    # '고덕제1동' → '고덕1동'  (맨 뒤의 '제N동' 만 건드린다)
    out.add(re.sub(r"제(\d+)동$", r"\1동", base))
    
    # '고덕1동' → '고덕제1동'  (반대 방향도 준비)
    out.add(re.sub(r"(?<!제)(\d+)동$", r"제\1동", base)) 
    
    return list(out)
    
    
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
    row["보행편의_백분위"] = to_percentile("쓰레기통_밀도", row.get("쓰레기통_밀도"))

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
    
    
def to_percentile(column, value, invert=False):
    """어떤 값이 427개 동 중 백분위 몇인지 계산한다.

    밀도 원값(12.3개/km²)은 사용자에게 의미가 없다.
    "상위 30%" 처럼 다른 동네와 비교한 위치로 바꿔야 읽힌다
    invert=True 면 "낮을수록 높은 점수"로 뒤집는다 (시세처럼 작을수록 좋은 지표용)
    """
    if value is None:
        return None

    total = one('SELECT COUNT(*) FROM master_dataset_v3')[0]
    below = one(
        f'SELECT COUNT(*) FROM master_dataset_v3 WHERE "{column}" <= ?',
        (value,),
    )[0]
    pct = round(below / total * 100)

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


## 캐시를 버리는 코드

def _run_update(table, where_sql, where_params, patch, allowed):
    """patch 중 allowed(화이트리스트)에 있는 칸만 골라 UPDATE 한다.

    화이트리스트 밖 칸은 조용히 버린다 — SQL 주입 방지 (5-4)
    """
    fields = [name for name in patch if name in allowed]
    if not fields:
        return 0

    sets = ", ".join(f'"{name}" = ?' for name in fields)
    values = [patch[name] for name in fields]

    get_con().execute(
        f'UPDATE "{table}" SET {sets} WHERE {where_sql}',
        (*values, *where_params),
    )
    get_con().commit()
    return len(fields)


def update_customer(customer_id, patch, allowed):
    return _run_update("customers", "customer_id = ?", (customer_id,), patch, allowed)


def update_preferences(customer_id, patch, allowed):
    return _run_update("user_preferences", "customer_id = ?", (customer_id,), patch, allowed)


def update_region(gu, dong, patch, allowed):
    """행정동 표기가 갈릴 수 있으니 region_one 과 같은 방식으로 dong_variants 를 쓴다"""
    names = dong_variants(dong)
    marks = ", ".join("?" * len(names))
    where_sql = f'TRIM(구) = ? AND TRIM(행정동명) IN ({marks})'
    return _run_update("master_dataset_v3", where_sql, (gu.strip(), *names), patch, allowed)


if __name__ =="__main__":
    print()
    print("중계1동 학원 분야:")
    for r in facility_categories("노원구", "중계1동", "학원"):
        print(f"   {r['category']:20s} {r['n']}")
    
    print(len(customer_list()))              # 100 이 나와야 함
    print(customer_one("C001"))              # 딕셔너리 하나
    print(customer_preferences("C001"))      # {"녹지": ..., "안전": ..., ...}
    print(customer_persona("C001"))          # 칸 9개짜리 딕셔너리
    print(len(region_list()))                # 427
    print(region_one("강남구", "역삼1동", ["공원_밀도"]))