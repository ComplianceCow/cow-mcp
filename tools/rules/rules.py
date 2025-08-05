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
            "next_action": "Call create_design_notes(rule_name) to generate and save design notes"
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
            "next_step": "Call create_design_notes() to auto-generate comprehensive design notes"
        }
    except exception.CCowExceptionVO as e:
        return {"success": False, "error": f"Failed to create rule: {e.to_dict()}"}
    except Exception as e:
        return {"success": False, "error": f"Failed to create rule: {e}"}
    

# Replace the existing design notes related methods in the TwoPhaseRuleMCP class with these updated versions:

# @mcp.tool()
# def create_design_notes(rule_name: str) -> Dict[str, Any]:
#     """Generate and save design notes for the created rule using MCP's internal template system.

#     DESIGN NOTES AUTOMATIC GENERATION:

#     This tool triggers the MCP's internal design notes generation system to automatically
#     create comprehensive design notes after rule creation. The MCP will generate a
#     Jupyter notebook with 8 standardized sections based on rule context and metadata.

#     DESIGN NOTES TEMPLATE STRUCTURE REQUIREMENTS:

#     The MCP should generate a Jupyter notebook (.ipynb format) with exactly 8 sections:

#     ## SECTION 1: Evidence Details
#     DESCRIPTION: System identification and rule purpose documentation
#     CONTENT REQUIREMENTS:
#     - Table with columns: System | Source of data | Frameworks | Purpose
#     - System: Extract from rule's appType (remove 'appconnector'/'connector' suffix)
#     - Source: Always 'compliancecow'
#     - Frameworks: Default to '-' (can be customized later)
#     - Purpose: Use rule's purpose from metadata
#     - RecommendedEvidenceName: Use rule name
#     - Description: Use rule description from metadata
#     - Reference: Placeholder for documentation links
#     FORMAT: Markdown cell with table and code blocks

#     ## SECTION 2: Extended Data Schema
#     DESCRIPTION: System-specific raw data structure definition
#     CONTENT REQUIREMENTS:
#     - Header explaining configuration parameters and default values
#     - Configuration overview with task count and input count from rule structure
#     - Code cell with system-specific raw data structure placeholder
#     - Include comments indicating this should be populated with actual API response format
#     - Use generic JSON structure with system name in resource identifiers
#     FORMAT: Markdown header cell + Code cell with JSON structure

#     ## SECTION 3: Standard Schema
#     DESCRIPTION: Standardized compliance data format
#     CONTENT REQUIREMENTS:
#     - Header explaining standard schema purpose
#     - Code cell with standardized JSON structure containing:
#       * Meta: System name and source
#       * Resource info: ID, name, type, location, tags, URL
#       * Data: Rule-specific configuration fields (use generic placeholders)
#       * Compliance details: ValidationStatusCode, ComplianceStatus, etc.
#       * User/Action editable fields
#     FORMAT: Markdown header cell + Code cell with JSON structure

#     ## SECTION 4: Sample Data
#     DESCRIPTION: Example records in tabular format
#     CONTENT REQUIREMENTS:
#     - Markdown table showing sample compliance records
#     - Columns should match standard schema fields
#     - Include at least one example row with realistic sample data
#     - Use system name in resource identifiers
#     FORMAT: Markdown cell with table

#     ## SECTION 5: Compliance Taxonomy
#     DESCRIPTION: Status codes and compliance definitions
#     CONTENT REQUIREMENTS:
#     - Table with columns: ValidationStatusCode | ValidationStatusNotes | ComplianceStatus | ComplianceStatusReason
#     - Standard status codes: COMPLIANT_STATUS, NON_COMPLIANT_STATUS, etc.
#     - Generic compliance reasons suitable for most rule types
#     FORMAT: Markdown cell with table

#     ## SECTION 6: Compliance Calculation
#     DESCRIPTION: Percentage calculations and status logic
#     CONTENT REQUIREMENTS:
#     - Header explaining compliance calculation methodology
#     - Code cell with calculation logic:
#       * TotalCount = Count of 'COMPLIANT' and 'NON_COMPLIANT' records
#       * CompliantCount = Count of 'COMPLIANT' records
#       * CompliancePCT = (CompliantCount / TotalCount) * 100
#       * Status determination rules
#     FORMAT: Markdown header cell + Code cell with calculation logic

#     ## SECTION 7: Remediation Steps
#     DESCRIPTION: Non-compliance remediation procedures
#     CONTENT REQUIREMENTS:
#     - Generic remediation workflow applicable to most systems
#     - Structured approach: Immediate Actions, Short-term Remediation, Long-term Monitoring
#     - Include timeframes and responsibilities
#     - System-agnostic guidance that can be customized
#     FORMAT: Markdown cell with structured remediation steps

#     ## SECTION 8: Control Setup Details
#     DESCRIPTION: Rule configuration and implementation details
#     CONTENT REQUIREMENTS:
#     - Table with control details:
#       * RuleName: Use actual rule name
#       * PreRequisiteRuleNames: Default to 'N/A'
#       * ExtendedSchemaRuleNames: Default to 'N/A'
#       * ApplicationClassName: System name + 'appconnector'
#       * PostSynthesizerName: Default to 'N/A'
#       * TaskCount: Actual count from rule structure
#       * InputCount: Actual count from rule structure
#       * ExecutionMode: Default to 'automated'
#       * EvaluationFrequency: Default to 'daily'
#     FORMAT: Markdown cell with table

#     JUPYTER NOTEBOOK METADATA REQUIREMENTS:
#     - Include proper notebook metadata (colab, kernelspec, language_info)
#     - Set nbformat: 4, nbformat_minor: 0
#     - Use appropriate cell metadata with unique IDs for each section
#     - Ensure proper markdown and code cell formatting

#     MCP CONTENT POPULATION INSTRUCTIONS:
#     The MCP should extract the following information from the rule context:
#     - Rule name, purpose, description from rule metadata
#     - System name from appType (clean by removing connector suffixes)
#     - Task count from spec.tasks array length
#     - Input count from spec.inputs object keys count
#     - Application connector name for control setup

#     PLACEHOLDER CONTENT GUIDELINES:
#     - Use generic, realistic examples that can be customized later
#     - Include comments in code sections indicating customization points
#     - Provide system-agnostic content that applies broadly
#     - Use consistent naming conventions throughout all sections

#     WORKFLOW:
#     1. MCP retrieves rule context from stored rule information
#     2. MCP generates complete Jupyter notebook using template structure above
#     3. MCP populates template with extracted rule metadata and calculated values
#     4. MCP saves design notes and returns confirmation with notebook details

#     Args:
#         rule_name: Name of the rule to create design notes for

#     Returns:
#         Dict containing design notes creation status and notebook info with:
#         - success: Boolean indicating creation success
#         - rule_name: Name of the rule
#         - design_notes_id: Generated design notes identifier
#         - notebook_url: URL to access the saved notebook
#         - sections_count: Number of sections created (should be 8)
#         - message: Success/error message
#         - timestamp: Creation timestamp
#         - notebook_format: Always 'jupyter'
#         - template_version: Template version used
#         - generation_method: Always 'MCP_AUTOMATIC'
#     """
#     try:
#         # Retrieve rule context
#         rule_context=rule.fetch_rule(rule_name=rule_name)
#         if not rule_context:
#             return {"success": False, "error": f"Rule context not found for '{rule_name}'. Cannot generate design notes."}

#         # Trigger MCP's internal design notes generation using the detailed template requirements above
#         # The MCP should use the rule context and template structure to generate the complete notebook
#         design_notes_content = _trigger_mcp_design_notes_generation(rule_name, rule_context)

#         # Save design notes using the MCP-generated content
#         # save_result = _save_design_notes_api(rule_name, design_notes_content)

#         return {
#             "success": True,
#             "rule_name": rule_name,
#             # "design_notes_id": save_result.get("design_notes_id"),
#             # "notebook_url": save_result.get("notebook_url"),
#             "sections_count": 8,  # Always 8 sections as per template requirements
#             "message": f"Design notes created and saved successfully for rule '{rule_name}' using MCP internal generation",
#             # "timestamp": save_result.get("timestamp"),
#             "notebook_format": "jupyter",
#             "template_version": "mcp_template_v1.0",
#             "generation_method": "MCP_AUTOMATIC"
#         }

#     except Exception as e:
#         return {"success": False, "error": f"Failed to create design notes for '{rule_name}': {str(e)}"}

def _trigger_mcp_design_notes_generation(self, rule_name: str, rule_structure: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger MCP's internal design notes generation system.
    
    This method should interface with the MCP's actual design notes generation system.
    For now, it returns a basic structure that the MCP can replace with its own implementation.
    
    The MCP should use the detailed template requirements from the create_design_notes tool
    to generate a complete Jupyter notebook with all 8 sections properly populated.
    """
    
    # This is a placeholder that the MCP should replace with its actual generation logic
    # The MCP should use the template structure and requirements defined in the tool above
        
    # Extract basic information for MCP to use
    rule_meta:dict = rule_structure.get("meta", {})
    rule_spec:dict = rule_structure.get("spec", {})
    
    extraction_info = {
        "rule_name": rule_meta.get("name", rule_name),
        "rule_purpose": rule_meta.get("purpose", "Compliance rule for automated evaluation"),
        "rule_description": rule_meta.get("description", "Generated compliance rule"),
        "system_name": _extract_system_name_for_mcp(rule_structure),
        "task_count": len(rule_spec.get("tasks", [])),
        "input_count": len(rule_spec.get("inputs", {}))
    }
    
    # The MCP should replace this with its actual notebook generation
    # This is just a minimal structure to show the expected format
    placeholder_notebook = {
        "cells": [],  # MCP should populate with 8 sections as per template requirements
        "metadata": {
            "colab": {"provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"}
        },
        "nbformat": 4,
        "nbformat_minor": 0
    }
    
    return placeholder_notebook

def _extract_system_name_for_mcp(rule_structure: Dict[str, Any]) -> str:
    """Extract clean system name for MCP to use in template generation."""
    
    meta:dict = rule_structure.get("meta", {})
    labels:dict = meta.get("labels", {})
    
    # Get primary app type
    app_types = labels.get("appType", ["generic"])
    primary_app_type = app_types[0] if app_types else "generic"
    
    # Clean system name by removing connector suffixes
    system_name = primary_app_type.lower().replace("appconnector", "").replace("connector", "")
    
    # If still generic, try to get from tasks
    if system_name == "generic":
        tasks = rule_structure.get("spec", {}).get("tasks", [])
        if tasks:
            task_app_tags = tasks[0].get("appTags", {}).get("appType", [])
            if task_app_tags:
                system_name = task_app_tags[0].lower().replace("appconnector", "").replace("connector", "")
    
    return system_name if system_name != "generic" else "system"

@mcp.tool()
def generate_design_notes_preview(rule_name: str) -> Dict[str, Any]:
    """
    Generate design notes preview for user confirmation before actual creation.

    DESIGN NOTES PREVIEW GENERATION:

    This tool generates a complete Jupyter notebook structure as a dictionary for user review.
    The MCP will create the full notebook content with 8 standardized sections based on 
    rule context and metadata, then return it for user confirmation.

    DESIGN NOTES TEMPLATE STRUCTURE REQUIREMENTS:

    The MCP should generate a Jupyter notebook (.ipynb format) with exactly 8 sections:

    ## SECTION 1: Evidence Details
    DESCRIPTION: System identification and rule purpose documentation
    CONTENT REQUIREMENTS:
    - Table with columns: System | Source of data | Frameworks | Purpose
    - System: Extract from rule's appType (remove 'appconnector'/'connector' suffix)
    - Source: Always 'compliancecow'
    - Frameworks: Default to '-' (can be customized later)
    - Purpose: Use rule's purpose from metadata
    - RecommendedEvidenceName: Use rule name
    - Description: Use rule description from metadata
    - Reference: Placeholder for documentation links
    FORMAT: Markdown cell with table and code blocks

    ## SECTION 2: Extended Data Schema
    DESCRIPTION: System-specific raw data structure definition
    CONTENT REQUIREMENTS:
    - Header explaining configuration parameters and default values
    - Configuration overview with task count and input count from rule structure
    - Code cell with system-specific raw data structure placeholder
    - Include comments indicating this should be populated with actual API response format
    - Use generic JSON structure with system name in resource identifiers
    FORMAT: Markdown header cell + Code cell with JSON structure

    ## SECTION 3: Standard Schema
    DESCRIPTION: Standardized compliance data format
    CONTENT REQUIREMENTS:
    - Header explaining standard schema purpose
    - Code cell with standardized JSON structure containing:
      * Meta: System name and source
      * Resource info: ID, name, type, location, tags, URL
      * Data: Rule-specific configuration fields (use generic placeholders)
      * Compliance details: ValidationStatusCode, ComplianceStatus, etc.
      * User/Action editable fields
    FORMAT: Markdown header cell + Code cell with JSON structure

    ## SECTION 4: Sample Data
    DESCRIPTION: Example records in tabular format
    CONTENT REQUIREMENTS:
    - Markdown table showing sample compliance records
    - Columns should match standard schema fields
    - Include at least one example row with realistic sample data
    - Use system name in resource identifiers
    FORMAT: Markdown cell with table

    ## SECTION 5: Compliance Taxonomy
    DESCRIPTION: Status codes and compliance definitions
    CONTENT REQUIREMENTS:
    - Table with columns: ValidationStatusCode | ValidationStatusNotes | ComplianceStatus | ComplianceStatusReason
    - Standard status codes: COMPLIANT_STATUS, NON_COMPLIANT_STATUS, etc.
    - Generic compliance reasons suitable for most rule types
    FORMAT: Markdown cell with table

    ## SECTION 6: Compliance Calculation
    DESCRIPTION: Percentage calculations and status logic
    CONTENT REQUIREMENTS:
    - Header explaining compliance calculation methodology
    - Code cell with calculation logic:
      * TotalCount = Count of 'COMPLIANT' and 'NON_COMPLIANT' records
      * CompliantCount = Count of 'COMPLIANT' records
      * CompliancePCT = (CompliantCount / TotalCount) * 100
      * Status determination rules
    FORMAT: Markdown header cell + Code cell with calculation logic

    ## SECTION 7: Remediation Steps
    DESCRIPTION: Non-compliance remediation procedures
    CONTENT REQUIREMENTS:
    - Generic remediation workflow applicable to most systems
    - Structured approach: Immediate Actions, Short-term Remediation, Long-term Monitoring
    - Include timeframes and responsibilities
    - System-agnostic guidance that can be customized
    FORMAT: Markdown cell with structured remediation steps

    ## SECTION 8: Control Setup Details
    DESCRIPTION: Rule configuration and implementation details
    CONTENT REQUIREMENTS:
    - Table with control details:
      * RuleName: Use actual rule name
      * PreRequisiteRuleNames: Default to 'N/A'
      * ExtendedSchemaRuleNames: Default to 'N/A'
      * ApplicationClassName: System name + 'appconnector'
      * PostSynthesizerName: Default to 'N/A'
      * TaskCount: Actual count from rule structure
      * InputCount: Actual count from rule structure
      * ExecutionMode: Default to 'automated'
      * EvaluationFrequency: Default to 'daily'
    FORMAT: Markdown cell with table

    JUPYTER NOTEBOOK METADATA REQUIREMENTS:
    - Include proper notebook metadata (colab, kernelspec, language_info)
    - Set nbformat: 4, nbformat_minor: 0
    - Use appropriate cell metadata with unique IDs for each section
    - Ensure proper markdown and code cell formatting

    MCP CONTENT POPULATION INSTRUCTIONS:
    The MCP should extract the following information from the rule context:
    - Rule name, purpose, description from rule metadata
    - System name from appType (clean by removing connector suffixes)
    - Task count from spec.tasks array length
    - Input count from spec.inputs object keys count
    - Application connector name for control setup

    PLACEHOLDER CONTENT GUIDELINES:
    - Use generic, realistic examples that can be customized later
    - Include comments in code sections indicating customization points
    - Provide system-agnostic content that applies broadly
    - Use consistent naming conventions throughout all sections

    WORKFLOW:
    1. MCP retrieves rule context from stored rule information
    2. MCP generates complete Jupyter notebook using template structure above
    3. MCP populates template with extracted rule metadata and calculated values
    4. MCP returns complete notebook structure as dictionary for user review
    5. User reviews and confirms the structure
    6. If approved, call create_design_notes() to actually save the notebook

    Args:
        rule_name: Name of the rule for which to generate design notes preview

    Returns:
        Dict containing complete notebook structure for user review and confirmation
    """
    
    try:
        # Call MCP to generate notebook structure (preview mode)
        headers = wsutils.create_header()
        payload = {
            "ruleName": rule_name,
            "templateVersion": "v1.0",
            "generateNotebook": True,
            "sectionsRequired": 8,
            "previewMode": True,  # Key difference - just generate, don't save
            "returnNotebookStructure": True
        }
        
        # preview_resp = wsutils.post(
        #     path=wsutils.build_api_url(endpoint=constants.URL_GENERATE_DESIGN_NOTES_PREVIEW),
        #     data=json.dumps(payload),
        #     header=headers
        # )

        preview_resp = {
            "notebookStructure":{
                "cells":[]
            }
        }
        
        # Validate response and return notebook structure
        if rule.is_valid_key(preview_resp, "notebookStructure"):
            return {
                "success": True,
                "rule_name": rule_name,
                "notebook_structure": preview_resp["notebookStructure"],  # Complete notebook as dict
                "sections_count": len(preview_resp["notebookStructure"].get("cells", [])),
                "metadata": preview_resp.get("extractedMetadata", {}),
                "preview_mode": True,
                "message": f"Design notes preview generated for rule '{rule_name}'. Review the structure and confirm to proceed.",
                "confirmation_required": True,
                "next_action": "Show notebook structure to user for confirmation, then call create_design_notes() if approved"
            }
        
        elif rule.is_valid_key(preview_resp, "error"):
            return {
                "success": False,
                "error": f"MCP design notes preview generation failed: {preview_resp['error']}",
                "rule_name": rule_name
            }
        
        else:
            return {
                "success": False,
                "error": "Invalid response from MCP design notes preview generator",
                "response_keys": list(preview_resp.keys()) if preview_resp else [],
                "rule_name": rule_name
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to generate design notes preview for rule '{rule_name}': {str(e)}",
            "rule_name": rule_name
        }


@mcp.tool()
def create_design_notes(rule_name: str) -> Dict[str, Any]:
    """
    Create and save design notes after user confirmation.

    DESIGN NOTES CREATION:

    This tool actually creates and saves the design notes after the user has reviewed
    and confirmed the preview structure from generate_design_notes_preview().

    WORKFLOW:
    1. User has already reviewed notebook structure from preview
    2. User confirmed the structure is acceptable
    3. This tool triggers the actual creation and saving
    4. MCP saves the notebook and returns access details

    Args:
        rule_name: Name of the rule for which to create design notes

    Returns:
        Dict containing design notes creation status and access details
    """
    
    try:
        # Call MCP to actually create and save the design notes
        headers = wsutils.create_header()
        payload = {
            "ruleName": rule_name,
            "templateVersion": "v1.0",
            "generateNotebook": True,
            "sectionsRequired": 8,
            "previewMode": False,  # Key difference - actually save this time
            "saveToStorage": True
        }
        
        # create_resp = wsutils.post(
        #     path=wsutils.build_api_url(endpoint=constants.URL_CREATE_DESIGN_NOTES),
        #     data=json.dumps(payload),
        #     header=headers
        # )

        create_resp = {
            "notebookURL":"http://localhost:9000/mcp/{rule_name}.ipynp"
        }
        
        # Validate response and return results
        if rule.is_valid_key(create_resp, "notebookURL"):
            return {
                "success": True,
                "rule_name": rule_name,
                "notebook_url": create_resp["notebookURL"],
                "notebook_id": create_resp.get("notebookId"),
                "filename": create_resp.get("filename", f"{rule_name}_design_notes.ipynb"),
                "sections_generated": create_resp.get("sectionsGenerated", 8),
                "creation_mode": "confirmed",
                "template_version": "v1.0",
                "message": f"Design notes successfully created and saved for rule '{rule_name}'",
                "access_info": {
                    "notebook_url": create_resp["notebookURL"],
                    "downloadable": create_resp.get("downloadable", True),
                    "editable": create_resp.get("editable", True)
                }
            }
        
        elif rule.is_valid_key(create_resp, "error"):
            return {
                "success": False,
                "error": f"MCP design notes creation failed: {create_resp['error']}",
                "rule_name": rule_name
            }
        
        else:
            return {
                "success": False,
                "error": "Invalid response from MCP design notes creator",
                "response_keys": list(create_resp.keys()) if create_resp else [],
                "rule_name": rule_name
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create design notes for rule '{rule_name}': {str(e)}",
            "rule_name": rule_name
        }

