"""회원 표를 다룬다. customers 와 user_preferences.

돌려주는 것은 전부 딕셔너리·튜플·기본값이다 — ORM 객체를 내보내면
세션이 닫힌 뒤 쓸 수 없다(DetachedInstanceError).
옛 app/tables/members.py 와 반환 모양을 똑같이 맞춘다.

집계 함수가 (이름, 개수) 튜플 목록을 돌려주는 것도 옛 파일 그대로다.
{label, value} 로 바꾸는 건 화면 쪽(features) 일이다.
"""

from sqlalchemy import Integer, cast, func, inspect

from app.core.config import INDICATORS
from app.db import engine
from app.models.chunk import MemberChunk
from app.models.customer import Customer
from app.models.preference import Preference

CUSTOMER_LIST_FIELDS = ("customer_id", "name", "age", "city", "city_dong")


def _dicts(db, columns, fields, *filters):
    """고른 칸만 딕셔너리 목록으로 꺼낸다. 옛 dicts() 와 같은 모양."""
    query = db.query(*columns)
    for condition in filters:
        query = query.filter(condition)
    return [dict(zip(fields, row)) for row in query.all()]


# ── 공용 쓰기 헬퍼 ──────────────
# 옛 _run_update 는 SET 절 문자열을 손으로 이어 붙였고 SQL 주입을 화이트리스트로
# 막았다. ORM 은 setattr 로 값을 넣으므로 문자열 조립 자체가 없다.
# 화이트리스트는 그대로 둔다 — 그건 주입 방지가 아니라 "고쳐도 되는 칸" 정책이다.

def _apply(db, model, where, patch, allowed):
    """patch 중 allowed 에 있는 칸만 골라 고친다. 고친 칸 수를 돌려준다."""
    fields = [name for name in patch if name in allowed]
    if not fields:
        return 0

    row = db.query(model).filter(where).first()
    if row is not None:
        for name in fields:
            setattr(row, name, patch[name])
        db.commit()

    # ⚠ 옛 코드는 대상 줄이 없어도 len(fields) 를 돌려줬다. 그 동작을 그대로 둔다 —
    #    고칠 값어치가 있어 보이지만, 리팩터링 중에 동작을 바꾸면 "옮겨서 깨진 건지
    #    고쳐서 바뀐 건지" 를 구분할 수 없다. 리팩터링이 끝난 뒤에 따로 다룬다
    return len(fields)


def _insert(db, model, customer_id, patch, allowed):
    """patch 중 allowed 에 있는 칸만 골라 INSERT 한다.

    allowed 순서로 도는 것도 옛 코드 그대로다 — 칸 순서가 결과에 영향을 주진
    않지만, 옮기면서 굳이 바꿀 이유도 없다.
    """
    values = {name: patch[name] for name in allowed if name in patch}
    db.add(model(customer_id=customer_id, **values))
    db.commit()


# ── 프로젝트 전용 조회 함수 ─────────────────────────────

def member_weights(db, customer_ids):
    """회원들의 가중치 7개를 꺼낸다.

    옛 코드는 IN (?, ?, ?) 의 물음표를 사람 수만큼 손으로 만들었다.
    ORM 은 in_() 하나로 끝난다 — 개수를 셀 일이 없다.
    """
    if not customer_ids:
        return []

    fields = ("customer_id", *INDICATORS)
    columns = [getattr(Preference, name) for name in fields]

    return _dicts(db, columns, fields, Preference.customer_id.in_(customer_ids))


# ── 회원 관리자 조회 (app/features/admin.py 가 쓴다) ──────────────

def customer_list(db):
    """회원 목록. 화면 왼쪽 목록에 쓴다. 목록엔 다 필요 없으니 몇 칸만"""
    columns = [getattr(Customer, name) for name in CUSTOMER_LIST_FIELDS]
    rows = db.query(*columns).order_by(Customer.customer_id).all()
    return [dict(zip(CUSTOMER_LIST_FIELDS, row)) for row in rows]


def customer_one(db, customer_id):
    """customers 표에서 회원 한 명. 없으면 None

    옛 SQL 은 SELECT * 였다. 모델에 적은 칸 전부를 같은 순서로 담는다.
    """
    fields = tuple(c.name for c in Customer.__table__.columns)
    columns = [getattr(Customer, name) for name in fields]

    rows = _dicts(db, columns, fields, Customer.customer_id == customer_id)
    return rows[0] if rows else None


def customer_preferences(db, customer_id):
    """user_preferences 표에서 한 명의 가중치 7개. 없으면 None"""
    fields = tuple(INDICATORS)
    columns = [getattr(Preference, name) for name in fields]

    rows = _dicts(db, columns, fields, Preference.customer_id == customer_id)
    return rows[0] if rows else None


def customer_preferences_initial(db, customer_id):
    """가입 시 가중치 7개(`녹지_초기` 등). 없으면 None.

    돌려주는 키는 `_초기`를 뗀 이름이다 — 현재값과 같은 키라서 화면이
    같은 방식으로 돌 수 있다. 옛 SQL 의 `AS` 가 하던 일을 zip 이 대신한다.

    `_초기` 칸은 CSV 에 없고 적재(pipeline/schema.py)가 파생시켜 만든다.
    낡은 DB 에는 없을 수 있으므로 먼저 확인한다
    """
    if not has_initial_columns(db):
        return None

    fields = tuple(INDICATORS)
    columns = [getattr(Preference, f"{name}_초기") for name in fields]

    rows = _dicts(db, columns, fields, Preference.customer_id == customer_id)
    return rows[0] if rows else None


def customer_persona(db, customer_id):
    """member_chunk 에서 회원 한 명의 페르소나 9칸을 {category: text} 로 되돌린다"""
    rows = (
        db.query(MemberChunk.category, MemberChunk.text)
        .filter(MemberChunk.customer_id == customer_id)
        .all()
    )
    return {category: text for category, text in rows}


# ── 회원 관리자 수정 (app/features/admin.py 가 쓴다) ──────────────

def update_customer(db, customer_id, patch, allowed):
    return _apply(db, Customer, Customer.customer_id == customer_id, patch, allowed)


def update_preferences(db, customer_id, patch, allowed):
    return _apply(db, Preference, Preference.customer_id == customer_id, patch, allowed)


def insert_customer(db, customer_id, patch, allowed):
    return _insert(db, Customer, customer_id, patch, allowed)


def insert_preferences(db, customer_id, patch, allowed):
    return _insert(db, Preference, customer_id, patch, allowed)


def customer_names(db):
    """마스킹에 쓸 회원 이름 목록. 빈 값은 뺀다"""
    return [name for (name,) in db.query(Customer.name).all() if name]


def customer_ids(db):
    """회원 번호 전부"""
    return [customer_id for (customer_id,) in db.query(Customer.customer_id).all()]


# ── 집계 (관리자 대시보드·분석이 쓴다) ──────────────────
# 두 칸짜리 결과는 (이름, 개수) 튜플 목록으로 돌려준다.

def customer_count(db):
    """customers 표에 몇 명이 있나. 로그인만 발급된 빈 계정도 포함된다."""
    return db.query(func.count()).select_from(Customer).scalar()


def preference_count(db):
    """가중치를 실제로 가진 사람 수. customer_count 와 다를 수 있다."""
    return db.query(func.count()).select_from(Preference).scalar()


def has_initial_columns(db):
    """user_preferences 에 `_초기` 7칸이 다 있나.

    모델이 아니라 실제 DB 를 본다 — 모델에 적혀 있어도 표에는 없을 수 있다.
    이 질문은 ORM 이 못 답한다. ORM 은 "칸이 있다고 치고" 도는 도구다.
    (db 를 안 쓰지만 다리가 모든 함수를 fn(db, *args) 로 부르므로 받아 둔다)
    """
    actual = {c["name"] for c in inspect(engine).get_columns("user_preferences")}
    return {f"{name}_초기" for name in INDICATORS} <= actual


def indicator_averages(db):
    """지표 7개의 평균. {지표이름: 평균} 으로 돌려준다."""
    columns = [func.avg(getattr(Preference, name)) for name in INDICATORS]
    row = db.query(*columns).one()
    return dict(zip(INDICATORS, row))


def indicator_spread(db, name):
    """지표 하나를 1~5 중 몇 명이 골랐나. (점수, 인원) 목록."""
    score = cast(getattr(Preference, name), Integer)

    return [
        tuple(row)
        for row in db.query(score, func.count())
        .filter(getattr(Preference, name).isnot(None))
        .group_by(score)
        .order_by(score)
        .all()
    ]


def indicator_drift(db, name):
    """지표 하나가 가입 시 값에서 얼마나 움직였나. (인원, 평균변화).

    0.005 미만 차이는 세지 않는다 — 소수점 오차를 변동으로 세지 않기 위해서다
    """
    current = getattr(Preference, name)
    initial = getattr(Preference, f"{name}_초기")

    row = (
        db.query(func.count(), func.avg(current - initial))
        .filter(initial.isnot(None))
        .filter(func.abs(current - initial) >= 0.005)
        .one()
    )
    return tuple(row)


def age_group_counts(db):
    """연령대(10년 단위)별 인원. (연령대, 인원) 목록."""
    group = cast(Customer.age / 10, Integer) * 10

    return [
        tuple(row)
        for row in db.query(group, func.count())
        .filter(Customer.age.isnot(None))
        .group_by(group)
        .order_by(group)
        .all()
    ]


def gender_counts(db):
    """성별 인원. (성별코드, 인원) 목록."""
    return [
        tuple(row)
        for row in db.query(Customer.gender, func.count())
        .group_by(Customer.gender)
        .order_by(Customer.gender)
        .all()
    ]


def join_month_counts(db):
    """가입 월(YYYY-MM)별 인원. (월, 인원) 목록."""
    month = func.substr(Customer.joined_at, 1, 7)

    return [
        tuple(row)
        for row in db.query(month, func.count())
        .filter(Customer.joined_at.isnot(None))
        .filter(Customer.joined_at != "")
        .group_by(month)
        .order_by(month)
        .all()
    ]


def home_city_counts(db):
    """거주 자치구별 인원. (자치구, 인원) 목록."""
    total = func.count()

    return [
        tuple(row)
        for row in db.query(Customer.city, total)
        .filter(Customer.city.isnot(None))
        .group_by(Customer.city)
        .order_by(total.desc(), Customer.city)
        .all()
    ]


def work_city_counts(db, limit=15):
    """직장 자치구별 인원. (자치구, 인원) 목록."""
    total = func.count()

    return [
        tuple(row)
        for row in db.query(Customer.work_city, total)
        .filter(Customer.work_city.isnot(None))
        .group_by(Customer.work_city)
        .order_by(total.desc())
        .limit(limit)
        .all()
    ]


def deal_type_counts(db):
    """희망 거래형태별 인원. (거래형태, 인원) 목록."""
    total = func.count()

    return [
        tuple(row)
        for row in db.query(Preference.거래형태, total)
        .filter(Preference.거래형태.isnot(None))
        .filter(Preference.거래형태 != "")
        .group_by(Preference.거래형태)
        .order_by(total.desc())
        .all()
    ]
