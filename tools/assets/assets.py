import json
import traceback
import base64
import asyncio
from typing import List
from typing import Tuple


from utils import utils
from utils.debug import logger
from tools.mcpconfig import mcp

from constants import constants

@mcp.tool()
async def list_assets() -> list:
    """
        Get all assets
    """
    try:
        logger.info("get_assets_list: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_ASSETS)
        # logger.debug("output: {}\n".format(output))

        categories=[]
        for item in output["items"]:
            if "name" in item:
                categories.append({"id":item["id"],"name":item["name"]})
        
        logger.debug("assets: {}\n".format(categories))

        return categories
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_assets error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_assets_summary(id: str) -> dict:
    """
        Get assets summary for given assessment id

        Args:
        id: assessment id
    """
    try:
        logger.info("fetch_assets_summary: \n")
        output=await utils.make_API_call_to_CCow({
            "planID": id,
        },constants.URL_FETCH_ASSETS_SUMMARY)
        logger.debug("output: {}\n".format(json.dumps(output)))

        output["integrationRunID"]=output["planRunID"]
        del output['planRunID']

        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_assets_summary error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_resource_types(id: str, page: int=1, pageSize: int=0) -> dict:
    """
        Get resource types for given asset run id.
        Use 'fetch_assets_summary' tool to get assets run id
        Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize.
        If the request times out retry with pagination, increasing pageSize from 50 to 100.

        1. Call fetch_resource_types with page=1, pageSize=50
        2. Note the totalPages from the response
        3. Continue calling each page until complete
        4. Summarize all results together

        Args:
        id: asset run id
    """

    try:
        logger.info("fetch_resource_types: \n")
        logger.debug("page: {}".format(page))
        logger.debug("pageSize: {}".format(pageSize))
        if page==0 and pageSize==0:
            return "use pagination"
        elif page==0 and pageSize>0:
            page=1
        elif page>0  and pageSize==0:
            pageSize=10
        elif pageSize>50:
            return "max page size is 50"
        output=await utils.make_API_call_to_CCow({
            "planRunID": id,
            "page": page,
            "pageSize": pageSize
        },constants.URL_FETCH_RESOURCE_TYPES)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str):
            return output
        for item in output["items"]:
            if "complianceStatus" in item:
                del item['complianceStatus']

        logger.debug("modified output: {}\n".format(json.dumps(output)))
        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_resource_types error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_checks(id: str, resourceType: str, page: int=1, pageSize: int=0, complianceStatus: str="") -> dict | str:
    """
        Get checks for given assets run id and resource type. Use this function to get all checks for given assets run id and resource type
        Use 'fetch_assets_summary' tool to get asset run id
        Use 'fetch_resource_types' tool to get all resource types
        Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize.
        If the request times out retry with pagination, increasing pageSize from 5 to 10.

        If the check data set is large to fetch efficiently or results in timeouts, 
        it is recommended to use the 'summary tool' instead to get a summarized view of the checks.
        
        1. Call fetch_checks with page=1, pageSize=10
        2. Note the totalPages from the response
        3. Continue calling each page until complete
        4. Summarize all results together

        Args:
        id: asset run id
        resourceType: resource type
        complianceStatus
    """
    try:
        logger.info("fetch_checks: \n")
        logger.debug("id: {}".format(id))
        logger.debug("resourceType: {}".format(resourceType))
        logger.debug("page: {}".format(page))
        logger.debug("pageSize: {}".format(pageSize))
        if page==0 and pageSize==0:
            return "use pagination"
        elif page==0 and pageSize>0:
            page=1
        elif page>0  and pageSize==0:
            pageSize=10
        elif pageSize>10:
            return "max page size is 10"

        output=await utils.make_API_call_to_CCow({
            "planRunID": id,
            "resourceType": resourceType,
            "page": page,
            "pageSize": pageSize,
            "complianceStatus": complianceStatus
        },constants.URL_FETCH_CHECKS)
        logger.debug("output: {}\n".format(json.dumps(output)))
        for item in output["items"]:
            if "controlName" in item:
                del item['controlName']

        output = utils.formatChecks(output)

        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_checks error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_resources(id: str, resourceType: str, page: int=1, pageSize: int=0, complianceStatus: str="") -> dict | str:
    """
        Get resources for given asset run id and resource type
        Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize, default page is 1
        If the request times out retry with pagination, increasing pageSize from 5 to 10.

        If the resource data set is large to fetch efficiently or results in timeouts, 
        it is recommended to use the 'summary tool' instead to get a summarized view of the resource.
    
        1. Call fetch_resources with page=1, pageSize=10
        2. Note the totalPages from the response
        3. Continue calling each page until complete
        4. Summarize all results together
   
        Args:
        id: asset run id
        resourceType: resource type
        complianceStatus
    """
    try:
        logger.info("fetch_resources: \n")
        logger.debug("id: {}".format(id))
        logger.debug("resourceType: {}".format(resourceType))
        logger.debug("page: {}".format(page))
        logger.debug("pageSize: {}".format(pageSize))
        if page==0 and pageSize==0:
            return "use pagination"
        elif page==0 and pageSize>0:
            page=1
        elif page>0  and pageSize==0:
            pageSize=10
        elif pageSize>10:
            return "max page size is 10"
        output=await utils.make_API_call_to_CCow({
            "planRunID": id,
            "resourceType": resourceType,
            "page": page,
            "pageSize": pageSize,
            "complianceStatus": complianceStatus
        },constants.URL_FETCH_RESOURCES)
        logger.debug("output: {}\n".format(json.dumps(output)))

        output=utils.formatResources(output,True)

        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_resources error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_resources_with_this_check(id: str, resourceType: str, check: str, page: int=1, pageSize: int=0) -> dict | str:
    """
        Get checks for given asset run id, resource type and check
        Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize.
        If the request times out retry with pagination, increasing pageSize from 10 to 50.

        If the resource data set is large to fetch efficiently or results in timeouts, 
        it is recommended to use the 'summary tool' instead to get a summarized view of the resource.
        
        1. Call fetch_resources_for_check with page=1, pageSize=10
        2. Note the totalPages from the response
        3. Continue calling each page until complete
        4. Summarize all results together

        Args:
        id: asset run id
        resourceType: resource type
    """
    try:
        logger.info("fetch_resources: \n")
        logger.debug("id: {}".format(id))
        logger.debug("resourceType: {}".format(resourceType))
        logger.debug("check: {}".format(check))

        if page==0 and pageSize==0:
            return "use pagination"
        elif page==0 and pageSize>0:
            page=1
        elif page>0  and pageSize==0:
            pageSize=10
        elif pageSize>10:
            return "max page size is 10"
        output=await utils.make_API_call_to_CCow({
            "planRunID": id,
            "resourceType": resourceType,
            "checkName": check,
            "page": page,
            "pageSize": pageSize
        },constants.URL_FETCH_RESOURCES)
        logger.debug("output: {}\n".format(json.dumps(output)))
        if isinstance(output, str):
            return output
        for item in output["items"]:
            if "checks" in item:
                del item['checks']
            if "assessmentControlId" in item:
                del item['assessmentControlId']
            if "assessmentRunControlId" in item:
                del item['assessmentRunControlId']

        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_resources_for_check error: {}\n".format(e))
        return "Facing internal error"
    

# @mcp.tool()
async def fetch_resource_types_summary(id: str) -> dict:
    """
        Use this to get the summary on resource types
        Use this when total items in 'fetch_resource_types' is high
        Get resource types summary for given asset run id.
        Use 'fetch_assets_summary' tool to get asset run id
        Paginated data is enough for summary
        Get a summarized view of resource types including: 
            - totalResourceTypes
            - totalResources

        Args:
        id: asset run id
    """

    try:
        logger.info("fetch_resource_types_summary:\n")

        responses = await asyncio.gather(
            utils.make_API_call_to_CCow({
                "planRunID": id,
                "page": 1,
                "pageSize": 10
            }, constants.URL_FETCH_RESOURCE_TYPES),
            utils.make_API_call_to_CCow({
                "planRunID": id,
                "page": 2,
                "pageSize": 10
            }, constants.URL_FETCH_RESOURCE_TYPES),
            utils.make_API_call_to_CCow({
                "planRunID": id,
                "page": 3,
                "pageSize": 10
            }, constants.URL_FETCH_RESOURCE_TYPES)
        )

        all_items = []
        total_items = None

        for output in responses:
            if isinstance(output, str):
                return output
            if total_items is None:
                total_items = output.get("totalItems")
            for item in output.get("items", []):
                if "complianceStatus" in item:
                    del item["complianceStatus"]
                all_items.append(item)

        final_output = {"items": all_items, "totalItems": total_items}
        logger.debug("modified output: {}\n".format(json.dumps(final_output)))
        return final_output

    except Exception as e:
        logger.error("fetch_resource_types_summary error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_checks_summary(id: str, resourceType: str) -> dict | str:
    """
        Use this to get the summary on checks
        Use this when total items in 'fetch_checks' is high
        Get checks summary for given asset run id and resource type.
        Get a summarized view of resources based on
            - Compliance breakdown for checks
                - Total Checks available
                - Total compliant checks
                - Total non-compliant checks

        Args:
        id: asset run id
        resourceType: resource type
    """
    try:
        logger.info("fetch_checks: \n")
        logger.debug("id: {}".format(id))
        logger.debug("resourceType: {}".format(resourceType))

        output=await utils.make_API_call_to_CCow({
                "planRunID": id,
                "resourceType": resourceType,
                "summaryType": "checks"
            }, constants.URL_FETCH_ASSETS_DETAIL_SUMMARY)

        logger.debug("output: {}\n".format(json.dumps(output)))

        return output
    except Exception as e:
        logger.error("fetch_checks error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_resources_summary(id: str, resourceType: str) -> dict | str:
    """
        Use this to get the summary on resource 
        Use this when total items in 'fetch_resources' is high
        Fetch a summary of resources for a given asset run id and resource type.
        Get a summarized view of resources include
            - Compliance breakdown for resource
                - Total Resources available
                - Total compliant resources
                - Total non-compliant resources

    Args:
        id: asset run ID
        resourceType: resource type
    """
    try:
        logger.info("fetch_resources: \n")
        logger.debug("id: {}".format(id))
        logger.debug("resourceType: {}".format(resourceType))

        output=await utils.make_API_call_to_CCow({
                "planRunID": id,
                "resourceType": resourceType,
                "summaryType": "resources"
            }, constants.URL_FETCH_ASSETS_DETAIL_SUMMARY)

        logger.debug("output: {}\n".format(json.dumps(output)))

        return output
    except Exception as e:
        logger.error("fetch_resources error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def fetch_resources_with_this_check_summary(id: str, resourceType: str, check: str) -> dict | str:
    """
        Use this to get the summary on check resources 
        Use this when total items in 'fetch_resources_for_check' is high
        Get check resources summary for given asset run id, resource type and check
        Paginated data is enough for summary
        Get a summarized view of check resources based on
            - Compliance breakdown for resources
                - Total Resources available
                - Total compliant resources
                - Total non-compliant resources

        Args:
        id: asset run id
        resourceType: resource type

    """

    try:
        logger.info("fetch_resources: \n")
        logger.debug("id: {}".format(id))
        logger.debug("resourceType: {}".format(resourceType))
        logger.debug("check: {}".format(check))

        output=await utils.make_API_call_to_CCow({
            "planRunID": id,
            "resourceType": resourceType,
            "checkName": check,
            "summaryType": "resources"
        },constants.URL_FETCH_ASSETS_DETAIL_SUMMARY)
        logger.debug("output: {}\n".format(json.dumps(output)))

        return output
    except Exception as e:
        logger.error("fetch_resources_for_check error: {}\n".format(e))
        return "Facing internal error"
