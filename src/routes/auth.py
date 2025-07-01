from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List

from models.database import get_db
from schemas.auth import (
    UserCreate, 
    UserUpdate, 
    UserResponse, 
    TokenResponse, 
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetConfirm
)
from auth import (
    authenticate_user, 
    create_access_token, 
    get_current_user,
    require_role,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_password_hash,
    verify_password
)
from models.load_balancer import User
from utils.audit import log_audit

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticate user and return access token"""
    user = authenticate_user(db, login_data.username, login_data.password)
    if not user:
        log_audit("login_failed", login_data.username, "auth", 0, {
            "ip": request.client.host,
            "user_agent": request.headers.get("user-agent")
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )
    
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "tenant_id": user.tenant_id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    log_audit("login_success", user.username, "auth", user.id, {
        "ip": request.client.host,
        "user_agent": request.headers.get("user-agent")
    })
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            tenant_id=user.tenant_id,
            is_active=user.is_active
        )
    )

@router.post("/token", response_model=TokenResponse)
async def login_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    request: Request = None
):
    """OAuth2 compatible login endpoint"""
    login_data = LoginRequest(username=form_data.username, password=form_data.password)
    return await login(login_data, request or Request, db)

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new user"""
    # Check if username or email already exists
    existing_user = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username or email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role,
        tenant_id=user_data.tenant_id
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    log_audit("user_registered", user_data.username, "user", db_user.id, {
        "email": user_data.email,
        "role": user_data.role
    })
    
    return UserResponse(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        role=db_user.role,
        tenant_id=db_user.tenant_id,
        is_active=db_user.is_active
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        is_active=current_user.is_active
    )

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user information"""
    # Users can only update certain fields
    allowed_fields = ["username", "email"]
    update_data = {k: v for k, v in user_update.dict(exclude_unset=True).items() 
                   if k in allowed_fields}
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    log_audit("user_updated", current_user.username, "user", current_user.id, update_data)
    
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        is_active=current_user.is_active
    )

@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    
    log_audit("password_changed", current_user.username, "user", current_user.id, {})
    
    return {"detail": "Password updated successfully"}

@router.get("/users", response_model=List[UserResponse], dependencies=[Depends(require_role("admin"))])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all users (admin only)"""
    users = db.query(User).offset(skip).limit(limit).all()
    return [
        UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            tenant_id=user.tenant_id,
            is_active=user.is_active
        )
        for user in users
    ]

@router.get("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(require_role("admin"))])
async def get_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get user by ID (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        tenant_id=user.tenant_id,
        is_active=user.is_active
    )

@router.put("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(require_role("admin"))])
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    log_audit("user_updated_by_admin", current_user.username, "user", user.id, update_data)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        tenant_id=user.tenant_id,
        is_active=user.is_active
    )

@router.delete("/users/{user_id}", dependencies=[Depends(require_role("admin"))])
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete user (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Soft delete by marking as inactive
    user.is_active = False
    db.commit()
    
    log_audit("user_deleted", current_user.username, "user", user.id, {})
    
    return {"detail": "User deleted successfully"}

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """Logout user (token blacklisting would be implemented here)"""
    log_audit("logout", current_user.username, "auth", current_user.id, {})
    return {"detail": "Successfully logged out"}