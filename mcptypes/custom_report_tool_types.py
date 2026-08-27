from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
    
class InsightDashboardVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = ""
    category_id: Optional[str] = ""
    status: Optional[str] = ""
    error: Optional[str] = ""
    
class InsightDashboardListVO(BaseModel):
    insights: Optional[list[InsightDashboardVO]] = None
    error: Optional[str] = None
    model_config = {
        "extra": "ignore",
    }