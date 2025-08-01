from __future__ import annotations
import asyncio
import base64
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, get_type_hints

from mcpconfig.config import mcp
from constants import constants
from utils import rule, wsutils
from mcptypes.rule_type import TaskVO


# Phase 1: Lightweight task summary resource


@mcp.resource("tasks://summary")
def get_tasks_summary() -> str:
    """
    Resource containing minimal task information for initial selection.

    This resource provides only the essential information needed for task selection:
    - Task name and display name
    - Brief description
    - Purpose and capabilities
    - Tags for categorization
    - Basic README summary

    Use this for initial task discovery and selection. Detailed information can be
    retrieved later using `tasks://details/{task_name}` for selected tasks only.
    """

    try:
        available_tasks = []
        tasks_resp = rule.fetch_task_api(params={
            "tags": "primitive"})

        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            available_tasks = [TaskVO.from_dict(
                task) for task in tasks_resp["items"]]

        if not available_tasks:
            return json.dumps({"error": "No tasks loaded", "tasks": []})

        tasks_summary = []
        for task in available_tasks:
            # Decode readme for capabilities only
            readme_content = rule.decode_content(task.readmeData)
            capabilities = rule.extract_capabilities_from_readme(
                readme_content)

            # Minimal info for selection
            task_summary = {"name": task.name, "displayName": task.displayName, "description": task.description, "purpose": rule.extract_purpose_from_description(task.description), "tags": task.tags, "capabilities": capabilities, "input_count": len(
                task.inputs), "output_count": len(task.outputs), "has_templates": any(inp.templateFile for inp in task.inputs), "app_type": task.appTags.get("appType", ["generic"])[0] if task.appTags.get("appType") else "generic"}
            tasks_summary.append(task_summary)

        return json.dumps({"total_tasks": len(tasks_summary), "tasks": tasks_summary, "message": f"Found {len(tasks_summary)} available tasks - use tasks://details/{{task_name}} for full details", "categories": rule.categorize_tasks_by_tags(tasks_summary)}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"An error occurred while fetching the task summary: {e}", "tasks": []})


# Phase 2: Detailed task information resource
@mcp.resource("tasks://details/{task_name}")
def get_task_details(task_name: str) -> str:
    """
    Resource for retrieving complete task details after selection.

    This resource provides detailed information for a specific task, including:
    - Complete input/output specifications with template information
    - Full README documentation
    - All metadata and configuration options
    - Decoded template content for inputs that have associated templates

    Args:
        task_name: The name of the selected task for which to retrieve full details

    Returns:
        A JSON string containing the complete task information
    """

    try:
        task = None
        tasks_resp = rule.fetch_task_api(params={
            "name": task_name})

        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            task = TaskVO.from_dict(tasks_resp["items"][0])

        if not task:
            return json.dumps({"error": f"Task '{task_name}' not found in available tasks", "task": {}})

        # Full detailed information
        readme_content = rule.decode_content(task.readmeData)

        # Process inputs with template information
        detailed_inputs = []
        for inp in task.inputs:
            input_detail = {"name": inp.name, "description": inp.description, "dataType": inp.dataType, "defaultValue": inp.defaultValue, "required": inp.required,
                            "allowedValues": inp.allowedValues or [], "format": inp.format, "showField": inp.showField, "allowUserValues": inp.allowUserValues, "has_template": bool(inp.templateFile)}

            # Include decoded template if it exists
            if inp.templateFile:
                decoded_template = rule.decode_content(inp.templateFile)
                input_detail.update({"template_decoded": decoded_template, "template_format": inp.format,
                                    "template_guidance": f"Use get_template_guidance('{task.name}', '{inp.name}') for detailed guidance"})

            detailed_inputs.append(input_detail)

        task_details = {
            "name": task.name,
            "displayName": task.displayName,
            "version": task.version,
            "description": task.description,
            "type": task.type,
            "tags": task.tags,
            "applicationType": task.applicationType,
            "appTags": task.appTags,
            "full_readme": readme_content,
            "capabilities": rule.extract_capabilities_from_readme(readme_content),
            "use_cases": rule.extract_use_cases_from_readme(readme_content),
            "inputs": detailed_inputs,
            "outputs": [{"name": out.name, "description": out.description, "dataType": out.dataType} for out in task.outputs],
            "template_summary": {"total_templates": len([inp for inp in task.inputs if inp.templateFile]), "template_inputs": [inp.name for inp in task.inputs if inp.templateFile], "instructions": "Use get_template_guidance(task_name, input_name) for each template input"},
            "integration_info": {"app_type": task.appTags.get("appType", ["generic"])[0] if task.appTags.get("appType") else "generic", "environment": task.appTags.get("environment", ["logical"]), "exec_level": task.appTags.get("execlevel", ["app"])},
        }

        return json.dumps(task_details, indent=2)
    except Exception as e:
        return json.dumps({"error": f"An error occurred while fetching the task {task_name} details: {e}", "task": {}})


# Alternative tool version for task details
@mcp.tool()
def get_task_details(task_name: str) -> Dict[str, Any]:
    """
    Tool-based version of get_task_details for improved compatibility.

    DETAILED TASK ANALYSIS REQUIREMENTS:
    - Use this tool if the tasks://details/{task_name} resource is not accessible
    - Extract complete input/output specifications with template information
    - Review detailed capabilities and requirements from the full README
    - Identify template-based inputs (those with the templateFile property)
    - Analyze appTags to determine the application type
    - Review all metadata and configuration options
    - Use this information for accurate task matching and rule structure creation

    Args:
        task_name: The name of the task for which to retrieve details

    Returns:
        A dictionary containing the complete task information
    """

    try:
        task = None
        tasks_resp = rule.fetch_task_api(params={
            "name": task_name})

        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            task = TaskVO.from_dict(tasks_resp["items"][0])
        if not task:
            return {"error": f"Task '{task_name}' not found"}
        # Return same detailed information as resource
        readme_content = rule.decode_content(task.readmeData)
        return {"name": task.name, "description": task.description, "tags": task.tags, "appTags": task.appTags, "readme_content": readme_content, "inputs": [{"name": inp.name, "description": inp.description, "dataType": inp.dataType, "required": inp.required, "has_template": bool(inp.templateFile), "format": inp.format if inp.templateFile else None} for inp in task.inputs], "outputs": [{"name": out.name, "description": out.description, "dataType": out.dataType} for out in task.outputs], "template_count": len([inp for inp in task.inputs if inp.templateFile]), "message": f"Use get_template_guidance('{task.name}', '<input_name>') for template details"}
    except Exception as e:
        return {"error": f"An error occurred while fetching the task {task_name} details: {e}"}


# Category-filtered task summaries
@mcp.resource("tasks://by-category/{category}")
def get_tasks_by_category(category: str) -> str:
    """
    Resource for retrieving task summaries filtered by category or tag.

    Args:
        category: The task category or tag to filter by

    Returns:
        A JSON string containing minimal task information for tasks matching the category or tag
    """

    try:
        tasks = []
        tasks_resp = rule.fetch_task_api(params={
            "tags": category})

        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            tasks = [TaskVO.from_dict(task) for task in tasks_resp["items"]]
        if not tasks:
            return json.dumps({"error": f"No tasks found for the provided category or tag: {category}", "tasks": []})

        filtered_tasks = []
        for task in filtered_tasks:
            readme_content = rule.decode_content(task.readmeData)
            capabilities = rule.extract_capabilities_from_readme(
                readme_content)

            task_summary = {"name": task.name, "description": task.description, "purpose": rule.extract_purpose_from_description(
                task.description), "tags": task.tags, "capabilities": capabilities, "input_count": len(task.inputs), "output_count": len(task.outputs), "has_templates": any(inp.templateFile for inp in task.inputs)}
            filtered_tasks.append(task_summary)

        return json.dumps({"category": category, "tasks": filtered_tasks, "count": len(filtered_tasks), "message": f"Use tasks://details/'{{task_name}} for complete information"}, indent=2)

    except Exception as e:
        return json.dumps({"error": f"An error occurred while fetching the tasks by category or tag: {category}: {e}"})


# Template processing tools
@mcp.tool()
def get_template_guidance(task_name: str, input_name: str) -> Dict[str, Any]:
    """Get detailed guidance for filling out a template-based input.

    COMPLETE TEMPLATE HANDLING PROCESS:

    STEP 1 - TEMPLATE IDENTIFICATION:
    - Called for inputs that have a templateFile property
    - Provides decoded template content and structure explanation
    - Returns required fields, format-specific tips, and validation rules

    STEP 2 - TEMPLATE PRESENTATION TO USER:
    Show the template with this EXACT format:
    "Now configuring: [X of Y inputs]

    Task: {task_name}
    Input: {input_name} - {description}

    Here's the template structure:

    [Show decoded_template]

    This {format} file requires:
    - Field 1: [description]
    - Field 2: [description]

    Please provide your actual configuration following this template."

    STEP 3 - COLLECT USER CONTENT:
    - Wait for the user to provide their actual content
    - Do NOT proceed until the user provides content
    - NEVER use template content as default values

    STEP 4 - PROCESS TEMPLATE INPUT:
    - Call collect_template_input(task_name, input_name, user_content)
    - Validates content format, checks required fields, uploads file
    - Returns file URL for use in rule structure

    TEMPLATE FORMAT HANDLING:
    - JSON: Must be valid JSON with proper brackets and quotes
    - TOML: Must follow TOML syntax with proper sections [section_name]
    - YAML: Must have correct indentation and structure
    - XML: Must be well-formed XML with proper tags

    VALIDATION RULES:
    - Format-specific syntax validation
    - Required field presence checking
    - Data type validation where applicable
    - Template structure compliance

    CRITICAL TEMPLATE RULES:
    - ALWAYS call get_template_guidance() for inputs with templates
    - ALWAYS show the decoded template to the user with exact presentation format
    - ALWAYS wait for the user to provide actual content
    - ALWAYS call collect_template_input() to process user content
    - NEVER use template content directly - always use the user's actual content
    - ALWAYS use returned file URLs in rule structure

    PROGRESS TRACKING:
    - Show "Now configuring: [X of Y inputs]" for user progress
    - Include clear task and input identification
    - Provide format-specific guidance and tips

    Args:
        task_name: Name of the task
        input_name: Name of the input that has a template

    Returns:
        Dict containing template content and guidance
    """

    try:
        task = None
        tasks_resp = rule.fetch_task_api(params={
            "name": task_name})

        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            task = TaskVO.from_dict(tasks_resp["items"][0])

        if not task:
            return {"success": False, "error": f"Task '{task_name}' not found in available tasks"}

        # Find the specific input
        task_input = None
        for inp in task.inputs:
            if inp.name == input_name:
                task_input = inp
                break

        if not task_input:
            return {"success": False, "error": f"Input {input_name} not found in task {task_name}"}

        if not task_input.templateFile:
            return {"success": False, "error": f"Input {input_name} does not have a template file"}

        # Decode template and provide guidance
        decoded_template = rule.decode_content(task_input.templateFile)
        guidance = rule.generate_detailed_template_guidance(
            decoded_template, task_input)

        return {"success": True, "task_name": task_name, "input_name": input_name, "input_description": task_input.description, "format": task_input.format, "decoded_template": decoded_template, "guidance": guidance, "example_content": rule.generate_example_content(decoded_template, task_input.format), "validation_rules": rule.get_template_validation_rules(task_input.format), "presentation_format": f"Now configuring: [X of Y inputs]\n\nTask: {task_name}\nInput: {input_name} - {task_input.description}\n\nHere's the template structure:\n\n{decoded_template}\n\nThis {task_input.format} file requires specific fields. Please provide your actual configuration following this template."}

    except Exception as e:
        return {"success": False, "error": f"Failed to get template guidance: {e}"}


@mcp.tool()
def collect_template_input(task_name: str, input_name: str, user_content: str) -> Dict[str, Any]:
    """Collect user input for template-based task inputs.

    TEMPLATE INPUT PROCESSING:
    - Validates user content against template format (JSON/TOML/YAML)
    - Handles JSON arrays and objects properly
    - Checks for required fields from template structure
    - Uploads validated content as file (ONLY for FILE dataType inputs)
    - Returns file URL for use in rule structure
    - MANDATORY: Gets final confirmation for EVERY input before proceeding
    - CRITICAL: Only processes user-provided content, never use default templates

    JSON ARRAY HANDLING:
    - Properly validates JSON arrays: [{"key": "value"}, {"key": "value"}]
    - Validates JSON objects: {"key": "value", "nested": {"key": "value"}}
    - Handles complex nested structures with arrays and objects
    - Validates each array element and object property

    VALIDATION REQUIREMENTS:
    - JSON: Must be valid JSON (arrays/objects) with proper brackets and quotes
    - TOML: Must follow TOML syntax with proper sections [section_name]
    - YAML: Must have correct indentation and structure
    - XML: Must be well-formed XML with proper tags
    - Required fields: All template fields must be present in user content

    FINAL CONFIRMATION WORKFLOW (MANDATORY):
    1. After user provides template content
    2. Validate content format and structure
    3. Show preview of content to user
    4. Ask: "You provided this [format] content: [preview]. Is this correct? (yes/no)"
    5. If 'yes': Upload file (if FILE type) or store in memory
    6. If 'no': Allow user to re-enter content
    7. NEVER proceed without final confirmation

    FILE NAMING CONVENTION:
    - Format: {task_name}_{input_name}.{extension}
    - Extensions: .json, .toml, .yaml, .xml, .txt based on format

    WORKFLOW INTEGRATION:
    1. Called after get_template_guidance() shows template to user
    2. User provides their actual configuration content
    3. This tool validates content (including JSON arrays)
    4. Shows content preview and asks for confirmation
    5. Only after confirmation: uploads file or stores in memory
    6. Returns file URL or memory reference for rule structure

    CRITICAL RULES:
    - ONLY upload files for inputs with dataType = "FILE" or "HTTP_CONFIG"
    - Template inputs and HTTP_CONFIG inputs are typically file types and need file uploads
    - Store non-FILE template content in memory
    - ALWAYS get final confirmation before proceeding
    - Handle JSON arrays properly: validate each element
    - Never use template defaults - always use user-provided content

    Args:
        task_name: Name of the task this input belongs to
        input_name: Name of the input parameter
        user_content: Content provided by the user based on the template

    Returns:
        Dict containing validation results and file URL or memory reference
    """
    try:
        task = None
        tasks_resp = rule.fetch_task_api(params={
            "name": task_name})

        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            task = TaskVO.from_dict(tasks_resp["items"][0])
        if not task:
            return {"success": False, "error": f"Task '{task_name}' not found in available tasks"}

        # Find the specific input
        task_input = None
        for inp in task.inputs:
            if inp.name == input_name:
                task_input = inp
                break

        if not task_input:
            return {"success": False, "error": f"Input {input_name} not found in task {task_name}"}

        # Validate the content including JSON arrays
        validation_result = rule.validate_template_content_enhanced(
            task_input, user_content)
        if not validation_result["valid"]:
            return {"success": False, "error": "Content validation failed", "validation_errors": validation_result["errors"], "suggestions": validation_result["suggestions"]}

        # Generate content preview for confirmation
        content_preview = rule.generate_content_preview(
            user_content, task_input.format)

        # Need final confirmation before storing/uploading
        return {"success": True, "task_name": task_name, "input_name": input_name, "validated_content": user_content, "content_preview": content_preview, "needs_final_confirmation": True, "data_type": task_input.dataType, "format": task_input.format, "is_file_type": task_input.dataType.upper() in ["FILE", "HTTP_CONFIG"], "final_confirmation_message": f"You provided this {task_input.format.upper()} content:\n\n{content_preview}\n\nIs this correct? (yes/no)", "message": "Template content validated - needs final confirmation before processing"}

    except Exception as e:
        return {"success": False, "error": f"Failed to process template input: {e}"}


@mcp.tool()
def confirm_template_input(rule_name: str, task_name: str, input_name: str, confirmed_content: str) -> Dict[str, Any]:
    """Confirm and process template input after user validation.

    CONFIRMATION PROCESSING:
    - Handles final confirmation of template content
    - Uploads files for FILE dataType inputs
    - Stores content in memory for non-FILE inputs
    - MANDATORY step before proceeding to next input

    PROCESSING RULES:
    - FILE dataType: Upload content as file, return file URL
    - HTTP_CONFIG dataType: Upload content as file, return file URL
    - Non-FILE dataType: Store content in memory
    - Include metadata about confirmation and timestamp

    Args:
        rule_name: Descriptive name for the rule based on the user's use case. 
                   Note: Use the same rule name for all inputs that belong to this rule.
                   Example: rule_name = "MeaningfulRuleName"
        task_name: Name of the task this input belongs to
        input_name: Name of the input parameter
        confirmed_content: The content user confirmed

    Returns:
        Dict containing processing results (file URL or memory reference)
    """
    try:
        task = None
        tasks_resp = rule.fetch_task_api(params={
            "name": task_name})

        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            task = TaskVO.from_dict(tasks_resp["items"][0])
        if not task:
            return {"success": False, "error": f"Task '{task_name}' not found in available tasks"}

        # Find the specific input
        task_input = None
        for inp in task.inputs:
            if inp.name == input_name:
                task_input = inp
                break

        if not task_input:
            return {"success": False, "error": f"Input {input_name} not found in task {task_name}"}

        # Check if this is a FILE or HTTP_CONFIG type input that needs upload
        if task_input.dataType.upper() in ["FILE", "HTTP_CONFIG"]:
            # Generate appropriate filename
            file_extension = rule.get_file_extension(
                task_input.format)
            file_name = f"{task_name}_{input_name}{file_extension}"

            # Upload the file and get URL
            upload_result = upload_file(
                rule_name=rule_name, file_name=file_name, content=confirmed_content)

            if upload_result["success"]:
                return {"success": True, "task_name": task_name, "input_name": input_name, "file_url": upload_result["file_url"], "filename": file_name, "content_size": len(confirmed_content), "storage_type": "FILE", "data_type": task_input.dataType, "format": task_input.format, "timestamp": datetime.now().isoformat(), "message": f"Template file uploaded successfully for {input_name} in {task_name}"}
            else:
                return {"success": False, "error": f"File upload failed: {upload_result.get('error', 'Unknown error')}"}
        else:
            # For non-FILE inputs, store content in memory (don't upload)
            return {"success": True, "task_name": task_name, "input_name": input_name, "stored_content": confirmed_content, "content_size": len(confirmed_content), "storage_type": "MEMORY", "data_type": task_input.dataType, "format": task_input.format, "timestamp": datetime.now().isoformat(), "message": f"Template content stored in memory for {input_name} in {task_name}"}

    except Exception as e:
        return {"success": False, "error": f"Failed to confirm template input: {str(e)}"}


@mcp.tool()
def upload_file(rule_name: str, file_name: str, content: str, content_encoding: str = "utf-8") -> Dict[str, Any]:
    """Upload file content and return file URL for use in rules.

    FILE UPLOAD PROCESS:
    - Generate unique file ID and URL for storage system integration
    - Support multiple content encodings (utf-8, base64, etc.)
    - Return file URL that can be used in rule structure inputs
    - Integrate with actual file storage system (AWS S3, Minio, internal storage)
    - Validate content size and encoding before upload
    - Provide detailed upload results with file metadata

    Args:
        rule_name: Descriptive name for the rule based on the user's use case. 
                   Note: Use the same rule name for all inputs that belong to this rule.
                   Example: rule_name = "MeaningfulRuleName"
        file_name: Name of the file to upload
        content: File content (text or base64 encoded).
        content_encoding: Encoding of the content (utf-8, base64, etc.)

    Returns:
        Dict containing file upload results and URL
    """
    try:
        if content_encoding in ["utf-8", "base64"]:
            # Convert UTF-8 string to base64 if needed
            if content_encoding == "utf-8":
                encoded_content = base64.b64encode(
                    content.encode("utf-8")).decode("utf-8")
            else:
                encoded_content = content
        else:
            return {"success": False, "error": f"Unsupported encoding: {content_encoding}", "filename": file_name}

        # Generate file ID and URL
        file_id = f"file_{abs(hash(encoded_content)) % 100000}"
        unique_file_name = f"{file_id}_{file_name}"

        headers = wsutils.create_header()
        payload = {
            "fileName": unique_file_name,
            "fileContent": encoded_content,
            "ruleName": rule_name
        }
        file_upload_resp = wsutils.post(path=wsutils.build_api_url(
            endpoint=constants.URL_UPLOAD_FILE), data=json.dumps(payload), header=headers)

        if rule.is_valid_key(file_upload_resp, "fileURL"):
            return {"success": True, "file_url": file_upload_resp["fileURL"], "filename": file_name, "file_id": file_id, "content_size": len(content), "content_encoding": content_encoding, "message": f"File '{file_name}' uploaded successfully"}

        return {"success": False, "error": "Unable to find the uploaded file URL", "filename": file_name}

    except Exception as e:
        return {"success": False, "error": f"Failed to upload file: {e}", "filename": file_name}


@mcp.tool()
def collect_parameter_input(task_name: str, input_name: str, user_value: str = None, use_default: bool = False) -> Dict[str, Any]:
    """Collect user input for non-template parameter inputs.

    PARAMETER INPUT PROCESSING:
    - Collects primitive data type values (STRING, INT, FLOAT, BOOLEAN, DATE, DATETIME)
    - Stores values in memory (NEVER uploads files for primitive types)
    - Handles optional vs required inputs based on 'required' attribute
    - Supports default value confirmation workflow
    - Validates data types and formats
    - MANDATORY: Gets final confirmation for EVERY input before proceeding

    INPUT REQUIREMENT RULES:
    - MANDATORY: Only if input.required = true
    - OPTIONAL: If input.required = false, user can skip or provide value
    - DEFAULT VALUES: If user requests defaults, must get confirmation
    - FINAL CONFIRMATION: Always required before proceeding to next input

    DEFAULT VALUE WORKFLOW:
    1. User requests to use default values
    2. Show default value to user for confirmation
    3. "I can fill this with the default value: '[default_value]'. Confirm?"
    4. Only proceed after explicit user confirmation
    5. Store confirmed default value in memory

    FINAL CONFIRMATION WORKFLOW (MANDATORY):
    1. After user provides value (or confirms default)
    2. Show final confirmation: "You entered: '[value]'. Is this correct? (yes/no)"
    3. If 'yes': Store value and proceed to next input
    4. If 'no': Allow user to re-enter value
    5. NEVER proceed without final confirmation

    DATA TYPE VALIDATION:
    - STRING: Any text value
    - INT: Integer numbers only
    - FLOAT: Decimal numbers
    - BOOLEAN: true/false, yes/no, 1/0
    - DATE: YYYY-MM-DD format
    - DATETIME: ISO 8601 format

    COLLECTION PRESENTATION:
    "Now configuring: [X of Y inputs]

    Task: {task_name}
    Input: {input_name} ({data_type})
    Description: {description}
    Required: {Yes/No}
    Default: {default_value or 'None'}

    Please provide a value, type 'default' to use default, or 'skip' if optional:"

    CRITICAL RULES:
    - NEVER upload files for primitive data types
    - Store all primitive values in memory only
    - Always confirm default values with user
    - ALWAYS get final confirmation before proceeding to next input
    - Respect required vs optional based on input.required attribute
    - Validate data types before storing

    Args:
        task_name: Name of the task this input belongs to
        input_name: Name of the input parameter
        user_value: Value provided by user (optional)
        use_default: Whether to use default value (requires confirmation)

    Returns:
        Dict containing parameter value and storage info
    """
    try:
        task = None
        tasks_resp = rule.fetch_task_api(params={
            "name": task_name})

        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            task = TaskVO.from_dict(tasks_resp["items"][0])
        if not task:
            return {"success": False, "error": f"Task '{task_name}' not found in available tasks"}

        # Find the specific input
        task_input = None
        for inp in task.inputs:
            if inp.name == input_name:
                task_input = inp
                break

        if not task_input:
            return {"success": False, "error": f"Input {input_name} not found in task {task_name}"}

        # Check if this input is required
        is_required = task_input.required
        has_default = bool(task_input.defaultValue)

        # Handle different input scenarios
        if use_default and has_default:
            # User wants to use default - need confirmation
            return {"success": True, "task_name": task_name, "input_name": input_name, "needs_default_confirmation": True, "default_value": task_input.defaultValue, "data_type": task_input.dataType, "required": is_required, "confirmation_message": f"I can fill this with the default value: '{task_input.defaultValue}'. Confirm? (yes/no)", "message": "Default value needs user confirmation before proceeding"}

        elif user_value is not None:
            # User provided a value - validate it
            validation_result = rule.validate_parameter_value(
                user_value, task_input.dataType)
            if not validation_result["valid"]:
                return {"success": False, "error": "Invalid value format", "validation_errors": validation_result["errors"], "expected_type": task_input.dataType, "message": "Please provide a valid value"}

            # Value is valid - need FINAL confirmation before storing
            return {"success": True, "task_name": task_name, "input_name": input_name, "validated_value": validation_result["converted_value"], "needs_final_confirmation": True, "data_type": task_input.dataType, "required": is_required, "final_confirmation_message": f"You entered: '{validation_result['converted_value']}'. Is this correct? (yes/no)", "message": "Value validated - needs final confirmation before storing"}

        else:
            # Need to collect input from user
            presentation = rule.generate_parameter_presentation(
                task_input, task_name)
            return {"success": True, "task_name": task_name, "input_name": input_name, "needs_user_input": True, "presentation": presentation, "data_type": task_input.dataType, "required": is_required, "has_default": has_default, "default_value": task_input.defaultValue if has_default else None, "message": "Ready to collect parameter input from user"}

    except Exception as e:
        return {"success": False, "error": f"Failed to process parameter input: {e}"}


@mcp.tool()
def confirm_parameter_input(task_name: str, input_name: str, confirmed_value: str, confirmation_type: str = "final") -> Dict[str, Any]:
    """Confirm and store parameter input after user validation.

    CONFIRMATION PROCESSING:
    - Handles final confirmation of parameter values
    - Stores confirmed values in memory
    - Supports both default value confirmation and final value confirmation
    - MANDATORY step before proceeding to next input

    CONFIRMATION TYPES:
    - "default": User confirmed they want to use default value
    - "final": User confirmed their entered value is correct
    - Both types require explicit user confirmation

    STORAGE RULES:
    - Store all confirmed values in memory (never upload files)
    - Only store after explicit user confirmation
    - Include metadata about confirmation type and timestamp

    Args:
        task_name: Name of the task this input belongs to
        input_name: Name of the input parameter
        confirmed_value: The value user confirmed
        confirmation_type: Type of confirmation ("default" or "final")

    Returns:
        Dict containing stored value confirmation
    """
    try:
        task = None
        tasks_resp = rule.fetch_task_api(params={
            "name": task_name})

        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            task = TaskVO.from_dict(tasks_resp["items"][0])
        if not task:
            return {"success": False, "error": f"Task '{task_name}' not found in available tasks"}

        # Find the specific input
        task_input = None
        for inp in task.inputs:
            if inp.name == input_name:
                task_input = inp
                break

        if not task_input:
            return {"success": False, "error": f"Input {input_name} not found in task {task_name}"}

        # Validate the confirmed value
        validation_result = rule.validate_parameter_value(
            confirmed_value, task_input.dataType)
        if not validation_result["valid"]:
            return {"success": False, "error": "Confirmed value is invalid", "validation_errors": validation_result["errors"]}

        # Store the confirmed value in memory
        return {"success": True, "task_name": task_name, "input_name": input_name, "stored_value": validation_result["converted_value"], "data_type": task_input.dataType, "required": task_input.required, "storage_type": "MEMORY", "confirmation_type": confirmation_type, "timestamp": datetime.now().isoformat(), "message": f"Parameter value confirmed and stored in memory for {input_name}"}

    except Exception as e:
        return {"success": False, "error": f"Failed to confirm parameter input: {e}"}


# INPUT VERIFICATION TOOLS - MANDATORY WORKFLOW STEPS
@mcp.tool()
def prepare_input_collection_overview(selected_tasks: List[str]) -> Dict[str, Any]:
    """Prepare and present input collection overview before starting any input collection.

    MANDATORY FIRST STEP - INPUT OVERVIEW PROCESS:

    This tool MUST be called before collecting any inputs. It analyzes all selected tasks
    and presents a complete overview of what inputs will be needed.

    HANDLES DUPLICATE INPUT NAMES:
    - Creates unique identifiers for each task-input combination
    - Format: "{task_name}.{input_name}" for uniqueness
    - Prevents conflicts when multiple tasks have same input names
    - Maintains clear mapping between tasks and their specific inputs

    OVERVIEW REQUIREMENTS:
    1. Analyze ALL selected tasks for input requirements
    2. Categorize inputs: templates vs parameters
    3. Create unique identifiers for each task-input combination
    4. Count total inputs needed
    5. Present clear overview to user
    6. Get user confirmation before proceeding
    7. Return structured overview for systematic collection

    OVERVIEW PRESENTATION FORMAT:
    "INPUT COLLECTION OVERVIEW:

    I've analyzed your selected tasks. Here's what we need to configure:

    TEMPLATE INPUTS (Files):
    • Task: [TaskName] → Input: [InputName] ([Format] file)
        Unique ID: [TaskName.InputName]
        Description: [InputDescription]

    PARAMETER INPUTS (Values):
    • Task: [TaskName] → Input: [InputName] ([DataType])
        Unique ID: [TaskName.InputName]
        Description: [InputDescription]
        Required: [Yes/No]

    SUMMARY:
    - Total inputs needed: X
    - Template files: Y ([formats])
    - Parameter values: Z
    - Estimated time: ~[X] minutes

    This will be collected step-by-step with progress indicators.
    Ready to start systematic input collection?"

    CRITICAL WORKFLOW RULES:
    - ALWAYS call this tool first before any input collection
    - NEVER start collecting inputs without user seeing overview
    - NEVER proceed without user confirmation
    - Create unique task.input identifiers to avoid conflicts
    - Show clear task-input relationships to user

    Args:
        selected_tasks: List of task names that will be used in the rule

    Returns:
        Dict containing structured input overview and collection plan with unique identifiers
    """

    if not selected_tasks:
        return {"success": False, "error": "No tasks selected for input analysis"}

    try:
        input_analysis = {"template_inputs": [], "parameter_inputs": [], "total_count": 0, "template_count": 0,
                          "parameter_count": 0, "estimated_minutes": 0, "unique_input_map": {}}  # Maps unique_id to task and input info

        available_tasks = []
        tasks_resp = rule.fetch_task_api(params={
            "tags": "primitive"})

        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            available_tasks = [TaskVO.from_dict(
                task) for task in tasks_resp["items"]]

        if not available_tasks:
            return json.dumps({"success": False, "error": "No tasks loaded"})

        # Analyze each selected task
        for task_name in selected_tasks:
            task = None
            for available_task in available_tasks:
                if available_task.name == task_name:
                    task = available_task
                    break

            if not task:
                continue

            # Process each input with unique identifier
            for inp in task.inputs:
                # Create unique identifier: TaskName.InputName
                unique_input_id = f"{task_name}.{inp.name}"

                input_info = {"task_name": task_name, "input_name": inp.name, "unique_input_id": unique_input_id, "description": inp.description, "data_type": inp.dataType, "required": inp.required, "has_template": bool(
                    inp.templateFile), "format": inp.format if inp.templateFile else None, "has_default": bool(inp.defaultValue), "default_value": inp.defaultValue if inp.defaultValue else None}

                # Store in unique input map for easy lookup
                input_analysis["unique_input_map"][unique_input_id] = {
                    "task_name": task_name, "input_name": inp.name, "task_input_obj": inp}

                if inp.templateFile or inp.dataType.upper() in ["FILE", "HTTP_CONFIG"]:
                    input_analysis["template_inputs"].append(
                        input_info)
                    input_analysis["template_count"] += 1
                    # File inputs take longer (2-3 minutes each)
                    input_analysis["estimated_minutes"] += 3
                else:
                    input_analysis["parameter_inputs"].append(
                        input_info)
                    input_analysis["parameter_count"] += 1
                    # Parameter inputs are quicker (30 seconds each)
                    input_analysis["estimated_minutes"] += 0.5

        input_analysis["total_count"] = input_analysis["template_count"] + \
            input_analysis["parameter_count"]

        # Generate overview presentation
        overview_text = rule.generate_input_overview_presentation_with_unique_ids(
            input_analysis)

        return {"success": True, "input_analysis": input_analysis, "overview_presentation": overview_text, "unique_input_map": input_analysis["unique_input_map"], "collection_plan": {"step1": "Template inputs (files) - collected first with unique IDs", "step2": "Parameter inputs (values) - collected second with unique IDs", "step3": "Final verification of all collected inputs", "step4": "Rule structure creation with proper task-input mapping"}, "message": "Input overview prepared with unique identifiers. Present to user and get confirmation before proceeding.", "next_action": "Show overview_presentation to user and wait for confirmation"}

    except Exception as e:
        return {"success": False, "error": f"Failed to prepare input overview: {e}"}


@mcp.tool()
def verify_collected_inputs(collected_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Verify all collected inputs with user before rule creation.

    MANDATORY VERIFICATION STEP:

    This tool MUST be called after all inputs are collected but before create_rule().
    It presents a comprehensive summary of all collected inputs for user verification.

    HANDLES DUPLICATE INPUT NAMES:
    - Uses unique identifiers (TaskName.InputName) for each input
    - Properly maps each unique input to its specific task
    - Creates structured inputs for rule creation with unique names
    - Maintains clear separation between inputs from different tasks

    VERIFICATION REQUIREMENTS:
    1. Show complete summary of ALL collected inputs with unique IDs
    2. Display both template files and parameter values
    3. Show file URLs for uploaded templates
    4. Present clear verification checklist
    5. Get explicit user confirmation
    6. Allow user to modify values if needed
    7. Prepare inputs for rule structure creation with unique identifiers

    VERIFICATION PRESENTATION FORMAT:
    "INPUT VERIFICATION SUMMARY:

    Please review all collected inputs before rule creation:

    TEMPLATE INPUTS (Uploaded Files):
    ✓ Task Input: [TaskName.InputName]
        Task: [TaskName] → Input: [InputName]
        Format: [Format]
        File: [filename]
        URL: [file_url]
        Size: [file_size] bytes
        Status: ✓ Validated

    PARAMETER INPUTS (Values):
    ✓ Task Input: [TaskName.InputName]
        Task: [TaskName] → Input: [InputName]
        Type: [DataType]
        Value: [user_value]
        Required: [Yes/No]
        Status: ✓ Set

    VERIFICATION CHECKLIST:
    □ All required inputs collected
    □ Template files uploaded and validated
    □ Parameter values set and confirmed
    □ No missing or invalid inputs
    □ Ready for rule creation

    Are all these inputs correct?
    - Type 'yes' to proceed with rule creation
    - Type 'modify [TaskName.InputName]' to change a specific input
    - Type 'cancel' to abort rule creation"

    CRITICAL VERIFICATION RULES:
    - NEVER proceed to create_rule() without user verification
    - ALWAYS show complete input summary with unique identifiers
    - ALWAYS get explicit user confirmation
    - Allow input modifications using unique IDs
    - Validate completeness before approval
    - Prepare structured inputs for rule creation with proper task mapping

    Args:
        collected_inputs: Dict containing all collected template files and parameter values with unique IDs

    Returns:
        Dict containing verification status, user confirmation, and structured inputs for rule creation
    """

    if not collected_inputs:
        return {"success": False, "error": "No inputs provided for verification"}

    try:
        # Analyze collected inputs with unique ID handling
        verification_summary = {"template_files": [], "parameter_values": [], "total_collected": 0, "missing_inputs": [], "validation_errors": [], "structured_inputs": {}, "inputs_meta": [
        ], "task_input_mapping": {}}  # For rule creation with unique names  # For rule creation with metadata - FIXED: only original input names  # Maps rule input names to original task inputs

        # Process template files with unique IDs
        template_files = collected_inputs.get("template_files", {})
        for unique_input_id, file_info in template_files.items():
            # Parse unique_input_id: "TaskName.InputName"
            if "." not in unique_input_id:
                continue  # Skip invalid IDs

            task_name, input_name = unique_input_id.split(".", 1)

            verification_summary["template_files"].append({"unique_input_id": unique_input_id, "task_name": task_name, "input_name": input_name, "filename": file_info.get("filename"), "file_url": file_info.get(
                "file_url"), "file_size": file_info.get("file_size"), "format": file_info.get("format"), "data_type": file_info.get("data_type", "FILE"), "status": "✓ Validated" if file_info.get("validated") else "⚠ Needs validation"})

            # Add to structured inputs for rule creation - FIXED: Remove task prefix
            # FIXED: Use original input name only (no task prefix)
            rule_input_name = input_name
            # FIXED: For FILE and HTTP_CONFIG inputs, use the uploaded file URL as the value (not content)
            # Always use file URL for FILE and HTTP_CONFIG inputs
            input_value = file_info.get("file_url")
            verification_summary["structured_inputs"][rule_input_name] = input_value

            # FIXED: inputs_meta should only contain original input names, not TaskName_InputName
            verification_summary["inputs_meta"].append({"name": input_name, "dataType": file_info.get("data_type", "FILE"), "required": file_info.get(
                "required", True), "defaultValue": input_value})  # FIXED: Use original input name only  # Use file URL as default value

            # Store mapping for I/O map creation
            verification_summary["task_input_mapping"][rule_input_name] = {
                "task_name": task_name, "input_name": input_name, "unique_id": unique_input_id, "rule_input_name": rule_input_name}  # For I/O mapping reference

        # Process parameter values with unique IDs
        parameter_values = collected_inputs.get("parameter_values", {})
        for unique_input_id, value_info in parameter_values.items():
            # Parse unique_input_id: "TaskName.InputName"
            if "." not in unique_input_id:
                continue  # Skip invalid IDs

            task_name, input_name = unique_input_id.split(".", 1)

            verification_summary["parameter_values"].append({"unique_input_id": unique_input_id, "task_name": task_name, "input_name": input_name, "value": value_info.get(
                "value"), "data_type": value_info.get("data_type"), "required": value_info.get("required"), "status": "✓ Set" if value_info.get("value") is not None else "⚠ Missing"})

            # Add to structured inputs for rule creation - FIXED: Remove task prefix
            # FIXED: Use original input name only (no task prefix)
            rule_input_name = input_name
            # For parameter inputs, use the actual user-provided value
            input_value = value_info.get("value")
            verification_summary["structured_inputs"][rule_input_name] = input_value

            # FIXED: inputs_meta should only contain original input names, not TaskName_InputName
            verification_summary["inputs_meta"].append({"name": input_name, "dataType": value_info.get("data_type", "STRING"), "required": value_info.get(
                "required", True), "defaultValue": input_value})  # FIXED: Use original input name only  # Use actual user value as default

            # Store mapping for I/O map creation
            verification_summary["task_input_mapping"][rule_input_name] = {
                "task_name": task_name, "input_name": input_name, "unique_id": unique_input_id, "rule_input_name": rule_input_name}  # For I/O mapping reference

        verification_summary["total_collected"] = len(
            template_files) + len(parameter_values)

        # Check for missing required inputs
        for item in verification_summary["template_files"] + verification_summary["parameter_values"]:
            if "Missing" in item["status"] or "⚠" in item["status"]:
                verification_summary["missing_inputs"].append(
                    item["unique_input_id"])

        # Generate verification presentation
        verification_text = rule.generate_verification_presentation_with_unique_ids(
            verification_summary)

        return {"success": True, "verification_summary": verification_summary, "verification_presentation": verification_text, "ready_for_creation": len(verification_summary["missing_inputs"]) == 0, "missing_count": len(verification_summary["missing_inputs"]), "structured_inputs": verification_summary["structured_inputs"], "inputs_meta": verification_summary["inputs_meta"], "task_input_mapping": verification_summary["task_input_mapping"], "message": "Input verification prepared with unique identifiers. Present to user for confirmation.", "next_action": "Show verification_presentation to user and wait for confirmation"}

    except Exception as e:
        return {"success": False, "error": f"Failed to verify collected inputs: {e}"}


# Rule creation tools
@mcp.tool()
def create_rule(rule_structure: Dict[str, Any]) -> Dict[str, Any]:
    """Create a rule with the provided structure.

    COMPLETE RULE CREATION PROCESS:

    CRITICAL: This tool should ONLY be called after complete input collection and verification workflow.

    PRE-CREATION REQUIREMENTS:
    1. All inputs must be collected through systematic workflow
    2. User must provide input overview confirmation
    3. All template inputs processed via collect_template_input()
    4. All parameter values collected and verified
    5. User must confirm all input values before rule creation
    6. Primary application type must be determined
    7. Rule structure must be shown to user in YAML format for approval

    RULE PREVIEW REQUIREMENT:
    - ALWAYS show complete rule structure in YAML format to user before creation
    - Get explicit user confirmation: "Here's your rule structure: [YAML]. Create this rule? (yes/no)"
    - Only proceed after user approves the rule structure
    - Allow modifications if user requests changes

    STEP 1 - PRIMARY APPLICATION TYPE DETERMINATION:
    Before creating rule structure, determine primary application type:
    1. Collect all unique appType tags from selected tasks
    2. Filter out 'nocredapp' (dummy placeholder value)
    3. Handle app type selection:
        - If only one valid appType: Use automatically
        - If multiple valid appTypes: Ask user to choose primary application
            "I found multiple application types in your selected tasks:
            - AppType1 (used by Task1, Task2)
            - AppType2 (used by Task3)
            Which application type should be the primary one for this rule?"
        - If no valid appTypes (all were nocredapp): Use 'generic' as default
    4. Set primary app type for appType, annotateType, and app fields (single value arrays)

    STEP 2 - RULE STRUCTURE REQUIREMENTS:
    ```yaml    
        apiVersion: rule.policycow.live/v1alpha1
        kind: rule
        meta:
            name: MeaningfulRuleName
            purpose: Clear statement based on user breakdown
            description: Detailed description combining all steps
            labels:
            appType: [PRIMARY_APP_TYPE_FROM_STEP_1] # Single value array
            environment: [logical] # Array
            execlevel: [app] # Array
            annotations:
            annotateType: [PRIMARY_APP_TYPE_FROM_STEP_1] # Same as appType
            app: [PRIMARY_APP_TYPE_FROM_STEP_1] # Same as appType
        spec:
            inputs:
              InputName: [ACTUAL_USER_VALUE_OR_FILE_URL]  # FIXED: No task prefix, just original input names
            inputsMeta__:
            - name: InputName  # FIXED: Original input names only
              dataType: FILE|HTTP_CONFIG|STRING|INT|FLOAT|BOOLEAN|DATE|DATETIME
              required: true
              defaultValue: [ACTUAL_USER_VALUE_OR_FILE_URL] # Values collected from users
            outputsMeta__:
            - name: FinalOutput
              dataType: FILE|STRING|INT|FLOAT|BOOLEAN|DATE|DATETIME
              required: true
              defaultValue: [ACTUAL_RULE_OUTPUT_VALUE]
            tasks:
            - name: Step1TaskName # FIXED: Original task names only
              alias: t1
              type: task
              appTags:
                appType: [COPY_FROM_TASK_DEFINITION] # Keep original task appType
              purpose: What this task does for Step 1
        ioMap:
        - t1.Input.TaskInput:=*.Input.InputName  # FIXED: Use original input names
        - t2.Input.TaskInput:=t1.Output.TaskOutput
        - '*.Output.FinalOutput:=t2.Output.TaskOutput'
    ```

    STEP 3 - I/O MAPPING COMPLETE SYNTAX GUIDE:

    CRITICAL SYNTAX: Use golang-style assignment: destination:=source

    3-PART STRUCTURE: PLACE.DIRECTION.ATTRIBUTE_NAME

    1. PLACE (First part):
        - '*' = Rule level (inputs/outputs that user provides/receives)
        - 't1', 't2', 't3', etc. = Task alias (refers to specific task in workflow)

    2. DIRECTION (Second part):
        - 'Input' = Input parameters/data going INTO task
        - 'Output' = Output results/data coming FROM task

    3. ATTRIBUTE_NAME (Third part):
        - Exact name of input/output attribute from task specifications
        - Must match actual parameter names from task definitions (case-sensitive)
        - Use EXACT names from tasks://details/{task_name} specifications

    MAPPING RULES:
    - *.Input.X:=source = Rule-level input X gets value from source
    - *.Output.Y:=source = Rule-level output Y gets value from source
    - t1.Input.Z:=source = Task t1's input Z gets value from source
    - t2.Input.A:=t1.Output.B = Task t2's input A gets value from task t1's output B

    SEQUENTIAL FLOW PATTERN (3 tasks example):
    ```
    ioMap:
    # Rule inputs to first task
    - t1.Input.DataFile:=*.Input.ConfigFile   # FIXED: Rule input "ConfigFile" → Task1 input "DataFile"
    - t1.Input.ConfigFile:=*.Input.Settings   # FIXED: Rule input "Settings" → Task1 input "ConfigFile"

    # First task output to second task input
    - t2.Input.InputData:=t1.Output.ProcessedData     # Task1 output "ProcessedData" → Task2 input "InputData"
    - t2.Input.MappingRules:=*.Input.Rules   # FIXED: Rule input "Rules" → Task2 input "MappingRules"

    # Second task output to third task input
    - t3.Input.ProcessedData:=t2.Output.TransformedData # Task2 output "TransformedData" → Task3 input "ProcessedData"

    # Final task outputs to rule outputs
    - '*.Output.FinalReport:=t3.Output.GeneratedReport'     # Task3 output "GeneratedReport" → Rule output "FinalReport"
    - '*.Output.ProcessedRecords:=t2.Output.TransformedData' # Task2 output "TransformedData" → Rule output "ProcessedRecords"
    ```

    CRITICAL I/O MAPPING RULES:
    - Always use EXACT attribute names from task input/output specifications
    - Ensure data flows sequentially: Rule → Task1 → Task2 → Task3 → Rule
    - Rule inputs (*.Input.X) come from user-provided values OR uploaded file URLs
    - Rule outputs (*.Output.Y) are final results user receives
    - Task aliases (t1, t2, etc.) must match exactly with task aliases in tasks section
    - Use quotes around mappings that start with *.Output to handle YAML parsing
    - Validate attribute names against task specifications before creating mappings
    - For FILE inputs: Use uploaded file URLs as values
    - For HTTP_CONFIG inputs: Use uploaded file URLs as values
    - For PARAMETER inputs: Use actual user-provided values

    STEP 4 - INPUT VALUE HANDLING:
    - FILE inputs: Use file URLs from upload (e.g., "<<MINIO_FILE_PATH>>/file_12345_config.json")
    - HTTP_CONFIG inputs: Use file URLs from upload (e.g., "<<MINIO_FILE_PATH>>/file_12345_http_config.json")
    - STRING inputs: Use actual user values (e.g., "threshold_75")
    - INT inputs: Use converted integer values (e.g., 100)
    - BOOLEAN inputs: Use boolean values (e.g., true)
    - All inputs must have actual values, never use placeholder or default values

    STEP 5 - RULE STRUCTURE CONFIRMATION:
    - Get explicit confirmation from user before creating rule
    - Show complete rule structure in YAML format
    - Wait for user approval before proceeding

    STEP 6 - PRIMARY APPLICATION TYPE RULES:
    - ALWAYS extract all appType tags from selected tasks
    - ALWAYS filter out 'nocredapp' (dummy placeholder)
    - SINGLE VALUE ONLY: appType, annotateType, and app fields must contain only one value in array
    - IF multiple valid appTypes: Ask user to choose primary application type
    - IF only one valid appType: Use it automatically
    - IF no valid appTypes: Default to 'generic'
    - SAME VALUE: appType, annotateType, and app must all use same primary app type
    - TASK appTags: Keep original task appType values in individual task definitions

    VALIDATION CHECKLIST BEFORE CALLING create_rule():
    □ Input overview presented to user and confirmed
    □ All template inputs processed through collect_template_input()
    □ File URLs received for all template inputs and used as input values
    □ Parameter values collected for non-template inputs
    □ All input values summarized and verified by user
    □ Primary app type determined (single value)
    □ I/O mappings use exact attribute names from task specs
    □ Sequential data flow established
    □ Rule structure shown to user in YAML format
    □ User confirmed rule structure before creation

    Args:
        rule_structure: Complete rule structure in the required format

    Returns:
        Result of rule creation including status and rule ID
    """

    # Validate rule structure
    validation_result = rule.validate_rule_structure(rule_structure)
    if not validation_result["valid"]:
        return {"success": False, "error": "Invalid rule structure", "validation_errors": validation_result["errors"]}

    # Generate YAML preview for user confirmation
    yaml_preview = rule.generate_yaml_preview(rule_structure)

    # Check if this is a preview request or actual creation
    # if not rule_structure.get("_user_confirmed", False):
    #     return {"success": True, "needs_user_confirmation": True, "yaml_preview": yaml_preview, "confirmation_message": f"Here's your rule structure:\n\n{yaml_preview}\n\nCreate this rule? (yes/no)", "rule_structure": rule_structure, "message": "Rule structure prepared. Show YAML preview to user for confirmation."}

    # Create the rule (integrate with your actual API here)
    try:
        result = rule.create_rule_api(rule_structure)

        # Store rule structure for design notes generation
        # self.store_rule_context(result["rule_id"], rule_structure)

        # Auto-generate design notes using internal template after rule creation
        design_notes_result = {"auto_generated": True, "message": "Design notes will be auto-generated using comprehensive internal template",
                               "next_action": "Call create_design_notes(rule_name) to generate and save design notes"}

        return {"success": True, "rule_id": result["rule_id"], "message": "Rule created successfully", "rule_structure": rule_structure, "yaml_preview": yaml_preview, "timestamp": result.get("timestamp"), "status": result.get("status", "created"), "design_notes_info": design_notes_result, "next_step": "Call create_design_notes() to auto-generate comprehensive design notes"}
    except Exception as e:
        return {"success": False, "error": f"Failed to create rule: {e}"}
