from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def health_check():
    return {"status": "healthy", "service": "LBaaS"}

@router.get("/ready")
async def readiness_check():
    # Add database connectivity check here
    return {"status": "ready"}