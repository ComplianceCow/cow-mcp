from pydantic import BaseModel, Field
from typing import List, Optional, Any


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
    columnsInfo: Optional[list[ColumnInfoVO]] = None
    
    model_config = {
        "extra": "ignore"
    }


class LineageVO(BaseModel):
    originType: Optional[str] = ""
    recursionLevel: Optional[int] = 0
    linkedFrom: Optional[list['LinkedControlVO']] = None
    model_config = {
        "extra": "ignore"
    }

class LinkedControlVO(BaseModel):
    assessmentMetricsId: Optional[str] = Field("", alias="assessmentId")
    assessmentMetricsName: Optional[str] = Field("", alias="assessmentName")
    metricsId: Optional[str] = Field("", alias="controlId")
    metricsName: Optional[str] = Field("", alias="controlName")
    metricsDescription: Optional[str] = Field("", alias="controlDescription")
    referenceType: Optional[str] = ""

    lineage: Optional[list[LineageVO]] = None
    evidences: Optional[list[EvidenceVO]] = None
    rule: Optional[RuleVO] = None

    model_config = {
        "extra": "ignore",
        "populate_by_name": True
    }


# Update forward reference after LinkedControlVO is defined
LineageVO.model_rebuild()


class MetricsSourceSummaryVO(BaseModel):
    assessmentMetricsId: Optional[str] = Field("", alias="assessmentId")
    assessmentMetricsName: Optional[str] = Field("", alias="assessmentName")
    metricsId: Optional[str] = Field("", alias="controlId")
    metricsName: Optional[str] = Field("", alias="controlName")

    lineage: Optional[list[LineageVO]] = None

    model_config = {
        "extra": "ignore",
        "populate_by_name": True
    }

class MetricsSourceSummaryResponseVO(BaseModel):
    success: bool = True
    data: Optional[MetricsSourceSummaryVO] = None
    error: Optional[Any] = None
    next_action: Optional[str] = None
    next_step: Optional[str] = None
    model_config = {
        "extra": "ignore"
    }

