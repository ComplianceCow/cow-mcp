
from pydantic import BaseModel
from typing import List, Optional, TypeAlias

class ErrorVO (BaseModel) :
    error: Optional[str] = ""

class ErrorResponseVO (BaseModel) :
    Message: Optional[str] = ""
    Description: Optional[str] = ""

class ErrorWorkflowVO (BaseModel):
    Message: Optional[str] = ""
    ErrorDetails: Optional[list[object]] = None

StructuredError: TypeAlias = ErrorVO | ErrorResponseVO | ErrorWorkflowVO