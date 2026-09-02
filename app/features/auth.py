"""
임시 로그인 발급/검증.

이 파일은 "규칙"만 담당한다 — SQL은 app.core.db 에 있다.
app/features/admin.py 가 이미 쓰는 것과 같은 구조.
"""

import random
import string

from app.core.db import next_customer_id, create_customer_stub, create_login, find_login


def _random_code(length, chars):
    return "".join(random.choice(chars) for _ in range(length))


def issue_account():
    """새 임시 계정을 발급한다. {customer_id, login_id, password} 를 돌려준다.

    customers 에 최소 행을 만들어 두는 이유 — customer_list(), dashboard() 같은
    기존 집계 함수들이 전부 customers 표를 기준으로 세기 때문에, 여기 행이 없으면
    이 손님은 회원수·나이·성별 집계 어디에도 안 잡힌다.
    """
    customer_id = next_customer_id()
    login_id = _random_code(6, string.ascii_lowercase + string.digits)
    password = _random_code(6, string.digits)

    create_customer_stub(customer_id)
    create_login(customer_id, login_id, password)

    return {"customer_id": customer_id, "login_id": login_id, "password": password}


def login(login_id, password):
    """아이디+비번이 맞으면 customer_id, 틀리면 None."""
    return find_login(login_id, password)
