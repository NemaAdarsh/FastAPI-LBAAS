#!/usr/bin/env python3
"""
FastAPI Load Balancer Service Startup Script

This script provides a comprehensive way to start the FastAPI application
with proper initialization, database setup, and configuration.
"""

import os
import sys
import subprocess
import argparse
import time
import logging
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def check_dependencies():
    """Check if required dependencies are installed"""
    logger = logging.getLogger(__name__)
    
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import redis
        logger.info("✅ Core dependencies are available")
        return True
    except ImportError as e:
        logger.error(f"❌ Missing dependency: {e}")
        logger.error("Please install dependencies: pip install -r requirements.txt")
        return False

def setup_environment():
    """Setup environment variables"""
    logger = logging.getLogger(__name__)
    
    # Load .env file if it exists
    env_file = Path(".env")
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("✅ Loaded environment variables from .env")
    
    # Set default environment variables if not present
    defaults = {
        "ENV": "development",
        "DEBUG": "true",
        "DATABASE_URL": "sqlite:///./app.db",
        "SECRET_KEY": "your-secret-key-change-in-production",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
        "REDIS_URL": "redis://localhost:6379/0"
    }
    
    for key, value in defaults.items():
        if not os.getenv(key):
            os.environ[key] = value
            logger.info(f"Set default {key}={value}")

def check_database():
    """Check database connection and create tables if needed"""
    logger = logging.getLogger(__name__)
    
    try:
        from models.database import engine, Base
        from models.load_balancer import User, Tenant, LoadBalancer, BackendServer
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified")
        
        return True
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")
        return False

def check_redis():
    """Check Redis connection"""
    logger = logging.getLogger(__name__)
    
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        logger.info("✅ Redis connection successful")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Redis not available: {e}")
        logger.warning("Some features may not work properly without Redis")
        return False

def create_default_user():
    """Create default admin user if it doesn't exist"""
    logger = logging.getLogger(__name__)
    
    try:
        from models.database import SessionLocal
        from models.load_balancer import User, Tenant
        from auth import get_password_hash
        
        db = SessionLocal()
        
        # Check if admin user exists
        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user:
            logger.info("✅ Admin user already exists")
            db.close()
            return True
        
        # Create default tenant if it doesn't exist
        default_tenant = db.query(Tenant).filter(Tenant.slug == "default").first()
        if not default_tenant:
            default_tenant = Tenant(
                name="Default Tenant",
                slug="default",
                subscription_tier="enterprise",
                max_load_balancers=100
            )
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)
            logger.info("✅ Created default tenant")
        
        # Create admin user
        admin_user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            role="admin",
            tenant_id=default_tenant.id,
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        db.close()
        
        logger.info("✅ Created default admin user (username: admin, password: admin123)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create default user: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    logger = logging.getLogger(__name__)
    
    directories = ["logs", "config", "data"]
    
    for dir_name in directories:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Created directory: {dir_name}")

def start_application(host: str = "0.0.0.0", port: int = 8000, reload: bool = True, workers: int = 1):
    """Start the FastAPI application"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"🚀 Starting FastAPI application on {host}:{port}")
    
    if reload and workers > 1:
        logger.warning("Cannot use reload with multiple workers, disabling reload")
        reload = False
    
    try:
        import uvicorn
        
        config = {
            "app": "src.app:app",
            "host": host,
            "port": port,
            "reload": reload,
            "log_level": "info"
        }
        
        if not reload:
            config["workers"] = workers
        
        uvicorn.run(**config)
        
    except KeyboardInterrupt:
        logger.info("👋 Application stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        sys.exit(1)

def run_tests():
    """Run API tests"""
    logger = logging.getLogger(__name__)
    
    logger.info("🧪 Running API tests...")
    
    try:
        result = subprocess.run([
            sys.executable, "test_api.py", "--url", "http://localhost:8000"
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            logger.info("✅ Tests completed successfully")
        else:
            logger.error("❌ Tests failed")
        
    except Exception as e:
        logger.error(f"❌ Failed to run tests: {e}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="FastAPI Load Balancer Service Startup")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    parser.add_argument("--check-only", action="store_true", help="Only run checks, don't start server")
    parser.add_argument("--test", action="store_true", help="Run tests after startup")
    parser.add_argument("--skip-checks", action="store_true", help="Skip all initialization checks")
    
    args = parser.parse_args()
    
    logger = setup_logging()
    
    print("🔧 FastAPI Load Balancer Service Initialization")
    print("=" * 50)
    
    if not args.skip_checks:
        # Run all checks
        checks = [
            ("Dependencies", check_dependencies),
            ("Environment", lambda: (setup_environment(), True)[1]),
            ("Directories", lambda: (create_directories(), True)[1]),
            ("Database", check_database),
            ("Redis", check_redis),
            ("Default User", create_default_user)
        ]
        
        failed_checks = []
        for check_name, check_func in checks:
            try:
                if not check_func():
                    failed_checks.append(check_name)
            except Exception as e:
                logger.error(f"❌ {check_name} check failed: {e}")
                failed_checks.append(check_name)
        
        if failed_checks:
            logger.error(f"❌ Failed checks: {', '.join(failed_checks)}")
            if "Dependencies" in failed_checks or "Database" in failed_checks:
                logger.error("Cannot continue without core dependencies")
                sys.exit(1)
    
    if args.check_only:
        logger.info("✅ All checks completed")
        return
    
    # Start the application
    reload = not args.no_reload and os.getenv("ENV", "development") == "development"
    
    if args.test:
        logger.info("Test mode: Starting server in background and running tests")
        # This would need a more complex implementation to start server in background
        # For now, just start normally
        pass
    
    start_application(
        host=args.host,
        port=args.port,
        reload=reload,
        workers=args.workers
    )

if __name__ == "__main__":
    main()
