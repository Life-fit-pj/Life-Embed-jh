"""
SQLite 조회 기능을 여기 모아둔다.

pipeline/ 은 DB 를 만들고 채우는 역할,
이 파일은 이미 만들어진 표에서 데이터를 꺼내는 역할만 한다.

나중에 다른 DB 로 바꾸더라도 이 파일만 고치면 되도록 분리해 둔다.
"""
import re
import sqlite3

from core.config import DB_PATH, INDICATORS

# check_same_thread=False 는 나중에 Flask 서버를 붙일 때 필요하다.
# SQLite 연결은 기본적으로 만든 스레드에서만 쓸 수 있는데,
# 웹 서버는 요청마다 다른 스레드로 도는 경우가 있어서 막힌다

con = sqlite3.connect(DB_PATH, check_same_thread=False)


def query(sql, params=()):
    """여러 줄을 튜플 목록으로 돌려준다."""
    return con.execute(sql, params).fetchall()


def one(sql, params=()):
    """한 줄만 돌려준다. 없으면 None."""
    return con.execute(sql, params).fetchone()


def dicts(sql, params=()):
    """칸 이름이 붙은 딕셔너리 목록으로 돌려준다.

    query 는 ('종로구', '청운효자동', 0.5) 처럼 튜플이라
    r[0], r[1] 처럼 위치로 꺼내야 한다.
    칸 순서가 바뀌면 조용히 잘못된 값을 읽게 된다.

    dicts 는 r["행정동명"] 처럼 이름으로 꺼낼 수 있다.
    특히 Claude 에게 데이터를 넘길 때는 칸 이름이 있어야
    LLM 이 무엇을 보고 있는지 알 수 있다.
    """
    cur = con.execute(sql, params)
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
    out.add(re.sub(r"(?<!제)(\d+)동$", r"제\동", base))
    
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


if __name__ =="__main__":
    print("표 목록:")
    for r in query("SELECT name FROM sqlite_master WHERE type='table' "
                   "AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        n = one(f'SELECT COUNT(*) FROM "{r[0]}"')[0]
        print(f"   {r[0]:34s} {n:>8,}")
    
    print("======================")    
    print()
    print("전체 커버리지 검사:")
    regions = dicts('SELECT 구, 행정동명 FROM master_dataset_v3')
    empty = []
    for r in regions:
        if not facility_counts(r["구"], r["행정동명"]):
            empty.append(f'{r["구"]} {r["행정동명"]}')

    print(f"   {len(regions) - len(empty)}/{len(regions)}개 동 조회 성공")
    if empty:
        print(f"   시설이 하나도 안 잡힌 동 {len(empty)}개:")
        for name in empty[:15]:
            print(f"      {name}")
    
    print()
    print("master_dataset_v3 칸:")
    for r in query("PRAGMA table_info(master_dataset_v3)"):
        print(f"   {r[1]}")