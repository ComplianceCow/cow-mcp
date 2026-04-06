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
        Get the default ccf assessment from the domain preferences.
    """
    try:
        logger.info("get_default_ccf_assessment: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_ASSESSMENTS+"/35081fe5-c85d-4c69-812b-14e7361779fd", ctx)
        
        if isinstance(output, str) or  "error" in output:
            logger.error("get_default_ccf_assessment error: {}\n".format(output))
            return vo.AssessmentVO(error="Facing internal error")
    
        assessment=vo.AssessmentVO(**output)
        logger.debug("assessment: {}\n".format(output))
        return assessment
    except Exception as e:
        logger.error("get_default_ccf_assessment error: {}\n".format(e))
        return vo.AssessmentVO(error="Facing internal error")