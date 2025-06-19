
import traceback
import json
import traceback
from typing import List
from typing import Tuple

from utils import utils
from utils.debug import logger
from tools.mcpconfig import mcp
from constants import constants


@mcp.tool(name="fetch_unique_node_data_and_schema",description="Fetch unique node data and schema")
# async def f1(question: str) -> Tuple[list, list, str]:
async def fetch_unique_node_data_and_schema(question: str) -> Tuple[list, list, str]:
    """Given a question get unique node data and schema from CCow system. Here question is the user question.

    Args:
        question: user question
    
    Results:
        node_names: graph node names
        unique_property_values: unique value of each property of nodes
        neo4j_schema: graph node schema details

    """
    try:
        logger.info("\nget_unique_node_data_and_schema: \n")
        logger.debug("question: {}".format(question))

        output=await utils.make_API_call_to_CCow({"user_question":question},constants.URL_RETRIEVE_UNIQUE_NODE_DATA_AND_SCHEMA)
        logger.debug("output: {}\n".format(output))

        return output["node_names"],output["unique_property_values"], output["neo4j_schema"]
    except Exception as e:
        logger.error("fetch_unique_node_data_and_schema error: {}\n".format(e))
        return "Facing internal error"



@mcp.tool()
# async def execute_cypher_query(question,query: str) -> str: 
async def execute_cypher_query(query: str) -> dict | str: 
    """Given a question and query, execute a cypher query and transform result to human readable format.

    Args:
        query: query to execute in graph DB
    """
    try:
        logger.info("\nrun_cypher_query: \n")
        logger.debug("query: {}".format(query))

        output=await utils.make_API_call_to_CCow({
            "query": query,
        },constants.URL_EXECUTE_CYPHER_QUERY)
        logger.debug("output: {}\n".format(output))

        # return output["result_in_text"]
        return output["result"]
    except Exception as e:
        logger.error("execute_cypher_query error: {}\n".format(e))
        return "Facing internal error"
