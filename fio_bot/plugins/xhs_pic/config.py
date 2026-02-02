from pydantic import BaseModel
from typing import Optional

class Config(BaseModel):
    xhs_cookie: Optional[str] = None
