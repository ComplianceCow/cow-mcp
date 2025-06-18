import os
from typing import Any
import httpx
import traceback
from utils.debug import logger
from constants.constants import headers, host

# from mcpconfig import get_access_token
from mcp.server.auth.middleware.auth_context import get_access_token



async def make_API_call_to_CCow(request_body: dict,uriSuffix: str) -> dict[str, Any] | str  :
    logger.info(f"uriSuffix: {uriSuffix}")
    async with httpx.AsyncClient() as client:
        try:
            requestHeader=headers
            accessToken=get_access_token()
            if accessToken is not None:
                requestHeader=headers.copy()
                requestHeader["Authorization"]=accessToken.token
            # response = await client.post("http://localhost:14600/v1/llm/"+uriSuffix,json=request_body, headers={"Authorization": "db4f39f2-45b1-445c-9b05-5cd4d5f04990"}, timeout=300.0)
            response = await client.post(host+uriSuffix,json=request_body, headers=requestHeader, timeout=60.0)
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
            return response.json()
        except httpx.TimeoutException:
            logger.error(f"make_API_call_to_CCow error: Request timed out after 60 seconds for uriSuffix: {uriSuffix}")
            return "Facing error : Request timed out."
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error("make_API_call_to_CCow error: {}\n".format(e))
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