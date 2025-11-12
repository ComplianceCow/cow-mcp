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
from mcptypes import workflow_tools_type as vo
import yaml


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
            categories_resp = await utils.make_GET_API_call_to_CCow(constants.URL_ASSESSMENT_CATEGORIES)
            
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
                create_category_resp_raw = await utils.make_API_call_to_CCow_and_get_response(constants.URL_ASSESSMENT_CATEGORIES,"POST",create_category_payload,return_raw=True)
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
        
        resp_raw = await utils.make_API_call_to_CCow_and_get_response(constants.URL_ASSESSMENTS,"POST",payload,return_raw=True)
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


 
