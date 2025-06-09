from typing import List
from ..schemas.load_balancer import LoadBalancer

# Dummy in-memory store
load_balancers: List[LoadBalancer] = []

def get_all_load_balancers() -> List[LoadBalancer]:
    return load_balancers

def add_load_balancer(lb: LoadBalancer):
    load_balancers.append(lb)