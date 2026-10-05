"""preview_member() — 이 회원 조건으로 추천을 돌려본다. DB 없이 저장소 호출을 흉내 낸다.

선호도 행이 없는 회원(설문을 건너뛰고 가입)과 없는 회원은 다르다 — 앞은 보통(3)으로 돌려 보고, 뒤만 None 이다.
둘을 같이 None 으로 내면 화면이 가중치 저장 직전에 부르는 이 조회가 404 로 죽어 저장 요청이 안 나간다."""

from unittest.mock import patch

from app.core.config import INDICATORS
from app.services import admin_service


def test_선호도_행이_없는_회원은_보통으로_돌려_본다():
    with patch.object(admin_service, "customer_preferences", return_value=None), \
         patch.object(admin_service, "customer_one", return_value={"customer_id": "C107"}), \
         patch.object(admin_service.search_service, "recommend_by_weights", return_value=["동네"]) as mock_recommend:

        result = admin_service.preview_member("C107")

    assert result == ["동네"]
    mock_recommend.assert_called_once_with({name: 3 for name in INDICATORS}, top_k=5)


def test_없는_회원이면_None():
    with patch.object(admin_service, "customer_preferences", return_value=None), \
         patch.object(admin_service, "customer_one", return_value=None), \
         patch.object(admin_service.search_service, "recommend_by_weights") as mock_recommend:

        assert admin_service.preview_member("C999") is None

    mock_recommend.assert_not_called()
