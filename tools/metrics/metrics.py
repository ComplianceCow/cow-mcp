import json
import base64
import asyncio
import random
import re
import string
import traceback
from datetime import datetime
from typing import List

from fastmcp import Context
import yaml
import os

from constants import constants
from mcpconfig.config import mcp
from utils import utils
from utils.debug import logger
from mcptypes import assessment_config_tool_types as assessment_vo
from mcptypes import assets_tools_type as assets_vo

from mcptypes.metrics_tool_types import MetricsSourceSummaryResponseVO, MetricsSourceSummaryVO
import constants.error_constants as error_constants
from mcptypes.graph_tool_types import UniqueNodeDataVO , CypherQueryVO


@mcp.tool()
async def get_metrics_assessment(ctx: Context | None = None) -> dict:
    """
    Get metrics assessment

    Returns:
        - assessments (AssessmentVO): A assessment objects containing:
            - id (str): Unique identifier of the assessment.
            - name (str): Name of the assessment.
            - categoryName (str): Name of the category.
        - error (Optional[str]): An error message if any issues occurred during retrieval.
    
    """
    try:
        logger.info("get_metrics_assessment:\n")

        METRICS_ASSESSMENT_NAME = os.getenv("METRICS_ASSESSMENT_NAME", "Metric Manager").strip()

        METRICS_CATEGORY_NAME = os.getenv("METRICS_CATEGORY_NAME", "Metric Manager").strip()

        url = f"{constants.URL_PLANS}?fields=basic&name={METRICS_ASSESSMENT_NAME}"
        resp = await utils.make_GET_API_call_to_CCow(url, ctx=ctx)
        logger.debug(
            "get_metrics_assessment output: {}\n".format(
                json.dumps(resp) if isinstance(resp, (dict, list)) else resp
            )
        )

        error = utils.handle_error_response(resp,"get_metrics_assessment")
        if error:
            logger.error("get_metrics_assessment error: {}\n".format(error))
            return error

        if isinstance(resp, dict) and "items" in resp:
            items = resp["items"]
        else:
            items = []

        first_item = next(iter(items), None)

        assessment = None
        if first_item is not None:
            assessment = assessment_vo.AssessmentVO(
                id=first_item.get("id"),
                name=first_item.get("name"),
                categoryName=first_item.get("categoryName")
            )
        
        logger.debug(f"get_metrics_assessment: assessment:\n{assessment}")    

        if assessment is not None:
            return {"success": True, "data": assessment}
        
        else :   
            logger.error("get_metrics_assessment error: No assessment found with name {}\n".format(METRICS_ASSESSMENT_NAME))


            category_create_payload = {
                "name" : METRICS_CATEGORY_NAME
            }

            create_category = await utils.make_API_call_to_CCow_and_get_response(
                constants.URL_ASSESSMENT_CATEGORIES,"POST",category_create_payload, ctx=ctx
            )

            error = utils.handle_error_response(create_category,"get_metrics_assessment")
            if error:
                logger.error("get_metrics_assessment create_category_error: {}\n".format(error))
                if isinstance(resp, dict) and create_category.get("Description") != "category name already exists":
                    return error


            payload = {
                "name": METRICS_ASSESSMENT_NAME,
                "type": "metric",
                "applicationType": "generic",
                "status": "active",
                "categoryName": METRICS_CATEGORY_NAME,
                "linkDefaultCCFPlan":{
                    "propagate": "evidence", "propagateToSource": "none", "nonReportable": True,
                },
                "tags": {"assessment_class":["metrics"],"assessment_class_singular":["metric"]}
            }

            create_output = await utils.make_API_call_to_CCow_and_get_response(
                constants.URL_PLANS, "POST", payload, ctx=ctx
            )
            error = utils.handle_error_response(create_output,"get_metrics_assessment")
            if error:
                logger.error("get_metrics_assessment create_error: {}\n".format(error))
                return error
            
            if create_output.get("id"):
                assessment = assessment_vo.AssessmentVO(
                            id=create_output.get("id"),
                            name=METRICS_ASSESSMENT_NAME,
                            categoryName=METRICS_CATEGORY_NAME
                        )
                return {"success": True, "data": assessment}

            return {"success": False, "error": "No metrics assessment found"}

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_metrics_assessment error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}

@mcp.tool()
async def list_assets(ctx: Context | None = None) -> dict:
    """
        Get all assets
        
        Returns:
            - assets (list[AssetsVo]): A list of assets.
                - id (str):  Asset id.
                - name (str): Name of the asset.
            - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("get_assets_list: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_ASSETS, ctx)
        logger.debug("assets output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("list_assets error: {}\n".format(output))
            return assets_vo.AssetListVO(error="Facing internal error")
        
        error = utils.handle_error_response(output,"list_assets")
        if error:
            return error
        
        assets: list[assets_vo.AssetVO]=[]
        for item in output["items"]:
            if "name" in item:
                assets.append(assets_vo.AssetVO.model_validate(item))
        
        logger.debug("modified assets: {}\n".format(assets))

        return {"success": True, "data": assets}
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_assets error: {}\n".format(e))
        return assets_vo.AssetListVO(error="Facing internal error")

@mcp.tool()
async def get_assets_data(assetId: str , ctx: Context | None = None) -> dict:
    """
    Get controls and evidence metadata for one asset (no sample data).

    Workflow:
    1. Call `list_assets` to find an asset name.
    2. Call this tool with the selected `assetId`.
    3. If metrics are many (>30), this tool returns only a first-page summary and asks to narrow by metrics ids.
    4. Call `get_asset_metrics_evidence_sample_data` with narrowed metrics ids to fetch sample data.

    Args:
        assetId (str): Asset id from `list_assets`.

    Returns:
        success (bool)
        data (dict):
            - assetName (str)
            - assetId (str)
            - requiresNarrowing (bool)
            - metrics (list):
                - metricsId (str)
                - metricsName (str)
                - metricsDescription (str)
                - evidence (list):
                    - evidenceName (str)
                    - evidenceDescription (str)
        next_action (str, optional)
        next_step (str, optional)

    """
    try:
        logger.info("get_assets_data:\n")

        EVIDENCE_NAMES_TO_IGNORE = ["LogFile", "AuditFile"]
        metrics_narrowing_threshold = 30
        page_size = 500
        assetId = (assetId or "").strip()
        ignored_evidence_names = {name.lower() for name in EVIDENCE_NAMES_TO_IGNORE}

        if not assetId:
            return {
                "success": False,
                "error": "assetId is required",
                "next_action": "list_assets",
                "next_step": "Call list_assets and then re-run get_assets_data with an exact assetId.",
            }

        plan_url = (
            f"{constants.URL_PLANS}"
            f"?fields=basic&ids={assetId}&page=1&page_size=1"
        )
        plan_resp = await utils.make_GET_API_call_to_CCow(plan_url, ctx=ctx)
        logger.debug(
            "get_assets_data plan_resp for {}: {}\n".format(
                assetId,
                json.dumps(plan_resp) if isinstance(plan_resp, (dict, list)) else plan_resp,
            )
        )

        plan_error = utils.handle_error_response(plan_resp, "get_assets_data:plan_lookup")
        if plan_error:
            return plan_error

        plan_items = plan_resp.get("items", []) if isinstance(plan_resp, dict) else []
        plan = next(iter(plan_items), None)
        if not plan or not plan.get("id"):
            return {
                "success": False,
                "error": f"No asset found for asset id: {assetId}",
            }

        plan_id = plan.get("id")
        plan_name = plan.get("name")

        run_url = f"{constants.URL_PLAN_INSTANCES}?plan_id={plan_id}&fields=basic&page=1&page_size=1"
        run_resp = await utils.make_GET_API_call_to_CCow(run_url, ctx=ctx)
        logger.debug(
            "get_assets_data run_resp for {}: {}\n".format(
                assetId,
                json.dumps(run_resp) if isinstance(run_resp, (dict, list)) else run_resp,
            )
        )

        run_error = utils.handle_error_response(run_resp, "get_assets_data:run_lookup")
        if run_error:
            return run_error

        run_items = run_resp.get("items", []) if isinstance(run_resp, dict) else []
        run = next(iter(run_items), None)
        if not run or not run.get("id"):
            return {
                "success": False,
                "error": f"No data found for asset id: {assetId}",
            }

        asset_run_id = run.get("id")
        metrics: list[dict] = []
        page = 1

        controls_url = f"{constants.URL_PLAN_INSTANCE_CONTROLS}?page={page}&page_size={page_size}&is_leaf_control=true&plan_instance_id={asset_run_id}"
        controls_resp = await utils.make_GET_API_call_to_CCow(controls_url, ctx=ctx)
        logger.debug(
            "get_assets_data controls_resp for {} (page {}): {}\n".format(
                assetId,
                page,
                json.dumps(controls_resp) if isinstance(controls_resp, (dict, list)) else controls_resp,
            )
        )

        controls_error = utils.handle_error_response(controls_resp, "get_assets_data:controls_lookup")
        if controls_error:
            return controls_error

        if not isinstance(controls_resp, dict):
            return {"success": False, "error": "Invalid controls response"}

        controls = controls_resp.get("items", [])
        for control in controls:
            evidence_list: list[dict] = []
            for evidence in control.get("evidences", []) or []:
                evidence_name = evidence.get("name", "")
                evidence_status = evidence.get("status", "")
                if (evidence_name or "").strip().lower() in ignored_evidence_names:
                    continue

                if evidence_status != "Completed":
                    continue

                evidence_list.append(
                    {
                        "evidenceName": evidence_name,
                        "evidenceDescription": evidence.get("description", ""),
                    }
                )

            if evidence_list:
                metrics.append(
                    {
                        "metricsId": control.get("controlId"),
                        "metricsName": control.get("name", ""),
                        "metricsDescription": control.get("description", ""),
                        "evidence": evidence_list,
                    }
                )

        total_metrics = len(metrics)
        requires_narrowing = total_metrics > metrics_narrowing_threshold

        response = {
            "success": True,
            "data": {
                "assetName": plan_name,
                "assetId": plan_id,
                "requiresNarrowing": requires_narrowing,
                "metrics": metrics,
            },
        }

        if requires_narrowing:
            response["next_action"] = "get_asset_metrics_evidence_sample_data"
            response["next_step"] = (
                "Ask the user to narrow their requirement first. Then select matching "
                "metricsId values and call get_asset_metrics_evidence_sample_data with assetName and metricsIds."
            )
        return response

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_assets_data error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}

@mcp.tool()
async def get_asset_metrics_evidence_sample_data(
    assetId: str,
    metricsIds: list[str],
    sampleRecordsPerEvidence: int = 3,
    ctx: Context | None = None,
) -> dict:
    """
    Get sample evidence records for selected metrics of an asset.

    Use this only after `get_assets_data` when user narrows down to specific metrics.

    Args:
        assetId (str): Asset id from `list_assets`.
        metricsIds (list[str]): Selected metrics ids to fetch evidence sample data for.
        sampleRecordsPerEvidence (int, optional): Max sample rows per evidence. Allowed range: 1-10. Defaults to 3.

    Returns:
        success (bool)
        data (dict): keyed by asset assessment name.
            - assetName (str)
            - metrics (list):
                - metricsId (str)
                - metricsName (str)
                - evidence (list):
                    - evidenceRunId (str)
                    - evidenceName (str)
                    - sampleRecords (list[dict])
        errors (list, optional): partial fetch failures, if any.
    
    
    """
    try:
        logger.info("get_asset_metrics_evidence_sample_data:\n")

        assetId = (assetId or "").strip()
        if not assetId:
            return {"success": False, "error": "assetId is required"}

        EVIDENCE_NAMES_TO_IGNORE = ["LogFile", "AuditFile"]
        ignored_evidence_names = {name.lower() for name in EVIDENCE_NAMES_TO_IGNORE}
        excluded_columns = ["ComplianceStatus"]

        selected_metrics_ids = list(
            {
                str(metrics_id).strip()
                for metrics_id in (metricsIds or [])
                if str(metrics_id).strip()
            }
        )

        if not selected_metrics_ids:
            return {"success": False, "error": "metrics ids cannot be empty"}

        sample_size = int(sampleRecordsPerEvidence or 5)
        if sample_size <= 0:
            sample_size = 5
        sample_size = min(sample_size, 10)

        plan_url = f"{constants.URL_PLANS}?fields=basic&ids={assetId}&page=1&page_size=1"
        plan_resp = await utils.make_GET_API_call_to_CCow(plan_url, ctx=ctx)
        plan_error = utils.handle_error_response(plan_resp, "get_asset_metrics_evidence_sample_data:plan_lookup")
        if plan_error:
            return plan_error

        plan_items = plan_resp.get("items", []) if isinstance(plan_resp, dict) else []
        plan = next(iter(plan_items), None)
        if not plan or not plan.get("id"):
            return {"success": False, "error": f"No asset found for asset id: {assetId}"}

        plan_id = plan.get("id")

        run_url = f"{constants.URL_PLAN_INSTANCES}?plan_id={plan_id}&fields=basic&page=1&page_size=1"
        run_resp = await utils.make_GET_API_call_to_CCow(run_url, ctx=ctx)
        run_error = utils.handle_error_response(run_resp, "get_asset_metrics_evidence_sample_data:run_lookup")
        if run_error:
            return run_error

        run_items = run_resp.get("items", []) if isinstance(run_resp, dict) else []
        run = next(iter(run_items), None)
        if not run or not run.get("id"):
            return {"success": False, "error": f"No data found for asset id: {assetId}"}

        asset_run_id = run.get("id")
        page_size = 500
        page = 1
        matched_metrics: list[dict] = []
        selected_set = set(selected_metrics_ids)

        controls_url = (
            f"{constants.URL_PLAN_INSTANCE_CONTROLS}"
            f"?page={page}&page_size={page_size}&is_leaf_control=true&plan_instance_id={asset_run_id}"
        )
        controls_resp = await utils.make_GET_API_call_to_CCow(controls_url, ctx=ctx)
        controls_error = utils.handle_error_response(
            controls_resp, "get_asset_metrics_evidence_sample_data:controls_lookup"
        )
        if controls_error:
            return controls_error

        if not isinstance(controls_resp, dict):
            return {"success": False, "error": "Invalid controls response format"}

        controls = controls_resp.get("items", [])
        for control in controls:
            control_id = str(control.get("controlId") or "").strip()
            if not control_id or control_id not in selected_set:
                continue
            matched_metrics.append(
                {
                    "metricsId": control_id,
                    "metricsName": control.get("name", ""),
                    "metricsDescription": control.get("description", ""),
                    "evidence": [],
                }
            )

        metrics_by_id = {
            str(metric.get("metricsId") or "").strip(): metric
            for metric in matched_metrics
        }
        max_concurrency = 10
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _fetch_for_metric(metric_id: str, evidence: dict):
            async with semaphore:
                try:
                    evidence_obj = await fetch_evidence_sample(
                        ctx,
                        evidence,
                        sample_size,
                        set(ignored_evidence_names),
                        set(excluded_columns),
                    )
                    return metric_id, evidence_obj
                except Exception as evidence_error:
                    return metric_id, {
                        "evidenceRunId": evidence.get("id"),
                        "evidenceName": evidence.get("name", ""),
                        "evidenceDescription": evidence.get("description", ""),
                        "sampleRecords": [],
                        "error": f"Failed to fetch sample data: {evidence_error}",
                    }

        evidence_coroutines = []
        for control in controls:
            control_id = str(control.get("controlId") or "").strip()
            if control_id not in metrics_by_id:
                continue
            for evidence in control.get("evidences", []) or []:
                evidence_coroutines.append(_fetch_for_metric(control_id, evidence))

        if evidence_coroutines:
            results = await asyncio.gather(*evidence_coroutines)
            for metric_id, evidence_obj in results:
                if evidence_obj is None:
                    continue
                metrics_by_id[metric_id]["evidence"].append(evidence_obj)

        response = {
            "success": True,
            "data": {
                "assetId": plan_id,
                "metrics": matched_metrics,
            },
        }
        return response
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_asset_metrics_evidence_sample_data error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}

@mcp.tool()
async def run_metrics_assessment(
    metrics_assessment_id: str,
    name: str,
    description: str,
    ctx: Context | None = None
) -> dict:
    """
    Trigger a new metrics assessment run.

    Args:
        metrics_assessment_id (str): Metrics assessment (plan) ID.
        name (str): Run name.
        description (str): Run description.
    """
    try:
        logger.info("run_metrics_assessment:\n")

        metrics_assessment_id = (metrics_assessment_id or "").strip()
        name = (name or "").strip()
        description = (description or "").strip()

        err = utils.require_fields(locals(), ["metrics_assessment_id", "name", "description"])
        if err:
            return err

        today_date = datetime.now().strftime("%m/%d/%Y")
        payload = {
            "planId": metrics_assessment_id,
            "fromDate": today_date,
            "toDate": today_date,
            "tags": {},
            "name": name,
            "description": description,
            "inputs": {},
            "profileId": "",
            "otherInfos": {"disableAutomatedAction": True}
        }
        logger.debug("run_metrics_assessment payload: {}\n".format(json.dumps(payload)))

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_INSTANCES, "POST", payload, ctx=ctx
        )
        logger.debug(
            "run_metrics_assessment output: {}\n".format(
                json.dumps(output) if isinstance(output, (dict, list)) else output
            )
        )

        error = utils.handle_error_response(output, "run_metrics_assessment")
        if error:
            logger.error("run_metrics_assessment error: {}\n".format(error))
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
        logger.error("run_metrics_assessment error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}

@mcp.tool()
async def get_all_recent_assessment_run_details(
    assessmentMetricsId: str,
    ctx: Context | None = None
) -> dict:
    """
    Get recent metrics assessment run details (latest 10).

    Context instructions:
    - Use this tool first when user asks for latest/recent metrics.
    - This tool only returns run summary, not metric details.
    - Take `metricAssessmentRunId` from this response and call `get_all_run_metrics`.
    - Prioritize the most recent run item for "latest metrics" questions.

    Args:
        assessmentMetricsId (str): Metrics assessment id.
    """
    try:
        logger.info("get_all_recent_run_details:\n")

        assessment_metrics_id = (assessmentMetricsId or "").strip()
        err = utils.require_fields(locals(), ["assessment_metrics_id"])
        if err:
            return err

        url = (
            f"{constants.URL_PLAN_INSTANCES}"
            f"?fields=basic&page=1&page_size=10&plan_id={assessment_metrics_id}"
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
                    "metricAssessmentRunId": item.get("id", ""),
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
async def get_all_metrics_of_run(
    assessmentMetricsRunId: str,
    assessmentMetricsId: str,
    ctx: Context | None = None
) -> dict:
    """
    Get transformed metrics for a metrics assessment run.

    Args:
        assessmentMetricsRunId (str): Metrics assessment run id.
        assessmentMetricsId (str): Metrics assessment id.

    """
    try:
        logger.info("get_all_metrics_of_run:\n")

        assessment_metrics_run_id = (assessmentMetricsRunId or "").strip()
        assessment_metrics_id = (assessmentMetricsId or "").strip()
        err = utils.require_fields(
            locals(),
            ["assessment_metrics_run_id", "assessment_metrics_id"],
        )
        if err:
            return err

        output, error = await get_assessment_run_controls(ctx,assessment_metrics_run_id,basicFields=False)

        if error:
            logger.error("get_all_metrics_of_run error: {}\n".format(error))
            return error

        items = output.get("items", []) if isinstance(output, dict) else []
        if not isinstance(items, list):
            items = []

        metrics = []
        for item in items:
            if not isinstance(item, dict):
                continue

            metric_evidences = []
            metric_evidences_sources = []

            evidences = item.get("evidences", [])
            if not isinstance(evidences, list):
                evidences = []

            for evidence in evidences:
                if not isinstance(evidence, dict):
                    continue

                evidence_name = str(evidence.get("name") or "").strip()
                evidence_status = evidence.get("status", "")
                evidence_score = evidence.get("compliancePCT__", "")
                has_rule_id = bool(str(evidence.get("ruleId") or "").strip())

                if has_rule_id:
                    rule_evidence = {
                        "name": evidence_name,
                        "status": evidence_status,
                        "metricScore": evidence_score,
                    }
                    compliance_calculation_infos = evidence.get("complianceCalculationInfos", {})
                    if isinstance(compliance_calculation_infos, dict):
                        gocel = compliance_calculation_infos.get("gocel")
                        if isinstance(gocel, dict):
                            rule_evidence["cel_formula"] = {
                                "filteringExpression (b)": gocel.get("include", ""),
                                "compliantExpression (a)": gocel.get("compliance", ""),
                            }
                    metric_evidences.append(rule_evidence)
                elif evidence_name in ["LogFile", "AuditFile"]:
                    metric_evidences_sources.append(
                        {
                            "name": evidence_name,
                            "status": evidence_status,
                        }
                    )

            if len(metric_evidences) == 0:
                metric_evidences.append({"message": "No data available on this metric"})

            metric = {
                "metricRunId": item.get("id", ""),
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "metricId": item.get("controlId", ""),
                "metricNumber": item.get("displayable", ""),
                # "metricScore": item.get("compliancePCT__", ""),
                "formula": "(a/b)*100",
                "metricEvidences": metric_evidences,
                "metricEvidencesSources": metric_evidences_sources,
            }
            metrics.append(metric)


        return {
            "success": True,
            "data": {
                "assessmentMetricsRunId": assessment_metrics_run_id,
                "assessmentMetricsId": assessment_metrics_id,
                "metrics": metrics,
            },
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_all_metrics_of_run error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}

@mcp.tool()
async def add_metric(assessmentMetricsId: str,categoryName: str, descrition: str, ctx: Context | None = None) -> dict:
    """
    Add a metric to an assessment under the best matching category.

    Category routing rule:
    - Infer category from the metric description; do not ask the user for category selection.
    - Mandatory: call `get_all_metrics_categories` first for the same `assessmentMetricsId`.
    - Then map the inferred category to an existing category in the target assessment.
    - If no existing category fits, create a new category with the inferred name, then add the metric there.

    Args:
        assessmentMetricsId (str): The ID of the metrics assessment to which the metric will be added.
        categoryName (str): System-resolved category name derived from description; reused if existing, else created.
        description (str): A description for the metric.

    Returns:
        metricsId (str): The ID of the newly created metric control.
    """
    try:
        logger.info("add_metric:\n")

        assessmentMetricsId = (assessmentMetricsId or "").strip()
        categoryName = (categoryName or "").strip()
        descrition = (descrition or "").strip()

        err = utils.require_fields(locals(), ["assessmentMetricsId", "categoryName", "descrition"])
        if err:
            return err

        payload = {
            "categoryName": categoryName,
            "name": descrition,
            "description": descrition,
            "addCategory":True
        }
        logger.debug("add_metric payload: {}\n".format(json.dumps(payload)))

        url = f"{constants.URL_PLANS}/{assessmentMetricsId}/add-control"

        output = await utils.make_API_call_to_CCow_and_get_response(
            url, "POST", payload, ctx=ctx
        )
        logger.debug(
            "add_metric output: {}\n".format(
                json.dumps(output) if isinstance(output, dict) else output
            )
        )
        error = utils.handle_error_response(output,"add_metric")
        if error:
            return error

        control_id = output.get("id")
        
        return {"success": True, "data": {"metricsId": control_id}}

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("add_metric error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}


@mcp.tool()
async def update_metric(assessmentMetricsId: str,metricsId: str, descrition: str, ctx: Context | None = None) -> dict:
    """
    Update an existing metric definition (name/description).

    Alignment requirement after update:
    - Ensure SQL query evidence, CEL expressions, and metric notes still match the updated requirement.
    - If any artifact is out of sync, update it before considering the metric update complete.

    Args:
        assessmentMetricsId (str): Metrics assessment ID containing the metric.
        metricsId (str): Metric ID to update.
        description (str): Updated metric description/definition.
    """
    try:
        logger.info("update_metric:\n")

        assessmentMetricsId = (assessmentMetricsId or "").strip()
        metricsId = (metricsId or "").strip()
        descrition = (descrition or "").strip()

        err = utils.require_fields(locals(), ["assessmentMetricsId", "metricsId", "descrition"])
        if err:
            return err

        payload = [
            {
                "op": "replace",
                "path": "/name",
                "value": descrition
            },
            {
                "op": "replace",
                "path": "/description",
                "value": descrition
            }
        ]
        logger.debug("update_metric payload: {}\n".format(json.dumps(payload)))

        url = f"{constants.URL_PLAN_CONTROLS}/{metricsId}"

        output = await utils.make_API_call_to_CCow_and_get_response(
            url, "PATCH", payload, ctx=ctx
        )
        logger.debug(
            "update_metric output: {}\n".format(
                json.dumps(output) if isinstance(output, dict) else output
            )
        )
        error = utils.handle_error_response(output,"update_metric")
        if error:
            return error
        
        return {"success": True, "message": "Metrics updated successfully"}

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_metric error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}

@mcp.tool()
async def get_all_metrics_categories(
    assessmentMetricsId: str,
    ctx: Context | None = None,
) -> dict:
    """
    Get all metrics categories for an assessment id.
    """
    try:
        logger.info("get_all_metrics_category:\n")

        assessment_metrics_id = (assessmentMetricsId or "").strip()
        err = utils.require_fields(locals(), ["assessment_metrics_id"])
        if err:
            return err
        
        page_size = 100
        cur_page = 1
        has_next = True
        all_controls = []
        max_pages = 10

        while has_next and cur_page <= max_pages:
            query_params = f"?page={cur_page}&page_size={page_size}&plan_id={assessment_metrics_id}&fields=basic&is_root_control=true"
            logger.debug(f"get_all_metrics_category fetching page {cur_page}: {query_params}\n")

            output = await utils.make_GET_API_call_to_CCow(constants.URL_PLAN_CONTROLS + query_params, ctx=ctx)
            logger.debug(
                "get_all_metrics_category page: {}\noutput: {}\n".format(
                    cur_page, json.dumps(output) if isinstance(output, (dict, list)) else output
                )
            )

            if isinstance(output, str) or (isinstance(output, dict) and "error" in output):
                if cur_page == 1:
                    logger.error("get_all_metrics_category error: {}\n".format(output))
                    return {"success": False, "error": "Failed to fetch metrics categories"}
                has_next = False
                break

            if isinstance(output, dict):
                if "Message" in output:
                    if cur_page == 1:
                        logger.error("get_all_metrics_category error: {}\n".format(output))
                        return {"success": False, "error": output}
                    has_next = False
                    break

                items = output.get("items", [])
                if not isinstance(items, list) or not items:
                    break

                for item in items:
                    if isinstance(item, dict) and "id" in item and "name" in item:
                        name = str(item.get("name") or "").strip()
                        all_controls.append(name)

                total_pages = int(output.get("TotalPage", 0)) or 1
                cur_page += 1
                has_next = cur_page <= total_pages
            else:
                has_next = False

        if len(all_controls) == 0:
            return {
                "success": True,
                "message": "No metrics categories exist",
            }
        
        return {
            "success": True,
            "data": all_controls,
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_all_metrics_category error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}


@mcp.tool()
async def get_all_assessment_metrics(
    assessmentMetricsId: str,
    ctx: Context | None = None,
) -> dict:
    """
    Get all metrics for an assessment id.
    """
    try:
        logger.info("get_all_assessment_metrics:\n")

        assessment_metrics_id = (assessmentMetricsId or "").strip()

        err = utils.require_fields(locals(), ["assessment_metrics_id"])
        if err:
            return err
        
        page_size = 100
        cur_page = 1
        has_next = True
        all_controls = []
        max_pages = 10

        while has_next and cur_page <= max_pages:
            query_params = f"?page={cur_page}&page_size={page_size}&plan_id={assessment_metrics_id}&fields=basic&is_leaf_control=true"
            logger.debug(f"get_all_assessment_metrics fetching page {cur_page}: {query_params}\n")

            output = await utils.make_GET_API_call_to_CCow(constants.URL_PLAN_CONTROLS + query_params, ctx=ctx)
            logger.debug(
                "get_all_assessment_metrics page: {}\noutput: {}\n".format(
                    cur_page, json.dumps(output) if isinstance(output, (dict, list)) else output
                )
            )

            if isinstance(output, str) or (isinstance(output, dict) and "error" in output):
                if cur_page == 1:
                    logger.error("get_all_assessment_metrics error: {}\n".format(output))
                    return {"success": False, "error": "Failed to fetch assessment metrics"}
                has_next = False
                break

            if isinstance(output, dict):
                if "Message" in output:
                    if cur_page == 1:
                        logger.error("get_all_assessment_metrics error: {}\n".format(output))
                        return {"success": False, "error": output}
                    has_next = False
                    break

                items = output.get("items", [])
                if not isinstance(items, list) or not items:
                    break

                for item in items:
                    if isinstance(item, dict) and "id" in item and "name" in item:
                        all_controls.append(
                            {
                                "id": item.get("id", ""),
                                "name": item.get("name", ""),
                                "description": item.get("description", ""),
                                "alias": item.get("alias", ""),
                                "metricNumber": item.get("displayable", ""),
                            }
                        )
                total_pages = int(output.get("TotalPage", 0)) or 1
                cur_page += 1
                has_next = cur_page <= total_pages
            else:
                has_next = False

        logger.info(
            f"get_all_assessment_metrics: Found {len(all_controls)} control(s) across {cur_page - 1} page(s)\n"
        )
        return {"success": True, "controls": all_controls, "totalCount": len(all_controls)}
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_all_assessment_metrics error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}


@mcp.tool()
async def suggest_metrics_citations(
    metricName: str,
    assessmentMetricsId: str,
    description: str,
    metricsId: str = "",
    ctx: Context | None = None,
) -> dict:
    """
    Suggest citations for a metric name and description.

    Args:
        metricName (str): Name of metric to get suggestions for (required).
        assessmentMetricsId (str): Assessment ID - resolved from assessment name (required).
        description (str, optional): Description of the metric to get suggestions for.
        metricId (str, optional): Metric ID - resolved from metric name if selecting existing metric, empty if creating new control.
    
    Returns:
        Dict with success status and suggestions:
        - success (bool): Whether the request was successful
        - items (list[dict]): List of suggestion items, each containing:
            - inputMetricName (str): The input metric name
            - controlId (str): The control ID (empty if control doesn't exist yet)
            - suggestions (list[dict]): List of suggested controls, each containing:
                - Name (str): metric name
                - metric ID (int): Control ID number
                - Metric Classification (str): Classification type
                - Impact Zone (str): Impact zone category
                - Metric Requirement (str): Requirement level
                - Sort ID (str): Sort identifier
                - Metric Type (str): Type of Metric
                - Score (float): Similarity score
        - authorityDocument (str): Name of the authorityDocument
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("suggest_metrics_citations:\n")

        metric_name = (metricName or "").strip()
        assessment_metrics_id = (assessmentMetricsId or "").strip()

        err = utils.require_fields(locals(), ["assessment_metrics_id", "metric_name"])
        if err:
            return err

        payload = {
            "assessment_type": "asset",
            "assessment_id": "",
            "assessment_name": "",
            "use_default_authority_document": True,
            "controls": [
                {
                    "id": "",
                    "name": metric_name,
                    "description": str(description).strip() if description else "",
                }
            ],
        }
        logger.debug("suggest_metrics_citations payload: {}\n".format(json.dumps(payload)))

        output = await utils.make_API_call_to_CCow(payload, constants.URL_GET_SIMILAR_CONTROLS, ctx=ctx)
        logger.debug(
            "suggest_metrics_citations output: {}\n".format(
                json.dumps(output) if isinstance(output, dict) else output
            )
        )

        if isinstance(output, str):
            logger.error("suggest_metrics_citations error: {}\n".format(output))
            return {"success": False, "error": output}

        if isinstance(output, dict):
            if "error" in output:
                logger.error("suggest_metrics_citations error: {}\n".format(output))
                return {"success": False, "error": output.get("error")}
            if "Message" in output:
                logger.error("suggest_metrics_citations error: {}\n".format(output))
                return {"success": False, "error": output}

            items = output.get("items", [])
            authority_document = output.get("authorityDocument", "")
            abstracted_items = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                abstracted_item = {
                    "inputMetricName": item.get("inputMetricName", item.get("inputControlName", "")),
                    "metricsId": item.get("metricsId", item.get("controlId", "")),
                    "suggestions": [],
                }
                for suggestion in item.get("suggestions", []):
                    if not isinstance(suggestion, dict):
                        continue
                    abstracted_item["suggestions"].append(
                        {
                            "Name": suggestion.get("Name", ""),
                            "Metric ID": suggestion.get("Metric ID", suggestion.get("Control ID", "")),
                            "Metric Classification": suggestion.get("Classification", suggestion.get("Control Classification", "")),
                            "Impact Zone": suggestion.get("Impact Zone", ""),
                            "Metric Requirement": suggestion.get("Requirement", suggestion.get("Control Requirement", "")),
                            "Sort ID": suggestion.get("Sort ID", ""),
                            "Metric Type": suggestion.get("Type", suggestion.get("Control Type", "")),
                            "Score": suggestion.get("Score", 0.0),
                        }
                    )
                abstracted_items.append(abstracted_item)
            

            logger.info(f"suggest_metrics_citations Response : {abstracted_items}")
            return {
                "success": True,
                "items": abstracted_items,
                "authorityDocument": authority_document,
            }

        logger.error("suggest_metrics_citations error: Unexpected response type: {}\n".format(type(output)))
        return {"success": False, "error": f"Unexpected response type: {type(output)}"}
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("suggest_metrics_citations error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}


@mcp.tool()
async def attach_citation_to_metrics(
    assessmentMetricsId: str,
    metricsId: str,
    authorityDocument: str,
    metricsIdsInAuthorityDocument: list[str],
    sortId: str,
    metricsNames: list[str],
    ctx: Context | None = None,
) -> dict:
    """
    Attach one citation to a metric.

    Args:
    assessmentId (str): The assessment ID (plan ID) - MUST be user-selected.
    metricsId (str): The control ID to attach citations to - MUST be user-selected.
    authorityDocument (str): The authority document name (e.g., "Trial1 CF").
    controlIdsInAuthorityDocument (list[str]): List of metric IDs from the authority document (e.g., ["10014"]).
    sortId (str): Sort ID from the suggestion (e.g., "010 014").
    metricNames (list[str]): List of metric names from the suggestion (e.g., ["Multifactor Authentication"]).

    Returns:
        Dict with success status and citation data:
        - success (bool): Whether the request was successful
        - citations (list[dict], optional): List of attached citation objects (only when confirm=True), each containing:
            - id (str): Citation ID
            - metricsID (str): metric ID
            - authorityDocument (str): Authority document name
            - MetricNames (list[str]): Metric names
            - MetricInAuthorityDocument (list[str]): Metric IDs in authority document
            - sortID (str): Sort ID
            - status (str): Citation status
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("attach_citation_to_metrics:\n")

        assessment_metrics_id = (assessmentMetricsId or "").strip()
        metrics_id = (metricsId or "").strip()
        authority_document = (authorityDocument or "").strip()
        sort_id = (sortId or "").strip()

        if not assessment_metrics_id:
            return {"success": False, "error": "assessmentMetricsId is required"}
        if not metrics_id:
            return {"success": False, "error": "metricsId is required"}
        if not authority_document:
            return {"success": False, "error": "authorityDocument is required"}
        if not metricsIdsInAuthorityDocument or not isinstance(metricsIdsInAuthorityDocument, list):
            return {"success": False, "error": "metricsIdsInAuthorityDocument must be a non-empty list"}
        if not sort_id:
            return {"success": False, "error": "sortId is required"}
        if not metricsNames or not isinstance(metricsNames, list):
            return {"success": False, "error": "metricsNames must be a non-empty list"}

        payload = {
            "authorityDocument": authority_document,
            "planControlCitations": [
                {
                    "planControlID": metrics_id,
                    "controlsInAuthorityDocument": [
                        str(metric_id).strip()
                        for metric_id in metricsIdsInAuthorityDocument
                        if str(metric_id).strip()
                    ],
                    "sortID": sort_id,
                    "controlNames": [
                        str(metric_name).strip()
                        for metric_name in metricsNames
                    ],
                }
            ],
        }
        logger.debug("attach_citation_to_metrics payload: {}\n".format(json.dumps(payload)))

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_CONTROL_CITATIONS_BATCH, "POST", payload, ctx=ctx
        )
        logger.debug(
            "attach_citation_to_metrics output: {}\n".format(
                json.dumps(output) if isinstance(output, dict) else output
            )
        )

        if isinstance(output, str):
            logger.error("attach_citation_to_metrics error: {}\n".format(output))
            return {"success": False, "error": output}
        
        if isinstance(output, dict):
            if "error" in output:
                logger.error("attach_citation_to_metrics error: {}\n".format(output))
                return {"success": False, "error": output.get("error")}
            if "Message" in output:
                logger.error("attach_citation_to_metrics error: {}\n".format(output))
                return {"success": False, "error": output}
            
            items = output.get("items", [])
            abstracted_citations = []
            for item in items:
                if isinstance(item, dict):
                    abstracted_citation = {
                        "id": item.get("id", ""),
                        "metricsID": item.get("planControlID", ""),
                        "authorityDocument": item.get("authorityDocument", ""),
                        "metricsNames": item.get("controlNames", []),
                        "metricsIdsInAuthorityDocument": item.get("controlsInAuthorityDocument", []),
                        "sortID": item.get("sortID", ""),
                        "status": item.get("status", "")
                    }
                    abstracted_citations.append(abstracted_citation)

            logger.info(f"attach_citation_to_metrics: Successfully attached {len(abstracted_citations)} citation(s)\n")

            # Sync CCF IDs after successful citation attachment
            try:
                sync_payload = {
                    "planID": assessment_metrics_id,
                    "authorityDocument": str(authorityDocument).strip(),
                    "updateControlLinking": True,
                    "controlId": metrics_id,
                    # "syncGraph": True
                }
                logger.debug("attach_citation_to_metrics: Syncing CCF IDs with payload: {}\n".format(json.dumps(sync_payload)))
                
                sync_resp = await utils.make_API_call_to_CCow_and_get_response(
                    constants.URL_PLANS_SYNC_CCFID,
                    "POST",
                    sync_payload,
                    ctx=ctx
                )
                # Log sync result but don't fail the citation attachment if sync fails
                if isinstance(sync_resp, str):
                    logger.warning(f"attach_citation_to_metrics: CCF ID sync returned error (citation still attached): {sync_resp}\n")
                elif isinstance(sync_resp, dict) and ("Message" in sync_resp or "error" in sync_resp):
                    logger.warning(f"attach_citation_to_metrics: CCF ID sync returned error (citation still attached): {sync_resp}\n")
                else:
                    logger.info(f"attach_citation_to_metrics: Successfully synced CCF IDs\n")

            except Exception as sync_error:
                # Log sync error but don't fail the citation attachment
                logger.warning(f"attach_citation_to_metrics: Failed to sync CCF IDs (citation still attached): {sync_error}\n")
                logger.debug(traceback.format_exc())

            return {"success": True, "citations": abstracted_citations}
        
        logger.error("attach_citation_to_metrics error: Unexpected response type {}\n".format(type(output)))
        return {"success": False, "error": f"Unexpected response type: {type(output)}"}
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("attach_citation_to_metrics error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}


@mcp.tool()
async def fetch_metrics_source_summary(
    metricsId: str,
    ctx: Context | None = None,
) -> dict:
    """
    Fetch source summary for a metric.

    Fetch aggregated source summary for a metrics, including linked metrics, evidences (including schema), and lineage depth.

    It returns how a metrics is connected to evidence configurations and what evidence
    structures (schemas) are available.

    ⚠️ IMPORTANT WORKFLOW 
    If **no evidence configs** exist and a **citation is already attached**, SQL query and formula generation must STOP.  
    If no evidence configs exist and a citation is already attached, SQL query generation must stop immediately.
    Do not proceed and do not provide any suggestions.
    No further actions or recommendations are allowed.
    
    Args:
        controlId (str): Plan control ID provided by the user (mandatory).

    Returns:
        MetricsSourceSummaryResponseVO containing:
            - success (bool): API invocation status.
            - data (MetricsSourceSummaryVO, optional): Source summary (lineage, evidence, schema) on success.
            - error (str, optional): Validation or API error details.
            - next_action (str, optional): Recommended next action.
    """
    try:
        logger.info("fetch_metrics_source_summary:\n")

        metrics_id = (metricsId or "").strip()
        if not metrics_id:
            logger.error("fetch_metrics_source_summary error: metricsId is mandatory\n")
            return MetricsSourceSummaryResponseVO(success=False, error="metricsId is mandatory")

        payload = {"controlID": metrics_id}
        logger.debug("fetch_metrics_source_summary payload: {}\n".format(json.dumps(payload)))

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_CONTROLS_FETCH_SOURCE_SUMMARY, "POST", payload, ctx=ctx
        )
        logger.debug(
            "fetch_metrics_source_summary output: {}\n".format(
                json.dumps(output) if isinstance(output, dict) else output
            )
        )

        if isinstance(output, str):
            logger.error("fetch_metrics_source_summary error: {}\n".format(output))
            return MetricsSourceSummaryResponseVO(success=False, error=output).model_dump()
        if isinstance(output, dict):
            if "error" in output:
                logger.error("fetch_metrics_source_summary error: {}\n".format(output))
                return MetricsSourceSummaryResponseVO(success=False, error=output.get("error")).model_dump()
            if "Message" in output:
                logger.error("fetch_metrics_source_summary error: {}\n".format(output))
                return MetricsSourceSummaryResponseVO(success=False, error=output).model_dump()

            try:
                summary_data = MetricsSourceSummaryVO(**output)
                logger.info("fetch_metrics_source_summary: Successfully parsed response into VO\n")
                response = MetricsSourceSummaryResponseVO(
                    success=True, 
                    data=summary_data,
                )
                if summary_data.lineage and len(summary_data.lineage)>0:
                    response.next_action="get evidence sample data"
                else:
                    response.next_action="STOP_SQL_QUERY_GENERATION_NO_EVIDENCE_CONFIGS_ATTACHED"
                    response.next_step = (
                        "No evidence configurations are linked to this control. "
                        "SQL query automation cannot proceed. "
                    )
                return response.model_dump()
            except Exception as parse_error:
                logger.error(f"fetch_metrics_source_summary error: Failed to parse response: {parse_error}\n")
                logger.debug(traceback.format_exc())
                return MetricsSourceSummaryResponseVO(
                    success=False, 
                    error=f"Failed to parse response: {parse_error}"
                ).model_dump()
        
        logger.error("fetch_metrics_source_summary error: Unexpected response type {}\n".format(type(output)))
        return MetricsSourceSummaryResponseVO(success=False, error=f"Unexpected response type: {type(output)}")
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_metrics_source_summary error: {}\n".format(e))
        return MetricsSourceSummaryResponseVO(success=False, error=f"Unexpected error: {e}").model_dump()


@mcp.tool()
async def get_metrics_evidence_sample_data(
    metricsId: str,
    evidenceNames: list[str] | None = None,
    records: int = 3,
    ctx: Context | None = None,
) -> dict:
    """
    Fetch sample evidence data for a metric.

    Usage guidance:
    1. Run `fetch_metrics_source_summary` first to understand schema/lineage.
    2. Call this tool before drafting SQL query to inspect real evidence rows.
    3. Pass 1-10 records to keep payloads lightweight (defaults to 3).

    Args:
        metricsId (str): metricsId where the SQL query will be attached (required).
        evidenceNames (list[str], optional): Specific evidence metrics names (table names) to sample.
            If omitted/empty, all evidences linked to the metrics are sampled.
        records (int, optional): Number of records per evidence (1-10, default 3).

    Returns:
        Dict containing:
            - success (bool): API invocation status.
            - metricsId (str): metrics ID.
            - evidences (list[dict]): Evidence samples grouped by metrics/evidence. If an evidence
              is missing from the response, no records exist for it in the latest run.
            - next_action (str): Recommended next step.
            - error (str, optional): Validation or API error.
    """
    try:
        logger.info("get_metrics_evidence_sample_data:\n")

        metrics_id = (metricsId or "").strip()
        if not metrics_id:
            logger.error("get_metrics_evidence_sample_data error: metricsId is mandatory\n")
            return {"success": False, "error": "metricsId is required"}

        try:
            record_count = int(records)
        except (TypeError, ValueError):
            record_count = 3

        if record_count < 1 or record_count > 10:
            record_count = 3

        payload = {
            "controlID": metrics_id,
            "records": record_count,
        }
        if evidenceNames:
            payload["evidenceNames"] = evidenceNames
        logger.debug("get_metrics_evidence_sample_data payload: {}\n".format(json.dumps(payload)))

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_CONTROLS_FETCH_SAMPLE_EVIDENCE_DATA, "POST", payload, ctx=ctx
        )
        
        error = utils.handle_error_response(output,"get_metrics_evidence_sample_data")
        if error:
            logger.error("get_metrics_evidence_sample_data error: {}\n".format(error))
            return {"success": False, "error": error}

        if isinstance(output, list):

            for item in output:
                if "controlId" in item:
                    item["metricsId"] = item.pop("controlId")

            return {
                "success": True,
                "metricsId": metrics_id,
                "evidences": output,
            }
        return {"success": False, "error": f"Unexpected response type: {type(output)}"}
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_metrics_evidence_sample_data error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}


@mcp.tool()
async def validate_sql_query_and_cel(
    sqlQuery: str,
    referenceEvidences: list[dict],
    assessmentMetricsId: str,
    metricsId: str,
    filteringCELExpression: str,
    compliantCELExpression: str,
    ctx: Context | None = None,
) -> dict:
    """
    Validate a SQL query and CEL Expression against reference evidence data.
    
    This tool validates a SQL query by executing it against provided evidence data.
    The evidence data can be provided in two ways:
    1. Using runEvidenceId (id) - obtained from `get_metrics_evidence_sample_data` response
    2. Using file content - base64 encoded CSV or JSON file content
    
    ⚠️ IMPORTANT REQUIREMENTS
    - For each evidence in referenceEvidences, either `id` OR `file` must be provided (not both).
    - If using `file`, the content must be base64 encoded and type must be "csv" or "json".
    - The evidence name should match the table name used in the SQL query.
    
    Args:
        sqlQuery (str): The SQL query to validate (required).
        referenceEvidences (list[dict]): List of evidence objects, each containing:
            - name (str): Evidence config name (table name used in SQL query) (required).
            - id (str, optional): runEvidenceId obtained from `get_metrics_evidence_sample_data` response.
            - file (dict, optional): File object containing:
                - content (str): Base64 encoded file content (required if using file).
                - type (str): File type, either "csv" or "json" (required if using file).
            - Either `id` OR `file` must be provided for each evidence (not both).
        assessmentId (str): The assessment ID that contains the control config (required).
        metricsId (str): MetricsId (required).
        filteringCELExpression (str): filtering expression to be validated,
        compliantCELExpression (str): compliant expression to be validated,

    
    Returns:
        Dict with validation status and executed query data:
        - success (bool): Whether the request was successful
        - queryStatus (str): Query validation status - "success" or "fail"
        - data (list, optional): Executed query results (rows returned by the query execution)
        - error (str, optional): Error message if validation failed or request failed
        - includeCELStatus (str): Include CEL validation status - "Success" or "Failed"
        - includeCELError (str, optional) : Error message if includeCEL validation failed
        - complianceCELStatus (str): Compliance CEL validation status - "Success" or "Failed"
        - complianceCELError (str, optional) : Error message if complianceCEL validation failed
    """
    try:
        logger.info("validate_metrics_sql_query:\n")

        sql_query = (sqlQuery or "").strip()
        assessment_metrics_id = (assessmentMetricsId or "").strip()
        metrics_id = (metricsId or "").strip()
        filteringCEL_expression = (filteringCELExpression or "").strip()
        compliantCEL_expression = (compliantCELExpression or "").strip()

        err = utils.require_fields(locals(), ["sql_query", "assessment_metrics_id", "metrics_id","filteringCEL_expression","compliantCEL_expression"])
        if err:
            return err

        validated_evidences = []
        for idx, evidence in enumerate(referenceEvidences or []):
            if not isinstance(evidence, dict):
                return {"success": False, "error": f"referenceEvidences[{idx}] must be a dict"}

            evidence_name = evidence.get("name")
            if not evidence_name or not str(evidence_name).strip():
                return {"success": False, "error": f"referenceEvidences[{idx}].name is required"}

            evidence_id = evidence.get("id")
            evidence_file = evidence.get("file")
            if evidence_id and evidence_file:
                return {
                    "success": False,
                    "error": f"referenceEvidences[{idx}] cannot include both 'id' and 'file'",
                }
            if not evidence_id and not evidence_file:
                return {
                    "success": False,
                    "error": f"referenceEvidences[{idx}] must include either 'id' or 'file'",
                }

            evidence_payload = {"name": str(evidence_name).strip()}
            if evidence_id:
                evidence_payload["id"] = str(evidence_id).strip()
            else:
                if not isinstance(evidence_file, dict):
                    return {
                        "success": False,
                        "error": f"referenceEvidences[{idx}].file must be a dict",
                    }
                file_content = evidence_file.get("content")
                file_type = str(evidence_file.get("type") or "").strip().lower()
                if not file_content or not str(file_content).strip():
                    return {
                        "success": False,
                        "error": f"referenceEvidences[{idx}].file.content is required",
                    }
                if file_type not in ["csv", "json"]:
                    return {
                        "success": False,
                        "error": f"referenceEvidences[{idx}].file.type must be csv or json",
                    }
                evidence_payload["file"] = {
                    "content": str(file_content).strip(),
                    "type": file_type,
                }
            validated_evidences.append(evidence_payload)

        payload = {
            "sqlQuery": sql_query,
            "referenceEvidences": validated_evidences,
            "assessmentID": assessment_metrics_id,
            "assessmentControlID": metrics_id,
            "validateCEL": True,
            "includeCEL" : filteringCEL_expression,
            "complianceCEL" : compliantCEL_expression
        }
        logger.debug("validate_metrics_sql_query payload: {}\n".format(json.dumps(payload)))

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_PLAN_CONTROLS_VALIDATE_SQL_QUERY, "POST", payload, ctx=ctx
        )
        logger.debug(
            "validate_metrics_sql_query output: {}\n".format(
                json.dumps(output) if isinstance(output, dict) else output
            )
        )

        if isinstance(output, str):
            logger.error("validate_metrics_sql_query error: {}\n".format(output))
            return {"success": False, "error": output}
        if isinstance(output, dict):
            if "error" in output:
                logger.error("validate_metrics_sql_query error: {}\n".format(output))
                return {"success": False, "error": output.get("error")}
            if "Message" in output:
                logger.error("validate_metrics_sql_query error: {}\n".format(output))
                return {"success": False, "error": output}
            
            data_block = output.get("data")
            columns = data_block.get("columns") if isinstance(data_block, dict) else None

            if columns and isinstance(columns, list):
                if len(columns) != len(set(columns)):
                    return {
                        "success": False,
                        "error": "The column names are duplicated"
                    }

            result = {
                "success": True,
                "resp": output
            }
            return result
        
        logger.error("validate_metrics_sql_query error: Unexpected response type {}\n".format(type(output)))
        return {"success": False, "error": f"Unexpected response type: {type(output)}"}
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("validate_metrics_sql_query error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}

@mcp.tool()
async def create_metric_sql_query_evidence(
    metricsId: str,
    sqlquery: str,
    referedEvidenceNames: list[str],
    newEvidenceName: str,
    confirm: bool = False,
    ctx: Context | None = None,
) -> dict:
    """
    Create a SQL query evidence for a metricsId.
    
    This tool creates a SQL-based query and associates it with a specified metricsId.

    ⚠️ IMPORTANT WORKFLOW (Two-Step Confirmation)
    1. The SQL query MUST always be shown to the user in PREVIEW mode before execution.
    2. The user can review, edit, or approve the SQL query.
    3. SQL validation is MANDATORY before calling this tool.
       Use `validate_metrics_sql_query` and ensure SQL is valid.
    4. Only after explicit confirmation (confirm=True) will the SQL query be created and attached.
    
    🔍 EVIDENCE & TABLE MAPPING
    - The `referedEvidenceNames` represent existing evidenceConfigNames.
    - These names MUST be used as table names inside the SQL query.
    - A new evidence config will be created using `newEvidenceName` to store the output of the SQL query.

    ⚠️ EVIDENCE ASSUMPTION (MANDATORY)
    - NEVER assume that an evidence config, its structure (schema), or its data exists.
    - NEVER fabricate evidence config names, table structures, or sample data.
    - If required evidence config details, schema, or data are NOT explicitly available:
        → Clearly inform the user that this information is missing.
        → Ask the user to provide:
            - Evidence config name(s)
            - Evidence schema / structure (e.g., columns and types)
            - And/or sample data
    - The tool MUST NOT proceed based on guessed or assumed evidence structures.

    🧪 OPTIONAL QUERY EXECUTION & OUTPUT PREVIEW
    - After showing the SQL preview, the user may optionally request to:
        → Run the SQL query on sample data to preview the output.
    - If sample data is available:
        → The system will manually execute the query and display the result to the user.
    - If sample data is NOT available and the user requests execution:
        → The system must explicitly ask the user to provide sample data before execution.

    Show the suggestion optional to run query to user to run query and see output, U manually perform the run on sample data and show output, If sample data is not available if user ask to run, ask user to provide the sample data.
    
    Args:
        metricsId (str): The metricsId where the query is to be attached (required).
        sqlquery (str): The SQL query definition (required). The query should reference evidenceConfigNames as table names.
                      When confirm=False, this will be displayed in the preview. When confirm=True, the SQL query will be created and attached.
        referedEvidenceNames (list[str]): List of evidenceConfigNames that are referenced as table names in the SQL query (required, non-empty).
        newEvidenceName (str): Name of the new evidence config to be created (required).
        confirm (bool, optional): If False, returns preview with the SQL query displayed for review (and optional modification).
                                 If True, proceeds with SQL query creation using the provided sqlquery.

    Returns:
        Dict with success status and data:
        - success (bool): Whether the request was successful
        - ruleId (str, optional): Created rule ID
        - evidenceId (str, optional): Created evidence Config,
        - message (str, optional): Success or error message
        - sqlquery (str, optional): The SQL query shown in preview (when confirm=False)
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("create_sql_query_evidence: \n")
        
        if not metricsId or not str(metricsId).strip():
            logger.error("create_sql_query_evidence error: metricsId is mandatory\n")
            return {"success": False, "error": "metricsId is mandatory"}
        
        if not sqlquery or not str(sqlquery).strip():
            logger.error("create_sql_query_evidence error: sqlquery is mandatory\n")
            return {"success": False, "error": "sqlquery is mandatory"}
        
        if not newEvidenceName or not str(newEvidenceName).strip():
            logger.error("create_sql_query_evidence error: newEvidenceName is mandatory\n")
            return {"success": False, "error": "newEvidenceName is mandatory"}
        
        # Build payload according to API specification
        payload = {
            "sqlQuery": str(sqlquery).strip(),
            "evidenceName": str(newEvidenceName).strip(),
            "referedEvidenceNames": [str(name).strip() for name in referedEvidenceNames if name and str(name).strip()]
        }
        
        if not confirm:
            logger.info("create_sql_query_evidence: Returning confirmation preview\n")
            return {
                "success": True,
                "message": "Confirmation required before creating SQL query",
                "controlConfigId": str(metricsId).strip(),
                "sqlQuery": payload["sqlQuery"],
                "newEvidenceName": payload["evidenceName"],
                "referedEvidenceNames": payload["referedEvidenceNames"],
                "next_step": "Review the SQL query above. If you need to modify it, provide the updated sqlquery parameter when calling with confirm=True. If correct, re-run with confirm=True to create and attach the query."
            }
        
        url = f"{constants.URL_PLAN_CONTROLS}/{str(metricsId).strip()}/sql-query-evidences"
        
        logger.debug("create_sql_query_evidence payload: {}\n".format(json.dumps(payload)))
        logger.debug("create_sql_query_evidence URL: {}\n".format(url))
        
        # Make API call
        resp = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "POST",
            payload,
            ctx=ctx
        )
        
        logger.debug("create_sql_query_evidence output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))
        
        # Handle error response
        if isinstance(resp, str):
            logger.error("create_sql_query_evidence error: {}\n".format(resp))
            return {"success": False, "error": resp}
        
        if isinstance(resp, dict):
            # Check for error fields
            if "Message" in resp:
                logger.error("create_sql_query_evidence error: {}\n".format(resp))
                return {"success": False, "error": resp}
            
            if "error" in resp:
                logger.error("create_sql_query_evidence error: {}\n".format(resp.get("error")))
                return {"success": False, "error": resp.get("error")}

            rule_id = resp.get("ruleId")
            evidence_id = resp.get("evidenceId")

            if rule_id:
                logger.info(f"create_sql_query_evidence: Successfully created SQL query with ruleId: {rule_id}\n")
                return {
                    "success": True,
                    "evidenceId": evidence_id,
                    "message": "SQL query and evidence config created successfully",
                    "next_step": "Would you like to add documentation notes for this SQL query on the control? This is optional but recommended for traceability."
                }
        
        # Fallback: wrap unexpected response type
        logger.error("create_sql_query_evidence error: Unexpected response type: {}\n".format(type(resp)))
        return {"success": False, "error": f"Unexpected response type: {resp}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_sql_query_evidence error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error creating SQL query: {e}"}

@mcp.tool()
async def list_metric_sql_query_evidence(
    metricsId: str,
    ctx: Context | None = None
) -> dict:
    """
    List all SQL query evidences for a given metricsId.
    
    This tool retrieves all SQL query evidences associated with a control configuration.
    
    Args:
        metricsId (str): The metrics ID to list SQL query evidences for (required).
    
    Returns:
        Dict with success status and evidences:
        - success (bool): Whether the request was successful
        - evidences (list[dict]): List of SQL query evidence objects, each containing:
            - id (str): Evidence ID
            - evidenceId (str): Evidence config ID
            - ruleId (str): Rule ID
            - sqlQuery (str): SQL query string
            - evidenceName (str): Evidence config name
            - referedEvidenceNames (list[str]): List of referenced evidence names
        - totalCount (int): Total number of evidences found
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("list_sql_query_evidence: \n")
        
        if not metricsId or not str(metricsId).strip():
            logger.error("list_sql_query_evidence error: metricsId is mandatory\n")
            return {"success": False, "error": "metricsId is mandatory"}
        
        metrics_id = str(metricsId).strip()
        url = f"{constants.URL_PLAN_CONTROLS}/{metrics_id}/sql-query-evidences"
        
        logger.debug("list_sql_query_evidence URL: {}\n".format(url))
        
        output = await utils.make_GET_API_call_to_CCow(url, ctx=ctx)
        
        if isinstance(output, str) or (isinstance(output, dict) and "error" in output):
            logger.error("list_sql_query_evidence error: {}\n".format(output))
            return {"success": False, "error": "Failed to fetch SQL query evidences"}
        
        if isinstance(output, dict):
            if "Message" in output:
                logger.error("list_sql_query_evidence error: {}\n".format(output))
                return {"success": False, "error": output}
            
            items = output.get("items", [])
            if not isinstance(items, list):
                items = []
            
            logger.info(f"list_sql_query_evidence: Found {len(items)} SQL query evidence(s)\n")
            return {"success": True, "evidences": items, "totalCount": len(items)}

        logger.error("list_sql_query_evidence error: Unexpected response type: {}\n".format(type(output)))
        return {"success": False, "error": f"Unexpected response type: {output}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_sql_query_evidence error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error listing SQL query evidences: {e}"}

@mcp.tool()
async def update_metric_sql_query_evidence(
    metricsId: str,
    evidenceId: str,
    sqlquery: str,
    referedEvidenceNames: list[str],
    newEvidenceName: str,
    confirm: bool = False,
    ctx: Context | None = None,
) -> dict:
    """
    Update an existing SQL query evidence for a control configuration.
    
    This tool updates an existing SQL query evidence with new SQL query, evidence mappings, or evidence name.

    ⚠️ IMPORTANT WORKFLOW (Two-Step Confirmation)
    1. The updated SQL query MUST always be shown to the user in PREVIEW mode before execution.
    2. The user can review, edit, or approve the updated SQL query.
    3. SQL validation is MANDATORY before calling this tool.
       Use `validate_metrics_sql_query` and ensure SQL is valid.
    4. Only after explicit confirmation (confirm=True) will the SQL query evidence be updated.
    
    🔍 EVIDENCE & TABLE MAPPING
    - The `referedEvidenceNames` represent existing evidenceConfigNames.
    - These names MUST be used as table names inside the SQL query.
    - The evidence config name can be updated using `newEvidenceName`.
    
    Args:
        metricsId (str): The metrics ID where the SQL query evidence exists (required).
        evidenceId (str): The evidence ID of the SQL query evidence to update (required).
        sqlquery (str): The updated SQL query definition (required). The query should reference evidenceConfigNames as table names.
                      When confirm=False, this will be displayed in the preview. When confirm=True, the SQL query will be updated.
        referedEvidenceNames (list[str]): List of evidenceConfigNames that are referenced as table names in the SQL query (required, non-empty).
        newEvidenceName (str): Updated name of the evidence config (required).
        confirm (bool, optional): If False, returns preview with the updated SQL query displayed for review (and optional modification).
                                 If True, proceeds with SQL query evidence update using the provided sqlquery.
        entityHierarchyReferenceName (str, optional): Reference name for entity hierarchy table.
        additionalContextReferenceName (str, optional): Reference name for additional control context table.

    Returns:
        Dict with success status and data:
        - success (bool): Whether the request was successful
        - evidenceId (str, optional): Updated evidence ID
        - message (str, optional): Success or error message
        - sqlquery (str, optional): The SQL query shown in preview (when confirm=False)
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("update_sql_query_evidence: \n")
        
        if not metricsId or not str(metricsId).strip():
            logger.error("update_sql_query_evidence error: metricsId is mandatory\n")
            return {"success": False, "error": "metricsId is mandatory"}
        
        if not evidenceId or not str(evidenceId).strip():
            logger.error("update_sql_query_evidence error: evidenceId is mandatory\n")
            return {"success": False, "error": "evidenceId is mandatory"}
        
        if not sqlquery or not str(sqlquery).strip():
            logger.error("update_sql_query_evidence error: sqlquery is mandatory\n")
            return {"success": False, "error": "sqlquery is mandatory"}
        
        if not newEvidenceName or not str(newEvidenceName).strip():
            logger.error("update_sql_query_evidence error: newEvidenceName is mandatory\n")
            return {"success": False, "error": "newEvidenceName is mandatory"}
        
        # Build payload according to API specification
        payload = {
            "sqlQuery": str(sqlquery).strip(),
            "evidenceName": str(newEvidenceName).strip(),
            "referedEvidenceNames": [str(name).strip() for name in referedEvidenceNames if name and str(name).strip()]
        }
        
        if not confirm:
            logger.info("update_sql_query_evidence: Returning confirmation preview\n")
            return {
                "success": True,
                "message": "Confirmation required before updating SQL query evidence",
                "controlConfigId": str(metricsId).strip(),
                "evidenceId": str(evidenceId).strip(),
                "sqlQuery": payload["sqlQuery"],
                "newEvidenceName": payload["evidenceName"],
                "referedEvidenceNames": payload["referedEvidenceNames"],
                "next_step": "Review the updated SQL query above. If you need to modify it, provide the updated sqlquery parameter when calling with confirm=True. If correct, re-run with confirm=True to update the SQL query evidence."
            }
        
        url = f"{constants.URL_PLAN_CONTROLS}/{str(metricsId).strip()}/sql-query-evidences/{str(evidenceId).strip()}"
        
        logger.debug("update_sql_query_evidence payload: {}\n".format(json.dumps(payload)))
        logger.debug("update_sql_query_evidence URL: {}\n".format(url))
        
        resp = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "PUT",
            payload,
            ctx=ctx
        )
        
        logger.debug("update_sql_query_evidence output: {}\n".format(json.dumps(resp) if isinstance(resp, dict) else resp))
        
        # Handle error response
        if isinstance(resp, str):
            logger.error("update_sql_query_evidence error: {}\n".format(resp))
            return {"success": False, "error": resp}
        
        if isinstance(resp, dict):
            # Check for error fields
            if "Message" in resp:
                logger.error("update_sql_query_evidence error: {}\n".format(resp))
                return {"success": False, "error": resp}
            
            if "error" in resp:
                logger.error("update_sql_query_evidence error: {}\n".format(resp.get("error")))
                return {"success": False, "error": resp.get("error")}

            updated_evidence_id = resp.get("evidenceId") or str(evidenceId).strip()

            logger.info(f"update_sql_query_evidence: Successfully updated SQL query evidence with evidenceId: {updated_evidence_id}\n")
            return {
                "success": True,
                "evidenceId": updated_evidence_id,
                "message": "SQL query evidence updated successfully",
            }
        
        logger.error("update_sql_query_evidence error: Unexpected response type: {}\n".format(type(resp)))
        return {"success": False, "error": f"Unexpected response type: {resp}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_sql_query_evidence error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error updating SQL query evidence: {e}"}




@mcp.tool()
async def add_cel_expression_to_metrics(
    metricsId: str,
    metricsEvidenceId  :str,
    filteringExpression: str,
    compliantExpression: str,
    ctx: Context | None = None,
) -> dict:
    """
    Add CEL expressions to an existing metric.
    """
    try:
        logger.info("add_metrics_cel_expression:\n")

        metrics_id = (metricsId or "").strip()
        filtering_expression = (filteringExpression or "").strip()
        compliant_expression = (compliantExpression or "").strip()

        if not metrics_id:
            return {"success": False, "error": "metricsId is required"}
        if not filtering_expression:
            return {"success": False, "error": "filteringExpression is required"}
        if not compliant_expression:
            return {"success": False, "error": "compliantExpression is required"}

        payload = [
            {
                "op": "add",
                "path": "/complianceCalculationInfos",
                "value": {
                "gocel": {
                    "include": filtering_expression,
                    "compliance": compliant_expression
                }
            }
            }
        ]

        logger.debug(
            "add_metrics_cel_expression payload: {}\n".format(json.dumps(payload))
        )

        resp_raw = await utils.make_API_call_to_CCow_and_get_response(
            f"{constants.URL_PLAN_CONTROLS}/{metrics_id}/evidences/{metricsEvidenceId}", "PATCH", payload,return_raw=True, ctx=ctx
        )

        if resp_raw.status_code == 502:
            return {"success": False, "error": error_constants.ERROR_BAD_GATEWAY}
        
        
        if resp_raw.status_code == 204:
            return {"success": True, "message": "CEL expressions added successfully"}

        else:
                        # Error - parse error response
            error_resp = {}
            try:
                if resp_raw.content:
                    error_resp = resp_raw.json()
            except Exception:
                error_resp = {"error": f"HTTP {resp_raw.status_code}"}
            
            logger.error("create_metrics_note error: Status {} - {}\n".format(resp_raw.status_code, error_resp))
            
            # Check for error fields in response
            if isinstance(error_resp, dict):
                if "Message" in error_resp:
                    return {"success": False, "error": error_resp}
                if "error" in error_resp:
                    return {"success": False, "error": error_resp.get("error")}

            return {"success": False, "error": f"Failed to add CEL expressions: HTTP {resp_raw.status_code}"}
     
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("add_metrics_cel_expression error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}


@mcp.tool()
async def update_cel_expression_to_metrics(
    metricsId: str,
    metricsEvidenceId  :str,
    filteringExpression: str,
    compliantExpression: str,
    ctx: Context | None = None,
) -> dict:
    """
    Update CEL expressions to an existing metric.
    """
    try:
        logger.info("update_cel_expression_to_metrics:\n")

        metrics_id = (metricsId or "").strip()
        filtering_expression = (filteringExpression or "").strip()
        compliant_expression = (compliantExpression or "").strip()

        if not metrics_id:
            return {"success": False, "error": "metricsId is required"}
        if not filtering_expression:
            return {"success": False, "error": "filteringExpression is required"}
        if not compliant_expression:
            return {"success": False, "error": "compliantExpression is required"}

        payload = [
            {
                "op": "add",
                "path": "/complianceCalculationInfos",
                "value": {
                "gocel": {
                    "include": filtering_expression,
                    "compliance": compliant_expression
                }
            }
            }
        ]

        logger.debug(
            "update_cel_expression_to_metrics payload: {}\n".format(json.dumps(payload))
        )

        resp_raw = await utils.make_API_call_to_CCow_and_get_response(
            f"{constants.URL_PLAN_CONTROLS}/{metrics_id}/evidences/{metricsEvidenceId}", "PATCH", payload,return_raw=True, ctx=ctx
        )

        if resp_raw.status_code == 502:
            return {"success": False, "error": error_constants.ERROR_BAD_GATEWAY}
        
        
        if resp_raw.status_code == 204:
            return {"success": True, "message": "CEL expressions uplodated successfully"}

        else:
                        # Error - parse error response
            error_resp = {}
            try:
                if resp_raw.content:
                    error_resp = resp_raw.json()
            except Exception:
                error_resp = {"error": f"HTTP {resp_raw.status_code}"}
            
            logger.error("update_cel_expression_to_metrics error: Status {} - {}\n".format(resp_raw.status_code, error_resp))
            
            # Check for error fields in response
            if isinstance(error_resp, dict):
                if "Message" in error_resp:
                    return {"success": False, "error": error_resp}
                if "error" in error_resp:
                    return {"success": False, "error": error_resp.get("error")}

            return {"success": False, "error": f"Failed to add CEL expressions: HTTP {resp_raw.status_code}"}
     
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_cel_expression_to_metrics error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}



@mcp.tool()
async def get_cel_expression_for_metrics(metricsId: str,evidenceId:str, ctx: Context | None = None) -> dict:
    """
    Get CEL expressions of an existing metric.
    """

    try:
        logger.info("get_cel_expression_for_metrics:\n")

        metrics_id = (metricsId or "").strip()

        if not metrics_id:
            return {"success": False, "error": "metricsId is required"}
        
        if not evidenceId or not str(evidenceId).strip():
            return {"success": False, "error": "evidenceId is required"}

        assessment_control, error = await get_assessment_control(metrics_id, ctx=ctx) 

        if error:
            logger.error("get_cel_expression_for_metrics error: {}\n".format(error))
            return {"success": False, "error": error}
        

        evidences = assessment_control.get("evidences", [])

        evidence_obj = next(
            (e for e in evidences if e.get("id") == evidenceId),
            None
        )

        compliance_calculation_infos = evidence_obj.get("complianceCalculationInfos", {}) if evidence_obj else {}
        gocel_info = compliance_calculation_infos.get("gocel", {})

        filtering_expression = gocel_info.get("include", "")
        compliant_expression = gocel_info.get("compliance", "")

        if not filtering_expression and not compliant_expression:
            return {"success": False, "error": "No CEL expressions found for this evidence"}

        return {
            "success": True,
            "filteringExpression": filtering_expression,
            "compliantExpression": compliant_expression
        }


    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_cel_expression_for_metrics error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error: {e}"}

@mcp.tool()
async def create_metrics_note(
    metricsId: str,
    assessmentMetricsId: str,
    notes: str,
    topic: str,
    confirm: bool = False,
    ctx: Context | None = None,
) -> dict:
    """
    Create a documentation note on a metrics.
    
    This tool creates a markdown documentation note that is attached to a control configuration.
    

    Args:
        metricsId (str): The metrics ID where the note will be attached (required).
                              This is the same metrics ID used in `create_sql_query_evidence`.
        assessmentMetricsId (str): The assessment ID that contains the metrics (required).
        notes (str): The documentation content in MARKDOWN format (required).
        topic (str, optional): Topic or subject of the note. Defaults to "SQL Query Documentation".
        confirm (bool, optional):  
            - False → Preview only (default, no persistence)
            - True  → Create and permanently attach the note
    
    Returns:
        Dict with success status and note data:
        - success (bool): Whether the request was successful
        - note (dict, optional): Created note object containing:
            - id (str): Note ID
            - topic (str): Note topic
            - notes (str): Note content in markdown format
            - metricsId (str): Metrics ID the note is attached to
            - assessmentMetricsId (str): Assessment metrics ID
        - error (str, optional): Error message if request failed
        - next_action (str, optional): Recommended next action
    """
    try:
        logger.info("create_metrics_note: \n")
        
        if not metricsId or not str(metricsId).strip():
            logger.error("create_metrics_note error: metricsId is mandatory\n")
            return {"success": False, "error": "metricsId is mandatory"}
        
        if not assessmentMetricsId or not str(assessmentMetricsId).strip():
            logger.error("create_metrics_note error: assessmentMetricsId is mandatory\n")
            return {"success": False, "error": "assessmentMetricsId is mandatory"}
        
        if not notes or not str(notes).strip():
            logger.error("create_metrics_note error: notes content is mandatory\n")
            return {"success": False, "error": "notes content is mandatory"}
        
        # Build payload
        payload = {
            "topic": str(topic).strip(),
            "notes": str(notes).strip(),
            "planId": str(assessmentMetricsId).strip(),
            "planControlID": str(metricsId).strip(),
        }

        if not confirm:
            logger.info("create_metrics_note: Returning confirmation preview\n")
            return {
                "success": True,
                "message": "Confirmation required before creating note",
                "metricsId": payload["planControlID"],
                "topic": payload["topic"],
                "notes": payload["notes"],
                "next_step": "Review the Note above. If you need to modify it, provide the updated note parameter when calling with confirm=True. If correct, re-run with confirm=True to create note."
        }
        
        # Construct URL with control config ID
        url = constants.URL_PLAN_CONTROL_NOTES.format(controlConfigId=str(metricsId).strip())
        
        logger.debug("create_metrics_note payload: {}\n".format(json.dumps(payload)))
        logger.debug("create_metrics_note URL: {}\n".format(url))
        
        # Make API call
        resp_raw = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "POST",
            payload,
            return_raw=True,
            ctx=ctx
        )

        if resp_raw.status_code == 502:
            return {"success": False, "error": error_constants.ERROR_BAD_GATEWAY}
        
        
        if resp_raw.status_code == 201:
            resp = {}
            try:
                if resp_raw.content:
                    resp = resp_raw.json()
            except Exception:
                resp = {"error": f"HTTP {resp_raw.status_code}"}

            logger.info(f"create_metrics_note: \n Response : {resp}\n")
            noteId = ""
            if isinstance(resp, dict):
                noteId = resp.get("id")
            
            logger.info(f"create_metrics_note: Successfully created note with status 201\n")
            return {
                "success": True,
                "noteId": noteId,
                "message": "Note created successfully",
            }
        else:
            # Error - parse error response
            error_resp = {}
            try:
                if resp_raw.content:
                    error_resp = resp_raw.json()
            except Exception:
                error_resp = {"error": f"HTTP {resp_raw.status_code}"}
            
            logger.error("create_metrics_note error: Status {} - {}\n".format(resp_raw.status_code, error_resp))
            
            # Check for error fields in response
            if isinstance(error_resp, dict):
                if "Message" in error_resp:
                    return {"success": False, "error": error_resp}
                if "error" in error_resp:
                    return {"success": False, "error": error_resp.get("error")}

            return {"success": False, "error": f"Failed to create note: HTTP {resp_raw.status_code}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_metrics_note error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error creating metrics note: {e}"}


@mcp.tool()
async def list_metrics_notes(
    metricsId: str,
    ctx: Context | None = None
) -> dict:
    """
    List all notes for a given metrics ID.
    
    Args:
        metricsId (str): The metrics ID to list notes for (required).
    
    Returns:
        Dict with success status and notes:
        - success (bool): Whether the request was successful
        - notes (list[dict]): List of note objects, each containing:
            - id (str): Note ID
            - topic (str): Note topic
            - notes (str): Note content
        - totalCount (int): Total number of notes found
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("list_metrics_notes: \n")
        
        if not metricsId or not str(metricsId).strip():
            logger.error("list_metrics_notes error: metricsId is mandatory\n")
            return {"success": False, "error": "metricsId is mandatory"}
        
        metrics_id = str(metricsId).strip()
        url = constants.URL_PLAN_CONTROL_NOTES.format(controlConfigId=metrics_id)
        
        logger.debug("list_metrics_notes URL: {}\n".format(url))
        
        output = await utils.make_GET_API_call_to_CCow(url, ctx=ctx)
        
        error = utils.handle_error_response(output,"list_metrics_notes")
        if error:
            logger.error("list_metrics_notes error: {}\n".format(error))
            return {"success": False, "error": error}

        items = output.get("items", [])
        if not isinstance(items, list):
            items = []

        abstracted_items = []
        for item in items:
            if isinstance(item, dict):
                abstracted_item = {
                    "id": item.get("id", ""),
                    "topic": item.get("topic", ""),
                    "notes": item.get("notes", ""),
                }
                abstracted_items.append(abstracted_item)
        
        logger.info(f"list_metrics_notes: {abstracted_items} \n Found {len(abstracted_items)} note(s)\n")
        return {"success": True, "notes": abstracted_items, "totalCount": len(abstracted_items)}
    
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_metrics_notes error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error listing metrics notes: {e}"}

@mcp.tool()
async def update_metrics_note(
    metricsId: str,
    noteId: str,
    assessmentId: str,
    notes: str,
    topic: str,
    confirm: bool = False,
    ctx: Context | None = None,
) -> dict:
    """
    Update an existing documentation note on a metrics.
    
    ✅ PURPOSE
    This tool updates an existing note that was previously created on a metrics.
    It allows modification of the note content, topic, or both.
    
    ✅ CONFIRMATION-BASED SAFETY FLOW
    - When confirm=False:
        → The tool returns a PREVIEW of the updated markdown note.
        → The user may edit the note before confirming.
    - When confirm=True:
        → The note is permanently updated and saved.
    
    Args:
        metricsId (str): The metrics ID where the note exists (required).
        noteId (str): The note ID to update (required).
        assessmentId (str): The assessment ID that contains the metrics (required).
        notes (str): The updated documentation content in MARKDOWN format (required).
        topic (str, optional): Updated topic or subject of the note. Defaults to "SQL Query Documentation".
        confirm (bool, optional):  
            - False → Preview only (default, no persistence)
            - True  → Update and permanently save the note
    
    Returns:
        Dict with success status and note data:
        - success (bool): Whether the request was successful
        - message (str, optional): Success or error message
        - noteId (str, optional): Updated note ID
        - error (str, optional): Error message if request failed
    """
    try:
        logger.info("update_metrics_note: \n")
        
        if not metricsId or not str(metricsId).strip():
            logger.error("update_metrics_note error: metricsId is mandatory\n")
            return {"success": False, "error": "metricsId is mandatory"}
        
        if not noteId or not str(noteId).strip():
            logger.error("update_metrics_note error: noteId is mandatory\n")
            return {"success": False, "error": "noteId is mandatory"}
        
        if not assessmentId or not str(assessmentId).strip():
            logger.error("update_metrics_note error: assessmentId is mandatory\n")
            return {"success": False, "error": "assessmentId is mandatory"}
        
        if not notes or not str(notes).strip():
            logger.error("update_metrics_note error: notes content is mandatory\n")
            return {"success": False, "error": "notes content is mandatory"}
        
        # Build payload
        payload = {
            "topic": str(topic).strip(),
            "notes": str(notes).strip(),
            "planId": str(assessmentId).strip(),
            "planControlID": str(metricsId).strip(),
        }

        if not confirm:
            logger.info("update_metrics_note: Returning confirmation preview\n")
            return {
                "success": True,
                "message": "Confirmation required before updating note",
                "metricsId": payload["planControlID"],
                "noteId": str(noteId).strip(),
                "topic": payload["topic"],
                "notes": payload["notes"],
                "next_step": "Review the updated Note above. If you need to modify it, provide the updated notes or topic parameters when calling with confirm=True. If correct, re-run with confirm=True to update the note."
            }
        
        # Construct URL with metrics ID and note ID
        url = f"{constants.URL_PLAN_CONTROL_NOTES.format(controlConfigId=str(metricsId).strip())}/{str(noteId).strip()}"
        
        logger.debug("update_metrics_note payload: {}\n".format(json.dumps(payload)))
        logger.debug("update_metrics_note URL: {}\n".format(url))
        
        # Make API call
        resp_raw = await utils.make_API_call_to_CCow_and_get_response(
            url,
            "PUT",
            payload,
            return_raw=True,
            ctx=ctx
        )

        if resp_raw.status_code == 502:
            return {"success": False, "error": error_constants.ERROR_BAD_GATEWAY}
        
        if resp_raw.status_code == 204:
            logger.info(f"update_metrics_note: Successfully updated note with status 204\n")
            return {
                "success": True,
                "noteId": str(noteId).strip(),
                "message": "Note updated successfully",
            }
        else:
            # Error - parse error response
            error_resp = {}
            try:
                if resp_raw.content:
                    error_resp = resp_raw.json()
            except Exception:
                error_resp = {"error": f"HTTP {resp_raw.status_code}"}
            
            logger.error("update_metrics_note error: Status {} - {}\n".format(resp_raw.status_code, error_resp))
            
            # Check for error fields in response
            if isinstance(error_resp, dict):
                if "Message" in error_resp:
                    return {"success": False, "error": error_resp}
                if "error" in error_resp:
                    return {"success": False, "error": error_resp.get("error")}

            return {"success": False, "error": f"Failed to update note: HTTP {resp_raw.status_code}"}
        
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_metrics_note error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error updating metrics note: {e}"}
 

@mcp.tool() 
async def link_source_metrics_to_target_metric(sourceMetricsIds: list[str], targetMetricId: str, ctx: Context | None = None) -> dict: 
    """
    Args:
    query (str): The Cypher query to execute against the graph database.
    
    Returns:
        - result (Any): The formatted, human-readable result of the Cypher query.
        - error (Optional[str]): An error message if the query execution fails or encounters issues.
    """

    try:
        logger.info("link_source_metrics_to_metric: \n")

        if not sourceMetricsIds:
            return "sourceMetricsIds is required"
        
        if not targetMetricId or not targetMetricId.strip():
            return "targetMetricId is required"        


        payload = [
            {
                "sourcePlan": {
                    "controlId": source_id
                },
                "targetPlan": {
                    "controlId": targetMetricId
                },
                "userGenerated": True,
                "propagate": "evidence",
                "propagateToSource": "none",
                "nonReportable": True,
            }
            for source_id in sourceMetricsIds
        ]

        logger.info(f"link_source_metrics_to_metric payload: {payload}\n")


        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_LINK_CONTROL,
            "POST",
            payload,
            ctx=ctx
        )

        error = utils.handle_error_response(output,"link_source_metrics_to_metric")

        if error:
            return error
        
        return {"success":True, "message" : "Source metrics were successfully linked to the target metric."}


    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("link_source_metrics_to_metric error: {}\n".format(e))
        return {"success": False, "error": f"Unexpected error linking source metrics to target metric notes: {e}"}


# @mcp.tool()
async def get_graph_schema_relationship() -> dict | str:
    """
    Retrieve the complete graph database schema and relationship structure
    
    Returns:
        dict: Complete database schema with structural patterns and query guidelines
        str: Error message if schema retrieval fails
    """
    
    try:
        logger.info("\nget_schema_form_control: \n")
        output=await utils.make_API_call_to_CCow({},constants.URL_RETRIEVE_GRAPH_SCHEMA_RELATIONSHIP)
        logger.debug("output: {}\n".format(output))
        enhanced_guidance = {
            "control_status_values": {
                "status": ["Completed", "In Progress", "Pending", "Unassigned"],
                "complianceStatus": ["COMPLIANT", "NON_COMPLIANT", "NOT_DETERMINED"],
                "priority(case insensitive)": ["Low", "Medium", "High"],
                "overdue_logic": "Controls are overdue when due_date < current_date is [In progress, Pending] (requires manual date comparison)"
            },
            "query_best_practices": {
                "large_datasets": "Use LIMIT clauses and aggregation functions for performance",
                "hierarchy_traversal": "Always determine depth before complex recursive queries",
                "evidence_queries": "Evidence only exists on leaf controls - filter accordingly",
                "performance_tips": [
                    "Use WHERE clauses early in queries for filtering",
                    "Prefer specific relationship patterns over generic traversal",
                    "Use PROFILE or EXPLAIN for query optimization"
                ]
            },
            "common_patterns": {
                "find_roots": "MATCH (c:Control) WHERE NOT ()-[:HAS_CHILD]->(c)",
                "find_leaves": "MATCH (c:Control) WHERE NOT (c)-[:HAS_CHILD]->()",
                "full_hierarchy": "MATCH (root)-[:HAS_CHILD*]->(descendant)",
                "evidence_with_controls": "MATCH (c:Control)-[:HAS_EVIDENCE]->(e:Evidence) WHERE NOT (c)-[:HAS_CHILD]->()"
            },
            "large_dataset_handling": {
                "description": "Strategies for managing overwhelming query results",
                "detection_approach": "Identify broad queries through parameter analysis and keyword detection", 
                "response_strategy": "Provide summary statistics and guided refinement suggestions",
                "user_experience_goals": [
                    "Prevent information overload",
                    "Guide users to actionable insights", 
                    "Offer immediate value through summaries",
                    "Enable progressive query refinement"
                ]
            },
            "refinement_suggestions": {
                "controls": {
                    "status_based": "Filter by completion state, progress status, assignment status, or overdue conditions",
                    "compliance_status_based": "Focus on compliance outcomes", 
                    "framework_based": "Narrow by specific regulatory frameworks or compliance standards",
                    "priority_based": "Filter by control prioriy",
                    "time_period_based": "control on specific date, date range, or review period"
                },
            },
            "user_guidance_approach": {
                "summary_first": "Always provide high-level statistics and patterns before detailed results",
                "contextual_suggestions": "Offer refinement options specific to the data and user context",
                "progressive_refinement": "Enable users to iteratively narrow their focus through guided questions",
                "actionable_examples": "Provide concrete, ready-to-use query phrases that users can immediately apply",
                "visual_formatting": "Use clear structure, emojis, and hierarchy to make responses scannable"
            },
            "Risks": "RiskItem nodes are attached to control-config via HAS_RISK & HAS_MAPPED_CONTROL edges and RiskItemAttribute nodes are attached to RiskItem via HAS_ATTRIBUTE edges, Both nodes are always linked"
        }

        # return {"Important": "If you need to check control, find try to find how much nested level of controls available then query according", "output": output}
        return {
         "output": output,
         "guidance": enhanced_guidance
         }
    except Exception as e:
        logger.error("get_schema_form_control error: {}\n".format(e))
        return "Facing internal error"        


# @mcp.tool() 
async def execute_cypher_query(query: str, ctx: Context | None = None) -> CypherQueryVO: 
    """
    Args:
    query (str): The Cypher query to execute against the graph database.
    
    Returns:
        - result (Any): The formatted, human-readable result of the Cypher query.
        - error (Optional[str]): An error message if the query execution fails or encounters issues.
    """
    try:
        logger.info("\nexecute_cypher_query: \n")
        logger.debug("query: {}".format(query))

        output=await utils.make_API_call_to_CCow({
            "query": query,
        },constants.URL_EXECUTE_CYPHER_QUERY, ctx=ctx)
        logger.debug("output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("\nexecute_cypher_query error: {}\n".format(output))
            return CypherQueryVO(error="Facing internal error")

        return CypherQueryVO(result=output.get('result'))
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("\nexecute_cypher_query error: {}\n".format(e))
        return CypherQueryVO(error="Facing internal error")


async def get_assessment(id: str, ctx: Context) -> tuple[dict | None, dict | None]:

    url = f"{constants.URL_PLANS}/{id}?fields=basic"

    output = await utils.make_API_call_to_CCow_and_get_response(
            url, "GET", ctx=ctx
        )
    
    error = utils.handle_error_response(output,"get_assessment_method")

    if error:
        return None, error

    return output, None


async def get_assessment_control(id: str, ctx: Context) -> tuple[dict | None, dict | None]:

    url = f"{constants.URL_PLAN_CONTROLS}/{id}?fields=basic"

    output = await utils.make_API_call_to_CCow_and_get_response(
            url, "GET", ctx=ctx
        )
    
    error = utils.handle_error_response(output,"get_assessment_control_method")

    if error:
        return None, error

    return output, None


async def get_assessment_run(ctx: Context, assessment_id: str, ids: str = None, size: int = 10, basicFields: bool = True) -> tuple[dict | None, dict | None]:

    url = f"{constants.URL_PLAN_INSTANCES}?plan_id={assessment_id}&"

    if ids is not None:
        url += f"ids={ids}&"
    else:
        url += f"page=1&page_size={size}&"

    if basicFields:
        url += "fields=basic&"

    output = await utils.make_API_call_to_CCow_and_get_response(
            url, "GET", ctx=ctx
        )
    
    error = utils.handle_error_response(output,"get_assessment_run_method")

    if error:
        return None, error

    return output, None


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

async def fetch_evidence_sample(
    ctx,
    evidence: dict,
    sample_size: int = 3,
    ignored_evidence_names: set[str] = {"logfile", "auditfile"},
    excluded_columns: set[str] = set(),
):
    evidence_id = evidence.get("id")
    evidence_name = evidence.get("name", "")
    evidence_description = evidence.get("description", "")
    evidence_status = evidence.get("status", "")

    ignored_evidence_names = {
        (name or "").strip().lower() for name in ignored_evidence_names
    }
    excluded_columns = {
        (col or "").strip().lower() for col in excluded_columns
    }

    if (evidence_name or "").strip().lower() in ignored_evidence_names:
        return None

    if evidence_status != "Completed":
        return None

    evidence_obj = {
        "evidenceRunId": evidence_id,
        "evidenceName": evidence_name,
        "evidenceDescription": evidence_description,
        "sampleRecords": [],
    }

    if not evidence_id:
        return evidence_obj

    fetch_data_payload = {
        "evidenceID": evidence_id,
        "returnFormat": "json",
        "isRelatedDataToBeInclude": True,
        "isDataToBeSplitted": True,
    }

    fetch_data_resp = await utils.make_API_call_to_CCow(
        fetch_data_payload,
        constants.URL_DATAHANDLER_FETCH_DATA,
        ctx=ctx,
    )

    fetch_data_error = utils.handle_error_response(
        fetch_data_resp,
        "get_asset_metrics_evidence_sample_data:fetch_data",
    )

    if fetch_data_error:
        evidence_obj["error"] = (
            fetch_data_error.get("error")
            if isinstance(fetch_data_error, dict)
            else fetch_data_error
        )
        return evidence_obj

    if isinstance(fetch_data_resp, dict) and fetch_data_resp.get("Message") == "CANNOT_FIND_THE_FILE":
        evidence_obj["error"] = "No data available"
        return evidence_obj

    if not (isinstance(fetch_data_resp, dict) and fetch_data_resp.get("fileBytes")):
        evidence_obj["error"] = "fileBytes not found in fetch-data response"
        return evidence_obj

    try:
        decoded_bytes = base64.b64decode(fetch_data_resp["fileBytes"])
        decoded_string = decoded_bytes.decode("utf-8")
        decoded_json = json.loads(decoded_string)

        if isinstance(decoded_json, list):
            evidence_obj["sampleRecords"] = [
                {k: v for k, v in row.items() if (k or "").lower() not in excluded_columns}
                if isinstance(row, dict)
                else row
                for row in decoded_json[:sample_size]
            ]
        elif isinstance(decoded_json, dict):
            evidence_obj["sampleRecords"] = [
                {k: v for k, v in decoded_json.items() if (k or "").lower() not in excluded_columns}
            ]
        else:
            evidence_obj["error"] = "Decoded evidence data is not JSON object/list"

    except Exception as decode_error:
        evidence_obj["error"] = f"Failed to decode sample evidence data: {decode_error}"

    return evidence_obj
