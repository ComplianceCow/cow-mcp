
import traceback
import json
import traceback
from typing import List
from typing import Tuple

from utils import utils
from utils.debug import logger
from mcptypes.graph_tool_types import UniqueNodeDataVO , CypherQueryVO
from mcpconfig.config import mcp
from constants import constants


@mcp.tool(name="fetch_unique_node_data_and_schema",description="Fetch unique node data and schema")
async def fetch_unique_node_data_and_schema(question: str) -> UniqueNodeDataVO:

    """
    Fetch unique node data and corresponding schema for a given question.

    Args:
        question (str): The user's input question.

    Returns:
        - node_names (List[str]): List of unique node names involved.
        - unique_property_values (list[any]): Unique property values per node.
        - neo4j_schema (str): The Neo4j schema associated with the nodes.
        - error (Optional[str]): Error message if any issues occurred during processing.
    """

    try:
        logger.info("\nget_unique_node_data_and_schema: \n")
        logger.debug("question: {}".format(question))

        output=await utils.make_API_call_to_CCow({"user_question":question},constants.URL_RETRIEVE_UNIQUE_NODE_DATA_AND_SCHEMA)
        logger.debug("output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_unique_node_data_and_schema error: {}\n".format(output))
            return UniqueNodeDataVO(error="Facing internal error")
        
        uniqueNodeDataVO = UniqueNodeDataVO(
            node_names=output["node_names"],
            unique_property_values=output["unique_property_values"],
            neo4j_schema=output["neo4j_schema"]
        )
        return uniqueNodeDataVO
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_unique_node_data_and_schema error: {}\n".format(e))
        return  UniqueNodeDataVO(error='Facing internal server error')



@mcp.tool() 
async def execute_cypher_query(query: str) -> CypherQueryVO: 
    """
    Given a question and query, execute a cypher query and transform result to human readable format.
        
    This tool queries a Neo4j graph database containing compliance controls, frameworks, and evidence.
    
    Key database structure:
        - Controls have hierarchical relationships via HAS_CHILD edges
        - Evidence nodes are attached to leaf controls (controls with no children)
        - Use recursive patterns [HAS_CHILD*] for traversing control hierarchies
        - Controls may have multiple levels of nesting
        - Evidence contains records
        - RiskItem nodes are attached to control-config via HAS_RISK & HAS_MAPPED_CONTROL edges 
        - RiskItemAttribute nodes are attached to RiskItem via HAS_ATTRIBUTE edges
        
    Query guidelines:
        - For control hierarchies: Use MATCH (parent)-[HAS_CHILD*]->(child) patterns
        - For evidence: Evidence is only available on leaf controls (Always check last child of control for evidence) (no outgoing HAS_CHILD relationships)
        - For control depth: Calculate hierarchy depth when analyzing control structures
        - Use APOC procedures for complex graph operations when available
        - While list assessment run always include assessment name
        - For large datasets from query: Provide overview summary & suggest refinement suggestion   
        

    Args:
    query (str): The Cypher query to execute against the graph database.
    
    Returns:
        - result (Any): The formatted, human-readable result of the Cypher query.
        - error (Optional[str]): An error message if the query execution fails or encounters issues.

    Example queries:
        - Find all root controls: MATCH (c:Control) WHERE NOT ()-[:HAS_CHILD]->(c) RETURN c
        - Get control hierarchy: MATCH (root)-[:HAS_CHILD*]->(leaf) RETURN root, leaf
        - Find evidence for controls (leaf control): MATCH (c:Control)-[:HAS_EVIDENCE]->(e:Evidence) RETURN c, e
        - Find leaf control: MATCH (c:Control) WHERE NOT (c)-[:HAS_CHILD]->(:Control) RETURN c
        - Find records: MATCH (e:Evidence)-[:HAS_RECORD]-(:Record) RETURN e
    """
    try:
        logger.info("\nexecute_cypher_query: \n")
        logger.debug("query: {}".format(query))

        output=await utils.make_API_call_to_CCow({
            "query": query,
        },constants.URL_EXECUTE_CYPHER_QUERY)
        logger.debug("output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("\nexecute_cypher_query error: {}\n".format(output))
            return CypherQueryVO(error="Facing internal error")

        return CypherQueryVO(result=output.get('result'))
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("\nexecute_cypher_query error: {}\n".format(e))
        return CypherQueryVO(error="Facing internal error")
