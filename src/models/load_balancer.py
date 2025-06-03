from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum

class LoadBalancingAlgorithm(str, enum.Enum):
    ROUND_ROBIN = "roundrobin"
    LEAST_CONNECTIONS = "leastconn"
    IP_HASH = "source"
    WEIGHTED_ROUND_ROBIN = "weighted_roundrobin"

class LoadBalancer(Base):
    __tablename__ = "load_balancers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    frontend_port = Column(Integer)
    algorithm = Column(Enum(LoadBalancingAlgorithm), default=LoadBalancingAlgorithm.ROUND_ROBIN)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship with backend servers
    backend_servers = relationship("BackendServer", back_populates="load_balancer")

class BackendServer(Base):
    __tablename__ = "backend_servers"
    
    id = Column(Integer, primary_key=True, index=True)
    load_balancer_id = Column(Integer, ForeignKey("load_balancers.id"))
    host = Column(String)
    port = Column(Integer)
    weight = Column(Integer, default=1)
    is_healthy = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship with load balancer
    load_balancer = relationship("LoadBalancer", back_populates="backend_servers")