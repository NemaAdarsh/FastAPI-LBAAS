from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from routes.load_balancer import router as lb_router
from routes.health import router as health_router

load_dotenv()

app = FastAPI(
    title="LBaaS - Load Balancer as a Service",
    description="A service for managing load balancers",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(lb_router, prefix="/api/v1/loadbalancer", tags=["load-balancer"])

@app.get("/")
async def root():
    return {"message": "LBaaS API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)