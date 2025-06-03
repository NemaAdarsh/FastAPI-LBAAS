from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from models.database import get_db
from models.load_balancer import LoadBalancer, BackendServer
from utils.lb_manager import LoadBalancerManager
from utils.schemas import LoadBalancerCreate, LoadBalancerResponse, BackendServerCreate

router = APIRouter()
lb_manager = LoadBalancerManager()

@router.post("/", response_model=LoadBalancerResponse)
async def create_load_balancer(
    lb_data: LoadBalancerCreate,
    db: Session = Depends(get_db)
):
    # Create load balancer in database
    db_lb = LoadBalancer(**lb_data.dict())
    db.add(db_lb)
    db.commit()
    db.refresh(db_lb)
    
    # Generate HAProxy configuration
    await lb_manager.create_lb_config(db_lb)
    
    return db_lb

@router.get("/", response_model=List[LoadBalancerResponse])
async def list_load_balancers(db: Session = Depends(get_db)):
    return db.query(LoadBalancer).all()

@router.get("/{lb_id}", response_model=LoadBalancerResponse)
async def get_load_balancer(lb_id: int, db: Session = Depends(get_db)):
    lb = db.query(LoadBalancer).filter(LoadBalancer.id == lb_id).first()
    if not lb:
        raise HTTPException(status_code=404, detail="Load balancer not found")
    return lb

@router.post("/{lb_id}/backends")
async def add_backend_server(
    lb_id: int,
    backend_data: BackendServerCreate,
    db: Session = Depends(get_db)
):
    lb = db.query(LoadBalancer).filter(LoadBalancer.id == lb_id).first()
    if not lb:
        raise HTTPException(status_code=404, detail="Load balancer not found")
    
    backend = BackendServer(load_balancer_id=lb_id, **backend_data.dict())
    db.add(backend)
    db.commit()
    db.refresh(backend)
    
    # Update HAProxy configuration
    await lb_manager.update_lb_config(lb)
    
    return backend

@router.delete("/{lb_id}")
async def delete_load_balancer(lb_id: int, db: Session = Depends(get_db)):
    lb = db.query(LoadBalancer).filter(LoadBalancer.id == lb_id).first()
    if not lb:
        raise HTTPException(status_code=404, detail="Load balancer not found")
    
    db.delete(lb)
    db.commit()
    
    # Remove from HAProxy configuration
    await lb_manager.delete_lb_config(lb)
    
    return {"message": "Load balancer deleted successfully"}