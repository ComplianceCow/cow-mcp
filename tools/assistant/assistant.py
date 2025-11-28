import json
import traceback
import base64
import asyncio
from typing import List
from typing import Tuple


from utils import utils
from utils.debug import logger
from mcpconfig.config import mcp

from constants import constants
import yaml

from mcptypes import assessment_config_tool_types as assessment_vo
from mcptypes import workflow_tools_type as workflow_vo
from mcptypes.graph_tool_types import UniqueNodeDataVO
from mcptypes.assistant_tool_types import ControlSourceSummaryResponseVO, ControlSourceSummaryVO

@mcp.tool()
async def create_assessment(yaml_content: str) -> dict:
    """
    Create a new assessment from YAML definition.
    
    This function creates an assessment from a YAML specification that defines the hierarchical control structure.
    The YAML must contain metadata with name and categoryName. If the categoryName doesn't exist, a new category will be created.
    
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
            categories_resp = await utils.make_GET_API_call_to_CCow(constants.URL_ASSESSMENT_CATEGORIES, ctx)
            
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
                    it_name = it.get("name") or ""
                    if it_name and it_name.strip() == category_name:
                        category_id = it.get("id")
                        break
            
            # If category doesn't exist, create it
            if not category_id:
                logger.info(f"Category '{category_name}' not found, creating new category\n")
                create_category_payload = {"name": category_name}
                create_category_resp_raw = await utils.make_API_call_to_CCow_and_get_response(constants.URL_ASSESSMENT_CATEGORIES,"POST",create_category_payload,return_raw=True, ctx=ctx)
                create_category_resp = create_category_resp_raw.json()
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
            "fileContent": file_b64
        }
        payload["categoryId"] = category_id


        logger.debug("create_assessment payload: {}\n".format(json.dumps({**payload, "fileContent": "<base64-encoded>"})))
        
        resp_raw = await utils.make_API_call_to_CCow_and_get_response(constants.URL_ASSESSMENTS,"POST",payload,return_raw=True, ctx=ctx)
        resp = resp_raw.json()
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
async def suggest_control_config_citations(
    controlName: str,
    assessmentId: str,
    description: str = "",
    controlId: str = ""
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
        - items (List[dict]): List of suggestion items, each containing:
            - inputControlName (str): The input control name
            - controlId (str): The control ID (empty if control doesn't exist yet)
            - suggestions (List[dict]): List of suggested controls, each containing:
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
        resp = await utils.make_API_call_to_CCow(payload, constants.URL_GET_SIMILAR_CONTROLS)
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
async def list_assessments(
    categoryId: str = "",
    categoryName: str = "",
    assessmentName: str = ""
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
            - assessments (List[AssessmentVO]): A list of assessment objects, where each assessment includes:
                - id (str): Unique identifier of the assessment.
                - name (str): Name of the assessment.
                - category_name (str): Name of the category.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        logger.info("list_assessments: \n")
        
        output=await utils.make_GET_API_call_to_CCow(constants.URL_PLANS+"?fields=basic&category_id="+categoryId+"&category_name_contains="+categoryName+"&name_contains="+assessmentName)

        if isinstance(output, str) or "error" in output:
            logger.error("list_assessments error: {}\n".format(output))
            return assessment_vo.AssessmentListVO(error="Facing internal error")
        
        assessments: List[assessment_vo.AssessmentVO] = []
        
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
                        category_name=item.get("categoryName")
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
async def list_assessment_control_configs(
    assessmentId: str
) -> dict:
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
            
            output = await utils.make_GET_API_call_to_CCow(constants.URL_PLAN_CONTROLS + query_params)
            
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
                            "alias": item.get("alias", ""),
                            "controlNumber": item.get("displayable", ""),
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


@mcp.tool()
async def create_control_config(
    assessmentId: str,
    name: str,
    alias: str = "",
    controlNumber: str = "",
    description: str = ""
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
        resp_raw = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_CONTROLS,
            "POST",
            payload,
            return_raw=True
        )
        
        resp = resp_raw.json()
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
async def attach_citation_to_control_config(
    assessmentId: str,
    controlId: str,
    authorityDocument: str,
    controlIdsInAuthorityDocument: List[str],
    sortId: str,
    controlNames: List[str],
    confirm: bool = False
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
        controlIdsInAuthorityDocument (List[str]): List of control IDs from the authority document (e.g., ["10014"]).
        sortId (str): Sort ID from the suggestion (e.g., "010 014").
        controlNames (List[str]): List of control names from the suggestion (e.g., ["Multifactor Authentication"]).
        confirm (bool, optional): If False, shows preview with assessment and control IDs for confirmation.
                                  If True, proceeds with attachment. Defaults to False.
    
    Returns:
        Dict with success status and citation data:
        - success (bool): Whether the request was successful
        - citations (List[dict], optional): List of attached citation objects (only when confirm=True), each containing:
            - id (str): Citation ID
            - planControlID (str): Plan control ID
            - authorityDocument (str): Authority document name
            - controlNames (List[str]): Control names
            - controlsInAuthorityDocument (List[str]): Control IDs in authority document
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
            payload
        )
        logger.debug("attach_citation_to_control_config output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))
        
        # Handle error response
        if isinstance(resp, str):
            logger.error("attach_citation_to_control_config error: {}\n".format(resp))
            return {"success": False, "error": resp}
        
        if isinstance(resp, dict):
            # Check for error fields
            if "Message" in resp:
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
                    return_raw=False
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
async def create_sql_rule_and_attach(
    controlConfigId: str,
    sqlrule: str,
    referedEvidenceNames: List[str],
    newEvidenceName: str,
    confirm: bool = False,
) -> dict:
    """
    Create a SQL rule with control and evidence mappings.
    
    This tool creates a SQL-based rule and associates it with a specified control configuration.

    ⚠️ IMPORTANT WORKFLOW (Two-Step Confirmation)
    1. The SQL query MUST always be shown to the user in PREVIEW mode before execution.
    2. The user can review, edit, or approve the SQL query.
    3. Only after explicit confirmation (confirm=True) will the SQL rule be created and attached.
    
    🔍 EVIDENCE & TABLE MAPPING
    - The `referedEvidenceNames` represent existing evidenceConfigNames.
    - These names MUST be used as table names inside the SQL query.
    - A new evidence config will be created using `newEvidenceName` to store the output of the SQL rule.

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
        controlConfigId (str): The control config ID where the rule is to be attached (required).
        sqlrule (str): The SQL query/rule definition (required). The query should reference evidenceConfigNames as table names.
                      When confirm=False, this will be displayed in the preview. When confirm=True, the SQL rule will be created and attached.
        referedEvidenceNames (List[str]): List of evidenceConfigNames that are referenced as table names in the SQL query (required, non-empty).
        newEvidenceName (str): Name of the new evidence config to be created (required).
        confirm (bool, optional): If False, returns preview with the SQL query displayed for review (and optional modification).
                                 If True, proceeds with SQL rule creation using the provided sqlrule.

    Returns:
        Dict with success status and rule data:
        - success (bool): Whether the request was successful
        - ruleId (str, optional): Created rule ID
        - message (str, optional): Success or error message
        - sqlrule (str, optional): The SQL query shown in preview (when confirm=False)
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("create_sql_rule_and_attach: \n")
        
        if not controlConfigId or not str(controlConfigId).strip():
            logger.error("create_sql_rule_and_attach error: controlConfigId is mandatory\n")
            return {"success": False, "error": "controlConfigId is mandatory"}
        
        if not sqlrule or not str(sqlrule).strip():
            logger.error("create_sql_rule_and_attach error: sqlrule is mandatory\n")
            return {"success": False, "error": "sqlrule is mandatory"}
        
        if not referedEvidenceNames or not isinstance(referedEvidenceNames, list) or len(referedEvidenceNames) == 0:
            logger.error("create_sql_rule_and_attach error: referedEvidenceNames must be a non-empty list\n")
            return {"success": False, "error": "referedEvidenceNames must be a non-empty list"}
        
        if not newEvidenceName or not str(newEvidenceName).strip():
            logger.error("create_sql_rule_and_attach error: newEvidenceName is mandatory\n")
            return {"success": False, "error": "newEvidenceName is mandatory"}
        
        # Build payload according to API specification
        payload = {
            "sqlQuery": str(sqlrule).strip(),
            "evidenceName": str(newEvidenceName).strip(),
            "referedEvidenceNames": [str(name).strip() for name in referedEvidenceNames if name and str(name).strip()]
        }

        if not confirm:
            logger.info("create_sql_rule_and_attach: Returning confirmation preview\n")
            return {
                "success": True,
                "message": "Confirmation required before creating SQL rule",
                "controlConfigId": str(controlConfigId).strip(),
                "sqlQuery": payload["sqlQuery"],
                "newEvidenceName": payload["evidenceName"],
                "referedEvidenceNames": payload["referedEvidenceNames"],
                "next_step": "Review the SQL rule above. If you need to modify it, provide the updated sqlrule parameter when calling with confirm=True. If correct, re-run with confirm=True to create and attach the rule."
            }
        
        # Construct URL: /v1/plan-controls/{controlConfigId}/create-sql-rule-evidence
        url = f"{constants.URL_PLAN_CONTROLS}/{str(controlConfigId).strip()}/create-sql-rule-evidence"
        
        logger.debug("create_sql_rule_and_attach payload: {}\n".format(json.dumps(payload)))
        logger.debug("create_sql_rule_and_attach URL: {}\n".format(url))
        
        # Make API call
        resp_raw = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "POST",
            payload,
            return_raw=True
        )
        
        resp = resp_raw.json()
        logger.debug("create_sql_rule_and_attach output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))
        
        # Handle error response
        if isinstance(resp, str):
            logger.error("create_sql_rule_and_attach error: {}\n".format(resp))
            return {"success": False, "error": resp}
        
        if isinstance(resp, dict):
            # Check for error fields
            if "Message" in resp:
                logger.error("create_sql_rule_and_attach error: {}\n".format(resp))
                return {"success": False, "error": resp}
            
            if "error" in resp:
                logger.error("create_sql_rule_and_attach error: {}\n".format(resp.get("error")))
                return {"success": False, "error": resp.get("error")}

            rule_id = resp.get("ruleId")
            evidence_id = resp.get("evidenceId")

            if rule_id:
                logger.info(f"create_sql_rule_and_attach: Successfully created SQL rule with ruleId: {rule_id}\n")
                return {
                    "success": True,
                    "ruleId": rule_id,
                    "evidenceId": evidence_id,
                    "message": "SQL rule and evidence config created successfully",
                    "next_step": "Would you like to add documentation notes for this SQL rule on the control? This is optional but recommended for traceability."
                }
        
        # Fallback: wrap unexpected response type
        logger.error("create_sql_rule_and_attach error: Unexpected response type: {}\n".format(type(resp)))
        return {"success": False, "error": f"Unexpected response type: {resp}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_sql_rule_and_attach error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error creating SQL rule: {e}"}

@mcp.tool()
async def fetch_control_source_summary(controlId: str) -> ControlSourceSummaryResponseVO:
    """
    Fetch aggregated source summary for a control config, including linked control configs, evidences (including schema), and lineage depth.
    This tool is the PRIMARY way to gather SQL rule context for a control config.

    It returns how a control is connected to evidence configurations and what evidence
    structures (schemas) are available.

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

        resp_raw = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_CONTROLS_FETCH_SOURCE_SUMMARY,
            "POST",
            payload,
            return_raw=True,
        )

        resp = resp_raw.json()
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
                    response.next_action="STOP_SQL_RULE_GENERATION_NO_EVIDENCE_CONFIGS_CITATION_ATTACHED"
                    response.next_step = (
                        "No evidence configurations are linked to this control. "
                        "Since a citation is already attached, SQL rule automation cannot proceed. "
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
            next_action="create sql rule and attach"
        )

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_control_source_summary error: {}\n".format(e))
        return ControlSourceSummaryResponseVO(
            success=False,
            error=f"Unexpected error fetching control source summary: {e}",
        )

@mcp.tool()
async def get_evidence_sample_data(controlConfigId: str, evidenceNames: List[str] | None = None, records: int = 3) -> dict:
    """
    Fetch concrete evidence samples for a control config.

    Usage guidance:
    1. Run `fetch_control_source_summary` first to understand schema/lineage.
    2. Call this tool before drafting SQL rules to inspect real evidence rows.
    3. Pass 1-10 records to keep payloads lightweight (defaults to 3).

    Args:
        controlConfigId (str): Control config ID where the SQL rule will be attached (required).
        evidenceNames (List[str], optional): Specific evidence config names (table names) to sample.
            If omitted/empty, all evidences linked to the control are sampled.
        records (int, optional): Number of records per evidence (1-10, default 3).

    Returns:
        Dict containing:
            - success (bool): API invocation status.
            - controlId (str): Echoed control ID.
            - recordCount (int): Number of rows requested (after validation).
            - evidences (List[dict]): Evidence samples grouped by control/evidence. If an evidence
              is missing from the response, no records exist for it in the latest run.
            - next_action (str): Recommended next step (typically "create sql rule").
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

        resp_raw = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_CONTROLS_FETCH_SAMPLE_EVIDENCE_DATA,
            "POST",
            payload,
            return_raw=True
        )

        resp = resp_raw.json()
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
                response["next_action"]="create sql rule"
            else:
                response["next_action"] = "CREATE_SQL_RULE_FROM_SCHEMA_OR_REQUEST_USER_SAMPLES"
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

@mcp.tool()
async def get_assessment_context() -> dict:
    """
    Use this tool when the user wants to automate control operations,
    or before creating an SQL rule.
    
    This tool retrieves assessment context information from ServiceNow entities endpoint.
    Returns:
        Dict with success status and context data:
        - success (bool): Whether the request was successful
        - data (dict, optional): Assessment context data containing ServiceNow entities
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("get_assessment_context: \n")
        
        # Make GET API call to ServiceNow entities endpoint
        output = await utils.make_GET_API_call_to_CCow(constants.URL_GET_ASSESSMENT_CONTEXT)
        
        # Handle error response
        if isinstance(output, str) or (isinstance(output, dict) and "error" in output):
            logger.error("get_assessment_context error: {}\n".format(output))
            return {"success": False, "error": "Failed to fetch assessment context"}
        
        # Check for error fields in response
        if isinstance(output, dict):
            if "Message" in output:
                logger.error("get_assessment_context error: {}\n".format(output))
                return {"success": False, "error": output}
            
            logger.info(f"get_assessment_context: Successfully retrieved assessment context\n")
            return {"success": True, "data": output}
        
        # Fallback: wrap unexpected response type
        logger.error("get_assessment_context error: Unexpected response type: {}\n".format(type(output)))
        return {"success": False, "error": f"Unexpected response type: {output}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_assessment_context error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error fetching assessment context: {e}"}

@mcp.tool()
async def create_control_config_note(
    controlConfigId: str,
    assessmentId: str,
    notes: str,
    topic: str = "SQL Rule Documentation",
    confirm: bool = False,
) -> dict:
    """
    Create a documentation note on a control configuration to record SQL rule logic, evidence generation strategy, and implementation context.
    
    ✅ PURPOSE
    This tool is used AFTER a SQL rule has been successfully created and attached
    to a control config (via `create_sql_rule_and_attach`).
    
    It provides long-term traceability by documenting:
    - How the SQL query was generated
    - Which evidence sources were referenced
    - Why specific filters, joins, and aggregations were chosen
    - How the generated evidence supports the control objective

    ✅ OPTIONAL & USER-DRIVEN
    This tool is OPTIONAL and should be offered only if the user chooses
    to add documentation after SQL rule creation.
    
    ✅ CONFIRMATION-BASED SAFETY FLOW
    - When confirm=False:
        → The tool returns a PREVIEW of the generated markdown note.
        → The user may edit the note before confirming.
    - When confirm=True:
        → The note is permanently created and attached to the control config.

    ✅ EVIDENCE TRACEABILITY ENHANCEMENT
    If a rule name is provided and README documentation is available:
    - The system should retrieve the README
    - Extract how the evidence is generated
    - Embed that explanation inside the note automatically

    
    Args:
        controlConfigId (str): The control config ID where the note will be attached (required).
                              This is the same control config ID used in `create_sql_rule_and_attach`.
        assessmentId (str): The assessment ID that contains the control config (required).
        notes (str): The documentation content in MARKDOWN format. (Required)
                    Must include:
                    - SQL logic explanation
                    - Evidence source mapping
                    - Rule intent and compliance purpose
                    Recommended Template:
                        # Control {CONTROL_NUMBER} - {CONTROL_NAME} SQL Automation Documentation
                        ## Overview
                        Automation for assessment {ASSESSMENT_NAME} ensuring {CONTROL_OBJECTIVE} aligned to {FRAMEWORK_NAME} {FRAMEWORK_CONTROL}.

                        ## Assessment Context
                        Assessment ID: {ASSESSMENT_ID}
                        Control ID: {CONTROL_ID}
                        Assets: {ASSET_LIST}

                        ## Evidence Sources
                        1. {EVIDENCE_TABLE_1} - {EVIDENCE_1_PURPOSE}
                        2. {EVIDENCE_TABLE_2} - {EVIDENCE_2_PURPOSE}

                        ## Query 1: {QUERY_1_NAME}
                        Purpose: {QUERY_1_PURPOSE}
                        Logic: Filters control assets + normalizes evidence.

                        ## Query 2: {QUERY_2_NAME}
                        Purpose: {QUERY_2_PURPOSE}
                        Logic: Aggregates metrics + determines compliance.

                        ## Outputs
                        - {OUTPUT_1_NAME}: Operational evidence  
                        - {OUTPUT_2_NAME}: Compliance summary

        topic (str, optional): Topic or subject of the note. Defaults to "SQL Rule Documentation".
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
            "topic": str(topic).strip() if topic else "SQL Rule Documentation",
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
            return_raw=True
        )
        
        if resp_raw.status_code == 201:
            
            logger.info(f"create_control_config_note: Successfully created note with status 201\n")
            return {
                "success": True,
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
async def fetch_rule_readme(name: str) -> workflow_vo.RuleReadmeResponseVO:
    """
    Use this tool to get details about the rule to add in SQL rule control config notes.

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

        output = await utils.make_GET_API_call_to_CCow(f"{constants.URL_FETCH_RULE_README}?name={name}")
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
            readme_response = await utils.make_GET_API_call_to_CCow(f"{constants.URL_FETCH_FILE_BY_HASH}/{readme_hash}")
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
