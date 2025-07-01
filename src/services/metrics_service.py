from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import redis
import json
from models.load_balancer import LoadBalancer, BackendServer
from schemas.metrics import (
    LoadBalancerMetrics,
    BackendMetrics, 
    SystemMetrics,
    MetricsResponse
)

class MetricsService:
    def __init__(self, db: Session, redis_client=None):
        self.db = db
        self.redis = redis_client or redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
    
    def get_load_balancer_metrics(self, lb_id: int, period: str = "1h") -> LoadBalancerMetrics:
        """Get comprehensive metrics for a load balancer"""
        lb = self.db.query(LoadBalancer).filter(LoadBalancer.id == lb_id).first()
        if not lb:
            raise ValueError("Load balancer not found")
        
        # Get backend metrics
        backend_metrics = []
        healthy_count = 0
        total_requests = 0
        total_response_time = 0.0
        
        for backend in lb.servers:
            backend_metric = self._get_backend_metric(backend, period)
            backend_metrics.append(backend_metric)
            
            if backend.healthy:
                healthy_count += 1
            
            total_requests += backend_metric.requests
            total_response_time += backend_metric.response_time
        
        total_backends = len(lb.servers)
        avg_response_time = total_response_time / total_backends if total_backends > 0 else 0.0
        health_percentage = (healthy_count / total_backends * 100) if total_backends > 0 else 100
        
        return LoadBalancerMetrics(
            load_balancer_id=lb.id,
            name=lb.name,
            total_backends=total_backends,
            healthy_backends=healthy_count,
            unhealthy_backends=total_backends - healthy_count,
            overall_health_percentage=health_percentage,
            total_requests=total_requests,
            active_connections=self._get_active_connections(lb_id),
            average_response_time=avg_response_time,
            error_rate=self._get_error_rate(lb_id, period),
            backends=backend_metrics,
            timestamp=datetime.utcnow()
        )
    
    def get_backend_metrics(self, lb_id: int, period: str = "1h") -> List[BackendMetrics]:
        """Get metrics for all backends of a load balancer"""
        lb = self.db.query(LoadBalancer).filter(LoadBalancer.id == lb_id).first()
        if not lb:
            raise ValueError("Load balancer not found")
        
        return [self._get_backend_metric(backend, period) for backend in lb.servers]
    
    def get_single_backend_metrics(self, backend_id: int, period: str = "1h") -> BackendMetrics:
        """Get metrics for a specific backend"""
        backend = self.db.query(BackendServer).filter(BackendServer.id == backend_id).first()
        if not backend:
            raise ValueError("Backend not found")
        
        return self._get_backend_metric(backend, period)
    
    def get_system_metrics(self, period: str = "1h") -> SystemMetrics:
        """Get system-wide metrics"""
        import psutil
        
        # Database counts
        total_lbs = self.db.query(LoadBalancer).count()
        total_backends = self.db.query(BackendServer).count()
        healthy_backends = self.db.query(BackendServer).filter(BackendServer.healthy == True).count()
        
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()
        
        return SystemMetrics(
            total_load_balancers=total_lbs,
            total_backends=total_backends,
            total_healthy_backends=healthy_backends,
            total_requests=self._get_total_requests(period),
            average_response_time=self._get_global_avg_response_time(period),
            overall_error_rate=self._get_global_error_rate(period),
            cpu_usage=cpu_percent,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            network_in=network.bytes_recv,
            network_out=network.bytes_sent,
            timestamp=datetime.utcnow()
        )
    
    def _get_backend_metric(self, backend: BackendServer, period: str) -> BackendMetrics:
        """Get metrics for a single backend"""
        # In a real implementation, this would query your metrics store
        # For now, return mock data with some realistic values
        
        metric_key = f"backend:{backend.id}:metrics:{period}"
        
        try:
            cached_metrics = self.redis.get(metric_key)
            if cached_metrics:
                data = json.loads(cached_metrics)
                return BackendMetrics(**data)
        except:
            pass  # Fallback to generating new metrics
        
        # Generate realistic mock data
        requests = 100 if backend.healthy else 10
        response_time = 0.05 if backend.healthy else 2.0
        error_count = 0 if backend.healthy else 5
        
        metrics = BackendMetrics(
            backend_id=backend.id,
            ip=backend.ip,
            port=backend.port,
            healthy=backend.healthy,
            requests=requests,
            active_connections=10 if backend.healthy else 0,
            response_time=response_time,
            last_response_time=response_time,
            error_count=error_count,
            last_check=datetime.utcnow()
        )
        
        # Cache for 60 seconds
        try:
            self.redis.setex(metric_key, 60, json.dumps(metrics.dict(), default=str))
        except:
            pass  # Redis not available, continue without caching
        
        return metrics
    
    def _get_active_connections(self, lb_id: int) -> int:
        """Get active connections for a load balancer"""
        # Mock implementation
        return 25
    
    def _get_error_rate(self, lb_id: int, period: str) -> float:
        """Get error rate for a load balancer"""
        # Mock implementation
        return 0.5
    
    def _get_total_requests(self, period: str) -> int:
        """Get total requests across all load balancers"""
        # Mock implementation
        return 10000
    
    def _get_global_avg_response_time(self, period: str) -> float:
        """Get global average response time"""
        # Mock implementation
        return 0.15
    
    def _get_global_error_rate(self, period: str) -> float:
        """Get global error rate"""
        # Mock implementation
        return 1.2

# Legacy functions for backwards compatibility
def get_metrics(lb_id: str):
    """Legacy function for backwards compatibility"""
    return {
        "lb_id": lb_id,
        "requests_per_second": 100,
        "active_connections": 50,
        "error_rate": 0.01
    }

def update_metrics(lb_id: str, metrics: dict = None):
    """Legacy function for backwards compatibility"""
    return True