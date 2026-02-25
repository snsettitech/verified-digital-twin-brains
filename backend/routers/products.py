"""
Products API - Phase 7 Digital Brains
Products that can be promoted in chat when keywords match.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field
from modules.auth_guard import verify_owner, verify_twin_ownership
from modules.observability import supabase

router = APIRouter(tags=["products"])


class ProductCreate(BaseModel):
    product_name: str = Field(..., min_length=1)
    product_link: str = Field(..., min_length=1)
    image_url: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    promotion_frequency: str = Field(
        default="once_per_conversation",
        pattern="^(every_mention|once_per_user|once_per_conversation)$",
    )
    priority: int = Field(default=0, ge=0)
    active: bool = True


class ProductUpdate(BaseModel):
    product_name: Optional[str] = Field(None, min_length=1)
    product_link: Optional[str] = Field(None, min_length=1)
    image_url: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    promotion_frequency: Optional[str] = Field(
        None,
        pattern="^(every_mention|once_per_user|once_per_conversation)$",
    )
    priority: Optional[int] = Field(None, ge=0)
    active: Optional[bool] = None


@router.get("/twins/{twin_id}/products")
async def list_products(
    twin_id: str,
    active_only: bool = True,
    user=Depends(verify_owner),
):
    """List products for a twin."""
    verify_twin_ownership(twin_id, user)
    q = supabase.table("products").select("*").eq("twin_id", twin_id).order("priority", desc=True)
    if active_only:
        q = q.eq("active", True)
    result = q.execute()
    return result.data or []


@router.post("/twins/{twin_id}/products")
async def create_product(
    twin_id: str,
    body: ProductCreate,
    user=Depends(verify_owner),
):
    """Create a product for a twin."""
    verify_twin_ownership(twin_id, user)
    payload = {
        "twin_id": twin_id,
        "product_name": body.product_name,
        "product_link": body.product_link,
        "image_url": body.image_url,
        "description": body.description,
        "keywords": body.keywords or [],
        "promotion_frequency": body.promotion_frequency,
        "priority": body.priority,
        "active": body.active,
    }
    result = supabase.table("products").insert(payload).select().execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create product")
    return result.data[0]


@router.patch("/products/{product_id}")
async def update_product(
    product_id: str,
    body: ProductUpdate,
    user=Depends(verify_owner),
):
    """Update a product. Verifies ownership via twin_id."""
    existing = supabase.table("products").select("id, twin_id").eq("id", product_id).single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Product not found")
    verify_twin_ownership(existing.data["twin_id"], user)
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        return existing.data
    result = supabase.table("products").update(payload).eq("id", product_id).select().execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update product")
    return result.data[0]


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    user=Depends(verify_owner),
):
    """Delete a product."""
    existing = supabase.table("products").select("id, twin_id").eq("id", product_id).single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Product not found")
    verify_twin_ownership(existing.data["twin_id"], user)
    supabase.table("products").delete().eq("id", product_id).execute()
    return {"status": "deleted", "id": product_id}
