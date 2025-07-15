from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str
    phone: str
    role: str
    approved: bool