import os
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware
import uuid

from routes.load_balancer import router as lb_router
from routes.health import router as health_router

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger("lbaas")

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

def get_settings():
    return {
        "ENV": os.getenv("ENV", "development"),
        "DEBUG": os.getenv("DEBUG", "false").lower() == "true"
    }

app = FastAPI(
    title="LBaaS - Load Balancer as a Service",
    description="A service for managing load balancers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error", "request_id": getattr(request.state, 'request_id', None)}
    )

# Routers
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(lb_router, prefix="/api/v1/loadbalancer", tags=["load-balancer"])

@app.get("/", tags=["root"])
async def root():
    return {"message": "LBaaS API is running", "env": get_settings()["ENV"]}

@app.on_event("startup")
async def on_startup():
    logger.info("Starting LBaaS API...")

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Shutting down LBaaS API...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.app:app",
        host="0.0.0.0",
        port=8000,
        reload=get_settings()["DEBUG"]
    )