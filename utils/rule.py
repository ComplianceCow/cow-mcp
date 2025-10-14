import base64
import json
import re
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any, Dict, List, Union
import pandas as pd
import csv
import re

import toml
from ruamel.yaml import YAML

from constants import constants
import mcptypes.rule_type as vo
from utils import rule,wsutils
from utils.debug import logger


yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.preserve_quotes = True


def is_valid_key(element, key, array_check: bool = False):
    if not element or not key or key not in element:
        return False
    value = element[key]
    if ((isinstance(value, int) and value >= 0) or value):
        if array_check:
            if (isinstance(value, list) or isinstance(value, set) or isinstance(value, tuple) and len(value) > 0):
                return True
            else:
                return False
        return True

    return False

def is_valid_array(ele, key):
    return is_valid_key(ele, key, array_check=True)


def decode_content(content: str) -> str:
    """Decode base64 content"""
    try:
        if content:
            return base64.b64decode(content).decode("utf-8")
        return ""
    except Exception:
        return ""


def extract_capabilities_from_readme(readme_content: str) -> List[str]:
    """Extract capabilities from README content"""
    if not readme_content:
        return []

    capabilities = []
    readme_lower = readme_content.lower()

    # Look for action words and capabilities
    capability_indicators = ["validate", "transform", "check", "process", "generate", "filter", "convert", "analyze", "compare", "merge", "split", "join",
                             "aggregate", "calculate", "format", "parse", "extract", "match", "classify", "sort", "group", "report", "summarize", "notify", "send", "receive"]

    for indicator in capability_indicators:
        if indicator in readme_lower:
            capabilities.append(indicator)

    return list(set(capabilities))


def extract_purpose_from_description(description: str) -> str:
    """Extract purpose from task description"""
    sentences = description.split(".")
    if sentences:
        first_sentence = sentences[0].strip()
        action_words = ["validates", "transforms", "generates",
                        "processes", "checks", "converts", "analyzes"]
        for word in action_words:
            if word.lower() in first_sentence.lower():
                return first_sentence
        return first_sentence
    return description[:100] + "..." if len(description) > 100 else description


def categorize_tasks_by_tags(tasks_info: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Categorize tasks by their tags"""
    categories = {}
    for task in tasks_info:
        for tag in task.get("tags", []):
            if tag not in categories:
                categories[tag] = []
            categories[tag].append(task["name"])
    return categories


def extract_use_cases_from_readme(readme_content: str) -> List[str]:
    """Extract use cases from README content"""
    if not readme_content:
        return []

    use_cases = []
    lines = readme_content.split("\n")

    for line in lines:
        line_lower = line.lower().strip()
        if any(indicator in line_lower for indicator in ["use case", "example", "scenario", "when to use"]):
            use_cases.append(line.strip())

    return use_cases[:3]


def generate_detailed_template_guidance(template_content: str, task_input: vo.TaskInputVO) -> Dict[str, Any]:
    """Generate detailed guidance for filling out a template"""
    guidance = {"overview": f"This template is for {task_input.description}", "format": f"Please provide content in {task_input.format.upper()} format", "structure_explanation": explain_template_structure(
        template_content, task_input.format), "required_fields": extract_required_fields(template_content, task_input.format), "field_descriptions": generate_field_descriptions(template_content, task_input.format), "tips": generate_format_tips(task_input.format)}
    return guidance


def explain_template_structure(template_content: str, format_type: str) -> str:
    """Explain the structure of the template"""
    if not template_content:
        return "Template structure not available"

    if format_type.lower() == "toml":
        return "This TOML file contains sections [section_name] with key-value pairs. Follow the exact section names and provide your values."
    elif format_type.lower() == "json":
        return "This JSON file contains nested objects and arrays. Maintain the structure and replace values with your data."
    elif format_type.lower() == "yaml":
        return "This YAML file uses indentation to show structure. Maintain the indentation and replace values."
    else:
        return f"This {format_type} file contains configuration data. Follow the template structure."


def extract_required_fields(template_content: str, format_type: str) -> List[str]:
    """Extract required fields from template content"""
    required_fields = []

    if not template_content:
        return required_fields

    try:
        if format_type.lower() == "json":
            keys = re.findall(r'"([^"]+)":', template_content)
            required_fields = list(set(keys))

        elif format_type.lower() == "toml":
            lines = template_content.split("\n")
            for line in lines:
                if "=" in line and not line.strip().startswith("#"):
                    key = line.split("=")[0].strip()
                    if key:
                        required_fields.append(key)

        elif format_type.lower() == "yaml":
            lines = template_content.split("\n")
            for line in lines:
                if ":" in line and not line.strip().startswith("#"):
                    key = line.split(":")[0].strip()
                    if key and not key.startswith("-"):
                        required_fields.append(key)

    except Exception:
        pass

    return list(set(required_fields))


def generate_field_descriptions(template_content: str, format_type: str) -> Dict[str, str]:
    """Generate descriptions for template fields"""
    descriptions = {}
    required_fields = extract_required_fields(
        template_content, format_type)

    for field in required_fields:
        descriptions[field] = f"Configuration value for {field}"

    return descriptions


def generate_format_tips(format_type: str) -> List[str]:
    """Generate format-specific tips"""
    tips = {"json": ["Use double quotes for strings", "Don't forget commas between items", "Use proper brackets: {} for objects, [] for arrays"], "toml": ["Use [section] headers for grouping",
                                                                                                                                                           "Strings can use single or double quotes", "Use # for comments"], "yaml": ["Indentation is important - use spaces, not tabs", "Use # for comments", "Strings usually don't need quotes unless they contain special characters"]}
    return tips.get(format_type.lower(), ["Follow the template structure exactly"])


def generate_example_content(template_content: str, format_type: str) -> str:
    """Generate example content based on template"""
    if not template_content:
        return f"Example {format_type} content"

    if format_type.lower() == "toml":
        return '# Example TOML configuration\n[section]\nkey = "value"'
    elif format_type.lower() == "json":
        return '{\n  "key": "value",\n  "number": 123\n}'
    elif format_type.lower() == "yaml":
        return "key: value\nnumber: 123"
    else:
        return f"Example {format_type} content based on template structure"


def get_template_validation_rules(format_type: str) -> Dict[str, Any]:
    """Get validation rules for the format type"""
    rules = {"json": {"syntax": "Must be valid JSON with proper brackets and quotes", "required": "All template fields should be present"}, "toml": {"syntax": "Must follow TOML syntax with proper sections",
                                                                                                                                                     "required": "All template keys should have values"}, "yaml": {"syntax": "Must have correct YAML indentation and structure", "required": "All template fields should be provided"}}
    return rules.get(format_type.lower(), {"syntax": "Follow template format"})


def check_missing_fields(user_content: str, required_fields: List[str]) -> List[str]:
    """Check which required fields are missing from user content"""
    if not required_fields:
        return []

    missing_fields = []

    try:
        for field in required_fields:
            if field not in user_content:
                missing_fields.append(field)
    except Exception:
        pass

    return missing_fields


def generate_content_preview(content: str, format_type: str) -> str:
    """Generate a preview of content for user confirmation"""
    max_preview_length = 200

    if len(content) <= max_preview_length:
        return content

    # For longer content, show beginning and end
    preview = content[: max_preview_length // 2] + \
        "\n...\n" + content[-max_preview_length // 2:]

    # For JSON, try to format nicely
    if format_type.lower() == "json":
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                item_count = len(parsed)
                preview = f"JSON Array with {item_count} items:\n{json.dumps(parsed[:2], indent=2)}"
                if item_count > 2:
                    preview += f"\n... and {item_count - 2} more items"
            elif isinstance(parsed, dict):
                key_count = len(parsed.keys())
                preview_obj = dict(list(parsed.items())[:3])
                preview = f"JSON Object with {key_count} keys:\n{json.dumps(preview_obj, indent=2)}"
                if key_count > 3:
                    preview += f"\n... and {key_count - 3} more keys"
        except:
            # Fallback to truncated content
            pass

    return preview


def validate_template_content_enhanced(task_input: vo.TaskInputVO, user_content: str) -> Dict[str, Any]:
    """Enhanced validation for template content including JSON arrays"""
    errors = []
    suggestions = []

    if not user_content.strip():
        errors.append("Content cannot be empty")
        return {"valid": False, "errors": errors, "suggestions": suggestions}

    # Format-specific validation with enhanced JSON handling
    if task_input.format.lower() == "json":
        try:
            parsed_json = json.loads(user_content)

            # Handle JSON arrays specifically
            if isinstance(parsed_json, list):
                # Validate each item in the array
                for i, item in enumerate(parsed_json):
                    if not isinstance(item, (dict, list, str, int, float, bool, type(None))):
                        errors.append(
                            f"Invalid JSON array element at index {i}")
                suggestions.append("JSON array validated successfully")
            elif isinstance(parsed_json, dict):
                # Validate JSON object
                suggestions.append("JSON object validated successfully")
            else:
                # Simple JSON value (string, number, boolean, null)
                suggestions.append("JSON value validated successfully")

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON format: {str(e)}")
            suggestions.append(
                "Please ensure your JSON is properly formatted with correct brackets and quotes")
            suggestions.append(
                'For arrays: [{"key": "value"}, {"key": "value"}]')
            suggestions.append(
                'For objects: {"key": "value", "nested": {"key": "value"}}')

    elif task_input.format.lower() == "toml":
        try:
            toml.loads(user_content)
        except Exception as e:
            errors.append(f"Invalid TOML format: {str(e)}")
            suggestions.append(
                "Please ensure your TOML follows the correct syntax with proper [section] headers")

    elif task_input.format.lower() == "yaml":
        try:
            yaml.load(user_content)
        except Exception as e:
            errors.append(f"Invalid YAML format: {str(e)}")
            suggestions.append(
                "Please ensure your YAML has correct indentation and syntax")

    # Check required fields based on template if available
    if task_input.templateFile:
        template_content = decode_content(task_input.templateFile)
        required_fields = extract_required_fields(
            template_content, task_input.format)
        missing_fields = check_missing_fields(
            user_content, required_fields)

        if missing_fields:
            errors.extend(
                [f"Missing required field: {field}" for field in missing_fields])
            suggestions.append(
                f"Please include the following required fields: {', '.join(missing_fields)}")

    return {"valid": len(errors) == 0, "errors": errors, "suggestions": suggestions}


def get_file_extension(format_type: str) -> str:
    """Get appropriate file extension for format type"""
    format_extensions = {"json": ".json", "toml": ".toml",
                         "yaml": ".yaml", "yml": ".yml", "xml": ".xml", "txt": ".txt"}
    return format_extensions.get(format_type.lower(), ".txt")


def validate_parameter_value(value: str, data_type: str) -> Dict[str, Any]:
    """Validate parameter value against expected data type"""
    errors = []
    converted_value = value

    try:
        if data_type.upper() == "INT":
            converted_value = int(value)
        elif data_type.upper() == "FLOAT":
            converted_value = float(value)
        elif data_type.upper() == "BOOLEAN":
            if value.lower() in ["true", "yes", "1", "on"]:
                converted_value = True
            elif value.lower() in ["false", "no", "0", "off"]:
                converted_value = False
            else:
                errors.append(
                    "Invalid boolean value. Use: true/false, yes/no, 1/0")
        elif data_type.upper() == "DATE":
            from datetime import datetime

            try:
                datetime.strptime(value, "%Y-%m-%d")
                converted_value = value
            except ValueError:
                errors.append("Invalid date format. Use: YYYY-MM-DD")
        elif data_type.upper() == "DATETIME":
            from datetime import datetime

            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                converted_value = value
            except ValueError:
                errors.append(
                    "Invalid datetime format. Use ISO 8601 format")
        elif data_type.upper() == "STRING":
            converted_value = str(value)
        else:
            # Unknown type, keep as string
            converted_value = str(value)

    except ValueError as e:
        errors.append(f"Cannot convert '{value}' to {data_type}: {str(e)}")

    return {"valid": len(errors) == 0, "errors": errors, "converted_value": converted_value}


def generate_parameter_presentation(task_input: vo.TaskInputVO, task_name: str) -> str:
    """Generate parameter collection presentation"""
    required_text = "Yes" if task_input.required else "No"
    default_text = task_input.defaultValue if task_input.defaultValue else "None"

    presentation = f"Task: {task_name}\n"
    presentation += f"Input: {task_input.name} ({task_input.dataType})\n"
    presentation += f"Description: {task_input.description}\n"
    presentation += f"Required: {required_text}\n"
    presentation += f"Default: {default_text}\n\n"

    if task_input.required:
        presentation += "This input is required. Please provide a value"
        if task_input.defaultValue:
            presentation += ", type 'default' to use default value"
    else:
        presentation += "This input is optional. Please provide a value"
        if task_input.defaultValue:
            presentation += ", type 'default' to use default value"
        presentation += ", or type 'skip' to skip"

    presentation += ":"

    return presentation


def generate_input_overview_presentation_with_unique_ids(input_analysis: Dict[str, Any]) -> str:
    """Generate user-friendly input overview presentation with unique IDs"""

    overview = "INPUT COLLECTION OVERVIEW:\n\n"
    overview += "I've analyzed your selected tasks. Here's what we need to configure:\n\n"

    # Template inputs section
    if input_analysis["template_inputs"]:
        overview += "TEMPLATE INPUTS (Files):\n"
        for inp in input_analysis["template_inputs"]:
            required_text = "Required" if inp["required"] else "Optional"
            format_text = f"({inp['format']} file)" if inp["format"] else "(FILE)"
            overview += f"• Task: {inp['task_name']} → Input: {inp['input_name']} {format_text}\n"
            overview += f"  Unique ID: {inp['unique_input_id']}\n"
            overview += f"  Description: {inp['description']}\n"
            overview += f"  Status: {required_text}\n"
        overview += "\n"

    # Parameter inputs section
    if input_analysis["parameter_inputs"]:
        overview += "PARAMETER INPUTS (Values):\n"
        for inp in input_analysis["parameter_inputs"]:
            required_text = "Required" if inp["required"] else "Optional"
            default_info = f" (Default: {inp['default_value']})" if inp["has_default"] else ""
            overview += f"• Task: {inp['task_name']} → Input: {inp['input_name']} ({inp['data_type']}){default_info}\n"
            overview += f"  Unique ID: {inp['unique_input_id']}\n"
            overview += f"  Description: {inp['description']}\n"
            overview += f"  Status: {required_text}\n"
        overview += "\n"

    # Summary section
    overview += "SUMMARY:\n"
    overview += f"- Total inputs needed: {input_analysis['total_count']}\n"

    if input_analysis["template_count"] > 0:
        formats = list(set(
            [inp["format"] for inp in input_analysis["template_inputs"] if inp["format"]]))
        overview += f"- Template files: {input_analysis['template_count']} ({', '.join(formats)})\n"

    if input_analysis["parameter_count"] > 0:
        overview += f"- Parameter values: {input_analysis['parameter_count']}\n"

    overview += f"- Estimated time: ~{int(input_analysis['estimated_minutes'])} minutes\n\n"

    # Show unique ID explanation
    overview += "NOTE: Each input has a unique ID (TaskName.InputName) to handle cases where multiple tasks have the same input names.\n\n"
    overview += "This will be collected step-by-step with progress indicators.\n"
    overview += "Ready to start systematic input collection?"

    return overview


def generate_verification_presentation_with_unique_ids(verification_summary: Dict[str, Any]) -> str:
    """Generate user-friendly verification presentation with unique IDs"""

    verification = "INPUT VERIFICATION SUMMARY:\n\n"
    verification += "Please review all collected inputs before rule creation:\n\n"

    # Template files section
    if verification_summary["template_files"]:
        verification += "TEMPLATE INPUTS (Uploaded Files):\n"
        for file_info in verification_summary["template_files"]:
            verification += f"✓ Task Input: {file_info['unique_input_id']}\n"
            verification += f"  Task: {file_info['task_name']} → Input: {file_info['input_name']}\n"
            verification += f"  Format: {file_info['format']}\n"
            verification += f"  File: {file_info['filename']}\n"
            # FIXED: Show file URL in verification
            verification += f"  URL: {file_info['file_url']}\n"
            verification += f"  Size: {file_info['file_size']} bytes\n"
            verification += f"  Status: {file_info['status']}\n\n"

    # Parameter values section
    if verification_summary["parameter_values"]:
        verification += "PARAMETER INPUTS (Values):\n"
        for param_info in verification_summary["parameter_values"]:
            required_text = "Yes" if param_info["required"] else "No"
            verification += f"✓ Task Input: {param_info['unique_input_id']}\n"
            verification += f"  Task: {param_info['task_name']} → Input: {param_info['input_name']}\n"
            verification += f"  Type: {param_info['data_type']}\n"
            verification += f"  Value: {param_info['value']}\n"
            verification += f"  Required: {required_text}\n"
            verification += f"  Status: {param_info['status']}\n\n"

    # Verification checklist
    verification += "VERIFICATION CHECKLIST:\n"
    verification += f"□ All required inputs collected ({verification_summary['total_collected']} total)\n"
    verification += "□ Template files uploaded and validated\n"
    verification += "□ Parameter values set and confirmed\n"
    verification += "□ No missing or invalid inputs\n"
    verification += "□ Ready for rule creation\n\n"

    if verification_summary["missing_inputs"]:
        verification += f"⚠ WARNING: {len(verification_summary['missing_inputs'])} inputs need attention:\n"
        for missing in verification_summary["missing_inputs"]:
            verification += f"  - {missing}\n"
        verification += "\n"

    verification += "Are all these inputs correct?\n"
    verification += "- Type 'yes' to proceed with rule creation\n"
    verification += "- Type 'modify [TaskName.InputName]' to change a specific input\n"
    verification += "- Type 'cancel' to abort rule creation"

    return verification


def validate_rule_structure(rule_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate rule structure"""
    errors = []

    # Check required fields
    if "kind" not in rule_data or rule_data["kind"] != "rule":
        errors.append("Missing or invalid 'kind' field - must be 'rule'")

    if "meta" not in rule_data:
        errors.append("Missing 'meta' section")
    else:
        meta = rule_data["meta"]
        required_meta = ["name", "purpose", "description"]
        for field in required_meta:
            if field not in meta or not meta[field]:
                errors.append(f"Missing required meta field: {field}")

    if "spec" not in rule_data:
        errors.append("Missing 'spec' section")
    else:
        spec = rule_data["spec"]
        if "tasks" not in spec or not spec["tasks"]:
            errors.append("Missing or empty 'tasks' in spec")

        if "ioMap" not in spec:
            errors.append("Missing 'ioMap' in spec")

        # Validate tasks structure
        if "tasks" in spec:
            for i, task in enumerate(spec["tasks"]):
                required_task_fields = ["name", "alias", "type", "appTags"]
                for field in required_task_fields:
                    if field not in task:
                        errors.append(f"Task {i}: missing '{field}' field")

    return {"valid": len(errors) == 0, "errors": errors}


def generate_yaml_preview(rule_structure: Dict[str, Any]) -> str:
    """Generate YAML preview of rule structure for user confirmation"""
    try:
        # Create a clean copy without internal flags
        clean_structure = {
            k: v for k, v in rule_structure.items() if not k.startswith("_")}

        # Use ruamel.yaml to generate properly formatted YAML
        stream = StringIO()
        yaml.dump(clean_structure, stream)
        yaml_content = stream.getvalue()

        return yaml_content
    except Exception:
        # Fallback to basic YAML-like formatting
        return basic_yaml_format(rule_structure)


def basic_yaml_format(data: Dict[str, Any], indent: int = 0) -> str:
    """Basic YAML formatting as fallback"""
    result = ""
    for key, value in data.items():
        if key.startswith("_"):  # Skip internal flags
            continue

        spaces = "  " * indent
        if isinstance(value, dict):
            result += f"{spaces}{key}:\n"
            result += basic_yaml_format(value, indent + 1)
        elif isinstance(value, list):
            result += f"{spaces}{key}:\n"
            for item in value:
                if isinstance(item, dict):
                    result += f"{spaces}- \n"
                    result += basic_yaml_format(item, indent + 1)
                else:
                    result += f"{spaces}- {item}\n"
        else:
            result += f"{spaces}{key}: {value}\n"
    return result


def fetch_task_api(params: Dict[str, Any] = {}) -> Dict[str, Any]:
    headers = wsutils.create_header()
    tasks = wsutils.get(path=wsutils.build_api_url(
        endpoint=constants.URL_FETCH_TASKS), params=params, header=headers)
    return tasks


def create_rule_api(rule_structure: Dict[str, Any]) -> Dict[str, Any]:
    headers = wsutils.create_header()
    rule_id = f"rule_{abs(hash(str(rule_structure))) % 10000}"
    wsutils.post(path=wsutils.build_api_url(
        endpoint=constants.URL_CREATE_RULE), data=json.dumps(rule_structure), header=headers)
    return {"rule_id": rule_id, "status": "created", "message": "Rule created successfully", "timestamp": datetime.now().isoformat()}

def fetch_rule(rule_name: str, include_read_me: bool = False) -> Dict[str, Any]:
    params = {
        "name":rule_name
    }
    if include_read_me:
        params={**params,"include_read_me" : "true"}

    headers = wsutils.create_header()
    try:
        rules_items = wsutils.get(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_RULES),
            params=params,
            header=headers
        )
        if is_valid_array(rules_items,"items"):
            return rules_items[0]
        else:
            return {"error": f"unable to find the rule named: {rule_name}"}
    except Exception as e:
        return {"error": f"Failed to fetch the rule by name '{rule_name}': {str(e)}"}


def encode_content(data: Union[Dict[str, Any], str]) -> str:
    """Base64 encode a dictionary or string"""
    try:
        if isinstance(data, dict):
            json_str = json.dumps(data)
            return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
        elif isinstance(data, str):
            return base64.b64encode(data.encode("utf-8")).decode("utf-8")
        return ""
    except Exception:
        return ""

def fetch_rules_api(params: Dict[str, Any] = None ) -> List[vo.SimplifiedRuleVO]:
    if params is None:
        params = {}

    if not is_valid_key(params,"page_size"):
        params["page_size"] = 50

    headers = wsutils.create_header()
    cur_page = 1
    has_next = True
    combined_rules = []

    while has_next:
        paginated_params = { **params, "page": cur_page, "tags":constants.MCP_GET_RULES_TAG }

        response = wsutils.get(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_RULES),
            params=paginated_params,
            header=headers,
        )

        if rule.is_valid_key(response, "items", array_check=True):
            rules = response["items"]

            for data in rules:
                if data.get("readmeData"):
                    try:
                        data["readmeData"] = base64.b64decode(data["readmeData"])
                    except Exception as e:
                        return f"Failed to decode base64 content: {e}"
                
                meta =data.get('meta',None)
                if meta:
                    combined_rules.append(vo.SimplifiedRuleVO.model_validate(meta))
                
            total_pages = int(response.get("totalPage", 0))
            cur_page += 1
            has_next = cur_page <= total_pages
        else:
            has_next = False

    return combined_rules

def fetch_rules_and_tasks_suggestions(query: str = None, identifierType: str = None) -> List[vo.SimplifiedRuleVO]:
    req_data = {
        "query": query,
        "identifierType": identifierType
    }
    headers = wsutils.create_header()
    suggestions = []
    try:
        rules_items = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_RULES_AND_TASKS_SUGGESTIONS),
            data=json.dumps(req_data),
            header=headers
        )
        if is_valid_array(rules_items,"items"):
            for data in rules_items["items"]:
                suggestions.append(vo.SimplifiedRulesAndTasksSuggestionVO.model_validate(data))
            return suggestions
        else:
            return {"error": f"unable to find the  {identifierType} suggestions for the query: {query}"}
    except Exception as e:
        return {"error": f"Failed to fetch {identifierType} suggestions : {str(e)}"}

def create_support_ticket_api(body: Dict[str, Any] = None ) -> Dict[str, Any]:
    headers = wsutils.create_header()
    try:
        ticket_details = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_CREATE_TICKET),
            data=json.dumps(body),
            header=headers
        )
        return {**ticket_details, "status": "created", "message": "Ticket created successfully", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"error": f"Failed to create support ticket: {e}"}
    
def get_json_preview(content: str, file_size_kb: float) -> tuple[str, str]:
    """Extract preview of JSON content. Shows all if < 1KB or only 1 record, first 3 if >= 1KB with multiple records."""
    try:
        data = json.loads(content)
        
        if isinstance(data, list):
            total = len(data)
            # Show all if file < 1KB OR only 1 record
            if file_size_kb < 1.0 or total <= 1:
                preview_json = json.dumps(data, indent=2)
                return preview_json, f"All {total} records shown"
            else:
                # Show first 3 records for large files with multiple records
                preview = data[:3]
                preview_json = json.dumps(preview, indent=2)
                if total > 3:
                    preview_json += "\n... (truncated)"
                return preview_json, f"Showing first 3 of {total} records"
                
        elif isinstance(data, dict):
            # Single object - always show complete for < 1KB, check arrays for >= 1KB
            if file_size_kb < 1.0:
                preview_json = json.dumps(data, indent=2)
                return preview_json, "Complete object shown"
            else:
                # For large files, truncate arrays to 3 items
                preview_data = {}
                for key, value in data.items():
                    if isinstance(value, list) and len(value) > 3:
                        preview_data[key] = value[:3]
                    else:
                        preview_data[key] = value
                
                preview_json = json.dumps(preview_data, indent=2)
                return preview_json, "Object shown (arrays truncated to 3 items)"
        else:
            # Single value - always show complete
            return json.dumps(data, indent=2), "Single value"
            
    except:
        lines = content.split('\n')
        if file_size_kb < 1.0:
            return content, f"All {len(lines)} lines"
        else:
            preview = '\n'.join(lines[:3])
            return preview, f"First 3 of {len(lines)} lines"

def get_csv_preview(content: str, file_size_kb: float) -> tuple[str, str]:
    """Extract preview of CSV content. Shows all if < 1KB or only 1 record, header + first 3 if >= 1KB with multiple records."""
    lines = [line for line in content.split('\n') if line.strip()]
    
    if not lines:
        return content, "Empty file"
    
    total_data_rows = len(lines) - 1  # Exclude header
    
    # Show all if file < 1KB OR only 1 data record
    if file_size_kb < 1.0 or total_data_rows <= 1:
        preview_content = '\n'.join(lines)
        return preview_content, f"Header + all {total_data_rows} records shown"
    else:
        # Show header + first 3 data rows for large files with multiple records
        if total_data_rows > 3:
            # More than 3 data rows - show header + first 3 data rows
            preview_lines = lines[:4]  # Header + 3 data rows
            preview_content = '\n'.join(preview_lines)
            preview_content += "\n... (truncated)"
            return preview_content, f"Header + first 3 of {total_data_rows} records"
        else:
            # 2 or 3 data rows - show all
            preview_content = '\n'.join(lines)
            return preview_content, f"Header + all {total_data_rows} records shown"

def get_parquet_preview(content: str, file_size_kb: float) -> tuple[str, str]:
    """Decode base64 Parquet content. Shows all if < 1KB or only 1 record, first 3 if >= 1KB with multiple records."""
    try:
        decoded_bytes = base64.b64decode(content)
        df = pd.read_parquet(BytesIO(decoded_bytes))
        
        total = len(df)
        
        # Show all if file < 1KB OR only 1 record
        if file_size_kb < 1.0 or total <= 1:
            preview_json = df.to_json(orient="records", indent=2)
            return preview_json, f"All {total} records shown"
        else:
            # Show first 3 records for large files with multiple records
            if total > 3:
                preview_df = df.head(3)
                preview_json = preview_df.to_json(orient="records", indent=2)
                preview_json += "\n... (truncated)"
                return preview_json, f"First 3 of {total} records shown"
            else:
                preview_json = df.to_json(orient="records", indent=2)
                return preview_json, f"All {total} records shown"
        
    except Exception as e:
        return f"Error processing Parquet: {e}", "Processing failed"
    
def get_assessment_controls(params: Dict[str, Any] = None ) -> List[vo.AssessmentControlVO]:
    if params is None:
        params = {}

    if not is_valid_key(params,"page_size"):
        params["page_size"] = 100

    headers = wsutils.create_header()
    cur_page = 1
    has_next = True
    combined_leaf_controls = []


    while has_next:
        paginated_params = { **params, "page": cur_page}

        response = wsutils.get(
            path=wsutils.build_api_url(endpoint=constants.URL_PLAN_CONTROLS),
            params=paginated_params,
            header=headers,
        )

        if rule.is_valid_key(response, "items", array_check=True):
            leaf_controls = response["items"]
            if not leaf_controls:
                return combined_leaf_controls 

            for control in leaf_controls:
                combined_leaf_controls.append(vo.AssessmentControlVO.model_validate(control))

            total_pages = int(response.get("TotalPage", 0)) or 1
            cur_page += 1
            has_next = cur_page <= total_pages
        else:
            has_next = False

    return combined_leaf_controls

def get_assessments(params: Dict[str, Any] = None ) -> List[vo.AssessmentVO]:
    headers = wsutils.create_header()
    assessment_response = wsutils.get(
        path=wsutils.build_api_url(endpoint=constants.URL_PLANS),
        params=params,
        header=headers,
    )

    if isinstance(assessment_response, str) or (isinstance(assessment_response, dict) and "error" in assessment_response):
        return vo.AssessmentListVO(error="Unable to retrieve assessment details. Please try again later.")                
    assessments = []
    for item in assessment_response.get("items", []):
        if "name" in item and "categoryName" in item:
            assessments.append(vo.AssessmentVO.model_validate(item))
    
    return assessments


def fetch_cc_rule_by_id(rule_id: str) -> Dict[str, Any]:

    headers = wsutils.create_header()
    try:
        rule_response = wsutils.get(
            path=wsutils.build_api_url(endpoint=f"{constants.URL_GET_CC_RULE_BY_ID.replace('{id}',rule_id)}"),
            header=headers
        )
        return rule_response
    except Exception as e:
        return {"error": f"Failed to fetch the rule: {e}"}
    
def fetch_cc_rule_by_name(rule_name: str) -> Dict[str, Any]:
    params={
        "name":rule_name,
        "page_size":10,
        "page":1
    }

    headers = wsutils.create_header()
    try:
        rule_response = wsutils.get(
            path=wsutils.build_api_url(endpoint=f"{constants.URL_GET_CC_RULE}"),
            params=params,
            header=headers
        )
        if rule.is_valid_key(rule_response, "items", array_check=True):
            leaf_controls = rule_response["items"]
            return leaf_controls
        else:
            return []
    except Exception as e:
        return {"error": f"Failed to fetch the rule: {e}"}
    
def attach_rule_to_control_api(control_id: str, body:dict) -> Dict[str, Any]:

    headers = wsutils.create_header()
    try:
        wsutils.post(
            path=wsutils.build_api_url(endpoint=f"{constants.URL_LINK_CC_RULE_TO_CONTROL.replace('{control_id}',control_id)}"),
            data=json.dumps(body),
            header=headers
        )

        logger.debug(f"debug : attached the rule to the control: {control_id}\n")

        return {"success":True ,"status": "attached", "message": "Rule attached to control successfully", "timestamp": datetime.now().isoformat()}
    
    except Exception as e:
        return {"error": f"Failed while associating rule with control: {e}"}

def validate_and_format_content(content: str, file_format: str) -> tuple[str, bool, str]:
    """Validate and format content based on file type. Returns (formatted_content, is_valid, message)."""

    if file_format == 'json':
        try:
            # Fix common JSON issues first
            fixed_content = fix_json_string(content)
            parsed = json.loads(fixed_content)
            # Re-serialize with proper formatting
            formatted_content = json.dumps(
                parsed, indent=2, ensure_ascii=False)
            return formatted_content, True, "JSON validated and formatted"
        except json.JSONDecodeError as e:
            return content, False, f"Invalid JSON: {str(e)}"

    elif file_format in ['yaml', 'yml']:
        if yaml is None:
            return content, True, "YAML validation skipped (PyYAML not available)"
        try:
            parsed = yaml.load(content)
            formatted_content = yaml.dump(
                parsed, default_flow_style=False, allow_unicode=True, indent=2)
            return formatted_content, True, "YAML validated and formatted"
        except Exception as e:
            return content, False, f"Invalid YAML: {str(e)}"

    elif file_format == 'toml':
        if toml is None:
            return content, True, "TOML validation skipped (toml not available)"
        try:
            parsed = toml.loads(content)
            formatted_content = toml.dumps(parsed)
            return formatted_content, True, "TOML validated and formatted"
        except toml.TomlDecodeError as e:
            return content, False, f"Invalid TOML: {str(e)}"

    elif file_format in ['csv', 'tsv']:
        try:
            # Detect delimiter
            sniffer = csv.Sniffer()
            try:
                delimiter = sniffer.sniff(content[:1024]).delimiter
            except:
                delimiter = ',' if file_format == 'csv' else '\t'

            # Parse and reformat
            csv_input = StringIO(content)
            reader = csv.reader(csv_input, delimiter=delimiter)

            csv_output = StringIO()
            writer = csv.writer(csv_output, quoting=csv.QUOTE_MINIMAL)

            row_count = 0
            for row in reader:
                cleaned_row = [cell.strip() if isinstance(
                    cell, str) else cell for cell in row]
                writer.writerow(cleaned_row)
                row_count += 1

            formatted_content = csv_output.getvalue()
            return formatted_content, True, f"CSV validated with {row_count} rows"
        except Exception as e:
            return content, False, f"Invalid CSV: {str(e)}"

    elif file_format == 'xml':
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(content)
            return content, True, "XML validated"
        except ET.ParseError as e:
            return content, False, f"Invalid XML: {str(e)}"

    else:
        # For other formats, no validation needed
        return content, True, f"Content accepted as {file_format} format"
    

def detect_file_format(file_name: str, content: str) -> str:
    """Detect file format from filename and content."""
    # First try from filename extension
    if '.' in file_name:
        extension = file_name.split('.')[-1].lower()
        if extension in ['json', 'yaml', 'yml', 'toml', 'csv', 'tsv', 'txt', 'xml']:
            return extension

    # Try to detect from content
    content_stripped = content.strip()

    if content_stripped.startswith('{') and content_stripped.endswith('}'):
        return 'json'
    elif content_stripped.startswith('[') and content_stripped.endswith(']'):
        return 'json'
    elif any(line.strip().startswith('[') and line.strip().endswith(']') for line in content_stripped.split('\n')[:5]):
        return 'toml'
    elif ',' in content_stripped and '\n' in content_stripped:
        return 'csv'

    return 'txt'  # Default fallback

def fix_json_string(content: str) -> str:
    """Fix common JSON string issues."""
    
    # Remove literal \n characters (not actual newlines)
    content = content.replace('\\n', '')

    # Remove potential BOM
    if content.startswith('\ufeff'):
        content = content[1:]

    # Fix escaped quotes within string values
    content = re.sub(r'\\\"', '"', content)

    # Fix single quotes to double quotes (only for keys and string values)
    content = re.sub(r"'([^']*)':", r'"\1":', content)  # Fix keys
    content = re.sub(r":\s*'([^']*)'", r': "\1"', content)  # Fix string values

    return content.strip()    

def execute_task_api(body: Dict[str, Any] = None ) -> Dict[str, Any]:
    headers = wsutils.create_header()
    try:
        execute_response = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_EXECUTE_TASK),
            data=json.dumps(body),
            header=headers
        )

        task_outputs = execute_response.get("taskOutputs")
        log_file = execute_response.get("LogFile")
        outputs = log_file.get("Outputs") if isinstance(log_file, dict) else None
        log_file_url = outputs.get("LogFile") if isinstance(outputs, dict) else None

        if task_outputs and log_file and outputs and log_file_url:
            payload = {"fileURL": log_file_url}
            log_response = wsutils.post(
                path=wsutils.build_api_url(endpoint=constants.URL_FETCH_FILE),
                data=json.dumps(payload),
                header=headers
            )
            file_content = log_response.get("fileContent", "")
            actual_content = base64.b64decode(file_content).decode('utf-8')
            # Update execute_response to include Errors in the correct nested structure
            execute_response["taskOutputs"] = {"Outputs": {"Errors": json.loads(actual_content)}}

        return {**execute_response, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"error": f"Failed to execute task: {e}"}