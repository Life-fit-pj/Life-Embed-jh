# Last Updated: 2026-09-08
"""동네 시설 조회 창구. app/api가 부르는 문."""

from app.repositories.regions import facilities, facility_counts, region_extras


def get_facilities(gu, dong, limit=5):
    """행정동 하나의 시설 정보. 지도 핀을 눌렀을 때 쓴다."""
    return {
        "counts": facility_counts(gu, dong),
        "items": facilities(gu, dong, limit=limit),
        "extras": region_extras(gu, dong),
    }
