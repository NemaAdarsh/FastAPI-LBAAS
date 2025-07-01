from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

class TenantBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Tenant name")
    slug: str = Field(..., min_length=1, max_length=50, description="URL-friendly identifier")
    subscription_tier: str = Field("free", description="Subscription tier")
    max_load_balancers: int = Field(5, ge=1, description="Maximum number of load balancers")

    @validator('subscription_tier')
    def validate_subscription_tier(cls, v):
        allowed_tiers = ['free', 'pro', 'enterprise']
        if v not in allowed_tiers:
            raise ValueError(f'Subscription tier must be one of: {", ".join(allowed_tiers)}')
        return v

    @validator('slug')
    def validate_slug(cls, v):
        import re
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        return v

class TenantCreate(TenantBase):
    pass

class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    subscription_tier: Optional[str] = None
    max_load_balancers: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None

    @validator('subscription_tier')
    def validate_subscription_tier(cls, v):
        if v is None:
            return v
        allowed_tiers = ['free', 'pro', 'enterprise']
        if v not in allowed_tiers:
            raise ValueError(f'Subscription tier must be one of: {", ".join(allowed_tiers)}')
        return v

class TenantResponse(TenantBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TenantLimitsResponse(BaseModel):
    current_load_balancers: int
    max_load_balancers: int
    can_create_more: bool
    subscription_tier: str

class TenantUsageResponse(BaseModel):
    tenant_name: str
    total_load_balancers: int
    total_backends: int
    active_users: int
