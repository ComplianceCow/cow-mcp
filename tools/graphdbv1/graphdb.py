
import json
import traceback
import traceback

from utils import utils
from utils.debug import logger
from mcptypes.graph_tool_types import CypherQueryVO
from mcpconfig.config import mcp
from constants import constants
from fastmcp import Context
from typing import Any

from mcptypes import assessment_run_tool_types as vo

@mcp.tool() 
async def execute_cypher_query(query: str, ctx: Context | None = None) -> CypherQueryVO: 
    """
    All the required information is available in the Neo4j graph. If any information is needed, fetch the data from the graph using this function. 
    If schema information is required, use the execute_cypher_query function to retrieve the relevant schema.
    """
    try:
        logger.info("\nexecute_cypher_query: \n")
        logger.debug("query: {}".format(query))

        output=await utils.make_API_call_to_CCow({
            "query": query,
        },constants.URL_EXECUTE_CYPHER_QUERY, ctx=ctx)
        logger.debug("output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("\nexecute_cypher_query error: {}\n".format(output))
            return CypherQueryVO(error="Facing internal error")

        return CypherQueryVO(result=output.get('result'))
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("\nexecute_cypher_query error: {}\n".format(e))
        return CypherQueryVO(error="Facing internal error")
    
    
# action tools
@mcp.tool()
async def fetch_available_control_actions(assessmentName: str, controlNumber: str = "", controlAlias: str = "", evidenceName: str = "", ctx: Context | None = None) -> vo.RecordListVO:
    """
        This tool should be used for handling control-related actions such as create, update, or to retrieve available actions for a given control.

        If no control details are given use the tool "fetch_controls" to get the control details.
        
        1. Fetch the available actions.
        2. Prompt the user to confirm the intended action.
        3. Once confirmed, use the `execute_action` tool with the appropriate parameters to carry out the operation.

        ### Args:
        -  assessmentName (str): Name of the assessment (**required**)
        -  controlNumber (str): Identifier for the control (**required**)
        - controlAlias (str): Alias of the control (**required**)

        If the above arguments are not available:
        - Use the `fetch_controls` tool to retrieve control details.
        - Then generate and execute a query to fetch the related assessment information before proceeding.
        
        Returns:
            - actions (list[ActionsVO]): List of actions
                - actionName (str):  Action name.
                - actionDescription (str): Action description.
                - actionSpecID (str): Action specific id.
                - actionBindingID (str): Action binding id.
                - target (str):  Target.
            - error (Optional[str]): An error message if any issues occurred during retrieval.

    """
    try:
        output=await utils.make_API_call_to_CCow({
            "actionType":"action",
            "assessmentName": assessmentName,
            "controlNumber" : controlNumber,
            "controlAlias": controlAlias,
            "evidenceName": evidenceName,
            "isRulesReq":True,
            "triggerType":"userAction"
        },constants.URL_FETCH_AVAILABLE_ACTIONS, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_available_control_actions error: {}\n".format(output))
            return vo.ActionsListVO(error="Facing internal error")
        
        actions: list[vo.ActionsVO] = []
        for item in output.get("items", []):
            if not item.get("actionBindingID"):
                continue
            rules = item.get("rules", [])
            if rules and isinstance(rules, list):
                rule_inputs = rules[0].get("ruleInputs", {})
                filtered_inputs = {
                    key: value for key, value in rule_inputs.items()
                    if not key.endswith("__")
                }
                item["ruleInputs"] = filtered_inputs

            item.pop("rules", None)
            actions.append(vo.ActionsVO.model_validate(item))
        
        logger.debug("output: {}\n".format(vo.ActionsListVO(actions=actions).model_dump()))
        return vo.ActionsListVO(actions=actions)
    except Exception as e:
        logger.error("fetch_available_control_actions error: {}\n".format(e))
        return vo.ActionsListVO(error="Facing internal error")
    
@mcp.tool()
async def fetch_assessment_available_actions(name: str = "", ctx: Context | None = None) -> vo.RecordListVO:
    """
        Get **actions available on assessment** for given assessment name. 
        Once fetched, ask user to confirm to execute the action, then use 'execute_action' tool with appropriate parameters to execute the action.
        Args: 
         - name (str): Assessment name
         
        Returns:
            - actions (list[ActionsVO]): List of actions
                - actionName (str):  Action name.
                - actionDescription (str): Action description.
                - actionSpecID (str): Action specific id.
                - actionBindingID (str): Action binding id.
                - target (str):  Target.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        output=await utils.make_API_call_to_CCow({
            "actionType":"action",
            "assessmentName": name,
            "isRulesReq":True,
            "triggerType":"userAction"
        },constants.URL_FETCH_AVAILABLE_ACTIONS, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_available_control_actions error: {}\n".format(output))
            return vo.ActionsListVO(error="Facing internal error")
        
        actions: list[vo.ActionsVO] = []
        for item in output.get("items", []):
            if not item.get("actionBindingID"):
                continue
            rules = item.get("rules", [])
            if rules and isinstance(rules, list):
                rule_inputs = rules[0].get("ruleInputs", {})
                filtered_inputs = {
                    key: value for key, value in rule_inputs.items()
                    if not key.endswith("__")
                }
                item["ruleInputs"] = filtered_inputs

            item.pop("rules", None)
            actions.append(vo.ActionsVO.model_validate(item))
        
        logger.debug("output: {}\n".format(vo.ActionsListVO(actions=actions).model_dump()))
        return vo.ActionsListVO(actions=actions)
    except Exception as e:
        logger.error("fetch_assessment_available_actions error: {}\n".format(e))
        return vo.ActionsListVO(error="Facing internal error")
    

@mcp.tool()
async def fetch_evidence_available_actions(assessment_name: str = "", control_number: str="", control_alias: str ="", evidence_name: str ="", ctx: Context | None = None) -> vo.ActionsListVO:
    """
        Get actions available on evidence for given evidence name. 
        If the required parameters are not provided, use the existing tools to retrieve them.
        Once fetched, ask user to confirm to execute the action, then use 'execute_action' tool with appropriate parameters to execute the action.
        Args: 
            - assessment_name (str): assessment name (required)
            - control_number (str): control number (required)
            - control_alias (str): control alias (required)  
            - evidence_name (str): evidence name (required)

        Returns:
            - actions (list[ActionsVO]): List of actions
                - actionName (str):  Action name.
                - actionDescription (str): Action description.
                - actionSpecID (str): Action specific id.
                - actionBindingID (str): Action binding id.
                - target (str):  Target.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        output=await utils.make_API_call_to_CCow({
            "actionType":"action",
            "assessmentName": assessment_name,
            "controlNumber" : control_number,
            "controlAlias": control_alias,
            "evidenceName": evidence_name,
            "isRulesReq":True,
            "triggerType":"userAction"
        },constants.URL_FETCH_AVAILABLE_ACTIONS, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_evidence_available_actions error: {}\n".format(output))
            return vo.ActionsListVO(error="Facing internal error")
                
        actions: list[vo.ActionsVO] = []
        for item in output.get("items", []):
            if not item.get("actionBindingID"):
                continue
            rules = item.get("rules", [])
            if rules and isinstance(rules, list):
                rule_inputs = rules[0].get("ruleInputs", {})
                filtered_inputs = {
                    key: value for key, value in rule_inputs.items()
                    if not key.endswith("__")
                }
                item["ruleInputs"] = filtered_inputs

            item.pop("rules", None)
            actions.append(vo.ActionsVO.model_validate(item))
        
        logger.debug("output: {}\n".format(vo.ActionsListVO(actions=actions).model_dump()))
        return vo.ActionsListVO(actions=actions)
    except Exception as e:
        logger.error("fetch_evidence_available_actions error: {}\n".format(e))
        return vo.ActionsListVO(error="Facing internal error")

@mcp.tool()
async def fetch_general_available_actions(type: str = "", ctx: Context | None = None) -> vo.ActionsListVO:
    """
        Get general actions available on assessment, control & evidence. 
        Once fetched, ask user to confirm to execute the action, then use 'execute_action' tool with appropriate parameters to execute the action.
        For inputs use default value as sample, based on that generate the inputs for the action.
        Args: 
            - type (str): Type of the action, can be "assessment", "control" or "evidence".

        Returns:
            - actions (list[ActionsVO]): List of actions
                - actionName (str):  Action name.
                - actionDescription (str): Action description.
                - actionSpecID (str): Action specific id.
                - actionBindingID (str): Action binding id.
                - target (str):  Target.
                - ruleInputs: Optional[dict[str, Any]]: Rule inputs for the action, if applicable.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        output=await utils.make_API_call_to_CCow({
            "actionType":"action",
            "targetType" : type,
            "isRulesReq":True,
            "triggerType":"userAction"
        },constants.URL_FETCH_AVAILABLE_ACTIONS, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_evidence_available_actions error: {}\n".format(output))
            return vo.ActionsListVO(error="Facing internal error")
                
        actions: list[vo.ActionsVO] = []
        for item in output.get("items", []):
            if not item.get("actionBindingID"):
                continue
            rules = item.get("rules", [])
            if rules and isinstance(rules, list):
                rule_inputs = rules[0].get("ruleInputs", {})
                filtered_inputs = {
                    key: value for key, value in rule_inputs.items()
                    if not key.endswith("__")
                }
                item["ruleInputs"] = filtered_inputs

            item.pop("rules", None)
            actions.append(vo.ActionsVO.model_validate(item))
        
        logger.debug("output: {}\n".format(vo.ActionsListVO(actions=actions).model_dump()))
        return vo.ActionsListVO(actions=actions)
    except Exception as e:
        logger.error("fetch_evidence_available_actions error: {}\n".format(e))
        return vo.ActionsListVO(error="Facing internal error")

@mcp.tool()
async def execute_action(assessmentId: str, assessmentRunId: str, actionBindingId: str , assessmentRunControlId: str="", assessmentRunControlEvidenceId: str="", evidenceRecordIds: list[str]=[], inputs: dict[str, Any] = None, ctx: Context | None = None) -> vo.TriggerActionVO:
    """
        Use this tool when the user asks about actions such as create, update or other action-related queries.

        IMPORTANT: This tool MUST ONLY be executed after explicit user confirmation. 
        Always prompt for REQUIRED-FROM-USER field from user and get inputs from user.
        Always confirm the inputs below execute action.
        Always describe the intended action and its effects to the user, then wait for their explicit approval before proceeding.
        Do not execute this tool without clear user consent, as it performs actual operations that modify system state.

        Execute or trigger a specific action on an assessment run. use assessment id, assessment run id and action binding id.
        Execute or trigger a specific action on an control run. use assessment id, assessment run id, action binding id and assessment run control id .
        Execute or trigger a specific action on an evidence level. use assessment id, assessment run id, action binding id, assessment run control evidence id and evidence record ids.
        Use fetch assessment available actions to get action binding id.
        Only once action can be triggered at a time, assessment level or control level or evidence level based on user preference.
        Use this to trigger action for assessment level or control level or evidence level.
        Please also provide the intended effect when executing actions.
        For inputs use default value as sample, based on that generate the inputs for the action. Format key - inputName value - inputValue.
        If inputs are provided, Always ensure to show all inputs to the user before executing the action, and also user to make changes to the inputs and also confirm modified inputs before executing the action.

        WORKFLOW:
        1. First fetch the available actions based on user preference assessment level or control level or evidence level
        2. Present the available actions to the user
        3. Ask user to confirm which specific action they want to execute
        4. Explain what the action will do and its expected effects
        5. Wait for explicit user confirmation before calling this tool
        6. Only then execute the action with this tool
        
        Args:
            - assessmentId 
            - assessmentRunId
            - actionBindingId
            - assessmentRunControlId - needed for control level action
            - assessmentRunControlEvidenceId - needed for evidence level action
            - evidenceRecordIds - needed for evidence level action
            - inputs (Optional[dict[str, Any]]): Additional inputs for the action, if required by the action's rules.
        
        Returns:
            - id (str): id of triggered action.
    """
    try:
        input_dict = {}
        if inputs:
            input_dict = {
                key: {
                    "name": key,
                    "value": value
                }
                for key, value in inputs.items()
            }
        
        req_body = {
            "actionBindingID": actionBindingId,
            "planInstanceID":assessmentRunId,
            "planID": assessmentId,
            "planInstanceControlID": assessmentRunControlId,
            "planInstanceControlEvidenceID": assessmentRunControlEvidenceId,
            "recordIDs": evidenceRecordIds,
            "actionInputs": input_dict
        }

        logger.debug("execute_action request body: {}\n".format(json.dumps(req_body)))

        output=await utils.make_API_call_to_CCow(req_body,constants.URL_ACTIONS_EXECUTIONS, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("execute_action error: {}\n".format(output))
            return vo.TriggerActionVO(error="Facing internal error")

        return vo.TriggerActionVO(id=output['id'])
    except Exception as e:
        logger.error("execute_action error: {}\n".format(e))
        return vo.TriggerActionVO(error="Facing internal error")