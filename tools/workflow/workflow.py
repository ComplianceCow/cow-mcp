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


@mcp.tool()
async def list_workflow_event_categories() -> vo.WorkflowEventCategoryListVO:
    """
        List workflow event categories

        Returns:
            - event categories (List[WorkflowEventCategoryItemVO]): A list of event categories.
                - type (str):  event category type.
                - name (str): Name of the category.
            - error (Optional[str]): An error message if any issues occurred during retrieval. 
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
        List workflow events

        Returns:
            - events (List[WorkflowEventVO]): A list of events.
                - categoryId (str)
                - desc (str)
                - name: (str)
                - payload: [List[WorkflowPayloadVO]]
                - status: (str)
                - type: (str)
            - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("list_workflow_events: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_EVENTS)
        logger.debug("workflow events output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow events error: {}\n".format(output))
            return vo.WorkflowEventListVO(error="Facing internal error")
        
        events: List[vo.WorkflowEventVO]=[]
        for item in output["items"]:
            if "type" in item and "displayable" in item and item.get("status") == "Active":
                events.append(vo.WorkflowEventVO.model_validate(item))
        
        logger.debug("modified events: {}\n".format(vo.WorkflowEventListVO(events=events).model_dump()))

        return vo.WorkflowEventListVO(events=events)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("workflow events: {}\n".format(e))
        return vo.WorkflowEventListVO(error="Facing internal error")

@mcp.tool()
async def list_workflow_activity_types() -> List[str]:
    """
        List workflow activite prebuild function categories
    """
    try:
        return ['Pre-build Function','Pre-build Rule','Pre-build Task']
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_workflow_activity_types error: {}\n".format(e))
        return vo.WorkflowActivityCategoryListVO(error="Facing internal error")

@mcp.tool()
async def list_workflow_function_categories() -> vo.WorkflowActivityCategoryListVO:
    """
        List workflow activity prebuild function categories

        Returns:
            - activity categories (List[WorkflowActivityCategoryItemVO]): A list of activity categories.
                - type (str): activity category type.
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
        List workflow activity prebuild functions

        Returns:
            - activities (List[WorkflowActivityVO]): A list of activities.
                - categoryId (str)
                - desc (str)
                - name: (str)
                - inputs: [List[WorkflowInputsVO]]
                - outputs: [List[WorkflowOutputsVO]]
                - status: (str)

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
        List workflow activity prebuild rules

        Returns:
            - rules (List[WorkflowRuleVO]): A list of rules.
                - name: (str)
                - desc (str)
                - ruleInputs: [List[WorkflowRuleInputsVO]]
                - ruleOutputs: [List[WorkflowRuleOutputsVO]]

            - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("list_workflow_prebuild_rules: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_PREBUILD_RULES)
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
async def list_workflow_tasks() -> vo.WorkflowTaskListVO:
    """
        List workflow activity prebuild tasks

        Returns:
            - tasks (List[WorkflowTaskVO]): A list of tasks.
                - name: (str)
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
        List workflow condition categories

        Returns:
            - Condition categories (List[WorkflowConditionCategoryItemVO]): A list of Condition categories.
                - type (str): Condition category type.
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
        List workflow conditions

        Returns:
            - conditions (List[WorkflowConditionVO]): A list of conditions.
                - categoryId (str)
                - desc (str)
                - name: (str)
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
        Fetch workflow resource data for given resource

        Returns:
            - List of resource data
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
        return "Facing internal error";

@mcp.tool()
async def create_workflow(workflow_yaml: str) -> str:
    """
        To create a workflow with YAML
        Always display the workflow diagram and confirm with the user before executing the tool to create the workflow.
        Returns:
            - message
            - Error
    """
    try:
        logger.info("create_workflow: \n")

        logger.debug("Input workFlowYaml: {}\n".format(workflow_yaml))

        output=await utils.make_API_call_to_CCow_and_get_response(constants.URL_WORKFLOW_CREATE,"POST",workflow_yaml,type="yaml")
        logger.debug("create workflow output: {}\n".format(output))
        
        if output and output.get("status") and output["status"].get("id"):
            workflow_id = output["status"]["id"]
            logger.info(f"Workflow created successfully, id:{workflow_id}")
            return f"Workflow created successfully, id:{workflow_id}"
        else:
            logger.error("Failed to create workflow: ",output)
            return output
    
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
        Modify Workflow with YAML
        To modify a workflow,It need the workflow ID and the corresponding YAML definition.
        Always display the workflow diagram and confirm with the user before executing the tool to modify the workflow.

        Returns:
            - message
            - Error
    """
    try:
        logger.info("modify_workflow: \n")

        logger.debug("Input workFlowYaml: {}\n".format(workflow_yaml))

        response =await utils.make_API_call_to_CCow_and_get_response(f"{constants.URL_WORKFLOW_CREATE}/{workflow_id}","PUT",workflow_yaml,type="yaml",return_raw=True)
        logger.debug("create workflow output: {}\n".format(response))

        if response.status_code == 204:
            return "Workflow upadted" 
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
