from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, WebSocket
from sqlalchemy.orm import Session
from typing import List, Optional
from models.database import get_db
from models.load_balancer import LoadBalancer, BackendServer
from utils.lb_manager import LoadBalancerManager
from utils.schemas import LoadBalancerCreate, LoadBalancerResponse, BackendServerCreate
from ..services.load_balancer_service import delete_load_balancer
from ..auth import require_role
from routes.auth import router as auth_router
from routes.tenant import router as tenant_router
import asyncio
import aiohttp
import logging
from utils.audit import log_audit
from fastapi import Security
from ..auth import get_current_user
import subprocess
import tempfile
import os
import time
from fastapi.responses import JSONResponse
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship, joinedload
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import redis.asyncio as redis
import json
from typing import Optional, Any
from datetime import timedelta
from celery import Celery
from kombu import Queue
from celery import current_task
from .celery_app import celery_app
import aiohttp
import asyncio
from sqlalchemy.orm import sessionmaker
from models.database import engine
from models.load_balancer import BackendServer
import logging

app = FastAPI()
router = APIRouter()    
lb_manager = LoadBalancerManager()

audit_logger = logging.getLogger("audit")

def log_audit(action: str, user: str, resource: str, resource_id: int, details: dict = None):
    audit_logger.info({
        "action": action,       
        "user": user,
        "resource": resource,
        "resource_id": resource_id,
        "details": details or {}
    })

@router.post("/", response_model=LoadBalancerResponse)
async def create_load_balancer(
    lb_data: LoadBalancerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_tenant_access("user"))
):
    # Check tenant limits
    tenant_service = TenantService(db)
    limits = tenant_service.check_tenant_limits(user.tenant_id)
    
    if not limits["can_create_more"]:
        raise HTTPException(
            status_code=403, 
            detail=f"Tenant limit reached. Max {limits['max_load_balancers']} load balancers allowed."
        )
    
    # Create load balancer with tenant isolation
    lb_data_dict = lb_data.dict()
    lb_data_dict["tenant_id"] = user.tenant_id
    
    db_lb = LoadBalancer(**lb_data_dict)
    db.add(db_lb)
    db.commit()
    db.refresh(db_lb)
    
    # Generate HAProxy configuration
    await lb_manager.create_lb_config(db_lb)
    log_audit("create_lb", user.username, "load_balancer", db_lb.id, {"tenant_id": user.tenant_id})
    
    return db_lb

@router.get("/", response_model=List[LoadBalancerResponse])
async def list_load_balancers(
    db: Session = Depends(get_db),
    user: User = Depends(require_tenant_access("user"))
):
    # Only return load balancers for the user's tenant
    return db.query(LoadBalancer).filter(LoadBalancer.tenant_id == user.tenant_id).all()

@router.get("/{lb_id}", response_model=LoadBalancerResponse)
async def get_load_balancer(
    lb_id: int, 
    db: Session = Depends(get_db),
    user: User = Depends(require_tenant_access("user"))
):
    lb = db.query(LoadBalancer).filter(
        LoadBalancer.id == lb_id, 
        LoadBalancer.tenant_id == user.tenant_id
    ).first()
    if not lb:
        raise HTTPException(status_code=404, detail="Load balancer not found")
    return lb

@router.post("/{lb_id}/backends", dependencies=[Depends(require_role("admin"))])
async def add_backend_server(
    lb_id: int,
    backend_data: BackendServerCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    lb = db.query(LoadBalancer).filter(LoadBalancer.id == lb_id).first()
    if not lb:
        raise HTTPException(status_code=404, detail="Load balancer not found")
    backend = BackendServer(load_balancer_id=lb_id, **backend_data.dict())
    db.add(backend)
    db.commit()
    db.refresh(backend)
    await lb_manager.update_lb_config(lb)
    log_audit("add_backend", user.username, "load_balancer", lb_id, {"backend": backend_data.dict()})
    return backend

@router.delete("/{lb_id}/backends/{backend_id}", dependencies=[Depends(require_role("admin"))])
async def remove_backend_server(
    lb_id: int,
    backend_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    backend = db.query(BackendServer).filter(BackendServer.id == backend_id, BackendServer.load_balancer_id == lb_id).first()
    if not backend:
        raise HTTPException(status_code=404, detail="Backend not found")
    db.delete(backend)
    db.commit()
    lb = db.query(LoadBalancer).filter(LoadBalancer.id == lb_id).first()
    await lb_manager.update_lb_config(lb)
    log_audit("remove_backend", user.username, "load_balancer", lb_id, {"backend_id": backend_id})
    return {"detail": "Backend removed"}

@router.delete("/{lb_id}", dependencies=[Depends(require_role("admin"))])
def delete_lb(lb_id: str):
    if not delete_load_balancer(lb_id):
        raise HTTPException(status_code=404, detail="Load balancer not found")
    return {"detail": "Deleted"}

@router.get("/{lb_id}/metrics")
async def get_lb_metrics(lb_id: int, db: Session = Depends(get_db)):
    lb = db.query(LoadBalancer).filter(LoadBalancer.id == lb_id).first()
    if not lb:
        raise HTTPException(status_code=404, detail="Load balancer not found")
    healthy = sum(1 for s in lb.servers if s.healthy)
    unhealthy = len(lb.servers) - healthy
    return {
        "total_backends": len(lb.servers),
        "healthy_backends": healthy,
        "unhealthy_backends": unhealthy,
    }

@router.get("/{lb_id}/backends/health")
async def get_backends_health(lb_id: int, db: Session = Depends(get_db)):
    lb = db.query(LoadBalancer).filter(LoadBalancer.id == lb_id).first()
    if not lb:
        raise HTTPException(status_code=404, detail="Load balancer not found")
    return [
        {"ip": s.ip, "port": s.port, "healthy": s.healthy}
        for s in lb.servers
    ]

class HealthChecker:
    def __init__(self, db_session_factory, interval=10):
        self.db_session_factory = db_session_factory
        self.interval = interval
        self.running = False

    async def check_backend(self, backend):
        url = f"http://{backend.ip}:{backend.port}/health"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=2) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def run(self):
        self.running = True
        while self.running:
            async with self.db_session_factory() as db:
                backends = db.query(BackendServer).all()
                for backend in backends:
                    healthy = await self.check_backend(backend)
                    backend.healthy = healthy
                db.commit()
            await asyncio.sleep(self.interval)

    def stop(self):
        self.running = False

    async def create_lb_config(self, lb):
        # Generate config file content (implement as needed)
        config_content = self.generate_config(lb)
        config_path = f"/etc/haproxy/haproxy-{lb.id}.cfg"
        with open(config_path, "w") as f:
            f.write(config_content)
        await self.reload_haproxy(config_path)

    async def reload_haproxy(self, config_path):
        # Validate config before reload
        result = subprocess.run(["haproxy", "-c", "-f", config_path], capture_output=True)
        if result.returncode != 0:
            raise Exception(f"HAProxy config validation failed: {result.stderr.decode()}")
        # Reload HAProxy gracefully
        subprocess.run(["systemctl", "reload", "haproxy"])

@router.get("/audit/logs", dependencies=[Depends(require_role("admin"))])
def get_audit_logs(limit: int = 100):
    # Assuming audit logs are written to a file
    with open("/var/log/lbaas_audit.log") as f:
        lines = f.readlines()[-limit:]
    return [line.strip() for line in lines]

rate_limit_store = {}

@router.middleware("http")
async def rate_limiter(request: Request, call_next):
    user = request.state.user.username if hasattr(request.state, "user") else request.client.host
    now = time.time()
    window = 60  # seconds
    max_requests = 100
    history = rate_limit_store.get(user, [])
    history = [t for t in history if now - t < window]
    if len(history) >= max_requests:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    history.append(now)
    rate_limit_store[user] = history
    return await call_next(request)

@app.on_event("startup")
async def start_health_checker():
    checker = HealthChecker(db_session_factory=get_db, interval=10)
    asyncio.create_task(checker.run())

@router.websocket("/{lb_id}/ws/metrics")
async def websocket_metrics(lb_id: int, websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    while True:
        lb = db.query(LoadBalancer).filter(LoadBalancer.id == lb_id).first()
        if not lb:
            await websocket.send_json({"error": "Load balancer not found"})
            break
        healthy = sum(1 for s in lb.servers if s.healthy)
        unhealthy = len(lb.servers) - healthy
        await websocket.send_json({
            "total_backends": len(lb.servers),
            "healthy_backends": healthy,
            "unhealthy_backends": unhealthy,
        })
        await asyncio.sleep(5)

app.include_router(router, prefix="/api/v1/load-balancers", tags=["load-balancers"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(tenant_router, prefix="/api/v1/tenant", tags=["tenant"])

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    slug = Column(String, unique=True, index=True)  # URL-friendly identifier
    subscription_tier = Column(String, default="free")  # free, pro, enterprise
    max_load_balancers = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    users = relationship("User", back_populates="tenant")
    load_balancers = relationship("LoadBalancer", back_populates="tenant")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="user")  # user, admin, tenant_admin
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")

class LoadBalancer(Base):
    __tablename__ = "load_balancers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    algorithm = Column(String, default="roundrobin")  # roundrobin, leastconn, source
    port = Column(Integer, default=80)
    ssl_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    
    # Relationships
    tenant = relationship("Tenant", back_populates="load_balancers")
    servers = relationship("BackendServer", back_populates="load_balancer", cascade="all, delete-orphan")

class BackendServer(Base):
    __tablename__ = "backend_servers"
    
    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, index=True)
    port = Column(Integer, index=True)
    weight = Column(Integer, default=1)
    max_conns = Column(Integer, default=100)
    backup = Column(Boolean, default=False)
    monitor = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    load_balancer_id = Column(Integer, ForeignKey("load_balancers.id"))
    
    # Relationships
    load_balancer = relationship("LoadBalancer", back_populates="servers")

class TenantService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        return self.db.query(Tenant).filter(Tenant.slug == slug, Tenant.is_active == True).first()
    
    def create_tenant(self, tenant_data: dict) -> Tenant:
        tenant = Tenant(**tenant_data)
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant
    
    def check_tenant_limits(self, tenant_id: int) -> dict:
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        current_lbs = self.db.query(LoadBalancer).filter(LoadBalancer.tenant_id == tenant_id).count()
        
        return {
            "current_load_balancers": current_lbs,
            "max_load_balancers": tenant.max_load_balancers,
            "can_create_more": current_lbs < tenant.max_load_balancers,
            "subscription_tier": tenant.subscription_tier
        }
    
    def get_tenant_usage_metrics(self, tenant_id: int) -> dict:
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        load_balancers = self.db.query(LoadBalancer).filter(LoadBalancer.tenant_id == tenant_id).all()
        total_backends = sum(len(lb.servers) for lb in load_balancers)
        
        return {
            "tenant_name": tenant.name,
            "total_load_balancers": len(load_balancers),
            "total_backends": total_backends,
            "active_users": self.db.query(User).filter(User.tenant_id == tenant_id, User.is_active == True).count()
        }

from models.tenant import User, Tenant

async def get_current_user_with_tenant(token: str = Depends(oauth2_scheme)):
    user = await get_current_user(token)
    # Load tenant relationship
    user_with_tenant = db.query(User).options(joinedload(User.tenant)).filter(User.id == user.id).first()
    if not user_with_tenant.tenant or not user_with_tenant.tenant.is_active:
        raise HTTPException(status_code=403, detail="Tenant inactive or not found")
    return user_with_tenant

def require_tenant_access(required_role: str = "user"):
    def tenant_checker(user: User = Depends(get_current_user_with_tenant)):
        if user.role not in ["admin", "tenant_admin", required_role]:
            raise HTTPException(status_code=403, detail="Insufficient privileges")
        return user
    return tenant_checker

@router.get("/usage", summary="Get tenant usage metrics")
async def get_tenant_usage(
    db: Session = Depends(get_db),
    user: User = Depends(require_tenant_access("user"))
):
    tenant_service = TenantService(db)
    return tenant_service.get_tenant_usage_metrics(user.tenant_id)

@router.get("/limits", summary="Get tenant limits and current usage")
async def get_tenant_limits(
    db: Session = Depends(get_db),
    user: User = Depends(require_tenant_access("user"))
):
    tenant_service = TenantService(db)
    return tenant_service.check_tenant_limits(user.tenant_id)

@router.post("/", dependencies=[Depends(require_role("admin"))], summary="Create new tenant (admin only)")
async def create_tenant(
    tenant_data: dict,
    db: Session = Depends(get_db)
):
    tenant_service = TenantService(db)
    return tenant_service.create_tenant(tenant_data)

class CacheService:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """Cache a value with expiration"""
        return await self.redis.set(key, json.dumps(value), ex=expire)
    
    async def delete(self, key: str) -> bool:
        """Delete cached value"""
        return await self.redis.delete(key) > 0
    
    async def get_or_set(self, key: str, callable_func, expire: int = 3600):
        """Get from cache or execute function and cache result"""
        cached = await self.get(key)
        if cached is not None:
            return cached
        
        result = await callable_func() if asyncio.iscoroutinefunction(callable_func) else callable_func()
        await self.set(key, result, expire)
        return result
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching pattern"""
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

# Global cache instance
cache = CacheService()

celery_app = Celery(
    "lbaas_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["tasks.load_balancer_tasks", "tasks.health_check_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "tasks.health_check_tasks.check_backend_health": {"queue": "health_checks"},
        "tasks.load_balancer_tasks.*": {"queue": "lb_operations"},
    },
    task_queues=(
        Queue("health_checks", routing_key="health_checks"),
        Queue("lb_operations", routing_key="lb_operations"),
        Queue("default", routing_key="default"),
    ),
)

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def check_backend_health(self, backend_id: int):
    """Check health of a specific backend server"""
    try:
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        backend = db.query(BackendServer).filter(BackendServer.id == backend_id).first()
        if not backend:
            return {"status": "error", "message": "Backend not found"}
        
        # Perform health check
        url = f"http://{backend.ip}:{backend.port}/health"
        
        async def check():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        return resp.status == 200
            except Exception as e:
                logger.error(f"Health check failed for {url}: {e}")
                return False
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_healthy = loop.run_until_complete(check())
        loop.close()
        
        # Update database
        backend.healthy = is_healthy
        db.commit()
        db.close()
        
        return {
            "status": "success",
            "backend_id": backend_id,
            "healthy": is_healthy,
            "url": url
        }
        
    except Exception as e:
        logger.error(f"Health check task failed: {e}")
        return {"status": "error", "message": str(e)}

@celery_app.task
def bulk_health_check():
    """Check health of all backend servers"""
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    backends = db.query(BackendServer).all()
    task_ids = []
    
    for backend in backends:
        task = check_backend_health.delay(backend.id)
        task_ids.append(task.id)
    
    db.close()
    return {"message": f"Queued {len(task_ids)} health checks", "task_ids": task_ids}