import json
import traceback
import base64
from typing import List
from typing import Tuple

from utils import utils
from utils.debug import logger
from tools.mcpconfig import mcp

from constants import constants


@mcp.tool()
async def get_dashboard_data(payload : dict) -> dict:
    """
    Function accepts compliance period as 'period'. Period denotes for which quarter of year dashboard data is needed. Format: Q1 2024. 

    Dashboard contains summary data of Common Control Framework (CCF). For any related to contorl category, framework, assignment status use this function.
    This contains details of control status such as 'Completed', 'In Progress', 'Overdue', 'Pending'.
    The summarization levels are 'overall control status', 'control category wise', 'control framework wise',
    'overall control status' can be fetched from 'controlStatus'
    'control category wise' can be fetched from 'controlSummary'
    'control framework wise' can be fetched from 'frameworks'

    """
    try:
        logger.info("get_dashboard: \n")
        logger.debug("payload: {}\n".format(payload))

        data={
            "ccfPeriod":payload["period"],
            "includeCompliancePerformance": True,
            "includeControlSummary": True,
            "includeFrameworkCompliance": True
        }

        output=await utils.make_API_call_to_CCow(data, constants.URL_CCF_DASHBOARD_FRAMEWORK_SUMMARY)
        logger.debug("output: {}\n".format(output))

        return output
    except Exception as e:
        logger.error("get_dashboard_data error: {}\n".format(e))
        return "Facing internal error"
  
@mcp.tool()
async def fetch_dashboard_framework_controls(period: str, framework_name : str) -> dict:
    """
    ### Function Overview: Retrieve Control Details for a Given CCF and Review Period

    This function retrieves detailed control-level data for a specified **Common Control Framework (CCF)** during a specific **review period**. 

    #### Parameters

    - **`review_period`**:  
    The compliance period (typically a quarter) for which the control-level data is requested.  
    **Format**: `"Q1 2024"`

    - **`framework_name`**:  
    The name of the Common Control Framework to fetch data for.

    #### Purpose

    This function is used to fetch a list of controls and their associated data for a specific CCF and review period.  
    It does not return an aggregated overview — instead, it retrieves detailed, item-level data for each control via an API call.

    The results are displayed in the MCP host with **client-side pagination**, allowing users to navigate through the control list efficiently without making repeated API calls.


    #### Output Fields

    Each control entry in the output includes the following attributes:

    - **Name** — from `controlName`
    - **Assigned To** — extracted from the email ID in `lastAssignedTo`, if available
    - **Assignment Status** — from `status`, if available
    - **Compliance Status** — from `complianceStatus`
    - **Due Date** — from `dueDate`
    - **Score** — from `score`
    - **Priority** — from `priority`


    """
    try:
        
        data = {
        "ccfPeriod": period,
        "includeOverDueControls": False,
        "includeNonCompliantControls": False,
        "fetchleafControls": True,
        "authorityDocumentName": framework_name,
        }
        
        logger.info("fetch_ccf_details_and_controls: \n")
        logger.debug("payload: {}\n".format(data))
        

        output=await utils.make_API_call_to_CCow(data, constants.URL_CCF_DASHBOARD_CONTROL_DETAILS)
        logger.debug("output: {}\n".format(output))

        # return list_as_table_prompt(output)
        return output
    except Exception as e:
        logger.error("get_dashboard_data error: {}\n".format(e))
        return "Facing internal error"  
    
@mcp.tool()
async def fetch_dashboard_framework_summary(period: str, framework_name : str) -> dict:
    """
    ### Function Overview: CCF Dashboard Summary Retrieval

    This function returns a summary dashboard for a specified **compliance period** and **Common Control Framework (CCF)**.
    It is designed to provide a high-level view of control statuses within a given framework and period, making it useful for compliance tracking, reporting, and audits.

    #### Parameters

    - **`period`**:  
    The compliance quarter for which the dashboard data is requested.  
    **Format**: `"Q1 2024"`

    - **`framework_name`**:  
    The name of the Common Control Framework whose data is to be retrieved.

    #### Dashboard Overview

    The dashboard provides a consolidated view of all controls under the specified framework and period.
    It includes key information such as assignment status, compliance progress, due dates, and risk scoring to help stakeholders monitor and manage compliance posture.

    #### Output Fields

    Each control entry in the output includes the following attributes:

    - **Name** — from `controlName`
    - **Assigned To** — extracted from the email ID in `lastAssignedTo`, if available
    - **Assignment Status** — from `status`, if available
    - **Compliance Status** — from `complianceStatus`
    - **Due Date** — from `dueDate`
    - **Score** — from `score`
    - **Priority** — from `priority`

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
        logger.debug("output: {}\n".format(output))

        return output
    except Exception as e:
        logger.error("get_dashboard_data error: {}\n".format(e))
        return "Facing internal error"  
    
@mcp.tool()
async def get_dashboard_common_controls_details(period: str, complianceStatus: str="", controlStatus: str="",  priority: str="", controlCategoryName: str="",page: int=1, pageSize:  int=50) -> dict:
    """
    Function accepts compliance period as 'period'. Period donates for which quarter of year dashboard data is needed. Format: Q1 2024. 
    Use this tool to get Common Control Framework (CCF) dashboard data for a specific compliance period with filters.
    This function provides detailed information about common controls, including their compliance status, control status, and priority.
    Use pagination if controls count is more than 50 then use page and pageSize to get control data pagewise, Once 1st page is fetched,then more pages available suggest to get next page data then increase page number.
    Args:
    period (str): Compliance period for which dashboard data is needed. Format: 'Q1 2024'. (Required)
    complianceStatus (str): Compliance status filter (Optional, possible values: 'COMPLIANT', 'NON_COMPLIANT', 'NOT_DETERMINED"). Default is empty string (fetch all Compliance statuses).
    controlStatus (str): Control status filter (Optional, possible values: 'Pending', 'InProgress', 'Completed', 'Unassigned', 'Overdue'). Default is empty string (fetch all statuses).
    priority (str): Priority of the controls. (Optional, possible values: 'High', 'Medium', 'Low'). Default is empty string (fetch all priorities).
    controlCategoryName (str): Control category name filter (Optional). Default is empty string (fetch all categories).
    page (int): Page number for pagination (Optional). Default is 1 (fetch first page).
    pageSize (int): Number of items per page (Optional). Default is 50.
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
        };

        logger.debug("payload: {}\n".format(data))

        output=await utils.make_API_call_to_CCow(data,constants.URL_CCF_DASHBOARD_CONTROL_DETAILS)
        logger.debug("output: {}\n".format(output))

        return output
    except Exception as e:
        logger.error("get_dashboard_data error: {}\n".format(e))
        return "Facing internal error"


@mcp.prompt()
def list_as_table_prompt(response: dict) -> dict:
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
     



# @mcp.resource("controls://over-due")
# async def get_top_over_due_controls() -> dict:


# @mcp.resource("controls://over-due?count={count}")
# async def get_top_over_due_controls(count: int) -> dict:

@mcp.tool()
async def get_top_over_due_controls_detail(payload : dict) -> dict | str: 
    """
        Fetch controls with top over due (over-due)
        Function accepts count as 'count'
        Function accepts compliance period as 'period'. Period donates for which quarter of year dashboard data is needed. Format: Q1 2024. 
    """
    try:
        logger.info("get_top_over_due_controls: \n")
        logger.debug("payload: {}\n".format(payload))

        if 'count' not in payload:
            payload['count']=10

        data={
            "ccfPeriod":payload["period"],
            "includeOverDueControls": True,
            "page": 1,
            "pageSize": payload['count']
        }

        output=await utils.make_API_call_to_CCow(data,constants.URL_CCF_DASHBOARD_CONTROL_DETAILS)
        logger.debug("output: {}\n".format(output))

        return output["items"]
    except Exception as e:
        logger.error("get_top_over_due_controls_detail error: {}\n".format(e))
        return "Facing internal error"

@mcp.tool()
async def get_top_non_compliant_controls_detail(period: str, count= 1, page=1) -> dict | str: 
    # """
    #     Fetch controls with low compliant score
    #     Function accepts count as 'count'. Format: 2
        
    #     Function accepts compliance period as 'period'. Period donates for which quarter of year dashboard data is needed. Format: Q1 2024. 
    # """
    """
        Function overview: Fetch control with low compliant score or non compliant controls.
        Arguments: 
        1. period: Compliance period which denotes quarter of the year whose dashboard data is needed. By default: Q1 2024.
        2. count: 
        3. page: If the user asks of next page use smartly decide the page.
    """
    try:
        data={
            "ccfPeriod":period,
            "includeNonCompliantControls": True,
            "page": int(page),
            "pageSize": int(count)
        }
        
        logger.info("get_top_over_due_controls: \n")
        logger.debug("payload: {}\n".format(data))

        # if 'count' not in payload:
        #     payload['count']=10

        # data={
        #     "ccfPeriod":payload["period"],
        #     "includeNonCompliantControls": True,
        #     "page": payload["page"],
        #     "pageSize": payload['count']
        # }

        output=await utils.make_API_call_to_CCow(data,constants.URL_CCF_DASHBOARD_CONTROL_DETAILS)
        logger.debug("output: {}\n".format(output))

        return output["items"]
    except Exception as e:
        logger.error("get_top_non_compliant_controls_detail error: {}\n".format(e))
        return "Facing internal error"
    
