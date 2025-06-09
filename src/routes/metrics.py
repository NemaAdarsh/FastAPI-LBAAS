from fastapi import APIRouter, HTTPException
from ..services.metrics_service import get_metrics, update_metrics

router = APIRouter()

@router.get("/{lb_id}", summary="Get metrics for a load balancer")
def read_metrics(lb_id: str):
    metrics = get_metrics(lb_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")
    return metrics