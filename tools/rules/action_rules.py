from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import os
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, get_type_hints
from urllib.parse import urlparse

import mcptypes.rule_type as vo
from constants import constants
from mcpconfig.config import mcp
from mcptypes import exception
from mcptypes.rule_type import TaskVO
from utils import rule, wsutils
from utils.debug import logger
from fastmcp import Context
from utils import utils
import re

from mcptypes import assets_tools_type as assets_vo
import constants.error_constants as error_constants
import json
from mcptypes.rule_type import CVEEntryVO
import yaml
from mcptypes import action_tool_types as actionvo




@mcp.tool()
def fetch_action_rule_summary( ctx: Context | None = None) -> list[vo.SimplifiedRuleVO] | dict[str, Any]:
    """
    Fetch summary of ACTION rules

    Returns:
        List of simplified ACTION rule objects containing name, purpose, description, and README data.
    """
    try:
        rule_response = rule.fetch_action_rules_api(include_read_me=True, ctx=ctx)
        if not rule_response:
            return {"error": "No action rules found that match the specified criteria."}
        return rule_response
    except Exception as e:
        return {
            "error": f"An error occurred while retrieving action rule summary: {str(e)}"
        }

@mcp.tool(annotations=utils.tool_annotations("List Action Specs", read_only=True))
async def list_action_specs(ctx: Context | None = None) -> actionvo.ActionSpecListVO:
    """
    List action specifications

    Returns:
        ActionSpecListVO containing:
            - items (list[ActionSpecVO]): List of action spec objects.
            - error (str, optional): Error message if request failed.
    """
    try:
        logger.info("list_action_specs: \n")
        params = {
            "isStatusToBeIncluded": True,
            "state": "inactive,active",
        }
        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_ACTION_SPECS, "GET", request_body=params, ctx=ctx
        )
        logger.debug("list_action_specs output: {}\n".format(output))

        error = utils.build_structured_error(output, "list_action_specs")
        if error:
            logger.error("list_action_specs error: {}\n".format(output))
            return actionvo.ActionSpecListVO(error=str(error))

        items: list[actionvo.ActionSpecVO] = []
        if isinstance(output, dict) and "items" in output:
            for item in output["items"]:
                items.append(actionvo.ActionSpecVO.model_validate(item))

        return actionvo.ActionSpecListVO(items=items)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_action_specs error: {}\n".format(e))
        return actionvo.ActionSpecListVO(
            error=f"Unexpected error listing action specs: {e}"
        )

@mcp.tool(annotations=utils.tool_annotations("List Action Deployments", read_only=True))
async def list_action_deployment(
    ctx: Context | None = None,
) -> actionvo.ActionDeploymentListVO:
    """
    List action deployments.

    Returns:
        ActionDeploymentListVO containing:
            - items (list[ActionDeploymentVO]): List of action deployment objects.
            - error (str, optional): Error message if request failed.
    """
    try:
        logger.info("list_action_deployments: \n")
        params = {
            "isStatusToBeIncluded": True,
            "state": "inactive,active",
        }
        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_ACTION_DEPLOYMENTS, "GET", request_body=params, ctx=ctx
        )
        logger.debug("list_action_deployments output: {}\n".format(output))

        error = utils.build_structured_error(output, "list_action_deployments")
        if error:
            logger.error("list_action_deployments error: {}\n".format(output))
            return actionvo.ActionDeploymentListVO(error=str(error))

        items: list[actionvo.ActionDeploymentVO] = []
        if isinstance(output, dict) and "items" in output:
            for item in output["items"]:
                items.append(actionvo.ActionDeploymentVO.model_validate(item))

        return actionvo.ActionDeploymentListVO(items=items)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_action_deployments error: {}\n".format(e))
        return actionvo.ActionDeploymentListVO(
            error=f"Unexpected error listing action deployments: {e}"
        )

@mcp.tool(annotations=utils.tool_annotations("List Action Bindings", read_only=True))
async def list_action_bindings(
    ctx: Context | None = None,
) -> actionvo.ActionBindingListVO:
    """
    List action bindings.

    Returns:
        ActionBindingListVO containing:
            - items (list[ActionBindingVO]): List of action binding objects.
            - error (str, optional): Error message if request failed.
    """
    try:
        logger.info("list_action_bindings: \n")
        params = {
            "isStatusToBeIncluded": True,
            "state": "inactive,active",
        }
        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_ACTION_BINDINGS, "GET", request_body=params, ctx=ctx
        )
        logger.debug("list_action_bindings output: {}\n".format(output))

        error = utils.build_structured_error(output, "list_action_bindings")
        if error:
            logger.error("list_action_bindings error: {}\n".format(output))
            return actionvo.ActionBindingListVO(error=str(error))

        items: list[actionvo.ActionBindingVO] = []
        if isinstance(output, dict) and "items" in output:
            for item in output["items"]:
                items.append(actionvo.ActionBindingVO.model_validate(item))

        return actionvo.ActionBindingListVO(items=items)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_action_bindings error: {}\n".format(e))
        return actionvo.ActionBindingListVO(
            error=f"Unexpected error listing action bindings: {e}"
        )

@mcp.tool(annotations=utils.tool_annotations("List Action Loopbacks", read_only=True))
async def list_action_loopbacks(
    ctx: Context | None = None,
) -> actionvo.ActionLoopbackListVO:
    """
    List action loopbacks.

    Returns:
        ActionLoopbackListVO containing:
            - items (list[ActionLoopbackVO]): List of action loopback objects.
            - error (str, optional): Error message if request failed.
    """
    try:
        logger.info("list_action_loopbacks: \n")
        params = {
            "isStatusToBeIncluded": True,
            "state": "inactive,active",
        }
        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_ACTION_LOOPBACKS, "GET", request_body=params, ctx=ctx
        )
        logger.debug("list_action_loopbacks output: {}\n".format(output))

        error = utils.build_structured_error(output, "list_action_loopbacks")
        if error:
            logger.error("list_action_loopbacks error: {}\n".format(output))
            return actionvo.ActionLoopbackListVO(error=str(error))

        items: list[actionvo.ActionLoopbackVO] = []
        if isinstance(output, dict):
            raw_items = output.get("items", []) if "items" in output else []
            for item in raw_items:
                items.append(actionvo.ActionLoopbackVO.model_validate(item))
        elif isinstance(output, list):
            for item in output:
                items.append(actionvo.ActionLoopbackVO.model_validate(item))

        return actionvo.ActionLoopbackListVO(items=items)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_action_loopbacks error: {}\n".format(e))
        return actionvo.ActionLoopbackListVO(
            error=f"Unexpected error listing action loopbacks: {e}"
        )

@mcp.tool(annotations=utils.tool_annotations("Create Action Spec", read_only=False))
async def create_action_spec(
    specPayload: actionvo.ActionSpecCreatePayloadVO | None = None,
    yamlContent: str = "",
    ctx: Context | None = None,
) -> actionvo.ActionCreateResponseVO:
    """
    Create a new Action Spec.

    Args:
        specPayload (ActionSpecCreatePayloadVO, optional): Structured Pydantic model payload (preferred).
        yamlContent (str, optional): Raw YAML string for action spec.

    Target Rules Enforced:
    1. Assessment: sourceBindings contain `assessmentName`. `controlNumber` & `evidenceName` are empty.
    2. Control: sourceBindings contain `assessmentName`, `controlNumber` (empty string '' = ALL controls). `evidenceName` is empty.
    3. Evidence targets ("Single Evidence Record", "Multiple Evidence Records", "Entire Evidence File"):
        sourceBindings contain `assessmentName`, `controlNumber`, `evidenceName` (empty string '' = ALL evidences).

    Returns:
        ActionCreateResponseVO
    """
    try:
        logger.info("create_action_spec: \n")
        body_yaml = ""
        if specPayload:
            payload_dict = specPayload.model_dump(mode="json", exclude_none=True)
            if "spec" in payload_dict and "target" in payload_dict["spec"]:
                payload_dict["spec"]["target"] = specPayload.spec.target.value
            body_yaml = yaml.dump(payload_dict, sort_keys=False)
        elif yamlContent and yamlContent.strip():
            body_yaml = yamlContent.strip()

        if not body_yaml or not body_yaml.strip():
            return actionvo.ActionCreateResponseVO(
                success=False, error="Either specPayload or yamlContent must be provided."
            )

        logger.debug("create_action_spec payload: {}\n".format(body_yaml))

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_ACTION_SPECS,
            "POST",
            request_body=body_yaml.strip(),
            type="yaml",
            ctx=ctx,
        )

        logger.debug("create_action_spec output: {}\n".format(output))

        error = utils.build_structured_error(output, "create_action_spec")
        if error:
            logger.error("create_action_spec error: {}\n".format(output))
            return actionvo.ActionCreateResponseVO(success=False, error=str(error))

        spec_id = ""
        spec_info = None
        if isinstance(output, dict):
            spec_id = output.get("id", "")
            spec_info = output.get("spec")

        return actionvo.ActionCreateResponseVO(
            success=True,
            id=spec_id,
            spec=spec_info,
            message="Action spec created successfully",
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_action_spec error: {}\n".format(e))
        return actionvo.ActionCreateResponseVO(
            success=False, error=f"Unexpected error creating action spec: {e}"
        )

@mcp.tool(annotations=utils.tool_annotations("Create Action Deployment", read_only=False))
async def create_action_deployment(
    deploymentPayload: actionvo.ActionDeploymentCreatePayloadVO | None = None,
    yamlContent: str = "",
    ctx: Context | None = None,
) -> actionvo.ActionCreateResponseVO:
    """
    Create a new Action Deployment.

    Args:
        deploymentPayload (ActionDeploymentCreatePayloadVO, optional): Structured Pydantic model payload (preferred).
        yamlContent (str, optional): Raw YAML string for action deployment.

    Returns:
        ActionCreateResponseVO
    """
    try:
        logger.info("create_action_deployment: \n")
        body_yaml = ""
        if deploymentPayload:
            body_yaml = yaml.dump(deploymentPayload.model_dump(mode="json", exclude_none=True), sort_keys=False)
        elif yamlContent and yamlContent.strip():
            body_yaml = yamlContent.strip()

        if not body_yaml or not body_yaml.strip():
            return actionvo.ActionCreateResponseVO(
                success=False, error="Either deploymentPayload or yamlContent must be provided."
            )

        logger.debug("create_action_deployment payload: {}\n".format(body_yaml))

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_ACTION_DEPLOYMENTS,
            "POST",
            request_body=body_yaml.strip(),
            type="yaml",
            ctx=ctx,
        )

        logger.debug("create_action_deployment output: {}\n".format(output))

        error = utils.build_structured_error(output, "create_action_deployment")
        if error:
            logger.error("create_action_deployment error: {}\n".format(output))
            return actionvo.ActionCreateResponseVO(success=False, error=str(error))

        dep_id = ""
        spec_info = None
        if isinstance(output, dict):
            dep_id = output.get("id", "")
            spec_info = output.get("spec")

        return actionvo.ActionCreateResponseVO(
            success=True,
            id=dep_id,
            spec=spec_info,
            message="Action deployment created successfully",
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_action_deployment error: {}\n".format(e))
        return actionvo.ActionCreateResponseVO(
            success=False, error=f"Unexpected error creating action deployment: {e}"
        )

@mcp.tool(annotations=utils.tool_annotations("Create Action Binding", read_only=False))
async def create_action_binding(
    bindingPayload: actionvo.ActionBindingCreatePayloadVO | None = None,
    yamlContent: str = "",
    ctx: Context | None = None,
) -> actionvo.ActionCreateResponseVO:
    """
    Create a new Action Binding in ComplianceCow.

    Args:
        bindingPayload (ActionBindingCreatePayloadVO, optional): Structured Pydantic model payload (preferred).
        yamlContent (str, optional): Raw YAML string for action binding.

    Returns:
        ActionCreateResponseVO
    """
    try:
        logger.info("create_action_binding: \n")
        body_yaml = ""
        if bindingPayload:
            body_yaml = yaml.dump(bindingPayload.model_dump(mode="json", exclude_none=True), sort_keys=False)
        elif yamlContent and yamlContent.strip():
            body_yaml = yamlContent.strip()

        if not body_yaml or not body_yaml.strip():
            return actionvo.ActionCreateResponseVO(
                success=False, error="Either bindingPayload or yamlContent must be provided."
            )

        logger.debug("create_action_binding payload: {}\n".format(body_yaml))

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_ACTION_BINDINGS,
            "POST",
            request_body=body_yaml.strip(),
            type="yaml",
            ctx=ctx,
        )

        logger.debug("create_action_binding output: {}\n".format(output))

        error = utils.build_structured_error(output, "create_action_binding")
        if error:
            logger.error("create_action_binding error: {}\n".format(output))
            return actionvo.ActionCreateResponseVO(success=False, error=str(error))

        binding_id = ""
        spec_info = None
        if isinstance(output, dict):
            binding_id = output.get("id", "")
            spec_info = output.get("spec")

        return actionvo.ActionCreateResponseVO(
            success=True,
            id=binding_id,
            spec=spec_info,
            message="Action binding created successfully",
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_action_binding error: {}\n".format(e))
        return actionvo.ActionCreateResponseVO(
            success=False, error=f"Unexpected error creating action binding: {e}"
        )

@mcp.tool(annotations=utils.tool_annotations("Create Action Loopback", read_only=False))
async def create_action_loopback(
    loopbackPayload: actionvo.ActionLoopbackCreatePayloadVO | None = None,
    yamlContent: str = "",
    ctx: Context | None = None,
) -> actionvo.ActionCreateResponseVO:
    """
    Create a new Action Loopback in ComplianceCow (supports both 'polling' and 'push' loopback types).

    Args:
        loopbackPayload (ActionLoopbackCreatePayloadVO, optional): Structured Pydantic model payload (preferred).
        yamlContent (str, optional): Raw YAML string for action loopback.

    Returns:
        ActionCreateResponseVO
    """
    try:
        logger.info("create_action_loopback: \n")
        body_yaml = ""
        if loopbackPayload:
            payload_dict = loopbackPayload.model_dump(mode="json", exclude_none=True)
            if "spec" in payload_dict and "loopBackType" in payload_dict["spec"]:
                payload_dict["spec"]["loopBackType"] = loopbackPayload.spec.loopBackType.value
            body_yaml = yaml.dump(payload_dict, sort_keys=False)
        elif yamlContent and yamlContent.strip():
            body_yaml = yamlContent.strip()

        if not body_yaml or not body_yaml.strip():
            return actionvo.ActionCreateResponseVO(
                success=False, error="Either loopbackPayload or yamlContent must be provided."
            )

        logger.debug("create_action_loopback payload: {}\n".format(body_yaml))

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_ACTION_LOOPBACKS,
            "POST",
            request_body=body_yaml.strip(),
            type="yaml",
            ctx=ctx,
        )

        logger.debug("create_action_loopback output: {}\n".format(output))

        error = utils.build_structured_error(output, "create_action_loopback")
        if error:
            logger.error("create_action_loopback error: {}\n".format(output))
            return actionvo.ActionCreateResponseVO(success=False, error=str(error))

        lb_id = ""
        spec_info = None
        if isinstance(output, dict):
            lb_id = output.get("id", "")
            spec_info = output.get("spec")

        return actionvo.ActionCreateResponseVO(
            success=True,
            id=lb_id,
            spec=spec_info,
            message="Action loopback created successfully",
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_action_loopback error: {}\n".format(e))
        return actionvo.ActionCreateResponseVO(
            success=False, error=f"Unexpected error creating action loopback: {e}"
        )

@mcp.tool(annotations=utils.tool_annotations("Update Action Spec", read_only=False))
async def update_action_spec(
    id: str,
    specPayload: actionvo.ActionSpecCreatePayloadVO | None = None,
    yamlContent: str = "",
    ctx: Context | None = None,
) -> actionvo.ActionCreateResponseVO:
    """
    Update an existing Action Spec.

    Args:
        id (str): Action Spec ID to update.
        specPayload (ActionSpecCreatePayloadVO, optional): Structured Pydantic model payload (preferred).
        yamlContent (str, optional): Raw YAML string for action spec.

    Returns:
        ActionCreateResponseVO
    """
    try:
        logger.info("update_action_spec: \n")
        if not id or not str(id).strip():
            return actionvo.ActionCreateResponseVO(
                success=False, error="id is required for update_action_spec."
            )

        body_yaml = ""
        if specPayload:
            payload_dict = specPayload.model_dump(mode="json", exclude_none=True)
            if "spec" in payload_dict and "target" in payload_dict["spec"]:
                payload_dict["spec"]["target"] = specPayload.spec.target.value
            body_yaml = yaml.dump(payload_dict, sort_keys=False)
        elif yamlContent and yamlContent.strip():
            body_yaml = yamlContent.strip()

        if not body_yaml or not body_yaml.strip():
            return actionvo.ActionCreateResponseVO(
                success=False, error="Either specPayload or yamlContent must be provided."
            )

        url = f"{constants.URL_ACTION_SPECS}/{str(id).strip()}"
        output = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "PUT",
            request_body=body_yaml.strip(),
            type="yaml",
            ctx=ctx,
        )

        logger.debug("update_action_spec output: {}\n".format(output))

        error = utils.build_structured_error(output, "update_action_spec")
        if error:
            logger.error("update_action_spec error: {}\n".format(output))
            return actionvo.ActionCreateResponseVO(success=False, error=str(error))

        spec_id = ""
        spec_info = None
        if isinstance(output, dict):
            spec_id = output.get("id", str(id).strip())
            spec_info = output.get("spec")

        target_id = spec_id if spec_id else str(id).strip()
        refresh_url = f"{constants.URL_ACTION_SPECS}/{target_id}/status/refresh"
        refresh_output = await utils.make_API_call_to_CCow_and_get_response(
            refresh_url,
            "POST",
            request_body={},
            ctx=ctx,
        )
        logger.debug("update_action_spec refresh output: {}\n".format(refresh_output))

        return actionvo.ActionCreateResponseVO(
            success=True,
            id=spec_id,
            spec=spec_info,
            message="Action spec updated successfully",
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_action_spec error: {}\n".format(e))
        return actionvo.ActionCreateResponseVO(
            success=False, error=f"Unexpected error updating action spec: {e}"
        )

@mcp.tool(annotations=utils.tool_annotations("Update Action Deployment", read_only=False))
async def update_action_deployment(
    id: str,
    deploymentPayload: actionvo.ActionDeploymentCreatePayloadVO | None = None,
    yamlContent: str = "",
    ctx: Context | None = None,
) -> actionvo.ActionCreateResponseVO:
    """
    Update an existing Action Deployment.

    Args:
        id (str): Action Deployment ID to update.
        deploymentPayload (ActionDeploymentCreatePayloadVO, optional): Structured Pydantic model payload (preferred).
        yamlContent (str, optional): Raw YAML string for action deployment.

    Returns:
        ActionCreateResponseVO
    """
    try:
        logger.info("update_action_deployment: \n")
        if not id or not str(id).strip():
            return actionvo.ActionCreateResponseVO(
                success=False, error="id is required for update_action_deployment."
            )

        body_yaml = ""
        if deploymentPayload:
            body_yaml = yaml.dump(deploymentPayload.model_dump(mode="json", exclude_none=True), sort_keys=False)
        elif yamlContent and yamlContent.strip():
            body_yaml = yamlContent.strip()

        if not body_yaml or not body_yaml.strip():
            return actionvo.ActionCreateResponseVO(
                success=False, error="Either deploymentPayload or yamlContent must be provided."
            )

        url = f"{constants.URL_ACTION_DEPLOYMENTS}/{str(id).strip()}"
        output = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "PUT",
            request_body=body_yaml.strip(),
            type="yaml",
            ctx=ctx,
        )

        logger.debug("update_action_deployment output: {}\n".format(output))

        error = utils.build_structured_error(output, "update_action_deployment")
        if error:
            logger.error("update_action_deployment error: {}\n".format(output))
            return actionvo.ActionCreateResponseVO(success=False, error=str(error))

        dep_id = ""
        spec_info = None
        if isinstance(output, dict):
            dep_id = output.get("id", str(id).strip())
            spec_info = output.get("spec")

        target_id = dep_id if dep_id else str(id).strip()
        refresh_url = f"{constants.URL_ACTION_DEPLOYMENTS}/{target_id}/status/refresh"
        refresh_output = await utils.make_API_call_to_CCow_and_get_response(
            refresh_url,
            "POST",
            request_body={},
            ctx=ctx,
        )
        logger.debug("update_action_deployment refresh output: {}\n".format(refresh_output))

        return actionvo.ActionCreateResponseVO(
            success=True,
            id=dep_id,
            spec=spec_info,
            message="Action deployment updated successfully",
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_action_deployment error: {}\n".format(e))
        return actionvo.ActionCreateResponseVO(
            success=False, error=f"Unexpected error updating action deployment: {e}"
        )

@mcp.tool(annotations=utils.tool_annotations("Update Action Binding", read_only=False))
async def update_action_binding(
    id: str,
    bindingPayload: actionvo.ActionBindingCreatePayloadVO | None = None,
    yamlContent: str = "",
    ctx: Context | None = None,
) -> actionvo.ActionCreateResponseVO:
    """
    Update an existing Action Binding.

    Args:
        id (str): Action Binding ID to update.
        bindingPayload (ActionBindingCreatePayloadVO, optional): Structured Pydantic model payload (preferred).
        yamlContent (str, optional): Raw YAML string for action binding.

    Returns:
        ActionCreateResponseVO
    """
    try:
        logger.info("update_action_binding: \n")
        if not id or not str(id).strip():
            return actionvo.ActionCreateResponseVO(
                success=False, error="id is required for update_action_binding."
            )

        body_yaml = ""
        if bindingPayload:
            body_yaml = yaml.dump(bindingPayload.model_dump(mode="json", exclude_none=True), sort_keys=False)
        elif yamlContent and yamlContent.strip():
            body_yaml = yamlContent.strip()

        if not body_yaml or not body_yaml.strip():
            return actionvo.ActionCreateResponseVO(
                success=False, error="Either bindingPayload or yamlContent must be provided."
            )

        url = f"{constants.URL_ACTION_BINDINGS}/{str(id).strip()}"
        output = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "PUT",
            request_body=body_yaml.strip(),
            type="yaml",
            ctx=ctx,
        )

        logger.debug("update_action_binding output: {}\n".format(output))

        error = utils.build_structured_error(output, "update_action_binding")
        if error:
            logger.error("update_action_binding error: {}\n".format(output))
            return actionvo.ActionCreateResponseVO(success=False, error=str(error))

        binding_id = ""
        spec_info = None
        if isinstance(output, dict):
            binding_id = output.get("id", str(id).strip())
            spec_info = output.get("spec")

        target_id = binding_id if binding_id else str(id).strip()
        refresh_url = f"{constants.URL_ACTION_BINDINGS}/{target_id}/status/refresh"
        refresh_output = await utils.make_API_call_to_CCow_and_get_response(
            refresh_url,
            "POST",
            request_body={},
            ctx=ctx,
        )
        logger.debug("update_action_binding refresh output: {}\n".format(refresh_output))

        return actionvo.ActionCreateResponseVO(
            success=True,
            id=binding_id,
            spec=spec_info,
            message="Action binding updated successfully",
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_action_binding error: {}\n".format(e))
        return actionvo.ActionCreateResponseVO(
            success=False, error=f"Unexpected error updating action binding: {e}"
        )

@mcp.tool(annotations=utils.tool_annotations("Update Action Loopback", read_only=False))
async def update_action_loopback(
    id: str,
    loopbackPayload: actionvo.ActionLoopbackCreatePayloadVO | None = None,
    yamlContent: str = "",
    ctx: Context | None = None,
) -> actionvo.ActionCreateResponseVO:
    """
    Update an existing Action Loopback.

    Args:
        id (str): Action Loopback ID to update.
        loopbackPayload (ActionLoopbackCreatePayloadVO, optional): Structured Pydantic model payload (preferred).
        yamlContent (str, optional): Raw YAML string for action loopback.

    Returns:
        ActionCreateResponseVO
    """
    try:
        logger.info("update_action_loopback: \n")
        if not id or not str(id).strip():
            return actionvo.ActionCreateResponseVO(
                success=False, error="id is required for update_action_loopback."
            )

        body_yaml = ""
        if loopbackPayload:
            payload_dict = loopbackPayload.model_dump(mode="json", exclude_none=True)
            if "spec" in payload_dict and "loopBackType" in payload_dict["spec"]:
                payload_dict["spec"]["loopBackType"] = loopbackPayload.spec.loopBackType.value
            body_yaml = yaml.dump(payload_dict, sort_keys=False)
        elif yamlContent and yamlContent.strip():
            body_yaml = yamlContent.strip()

        if not body_yaml or not body_yaml.strip():
            return actionvo.ActionCreateResponseVO(
                success=False, error="Either loopbackPayload or yamlContent must be provided."
            )

        url = f"{constants.URL_ACTION_LOOPBACKS}/{str(id).strip()}"
        output = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "PUT",
            request_body=body_yaml.strip(),
            type="yaml",
            ctx=ctx,
        )

        logger.debug("update_action_loopback output: {}\n".format(output))

        error = utils.build_structured_error(output, "update_action_loopback")
        if error:
            logger.error("update_action_loopback error: {}\n".format(output))
            return actionvo.ActionCreateResponseVO(success=False, error=str(error))

        lb_id = ""
        spec_info = None
        if isinstance(output, dict):
            lb_id = output.get("id", str(id).strip())
            spec_info = output.get("spec")

        target_id = lb_id if lb_id else str(id).strip()
        refresh_url = f"{constants.URL_ACTION_LOOPBACKS}/{target_id}/status/refresh"
        refresh_output = await utils.make_API_call_to_CCow_and_get_response(
            refresh_url,
            "POST",
            request_body={},
            ctx=ctx,
        )
        logger.debug("update_action_loopback refresh output: {}\n".format(refresh_output))

        return actionvo.ActionCreateResponseVO(
            success=True,
            id=lb_id,
            spec=spec_info,
            message="Action loopback updated successfully",
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_action_loopback error: {}\n".format(e))
        return actionvo.ActionCreateResponseVO(
            success=False, error=f"Unexpected error updating action loopback: {e}"
        )

@mcp.tool(annotations=utils.tool_annotations("Fetch Action Content by Hash", read_only=True))
async def fetch_action_content_by_hash(
    filePathHash: str,
    ctx: Context | None = None,
) -> actionvo.ActionFileContentVO:
    """
    Fetch action YAML file content using its `filePathHash`.

    Args:
        filePathHash (str): File path hash returned in action item listing.

    Returns:
        ActionFileContentVO containing:
            - success (bool): True if retrieved and decoded successfully.
            - yamlContent (str): Decoded raw YAML string.
            - contentDict (dict): Parsed dictionary structure of the YAML.
            - error (str, optional): Error message if failed.
    """
    try:
        logger.info("fetch_action_content_by_hash: \n")
        if not filePathHash or not str(filePathHash).strip():
            return actionvo.ActionFileContentVO(
                success=False, error="filePathHash is required."
            )

        hash_val = str(filePathHash).strip()
        url = f"{constants.URL_FETCH_FILE_BY_HASH}/{hash_val}"

        output = await utils.make_API_call_to_CCow_and_get_response(
            url, "GET", ctx=ctx
        )
        logger.debug("fetch_action_content_by_hash output: {}\n".format(output))

        error = utils.build_structured_error(output, "fetch_action_content_by_hash")
        if error:
            logger.error("fetch_action_content_by_hash error: {}\n".format(output))
            return actionvo.ActionFileContentVO(success=False, error=str(error))

        if isinstance(output, dict) and "FileContent" in output:
            file_content_b64 = output.get("FileContent", "")
            decoded_bytes = base64.b64decode(file_content_b64)
            yaml_str = decoded_bytes.decode("utf-8")
            content_dict = None
            try:
                content_dict = yaml.safe_load(yaml_str)
            except Exception as ye:
                logger.error(f"Failed to parse YAML string: {ye}")

            return actionvo.ActionFileContentVO(
                success=True,
                contentDict=content_dict,
            )
        else:
            return actionvo.ActionFileContentVO(
                success=False,
                filePathHash=hash_val,
                error="Response does not contain FileContent.",
            )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_action_content_by_hash error: {}\n".format(e))
        return actionvo.ActionFileContentVO(
            success=False,
            filePathHash=filePathHash,
            error=f"Unexpected error fetching action content by hash: {e}",
        )

@mcp.tool()
async def fetch_assessment_leaf_control_evidence(id: str, ctx: Context | None = None) -> dict:
    """
        Get leaf control evidence for given assessment run control id.

        Args:
        - id (str): Assessment control id
        
        Returns:
            - evidences (list[ControlEvidenceVO]): List of control evidences
                - id (str):  Evidence id.
                - name (str): Evidence name.
                - description (str): Evidence description.
                - fileName (str):  File name.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        output=await utils.make_GET_API_call_to_CCow(f"{constants.URL_PLAN_CONTROLS}/{id}", ctx)
        logger.debug("output: {}\n".format(json.dumps(output)))

        if isinstance(output, str) or  "error" in output:
            logger.error("fetch_assessment_leaf_control_evidence error: {}\n".format(output))
            return {"success": False, "error": output}

        evidences = output.get("evidences", [])

        skip_names = {"auditfile", "logfile"}

        control_evidences = [
            {
                "id": evidence.get("id"),
                "name": evidence.get("name"),
                "description": evidence.get("description"),
                "fileName": evidence.get("fileName"),
            }
            for evidence in evidences
            if evidence.get("name", "").lower() not in skip_names
        ]

        return {"success": True, "evidences": control_evidences}

    except Exception as e:
        logger.error("fetch_assessment_run_leaf_control_evidence error: {}\n".format(e))
        return vo.ControlEvidenceListVO(error="Facing internal error")

@mcp.tool()
async def get_sample_evidence_records_in_control(control_id: str, evidence_name: str, ctx: Context | None = None) -> dict[str, Any]:
    """
    Fetch sample evidence records for a given control ID and evidence ID.

    Args:
        control_id: The ID of the plan instance control.
        evidence_id: The ID of the evidence to match and fetch records for.

    Returns:
        Dict containing a list of sample evidence records
    """
    try:
        url = f"{constants.URL_PLAN_INSTANCE_CONTROLS}?control_id={control_id}&page_size=1&page=1"
        output_ctrl = await utils.make_GET_API_call_to_CCow(url, ctx=ctx)

        if isinstance(output_ctrl, str) or "error" in output_ctrl or not isinstance(output_ctrl, dict):
            logger.error("get_sample_evidence_records error fetching plan instance control: {}\n".format(output_ctrl))
            return {"error": "Facing internal error"}

        items = output_ctrl.get("items", [])
        if not items or not isinstance(items, list):
            return {"error": "No data available to display"}

        first_item = items[0]
        evidences = first_item.get("evidences", [])
        if not isinstance(evidences, list):
            return {"error": "No data available to display"}

        target_evidence_id = None
        for ev in evidences:
            if isinstance(ev, dict) and ev.get("name") == evidence_name:
                target_evidence_id = ev.get("id")
                break

        if not target_evidence_id:
            return {"error": "No matching evidence found"}

        data_payload = {
            "evidenceID": target_evidence_id,
            "templateType": "evidence",
            "status": ["active"],
            "returnFormat": "json",
            "isSrcFetchCall": True,
            "isUserPriority": True,
            "considerFileSizeRestriction": True,
            "viewEvidenceFlow": True
        }
        output = await utils.make_API_call_to_CCow(data_payload, constants.URL_DATAHANDLER_FETCH_DATA, ctx=ctx)
        logger.debug("output: {}\n".format(json.dumps(output) if isinstance(output, dict) else output))

        if isinstance(output, str) or (isinstance(output, dict) and "error" in output):
            logger.error("get_sample_evidence_records fetch_evidence_records error: {}\n".format(output))
            return {"error": "Facing internal error"}

        if isinstance(output, dict) and output.get("Message") == "CANNOT_FIND_THE_FILE":
            return {"error": "No data available to display"}

        if not isinstance(output, dict) or "fileBytes" not in output:
            return {"error": "No data available to display"}

        decoded_bytes = base64.b64decode(output["fileBytes"])
        decoded_string = decoded_bytes.decode('utf-8')
        obj_list = json.loads(decoded_string)

        sample_items = []
        if isinstance(obj_list, list):
            for item in obj_list:
                if not isinstance(item, dict):
                    continue
                if "id" not in item:
                    continue
                new_item = {k: v for k, v in item.items() if not k.endswith("__") and k != "id"}
                sample_items.append(new_item)
                if len(sample_items) == 3:
                    break

        return {"items": sample_items}

    except Exception as e:
        logger.error("get_sample_evidence_records exception: {}\n".format(e))
        return {"error": "Facing internal error"}


# Assessment Run tools


@mcp.tool()
async def run_assessment(
    assessment_id: str,
    name: str,
    description: str,
    ctx: Context | None = None
) -> dict:
    """
    Trigger a new assessment run.

    Args:
        assessment_id (str): Assessment (plan) ID.
        name (str): Run name.
        description (str): Run description.
    """
    try:
        logger.info("run_assessment:\n")

        assessment_id = (assessment_id or "").strip()
        name = (name or "").strip()
        description = (description or "").strip()

        err = utils.require_fields(locals(), ["assessment_id", "name", "description"])
        if err:
            return err

        today_date = datetime.now().strftime("%m/%d/%Y")
        payload = {
            "planId": assessment_id,
            "fromDate": today_date,
            "toDate": today_date,
            "tags": {},
            "name": name,
            "description": description,
            "inputs": {},
            "profileId": "",
            "otherInfos": {"disableAutomatedAction": True}
        }
        logger.debug("run_assessment payload: {}\n".format(json.dumps(payload)))

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_INSTANCES, "POST", payload, ctx=ctx
        )
        logger.debug(
            "run_assessment output: {}\n".format(
                json.dumps(output) if isinstance(output, (dict, list)) else output
            )
        )

        error = utils.handle_error_response(output, "run_assessment")
        if error:
            logger.error("run_assessment error: {}\n".format(error))
            return error

        return {
            "success": True,
            "data": {
                "runId": output.get("id", "") if isinstance(output, dict) else "",
                "status": output.get("status", "") if isinstance(output, dict) else "",
                "name": output.get("name", name) if isinstance(output, dict) else name,
                "description": output.get("description", description) if isinstance(output, dict) else description
            }
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("run_assessment error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}

@mcp.tool()
async def get_all_recent_assessment_runs(
    assessmentId: str,
    ctx: Context | None = None
) -> dict:
    """
    Get recent assessment run details (latest 10).

    Context instructions:
    - Use this tool first when user asks for latest/recent metrics.
    - This tool only returns run summary, not metric details.
    - Take `assessmentRunId` from this response and call `get_all_run_metrics`.
    - Prioritize the most recent run item for "latest metrics" questions.

    Args:
        assessmentId (str): Assessment id.
    """
    try:
        logger.info("get_all_recent_run_details:\n")

        assessment_id = (assessmentId or "").strip()
        err = utils.require_fields(locals(), ["assessment_id"])
        if err:
            return err

        url = (
            f"{constants.URL_PLAN_INSTANCES}"
            f"?fields=basic&page=1&page_size=10&plan_id={assessment_id}"
        )
        output = await utils.make_GET_API_call_to_CCow(url, ctx=ctx)
        logger.debug(
            "get_all_recent_run_details output: {}\n".format(
                json.dumps(output) if isinstance(output, (dict, list)) else output
            )
        )

        error = utils.handle_error_response(output, "get_all_recent_run_details")
        if error:
            logger.error("get_all_recent_run_details error: {}\n".format(error))
            return error

        items = output.get("items", []) if isinstance(output, dict) else []
        if not isinstance(items, list):
            items = []

        runs = []
        for item in items:
            if not isinstance(item, dict):
                continue
            runs.append(
                {
                    "assessmentRunId": item.get("id", ""),
                    "name": item.get("name", ""),
                    "runTime": item.get("started", ""),
                    "status": item.get("status", ""),
                }
            )

        return {"success": True, "data": runs}
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_all_recent_run_details error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}

@mcp.tool()
async def get_assessment_run_details(
    assessmentRunId: str,
    assessmentId: str,
    ctx: Context | None = None
) -> dict:
    """
    Get assessment run details.

    Args:
        assessmentRunId (str): Assessment run id.
        assessmentId (str): Assessment id.
    """
    try:
        logger.info("get_assessment_run_details")

        assessment_run_id = (assessmentRunId or "").strip()
        assessment_id = (assessmentId or "").strip()

        err = utils.require_fields(
            locals(),
            ["assessment_run_id", "assessment_id"],
        )
        if err:
            return err

        output, error = await get_assessment_run_controls(
            ctx,
            assessment_run_id,
            basicFields=False,
        )

        if error:
            logger.error(
                "get_assessment_run_details error: %s",
                error,
            )
            return error

        items = output.get("items", []) if isinstance(output, dict) else []

        if not isinstance(items, list):
            items = []

        controls = []

        for control in items:
            if not isinstance(control, dict):
                continue

            evidences = control.get("evidences", [])

            if not isinstance(evidences, list):
                evidences = []

            evidence = []

            for item in evidences:
                if not isinstance(item, dict):
                    continue

                evidence.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                })

            controls.append({
                "id": control.get("id"),
                "name": control.get("name"),
                "description": control.get("description"),
                "complianceStatus": control.get("complianceStatus"),
                "compliancePercentage": control.get("compliancePCT__"),
                "controlNo": control.get("displayable"),
                "evidence": evidence,
            })

        return {
            "success": True,
            "data": {
                "assessmentRunId": assessment_run_id,
                "assessmentId": assessment_id,
                "controls": controls,
            },
        }

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(
            "get_assessment_run_details error: %s",
            e,
        )
        return {
            "success": False,
            "error": f"Unexpected error: {e}",
        }

@mcp.tool()
async def get_run_evidence_data(
    evidenceId: str,
    ctx: Context | None = None,
) -> dict:
    """
    Get sample evidence data for an evidence record.

    This tool fetches the evidence data associated with the given evidence ID
    and returns only the first 3 records.

    Args:
        evidenceId (str): Evidence ID for which the data should be fetched.
        ctx (Context | None): MCP request context.

    Returns:
        dict: A response containing the first 3 evidence records.
    """
    try:
        logger.info("get_run_evidence_data")

        target_evidence_id = (evidenceId or "").strip()

        if not target_evidence_id:
            return {
                "success": False,
                "error": "No evidence ID provided",
            }

        data_payload = {
            "evidenceID": target_evidence_id,
            "templateType": "evidence",
            "status": ["active"],
            "returnFormat": "json",
            "isSrcFetchCall": True,
            "isUserPriority": True,
            "considerFileSizeRestriction": True,
            "viewEvidenceFlow": True,
        }

        output = await utils.make_API_call_to_CCow(
            data_payload,
            constants.URL_DATAHANDLER_FETCH_DATA,
            ctx=ctx,
        )

        logger.debug(
            "get_run_evidence_data output: %s",
            json.dumps(output) if isinstance(output, dict) else output,
        )

        # Handle API errors
        if isinstance(output, str) or (
            isinstance(output, dict) and "error" in output
        ):
            logger.error(
                "get_run_evidence_data fetch error: %s",
                output,
            )
            return {
                "success": False,
                "error": "Facing internal error",
            }

        # Evidence file not found
        if (
            isinstance(output, dict)
            and output.get("Message") == "CANNOT_FIND_THE_FILE"
        ):
            return {
                "success": False,
                "error": "No data available to display",
            }

        # Invalid response
        if not isinstance(output, dict) or "fileBytes" not in output:
            return {
                "success": False,
                "error": "No data available to display",
            }

        try:
            decoded_bytes = base64.b64decode(output["fileBytes"])
            decoded_string = decoded_bytes.decode("utf-8")
            obj_list = json.loads(decoded_string)
        except Exception as e:
            logger.error(
                "get_run_evidence_data decode/parse error: %s",
                e,
            )
            return {
                "success": False,
                "error": "Unable to parse evidence data",
            }

        sample_items = []

        if isinstance(obj_list, list):
            for item in obj_list:
                if not isinstance(item, dict):
                    continue

                if "id" not in item:
                    continue

                new_item = {
                    key: value
                    for key, value in item.items()
                    if not key.endswith("__") and key != "id"
                }

                sample_items.append(new_item)

                # Return only the first 3 records
                if len(sample_items) == 3:
                    break

        return {
            "success": True,
            "data": {
                "items": sample_items,
            },
        }

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(
            "get_run_evidence_data error: %s",
            e,
        )

        return {
            "success": False,
            "error": f"Unexpected error: {e}",
        }


@mcp.tool()
async def add_assessment_input(
    id: str,
    input_key: str,
    value: Any = "",
    input_type: str = "file",
    file_name: str = "",
    description: str = "",
    ctx: Context | None = None
) -> dict[str, Any]:
    """
    Add or update an assessment input.

    Args:
        id: Assessment plan ID.
        input_key: Key name of the input (e.g. 'input1').
        value: Input value or raw file content. Note: For 'file' input_type, this MUST be the raw file content itself (file URLs are NOT supported).
        input_type: Type of input. Supported types: 'string', 'bool', 'file', 'integer', 'float', 'jq_expression', 'sql_expression'.
        file_name: Name of the input file (e.g. 'inputs.yaml'), used when input_type is 'file'.
        description: Optional description for the input.

    Returns:
        Dict containing the status and final API response.
    """
    try:
        supported_types = [
            "string",
            "bool",
            "file",
            "integer",
            "float",
            "jq_expression",
            "sql_expression"
        ]

        norm_type = input_type.lower() if input_type else ""
        if norm_type not in supported_types:
            return {
                "success": False,
                "error": f"Unsupported input_type '{input_type}'. Supported types are: {', '.join(supported_types)}"
            }

        if norm_type == "file":
            init_patch_payload = [
                {
                    "op": "add",
                    "path": f"/inputs/{input_key}",
                    "value": {
                        "type": input_type,
                        "template": None,
                        "isrequired": True,
                        "showfieldinui": True,
                        "format": "",
                        "defaultvalue": "",
                        "description": description or "",
                        "allowedValues": None,
                        "controlInputsMapping": []
                    }
                }
            ]

            logger.debug(f"add_assessment_input step 1 init patch payload: {init_patch_payload}\n")

            resp1 = await utils.make_API_call_to_CCow_and_get_response(
                f"{constants.URL_PLANS}/{id}",
                "PATCH",
                init_patch_payload,
                ctx=ctx
            )

            logger.debug(f"add_assessment_input step 1 init patch resp: {resp1}\n")

            if isinstance(resp1, str) or (isinstance(resp1, dict) and ("error" in resp1 or "ErrorMessage" in resp1 or "ErrorDetails" in resp1)):
                logger.error(f"add_assessment_input step 1 error: {resp1}\n")
                return {"success": False, "error": f"Failed step 1 (create input placeholder): {resp1}"}

            val_str = str(value) if value is not None else ""
            encoded_value = base64.b64encode(val_str.encode('utf-8')).decode('utf-8')

            update_input_payload = {
                "planId": id,
                "inputs": {
                    input_key: {
                        "value": encoded_value,
                        "fileName": file_name
                    }
                }
            }

            logger.debug(f"add_assessment_input step 2 update-input payload: {update_input_payload}\n")

            resp2 = await utils.make_API_call_to_CCow_and_get_response(
                f"{constants.URL_PLANS}/update-input",
                "POST",
                update_input_payload,
                ctx=ctx
            )

            logger.debug(f"add_assessment_input step 2 update-input resp: {resp2}\n")

            if isinstance(resp2, str) or (isinstance(resp2, dict) and ("error" in resp2 or "ErrorMessage" in resp2 or "ErrorDetails" in resp2)):
                logger.error(f"add_assessment_input step 2 error: {resp2}\n")
                return {"success": False, "error": f"Failed step 2 (update-input): {resp2}"}

            file_val = None
            if isinstance(resp2, dict) and "inputs" in resp2 and input_key in resp2["inputs"]:
                file_val = resp2["inputs"][input_key].get("value")

            if not file_val:
                file_val = {
                    "FileName": file_name,
                    "FileContent": None,
                    "FileHash": ""
                }

            final_patch_payload = [
                {
                    "op": "add",
                    "path": f"/inputs/{input_key}",
                    "value": {
                        "type": input_type,
                        "template": None,
                        "isrequired": True,
                        "showfieldinui": True,
                        "format": "",
                        "defaultvalue": file_val,
                        "description": description or "",
                        "allowedValues": None,
                        "controlInputsMapping": []
                    }
                }
            ]

            logger.debug(f"add_assessment_input step 3 final patch payload: {final_patch_payload}\n")

            resp3 = await utils.make_API_call_to_CCow_and_get_response(
                f"{constants.URL_PLANS}/{id}",
                "PATCH",
                final_patch_payload,
                ctx=ctx
            )

            logger.debug(f"add_assessment_input step 3 final patch resp: {resp3}\n")

            if isinstance(resp3, str) or (isinstance(resp3, dict) and ("error" in resp3 or "ErrorMessage" in resp3 or "ErrorDetails" in resp3)):
                logger.error(f"add_assessment_input step 3 error: {resp3}\n")
                return {"success": False, "error": f"Failed step 3 (final patch): {resp3}"}

            return {
                "success": True,
                "plan_id": id,
                "input_key": input_key,
            }
        else:
            # Parse defaultvalue based on input type
            default_val: Any = value
            if norm_type == "bool":
                if isinstance(value, bool):
                    default_val = value
                elif isinstance(value, str):
                    default_val = value.lower() in ("true")
                else:
                    default_val = bool(value)
            elif norm_type == "integer":
                if isinstance(value, int):
                    default_val = value
                else:
                    try:
                        default_val = int(value)
                    except (ValueError, TypeError):
                        default_val = value
            elif norm_type == "float":
                if isinstance(value, (float, int)):
                    default_val = float(value)
                else:
                    try:
                        default_val = float(value)
                    except (ValueError, TypeError):
                        default_val = value

            patch_payload = [
                {
                    "op": "add",
                    "path": f"/inputs/{input_key}",
                    "value": {
                        "type": input_type,
                        "template": None,
                        "isrequired": True,
                        "showfieldinui": True,
                        "format": "",
                        "defaultvalue": default_val,
                        "description": description or "",
                        "allowedValues": None,
                        "controlInputsMapping": []
                    }
                }
            ]

            logger.debug(f"add_assessment_input non-file patch payload: {patch_payload}\n")

            resp = await utils.make_API_call_to_CCow_and_get_response(
                f"{constants.URL_PLANS}/{id}",
                "PATCH",
                patch_payload,
                ctx=ctx
            )

            logger.debug(f"add_assessment_input non-file patch resp: {resp}\n")

            if isinstance(resp, str) or (isinstance(resp, dict) and ("error" in resp or "ErrorMessage" in resp or "ErrorDetails" in resp)):
                logger.error(f"add_assessment_input non-file error: {resp}\n")
                return {"success": False, "error": f"Failed to add/update input '{input_key}': {resp}"}

            return {
                "success": True,
                "plan_id": id,
                "input_key": input_key,
            }

    except Exception as e:
        logger.error(f"add_assessment_input exception: {e}\n")
        return {"success": False, "error": f"Unexpected error adding assessment input: {str(e)}"}



async def get_assessment_run_controls(ctx: Context, assessment_run_id: str,size: int = 100,leafLevel: bool = True,basicFields: bool = True) -> tuple[dict | None, dict | None]:

    url = f"{constants.URL_PLAN_INSTANCE_CONTROLS}?plan_instance_id={assessment_run_id}&"

    url += f"page=1&page_size={size}&"

    if basicFields:
        url += "fields=basic&"

    if leafLevel:
        url += "is_leaf_control=true&"

    output = await utils.make_API_call_to_CCow_and_get_response(
            url, "GET", ctx=ctx
        )
    
    error = utils.handle_error_response(output,"get_assessment_run_method")

    if error:
        return None, error

    return output, None




