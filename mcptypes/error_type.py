
from pydantic import BaseModel
from typing import List, Optional

class ErrorVO (BaseModel) :
    error: Optional[str] = ""
