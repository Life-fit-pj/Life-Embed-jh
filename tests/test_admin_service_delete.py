"""delete_member() 의 탈퇴 절차. DB 없이 각 저장소 호출을 흉내 낸다.

없는 회원이면 아무것도 안 건드리고 False, 있으면 청크·로그인·활동·본표 순으로
지우고 True를 돌려줘야 한다."""

from unittest.mock import patch

from app.services import admin_service


def test_없는_회원이면_아무것도_안_지운다():
    with patch.object(admin_service, "get_member", return_value=None), \
         patch.object(admin_service, "delete_customer") as mock_delete_customer:

        result = admin_service.delete_member("C999")

    assert result is False
    mock_delete_customer.assert_not_called()


def test_있는_회원이면_전부_지우고_True():
    with patch.object(admin_service, "get_member", return_value={"customer_id": "C101"}), \
         patch.object(admin_service, "replace_member_chunks") as mock_chunks, \
         patch.object(admin_service.vector_store, "invalidate") as mock_invalidate, \
         patch.object(admin_service, "delete_logins_by_customer") as mock_logins, \
         patch.object(admin_service, "delete_activity") as mock_activity, \
         patch.object(admin_service, "delete_customer") as mock_customer:

        result = admin_service.delete_member("C101")

    assert result is True
    mock_chunks.assert_called_once_with("C101", [])
    mock_invalidate.assert_called_once_with("member")
    mock_logins.assert_called_once_with("C101")
    mock_activity.assert_called_once_with("C101")
    mock_customer.assert_called_once_with("C101")
