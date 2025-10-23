import json
import logging
import re
import urllib.parse
from enum import Enum
from typing import Union
from urllib.parse import urlencode

import requests
from django.http import JsonResponse
from mcp.server.auth.middleware.auth_context import get_access_token
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout, TooManyRedirects

from constants import constants, cowenums, errordesc
from mcptypes import exception
from utils import rule


class ContentTypeEnum(Enum):
    JSON = "application/json"
    FORM = "application/x-www-form-urlencoded"
    HTML = "text/html"
    XML = "application/xml"
    TEXT = "text/plain"


GET = "GET"
POST = "POST"
PUT = "PUT"
DELETE = "DELETE"
PATCH = "PATCH"

SECURITYCONTEXT = "X-Cow-Security-Context"
AUTHORIZATION = "Authorization"


logger = logging.getLogger(__name__)


def post(path: str = None, params: dict = None, json: dict = None, data: dict = None, files: dict = None, header: dict = None, timeout: int = 600, verify: bool = False, content_type: str = None):
    return make_call_and_process_response(request_method=POST, params=params, path=path, json=json, data=data, files=files, headers=headerbuilder(header), timeout=timeout, verify=verify, content_type=content_type)


def put(path: str = None, params: dict = None, json: dict = None, data: dict = None, files: dict = None, header: dict = None, timeout: int = 600, verify: bool = False, content_type: str = None):
    return make_call_and_process_response(request_method=PUT, params=params, json=json, data=data, files=files, path=path, headers=headerbuilder(header), timeout=timeout, verify=verify, content_type=content_type)


def patch(path: str = None, params: dict = None, json: dict = None, data: dict = None, files: dict = None, header: dict = None, timeout: int = 600, verify: bool = False, content_type: str = None):
    return make_call_and_process_response(request_method=PATCH, params=params, json=json, data=data, files=files, path=path, headers=headerbuilder(header), timeout=timeout, verify=verify, content_type=content_type)


def delete(path: str = None, params: dict = None, json: dict = None, data: dict = None, files: dict = None, header: dict = None, timeout: int = 600, verify: bool = False, content_type: str = None):
    return make_call_and_process_response(request_method=DELETE, params=params, json=json, data=data, files=files, path=path, headers=headerbuilder(header), timeout=timeout, verify=verify, content_type=content_type)


def get(path: str = None, params: dict = None, header: dict = None, timeout: int = 600, verify: bool = False, content_type: str = None):
    return make_call_and_process_response(request_method=GET, params=params, path=path, headers=headerbuilder(header), timeout=timeout, verify=verify, content_type=content_type)


def headerbuilder(header):
    if header:
        if not rule.is_valid_key(header, "Authorization"):
            access_token = get_access_token()
            if access_token and hasattr(access_token, "token"):
                header["Authorization"] = access_token.token
        return header

    return create_header()


def get_json_response(response):
    status = 200
    if "status" in response:
        status = response["status"]
        del response["status"]
    return JsonResponse(response, safe=False, status=status)


def make_call_and_process_response(request_method: str = None, path: str = None, json: dict = None, data: dict = None, files: dict = None, params: dict = None, headers: dict = None, timeout: int = 600, verify: bool = False, content_type: str = None) -> dict:

    return make_call_and_process_response_with_resource_type(request_method=request_method, path=path, json=json, data=data, files=files, params=params, headers=headers, timeout=timeout, verify=verify, content_type=content_type)


def make_call_and_process_response_with_resource_type(request_method: str = None, path: str = None, json: dict = None, data: dict = None, files: dict = None, params: dict = None, headers: dict = None, timeout: int = 600, resource_type: str = None, error_message: str = None, verify: bool = False, content_type: str = "application/json") -> dict:

    error_vo = exception.ErrorVO()

    service_name = get_service_name(path)

    if content_type == ContentTypeEnum.JSON.value:
        json = json
    elif content_type == ContentTypeEnum.FORM.value:
        data = urlencode(data) if data else None
    elif content_type in [ContentTypeEnum.TEXT.value, ContentTypeEnum.XML.value, ContentTypeEnum.HTML.value]:
        data = data if data else None

    try:
        response = requests.request(method=request_method, url=path, json=json, data=data, files=files, headers=headerbuilder(headers), timeout=timeout, params=params, verify=verify)
    except Exception as err:
        logger.error(f"Unable to process request: {err}")
        error_vo.retryable = True
        error_vo.message = camel_to_upper_snake(type(err).__name__)
        error_vo.description = get_friendly_error_message(err, service_name=service_name, resource_type=resource_type)
        error_vo.error_type = cowenums.ErrorType.SYSTEM_ERROR
        raise exception.CCowExceptionVO(status_code=500, error_vo=error_vo)

    if response.status_code == 204 and not response.text:
        return None

    if response.status_code in [200, 201] and not response.text:
        return None

    if not response.text or response.text.strip() == "":
        error_vo.retryable = False
        error_vo.message = "Empty response received"
        error_vo.description = f"No content returned from {path})"
        error_vo.error_type = cowenums.ErrorType.USER_ERROR
        raise exception.CCowExceptionVO(status_code=response.status_code, error_vo=error_vo)

    response_content_type = response.headers.get("Content-Type", "")
    if "application/json" in response_content_type or "application/ld+json" in response_content_type:
        try:
            response_dict = response.json()

        except Exception as err:
            logger.error(f"Unable to convert the response to JSON: {err}")
            error_vo.retryable = True
            if not error_message:
                error_message = f"Unable to convert the response to JSON: {err}"

            error_vo.message = error_message
            error_vo.description = get_resource_specific_error(resource_type=resource_type, error_message=error_message)
            error_vo.error_type = cowenums.ErrorType.SYSTEM_ERROR
            raise exception.CCowExceptionVO(status_code=500, error_vo=error_vo)
    else:
        error_vo.retryable = False
        error_vo.message = "Invalid response Content-Type"
        error_vo.description = f"Expected 'application/json' or 'application/ld+json', but received: '{content_type}'."
        error_vo.error_type = cowenums.ErrorType.USER_ERROR
        raise exception.CCowExceptionVO(status_code=response.status_code, error_vo=error_vo)

    if response.status_code in [200, 201, 204]:
        return response_dict

    error_vo = exception.ErrorVO()

    if isinstance(response_dict, dict):
        error_vo = exception.ErrorVO.from_dict(response_dict)

    logger.error(f"Error while getting responses: {response.status_code}, {response.reason}, {path}")
    match (response.status_code):
        case 500:
            if error_vo and (error_vo.description or error_vo.message) and response.status_code:
                raise exception.CCowExceptionVO(status_code=response.status_code, error_vo=error_vo)
            error_vo.retryable = True
            error_vo.message = errordesc.InternalServerError
            error_vo.description = get_resource_specific_error(resource_type=resource_type, error_message=error_message)
            error_vo.error_type = cowenums.ErrorType.SYSTEM_ERROR
        case 400 | 401 | 403 | 404:
            error_vo.retryable = False
            if error_vo and (error_vo.description or error_vo.message) and response.status_code:
                raise exception.CCowExceptionVO(status_code=response.status_code, error_vo=error_vo)
            error_vo.message = response.reason
            error_vo.description = get_resource_specific_error(resource_type=resource_type, error_message=error_message)
            error_vo.error_type = cowenums.ErrorType.USER_ERROR
        case _:
            error_vo.retryable = True
            error_vo.message = f"Unexpected status code: {response.status_code}"
            error_vo.description = response.reason
            error_vo.error_type = cowenums.ErrorType.UNKNOWN_ERROR

    raise exception.CCowExceptionVO(status_code=response.status_code, error_vo=error_vo)


def get_resource_specific_error(resource_type: str = None, error_message: str = None):
    if resource_type and error_message:
        return f"An error occurred while retrieving the '{resource_type}'. {error_message}"
    if resource_type:
        return f"An error occurred while retrieving the '{resource_type}'"
    return error_message


def get_friendly_error_message(e, service_name: str = None, resource_type: str = None, error_message: str = None):
    if error_message:
        return error_message
    if resource_type:
        return f"An error occurred while retrieving '{resource_type}'"
    if isinstance(e, ConnectionError):
        server_name = "server"
        if service_name:
            server_name = f"'{service_name}'"
        return f"Failed to connect to the {server_name}. Please check your network connection."
    elif isinstance(e, Timeout):
        return "The request timed out. The server may be busy, or your network connection is slow."
    elif isinstance(e, TooManyRedirects):
        return "The request exceeded the maximum number of redirects. The URL might be misconfigured."
    elif isinstance(e, HTTPError):
        return f"HTTP error occurred: {e.response.status_code} - {e.response.reason}"
    elif isinstance(e, RequestException):
        return "An error occurred while making the request. Please try again later."
    else:
        return str(e)


def camel_to_upper_snake(name):
    snake_case = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    upper_snake_case = snake_case.upper()
    return upper_snake_case


def get_service_name(url):
    """Extracts the service name from a URL.

    Args:
      url: The URL to extract the service name from.

    Returns:
      The service name, or None if the URL is invalid or lacks a service name.
    """

    try:
        parsed_url = urllib.parse.urlparse(url)
        netloc = parsed_url.netloc

        if not netloc:
            return None
        service_name, _, _ = netloc.partition(":")
        return service_name
    except ValueError:
        return None


def create_header():

    request_headers = {}
    if constants.basic_auth_flow:
        auth_token = get_auth_token()
        if auth_token:
            newHeader=constants.headers.copy()
            newHeader["Authorization"]= auth_token
            return newHeader

    request_headers = constants.headers.copy()
    access_token = get_access_token()

    if access_token and hasattr(access_token, "token"):
        request_headers["Authorization"] = access_token.token

    return request_headers


def build_api_url(endpoint: str):
    return f"{constants.host}{endpoint}"


def get_auth_token():
    logger.info(f"get_auth_token entered")
    auth_token = constants.cow_cache.get(constants.cid, None)
    if auth_token:
        logger.info(f"got the auth token from cache {auth_token}")
        return auth_token

    payload = {
        "grant_type": "client_credentials",
        "client_id": constants.cid,
        "client_secret": constants.cs,
    }

    auth_reponse = requests.request("POST", build_api_url(endpoint=constants.URL_AUTH_TOKEN_GENERATION), data=payload).json()

    logger.info(f"auth_reponse {auth_reponse}")

    if "tokenType" in auth_reponse and "authToken" in auth_reponse:
        auth_token = f"{auth_reponse['tokenType']} {auth_reponse['authToken']}"
        constants.cow_cache.setdefault(constants.cid, auth_token)
        return auth_token
    return None
