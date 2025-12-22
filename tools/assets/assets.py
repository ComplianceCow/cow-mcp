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
from mcptypes import assets_tools_type as vo
from fastmcp import Context


@mcp.tool()
async def list_assets(ctx: Context | None = None) -> vo.AssetListVO:
    """
        Get all assets
        
        Returns:
            - assets (List[AssetsVo]): A list of assets.
                - id (str):  Asset id.
                - name (str): Name of the asset.
            - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("get_assets_list: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_ASSETS, ctx)
        logger.debug("assets output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("list_assets error: {}\n".format(output))
            return vo.AssetListVO(error="Facing internal error")
        
        assets: List[vo.AssetVO]=[]
        for item in output["items"]:
            if "name" in item:
                assets.append(vo.AssetVO.model_validate(item))
        
        logger.debug("modified assets: {}\n".format(vo.AssetListVO(assets=assets).model_dump))

        return vo.AssetListVO(assets=assets)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_assets error: {}\n".format(e))
        return vo.AssetListVO(error="Facing internal error")

@mcp.tool()
async def fetch_assets_summary(id: str, ctx: Context | None = None) -> vo.AssestsSummaryVO:
    """
        Get assets summary for given assessment id

        Args:
            - id (str): Assessment id
            
        Returns:
            - integrationRunId (str):  Asset id.
            - assessmentName (str): Name of the asset.
            - status (str): Name of the asset.
            - numberOfResources (str): Name of the asset.
            - numberOfChecks (str): Name of the asset.
            - dataStatus (str): Name of the asset.
            - createdAt (str): Name of the asset.
            - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("fetch_assets_summary: \n")
        output=await utils.make_API_call_to_CCow({
            "planID": id,
        },constants.URL_FETCH_ASSETS_SUMMARY, ctx=ctx)
        
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_assets_summary error: {}\n".format(output))
            return vo.AssestsSummaryVO(error="Facing internal error")
        
        logger.debug("output: {}\n".format(json.dumps(output)))
        output = vo.AssestsSummaryVO.model_validate(output)
        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_assets_summary error: {}\n".format(e))
        return vo.AssestsSummaryVO(error="Facing internal error")

@mcp.tool()
async def fetch_resource_types(id: str, page: int=1, pageSize: int=0, ctx: Context | None = None) -> dict:
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
            - id(str): Asset run id
            
        Returns:
            - resourceTypes (List[AssetsVo]): A list of resource types.
                - resourceType (str):  Resource type.
                - totalResources (int): Total number of resources.               
            - error (Optional[str]): An error message if any issues occurred during retrieval. 
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
        },constants.URL_FETCH_RESOURCE_TYPES, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_resource_types error: {}\n".format(output))
            return vo.ResourceTypeListVO(error="Facing internal error")
    
        resourceTypes : List[vo.ResourceTypeVO] = []
        for item in output["items"]:
            resourceTypes.append(vo.ResourceTypeVO.model_validate(item))

        logger.debug("modified output: {}\n".format(vo.ResourceTypeListVO(resourceTypes=resourceTypes).model_dump()))
        return vo.ResourceTypeListVO(resourceTypes=resourceTypes).model_dump()
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_resource_types error: {}\n".format(e))
        return vo.ResourceTypeListVO(error="Facing internal error")

@mcp.tool()
async def fetch_checks(id: str, resourceType: str, page: int=1, pageSize: int=0, complianceStatus: str="", ctx: Context | None = None) -> vo.ChecksListVO:
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
            - id (str): Asset run id
            - resourceType (str): Resource type
            - complianceStatus (str): Compliance status
            
        Returns:
            - checks (List[CheckVO]): A list of checks.
                - name (str): Name of the check.
                - description (str): Description of the check.
                - rule (RuleVO): Rule associated with the check.
                    - type (str): Type of the rule.
                    - name (str): Name of the rule.
                - activationStatus (str): Activation status of the check.
                - priority (str): Priority level of the check.
                - complianceStatus (str): Compliance status of the check.
                - compliancePCT (float): Compliance percentage.
            - error (Optional[str]): An error message if any issues occurred during retrieval.

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
        },constants.URL_FETCH_CHECKS, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_checks error: {}\n".format(output))
            return vo.ChecksListVO(error="Facing internal error")
        
        checks: List[vo.CheckVO] = []
        for item in output["items"]:
            checks.append(vo.CheckVO.model_validate(item))
            
        return vo.ChecksListVO(checks=checks, 
                               totalItems=output["totalItems"],
                               totalPage=output["totalPage"],
                               page=output["page"],
                               )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_checks error: {}\n".format(e))
        return vo.ChecksListVO(error="Facing internal error")

@mcp.tool()
async def fetch_resources(id: str, resourceType: str, page: int=1, pageSize: int=0, complianceStatus: str="", ctx: Context | None = None) -> vo.ResourceListVO:
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
            - id (str): Asset run id
            - resourceType (str): Resource type
            - complianceStatus (str): Compliance status
            
        Returns:
            - resources (List[ResourceVO]): A list of resources.
                - name (str): Name of the resource.
                - resourceType (str): Type of the resource.
                - complianceStatus (str): Compliance status of the resource.
                - checks (List[ResourceCheckVO]): List of checks associated with the resource.
                    - name (str): Name of the check.
                    - description (str): Description of the check.
                    - rule (RuleVO): Rule applied in the check.
                        - type (str): Type of the rule.
                        - name (str): Name of the rule.
                    - activationStatus (str): Activation status of the check.
                    - priority (str): Priority level of the check.
                    - controlName (str): Name of the control.
                    - complianceStatus (str): Compliance status specific to the resource.
            - error (Optional[str]): An error message if any issues occurred during retrieval.

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
        },constants.URL_FETCH_RESOURCES, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_resources error: {}\n".format(output))
            return vo.ResourceListVO(error="Facing internal error")

        output=utils.formatResources(output,True)
        resources: List[vo.ResourceVO] = []
        for item in output["items"]:
            resources.append(vo.ResourceVO.model_validate(item))
            
        return vo.ResourceListVO(
                               resources=resources,
                               totalItems=output["totalItems"],
                               totalPage=output["totalPage"],
                               page=output["page"]
                               ).model_dump()
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_resources error: {}\n".format(e))
        return vo.ResourceListVO(error="Facing internal error")

@mcp.tool()
async def fetch_resources_by_check_name(id: str,  checkName: str, page: int=1, pageSize: int=0, ctx: Context | None = None) -> vo.ResourceListVO:
    """
        Get resources for given asset run id, and check name.
        Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize.
        If the request times out retry with pagination, increasing pageSize from 10 to 50.

        If the resource data set is large to fetch efficiently or results in timeouts, 
        it is recommended to use the 'summary tool' instead to get a summarized view of the resource.
        
        1. Call fetch_resources_for_check with page=1, pageSize=10
        2. Note the totalPages from the response
        3. Continue calling each page until complete
        4. Summarize all results together

        Args:
            - id: Asset run id.
            - checkName: Check name.

        Returns:
            - resources (List[ResourceVO]): A list of resources.
                - name (str): Name of the resource.
                - resourceType (str): Type of the resource.
                - complianceStatus (str): Compliance status of the resource.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        logger.info("fetch_resources_by_check_name: \n")
        logger.debug("id: {}".format(id))
        logger.debug("checkName: {}".format(checkName))

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
            "checkName": checkName,
            "page": page,
            "pageSize": pageSize
        },constants.URL_FETCH_RESOURCES, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_resources_by_check_name error: {}\n".format(output))
            return vo.ResourceListVO(error="Facing internal error")
        
        resources: List[vo.ResourceVO] = []
        for item in output["items"]:
            if "checks" in item:
                del item['checks']
            resources.append(vo.ResourceVO.model_validate(item))

        return vo.ResourceListVO(resources=resources, totalItems=output["totalItems"], page=output["page"], totalPage=output["totalPage"])
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_resources_by_check_name error: {}\n".format(e))
        return vo.ResourceListVO(error="Facing internal error")
    

# @mcp.tool()
async def fetch_resource_types_summary(id: str, ctx: Context | None = None) -> dict:
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
            - id (str): Asset run id
    """

    try:
        logger.info("fetch_resource_types_summary:\n")

        responses = await asyncio.gather(
            utils.make_API_call_to_CCow({
                "planRunID": id,
                "page": 1,
                "pageSize": 10
            }, constants.URL_FETCH_RESOURCE_TYPES, ctx=ctx),
            utils.make_API_call_to_CCow({
                "planRunID": id,
                "page": 2,
                "pageSize": 10
            }, constants.URL_FETCH_RESOURCE_TYPES, ctx=ctx),
            utils.make_API_call_to_CCow({
                "planRunID": id,
                "page": 3,
                "pageSize": 10
            }, constants.URL_FETCH_RESOURCE_TYPES, ctx=ctx)
        )

        resource_types: List[vo.ResourceTypeVO] = []
        total_items = None

        for output in responses:
            if isinstance(output, str) or  "error" in output:
                logger.error("fetch_resource_types_summary error: {}\n".format(output))
                return vo.ResourceListVO(error="Facing internal error")
            if total_items is None:
                total_items = output.get("totalItems")
            for item in output.get("items", []):
                resource_types.append(vo.ResourceTypeVO.model_validate(item))

        final_output = vo.ResourceTypeSummaryVO(resourcesTypes=resource_types, totalItems = total_items)
        logger.debug("modified output: {}\n".format(final_output.model_dump()))
        return final_output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_resource_types_summary error: {}\n".format(e))
        return vo.ResourceListVO(error="Facing internal error")

@mcp.tool()
async def fetch_checks_summary(id: str, resourceType: str, ctx: Context | None = None) -> vo.CheckSummaryVO:
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
            - id (str): Asset run id
            - resourceType (str): Resource type

        Returns:
            - complianceSummary (dict): Summary of compliance status across checks.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
        
    """
    try:
        logger.info("fetch_checks_summary: \n")
        logger.debug("id: {}".format(id))
        logger.debug("resourceType: {}".format(resourceType))

        output=await utils.make_API_call_to_CCow({
                "planRunID": id,
                "resourceType": resourceType,
                "summaryType": "checks"
            }, constants.URL_FETCH_ASSETS_DETAIL_SUMMARY, ctx=ctx)

        logger.debug("output: {}\n".format(json.dumps(output)))
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_checks_summary error: {}\n".format(output))
            return vo.CheckSummaryVO(error="Facing internal error")

        return vo.CheckSummaryVO.model_validate(output)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_checks_summary error: {}\n".format(e))
        return vo.CheckSummaryVO(error="Facing internal error")
    
@mcp.tool()
async def fetch_resources_summary(id: str, resourceType: str, ctx: Context | None = None) -> vo.ResourceSummaryVO:
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
        - id (str): asset run ID
         - resourceType (str): Resource type
         
    Returns:
        - complianceSummary (dict): Summary of compliance status across checks.
        - error (Optional[str]): An error message if any issues occurred during retrieval.
        
    """
    try:
        logger.info("fetch_resources: \n")
        logger.debug("id: {}".format(id))
        logger.debug("fetch_resources_summary: {}".format(resourceType))

        output=await utils.make_API_call_to_CCow({
                "planRunID": id,
                "resourceType": resourceType,
                "summaryType": "resources"
            }, constants.URL_FETCH_ASSETS_DETAIL_SUMMARY, ctx=ctx)

        logger.debug("output: {}\n".format(json.dumps(output)))
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_checks_summary error: {}\n".format(output))
            return vo.ResourceSummaryVO(error="Facing internal error")

        return vo.ResourceSummaryVO.model_validate(output)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_resources_summary error: {}\n".format(e))
        return vo.ResourceSummaryVO(error="Facing internal error")

@mcp.tool()
async def fetch_resources_by_check_name_summary(id: str, resourceType: str, check: str, ctx: Context | None = None) -> vo.ResourceSummaryVO:
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
            - id (str): Asset run id
            - resourceType (str): Resource type
        
        Returns:
            - complianceSummary (dict): Summary of compliance status across checks.
            - error (Optional[str]): An error message if any issues occurred during retrieval.

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
        },constants.URL_FETCH_ASSETS_DETAIL_SUMMARY, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_checks_summary error: {}\n".format(output))
            return vo.ResourceSummaryVO(error="Facing internal error")
        return vo.ResourceSummaryVO.model_validate(output)
    
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_resources_by_check_name_summary error: {}\n".format(e))
        return vo.ResourceSummaryVO(error="Facing internal error")
