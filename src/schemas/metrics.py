from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

class MetricsBase(BaseModel):
    load_balancer_id: int
    total_requests: int = 0
    active_connections: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    response_time_avg: float = 0.0
    error_rate: float = Field(0.0, ge=0.0, le=100.0)

class MetricsResponse(MetricsBase):
    timestamp: datetime
    
    class Config:
        from_attributes = True

class BackendMetrics(BaseModel):
    backend_id: int
    ip: str
    port: int
    healthy: bool
    requests: int = 0
    active_connections: int = 0
    response_time: float = 0.0
    last_response_time: Optional[float] = None
    error_count: int = 0
    last_check: datetime

class LoadBalancerMetrics(BaseModel):
    load_balancer_id: int
    name: str
    total_backends: int
    healthy_backends: int
    unhealthy_backends: int
    overall_health_percentage: float
    total_requests: int
    active_connections: int
    average_response_time: float
    error_rate: float
    backends: list[BackendMetrics]
    timestamp: datetime

class SystemMetrics(BaseModel):
    total_load_balancers: int
    total_backends: int
    total_healthy_backends: int
    total_requests: int
    average_response_time: float
    overall_error_rate: float
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_in: int
    network_out: int
    timestamp: datetime

class HealthStatus(BaseModel):
    status: str = Field(..., regex="^(healthy|unhealthy|degraded)$")
    message: str
    details: Dict[str, Any] = {}

class AuditLogEntry(BaseModel):
    id: int
    action: str
    user: str
    resource: str
    resource_id: int
    details: Dict[str, Any]
    timestamp: datetime
    ip_address: Optional[str] = None

class AuditLogsResponse(BaseModel):
    logs: list[AuditLogEntry]
    total: int
    page: int
    per_page: int
    
class AlertRule(BaseModel):
    name: str
    condition: str  # e.g., "error_rate > 5"
    threshold: float
    enabled: bool = True
    
class AlertResponse(BaseModel):
    id: int
    rule: AlertRule
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    message: str
from typing import Dict

class LoadBalancerMetrics(BaseModel):
    lb_id: str
    total_requests: int
    healthy_backends: int
    unhealthy_backends: int
    custom_metrics: Dict[str, float] = {}