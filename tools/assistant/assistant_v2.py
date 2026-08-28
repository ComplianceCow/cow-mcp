import json
import traceback
import base64
import asyncio
import csv
import io
import secrets
from typing import Any, List, Literal
from typing import Tuple
import constants.error_constants as error_constants

from utils import utils
from utils import assistant as assistant_utils
from utils.debug import logger
from mcpconfig.config import mcp


from constants import constants
import yaml

from mcptypes import assessment_config_tool_types as assessment_vo
from mcptypes import workflow_tools_type as workflow_vo
from mcptypes.graph_tool_types import UniqueNodeDataVO
from mcptypes.assistant_tool_types import ControlSourceSummaryResponseVO, ControlSourceSummaryVO, FilteredEvidenceInputVO
from fastmcp import Context

from toon_format import encode

@mcp.tool()
async def assit_create_assessment(yaml_content: str, ctx: Context | None = None) -> dict:
    """
    Create a new assessment from YAML definition.
    
    This function creates an assessment from a YAML specification that defines the hierarchical control structure.
    The YAML must contain metadata with name and categoryName(Case In). The category lookup is **case-insensitive**. If a matching assessment category
    already exists (regardless of letter casing), it will be used. Otherwise, a new
    category will be created automatically

    Args:
        yaml_content: YAML string defining the assessment structure with metadata (including name and categoryName) and planControls
        
    Returns:
        Dict with success status, assessment data, UI URL, category name, or error details
    """
    try:
        logger.info("create_assessment: \n")
        
        if not yaml_content or not yaml_content.strip():
            logger.error("create_assessment error: YAML content is empty\n")
            return {"success": False, "error": "YAML content is empty"}

        try:
            parsed = yaml.safe_load(yaml_content)
            logger.debug("create_assessment yaml_content: {}\n".format(yaml_content))
        except Exception as ye:
            logger.error(f"create_assessment error: Invalid YAML: {ye}\n")
            return {"success": False, "error": f"Invalid YAML: {ye}"}

        # Extract name
        name = None
        if isinstance(parsed, dict):
            meta = parsed.get("metadata") or {}
            if isinstance(meta, dict):
                name = meta.get("name")

        if not name or not str(name).strip():
            logger.error("create_assessment error: Assessment name not found in metadata.name\n")
            return {"success": False, "error": "Assessment name not found in metadata.name"}

        # Extract categoryName from metadata
        category_name = None
        if isinstance(parsed, dict):
            meta = parsed.get("metadata") or {}
            if isinstance(meta, dict):
                category_name = meta.get("categoryName")

        if not category_name or not isinstance(category_name, str) or not category_name.strip():
            logger.error("create_assessment error: categoryName not found in metadata.categoryName\n")
            return {"success": False, "error": "categoryName is required in metadata.categoryName"}

        category_name = category_name.strip()
        category_id = None

        # Fetch all categories to check if category exists
        try:
            categories_resp = await utils.make_GET_API_call_to_CCow(constants.URL_ASSESSMENT_CATEGORIES, ctx=ctx)
            
            # Handle error response
            if isinstance(categories_resp, str):
                logger.error(f"create_assessment error: Failed to fetch categories: {categories_resp}\n")
                return {"success": False, "error": f"Failed to fetch assessment categories"}
            
            if isinstance(categories_resp, dict) and categories_resp.get("Description"):
                logger.error(f"create_assessment error: Failed to fetch categories: {categories_resp}\n")
                return {"success": False, "error": f"Failed to fetch assessment categories"}
            
            # Expect list response
            items = categories_resp
            
            if not isinstance(items, list):
                items = []
            
            for it in items:
                if isinstance(it, dict):
                    it_name = (it.get("name") or "").strip()
                    if it_name and it_name.lower() == category_name.lower():
                        category_id = it.get("id")
                        category_name = it_name
                        break
            
            # If category doesn't exist, create it
            if not category_id:
                logger.info(f"Category '{category_name}' not found, creating new category\n")
                create_category_payload = {"name": category_name}
                create_category_resp = await utils.make_API_call_to_CCow_and_get_response(constants.URL_ASSESSMENT_CATEGORIES,"POST",create_category_payload, ctx=ctx)
                # Handle error response from category creation
                if isinstance(create_category_resp, str):
                    logger.error(f"create_assessment error: Failed to create category: {create_category_resp}\n")
                    return {"success": False, "error": f"Failed to create category"}
                
                if isinstance(create_category_resp, dict):
                    if "Message" in create_category_resp:
                        logger.error(f"create_assessment error: Failed to create category: {create_category_resp}\n")
                        return {"success": False, "error": create_category_resp}

                    # Extract category ID from successful creation
                    category_id = create_category_resp.get("id")
                    if not category_id:
                        logger.error(f"create_assessment error: Category created but no ID returned: {create_category_resp}\n")
                        return {"success": False, "error": f"Failed to create category"}
                    
                    logger.info(f"Category '{category_name}' created successfully with ID: {category_id}\n")
                else:
                    logger.error(f"create_assessment error: Unexpected response type when creating category: {type(create_category_resp)}\n")
                    return {"success": False, "error": f"Unexpected response type when creating category"}
            else:
                logger.info(f"Using existing category '{category_name}' with ID: {category_id}\n")
                
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f"create_assessment error: Unable to resolve or create category: {e}\n")
            return {"success": False, "error": f"Unable to resolve or create category: {e}"}

        try:
            file_bytes = yaml_content.encode("utf-8")
            file_b64 = base64.b64encode(file_bytes).decode("utf-8")
        except Exception as be:
            logger.error(f"create_assessment error: Failed to encode YAML content: {be}\n")
            return {"success": False, "error": f"Failed to encode YAML content: {be}"}

        payload = {
            "name": str(name).strip(),
            "fileType": "yaml",
            "fileContent": file_b64,
            "linkDefaultCCFPlan":{
                "propagate": "evidence", "propagateToSource": "none", "nonReportable": True,
            }
        }
        payload["categoryId"] = category_id


        logger.debug("create_assessment payload: {}\n".format(json.dumps({**payload, "fileContent": "<base64-encoded>"})))
        
        resp = await utils.make_API_call_to_CCow_and_get_response(constants.URL_ASSESSMENTS,"POST",payload, ctx=ctx)
        logger.debug("create_assessment output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))
        
        # Ensure response is always a dict (utils can return string on error)
        if isinstance(resp, str):
            logger.error("create_assessment error: {}\n".format(resp))
            return {"success": False, "error": resp}
        
        # If response is already a dict, check for error fields
        if isinstance(resp, dict):
            if "Message" in resp:
                logger.error("create_assessment error: {}\n".format(resp))
                return {"success": False, "error": resp}
            
            # Extract assessment ID from response
            assessment_id = resp.get("id", "")
            
            # Build UI URL
            ui_url = ""
            try:
                base_host = constants.host.rstrip("/api") if hasattr(constants, "host") and isinstance(constants.host, str) else getattr(constants, "host", "")
                ui_url = f"{base_host}/ui/assessment-controls/{assessment_id}" if base_host and assessment_id else ""
            except Exception:
                ui_url = ""
            
            if assessment_id:
                logger.info(f"Assessment created successfully with ID: {assessment_id}")
            if ui_url:
                logger.info(f"Assessment created URL: {ui_url}")
            
            # Return successful response with URL and category name
            return {"success": True, "data": resp, "url": ui_url, "categoryName": category_name}
        
        # Fallback: wrap unexpected response type
        logger.error("create_assessment error: Unexpected response type: {}\n".format(type(resp)))
        return {"success": False, "error": f"Unexpected response type: {resp}"}
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_assessment error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error creating assessment: {e}"}



@mcp.tool()
async def assit_suggest_control_config_citations(
    controlName: str,
    assessmentId: str,
    description: str,
    controlId: str = "",
    ctx: Context | None = None
) -> dict:
    """
    Suggest control citations for a given control name or description.
    
    WORKFLOW: When user provides a requirement, ask which assessment they want to use.
    Get assessment name from user, then resolve to assessmentId (mandatory).
    For control: offer two options - select from existing control on selected assessment OR create new control.
    If selecting existing control, get control name from user and resolve to controlId.
    If creating new control, controlId will be empty.
    
    This function provides suggestions for control citations based on control names or descriptions.
    The user can select from the suggested controls to attach citations to their assessment controls.
    
    Args:
        controlName (str): Name of control to get suggestions for (required).
        assessmentId (str): Assessment ID - resolved from assessment name (required).
        description (str, optional): Description of the control to get suggestions for.
        controlId (str, optional): Control ID - resolved from control name if selecting existing control, empty if creating new control.
    
    Returns:
        Dict with success status and suggestions:
        - success (bool): Whether the request was successful
        - items (list[dict]): List of suggestion items, each containing:
            - inputControlName (str): The input control name
            - controlId (str): The control ID (empty if control doesn't exist yet)
            - suggestions (list[dict]): List of suggested controls, each containing:
                - Name (str): Control name
                - Control ID (int): Control ID number
                - Control Classification (str): Classification type
                - Impact Zone (str): Impact zone category
                - Control Requirement (str): Requirement level
                - Sort ID (str): Sort identifier
                - Control Type (str): Type of control
                - Score (float): Similarity score
        - authorityDocument (str): Name of the authorityDocument
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("suggest_control_config_citations: \n")
        
        # Validate mandatory assessmentId
        if not assessmentId or not str(assessmentId).strip():
            logger.error("suggest_control_config_citations error: assessmentId is mandatory\n")
            return {"success": False, "error": "assessmentId is mandatory"}
        
        # Log assessment and control IDs for context
        logger.info(f"suggest_control_config_citations: assessmentId={assessmentId}\n")
        if controlId:
            logger.info(f"suggest_control_config_citations: controlId={controlId} (existing control)\n")
        else:
            logger.info(f"suggest_control_config_citations: controlId=empty (creating new control)\n")
        
        if not controlName or not str(controlName).strip():
            logger.error("suggest_control_config_citations error: control name is mandatory and cannot be empty\n")
            return {"success": False, "error": "control name is mandatory and cannot be empty"}
        
        # Build payload - using minimal required fields
        payload = {
            "assessment_type": "asset",
            "assessment_id": "",
            "assessment_name": "",
            "use_default_authority_document": True,
            "controls": [
                {
                    "id": "",
                    "name": str(controlName).strip(),
                    "description": str(description).strip() if description else ""
                }
            ]
        }
        
        logger.debug("suggest_control_config_citations payload: {}\n".format(json.dumps(payload)))
        
        # Make API call
        resp = await utils.make_API_call_to_CCow(payload, constants.URL_GET_SIMILAR_CONTROLS, ctx=ctx)
        logger.debug("suggest_control_config_citations output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))
        
        # Handle error response
        if isinstance(resp, str):
            logger.error("suggest_control_config_citations error: {}\n".format(resp))
            return {"success": False, "error": resp}
        
        if isinstance(resp, dict):
            # Check for error fields
            if "error" in resp:
                logger.error("suggest_control_config_citations error: {}\n".format(resp.get("error")))
                return {"success": False, "error": resp.get("error")}
            
            if "Message" in resp:
                logger.error("suggest_control_config_citations error: {}\n".format(resp))
                return {"success": False, "error": resp}
            
            # Abstract and return only necessary fields
            items = resp.get("items", [])
            authorityDocument = resp.get("authorityDocument", "")
            abstracted_items = []
            for item in items:
                if isinstance(item, dict):
                    abstracted_item = {
                        "inputControlName": item.get("inputControlName", ""),
                        "controlId": item.get("controlId", ""),
                        "suggestions": []
                    }
                    suggestions = item.get("suggestions", [])
                    for suggestion in suggestions:
                        if isinstance(suggestion, dict):
                            abstracted_suggestion = {
                                "Name": suggestion.get("Name", ""),
                                "Control ID": suggestion.get("Control ID", ""),
                                "Control Classification": suggestion.get("Control Classification", ""),
                                "Impact Zone": suggestion.get("Impact Zone", ""),
                                "Control Requirement": suggestion.get("Control Requirement", ""),
                                "Sort ID": suggestion.get("Sort ID", ""),
                                "Control Type": suggestion.get("Control Type", ""),
                                "Score": suggestion.get("Score", 0.0)
                            }
                            abstracted_item["suggestions"].append(abstracted_suggestion)
                    abstracted_items.append(abstracted_item)
            
            logger.info(f"suggest_control_config_citations: Successfully retrieved {len(abstracted_items)} suggestion item(s)\n")
            return {"success": True, "items": abstracted_items,"authorityDocument": authorityDocument, "next_action": "attachToControl"}
        
        # Fallback: wrap unexpected response type
        logger.error("suggest_control_config_citations error: Unexpected response type: {}\n".format(type(resp)))
        return {"success": False, "error": f"Unexpected response type: {resp}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("suggest_control_config_citations error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error suggesting control citations: {e}"}


@mcp.tool()
async def assit_list_assessments(
    categoryId: str = "",
    categoryName: str = "",
    assessmentName: str = "",
    ctx: Context | None = None
) -> assessment_vo.AssessmentListVO:
    """
    Get all assessments with optional filtering.
    
    This function retrieves a list of assessments, optionally filtered by category ID, category name, or assessment name.
    
    Args:
        categoryId (str, optional): Assessment category ID to filter by.
        categoryName (str, optional): Assessment category name to filter by (partial match).
        assessmentName (str, optional): Assessment name to filter by (partial match).
    
    Returns:
        AssessmentListVO containing:
            - assessments (list[AssessmentVO]): A list of assessment objects, where each assessment includes:
                - id (str): Unique identifier of the assessment.
                - name (str): Name of the assessment.
                - categoryName (str): Name of the category.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        logger.info("list_assessments: \n")
        
        output=await utils.make_GET_API_call_to_CCow(constants.URL_PLANS+"?fields=basic&category_id="+categoryId+"&category_name_contains="+categoryName+"&name_contains="+assessmentName, ctx=ctx)

        if isinstance(output, str) or "error" in output:
            logger.error("list_assessments error: {}\n".format(output))
            return assessment_vo.AssessmentListVO(error="Facing internal error")
        
        assessments: list[assessment_vo.AssessmentVO] = []
        
        if isinstance(output, dict) and "items" in output:
            items = output["items"]
        else:
            items = []
        
        for item in items:
            if isinstance(item, dict) and "name" in item and "categoryName" in item:
                assessments.append(
                    assessment_vo.AssessmentVO(
                        id=item.get("id"),
                        name=item.get("name"),
                        categoryName=item.get("categoryName")
                    )
                )
        
        logger.debug("list_assessments: Found {} assessment(s)\n".format(len(assessments)))
        logger.debug(f"list_assessments: All assessments:\n{assessments}")      

        return assessment_vo.AssessmentListVO(assessments=assessments)
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_assessments error: {}\n".format(e))
        return assessment_vo.AssessmentListVO(error="Facing internal error")


@mcp.tool()
async def assit_list_assessment_control_configs(
    assessmentId: str,
    ctx: Context | None = None
) -> dict:
    """
    List all control configs for a given assessment id
    
    This function retrieves all control configs for an assessment
    
    Args:
        assessmentId (str): The assessment ID (plan ID) to list control configs for.
    
    Returns:
        Dict with success status and controls:
        - success (bool): Whether the request was successful
        - controls (list[dict]): List of control objects, each containing:
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
            return {"success": False, "error": "assessmentId is mandatory"}
        
        assessment_id = str(assessmentId).strip()
        page_size = 100
        cur_page = 1
        has_next = True
        all_controls = []
        max_pages = 10
        
        # Recursively fetch pages using TotalPage from response (max 10 pages)
        while has_next and cur_page <= max_pages:
            query_params = f"?page={cur_page}&page_size={page_size}&plan_id={assessment_id}&fields=basic&is_leaf_control=true&include_additional_context=true"
            logger.debug(f"list_assessment_control_configs fetching page {cur_page}: {query_params}\n")
            
            output = await utils.make_GET_API_call_to_CCow(constants.URL_PLAN_CONTROLS + query_params, ctx=ctx)
            
            logger.error("list_assessment_control_configs page: {}\noutput: {}\n".format(cur_page, output))


            # Handle error response
            if isinstance(output, str) or (isinstance(output, dict) and "error" in output):
                if cur_page == 1:
                    logger.error("list_assessment_control_configs error: {}\n".format(output))
                    return {"success": False, "error": "Failed to fetch controls"}
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
                        abstracted_control = {
                            "id": item.get("id", ""),
                            "name": item.get("name", ""),
                            "description": item.get("description", ""),
                            "alias": item.get("alias", ""),
                            "controlNumber": item.get("displayable", ""),
                            "context": item.get("context", ""),
                            "additionalContext": item.get("additionalContext", "")
                        }
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

        return {"success": True, "controls": all_controls, "totalCount": len(all_controls)}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_assessment_control_configs error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error listing assessment controls: {e}"}


# @mcp.tool()
async def assit_create_control_config(
    assessmentId: str,
    name: str,
    alias: str,
    controlNumber: str,
    description: str,
    ctx: Context | None = None
) -> dict:
    """
    Create a new control config in an assessment.
    
    This tool creates a new control config with the specified details.
    
    Args:
        assessmentId (str): The assessment ID (plan ID) to create the control in.
        name (str): Control name (required).
        description (str, optional): Control description.
        alias (str): Control alias (required).
        controlNumber (str): Displayable control number (required).
    
    Returns:
        Dict with success status and control data:
        - success (bool): Whether the request was successful
        - control (dict): Created control object containing:
            - id (str): Control ID
            - displayable (str): Displayable control number
            - alias (str): Control alias
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("create_control_config: \n")
        
        if not assessmentId or not str(assessmentId).strip():
            logger.error("create_control_config error: assessmentId is mandatory\n")
            return {"success": False, "error": "assessmentId is mandatory"}
        
        if not name or not str(name).strip():
            logger.error("create_control_config error: name is mandatory\n")
            return {"success": False, "error": "name is mandatory"}
        
        # Build payload
        payload = {
            "name": str(name).strip(),
            "description": str(description).strip() if description else "",
            "displayable": str(controlNumber).strip() if controlNumber else "",
            "alias": str(alias).strip() if alias else "",
            "planId": str(assessmentId).strip(),
            "isPreRequisite": False
        }
        
        logger.debug("create_control_config payload: {}\n".format(json.dumps(payload)))
        
        # Make API call
        resp = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_CONTROLS,
            "POST",
            payload,
            ctx=ctx
        )
        
        logger.debug("create_control_config output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))
        
        # Handle error response
        if isinstance(resp, str):
            logger.error("create_control_config error: {}\n".format(resp))
            return {"success": False, "error": resp}
        
        if isinstance(resp, dict):
            # Check for error fields
            if "Message" in resp:
                logger.error("create_control_config error: {}\n".format(resp))
                return {"success": False, "error": resp}
            
            # Abstract and return only necessary fields
            control = {
                "id": resp.get("id", ""),
                "displayable": resp.get("displayable", ""),
                "alias": resp.get("alias", "")
            }
            
            logger.info(f"create_control_config: Successfully created control with ID: {control.get('id')}\n")
            return {"success": True, "control": control}
        
        # Fallback: wrap unexpected response type
        logger.error("create_control_config error: Unexpected response type: {}\n".format(type(resp)))
        return {"success": False, "error": f"Unexpected response type: {resp}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_control_config error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error creating control: {e}"}


@mcp.tool()
async def assit_attach_citation_to_control_config(
    assessmentId: str,
    controlId: str,
    authorityDocument: str,
    controlIdsInAuthorityDocument: list[str],
    sortId: str,
    controlNames: list[str],
    confirm: bool = False,
    ctx: Context | None = None
) -> dict:
    """
    Attach citation to a control in an assessment.
    
    This tool attaches ONE citation from an authority document to a specific control in an assessment.
    The citation details should come from the get similar control config suggestions.
    A control config can have ONLY ONE citation.
    Use control config existing or create new control config on assessment.
    
    ✅ CONFIRMATION-BASED SAFETY FLOW
    - When confirm=False:
        → The tool returns a PREVIEW of the citation details.
        → The user may change the details before confirming.
    - When confirm=True:
        → The citation is permanently attached to the control config.
        
    ❌ IMPORTANT RESTRICTIONS
    - NEVER auto-select an assessment or control or citation.
    - NEVER call this tool with confirm=True in the same turn where the preview is first shown.
    - Assessment, control and citation MUST be explicitly user-selected and user-confirmed.

    Args:
        assessmentId (str): The assessment ID (plan ID) - MUST be user-selected.
        controlId (str): The control ID to attach citations to - MUST be user-selected.
        authorityDocument (str): The authority document name (e.g., "Trial1 CF").
        controlIdsInAuthorityDocument (list[str]): List of control IDs from the authority document (e.g., ["10014"]).
        sortId (str): Sort ID from the suggestion (e.g., "010 014").
        controlNames (list[str]): List of control names from the suggestion (e.g., ["Multifactor Authentication"]).
        confirm (bool, optional): If False, shows preview with assessment and control IDs for confirmation.
                                  If True, proceeds with attachment. Defaults to False.
    
    Returns:
        Dict with success status and citation data:
        - success (bool): Whether the request was successful
        - citations (list[dict], optional): List of attached citation objects (only when confirm=True), each containing:
            - id (str): Citation ID
            - planControlID (str): Plan control ID
            - authorityDocument (str): Authority document name
            - controlNames (list[str]): Control names
            - controlsInAuthorityDocument (list[str]): Control IDs in authority document
            - sortID (str): Sort ID
            - status (str): Citation status
        - assessmentId (str, optional): Assessment ID for confirmation (only when confirm=False)
        - controlId (str, optional): Control ID for confirmation (only when confirm=False)
        - citationDetails (dict, optional): Citation details for confirmation (only when confirm=False)
        - message (str, optional): Confirmation message (only when confirm=False)
        - next_step (str, optional): Next step instruction (only when confirm=False)
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("attach_citation_to_control_config: \n")
        
        if not assessmentId or not str(assessmentId).strip():
            logger.error("attach_citation_to_control_config error: assessmentId is mandatory\n")
            return {"success": False, "error": "assessmentId is mandatory"}
        
        if not controlId or not str(controlId).strip():
            logger.error("attach_citation_to_control_config error: controlId is mandatory\n")
            return {"success": False, "error": "controlId is mandatory"}
        
        if not authorityDocument or not str(authorityDocument).strip():
            logger.error("attach_citation_to_control_config error: authorityDocument is mandatory\n")
            return {"success": False, "error": "authorityDocument is mandatory"}
        
        if not controlIdsInAuthorityDocument or not isinstance(controlIdsInAuthorityDocument, list) or len(controlIdsInAuthorityDocument) == 0:
            logger.error("attach_citation_to_control_config error: controlIdsInAuthorityDocument must be a non-empty list\n")
            return {"success": False, "error": "controlIdsInAuthorityDocument must be a non-empty list"}
        
        if not sortId or not str(sortId).strip():
            logger.error("attach_citation_to_control_config error: sortId is mandatory\n")
            return {"success": False, "error": "sortId is mandatory"}
        
        if not controlNames or not isinstance(controlNames, list) or len(controlNames) == 0:
            logger.error("attach_citation_to_control_config error: controlNames must be a non-empty list\n")
            return {"success": False, "error": "controlNames must be a non-empty list"}
        
        assessment_id = str(assessmentId).strip()
        control_id = str(controlId).strip()
        
        # If confirm=False, return preview for user confirmation
        if not confirm:
            logger.info("attach_citation_to_control_config: Returning confirmation preview\n")
            return {
                "success": True,
                "message": "Confirmation required before attaching citation to control config",
                "assessmentId": assessment_id,
                "controlId": control_id,
                "citationDetails": {
                    "authorityDocument": str(authorityDocument).strip(),
                    "controlIdsInAuthorityDocument": controlIdsInAuthorityDocument,
                    "sortId": str(sortId).strip(),
                    "controlNames": controlNames
                },
                "next_step": "Review the assessment, control config ID and citation details above. If correct, re-run with confirm=True to attach the citation.",
                "next_action": "Await for user confirmation",
            }
        
        # Ensure authority document assessment is linked before attaching citations
        link_payload = {"id": assessment_id}
        logger.debug(f"attach_citation_to_control_config: Linking authority document assessment with payload: {json.dumps(link_payload)}\n")
        link_resp = await utils.make_API_call_to_CCow_and_get_response(
            f"{constants.URL_PLANS}/link-authority-document-assessment",
            "POST",
            link_payload,
            ctx=ctx
        )
        logger.debug("attach_citation_to_control_config link output: {}\n".format(json.dumps(link_resp) if isinstance(link_resp, dict) else link_resp))

        if isinstance(link_resp, str):
            logger.error("attach_citation_to_control_config error linking authority document assessment: {}\n".format(link_resp))
            return {"success": False, "error": link_resp}

        if isinstance(link_resp, dict):
            if "Message" in link_resp:
                if link_resp.get("Message") == "LINK_ALREADY_EXISTS":
                    logger.info(f"attach_citation_to_control_config: Authority document assessment already linked: {link_resp}\n")
                else:
                    logger.error("attach_citation_to_control_config error linking authority document assessment: {}\n".format(link_resp))
                    return {"success": False, "error": link_resp}

        # Build payload
        payload = {
            "authorityDocument": str(authorityDocument).strip(),
            "planControlCitations": [
                {
                    "planControlID": control_id,
                    "controlsInAuthorityDocument": [str(cid).strip() for cid in controlIdsInAuthorityDocument],
                    "sortID": str(sortId).strip(),
                    "controlNames": [str(name).strip() for name in controlNames]
                }
            ]
        }
        
        logger.debug("attach_citation_to_control_config payload: {}\n".format(json.dumps(payload)))
        
        # Make API call
        resp = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_CONTROL_CITATIONS_BATCH,
            "POST",
            payload,
            ctx=ctx
        )
        logger.debug("attach_citation_to_control_config output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))
        
        # Handle error response
        if isinstance(resp, str):
            logger.error("attach_citation_to_control_config error: {}\n".format(resp))
            return {"success": False, "error": resp}
        
        if isinstance(resp, dict):
            # Check for error fields
            if "Message" in resp and resp.get("Message") != "AUTHORITY_DOCUMENT_EXISTS":
                logger.error("attach_citation_to_control_config error: {}\n".format(resp))
                return {"success": False, "error": resp}

            # Abstract and return only necessary fields
            items = resp.get("items", [])
            abstracted_citations = []
            for item in items:
                if isinstance(item, dict):
                    abstracted_citation = {
                        "id": item.get("id", ""),
                        "planControlID": item.get("planControlID", ""),
                        "authorityDocument": item.get("authorityDocument", ""),
                        "controlNames": item.get("controlNames", []),
                        "controlsInAuthorityDocument": item.get("controlsInAuthorityDocument", []),
                        "sortID": item.get("sortID", ""),
                        "status": item.get("status", "")
                    }
                    abstracted_citations.append(abstracted_citation)

            logger.info(f"attach_citation_to_control_config: Successfully attached {len(abstracted_citations)} citation(s)\n")
            
            # Sync CCF IDs after successful citation attachment
            try:
                sync_payload = {
                    "planID": assessment_id,
                    "authorityDocument": str(authorityDocument).strip(),
                    "updateControlLinking": True,
                    "controlId": control_id,
                    # "syncGraph": True
                }
                logger.debug("attach_citation_to_control_config: Syncing CCF IDs with payload: {}\n".format(json.dumps(sync_payload)))
                
                sync_resp = await utils.make_API_call_to_CCow_and_get_response(
                    constants.URL_PLANS_SYNC_CCFID,
                    "POST",
                    sync_payload,
                    ctx=ctx
                )
                
                # Log sync result but don't fail the citation attachment if sync fails
                if isinstance(sync_resp, str):
                    logger.warning(f"attach_citation_to_control_config: CCF ID sync returned error (citation still attached): {sync_resp}\n")
                elif isinstance(sync_resp, dict) and ("Message" in sync_resp or "error" in sync_resp):
                    logger.warning(f"attach_citation_to_control_config: CCF ID sync returned error (citation still attached): {sync_resp}\n")
                else:
                    logger.info(f"attach_citation_to_control_config: Successfully synced CCF IDs\n")
            except Exception as sync_error:
                # Log sync error but don't fail the citation attachment
                logger.warning(f"attach_citation_to_control_config: Failed to sync CCF IDs (citation still attached): {sync_error}\n")
                logger.debug(traceback.format_exc())
            
            return {"success": True, "citations": abstracted_citations, "next_action": "fetch control source summary"}
        
        # Fallback: wrap unexpected response type
        logger.error("attach_citation_to_control_config error: Unexpected response type: {}\n".format(type(resp)))
        return {"success": False, "error": f"Unexpected response type: {resp}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("attach_citation_to_control_config error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error attaching citation to control: {e}"}

@mcp.tool()
async def assit_create_sql_query_evidence(
    controlConfigId: str,
    sqlquery: str,
    referedEvidenceNames: list[str],
    newEvidenceName: str,
    confirm: bool = False,
    entityHierarchyReferenceName: str = None,
    additionalContextReferenceName: str = None,
    ctx: Context | None = None,
) -> dict:
    """
    Create a SQL query evidence for a control configuration.
    
    This tool creates a SQL-based query and associates it with a specified control configuration.

    ⚠️ IMPORTANT WORKFLOW (Two-Step Confirmation)
    1. The SQL query MUST always be shown to the user in PREVIEW mode before execution.
    2. The user can review, edit, or approve the SQL query.
    3. Only after explicit confirmation (confirm=True) will the SQL query be created and attached.
    
    🔍 EVIDENCE & TABLE MAPPING
    - The `referedEvidenceNames` represent existing evidenceConfigNames.
    - These names MUST be used as table names inside the SQL query.
    - A new evidence config will be created using `newEvidenceName` to store the output of the SQL query.

    ⚠️ EVIDENCE ASSUMPTION (MANDATORY)
    - NEVER assume that an evidence config, its structure (schema), or its data exists.
    - NEVER fabricate evidence config names, table structures, or sample data.
    - If required evidence config details, schema, or data are NOT explicitly available:
        → Clearly inform the user that this information is missing.
        → Ask the user to provide:
            - Evidence config name(s)
            - Evidence schema / structure (e.g., columns and types)
            - And/or sample data
    - The tool MUST NOT proceed based on guessed or assumed evidence structures.

    🧪 OPTIONAL QUERY EXECUTION & OUTPUT PREVIEW
    - After showing the SQL preview, the user may optionally request to:
        → Run the SQL query on sample data to preview the output.
    - If sample data is available:
        → The system will manually execute the query and display the result to the user.
    - If sample data is NOT available and the user requests execution:
        → The system must explicitly ask the user to provide sample data before execution.

    Show the suggestion optional to run query to user to run query and see output, U manually perform the run on sample data and show output, If sample data is not available if user ask to run, ask user to provide the sample data.
    
    Args:
        controlConfigId (str): The control config ID where the query is to be attached (required).
        sqlquery (str): The SQL query definition (required). The query should reference evidenceConfigNames as table names.
                      When confirm=False, this will be displayed in the preview. When confirm=True, the SQL query will be created and attached.
        referedEvidenceNames (list[str]): List of evidenceConfigNames that are referenced as table names in the SQL query (required, non-empty).
        newEvidenceName (str): Name of the new evidence config to be created (required).
        confirm (bool, optional): If False, returns preview with the SQL query displayed for review (and optional modification).
                                 If True, proceeds with SQL query creation using the provided sqlquery.
        entityHierarchyReferenceName (str, optional): Reference name for entity hierarchy table.
        additionalContextReferenceName (str, optional): Reference name for additional control context table.

    Returns:
        Dict with success status and data:
        - success (bool): Whether the request was successful
        - ruleId (str, optional): Created rule ID
        - evidenceId (str, optional): Created evidence Config,
        - message (str, optional): Success or error message
        - sqlquery (str, optional): The SQL query shown in preview (when confirm=False)
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("create_sql_query_evidence: \n")
        
        if not controlConfigId or not str(controlConfigId).strip():
            logger.error("create_sql_query_evidence error: controlConfigId is mandatory\n")
            return {"success": False, "error": "controlConfigId is mandatory"}
        
        if not sqlquery or not str(sqlquery).strip():
            logger.error("create_sql_query_evidence error: sqlquery is mandatory\n")
            return {"success": False, "error": "sqlquery is mandatory"}
        
        if not newEvidenceName or not str(newEvidenceName).strip():
            logger.error("create_sql_query_evidence error: newEvidenceName is mandatory\n")
            return {"success": False, "error": "newEvidenceName is mandatory"}
        
        # Build payload according to API specification
        payload = {
            "sqlQuery": str(sqlquery).strip(),
            "evidenceName": str(newEvidenceName).strip(),
            "referedEvidenceNames": [str(name).strip() for name in referedEvidenceNames if name and str(name).strip()]
        }
        
        # Add optional context reference names if provided
        if entityHierarchyReferenceName and str(entityHierarchyReferenceName).strip():
            payload["entityHierarchyEvidenceName"] = str(entityHierarchyReferenceName).strip()
        
        if additionalContextReferenceName and str(additionalContextReferenceName).strip():
            payload["controlContextEvidenceName"] = str(additionalContextReferenceName).strip()

        if not confirm:
            logger.info("create_sql_query_evidence: Returning confirmation preview\n")
            return {
                "success": True,
                "message": "Confirmation required before creating SQL query",
                "controlConfigId": str(controlConfigId).strip(),
                "sqlQuery": payload["sqlQuery"],
                "newEvidenceName": payload["evidenceName"],
                "referedEvidenceNames": payload["referedEvidenceNames"],
                "next_step": "Review the SQL query above. If you need to modify it, provide the updated sqlquery parameter when calling with confirm=True. If correct, re-run with confirm=True to create and attach the query."
            }
        
        url = f"{constants.URL_PLAN_CONTROLS}/{str(controlConfigId).strip()}/sql-query-evidences"
        
        logger.debug("create_sql_query_evidence payload: {}\n".format(json.dumps(payload)))
        logger.debug("create_sql_query_evidence URL: {}\n".format(url))
        
        # Make API call
        resp = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "POST",
            payload,
            ctx=ctx
        )
        
        logger.debug("create_sql_query_evidence output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))
        
        # Handle error response
        if isinstance(resp, str):
            logger.error("create_sql_query_evidence error: {}\n".format(resp))
            return {"success": False, "error": resp}
        
        if isinstance(resp, dict):
            # Check for error fields
            if "Message" in resp:
                logger.error("create_sql_query_evidence error: {}\n".format(resp))
                return {"success": False, "error": resp}
            
            if "error" in resp:
                logger.error("create_sql_query_evidence error: {}\n".format(resp.get("error")))
                return {"success": False, "error": resp.get("error")}

            rule_id = resp.get("ruleId")
            evidence_id = resp.get("evidenceId")

            if rule_id:
                logger.info(f"create_sql_query_evidence: Successfully created SQL query with ruleId: {rule_id}\n")
                return {
                    "success": True,
                    "evidenceId": evidence_id,
                    "message": "SQL query and evidence config created successfully",
                    "next_step": "Would you like to add documentation notes for this SQL query on the control? This is optional but recommended for traceability."
                }
        
        # Fallback: wrap unexpected response type
        logger.error("create_sql_query_evidence error: Unexpected response type: {}\n".format(type(resp)))
        return {"success": False, "error": f"Unexpected response type: {resp}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_sql_query_evidence error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error creating SQL query: {e}"}

@mcp.tool()
async def assit_list_sql_query_evidence(
    controlConfigId: str,
    ctx: Context | None = None
) -> dict:
    """
    List all SQL query evidences for a given control configuration.
    
    This tool retrieves all SQL query evidences associated with a control configuration.
    
    Args:
        controlConfigId (str): The control config ID to list SQL query evidences for (required).
    
    Returns:
        Dict with success status and evidences:
        - success (bool): Whether the request was successful
        - evidences (list[dict]): List of SQL query evidence objects, each containing:
            - id (str): Evidence ID
            - evidenceId (str): Evidence config ID
            - ruleId (str): Rule ID
            - sqlQuery (str): SQL query string
            - evidenceName (str): Evidence config name
            - referedEvidenceNames (list[str]): List of referenced evidence names
        - totalCount (int): Total number of evidences found
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("list_sql_query_evidence: \n")
        
        if not controlConfigId or not str(controlConfigId).strip():
            logger.error("list_sql_query_evidence error: controlConfigId is mandatory\n")
            return {"success": False, "error": "controlConfigId is mandatory"}
        
        control_config_id = str(controlConfigId).strip()
        url = f"{constants.URL_PLAN_CONTROLS}/{control_config_id}/sql-query-evidences"
        
        logger.debug("list_sql_query_evidence URL: {}\n".format(url))
        
        output = await utils.make_GET_API_call_to_CCow(url, ctx=ctx)
        
        if isinstance(output, str) or (isinstance(output, dict) and "error" in output):
            logger.error("list_sql_query_evidence error: {}\n".format(output))
            return {"success": False, "error": "Failed to fetch SQL query evidences"}
        
        if isinstance(output, dict):
            if "Message" in output:
                logger.error("list_sql_query_evidence error: {}\n".format(output))
                return {"success": False, "error": output}
            
            items = output.get("items", [])
            if not isinstance(items, list):
                items = []
            
            logger.info(f"list_sql_query_evidence: Found {len(items)} SQL query evidence(s)\n")
            return {"success": True, "evidences": items, "totalCount": len(items)}

        logger.error("list_sql_query_evidence error: Unexpected response type: {}\n".format(type(output)))
        return {"success": False, "error": f"Unexpected response type: {output}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_sql_query_evidence error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error listing SQL query evidences: {e}"}

@mcp.tool()
async def assit_update_sql_query_evidence(
    controlConfigId: str,
    evidenceId: str,
    sqlquery: str,
    referedEvidenceNames: list[str],
    newEvidenceName: str,
    confirm: bool = False,
    entityHierarchyReferenceName: str = None,
    additionalContextReferenceName: str = None,
    ctx: Context | None = None,
) -> dict:
    """
    Update an existing SQL query evidence for a control configuration.
    
    This tool updates an existing SQL query evidence with new SQL query, evidence mappings, or evidence name.

    ⚠️ IMPORTANT WORKFLOW (Two-Step Confirmation)
    1. The updated SQL query MUST always be shown to the user in PREVIEW mode before execution.
    2. The user can review, edit, or approve the updated SQL query.
    3. Only after explicit confirmation (confirm=True) will the SQL query evidence be updated.
    
    🔍 EVIDENCE & TABLE MAPPING
    - The `referedEvidenceNames` represent existing evidenceConfigNames.
    - These names MUST be used as table names inside the SQL query.
    - The evidence config name can be updated using `newEvidenceName`.
    
    Args:
        controlConfigId (str): The control config ID where the SQL query evidence exists (required).
        evidenceId (str): The evidence ID of the SQL query evidence to update (required).
        sqlquery (str): The updated SQL query definition (required). The query should reference evidenceConfigNames as table names.
                      When confirm=False, this will be displayed in the preview. When confirm=True, the SQL query will be updated.
        referedEvidenceNames (list[str]): List of evidenceConfigNames that are referenced as table names in the SQL query (required, non-empty).
        newEvidenceName (str): Updated name of the evidence config (required).
        confirm (bool, optional): If False, returns preview with the updated SQL query displayed for review (and optional modification).
                                 If True, proceeds with SQL query evidence update using the provided sqlquery.
        entityHierarchyReferenceName (str, optional): Reference name for entity hierarchy table.
        additionalContextReferenceName (str, optional): Reference name for additional control context table.

    Returns:
        Dict with success status and data:
        - success (bool): Whether the request was successful
        - evidenceId (str, optional): Updated evidence ID
        - message (str, optional): Success or error message
        - sqlquery (str, optional): The SQL query shown in preview (when confirm=False)
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("update_sql_query_evidence: \n")
        
        if not controlConfigId or not str(controlConfigId).strip():
            logger.error("update_sql_query_evidence error: controlConfigId is mandatory\n")
            return {"success": False, "error": "controlConfigId is mandatory"}
        
        if not evidenceId or not str(evidenceId).strip():
            logger.error("update_sql_query_evidence error: evidenceId is mandatory\n")
            return {"success": False, "error": "evidenceId is mandatory"}
        
        if not sqlquery or not str(sqlquery).strip():
            logger.error("update_sql_query_evidence error: sqlquery is mandatory\n")
            return {"success": False, "error": "sqlquery is mandatory"}
        
        if not newEvidenceName or not str(newEvidenceName).strip():
            logger.error("update_sql_query_evidence error: newEvidenceName is mandatory\n")
            return {"success": False, "error": "newEvidenceName is mandatory"}
        
        # Build payload according to API specification
        payload = {
            "sqlQuery": str(sqlquery).strip(),
            "evidenceName": str(newEvidenceName).strip(),
            "referedEvidenceNames": [str(name).strip() for name in referedEvidenceNames if name and str(name).strip()]
        }
        
        # Add optional context reference names if provided
        if entityHierarchyReferenceName and str(entityHierarchyReferenceName).strip():
            payload["entityHierarchyEvidenceName"] = str(entityHierarchyReferenceName).strip()
        
        if additionalContextReferenceName and str(additionalContextReferenceName).strip():
            payload["controlContextEvidenceName"] = str(additionalContextReferenceName).strip()

        if not confirm:
            logger.info("update_sql_query_evidence: Returning confirmation preview\n")
            return {
                "success": True,
                "message": "Confirmation required before updating SQL query evidence",
                "controlConfigId": str(controlConfigId).strip(),
                "evidenceId": str(evidenceId).strip(),
                "sqlQuery": payload["sqlQuery"],
                "newEvidenceName": payload["evidenceName"],
                "referedEvidenceNames": payload["referedEvidenceNames"],
                "next_step": "Review the updated SQL query above. If you need to modify it, provide the updated sqlquery parameter when calling with confirm=True. If correct, re-run with confirm=True to update the SQL query evidence."
            }
        
        url = f"{constants.URL_PLAN_CONTROLS}/{str(controlConfigId).strip()}/sql-query-evidences/{str(evidenceId).strip()}"
        
        logger.debug("update_sql_query_evidence payload: {}\n".format(json.dumps(payload)))
        logger.debug("update_sql_query_evidence URL: {}\n".format(url))
        
        resp = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "PUT",
            payload,
            ctx=ctx
        )
        
        logger.debug("update_sql_query_evidence output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))
        
        # Handle error response
        if isinstance(resp, str):
            logger.error("update_sql_query_evidence error: {}\n".format(resp))
            return {"success": False, "error": resp}
        
        if isinstance(resp, dict):
            # Check for error fields
            if "Message" in resp:
                logger.error("update_sql_query_evidence error: {}\n".format(resp))
                return {"success": False, "error": resp}
            
            if "error" in resp:
                logger.error("update_sql_query_evidence error: {}\n".format(resp.get("error")))
                return {"success": False, "error": resp.get("error")}

            updated_evidence_id = resp.get("evidenceId") or str(evidenceId).strip()

            logger.info(f"update_sql_query_evidence: Successfully updated SQL query evidence with evidenceId: {updated_evidence_id}\n")
            return {
                "success": True,
                "evidenceId": updated_evidence_id,
                "message": "SQL query evidence updated successfully",
            }
        
        logger.error("update_sql_query_evidence error: Unexpected response type: {}\n".format(type(resp)))
        return {"success": False, "error": f"Unexpected response type: {resp}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_sql_query_evidence error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error updating SQL query evidence: {e}"}

@mcp.tool()
async def assit_fetch_control_source_summary(controlId: str, ctx: Context | None = None) -> ControlSourceSummaryResponseVO:
    """
    Fetch aggregated source summary for a control config, including linked control configs, evidences (including schema), and lineage depth.
    This tool is the PRIMARY way to gather SQL query context for a control config.

    It returns how a control is connected to evidence configurations and what evidence
    structures (schemas) are available.

    ⚠️ IMPORTANT WORKFLOW 
    If **no evidence configs** exist and a **citation is already attached**, SQL query generation must STOP.  
    If no evidence configs exist and a citation is already attached, SQL query generation must stop immediately.
    Do not proceed and do not provide any suggestions.
    No further actions or recommendations are allowed.
    
    Args:
        controlId (str): Plan control ID provided by the user (mandatory).

    Returns:
        ControlSourceSummaryResponseVO containing:
            - success (bool): API invocation status.
            - data (ControlSourceSummaryVO, optional): Source summary (lineage, evidence, schema) on success.
            - error (str, optional): Validation or API error details.
            - next_action (str, optional): Recommended next action.
    """
    try:
        logger.info("fetch_control_source_summary: \n")

        if not controlId or not str(controlId).strip():
            logger.error("fetch_control_source_summary error: controlId is mandatory\n")
            return ControlSourceSummaryResponseVO(success=False, error="controlId is mandatory")

        payload = {"controlID": str(controlId).strip()}
        logger.debug(
            "fetch_control_source_summary payload: {}\n".format(json.dumps(payload))
        )

        resp = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_CONTROLS_FETCH_SOURCE_SUMMARY,
            "POST",
            payload,
            ctx=ctx
        )

        logger.debug(
            "fetch_control_source_summary output: {}\n".format(
                json.dumps(resp) if isinstance(resp, dict) else resp
            )
        )

        if isinstance(resp, str):
            logger.error("fetch_control_source_summary error: {}\n".format(resp))
            return ControlSourceSummaryResponseVO(success=False, error=resp)

        if isinstance(resp, dict):
            if "Message" in resp:
                logger.error("fetch_control_source_summary error: {}\n".format(resp))
                return ControlSourceSummaryResponseVO(success=False, error=str(resp))

            try:
                summary_data = ControlSourceSummaryVO(**resp)
                logger.info("fetch_control_source_summary: Successfully parsed response into VO\n")
                response = ControlSourceSummaryResponseVO(
                    success=True, 
                    data=summary_data,
                )
                if summary_data.lineage and len(summary_data.lineage)>0:
                    response.next_action="get evidence sample data"
                else:
                    response.next_action="STOP_SQL_QUERY_GENERATION_NO_EVIDENCE_CONFIGS_ATTACHED"
                    response.next_step = (
                        "No evidence configurations are linked to this control. "
                        "SQL query automation cannot proceed. "
                    )
                return response
            except Exception as parse_error:
                logger.error(f"fetch_control_source_summary error: Failed to parse response: {parse_error}\n")
                logger.debug(traceback.format_exc())
                return ControlSourceSummaryResponseVO(
                    success=False, 
                    error=f"Failed to parse response: {parse_error}"
                )

        logger.error(
            "fetch_control_source_summary error: Unexpected response type: {}\n".format(
                type(resp)
            )
        )
        return ControlSourceSummaryResponseVO(
            success=False, 
            error=f"Unexpected response type: {resp}", 
            next_action="create sql query evidence"
        )

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_control_source_summary error: {}\n".format(e))
        return ControlSourceSummaryResponseVO(
            success=False,
            error=f"Unexpected error fetching control source summary: {e}",
        )

@mcp.tool()
async def assit_get_evidence_sample_data(controlConfigId: str, evidenceNames: list[str] | None = None, records: int = 3, ctx: Context | None = None) -> dict:
    """
    Fetch concrete evidence samples for a control config.

    Usage guidance:
    1. Run `fetch_control_source_summary` first to understand schema/lineage.
    2. Call this tool before drafting SQL query to inspect real evidence rows.
    3. Pass 1-10 records to keep payloads lightweight (defaults to 3).

    Args:
        controlConfigId (str): Control config ID where the SQL query will be attached (required).
        evidenceNames (list[str], optional): Specific evidence config names (table names) to sample.
            If omitted/empty, all evidences linked to the control are sampled.
        records (int, optional): Number of records per evidence (1-10, default 3).

    Returns:
        Dict containing:
            - success (bool): API invocation status.
            - controlId (str): Echoed control ID.
            - recordCount (int): Number of rows requested (after validation).
            - evidences (list[dict]): Evidence samples grouped by control/evidence. If an evidence
              is missing from the response, no records exist for it in the latest run.
            - next_action (str): Recommended next step (typically "create sql query").
            - error (str, optional): Validation or API error.
    """
    try:
        logger.info("get_evidence_sample_data: \n")

        if not controlConfigId or not str(controlConfigId).strip():
            logger.error("get_evidence_sample_data error: controlConfigId is mandatory\n")
            return {"success": False, "error": "controlConfigId is mandatory"}

        try:
            record_count = int(records)
        except (TypeError, ValueError):
            record_count = 3

        if record_count < 1 or record_count > 10:
            logger.warning(f"get_evidence_sample_data: records {record_count} out of bounds, defaulting to 3\n")
            record_count = 3

        payload = {
            "controlID": str(controlConfigId).strip(),
            "records": record_count
        }
        if evidenceNames:
            payload["evidenceNames"] = evidenceNames

        logger.debug("get_evidence_sample_data payload: {}\n".format(json.dumps(payload)))

        resp = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_CONTROLS_FETCH_SAMPLE_EVIDENCE_DATA,
            "POST",
            payload,
            ctx=ctx
        )

        logger.debug("get_evidence_sample_data output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))

        if isinstance(resp, str):
            logger.error("get_evidence_sample_data error: {}\n".format(resp))
            return {"success": False, "error": resp}

        if isinstance(resp, dict):
            if "error" in resp or "Message" in resp:
                logger.error("get_evidence_sample_data error: {}\n".format(resp))
                return {"success": False, "error": resp.get("error") or resp}

            logger.info("get_evidence_sample_data: Received dict payload\n")

        if isinstance(resp, list):
            logger.info(f"get_evidence_sample_data: Retrieved samples for {len(resp)} control(s)\n")
            response = {
                "success": True,
                "controlId": payload["controlID"],
                "evidences": resp,
            }

            if resp and len(resp)>0:
                response["next_action"]="create sql query"
            else:
                response["next_action"] = "CREATE_SQL_QUERY_FROM_SCHEMA_OR_REQUEST_USER_SAMPLES"
            return response

        logger.error("get_evidence_sample_data error: Unexpected response type: {}\n".format(type(resp)))
        return {
            "success": False,
            "error": f"Unexpected response type: {resp}",
        }

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_evidence_sample_data error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error fetching evidence samples: {e}"}

# @mcp.tool()
async def assit_get_entity_hierarchy(ctx: Context | None = None) -> dict:
    """
    Use this tool when the user wants to automate control operations,
    or before creating an SQL query.
    
    This tool retrieves entity hierarchy information.
    Returns:
        Dict with success status and context data:
        - success (bool): Whether the request was successful
        - data (dict, optional): Entity hierarchy data containing entities
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("get_entity_hierarchy: \n")
        
        # Make GET API call to ServiceNow entities endpoint
        output = await utils.make_GET_API_call_to_CCow(constants.URL_GET_ENTITY_HIERARCHY, ctx=ctx)
        
        # Handle error response
        if isinstance(output, str) or (isinstance(output, dict) and "error" in output):
            logger.error("get_entity_hierarchy error: {}\n".format(output))
            return {"success": False, "error": "Failed to fetch entity hierarchy"}
        
        # Check for error fields in response
        if isinstance(output, dict):
            if "Message" in output:
                logger.error("get_entity_hierarchy error: {}\n".format(output))
                return {"success": False, "error": output}
            
            logger.info(f"get_entity_hierarchy: Successfully retrieved entity hierarchy\n")
            return {"success": True, "data": output}
        
        # Fallback: wrap unexpected response type
        logger.error("get_entity_hierarchy error: Unexpected response type: {}\n".format(type(output)))
        return {"success": False, "error": f"Unexpected response type: {output}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_entity_hierarchy error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error fetching entity hierarchy: {e}"}

@mcp.tool()
async def assit_create_control_config_note(
    controlConfigId: str,
    assessmentId: str,
    notes: str,
    topic: str,
    confirm: bool = False,
    ctx: Context | None = None,
) -> dict:
    """
    Create a documentation note on a control configuration to record SQL query logic, evidence generation strategy, and implementation context.
    
    This tool creates a markdown documentation note that is attached to a control configuration.
    
    ✅ CONFIRMATION-BASED SAFETY FLOW
    - When confirm=False:
        → The tool returns a PREVIEW of the generated markdown note.
        → The user may edit the note before confirming.
    - When confirm=True:
        → The note is permanently created and attached to the control config.
    
    Args:
        controlConfigId (str): The control config ID where the note will be attached (required).
                              This is the same control config ID used in `create_sql_query_evidence`.
        assessmentId (str): The assessment ID that contains the control config (required).
        notes (str): The documentation content in MARKDOWN format (required).
        topic (str, optional): Topic or subject of the note. Defaults to "SQL Query Documentation".
        confirm (bool, optional):  
            - False → Preview only (default, no persistence)
            - True  → Create and permanently attach the note
    
    Returns:
        Dict with success status and note data:
        - success (bool): Whether the request was successful
        - note (dict, optional): Created note object containing:
            - id (str): Note ID
            - topic (str): Note topic
            - notes (str): Note content in markdown format
            - controlConfigId (str): Control config ID the note is attached to
            - assessmentId (str): Assessment ID
        - error (str, optional): Error message if request failed
        - next_action (str, optional): Recommended next action
    """
    try:
        logger.info("create_control_config_note: \n")
        
        if not controlConfigId or not str(controlConfigId).strip():
            logger.error("create_control_config_note error: controlConfigId is mandatory\n")
            return {"success": False, "error": "controlConfigId is mandatory"}
        
        if not assessmentId or not str(assessmentId).strip():
            logger.error("create_control_config_note error: assessmentId is mandatory\n")
            return {"success": False, "error": "assessmentId is mandatory"}
        
        if not notes or not str(notes).strip():
            logger.error("create_control_config_note error: notes content is mandatory\n")
            return {"success": False, "error": "notes content is mandatory"}
        
        # Build payload
        payload = {
            "topic": str(topic).strip(),
            "notes": str(notes).strip(),
            "planId": str(assessmentId).strip(),
            "planControlID": str(controlConfigId).strip(),
        }

        if not confirm:
            logger.info("create_control_config_note: Returning confirmation preview\n")
            return {
                "success": True,
                "message": "Confirmation required before creating note",
                "controlConfigId": payload["planControlID"],
                "topic": payload["topic"],
                "notes": payload["notes"],
                "next_step": "Review the Note above. If you need to modify it, provide the updated note parameter when calling with confirm=True. If correct, re-run with confirm=True to create note."
        }
        
        # Construct URL with control config ID
        url = constants.URL_PLAN_CONTROL_NOTES.format(controlConfigId=str(controlConfigId).strip())
        
        logger.debug("create_control_config_note payload: {}\n".format(json.dumps(payload)))
        logger.debug("create_control_config_note URL: {}\n".format(url))
        
        # Make API call
        resp_raw = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "POST",
            payload,
            return_raw=True,
            ctx=ctx
        )

        if resp_raw.status_code == 502:
            return {"success": False, "error": error_constants.ERROR_BAD_GATEWAY}
        
        
        if resp_raw.status_code == 201:
            resp = {}
            try:
                if resp_raw.content:
                    resp = resp_raw.json()
            except Exception:
                resp = {"error": f"HTTP {resp_raw.status_code}"}

            logger.info(f"create_control_config_note: \n Response : {resp}\n")
            noteId = ""
            if isinstance(resp, dict):
                noteId = resp.get("id")
            
            logger.info(f"create_control_config_note: Successfully created note with status 201\n")
            return {
                "success": True,
                "noteId": noteId,
                "message": "Note created successfully",
            }
        else:
            # Error - parse error response
            error_resp = {}
            try:
                if resp_raw.content:
                    error_resp = resp_raw.json()
            except Exception:
                error_resp = {"error": f"HTTP {resp_raw.status_code}"}
            
            logger.error("create_control_config_note error: Status {} - {}\n".format(resp_raw.status_code, error_resp))
            
            # Check for error fields in response
            if isinstance(error_resp, dict):
                if "Message" in error_resp:
                    return {"success": False, "error": error_resp}
                if "error" in error_resp:
                    return {"success": False, "error": error_resp.get("error")}

            return {"success": False, "error": f"Failed to create note: HTTP {resp_raw.status_code}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_control_config_note error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error creating control config note: {e}"}

@mcp.tool()
async def assit_list_control_config_notes(
    controlConfigId: str,
    ctx: Context | None = None
) -> dict:
    """
    List all notes for a given control configuration.
    
    This tool retrieves all notes associated with a control configuration.
    
    Args:
        controlConfigId (str): The control config ID to list notes for (required).
    
    Returns:
        Dict with success status and notes:
        - success (bool): Whether the request was successful
        - notes (list[dict]): List of note objects, each containing:
            - id (str): Note ID
            - topic (str): Note topic
            - notes (str): Note content
        - totalCount (int): Total number of notes found
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("list_control_config_notes: \n")
        
        if not controlConfigId or not str(controlConfigId).strip():
            logger.error("list_control_config_notes error: controlConfigId is mandatory\n")
            return {"success": False, "error": "controlConfigId is mandatory"}
        
        control_config_id = str(controlConfigId).strip()
        url = constants.URL_PLAN_CONTROL_NOTES.format(controlConfigId=control_config_id)
        
        logger.debug("list_control_config_notes URL: {}\n".format(url))
        
        output = await utils.make_GET_API_call_to_CCow(url, ctx=ctx)
        
        logger.info(f"create_control_config_note: \n Response : {output}\n")

        if isinstance(output, str) or (isinstance(output, dict) and "error" in output):
            logger.error("list_control_config_notes error: {}\n".format(output))
            return {"success": False, "error": "Failed to fetch control config notes"}
        
        if isinstance(output, dict):
            if "Message" in output:
                logger.error("list_control_config_notes error: {}\n".format(output))
                return {"success": False, "error": output}
            
            items = output.get("items", [])
            if not isinstance(items, list):
                items = []

            abstracted_items = []
            for item in items:
                if isinstance(item, dict):
                    abstracted_item = {
                        "id": item.get("id", ""),
                        "topic": item.get("topic", ""),
                        "notes": item.get("notes", ""),
                    }
                    abstracted_items.append(abstracted_item)
            
            logger.info(f"list_control_config_notes: {abstracted_items} \n Found {len(abstracted_items)} note(s)\n")
            return {"success": True, "notes": abstracted_items, "totalCount": len(abstracted_items)}
        
        logger.error("list_control_config_notes error: Unexpected response type: {}\n".format(type(output)))
        return {"success": False, "error": f"Unexpected response type: {output}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_control_config_notes error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error listing control config notes: {e}"}

@mcp.tool()
async def assit_update_control_config_note(
    controlConfigId: str,
    noteId: str,
    assessmentId: str,
    notes: str,
    topic: str,
    confirm: bool = False,
    ctx: Context | None = None,
) -> dict:
    """
    Update an existing documentation note on a control configuration.
    
    ✅ PURPOSE
    This tool updates an existing note that was previously created on a control config.
    It allows modification of the note content, topic, or both.
    
    ✅ CONFIRMATION-BASED SAFETY FLOW
    - When confirm=False:
        → The tool returns a PREVIEW of the updated markdown note.
        → The user may edit the note before confirming.
    - When confirm=True:
        → The note is permanently updated and saved.
    
    Args:
        controlConfigId (str): The control config ID where the note exists (required).
        noteId (str): The note ID to update (required).
        assessmentId (str): The assessment ID that contains the control config (required).
        notes (str): The updated documentation content in MARKDOWN format (required).
        topic (str, optional): Updated topic or subject of the note. Defaults to "SQL Query Documentation".
        confirm (bool, optional):  
            - False → Preview only (default, no persistence)
            - True  → Update and permanently save the note
    
    Returns:
        Dict with success status and note data:
        - success (bool): Whether the request was successful
        - message (str, optional): Success or error message
        - noteId (str, optional): Updated note ID
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("update_control_config_note: \n")
        
        if not controlConfigId or not str(controlConfigId).strip():
            logger.error("update_control_config_note error: controlConfigId is mandatory\n")
            return {"success": False, "error": "controlConfigId is mandatory"}
        
        if not noteId or not str(noteId).strip():
            logger.error("update_control_config_note error: noteId is mandatory\n")
            return {"success": False, "error": "noteId is mandatory"}
        
        if not assessmentId or not str(assessmentId).strip():
            logger.error("update_control_config_note error: assessmentId is mandatory\n")
            return {"success": False, "error": "assessmentId is mandatory"}
        
        if not notes or not str(notes).strip():
            logger.error("update_control_config_note error: notes content is mandatory\n")
            return {"success": False, "error": "notes content is mandatory"}
        
        # Build payload
        payload = {
            "topic": str(topic).strip(),
            "notes": str(notes).strip(),
            "planId": str(assessmentId).strip(),
            "planControlID": str(controlConfigId).strip(),
        }

        if not confirm:
            logger.info("update_control_config_note: Returning confirmation preview\n")
            return {
                "success": True,
                "message": "Confirmation required before updating note",
                "controlConfigId": payload["planControlID"],
                "noteId": str(noteId).strip(),
                "topic": payload["topic"],
                "notes": payload["notes"],
                "next_step": "Review the updated Note above. If you need to modify it, provide the updated notes or topic parameters when calling with confirm=True. If correct, re-run with confirm=True to update the note."
            }
        
        # Construct URL with control config ID and note ID
        url = f"{constants.URL_PLAN_CONTROL_NOTES.format(controlConfigId=str(controlConfigId).strip())}/{str(noteId).strip()}"
        
        logger.debug("update_control_config_note payload: {}\n".format(json.dumps(payload)))
        logger.debug("update_control_config_note URL: {}\n".format(url))
        
        # Make API call
        resp_raw = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "PUT",
            payload,
            return_raw=True,
            ctx=ctx
        )

        if resp_raw.status_code == 502:
            return {"success": False, "error": error_constants.ERROR_BAD_GATEWAY}
        
        if resp_raw.status_code == 204:
            logger.info(f"update_control_config_note: Successfully updated note with status 204\n")
            return {
                "success": True,
                "noteId": str(noteId).strip(),
                "message": "Note updated successfully",
            }
        else:
            # Error - parse error response
            error_resp = {}
            try:
                if resp_raw.content:
                    error_resp = resp_raw.json()
            except Exception:
                error_resp = {"error": f"HTTP {resp_raw.status_code}"}
            
            logger.error("update_control_config_note error: Status {} - {}\n".format(resp_raw.status_code, error_resp))
            
            # Check for error fields in response
            if isinstance(error_resp, dict):
                if "Message" in error_resp:
                    return {"success": False, "error": error_resp}
                if "error" in error_resp:
                    return {"success": False, "error": error_resp.get("error")}

            return {"success": False, "error": f"Failed to update note: HTTP {resp_raw.status_code}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_control_config_note error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error updating control config note: {e}"}
    
@mcp.tool()
async def assit_fetch_rule_readme(name: str, ctx: Context | None = None) -> workflow_vo.RuleReadmeResponseVO:
    """
    Use this tool to get details about the rule to add in SQL query control config notes.

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

        output = await utils.make_GET_API_call_to_CCow(f"{constants.URL_FETCH_RULE_README}?name={name}", ctx=ctx)
        logger.debug("rule readme output: {}\n".format(output))
        
        if isinstance(output, str) or "error" in output:
            logger.error("rule readme error: {}\n".format(output))
            return workflow_vo.RuleReadmeResponseVO(error="Facing internal error")
        
        if not output.get("items") or len(output["items"]) == 0:
            logger.warning(f"No rule found with name: {name}")
            return workflow_vo.RuleReadmeResponseVO(ruleName=name, error=f"Rule '{name}' not available")
        
        rule_item = output["items"][0]
        rule_name = rule_item.get("name", name)
        readme_hash = rule_item.get("readme", "")
        
        if not readme_hash:
            logger.warning(f"No README hash found for rule: {name}")
            return workflow_vo.RuleReadmeResponseVO(ruleName=rule_name, error=f"README not available for rule: {name}")
        
        try:
            readme_response = await utils.make_GET_API_call_to_CCow(f"{constants.URL_FETCH_FILE_BY_HASH}/{readme_hash}", ctx=ctx)
            logger.debug(f"README fetch response for rule {rule_name}: {readme_response}")
            
            if isinstance(readme_response, str) or "error" in readme_response:
                logger.error(f"Failed to fetch README content for rule {name}: {readme_response}")
                return workflow_vo.RuleReadmeResponseVO(ruleName=rule_name, error=f"Failed to fetch README content for rule: {name}")
            
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
                    return workflow_vo.RuleReadmeResponseVO(ruleName=rule_name, error=f"README not available for rule: {name}")
            elif isinstance(readme_response, str):
                readme_text = readme_response
            
            if not readme_text:
                logger.warning(f"No README content found for rule: {name}")
                return workflow_vo.RuleReadmeResponseVO(ruleName=rule_name, error=f"README not available for rule: {name}")
            
            logger.debug(f"Successfully fetched README for rule: {rule_name}")
            return workflow_vo.RuleReadmeResponseVO(readmeText=readme_text, ruleName=rule_name)
            
        except Exception as fetch_error:
            logger.error(f"Failed to fetch README content for rule {name}: {fetch_error}")
            return workflow_vo.RuleReadmeResponseVO(ruleName=rule_name, error=f"Failed to fetch README content for rule: {name}")

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_rule_readme error: {}\n".format(e))
        return workflow_vo.RuleReadmeResponseVO(error="Facing internal error")

@mcp.tool()
async def assit_validate_sql_query(
    sqlQuery: str,
    referenceEvidences: list[dict],
    assessmentId: str,
    controlId: str,
    ctx: Context | None = None,
) -> dict:
    """
    Validate a SQL query against reference evidence data.
    
    This tool validates a SQL query by executing it against provided evidence data.
    The evidence data can be provided in two ways:
    1. Using evidence ID (id) - evidence CSV data will be fetched automatically
    2. Using file content - base64 encoded CSV or JSON file content
    
    ⚠️ IMPORTANT REQUIREMENTS
    - For each evidence in referenceEvidences, either `id` OR `file` must be provided (not both).
    - If using `file`, the content must be base64 encoded and type must be "csv" or "json".
    - The evidence name should match the table name used in the SQL query.
    
    Args:
        sqlQuery (str): The SQL query to validate (required).
        referenceEvidences (list[dict]): List of evidence objects, each containing:
            - name (str): Evidence config name (table name used in SQL query) (required). Pass only name filtered evidences
            - id (str, optional): runEvidenceId obtained from `get_evidence_sample_data` response
            - file (dict, optional): File object containing:
                - content (str): Base64 encoded file content (required if using file).
                - type (str): File type, either "csv" or "json" (required if using file).
            - Either `id` OR `file` must be provided for each evidence (not both).
        assessmentId (str): The assessment ID that contains the control config (required).
        controlId (str): Control ID (required).
    
    Returns:
        Dict with validation status and executed query data:
        - success (bool): Whether the request was successful
        - queryStatus (str): Query validation status - "success" or "fail"
        - data (list, optional): Executed query results (rows returned by the query execution)
        - error (str, optional): Error message if validation failed or request failed
    """
    try:
        logger.info("validate_sql_query: \n")
        
        logger.info(f"validate_sql_query: sqlQuery: {sqlQuery}\n referenceEvidences: {referenceEvidences}\n")
        
        if not sqlQuery or not str(sqlQuery).strip():
            logger.error("validate_sql_query error: sqlQuery is mandatory\n")
            return {"success": False, "error": "sqlQuery is mandatory"}

        if not assessmentId or not str(assessmentId).strip():
            logger.error("validate_sql_query error: assessmentId is mandatory\n")
            return {"success": False, "error": "assessmentId is mandatory"}
        
        if not controlId or not str(controlId).strip():
            logger.error("validate_sql_query error: controlId is mandatory\n")
            return {"success": False, "error": "controlId is mandatory"}

        # Validate and build reference evidences payload
        validated_evidences = []
        for idx, evidence in enumerate(referenceEvidences):
            if not isinstance(evidence, dict):
                logger.error(f"validate_sql_query error: referenceEvidences[{idx}] must be a dict\n")
                return {"success": False, "error": f"referenceEvidences[{idx}] must be a dict"}
            
            evidence_name = evidence.get("name")
            if not evidence_name or not str(evidence_name).strip():
                logger.error(f"validate_sql_query error: referenceEvidences[{idx}].name is mandatory\n")
                return {"success": False, "error": f"referenceEvidences[{idx}].name is mandatory"}
            
            evidence_id = evidence.get("id")
            evidence_file = evidence.get("file")
            
            # Validate that either id or file is provided, but not both
            if evidence_id and evidence_file:
                logger.error(f"validate_sql_query error: referenceEvidences[{idx}] cannot have both 'id' and 'file'\n")
                return {"success": False, "error": f"referenceEvidences[{idx}] cannot have both 'id' and 'file'. Provide either 'id' or 'file'."}
            
            if not evidence_id and not evidence_file:
                logger.error(f"validate_sql_query error: referenceEvidences[{idx}] must have either 'id' or 'file'\n")
                return {"success": False, "error": f"referenceEvidences[{idx}] must have either 'id' or 'file'"}
            
            evidence_payload = {
                "name": str(evidence_name).strip()
            }
            
            if evidence_id:
                # Fetch evidence CSV base64 bytes using filter-evidence-data API
                data_payload = {
                    "evidenceID": str(evidence_id).strip()
                }
                fetch_output = await utils.make_API_call_to_CCow(
                    data_payload,
                    constants.URL_FILTER_EVIDENCE_DATA,
                    ctx=ctx
                )
                logger.debug("validate_sql_query fetch_evidence_data output: {}\n".format(json.dumps(fetch_output) if isinstance(fetch_output, dict) else fetch_output))

                if isinstance(fetch_output, str) or (isinstance(fetch_output, dict) and "error" in fetch_output):
                    logger.error(f"validate_sql_query error fetching evidence data for ID '{evidence_id}': {fetch_output}\n")
                    return {"success": False, "error": f"Failed to fetch evidence data for ID '{evidence_id}'"}

                if isinstance(fetch_output, dict) and fetch_output.get("Message") == "CANNOT_FIND_THE_FILE":
                    return {"success": False, "error": f"No evidence data file found for ID '{evidence_id}'"}

                file_content = None
                if isinstance(fetch_output, dict):
                    file_content = fetch_output.get("FileContent") or fetch_output.get("fileBytes")

                if not file_content:
                    return {"success": False, "error": f"No evidence data file content available for ID '{evidence_id}'"}

                evidence_payload["file"] = {
                    "content": str(file_content).strip(),
                    "type": "csv"
                }
            elif evidence_file:
                if not isinstance(evidence_file, dict):
                    logger.error(f"validate_sql_query error: referenceEvidences[{idx}].file must be a dict\n")
                    return {"success": False, "error": f"referenceEvidences[{idx}].file must be a dict"}
                
                file_content = evidence_file.get("content")
                file_type = evidence_file.get("type")
                
                if not file_content or not str(file_content).strip():
                    logger.error(f"validate_sql_query error: referenceEvidences[{idx}].file.content is mandatory\n")
                    return {"success": False, "error": f"referenceEvidences[{idx}].file.content is mandatory"}
                
                clean_file_type = str(file_type).strip().lower() if file_type else ""
                if clean_file_type not in ["csv", "json"]:
                    logger.error(f"validate_sql_query error: referenceEvidences[{idx}].file.type must be 'csv' or 'json'\n")
                    return {"success": False, "error": f"referenceEvidences[{idx}].file.type must be 'csv' or 'json'"}

                evidence_payload["file"] = {
                    "content": str(file_content).strip(),
                    "type": clean_file_type
                }
            
            validated_evidences.append(evidence_payload)
        
        payload = {
            "sqlQuery": str(sqlQuery).strip(),
            "referenceEvidences": validated_evidences,
            "assessmentID": assessmentId,
            "assessmentControlID": controlId
        }
        
        logger.debug("validate_sql_query payload: {}\n".format(json.dumps(payload)))

        resp = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_CONTROLS_VALIDATE_SQL_QUERY,
            "POST",
            payload,
            ctx=ctx
        )
        
        logger.debug("validate_sql_query output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))
        
        # Handle error response
        if isinstance(resp, str):
            logger.error("validate_sql_query error: {}\n".format(resp))
            return {"success": False, "error": resp}
        
        if isinstance(resp, dict):
            # Check for error fields
            if "Message" in resp:
                logger.error("validate_sql_query error: {}\n".format(resp))
                return {"success": False, "error": resp}
            
            if "error" in resp:
                logger.error("validate_sql_query error: {}\n".format(resp.get("error")))
                return {"success": False, "error": resp.get("error")}
            

            data_block = resp.get("data")
            columns = data_block.get("columns") if isinstance(data_block, dict) else None

            if columns and isinstance(columns, list):
                if len(columns) != len(set(columns)):
                    return {
                        "success": False,
                        "error": "The column names are duplicated"
                    }

            result = {
                "success": True,
                "resp": resp
            }
            return result
        
        # Fallback: wrap unexpected response type
        logger.error("validate_sql_query error: Unexpected response type: {}\n".format(type(resp)))
        return {"success": False, "error": f"Unexpected response type: {resp}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("validate_sql_query error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error validating SQL query: {e}"}

# @mcp.tool()
async def assit_fetch_sql_query_feedback(
    control_name: str, 
    control_description: str, 
    control_context:str, 
    control_additional_context: dict[str, Any],
    evidence_details: list[dict],
    assessment_context: dict,
    sql_query: str,
    query_type: Literal["primary", "supporting"],
    ctx: Context | None = None):
    """
    Validate the filter query and summary query for the automated control.
    IMPORTANT: **This must include **all evidence sources linked to the control**.
    The evidence list must be fetched directly from the **source control summary**
    (not from input context or filtering logic).**

    Args:
        control_name (str):
            Name of the automated control.

        control_description (str):
            Detailed description of the control, used to understand the expected
            behavior of the queries.

        control_context (str):
            Primary contextual information for the control (use cases, scope,
            expected inputs, environment details, etc.).

        control_additional_context (dict):
            Additional supporting information not covered in control_context.

        evidence_details (list[dict]): 
            DO NOT use the input context to determine evidences.
            DO NOT infer evidences from filter_query, control context, or additional context.
            DO NOT limit or filter evidences by relevance.

            You MUST fetch **every evidence source linked to the control** directly from the
            "source control summary" (i.e., the output of fetch_control_source_summary).
            This includes:
                - directly linked evidences
                - indirectly linked evidences (nested lineage, recursion-level links)
                - ALL evidence sources, even if they appear unused or irrelevant

            The tool must treat the source control summary as the **single source of truth**
            for evidence discovery. Missing even one evidence source is considered an error.
            Each evidence item must follow this structure:
            {
                "name": "<evidence name>",
                "data": [
                    {   # exactly one evidence sample
                        <column>: <value>,
                        ...
                    }
                ]
            }
            Requirements:
                - "name" must match the evidence name exactly as provided in the source control summary.
                - "data" must contain exactly one sample row of column/value pairs from that evidence.
                - Include ALL evidences, even if:
                    • they appear unused in queries  
                    • they contain no useful columns  
                    • they are from nested/linked controls  
                    • they belong to deeper recursion levels  

                The validation relies on evidence_details as the **authoritative schema source**
                for query completeness and consistency checks.

        assessment_context (dict):
            Assessment-level metadata used to determine filtering levels and to
            validate whether the filter_query aligns with the correct entity scope.

        filter_query (str):
            SQL-like filter query generated for evidence extraction.

        summary_query (str):
            Query defining how evidence contributes to the control summary.
            
    Returns:
        dict:
            ```json
            {
                "completeness_score": float,
                "consistency_score": float,
                "correctness_score": float,
                "overall_score": float,
                "issues_found": str,
                "improvements": str,
                "usefulness": str,
                "final_validation": "valid" | "invalid"
            }
            ```
    """
    try:

        logger.info("validate_sql_query_context: \n")
        req_payload = {
            "control_name": control_name,
            "control_description": control_description,
            "control_context": control_context,
            "control_additional_context": control_additional_context,
            "evidence_details": evidence_details,
            "assessment_context": assessment_context,
        }

        if query_type == "primary":
            req_payload["summary_query"] = sql_query
        elif query_type == "supporting":
            req_payload["filter_query"] = sql_query
        logger.debug(f"req_payload ::: {req_payload}")
        resp = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_VALIDATE_AUTOMATE_CONTROL,
            "POST",
            req_payload,
            ctx=ctx
        )
        logger.debug("validate_sql_query_context: resp:\n%s", json.dumps(resp, indent=2))
        return resp
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("validate_sql_query error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error validating SQL query: {e}"}


@mcp.tool()
async def assit_mark_control_ready_for_execution(
    assessmentId: str,
    assessmentName: str,
    controlName: str,
    primaryEvidenceName: str,
    supportingEvidenceName: str,
    ctx: Context | None = None,
) -> dict:
    """
    Mark an automated control as ready for execution.

    This tool should be invoked only AFTER automation is complete (both supporting
    and primary SQL queries are approved and created).

    Args:
        assessmentId (str): Assessment (plan) ID containing the control (required).
        assessmentName (str): assessment name (required).
        controlName (str): Control name to be marked ready (required).
        primaryEvidenceName (str): Evidence config name for the primary query (required).
        supportingEvidenceName (str): Evidence config name for supporting query(required).

    Returns:
        Dict with success status and message:
            - success (bool): Whether the control was marked ready
            - message (str): Status message
            - response (dict, optional): Raw API response on success
            - error (str, optional): Error details on failure

    """
    try:
        logger.info("mark_control_ready_for_execution: \n")

        if not assessmentId or not str(assessmentId).strip():
            logger.error("mark_control_ready_for_execution error: assessmentId is mandatory\n")
            return {"success": False, "error": "assessmentId is mandatory"}

        if not assessmentName or not str(assessmentName).strip():
            logger.error("mark_control_ready_for_execution error: assessmentName is mandatory\n")
            return {"success": False, "error": "assessmentName is mandatory"}

        if not controlName or not str(controlName).strip():
            logger.error("mark_control_ready_for_execution error: controlName is mandatory\n")
            return {"success": False, "error": "controlName is mandatory"}

        if not primaryEvidenceName or not str(primaryEvidenceName).strip():
            logger.error("mark_control_ready_for_execution error: primaryEvidenceName is mandatory\n")
            return {"success": False, "error": "primaryEvidenceName is mandatory"}

        if not supportingEvidenceName or not str(supportingEvidenceName).strip():
            logger.error("mark_control_ready_for_execution error: supportingEvidenceName is mandatory\n")
            return {"success": False, "error": "supportingEvidenceName is mandatory"}

        payload = {
            "assessmentId": str(assessmentId).strip(),
            "assessmentName": str(assessmentName).strip(),
            "controlName": str(controlName).strip(),
            "primaryEvidenceName": str(primaryEvidenceName).strip(),
            "supportingEvidenceName": str(supportingEvidenceName).strip(),
        }

        logger.debug("mark_control_ready_for_execution payload: {}\n".format(json.dumps(payload)))

        resp = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_MARK_CONTROL_READY,
            "POST",
            payload,
            ctx=ctx
        )

        logger.debug("mark_control_ready_for_execution output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))

        if isinstance(resp, str):
            logger.error("mark_control_ready_for_execution error: {}\n".format(resp))
            return {"success": False, "error": resp}

        if isinstance(resp, dict):
            if "Message" in resp:
                logger.error("mark_control_ready_for_execution error: {}\n".format(resp))
                return {"success": False, "error": resp}

            if "error" in resp:
                logger.error("mark_control_ready_for_execution error: {}\n".format(resp.get("error")))
                return {"success": False, "error": resp.get("error")}

            logger.info("mark_control_ready_for_execution: Control marked ready for execution\n")
            return {
                "success": True,
                "message": "Control marked ready for execution",
                "response": resp
            }

        logger.error("mark_control_ready_for_execution error: Unexpected response type: {}\n".format(type(resp)))
        return {"success": False, "error": f"Unexpected response type: {resp}"}

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("mark_control_ready_for_execution error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error marking control ready: {e}"}
    

# @mcp.tool()
async def assit_get_context_tables(controlId: str, ctx: Context | None = None) -> dict:
    """
    Get flattened context tables for:
    1. Entity hierarchy
    2. Control additional context (by controlId)

    Returns both tables in TOON format

    Args:
        controlId (str): Control ID

    Returns:
        Dict with:
        - success (bool)
        - entity_hierarchy (dict)
        - entity_hierarchy_format (str) 
        - control_additional_context (dict)
        - control_additional_context_format (str)
        - error (str, optional)
    """
    try:
        logger.info("get_context_tables started\n")

        if not controlId or not str(controlId).strip():
            return {
                "success": False,
                "error": "controlId is mandatory"
            }

        control_id = str(controlId).strip()
        def flatten_context(data: dict) -> tuple[list[str], list[list[str]]]:
            rows = []
            columns = []

            def collect_classes(entities):
                for e in entities:
                    cls = e.get("class")
                    if cls and cls not in columns:
                        columns.append(cls)
                    collect_classes(e.get("entities", []))

            def walk(entities, current_row):
                for e in entities:
                    row = current_row.copy()
                    cls = e.get("class")
                    name = e.get("name")

                    if cls:
                        row[cls] = name

                    children = e.get("entities", [])
                    if children:
                        walk(children, row)
                    else:
                        rows.append(row)

            entities = data.get("entities", [])
            collect_classes(entities)

            empty_row = {c: "" for c in columns}
            walk(entities, empty_row)

            data_rows = [
                [row.get(col, "") for col in columns]
                for row in rows
            ]

            return columns, data_rows

        def is_empty(value: Any) -> bool:
            """Treat blank strings, nulls, and empty containers as empty cells."""
            if value is None:
                return True
            if isinstance(value, str):
                return value.strip() == ""
            if isinstance(value, (list, dict, tuple, set)):
                return len(value) == 0
            return False

        def filter_entities_dict(entities: dict, classname: str, names: list[str])->dict:
            """
            Filter an entities table by classname column values and remove empty columns.

            Args:
                entities: Dict with "headerRow" and "dataRows".
                classname: Header name of the column to filter.
                names: Iterable of accepted values in the classname column.

            Returns:
                Dict with filtered "headerRow" and "dataRows".
            """

            if not entities:
                return {"headerRow": [], "dataRows": []}
            
            headers = entities.get("headerRow", [])
            rows = entities.get("dataRows", [])

            if not headers or not rows:
                return {"headerRow": headers, "dataRows": []}
    
            names = set(names or [])

            if not names:
                return {"headerRow": headers, "dataRows": []}
            
            # Check classname existence
            if classname not in headers:
                return {"headerRow": headers, "dataRows": []}

            classname_index = headers.index(classname)

            selected_rows = [
                row
                for row in rows
                if len(row) > classname_index and row[classname_index] in names
            ]

            # No matching rows
            if not selected_rows:
                return {"headerRow": headers, "dataRows": []}

            non_empty_column_indexes = [
                index
                for index in range(len(headers))
                if any(index < len(row) and not is_empty(row[index]) for row in selected_rows)
            ]

            return {
                "headerRow": [headers[index] for index in non_empty_column_indexes],
                "dataRows": [
                    [
                        row[index] if index < len(row) else ""
                        for index in non_empty_column_indexes
                    ]
                    for row in selected_rows
                ],
            }
        
        logger.info("Fetching entity hierarchy\n")

        entity_hierarchy_resp = await utils.make_GET_API_call_to_CCow(
            constants.URL_GET_ENTITY_HIERARCHY,
            ctx=ctx
        )

        if (
            isinstance(entity_hierarchy_resp, str)
            or (isinstance(entity_hierarchy_resp, dict) and "error" in entity_hierarchy_resp)
            or (isinstance(entity_hierarchy_resp, dict) and "Message" in entity_hierarchy_resp)
        ):
            logger.error(f"Entity hierarchy fetch failed: {entity_hierarchy_resp}\n")
            return {
                "success": False,
                "error": "Failed to fetch entity hierarchy"
            }

        if isinstance(entity_hierarchy_resp, dict) and "entitiesTable" in entity_hierarchy_resp:
            entity_hierarchy_table = entity_hierarchy_resp.get("entitiesTable", {})
        else:
            headers, rows = flatten_context(entity_hierarchy_resp)
            entity_hierarchy_table = {
                "headerRow": headers,
                "dataRows": rows
            }

        logger.info(f"Fetching control by id={control_id}\n")

        query_params = (
            f"?fields=basic"
            f"&include_additional_context=true"
        )

        control_resp = await utils.make_GET_API_call_to_CCow(
            f"{constants.URL_PLAN_CONTROLS}/{control_id}{query_params}",
            ctx=ctx
        )

        if (
            isinstance(control_resp, str)
            or (isinstance(control_resp, dict) and "error" in control_resp)
        ):
            logger.error(f"Control fetch failed: {control_resp}\n")
            return {
                "success": False,
                "error": "Failed to fetch control"
            }

        if not control_resp:
            return {
                "success": False,
                "error": f"No control found for controlId={control_id}"
            }

        additional_context_raw = control_resp.get("additionalContext",{})
        
        if not additional_context_raw:
            return {
                "success": False,
                "error": f"No control additional context found for controlId={control_id}"
            }
        if isinstance(additional_context_raw, dict):
            headers, rows = flatten_context(additional_context_raw)
            control_additional_context_table = {
                "headerRow": headers,
                "dataRows": rows
            }
        else:
            control_additional_context_table = {
                "headerRow": [],
                "dataRows": []
            }

        logger.info(
            "get_context_tables completed successfully\n"
            f"entity_hierarchy:\n{entity_hierarchy_table}\n\n"
            f"control_additional_context:\n{control_additional_context_table}"
        )
        
        control_additional_context_class = (control_additional_context_table.get("headerRow", [None])[0])

        flattened_control_additional_context = [
            item
            for row in control_additional_context_table.get("dataRows", [])
            for item in row
        ]

        if not control_additional_context_class or not flattened_control_additional_context:
            return {
                "success": False,
                "error": f"Invalid control additional context found for controlId={control_id}"
            }

        entity_hierarchy_table = filter_entities_dict(entity_hierarchy_table,control_additional_context_class,flattened_control_additional_context)

        logger.info(
            "get_context_tables after entity_hierarchy filter\n"
            f"entity_hierarchy:\n{entity_hierarchy_table}\n\n"
            f"control_additional_context:\n{control_additional_context_table}"
        )

        try:
            entity_hierarchy_toon = encode(entity_hierarchy_table)
            entity_hierarchy_format = "toon"
        except Exception as enc_err:
            logger.warning(f"TOON encode failed for entity_hierarchy, falling back: {enc_err}")
            entity_hierarchy_toon = entity_hierarchy_table  # raw dict fallback
            entity_hierarchy_format = "json"

        try:
            control_additional_context_toon = encode(control_additional_context_table)
            control_additional_context_format = "toon"
        except Exception as enc_err:
            logger.warning(f"TOON encode failed for control_additional_context, falling back: {enc_err}")
            control_additional_context_toon = control_additional_context_table
            control_additional_context_format = "json"

        response = {
            "success": True,
            "entity_hierarchy": entity_hierarchy_toon,
            "entity_hierarchy_format": entity_hierarchy_format,
            "control_additional_context": control_additional_context_toon,
            "control_additional_context_format": control_additional_context_format,
        }

        response_string = json.dumps(response)

        logger.info(f"get_context_tables response Character count: {len(response_string)}" )

        return response

    except Exception as e:
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": f"Unexpected error fetching context tables: {e}"
        }

@mcp.tool()
async def assit_create_control_config(
    assessmentName: str,
    controlObjectiveName: str,
    controlObjectiveDescription: str,
    controlObjectiveCategory: str,
    entityClass: str,
    entities: list[str],
    controlContext: str | None = None,
    ctx: Context | None = None
) -> dict:
    """
    Create or update an assessment by adding a control config (control objective).

    Important:
    - Use only user-provided inputs and do not assume any values.

    Behavior:
    - If an assessment with the given `assessmentName` already exists, the control objective
      is added to the existing assessment.
    - If no assessment with the given `assessmentName` exists, a new assessment is created
      and the control objective is added to it.
    
    Args:
        assessmentName (str): Name of the assessment (required).
        controlObjectiveName (str): Control objective name (required).
        controlObjectiveDescription (str): Control objective description (required).
        controlObjectiveCategory (str): Parent control name that will be a first-level control (required).
        entityClass (str): Entity class name (required).
        entities (list[str]): List of entity names (required).
        controlContext (str, optional): Additional control context.

    Returns:
        Dict with:
        - success (bool)
        - data (dict, optional): API response
            - assessment id (str)
        - error (str, optional)
    """
    try:
        logger.info("create_control_config invoked\n")

        if not assessmentName or not assessmentName.strip():
            return {"success": False, "error": "assessmentName is mandatory"}

        if not controlObjectiveName or not controlObjectiveName.strip():
            return {"success": False, "error": "controlObjectiveName is mandatory"}

        if not controlObjectiveDescription or not controlObjectiveDescription.strip():
            return {"success": False, "error": "controlObjectiveDescription is mandatory"}
        
        if not controlObjectiveCategory or not controlObjectiveCategory.strip():
            return {"success": False, "error": "controlObjectiveCategory is mandatory"}

        if not entityClass or not entityClass.strip():
            return {"success": False, "error": "entityClass is mandatory"}

        if not isinstance(entities, list) or not entities:
            return {"success": False, "error": "entities must be a non-empty array of strings"}

        for e in entities:
            if not isinstance(e, str) or not e.strip():
                return {"success": False, "error": "Each entity must be a non-empty string"}


        entity_payload = [
            {
                "name": entity.strip(),
                "class": entityClass.strip()
            }
            for entity in entities
        ]

        payload = {
            "assessmentName": assessmentName.strip(),
            "controlObjectives": [
                {
                    "name": controlObjectiveName.strip(),
                    "description": controlObjectiveDescription.strip(),
                    "category": controlObjectiveCategory.strip(),
                    "context": controlContext.strip() if controlContext else "",
                    "additionalContext": {
                        "entities": entity_payload
                    }
                }
            ]
        }

        logger.debug("create_control_config payload:\n{}\n".format(json.dumps(payload, indent=2)))

        resp = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_ADD_CONTROL_OBJECTIVE,
            "POST",
            payload,
            ctx=ctx
        )

        logger.debug(
            "create_control_config response:\n{}\n".format(
                json.dumps(resp) if isinstance(resp, dict) else resp
            )
        )

        if isinstance(resp, str):
            logger.error(f"create_control_config error: {resp}\n")
            return {"success": False, "error": resp}

        if isinstance(resp, dict):
            if "id" not in resp:
                return {"success": False, "error": f"Unexpected response: {resp}"}
            result = {
                "assessment_id": resp.get("id")
            }
            logger.info(
                f"create_control_config: Successfully created custom control with ID: {result['assessment_id']}\n"
            )
            return {"success": True, "data": result}

        return {
            "success": False,
            "error": f"Unexpected response type: {type(resp)}"
        }

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_control_config error: {}\n".format(e))
        return {
            "success": False,
            "error": f"Unexpected error while adding custom control: {e}"
        }
    

@mcp.tool()
async def assit_update_control_config_contexts(
    controlConfigId: str,
    entityClass: str,
    entities: list[str],
    controlContext: str | None = None,
    ctx: Context | None = None
) -> dict:
    """
    Update both context and additionalContext (entities) of an existing control config (control objective).

    Args:
        controlConfigId (str): ID of the control config to update (required).
        entityClass (str): Entity class name (required).
        entities (list[str]): List of entity names (required).
        controlContext (str | None): New context value. If None/empty, context will be set to "".

    Returns:
        dict:
            - success (bool)
            - controlConfigId (str)
            - message (str)
            - error (str, optional)
    """
    try:
        logger.info("update_control_config_contexts invoked\n")

        if not controlConfigId or not controlConfigId.strip():
            return {"success": False, "error": "controlConfigId is mandatory"}


        if not entityClass or not entityClass.strip():
            return {"success": False, "error": "entityClass is mandatory"}

        if not isinstance(entities, list) or not entities:
            return {"success": False, "error": "entities must be a non-empty array of strings"}

        for e in entities:
            if not isinstance(e, str) or not e.strip():
                return {"success": False, "error": "Each entity must be a non-empty string"}


        controlConfigId = controlConfigId.strip()

        context_value = controlContext.strip() if isinstance(controlContext, str) else ""

        entity_payload = [
            {
                "name": entity.strip(),
                "class": entityClass.strip()
            }
            for entity in entities
        ]

        payload = [
            {
                "op": "replace",
                "path": "/context",
                "value": context_value
            },
            {
                "op": "replace",
                "path": "/additionalContext",
                "value": {
                    "entities": entity_payload
                }
            }
        ]

        logger.debug(
            "update_control_config_contexts payload:\n{}\n".format(
                json.dumps(payload, indent=2)
            )
        )

        resp_raw = await utils.make_API_call_to_CCow_and_get_response(
            f"{constants.URL_PLAN_CONTROLS}/{controlConfigId}",
            "PATCH",
            payload,
            return_raw=True,
            ctx=ctx
        )

        if resp_raw.status_code == 502:
            return {"success": False, "error": error_constants.ERROR_BAD_GATEWAY}

        if resp_raw.status_code == 204:
            logger.info(
                "update_control_config_contexts: Successfully updated context and additional context "
                f"with status {resp_raw.status_code}\n"
            )
            return {
                "success": True,
                "controlConfigId": controlConfigId,
                "message": "Control config context and additional context updated successfully"
            }

        # ---- Error handling ----
        error_resp = {}
        try:
            if resp_raw.content:
                error_resp = resp_raw.json()
        except Exception:
            error_resp = {"error": f"HTTP {resp_raw.status_code}"}

        logger.error(
            "update_control_config_contexts error: Status {} - {}\n".format(
                resp_raw.status_code, error_resp
            )
        )

        if isinstance(error_resp, dict):
            if "Message" in error_resp:
                return {"success": False, "error": error_resp}
            if "error" in error_resp:
                return {"success": False, "error": error_resp.get("error")}

        return {
            "success": False,
            "error": f"Failed to update control config contexts: HTTP {resp_raw.status_code}"
        }

    except Exception as e:
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": f"Unexpected error while updating control contexts: {e}"
        }


@mcp.tool(annotations=utils.tool_annotations("Create Filtered Evidence", read_only=False))
async def assit_create_filtered_evidence(
    assessmentId: str,
    controlId: str,
    evidenceNames: list[FilteredEvidenceInputVO],
    meaningfulName: str,
    ctx: Context | None = None
) -> dict:
    """
    Create a new rule for an assessment control to generate filtered evidence, publish it, and link it to the control.

    Args:
        assessmentId (str): ID of the assessment plan (required).
        controlId (str): ID of the plan control (required).
        evidenceNames (list[FilteredEvidenceInputVO]): List of evidence objects, each containing evidenceName and columnName (Column name in the evidence used for joining/filtering) (required).
        meaningfulName (str): Meaningful descriptive name for the rule (25-35 characters) (required).

    Returns:
        dict:
            - success (bool)
            - message (str)
            - filtered_evidences (list[str])
            - error (str, optional)
    """
    try:
        logger.info(f"create_filtered_evidence invoked: assessmentId={assessmentId}, controlId={controlId}, evidenceNames={evidenceNames}, meaningfulName={meaningfulName}\n")

        req_check = utils.require_fields(
            {"assessmentId": assessmentId, "controlId": controlId, "meaningfulName": meaningfulName},
            ["assessmentId", "controlId", "meaningfulName"]
        )
        if req_check:
            logger.error(f"create_filtered_evidence validation failed: {req_check}")
            return req_check

        if not evidenceNames or not isinstance(evidenceNames, list):
            return {"success": False, "error": "evidenceNames must be a non-empty list of evidence objects"}

        normalized_evidences = []
        for item in evidenceNames:
            ev = getattr(item, "evidenceName", None) or (item.get("evidenceName") if isinstance(item, dict) else "")
            col = getattr(item, "columnName", None) or (item.get("columnName") if isinstance(item, dict) else "")
            if not ev or not str(ev).strip() or not col or not str(col).strip():
                return {"success": False, "error": "Each evidence item must contain non-empty evidenceName and columnName"}
            normalized_evidences.append({"evidenceName": str(ev).strip(), "columnName": str(col).strip()})

        assessment_id = assessmentId.strip()
        control_id = controlId.strip()

        assessment_resp = await assistant_utils.get_assessment_details_api(assessment_id, ctx=ctx)
        logger.info(f"create_filtered_evidence step 1 (get_assessment_details_api) response:\n{json.dumps(assessment_resp, indent=2) if isinstance(assessment_resp, (dict, list)) else assessment_resp}")
        err = utils.handle_error_response(assessment_resp, "create_filtered_evidence:get_assessment_details")
        if err:
            return err

        plan_name = assessment_resp.get("name")
        plan_id = assessment_resp.get("id")
        if not plan_name:
            err = {"success": False, "error": f"Failed to retrieve assessment name for assessmentId: {assessment_id}"}
            logger.error(f"create_filtered_evidence step 1 failed: {err}")
            return err

        control_resp = await assistant_utils.get_control_details_api(control_id, ctx=ctx)
        logger.info(f"create_filtered_evidence step 2 (get_control_details_api) response:\n{json.dumps(control_resp, indent=2) if isinstance(control_resp, (dict, list)) else control_resp}")
        err = utils.handle_error_response(control_resp, "create_filtered_evidence:get_control_details")
        if err:
            return err

        displayable = control_resp.get("displayable") or control_resp.get("alias") or control_resp.get("name") or ""

        rule_payload = assistant_utils.construct_assistant_rule(
            evidence_names=normalized_evidences,
            plan_name=plan_name,
            plan_id=plan_id,
            plan_control_displayable=displayable,
            meaningful_name=meaningfulName.strip(),
        )

        rule_name = rule_payload.get("meta", {}).get("name")
        if not rule_name:
            err = {"success": False, "error": "Failed to construct rule name"}
            logger.error(f"create_filtered_evidence step 3 failed: {err}")
            return err

        yaml_payload = yaml.dump(rule_payload, sort_keys=False)
        logger.info(f"create_filtered_evidence step 3 (construct_assistant_rule) YAML payload:\n{yaml_payload}")

        create_resp = await assistant_utils.create_rule_api(yaml_payload, type="yaml", ctx=ctx)
        logger.info(f"create_filtered_evidence step 4 (create_rule_api) response:\n{json.dumps(create_resp, indent=2) if isinstance(create_resp, (dict, list)) else create_resp}")
        err = utils.handle_error_response(create_resp, "create_filtered_evidence:create_rule")
        if err:
            return err

        created_rule_name = create_resp.get("name") if isinstance(create_resp, dict) and create_resp.get("name") else rule_name

        publish_resp = await assistant_utils.publish_rule_api(created_rule_name, cc_rule_name=created_rule_name, ctx=ctx)
        logger.info(f"create_filtered_evidence step 5 (publish_rule_api) response:\n{json.dumps(publish_resp, indent=2) if isinstance(publish_resp, (dict, list)) else publish_resp}")
        err = utils.handle_error_response(publish_resp, "create_filtered_evidence:publish_rule")
        if err:
            return err

        rule_id = publish_resp.get("ruleId") if isinstance(publish_resp, dict) else None
        if not rule_id:
            err = {"success": False, "error": f"Rule published but ruleId not returned in response: {publish_resp}"}
            logger.error(f"create_filtered_evidence step 5 failed: {err}")
            return err

        link_resp = await assistant_utils.link_rule_to_control_api(control_id, rule_id, create_evidence=True, create_input=False, ctx=ctx)
        logger.info(f"create_filtered_evidence step 6 (link_rule_to_control_api) response:\n{json.dumps(link_resp, indent=2) if isinstance(link_resp, (dict, list)) else link_resp}")
        err = utils.handle_error_response(link_resp, "create_filtered_evidence:link_rule_to_control")
        if err:
            return err

        filtered_evidences = [f"{ev['evidenceName']}_filtered" for ev in normalized_evidences]
        result = {
            "success": True,
            "message": f"Rule '{created_rule_name}' created, published, and linked to control successfully",
            "filtered_evidences": filtered_evidences,
            "filtered_evidence": filtered_evidences,
        }
        logger.info(f"create_filtered_evidence final output:\n{json.dumps(result, indent=2)}")
        return result

    except Exception as e:
        logger.error(traceback.format_exc())
        err = {
            "success": False,
            "error": f"Unexpected error while creating assistant rule: {e}"
        }
        logger.error(f"create_filtered_evidence exception: {err}")
        return err


@mcp.tool(annotations=utils.tool_annotations("Update Filtered Evidence", read_only=False))
async def assit_update_filtered_evidence(
    assessmentId: str,
    controlId: str,
    evidenceNames: list[FilteredEvidenceInputVO],
    ctx: Context | None = None
) -> dict:
    """
    Update an existing rule for an assessment control to generate filtered evidence using its current rule name and publish it.

    Args:
        assessmentId (str): ID of the assessment plan (required).
        controlId (str): ID of the plan control (required).
        evidenceNames (list[FilteredEvidenceInputVO]): List of evidence objects, each containing evidenceName and columnName (Column name in the evidence used for joining/filtering) (required).

    Returns:
        dict:
            - success (bool)
            - message (str)
            - filtered_evidences (list[str])
            - error (str, optional)
    """
    try:
        logger.info(f"update_filtered_evidence invoked: assessmentId={assessmentId}, controlId={controlId}, evidenceNames={evidenceNames}\n")

        req_check = utils.require_fields(
            {"assessmentId": assessmentId, "controlId": controlId},
            ["assessmentId", "controlId"]
        )
        if req_check:
            logger.error(f"update_filtered_evidence validation failed: {req_check}")
            return req_check

        if not evidenceNames or not isinstance(evidenceNames, list):
            return {"success": False, "error": "evidenceNames must be a non-empty list of evidence objects"}

        normalized_evidences = []
        for item in evidenceNames:
            ev = getattr(item, "evidenceName", None) or (item.get("evidenceName") if isinstance(item, dict) else "")
            col = getattr(item, "columnName", None) or (item.get("columnName") if isinstance(item, dict) else "")
            if not ev or not str(ev).strip() or not col or not str(col).strip():
                return {"success": False, "error": "Each evidence item must contain non-empty evidenceName and columnName"}
            normalized_evidences.append({"evidenceName": str(ev).strip(), "columnName": str(col).strip()})

        assessment_id = assessmentId.strip()
        control_id = controlId.strip()

        # Step 1: Fetch Control Details & check rule & rule.name
        control_resp = await assistant_utils.get_control_details_api(control_id, ctx=ctx)
        logger.info(f"update_filtered_evidence step 1 (get_control_details_api) response:\n{json.dumps(control_resp, indent=2) if isinstance(control_resp, (dict, list)) else control_resp}")
        err = utils.handle_error_response(control_resp, "update_filtered_evidence:get_control_details")
        if err:
            return err

        rule_obj = control_resp.get("rule") if isinstance(control_resp, dict) else None
        rule_id = control_resp.get("ruleId") if isinstance(control_resp, dict) else None
        if not rule_obj or not isinstance(rule_obj, dict) or not rule_id:
            err = {
                "success": False,
                "error": f"Control '{control_id}' does not have a rule linked to it."
            }
            logger.error(f"update_filtered_evidence step 1 failed: {err}")
            return err

        rule_name = rule_obj.get("name")
        if not rule_name or not str(rule_name).strip():
            err = {
                "success": False,
                "error": f"Control '{control_id}' has a rule linked, but rule.name is missing or empty."
            }
            logger.error(f"update_filtered_evidence step 1 failed: {err}")
            return err

        rule_name = str(rule_name).strip()

        # Step 2: Fetch Assessment Details
        assessment_resp = await assistant_utils.get_assessment_details_api(assessment_id, ctx=ctx)
        logger.info(f"update_filtered_evidence step 2 (get_assessment_details_api) response:\n{json.dumps(assessment_resp, indent=2) if isinstance(assessment_resp, (dict, list)) else assessment_resp}")
        err = utils.handle_error_response(assessment_resp, "update_filtered_evidence:get_assessment_details")
        if err:
            return err

        plan_name = assessment_resp.get("name")
        plan_id = assessment_resp.get("id")
        if not plan_name:
            err = {"success": False, "error": f"Failed to retrieve assessment name for assessmentId: {assessment_id}"}
            logger.error(f"update_filtered_evidence step 2 failed: {err}")
            return err

        displayable = control_resp.get("displayable") or control_resp.get("alias") or control_resp.get("name") or ""

        # Step 3: Construct Rule Payload keeping existing rule_name
        rule_payload = assistant_utils.construct_assistant_rule(
            evidence_names=normalized_evidences,
            plan_name=plan_name,
            plan_id=plan_id,
            plan_control_displayable=displayable,
            rule_name=rule_name,
        )

        # Convert payload dict to YAML content string
        yaml_payload = yaml.dump(rule_payload, sort_keys=False)
        logger.info(f"update_filtered_evidence step 3 (construct_assistant_rule) YAML payload:\n{yaml_payload}")

        # Step 4: Create/Update Rule via API using existing rule_name (YAML content)
        create_resp = await assistant_utils.create_rule_api(yaml_payload, type="yaml", ctx=ctx)
        logger.info(f"update_filtered_evidence step 4 (create_rule_api) response:\n{json.dumps(create_resp, indent=2) if isinstance(create_resp, (dict, list)) else create_resp}")
        err = utils.handle_error_response(create_resp, "update_filtered_evidence:create_rule")
        if err:
            return err

        updated_rule_name = create_resp.get("name") if isinstance(create_resp, dict) and create_resp.get("name") else rule_name

        # Step 5: Publish Rule via API
        publish_resp = await assistant_utils.publish_rule_api(updated_rule_name, cc_rule_name=updated_rule_name, ctx=ctx)
        logger.info(f"update_filtered_evidence step 5 (publish_rule_api) response:\n{json.dumps(publish_resp, indent=2) if isinstance(publish_resp, (dict, list)) else publish_resp}")
        err = utils.handle_error_response(publish_resp, "update_filtered_evidence:publish_rule")
        if err:
            return err

        rule_id = publish_resp.get("ruleId") if isinstance(publish_resp, dict) else None
        if not rule_id:
            err = {"success": False, "error": f"Rule published but ruleId not returned in response: {publish_resp}"}
            logger.error(f"update_filtered_evidence step 5 failed: {err}")
            return err

        link_resp = await assistant_utils.link_rule_to_control_api(control_id, rule_id, create_evidence=True, create_input=False, ctx=ctx)
        logger.info(f"create_filtered_evidence step 6 (link_rule_to_control_api) response:\n{json.dumps(link_resp, indent=2) if isinstance(link_resp, (dict, list)) else link_resp}")
        err = utils.handle_error_response(link_resp, "update_filtered_evidence:link_rule_to_control")
        if err:
            return err

        filtered_evidences = [f"{ev['evidenceName']}_filtered" for ev in normalized_evidences]
        result = {
            "success": True,
            "message": f"Rule '{updated_rule_name}' updated and published successfully",
            "filtered_evidences": filtered_evidences,
            "filtered_evidence": filtered_evidences,
        }
        logger.info(f"update_filtered_evidence final output:\n{json.dumps(result, indent=2)}")
        return result

    except Exception as e:
        logger.error(traceback.format_exc())
        err = {
            "success": False,
            "error": f"Unexpected error while updating assistant rule: {e}"
        }
        return err


@mcp.tool(annotations=utils.tool_annotations("Get Sample Data for Filtered Evidences", read_only=False))
async def assit_get_sample_data_for_filtered_evidences(
    controlId: str,
    filteredEvidenceNames: list[str],
    originalEvidenceIds: list[str],
    ctx: Context | None = None
) -> dict:
    """
    Fetch sample evidence data for filtered evidences.

    Args:
        controlId (str): ID of the plan control (required).
        filteredEvidenceNames (list[str] | str): List of filtered evidence names (required).
        originalEvidenceIds (list[str] | str): List of original evidence IDs corresponding to the evidence names (Get from get_evidence_sample_data tool)(required).

    Returns:
        dict:
            - success (bool)
            - controlId (str)
            - results (dict): Mapping of filtered evidence name to sample data response.
            - error (str, optional)
    """
    try:
        logger.info(
            f"get_sample_data_for_filtered_evidences invoked: controlId={controlId}, "
            f"filteredEvidenceNames={filteredEvidenceNames}, originalEvidenceIds={originalEvidenceIds}, "
        )

        req_check = utils.require_fields(
            {"controlId": controlId},
            ["controlId"]
        )
        if req_check:
            logger.error(f"get_sample_data_for_filtered_evidences validation failed: {req_check}")
            return req_check

        if isinstance(filteredEvidenceNames, str):
            filteredEvidenceNames = [filteredEvidenceNames]

        if isinstance(originalEvidenceIds, str):
            originalEvidenceIds = [originalEvidenceIds]

        if not isinstance(filteredEvidenceNames, list) or not filteredEvidenceNames:
            err = {"success": False, "error": "filteredEvidenceNames must be a non-empty list of strings"}
            logger.error(f"get_sample_data_for_filtered_evidences validation failed: {err}")
            return err

        if not isinstance(originalEvidenceIds, list) or not originalEvidenceIds:
            err = {"success": False, "error": "originalEvidenceIds must be a non-empty list of strings"}
            logger.error(f"get_sample_data_for_filtered_evidences validation failed: {err}")
            return err

        if len(filteredEvidenceNames) != len(originalEvidenceIds):
            err = {
                "success": False,
                "error": (
                    f"Length mismatch: filteredEvidenceNames count ({len(filteredEvidenceNames)}) "
                    f"does not match originalEvidenceIds count ({len(originalEvidenceIds)})"
                )
            }
            logger.error(f"get_sample_data_for_filtered_evidences validation failed: {err}")
            return err

        sample_data_results = {}
        for ev_name, ev_id in zip(filteredEvidenceNames, originalEvidenceIds):
            ev_name_clean = str(ev_name).strip()
            ev_id_clean = str(ev_id).strip()

            logger.info(f"Fetching sample data for evidence '{ev_name_clean}' (evidenceId={ev_id_clean})...")
            payload = {"evidenceID": ev_id_clean}
            resp = await utils.make_API_call_to_CCow(
                payload,
                constants.URL_FILTER_EVIDENCE_DATA,
                ctx=ctx
            )

            records = []
            if isinstance(resp, dict):
                b64_file = resp.get("FileContent") or resp.get("fileBytes")
                if b64_file and isinstance(b64_file, str):
                    try:
                        decoded_csv = base64.b64decode(b64_file).decode('utf-8')
                        f_in = io.StringIO(decoded_csv)
                        reader = csv.DictReader(f_in)
                        for row in reader:
                            clean_row = {k: v for k, v in row.items() if k and not k.endswith("__") and k != "id"}
                            records.append(clean_row)
                            if len(records) == 3:
                                break
                    except Exception as parse_err:
                        logger.warning(f"Failed to parse CSV records: {parse_err}")
                sample_data_results[ev_name_clean] = {"items": records}
            else:
                sample_data_results[ev_name_clean] = {"error": str(resp)}

        result = {
            "success": True,
            "controlId": controlId.strip(),
            "results": sample_data_results,
        }
        logger.info(f"get_sample_data_for_filtered_evidences final output:\n{json.dumps(result, indent=2) if isinstance(result, dict) else result}")
        return result

    except Exception as e:
        logger.error(traceback.format_exc())
        err = {
            "success": False,
            "error": f"Unexpected error while fetching sample data: {e}"
        }
        logger.error(f"get_sample_data_for_filtered_evidences exception: {err}")
        return err



