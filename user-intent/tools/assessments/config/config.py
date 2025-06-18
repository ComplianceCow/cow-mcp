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
async def list_all_assessment_categories() -> list | str:
    """
        Get all assessment categories
    """
    try:
        logger.info("get_all_assessment_categories: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.API_LIST_ASSESSMENT_CATEGORIES)
        # logger.debug("output: {}\n".format(output))

        if isinstance(output, str):
            return output

        categories=[]

        for item in output:
            if "name" in item:
                categories.append({"id":item["id"],"name":item["name"]})
        
        logger.debug("categories: {}\n".format(categories))

        return categories
    except Exception as e:
        logger.error("list_all_assessment_categories error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def list_assessments(payload : dict) -> list | str:
    """
        Get all assessments
        Function accepts category id as 'categoryId' and category name as 'categoryName'
    """
    try:
        logger.info("get_all_assessments: \n")
        logger.debug("payload: {}\n".format(payload))

        output=await utils.make_GET_API_call_to_CCow(constants.API_LIST_ASSESSMENTS)
        # logger.debug("output: {}\n".format(output))

        if isinstance(output, str):
            return output
        
        assessments=[]

        for item in output["items"]:
            if "name" in item and "categoryName" in item:
                assessments.append({"id":item["id"],"name":item["name"],"categoryName":item["categoryName"]})
        
        logger.debug("assessments: {}\n".format(assessments))

        return assessments
    except Exception as e:
        logger.error("list_assessments error: {}\n".format(e))
        return "Facing internal error"