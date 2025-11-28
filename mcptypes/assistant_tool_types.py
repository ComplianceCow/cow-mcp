from pydantic import BaseModel, Field
from typing import List, Optional


class ColumnInfoVO(BaseModel):
    name: Optional[str] = ""
    type: Optional[str] = ""
    mode: Optional[str] = ""
    fieldDataType: Optional[str] = ""
    fieldOrder: Optional[int] = 0
    
    model_config = {
        "extra": "ignore"
    }


class RuleVO(BaseModel):
    ruleId: Optional[str] = ""
    ruleName: Optional[str] = ""
    ruleDescription: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class EvidenceVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = ""
    description: Optional[str] = ""
    fileName: Optional[str] = ""
    columnsInfo: Optional[List[ColumnInfoVO]] = None
    
    model_config = {
        "extra": "ignore"
    }


class LineageVO(BaseModel):
    originType: Optional[str] = ""
    recursionLevel: Optional[int] = 0
    linkedFrom: Optional[List['LinkedControlVO']] = None
    model_config = {
        "extra": "ignore"
    }

class LinkedControlVO(BaseModel):
    assessmentId: Optional[str] = ""
    assessmentName: Optional[str] = ""
    controlId: Optional[str] = ""
    controlName: Optional[str] = ""
    controlDescription: Optional[str] = ""
    referenceType: Optional[str] = ""
    lineage: Optional[List[LineageVO]] = None
    evidences: Optional[List[EvidenceVO]] = None
    rule: Optional[RuleVO] = None
    model_config = {
        "extra": "ignore"
    }


# Update forward reference after LinkedControlVO is defined
LineageVO.model_rebuild()


class ControlSourceSummaryVO(BaseModel):
    assessmentId: Optional[str] = ""
    assessmentName: Optional[str] = ""
    controlId: Optional[str] = ""
    controlName: Optional[str] = ""
    lineage: Optional[List[LineageVO]] = None
    model_config = {
        "extra": "ignore"
    }


class ControlSourceSummaryResponseVO(BaseModel):
    success: bool = True
    data: Optional[ControlSourceSummaryVO] = None
    error: Optional[str] = None
    next_action: Optional[str] = None
    next_step: Optional[str] = None
    model_config = {
        "extra": "ignore"
    }

