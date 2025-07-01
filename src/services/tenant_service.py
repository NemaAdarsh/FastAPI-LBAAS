from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from fastapi import HTTPException
from models.load_balancer import Tenant, User, LoadBalancer
from schemas.tenant import TenantCreate, TenantUpdate

class TenantService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug"""
        return self.db.query(Tenant).filter(
            Tenant.slug == slug, 
            Tenant.is_active == True
        ).first()
    
    def get_tenant_by_id(self, tenant_id: int) -> Optional[Tenant]:
        """Get tenant by ID"""
        return self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
    
    def create_tenant(self, tenant_data: Dict[str, Any]) -> Tenant:
        """Create a new tenant"""
        # Validate subscription tier limits
        if tenant_data.get("subscription_tier") == "free":
            tenant_data["max_load_balancers"] = 5
        elif tenant_data.get("subscription_tier") == "pro":
            tenant_data["max_load_balancers"] = 25
        elif tenant_data.get("subscription_tier") == "enterprise":
            tenant_data["max_load_balancers"] = 100
        
        tenant = Tenant(**tenant_data)
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant
    
    def update_tenant(self, tenant_id: int, tenant_data: Dict[str, Any]) -> Tenant:
        """Update an existing tenant"""
        tenant = self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        for field, value in tenant_data.items():
            setattr(tenant, field, value)
        
        self.db.commit()
        self.db.refresh(tenant)
        return tenant
    
    def check_tenant_limits(self, tenant_id: int) -> Dict[str, Any]:
        """Check tenant limits and current usage"""
        tenant = self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        current_lbs = self.db.query(LoadBalancer).filter(
            LoadBalancer.tenant_id == tenant_id
        ).count()
        
        return {
            "current_load_balancers": current_lbs,
            "max_load_balancers": tenant.max_load_balancers,
            "can_create_more": current_lbs < tenant.max_load_balancers,
            "subscription_tier": tenant.subscription_tier
        }
    
    def get_tenant_usage_metrics(self, tenant_id: int) -> Dict[str, Any]:
        """Get comprehensive usage metrics for a tenant"""
        tenant = self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Load balancer metrics
        load_balancers = self.db.query(LoadBalancer).filter(
            LoadBalancer.tenant_id == tenant_id
        ).all()
        
        total_backends = sum(len(lb.servers) for lb in load_balancers)
        healthy_backends = sum(
            sum(1 for server in lb.servers if server.healthy) 
            for lb in load_balancers
        )
        
        # User metrics
        active_users = self.db.query(User).filter(
            User.tenant_id == tenant_id,
            User.is_active == True
        ).count()
        
        total_users = self.db.query(User).filter(
            User.tenant_id == tenant_id
        ).count()
        
        return {
            "tenant_name": tenant.name,
            "total_load_balancers": len(load_balancers),
            "total_backends": total_backends,
            "healthy_backends": healthy_backends,
            "backend_health_percentage": (
                (healthy_backends / total_backends * 100) 
                if total_backends > 0 else 100
            ),
            "active_users": active_users,
            "total_users": total_users,
            "subscription_tier": tenant.subscription_tier,
            "max_load_balancers": tenant.max_load_balancers,
            "usage_percentage": (
                (len(load_balancers) / tenant.max_load_balancers * 100) 
                if tenant.max_load_balancers > 0 else 0
            )
        }
    
    def is_tenant_limit_reached(self, tenant_id: int) -> bool:
        """Check if tenant has reached their load balancer limit"""
        limits = self.check_tenant_limits(tenant_id)
        return not limits["can_create_more"]
    
    def get_tenant_load_balancers(self, tenant_id: int) -> list:
        """Get all load balancers for a tenant"""
        return self.db.query(LoadBalancer).filter(
            LoadBalancer.tenant_id == tenant_id
        ).all()
    
    def get_tenant_users(self, tenant_id: int) -> list:
        """Get all users for a tenant"""
        return self.db.query(User).filter(
            User.tenant_id == tenant_id
        ).all()
    
    def validate_tenant_access(self, user_tenant_id: int, resource_tenant_id: int) -> bool:
        """Validate that a user can access a resource based on tenant isolation"""
        return user_tenant_id == resource_tenant_id
    
    def get_subscription_tier_limits(self, tier: str) -> Dict[str, int]:
        """Get limits for a subscription tier"""
        limits = {
            "free": {
                "max_load_balancers": 5,
                "max_backends_per_lb": 3,
                "max_users": 2,
                "ssl_enabled": False,
                "custom_algorithms": False
            },
            "pro": {
                "max_load_balancers": 25,
                "max_backends_per_lb": 10,
                "max_users": 10,
                "ssl_enabled": True,
                "custom_algorithms": True
            },
            "enterprise": {
                "max_load_balancers": 100,
                "max_backends_per_lb": 50,
                "max_users": 50,
                "ssl_enabled": True,
                "custom_algorithms": True
            }
        }
        return limits.get(tier, limits["free"])
    
    def upgrade_subscription(self, tenant_id: int, new_tier: str) -> Tenant:
        """Upgrade tenant subscription tier"""
        tenant = self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Validate tier
        valid_tiers = ["free", "pro", "enterprise"]
        if new_tier not in valid_tiers:
            raise HTTPException(status_code=400, detail="Invalid subscription tier")
        
        # Get new limits
        new_limits = self.get_subscription_tier_limits(new_tier)
        
        # Update tenant
        tenant.subscription_tier = new_tier
        tenant.max_load_balancers = new_limits["max_load_balancers"]
        
        self.db.commit()
        self.db.refresh(tenant)
        
        return tenant
    
    def deactivate_tenant(self, tenant_id: int) -> bool:
        """Deactivate a tenant (soft delete)"""
        tenant = self.get_tenant_by_id(tenant_id)
        if not tenant:
            return False
        
        tenant.is_active = False
        self.db.commit()
        
        return True
    
    def get_tenant_statistics(self, tenant_id: int) -> Dict[str, Any]:
        """Get detailed statistics for a tenant"""
        tenant = self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Get load balancers with their backends
        load_balancers = self.db.query(LoadBalancer).filter(
            LoadBalancer.tenant_id == tenant_id
        ).all()
        
        # Calculate statistics
        total_lbs = len(load_balancers)
        active_lbs = sum(1 for lb in load_balancers if len(lb.servers) > 0)
        
        algorithms_used = {}
        total_backends = 0
        healthy_backends = 0
        ssl_enabled_count = 0
        
        for lb in load_balancers:
            # Algorithm statistics
            algo = lb.algorithm
            algorithms_used[algo] = algorithms_used.get(algo, 0) + 1
            
            # Backend statistics
            total_backends += len(lb.servers)
            healthy_backends += sum(1 for server in lb.servers if server.healthy)
            
            # SSL statistics
            if lb.ssl_enabled:
                ssl_enabled_count += 1
        
        return {
            "tenant_id": tenant_id,
            "tenant_name": tenant.name,
            "subscription_tier": tenant.subscription_tier,
            "total_load_balancers": total_lbs,
            "active_load_balancers": active_lbs,
            "inactive_load_balancers": total_lbs - active_lbs,
            "total_backends": total_backends,
            "healthy_backends": healthy_backends,
            "unhealthy_backends": total_backends - healthy_backends,
            "ssl_enabled_count": ssl_enabled_count,
            "algorithms_used": algorithms_used,
            "usage_percentage": (total_lbs / tenant.max_load_balancers * 100) if tenant.max_load_balancers > 0 else 0,
            "health_percentage": (healthy_backends / total_backends * 100) if total_backends > 0 else 100
        }
