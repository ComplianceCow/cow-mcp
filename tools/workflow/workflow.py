import json
import re
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
from tools.workflow import blueprint_apply
from tools.workflow import blueprint_inspect
from tools.workflow import blueprint_prerequisites
from tools.workflow import blueprint_readmes
from tools.workflow import blueprint_scopes
from tools.workflow import rule_lookup
import yaml
from fastmcp import Context

import constants.error_constants as error_constants

@mcp.tool()
async def list_workflow_event_categories(ctx: Context | None = None) -> vo.WorkflowEventCategoryListVO:
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

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_EVENT_CATEGORIES,ctx)
        logger.debug("workflow event categories output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow event categories error: {}\n".format(output))
            return vo.WorkflowEventCategoryListVO(error="Facing internal error")
        
        eventCategories: list[vo.WorkflowEventCategoryItemVO]=[]
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
async def list_workflow_events(ctx: Context | None = None) -> vo.WorkflowEventListVO:
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
        - systemEvents (list[WorkflowEventVO]): A list of system events that are automatically triggered.
            - id (str)
            - categoryId (str)
            - desc (str)
            - displayable (str)
            - payload [list[WorkflowPayloadVO]]
            - status (str)
            - type (str)
        - customEvents (list[WorkflowEventVO]): A list of custom events that can be manually triggered.
            - id (str)
            - categoryId (str)
            - desc (str)
            - displayable (str)
            - payload [list[WorkflowPayloadVO]]
            - status (str)
            - type (str)
        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("Fetching workflow events")
        
        output = await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_EVENTS, ctx)
        logger.debug(f"Events response: {output}")
        
        if isinstance(output, str) or "error" in output:
            logger.error(f"Failed to fetch events: {output}")
            return vo.WorkflowEventListVO(error="Failed to retrieve events")
        
        systemEvents: list[vo.WorkflowEventVO] = []
        customEvents: list[vo.WorkflowEventVO] = []
        
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
async def list_workflow_activity_types(ctx: Context | None = None) -> list[str]:
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
async def list_workflow_function_categories(ctx: Context | None = None) -> vo.WorkflowActivityCategoryListVO:
    """
    Retrieve available workflow function categories.
    
    Function categories help organize workflow activities by type. This is useful 
    for filtering and selecting appropriate functions when building workflows.
    
    Returns:
        - activity categories (list[WorkflowActivityCategoryItemVO]): List of activity categories.
            - name (str): Name of the category.
        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("list_workflow_activity_categories: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_ACTIVITY_CATEGORIES, ctx)
        logger.debug("workflow activity categories output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow activity categories error: {}\n".format(output))
            return vo.WorkflowActivityCategoryListVO(error="Facing internal error")
        
        activityCategories: list[vo.WorkflowActivityCategoryItemVO]=[]
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
async def list_workflow_functions(ctx: Context | None = None) -> vo.WorkflowActivityListVO:
    """
    Retrieve available workflow functions (activities).
    
    Functions are the core actions that can be performed in workflow nodes. They 
    take inputs and produce outputs that can be used by subsequent nodes. Only 
    active functions are returned.
    
    Returns:
        - activities (list[WorkflowActivityVO]): List of active workflow functions with input/output specifications
            - id: Optional[str] = ""
            - categoryId (str)
            - desc (str)
            - displayable Optional[str] = ""
            - name (str)
            - inputs [list[WorkflowInputsVO]]
            - outputs [list[WorkflowOutputsVO]]
            - status (str)

        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("list_workflow_activities: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_ACTIVITIES, ctx)
        logger.debug("workflow activities output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow activities error: {}\n".format(output))
            return vo.WorkflowActivityListVO(error="Facing internal error")
        
        activities: list[vo.WorkflowActivityVO]=[]
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
async def list_workflow_rules(ctx: Context | None = None) -> vo.WorkflowRuleListVO:
    """
    Retrieve available workflow rules.
    
    Rules are predefined logic that can be executed in workflow nodes. They typically 
    handle data processing, validation, or business logic. Rules have inputs and 
    outputs that can be mapped to other workflow components.
    
    Returns:
        - rules (list[WorkflowRuleVO]): List of available workflow rules with input/output specifications
            - id (str)
            - name: (str)
            - description (str)
            - ruleInputs: [list[WorkflowRuleInputsVO]]
            - ruleOutputs: [list[WorkflowRuleOutputsVO]]

        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("list_workflow_prebuild_rules: \n")

        output=await utils.make_GET_API_call_to_CCow(f"{constants.URL_WORKFLOW_PREBUILD_RULES}?type=rule&meta_tags=MCP", ctx)
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

        rules: list[vo.WorkflowRuleVO]=[]
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
async def fetch_workflow_rule(name: str, ctx: Context | None = None) -> vo.WorkflowRuleListVO:
    """
    Retrieve a specific workflow rule by name.
    
    Finds and returns the single workflow rule that matches the provided name. This rule
    contains the input/output specifications needed for workflow operations.
    
    Args:
        name (str): The name of the workflow rule to retrieve
        
    Returns:
        - rules (list[WorkflowRuleVO]): List containing the single matched workflow rule with input/output specifications
            - id: (str)
            - name: (str) 
            - description: (str)
            - ruleInputs: [list[WorkflowRuleInputsVO]]
            - ruleOutputs: [list[WorkflowRuleOutputsVO]]

        - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        logger.info(f"fetch_workflow_rule: searching for rule '{name}'\n")

        output = await utils.make_GET_API_call_to_CCow(f"{constants.URL_WORKFLOW_PREBUILD_RULES}?name={name}", ctx)
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
async def fetch_task_readme(name: str, ctx: Context | None = None) -> vo.TaskReadmeResponseVO:
    """
    Retrieve README documentation for a specific task by name.
    
    Fetches the complete README documentation for a task, providing 
    detailed information about the task's purpose, usage instructions, prerequisites, 
    and implementation steps. This is useful for understanding how to properly use 
    a task in workflows.
    
    Args:
        name (str): The exact name of the task to retrieve README for
        
    Returns:
        - readmeText (str): Complete README documentation as readable text
        - taskName (str): Name of the task for reference
        - error (str): Error message if retrieval fails or README not available
    """
    try:
        logger.info(f"fetch_task_readme: searching for task '{name}'\n")

        output = await utils.make_GET_API_call_to_CCow(f"{constants.URL_FETCH_TASK_README}?name={name}", ctx)
        logger.debug("task readme output: {}\n".format(output))
        
        if isinstance(output, str) or "error" in output:
            logger.error("task readme error: {}\n".format(output))
            return vo.TaskReadmeResponseVO(error="Facing internal error")
        
        if not output.get("items") or len(output["items"]) == 0:
            logger.warning(f"No task found with name: {name}")
            return vo.TaskReadmeResponseVO(taskName=name, error=f"Task '{name}' not available")
        
        task_item = output["items"][0]
        task_name = task_item.get("name", name)
        readme_data = task_item.get("readmeData", "")
        
        if not readme_data:
            logger.warning(f"No README data found for task: {name}")
            return vo.TaskReadmeResponseVO(taskName=task_name, error=f"README not available for task: {name}")
        
        try:
            readme_text = base64.b64decode(readme_data).decode('utf-8')
            logger.debug(f"Successfully decoded README for task: {task_name}")
            return vo.TaskReadmeResponseVO(readmeText=readme_text, taskName=task_name)
        except Exception as decode_error:
            logger.error(f"Failed to decode README data for task {name}: {decode_error}")
            return vo.TaskReadmeResponseVO(taskName=task_name, error=f"Failed to decode README data for task: {name}")

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_task_readme error: {}\n".format(e))
        return vo.TaskReadmeResponseVO(error="Facing internal error")

@mcp.tool()
async def fetch_rule_readme_documentaion(name: str, ctx: Context | None = None) -> vo.RuleReadmeResponseVO:
    """
    Retrieve README documentation for a specific rule by name.
    
    Fetches the complete README documentation for a rule, providing 
    detailed information about the rule's purpose, usage instructions, prerequisites, 
    and implementation steps. This is useful for understanding how to properly use 
    a rule in workflows.
    
    Args:
        name (str): The exact name of the rule to retrieve README for
        
    Returns:
        - readmeText (str): Complete README documentation as readable text
        - ruleName (str): Name of the rule for reference
        - error (str): Error message if retrieval fails or README not available
    """
    try:
        logger.info(f"fetch_rule_readme: searching for rule '{name}'\n")

        output = await utils.make_GET_API_call_to_CCow(f"{constants.URL_FETCH_RULE_README}?name={name}", ctx)
        logger.debug("rule readme output: {}\n".format(output))
        
        if isinstance(output, str) or "error" in output:
            logger.error("rule readme error: {}\n".format(output))
            return vo.RuleReadmeResponseVO(error="Facing internal error")
        
        if not output.get("items") or len(output["items"]) == 0:
            logger.warning(f"No rule found with name: {name}")
            return vo.RuleReadmeResponseVO(ruleName=name, error=f"Rule '{name}' not available")
        
        rule_item = output["items"][0]
        rule_name = rule_item.get("name", name)
        readme_hash = rule_item.get("readme", "")
        
        if not readme_hash:
            logger.warning(f"No README hash found for rule: {name}")
            return vo.RuleReadmeResponseVO(ruleName=rule_name, error=f"README not available for rule: {name}")
        
        try:
            readme_response = await utils.make_GET_API_call_to_CCow(f"{constants.URL_FETCH_FILE_BY_HASH}/{readme_hash}", ctx)
            logger.debug(f"README fetch response for rule {rule_name}: {readme_response}")
            
            if isinstance(readme_response, str) or "error" in readme_response:
                logger.error(f"Failed to fetch README content for rule {name}: {readme_response}")
                return vo.RuleReadmeResponseVO(ruleName=rule_name, error=f"Failed to fetch README content for rule: {name}")
            
            readme_text = ""
            if isinstance(readme_response, dict):
                file_content = readme_response.get("FileContent", "")
                if file_content:
                    try:
                        readme_text = base64.b64decode(file_content).decode('utf-8')
                    except Exception:
                        readme_text = file_content
                else:
                    logger.warning(f"No FileContent found in response for rule: {name}")
                    return vo.RuleReadmeResponseVO(ruleName=rule_name, error=f"README not available for rule: {name}")
            elif isinstance(readme_response, str):
                readme_text = readme_response
            
            if not readme_text:
                logger.warning(f"No README content found for rule: {name}")
                return vo.RuleReadmeResponseVO(ruleName=rule_name, error=f"README not available for rule: {name}")
            
            logger.debug(f"Successfully fetched README for rule: {rule_name}")
            return vo.RuleReadmeResponseVO(readmeText=readme_text, ruleName=rule_name)
            
        except Exception as fetch_error:
            logger.error(f"Failed to fetch README content for rule {name}: {fetch_error}")
            return vo.RuleReadmeResponseVO(ruleName=rule_name, error=f"Failed to fetch README content for rule: {name}")

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_rule_readme error: {}\n".format(e))
        return vo.RuleReadmeResponseVO(error="Facing internal error")

@mcp.tool()
async def list_workflow_tasks(ctx: Context | None = None) -> vo.WorkflowTaskListVO:
    """
    Retrieve available workflow tasks.
    
    Tasks are predefined operations that can be executed in workflow nodes. They 
    typically handle external integrations, notifications, or complex operations.
    Tasks have inputs and outputs that can be mapped to other workflow components.
    
    Returns:
        - tasks (list[WorkflowTaskVO]): List of available workflow tasks with input/output specifications
            - id (str)
            - name (str)
            - displayable (str)
            - description (str)
            - inputs: [list[WorkflowTaskInputsVO]]
            - outputs: [list[WorkflowTaskOutputsVO]]

        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("list_workflow_prebuild_tasks: \n")

        output = await utils.make_GET_API_call_to_CCow(f"{constants.URL_WORKFLOW_PREBUILD_TASKS}?tags=MCP-WORKFLOW", ctx)
        logger.debug("workflow prebuild tasks output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow prebuild tasks error: {}\n".format(output))
            return vo.WorkflowTaskListVO(error="Facing internal error")

        tasks: list[vo.WorkflowTaskVO]=[]
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
async def list_workflow_condition_categories(ctx: Context | None = None) -> vo.WorkflowConditionCategoryListVO:
    """
    Retrieve available workflow condition categories.
    
    Condition categories help organize workflow decision points by type. This is 
    useful for filtering and selecting appropriate conditions when building workflows.
    
    Returns:
        - Condition categories (list[WorkflowConditionCategoryItemVO]): List of condition categories
            - name (str): Name of the category.
        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("list_workflow_condition_categories: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_CONDITION_CATEGORIES, ctx)
        logger.debug("workflow condition categories output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow condition categories error: {}\n".format(output))
            return vo.WorkflowConditionCategoryListVO(error="Facing internal error")
        
        conditionCategories: list[vo.WorkflowConditionCategoryItemVO]=[]
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
async def list_workflow_conditions(ctx: Context | None = None) -> vo.WorkflowConditionListVO:
    """
    Retrieve available workflow conditions.
    
    Conditions are decision points in workflows that evaluate expressions or functions 
    to determine the flow path. They can use CEL expressions or predefined functions 
    to make branching decisions. Only active conditions are returned.
    
    Returns:
        - conditions (list[WorkflowConditionVO]): List of active workflow conditions with input/output specifications
            - categoryId (str)
            - desc (str)
            - displayable: (str)
            - inputs: [list[WorkflowInputsVO]]
            - outputs: [list[WorkflowOutputsVO]]
            - status: (str)

        - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        logger.info("list_workflow_conditions: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_CONDITIONS, ctx)
        logger.debug("workflow conditions output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow conditions error: {}\n".format(output))
            return vo.WorkflowConditionListVO(error="Facing internal error")
        
        conditions: list[vo.WorkflowConditionVO]=[]
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
async def fetch_workflow_resource_data(resource: str, ctx: Context | None = None) -> dict | str:
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

        output=await utils.make_API_call_to_CCow({"resource":resource},constants.URL_WORKFLOW_RESOURCE_DATA, ctx=ctx)
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
async def create_workflow(workflow_yaml: str, ctx: Context | None = None) -> str:
    """
    Create a new workflow using YAML definition. Always display the workflow diagram. 
    Before creation confirm workflow name and creation with the user before executing this tool. 
    Later use 'modify_workflow' tool to update states, activities, conditions, and transitions.

    yaml struct:
    
    metadata:
        name:
        description:
        summary:
        mermaidDiagram:

    This function creates a workflow from a YAML specification.

    Create workflow (establishes the ID)
    Update summary (document what we're building)
    Update mermaid diagram (visualize the flow)
    Then modify workflow (implement the actual logic)
    
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
        output = await utils.make_API_call_to_CCow_and_get_response(constants.URL_WORKFLOW_CREATE,"POST",workflow_yaml,type="yaml", ctx=ctx)
        logger.debug("create workflow output: {}\n".format(output))

        if not (output and isinstance(output, dict) and output.get("status") and output["status"].get("id")):
            logger.error(f"Failed to create workflow: {output}")
            return f"Failed to create workflow: {output}"

        workflow_id = output["status"]["id"]

        logger.info(f"Workflow created successfully with ID: {workflow_id}")

        # Build UI URL
        ui_url = utils.get_workflow_config_ui_url(workflow_id) if workflow_id else ""
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
                        "type": "GENERIC",
                        "includes": [],
                        "excludes": [],
                    }
                ],
                "reviewers": {"references": []},
                "approvers": {"references": []},
            },
        }

        spec_resp = await utils.make_API_call_to_CCow_and_get_response(constants.URL_WORKFLOW_SPECS, "POST", spec_payload, ctx=ctx)
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

        binding_resp = await utils.make_API_call_to_CCow_and_get_response(constants.URL_WORKFLOW_BINDINGS, "POST", binding_payload, ctx=ctx)
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
async def list_workflows(ctx: Context | None = None) -> list | str:
    """
    Retrieve a list of all available workflow configurations.
    
    Returns:
        - List of workflow configuration items : Each item contains workflow metadata
        - Error message (str): If retrieval fails or an error occurs
    
    """
    try:
        logger.info("list_workflows: \n")

        output=await utils.make_GET_API_call_to_CCow("/v3/workflow-configs?fields=meta", ctx)
        logger.debug("list_workflows output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("list_workflows error: {}\n".format(output))
            return "Facing internal error"
        if "items" in output:
            for item in output["items"]:
                utils.trimWorkflowDetails(item)
                workflow_id = (item.get("status") or {}).get("id") or item.get("id") or ""
                item["uiUrl"] = utils.get_workflow_config_ui_url(workflow_id) if workflow_id else ""
                # utils.deleteKey(item,"domainId")
                # utils.deleteKey(item,"orgId")
                # utils.deleteKey(item,"groupId")
                # utils.deleteKey(item,"spec")
                # if "status" in item:
                #     utils.deleteKey(item["status"],"filePathHash")
        # output["items"]=[]
        logger.debug("list_workflows output: {}\n".format(output))
        return output["items"]
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_workflow: {}\n".format(e))
        return "Facing internal error"


@mcp.tool()
async def get_workflow_by_name(name: str, ctx: Context | None = None) -> dict | str:
    """
        Get a workflow configuration by its name (exact, case-sensitive match).

        Args:
            - name (str): workflow name to search
    """
    try:
        logger.info(f"get_workflow_by_name: {name}\n")

        output = await utils.make_GET_API_call_to_CCow(f"/v3/workflow-configs?name={name}", ctx)
        logger.debug("get_workflow_by_name output: {}\n".format(output))

        if isinstance(output, str) or  "error" in output:
            logger.error("get_workflow_by_name error: {}\n".format(output))
            return "Facing internal error"
        if "items" in output and isinstance(output["items"], list):
            for item in output["items"]:
                utils.trimWorkflowDetails(item, True)
            if len(output["items"]) > 0:
                item = output["items"][0]
                workflow_id = (item.get("status") or {}).get("id") or item.get("id") or ""
                item["uiUrl"] = utils.get_workflow_config_ui_url(workflow_id) if workflow_id else ""
                return item
            return "No workflow found with the given name"
        return "Facing internal error"
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_workflow_by_name: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_workflow_details(id:str, ctx: Context | None = None) -> dict | str:
    """
        Args:
            - id (str): workflow id. This can be fetched from path /status/id of 'get_workflows' output
    """
    try:
        logger.info(f"fetch_workflow_details: {id}\n")

        output=await utils.make_GET_API_call_to_CCow("/v3/workflow-configs/"+id, ctx)
        logger.debug("fetch_workflow_details output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_workflow_details error: {}\n".format(output))
            return "Facing internal error"
        if isinstance(output, dict):
            output["uiUrl"] = utils.get_workflow_config_ui_url(id) if id else ""
        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_workflow_details: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def update_workflow_summary(id:str,summary:str, ctx: Context | None = None) -> dict | str:
    """
        Args:
            - id (str): workflow id. This can be fetched from path /status/id of 'get_workflows' output
            - summary (str): workflow summary, preferably ReadMe.
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
        output=await utils.make_API_call_to_CCow_and_get_response("/v3/workflow-configs/"+id,"PATCH",req, ctx=ctx)
        logger.debug("update_workflow_summary output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("update_workflow_summary error: {}\n".format(output))
            return "Facing internal error"
        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_workflow_summary: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def update_workflow_mermaid_diagram(id:str,mermaidDiagram:str, ctx: Context | None = None) -> dict | str:
    """
        Args:
            - id (str): workflow id. This can be fetched from path /status/id of 'get_workflows' output
            - mermaidDiagram (str): workflow mermaid diagram
    """
    try:
        logger.info(f"update_workflow_mermaid_diagram: {id}, {mermaidDiagram}\n")

        req=[
            {
                "op":"add",
                "path": "/metadata/mermaidDiagram",
                "value": mermaidDiagram
            }
        ]
        output=await utils.make_API_call_to_CCow_and_get_response("/v3/workflow-configs/"+id,"PATCH",req, ctx=ctx)
        logger.debug("update_workflow_mermaid_diagram output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("update_workflow_mermaid_diagram error: {}\n".format(output))
            return "Facing internal error"
        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_workflow_mermaid_diagram: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def modify_workflow(workflow_yaml: str, workflow_id: str, ctx: Context | None = None) -> str:
    """
    Modify an existing workflow using YAML definition.
    
    The workflow ID (UUID) is required to identify which workflow to modify. This 
    function updates an existing workflow with a new YAML specification. The YAML 
    should define the workflow structure including states, activities, conditions, 
    and transitions. Always display the workflow diagram and confirm with the 
    user before executing this tool.

    BEFORE using 'modify_workflow' tool, you MUST check:
    - Do I have the complete CCow workflow YAML schema?
    - Do I know the exact state configuration requirements?
    - Do I understand the data flow and variable reference patterns?
    If the answer to ANY of these is "no", respond with:
    "I need CCow workflow schema knowledge to properly implement this workflow. 
    Please provide the workflow YAML specification, state definitions, and 
    integration patterns before I proceed with modify_workflow."

    
    Args:
        workflow_yaml: YAML string defining the updated workflow structure
        workflow_id: ID of the workflow to modify
        
    Returns:
        Success message or error message
    """
    try:
        logger.info(f"Modifying workflow with ID: {workflow_id}")
        logger.debug(f"Updated workflow YAML: {workflow_yaml}")

        response =await utils.make_API_call_to_CCow_and_get_response(f"{constants.URL_WORKFLOW_CREATE}/{workflow_id}","PUT",workflow_yaml,type="yaml",return_raw=True, ctx=ctx)
        logger.debug("create workflow output: {}\n".format(response))

        if response.status_code == 502:
            return error_constants.ERROR_BAD_GATEWAY

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
async def list_workflow_predefined_variables(ctx: Context | None = None) -> vo.WorkflowPredefinedVariableListVO:
    """
    Retrieve available predefined variables for workflow configuration.
    
    Predefined variables are system-level variables that can be used in workflow 
    configurations. These system-level variables are mapped to specific operations. When you set a value for a predefined variable, 
    it automatically triggers the associated system operation (like sending workflow failure notifications).
    Example:
        - Sending workflow failure notifications to specific users
        - Sending workflow failure notifications to admin
    Returns:
        - items (list[WorkflowPredefinedVariableVO]): A list of predefined variables.
            - id (str): Unique identifier of the predefined variable
            - type (str): Data type of the variable (e.g., Text, Boolean)
            - name (str): Name of the predefined variable
        - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        logger.info("list_workflow_predefined_variables: \n")

        output = await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_PREDEFINED_VARIABLES, ctx)
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
    payload: list[vo.WorkflowCustomEventPayloadVO],
    categoryId: str = "7",
    eventType: str = "CUSTOM_EVENT",
    confirm: bool = False,
    ctx: Context | None = None
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

        sanitized_payload: list[dict] = []
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
            ctx=ctx,
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

@mcp.tool()
async def trigger_workflow(
    workflowConfigId: str,
    event: str,
    inputs: dict | None = None,
    confirm: bool = False,
    ctx: Context | None = None
) -> str:
    """
    Trigger a workflow by the given workflow config id.
    
    Args:
        - workflowConfigId: The workflow config id 
        - event: Start event name.
        - inputs: Additional input payload for the event. IMPORTANT: Input values must be obtained from the user only - do not pass random/placeholder values. Each field requires meaningful user-provided values.
        - confirm: If False, shows a preview of required inputs and does not execute. If True, executes.

    Returns:
        - JSON string containing execution acknowledgement or error message
    """
    try:
        logger.info(f"trigger_workflow: workflowConfigId={workflowConfigId}, event={event}, inputs={inputs}, confirm={confirm}")

        query = {
            "workflow_advanced_config_id": workflowConfigId,
            "page": 1,
            "page_size": 1,
        }
        bindings_resp = await utils.make_API_call_to_CCow_and_get_response(
            f"{constants.URL_WORKFLOW_BINDINGS}", "GET", query, ctx=ctx
        )
        logger.debug(f"trigger_workflow bindings_resp: {bindings_resp}")

        if isinstance(bindings_resp, str) or not isinstance(bindings_resp, dict) or not bindings_resp.get("items"):
            logger.error(f"Failed to resolve workflow binding: {bindings_resp}")
            return "Failed to execute workflow"

        item = bindings_resp["items"][0]
        status = item.get("status", {}) if isinstance(item, dict) else {}
        binding_id = status.get("id", "")

        if not binding_id:
            logger.error("No binding ID found in response")
            return "Failed to execute workflow"

        exec_inputs = inputs.copy() if isinstance(inputs, dict) else {}
        if event and isinstance(event, str):
            exec_inputs["event"] = event
        if "event" not in exec_inputs or not isinstance(exec_inputs["event"], str) or not exec_inputs["event"].strip():
            logger.error("Missing or invalid event in inputs")
            return "Starting event is required"

        required_fields: list[str] = []
        try:
            logger.info("Fetching workflow events to validate required fields")
            events_resp = await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_EVENTS, ctx)

            if isinstance(events_resp, dict) and events_resp.get("items"):
                for ev in events_resp["items"]:
                    displayable = ev.get("displayable")
                    if isinstance(displayable, str) and displayable.strip() == exec_inputs["event"].strip():
                        payload_list = ev.get("payload") or []
                        for p in payload_list:
                            name = p.get("name") if isinstance(p, dict) else None
                            if isinstance(name, str) and name:
                                required_fields.append(name)
                        break
            logger.debug(f"Required fields for event: {required_fields}")
        except Exception as e:
            logger.error(f"Error fetching workflow events: {e}")
            required_fields = required_fields

        missing = []
        if required_fields:
            for f in required_fields:
                if f not in exec_inputs or exec_inputs.get(f) in [None, ""]:
                    missing.append(f)
            logger.debug(f"Missing required fields: {missing}")

        preview_body = {
            "workflowBindingId": binding_id,
            "input": exec_inputs,
        }

        if not confirm or missing:
            logger.info("Returning preview/validation response")
            return json.dumps({
                "message": "Confirmation required before executing workflow",
                "event": exec_inputs.get("event"),
                "requiredInputs": required_fields,
                "provided": {k: v for k, v in exec_inputs.items() if k != "event"},
                "missing": missing,
                "next_step": "Provide missing inputs (if any) and re-run with confirm=True to execute"
            })

        body = {
            "workflowBindingId": binding_id,
            "input": exec_inputs,
        }

        logger.info(f"Executing workflow: {json.dumps(body)}")


        exec_resp = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_WORKFLOW_BINDINGS_EXECUTE, "POST", body, ctx=ctx
        )
        logger.debug(f"trigger_workflow exec_resp: {exec_resp}")

        if isinstance(exec_resp, str):
            logger.error(f"Error response from execute API: {exec_resp}")
            return exec_resp

        logger.info("Workflow triggered successfully")
        return json.dumps(exec_resp)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("trigger_workflow error: {}\n".format(e))
        return "Facing internal error"


@mcp.tool(annotations=utils.tool_annotations("List Workflow Blueprints", read_only = True))
async def list_workflow_blueprints(name: str = None, search: str = None, ctx: Context | None = None) -> dict | list | str:
    """
    Lists the workflow blueprints that can be used to create workflows. A blueprint is a folder of one workflow and the workflows it starts, not yet created in the tenant.

    Without `name` it returns a SHORT list, one row per blueprint folder: folder, workflow (its name), description, and hasDefinition (false for folders that cannot be deployed
    with create_workflow_from_blueprint). Use it to find a blueprint by purpose, and `search` to narrow it by words (every word must appear, any case) in the folder name,
    workflow name or description, for example search="jira ticket". Then call inspect_workflow_blueprint(<folder>) to see the workflows it starts and what it needs.

    With `name` it returns the FULL definition of that one folder (the workflow in config and the workflows it starts in config.subworkflow). That is very long (about 180,000
    characters for the Jira chain): do not call it to look at a blueprint, use inspect_workflow_blueprint, and create_workflow_from_blueprint reads the definition itself. `name` is the
    exact, case-sensitive folder name from the short list: it is not a search, so a keyword or a partial name returns nothing. An empty result for `name` does not mean no blueprint exists.

    Args:
        name: Exact folder name, to get that blueprint's full definition.
        search: Words to narrow the short list.

    Returns:
        - A list of rows (no name), or the folder's definition (name), or an error message.
    """
    try:
        logger.info("list_workflow_blueprints: \n")
        params = {"name": name} if name else {"fields": "basic"}
        output=await utils.make_API_call_to_CCow_and_get_response("/pc-api/v1/workflows",method="GET",request_body=params,ctx=ctx)
        error = utils.build_structured_error(output, "list_workflow_blueprints")
        if error:
            logger.error(f"list_workflow_blueprints error: {output}\n")
            return {"success": False, "error": error}
        if name:
            return output
        if not isinstance(output, dict) or "items" not in output:
            return {"success": False, "error": output}
        return blueprint_inspect.summarize_listing(output, search)

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_workflow_blueprints error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error list workflow blueprints: {e}"}


def _plain(value):
    return value.model_dump() if hasattr(value, "model_dump") else value


async def _rule_place(name: str, ctx: Context | None) -> str:
    """Where a rule is: "tenant", "catalog" (the platform publishes it when a workflow using it is created), "missing", or "unchecked" when a lookup failed."""
    found = _plain(await fetch_workflow_rule(name, ctx))
    if not isinstance(found, dict):
        return "unchecked"
    if any(r.get("name") == name for r in found.get("rules") or []):
        return "tenant"
    if found.get("error") and not str(found["error"]).startswith("No workflow rule returned"):
        return "unchecked"
    catalog = await utils.make_API_call_to_CCow_and_get_response(constants.URL_FETCH_RULES, method="GET", request_body={"name": name}, ctx=ctx)
    if not isinstance(catalog, dict) or not isinstance(catalog.get("items"), list):
        return "unchecked"
    return "catalog" if any((i.get("meta") or {}).get("name") == name for i in catalog["items"] if isinstance(i, dict)) else "missing"


async def _tenant_events(ctx: Context | None) -> list[dict] | None:
    try:
        return blueprint_prerequisites.tenant_events(_plain(await list_workflow_events(ctx))) or None
    except Exception:
        return None


async def _prerequisites_for(specs: dict[str, dict], ctx: Context | None) -> dict[str, dict]:
    """What each workflow needs (events, rules, functions) against what the tenant has, with every lookup made once."""
    needed = {name: blueprint_inspect.needs(spec) for name, spec in specs.items()}
    events = await _tenant_events(ctx)
    try:
        functions = blueprint_prerequisites.tenant_functions(_plain(await list_workflow_functions(ctx))) or None if any(n["functions"] for n in needed.values()) else []
    except Exception:
        functions = None
    names = sorted({r["name"] for n in needed.values() for r in n["rules"]})
    gate = asyncio.Semaphore(5)

    async def place(name: str):
        async with gate:
            try:
                return name, await _rule_place(name, ctx)
            except Exception:
                return name, "unchecked"

    places = dict(await asyncio.gather(*(place(n) for n in names)))
    return {name: blueprint_prerequisites.check(spec, events, functions, places) for name, spec in specs.items()}


async def _rule_app_types(name: str, ctx: Context | None) -> set[str] | None:
    catalog = await utils.make_API_call_to_CCow_and_get_response(constants.URL_FETCH_RULES, method="GET", request_body={"name": name}, ctx=ctx)
    if not isinstance(catalog, dict) or not isinstance(catalog.get("items"), list):
        return None
    rule = next((i for i in catalog["items"] if isinstance(i, dict) and (i.get("meta") or {}).get("name") == name), None)
    return blueprint_scopes.rule_app_types(rule) if rule else None


async def _scope_found(name: str, ctx: Context | None) -> dict | None:
    """{"types": the application types of the scope} when it exists, {"types": None} when it does not, None when a lookup failed."""
    try:
        from tools.applications import applications
        listed = await applications.list_application_scopes(name=name, ctx=ctx)
        if not isinstance(listed, dict) or not isinstance(listed.get("items"), list):
            return None
        scope = next((s for s in listed["items"] if s.get("name") == name), None)
        if scope is None:
            return {"types": None}
        types: set[str] = set()
        for application_id in scope.get("applications") or []:
            found = await applications.list_applications(id=application_id, ctx=ctx)
            rows = found.get("applications") if isinstance(found, dict) else None
            if rows is None:
                return None
            types.update(blueprint_scopes.normalize(a.get("applicationType")) for a in rows)
        return {"types": types}
    except Exception:
        return None


async def _scope_checks_for(specs: dict[str, dict], ctx: Context | None) -> dict[str, dict]:
    """For each workflow: the application types its rules need against the applications of the scope they run under, with every lookup made once."""
    gate = asyncio.Semaphore(5)

    async def guarded(lookup, name):
        async with gate:
            try:
                return name, await lookup(name, ctx)
            except Exception:
                return name, None

    rule_names = sorted({r["name"] for spec in specs.values() for r in blueprint_inspect.needs(spec)["rules"]})
    scope_names = sorted({scope for spec in specs.values() for scope in blueprint_inspect.app_scopes(spec)})
    rule_types = dict(await asyncio.gather(*(guarded(_rule_app_types, n) for n in rule_names)))
    scopes = dict(await asyncio.gather(*(guarded(_scope_found, n) for n in scope_names)))
    return {name: blueprint_scopes.check(spec, rule_types, scopes) for name, spec in specs.items()}


@mcp.tool(annotations=utils.tool_annotations("Find Rule By Name", read_only = True))
async def find_rule_by_name(name: str, ctx: Context | None = None) -> dict:
    """
    Looks up ONE rule by its exact name in everything the platform holds: the rules published in the tenant and the rule catalog, whether or not the rule is tagged for
    discovery. Use it when a rule is named explicitly (by the requirement, a blueprint or a person) and get_rules_summary does not list it. To find rules by what they do, use
    get_rules_summary: it lists only the rules tagged for discovery.

    Returns success (false when the rule is in neither place), name and where: "tenant" (published), "catalog" (published by the platform when a workflow that uses it is
    created), "missing", or "unchecked" when a lookup failed. When found it also returns what the two services hold about the rule: purpose, description, appTypes (the
    application types the rule and its tasks need, lower case, `nocredapp` needs no credential), discoverable (whether get_rules_summary lists it; null for a rule found only in
    the tenant), inputs ({name, type, required}), outputs ({name, type, description}) and readme (the README text, or null when the rule has none: many rules do not).
    lookupFailed names a service ("tenant" or "catalog") that could not be read: what only it holds, for example the README, is then unknown, not absent. Call the tool again.
    """
    tenant = await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_PREBUILD_RULES, ctx, query_params={"name": name})
    catalog = await utils.make_API_call_to_CCow_and_get_response(constants.URL_FETCH_RULES, method="GET", request_body={"name": name, "include_read_me": "true"}, ctx=ctx)
    rows = lambda response: response.get("items") if isinstance(response, dict) else None
    return rule_lookup.describe(name, rows(tenant), rows(catalog))


async def _blueprint_call(params: dict, ctx: Context | None):
    return await utils.make_API_call_to_CCow_and_get_response("/pc-api/v1/workflows", method="GET", request_body=params, ctx=ctx)


async def _rule_readmes(names: list[str], ctx: Context | None) -> dict[str, str | None]:
    """Per rule: its README, "" when it has none, None when the lookup failed."""
    gate = asyncio.Semaphore(5)

    async def one(name):
        async with gate:
            try:
                found = await utils.make_API_call_to_CCow_and_get_response(constants.URL_FETCH_RULES, method="GET", request_body={"name": name, "include_read_me": "true"}, ctx=ctx)
            except Exception:
                return name, None
        rows = found.get("items") if isinstance(found, dict) else None
        return name, None if rows is None else rule_lookup.readme_of(name, rows) or ""

    return dict(await asyncio.gather(*(one(n) for n in names)))


@mcp.tool(annotations=utils.tool_annotations("Inspect Workflow Blueprint", read_only = True))
async def inspect_workflow_blueprint(name: str, find: list[str] | None = None, include_literals: bool = False, activities: list[str] | None = None, check_tenant: bool = False, include_rule_readmes: bool = False, ctx: Context | None = None) -> dict:
    """
    Reads a workflow blueprint, and every workflow it starts, and reports what must be rebound before the workflow is created for a new use case. Changes nothing.

    Args:
        name: Name of the blueprint folder, which is the key of the item in list_workflow_blueprints (not the name of a workflow inside it).
        find: Optional strings (for example an assessment or evidence name from the blueprint) to locate in every value of every workflow in the blueprint.
        include_literals: Also list every input that has a fixed value instead of being mapped from an earlier node.
        check_tenant: Also look up, on the platform, every event, rule and function each workflow needs (prerequisites per workflow, and prerequisitesMissing for the whole blueprint).
            Do this before asking anyone about anything missing. A rule that is not in the tenant but is in the catalog is published by the platform when the workflow is created.
            It also compares the application types the rules need with the applications of the application scope they run under (applicationScope per workflow): the blueprint's own
            scope belongs to another use case, and a scope that is missing or lacks an application for a rule's type is reported in prerequisitesMissing.
        include_rule_readmes: Also return the README of every rule the workflows run (ruleReadmes: per rule, the workflows that use it and its README text; rulesWithoutReadme: rules that
            have none; ruleReadmesUnchecked: rules whose README could not be read, so it is unknown, not absent). A README can say which columns its input evidence must contain.
            Use it when the evidence that triggers the workflow is being designed. The result is large: leave it off otherwise.
        activities: Activity or condition labels whose inputs to list in full (inputDetails): each input's description, type, options, current value, whether it is optional,
            where it is mapped from, and whether it can be set. Use it on the activities whose description says they take a value that depends on the use case.

    Returns:
        - chain.order: workflow names in the order they must be created; a workflow that starts others comes after them.
        - chain.missing / chain.cycle: workflows the blueprint starts that are not in it, or the loop of workflows that start each other.
        - workflows[name]: triggers (start events with the quoted values in their filter), workflows (the `Workflow` activities: child name, id, start event, async),
          fixedFiles (files uploaded with the blueprint), templates (descriptions carrying a structure the user's file must follow),
          appScopes, conditionLiterals, and occurrences for `find`.
        The id of a workflow started by another is the id create_workflow returned for it in the tenant, and is set only after it exists: the ids in a
        blueprint belong to the tenant that made it, and a wrong id is accepted when the parent is created and fails when it runs.
    """
    try:
        output = await _blueprint_call({"name": name}, ctx)
        if not isinstance(output, dict) or "items" not in output:
            return {"success": False, "error": output}
        entry = blueprint_inspect.blueprint_named(output, name)
        if entry is None:
            known = blueprint_inspect.names_in(await _blueprint_call({"fields": "basic"}, ctx))
            return {"success": False, "error": f"No workflow blueprint named '{name}'.", "available": known}
        root, library = blueprint_inspect.library_of(entry)
        if root is None:
            return {"success": False, "error": f"The blueprint '{name}' has no workflow definition (config)."}
        chain = blueprint_inspect.chain_of(root, library)
        report = {
            "success": True,
            "chain": chain,
            "workflows": {n: blueprint_inspect.inspect(d, find, include_literals, activities) for n, d in library.items()},
        }
        if check_tenant:
            checked = await _prerequisites_for({n: d.get("spec") or {} for n, d in library.items()}, ctx)
            for n, result in checked.items():
                report["workflows"][n]["prerequisites"] = blueprint_prerequisites.summarize(result)
            scoped = await _scope_checks_for({n: d.get("spec") or {} for n, d in library.items()}, ctx)
            for n, result in scoped.items():
                report["workflows"][n]["applicationScope"] = result["scopes"]
            report["prerequisitesMissing"] = [f"{n}: {m}" for n, r in checked.items() for m in r["missing"]] + [f"{n}: {m}" for n, r in scoped.items() for m in r["missing"]]
            report["prerequisitesUnchecked"] = sorted({u for r in checked.values() for u in r["unchecked"]} | {u for r in scoped.values() for u in r["unchecked"]})
        if include_rule_readmes:
            specs = {n: d.get("spec") or {} for n, d in library.items()}
            report.update(blueprint_readmes.collect(specs, await _rule_readmes(blueprint_readmes.rule_names(specs), ctx)))
        return report
    except Exception as e:
        logger.error(traceback.format_exc())
        return {"success": False, "error": f"Unexpected error inspecting workflow blueprint: {e}"}


async def _workflow_name_taken(name: str, ctx: Context | None) -> bool | None:
    found = await get_workflow_by_name(name, ctx)
    if isinstance(found, dict):
        return True
    return False if found == "No workflow found with the given name" else None


async def _unknown_children(started: list[dict], ctx: Context | None) -> list[str]:
    """The workflows it starts whose id is not the id of a workflow with that name in this tenant."""
    problems = []
    for child in {(c["id"], c["name"]): c for c in started}.values():
        found = await fetch_workflow_details(child["id"], ctx)
        actual = (found.get("metadata") or {}).get("name") if isinstance(found, dict) else None
        if actual != child["name"]:
            what = "no workflow has that id" if actual is None else f"that id is the workflow '{actual}'"
            problems.append(f"'{child['name']}' was given the id {child['id']}, but {what}")
    return problems


@mcp.tool(annotations=utils.tool_annotations("Create Workflow From Blueprint", read_only = False))
async def create_workflow_from_blueprint(
    name: str,
    workflow: str | None = None,
    new_name: str | None = None,
    replacements: list[dict] | None = None,
    children: dict[str, dict] | None = None,
    files: list[dict] | None = None,
    keep_files: list[str] | None = None,
    set_inputs: list[dict] | None = None,
    check_prerequisites: bool = True,
    check_application_scope: bool = True,
    dry_run: bool = True,
    ctx: Context | None = None,
) -> dict:
    """
    Creates one workflow of a blueprint for a new use case, changing only what is listed here and nothing else, so the definition is never retyped.
    Call it first with dry_run=True (the default): it creates nothing and reports what would change and what is still missing. Create with dry_run=False only
    after the user has confirmed, and only when `ready` is true. Create the workflows of inspect_workflow_blueprint's chain.order one by one, children first.

    Args:
        name: Name of the blueprint folder (the key in list_workflow_blueprints).
        workflow: Name of the workflow inside the blueprint to create; omit for the blueprint's own (top-level) workflow.
        new_name: Name to create it under; omit to keep the blueprint's name. A workflow with that name must not exist.
        replacements: [{"from": "<text in the blueprint>", "to": "<new text>", "optional": false}]. Replaces the text inside every value (never ids or types).
            A "from" that is not found is an error unless optional. Use the quoted values inspect_workflow_blueprint reports (for example the whole start-event filter).
        children: {"<name of a workflow it starts, as in the blueprint>": {"id": "<id of that workflow in this tenant>", "name": "<its new name>", "displayable": "<optional>"}}.
            Every workflow it starts must be listed; the id is the one create_workflow_from_blueprint or create_workflow returned for it, or the id of the existing workflow adopted.
            Each id is checked against the tenant: it must be the id of a workflow with that name, so an id made up for a rehearsal makes `ready` false.
        files: [{"activity": "<activity label>", "input": "<input name>", "value": "<hash of the uploaded file>", "fileName": "<optional>"}] for files the blueprint uploaded.
        keep_files: activity labels whose uploaded file is deliberately kept as the blueprint has it.
        set_inputs: [{"activity": "<activity label>", "input": "<input name>", "value": <value>}] sets an input that is not taken from another step, including one that has no value yet.
            The value must fit the input's type: Boolean true or false, Number a number, DropDown one of its options, TextArray a list or comma-separated text. Files go in `files`.
        check_prerequisites: look up on the platform the events, rules and functions the workflow needs (prerequisites). A missing custom event, function, or a rule that is in neither
            the tenant nor the catalog is a problem; a rule only in the catalog is published by the platform when the workflow is created. Leave it on.
        check_application_scope: check that the application scope the workflow's rules run under (after your replacements) exists and holds an application of every type the rules and their tasks
            need. A workflow is created without this being checked and fails when it runs, so a missing or too small scope is a problem. Turn it off only when the user says the scope is right.
        dry_run: true to only report.

    Returns:
        ready (nothing missing), problems, eventsRebound (custom events pointed at this tenant's own event of the same name, with the id each had), inputsSet (what each input was and now is), pendingChildren (started workflows without an id yet), unresolvedFiles (uploaded files neither replaced nor kept),
        leftovers (replaced text still present), replacements (with how many places and where), workflowsStarted, files, nameTaken, and when created: created.id.
    """
    try:
        output = await _blueprint_call({"name": name}, ctx)
        if not isinstance(output, dict) or "items" not in output:
            return {"success": False, "error": output}
        entry = blueprint_inspect.blueprint_named(output, name)
        if entry is None:
            return {"success": False, "error": f"No workflow blueprint named '{name}'.", "available": blueprint_inspect.names_in(output)}
        root, library = blueprint_inspect.library_of(entry)
        if root is None:
            return {"success": False, "error": f"The blueprint '{name}' has no workflow definition (config)."}
        target = workflow or (root.get("metadata") or {}).get("name")
        if target not in library:
            return {"success": False, "error": f"The blueprint '{name}' has no workflow named '{target}'.", "available": sorted(library)}

        result = blueprint_apply.apply(library[target], new_name, replacements, children, files, keep_files, set_inputs)
        result["problems"].extend(await _unknown_children(result["workflowsStarted"], ctx))
        result["eventsRebound"] = blueprint_apply.bind_events(result["doc"], await _tenant_events(ctx) or [])
        if check_prerequisites:
            prerequisites = (await _prerequisites_for({result["name"]: library[target].get("spec") or {}}, ctx))[result["name"]]
            result["prerequisites"] = blueprint_prerequisites.summarize(prerequisites)
            result["problems"].extend(prerequisites["missing"])
        if check_application_scope:
            scoped = (await _scope_checks_for({result["name"]: result["doc"].get("spec") or {}}, ctx))[result["name"]]
            result["applicationScope"] = scoped["scopes"]
            result["problems"].extend(scoped["missing"])
            if scoped["unchecked"]:
                result["applicationScopeUnchecked"] = scoped["unchecked"]
        taken = await _workflow_name_taken(result["name"], ctx)
        if taken:
            result["problems"].append(f"a workflow named '{result['name']}' already exists")
        elif taken is None:
            result["problems"].append(f"could not check whether a workflow named '{result['name']}' already exists")
        result["ready"] = result["ready"] and taken is False and not result["problems"]
        report = {k: v for k, v in result.items() if k != "doc"}
        report["nameTaken"] = taken

        if dry_run:
            return {"success": True, "dryRun": True, **report}
        if not result["ready"]:
            return {"success": False, "dryRun": False, "error": "Nothing was created: the workflow is not ready.", **report}

        message = await create_workflow(blueprint_apply.to_yaml(result["doc"]), ctx)
        created = re.search(r"\(ID: ([0-9a-fA-F-]{36})\)", message) if isinstance(message, str) else None
        if not created:
            return {"success": False, "dryRun": False, "error": message, **report}
        return {"success": True, "dryRun": False, "created": {"id": created.group(1), "name": result["name"], "message": message}, **report}
    except Exception as e:
        logger.error(traceback.format_exc())
        return {"success": False, "error": f"Unexpected error creating the workflow from the blueprint: {e}"}
