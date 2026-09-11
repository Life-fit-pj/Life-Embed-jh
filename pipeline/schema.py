import sys
import re

from sqlalchemy import (BigInteger, Column, Date, Double, ForeignKeyConstraint,
                        Index, MetaData, Table, Text)

# 이 파일은 pipeline/ 안에 있는데 app/config.py 를 가져다 쓴다.
# 파이썬은 "실행한 파일이 있는 폴더" 를 기준으로 모듈을 찾기 때문에,
# 프로젝트 뿌리를 검색 경로에 직접 넣어 줘야 한다

from app.core.config import DATA_DIR, INDICATORS
from app.db import Base, engine
from app.models import chunk, customer, history, preference   # noqa: F401
from pipeline.io import read_csv, count_rows

# 타입을 살펴볼 때 읽을 줄 수. 11만 줄을 전부 읽을 필요가 없다.
SAMPLE_SIZE = 500


###============================================
# 0. 전역 상수 설정 (수동 설정값 모음)
###============================================

# 이름에 이런 말이 들어가면 계산할 숫자가 아니라 '코드'로 본다
CODE_HINTS = ("code", "코드", "_id", "id_", "uuid", "행정동id")
COMPOSITE_PK_HINTS = ("구","행정동명") # 하드코딩 방지용 상수 추가


# 별칭 적용
TABLE_ALIAS = {
    "customers_v2": "customers",
}

# 파이프라인 중간 산출물·작업용 파일은 표로 만들지 않는다.
# data/ 에 있다고 전부 DB 표가 되어야 하는 건 아니다.
# 파일명이 자주 바뀌므로 정확한 이름 대신 접두어로 거른다
EXCLUDE_PREFIX = (
    "kb_",                 # 02·03번 산출물 (청크는 pipeline/chunk.py 가 chunks 표에 직접 넣는다)
    "member_persona",      # 다른 AI 에게 넘기려고 뽑은 파일
    "user_preferences_v",  # 버전 보관용
    "nemotron",            # 원본 11만 줄. 회원 100명은 06번이 CSV 를 직접 읽는다
    "~$",                  # 엑셀이 CSV 를 열어둔 동안 만드는 잠금 임시 파일. 진짜 데이터가 아니다
)

# 매칭되지 않는 파일들 키 정리
# customers의 city, city_dong 두 칸이 → master_dataset_v3의 구, 행정동명을 가리킴
# 기존 fks에 합침
MANUAL_FKS = {
    "customers": [
        (["city", "city_dong"], "master_dataset_v3", ["구", "행정동명"]),
    ],
}


# CSV 에는 없지만 DB 에는 있어야 하는 파생 칸.
# 가중치 7개의 "가입 시 값" 스냅샷(`녹지_초기` …)이다. 관리자 화면이 위(가입 시)/
# 아래(현재)로 나눠 보여주고 analysis.facts_drift() 가 그 차이를 센다.
# CSV 에 같은 값을 두 벌 적는 대신, 적재가 끝난 뒤 현재값을 그대로 복사해 만든다.
#
# ⚠ 이 칸이 없으면 DB 마다 다르게 실패한다 —
#    SQLite 는 큰따옴표로 감싼 이름이 칸으로 안 잡히면 문자열 리터럴로 해석한다.
#    `SELECT "녹지_초기"` 가 글자 '녹지_초기' 를 돌려주고 화면이 그걸 숫자로
#    바꾸다 NaN 을 띄운다. 에러가 안 나서 더 위험하다.
#    PostgreSQL 은 그 자리에서 column does not exist 로 죽는다
SNAPSHOT_SUFFIX = "_초기"
SNAPSHOT_COLUMNS = {"user_preferences": tuple(INDICATORS)}

# 추론한 타입 이름 -> SQLAlchemy 타입 클래스.
# 글자가 아니라 클래스다 — DDL 문자열을 우리가 안 만들기 때문이다.
#
# ★ INTEGER 를 BigInteger 로 받는 이유 —
#   SQLite 의 INTEGER 는 최대 8바이트지만 Postgres 의 INTEGER 는 4바이트(21억)다.
#   CCTV 관리번호가 18자리라 Integer 로 두면 integer out of range 로 죽는다
COLUMN_TYPE = {
    "INTEGER": BigInteger,
    "FLOAT": Double,          # Postgres 의 DOUBLE PRECISION
    "TEXT": Text,
    "DATE": Date,
}

# CSV 에서 만드는 표만 담는다. app/db.py 의 Base.metadata 와 섞지 않는다 —
# 섞으면 create_all() 한 번이 CSV 표와 모델 표를 같이 만들어서
# "이 표는 누가 정의하나" 가 다시 흐려진다
csv_metadata = MetaData()

order = csv_metadata.sorted_tables      # [Table, Table, …] — 이름이 아니라 객체다


###============================================
# 1단계 : 파일 및 데이터 읽기 함수
###============================================

    
def human_size(num_bytes):
    """1234567 -> '1.2 MB' 처럼 사람이 읽기 좋게 바꾼다."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024

   
def preview(path, limit=SAMPLE_SIZE, count_all=True):
    """파일 하나를 확인해서 화면에 뿌린다."""
    columns, rows = read_csv(path, limit=limit)
    
    # 큰 파일은 줄 세는 데도 시간이 걸리니 건너뛸 수 있게 했다
    total = count_rows(path) if count_all else None
    total_text = f"{total:,}행" if total is not None else "행수 미확인"
    
    print(f"⏳ [{path.name}] 파일을 확인하는 중...")
    print(f"✅ {human_size(path.stat().st_size)} · {total_text} · {len(columns)}칸")
    print()
    
    # 칸 이름과, 그 칸의 첫 번째 값(비어있지 않은 것)을 나란히 보여준다
    for column in columns:
        # next(조건에 맞는 값들, 없을 때 쓸 기본값)
        # 빈칸이 아닌 첫 값을 하나만 꺼낸다
        example = next((r[column] for r in rows if r[column] not in ("", None)), "")
        example = example.replace("\n", " ")
        
        # 페르소나 서술문은 아주 기니까 잘라서 보여준다
        if len(example) > 60:
            example = example[:60] + " ..."
            
        print(f"    💬 {column:28s} {example}")
    print()    


###============================================
# 2단계 : 타입 추론 함수
###============================================

# 뭘 하는 건가
#
# CSV 는 전부 글자다. "46" 도 글자고 "홍성민" 도 글자다. 그런데 DB 에 넣을 땐
# age INTEGER, name TEXT 처럼 타입을 정해야 한다. 값들을 보고 타입을
# 알아맞히는 게 이 단계다.

def is_code_column(column):
    lower = column.lower()
    return any(hint in lower for hint in CODE_HINTS)

# 해당 값이 정수인지 확인하는 삼수    
def looks_int(text):
    # 만약 음수 부호 "="이 있으면 떼서 저장
    body = text[1:] if text.startswith("-") else text
    # 0~9 가 아닌 글자가 섞인 경우
    if not body.isdigit():
        return False # 정수가 아님
    # 만약 정수일 때 앞자리가 0으로 시작하면 전화번호 (조건 2자리 이상일때)
    #print("전화번호임")
    return not (len(body) > 1 and body.startswith("0"))

# 소수 판별 함수
def looks_float(text):
    # float 실수 반환되는지 우선 확인.
    try:
        float(text)
        
    # 위의 모든 경우가 아니면 실수가 아닌게 확실하니 False반환
    except ValueError:
        return False
    
    # 전달된 값에 "."이 없으면 실수 일리가 없으니확실히 false 반환
    if "." not in text:
        return False
         
    # 위의 모든 예외사항 통과하면 얘는 무조건 실수
    return True

# 날짜 판별 함수
def looks_date(text):
    # 정규표현식 \d(숫자)
    # \d{갯수} (숫자가 저 갯수만큼 일때)
    # fullmatch (검증할 정규표현식, 검사할 문자값)
    return re.fullmatch(r"\d{4}-\d{2}-\d{2}",text) is not None #무조건 한글자 검색. 

# 타입 추론 함수 생성
def infer_type(values):
    # 전달된 값에서 빈칸을 제외한 값을 변수에 담음
    seen = [v for v in values if v != ""]
    
    if not seen :
        return "TEXT"
    
    if all (looks_int(v) for v in seen):
        return "INTEGER"

    if all (looks_float(v) for v in seen):
            return "FLOAT"
    
    if all (looks_date(v) for v in seen):
            return "DATE"
    
    return "TEXT"

def column_type(column, rows) :
    """칸 하나의 타입을 정한다. 코드성 칸은 무조건 TEXT."""
    if is_code_column(column):
        return "TEXT"
    return infer_type([r[column] for r in rows])


def describe(path, limit=SAMPLE_SIZE):
    """파일 하나의 칸별 타입을 출력한다."""
    columns, rows = read_csv(path, limit=limit)
    
    print(f"⏳ [{path.stem}] 타입을 추론하는 중...")
    
    for column in columns:
        kind = column_type(column, rows)
        print(f"   💬 {column:28s} {kind}")

    print()



###============================================
# 3단계 : 키(PK/FK) 추론 함수
###============================================


# PK를 찾아주는 함수
def infer_pk(columns, rows):
    # 1) 칸 하나로 되는지 먼저 본다 (기존 로직)
    for col in columns:
        # 코드 컬럼이 아니면 제외
        if not is_code_column(col):
            continue
        
        # value 값이 빈 문자열은 제외
        values = [r[col] for r in rows]
        if "" in values:
            continue
        
        # value 값이 중복되지 않으면 그건 PK
        if len(set(values)) == len(values):
            return [col]    # 리스트로 통일 (2)번과 형태 맞추려고)
    
    # 2) 칸 하나로 안 되면, 코드 컬럼 두 개씩 짝지어 시도한다
    code_cols = [c for c in columns if is_code_column(c) or c in (COMPOSITE_PK_HINTS)]

    for i in range(len(code_cols)):
        for j in range(i + 1, len(code_cols)):
            c1, c2 = code_cols[i], code_cols[j]
            combo = [r[c1] + "|" + r[c2] for r in rows]
            if len(set(combo)) == len(rows):
                return [c1, c2]
        
    # 위의 조건이 모두 만족하지 않는다면 PK가 없음
    return None


# 안전한 PK를 만들기 위한 함수 추가 (infer_pk에 2) 추가함)


def table_name(path):
    stem = path.stem
    return TABLE_ALIAS.get(stem, stem)

def owner_of(column, tables):
    stem = column[:-3]     # 'customer_id' -> 'customer'
    for candidate in (stem, stem+"s", stem+"es"):
        if candidate in tables:
            return candidate
    return None


###============================================
# 4단계 : 딕셔너리 만들기
###============================================


# 1. 모든 테이블별 필드, 데이터타입, PK 구하기
tables = {}
for path in sorted(DATA_DIR.glob("*.csv")):
    if path.stem.startswith(EXCLUDE_PREFIX):
        continue
    columns, sample = read_csv(path, limit=SAMPLE_SIZE)
    name = table_name(path)     # ← path.stem 대신 이걸 써야 v2가 떨어진 이름으로 저장됨
    tables[name] = {
        "path": path,          # 적재할 때 전체를 다시 읽으려고 경로를 남긴다
        "columns" : columns,
        "type" : {col: column_type(col, sample) for col in columns},
        "pk" : infer_pk(columns, sample)
    }


###============================================
# 5단계 : FK(외래키) 찾기
###============================================


# 2. 특정 테이블에 연결되어 있는 외래키 찾기
for name, table in tables.items(): # 표 이름과 내용을 그룹으로 꺼냄
    
    # 특정 테이블에 복수개의 외래키가 담길 수 있으므로 빈 리스트 생성
    fks = []
    
    # 현재 반복도는 테이블의 코드컬럼이 없으면 제외(PK, FK 아님)
    for col in table["columns"]:
        if not is_code_column(col):
            continue
        # 테이블의 PK의 주인 테이블 몇 찾음    
        owner = owner_of(col,tables)
        
        # 현재 반복도는 후보 키값들 중에서 owner 값이 동일하면 FK 제외 (PK)
        if not owner or owner == name:
            continue
        
        # 반복도는 테이블의 주인키와 현재 컬럼의 키값이 같지 않으면
        if tables[owner]["pk"] != [col]:
            continue
        
        # fks란 빈 배열에 FK, 테이블 명 저장
        fks.append((col, owner))
        
    table["fks"] = fks
    table["manual_fks"] = MANUAL_FKS.get(name,[]) # 자동 매칭 되지 않는 키값 추가
        


###============================================
# 6단계 : SQL 생성 로직
###============================================


def build_table(name, spec):
    """추론 결과를 Table 객체로 바꾼다. csv_metadata 에 등록되는 것이 부수 효과다.

    옛 build_create() 자리다. 따옴표를 손으로 붙일 일이 없어졌다 —
    칸 이름에 ㎡ 든 / 든 들어 있어도 SQLAlchemy 가 알아서 감싼다
    """
    pk = spec["pk"] or []

    args = [
        Column(col, COLUMN_TYPE[spec["type"][col]], primary_key=(col in pk))
        for col in spec["columns"]
    ]

    # ★ `_초기` 칸을 여기서 같이 만든다.
    #   옛 판은 적재가 끝난 뒤 ALTER TABLE 로 붙였다 — CREATE 문과 INSERT 가
    #   같은 칸 목록을 쓰고 있어서 파생 칸을 섞으면 둘을 같이 고쳐야 했기 때문이다.
    #   이제 Table 을 우리가 들고 있고 INSERT 도 칸 이름으로 넣으므로,
    #   정의에 처음부터 넣어도 INSERT 가 안 건드린다(값이 없으면 NULL 이다)
    for col in SNAPSHOT_COLUMNS.get(name, ()):
        if col in spec["type"]:
            args.append(Column(f"{col}{SNAPSHOT_SUFFIX}", COLUMN_TYPE[spec["type"][col]]))

    # 자동으로 찾은 FK + 그 칸의 색인 (옛 5번 CREATE INDEX 자리)
    for col, owner in spec["fks"]:
        args.append(ForeignKeyConstraint([col], [f"{owner}.{col}"]))
        args.append(Index(f"idx_{name}_{col}", col))

    # 손으로 적어 둔 FK (customers.city·city_dong -> master_dataset_v3)
    for cols, owner, owner_cols in spec.get("manual_fks", []):
        args.append(ForeignKeyConstraint(cols, [f"{owner}.{c}" for c in owner_cols]))

    return Table(name, csv_metadata, *args)


def fill_snapshot_columns(con, table):
    """`{칸}_초기` 에 지금 값을 그대로 복사한다. 칸 자체는 build_table() 이 만들어 뒀다.

    적재 직후에 부르는 것이 전제다 — 이 시점의 CSV 값이 곧 "가입 시 값" 이다.
    나중에 관리자가 가중치를 고쳐도 `_초기` 는 화이트리스트 밖이라 안 따라 바뀐다
    (app/features/admin.py 의 PREFERENCE_FIELDS)
    """
    pairs = {
        table.c[f"{col}{SNAPSHOT_SUFFIX}"]: table.c[col]
        for col in SNAPSHOT_COLUMNS.get(table.name, ())
        if f"{col}{SNAPSHOT_SUFFIX}" in table.c
    }
    if not pairs:
        return 0

    con.execute(table.update().values(pairs))
    return len(pairs)


def convert(value,kind) :
    """CSV 의 글자를 DB 에 넣을 값으로 바꾼다."""
    if value == "" :
        return None         # 빈 칸은 NULL 로
    
    try:
        if kind == "INTEGER" :
            return int(value)
    
        if kind == "FLOAT":
            return float(value)
    
    except ValueError:
        return value
    
    # TEXT·DATE 는 글자 그대로 넘긴다.
    # SQLite 는 날짜 타입이 아예 없고, PostgreSQL 은 DATE 칸에 'YYYY-MM-DD' 글자를
    # 넣으면 알아서 날짜로 받아 준다 — 양쪽 다 글자로 보내면 된다
    return value


if __name__ == "__main__":
    for name, spec in tables.items():
        build_table(name, spec)              # csv_metadata 에 등록된다

    order = csv_metadata.sorted_tables       # 참조당하는 표가 앞에 온다

    target = engine.url.render_as_string(hide_password=True)
    answer = input(f"{target}\n위 DB 의 표 {len(order)}개를 지우고 다시 만듭니다! (y/n) ")
    if answer.lower() != "y":
        print("중단합니다!")
        sys.exit(0)

    # 1. 지운다. drop_all 이 참조하는 쪽을 먼저 떨어뜨린다
    csv_metadata.drop_all(engine)
    print(f"⏳ 표 만드는 순서: {[t.name for t in order]}")

    # 2. engine.begin() 은 블록을 무사히 빠져나올 때 커밋하고, 도중에 예외가 나면
    #    통째로 되돌린다. 중간에 죽었을 때 "표는 있는데 데이터는 반만 든" DB 가 남지 않는다
    with engine.begin() as con:

        # 3. 표 만들기 — 색인과 FK 까지 Table 정의에 들어 있다
        csv_metadata.create_all(con)
        print(f"✅ 표 {len(order)}개 생성")

        # 4. 데이터 넣기
        #    타입 추론에 쓴 500행 표본이 아니라 CSV 전체를 다시 읽는다.
        #    표본을 그대로 넣으면 6만 행짜리 파일도 500행만 들어가고 에러도 안 난다
        for table in order:
            spec = tables[table.name]
            _, rows = read_csv(spec["path"])          # limit 없이 전체

            # 딕셔너리 키가 곧 칸 이름이다. 자리표시자를 :c0 처럼 번호로 붙이던
            # 일이 없어졌다 — table.insert() 가 칸 이름에서 만들어 준다.
            # ㎡ · / · 숫자로 시작하는 이름도 그대로 통과한다(검증함)
            values = [
                {col: convert(row[col], spec["type"][col]) for col in spec["columns"]}
                for row in rows
            ]

            # 빈 목록이면 넘기지 않는다 — SQLAlchemy 가 "무엇을 넣으라는 건지 모르겠다"며 예외를 낸다
            if values:
                con.execute(table.insert(), values)

            # CSV 행수와 적재 행수가 같은지 확인한다. 조용한 누락을 막는 장치다
            actual = count_rows(spec["path"])
            mark = "✅" if len(values) == actual else "⚠️"
            print(f"{mark} {table.name:20s} {len(values):7,d}줄 적재 (CSV {actual:,}행)")

        # 5. CSV 에 없는 파생 칸(`녹지_초기` …)에 지금 값을 복사한다.
        #    이걸 빼먹으면 관리자 화면의 "가입 시 희망 조건"이 통째로 NaN 이 된다
        for table in order:
            made = fill_snapshot_columns(con, table)
            if made:
                print(f"✅ {table.name:20s} {SNAPSHOT_SUFFIX} 칸 {made}개 채움")

    print(f"\n✅ {engine.url.render_as_string(hide_password=True)} 생성 완료")

    # 6. CSV 가 없는 표 — 기록 5 + user_login + chunks. 모델이 정의처다.
    #    Base.metadata 는 csv_metadata 와 별개라 위에서 만든 표를 안 건드린다
    Base.metadata.create_all(engine)
    print("✅ 모델만 있는 표 생성 (chunks · likes · search_history · chat_history · analysis_chat · admin_log · user_login)")
