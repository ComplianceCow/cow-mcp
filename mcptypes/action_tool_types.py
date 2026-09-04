import base64
from pydantic import BaseModel, Field, model_validator
from enum import Enum
from typing import List, Optional, Dict, Any, Union


class ActionMetadataVO(BaseModel):
    name: Optional[str] = ""
    description: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }


class ActionSpecVO(BaseModel):
    id: Optional[str] = ""
    metadata: Optional[ActionMetadataVO] = None
    filePathHash: Optional[str] = ""
    state: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class ActionSpecListVO(BaseModel):
    items: Optional[List[ActionSpecVO]] = None
    error: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class ActionDeploymentInternalVO(BaseModel):
    cnFrameWorkID: Optional[str] = ""
    matchingPlan: Optional[str] = ""
    matchingControls: Optional[List[str]] = None
    applicationNames: Optional[List[str]] = None
    cloudConfigurationID: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }


class ActionDeploymentVO(BaseModel):
    id: Optional[str] = ""
    metadata: Optional[ActionMetadataVO] = None
    filePathHash: Optional[str] = ""
    state: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class ActionDeploymentListVO(BaseModel):
    items: Optional[List[ActionDeploymentVO]] = None
    error: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class ActionBindingVO(BaseModel):
    id: Optional[str] = ""
    metadata: Optional[ActionMetadataVO] = None
    filePathHash: Optional[str] = ""
    state: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class ActionBindingListVO(BaseModel):
    items: Optional[List[ActionBindingVO]] = None
    error: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class ActionLoopbackVO(BaseModel):
    id: Optional[str] = ""
    metadata: Optional[ActionMetadataVO] = None
    filePathHash: Optional[str] = ""
    state: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class ActionLoopbackListVO(BaseModel):
    items: Optional[List[ActionLoopbackVO]] = None
    error: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class ActionCreateResponseVO(BaseModel):
    success: bool = True
    id: Optional[str] = ""
    spec: Optional[Dict[str, Any]] = None
    message: Optional[str] = ""
    error: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

class ActionFileContentVO(BaseModel):
    success: bool = True
    contentDict: Optional[Dict[str, Any]] = None
    error: Optional[str] = ""
    model_config = {
        "extra": "ignore"
    }

# Action Payload Inputs & Enums for Creation and Updates

class ActionTargetEnum(str, Enum):
    SINGLE_RECORD = "Single Evidence Record"
    MULTIPLE_RECORDS = "Multiple Evidence Records"
    ENTIRE_FILE = "Entire Evidence File"
    CONTROL = "Control"
    ASSESSMENT = "Assessment"

class TriggerTypeEnum(str, Enum):
    USER_ACTION = "userAction"
    AUTOMATED_ACTION = "automatedAction"

class SourceBindingInputVO(BaseModel):
    assessmentName: str = Field(
        ..., 
        description="Name of the assessment (required for all targets)."
    )
    controlNumber: Optional[str] = Field(
        "", 
        description="Control number (e.g. '1.1'). If empty string '', targets ALL controls in the assessment."
    )
    evidenceName: Optional[str] = Field(
        "", 
        description="Evidence name (e.g. 'Evidence'). If empty string '', targets ALL evidences in the control."
    )

class ActionSpecMetadataInputVO(BaseModel):
    name: str = Field(..., description="Action spec name.")
    description: str = Field("", description="Action spec description.")

class MatchExpressionVO(BaseModel):
    sql: Optional[str] = Field("", description="SQL filter expression string (e.g. 'select * from df'). Defaults to empty string.")

class RecordsMatchVO(BaseModel):
    anyOf: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dictionary for anyOf match conditions. Defaults to empty dict {}")
    allOf: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dictionary for allOf match conditions. Defaults to empty dict {}")
    matchExpression: Optional[MatchExpressionVO] = Field(default_factory=MatchExpressionVO, description="Match SQL expression object.")

class ActionSpecTriggerVO(BaseModel):
    type: List[TriggerTypeEnum] = Field(
        default_factory=lambda: [TriggerTypeEnum.USER_ACTION],
        description="List of trigger types: 'userAction' (action performed by user), 'automatedAction' (action performed by system), or both. Defaults to ['userAction']."
    )
    recordsMatch: Optional[RecordsMatchVO] = Field(default_factory=RecordsMatchVO, description="Records match filters (anyOf, allOf, matchExpression).")

class LinkedRecordsVO(BaseModel):
    toBeInclude: bool = Field(False, description="Whether to include linked records. Defaults to False.")

class ActionSpecDetailInputVO(BaseModel):
    target: ActionTargetEnum = Field(..., description="Target scope of the action.")
    sourceBindings: List[SourceBindingInputVO] = Field(..., description="List of source bindings.")
    extendedAttributes: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Extended attributes dictionary. Defaults to empty dict {}")
    linkedRecords: Optional[LinkedRecordsVO] = Field(default_factory=LinkedRecordsVO, description="Linked records setting. Defaults to toBeInclude: False")
    trigger: Optional[ActionSpecTriggerVO] = Field(default_factory=ActionSpecTriggerVO, description="Trigger settings.")

    @model_validator(mode="after")
    def validate_target_rules(self):
        target = self.target
        for binding in self.sourceBindings:
            if target == ActionTargetEnum.ASSESSMENT:
                binding.controlNumber = ""
                binding.evidenceName = ""
            elif target == ActionTargetEnum.CONTROL:
                binding.evidenceName = ""
        return self

class ActionSpecCreatePayloadVO(BaseModel):
    apiVersion: str = Field("action.compliancecow.live/v1alpha1")
    kind: str = Field("action")
    metadata: ActionSpecMetadataInputVO
    spec: ActionSpecDetailInputVO


# Action App Scope & Deployment Rules
class ActionAppScopeVO(BaseModel):
    appScopeName: Optional[str] = Field(None, description="App scope name (e.g. 'awsiamtestingJ8'). Provide either appScopeName OR userApp, not both.")
    userApp: Optional[str] = Field(None, description="User app name (e.g. 'AWSIAM9'). Provide either appScopeName OR userApp, not both.")

    @model_validator(mode="after")
    def validate_app_scope(self):
        if self.appScopeName and self.userApp:
            raise ValueError("Only one of 'appScopeName' or 'userApp' must be provided in appScope, not both.")
        if not self.appScopeName and not self.userApp:
            raise ValueError("Either 'appScopeName' or 'userApp' must be provided in appScope.")
        return self

class RuleInputItemTypeEnum(str, Enum):
    STRING = "STRING"
    INT = "INT"
    BOOLEAN = "BOOLEAN"
    FLOAT = "FLOAT"
    FILE = "FILE"
    JSON = "JSON"
    HTTP_CONFIG = "HTTP_CONFIG"
    JQ_EXPRESSION = "JQ_EXPRESSION"
    SQL_EXPRESSION = "SQL_EXPRESSION"

class ActionRuleInputItemVO(BaseModel):
    name: str = Field(..., description="Rule input field name (e.g. 'RequestConfigFile', 'JQFilter').")
    type: RuleInputItemTypeEnum = Field(..., description="Type of rule input: STRING, INT, BOOLEAN, FLOAT, FILE, JSON, HTTP_CONFIG, JQ_EXPRESSION, SQL_EXPRESSION.")
    value: str = Field("", description="Value string. For FILE type, this contains the Base64 file bytes.")
    format: Optional[str] = Field(None, description="Format of file/content (e.g. 'toml', 'yaml', 'json', 'txt'). Recommended when type is 'FILE'.")

    @model_validator(mode="after")
    def auto_encode_file_value(self):
        if self.type == RuleInputItemTypeEnum.FILE and self.value:
            try:
                decoded_bytes = base64.b64decode(self.value.encode("utf-8"), validate=True)
                reencoded_str = base64.b64encode(decoded_bytes).decode("utf-8").strip()
                if reencoded_str == self.value.strip():
                    # Value is ALREADY valid Base64 string -> Leave untouched
                    return self
                else:
                    # Value is raw text -> Convert to Base64
                    self.value = base64.b64encode(self.value.encode("utf-8")).decode("utf-8")
            except Exception:
                # Not a Base64 string -> Convert raw text to Base64
                self.value = base64.b64encode(self.value.encode("utf-8")).decode("utf-8")
        return self



class ActionRuleInputVO(BaseModel):
    name: str = Field(..., description="Rule name (e.g. 'JiraActionCloud').")
    alias: str = Field(..., description="Rule alias (identical to name).")
    ruleInputs: Optional[Dict[str, Union[ActionRuleInputItemVO, Dict[str, Any]]]] = Field(
        default_factory=dict, 
        description="Rule inputs dict mapping input name (e.g. 'RequestConfigFile', 'JQFilter') to ActionRuleInputItemVO or dict."
    )
    appScope: ActionAppScopeVO = Field(..., description="App scope containing either appScopeName OR userApp.")

    @model_validator(mode="after")
    def sync_name_and_alias(self):
        if not self.alias:
            self.alias = self.name
        return self


# Action Deployment Output Mapping
class DeploymentMappingOutputDetailVO(BaseModel):
    category: str = Field(..., description="Category (e.g. 'jira/outputFile').")
    name: str = Field(..., description="Output file name.")
    compositeKey: List[str] = Field(default_factory=list, description="Composite key fields.")
    limitFields: Optional[List[str]] = Field(default_factory=list, description="Limited output fields.")

class DeploymentOutputMappingVO(BaseModel):
    output: DeploymentMappingOutputDetailVO

class ActionDeploymentSpecDetailVO(BaseModel):
    extendedAttributes: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Extended attributes dictionary. Defaults to empty dict {}")
    rules: List[ActionRuleInputVO] = Field(..., description="List of deployment rules. Typically contains 1 rule.")
    outputMapping: Optional[DeploymentOutputMappingVO] = None
    exceptionsMapping: Optional[DeploymentOutputMappingVO] = None

class ActionDeploymentCreatePayloadVO(BaseModel):
    apiVersion: str = Field("action.compliancecow.live/v1alpha1")
    kind: str = Field("actiondeployment")
    metadata: ActionSpecMetadataInputVO
    spec: ActionDeploymentSpecDetailVO

# Action Binding Payload
class ActionBindingSpecDetailVO(BaseModel):
    actionSpecName: str = Field(..., description="Name of the action spec to bind.")
    actionDeploymentName: str = Field(..., description="Name of the action deployment to bind.")

class ActionBindingCreatePayloadVO(BaseModel):
    apiVersion: str = Field("action.compliancecow.live/v1alpha1")
    kind: str = Field("actionbinding")
    metadata: ActionSpecMetadataInputVO
    spec: ActionBindingSpecDetailVO

# Action Loopback Payload & CallBack Config
class LoopbackTypeEnum(str, Enum):
    POLLING = "polling"
    PUSH = "push"

class ClientInfoVO(BaseModel):
    clientId: str = Field(..., description="Client ID dynamically provided (e.g. 'test123').")

class CallBackConfigVO(BaseModel):
    enableInternalValidation: bool = Field(True, description="Enable internal validation. Defaults to True.")
    clientInfo: ClientInfoVO = Field(..., description="Client info object containing clientId.")

class LoopbackMappingOutputDetailVO(BaseModel):
    category: str = Field(..., description="Category (e.g. 'jira/outputFile').")
    name: str = Field(..., description="Output file name.")
    compositeKey: List[str] = Field(default_factory=list, description="Composite key fields.")
    isKeyUnique: bool = Field(True, description="Whether key is unique. Defaults to True.")
    limitFields: Optional[List[str]] = Field(default_factory=list, description="Limited output fields.")
    fieldsMapping: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Fields mapping dictionary. Defaults to empty dict {}")

class LoopbackOutputMappingVO(BaseModel):
    mapToSourceBinding: bool = Field(True, description="Whether to map to source binding. Defaults to True.")
    output: LoopbackMappingOutputDetailVO

class ActionLoopbackSpecDetailVO(BaseModel):
    loopBackType: LoopbackTypeEnum = Field(..., description="Loopback type: 'polling' or 'push'.")
    deploymentName: str = Field(..., description="Deployment name for the loopback.")
    cronJob: Optional[str] = Field(None, description="Cron expression for polling loopback (e.g. '*/5 * * * *'). Defaults to '*/5 * * * *' for polling.")
    loopBackCount: Optional[int] = Field(None, description="Number of retries for polling loopback. Defaults to 1 for polling.")
    extendedAttributes: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Extended attributes dict. Defaults to empty dict {}")
    callbackFilters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Callback filters dict. Defaults to empty dict {}")
    callBackConfig: Optional[CallBackConfigVO] = Field(None, description="Callback config for push type loopback (contains enableInternalValidation: true and clientInfo.clientId).")
    rules: List[ActionRuleInputVO] = Field(..., description="Rules configuration list.")
    outputMapping: Optional[LoopbackOutputMappingVO] = None
    exceptionsMapping: Optional[LoopbackOutputMappingVO] = None

    @model_validator(mode="after")
    def validate_loopback_type_rules(self):
        if self.loopBackType == LoopbackTypeEnum.POLLING:
            if not self.cronJob:
                self.cronJob = "*/5 * * * *"
            if self.loopBackCount is None:
                self.loopBackCount = 1
            self.callBackConfig = None
        elif self.loopBackType == LoopbackTypeEnum.PUSH:
            self.cronJob = None
            self.loopBackCount = None
        return self

class ActionLoopbackCreatePayloadVO(BaseModel):
    apiVersion: str = Field("action.compliancecow.live/v1alpha1")
    kind: str = Field("actionloopback")
    metadata: ActionSpecMetadataInputVO
    spec: ActionLoopbackSpecDetailVO




