import base64
import json
import re
import secrets
import string
from typing import Any, Dict, List, Optional, Tuple, Union

from fastmcp import Context
from constants import constants
from utils import utils
from utils.debug import logger


def sanitize(text: str) -> str:
    """Sanitize string by replacing non-alphanumeric characters with hyphens and stripping excess hyphens."""
    if not text:
        return ""
    sanitized = re.sub(r"[^a-zA-Z0-9]+", "-", str(text).strip())
    return sanitized.strip("-")


def generate_random_alphanumeric_string(length: int = 6) -> str:
    """Generate a random alphanumeric string of given length."""
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def construct_assistant_rule(
    evidence_names: List[Dict[str, str]],
    plan_name: str,
    plan_id: str,
    plan_control_displayable: str,
    rule_name: str = "",
    meaningful_name: str = "",
) -> Dict[str, Any]:
    """Construct rule dictionary payload based on inputs.

    Args:
        evidence_names: List of evidence objects/dicts, each containing evidenceName and columnName.
        plan_name: Name of the plan (plan.Name).
        plan_id: ID of the plan (plan.ID).
        plan_control_displayable: Displayable control name (planControl.Displayable).
        rule_name: Optional explicit rule name. If empty, auto-generated using formula.
        meaningful_name: Optional meaningful name (25-35 characters) for the rule.

    Returns:
        Dictionary representation of the constructed rule payload.
    """
    evidence_items: List[Tuple[str, str]] = [
        (
            str(getattr(item, "evidenceName", None) or (item.get("evidenceName", "") if isinstance(item, dict) else "")).strip(),
            str(getattr(item, "columnName", None) or (item.get("columnName", "") if isinstance(item, dict) else "")).strip(),
        )
        for item in (evidence_names or [])
        if (getattr(item, "evidenceName", None) or (item.get("evidenceName") if isinstance(item, dict) else None))
    ]

    if not rule_name or not str(rule_name).strip():
        random_str = generate_random_alphanumeric_string(6)
        rule_name = f"{sanitize(meaningful_name or plan_name)}ctl{sanitize(plan_control_displayable)}A{sanitize(plan_id)}{random_str}".replace("-", "")
    else:
        rule_name = str(rule_name).strip()

    n = len(evidence_items)
    minio_file_path = "<<MINIO_FILE_PATH>>"
    task_name = "FilterServiceNowEvidence"
    task_purpose = "FilterServiceNowEvidence"
    task_description = "FilterServiceNowEvidence"

    # Construct spec.inputs
    inputs: Dict[str, Any] = {"EntityFilter": {}}
    for ev, col in evidence_items:
        inputs[ev] = minio_file_path
        inputs[f"{ev}_columnname"] = col

    # Construct spec.inputsMeta__
    inputs_meta: List[Dict[str, Any]] = [
        {
            "name": "EntityFilter",
            "dataType": "JSON",
            "repeated": False,
            "defaultValue": [],
            "allowedValues": [],
            "showField": True,
            "required": True,
        }
    ]
    for ev, col in evidence_items:
        inputs_meta.append(
            {
                "name": ev,
                "dataType": "FILE",
                "repeated": False,
                "defaultValue": minio_file_path,
                "allowedValues": [],
                "showField": True,
                "required": False,
            }
        )
        inputs_meta.append(
            {
                "name": f"{ev}_columnname",
                "dataType": "STRING",
                "repeated": False,
                "defaultValue": col,
                "allowedValues": [],
                "showField": True,
                "required": False,
            }
        )

    # Construct spec.outputsMeta__
    outputs_meta: List[Dict[str, Any]] = []
    for ev, _ in evidence_items:
        outputs_meta.append(
            {
                "name": f"{ev}_filtered",
                "dataType": "FILE",
                "description": f"{ev}_filtered",
                "repeated": False,
                "allowedValues": [],
                "defaultValue": minio_file_path,
                "showField": True,
                "required": True,
            }
        )

    # Construct spec.tasks
    tasks: List[Dict[str, Any]] = []
    for i in range(1, n + 1):
        tasks.append(
            {
                "name": task_name,
                "alias": f"t{i}",
                "type": "task",
                "appTags": {
                    "appType": ["nocredapp"],
                    "environment": ["logical"],
                    "execlevel": ["app"],
                },
                "purpose": task_purpose,
                "description": task_description,
            }
        )

    # Construct spec.ioMap
    io_map: List[str] = []
    # 1. EntityFilter input mapping for tasks t1 .. tn
    for i in range(1, n + 1):
        io_map.append(f"t{i}.Input.EntityFilter:=*.Input.EntityFilter")

    # 2. Evidence input mapping for tasks t1 .. tn
    for i, (ev, _) in enumerate(evidence_items, 1):
        io_map.append(f"t{i}.Input.EvidenceFile:=*.Input.{ev}")
        io_map.append(f"t{i}.Input.EntityNameColumn:=*.Input.{ev}_columnname")

    # 3. Output filtered mapping for evidences (FilteredEvidenceFile)
    for i, (ev, _) in enumerate(evidence_items, 1):
        io_map.append(f"*.Output.{ev}_filtered:=t{i}.Output.FilteredEvidenceFile")

    # 4. Final compliance status & log mappings from tn (last task)
    if n > 0:
        last_task_alias = f"t{n}"
        io_map.append(f"*.Output.CompliancePCT_:={last_task_alias}.Output.CompliancePCT_")
        io_map.append(f"*.Output.ComplianceStatus_:={last_task_alias}.Output.ComplianceStatus_")
        io_map.append(f"*.Output.LogFile:={last_task_alias}.Output.LogFile")

    # Assemble complete rule payload structure
    rule_dict: Dict[str, Any] = {
        "apiVersion": "rule.policycow.live/v1alpha1",
        "kind": "rule",
        "meta": {
            "name": rule_name,
            "purpose": rule_name,
            "description": rule_name,
            "labels": {
                "appType": ["nocredapp"],
                "environment": ["logical"],
                "execlevel": ["app"],
            },
        },
        "spec": {
            "inputs": inputs,
            "inputsMeta__": inputs_meta,
            "outputsMeta__": outputs_meta,
            "tasks": tasks,
            "ioMap": io_map,
        },
    }

    return rule_dict


async def get_assessment_details_api(assessment_id: str, ctx: Optional[Context] = None) -> Union[Dict[str, Any], str]:
    """Fetch assessment basic details by assessment ID."""
    url = f"{constants.URL_PLANS}/{assessment_id}?fields=basic"
    logger.info(f"get_assessment_details_api: GET {url}")
    resp = await utils.make_GET_API_call_to_CCow(url, ctx=ctx)
    logger.info(f"get_assessment_details_api response:\n{json.dumps(resp, indent=2) if isinstance(resp, (dict, list)) else resp}")
    return resp


async def get_control_details_api(control_id: str, ctx: Optional[Context] = None) -> Union[Dict[str, Any], str]:
    """Fetch control basic details by control ID."""
    url = f"{constants.URL_PLAN_CONTROLS}/{control_id}?fields=basic"
    logger.info(f"get_control_details_api: GET {url}")
    resp = await utils.make_GET_API_call_to_CCow(url, ctx=ctx)
    logger.info(f"get_control_details_api response:\n{json.dumps(resp, indent=2) if isinstance(resp, (dict, list)) else resp}")
    return resp


async def create_rule_api(rule_payload: Union[Dict[str, Any], str], type: str = "yaml", ctx: Optional[Context] = None) -> Union[Dict[str, Any], str]:
    """Create a new rule via CCow API."""
    url = constants.URL_FETCH_RULES  # /pc-api/v1/rules
    payload_str = json.dumps(rule_payload, indent=2) if isinstance(rule_payload, dict) else str(rule_payload)
    logger.info(f"create_rule_api: POST {url} (type={type})\nPayload:\n{payload_str}")
    resp = await utils.make_API_call_to_CCow(rule_payload, url, type=type, ctx=ctx)
    logger.info(f"create_rule_api response:\n{json.dumps(resp, indent=2) if isinstance(resp, (dict, list)) else resp}")
    return resp



async def publish_rule_api(rule_name: str, cc_rule_name: Optional[str] = None, ctx: Optional[Context] = None) -> Union[Dict[str, Any], str]:
    """Publish a rule via CCow API."""
    url = constants.URL_PUBLISH_RULE 
    payload = {
        "ruleName": rule_name,
        "ccRuleName": cc_rule_name or rule_name,
    }
    logger.info(f"publish_rule_api: POST {url}\nPayload:\n{json.dumps(payload, indent=2)}")
    resp = await utils.make_API_call_to_CCow(payload, url, type="json", ctx=ctx)
    logger.info(f"publish_rule_api response:\n{json.dumps(resp, indent=2) if isinstance(resp, (dict, list)) else resp}")
    return resp


async def link_rule_to_control_api(control_id: str, rule_id: str,  create_evidence: bool = True, create_input: bool = False,  ctx: Optional[Context] = None) -> Union[Dict[str, Any], str]:
    """Link a published rule to a plan control."""
    url = f"{constants.URL_PLAN_CONTROLS}/{control_id}/link-rule"
    payload = {
        "ruleId": rule_id,
        "createEvidence": create_evidence,
        "addAsAssessmentUserInput": create_input,
    }
    logger.info(f"link_rule_to_control_api: POST {url}\nPayload:\n{json.dumps(payload, indent=2)}")
    resp = await utils.make_API_call_to_CCow_and_get_response(url,"POST",payload, ctx=ctx)
    logger.info(f"link_rule_to_control_api response:\n{json.dumps(resp, indent=2) if isinstance(resp, (dict, list)) else resp}")
    return resp


async def get_sample_data_api(
    evidence_id: str,
    entity_filter: Any = "",
    ctx: Optional[Context] = None
) -> Union[Dict[str, Any], str]:
    """Fetch sample data for an evidence: POST /v1/getsampledata"""
    url = constants.URL_GET_SAMPLE_DATA
    payload = {
        "EntityFilter": entity_filter if entity_filter is not None else "",
        "evidenceId": evidence_id,
    }
    logger.info(f"get_sample_data_api: POST {url}\nPayload:\n{json.dumps(payload, indent=2) if isinstance(payload, (dict, list)) else payload}")
    resp = await utils.make_API_call_to_CCow(payload, url, type="json", ctx=ctx)
    logger.info(f"get_sample_data_api response:\n{json.dumps(resp, indent=2) if isinstance(resp, (dict, list)) else resp}")
    return resp


async def get_evidence_data(
    target_evidence_id: str,
    limit: Optional[int] = 3,
    return_all: bool = False,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Fetch evidence data for a given target evidence ID.

    Args:
        target_evidence_id: The ID of the evidence to fetch.
        limit: Optional maximum number of evidence items to return (default: 3). If None or <= 0, returns all items.
        return_all: If True, returns all records without applying any limit.
        ctx: Optional MCP Context.

    Returns:
        Dict containing list of sample items or an error dictionary.
    """
    try:
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
                if not return_all and limit is not None and limit > 0 and len(sample_items) == limit:
                    break

        return {"items": sample_items}

    except Exception as e:
        logger.error("get_evidence_data exception: {}\n".format(e))
        return {"error": "Facing internal error"}
