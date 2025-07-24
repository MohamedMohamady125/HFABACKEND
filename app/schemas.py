from pydantic import BaseModel, EmailStr
from typing import Optional, Union

class UserCreate(BaseModel):
    name: str
    phone: str
    email: EmailStr
    password: str
    branch_id: int  # ✅ Now expecting numeric branch_id

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    phone: str
    email: str
    role: str
    approved: bool

class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str

class PushSubscription(BaseModel):
    endpoint: str
    expirationTime: Optional[Union[int, float, str, None]] = None  # ✅ Fixed to handle null/number/string
    keys: SubscriptionKeys
    
    class Config:
        # Allow extra fields that might come from browser
        extra = "ignore"