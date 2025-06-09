from typing import Dict
from ..schemas.metrics import LoadBalancerMetrics
from .load_balancer_service import load_balancers

# In-memory metrics store
metrics_store: Dict[str, LoadBalancerMetrics] = {}

def update_metrics(lb_id: str, request_increment: int = 1):
    lb = next((lb for lb in load_balancers if lb.id == lb_id), None)
    if not lb:
        return None
    healthy = sum(1 for s in lb.servers if s.healthy)
    unhealthy = len(lb.servers) - healthy
    if lb_id not in metrics_store:
        metrics_store[lb_id] = LoadBalancerMetrics(
            lb_id=lb_id,
            total_requests=0,
            healthy_backends=healthy,
            unhealthy_backends=unhealthy,
            custom_metrics={}
        )
    metrics = metrics_store[lb_id]
    metrics.total_requests += request_increment
    metrics.healthy_backends = healthy
    metrics.unhealthy_backends = unhealthy
    return metrics

def get_metrics(lb_id: str) -> LoadBalancerMetrics:
    return metrics_store.get(lb_id)