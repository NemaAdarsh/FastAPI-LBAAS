from pydantic import BaseModel
from typing import List, Optional
from models.load_balancer import LoadBalancingAlgorithm
from datetime import datetime

class BackendServerBase(BaseModel):
    host: str
    port: int
    weight: Optional[int] = 1

class BackendServerCreate(BackendServerBase):
    pass

class BackendServerResponse(BackendServerBase):
    id: int
    is_healthy: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class LoadBalancerBase(BaseModel):
    name: str
    frontend_port: int
    algorithm: Optional[LoadBalancingAlgorithm] = LoadBalancingAlgorithm.ROUND_ROBIN

class LoadBalancerCreate(LoadBalancerBase):
    pass

class LoadBalancerResponse(LoadBalancerBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    backend_servers: List[BackendServerResponse] = []
    
    class Config:
        from_attributes = True