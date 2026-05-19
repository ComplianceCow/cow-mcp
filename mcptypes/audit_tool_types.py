

from pydantic import BaseModel, Field
from dataclasses import dataclass, field
from typing import List, Optional, Any
from mcptypes.error_type import StructuredError

class UserVO(BaseModel):
    id: Optional[str] = Field(default=None, validation_alias="ID")
    emailId:Optional[str] = Field(default=None, validation_alias="emailid")
    model_config = {
        "extra": "ignore"
    }

class UserListVO(BaseModel):
    Users: Optional[list[UserVO]] = None
    error: Optional[StructuredError] = None

    
