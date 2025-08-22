import json
import traceback
import base64
import asyncio
from typing import List
from typing import Tuple
import base64


from utils import utils
from utils.debug import logger
from mcpconfig.config import mcp

from constants import constants
from mcptypes import workflow_tools_type as vo
import yaml

@mcp.tool()
async def list_workflow_event_categories() -> vo.WorkflowEventCategoryListVO:
    """
    Retrieve available workflow event categories.
    
    Event categories help organize workflow triggers by type (e.g., assessment events, 
    time-based events, user actions). This is useful for filtering and selecting 
    appropriate events when building workflows.
    
    Returns:
        - eventCategories: List of event categories with type and displayable name
        - error: Error message if retrieval fails
    """
    try:
        logger.info("list_workflow_event_categories: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_EVENT_CATEGORIES)
        logger.debug("workflow event categories output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow event categories error: {}\n".format(output))
            return vo.WorkflowEventCategoryListVO(error="Facing internal error")
        
        eventCategories: List[vo.WorkflowEventCategoryItemVO]=[]
        for item in output["items"]:
            if "type" in item and "displayable" in item:
                eventCategories.append(vo.WorkflowEventCategoryItemVO.model_validate(item))
        
        logger.debug("modified event categories: {}\n".format(vo.WorkflowEventCategoryListVO(eventCategories=eventCategories).model_dump()))

        return vo.WorkflowEventCategoryListVO(eventCategories=eventCategories)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("workflow event categories: {}\n".format(e))
        return vo.WorkflowEventCategoryListVO(error="Facing internal error")

@mcp.tool()
async def list_workflow_events() -> vo.WorkflowEventListVO:
    """
    Retrieve available workflow events that can trigger workflows.
    
    Events are the starting points of workflows. Each event has a payload that 
    provides data to subsequent workflow nodes. Events are categorized into two types:
    
    **System Events**: Automatically triggered by the system when specific actions occur.
    Examples include:
    - Assessment run completed
    - Form submitted
    - Scheduled time-based triggers
    
    **Custom Events**: Manually triggered events that can be used to:
    - Trigger workflows from within other workflows
    - Integrate with external systems
    - Enable manual workflow execution
    
    Returns:
        - systemEvents (List[WorkflowEventVO]): A list of system events that are automatically triggered.
            - id (str)
            - categoryId (str)
            - desc (str)
            - displayable (str)
            - payload [List[WorkflowPayloadVO]]
            - status (str)
            - type (str)
        - customEvents (List[WorkflowEventVO]): A list of custom events that can be manually triggered.
            - id (str)
            - categoryId (str)
            - desc (str)
            - displayable (str)
            - payload [List[WorkflowPayloadVO]]
            - status (str)
            - type (str)
        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("Fetching workflow events")
        
        output = await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_EVENTS)
        logger.debug(f"Events response: {output}")
        
        if isinstance(output, str) or "error" in output:
            logger.error(f"Failed to fetch events: {output}")
            return vo.WorkflowEventListVO(error="Failed to retrieve events")
        
        systemEvents: List[vo.WorkflowEventVO] = []
        customEvents: List[vo.WorkflowEventVO] = []
        
        for item in output.get("items", []):
            if "type" in item and "displayable" in item and item.get("status") == "Active":
                event = vo.WorkflowEventVO.model_validate(item)
                
                # Categorize events based on eventType
                if item.get("type") == "CUSTOM_EVENT":
                    customEvents.append(event)
                else:
                    systemEvents.append(event)
        
        logger.debug("modified events - systemEvents: {}, customEvents: {}\n".format(
            len(systemEvents), len(customEvents)))

        return vo.WorkflowEventListVO(systemEvents=systemEvents, customEvents=customEvents)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("workflow events: {}\n".format(e))
        return vo.WorkflowEventListVO(error="Facing internal error")

@mcp.tool()
async def list_workflow_activity_types() -> List[str]:
    """
    Get available workflow activity types.
    
    Activity types define what kind of actions can be performed in workflow nodes:
    - Pre-build Function: Execute predefined logic
    - Pre-build Rule: Execute a rule
    - Pre-build Task: Trigger a predefined task
    
    Returns:
        List of available activity types
    """
    try:
        return ['Pre-build Function', 'Pre-build Rule', 'Pre-build Task', 'Existing Workflow']
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_workflow_activity_types error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def list_workflow_function_categories() -> vo.WorkflowActivityCategoryListVO:
    """
    Retrieve available workflow function categories.
    
    Function categories help organize workflow activities by type. This is useful 
    for filtering and selecting appropriate functions when building workflows.
    
    Returns:
        - activity categories (List[WorkflowActivityCategoryItemVO]): List of activity categories.
            - name (str): Name of the category.
        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("list_workflow_activity_categories: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_ACTIVITY_CATEGORIES)
        logger.debug("workflow activity categories output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow activity categories error: {}\n".format(output))
            return vo.WorkflowActivityCategoryListVO(error="Facing internal error")
        
        activityCategories: List[vo.WorkflowActivityCategoryItemVO]=[]
        for item in output["items"]:
            if "displayable" in item:
                activityCategories.append(vo.WorkflowActivityCategoryItemVO.model_validate(item))
        
        logger.debug("modified activity categories: {}\n".format(vo.WorkflowActivityCategoryListVO(activityCategories=activityCategories).model_dump()))

        return vo.WorkflowActivityCategoryListVO(activityCategories=activityCategories)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("workflow activity categories: {}\n".format(e))
        return vo.WorkflowActivityCategoryListVO(error="Facing internal error")

@mcp.tool()
async def list_workflow_functions() -> vo.WorkflowActivityListVO:
    """
    Retrieve available workflow functions (activities).
    
    Functions are the core actions that can be performed in workflow nodes. They 
    take inputs and produce outputs that can be used by subsequent nodes. Only 
    active functions are returned.
    
    Returns:
        - activities (List[WorkflowActivityVO]): List of active workflow functions with input/output specifications
            - id: Optional[str] = ""
            - categoryId (str)
            - desc (str)
            - displayable Optional[str] = ""
            - name (str)
            - inputs [List[WorkflowInputsVO]]
            - outputs [List[WorkflowOutputsVO]]
            - status (str)

        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("list_workflow_activities: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_ACTIVITIES)
        logger.debug("workflow activities output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow activities error: {}\n".format(output))
            return vo.WorkflowActivityListVO(error="Facing internal error")
        
        activities: List[vo.WorkflowActivityVO]=[]
        for item in output["items"]:
            if "displayable" in item and item.get("status") == "Active":
                activities.append(vo.WorkflowActivityVO.model_validate(item))
        
        logger.debug("modified activities: {}\n".format(vo.WorkflowActivityListVO(activities=activities).model_dump()))

        return vo.WorkflowActivityListVO(activities=activities)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("workflow activities: {}\n".format(e))
        return vo.WorkflowActivityListVO(error="Facing internal error")

@mcp.tool()
async def list_workflow_rules() -> vo.WorkflowRuleListVO:
    """
    Retrieve available workflow rules.
    
    Rules are predefined logic that can be executed in workflow nodes. They typically 
    handle data processing, validation, or business logic. Rules have inputs and 
    outputs that can be mapped to other workflow components.
    
    Returns:
        - rules (List[WorkflowRuleVO]): List of available workflow rules with input/output specifications
            - id (str)
            - name: (str)
            - description (str)
            - ruleInputs: [List[WorkflowRuleInputsVO]]
            - ruleOutputs: [List[WorkflowRuleOutputsVO]]

        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("list_workflow_prebuild_rules: \n")

        output=await utils.make_GET_API_call_to_CCow(f"{constants.URL_WORKFLOW_PREBUILD_RULES}?meta_tags=MCP")
        logger.debug("workflow rules output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow rules error: {}\n".format(output))
            return vo.WorkflowRuleListVO(error="Facing internal error")
        
        for item in output.get("items", []):
            if "ruleInputs" in item and isinstance(item["ruleInputs"], dict):
                item["ruleInputs"] = list(item["ruleInputs"].values())

            if "ruleOutputs" in item and isinstance(item["ruleOutputs"], dict):
                outputs = item["ruleOutputs"]
                transformed_rule_outputs = []
                for key, value in outputs.items():
                    if isinstance(value, dict) and not value:
                        transformed_rule_outputs.append({"name": key})
                    else:
                        transformed_rule_outputs.append(value)
                item["ruleOutputs"] = transformed_rule_outputs

        logger.error("Transformed rules output: {}\n".format(output))

        rules: List[vo.WorkflowRuleVO]=[]
        for item in output["items"]:
            if "name" in item:
                rules.append(vo.WorkflowRuleVO.model_validate(item))
        
        logger.debug("modified rules: {}\n".format(vo.WorkflowRuleListVO(rules=rules).model_dump()))

        return vo.WorkflowRuleListVO(rules=rules)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("workflow rules: {}\n".format(e))
        return vo.WorkflowRuleListVO(error="Facing internal error")

@mcp.tool()
async def fetch_workflow_rule(name: str) -> vo.WorkflowRuleListVO:
    """
    Retrieve a specific workflow rule by name.
    
    Finds and returns the single workflow rule that matches the provided name. This rule
    contains the input/output specifications needed for workflow operations.
    
    Args:
        name (str): The name of the workflow rule to retrieve
        
    Returns:
        - rules (List[WorkflowRuleVO]): List containing the single matched workflow rule with input/output specifications
            - id: (str)
            - name: (str) 
            - description: (str)
            - ruleInputs: [List[WorkflowRuleInputsVO]]
            - ruleOutputs: [List[WorkflowRuleOutputsVO]]

        - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        logger.info(f"fetch_workflow_rule: searching for rule '{name}'\n")

        output = await utils.make_GET_API_call_to_CCow(f"{constants.URL_WORKFLOW_PREBUILD_RULES}?name={name}")
        logger.debug("workflow rule output: {}\n".format(output))
        
        if isinstance(output, str) or "error" in output:
            logger.error("workflow rule error: {}\n".format(output))
            return vo.WorkflowRuleListVO(error="Facing internal error")
        
        for item in output.get("items", []):
            if "ruleInputs" in item and isinstance(item["ruleInputs"], dict):
                item["ruleInputs"] = list(item["ruleInputs"].values())

            if "ruleOutputs" in item and isinstance(item["ruleOutputs"], dict):
                outputs = item["ruleOutputs"]
                transformed_rule_outputs = []
                for key, value in outputs.items():
                    if isinstance(value, dict) and not value:
                        transformed_rule_outputs.append({"name": key})
                    else:
                        transformed_rule_outputs.append(value)
                item["ruleOutputs"] = transformed_rule_outputs

        if output.get("items") and len(output["items"]) > 0:
            item = output["items"][0]
            rule = vo.WorkflowRuleVO.model_validate(item)
            logger.debug("retrieved workflow rule: {}\n".format(rule.model_dump()))
            return vo.WorkflowRuleListVO(rules=[rule])
        
        logger.warning(f"No workflow rule returned for name: {name}")
        return vo.WorkflowRuleListVO(error=f"No workflow rule returned for name: {name}")

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_workflow_rule error: {}\n".format(e))
        return vo.WorkflowRuleListVO(error="Facing internal error")

@mcp.tool()
async def list_workflow_tasks() -> vo.WorkflowTaskListVO:
    """
    Retrieve available workflow tasks.
    
    Tasks are predefined operations that can be executed in workflow nodes. They 
    typically handle external integrations, notifications, or complex operations.
    Tasks have inputs and outputs that can be mapped to other workflow components.
    
    Returns:
        - tasks (List[WorkflowTaskVO]): List of available workflow tasks with input/output specifications
            - id (str)
            - name (str)
            - displayable (str)
            - description (str)
            - inputs: [List[WorkflowTaskInputsVO]]
            - outputs: [List[WorkflowTaskOutputsVO]]

        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("list_workflow_prebuild_tasks: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_PREBUILD_TASKS)
        logger.debug("workflow prebuild tasks output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow prebuild tasks error: {}\n".format(output))
            return vo.WorkflowTaskListVO(error="Facing internal error")

        tasks: List[vo.WorkflowTaskVO]=[]
        for item in output["items"]:
            if "name" in item:
                tasks.append(vo.WorkflowTaskVO.model_validate(item))
        
        logger.debug("modified tasks: {}\n".format(vo.WorkflowTaskListVO(tasks=tasks).model_dump()))

        return vo.WorkflowTaskListVO(tasks=tasks)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("prebuild tasks error: {}\n".format(e))
        return vo.WorkflowTaskListVO(error="Facing internal error")

@mcp.tool()
async def list_workflow_condition_categories() -> vo.WorkflowConditionCategoryListVO:
    """
    Retrieve available workflow condition categories.
    
    Condition categories help organize workflow decision points by type. This is 
    useful for filtering and selecting appropriate conditions when building workflows.
    
    Returns:
        - Condition categories (List[WorkflowConditionCategoryItemVO]): List of condition categories
            - name (str): Name of the category.
        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("list_workflow_condition_categories: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_CONDITION_CATEGORIES)
        logger.debug("workflow condition categories output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow condition categories error: {}\n".format(output))
            return vo.WorkflowConditionCategoryListVO(error="Facing internal error")
        
        conditionCategories: List[vo.WorkflowConditionCategoryItemVO]=[]
        for item in output["items"]:
            if "displayable" in item:
                conditionCategories.append(vo.WorkflowConditionCategoryItemVO.model_validate(item))
        
        logger.debug("modified condition categories: {}\n".format(vo.WorkflowConditionCategoryListVO(conditionCategories=conditionCategories).model_dump()))

        return vo.WorkflowConditionCategoryListVO(conditionCategories=conditionCategories)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("workflow condition categories: {}\n".format(e))
        return vo.WorkflowConditionCategoryListVO(error="Facing internal error")

@mcp.tool()
async def list_workflow_conditions() -> vo.WorkflowConditionListVO:
    """
    Retrieve available workflow conditions.
    
    Conditions are decision points in workflows that evaluate expressions or functions 
    to determine the flow path. They can use CEL expressions or predefined functions 
    to make branching decisions. Only active conditions are returned.
    
    Returns:
        - conditions (List[WorkflowConditionVO]): List of active workflow conditions with input/output specifications
            - categoryId (str)
            - desc (str)
            - displayable: (str)
            - inputs: [List[WorkflowInputsVO]]
            - outputs: [List[WorkflowOutputsVO]]
            - status: (str)

        - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        logger.info("list_workflow_conditions: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_CONDITIONS)
        logger.debug("workflow conditions output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow conditions error: {}\n".format(output))
            return vo.WorkflowConditionListVO(error="Facing internal error")
        
        conditions: List[vo.WorkflowConditionVO]=[]
        for item in output["items"]:
            if "displayable" in item and item.get("status") == "Active":
                conditions.append(vo.WorkflowConditionVO.model_validate(item))
        
        logger.debug("modified conditions: {}\n".format(vo.WorkflowConditionListVO(conditions=conditions).model_dump()))

        return vo.WorkflowConditionListVO(conditions=conditions)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("workflow conditions: {}\n".format(e))
        return vo.WorkflowConditionListVO(error="Facing internal error")

@mcp.tool()
async def fetch_workflow_resource_data(resource: str) -> List[any]:
    """
    Fetch workflow resource data for a given resource type.
    
    Resources provide dynamic data that can be used as inputs in workflow nodes. 
    This function retrieves available data for a specific resource type.
    
    Args:
        resource: The resource type to fetch data for. Resource options: USER_BLOCK
        
    Returns:
        List of resource data items or error message
    """
    try:
        logger.info("list_user_blocks: \n")

        output=await utils.make_API_call_to_CCow({"resource":resource},constants.URL_WORKFLOW_RESOURCE_DATA)
        logger.debug("list_user_blocks outputs : {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output or "items" not in output:
            logger.error("list_user_blocks error: {}\n".format(output))
            return output
        
        return output
    
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_user_blocks error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def create_workflow(workflow_yaml: str) -> str:
    """
    Create a new workflow using YAML definition.
    
    This function creates a workflow from a YAML specification. The YAML should 
    define the workflow structure including states, activities, conditions, and 
    transitions. Always display the workflow diagram and confirm with the user 
    before executing this tool.
    
    Args:
        workflow_yaml: YAML string defining the workflow structure
        
    Returns:
        Success message with workflow ID or error message
    """
    try:
        logger.info("Creating workflow from YAML")
        logger.debug(f"Workflow YAML: {workflow_yaml}")

        workflow_name = ""
        workflow_description = ""
        try:
            parsed_yaml = yaml.safe_load(workflow_yaml) if isinstance(workflow_yaml, str) else workflow_yaml
            if isinstance(parsed_yaml, dict):
                metadata = parsed_yaml.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {}
                    parsed_yaml["metadata"] = metadata
                metadata["tags"] = {"Channel": ["MCP_HOST"]}
                workflow_name = metadata.get("name") or ""
                workflow_description = metadata.get("description") or ""
                workflow_yaml = yaml.safe_dump(parsed_yaml, sort_keys=False)
        except Exception:
            logger.warning("Failed to set MCP tags or extract metadata from workflow YAML; proceeding with defaults")

        # Create workflow configuration first
        output = await utils.make_API_call_to_CCow_and_get_response(constants.URL_WORKFLOW_CREATE,"POST",workflow_yaml,type="yaml")
        logger.debug("create workflow output: {}\n".format(output))

        if not (output and isinstance(output, dict) and output.get("status") and output["status"].get("id")):
            logger.error(f"Failed to create workflow: {output}")
            return f"Failed to create workflow: {output}"

        workflow_id = output["status"]["id"]

        logger.info(f"Workflow created successfully with ID: {workflow_id}")

        # Build UI URL
        try:
            base_host = constants.host.rstrip("/api") if hasattr(constants, "host") and isinstance(constants.host, str) else getattr(constants, "host", "")
            ui_url = f"{base_host}/ui/workflow-config/{workflow_id}" if base_host else ""
        except Exception:
            ui_url = ""

        logger.info(f"Workflow created URL : {ui_url}")
        
        # Create Workflow Specification 
        spec_payload = {
            "metadata": {
                "name": workflow_name,
                "description": workflow_description,
                "tags":{
                    "Channel":["MCP_HOST"]
                }
            },
            "spec": {
                "resources": [
                    {
                        "type": "GENERAL",
                        "includes": [],
                        "excludes": [],
                    }
                ],
                "reviewers": {"references": []},
                "approvers": {"references": []},
            },
        }

        spec_resp = await utils.make_API_call_to_CCow_and_get_response(constants.URL_WORKFLOW_SPECS, "POST", spec_payload)
        logger.debug("create workflow spec output: {}\n".format(spec_resp))

        spec_id = None
        if isinstance(spec_resp, dict) and spec_resp.get("status") and spec_resp["status"].get("id"):
            spec_id = spec_resp["status"]["id"]
            logger.info(f"Workflow spec created successfully with ID: {spec_id}")
        else:
            logger.error(f"Failed to create workflow spec: {spec_resp}")

        # If spec creation failed, return summary without attempting binding
        if not spec_id:
            msg = f"Workflow created (ID: {workflow_id})."
            if ui_url:
                msg += f" UI: {ui_url}"
            return msg

        # Create Workflow Binding using the same name/description
        binding_payload = {
            "metadata": {
                "name": workflow_name,
                "description": workflow_description,
                "tags":{
                    "Channel":["MCP_HOST"]
                }
            },
            "spec": {
                "workflowResourceSpec": workflow_name,
                "workflowConfiguration": "",
                "workflowAdvancedConfig": workflow_name,
                "reviewers": {"references": []},
                "approvers": {"references": []},
            },
        }

        binding_resp = await utils.make_API_call_to_CCow_and_get_response(constants.URL_WORKFLOW_BINDINGS, "POST", binding_payload)
        logger.debug("create workflow binding output: {}\n".format(binding_resp))

        binding_id = None
        if isinstance(binding_resp, dict) and binding_resp.get("status") and binding_resp["status"].get("id"):
            binding_id = binding_resp["status"]["id"]
            logger.info(f"Workflow binding created successfully with ID: {binding_id}")
        else:
            logger.error(f"Failed to create workflow binding: {binding_resp}")

        # Build final message summarizing all creations
        if not binding_id:
            msg = f"Workflow created (ID: {workflow_id})."
            if ui_url:
                msg += f" UI: {ui_url}"
            return msg

        msg = f"Workflow created (ID: {workflow_id})."
        if ui_url:
            msg += f" UI: {ui_url}"
        return msg

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_workflow: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def list_workflows() -> dict | str:
    try:
        logger.info("get_workflows: \n")

        output=await utils.make_GET_API_call_to_CCow("/v3/workflow-configs?fields=meta")
        logger.debug("get_workflows output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("get_workflows error: {}\n".format(output))
            return "Facing internal error"
        if "items" in output:
            for item in output["items"]:
                utils.deleteKey(item,"domainId")
                utils.deleteKey(item,"orgId")
                utils.deleteKey(item,"groupId")
                utils.deleteKey(item,"spec")
                if "status" in item:
                    utils.deleteKey(item["status"],"filePathHash")
        logger.debug("get_workflows output: {}\n".format(output))
        return output["items"]
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_workflow: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_workflow_details(id:str) -> dict | str:
    """
        Args:
            - id (str): workflow id. This can be fetched from path /status/id of 'get_workflows' output
    """
    try:
        logger.info(f"get_workflow_details: {id}\n")

        output=await utils.make_GET_API_call_to_CCow("/v3/workflow-configs/"+id)
        logger.debug("get_workflows output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("get_workflows error: {}\n".format(output))
            return "Facing internal error"
        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_workflow: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def update_workflow_summary(id:str,summary:str) -> dict | str:
    """
        Args:
            - id (str): workflow id. This can be fetched from path /status/id of 'get_workflows' output
            - summary (str): workflow summary
    """
    try:
        logger.info(f"update_workflow_summary: {id}, {summary}\n")

        req=[
            {
                "op":"add",
                "path": "/metadata/summary",
                "value": summary
            }
        ]
        output=await utils.make_API_call_to_CCow_and_get_response("/v3/workflow-configs/"+id,"PATCH",req)
        logger.debug("get_workflows output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("get_workflows error: {}\n".format(output))
            return "Facing internal error"
        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_workflow: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def modify_workflow(workflow_yaml: str, workflow_id: str) -> str:
    """
    Modify an existing workflow using YAML definition.
    
    This function updates an existing workflow with a new YAML specification. 
    The workflow ID is required to identify which workflow to modify. Always 
    display the workflow diagram and confirm with the user before executing 
    this tool.
    
    Args:
        workflow_yaml: YAML string defining the updated workflow structure
        workflow_id: ID of the workflow to modify
        
    Returns:
        Success message or error message
    """
    try:
        logger.info(f"Modifying workflow with ID: {workflow_id}")
        logger.debug(f"Updated workflow YAML: {workflow_yaml}")

        response =await utils.make_API_call_to_CCow_and_get_response(f"{constants.URL_WORKFLOW_CREATE}/{workflow_id}","PUT",workflow_yaml,type="yaml",return_raw=True)
        logger.debug("create workflow output: {}\n".format(response))

        if response.status_code == 204:
            logger.info("Workflow updated successfully")
            return "Workflow updated successfully"
        else:
            try:
                error_msg = response.json().get("ErrorMessage", response.text)
            except Exception:
                error_msg = response.text or f"HTTP {response.status_code}"
            logger.error(f"Failed to modify workflow: {error_msg}")
            return f"Failed to update workflow: {error_msg}"
    
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("modify_workflow: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def list_workflow_predefined_variables() -> vo.WorkflowPredefinedVariableListVO:
    """
    Retrieve available predefined variables for workflow configuration.
    
    Predefined variables are system-level variables that can be used in workflow 
    configurations. These system-level variables are mapped to specific operations. When you set a value for a predefined variable, 
    it automatically triggers the associated system operation (like sending workflow failure notifications).
    Example:
        - Sending workflow failure notifications to specific users
        - Sending workflow failure notifications to admin
    Returns:
        - items (List[WorkflowPredefinedVariableVO]): A list of predefined variables.
            - id (str): Unique identifier of the predefined variable
            - type (str): Data type of the variable (e.g., Text, Boolean)
            - name (str): Name of the predefined variable
        - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        logger.info("list_workflow_predefined_variables: \n")

        output = await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_PREDEFINED_VARIABLES)
        logger.debug("workflow predefined variables output: {}\n".format(output))
        
        if isinstance(output, str) or "error" in output:
            logger.error(f"Failed to fetch predefined variables: {output}")
            return vo.WorkflowPredefinedVariableListVO(error="Failed to retrieve predefined variables")
        
        items = []
        for item in output.get("items", []):
            if "id" in item and "type" in item and "name" in item:
                items.append(vo.WorkflowPredefinedVariableVO.model_validate(item))
        
        logger.debug("modified predefined variables: {}\n".format(vo.WorkflowPredefinedVariableListVO(items=items).model_dump()))

        return vo.WorkflowPredefinedVariableListVO(items=items)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("workflow predefined variables: {}\n".format(e))
        return vo.WorkflowPredefinedVariableListVO(error="Facing internal error")


@mcp.tool()
async def create_workflow_custom_event(
    displayable: str,
    desc: str,
    payload: List[vo.WorkflowCustomEventPayloadVO],
    categoryId: str = "7",
    eventType: str = "CUSTOM_EVENT",
    confirm: bool = False
) -> str:
    """
    Create a Workflow Catalog Custom Event.
    Show a preview of the event configuration and ask for user confirmation before proceeding.
    Only create the event after explicit confirmation from user (confirm=True)
    This tool validates payload item types against allowed values and requires explicit
    user confirmation before creating the event.

    Args:
        - displayable: Event display name
        - desc: Event description
        - categoryId: Event category identifier
        - payload: List of payload items. Each item must have {name, type, desc}
                   and type must be one of: Text, MultilineText, TextArray, DynamicTextArray,
                   Number, File, Boolean, Json
        - eventType: Event type. Default: "CUSTOM_EVENT"
        - confirm: Boolean flag. If False, will show a preview for user confirmation.
                  Only returns True after user explicitly accepts the preview.
    Returns:
        - Success or error message
    """
    try:
        logger.info("create_workflow_custom_event: validating inputs")

        sanitized_payload: List[dict] = []
        for idx, item in enumerate(payload):
            if not isinstance(item, vo.WorkflowCustomEventPayloadVO):
                try:
                    item = vo.WorkflowCustomEventPayloadVO.model_validate(item)
                except Exception:
                    return f"Invalid payload item at index {idx}."

            sanitized_payload.append(item.model_dump())

        body_model = vo.WorkflowCustomEventCreateVO(
            displayable=displayable,
            desc=desc,
            categoryId=str(categoryId),
            payload=[vo.WorkflowCustomEventPayloadVO(**item) for item in sanitized_payload],
            type=eventType or "CUSTOM_EVENT",
        )
        body = body_model.model_dump()

        if not confirm:
            return json.dumps(
                {
                    "message": "Confirmation required before creating event",
                    "preview": body,
                    "next_step": "Re-run with confirm=True to create",
                },
                indent=2,
            )

        logger.info("create_workflow_custom_event: submitting request to API")
        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_WORKFLOW_EVENTS,
            "POST",
            body,
        )
        logger.debug("create_workflow_custom_event output: {}\n".format(output))

        if isinstance(output, str) or (isinstance(output, dict) and "id" not in output):
            logger.error(f"create_workflow_custom_event error: {output}")
            return f"Failed to create event: {output}"

        created_id = output.get("id")

        if created_id:
            return json.dumps({"id": created_id})

        return "Failed to create event"

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_workflow_custom_event: {}\n".format(e))
        return "Facing internal error"