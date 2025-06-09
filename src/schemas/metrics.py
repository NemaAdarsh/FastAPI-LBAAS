from pydantic import BaseModel
from typing import Dict

class LoadBalancerMetrics(BaseModel):
    lb_id: str
    total_requests: int
    healthy_backends: int
    unhealthy_backends: int
    custom_metrics: Dict[str, float] = {}