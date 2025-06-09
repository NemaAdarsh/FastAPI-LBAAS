from typing import List, Optional
from uuid import uuid4
from ..schemas.load_balancer import LoadBalancer, BackendServer

# Dummy in-memory store
load_balancers: List[LoadBalancer] = []

def get_all_load_balancers() -> List[LoadBalancer]:
    return load_balancers

def get_load_balancer(lb_id: str) -> Optional[LoadBalancer]:
    return next((lb for lb in load_balancers if lb.id == lb_id), None)

def add_load_balancer(lb_data: dict) -> LoadBalancer:
    lb = LoadBalancer(id=str(uuid4()), **lb_data)
    load_balancers.append(lb)
    return lb

def update_load_balancer(lb_id: str, lb_data: dict) -> Optional[LoadBalancer]:
    lb = get_load_balancer(lb_id)
    if lb:
        for key, value in lb_data.items():
            setattr(lb, key, value)
        return lb
    return None

def delete_load_balancer(lb_id: str) -> bool:
    global load_balancers
    before = len(load_balancers)
    load_balancers = [lb for lb in load_balancers if lb.id != lb_id]
    return len(load_balancers) < before

def add_backend_server(lb_id: str, server_data: dict) -> Optional[LoadBalancer]:
    lb = get_load_balancer(lb_id)
    if lb:
        server = BackendServer(**server_data)
        lb.servers.append(server)
        return lb
    return None

def remove_backend_server(lb_id: str, server_ip: str, server_port: int) -> Optional[LoadBalancer]:
    lb = get_load_balancer(lb_id)
    if lb:
        lb.servers = [
            s for s in lb.servers if not (s.ip == server_ip and s.port == server_port)
        ]
        return lb
    return None

def set_backend_health(lb_id: str, server_ip: str, server_port: int, healthy: bool) -> Optional[LoadBalancer]:
    lb = get_load_balancer(lb_id)
    if lb:
        for s in lb.servers:
            if s.ip == server_ip and s.port == server_port:
                s.healthy = healthy
        return lb
    return None