from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, get_type_hints

from constants import constants
from mcpconfig.config import mcp
from mcptypes import exception
from mcptypes.rule_type import TaskVO
from utils import rule, wsutils

# Phase 1: Lightweight task summary resource


# @mcp.resource("tasks://summary")
@mcp.tool()
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
def prepare_input_collection_overview(selected_tasks: List[Dict[str, str]]) -> Dict[str, Any]:
    """Prepare and present input collection overview before starting any input collection.

    MANDATORY FIRST STEP - INPUT OVERVIEW PROCESS:

    This tool MUST be called before collecting any inputs. It analyzes all selected tasks
    and presents a complete overview of what inputs will be needed.

    HANDLES DUPLICATE INPUT NAMES WITH TASK ALIASES:
    - Creates unique identifiers for each task-alias-input combination
    - Format: "{task_alias}.{input_name}" for uniqueness
    - Prevents conflicts when multiple tasks have same input names or same task used multiple times
    - Maintains clear mapping between task aliases and their specific inputs
    - Task aliases should be simple, meaningful step indicators (e.g., "step1", "validation", "processing")

    OVERVIEW REQUIREMENTS:
    1. Analyze ALL selected tasks with their aliases for input requirements
    2. Categorize inputs: templates vs parameters
    3. Create unique identifiers for each task-alias-input combination
    4. Count total inputs needed
    5. Present clear overview to user
    6. Get user confirmation before proceeding
    7. Return structured overview for systematic collection

    OVERVIEW PRESENTATION FORMAT:
    "INPUT COLLECTION OVERVIEW:

    I've analyzed your selected tasks. Here's what we need to configure:

    TEMPLATE INPUTS (Files):
    • Task: [TaskAlias] ([TaskName]) → Input: [InputName] ([Format] file)
        Unique ID: [TaskAlias.InputName]
        Description: [InputDescription]

    PARAMETER INPUTS (Values):
    • Task: [TaskAlias] ([TaskName]) → Input: [InputName] ([DataType])
        Unique ID: [TaskAlias.InputName]
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
    - Create unique task_alias.input identifiers to avoid conflicts
    - Show clear task-alias-input relationships to user

    Args:
        selected_tasks: List of dicts with 'task_name' and 'task_alias'
                       Example: [
                           {"task_name": "data_validation", "task_alias": "step1"},
                           {"task_name": "data_processing", "task_alias": "step2"},
                           {"task_name": "data_validation", "task_alias": "final_check"}
                       ]

    Returns:
        Dict containing structured input overview and collection plan with unique identifiers
    """

    if not selected_tasks:
        return {"success": False, "error": "No tasks selected for input analysis"}

    try:
        input_analysis = {
            "template_inputs": [], 
            "parameter_inputs": [], 
            "total_count": 0, 
            "template_count": 0,
            "parameter_count": 0, 
            "estimated_minutes": 0, 
            "unique_input_map": {},  # Maps unique_id to task alias and input info
            "task_alias_map": {}     # Maps task_alias to task_name for reference
        }

        # Validate input format and task aliases
        for task_info in selected_tasks:
            if not isinstance(task_info, dict) or "task_name" not in task_info or "task_alias" not in task_info:
                return {"success": False, "error": "Each task must be a dict with 'task_name' and 'task_alias' keys"}
            
            task_alias = task_info["task_alias"].strip()
            if not task_alias:
                return {"success": False, "error": f"Task alias is required for task {task_info['task_name']}"}
            
            if len(task_alias) > 100:
                return {"success": False, "error": f"Task alias '{task_alias}' exceeds 100 character limit"}
            
            # Check for duplicate aliases
            if task_alias in input_analysis["task_alias_map"]:
                return {"success": False, "error": f"Duplicate task alias '{task_alias}' found. Each alias must be unique."}
            
            # Store task alias mapping
            input_analysis["task_alias_map"][task_alias] = {
                "task_name": task_info["task_name"],
                "purpose": task_info.get("purpose", "")
            }

        available_tasks = []
        tasks_resp = rule.fetch_task_api(params={
            "tags": "primitive"})

        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            available_tasks = [TaskVO.from_dict(
                task) for task in tasks_resp["items"]]

        if not available_tasks:
            return {"success": False, "error": "No tasks loaded"}

        # Analyze each selected task with its alias
        for task_info in selected_tasks:
            task_name = task_info["task_name"]
            task_alias = task_info["task_alias"]
            task_purpose = task_info.get("purpose", "")

            # Find the task definition
            task = None
            for available_task in available_tasks:
                if available_task.name == task_name:
                    task = available_task
                    break

            if not task:
                continue

            # Process each input with unique identifier using task alias
            for inp in task.inputs:
                # Create unique identifier: TaskAlias.InputName
                unique_input_id = f"{task_alias}.{inp.name}"

                input_info = {
                    "task_name": task_name,
                    "task_alias": task_alias, 
                    "task_purpose": task_purpose,
                    "input_name": inp.name,
                    "unique_input_id": unique_input_id,
                    "description": inp.description,
                    "data_type": inp.dataType,
                    "required": inp.required,
                    "has_template": bool(inp.templateFile),
                    "format": inp.format if inp.templateFile else None,
                    "has_default": bool(inp.defaultValue),
                    "default_value": inp.defaultValue if inp.defaultValue else None
                }

                # Store in unique input map for easy lookup
                input_analysis["unique_input_map"][unique_input_id] = {
                    "task_name": task_name,
                    "task_alias": task_alias,
                    "input_name": inp.name,
                    "task_input_obj": inp
                }

                if inp.templateFile or inp.dataType.upper() in ["FILE", "HTTP_CONFIG"]:
                    input_analysis["template_inputs"].append(input_info)
                    input_analysis["template_count"] += 1
                    # File inputs take longer (2-3 minutes each)
                    input_analysis["estimated_minutes"] += 3
                else:
                    input_analysis["parameter_inputs"].append(input_info)
                    input_analysis["parameter_count"] += 1
                    # Parameter inputs are quicker (30 seconds each)
                    input_analysis["estimated_minutes"] += 0.5

        input_analysis["total_count"] = input_analysis["template_count"] + \
            input_analysis["parameter_count"]

        # Generate overview presentation
        overview_text = rule.generate_input_overview_presentation_with_unique_ids(
            input_analysis)

        return {
            "success": True,
            "input_analysis": input_analysis,
            "overview_presentation": overview_text,
            "unique_input_map": input_analysis["unique_input_map"],
            "task_alias_map": input_analysis["task_alias_map"],
            "collection_plan": {
                "step1": "Template inputs (files) - collected first with task aliases",
                "step2": "Parameter inputs (values) - collected second with task aliases",
                "step3": "Final verification of all collected inputs with aliases",
                "step4": "Rule structure creation with proper task alias mapping"
            },
            "message": "Input overview prepared with task aliases. Present to user and get confirmation before proceeding.",
            "next_action": "Show overview_presentation to user and wait for confirmation"
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to prepare input overview: {e}"}


@mcp.tool()
def verify_collected_inputs(collected_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Verify all collected inputs with user before rule creation.

    MANDATORY VERIFICATION STEP:

    This tool MUST be called after all inputs are collected but before create_rule().
    It presents a comprehensive summary of all collected inputs for user verification.

    HANDLES DUPLICATE INPUT NAMES WITH TASK ALIASES:
    - Uses unique identifiers (TaskAlias.InputName) for each input
    - Properly maps each unique input to its specific task alias
    - Creates structured inputs for rule creation with unique names when needed
    - Maintains clear separation between inputs from different task instances

    VERIFICATION REQUIREMENTS:
    1. Show complete summary of ALL collected inputs with unique IDs
    2. Display both template files and parameter values
    3. Show file URLs for uploaded templates
    4. Present clear verification checklist
    5. Get explicit user confirmation
    6. Allow user to modify values if needed
    7. Prepare inputs for rule structure creation with proper task alias mapping

    VERIFICATION PRESENTATION FORMAT:
    "INPUT VERIFICATION SUMMARY:

    Please review all collected inputs before rule creation:

    TEMPLATE INPUTS (Uploaded Files):
    ✓ Task Input: [TaskAlias.InputName]
        Task: [TaskAlias] ([TaskName]) → Input: [InputName]
        Format: [Format]
        File: [filename]
        URL: [file_url]
        Size: [file_size] bytes
        Status: ✓ Validated

    PARAMETER INPUTS (Values):
    ✓ Task Input: [TaskAlias.InputName]
        Task: [TaskAlias] ([TaskName]) → Input: [InputName]
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
    - Type 'modify [TaskAlias.InputName]' to change a specific input
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
        verification_summary = {
            "template_files": [], 
            "parameter_values": [], 
            "total_collected": 0, 
            "missing_inputs": [], 
            "validation_errors": [], 
            "structured_inputs": {}, 
            "inputs_meta": [],
            "task_input_mapping": {},  # Maps rule input names to original task inputs
            "task_alias_map": collected_inputs.get("task_alias_map", {})  # Preserve task alias mapping
        }

        # Process template files with unique IDs
        template_files = collected_inputs.get("template_files", {})
        for unique_input_id, file_info in template_files.items():
            # Parse unique_input_id: "TaskAlias.InputName"
            if "." not in unique_input_id:
                continue  # Skip invalid IDs

            task_alias, input_name = unique_input_id.split(".", 1)

            verification_summary["template_files"].append({
                "unique_input_id": unique_input_id,
                "task_alias": task_alias,
                "task_name": file_info.get("task_name", ""),
                "input_name": input_name,
                "filename": file_info.get("filename"),
                "file_url": file_info.get("file_url"),
                "file_size": file_info.get("file_size"),
                "format": file_info.get("format"),
                "data_type": file_info.get("data_type", "FILE"),
                "status": "✓ Validated" if file_info.get("validated") else "⚠ Needs validation"
            })

            # For rule creation: Handle input naming strategy
            # If there are conflicts (same input name from different tasks), use unique names
            # Otherwise, use original input names for simplicity
            input_value = file_info.get("file_url")
            
            # Check if this input name already exists in structured_inputs
            if input_name in verification_summary["structured_inputs"]:
                # Conflict detected - use unique naming: TaskAlias_InputName
                rule_input_name = f"{task_alias}_{input_name}"
            else:
                # No conflict - use original input name
                rule_input_name = input_name
                
            verification_summary["structured_inputs"][rule_input_name] = input_value

            verification_summary["inputs_meta"].append({
                "name": rule_input_name,
                "dataType": file_info.get("data_type", "FILE"),
                "required": file_info.get("required", True),
                "defaultValue": input_value
            })

            # Store mapping for I/O map creation
            verification_summary["task_input_mapping"][rule_input_name] = {
                "task_alias": task_alias,
                "task_name": file_info.get("task_name", ""),
                "input_name": input_name,
                "unique_id": unique_input_id,
                "rule_input_name": rule_input_name
            }

        # Process parameter values with unique IDs
        parameter_values = collected_inputs.get("parameter_values", {})
        for unique_input_id, value_info in parameter_values.items():
            # Parse unique_input_id: "TaskAlias.InputName"
            if "." not in unique_input_id:
                continue  # Skip invalid IDs

            task_alias, input_name = unique_input_id.split(".", 1)

            verification_summary["parameter_values"].append({
                "unique_input_id": unique_input_id,
                "task_alias": task_alias,
                "task_name": value_info.get("task_name", ""),
                "input_name": input_name,
                "value": value_info.get("value"),
                "data_type": value_info.get("data_type"),
                "required": value_info.get("required"),
                "status": "✓ Set" if value_info.get("value") is not None else "⚠ Missing"
            })

            # For rule creation: Handle input naming strategy
            input_value = value_info.get("value")
            
            # Check if this input name already exists in structured_inputs
            if input_name in verification_summary["structured_inputs"]:
                # Conflict detected - use unique naming: TaskAlias_InputName
                rule_input_name = f"{task_alias}_{input_name}"
            else:
                # No conflict - use original input name
                rule_input_name = input_name
                
            verification_summary["structured_inputs"][rule_input_name] = input_value

            verification_summary["inputs_meta"].append({
                "name": rule_input_name,
                "dataType": value_info.get("data_type", "STRING"),
                "required": value_info.get("required", True),
                "defaultValue": input_value
            })

            # Store mapping for I/O map creation
            verification_summary["task_input_mapping"][rule_input_name] = {
                "task_alias": task_alias,
                "task_name": value_info.get("task_name", ""),
                "input_name": input_name,
                "unique_id": unique_input_id,
                "rule_input_name": rule_input_name
            }

        verification_summary["total_collected"] = len(template_files) + len(parameter_values)

        # Check for missing required inputs
        for item in verification_summary["template_files"] + verification_summary["parameter_values"]:
            if "Missing" in item["status"] or "⚠" in item["status"]:
                verification_summary["missing_inputs"].append(item["unique_input_id"])

        # Generate verification presentation
        verification_text = rule.generate_verification_presentation_with_unique_ids(
            verification_summary)

        return {
            "success": True,
            "verification_summary": verification_summary,
            "verification_presentation": verification_text,
            "ready_for_creation": len(verification_summary["missing_inputs"]) == 0,
            "missing_count": len(verification_summary["missing_inputs"]),
            "structured_inputs": verification_summary["structured_inputs"],
            "inputs_meta": verification_summary["inputs_meta"],
            "task_input_mapping": verification_summary["task_input_mapping"],
            "task_alias_map": verification_summary["task_alias_map"],
            "message": "Input verification prepared with task aliases. Present to user for confirmation.",
            "next_action": "Show verification_presentation to user and wait for confirmation"
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to verify collected inputs: {e}"}


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

    STEP 2 - RULE STRUCTURE WITH TASK ALIASES:
    ```yaml
        apiVersion: rule.policycow.live/v1alpha1
        kind: rule
        meta:
            name: MeaningfulRuleName # Simple name. Without special characters and white spaces
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
              InputName: [ACTUAL_USER_VALUE_OR_FILE_URL]  # Use original or unique names based on conflicts
            inputsMeta__:
            - name: InputName  # Use original or unique names based on conflicts
              dataType: FILE|HTTP_CONFIG|STRING|INT|FLOAT|BOOLEAN|DATE|DATETIME
              required: true
              defaultValue: [ACTUAL_USER_VALUE_OR_FILE_URL] # Values collected from users
              format: [ACTUAL_FILE_FORMAT] # Only include for FILE types (json, yaml, toml, xml, etc.)
            outputsMeta__:
            - name: FinalOutput
              dataType: FILE|STRING|INT|FLOAT|BOOLEAN|DATE|DATETIME
              required: true
              defaultValue: [ACTUAL_RULE_OUTPUT_VALUE]
            tasks:
            - name: Step1TaskName # Original task names
              alias: step1 # Meaningful task aliases (simple descriptors)
              type: task
              appTags:
                appType: [COPY_FROM_TASK_DEFINITION] # Keep original task appType
              purpose: What this task does for Step 1
            - name: Step2TaskName
              alias: validation # Another meaningful alias
              type: task
              appTags:
                appType: [COPY_FROM_TASK_DEFINITION]
              purpose: What this task does for validation
            ioMap:
            - step1.Input.TaskInput:=*.Input.InputName  # Use task aliases in I/O mapping
            - validation.Input.TaskInput:=step1.Output.TaskOutput
            - '*.Output.FinalOutput:=validation.Output.TaskOutput'
    ```

    STEP 3 - I/O MAPPING WITH TASK ALIASES:

    CRITICAL SYNTAX: Use golang-style assignment: destination:=source

    3-PART STRUCTURE: PLACE.DIRECTION.ATTRIBUTE_NAME

    1. PLACE (First part):
        - '*' = Rule level (inputs/outputs that user provides/receives)
        - 'step1', 'validation', 'processing', etc. = Task alias (meaningful descriptors)

    2. DIRECTION (Second part):
        - 'Input' = Input parameters/data going INTO task
        - 'Output' = Output results/data coming FROM task

    3. ATTRIBUTE_NAME (Third part):
        - Exact name of input/output attribute from task specifications
        - Must match actual parameter names from task definitions (case-sensitive)
        - Use EXACT names from tasks://details/{task_name} specifications

    MAPPING RULES WITH TASK ALIASES:
    - *.Input.X:=source = Rule-level input X gets value from source
    - *.Output.Y:=source = Rule-level output Y gets value from source
    - step1.Input.Z:=source = Task with alias 'step1' input Z gets value from source
    - validation.Input.A:=step1.Output.B = Task 'validation' input A gets value from task 'step1' output B

    SEQUENTIAL FLOW PATTERN WITH MEANINGFUL ALIASES:
    ```
    ioMap:
    # Rule inputs to first task
    - step1.Input.DataFile:=*.Input.ConfigFile   # Rule input "ConfigFile" → step1 input "DataFile"
    - step1.Input.Settings:=*.Input.UserSettings # Rule input "UserSettings" → step1 input "Settings"

    # First task output to validation task input
    - validation.Input.InputData:=step1.Output.ProcessedData     # step1 output → validation input
    - validation.Input.Rules:=*.Input.ValidationRules           # Rule input → validation input

    # Validation task output to processing task input  
    - processing.Input.ValidatedData:=validation.Output.CleanData # validation output → processing input

    # Final task outputs to rule outputs
    - '*.Output.FinalReport:=processing.Output.Report'          # processing output → Rule output
    - '*.Output.ProcessedRecords:=processing.Output.Records'    # processing output → Rule output
    ```

    CRITICAL I/O MAPPING RULES:
    - Always use EXACT attribute names from task input/output specifications
    - Use meaningful task aliases instead of generic t1, t2, etc.
    - Ensure data flows sequentially: Rule → Task1 → Task2 → Task3 → Rule
    - Rule inputs (*.Input.X) come from user-provided values OR uploaded file URLs
    - Rule outputs (*.Output.Y) are final results user receives
    - Task aliases must match exactly with task aliases in tasks section
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
    □ Task aliases are meaningful and descriptive
    □ Sequential data flow established
    □ Rule structure shown to user in YAML format
    □ User confirmed rule structure before creation

    Args:
        rule_structure: Complete rule structure in the required format with task aliases

    Returns:
        Result of rule creation including status and rule ID
    """

    # Validate rule structure
    validation_result = rule.validate_rule_structure(rule_structure)
    if not validation_result["valid"]:
        return {"success": False, "error": "Invalid rule structure", "validation_errors": validation_result["errors"]}

    # Additional validation for task aliases in I/O mappings
    tasks_section = rule_structure.get("spec", {}).get("tasks", [])
    io_map = rule_structure.get("spec", {}).get("ioMap", [])
    
    # Extract task aliases from tasks section
    valid_aliases = set()
    for task in tasks_section:
        if "alias" in task:
            valid_aliases.add(task["alias"])
    
    # Validate I/O mappings use correct task aliases
    for mapping in io_map:
        if "." in mapping and ":=" in mapping:
            left_side = mapping.split(":=")[0].strip()
            right_side = mapping.split(":=")[1].strip()
            
            # Check left side for task alias
            if not left_side.startswith("*."):
                alias_part = left_side.split(".")[0]
                if alias_part not in valid_aliases and alias_part != "*":
                    return {
                        "success": False,
                        "error": f"Unknown task alias '{alias_part}' in I/O mapping: {mapping}. Valid aliases: {list(valid_aliases)}"
                    }
            
            # Check right side for task alias  
            if not right_side.startswith("*."):
                alias_part = right_side.split(".")[0]
                if alias_part not in valid_aliases and alias_part != "*":
                    return {
                        "success": False,
                        "error": f"Unknown task alias '{alias_part}' in I/O mapping: {mapping}. Valid aliases: {list(valid_aliases)}"
                    }

    # Generate YAML preview for user confirmation
    yaml_preview = rule.generate_yaml_preview(rule_structure)

    # Create the rule (integrate with your actual API here)
    try:
        result = rule.create_rule_api(rule_structure)

        # Auto-generate design notes using internal template after rule creation
        design_notes_result = {
            "auto_generated": True, 
            "message": "Design notes will be auto-generated using comprehensive internal template",
            "next_action": "Call create_design_notes(rule_name, design_notes_structure) to generate and save design notes"
        }

        readme_info = {
            "auto_generated": True, 
            "message": "README will be auto-generated using a comprehensive internal template",
            "next_action": "Call create_rule_readme(rule_name, readme_content) to generate and save the README"
        }

        return {
            "success": True,
            "rule_id": result["rule_id"],
            "message": "Rule created successfully with meaningful task aliases",
            "rule_structure": rule_structure,
            "yaml_preview": yaml_preview,
            "timestamp": result.get("timestamp"),
            "status": result.get("status", "created"),
            "design_notes_info": design_notes_result,
            "readme_info": readme_info,
            "next_step": "Call create_design_notes() to auto-generate comprehensive design notes. Call create_rule_readme() to auto-generate a comprehensive README file."
        }
    except exception.CCowExceptionVO as e:
        return {"success": False, "error": f"Failed to create rule: {e.to_dict()}"}
    except Exception as e:
        return {"success": False, "error": f"Failed to create rule: {e}"}
    

@mcp.tool()
def generate_design_notes_preview(rule_name: str) -> Dict[str, Any]:
    """
    Generate design notes preview for user confirmation before actual creation.

    ## DESIGN NOTES PREVIEW GENERATION

    This tool generates a complete Jupyter notebook structure as a dictionary for user review. The MCP will create the full notebook content with 7 standardized sections based on rule context and metadata, then return it for user confirmation.

    ## DESIGN NOTES TEMPLATE STRUCTURE REQUIREMENTS

    The MCP should generate a Jupyter notebook (.ipynb format) with exactly 7 sections:

    ### SECTION 1: Evidence Details
    **DESCRIPTION:** System identification and rule purpose documentation

    **CONTENT REQUIREMENTS:**
    - Table with columns: System | Source of data | Frameworks | Purpose
    - System: {TARGET_SYSTEM_NAME} (all lowercase")
    - Source: Always 'compliancecow'
    - Frameworks: Always '-'
    - Purpose: Use rule's purpose from metadata
    - RecommendedEvidenceName: {RULE_OUTPUT_NAME} (use rule's primary compliance output, exclude LogFile)
    - Description: Use rule description from metadata
    - Reference: Include actual API documentation links that the rule uses (extract from task specifications, no placeholder values)

    **FORMAT:** Markdown cell with table and code blocks only

    ### SECTION 2: Define the System Specific Data (Extended Data Schema)
    **DESCRIPTION:** System-specific raw data structure definition with detailed breakdown

    **CONTENT REQUIREMENTS:**

    #### Step 2a: Inputs
    - Generate numbered list from rule's spec.inputs
    - Format: "{NUMBER}. **{INPUT_NAME}({INPUT_DATA_TYPE})** - {INPUT_DESCRIPTION}"
    - Include all inputs with their types and purposes

    #### Step 2b: API & Flow
    - Generate numbered list of API endpoints based on target system
    - Format: "{NUMBER}. {HTTP_METHOD} {URL} - {BRIEF_DESCRIPTION}"
    - Include only actual API endpoints that this specific rule uses for data collection
    - Extract from task specifications, not generic templates

    #### Step 2c: Define the Extended Schema
    - Generate large JSON code block with actual API response structure
    - Use system-specific field names and realistic data values
    - Include all fields that will be processed by the rule

    **FORMAT:** Markdown headers with detailed lists + large JSON code block

    ### SECTION 3: Define the Standard Schema
    **DESCRIPTION:** Standardized compliance data format documentation

    **CONTENT REQUIREMENTS:**
    - Header explaining standard schema purpose
    - JSON code block with complete standardized structure containing:
    * System: based on target system (lowercase)
    * Source: Always 'compliancecow'
    * Resource info: ResourceID, ResourceName, ResourceType, ResourceLocation, ResourceTags, ResourceURL
    * System-specific data fields based on actual rule output columns, if unavailable then generate based on rule details
    * Compliance fields: ValidationStatusCode, ValidationStatusNotes, ComplianceStatus, ComplianceStatusReason
    * Evaluation and action fields: EvaluatedTime, UserAction, ActionStatus, ActionResponseURL (UserAction, ActionStatus, ActionResponseURL are empty by default)

    #### Step 3a: Sample Data
    - Generate markdown table with ALL standard schema columns in same order - include all columns even if empty
    - Include three complete example rows with realistic, system-specific data
    - Use proper data formatting and realistic identifiers

    **FORMAT:** JSON code block + comprehensive markdown table

    ### SECTION 4: Describe the Compliance Taxonomy
    **DESCRIPTION:** Status codes and compliance definitions

    **CONTENT REQUIREMENTS:**
    - Table with columns: ValidationStatusCode | ValidationStatusNotes | ComplianceStatus | ComplianceStatusReason
    - ValidationStatusCode: **CRITICAL FORMAT REQUIREMENT** - Rule-specific codes must strictly follow this exact format:
        * Each word must be exactly 3-4 characters long
        * Words must be separated by underscores (_)
        * Use ALL UPPERCASE letters
        * Create codes that directly relate to the rule's compliance purpose
        * Examples: CODE_OWN_HAS_PR_REV (code ownership has pull request review), REPO_SEC_SCAN_PASS (repository security scan passed), AUTH_MFA_ENBL (authentication multi-factor enabled)
        * **DO NOT** use generic codes like "PASS" or "FAIL" 
        * **DO NOT** exceed 4 characters per word
        * **DO NOT** use special characters other than underscores
        * Generate 4-6 different status codes covering various compliance scenarios
    - Detailed compliance reasons specific to the rule's purpose
    - Both COMPLIANT and NON_COMPLIANT scenarios

    **FORMAT:** Markdown cell with table

    ### SECTION 5: Calculation for Compliance Percentage and Status
    **DESCRIPTION:** Percentage calculations and status logic

    **CONTENT REQUIREMENTS:**
    - Header explaining compliance calculation methodology
    - Code cell with calculation logic:
    * TotalCount = Count of 'COMPLIANT' and 'NON_COMPLIANT' records
    * CompliantCount = Count of 'COMPLIANT' records
    * CompliancePCT = (CompliantCount / TotalCount) * 100
    * Status determination rules:
        - COMPLIANT: 100%
        - NON_COMPLIANT: 0% to less than 100%
        - NOT_DETERMINED: If no records are found

    **FORMAT:** Markdown header cell + Code cell with calculation logic

    ### SECTION 6: Describe (in words) the Remediation Steps for Non-Compliance
    **DESCRIPTION:** Non-compliance remediation procedures

    **CONTENT REQUIREMENTS:**
    - Can be "N/A" if no specific remediation steps apply
    - When applicable, provide:
    * Immediate Actions required
    * Short-term remediation steps
    * Long-term monitoring approaches
    * Responsible parties and timeframes
    - System-agnostic guidance that can be customized

    **FORMAT:** Markdown cell with detailed remediation procedures

    ### SECTION 7: Control Setup Details
    **DESCRIPTION:** Rule configuration and implementation details

    **CONTENT REQUIREMENTS:**
    - Table with two columns: Control Details | (Values)
    - Required fields (only these):
    * RuleName: Use actual rule name
    * PreRequisiteRuleNames: Default to 'N/A' or list dependencies
    * ExtendedSchemaRuleNames: Default to 'N/A' or list related rules
    * ApplicationClassName: Fetch all appType values from spec.tasks array, combine them, remove duplicates, and format as comma-separated values
    * PostSynthesizerName: Default to 'N/A' or specify if used

    **FORMAT:** Markdown table with control configuration details

    ## JUPYTER NOTEBOOK METADATA REQUIREMENTS

    - Include proper notebook metadata (colab, kernelspec, language_info)
    - Set nbformat: 4, nbformat_minor: 0
    - Use appropriate cell metadata with unique IDs for each section
    - Ensure proper markdown and code cell formatting

    ## MCP CONTENT POPULATION INSTRUCTIONS

    The MCP should extract the following information from the rule context:
    - Rule name, purpose, description from rule metadata
    - System name from appType (clean by removing connector suffixes like "-connector")
    - Task details from spec.tasks array
    - Input specifications from spec.inputs and spec.inputsMeta__
    - Output specifications from spec.outputsMeta__
    - Application connector information for control setup
    - API endpoints from task specifications (not generic placeholders)

    ## CONTENT GENERATION GUIDELINES

    - Use realistic, system-specific examples that can be customized later
    - Include comments in code sections indicating customization points
    - Provide system-agnostic content that applies broadly
    - Use consistent naming conventions throughout all sections
    - Extract actual API documentation links from task specifications
    - Generate ValidationStatusCodes that are specific to the rule's compliance purpose
    - Ensure all sample data reflects the actual system being monitored

    ## WORKFLOW

    1. MCP retrieves rule context from stored rule information
    2. MCP generates complete Jupyter notebook using template structure above
    3. MCP populates template with extracted rule metadata and calculated values
    4. MCP returns complete notebook structure as dictionary for user review
    5. User reviews and confirms the structure
    6. If approved, call create_design_notes() to actually save the notebook

    ## ARGS

    - rule_name: Name of the rule for which to generate design notes preview

    ## RETURNS

    Dict containing complete notebook structure for user review and confirmation
    """
    
    # MCP should directly construct the design notes based on the instructions above
    # No intermediate API calls needed - MCP has all the template details in the docstring
    # The MCP will use fetch_rule() internally and build the complete notebook structure
    
    return {
        "success": True, 
        "rule_name": rule_name,
        "design_notes_structure": {},  # MCP will populate this with complete notebook dictionary
        "sections_count": 7,
        "message": f"MCP should construct complete notebook structure for rule '{rule_name}' based on the detailed template instructions above",
        "next_action": "MCP should use fetch_rule() and build complete notebook dictionary, then return it in design_notes_structure"
    }


@mcp.tool()
def create_design_notes(rule_name: str, design_notes_structure: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create and save design notes after user confirmation.

    DESIGN NOTES CREATION:

    This tool actually creates and saves the design notes after the user has reviewed
    and confirmed the preview structure from generate_design_notes_preview().

    WORKFLOW:
    1. Before creating new design notes, call fetch_rule_design_notes() to check if already exist and continue the flow, if not then continue this flow
    2. User has already reviewed notebook structure from preview
    3. User confirmed the structure is acceptable
    4. This tool receives the complete design notes dictionary structure
    5. MCP saves the notebook and returns access details

    Args:
        rule_name: Name of the rule for which to create design notes
        design_notes_structure: Complete Jupyter notebook structure as dictionary

    Returns:
        Dict containing design notes creation status and access details
    """
    
    try:
        headers = wsutils.create_header()
        payload = {
            "ruleName": rule_name,
            "type": "mcp",
            "designNotesContent": rule.encode_content(design_notes_structure),  # Pass the complete notebook dictionary as an encoded string
        }
        
        save_resp = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_SAVE_DESIGN_NOTES),
            data=json.dumps(payload),
            header=headers
        )

        message = save_resp.get("message")
        if isinstance(message, str) and message == "Design notes file created successfully.":
            return {
                "success": True,
                "rule_name": rule_name,
                "filename": f"{rule_name}.ipynb",
                "sections_saved": len(design_notes_structure.get("cells", [])),
                "message": f"Design notes successfully created and saved for rule '{rule_name}'"
            }
        else:
            return {
                "success": False,
                "error": "Failed to save design notes",
                "rule_name": rule_name
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save design notes: {str(e)}",
            "rule_name": rule_name
        }


@mcp.tool()
def fetch_rule(rule_name: str,include_read_me: bool = False) -> Dict[str, Any]:
    """
    Fetch rule details by rule name.

    Args:
        rule_name: Name of the rule to retrieve
        include_read_me: Whether to include the README data in the response.
        
    Returns:
        Dict containing complete rule structure and metadata
    """
    
    try:
        headers = wsutils.create_header()
        
        get_rule_resp = wsutils.get(
            path=wsutils.build_api_url(endpoint=f"{constants.URL_FETCH_RULES}?name={rule_name}"),
            header=headers
        )
        
        if rule.is_valid_array(get_rule_resp, "items"):
            return {
                "success": True,
                "rule_name": rule_name,
                "rule_structure": get_rule_resp["items"][0],  # Complete rule as dictionary
                "message": f"Rule '{rule_name}' retrieved successfully"
            }
        
        else:
            return {
                "success": False,
                "error": f"Rule '{rule_name}' not found",
                "rule_name": rule_name
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch rule '{rule_name}': {str(e)}",
            "rule_name": rule_name
        }


@mcp.tool()
def fetch_rule_design_notes(rule_name: str) -> Dict[str,Any]:
    """
    Fetch and manage design notes for a rule.

    WORKFLOW:

    1. CHECK EXISTING NOTES:
    - Always check if design notes exist for the rule first (whether user wants to create or view)
    - If found: Present complete notebook to user in readable format
    - If not found: Offer to create new ones

    2. IF NOTES EXIST:
    - Show complete notebook with all sections (this serves as the VIEW)
    - Ask: "Here are your design notes. Modify or regenerate?"

    3. USER OPTIONS:
    - MODIFY: 
    1. Ask "Do you need any changes to the design notes?"
    2. If no changes needed: Get user confirmation, then call create_design_notes() to update
    3. If changes needed: Collect modifications, show preview, get confirmation, then call create_design_notes() to update
    - REGENERATE: 
    1. Generate the design notes using generate_design_notes_preview()
    2. Show preview to user
    3. Get user confirmation
    4. If confirmed: Call create_design_notes() to save the regenerated design notes
    - CANCEL: End workflow

    4. IF NO NOTES EXIST:
    - Inform user no design notes found
    - Ask: "Create comprehensive design notes for this rule?"
    - If yes: Generate the design notes using generate_design_notes_preview()
    - Show preview to user
    - Get user confirmation
    - If confirmed: Call create_design_notes() to generate

    KEY RULES:
    - MUST follow this workflow explicitly step by step
    - Always check for existing notes first whenever user asks about design notes (create or view)
    - ALWAYS get user confirmation before calling create_design_notes()
    - If any updates needed, explicitly call create_design_notes() tool to save changes
    - Present notes in Python notebook format
    - Use create_design_notes() for creation and updates

    Args:
        rule_name: Name of the rule

    Returns:
        Dict with success status, rule name, design notes content, and error details
    """

    try:
        headers = wsutils.create_header()
        payload = {
            "ruleName": rule_name,
            "type": "mcp"
        }
        design_notes_resp = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_DESIGN_NOTES),
            data=json.dumps(payload),
            header=headers
        )

        filename = design_notes_resp.get("fileName")
        design_notes_content = design_notes_resp.get("designNotesContent")
       

        if isinstance(design_notes_content,str) and design_notes_content!="":
            return {
                "success": True,
                "rule_name": rule_name,
                "filename": filename,
                "designNotesContent": rule.decode_content(design_notes_content),
                "message": f"Design notes successfully retrieved for rule {rule_name}. Displaying content to user."
            }
        else:
            return{
                "success": False,
                "rule_name": rule_name,
                "message": f"Design notes not found for rule {rule_name}. Offer to create comprehensive design notes."
            }
        
    except Exception as e:
        return {
            "success": False,
            "rule_name": rule_name,
            "message": f"Error fetching design notes for rule {rule_name}: {e}."
        }


@mcp.tool()
def generate_rule_readme_preview(rule_name: str) -> Dict[str, Any]:
    """
    Generate README.md preview for rule documentation before actual creation.

    RULE README GENERATION:

    This tool generates a complete README.md structure as a string for user review.
    The MCP will create comprehensive rule documentation with detailed sections based on 
    rule context and metadata, then return it for user confirmation.

    README TEMPLATE STRUCTURE REQUIREMENTS:

    The MCP should generate a README.md with exactly these sections:

    ## SECTION 1: Rule Header
    DESCRIPTION: Rule identification and overview
    CONTENT REQUIREMENTS:
    - Rule name as main title (# {RULE_NAME})
    - Brief description from rule metadata
    - Status badges (Version, Application Type, Environment)
    - Purpose statement
    - Last updated timestamp
    FORMAT: Markdown header with badges and overview

    ## SECTION 2: Overview
    DESCRIPTION: High-level rule explanation
    CONTENT REQUIREMENTS:
    - What this rule does (purpose and description)
    - Target system/application
    - Compliance framework alignment
    - Key benefits and use cases
    - When to use this rule
    FORMAT: Markdown sections with bullet points

    ## SECTION 3: Rule Architecture
    DESCRIPTION: Technical architecture and flow
    CONTENT REQUIREMENTS:
    - Rule flow diagram (text-based)
    - Task sequence and dependencies
    - Data flow: Input → Processing → Output
    - Integration points
    - Architecture decisions
    FORMAT: Markdown with code blocks for diagrams

    ## SECTION 4: Inputs
    DESCRIPTION: Detailed input specifications
    CONTENT REQUIREMENTS:
    - Table of all rule inputs with:
      * Input Name
      * Data Type  
      * Required/Optional
      * Description
      * Default Value
      * Example Value
    - Input validation rules
    - File format specifications (for FILE inputs)
    FORMAT: Markdown table with detailed explanations

    ## SECTION 5: Tasks
    DESCRIPTION: Individual task breakdown
    CONTENT REQUIREMENTS:
    - For each task in the rule:
      * Task name and alias
      * Purpose and functionality
      * Input requirements
      * Output specifications
      * Processing logic overview
      * Error handling
    - Task execution order
    - Dependencies between tasks
    FORMAT: Markdown subsections for each task

    ## SECTION 6: Outputs
    DESCRIPTION: Rule output specifications
    CONTENT REQUIREMENTS:
    - Table of all rule outputs with:
      * Output Name
      * Data Type
      * Description
      * Format/Structure
      * Example Value
    - Output file formats and schemas
    - Success/failure indicators
    FORMAT: Markdown table with examples

    ## SECTION 7: Configuration
    DESCRIPTION: Rule configuration and setup
    CONTENT REQUIREMENTS:
    - Application type and environment settings
    - Execution level and mode
    - Required permissions and access
    - System prerequisites
    - Configuration examples
    - Environment-specific settings
    FORMAT: Markdown with code blocks

    ## SECTION 8: Usage Examples
    DESCRIPTION: Practical usage scenarios
    CONTENT REQUIREMENTS:
    - Basic usage example
    - Advanced configuration example
    - Common use cases
    - Best practices
    - Troubleshooting tips
    FORMAT: Markdown with code examples

    ## SECTION 9: I/O Mapping
    DESCRIPTION: Data flow mapping details
    CONTENT REQUIREMENTS:
    - Complete I/O mapping visualization
    - Rule input to task input mappings
    - Task output to task input mappings  
    - Task output to rule output mappings
    - Data transformation explanations
    FORMAT: Markdown with formatted mapping table

    ## SECTION 10: Troubleshooting
    DESCRIPTION: Common issues and solutions
    CONTENT REQUIREMENTS:
    - Common error scenarios
    - Input validation failures
    - Task execution errors
    - Output generation issues
    - Performance considerations
    - Support and contact information
    FORMAT: Markdown FAQ-style sections

    ## SECTION 11: Version History
    DESCRIPTION: Change log and versioning
    CONTENT REQUIREMENTS:
    - Current version information
    - Version history table
    - Change descriptions
    - Migration notes
    - Deprecation warnings
    FORMAT: Markdown table with version details

    ## SECTION 12: References
    DESCRIPTION: Additional resources and links
    CONTENT REQUIREMENTS:
    - Related documentation links
    - Compliance framework references
    - API documentation
    - Support resources
    - Contributing guidelines
    FORMAT: Markdown bullet list with links

    MARKDOWN FORMATTING REQUIREMENTS:
    - Use proper Markdown syntax
    - Include table of contents with links
    - Use code blocks for examples
    - Include badges and shields
    - Proper heading hierarchy (H1, H2, H3)
    - Use tables for structured data
    - Include horizontal rules for section separation

    MCP CONTENT POPULATION INSTRUCTIONS:
    The MCP should extract the following information from the rule context:
    - Rule name, purpose, description from rule metadata
    - System name from appType (clean by removing connector suffixes)
    - Task details from spec.tasks array (name, alias, purpose, appTags)
    - Input specifications from spec.inputs object
    - Output specifications from spec.outputsMeta__
    - I/O mappings from spec.ioMap array
    - Environment and execution settings from labels
    - Application type and integration details

    PLACEHOLDER REPLACEMENT RULES:
    - {RULE_NAME} = meta.name
    - {RULE_PURPOSE} = meta.purpose  
    - {RULE_DESCRIPTION} = meta.description
    - {SYSTEM_NAME} = extracted from appType
    - {VERSION} = meta.version or "1.0.0"
    - {ENVIRONMENT} = meta.labels.environment[0]
    - {APP_TYPE} = meta.labels.appType[0]
    - {EXEC_LEVEL} = meta.labels.execlevel[0]
    - {TASK_COUNT} = len(spec.tasks)
    - {INPUT_COUNT} = len(spec.inputs)
    - {OUTPUT_COUNT} = len(spec.outputsMeta__)
    - {TIMESTAMP} = current ISO timestamp

    CONTENT GUIDELINES:
    - Use clear, technical language
    - Include practical examples
    - Provide comprehensive coverage
    - Make it developer-friendly
    - Include troubleshooting help
    - Keep sections well-organized
    - Use consistent formatting

    WORKFLOW:
    1. MCP retrieves rule context using fetch_rule()
    2. MCP extracts metadata and technical details
    3. MCP generates complete README.md content using template above
    4. MCP populates all placeholders with actual rule data
    5. MCP returns complete README content as string for user review
    6. User reviews and confirms the content
    7. If approved, call create_rule_readme() to actually save the README

    Args:
        rule_name: Name of the rule for which to generate README preview

    Returns:
        Dict containing complete README.md content as string for user review
    """
    
    # MCP should directly construct the README based on the instructions above
    # No intermediate API calls needed - MCP has all the template details in the docstring
    # The MCP will use fetch_rule() internally and build the complete README content
    
    return {
        "success": True, 
        "rule_name": rule_name,
        "readme_content": "",  # MCP will populate this with complete README.md content
        "sections_count": 12,
        "estimated_length": "2000-3000 lines",
        "message": f"MCP should construct complete README.md content for rule '{rule_name}' based on the detailed template instructions above",
        "next_action": "MCP should use fetch_rule() and build complete README markdown content, then return it in readme_content"
    }


@mcp.tool()
def create_rule_readme(rule_name: str, readme_content: str) -> Dict[str, Any]:
    """
    Create and save README.md file after user confirmation.

    README CREATION:

    This tool actually creates and saves the README.md file after the user has reviewed
    and confirmed the preview content from generate_rule_readme_preview().

    WORKFLOW:
    1. User has already reviewed README content from preview
    2. User confirmed the content is acceptable
    3. This tool receives the complete README.md content as string
    4. MCP saves the README file and returns access details

    Args:
        rule_name: Name of the rule for which to create README
        readme_content: Complete README.md content as string

    Returns:
        Dict containing README creation status and access details
    """
    
    try:
        headers = wsutils.create_header()
        payload = {
            "ruleName": rule_name,
            "type":"rule",
            "readmeContent": rule.encode_content(readme_content),  # Pass the complete README content as an encoded string
        }

        save_resp = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_SAVE_RULE_README),
            data=json.dumps(payload),
            header=headers
        )

        message = save_resp.get("message")
        if isinstance(message, str) and message == "Read-me file created successfully.":
            return {
                "success": True,
                "rule_name": rule_name,
                "filename": "README.md",
                "content_length": len(readme_content),
                "sections_saved": readme_content.count("##"),  # Count markdown sections
                "message": f"README.md successfully created and saved for rule '{rule_name}'"
            }
        else:
            return {
                "success": False,
                "error": "Failed to save README.md",
                "rule_name": rule_name
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save README.md: {str(e)}",
            "rule_name": rule_name
        }


@mcp.tool()
def update_rule_readme(rule_name: str, updated_readme_content: str) -> Dict[str, Any]:
    """
    Update existing README.md file with new content.

    README UPDATE:

    This tool updates an existing README.md file with new content. Useful for
    making changes after initial creation or updating documentation as rules evolve.

    Args:
        rule_name: Name of the rule for which to update README
        updated_readme_content: Updated README.md content as string

    Returns:
        Dict containing README update status and details
    """
    
    try:
        headers = wsutils.create_header()
        payload = {
            "ruleName": rule_name,
            "type":"rule",
            "readmeContent": rule.encode_content(updated_readme_content),  # Pass the complete README content as an encoded string
        }
        update_resp = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_SAVE_RULE_README),
            data=json.dumps(payload),
            header=headers
        )

        message = update_resp.get("message")
        if isinstance(message, str) and message == "Read-me file created successfully.":
            return {
                "success": True,
                "rule_name": rule_name,
                "filename": "README.md",
                "content_length": len(updated_readme_content),
                "message": f"README.md successfully updated for rule '{rule_name}'"
            }
        else:
            return {
                "success": False,
                "error": "Failed to update README.md",
                "rule_name": rule_name
            }
                     
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to update README.md: {str(e)}",
            "rule_name": rule_name
        }


@mcp.tool()
def fetch_rule_readme(rule_name: str) -> Dict[str, Any]:
    """
    Fetch and manage design notes for a rule.

    WORKFLOW:

    1. CHECK EXISTING NOTES:
    - Always check if design notes exist for the rule first (whether user wants to create or view)
    - If found: Present complete notebook to user in readable format
    - If not found: Offer to create new ones

    2. IF NOTES EXIST:
    - Show complete notebook with all sections (this serves as the VIEW)
    - Ask: "Here are your design notes. Modify or regenerate?"

    3. USER OPTIONS:
    - MODIFY: 
    1. Ask "Do you need any changes to the design notes?"
    2. If no changes needed: Get user confirmation, then call create_design_notes() to update
    3. If changes needed: Collect modifications, show preview, get confirmation, then call create_design_notes() to update
    - REGENERATE: 
    1. Generate the design notes using generate_design_notes_preview()
    2. Show preview to user
    3. Get user confirmation
    4. If confirmed: Call create_design_notes() to save the regenerated design notes
    - CANCEL: End workflow

    4. IF NO NOTES EXIST:
    - Inform user no design notes found
    - Ask: "Create comprehensive design notes for this rule?"
    - If yes: Generate the design notes using generate_design_notes_preview()
    - Show preview to user
    - Get user confirmation
    - If confirmed: Call create_design_notes() to generate

    KEY RULES:
    - MUST follow this workflow explicitly step by step
    - Always check for existing notes first whenever user asks about design notes (create or view)
    - ALWAYS get user confirmation before calling create_design_notes()
    - If any updates needed, explicitly call create_design_notes() tool to save changes
    - Present notes in Python notebook format
    - Use create_design_notes() for creation and updates

    Args:
        rule_name: Name of the rule

    Returns:
        Dict with success status, rule name, design notes content, and error details
    """ 

    try:
        headers = wsutils.create_header()
        params = {
            "name": rule_name,
            "include_read_me": True
        }
        readme_resp = wsutils.get(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_RULES),
            params=params, 
            header=headers
        )
        
        rule_info = None
        if rule.is_valid_key(readme_resp, "items"):
            rule_info = readme_resp["items"][0]

        if rule_info:
            readme_content = rule_info.get("readmeData")

            if isinstance(readme_content, str) and readme_content != "":
                return {
                    "success": True,
                    "rule_name": rule_name,
                    "readmeContent": rule.decode_content(readme_content),
                    "message": f"README successfully retrieved for rule {rule_name}. Displaying content to user."
                }
            else:
                return {
                    "success": False,
                    "rule_name": rule_name,
                    "message": f"README not found for rule {rule_name}. Offer to create comprehensive README."
                }
        else:
            return {
                "success": False,
                "rule_name": rule_name,
                "message": f"Rule '{rule_name}' not found. Unable to fetch README."
            }
            
    except Exception as e:
        return {
            "success": False,
            "rule_name": rule_name,
            "message": f"Error fetching README for rule {rule_name}: {e}"
        }

@mcp.tool()
def get_rules_summary() -> Dict[str, Any]:
    """
    Tool-based version of `get_rules_summary` for improved compatibility and prevention of duplicate rule creation.

    This tool serves as the initial step in the rule creation process. It helps determine whether the user's proposed use case matches any existing rule in the catalog.

    PURPOSE:
    - To analyze the user's use case and avoid duplicate rule creation by identifying the most suitable existing rule based on its name, description, and purpose.

    WHEN TO USE:
    - As the first step before initiating a new rule creation process
    - When the user wants to retrieve and review all available rules
    - When verifying if a similar rule already exists that can be reused or customized

    WHAT IT DOES:
    - Retrieves the full list of rules from the catalog with simplified metadata (name, purpose, description)
    - Performs intelligent matching using metadata (name, description, purpose) with user-provided use case details
    - Uses semantic pattern recognition to find similar rules, even across different systems (e.g., AzureUserUnusedPermission vs SalesforceUserUnusedPermissions)

    IF A MATCHING RULE IS FOUND:

    - Retrieves complete details via `fetch_rule()`.
    - If the readmeData field is available in the fetch_rule() response, Performs README-based validation using the `readmeData` field from the `fetch_rule()` response to assess its suitability for the user’s use case.
    - If suitable:
    - Returns the rule with full metadata, explanation, and the analysis report.
    - If not suitable:
    - Informs the user that the rule's README content does not align with the intended use case.
    - Prompts the user with clear next-step options:
        - "The rule's README content does not align with your use case. Please choose one of the following options:"
        - Customize the existing rule
        - Evaluate alternative matching rules
        - Proceed with new rule creation
    - Waits for the user's choice before proceeding.
    
    IF A SIMILAR RULE EXISTS FOR AN ALTERNATE TECHNOLOGY STACK:

    - Detects rules with the same logic but built for a different platform or system (e.g., AzureUserUnusedPermission for SalesforceUserUnusedPermissions)
    - If the readmeData field is available in the fetch_rule() response, Retrieves and analyzes the `readmeData` from the `fetch_rule()` response to compare the implementation details against the user's proposed use case
    - Based on the comparison:
        - If the README content matches or is mostly reusable, suggest using the existing rule structure and logic as a foundation to create a new rule tailored to the user's target system
        - If the README content does not match or is not suitable, clearly inform the user and recommend either modifying the logic significantly or proceeding with a completely new rule from scratch

    IF NO SUITABLE RULE IS FOUND:

    - Clearly informs the user that no relevant rule matches the proposed use case
    - Suggests continuing with new rule creation
    - Optionally highlights similar rules that can be used as a reference

    MANDATORY STEPS:

    README VALIDATION:
    - Always retrieve and analyze `readmeData` from `fetch_rule()`.
    - Ensure the rule's logic, behavior, and intended use align with the user's proposed use case.

    README ANALYSIS REPORT:
    - Generate a clear and concise report for each `readmeData` analysis that classifies the result as a full match, partially reusable, or not aligned.
    - Present this report to the user for review.

    USER CONFIRMATION BEFORE PROCEEDING:
    When analyzing a README file:
    - If no relevant rule matches the proposed use case, or if the README is deemed unsuitable, the tool must pause and request explicit user confirmation before proceeding further.
    - The tool should:
    - Clearly inform the user that no matching rule was found or the README is not appropriate.
    - Suggest creating a new rule as the next step.
    - Optionally recommend similar existing rules that can serve as references to help the user craft the new rule.

    ITERATE UNTIL MATCH:
    - Repeat the above steps until a suitable rule is found or all options are exhausted.

    CROSS-PLATFORM RULE HANDLING:
    - For rules from a different stack:
    - If reusable: suggest customization
    - If not reusable: recommend new rule creation

    Returns:
    - A single rule object with full metadata and verified README match — if an exact match is found
    - A similar rule suggestion with customization options — if a cross-system match is found (e.g., AzureUserUnusedPermission vs SalesforceUserUnusedPermissions)
    - A message indicating no suitable rule found — with next steps and guidance to create a new rule
    """

    try:

        rule_response = rule.fetch_rules_api()
        
        if not rule_response:
            return {"error": f"No rule found that matches the specified requirements."}

        return rule_response

    except Exception as e:
        return {
            "error": f"An error occurred while retrieving the rule with the specified details: {e}"
        }

@mcp.tool()
def get_applications_for_tag(tag_name: str) -> Dict[str, Any]:
    """
    Get available applications for a specific app tag.

    APPLICATION RETRIEVAL:
    - Fetches all existing applications configured for the specified app tag
    - Returns list of applications with ID, name, and app type
    - Used during rule execution to present application choices to user

    Args:
        tag_name: The app tag name to get applications for

    Returns:
        Dict containing available applications for the tag
    """
    try:
        header = wsutils.create_header()

        params = {
            "app_type_tag": tag_name,
            "fields": "basic",
            "validated": True
        }

        applications = []

        applications_resp = wsutils.get(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_CREDENTIAL), 
            params=params, 
            header=header
        )

        if rule.is_valid_array(applications_resp, "items"):
            for item in applications_resp["items"]:
                applications.append({"id": item.get("id"), "name": item.get("credentialName"), "appType": item.get("appType")})
            return {
                "success": True, 
                "tag_name": tag_name, 
                "applications": applications, 
                "count": len(applications), 
                "message": f"Found {len(applications)} applications for tag '{tag_name}'. User can select an existing application or create new credentials."
            }    
        else:
            return {
                "success": False,
                "tag_name": tag_name,
                "applications": [],
                "count": 0,
                "message": f"No applications found for tag '{tag_name}'. User can create new credentials."
            }

    except Exception as e:
        return {
            "success": False, 
            "tag_name": tag_name,
            "applications": [],
            "count": 0,
            "message": f"Error occurred while fetching applications for tag '{tag_name}': {e}"
        }


@mcp.tool()
def get_application_info(tag_name: str) -> Dict[str, Any]:
    """
    Get detailed information about an application, including supported credential types.

    APPLICATION CREDENTIAL CONFIGURATION WORKFLOW:

    1. User selects "Configure new application credentials".
    2. Call this tool to retrieve application details and supported credential types.
    3. Present credential options to the user with:
       - Required attributes
       - Data type
       - If type is bytes → must be Base64-encoded
    4. Collect credential values for the selected type.
    5. Validate that all required attributes are provided.
    6. Verify that each credential value matches its expected data type.
    7. Build the credential configuration and append it to the `apps_config` array.

    DATA VALIDATION REQUIREMENTS:
    - All required attributes must be present.
    - Data type must match specification.
    - Bytes values must be Base64-encoded before saving.

    Args:
        tag_name: The app tag name for retrieving application information

    Returns:
        Dict containing application details and supported credential types
    """
    try:
        header = wsutils.create_header()

        params = {"appType": tag_name}

        app_resp = wsutils.get(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_APPLICATION_CREDENTIALS), 
            params=params, 
            header=header
        )

        if rule.is_valid_array(app_resp, "items"):
            app_info = app_resp["items"][0]
            supported_creds = app_info.get("supportedCreds")
            return {
                "success": True, 
                "app_name": tag_name,
                "supportedCreds": supported_creds,
                "message": f"Retrieved information for application '{tag_name}'. User can select credential type and provide values."
            }
        else:
            return {
                "success": False, 
                "app_name": tag_name,
                "message": f"No credential information found for application '{tag_name}'."
            }

    except Exception as e:
        return {
            "success": False, 
            "app_name": tag_name,
            "message": f"Error occurred while fetching application info for '{tag_name}': {e}"
        }


@mcp.tool()
def execute_rule(rule_name: str, rule_inputs: List[Dict[str, Any]], applications: List[Dict[str, Any]]) -> Dict[str, Any]:
    """RULE EXECUTION WORKFLOW:

    PREREQUISITE STEPS:
    1. User chooses to execute rule after creation
    2. Extract unique appTags from selected tasks → get user confirmation
    3. For each tag:
        - Get available applications via get_applications_for_tag()
        - Present choice: existing app or new credentials → get user confirmation
        - If existing: use application ID → confirm → move to next tag
        ```json
        [
            {
                "applicationType": "[appType (split by :: and use the first value)]",
                "applicationId": "[Actual ID]",
                "appTags": "[Complete object from rule spec.tasks.appTags]"
            }
        ]
        ```
        - If new: get_application_info(tag_name) → collect credentials + get application URL from user (optional) → confirm → move to next tag
        ```json
        [
            {
                "applicationType": "[appType (split by :: and use the first value)]",
                "appURL": "[Application URL from user (optional)]",
                "credentialType": "[User chosen credential type]",
                "credentialValues": {
                    "[User provided credentials]"
                },
                "appTags": "[Complete object from rule spec.tasks.appTags]"
            }
        ]
        ```
    4. Build applications array → get user confirmation
    5. Final confirmation → execute rule
    6. If execution starts successfully → call fetch_execution_progress()

    Args:
        rule_name: Rule to execute
        rule_inputs: Complete objects from spec.inputsMeta__
        applications: Application configurations with credentials

    Returns:
        Dict with execution results
    """
    try:
        # Prepare execution payload
        execution_payload = {
            "ruleName": rule_name, 
            "ruleInputs": rule_inputs, 
            "applications": applications
        }

        headers = wsutils.create_header()
    
        execution_result = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_EXECUTE_RULE), 
            data=json.dumps(execution_payload), 
            header=headers
        )

        return {
            "success": True, 
            "rule_name": rule_name, 
            "execution_id": execution_result.get("id"), 
            "message": f"Rule '{rule_name}' started executing.",
        }

    except Exception as e:
        return {
            "success": False, 
            "rule_name": rule_name,
            "message": f"Failed to execute rule '{rule_name}': {e}"
        }


@mcp.tool()
def fetch_execution_progress(rule_name: str, execution_id: str) -> Dict[str, Any]:
    """
    Fetch execution progress and status for a running rule.

    LIVE PROGRESS DISPLAY:
    Show each task in one line as it runs:
    fetch_azure_users (ExecuteHttpRequestV2) ████████████████████ 100% COMPLETED

    MANDATORY PROGRESS BAR COLORS:
    - COMPLETED = Blue bars (REQUIRED)
    - INPROGRESS = Green bars (REQUIRED)
    - ERROR = Red bars (REQUIRED)
    - NEVER use black bars (CRITICAL)

    POLLING:
    - Call every 2 seconds
    - Show live progress as tasks run
    - Final call: Show summary

    EXECUTION SUMMARY:
    **Rule:** [rule_name]
    **Execution ID:** [execution_id]
    **Status:** [status] 
    **Tasks:** [completed]/[total] done
    **Duration:** [time]

    Output: [show outputs]

    CRITICAL:
    - One line per task
    - Color bars by task status
    - Show live, not at end

    Args:
        rule_name: Rule being executed
        execution_id: ID from execute_rule()
        
    Returns:
        Dict containing execution status, progress summary, progress bar data
    """    
    try:
        header = wsutils.create_header()

        exec_payload = {
            "executionID": execution_id
        }

        exec_progress_resp = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_EXECUTION_PROGRESS), 
            data=json.dumps(exec_payload), 
            header=header
        )
        
        task_progress = exec_progress_resp.get("taskProgressSummary", {})
        progress_percentage = task_progress.get("progressPercentage", 0)
        completed = task_progress.get("completed", 0)
        total = task_progress.get("total", 0)
        progress_array = exec_progress_resp.get("progress", [])
        outputs = exec_progress_resp.get("outputs", [])

        if (exec_progress_resp.get("status") == "COMPLETED"):
            return {
                "status": "COMPLETED",
                "rule_name": rule_name,
                "execution_id": execution_id,
                "progress_percentage": progress_percentage,
                "completed_tasks": completed,
                "total_tasks": total,
                "progress": progress_array,
                "show_progress_bar": True,
                "outputs": outputs,
                "message": f"Rule '{rule_name}' execution completed successfully."
            }
        elif (exec_progress_resp.get("status") == "ERROR"):
            return {
                "status": "ERROR",
                "rule_name": rule_name,
                "execution_id": execution_id,
                "progress_percentage": progress_percentage,
                "completed_tasks": completed,
                "total_tasks": total,
                "progress": progress_array,
                "show_progress_bar": True,
                "message": f"Rule '{rule_name}' execution completed with error."
            }
        else:
            return {
                "status": exec_progress_resp.get("status"),
                "rule_name": rule_name,
                "execution_id": execution_id,
                "progress_percentage": progress_percentage,
                "completed_tasks": completed,
                "total_tasks": total,
                "progress": progress_array,
                "show_progress_bar": True,
                "message": f"Rule '{rule_name}' execution in progress. {completed}/{total} tasks completed ({progress_percentage}%)."
            }

    except Exception as e:
        return {
            "status": "ERROR",
            "rule_name": rule_name,
            "execution_id": execution_id,
            "progress_percentage": 0,
            "completed_tasks": 0,
            "total_tasks": 0,
            "progress": [],
            "show_progress_bar": False,
            "message": f"Error occurred while fetching execution progress for rule '{rule_name}': {e}"
        }