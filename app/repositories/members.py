"""회원 표를 다루는 SQL. 이름이 붙은 조회·수정 함수만 낸다."""

from app.core.config import INDICATORS
from app.core.db import dicts, get_con, one, query, table_columns   # 실행기는 core 에서 가져온다


# ── 공용 쓰기 헬퍼 ──────────────

def _run_update(table, where_sql, where_params, patch, allowed):
    """patch 중 allowed(화이트리스트)에 있는 칸만 골라 UPDATE 한다.

    화이트리스트 밖 칸은 조용히 버린다 — SQL 주입 방지
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


def _run_insert(table, customer_id, patch, allowed):
    """patch 중 allowed(화이트리스트)에 있는 칸만 골라 INSERT 한다.
    _run_update 의 INSERT 버전이다. customer_id 는 항상 첫 칸으로 같이 넣는다.
    """
    fields = [name for name in allowed if name in patch]
    cols = ["customer_id"] + fields
    quoted = ", ".join(f'"{c}"' for c in cols)
    marks = ", ".join("?" * len(cols))
    values = [customer_id] + [patch[name] for name in fields]

    get_con().execute(f'INSERT INTO "{table}" ({quoted}) VALUES ({marks})', values)
    get_con().commit()


# ── 프로젝트 전용 조회 함수 ─────────────────────────────

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
    

# ── 회원 관리자 조회 (app/features/admin.py 가 쓴다) ──────────────

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


def customer_preferences_initial(customer_id):
    """가입 시 가중치 7개(`녹지_초기` 등). 없으면 None.

    현재값과 따로 꺼내는 이유 —
    관리자 화면이 "가입 때 이랬는데 지금 이렇다"를 위아래로 보여준다.
    한 딕셔너리에 섞어 주면 화면이 칸 이름에서 `_초기`를 떼어내며 돌아야 한다.

    돌려주는 키는 `_초기`를 뗀 이름이다 — 현재값과 같은 키라서 화면이
    같은 방식으로 돌 수 있다

    `_초기` 칸은 CSV 에 없고 적재(`pipeline/schema.py`)가 파생시켜 만든다.
    낡은 DB 에는 없을 수 있는데, 그대로 조회하면 에러 대신 칸 이름 글자가
    돌아와 화면이 NaN 을 띄운다. 없으면 None 을 주고 화면은 그 블록을 안 그린다
    """
    if not {f"{name}_초기" for name in INDICATORS} <= table_columns("user_preferences"):
        return None

    cols = ", ".join(f'"{name}_초기" AS "{name}"' for name in INDICATORS)
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
  

# ── 회원 관리자 수정 (app/features/admin.py 가 쓴다) ──────────────

def update_customer(customer_id, patch, allowed):
    return _run_update("customers", "customer_id = ?", (customer_id,), patch, allowed)


def update_preferences(customer_id, patch, allowed):
    return _run_update("user_preferences", "customer_id = ?", (customer_id,), patch, allowed)


def insert_customer(customer_id, patch, allowed):
    return _run_insert("customers", customer_id, patch, allowed)


def insert_preferences(customer_id, patch, allowed):
    return _run_insert("user_preferences", customer_id, patch, allowed)


# 마스킹에 쓸 회원 이름 목록. 빈 값은 뺀다
def customer_names():
    return [r["name"] for r in dicts("SELECT name FROM customers") if r["name"]]


# ── 집계 (관리자 대시보드·분석이 쓴다) ──────────────────
# 두 칸짜리 결과는 (이름, 개수) 튜플 목록으로 돌려준다.
# {label, value} 모양으로 바꾸는 건 화면 쪽(features) 일이다

def customer_count():
    """customers 표에 몇 명이 있나. 로그인만 발급된 빈 계정도 포함된다."""
    return one("SELECT COUNT(*) FROM customers")[0]


def preference_count():
    """가중치를 실제로 가진 사람 수. customer_count 와 다를 수 있다."""
    return one("SELECT COUNT(*) FROM user_preferences")[0]


def has_initial_columns():
    """user_preferences 에 `_초기` 7칸이 다 있나.

    없는 칸을 그냥 조회하면 SQLite 가 칸 이름을 문자열로 해석해 조용히
    틀린 숫자를 준다. 세기 전에 반드시 여기서 먼저 확인한다
    """
    return {f"{name}_초기" for name in INDICATORS} <= table_columns("user_preferences")


def indicator_averages():
    """지표 7개의 평균. {지표이름: 평균} 으로 돌려준다."""
    cols = ", ".join(f'AVG("{name}")' for name in INDICATORS)
    row = one(f"SELECT {cols} FROM user_preferences") or ()
    return dict(zip(INDICATORS, row))


def indicator_spread(name):
    """지표 하나를 1~5 중 몇 명이 골랐나. (점수, 인원) 목록."""
    return query(
        f'SELECT CAST("{name}" AS INT), COUNT(*) FROM user_preferences '
        f'WHERE "{name}" IS NOT NULL GROUP BY 1 ORDER BY 1'
    )


def indicator_drift(name):
    """지표 하나가 가입 시 값에서 얼마나 움직였나. (인원, 평균변화).

    0.005 미만 차이는 세지 않는다 — 소수점 오차를 변동으로 세지 않기 위해서다
    """
    return one(
        f'SELECT COUNT(*), AVG("{name}" - "{name}_초기") FROM user_preferences '
        f'WHERE "{name}_초기" IS NOT NULL AND ABS("{name}" - "{name}_초기") >= 0.005'
    )


def age_group_counts():
    """연령대(10년 단위)별 인원. (연령대, 인원) 목록."""
    return query(
        "SELECT CAST(age / 10 AS INT) * 10, COUNT(*) FROM customers "
        "WHERE age IS NOT NULL GROUP BY 1 ORDER BY 1"
    )


def gender_counts():
    """성별 인원. (성별코드, 인원) 목록."""
    return query("SELECT gender, COUNT(*) FROM customers GROUP BY 1 ORDER BY 1")


def join_month_counts():
    """가입 월(YYYY-MM)별 인원. (월, 인원) 목록."""
    return query(
        "SELECT substr(joined_at, 1, 7), COUNT(*) FROM customers "
        "WHERE joined_at IS NOT NULL AND joined_at <> '' GROUP BY 1 ORDER BY 1"
    )


def home_city_counts():
    """거주 자치구별 인원. (자치구, 인원) 목록."""
    return query(
        "SELECT city, COUNT(*) FROM customers WHERE city IS NOT NULL "
        "GROUP BY 1 ORDER BY 2 DESC, 1"
    )


def work_city_counts(limit=15):
    """직장 자치구별 인원. (자치구, 인원) 목록."""
    return query(
        "SELECT work_city, COUNT(*) FROM customers WHERE work_city IS NOT NULL "
        "GROUP BY 1 ORDER BY 2 DESC LIMIT ?", (limit,)
    )


def deal_type_counts():
    """희망 거래형태별 인원. (거래형태, 인원) 목록."""
    return query(
        'SELECT "거래형태", COUNT(*) FROM user_preferences '
        'WHERE "거래형태" IS NOT NULL AND "거래형태" <> \'\' GROUP BY 1 ORDER BY 2 DESC'
    )
  
  
# tables/members.py — 회원 번호 전부
def customer_ids():
    return [r["customer_id"] for r in dicts("SELECT customer_id FROM customers")]