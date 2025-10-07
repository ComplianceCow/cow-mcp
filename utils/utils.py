from typing import Any
import httpx
import traceback
from utils.debug import logger
from constants.constants import headers, host

# from mcpconfig import get_access_token
from mcp.server.auth.middleware.auth_context import get_access_token
from mcptypes.error_type import ErrorVO,ErrorResponseVO,ErrorWorkflowVO


async def make_API_call_to_CCow_and_get_response(uriSuffix: str,method: str,request_body: dict | list | str = None, type: str = "json",return_raw: bool = False):
    logger.info(f"uriSuffix: {uriSuffix}, Method: {method}, Type: {type}")
    async with httpx.AsyncClient() as client:
        try:
            requestHeader=headers.copy()
            accessToken=get_access_token()
            if accessToken is not None:
                requestHeader=headers.copy()
                requestHeader["Authorization"]=accessToken.token
            if accessToken:
                requestHeader["Authorization"] = accessToken.token

            if type == "yaml":
                requestHeader["Content-Type"] = "application/x-yaml"
            else:
                requestHeader["Content-Type"] = "application/json"

            method = method.upper()
            request_args = {"url": host + uriSuffix, "headers": requestHeader,"timeout": 60.0}

            if method in ["GET", "DELETE"]:
                if isinstance(request_body, dict):
                    request_args["params"] = request_body
            else:
                if type == "yaml":
                    request_args["data"] = request_body
                else:
                    request_args["json"] = request_body

            response = await client.request(method, **request_args)
            if return_raw:
                return response
            if response.status_code < 200 or response.status_code > 299:
                error = response.json()
                logger.error("make_API_call_to_CCow_and_get_response unexpected error: {}\n".format(error))
                if ("Message" in error and "Description" in error ):
                    return ErrorResponseVO(Message=error.get("Message"),Description=error.get("Description")).model_dump()
                if ("ErrorMessage" in error):
                    return ErrorVO(error=error.get("ErrorMessage")).model_dump()
                if ("Message" in error and "ErrorDetails" in error ):
                    return ErrorWorkflowVO(Message=error.get("Message"),ErrorDetails=error.get("ErrorDetails")).model_dump()
                return ErrorVO(error=f"Unexpected response status: {response.status_code}").model_dump()
            if response.content:
                return response.json()
            else:
                return {}
        except httpx.TimeoutException:
            logger.error(f"make_API_call_to_CCow_and_get_response error: Request timed out after 60 seconds for uriSuffix: {uriSuffix}")
            return "Facing error : Request timed out."
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error("make_API_call_to_CCow_and_get_response error: {}\n".format(e))
            return "Facing error  :  "+str(e)


async def make_API_call_to_CCow(request_body: dict | str,uriSuffix: str, type: str = "json") -> dict[str, Any] | str  :
    logger.info(f"uriSuffix: {uriSuffix}")
    async with httpx.AsyncClient() as client:
        try:
            requestHeader=headers
            accessToken=get_access_token()
            if accessToken is not None:
                requestHeader=headers.copy()
                requestHeader["Authorization"]=accessToken.token

            response = None
            if type=="yaml":
                requestHeader["Content-Type"] = "application/x-yaml"
                response = await client.post(host+uriSuffix,data=request_body, headers=requestHeader, timeout=60.0)
            else:
            # response = await client.post("http://localhost:14600/v1/llm/"+uriSuffix,json=request_body, headers={"Authorization": "db4f39f2-45b1-445c-9b05-5cd4d5f04990"}, timeout=300.0)
                response = await client.post(host+uriSuffix,json=request_body, headers=requestHeader, timeout=60.0)
            if response.status_code < 200 or response.status_code > 299:
                error = response.json()
                logger.error("make_API_call_to_CCow unexpected status code: error: {}\n".format(error))
                if (("Description" in error and "No recent run for ccf plans" in error["Description"])
                    or ( "description" in error  and "No recent run for ccf plans" in error["description"])):
                    return ErrorVO(error="NO_DATA_FOUND").model_dump()
                return ErrorVO(error=f"Unexpected response status: {response.status_code}").model_dump()
            return response.json()
        except httpx.TimeoutException:
            logger.error(f"make_API_call_to_CCow error: Request timed out after 60 seconds for uriSuffix: {uriSuffix}")
            return "Facing error : Request timed out."
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error("make_API_call_to_CCow error: {}\n".format(e))
            return "Facing error  :  "+str(e)

async def make_GET_API_call_to_CCow(uriSuffix: str) -> dict[str, Any] | str  :
    logger.info(f"uriSuffix: {uriSuffix}")
    async with httpx.AsyncClient() as client:
        try:
            requestHeader=headers
            accessToken=get_access_token()
            if accessToken is not None:
                requestHeader=headers.copy()
                requestHeader["Authorization"]=accessToken.token
            # response = await client.post("http://localhost:14600/v1/llm/"+uriSuffix,json=request_body, headers={"Authorization": "db4f39f2-45b1-445c-9b05-5cd4d5f04990"}, timeout=300.0)
            response = await client.get(host+uriSuffix, headers=requestHeader, timeout=60.0)
            if response.status_code < 200 or response.status_code > 299:
                logger.error("make_GET_API_call_to_CCow unexpected status code: error: {}\n".format(response.json()))
                return ErrorVO(error=f"Unexpected response status: {response.status_code}").model_dump()
            return response.json()
        except httpx.TimeoutException:
            logger.error(f"make_GET_API_call_to_CCow error: Request timed out after 60 seconds for uriSuffix: {uriSuffix}")
            return "Facing error : Request timed out."
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error("make_GET_API_call_to_CCow error: {}\n".format(e))
            return "Facing error  :  "+str(e)
        
        
def formatChecks (data: dict) -> dict:
    if data is not None and 'items' in data:
        for index, item in enumerate(data["items"]):
            newItem={}
            copyValue(item,newItem,"name")
            copyValue(item,newItem,"description")
            copyValue(item,newItem,"rule")
            copyValue(item,newItem,"activationStatus")
            copyValue(item,newItem,"priority")
            copyValue(item,newItem,"complianceStatus")
            copyValue(item,newItem,"compliancePCT")
            data["items"][index]=newItem
    return data

def formatResources (data: dict, includeChecks: bool) -> dict:
    if data is not None and 'items' in data:
        for index, item in enumerate(data["items"]):
            newItem={}
            copyValue(item,newItem,"name")
            copyValue(item,newItem,"resourceType")
            copyValue(item,newItem,"complianceStatus")
            if includeChecks:
                copyValue(item,newItem,"checks")
            elif 'checks' in item:
                newItem["checksCount"]=len(item["checks"])
            if 'checks' in newItem:
                for ci, cItem in enumerate(newItem["checks"]):
                    newCheckItem={}
                    copyValue(cItem,newCheckItem,"name")
                    copyValue(cItem,newCheckItem,"description")
                    copyValue(cItem,newCheckItem,"resourceComplianceStatus","complianceStatus")
                    copyValue(cItem,newCheckItem,"controlName")
                    copyValue(cItem,newCheckItem,"rule")
                    copyValue(cItem,newCheckItem,"activationStatus")
                    copyValue(cItem,newCheckItem,"priority")
                    newItem["checks"][ci]=newCheckItem
                
            data["items"][index]=newItem
    return data

def trimWorkflowDetails (item: dict, includeSpec: bool=False):
    deleteKey(item,"domainId")
    deleteKey(item,"orgId")
    deleteKey(item,"groupId")
    if not includeSpec:
        deleteKey(item,"spec")
    if "status" in item:
        deleteKey(item["status"],"filePathHash")

def copyValue(src: dict, dest: dict, srcKey: str, destKey: str=""):
    if src is None:
        src= {}
    if dest is None:
        dest= {}
    if destKey=="":
        destKey=srcKey
    if srcKey in src:
        dest[destKey]=src[srcKey]
    return dest

def deleteKey(src: dict,key: str):
    if src is None or str=="":
        logger.debug("delete is empty")
        return
    if key in src:
        del src[key]