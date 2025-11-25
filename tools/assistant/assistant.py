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
from mcptypes.graph_tool_types import UniqueNodeDataVO

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
    
    This function provides AI-powered suggestions for control citations based on control names or descriptions.
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
    
    This tool attach citation from an authority document to a control.
    The citation details should come from the get similar control config suggestions.
    Use control config existing or create new control config on assessment.
    
    🚨 CRITICAL: Assessment and control config MUST be user-selected and confirmed before execution.
    - If confirm=False, returns assessment and control IDs for user confirmation.
    - Only proceeds with attachment when confirm=True and user has explicitly confirmed.
    - NEVER assume or auto-select assessment or control - they must be user-selected.
    
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
                "next_step": "Review the assessment and control config ID above. If correct, re-run with confirm=True to attach the citation."
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
async def get_graph_schema_relationship() -> dict | str:
    """
    Important : Use this as an fallback tool for get-schema tool. if get-schema is incomplete, fails, or exceeds character limits or stored in file.
    Retrieve the complete graph database schema and relationship structure for ComplianceCow.

    Returns:
        dict: Complete database schema with structural patterns and query guidelines
        str: Error message if schema retrieval fails
    """
    
    try:
        logger.info("\nget_schema_form_control: \n")
        node_names = ["Assessment","AssessmentRun","Control","ControlConfig","Citation","Evidence","RiskItem","RiskItemAttribute","EvidenceConfig","EvidenceSchema"]
        output=await utils.make_API_call_to_CCow({"node_names":node_names},constants.URL_RETRIEVE_GRAPH_SCHEMA_RELATIONSHIP)
        return {
         "output": output,
         }
    except Exception as e:
        logger.error("get_schema_form_control error: {}\n".format(e))
        return "Facing internal error"

async def fetch_unique_node_data_and_schema(question: str) -> UniqueNodeDataVO:

    """
    Important : Use this as an fallback tool for get_graph_schema_relationship tool if enough data was not available on that

    Fetch unique node data and corresponding schema for a given question.

    Args:
        question (str): The user's input question.

    Returns:
        - node_names (List[str]): List of unique node names involved.
        - unique_property_values (list[any]): Unique property values per node.
        - neo4j_schema (str): The Neo4j schema associated with the nodes.
        - error (Optional[str]): Error message if any issues occurred during processing.
    """

    try:
        logger.info("\nget_unique_node_data_and_schema: \n")
        logger.debug("question: {}".format(question))

        output=await utils.make_API_call_to_CCow({"user_question":question},constants.URL_RETRIEVE_UNIQUE_NODE_DATA_AND_SCHEMA)
        logger.debug("output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_unique_node_data_and_schema error: {}\n".format(output))
            return UniqueNodeDataVO(error="Facing internal error")
        
        uniqueNodeDataVO = UniqueNodeDataVO(
            node_names=output["node_names"],
            unique_property_values=output["unique_property_values"],
            neo4j_schema=output["neo4j_schema"]
        )
        return uniqueNodeDataVO
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_unique_node_data_and_schema error: {}\n".format(e))
        return  UniqueNodeDataVO(error='Facing internal server error')

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
    
    This tool creates a SQL rule and associates it with a control and evidence configs.
    Important: The SQL query must always be shown to the user before calling this tool.
    
    🚨 Confirmation required: It will first return a preview showing the SQL query.
    The user can review the SQL query and optionally modify it before confirming. 
    Only after the user confirms (confirm=True) will the SQL rule be created and attached.
    The referedEvidenceNames are evidenceConfigNames which are used as table names in the SQL query.
    A new evidence config will be created with the newEvidenceName.
    Use graphdb to get the required details and evidence schema.
    
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
            
            # Extract rule ID and evidence config ID from response
            rule_id = resp.get("id")

            if rule_id:
                logger.info(f"create_sql_rule_and_attach: Successfully created SQL rule with ruleId: {rule_id}\n")
                return {
                    "success": True,
                    "ruleId": rule_id,
                    "message": "SQL rule and evidence config created successfully",
                }
        
        # Fallback: wrap unexpected response type
        logger.error("create_sql_rule_and_attach error: Unexpected response type: {}\n".format(type(resp)))
        return {"success": False, "error": f"Unexpected response type: {resp}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_sql_rule_and_attach error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error creating SQL rule: {e}"}

@mcp.tool()
async def fetch_control_source_summary(controlId: str) -> dict:
    """
    Fetch aggregated source summary for a control config, including linked control configs, evidences (including schema), and lineage depth.
    this is a fallback to gather SQL rule context for a control config.

    Primary flow: use graph schema + lineage to design SQL rules. When the graph lacks
    evidence metadata, use this tool with a control config ID.
    This will provide linked control configs, evidences (including schema), and lineage depth.
    Use this to gather SQL rule context for a control config.

    Args:
        controlId (str): Plan control ID provided by the user (mandatory).

    Returns:
        Dict containing:
            - success (bool): API invocation status.
            - data (dict, optional): Source summary (lineage, evidence, schema) on success.
            - error (str, optional): Validation or API error details.
    """
    try:
        logger.info("fetch_control_source_summary: \n")

        if not controlId or not str(controlId).strip():
            logger.error("fetch_control_source_summary error: controlId is mandatory\n")
            return {"success": False, "error": "controlId is mandatory"}

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
            return {"success": False, "error": resp}

        if isinstance(resp, dict):
            if "Message" in resp:
                logger.error("fetch_control_source_summary error: {}\n".format(resp))
                return {"success": False, "error": resp}

            return {"success": True, "data": resp, "next_action": "create sql rule"}

        logger.error(
            "fetch_control_source_summary error: Unexpected response type: {}\n".format(
                type(resp)
            )
        )
        return {"success": False, "error": f"Unexpected response type: {resp}", "next_action": "create sql rule and attach"}

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_control_source_summary error: {}\n".format(e))
        return {
            "success": False,
            "error": f"Unexpected error fetching control source summary: {e}",
        }


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