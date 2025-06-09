from pydantic import BaseModel
from typing import List, Optional

class BackendServer(BaseModel):
    ip: str
    port: int
    healthy: bool = True

class LoadBalancer(BaseModel):
    id: str
    name: str
    algorithm: str
    servers: List[BackendServer]
    enabled: bool = True