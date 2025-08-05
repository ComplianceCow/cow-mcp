
from pydantic import BaseModel
from typing import List, Optional

class ErrorVO (BaseModel) :
    error: Optional[str] = ""

class ErrorResponseVO (BaseModel) :
    Message: Optional[str] = ""
    Description: Optional[str] = ""

class ErrorWorkflowVO (BaseModel):
    Message: Optional[str] = ""
    ErrorDetails: Optional[List[object]] = None