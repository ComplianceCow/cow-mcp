from typing import List
from typing import Tuple

from utils import utils
from utils.debug import logger
from mcpconfig.config import mcp
from constants import constants
from mcptypes import assessment_config_tool_types as vo
from fastmcp import Context

@mcp.tool()
async def get_default_ccf_assessment(ctx: Context | None = None) -> vo.AssessmentVO:
    """
        Get the default ccf assessment from CCow.
    """
    try:
        logger.info("get_default_ccf_assessment: \n")

        output=await utils.make_API_call_to_CCow({},constants.URL_PLANS+"/fetch-ccf-assessment", ctx=ctx)
        
        if isinstance(output, str) or  "error" in output:
            logger.error("get_default_ccf_assessment error: {}\n".format(output))
            return vo.AssessmentVO(error="Facing internal error")
    
        assessment=vo.AssessmentVO(**output)
        logger.debug("assessment: {}\n".format(output))
        return assessment
    except Exception as e:
        logger.error("get_default_ccf_assessment error: {}\n".format(e))
        return vo.AssessmentVO(error="Facing internal error")
    

@mcp.tool()
async def get_ccf_control_last_run_date(ccfControlIDs: list[str], ctx: Context | None = None) -> vo.ControlsLastRunDate:
    """
        Get the ccf assessment controls last run date. 
        
        input:
        ccfControlIDs: id (GUID) field of leaf controls in ccf assessment
    """
    try:
        logger.info("get_ccf_control_last_run_date: {} \n".format(ccfControlIDs))

        output=await utils.make_API_call_to_CCow({"ControlIDs": ccfControlIDs},constants.URL_PLAN_INSTANCE_CONTROLS+"/fetch-latest-run-date", ctx=ctx)
        
        if isinstance(output, str) or  "error" in output:
            logger.error("get_ccf_control_last_run_date error: {}\n".format(output))
            return vo.ControlsLastRunDate(error="Facing internal error")
    
        assessment=vo.ControlsLastRunDate(**output)
        logger.debug("last run date: {}\n".format(output))
        return assessment
    except Exception as e:
        logger.error("get_ccf_control_last_run_date error: {}\n".format(e))
        return vo.ControlsLastRunDate(error="Facing internal error")