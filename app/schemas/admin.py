# Last Updated: 2026-09-08
"""관리자 API 요청·응답 모양. app/features/admin.py 와 1:1.

칸 이름이 회원/지표마다 다른 자리(희망조건 7칸, 페르소나 9칸, 지표 12칸, 대시보드 차트)는
Housing.targets(schemas/recommend.py)와 같은 방식으로 dict 로 둔다.
"""

from pydantic import BaseModel

from app.schemas.customers import CustomerOut
from app.schemas.history import ChatHistoryItem, SearchHistoryItem


class MemberListItem(BaseModel):
    customer_id: str
    name: str | None = None
    age: int | None = None
    city: str | None = None
    city_dong: str | None = None


class LikeOut(BaseModel):
    구: str
    행정동명: str
    created_at: str


class MemberOut(BaseModel):
    customer: CustomerOut
    preferences: dict
    preferences_initial: dict
    persona: dict | None = None
    likes: list[LikeOut]
    searches: list[SearchHistoryItem]
    chats: list[ChatHistoryItem]


class SimilarMemberOut(BaseModel):
    customer_id: str
    score: float
    category: str
    text: str


class PrivacyPreviewOut(BaseModel):
    raw: dict
    masked: dict
    changed: int


class RegionListItem(BaseModel):
    구: str
    행정동명: str


class RegionDetailOut(BaseModel):
    구: str
    행정동명: str
    likes: int
    values: dict
    percentiles: dict

class RecentLogOut(BaseModel):
    target: str
    target_id: str
    fields: list[str]
    field_count: int
    changed_at: str


class HealthOut(BaseModel):
    ok: bool
    regions: int
    members: int
    cache_warm: bool
    error: str | None = None


class ClearCachesOut(BaseModel):
    ok: bool
    cache_warm: bool


class DashboardOut(BaseModel):
    ok: bool
    regions: int
    members: int
    cache_warm: bool
    error: str | None = None
    counts: dict
    charts: dict
    recent: list[RecentLogOut]

class BackfillLoginOut(BaseModel):
    customer_id: str
    login_id: str
    password: str
