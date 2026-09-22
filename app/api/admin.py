# Last Updated: 2026-09-08
"""관리자 라우트. 회원/행정동 조회·수정, 대시보드, 로그인 백필."""

from fastapi import APIRouter, HTTPException

from app.features.admin import (
    InvalidPatch,
    clear_caches, create_member, dashboard, delete_member, get_member, get_region, health,
    list_members, list_regions, preview_member, privacy_preview, recent_logs,
    similar_members, update_member, update_region,
)
from app.features.auth import backfill_logins
from app.schemas.admin import (
    BackfillLoginOut, ClearCachesOut, DashboardOut, HealthOut, MemberListItem,
    MemberOut, PrivacyPreviewOut, RecentLogOut, RegionDetailOut, RegionListItem,
    SimilarMemberOut,
)
from app.schemas.recommend import RegionOut

router = APIRouter(prefix="/admin", tags=["admin"])

# ===================================================================
# 회원 
# ===================================================================

@router.get("/members", response_model=list[MemberListItem])
def get_members():
    """회원 100명 목록."""
    return list_members()


@router.get("/members/{customer_id}", response_model=MemberOut)
def get_member_detail(customer_id: str):
    """회원 한 명 상세. 없으면 404."""
    member = get_member(customer_id)
    if member is None:
        raise HTTPException(status_code=404, detail="member not found")
    return member


@router.post("/members", response_model=MemberOut, status_code=201)
def post_member(payload: dict):
    """회원 한 명을 손으로 새로 만든다. 규칙 위반이면 422."""
    try:
        return create_member(payload)
    except InvalidPatch as e:
        raise HTTPException(status_code=422, detail=e.errors)


@router.patch("/members/{customer_id}", response_model=MemberOut)
def patch_member(customer_id: str, patch: dict):
    """회원 정보 수정. 없으면 404, 규칙 위반이면 422."""
    try:
        member = update_member(customer_id, patch)
    except InvalidPatch as e:
        raise HTTPException(status_code=422, detail=e.errors)
    if member is None:
        raise HTTPException(status_code=404, detail="member not found")
    return member


@router.delete("/members/{customer_id}")
def delete_member_route(customer_id: str):
    """회원 탈퇴. 없으면 404."""
    if not delete_member(customer_id):
        raise HTTPException(status_code=404, detail="member not found")
    return {"ok": True}


@router.get("/members/{customer_id}/preview", response_model=list[RegionOut])
def get_member_preview(customer_id: str):
    """이 회원의 희망조건으로 추천 TOP 5를 뽑아본다. 아무것도 안 고친다."""
    result = preview_member(customer_id)
    if result is None:
        raise HTTPException(status_code=404, detail="member not found")
    return result


@router.get("/members/{customer_id}/similar", response_model=list[SimilarMemberOut])
def get_member_similar(customer_id: str, top_k: int = 5):
    """이 회원과 페르소나가 비슷한 회원들."""
    result = similar_members(customer_id, top_k=top_k)
    if result is None:
        raise HTTPException(status_code=404, detail="member not found")
    return result


@router.get("/members/{customer_id}/privacy-preview", response_model=PrivacyPreviewOut)
def get_member_privacy_preview(customer_id: str):
    """이 회원의 페르소나 9칸을 원본과 가린 것으로 나란히 준다."""
    result = privacy_preview(customer_id)
    if result is None:
        raise HTTPException(status_code=404, detail="member not found")
    return result

# ===================================================================
# 행정동 
# ===================================================================

@router.get("/regions", response_model=list[RegionListItem])
def get_regions():
    """행정동 427개 목록."""
    return list_regions()


@router.get("/regions/{gu}/{dong}", response_model=RegionDetailOut)
def get_region_detail(gu: str, dong: str):
    """행정동 하나의 지표 12개 + 백분위 + 좋아요 수. 없으면 404."""
    region = get_region(gu, dong)
    if region is None:
        raise HTTPException(status_code=404, detail="region not found")
    return region


@router.patch("/regions/{gu}/{dong}", response_model=RegionDetailOut)
def patch_region(gu: str, dong: str, patch: dict):
    """행정동 지표 수정. 없으면 404, 규칙 위반이면 422."""
    try:
        region = update_region(gu, dong, patch)
    except InvalidPatch as e:
        raise HTTPException(status_code=422, detail=e.errors)
    if region is None:
        raise HTTPException(status_code=404, detail="region not found")
    return region

# ===================================================================
# 대시보드·운영 
# ===================================================================

@router.get("/health", response_model=HealthOut)
def get_health():
    """일할 준비가 됐나."""
    return health()


@router.post("/clear-caches", response_model=ClearCachesOut)
def post_clear_caches():
    """캐시를 비운다. 관리자가 버튼으로 직접 부른다."""
    return clear_caches()


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard():
    """관리자 첫 화면 한 판."""
    return dashboard()


@router.get("/recent-logs", response_model=list[RecentLogOut])
def get_recent_logs(limit: int = 8):
    """관리자 수정 이력 최근 몇 건."""
    return recent_logs(limit)


@router.post("/backfill-logins", response_model=list[BackfillLoginOut])
def post_backfill_logins():
    """user_login 이 없는 기존 회원에게 임시 아이디/비번을 만들어 준다."""
    return backfill_logins()
