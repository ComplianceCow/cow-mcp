

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field

class CategoryVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = ""
    model_config = {
        "extra": "ignore",
    }

class CategoryListVO(BaseModel):
    categories: Optional[list[CategoryVO]] = None
    error: Optional[str] = None
    model_config = {
        "extra": "ignore",
    }

class CitationVO(BaseModel):
    authorityDocument: Optional[str] = ""
    controlsInAuthorityDocument: Optional[list[str]] = None
    model_config = {
        "extra": "ignore",
    }

class ControlVO(BaseModel):
    id: Optional[str] = None
    # parentControlId: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    displayable: Optional[str] = None
    alias: Optional[str] = None
    # priority: Optional[str] = None
    # stage: Optional[str] = None
    # status: Optional[str] = None
    # type: Optional[str] = None
    # weight: Optional[int] = None
    # tags: Optional[dict] = None
    controls: Optional[list[ControlVO]] = Field(default=None, validation_alias="planControls")
    # dependsOn: Optional[list[str]]  = None
    # cnControlId: Optional[str] = None
    # cnControlAlias: Optional[str] = None
    # cnControlDisplayable: Optional[str] = None
    # cnPlanId: Optional[str] = None
    # cnPlanIds: Optional[list[str]] = None
    # configId: Optional[str] = None
    activationStatus: Optional[str] = None
    leafControl: Optional[bool] = None
    isAutomated: Optional[bool] = None
    citations: Optional[list[CitationVO]] = None
    reportingLevelControl: Optional[bool] = None
    # dueDays: Optional[int] = None
    # AssignTo: Optional[list[str]] = None
    ccfSortID: Optional[str] = None
    ccfID: Optional[str] = None
    ccfImpactZone: Optional[str] = None
    ccfType: Optional[str] = None
    ccfRequirement: Optional[str] = None
    ccfClassification: Optional[str] = None
    ccfStatus: Optional[str] = None
    ccfTags: Optional[str] = None
    error: Optional[str] = ""
    model_config = {
        "extra": "ignore",
    }
    
    
class AssessmentVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = ""
    categoryName: Optional[str] = Field(default="", validation_alias="categoryName")
    controls: Optional[list[ControlVO]] = Field(default=None, validation_alias="planControls")
    error: Optional[str] = ""
    model_config = {
        "extra": "ignore",
    }

class AssessmentListVO(BaseModel):
    assessments: Optional[list[AssessmentVO]] = None
    error: Optional[str] = None
    model_config = {
        "extra": "ignore",
    }
    

class ControlLastRunDate(BaseModel):
    controlId: Optional[str] = ""
    latestRunDate: Optional[str] = ""
    executionId: Optional[str] = ""
    id: Optional[str] = ""
    model_config = {
        "extra": "ignore",
    }
    
class ControlsLastRunDate(BaseModel):
    controls: Optional[list[ControlLastRunDate]] = Field(default="", validation_alias="controls")
    error: Optional[str] = ""
    model_config = {
        "extra": "ignore",
    }