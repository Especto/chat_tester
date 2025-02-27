from typing import Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    text: Optional[str] = None
    image: bool = False
    image_url: Optional[str] = None
    time: Optional[str] = None


class UserMessage(BaseModel):
    text: Optional[str]
    send_star: bool


class UserModel(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    bio: Optional[str] = None
