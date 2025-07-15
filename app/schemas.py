from pydantic import BaseModel, EmailStr

from pydantic import BaseModel, EmailStr

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