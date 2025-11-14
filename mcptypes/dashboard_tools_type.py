from pydantic import BaseModel, Field
from typing import List, Optional
    
class ComplianceStatusSummaryVO(BaseModel):
    status: Optional[str] = ""
    count: Optional[int] = 0
    
class ControlSummaryVO(BaseModel):
    category: Optional[str] = ""
    status: Optional[str] = ""
    dueDate: Optional[str] = ""
    compliancePCT: Optional[float] = 0.0
    leafControls: Optional[int] = 0
    
    
class ControlAssignmentStatusVO(BaseModel):
    categoryName: Optional[str] = ""
    controlStatus: Optional[List[ComplianceStatusSummaryVO]] = None
    
class FrameworkSummaryVO(BaseModel):
    name: Optional[str] = ""
    compliancePCT: Optional[float] = 0.0
    leafControls: Optional[int] = 0
    complianceStatusSummary: Optional[List[ComplianceStatusSummaryVO]] = None

class DashboardSummaryVO(BaseModel): 
    totalControls: Optional[int] = 0
    controlStatus: Optional[List[ComplianceStatusSummaryVO]] = None
    controlAssignmentStatus: Optional[List[ControlAssignmentStatusVO]] = None
    compliancePCT: Optional[float] = 0.0
    controlSummary: Optional[List[ControlSummaryVO]] = None
    complianceStatusSummary: Optional[List[ComplianceStatusSummaryVO]] = None
    frameworks: Optional[List[FrameworkSummaryVO]] = None
    error: Optional[str] = ""

class UserVO(BaseModel):
    emailid: Optional[str] = ""
    
    model_config = {
        "extra": "ignore"
    }


class NonCompliantControlVO(BaseModel):
    # id: Optional[str] = ""
    # planInstanceID: Optional[str] = ""
    name: Optional[str] = Field(default="", alias="controlName")
    lastAssignedTo: Optional[List[UserVO]] = None
    score: Optional[float] = 0
    priority: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class NonCompliantControlListVO(BaseModel):
    controls: Optional[List[NonCompliantControlVO]] = None
    error: Optional[str] = ""

class OverdueControlVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = Field(default="", alias="controlName")
    assignedTo: Optional[List[UserVO]] = None
    dueDate: Optional[str] = ""
    daysOverDue: Optional[int] = 0
    score: Optional[float] = 0
    priority: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class OverdueControlListVO(BaseModel):
    controls: Optional[List[OverdueControlVO]] = None
    error: Optional[str] = ""

class FramworkControlVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = Field(default="", alias="controlName")
    assignedTo: Optional[List[UserVO]] = None
    assignmentStatus: Optional[str] = Field(default="", alias="status")
    complianceStatus: Optional[str] = Field(default="", alias="complianceStatus")
    dueDate: Optional[str] = ""
    score: Optional[float] = 0
    priority: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }
    
class FrameworkControlListVO(BaseModel):
    controls: Optional[List[FramworkControlVO]] = None
    page: Optional[int] = 0
    totalPage: Optional[int] = 0
    totalItems: Optional[int] = 0
    error: Optional[str] = ""
     
class CommonControlVO(BaseModel):
    id: Optional[str] = ""
    planInstanceID: Optional[str] = ""
    alias: Optional[str] = ""
    displayable: Optional[str] = ""
    controlName: Optional[str] = ""
    dueDate: Optional[str] = ""
    score: Optional[float] = 0.0
    priority: Optional[str] = ""
    status: Optional[str] = ""
    complianceStatus: Optional[str] = ""
    updatedAt: Optional[str] = ""
    
class CommonControlListVO (BaseModel):
    controls: Optional[List[CommonControlVO]] = None
    page: Optional[int] = 0
    totalPage: Optional[int] = 0
    totalItems: Optional[int] = 0
    error: Optional[str] = ""    

class CCFDashboardReviewPeriods (BaseModel):
    items: Optional[List[str]] = None
    error: Optional[str] = ""
    
    
   