import json
import traceback
import base64
from typing import List
from typing import Tuple

from utils import utils
from utils.debug import logger
from mcpconfig.config import mcp

from constants import constants

from mcptypes import dashboard_tools_type as vo

@mcp.tool()
async def get_dashboard_review_periods() -> vo.CCFDashboardReviewPeriods:
    """
    Fetch list of review periods
    Returns:
        - items (List[str]): list of review periods
        - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("get_dashboard_review_periods: \n")
        data={}

        output=await utils.make_API_call_to_CCow(data, constants.URL_CCF_DASHBOARD_REVIEW_PERIODS)
        logger.debug("output: {}\n".format(json.dumps(output)))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("get_dashboard_review_periods error: {}\n".format(output))
            return vo.CCFDashboardReviewPeriods(error="Facing internal error")

        return vo.CCFDashboardReviewPeriods.model_validate(output)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_dashboard_review_periods error: {}\n".format(e))
        return vo.CCFDashboardReviewPeriods(error="Facing internal error")

@mcp.tool()
async def get_dashboard_data(period: str = "Q1 2024") -> vo.DashboardSummaryVO:
    """
    Function accepts compliance period as 'period'. Period denotes for which quarter of year dashboard data is needed. Format: Q1 2024. 

    Dashboard contains summary data of Common Control Framework (CCF). For any related to contorl category, framework, assignment status use this function.
    This contains details of control status such as 'Completed', 'In Progress', 'Overdue', 'Pending'.
    The summarization levels are 'overall control status', 'control category wise', 'control framework wise',
    'overall control status' can be fetched from 'controlStatus'
    'control category wise' can be fetched from 'controlSummary'
    'control framework wise' can be fetched from 'frameworks'
    
    Args:
        - period (str) - Period denotes for which quarter of year dashboard data is needed. Format: Q1 2024. 
        
    Returns:
        - totalControls (int): Total number of controls in the dashboard.
        - controlStatus (List[ComplianceStatusSummaryVO]): Summary of control statuses.
            - status (str): Compliance status of the control.
            - count (int): Number of controls with the given status.
        - controlAssignmentStatus (List[ControlAssignmentStatusVO]): Assignment status categorized by control.
            - categoryName (str): Name of the control category.
            - controlStatus (List[ComplianceStatusSummaryVO]): Status summary within the category.
                - status (str): Compliance status.
                - count (int): Number of controls with this status.
        - compliancePCT (float): Overall compliance percentage across all controls.
        - controlSummary (List[ControlSummaryVO]): Detailed summary of each control.
            - category (str): Category name of the control.
            - status (str): Compliance status of the control.
            - dueDate (str): Due date for the control, if applicable.
            - compliancePCT (float): Compliance percentage for the control.
            - leafControls (int): Number of leaf-level controls in the category.
        - complianceStatusSummary (List[ComplianceStatusSummaryVO]): Summary of control statuses.
            - status (str): Compliance status.
            - count (int): Number of controls with the given status.
        - error (Optional[str]): An error message if any issues occurred during retrieval. 

    """
    try:


        data={
            "ccfPeriod": period,
            "includeCompliancePerformance": True,
            "includeControlSummary": True,
            "includeFrameworkCompliance": True
        }
        
        logger.info("get_dashboard: \n")
        logger.debug("payload: {}\n".format(data))

        output=await utils.make_API_call_to_CCow(data, constants.URL_CCF_DASHBOARD_FRAMEWORK_SUMMARY)
        logger.debug("output: {}\n".format(json.dumps(output)))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("get_dashboard_data error: {}\n".format(output))
            if "NO_DATA_FOUND" in output["error"]:
                return vo.DashboardSummaryVO(error=f"There is no data found for the review period: {period}")
            return vo.DashboardSummaryVO(error="Facing internal error")

        return vo.DashboardSummaryVO.model_validate(output)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_dashboard_data error: {}\n".format(e))
        return vo.DashboardSummaryVO(error="Facing internal error")
  
@mcp.tool()
async def fetch_dashboard_framework_controls(period: str, framework_name : str) -> vo.FrameworkControlListVO:
    """
    Function Overview: Retrieve Control Details for a Given CCF and Review Period

    This function retrieves detailed control-level data for a specified **Common Control Framework (CCF)** during a specific **review period**. 

    Args:
    - review_period: The compliance period (typically a quarter) for which the control-level data is requested.  
    Format: `"Q1 2024"`
    - framework_name:  
    The name of the Common Control Framework to fetch data for.

    Purpose

    This function is used to fetch a list of controls and their associated data for a specific CCF and review period.  
    It does not return an aggregated overview — instead, it retrieves detailed, item-level data for each control via an API call.

    The results are displayed in the MCP host with **client-side pagination**, allowing users to navigate through the control list efficiently without making repeated API calls.


    Returns:
        - controls (List[FramworkControlVO]): A list of framework controls.
            - name (str): Name of the control.
            - assignedTo (str): Email ID of the user the control is assigned to.
            - assignmentStatus (str): Status of the control assignment.
            - complianceStatus (str): Compliance status of the control.
            - dueDate (str): Due date for completing the control.
            - score (float): Score assigned to the control.
            - priority (str): Priority level of the control.
        - page (int): Current page number in the overall result set.
        - totalPage (int): Total number of pages.
        - totalItems (int): Total number of items.
        - error (Optional[str]): An error message if any issues occurred during retrieval.

    """
    try:
        
        data = {
        "ccfPeriod": period,
        "includeOverDueControls": False,
        "includeNonCompliantControls": False,
        "fetchleafControls": True,
        "authorityDocumentName": framework_name,
        }
        
        logger.info("fetch_dashboard_framework_controls: \n")
        logger.debug("payload: {}\n".format(data))
        

        output=await utils.make_API_call_to_CCow(data, constants.URL_CCF_DASHBOARD_CONTROL_DETAILS)
        logger.debug("output: {}\n".format(json.dumps(output)))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_dashboard_framework_controls error: {}\n".format(output))
            return vo.FrameworkControlListVO(error="Facing internal error")
        
        controls: List[vo.FramworkControlVO] = []
        if output["items"]:
            for item in output["items"]:
                if "controlName" in item:
                    controls.append(vo.FramworkControlVO.model_validate(item))

        return vo.FrameworkControlListVO(
                                controls=controls,
                                totalItems=output["TotalItems"],
                                totalPage=output["TotalPage"],
                                page=output["Page"],
            ).model_dump()
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_dashboard_framework_controls error: {}\n".format(e))
        return vo.FrameworkControlListVO(error="Facing internal error")
    
@mcp.tool()
async def fetch_dashboard_framework_summary(period: str, framework_name : str) -> vo.FrameworkControlListVO:
    """
    Function Overview: CCF Dashboard Summary Retrieval

    This function returns a summary dashboard for a specified **compliance period** and **Common Control Framework (CCF)**.
    It is designed to provide a high-level view of control statuses within a given framework and period, making it useful for compliance tracking, reporting, and audits.

    
    Args:
    - period:  
    The compliance quarter for which the dashboard data is requested.  
    Format: `"Q1 2024"`
    - framework_name:  
    The name of the Common Control Framework whose data is to be retrieved.

    Dashboard Overview

    The dashboard provides a consolidated view of all controls under the specified framework and period.
    It includes key information such as assignment status, compliance progress, due dates, and risk scoring to help stakeholders monitor and manage compliance posture.

    Returns:
        - controls (List[FramworkControlVO]): A list of framework controls.
            - name (str): Name of the control.
            - assignedTo (str): Email ID of the user the control is assigned to.
            - assignmentStatus (str): Status of the control assignment.
            - complianceStatus (str): Compliance status of the control.
            - dueDate (str): Due date for completing the control.
            - score (float): Score assigned to the control.
            - priority (str): Priority level of the control.
        - page (int): Current page number in the overall result set.
        - totalPage (int): Total number of pages.
        - totalItems (int): Total number of items.
        - error (Optional[str]): An error message if any issues occurred during retrieval.

    """
    try:
        
        data = {
        "ccfPeriod": period,
        "includeOverDueControls": False,
        "includeNonCompliantControls": False,
        "fetchleafControls": True,
        "authorityDocumentName": framework_name,
        }
        
        logger.info("fetch_ccf_dashboard: \n")
        logger.debug("payload: {}\n".format(data))
        

        output=await utils.make_API_call_to_CCow(data, constants.URL_CCF_DASHBOARD_CONTROL_DETAILS)
        logger.debug("output: {}\n".format(json.dumps(output)))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_dashboard_framework_summary error: {}\n".format(output))
            return vo.FrameworkControlListVO(error="Facing internal error")
        
        controls: List[vo.FramworkControlVO] = []
        if output["items"]:
            for item in output["items"]:
                if "controlName" in item:
                    controls.append(vo.FramworkControlVO.model_validate(item))

        return vo.FrameworkControlListVO(
                                controls=controls,
                                totalItems=output["TotalItems"],
                                totalPage=output["TotalPage"],
                                page=output["Page"],
            ).model_dump()
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_dashboard_framework_summary error: {}\n".format(e))
        return vo.FrameworkControlListVO(error="Facing internal error")
    
@mcp.tool()
async def get_dashboard_common_controls_details(period: str, complianceStatus: str="", controlStatus: str="",  priority: str="", controlCategoryName: str="",page: int=1, pageSize:  int=50) -> vo.CommonControlListVO:
    """
    Function accepts compliance period as 'period'. Period donates for which quarter of year dashboard data is needed. Format: Q1 2024. 
    Use this tool to get Common Control Framework (CCF) dashboard data for a specific compliance period with filters.
    This function provides detailed information about common controls, including their compliance status, control status, and priority.
    Use pagination if controls count is more than 50 then use page and pageSize to get control data pagewise, Once 1st page is fetched,then more pages available suggest to get next page data then increase page number.
    Args:
        - period (str): Compliance period for which dashboard data is needed. Format: 'Q1 2024'. (Required)
        - complianceStatus (str): Compliance status filter (Optional, possible values: 'COMPLIANT', 'NON_COMPLIANT', 'NOT_DETERMINED"). Default is empty string (fetch all Compliance statuses).
        - controlStatus (str): Control status filter (Optional, possible values: 'Pending', 'InProgress', 'Completed', 'Unassigned', 'Overdue'). Default is empty string (fetch all statuses).
        - priority (str): Priority of the controls. (Optional, possible values: 'High', 'Medium', 'Low'). Default is empty string (fetch all priorities).
        - controlCategoryName (str): Control category name filter (Optional). Default is empty string (fetch all categories).
        - page (int): Page number for pagination (Optional). Default is 1 (fetch first page).
        - pageSize (int): Number of items per page (Optional). Default is 50.

    Returns:
        - controls (List[CommonControlVO]): A list of common controls.
            - id (str): Unique identifier of the control.
            - planInstanceID (str): ID of the associated plan instance.
            - alias (str): Alias or alternate name for the control.
            - displayable (str): Flag or content that indicates display eligibility.
            - controlName (str): Name of the control.
            - dueDate (str): Due date assigned to the control.
            - score (float): Score assigned to the control.
            - priority (str): Priority level of the control.
            - status (str): Current status of the control.
            - complianceStatus (str): Compliance status of the control.
            - updatedAt (str): Timestamp when the control was last updated.
        - page (int): Current page number in the paginated result.
        - totalPage (int): Total number of pages available.
        - totalItems (int): Total number of control items.
        - error (Optional[str]): An error message if any issues occurred during retrieval.

    """
    try:
        logger.info("get_dashboard: \n")

        includeNonCompliantControls = complianceStatus == "NON_COMPLIANT"
        includeOverDueControls = controlStatus == "Overdue"
        # fetchleafControls = False if not controlStatus else True

        status = "" if includeOverDueControls else controlStatus
        complianceStatusField = "" if includeNonCompliantControls else complianceStatus

        data = {
        "ccfPeriod": period,
        "includeOverDueControls": includeOverDueControls,
        "includeNonCompliantControls": includeNonCompliantControls,
        "fetchleafControls": True,
        # "authorityDocumentName": authorityDocumentName,
        "status": status,
        "complianceStatus": complianceStatusField,
        "controlCategoryName" : controlCategoryName,
        "priority": priority,
        "page": page,
        "pageSize": pageSize
        }

        logger.debug("payload: {}\n".format(data))

        output=await utils.make_API_call_to_CCow(data,constants.URL_CCF_DASHBOARD_CONTROL_DETAILS)
        logger.debug("output: {}\n".format(json.dumps(output)))
        if isinstance(output, str) or  "error" in output:
            logger.error("get_dashboard_common_controls_details error: {}\n".format(output))
            return vo.CommonControlListVO(error="Facing internal error")
        
        controls: List[vo.CommonControlVO] = []
        if output["items"]:
            for item in output["items"]:
                if "controlName" in item:
                    controls.append(vo.CommonControlVO.model_validate(item))

        return vo.CommonControlListVO(
            controls=controls,
            totalItems=output["TotalItems"],
            totalPage=output["TotalPage"],
            page=output["Page"]
            )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_dashboard_common_controls_details error: {}\n".format(e))
        return vo.CommonControlListVO(error="Facing internal error")


@mcp.prompt()
def list_as_table_prompt(response: dict) -> str:
    # """
    #     This function retrieves detailed control-level data for a specified **Common Control Framework (CCF)** during a specific **review period**. 
    # """
    
    prompt = f"""
    Please return the data as a table: like the following:
    - **Name** — from `controlName`
    - **Assigned To** — extracted from the email ID in `lastAssignedTo`, if available
    - **Assignment Status** — from `status`, if available
    - **Compliance Status** — from `complianceStatus`
    - **Due Date** — from `dueDate`
    - **Score** — from `score`
    - **Priority** — from `priority`
    
    DATA: {response}
    """
    
    return prompt
     


@mcp.tool()
async def get_top_over_due_controls_detail(period: str = "Q1 2024", count: int = 10) -> vo.OverdueControlListVO: 
    """
        Fetch controls with top over due (over-due)
        Function accepts count as 'count'
        Function accepts compliance period as 'period'. Period donates for which quarter of year dashboard data is needed. Format: Q1 2024. 
        
        Args:
            - period (str, required) - Compliance period
            - count (int, required) - page content size, defaults to 10
            
        Returns:
            - controls (List[OverdueControlVO]): A list of overdue controls.
                - name (str): Name of the control.
                - assignedTo (List[UserVO]): List of users assigned to the control.
                    - emailid (str): Email ID of the assigned user.
                - assignmentStatus (str): Assignment status of the control.
                - complianceStatus (str): Compliance status of the control.
                - dueDate (str): Due date for the control.
                - score (float): Score assigned to the control.
                - priority (str): Priority level of the control.
            - error (Optional[str]): An error message if any issues occurred during retrieval.

        
    """
    try:

        data={
            "ccfPeriod": period,
            "includeOverDueControls": True,
            "page": 1,
            "pageSize": count
        }
        
        logger.info("get_top_over_due_controls: \n")
        logger.debug("payload: {}\n".format(data))

        output=await utils.make_API_call_to_CCow(data,constants.URL_CCF_DASHBOARD_CONTROL_DETAILS)
        logger.debug("output: {}\n".format(json.dumps(output)))
        if isinstance(output, str) or  "error" in output:
            logger.error("get_top_over_due_controls_detail error: {}\n".format(output))
            return vo.OverdueControlListVO(error="Facing internal error")
        
        controls: List[vo.OverdueControlVO] = []
        if output["items"]:
            for item in output["items"]:
                if "controlName" in item:
                    controls.append(vo.OverdueControlVO.model_validate(item))

        return vo.OverdueControlListVO(controls=controls)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_top_over_due_controls_detail error: {}\n".format(e))
        return vo.OverdueControlListVO(error="Facing internal error")

@mcp.tool()
async def get_top_non_compliant_controls_detail(period: str, count= 1, page=1) -> vo.NonCompliantControlListVO: 

    """
        Function overview: Fetch control with low compliant score or non compliant controls.
        Arguments: 
        1. period: Compliance period which denotes quarter of the year whose dashboard data is needed. By default: Q1 2024.
        2. count: 
        3. page: If the user asks of next page use smartly decide the page.
        
        Returns:
        - controls (List[NonCompliantControlVO]): A list of non-compliant controls.
            - name (str): Name of the control.
            - lastAssignedTo (List[UserVO]): List of users to whom the control was last assigned.
                - emailid (str): Email ID of the assigned user.
            - score (float): Score assigned to the control.
            - priority (str): Priority level of the control.
        - error (Optional[str]): An error message if any issues occurred during retrieval.

    """
    try:
        data={
            "ccfPeriod":period,
            "includeNonCompliantControls": True,
            "page": int(page),
            "pageSize": int(count)
        }
        
        logger.info("get_top_non_compliant_controls_detail: \n")
        logger.debug("payload: {}\n".format(data))

        output=await utils.make_API_call_to_CCow(data,constants.URL_CCF_DASHBOARD_CONTROL_DETAILS)
        logger.debug("output: {}\n".format(json.dumps(output)))
        if isinstance(output, str) or  "error" in output:
            logger.error("get_top_non_compliant_controls_detail error: {}\n".format(output))
            return vo.NonCompliantControlListVO(error="Facing internal error")
        
        controls: List[vo.NonCompliantControlVO] = []
        if output["items"]:
            for item in output["items"]:
                if "controlName" in item:
                    controls.append(vo.NonCompliantControlVO.model_validate(item))

        return vo.NonCompliantControlListVO(controls=controls)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_top_non_compliant_controls_detail error: {}\n".format(e))
        return vo.NonCompliantControlListVO(error="Facing internal error")
    
