import json
import traceback
import base64
from typing import List
from typing import Tuple

from utils import utils
from utils.debug import logger
from mcpconfig import mcp
from constants import constants


@mcp.tool()
async def fetch_recent_assessment_runs(id: str) -> list | str:
    """
        Get recent assessment run for given assessment id

        Args:
        id: assessment id
    """
    try:
        output=await utils.make_GET_API_call_to_CCow("/v1/plan-instances?fields=basic&page=1&page_size=10&plan_id="+id)
        logger.debug("output: {}\n".format(output))

        if isinstance(output, str):
            return output
        
        recentAssessmentRuns = []

        for item in output["items"]:
            if "planId" in item and "id" in item:
                filtered_item = {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "assessmentId": item.get("planId"),
                    "applicationType": item.get("applicationType"),
                    "configId": item.get("configId"),
                    "fromDate": item.get("fromDate"),
                    "toDate": item.get("toDate"),
                    "started": item.get("started"),
                    "ended": item.get("ended"),
                    "status": item.get("status"),
                    "computedScore": item.get("computedScore"),
                    "computedWeight": item.get("computedWeight"),
                    "complianceStatus": item.get("complianceStatus"),
                    "createdAt": item.get("createdAt"),
                }
                recentAssessmentRuns.append(filtered_item)

        logger.debug("Modified output: {}\n".format(recentAssessmentRuns))

        return recentAssessmentRuns
    
    except Exception as e:
        logger.error("fetch_recent_assessment_runs error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_assessment_runs(id: str, page: int=1, pageSize: int=0) -> list | str:
    """
        Get all assessment run for given assessment id
        Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize, default page is 1
        If the request times out retry with pagination, increasing pageSize from 5 to 10.
        use this tool when expected run is got in fetch recent assessment runs tool
        
        Args:
        id: assessment id
    """
    try:
        output=await utils.make_GET_API_call_to_CCow(f"/v1/plan-instances?fields=basic&page={page}&page_size={pageSize}&plan_id={id}")
        logger.debug("output: {}\n".format(output))

        if page==0 and pageSize==0:
            return "use pagination"
        elif page==0 and pageSize>0:
            page=1
        elif page>0  and pageSize==0:
            pageSize=10
        elif pageSize>10:
            return "max page size is 10"

        if isinstance(output, str):
            return output
        
        assessmentRuns = []

        for item in output["items"]:
            if "planId" in item and "id" in item:
                filtered_item = {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "assessmentId": item.get("planId"),
                    "applicationType": item.get("applicationType"),
                    "configId": item.get("configId"),
                    "fromDate": item.get("fromDate"),
                    "toDate": item.get("toDate"),
                    "started": item.get("started"),
                    "ended": item.get("ended"),
                    "status": item.get("status"),
                    "computedScore": item.get("computedScore"),
                    "computedWeight": item.get("computedWeight"),
                    "complianceStatus": item.get("complianceStatus"),
                    "createdAt": item.get("createdAt"),
                }
                assessmentRuns.append(filtered_item)

        logger.debug("Modified output: {}\n".format(assessmentRuns))

        return assessmentRuns
    
    except Exception as e:
        logger.error("fetch_recent_assessment_runs error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_assessment_run_details(id: str) -> list:
    """
        Get assessment run details for given assessment run id. This api will return many contorls, use page to get details pagewise.
        If output is large store it in a file.

        Args:
        id: assessment run id
    """

    try:
        output=await utils.make_GET_API_call_to_CCow("/v1/plan-instance-controls?fields=basic&is_leaf_control=true&plan_instance_id="+id)
        logger.debug("output: {}\n".format(json.dumps(output)))

        controls=output["items"]
        # controls=[]
        # try:
        #     for item in output["items"]:
        #         if re.search('Prerequisite', item["name"], re.IGNORECASE):
        #             continue
        #         control={"name": item["name"],"number":item["displayable"]}
        #         if "tags" in item:
        #             control["tags"]=item["tags"]
        #         controls.append(control)
        # except Exception as e: 
        #     logger.debug("get_assessment_run_details err: {}\n".format(e))

        return controls
    except Exception as e:
        logger.error("fetch_assessment_run_details error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_assessment_run_leaf_controls(id: str) -> list | str:
    """
        Get leaf controls for given assessment run id.
        If output is large store it in a file.

        Args:
        id: assessment run id
    """
    try:
        output=await utils.make_GET_API_call_to_CCow("/v1/plan-instance-controls?fields=basic&is_leaf_control=true&plan_instance_id="+id)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str):
            return output
        
        leftControls = []

        for item in output["items"]:
            if "id" in item and "name" in item:
                filtered_item = {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "controlNumber": item.get("displayable"),
                    "alias": item.get("alias"),
                    "priority": item.get("priority"),
                    "status": item.get("status"),
                    "dueDate": item.get("dueDate"),
                    "complianceStatus": item.get("complianceStatus")
                }
                leftControls.append(filtered_item)

        logger.debug("Modified output: {}\n".format(json.dumps(leftControls)))
        return leftControls 

    except Exception as e:
        logger.error("fetch_assessment_run_leaf_controls error: {}\n".format(e))
        return "Facing internal error"
    
@mcp.tool()
async def fetch_assessment_run_leaf_control_evidence(id: str) -> list | str:
    """
        Get leaf control evidence for given assessment run control id.

        Args:
        id: assessment run control id
    """
    try:
        output=await utils.make_GET_API_call_to_CCow("/v1/plan-instance-evidences?plan_instance_control_id="+id)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str):
            return output
        
        controlEvidences = []

        for item in output["items"]:
            if "id" in item and "name" in item:
                filtered_item = {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "fileName": item.get("fileName")
                }
                controlEvidences.append(filtered_item)
        return controlEvidences
    
    except Exception as e:
        logger.error("fetch_assessment_run_leaf_control_evidence error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_evidence_records(id: str) -> list | str:
    """
        Get evidence record for given evidence id.

        Args:
        id: evidence id
    """
    try:
        output=await utils.make_API_call_to_CCow({
            "evidenceID": id,
            "templateType": "evidence",
            "status": [
                "active"
            ],
            "returnFormat": "json",
            "isSrcFetchCall": True,
            "isUserPriority": True,
            "considerFileSizeRestriction": True,
            "viewEvidenceFlow": True
        },"/v1/datahandler/fetch-data")
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str):
            return output
        
        decoded_bytes = base64.b64decode(output["fileBytes"])
        decoded_string = decoded_bytes.decode('utf-8')
        obj_list = json.loads(decoded_string)

        evidenceRecords = []

        for item in obj_list:
            if "id" in item:
                filtered_item = {
                    "id": item.get("id"),
                    "ResourceID": item.get("ResourceID"),
                    "ResourceName": item.get("ResourceName"),
                    "ResourceType": item.get("ResourceType"),
                    "ComplianceStatus": item.get("ComplianceStatus")
                }
                evidenceRecords.append(filtered_item)

        logger.debug("Modified output: {}\n".format(json.dumps(evidenceRecords)))
        return evidenceRecords        
    
    except Exception as e:
        logger.error("fetch_evidence_records error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_available_actions(assessmentName: str, controlNumber: str = "", controlAlias: str = "", evidenceName: str = "") -> list | str:
    """
        Use this tool when the user asks about actions such as create, update or other action-related queries.
        Based on the input, the tool will determine whether to fetch actions at the assessment level, control level, or evidence level.
        Get actions available at assessment, control, or evidence level based on provided parameters.
        Once fetched, ask user to confirm to execute the action, then use 'execute_action' tool with appropriate parameters to execute the action.
        
        Usage patterns:
        - Assessment level: provide only assessment_name
        - Control level: provide assessment_name, control_number, and control_alias
        - Evidence level: provide all parameters
        
        Args:
        assessmentName: assessment name (required)
        controlNumber: control number (optional, required for control/evidence level)
        controlAlias: control alias (optional, required for control/evidence level)  
        evidenceName: evidence name (optional, required for evidence level only)
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
        },"/v1/actions/fetch-available-actions")
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str):
            return output
        
        actions = output["items"]

        for item in actions:
            if "rules" in item:
                del item["rules"] 
        
        logger.debug("output: {}\n".format(json.dumps(actions)))
        return actions
    except Exception as e:
        logger.error("fetch_available_actions error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def execute_action(assessmentId: str, assessmentRunId: str, actionBindingId: str , assessmentRunControlId: str="", assessmentRunControlEvidenceId: str="", evidenceRecordIds: List[str]=[] ) -> dict | str:
    """
        use this to trigger action for assessment level or control level or evidence level.
        Execute or trigger a specific action on an assessment run. use assessment id, assessment run id and action binding id.
        Execute or trigger a specific action on an control run. use assessment id, assessment run id, action binding id and assessment run control id .
        Execute or trigger a specific action on an evidence level. use assessment id, assessment run id, action binding id, assessment run control evidence id and evidence record ids.
        use fetch assessment available actions to get action binding id.
        Only once action can be triggered at a time, assessment level or control level or evidence level based on user preference.

        Args:
        assessmentId 
        assessmentRunId
        actionBindingId
        assessmentRunControlId - needed for control level action
        assessmentRunControlEvidenceId - needed for evidence level action
        evidenceRecordIds - needed for evidence level action
    """
    try:
        output=await utils.make_API_call_to_CCow({
            "actionBindingID": actionBindingId,
            "planInstanceID":assessmentRunId,
            "planID": assessmentId,
            "planInstanceControlID": assessmentRunControlId,
            "planInstanceControlEvidenceID": assessmentRunControlEvidenceId,
            "recordIDs": evidenceRecordIds,
            "rules":[]
        },"/v1/actions/executions")
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str):
            return output

        return output
    except Exception as e:
        logger.error("execute_action error: {}\n".format(e))
        return "Facing internal error"
