import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Configure audit logger
audit_logger = logging.getLogger("audit")
audit_handler = logging.FileHandler("logs/audit.log")
audit_formatter = logging.Formatter('%(asctime)s %(message)s')
audit_handler.setFormatter(audit_formatter)
audit_logger.addHandler(audit_handler)
audit_logger.setLevel(logging.INFO)

# Database model for audit logs
Base = declarative_base()

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    action = Column(String(100), index=True)
    user = Column(String(100), index=True)
    resource = Column(String(100), index=True)
    resource_id = Column(Integer, index=True)
    details = Column(Text)  # JSON string
    ip_address = Column(String(45))  # Support IPv6
    user_agent = Column(Text)

def log_audit(action: str, user: str, resource: str, resource_id: int, details: Dict[str, Any] = None, ip_address: str = None, user_agent: str = None):
    """Log an audit event"""
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "user": user,
        "resource": resource,
        "resource_id": resource_id,
        "details": details or {},
        "ip_address": ip_address,
        "user_agent": user_agent
    }
    
    # Log to file
    audit_logger.info(json.dumps(audit_entry))
    
    # Also store in database if configured
    try:
        database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(bind=engine)
        
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        
        db = SessionLocal()
        audit_record = AuditLog(
            action=action,
            user=user,
            resource=resource,
            resource_id=resource_id,
            details=json.dumps(details) if details else None,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(audit_record)
        db.commit()
        db.close()
    except Exception as e:
        # If database logging fails, at least we have file logging
        audit_logger.error(f"Failed to log to database: {e}")

def get_audit_logs(
    page: int = 1,
    per_page: int = 50,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    user: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """Get paginated audit logs with filtering"""
    try:
        database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        # Build query
        query = db.query(AuditLog)
        
        # Apply filters
        if action:
            query = query.filter(AuditLog.action.ilike(f"%{action}%"))
        if resource:
            query = query.filter(AuditLog.resource.ilike(f"%{resource}%"))
        if user:
            query = query.filter(AuditLog.user.ilike(f"%{user}%"))
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * per_page
        logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(per_page).all()
        
        # Convert to dict format
        result = []
        for log in logs:
            details = {}
            if log.details:
                try:
                    details = json.loads(log.details)
                except:
                    details = {"raw": log.details}
            
            result.append({
                "id": log.id,
                "timestamp": log.timestamp,
                "action": log.action,
                "user": log.user,
                "resource": log.resource,
                "resource_id": log.resource_id,
                "details": details,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent
            })
        
        db.close()
        return result, total
        
    except Exception as e:
        audit_logger.error(f"Failed to retrieve audit logs: {e}")
        return [], 0

def get_audit_logs_for_resource(resource: str, resource_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """Get audit logs for a specific resource"""
    try:
        database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        logs = db.query(AuditLog).filter(
            AuditLog.resource == resource,
            AuditLog.resource_id == resource_id
        ).order_by(AuditLog.timestamp.desc()).limit(limit).all()
        
        result = []
        for log in logs:
            details = {}
            if log.details:
                try:
                    details = json.loads(log.details)
                except:
                    details = {"raw": log.details}
            
            result.append({
                "id": log.id,
                "timestamp": log.timestamp,
                "action": log.action,
                "user": log.user,
                "details": details,
                "ip_address": log.ip_address
            })
        
        db.close()
        return result
        
    except Exception as e:
        audit_logger.error(f"Failed to retrieve resource audit logs: {e}")
        return []

def get_user_activity(user: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent activity for a specific user"""
    try:
        database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        logs = db.query(AuditLog).filter(
            AuditLog.user == user
        ).order_by(AuditLog.timestamp.desc()).limit(limit).all()
        
        result = []
        for log in logs:
            details = {}
            if log.details:
                try:
                    details = json.loads(log.details)
                except:
                    details = {"raw": log.details}
            
            result.append({
                "id": log.id,
                "timestamp": log.timestamp,
                "action": log.action,
                "resource": log.resource,
                "resource_id": log.resource_id,
                "details": details,
                "ip_address": log.ip_address
            })
        
        db.close()
        return result
        
    except Exception as e:
        audit_logger.error(f"Failed to retrieve user activity: {e}")
        return []

def get_audit_summary(start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """Get summary statistics for audit logs in a date range"""
    try:
        database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        # Total events
        total_events = db.query(AuditLog).filter(
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date
        ).count()
        
        # Events by action
        actions = db.query(AuditLog.action).filter(
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date
        ).all()
        
        action_counts = {}
        for action in actions:
            action_counts[action[0]] = action_counts.get(action[0], 0) + 1
        
        # Events by user
        users = db.query(AuditLog.user).filter(
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date
        ).all()
        
        user_counts = {}
        for user in users:
            user_counts[user[0]] = user_counts.get(user[0], 0) + 1
        
        # Events by resource
        resources = db.query(AuditLog.resource).filter(
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date
        ).all()
        
        resource_counts = {}
        for resource in resources:
            resource_counts[resource[0]] = resource_counts.get(resource[0], 0) + 1
        
        db.close()
        
        return {
            "total_events": total_events,
            "actions": action_counts,
            "users": user_counts,
            "resources": resource_counts,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
    except Exception as e:
        audit_logger.error(f"Failed to get audit summary: {e}")
        return {
            "total_events": 0,
            "actions": {},
            "users": {},
            "resources": {},
            "error": str(e)
        }

# Decorator for automatic audit logging
def audit_action(action: str, resource: str):
    """Decorator to automatically log function calls"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract user and resource_id from arguments if possible
            user = "system"
            resource_id = 0
            
            # Try to extract from kwargs
            if 'user' in kwargs:
                user = kwargs['user'].username if hasattr(kwargs['user'], 'username') else str(kwargs['user'])
            if 'current_user' in kwargs:
                user = kwargs['current_user'].username if hasattr(kwargs['current_user'], 'username') else str(kwargs['current_user'])
            
            # Execute function
            try:
                result = func(*args, **kwargs)
                log_audit(action, user, resource, resource_id, {"status": "success"})
                return result
            except Exception as e:
                log_audit(action, user, resource, resource_id, {"status": "error", "error": str(e)})
                raise
        return wrapper
    return decorator
