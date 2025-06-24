import json
import traceback
import base64
from typing import List
from typing import Tuple

from utils import utils
from utils.debug import logger
from mcpconfig.config import mcp
from constants import constants
from tools.graphdb import graphdb
from mcptypes import assessment_run_tool_types as vo


@mcp.tool()
async def fetch_recent_assessment_runs(id: str) -> vo.AssessmentRunListVO:
    """
        Get recent assessment run for given assessment id

        Args:
            - id (str): assessment id
        
        Returns:
            - assessmentRuns (List[AssessmentRuns]): A list of assessment runs.
                - id (str):  Assessement run id.
                - name (str): Name of the assessement run.
                - description (str):  Description of the assessment run.
                - assessmentId (str): Assessement id.
                - applicationType (str): Application type.
                - configId (str): Configuration id.
                - fromDate (str): From date of the assessement run.
                - toDate (str): To date of the assessment run.
                - status (str): Status of the assessment run.
                - computedScore (str): Computed score.
                - computedWeight (str): Computed weight.
                - complianceStatus (str): Compliance status.
                - createdAt (str): Time and date when the assessement run was created. 
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        output=await utils.make_GET_API_call_to_CCow(constants. URL_PLAN_INSTANCES + "?fields=basic&page=1&page_size=10&plan_id="+id)
        logger.debug("output: {}\n".format(output))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_recent_assessment_runs error: {}\n".format(output))
            return vo.AssessmentRunListVO(error="Facing internal error")
        
        recentAssessmentRuns: List[vo.AssessmentRunVO]= []

        for item in output["items"]:
            if "planId" in item and "id" in item:
                filtered_item = vo.AssessmentRunVO(
                    id = item.get("id"),
                    name = item.get("name"),
                    description = item.get("description"),
                    assessmentId = item.get("planId"),
                    applicationType = item.get("applicationType"),
                    configId = item.get("configId"),
                    fromDate =  item.get("fromDate"),
                    toDate =  item.get("toDate"),
                    # started =  item.get("started"),
                    # ended = item.get("ended"),
                    status = item.get("status"),
                    computedScore =  item.get("computedScore"),
                    computedWeight = item.get("computedWeight"),
                    complianceStatus = item.get("complianceStatus"),
                    createdAt = item.get("createdAt"),
                )
                recentAssessmentRuns.append(filtered_item)

        logger.debug("Modified output: {}\n".format(recentAssessmentRuns))

        return vo.AssessmentRunListVO(assessmentRuns=recentAssessmentRuns)
    
    except Exception as e:
        logger.error("fetch_recent_assessment_runs error: {}\n".format(e))
        return vo.AssessmentRunListVO(error="Facing internal error")

@mcp.tool()
async def fetch_assessment_runs(id: str, page: int=1, pageSize: int=0) -> vo.AssessmentRunListVO:
    """
        Get all assessment run for given assessment id
        Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize, default page is 1
        If the request times out retry with pagination, increasing pageSize from 5 to 10.
        use this tool when expected run is got in fetch recent assessment runs tool
        
        Args:
            - id (str): Assessment id
        
        Returns:
            - assessmentRuns (List[AssessmentRuns]): A list of assessment runs.
                - id (str):  Assessement run id.
                - name (str): Name of the assessement run.
                - description (str):  Description of the assessment run.
                - assessmentId (str): Assessement id.
                - applicationType (str): Application type.
                - configId (str): Configuration id.
                - fromDate (str): From date of the assessement run.
                - toDate (str): To date of the assessment run.
                - status (str): Status of the assessment run.
                - computedScore (str): Computed score.
                - computedWeight (str): Computed weight.
                - complianceStatus (str): Compliance status.
                - createdAt (str): Time and date when the assessement run was created. 
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        output=await utils.make_GET_API_call_to_CCow(f"{constants.URL_PLAN_INSTANCES}?fields=basic&page={page}&page_size={pageSize}&plan_id={id}")
        logger.debug("output: {}\n".format(output))

        if page==0 and pageSize==0:
            return "use pagination"
        elif page==0 and pageSize>0:
            page=1
        elif page>0  and pageSize==0:
            pageSize=10
        elif pageSize>10:
            return "max page size is 10"

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_assessment_runs error: {}\n".format(output))
            return vo.AssessmentRunListVO(error="Facing internal error")

        # if isinstance(output, str):
        #     return output
        
        assessmentRuns: List[vo.AssessmentRunVO] = []

        for item in output["items"]:
            if "planId" in item and "id" in item:
                filtered_item = vo.AssessmentRunVO(
                    id = item.get("id"),
                    name = item.get("name"),
                    description = item.get("description"),
                    assessmentId = item.get("planId"),
                    applicationType = item.get("applicationType"),
                    configId = item.get("configId"),
                    fromDate =  item.get("fromDate"),
                    toDate =  item.get("toDate"),
                    # started =  item.get("started"),
                    # ended = item.get("ended"),
                    status = item.get("status"),
                    computedScore =  item.get("computedScore"),
                    computedWeight = item.get("computedWeight"),
                    complianceStatus = item.get("complianceStatus"),
                    createdAt = item.get("createdAt"),
                )
                assessmentRuns.append(filtered_item)

        logger.debug("Modified output: {}\n".format(assessmentRuns))

        return vo.AssessmentRunListVO(assessmentRuns=assessmentRuns)
    
    except Exception as e:
        logger.error("fetch_assessment_runs error: {}\n".format(e))
        return vo.AssessmentRunListVO(error="Facing internal error")

@mcp.tool()
async def fetch_assessment_run_details(id: str) -> vo.ControlListVO:
    """
        Get assessment run details for given assessment run id. This api will return many contorls, use page to get details pagewise.
        If output is large store it in a file.

        Args:
            - id (str): Assessment run id
        
        Returns:
            - controls (List[Control]): A list of controls.
                - id (str):  Control run id.
                - name (str): Control name.
                - controlNumber (str): Control number.
                - alias (str):  Control alias.
                - priority (str): Priority.
                - stage (str): Control stage.
                - status (str): Control status.
                - type (str): Control type.
                - executionStatus (str): Rule execution status.
                - dueDate (str): Due date.
                - assignedTo (List[str]): Assigned user ids
                - assignedBy (str): Assigner's user id.
                - assignedDate (str): Assigned date.
                - checkedOut (bool): Control checked-out status.
                - compliancePCT__ (str): Compliance percentage.
                - complianceWeight__ (str): Compliance weight.
                - complianceStatus (str): Compliance status.
                - createdAt (str): Time and date when the control run was created. 
                - updatedAt (str): Time and date when the control run was updated. 
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """

    try:
        output=await utils.make_GET_API_call_to_CCow(constants.URL_PLAN_INSTANCE_CONTROLS + "?fields=basic&is_leaf_control=true&plan_instance_id="+id)
        logger.debug("output: {}\n".format(json.dumps(output)))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_assessment_run_details error: {}\n".format(output))
            return vo.ControlListVO(error="Facing internal error")

        controls: List[vo.ControlVO] = []        
        for control in output["items"]:
            if "id" in control and "name" in control:
                controls.append(vo.ControlVO.model_validate(control))
                
        return vo.ControlListVO(controls=controls).model_dump()
    except Exception as e:
        logger.error("fetch_assessment_run_details error: {}\n".format(e))
        return vo.ControlVO(error="Facing internal error")

@mcp.tool()
async def fetch_assessment_run_leaf_controls(id: str) ->  vo.ControlListVO:
    """
        Get leaf controls for given assessment run id.
        If output is large store it in a file.

        Args:
            - id (str): Assessment run id
        
        Returns:
            - controls (List[Control]): A list of controls.
                - id (str):  Control run id.
                - name (str): Control name.
                - controlNumber (str): Control number.
                - alias (str):  Control alias.
                - priority (str): Priority.
                - stage (str): Control stage.
                - status (str): Control status.
                - type (str): Control type.
                - executionStatus (str): Rule execution status.
                - dueDate (str): Due date.
                - assignedTo (List[str]): Assigned user ids
                - assignedBy (str): Assigner's user id.
                - assignedDate (str): Assigned date.
                - checkedOut (bool): Control checked-out status.
                - compliancePCT__ (str): Compliance percentage.
                - complianceWeight__ (str): Compliance weight.
                - complianceStatus (str): Compliance status.
                - createdAt (str): Time and date when the control run was created. 
                - updatedAt (str): Time and date when the control run was updated. 
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        output=await utils.make_GET_API_call_to_CCow(constants.URL_PLAN_INSTANCE_CONTROLS +"?fields=basic&is_leaf_control=true&plan_instance_id="+id)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_assessment_run_details error: {}\n".format(output))
            return vo.ControlListVO(error="Facing internal error")
        
        leaf_controls: List[vo.ControlVO] = []        
        for control in output["items"]:
            if "id" in control and "name" in control:
                leaf_controls.append(vo.ControlVO.model_validate(control))

        ControlListVO = vo.ControlListVO(controls=leaf_controls) 
        logger.debug("Modified output: {}\n".format(ControlListVO.model_dump()))
        return ControlListVO.model_dump()
    except Exception as e:
        logger.error("fetch_assessment_run_leaf_controls error: {}\n".format(e))
        return vo.ControlListVO(error="Facing internal error")

@mcp.tool()
async def fetch_run_controls(name: str) -> vo.ControlListVO:
    """
        use this tool when you there is no result from the tool "execute_cypher_query".
        use this tool to get all controls that matches the given name.
        Next use fetch control meta data tool if need assessment name, assessment Id, assessment run name, assessment run Id 
        
        Args:
            - name (str): Control name
        
        Returns:
            - controls (List[Control]): A list of controls.
                - id (str):  Control run id.
                - name (str): Control name.
                - controlNumber (str): Control number.
                - alias (str):  Control alias.
                - priority (str): Priority.
                - stage (str): Control stage.
                - status (str): Control status.
                - type (str): Control type.
                - executionStatus (str): Rule execution status.
                - dueDate (str): Due date.
                - assignedTo (List[str]): Assigned user ids
                - assignedBy (str): Assigner's user id.
                - assignedDate (str): Assigned date.
                - checkedOut (bool): Control checked-out status.
                - compliancePCT__ (str): Compliance percentage.
                - complianceWeight__ (str): Compliance weight.
                - complianceStatus (str): Compliance status.
                - createdAt (str): Time and date when the control run was created. 
                - updatedAt (str): Time and date when the control run was updated. 
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        output=await utils.make_GET_API_call_to_CCow(f"{constants.URL_PLAN_INSTANCE_CONTROLS}?fields=basic&control_name_contains={name}&page=1&page_size=50")
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_run_controls error: {}\n".format(output))
            return vo.ControlListVO(error="Facing internal error")
        
        controls: List[vo.ControlVO] = []        
        for control in output["items"]:
            if "id" in control and "name" in control:
                controls.append(vo.ControlVO.model_validate(control))
        ControlListVO = vo.ControlListVO(controls=controls) 
        logger.debug("Modified output: {}\n".format(ControlListVO.model_dump()))
        return ControlListVO.model_dump()
    except Exception as e:
        logger.error("fetch_run_controls error: {}\n".format(e))
        return vo.ControlListVO(error="Facing internal error")

@mcp.tool()
async def fetch_run_control_meta_data(id: str) -> vo.ControlMetadataVO:
    """
    Use this tool to retrieve control metadata for a given `control_id`, including:

    - **Control details**: control name  
    - **Assessment details**: assessment name and ID  
    - **Assessment run details**: assessment run name and ID

    Args:
        - id (str): Control id
        
    Returns:
        - assessmentId (str):  Assessment id.
        - assessmentName (str): Assessment name.
        - assessmentRunId (str): Assessment run id.
        - assessmentRunName (str):  Assessment run name.
        - controlId (str): Control id.
        - controlName (str): Control name.
        - controlNumber (str): Control number.
        - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        output = await utils.make_GET_API_call_to_CCow(f"{constants.URL_PLAN_INSTANCE_CONTROLS}/{id}/plan-data")
        logger.debug("output: {}\n".format(json.dumps(output)))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_run_control_meta_data error: {}\n".format(output))
            return vo.ControlMetadataVO(error="Facing internal error")

        controlMetaData = vo.ControlMetadataVO.model_validate(output)
        return controlMetaData.model_dump()
    except Exception as e:
        logger.error("fetch_control_meta_data error: {}\n".format(e))
        return vo.ControlMetadataVO(error="Facing internal error")



# had to check whether this leaf control is required or not
@mcp.tool()
async def fetch_assessment_run_leaf_control_evidence(id: str) -> vo.ControlEvidenceListVO:
    """
        Get leaf control evidence for given assessment run control id.

        Args:
        - id (str): Assessment run control id
        
        Returns:
            - evidences (List[ControlEvidenceVO]): List of control evidences
                - id (str):  Evidence id.
                - name (str): Evidence name.
                - description (str): Evidence description.
                - fileName (str):  File name.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        output=await utils.make_GET_API_call_to_CCow(constants.URL_PLAN_INSTANCE_EVIDENCES + "?plan_instance_control_id="+id)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_run_control_meta_data error: {}\n".format(output))
            return vo.ControlEvidenceListVO(error="Facing internal error")
        
        controlEvidences: List[vo.ControlEvidenceVO] = []
        for item in output["items"]:
            if "id" in item and "name" in item and "status" in item and item.get("status") == "Completed" and item.get("evidenceFileInfos"):
                controlEvidences.append(vo.ControlEvidenceVO.model_validate(item))
                
        return vo.ControlEvidenceListVO(evidences=controlEvidences)
    except Exception as e:
        logger.error("fetch_assessment_run_leaf_control_evidence error: {}\n".format(e))
        return vo.ControlEvidenceListVO(error="Facing internal error")


@mcp.tool()
async def fetch_controls(control_name:str = "") -> vo.ControlPromptVO:
    """
    To fetch controls.
    Args:
        control_name (str): name of the control.
    
    Returns:
        - prompt (str): The input prompt used to generate the Cypher query for fetching the control.
    """
    try:
    
        uniqueNodeSchemaVO = await graphdb.fetch_unique_node_data_and_schema(control_name)
        return generate_cypher_query_for_control(control_name,uniqueNodeSchemaVO.unique_property_values, uniqueNodeSchemaVO.neo4j_schema)
    except Exception as e:
        logger.error("fetch_controls error: {}\n".format(e))
        return vo.ControlPromptVO(error="Facing internal error")

@mcp.prompt()
def generate_cypher_query_for_control(control_name: str =  "", unique_nodes: str = "", schema = "") -> vo.ControlPromptVO:
    return vo.ControlPromptVO(prompt=f"""
        Using the information below — `control_name`, `unique_nodes`, and `schema` — generate a Cypher query.
        The query should search both the specified control and its child controls(HAS_CHILD - relationship), and be flexible enough to return results from either, depending on where the match is found.
        Use contains for the node property filters.
        If the query returns no results when executed using the "execute_cypher_query" tool, attempt to regenerate the query specifically targeting child controls.

        Inputs:
        - control_name: {control_name}
        - unique_nodes: {unique_nodes}
        - schema: {schema}

        The Cypher query should return:
        - control_name
        - displayable_alias
        - assessment_name (if available)
        """)


@mcp.tool()
async def fetch_evidence_records(id: str, compliantStatus: str = "") -> vo.RecordListVO:
    """
    Get evidence records for a given evidence ID with optional compliance status filtering.
    Returns max 50 records but counts all records for the summary.

    Args:
        - id (str): Evidence ID
        - compliantStatus Optional[(str)]: Compliance status to filter "COMPLIANT", "NON_COMPLIANT", "NOT_DETERMINED" (optional).
    
    Returns:
        - totalRecords (int):  Total records.
        - compliantRecords (int):  Number of complian records.
        - nonCompliantRecords (int):  Number of non compliant records.
        - notDeterminedRecords (int):  Number of not determined records.
        - records (List[RecordListVO]): List of evidence records.
            - id (str):  Record id.
            - name (str): System name.
            - source (str): Record source.
            - resourceId (str):  Resource id.
            - resourceName (str):  Resource name.
            - resourceType (str):  Resource type.
            - complianceStatus (str):  Compliance status.
            - complianceReason (str):  Compliance reason.
            - createdAt (str): The date and time the record was initially created.         
            - otherInfo (Any): Additional information.    
        - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        output=await utils.make_API_call_to_CCow({
            "evidenceID": id,
            "templateType": "evidence",
            "status": ["active"],
            "returnFormat": "json",
            "isSrcFetchCall": True,
            "isUserPriority": True,
            "considerFileSizeRestriction": True,
            "viewEvidenceFlow": True
        },constants.URL_DATAHANDLER_FETCH_DATA)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_evidence_records error: {}\n".format(output))
            return vo.RecordListVO(error="Facing internal error")
        
        if(output.get("Message") == "CANNOT_FIND_THE_FILE"):
            return vo.RecordListVO(error="No data available to display")
         
        decoded_bytes = base64.b64decode(output["fileBytes"])
        decoded_string = decoded_bytes.decode('utf-8')
        obj_list = json.loads(decoded_string)

        evidenceRecords: List[vo.RecordsVO]= []
        compliantCount = nonCompliantCount = notDeterminedCount = 0


        for item in obj_list:
            if "id" not in item:
                continue

            status = item.get("ComplianceStatus", "NOT_DETERMINED")
            if status not in ["COMPLIANT", "NON_COMPLIANT", "NOT_DETERMINED"]:
                status = "NOT_DETERMINED"

            if status == "COMPLIANT":
                compliantCount += 1
            elif status == "NON_COMPLIANT":
                nonCompliantCount += 1
            else:
                notDeterminedCount += 1
        for item in obj_list:
            if "id" not in item:
                continue

            status = item.get("ComplianceStatus", "NOT_DETERMINED")
            if status not in ["COMPLIANT", "NON_COMPLIANT", "NOT_DETERMINED"]:
                status = "NOT_DETERMINED"

            if compliantStatus and status != compliantStatus:
                continue

            new_item = {k: v for k, v in item.items() if not k.endswith("__")}
            
            evidenceRecord =  vo.RecordsVO.model_validate(new_item)
            keys_to_remove = [
                "System", "Source", "ResourceID", "ResourceName",
                "ResourceType", "ComplianceStatus", "ComplianceReason", "CreatedAt"
            ]
            for key in keys_to_remove:
                item.pop(key, None) 
            
            evidenceRecord.otherInfo = item
            evidenceRecords.append(evidenceRecord)

            if len(evidenceRecords) >= 50:
                break
        result = vo.RecordListVO(
            totalRecords= len(obj_list),
            compliantRecords =  compliantCount,
            nonCompliantRecords =  nonCompliantCount,
            notDeterminedRecords = notDeterminedCount,
            records = evidenceRecords
        )

        logger.debug("Modified output: {}\n".format(result.model_dump()))
        return result.model_dump()
    except Exception as e:
        logger.error("fetch_evidence_records error: {}\n".format(e))
        return vo.RecordListVO(error="Facing internal error")
    
    
@mcp.tool()
async def fetch_available_control_actions(assessmentName: str, controlNumber: str = "", controlAlias: str = "", evidenceName: str = "") -> vo.RecordListVO:
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
            - actions (List[ActionsVO]): List of actions
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
        },constants.URL_FETCH_AVAILABLE_ACTIONS)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_available_control_actions error: {}\n".format(output))
            return vo.ActionsListVO(error="Facing internal error")
        
        actions: List[vo.ActionsVO] = []
        for item in output.get("items", []):
            if not item.get("actionBindingID"):
                continue
            item.pop("rules", None)
            actions.append(vo.ActionsVO.model_validate(item))
        
        logger.debug("output: {}\n".format(vo.ActionsListVO(actions=actions).model_dump()))
        return vo.ActionsListVO(actions=actions)
    except Exception as e:
        logger.error("fetch_available_control_actions error: {}\n".format(e))
        return vo.ActionsListVO(error="Facing internal error")
    
@mcp.tool()
async def fetch_assessment_available_actions(name: str = "") -> vo.RecordListVO:
    """
        Get **actions available on assessment** for given assessment name. 
        Once fetched, ask user to confirm to execute the action, then use 'execute_action' tool with appropriate parameters to execute the action.
        Args: 
         - name (str): Assessment name
         
        Returns:
            - actions (List[ActionsVO]): List of actions
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
        },constants.URL_FETCH_AVAILABLE_ACTIONS)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_available_control_actions error: {}\n".format(output))
            return vo.ActionsListVO(error="Facing internal error")
        
        actions: List[vo.ActionsVO] = []
        for item in output.get("items", []):
            if not item.get("actionBindingID"):
                continue
            item.pop("rules", None)
            actions.append(vo.ActionsVO.model_validate(item))
        
        logger.debug("output: {}\n".format(vo.ActionsListVO(actions=actions).model_dump()))
        return vo.ActionsListVO(actions=actions)
    except Exception as e:
        logger.error("fetch_assessment_available_actions error: {}\n".format(e))
        return vo.ActionsListVO(error="Facing internal error")
    
@mcp.tool()
async def fetch_evidence_available_actions(assessment_name: str = "", control_number: str="", control_alias: str ="", evidence_name: str ="") -> list | str:
    """
        Get actions available on evidence for given evidence name. 
        If the required parameters are not provided, use the existing tools to retrieve them.
        Once fetched, ask user to confirm to execute the action, then use 'execute_action' tool with appropriate parameters to execute the action.
        Args: 
        assessment_name: assessment name (required)
        control_number: control number (required)
        control_alias: control alias (required)  
        evidence_name: evidence name (required)
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
        },constants.URL_FETCH_AVAILABLE_ACTIONS)
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
        logger.error("fetch_evidence_available_actions error: {}\n".format(e))
        return "Facing internal error"
    
@mcp.tool()
async def fetch_evidence_available_actions(assessment_name: str = "", control_number: str="", control_alias: str ="", evidence_name: str ="") -> vo.ActionsListVO:
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
            - actions (List[ActionsVO]): List of actions
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
        },constants.URL_FETCH_AVAILABLE_ACTIONS)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_evidence_available_actions error: {}\n".format(output))
            return vo.ActionsListVO(error="Facing internal error")
                
        actions: List[vo.ActionsVO] = []
        for item in output.get("items", []):
            if not item.get("actionBindingID"):
                continue
            item.pop("rules", None)
            actions.append(vo.ActionsVO.model_validate(item))
        
        logger.debug("output: {}\n".format(vo.ActionsListVO(actions=actions).model_dump()))
        return vo.ActionsListVO(actions=actions)
    except Exception as e:
        logger.error("fetch_evidence_available_actions error: {}\n".format(e))
        return vo.ActionsListVO(error="Facing internal error")
    
@mcp.tool()
async def fetch_automated_controls_of_an_assessment(assessment_id: str = "") -> vo.AutomatedControlListVO:
    
    """
    To fetch the only the **automated controls** for a given assessment.
    If assessment_id is not provided use other tools to get the assessment and its id.
    
    Args:
        - assessment_id (str, required): Assessment id or plan id.

    Returns:
        - controls (List[AutomatedControlVO]): List of controls
            - id (str): Control ID.
            - displayable (str): Displayable name or label.
            - alias (str): Alias of the control.
            - activationStatus (str): Activation status.
            - ruleName (str): Associated rule name.
            - assessmentId (str): Assessment identifier.
        - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    
    try:
        logger.info("fetch_automated_controls: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_PLAN_CONTROLS + 
         "?is_automated=true&fields=basic&skip_prereq_ctrl_priv_check=false&page=1&page_size=100&plan_id=" + assessment_id)
        logger.debug("output: {}\n".format(output))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_automated_controls_of_an_assessment error: {}\n".format(output))
            return vo.AutomatedControlListVO(error="Facing internal error")
        
        automated_controls: List[vo.AutomatedControlVO] = []
        for item in output["items"]:
            if "id" in item and "displayable" in item and "alias" in item:
                automated_control = vo.AutomatedControlVO(
                    id=item["id"],
                    displayable=item["displayable"],
                    alias=item["alias"],
                    activationStatus=item["activationStatus"],
                    assessmentId=item["planId"]
                )
                if "rule" in item and "name" in item["rule"]:
                    automated_control.ruleName = item["rule"]["name"]
                automated_controls.append(automated_control)
        
        logger.debug("automated control list: {}\n",vo.AutomatedControlListVO(controls=automated_controls).model_dump())

        return vo.AutomatedControlListVO(controls=automated_controls)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_automated_controls error: {}\n".format(e))
        return vo.AutomatedControlListVO(error="Facing internal error")


@mcp.tool()
async def execute_action(assessmentId: str, assessmentRunId: str, actionBindingId: str , assessmentRunControlId: str="", assessmentRunControlEvidenceId: str="", evidenceRecordIds: List[str]=[] ) -> vo.TriggerActionVO:
    """
        Use this tool when the user asks about actions such as create, update or other action-related queries.

        IMPORTANT: This tool MUST ONLY be executed after explicit user confirmation. 
        Always describe the intended action and its effects to the user, then wait for their explicit approval before proceeding.
        Do not execute this tool without clear user consent, as it performs actual operations that modify system state.

        Execute or trigger a specific action on an assessment run. use assessment id, assessment run id and action binding id.
        Execute or trigger a specific action on an control run. use assessment id, assessment run id, action binding id and assessment run control id .
        Execute or trigger a specific action on an evidence level. use assessment id, assessment run id, action binding id, assessment run control evidence id and evidence record ids.
        Use fetch assessment available actions to get action binding id.
        Only once action can be triggered at a time, assessment level or control level or evidence level based on user preference.
        Use this to trigger action for assessment level or control level or evidence level.
        Please also provide the intended effect when executing actions.

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
        
        Returns:
            - id (str): id of triggered action.
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
        },constants.URL_ACTIONS_EXECUTIONS)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("execute_action error: {}\n".format(output))
            return vo.TriggerActionVO(error="Facing internal error")

        return vo.TriggerActionVO(id=output['id'])
    except Exception as e:
        logger.error("execute_action error: {}\n".format(e))
        return vo.TriggerActionVO(error="Facing internal error")