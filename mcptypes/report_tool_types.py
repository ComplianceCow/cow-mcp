

from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel

@dataclass
class InsightsCategoryVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = ""
    description: Optional[str] = ""
    status: Optional[str] = ""
    level: Optional[str] = ""
    orgID: Optional[str] = ""
    domainID: Optional[str] = ""
    groupID: Optional[str] = ""
    groupID: Optional[str] = ""
    error: Optional[str]  = None
    
class InsightsCategoryListVO(BaseModel):
    insights_categories: Optional[list[InsightsCategoryVO]] = None
    error: Optional[str] = ""