from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")
    role: str = Field("user", description="User role")

    @validator('role')
    def validate_role(cls, v):
        allowed_roles = ['user', 'admin', 'tenant_admin']
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Password")
    tenant_id: Optional[int] = None

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @validator('role')
    def validate_role(cls, v):
        if v is None:
            return v
        allowed_roles = ['user', 'admin', 'tenant_admin']
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v

class UserResponse(UserBase):
    id: int
    tenant_id: Optional[int]
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)
