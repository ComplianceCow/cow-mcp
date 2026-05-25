from typing import List
from typing import Tuple

from utils import utils
from utils.debug import logger
from mcpconfig.config import mcp
from constants import constants
from mcptypes import assessment_config_tool_types as assessmentvo
from mcptypes import assessment_run_tool_types as assessmentrunvo
from mcptypes import audit_tool_types as auditvo
from fastmcp import Context
import os
import traceback
import json
import base64

@mcp.tool(annotations=utils.tool_annotations("List All Assessment Categories",read_only=True))
async def audit_list_all_assessment_categories(ctx: Context | None = None) -> assessmentvo.CategoryListV2VO:
    """
        Get all assessment categories
        
        Returns:
            - categories (list[Category]): A list of category objects, where each category includes:
                - id (str): Unique identifier of the assessment category.
                - name (str): Name of the category.
            - error : An error message if any issues occurred during retrieval.

    """
    try:
        logger.info("get_all_assessment_categories: \n")

        output=await utils.make_API_call_to_CCow_and_get_response(constants.URL_ASSESSMENT_CATEGORIES, "GET", ctx=ctx)
        
        error = utils.build_structured_error(output, "assessments:list_all_assessment_categories")
        if error:
            logger.error("list_all_assessment_categories error: {}\n".format(output))
            return assessmentvo.CategoryListV2VO(error=error)

        category_list: list[assessmentvo.CategoryVO] = []
        for item in output:
            if "id" in item and "name" in item:
                category_list.append(assessmentvo.CategoryVO(id=item["id"],name=item["name"]))
        
        logger.debug("categories: {}\n".format(category_list))
        return assessmentvo.CategoryListV2VO(categories=category_list)
    except Exception as e:
        logger.error("list_all_assessment_categories error: {}\n".format(e))
        return assessmentvo.CategoryListV2VO(error=utils.build_structured_error(f"Unexpected error: {e}", "assessments:list_all_assessment_categories"))

@mcp.tool(annotations=utils.tool_annotations("List Assessments",read_only=True))
async def audit_list_all_assessments(categoryId: str = "", categoryName: str = "", assessmentName: str = "", ctx: Context | None = None) -> assessmentvo.AssessmentListVO:
    """
        Get all assessments
        Args:
        categoryId: assessment category id (Optional)
        categoryName: assessment category name (Optional)
        assessmentName: assessment name (Optional)
        Returns:
            - assessments (list[Assessments]): A list of assessments objects, where each assessment includes:
                - id (str): Unique identifier of the assessment.
                - name (str): Name of the assessment.
                - categoryName (str): Name of the category.
            - error : An error message if any issues occurred during retrieval.
    """
    try:
        logger.info("get_all_assessments: \n")

        logger.debug("payload: {} {} {}\n".format(categoryId, categoryName, assessmentName))

        payload = {
            "fields": "basic"
        }

        if categoryId:
            payload["category_id"] = categoryId

        if categoryName:
            payload["category_name_contains"] = categoryName

        if assessmentName:
            payload["name_contains"] = assessmentName

        output=await utils.make_API_call_to_CCow_and_get_response(constants.URL_PLANS, "GET", {
            "fields": "basic",
            "category_id": categoryId,
            "category_name_contains": categoryName,
            "name_contains": assessmentName,
        }, ctx=ctx)

        error = utils.build_structured_error(output, "assessments:list_assessments")
        if error:
            logger.error("list_assessments error: {}\n".format(output))
            return assessmentvo.AssessmentListVO(error=error)
                    
        assessments: List[assessmentvo.AssessmentVO]=[]
        for item in output["items"]:
            if "id" in item and "name" in item and "categoryName" in item:
                assessments.append(assessmentvo.AssessmentVO(id=item["id"],name=item["name"],category_name=item["categoryName"]))
        
        logger.debug("assessments: {}\n".format(assessments))

        return assessmentvo.AssessmentListVO(assessments=assessments)
    except Exception as e:
        logger.error("list_assessments error: {}\n".format(e))
        return assessmentvo.AssessmentListVO(error=utils.build_structured_error(f"Unexpected error: {e}", "assessments:list_assessments"))

@mcp.tool(annotations=utils.tool_annotations("List Assessment Control Configs",read_only=True))
async def audit_list_assessment_control_configs( assessmentId: str, ctx: Context | None = None) -> assessmentvo.AssessmentControlConfigListResponseVO:
    """
    List all control configs for a given assessment id
    
    This function retrieves all control configs for an assessment
    
    Args:
        assessmentId (str): The assessment ID (plan ID) to list control configs for.
    
    Returns:
        Dict with success status and controls:
        - success (bool): Whether the request was successful
        - controls (List[dict]): List of control objects, each containing:
            - id (str): Control ID
            - name (str): Control name
            - alias (str): Control alias
            - controlNumber (str): Displayable control number
        - totalCount (int): Total number of controls found
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("list_assessment_control_configs: \n")
        
        if not assessmentId or not str(assessmentId).strip():
            logger.error("list_assessment_control_configs error: assessmentId is mandatory\n")
            return assessmentvo.AssessmentControlConfigListResponseVO(success=False, error=utils.build_structured_error("assessmentId is mandatory", "list_assessment_control_configs"))
        
        assessment_id = str(assessmentId).strip()
        page_size = 100
        cur_page = 1
        has_next = True
        all_controls = []
        max_pages = 10
        
        # Recursively fetch pages using TotalPage from response (max 10 pages)
        while has_next and cur_page <= max_pages:
            logger.debug(
                "list_assessment_control_configs fetching page %s with page_size=%s, plan_id=%s, fields=basic, is_leaf_control=true, include_additional_context=true\n",
                cur_page,
                page_size,
                assessment_id,
            )
            
            output = await utils.make_API_call_to_CCow_and_get_response(constants.URL_PLAN_CONTROLS, "GET", {
                "page": cur_page,
                "page_size": page_size,
                "plan_id": assessment_id,
                "fields": "basic",
                "is_leaf_control": "true",
                "include_additional_context": "true",
            }, ctx=ctx)
            
            logger.error("list_assessment_control_configs page: {}\noutput: {}\n".format(cur_page, output))


            # Handle error response
            output_error = utils.build_structured_error(output, "list_assessment_control_configs")
            if output_error:
                if cur_page == 1:
                    logger.error("list_assessment_control_configs error: {}\n".format(output))
                    return assessmentvo.AssessmentControlConfigListResponseVO(success=False, error=output_error)
                # If error on subsequent pages, break and return what we have
                has_next = False
                break
            
            # Check if response has valid items
            if isinstance(output, dict) and "items" in output and isinstance(output.get("items"), list):
                items = output.get("items", [])
                
                # If items is empty, return what we have
                if not items:
                    logger.info(f"list_assessment_control_configs: No more items found at page {cur_page}\n")
                    break
                
                # Abstract and add only necessary fields
                for item in items:
                    if isinstance(item, dict) and "id" in item and "name" in item:
                        abstracted_control = assessmentvo.AssessmentControlConfigVO.model_validate({
                            "id": item.get("id", ""),
                            "name": item.get("name", ""),
                            "description": item.get("description", ""),
                            "alias": item.get("alias", ""),
                            "controlNumber": item.get("displayable", ""),
                            "context": item.get("context", ""),
                            "additionalContext": item.get("additionalContext", "")
                        })
                        all_controls.append(abstracted_control)
                
                # Get total pages from response and determine if there are more pages
                total_pages = int(output.get("TotalPage", 0)) or 1
                cur_page += 1
                has_next = cur_page <= total_pages
                
                logger.debug(f"list_assessment_control_configs: Page {cur_page - 1}, TotalPages: {total_pages}, HasNext: {has_next}\n")
            else:
                # Invalid response structure, stop pagination
                has_next = False
        
        logger.info(f"list_assessment_control_configs: Found {len(all_controls)} control(s) across {cur_page - 1} page(s)\n")

        logger.info(f"list_assessment_control_configs: Final All control : \n {all_controls}")

        return assessmentvo.AssessmentControlConfigListResponseVO(success=True, controls=all_controls, totalCount=len(all_controls))
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_assessment_control_configs error: {}\n".format(e))
        return assessmentvo.AssessmentControlConfigListResponseVO(success=False, error=utils.build_structured_error(f"Unexpected error listing assessment controls: {e}", "list_assessment_control_configs"))


@mcp.tool(annotations=utils.tool_annotations("Fetch Assessment Runs",read_only=True))
async def audit_fetch_assessment_runs(id: str, page: int=1, pageSize: int=0, ctx: Context | None = None) -> assessmentrunvo.AssessmentRunListV2VO:
    """
        Get all assessment run for given assessment id
        Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize, default page is 1
        If the request times out retry with pagination, increasing pageSize from 5 to 10.
        use this tool when expected run is got in fetch recent assessment runs tool
        
        Args:
            - id (str): Assessment id
        
        Returns:
            - assessmentRuns (list[AssessmentRuns]): A list of assessment runs.
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
                - compliancePCT (str): Compliance percentage.
                - complianceWeight (str): Compliance weight.
                - createdAt (str): Time and date when the assessement run was created. 
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        if page==0 and pageSize==0:
            return assessmentrunvo.AssessmentRunListV2VO(error=utils.build_structured_error("use pagination", "assessments:fetch_assessment_runs"))
        elif page==0 and pageSize>0:
            page=1
        elif page>0  and pageSize==0:
            pageSize=10
        elif pageSize>10:
            return assessmentrunvo.AssessmentRunListV2VO(error=utils.build_structured_error("max page size is 10", "assessments:fetch_assessment_runs"))

        output=await utils.make_API_call_to_CCow_and_get_response(constants.URL_PLAN_INSTANCES, "GET", {
            "fields": "basic",
            "page": page,
            "page_size": pageSize,
            "plan_id": id,
        }, ctx=ctx)
        logger.debug("output: {}\n".format(output))

        error = utils.build_structured_error(output, "assessments:fetch_assessment_runs")
        if error:
            logger.error("fetch_assessment_runs error: {}\n".format(output))
            return assessmentrunvo.AssessmentRunListV2VO(error=error)

        assessmentRuns: list[assessmentrunvo.AssessmentRunVO] = []

        for item in output["items"]:
            if "planId" in item and "id" in item:
                filtered_item = assessmentrunvo.AssessmentRunVO(
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
                    compliancePCT = item.get("compliancePCT__"),
                    complianceWeight = item.get("complianceWeight__"),
                    createdAt = item.get("createdAt"),
                )
                assessmentRuns.append(filtered_item)

        logger.debug("Modified output: {}\n".format(assessmentRuns))

        return assessmentrunvo.AssessmentRunListV2VO(assessmentRuns=assessmentRuns)
    
    except Exception as e:
        logger.error("fetch_assessment_runs error: {}\n".format(e))
        return assessmentrunvo.AssessmentRunListV2VO(error=utils.build_structured_error(f"Unexpected error: {e}", "assessments:fetch_assessment_runs"))


@mcp.tool(annotations=utils.tool_annotations("Fetch Assessment Run Details",read_only=True))
async def audit_fetch_assessment_run_details(id: str, ctx: Context | None = None) -> assessmentrunvo.ControlListV2VO:
    """
        Get assessment run details for given assessment run id. This api will return many contorls, use page to get details pagewise.
        If output is large store it in a file.

        Args:
            - id (str): Assessment run id
        
        Returns:
            - controls (list[Control]): A list of controls.
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
                - assignedTo (list[str]): Assigned user ids
                - assignedBy (str): Assigner's user id.
                - assignedDate (str): Assigned date.
                - checkedOut (bool): Control checked-out status.
                - compliancePCT__ (str): Compliance percentage.
                - complianceWeight__ (str): Compliance weight.
                - complianceStatus (str): Compliance status.
                - createdAt (str): Time and date when the control run was created. 
                - updatedAt (str): Time and date when the control run was updated. 
            - error : An error message if any issues occurred during retrieval.
    """

    try:
        output=await utils.make_API_call_to_CCow_and_get_response(constants.URL_PLAN_INSTANCE_CONTROLS, "GET", {
            "fields": "basic",
            "is_leaf_control": "true",
            "plan_instance_id": id,
        }, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))
        
        error = utils.build_structured_error(output, "assessments:fetch_assessment_run_details")
        if error:
            logger.error("fetch_assessment_run_details error: {}\n".format(output))
            return assessmentrunvo.ControlListV2VO(error=error)

        controls: List[assessmentrunvo.ControlVO] = []        
        for control in output["items"]:
            if "id" in control and "name" in control:
                controls.append(assessmentrunvo.ControlVO.model_validate(control))
                
        return assessmentrunvo.ControlListV2VO(controls=controls)
    except Exception as e:
        logger.error("fetch_assessment_run_details error: {}\n".format(e))
        return assessmentrunvo.ControlListV2VO(error=utils.build_structured_error(f"Unexpected error: {e}", "assessments:fetch_assessment_run_details"))


@mcp.tool(annotations=utils.tool_annotations("Fetch Assessment Run Leaf Control Evidence",read_only=True))
async def audit_fetch_assessment_run_leaf_control_evidence(id: str, ctx: Context | None = None) -> assessmentrunvo.ControlEvidenceListV2VO:
    """
        Get leaf control evidence for given assessment run control id.

        Args:
        - id (str): Assessment run control id
        
        Returns:
            - evidences (list[ControlEvidenceVO]): List of control evidences
                - id (str):  Evidence id.
                - name (str): Evidence name.
                - description (str): Evidence description.
                - fileName (str):  File name.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        output = await utils.make_API_call_to_CCow_and_get_response(constants.URL_PLAN_INSTANCE_EVIDENCES, "GET", {
            "plan_instance_control_id": id,
        }, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))

        error = utils.build_structured_error(output, "assessments:fetch_assessment_run_leaf_control_evidence")
        if error:
            logger.error("fetch_run_control_meta_data error: {}\n".format(output))
            return assessmentrunvo.ControlEvidenceListV2VO(error=error)
        
        controlEvidences: List[assessmentrunvo.ControlEvidenceVO] = []
        for item in output["items"]:
            if "id" in item and "name" in item and "status" in item and item.get("status") == "Completed" and item.get("evidenceFileInfos"):
                controlEvidences.append(assessmentrunvo.ControlEvidenceVO.model_validate(item))
                
        return assessmentrunvo.ControlEvidenceListV2VO(evidences=controlEvidences)
    except Exception as e:
        logger.error("fetch_assessment_run_leaf_control_evidence error: {}\n".format(e))
        return assessmentrunvo.ControlEvidenceListV2VO(error=utils.build_structured_error(f"Unexpected error: {e}", "assessments:fetch_assessment_run_leaf_control_evidence"))


@mcp.tool(annotations=utils.tool_annotations("Fetch Evidence Records", read_only=True))
async def audit_fetch_evidence_records(
    id: str,
    resourceNames: list = [],
    page: int = 1,
    pageSize: int = 10,
    ctx: Context | None = None
) -> assessmentrunvo.RecordListV2VO:
    """
    Get evidence records for a given evidence ID with pagination.

    Args:
        - id (str): Evidence ID
        - resourceNames (list): List of resource names to filter
        - page (int): Page number (default: 1)
        - pageSize (int): Number of records per page (max: 10)

    Returns:
        - totalRecords (int)
        - compliantRecords (int)
        - nonCompliantRecords (int)
        - notDeterminedRecords (int)
        - currentPage (int)
        - pageSize (int)
        - totalPages (int)
        - records (list)
        - error (Optional[str])
    """

    try:
        # restrict max page size
        pageSize = min(max(pageSize, 1), 10)
        page = max(page, 1)

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_DATAHANDLER_FETCH_DATA,
            "POST",
            {
                "evidenceID": id,
                "templateType": "evidence",
                "status": ["active"],
                "returnFormat": "json",
                "isSrcFetchCall": True,
                "isUserPriority": True,
                "considerFileSizeRestriction": True,
                "viewEvidenceFlow": True
            },
            ctx=ctx
        )

        error = utils.build_structured_error(
            output,
            "assessments:fetch_evidence_records"
        )

        if error:
            logger.error(
                "fetch_evidence_records error: {}\n".format(output)
            )
            return assessmentrunvo.RecordListV2VO(error=error)

        decoded_bytes = base64.b64decode(output["fileBytes"])
        decoded_string = decoded_bytes.decode("utf-8")
        obj_list = json.loads(decoded_string)

        # Clean records
        cleaned_records = []

        for item in obj_list:
            if "id" not in item:
                continue

            new_item = {
                k: v
                for k, v in item.items()
                if not k.endswith("__")
            }

            cleaned_records.append(new_item)

        # Apply ResourceName filter
        if resourceNames:
            resource_names_set = {
                str(name).strip().lower()
                for name in resourceNames
                if name
            }

            cleaned_records = [
                record
                for record in cleaned_records
                if str(
                    record.get("ResourceName", "")
                ).strip().lower() in resource_names_set
            ]

        # Count statuses after filtering
        compliantCount = 0
        nonCompliantCount = 0
        notDeterminedCount = 0

        for item in cleaned_records:

            status = item.get(
                "ComplianceStatus",
                "NOT_DETERMINED"
            )

            if status not in [
                "COMPLIANT",
                "NON_COMPLIANT",
                "NOT_DETERMINED"
            ]:
                status = "NOT_DETERMINED"

            if status == "COMPLIANT":
                compliantCount += 1

            elif status == "NON_COMPLIANT":
                nonCompliantCount += 1

            else:
                notDeterminedCount += 1

        # Pagination
        totalRecords = len(cleaned_records)
        totalPages = (
            (totalRecords + pageSize - 1) // pageSize
            if totalRecords > 0
            else 0
        )

        start = (page - 1) * pageSize
        end = start + pageSize

        paginated_records = cleaned_records[start:end]

        result = {
            "totalRecords": totalRecords,
            "compliantRecords": compliantCount,
            "nonCompliantRecords": nonCompliantCount,
            "notDeterminedRecords": notDeterminedCount,
            "records": paginated_records,
            "currentPage": page,
            "pageSize": pageSize,
            "totalPages": totalPages,
        }

        recordList = assessmentrunvo.RecordListV2VO(**result)

        logger.debug(
            "Modified output: {}\n".format(result)
        )

        return recordList

    except Exception as e:
        logger.error(
            "fetch_evidence_records error: {}\n".format(e)
        )

        return assessmentrunvo.RecordListV2VO(
            error=utils.build_structured_error(
                f"Unexpected error: {e}",
                "assessments:fetch_evidence_records"
            )
        )


def _load_audit_events_from_file(filename: str) -> list[dict]:
    path = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Audit event file not found: {filename}")

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as ex:
        raise ValueError(f"Invalid JSON in {filename}: {ex}") from ex
    except OSError as ex:
        raise OSError(f"Unable to open audit event file {filename}: {ex}") from ex

    if not isinstance(data, list):
        raise ValueError(f"Audit event file {filename} must contain a JSON list of events.")

    return data

def _list_audit_events_from_file(filename: str) -> dict:
    try:

        events = _load_audit_events_from_file(filename)

        totalCount = len(events)
        return {
            "success": True,
            "totalCount": totalCount,
            "events": events,
        }
    except Exception as ex:
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(ex),
        }


@mcp.tool(annotations=utils.tool_annotations("List Control Config Audit Events", read_only=True))
async def audit_list_control_config_audit_events(
    id: str = "",
    ctx: Context | None = None,
) -> dict:
    """
    List control config audit events
    """
    try:
        output = _list_audit_events_from_file(
            "control_config_audit.json"
        )

        error = utils.build_structured_error(output, "audit:list_control_config_audit_events")
        if error:
            logger.error(f"audit_list_control_config_audit_events error: {output}\n")
            return {"success": False, "error": error}

        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": utils.build_structured_error(
                f"Unexpected error listing control config audit events: {e}",
                "audit:list_control_config_audit_events",
            ),
        }


@mcp.tool(annotations=utils.tool_annotations("List Control Run Audit Events", read_only=True))
async def audit_list_control_run_audit_events(
    id: str ,
    ctx: Context | None = None,
) -> dict:
    """
    List control run audit events 
    """
    try:

        output = _list_audit_events_from_file(
            "control_audit.json",
        )

        error = utils.build_structured_error(output, "audit:list_control_audit_events")
        if error:
            logger.error(f"audit_list_control_audit_events error: {output}\n")
            return {"success": False, "error": error}

        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": utils.build_structured_error(
                f"Unexpected error listing control audit events: {e}",
                "audit:list_control_audit_events",
            ),
        }


@mcp.tool(annotations=utils.tool_annotations("Create Control Run Note", read_only=False))
async def audit_create_control_run_note(
    controlRunId: str,
    assessmentRunId: str,
    notes: str,
    topic: str,
    confirm: bool = False,
    ctx: Context | None = None,
) -> dict:
    """
    Create a documentation note on a control run
    
    This tool creates a markdown documentation note that is attached to a control run.
    
    Get the topic from user

    ✅ CONFIRMATION-BASED SAFETY FLOW
    - When confirm=False:
        → The tool returns a PREVIEW of the generated markdown note.
        → The user may edit the note before confirming.
    - When confirm=True:
        → The note is permanently created and attached to the control run.
    
    Args:
        controlRunId (str): The control Run ID where the note will be attached (required).
        assessmentRunId (str): The assessment Run ID that contains the control run (required).
        notes (str): The documentation content in MARKDOWN format (required).
        topic (str, optional): Topic or subject of the note.
        confirm (bool, optional):  
            - False → Preview only (default, no persistence)
            - True  → Create and permanfently attach the note
    
    Returns:
        Dict with success status and note data:
        - success (bool): Whether the request was successful
        - note (dict, optional): Created note object containing:
            - id (str): Note ID
            - topic (str): Note topic
            - notes (str): Note content in markdown format
            - controlRunId (str): Control Run ID the note is attached to
        - error (str, optional): Error message if request failed
        - next_action (str, optional): Recommended next action
    """
    try:
        logger.info("audit_create_control_run_note: \n")
        
        if not controlRunId or not str(controlRunId).strip():
            logger.error("audit_create_control_run_note error: controlConfigId is mandatory\n")
            return {"success": False, "error": "controlRunId is mandatory"}
        
        if not assessmentRunId or not str(assessmentRunId).strip():
            logger.error("audit_create_control_run_note error: assessmentId is mandatory\n")
            return {"success": False, "error": "assessmentRunId is mandatory"}
        
        if not notes or not str(notes).strip():
            logger.error("audit_create_control_run_note error: notes content is mandatory\n")
            return {"success": False, "error": "notes content is mandatory"}
        
        # Build payload
        payload = {
            "topic": str(topic).strip(),
            "notes": str(notes).strip(),
            "planInstanceControlID": str(controlRunId).strip(),
        }

        if not confirm:
            logger.info("create_control_config_note: Returning confirmation preview\n")
            return {
                "success": True,
                "message": "Confirmation required before creating note",
                "controlRunId": payload["planInstanceControlID"],
                "topic": payload["topic"],
                "notes": payload["notes"],
                "next_step": "Review the Note above. If you need to modify it, provide the updated note parameter when calling with confirm=True. If correct, re-run with confirm=True to create note."
        }
        
        
        logger.debug("audit_create_control_run_note payload: {}\n".format(json.dumps(payload)))
        
        resp = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_INSTANCE_NOTES,
            "POST",
            payload,
            ctx=ctx
        )
        
        logger.info(f"audit_create_control_run_note: \n Response : {resp}\n")
        noteId = ""
        if isinstance(resp, dict):
            noteId = resp.get("id")
        
        if noteId: 
            return {
                "success": True,
                "noteId": noteId,
                "message": "Note created successfully",
            }
        
        return {
                "success": False,
                "error": resp,
            }

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("audit_create_control_run_note error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error creating control run note: {e}"}


@mcp.tool(annotations=utils.tool_annotations("Fetch Users By Ids", read_only=True))
async def audit_get_uses_by_ids(userIds:list, ctx: Context | None = None):
    """
    Get the user by ids
    """
    try:
        joinedUserIds = ",".join(userIds)
        output = await utils.make_API_call_to_CCow_and_get_response(constants.URL_USERS, "GET", {
            "ids": joinedUserIds,
        }, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))

        error = utils.build_structured_error(output, "audit_get_user_name_by_id")
        if error:
            logger.error("audit_get_user_name_by_id error: {}\n".format(output))
            return auditvo.UserListVO(error=error)
        
        users: List[auditvo.UserVO] = []
        for item in output.get("items",[]):
            if item.get("ID") and item.get("emailid"):
                users.append(auditvo.UserVO.model_validate(item))
                
        return auditvo.UserListVO(Users=users)
    except Exception as e:
        logger.error("audit_get_user_name_by_id error: {}\n".format(e))
        return auditvo.UserListVO(error=utils.build_structured_error(f"Unexpected error: {e}", "audit_get_user_name_by_id"))

