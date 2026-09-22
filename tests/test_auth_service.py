"""signup() 의 중복 방지. DB 없이 create_login/create_member 를 흉내 낸다.

login_id 선점(create_login)이 create_member 보다 먼저 돌아야, 같은 사용자의
중복 요청(더블클릭 등)이 겹쳐 와도 customer 가 한 명만 생긴다."""

from unittest.mock import patch

import pytest

from app.services import auth_service


def test_이미_선점된_login_id면_회원을_안_만든다():
    with patch.object(auth_service, "create_login", return_value=False) as mock_create_login, \
         patch.object(auth_service.admin_service, "create_member") as mock_create_member:

        result = auth_service.signup("user-1", {"name": "홍길동"})

    assert result is None
    mock_create_member.assert_not_called()
    mock_create_login.assert_called_once()


def test_회원_생성이_실패하면_선점한_자리를_반납한다():
    with patch.object(auth_service, "create_login", return_value=True), \
         patch.object(auth_service, "delete_login") as mock_delete_login, \
         patch.object(auth_service.admin_service, "create_member", side_effect=ValueError("boom")):

        with pytest.raises(ValueError):
            auth_service.signup("user-2", {"name": "홍길동"})

    mock_delete_login.assert_called_once_with(auth_service._login_id("user-2"))


def test_정상_가입이면_선점한_자리에_customer_id를_채운다():
    member = {"customer": {"customer_id": "C999"}}

    with patch.object(auth_service, "create_login", return_value=True), \
         patch.object(auth_service, "update_login_customer") as mock_update, \
         patch.object(auth_service.admin_service, "create_member", return_value=member):

        result = auth_service.signup("user-3", {"name": "홍길동"})

    assert result == "C999"
    mock_update.assert_called_once_with(auth_service._login_id("user-3"), "C999")
