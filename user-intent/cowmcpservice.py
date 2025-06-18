import os
import signal
import sys

from utils.debug import logger
from utils.auth import CCowOAuthProvider

from mcpconfig import mcp
from tools.assessments.config import  config
from tools.assessments.run import  run
from tools.graphdb import  graphdb
from tools.dashboard import  dashboard
from tools.assets import  assets
from constants.constants import host
from mcp.server.auth.settings import AuthSettings


def signal_handler(sig, frame):
    print("Shutting down...")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


# async def utils.make_API_call_to_CCow(request_body: dict,uriSuffix: str) -> dict[str, Any] | str  :
#     logger.info(f"uriSuffix: {uriSuffix}")
#     async with httpx.AsyncClient() as client:
#         try:
#             requestHeader=headers
#             accessToken=get_access_token()
#             if accessToken is not None:
#                 requestHeader=headers.copy()
#                 requestHeader["Authorization"]=accessToken.token
#             # response = await client.post("http://localhost:14600/v1/llm/"+uriSuffix,json=request_body, headers={"Authorization": "db4f39f2-45b1-445c-9b05-5cd4d5f04990"}, timeout=300.0)
#             response = await client.post(host+uriSuffix,json=request_body, headers=requestHeader, timeout=60.0)
#             return response.json()
#         except httpx.TimeoutException:
#             logger.error(f"utils.make_API_call_to_CCow error: Request timed out after 60 seconds for uriSuffix: {uriSuffix}")
#             return "Facing error : Request timed out."
#         except Exception as e:
#             logger.error(traceback.format_exc())
#             logger.error("utils.make_API_call_to_CCow error: {}\n".format(e))
#             return "Facing error  :  "+str(e)

# async def utils.make_GET_API_call_to_CCow(uriSuffix: str) -> dict[str, Any] | str  :
#     logger.info(f"uriSuffix: {uriSuffix}")
#     async with httpx.AsyncClient() as client:
#         try:
#             requestHeader=headers
#             accessToken=get_access_token()
#             if accessToken is not None:
#                 requestHeader=headers.copy()
#                 requestHeader["Authorization"]=accessToken.token
#             # response = await client.post("http://localhost:14600/v1/llm/"+uriSuffix,json=request_body, headers={"Authorization": "db4f39f2-45b1-445c-9b05-5cd4d5f04990"}, timeout=300.0)
#             response = await client.get(host+uriSuffix, headers=requestHeader, timeout=60.0)
#             return response.json()
#         except httpx.TimeoutException:
#             logger.error(f"utils.make_API_call_to_CCow error: Request timed out after 60 seconds for uriSuffix: {uriSuffix}")
#             return "Facing error : Request timed out."
#         except Exception as e:
#             logger.error(traceback.format_exc())
#             logger.error("utils.make_API_call_to_CCow error: {}\n".format(e))
#             return "Facing error  :  "+str(e)


# @mcp.tool()
# async def get_cypher_query(question: str) -> str: 
#     """Given a question generate a cypher query to fetch data from graph DB.
    
#     Args:
#         question: user question
#     """


# @mcp.tool()
# async def get_cypher_query(question: str, node_names: list,unique_property_values: list, neo4j_schema: str) -> str: 
#     """Given a question, unique_property_values and neo4j_schema, generate a cypher query to fetch data from graph DB.

#     Args:
#         question: user question
#         node_names: graph node names
#         unique_property_values: unique value of each property of nodes
#         neo4j_schema: graph node schema details
#     """

#     logger.info("\nget_cypher_query: \n")
#     logger.debug("question: {}\n".format(question))
#     logger.debug("node_names: {}\n".format(node_names))
#     logger.debug("unique_property_values: {}\n".format(unique_property_values))
#     logger.debug("neo4j_schema: {}\n".format(neo4j_schema))

#     output=await utils.make_API_call_to_CCow({
#         "user_question": question,
#         "node_data": {
#             "node_names": node_names,
#             "unique_property_values": unique_property_values,
#             "neo4j_schema": neo4j_schema
#         }
#     },"generate_cypher_query")
#     logger.debug("output: {}\n".format(output))

#     return output["query"]


# @mcp.tool()
# async def run_cypher_query(question: str) -> str: 
#     """Given a question, execute a cypher query to fetch data from graph DB.

#     Args:
#         question: user question
#     """

#     query="MATCH (c:Control)-[:HAS_EVIDENCE]->(e:Evidence) RETURN count(e) AS evidenceCount"



# @mcp.tool()
# async def write_to_file(data: str) -> str: 
#     """Save user question to file.

#     Args:
#         question: user question


#     """
#     with open("/Users/raja/projects/continube/ComplianceCow/src/cowmcpservice/data.txt", "a") as f:
#         f.write("question: {}\n".format(data))
#     return "executed"


@mcp.prompt()
async def generate_chart_prompt() -> list[str]:
    logger.info("generate_chart_prompt: \n")
    return [
        {
            "role": "user",
            "content":f"Generate a chart with "
                f"Compliance Overview section containing Total controls; Controls Status: each status"
                f"Progress bar chart for 'controlAssignmentStatus'"
                f"Fetch dashboard data for latest quarterly"
                # f"show 'Completed' status in orange color"
                f"for these user data."
        }
    ]


if __name__ == "__main__":
    port=os.environ.get('CCOW_MCP_SERVER_PORT',"")
    portInInt=0

    try:
        portInInt = int(port)
    except ValueError:
        print(f"Environment variable 'CCOW_MCP_SERVER_PORT' is not a valid integer: {port}")
    
    # Initialize and run the server
    
    if portInInt<1:
        try:
            mcp.run(transport='stdio')
        except KeyboardInterrupt:
            print("\nExiting due to Ctrl+C")
            exit(0)
    else :
        mcp.settings.host="0.0.0.0"
        mcp.settings.port=portInInt
        mcp.settings.auth=AuthSettings(issuer_url=host)
        mcp._auth_server_provider=CCowOAuthProvider()
        mcp.run(transport='sse')




