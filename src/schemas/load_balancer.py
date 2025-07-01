from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime

class BackendServerBase(BaseModel):
    ip: str = Field(..., description="IP address of the backend server")
    port: int = Field(..., ge=1, le=65535, description="Port number")
    weight: int = Field(1, ge=1, le=100, description="Weight for load balancing")
    max_conns: int = Field(100, ge=1, description="Maximum connections")
    backup: bool = Field(False, description="Whether this is a backup server")
    monitor: bool = Field(True, description="Whether to monitor this server")

class BackendServerCreate(BackendServerBase):
    pass

class BackendServerUpdate(BaseModel):
    ip: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    weight: Optional[int] = Field(None, ge=1, le=100)
    max_conns: Optional[int] = Field(None, ge=1)
    backup: Optional[bool] = None
    monitor: Optional[bool] = None

class BackendServerResponse(BackendServerBase):
    id: int
    healthy: bool = True
    created_at: datetime
    updated_at: datetime
    load_balancer_id: int

    class Config:
        from_attributes = True

class LoadBalancerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Load balancer name")
    algorithm: str = Field("roundrobin", description="Load balancing algorithm")
    port: int = Field(80, ge=1, le=65535, description="Port number")
    ssl_enabled: bool = Field(False, description="Whether SSL is enabled")

    @validator('algorithm')
    def validate_algorithm(cls, v):
        allowed_algorithms = ['roundrobin', 'leastconn', 'source', 'uri', 'static-rr']
        if v not in allowed_algorithms:
            raise ValueError(f'Algorithm must be one of: {", ".join(allowed_algorithms)}')
        return v

class LoadBalancerCreate(LoadBalancerBase):
    pass

class LoadBalancerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    algorithm: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    ssl_enabled: Optional[bool] = None

    @validator('algorithm')
    def validate_algorithm(cls, v):
        if v is None:
            return v
        allowed_algorithms = ['roundrobin', 'leastconn', 'source', 'uri', 'static-rr']
        if v not in allowed_algorithms:
            raise ValueError(f'Algorithm must be one of: {", ".join(allowed_algorithms)}')
        return v

class LoadBalancerResponse(LoadBalancerBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime
    servers: List[BackendServerResponse] = []

    class Config:
        from_attributes = True

class LoadBalancerStats(BaseModel):
    total_requests: int = 0
    active_connections: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    response_time_avg: float = 0.0
    error_rate: float = 0.0

class LoadBalancerMetrics(BaseModel):
    load_balancer_id: int
    total_backends: int
    healthy_backends: int
    unhealthy_backends: int
    stats: LoadBalancerStats
    timestamp: datetime

class HealthCheckResponse(BaseModel):
    backend_id: int
    ip: str
    port: int
    healthy: bool
    response_time: Optional[float] = None
    last_check: datetime