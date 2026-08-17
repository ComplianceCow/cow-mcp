
import traceback

from utils import utils
from utils.debug import logger
from mcptypes.graph_tool_types import CypherQueryVO
from mcptypes.report_tool_types import InsightsCategoryListVO, InsightsCategoryVO
from mcptypes.workflow_tools_type import WorkflowConfigVO, WorkflowInanceVO
from mcpconfig.config import mcp
from constants import constants
from fastmcp import Context
from mcptypes import forms_tool_types as vo

@mcp.tool() 
async def execute_cypher_query_for_reports(query: str, ctx: Context | None = None) -> CypherQueryVO: 
    """
    All the required information is available in the Neo4j graph. If any information is needed, fetch the data from the graph using this function. 
    If schema information is required, use the execute_cypher_query function to retrieve the relevant schema.
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


@mcp.tool()
async def fetch_custom_report_categories(ctx: Context | None = None) -> InsightsCategoryListVO:
    """
        Get all custom report categories
        
        Returns:
            - insights_categories (list[AssetsVo]): A list of assets.
                - id (str):  insights category id.
                - name (str): Name of the insights category.
                - displayable (str): displayable of the insights category.
            - error (Optional[str]): An error message if any issues occurred during retrieval. 
    """
    try:
        logger.info("fetch_custom_report_categories: \n")

        output=await utils.make_GET_API_call_to_CCow(constants.URL_INSIGHTS_CATEGORY, ctx)
        logger.debug("custom report categoires output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("list_all_insights_categories error: {}\n".format(output))
            return InsightsCategoryListVO(error="Facing internal error")

        insights_categories: list[InsightsCategoryVO]=[]
        if not output.get("items") or len(output["items"]) == 0:
            logger.warning(f"No insights category found.")
            return InsightsCategoryListVO(insights_categories=insights_categories)
        
        for item in output["items"]:
            if "name" in item:
                insights_categories.append(InsightsCategoryVO.model_validate(item))
        
        # logger.debug("modified insight categoies: {}\n".format(InsightsCategoryVO(insights_categories=insights_categories).model_dump))

        return InsightsCategoryListVO(insights_categories=insights_categories)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("insight categoies error: {}\n".format(e))
        return InsightsCategoryListVO(error="Facing internal error")    
    
    
async def fetch_workflow_config_for_custom_report(ctx: Context | None = None) -> WorkflowConfigVO:
    try:
        logger.info("fetch workflow configuration for custom reports: \n")
        output=await utils.make_GET_API_call_to_CCow(constants.URL_WORKFLOW_V1+"?name=Upload report card", ctx)
        logger.debug("workflow configuration for custom report -  output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("workflow configuration for custom report -  error: {}\n".format(output))
            return WorkflowConfigVO(error="Facing internal error")
        
        workflow_config: WorkflowConfigVO = {}
        if not output.get("items") or len(output["items"]) == 0:
            logger.warning(f"No workflow configuration found.")
            return workflow_config
        
        for item in output["items"]:
            if "name" in item:
                workflow_config = WorkflowConfigVO.model_validate(item)
                
        return workflow_config
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("workflow configuration for custom report -  error: {}\n".format(e))
        return WorkflowConfigVO(error="Facing internal error")    
    
    
# @mcp.tool()
async def upload_new_custom_report(name: str, description: str, file_bytes: str,category_id: str,level: str, ctx: Context | None = None) -> WorkflowInanceVO:
    """
        Create the new custom report in ComplianceCow.
        
        Returns:
            - name (str):  name of the new report.
            - description (str): description of the new report.
            - file_bytes (str): new custom report zip file as string.
            - category_id (str): category id of the custom report categories. 
            - level (str): level of the custom report categories. It should be one of the user and system. 
    """
    try:
        logger.info("upload_new_custom_report: \n")
        workflow_config_obj = await fetch_workflow_config_for_custom_report(ctx)
        workflow_config = workflow_config_obj.model_dump()
        if not workflow_config.get("id"):
                return WorkflowInanceVO(error="custom report workflow configuration not found")
            
        req_body = {
            "input":{
                "name":name,
                "description":description,
                "file_bytes":file_bytes,
                "categoryID":category_id,
                "level":level,
            },
            "workflowConfigId":workflow_config.get("id")
        }
        
        logger.debug("custom report upload req_body: {}\n".format(req_body))
        
        output=await utils.make_API_call_to_CCow(req_body,constants.URL_WORKFLOW_INSTANCE, ctx)
        logger.debug("custom report upload output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("create new custom report -  error: {}\n".format(output))
            return WorkflowInanceVO(error="Facing internal error")

        if not output.get("id"):
            logger.warning(f"custon report upload failed.")
            return WorkflowInanceVO(error="Facing internal error")
        
        return WorkflowInanceVO(id=output.get("id"))
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("creating new custom report - error: {}\n".format(e))
        return WorkflowInanceVO(error="Facing internal error")    
    
    
def create_report_files(report_dir: str, files: dict[str, str]):
    import os
    os.makedirs(report_dir, exist_ok=True)
    for rel_path, content in files.items():
        file_path = os.path.join(report_dir, rel_path)
        # Ensure parent directories exist (e.g. data/)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

def create_report_zip_from_dict(files: dict[str, str]) -> bytes:
    import io
    import zipfile
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for rel_path, content in files.items():
            filename = rel_path.split("/")[-1]
            if filename in ('.DS_Store', 'generate_mock_data.py') or rel_path.endswith('.zip') or rel_path.endswith('.pyc'):
                continue
            zip_file.writestr(rel_path, content)
    zip_buffer.seek(0)
    return zip_buffer.read()

def base64_encode_zip(zip_bytes: bytes) -> str:
    import base64
    return base64.b64encode(zip_bytes).decode('utf-8')

def cleanup_expired_report_folders(report_dir: str, delay_minutes: int):
    """
    Scans the report directory and deletes any timestamped report subfolders 
    whose modification time is older than the configured delay.
    """
    import os
    import time
    import shutil

    if not os.path.exists(report_dir):
        return

    now = time.time()
    cutoff_seconds = delay_minutes * 60

    try:
        for item in os.listdir(report_dir):
            item_path = os.path.join(report_dir, item)
            if os.path.isdir(item_path) and "_" in item:
                try:
                    folder_mtime = os.path.getmtime(item_path)
                    age_seconds = now - folder_mtime
                    if age_seconds > cutoff_seconds:
                        removed_files = []
                        for root_dir, _, file_list in os.walk(item_path):
                            for file_name in file_list:
                                removed_files.append(os.path.relpath(os.path.join(root_dir, file_name), item_path))
                        logger.info(f"cleanup_expired_report_folders: Deleting expired temp folder {item_path} (Age: {int(age_seconds/60)} mins). Removed files: {removed_files}")
                        shutil.rmtree(item_path, ignore_errors=True)
                except Exception as ex:
                    logger.debug(f"Failed to check mtime or delete folder {item_path}: {ex}")
    except Exception as e:
        logger.error(f"Error during expired folders cleanup scan: {e}")


@mcp.tool()
async def package_and_upload_custom_report(
    files: dict[str, str],
    name: str,
    description: str,
    category_id: str,
    level: str,
    report_dir: str = "",
    ctx: Context | None = None
) -> WorkflowInanceVO:
    """
    Write or update the report files in a target directory, convert them into a zip file,
    and call upload_new_custom_report to upload the zip as a custom report.

    Args:
        files (dict[str, str]): A dictionary mapping relative file paths to their contents.
        name (str): Name of the custom report.
        description (str): Description of the custom report.
        category_id (str): Category ID of the custom report categories.
        level (str): Visibility level of the report ('user' or 'system').
        report_dir (str, optional): Target local directory path to store files. Defaults to downloads folder with report name.
    """
    import os
    import datetime

    if not report_dir:
        report_dir = os.environ.get("COW_CUSTOM_REPORT_DIR", "/home/goose/cow-mcp/reporttempfiles")

    logger.debug("report_dir: {}".format(report_dir))

    if "_meta.json" not in files:
        logger.error("package_and_upload_custom_report: _meta.json not found in the files payload.")
        return WorkflowInanceVO(error="_meta.json not found in the files payload.")

    # Get expiration cutoff in minutes (defaulting to 30 mins)
    delay_minutes_str = os.environ.get("COW_REPORT_CLEANUP_DELAY_MINUTES", "30")
    try:
        delay_minutes = int(float(delay_minutes_str))
    except ValueError:
        delay_minutes = 30

    # Purge any expired folders before executing new tasks
    cleanup_expired_report_folders(report_dir, delay_minutes)

    # Create timestamped temporary folder to avoid user conflicts
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = os.path.join(report_dir, f"{name}_{timestamp}")

    try:
        logger.info("package_and_upload_custom_report: zipping files directly from in-memory dictionary")
        zip_data = create_report_zip_from_dict(files)

        logger.debug("zip_data: {}".format(zip_data))

        logger.info(f"package_and_upload_custom_report: creating/updating files on disk in temporary directory {temp_dir}")
        create_report_files(temp_dir, files)

        logger.info("package_and_upload_custom_report: base64 encoding zip archive")
        file_bytes_b64 = base64_encode_zip(zip_data)
        
        logger.debug("file_bytes_b64: {}".format(file_bytes_b64))
        
        logger.info(f"package_and_upload_custom_report: calling upload_new_custom_report for {name}")
        response = await upload_new_custom_report(
            name=name,
            description=description,
            file_bytes=file_bytes_b64,
            category_id=category_id,
            level=level,
            ctx=ctx
        )

        return response
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(f"package_and_upload_custom_report error: {e}")
        return WorkflowInanceVO(error=f"Packaging or upload failed: {str(e)}")

        
@mcp.tool()
async def send_custom_report_approval_workflow_url(ctx: Context | None = None) -> str:
    """
    This tool is used to identify if the current user has an admin role or not.
    If the user is an admin, it returns the custom report workflow approval URL.
    Otherwise, it returns an empty string.

    Returns:
        - return the approval url
    """
    import os
    try:
        logger.info("send_workflow_url")
        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_USERS_ME, "GET", ctx=ctx
        )
        logger.debug("users/me - output: %s", output)

        if not isinstance(output, dict) or "error" in output or "Message" in output:
            logger.error("send_workflow_url failed: %s", output)
            return ""

        is_admin = False
        roles = output.get("roles") or []
        if isinstance(roles, list):
            for r in roles:
                if isinstance(r, dict):
                    if "admin" in str(r.get("roleName", "")).lower() or "admin" in str(r.get("roleId", "")).lower():
                        is_admin = True
                else:
                    if "admin" in str(r).lower():
                        is_admin = True
        elif isinstance(roles, str):
            is_admin = "admin" in roles.lower()

        # Check direct RoleName keys
        role_name = output.get("RoleName") or output.get("roleName") or ""
        if "admin" in str(role_name).lower():
            is_admin = True

        if is_admin:
            base_host = constants.host.rstrip("/api") if hasattr(constants, "host") and isinstance(constants.host, str) else getattr(constants, "host", "")
            if not base_host:
                base_host = os.environ.get("CCOW_HOST", "").rstrip("/api")
            ui_url = f"{base_host}/ui/custom-reports-workflow" if base_host else "/ui/custom-reports-workflow"
            return ui_url

        return ""
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("send_workflow_url error: %s", e)
        return ""