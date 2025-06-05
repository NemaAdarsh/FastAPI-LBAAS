import os
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
from pythonjsonlogger import jsonlogger
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from starlette.responses import JSONResponse

from routes.load_balancer import router as lb_router
from routes.health import router as health_router

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

# Configure structured logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(env)s %(service)s'
)
logHandler.setFormatter(formatter)
logger = logging.getLogger("lbaas")
logger = logging.LoggerAdapter(logger, {"env": os.getenv("ENV", "development"), "service": "lbaas"})
logger.setLevel(logging.INFO)
logger.handlers = [logHandler]
logger.propagate = False

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        logger = logging.getLogger("lbaas")
        extra = {
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "user_agent": request.headers.get("user-agent", "")
        }
        request.state.request_id = request_id
        request.state.logger = logging.LoggerAdapter(logger, extra)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        logger = getattr(request.state, "logger", logging.getLogger("lbaas"))
        logger.info(
            "Request completed",
            extra={
                "status_code": response.status_code,
                "path": request.url.path,
                "method": request.method,
                "request_id": getattr(request.state, "request_id", None)
            }
        )
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
app.add_middleware(AccessLogMiddleware)
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
    log = getattr(request.state, "logger", logger)
    log.error(f"Unhandled error: {exc}", exc_info=True)
    debug = get_settings()["DEBUG"]
    detail = str(exc) if debug else "Internal Server Error"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": detail,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    log = getattr(request.state, "logger", logger)
    log.warning(f"HTTP error: {exc.detail}", extra={"status_code": exc.status_code})
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "request_id": getattr(request.state, "request_id", None)
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    log = getattr(request.state, "logger", logger)
    log.warning(f"Validation error: {exc.errors()}", extra={"status_code": 422})
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "request_id": getattr(request.state, "request_id", None)
        }
    )

# Routers
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(lb_router, prefix="/api/v1/loadbalancer", tags=["load-balancer"])

@app.get("/", tags=["root"])
async def root():
    return {"message": "LBaaS API is running", "env": get_settings()["ENV"]}

@app.on_event("startup")
async def on_startup():
    logger.info("Starting LBaaS API...", extra={"request_id": None})

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Shutting down LBaaS API...", extra={"request_id": None})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.app:app",
        host="0.0.0.0",
        port=8000,
        reload=get_settings()["DEBUG"]
    )