from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from models.database import get_db
from models.load_balancer import LoadBalancer, BackendServer
from schemas.metrics import (
    MetricsResponse,
    LoadBalancerMetrics,
    BackendMetrics,
    SystemMetrics,
    AuditLogsResponse,
    AuditLogEntry
)
from auth import require_role, require_tenant_access, get_current_user
from services.metrics_service import MetricsService
from utils.audit import get_audit_logs

router = APIRouter()

@router.get("/load-balancer/{lb_id}", response_model=LoadBalancerMetrics)
async def get_load_balancer_metrics(
    lb_id: int,
    period: str = Query("1h", regex="^(5m|15m|1h|6h|24h|7d)$", description="Time period for metrics"),
    db: Session = Depends(get_db),
    user = Depends(require_tenant_access("user"))
):
    """Get comprehensive metrics for a specific load balancer"""
    # Verify load balancer exists and user has access
    lb = db.query(LoadBalancer).filter(
        LoadBalancer.id == lb_id,
        LoadBalancer.tenant_id == user.tenant_id
    ).first()
    
    if not lb:
        raise HTTPException(status_code=404, detail="Load balancer not found")
    
    metrics_service = MetricsService(db)
    return metrics_service.get_load_balancer_metrics(lb_id, period)

@router.get("/load-balancer/{lb_id}/backends", response_model=List[BackendMetrics])
async def get_backend_metrics(
    lb_id: int,
    period: str = Query("1h", regex="^(5m|15m|1h|6h|24h|7d)$"),
    db: Session = Depends(get_db),
    user = Depends(require_tenant_access("user"))
):
    """Get metrics for all backends of a load balancer"""
    lb = db.query(LoadBalancer).filter(
        LoadBalancer.id == lb_id,
        LoadBalancer.tenant_id == user.tenant_id
    ).first()
    
    if not lb:
        raise HTTPException(status_code=404, detail="Load balancer not found")
    
    metrics_service = MetricsService(db)
    return metrics_service.get_backend_metrics(lb_id, period)

@router.get("/load-balancer/{lb_id}/backend/{backend_id}", response_model=BackendMetrics)
async def get_single_backend_metrics(
    lb_id: int,
    backend_id: int,
    period: str = Query("1h", regex="^(5m|15m|1h|6h|24h|7d)$"),
    db: Session = Depends(get_db),
    user = Depends(require_tenant_access("user"))
):
    """Get metrics for a specific backend server"""
    # Verify backend exists and belongs to user's tenant
    backend = db.query(BackendServer).join(LoadBalancer).filter(
        BackendServer.id == backend_id,
        BackendServer.load_balancer_id == lb_id,
        LoadBalancer.tenant_id == user.tenant_id
    ).first()
    
    if not backend:
        raise HTTPException(status_code=404, detail="Backend server not found")
    
    metrics_service = MetricsService(db)
    return metrics_service.get_single_backend_metrics(backend_id, period)

@router.get("/system", response_model=SystemMetrics, dependencies=[Depends(require_role("admin"))])
async def get_system_metrics(
    period: str = Query("1h", regex="^(5m|15m|1h|6h|24h|7d)$"),
    db: Session = Depends(get_db)
):
    """Get system-wide metrics (admin only)"""
    metrics_service = MetricsService(db)
    return metrics_service.get_system_metrics(period)

@router.get("/tenant/overview", response_model=dict)
async def get_tenant_metrics_overview(
    db: Session = Depends(get_db),
    user = Depends(require_tenant_access("user"))
):
    """Get overview metrics for current tenant"""
    # Get basic counts
    total_lbs = db.query(LoadBalancer).filter(LoadBalancer.tenant_id == user.tenant_id).count()
    
    # Get health summary
    healthy_backends = 0
    total_backends = 0
    
    for lb in db.query(LoadBalancer).filter(LoadBalancer.tenant_id == user.tenant_id).all():
        for backend in lb.servers:
            total_backends += 1
            if backend.healthy:
                healthy_backends += 1
    
    health_percentage = (healthy_backends / total_backends * 100) if total_backends > 0 else 100
    
    return {
        "total_load_balancers": total_lbs,
        "total_backends": total_backends,
        "healthy_backends": healthy_backends,
        "health_percentage": round(health_percentage, 2),
        "status": "healthy" if health_percentage >= 80 else "degraded" if health_percentage >= 50 else "critical",
        "timestamp": datetime.utcnow()
    }

@router.get("/audit/logs", response_model=AuditLogsResponse)
async def get_audit_logs_paginated(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    user_filter = Depends(require_role("admin"))
):
    """Get paginated audit logs (admin only)"""
    logs, total = get_audit_logs(
        page=page,
        per_page=per_page,
        action=action,
        resource=resource,
        start_date=start_date,
        end_date=end_date
    )
    
    return AuditLogsResponse(
        logs=logs,
        total=total,
        page=page,
        per_page=per_page
    )

@router.post("/refresh/{lb_id}")
async def refresh_metrics(
    lb_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user = Depends(require_tenant_access("user"))
):
    """Trigger metrics refresh for a load balancer"""
    lb = db.query(LoadBalancer).filter(
        LoadBalancer.id == lb_id,
        LoadBalancer.tenant_id == user.tenant_id
    ).first()
    
    if not lb:
        raise HTTPException(status_code=404, detail="Load balancer not found")
    
    # Add background task to refresh metrics
    background_tasks.add_task(refresh_lb_metrics, lb_id)
    
    return {"detail": "Metrics refresh queued", "load_balancer_id": lb_id}

@router.get("/alerts/{lb_id}")
async def get_load_balancer_alerts(
    lb_id: int,
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    user = Depends(require_tenant_access("user"))
):
    """Get alerts for a specific load balancer"""
    lb = db.query(LoadBalancer).filter(
        LoadBalancer.id == lb_id,
        LoadBalancer.tenant_id == user.tenant_id
    ).first()
    
    if not lb:
        raise HTTPException(status_code=404, detail="Load balancer not found")
    
    # This would integrate with an alerting system
    # For now, return mock alerts based on health status
    alerts = []
    
    for backend in lb.servers:
        if not backend.healthy:
            alerts.append({
                "id": f"backend_{backend.id}_down",
                "type": "backend_down",
                "severity": "critical",
                "message": f"Backend {backend.ip}:{backend.port} is unhealthy",
                "triggered_at": datetime.utcnow() - timedelta(minutes=5),
                "resolved_at": None,
                "backend_id": backend.id
            })
    
    if active_only:
        alerts = [alert for alert in alerts if alert["resolved_at"] is None]
    
    return {"alerts": alerts, "count": len(alerts)}

def refresh_lb_metrics(lb_id: int):
    """Background task to refresh load balancer metrics"""
    # This would trigger metric collection
    # Implementation depends on your metrics collection system
    pass