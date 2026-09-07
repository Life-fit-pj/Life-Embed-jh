# Last Updated: 2026-09-07
"""고객 조회 라우트."""

from fastapi import APIRouter, HTTPException

from app.features.customers import customer_one
from app.schemas.customers import CustomerOut

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: str):
    """customer_id 한 명. 없으면 404."""
    customer = customer_one(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return customer