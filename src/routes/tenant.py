from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from models.database import get_db
from schemas.tenant import (
    TenantCreate, 
    TenantUpdate, 
    TenantResponse, 
    TenantLimitsResponse, 
    TenantUsageResponse
)
from auth import require_role, require_tenant_access, get_current_user
from models.load_balancer import User, Tenant, LoadBalancer
from services.tenant_service import TenantService

router = APIRouter()

@router.post("/", response_model=TenantResponse, dependencies=[Depends(require_role("admin"))])
async def create_tenant(
    tenant_data: TenantCreate,
    db: Session = Depends(get_db)
):
    """Create a new tenant (admin only)"""
    tenant_service = TenantService(db)
    
    # Check if slug already exists
    existing = tenant_service.get_tenant_by_slug(tenant_data.slug)
    if existing:
        raise HTTPException(status_code=400, detail="Tenant slug already exists")
    
    return tenant_service.create_tenant(tenant_data.dict())

@router.get("/", response_model=List[TenantResponse], dependencies=[Depends(require_role("admin"))])
async def list_tenants(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    active_only: bool = Query(True, description="Filter by active tenants only"),
    db: Session = Depends(get_db)
):
    """List all tenants (admin only)"""
    query = db.query(Tenant)
    
    if active_only:
        query = query.filter(Tenant.is_active == True)
    
    return query.offset(skip).limit(limit).all()

@router.get("/{tenant_id}", response_model=TenantResponse, dependencies=[Depends(require_role("admin"))])
async def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    """Get tenant by ID (admin only)"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant

@router.put("/{tenant_id}", response_model=TenantResponse, dependencies=[Depends(require_role("admin"))])
async def update_tenant(
    tenant_id: int,
    tenant_update: TenantUpdate,
    db: Session = Depends(get_db)
):
    """Update tenant (admin only)"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    update_data = tenant_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
    
    db.commit()
    db.refresh(tenant)
    return tenant

@router.delete("/{tenant_id}", dependencies=[Depends(require_role("admin"))])
async def delete_tenant(
    tenant_id: int,
    force: bool = Query(False, description="Force deletion even if tenant has resources"),
    db: Session = Depends(get_db)
):
    """Delete tenant (admin only)"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Check if tenant has resources
    lb_count = db.query(LoadBalancer).filter(LoadBalancer.tenant_id == tenant_id).count()
    user_count = db.query(User).filter(User.tenant_id == tenant_id).count()
    
    if (lb_count > 0 or user_count > 0) and not force:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete tenant with {lb_count} load balancers and {user_count} users. Use force=true to override."
        )
    
    # Soft delete by marking as inactive
    tenant.is_active = False
    db.commit()
    
    return {"detail": "Tenant deleted successfully"}

@router.get("/current/info", response_model=TenantResponse)
async def get_current_tenant_info(
    user: User = Depends(require_tenant_access("user"))
):
    """Get current user's tenant information"""
    if not user.tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return user.tenant

@router.get("/current/usage", response_model=TenantUsageResponse)
async def get_current_tenant_usage(
    db: Session = Depends(get_db),
    user: User = Depends(require_tenant_access("user"))
):
    """Get current tenant usage metrics"""
    tenant_service = TenantService(db)
    return tenant_service.get_tenant_usage_metrics(user.tenant_id)

@router.get("/current/limits", response_model=TenantLimitsResponse)
async def get_current_tenant_limits(
    db: Session = Depends(get_db),
    user: User = Depends(require_tenant_access("user"))
):
    """Get current tenant limits and usage"""
    tenant_service = TenantService(db)
    return tenant_service.check_tenant_limits(user.tenant_id)

@router.put("/current/info", response_model=TenantResponse)
async def update_current_tenant(
    tenant_update: TenantUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_tenant_access("tenant_admin"))
):
    """Update current tenant (tenant admin only)"""
    tenant = user.tenant
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Tenant admins can only update certain fields
    allowed_fields = ["name"]
    update_data = {k: v for k, v in tenant_update.dict(exclude_unset=True).items() 
                   if k in allowed_fields}
    
    for field, value in update_data.items():
        setattr(tenant, field, value)
    
    db.commit()
    db.refresh(tenant)
    return tenant

@router.get("/{tenant_id}/users", response_model=List[dict], dependencies=[Depends(require_role("admin"))])
async def get_tenant_users(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    """Get all users for a tenant (admin only)"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    users = db.query(User).filter(User.tenant_id == tenant_id).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active
        }
        for user in users
    ]

@router.get("/{tenant_id}/load-balancers", response_model=List[dict], dependencies=[Depends(require_role("admin"))])
async def get_tenant_load_balancers(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    """Get all load balancers for a tenant (admin only)"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    load_balancers = db.query(LoadBalancer).filter(LoadBalancer.tenant_id == tenant_id).all()
    return [
        {
            "id": lb.id,
            "name": lb.name,
            "algorithm": lb.algorithm,
            "port": lb.port,
            "ssl_enabled": lb.ssl_enabled,
            "created_at": lb.created_at,
            "backend_count": len(lb.servers)
        }
        for lb in load_balancers
    ]
