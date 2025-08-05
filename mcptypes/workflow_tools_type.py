from pydantic import BaseModel, Field
from typing import List, Optional
    

class WorkflowEventCategoryItemVO(BaseModel):
    type: Optional[str] = ""
    displayable: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class WorkflowEventCategoryListVO(BaseModel):
    eventCategories: Optional[List[WorkflowEventCategoryItemVO]] = None
    error: Optional[str] = ""


class WorkflowActivityCategoryItemVO(BaseModel):
    displayable: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class WorkflowActivityCategoryListVO(BaseModel):
    activityCategories: Optional[List[WorkflowActivityCategoryItemVO]] = None
    error: Optional[str] = ""

    
class WorkflowConditionCategoryItemVO(BaseModel):
    displayable: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class WorkflowConditionCategoryListVO(BaseModel):
    conditionCategories: Optional[List[WorkflowConditionCategoryItemVO]] = None
    error: Optional[str] = ""

class WorkflowInputsVO(BaseModel):
    name: Optional[str] = ""
    desc: Optional[str] = ""
    type: Optional[str] = ""
    options: Optional[str] = ""
    optional: Optional[bool] = False
    resource: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class WorkflowOutputsVO(BaseModel):
    name: Optional[str] = ""
    desc: Optional[str] = ""
    type: Optional[str] = ""
    possible_values: Optional[List[str]] = None
    isPrimaryOutcome: Optional[bool] = False
    model_config = {
        "extra": "ignore"
    }

class WorkflowPayloadVO(BaseModel):
    name: Optional[str] = ""
    desc: Optional[str] = ""
    type: Optional[str] = ""
    possible_values: Optional[List[str]] = ""
    model_config = {
        "extra": "ignore"
    }

class WorkflowEventVO(BaseModel):
    id: Optional[str] = ""
    categoryId: Optional[str] = ""
    desc: Optional[str] = ""
    displayable: Optional[str] = ""
    payload: Optional[List[WorkflowPayloadVO]] = None
    status: Optional[str] = ""
    type: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class WorkflowEventListVO(BaseModel):
    events: Optional[List[WorkflowEventVO]] = None
    error: Optional[str] = ""


class WorkflowActivityVO(BaseModel):
    id: Optional[str] = ""
    categoryId: Optional[str] = ""
    desc: Optional[str] = ""
    displayable: Optional[str] = ""
    name: Optional[str] = ""
    inputs: Optional[List[WorkflowInputsVO]] = None
    outputs: Optional[List[WorkflowOutputsVO]] = None
    status: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class WorkflowActivityListVO(BaseModel):
    activities: Optional[List[WorkflowActivityVO]] = None
    error: Optional[str] = ""

class WorkflowConditionVO(BaseModel):
    categoryId: Optional[str] = ""
    desc: Optional[str] = ""
    displayable: Optional[str] = ""
    inputs: Optional[List[WorkflowInputsVO]] = None
    outputs: Optional[List[WorkflowOutputsVO]] = None
    status: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class WorkflowConditionListVO(BaseModel):
    conditions: Optional[List[WorkflowConditionVO]] = None
    error: Optional[str] = ""

class WorkflowTaskInputsVO(BaseModel):
    name: Optional[str] = ""
    description: Optional[str] = ""
    dataType: Optional[str] = ""
    required: Optional[bool] = False
    model_config = {
        "extra": "ignore"
    }

class WorkflowTaskOutputsVO(BaseModel):
    name: Optional[str] = ""
    description: Optional[str] = ""
    dataType: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class WorkflowTaskVO(BaseModel):
    name: Optional[str] = ""
    description: Optional[str] = ""
    inputs: Optional[List[WorkflowTaskInputsVO]] = None
    outputs: Optional[List[WorkflowTaskOutputsVO]] = None
    model_config = {
        "extra": "ignore"
    }

class WorkflowTaskListVO(BaseModel):
    tasks: Optional[List[WorkflowTaskVO]] = None
    error: Optional[str] = ""



class WorkflowRuleInputsVO(BaseModel):
    name: Optional[str] = ""
    description: Optional[str] = ""
    type: Optional[str] = ""
    isrequired: Optional[bool] = ""
    format: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class WorkflowRuleOutputsVO(BaseModel):
    name: Optional[str] = ""
    description: Optional[str] = ""
    type: Optional[str] = ""
    format: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class WorkflowRuleVO(BaseModel):
    name: Optional[str] = ""
    description: Optional[str] = ""
    ruleInputs: Optional[List[WorkflowRuleInputsVO]] = None
    ruleOutputs: Optional[List[WorkflowRuleOutputsVO]] = None
    model_config = {
        "extra": "ignore"
    }

class WorkflowRuleListVO(BaseModel):
    rules: Optional[List[WorkflowRuleVO]] = None
    error: Optional[str] = ""

class WorkflowPredefinedVariableVO(BaseModel):
    id: Optional[str] = ""
    type: Optional[str] = ""
    name: Optional[str] = ""
    desc: Optional[str] = ""

class WorkflowPredefinedVariableListVO(BaseModel):
    items: Optional[List[WorkflowPredefinedVariableVO]] = None
    error: Optional[str] = ""
