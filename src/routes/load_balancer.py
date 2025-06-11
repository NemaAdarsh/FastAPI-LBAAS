from fastapi import FastAPI, APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from models.database import get_db
from models.load_balancer import LoadBalancer, BackendServer
from utils.lb_manager import LoadBalancerManager
from utils.schemas import LoadBalancerCreate, LoadBalancerResponse, BackendServerCreate
from ..services.load_balancer_service import delete_load_balancer
from ..auth import require_role
from routes.auth import router as auth_router
import asyncio
import aiohttp
import logging
from utils.audit import log_audit
from fastapi import Security
from ..auth import get_current_user

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
    db: Session = Depends(get_db)
):
    # Create load balancer in database
    db_lb = LoadBalancer(**lb_data.dict())
    db.add(db_lb)
    db.commit()
    db.refresh(db_lb)
    
    # Generate HAProxy configuration
    await lb_manager.create_lb_config(db_lb)
    
    return db_lb

@router.get("/", response_model=List[LoadBalancerResponse])
async def list_load_balancers(db: Session = Depends(get_db)):
    return db.query(LoadBalancer).all()

@router.get("/{lb_id}", response_model=LoadBalancerResponse)
async def get_load_balancer(lb_id: int, db: Session = Depends(get_db)):
    lb = db.query(LoadBalancer).filter(LoadBalancer.id == lb_id).first()
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

app.include_router(router, prefix="/api/v1/load-balancers", tags=["load-balancers"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])