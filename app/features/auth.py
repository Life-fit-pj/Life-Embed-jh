"""
임시 로그인 발급/검증.

이 파일은 "규칙"만 담당한다 — SQL은 app.core.db 에 있다.
app/features/admin.py 가 이미 쓰는 것과 같은 구조.
"""

import random
import string

from app.core.db import (
    next_customer_id, next_unclaimed_customer_id, create_customer_stub,
    create_login, get_login_row, dicts,
)


def _random_code(length, chars):
    return "".join(random.choice(chars) for _ in range(length))


def login(login_id, password):
    """아이디+비번으로 로그인한다. 성공하면 customer_id, 실패하면 None.

    처음 보는 아이디면 그 자리에서 계정을 만들어 바로 로그인시킨다 — 로그인
    계정이 없는 기존 회원(이름·나이·페르소나가 이미 있는 시드 데이터)이 남아
    있으면 그 사람에게, 다 배정됐으면 새 빈 계정에 이 아이디/비번을 그대로
    붙인다. 이미 있는 아이디면 비번이 맞는지만 본다. 별도 "계정 발급" 단계
    없이 로그인 폼 하나로 발급+로그인을 겸하는 게 지금 요구사항이다 —
    실 회원가입이 붙으면 이 즉석 발급 분기는 걷어내면 된다.
    """
    row = get_login_row(login_id)
    if row is None:
        customer_id = next_unclaimed_customer_id()
        if customer_id is None:
            customer_id = next_customer_id()
            create_customer_stub(customer_id)
        create_login(customer_id, login_id, password)
        return customer_id

    return row["customer_id"] if row["password"] == password else None


def backfill_logins():
    """user_login 이 없는 기존 customers 에게 임시 아이디/비번을 만들어 준다.

    로그인 시 즉석 발급(login)과 기존 시드 회원(C001~C099)이 같은 user_login
    표를 쓰므로, 이 표에 행이 없는 사람만 골라 채운다 — 이미 있는 사람은
    건너뛰어 두 번 실행해도 안전하다.
    """
    have = {r["customer_id"] for r in dicts("SELECT customer_id FROM user_login")}
    missing = [r["customer_id"] for r in dicts("SELECT customer_id FROM customers")
               if r["customer_id"] not in have]

    issued = []
    for customer_id in missing:
        login_id = _random_code(6, string.ascii_lowercase + string.digits)
        password = _random_code(6, string.digits)
        create_login(customer_id, login_id, password)
        issued.append({"customer_id": customer_id, "login_id": login_id, "password": password})

    return issued
