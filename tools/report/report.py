
import traceback

from utils import utils
from utils.debug import logger
from mcptypes.graph_tool_types import CypherQueryVO
from mcptypes.report_tool_types import InsightsCategoryListVO, InsightsCategoryVO
from mcptypes.workflow_tools_type import WorkflowConfigVO, WorkflowInanceVO
from mcptypes.custom_report_tool_types import InsightDashboardVO, InsightDashboardListVO
from mcpconfig.config import mcp
from constants import constants
from fastmcp import Context
from mcptypes import forms_tool_types as vo
import os
import re
import datetime
import traceback
import io
import zipfile
import base64
import time
import shutil

ALLOWED_REPORT_FILE_PATTERNS = [
    r"^_meta\.json$",
    r"^cow_template\.jinja$",
    r"^template\.jinja$",
    r"^filter\.jinja$",
    r"^cowdashboard\.js$",
    r"^markdown\.md$",
    r"^data\/[a-zA-Z0-9_\-\. ]+\.csv$",  # Evidence CSV files inside data/
    r"^[a-zA-Z0-9_]+\.py$",               # Main report Python class
]

EXCLUDED_EXACT_FILENAMES = {
    "generate_mock_data.py",
    ".ds_store",
    "thumbs.db",
}

def is_whitelisted_report_file(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/").strip("/")
    base_name = os.path.basename(normalized).lower()
    
    # Exclude exact blacklisted filenames, hidden files, and scratch/test scripts
    if (
        base_name in EXCLUDED_EXACT_FILENAMES
        or base_name.startswith(".")
        or normalized.endswith(".pyc")
        or normalized.endswith(".zip")
        or normalized.endswith(".bak")
        or normalized.endswith(".tmp")
        or normalized.endswith("~")
        or base_name.startswith("test_")
        or base_name.startswith("temp_")
        or base_name.startswith("scratch_")
    ):
        return False
        
    return any(re.match(pattern, normalized, re.IGNORECASE) for pattern in ALLOWED_REPORT_FILE_PATTERNS)

def sanitize_report_template_payload(files: dict[str, str]) -> dict[str, str]:
    """
    Sanitizes report files before zipping or staging.
    Translates macro placeholders (__data_safe__, __js_script_safe__, __plan_id__, __id__)
    into standard Jinja2 curly braces and normalizes variable names.
    """
    sanitized = dict(files)
    macro_map = {
        "__data_safe__": "{{ data | safe }}",
        "__js_script_safe__": "{{ js_script | safe }}",
        "__plan_id__": "{{ plan_id }}",
        "__id__": "{{ id }}",
        "__data__": "{{ data }}",
        "__js_script__": "{{ js_script }}"
    }
    
    for filename in ["cow_template.jinja", "template.jinja", "filter.jinja"]:
        if filename in sanitized:
            content = sanitized[filename]
            for macro, jinja_expr in macro_map.items():
                if macro in content:
                    logger.info(f"sanitize_report_template_payload: Auto-translating macro '{macro}' to '{jinja_expr}' in {filename}")
                    content = content.replace(macro, jinja_expr)
            if "window.cbreDashboardData" in content and "window.cowDashboardData" not in content:
                logger.info(f"sanitize_report_template_payload: Normalizing window.cbreDashboardData to window.cowDashboardData in {filename}")
                content = content.replace("window.cbreDashboardData", "window.cowDashboardData")
            sanitized[filename] = content
            
    return sanitized


def filter_whitelisted_report_files(files: dict[str, str]) -> dict[str, str]:
    clean_files = {}
    for rel_path, content in files.items():
        if is_whitelisted_report_file(rel_path):
            clean_files[rel_path.replace("\\", "/").strip("/")] = content
        else:
            logger.info(f"filter_whitelisted_report_files: Skipping non-whitelisted/temporary file: {rel_path}")
    return clean_files

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
        
        output=await utils.make_API_call_to_CCow(req_body,constants.URL_WORKFLOW_INSTANCE, ctx=ctx)
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
    os.makedirs(report_dir, exist_ok=True)
    for rel_path, content in files.items():
        if not is_whitelisted_report_file(rel_path):
            continue
        file_path = os.path.join(report_dir, rel_path)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

def create_report_zip_from_dict(files: dict[str, str]) -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for rel_path, content in files.items():
            if not is_whitelisted_report_file(rel_path):
                continue
            zip_file.writestr(rel_path, content)
    zip_buffer.seek(0)
    return zip_buffer.read()

def base64_encode_zip(zip_bytes: bytes) -> str:
    return base64.b64encode(zip_bytes).decode('utf-8')

def cleanup_expired_report_folders(report_dir: str, delay_minutes: int):
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
        report_dir (str, optional): Target local directory path for upload staging. Defaults to COW_CUSTOM_REPORT_UPLOAD_DIR or COW_CUSTOM_REPORT_DIR.
    """
    # 1. Resolve Ephemeral Upload Staging Directory from ENV
    upload_base_dir = (
        report_dir
        or os.environ.get("COW_CUSTOM_REPORT_UPLOAD_DIR")
        or "/home/goose/cow-mcp/reporttempfiles"
    )
    
    # 2. Resolve Persistent Working Directory from ENV
    working_dir = (
        os.environ.get("COW_CUSTOM_REPORT_WORKING_DIR")
        or "/home/goose/cow-mcp/reporttempfiles/working"
    )

    logger.debug(f"package_and_upload_custom_report - upload_base_dir: {upload_base_dir}, working_dir: {working_dir}")

    # 3. Filter out temporary, scratch, and non-whitelisted files, and sanitize template macros
    clean_files = filter_whitelisted_report_files(files)
    clean_files = sanitize_report_template_payload(clean_files)

    if "_meta.json" not in clean_files:
        logger.error("package_and_upload_custom_report: _meta.json not found in the files payload.")
        return WorkflowInanceVO(error="_meta.json not found in the files payload.")

    # 4. Cleanup expired staging folders in upload directory
    delay_minutes_str = os.environ.get("COW_REPORT_CLEANUP_DELAY_MINUTES", "30")
    try:
        delay_minutes = int(float(delay_minutes_str))
    except ValueError:
        delay_minutes = 30
    cleanup_expired_report_folders(upload_base_dir, delay_minutes)

    # 5. Fetch user session info for isolated folder naming
    user_id = ""
    domain_id = ""
    role_id = ""
    try:
        user_info = await get_user_info(ctx=ctx)
        if isinstance(user_info, dict):
            user_id = user_info.get("id") or user_info.get("userId") or user_info.get("userID") or user_info.get("user_id") or ""
            domain_id = user_info.get("domainID") or user_info.get("domainId") or user_info.get("domain_id") or ""
            roles = user_info.get("roles") or []
            if isinstance(roles, list) and roles:
                first_role = roles[0]
                if isinstance(first_role, dict):
                    role_id = first_role.get("roleId") or first_role.get("roleID") or first_role.get("id") or ""
                elif isinstance(first_role, str):
                    role_id = first_role
            if not role_id:
                role_id = user_info.get("roleID") or user_info.get("roleId") or user_info.get("role_id") or ""
    except Exception as ex:
        logger.debug(f"Failed to fetch user session info for folder isolation: {ex}")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_components = [name]
    if user_id:
        folder_components.append(str(user_id))
    if domain_id:
        folder_components.append(str(domain_id))
    if role_id:
        folder_components.append(str(role_id))
    folder_components.append(timestamp)

    isolated_folder_name = "_".join(folder_components)
    temp_upload_dir = os.path.join(upload_base_dir, isolated_folder_name)

    try:
        # 6. Optional: Sync clean files to persistent working directory
        if os.path.exists(working_dir) or os.environ.get("COW_CUSTOM_REPORT_WORKING_DIR"):
            user_working_dir = os.path.join(working_dir, name)
            create_report_files(user_working_dir, clean_files)

        # 7. Zip ONLY whitelisted files directly from memory
        logger.info("package_and_upload_custom_report: zipping whitelisted files directly from in-memory dictionary")
        zip_data = create_report_zip_from_dict(clean_files)

        # 8. Write ONLY whitelisted files to isolated ephemeral upload directory
        logger.info(f"package_and_upload_custom_report: staging whitelisted files on disk in ephemeral directory {temp_upload_dir}")
        create_report_files(temp_upload_dir, clean_files)

        # 9. Base64 encode and upload
        file_bytes_b64 = base64_encode_zip(zip_data)
        
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
async def get_user_info(ctx: Context):
    """
        It is used to fetch the information of the current user information

    Returns:
        user information 
    """
    logger.info("fetch get_user_info : \n")
    output = await utils.make_API_call_to_CCow_and_get_response(
                constants.URL_USERS_ME, "GET", ctx=ctx
            )
    logger.info(f"fetch get_user_info - output : {output}")
    return output
        
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
        output = await get_user_info(ctx=ctx)
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
            ui_url = f"{base_host}"+constants.REPORT_WORKFLOW_APPROVAL_URL if base_host else constants.REPORT_WORKFLOW_APPROVAL_URL
            return ui_url

        return ""
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("send_workflow_url error: %s", e)
        return ""

@mcp.tool()
async def fetch_existing_custom_report(ctx: Context | None = None) -> InsightDashboardListVO:
    """
    Fetch all existing custom reports registered in the ComplianceCow platform.
    Args:
        ctx (Context, optional): FastMCP request context.
    Returns:
        InsightDashboardListVO: List of registered dashboard objects containing id, name, category_id, and status.
    """
    try:
        logger.info("fetch existing custom reports : \n")
        output=await utils.make_GET_API_call_to_CCow(constants.URL_INSIGHTS_DASHBOARD, ctx)
        logger.debug("existing custom report -  output: {}\n".format(output))
        
        if isinstance(output, str) or  "error" in output:
            logger.error("existing custom reports -  error: {}\n".format(output))
            return InsightDashboardListVO(error="Facing internal error")
        
        insights: list[InsightDashboardVO]=[]
        for item in output["items"]:
            if "name" in item and "id" in item:
                insights.append(InsightDashboardVO(id=item["id"],name=item["name"],category_id=item["categoryID"],status=item["status"]))
                
        logger.debug("insights: {}\n".format(insights))
        return InsightDashboardListVO(insights=insights)
    
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("existing custom reports -  error: {}\n".format(e))
        return InsightDashboardListVO(error="Facing internal error")    