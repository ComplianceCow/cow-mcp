

from pydantic import BaseModel, Field
from dataclasses import dataclass, field
from typing import List, Optional, Any

class AutomatedControlVO(BaseModel):
    id: Optional[str] = ""
    displayable: Optional[str] = ""
    alias: Optional[str] = ""
    activationStatus: Optional[str] = ""
    ruleName: Optional[str] = ""
    assessmentId: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }
    
class AutomatedControlListVO(BaseModel):
    controls: Optional[List[AutomatedControlVO]] = None
    error: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class ActionsVO(BaseModel):
    actionName: Optional[str] = ""
    actionDescription: Optional[str] = ""
    actionSpecID: Optional[str] = ""
    actionBindingID: Optional[str] = ""
    target: Optional[str] = ""
    
    model_config = {
        "extra": "ignore"
    }

class ActionsListVO(BaseModel):
    actions: Optional[List[ActionsVO]] = None
    error: Optional[str] = ""
    

class RecordsVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = Field(default="", alias="System")
    source: Optional[str] = Field(default="", alias="Source")
    resourceId: Optional[str] = Field(default="", alias="ResourceID")
    resourceName: Optional[str] = Field(default="", alias="ResourceName")
    resourceType: Optional[str] = Field(default="", alias="ResourceType")
    complianceStatus: Optional[str] = Field(default="", alias="ComplianceStatus")
    complianceReason: Optional[str] = Field(default="", alias="ComplianceReason")
    createdAt: Optional[str] = Field(default="", alias="CreatedAt")
    otherInfo : Optional[Any] = None
    
    model_config = {
        "extra": "ignore"
    }
    
class RecordListVO(BaseModel):
    totalRecords:  Optional[int] = ""
    compliantRecords:  Optional[int] = ""
    nonCompliantRecords:  Optional[int] = ""
    notDeterminedRecords:  Optional[int] = ""
    records:  Optional[List[Any]] = None

class RecordSchemaVO(BaseModel):
    name: Optional[str] = ""
    type: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }
    

class RecordSchemaListVO(BaseModel):
    schema: Optional[List[RecordSchemaVO]] = None
    error: Optional[str] = ""

@dataclass
class ControlPromptVO:
    prompt:  Optional[str] = ""
    error: Optional[str] = ""


class ControlMetadataVO(BaseModel):
    assessementId: Optional[str] = Field(default="", alias="planId")
    assessmentName: Optional[str] = Field(default="", alias="planName")
    assessmentRunId: Optional[str] = Field(default="", alias="planInstanceId")
    assessmentRunName: Optional[str] = Field(default="", alias="planInstanceName")
    controlId: Optional[str] = Field(default="", alias="planInstanceControlId")
    controlName: Optional[str] = Field(default="", alias="planInstanceControlName")
    controlNumber: Optional[str] = Field(default="", alias="planInstanceControlDisplayable")
    error: Optional[str] = ""
    
    model_config = {
        "extra": "ignore"
    }

# @dataclass
class ControlVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = ""
    controlNumber: Optional[str] = Field(default="", alias="displayable")
    alias: Optional[str] = ""
    priority: Optional[str] = ""
    stage: Optional[str] = ""
    status: Optional[str] = ""
    type: Optional[str] = ""
    executionStatus: Optional[str] = ""
    dueDate: Optional[str] = ""
    assignedTo: Optional[List[str]] = field(default_factory=list)
    assignedBy: Optional[str] = ""
    assignedDate: Optional[str] = ""
    checkedOut: Optional[bool] = False
    compliancePCT__: Optional[float] = ""
    complianceWeight__: Optional[float] = ""
    complianceStatus: Optional[str] = ""
    createdAt: Optional[str] = ""
    updatedAt: Optional[str] = ""
    
    model_config = {
        "extra": "ignore"
    }
    
# @dataclass
class ControlListVO(BaseModel):
    controls: Optional[List[ControlVO]] = None
    error: Optional[str] = None

@dataclass
class AssessmentRunVO:
    id: Optional[str] = ""
    name: Optional[str] = ""
    description: Optional[str] = ""
    assessmentId: Optional[str] = ""
    applicationType: Optional[str] = ""
    configId: Optional[str] = ""
    fromDate: Optional[str] = ""
    toDate: Optional[str] = ""
    # started: Optional[str] = ""
    ended: Optional[str] = ""
    status: Optional[str] = ""
    computedScore: Optional[str] = ""
    computedWeight: Optional[str] = ""
    complianceStatus: Optional[str] = ""
    createdAt: Optional[str] = ""


@dataclass
class AssessmentRunListVO:
    assessmentRuns: Optional[List[AssessmentRunVO]] = None
    error: Optional[str] = ""
    
    
class ControlEvidenceVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = ""
    description: Optional[str] = ""
    fileName: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }
    
class ControlEvidenceListVO(BaseModel):
    evidences: Optional[List[ControlEvidenceVO]] = None
    error: Optional[str] = ""
    


class TriggerActionVO(BaseModel):
    id: Optional[str] = ""
    error: Optional[str] = ""
    
    model_config = {
        "extra": "ignore"
    }