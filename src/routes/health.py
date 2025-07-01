from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.database import get_db
from models.load_balancer import LoadBalancer, BackendServer
from schemas.metrics import HealthStatus, SystemMetrics
from typing import Dict, Any
import psutil
import redis
from datetime import datetime

router = APIRouter()

@router.get("/", response_model=HealthStatus)
async def health_check():
    """Basic health check endpoint"""
    return HealthStatus(
        status="healthy",
        message="Load Balancer Service is operational",
        details={
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    )

@router.get("/detailed", response_model=Dict[str, Any])
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check including database and external services"""
    health_details = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    # Check database
    try:
        db.execute("SELECT 1")
        health_details["services"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_details["services"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
        health_details["status"] = "degraded"
    
    # Check Redis
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        health_details["services"]["redis"] = {
            "status": "healthy",
            "message": "Redis connection successful"
        }
    except Exception as e:
        health_details["services"]["redis"] = {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}"
        }
        health_details["status"] = "degraded"
    
    # Check system resources
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        health_details["services"]["system"] = {
            "status": "healthy",
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk.percent
        }
        
        # Mark as degraded if resources are high
        if cpu_percent > 80 or memory.percent > 80 or disk.percent > 90:
            health_details["services"]["system"]["status"] = "degraded"
            health_details["status"] = "degraded"
            
    except Exception as e:
        health_details["services"]["system"] = {
            "status": "unhealthy",
            "message": f"System metrics unavailable: {str(e)}"
        }
        health_details["status"] = "degraded"
    
    return health_details

@router.get("/readiness")
async def readiness_check(db: Session = Depends(get_db)):
    """Kubernetes readiness probe endpoint"""
    try:
        # Check if we can query the database
        db.execute("SELECT 1")
        return {"status": "ready"}
    except Exception:
        raise HTTPException(status_code=503, detail="Service not ready")

@router.get("/liveness")
async def liveness_check():
    """Kubernetes liveness probe endpoint"""
    return {"status": "alive"}

@router.get("/system", response_model=SystemMetrics)
async def get_system_metrics(db: Session = Depends(get_db)):
    """Get comprehensive system metrics"""
    try:
        # Database metrics
        total_lbs = db.query(LoadBalancer).count()
        total_backends = db.query(BackendServer).count()
        healthy_backends = db.query(BackendServer).filter(BackendServer.healthy == True).count()
        
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()
        
        return SystemMetrics(
            total_load_balancers=total_lbs,
            total_backends=total_backends,
            total_healthy_backends=healthy_backends,
            total_requests=0,  # This would come from metrics store
            average_response_time=0.0,  # This would come from metrics store
            overall_error_rate=0.0,  # This would come from metrics store
            cpu_usage=cpu_percent,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            network_in=network.bytes_recv,
            network_out=network.bytes_sent,
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve system metrics: {str(e)}")
