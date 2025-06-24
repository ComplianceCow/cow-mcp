

import traceback
import json
import traceback
from typing import List
from typing import Tuple

from utils import utils
from utils.debug import logger
# from tools.mcpconfig import mcp
from mcpconfig.config import mcp
from constants import constants


# @mcp.resource("graph_schema://{nodeNames}")
@mcp.resource("graphschema://{question}")
async def get_graph_schema(question: str = "" ) -> Tuple[list, list, str]:
    nodeNames = ""
    """
        Function overview: To get the graph database schema and its relationship for the control node.
    """
    
    if not nodeNames:
        nodeNames = 'assessment, control'
        
    try:
        logger.info("\nget_schema_form_control: \n")
        logger.debug("question: {}".format(question))

        output=await utils.make_API_call_to_CCow({"user_question":question},constants.URL_RETRIEVE_UNIQUE_NODE_DATA_AND_SCHEMA)
        logger.debug("output: {}\n".format(output))
        return output["node_names"],output["unique_property_values"], output["neo4j_schema"]
        # return output["neo4j_schema"]
    except Exception as e:
        logger.error("get_schema_form_control error: {}\n".format(e))
        return "Facing internal error"
        
    
    