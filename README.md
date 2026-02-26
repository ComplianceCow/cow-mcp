# ComplianceCow MCP Servers

## Table of Contents

1. [Introduction](#introduction)
2. [Glossary](#glossary)
3. [Architecture](#architecture)
4. [MCP Servers](#mcp-servers)
5. [Getting Started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [Authentication](#authentication)
   - [Installation](#installation)
   - [Configuration](#configuration)
6. [MCP Host Setup](#mcp-host-setup)
   - [Claude Desktop](#claude-desktop)
   - [Goose Desktop/CLI](#goose-desktopcli)
7. [Running Locally](#running-locally)
8. [Tools Reference](#tools-reference)
9. [FAQ](#faq)

---

## Introduction

MCP (Model Context Protocol) servers are designed to process structured requests from AI agents, perform domain-specific operations, and return context-aware responses. The ComplianceCow MCP servers enable seamless integration with MCP-compatible hosts like Claude Desktop and Goose Desktop/CLI for secure, modular, and intelligent compliance automation.

---

## Glossary

| Keyword | Description | Example |
|---------|-------------|---------|
| **Control** | A compliance or security control that needs to be implemented to ensure adherence to regulations, standards, and policies | Ensure MFA is enabled for all users |
| **Assessment** | A collection of controls organized hierarchically, representing an industry standard or cybersecurity framework | PCI DSS 4.0 |
| **Assessment Run** | The verification of controls in an assessment for a given time period, including evidence collection | - |
| **Check** | A rule or verification for compliance or conformance | Check if MFA is enabled for all AWS users |
| **Resource Type** | Category or class of resources | AWS EC2, AWS S3 |
| **Resource** | Instance of a resource type for which checks are performed | Specific EC2 instances, GitHub repositories |
| **Asset** | A group of resources of various types | AWS services, Kubernetes, GitHub |
| **Evidence** | Data aggregated through checks against resources for a given control | CSV file with AWS users and their MFA status |
| **Action** | Activity (automated or manual) to respond or remediate based on conditions | Create a JIRA ticket for non-compliant EC2 instance |
| **Rule** | A reusable automation unit that executes tasks and generates evidence | AWS MFA Compliance Check Rule |
| **Workflow** | An event-driven automation sequence with conditions and activities | Alert workflow on critical finding |

---

## Architecture

The ComplianceCow MCP servers support the **STDIO transport mechanism** for seamless local integration with your MCP host. At the core is the **Compliance Graph**, which continuously ingests data such as assessment runs, evidence, and compliance status. The server actively pulls information from:

- Vector stores for semantic search
- Relational databases for structured data
- Graph databases for relationship queries
- File storage systems for evidence artifacts

---

## MCP Servers

We have organized ComplianceCow’s MCP tools into 4 distinct servers.

> **Why multiple MCP servers?** In the MCP ecosystem, using fewer tools per server yields better results and better performance. 
<br>Each server can be enabled independently via the `MCP_TOOLS_TO_BE_INCLUDED` environment variable. 
<br>**Important:** Enable only **one server at a time** in the MCP Host to avoid tool name conflicts. Some tools share the same name across servers but have different implementations based on the use case.

### 1. ComplianceCow-Rules

The Rules server enables creating, managing, and executing compliance rules. It provides a comprehensive toolkit for rule creation with guided input collection, task orchestration, and ComplianceCow integration.

**Use Cases:**
- Create custom compliance rules with multiple tasks
- Execute rules against cloud infrastructure
- Publish rules to ComplianceCow and attach to controls
- Generate rule documentation (design notes, README)

---

### 2. ComplianceCow-Insights

The Insights server provides comprehensive access to compliance data, dashboards, assessments, and evidence through the Compliance Graph. Ideal for querying and analyzing compliance posture.

**Use Cases:**
- Query dashboard data for compliance overview
- Explore assessments and their runs
- Retrieve evidence and compliance status
- Execute Cypher queries on the Compliance Graph
- Perform actions on controls and evidence

---

### 3. ComplianceCow-Workflow

The Workflow server enables building and executing automated compliance workflows with event-driven triggers, conditions, and activities.

**Use Cases:**
- Create automated compliance workflows
- Define event triggers and conditions
- Execute multi-step workflow sequences
- Manage workflow states and transitions

---

### 4. ComplianceCow-Assistant

The Assistant server specializes in assessment configuration, control setup, and SQL-based evidence collection. It provides tools for configuring compliance assessments and managing control evidence.

**Use Cases:**
- Create and configure assessments
- Set up control configurations with context entities
- Create SQL-based evidence collection
- Manage control citations and documentation

---

## Getting Started

### Prerequisites

1. **MCP Host**: You need an MCP-compatible host:
   - [Claude Desktop](https://claude.ai/download)
   - [Goose Desktop/CLI](https://block.github.io/goose/docs/getting-started/installation/)

2. **Python**: Version 3.11 or higher
   - [Download Python](https://www.python.org/downloads/)

3. **uv Package Manager**: Required to run the MCP server
   - [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

### Authentication

The ComplianceCow MCP servers use OAuth 2.0 with `client_credentials` grant type.

**To obtain credentials:**

1. Sign up at [ComplianceCow](https://partner.compliancecow.live/ui/signup) (or your dedicated instance)
2. Click **"Manage Client Credentials"** in the top-right user profile menu
3. Fill out the form to obtain your **Client ID** and **Client Secret**

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ComplianceCow/cow-mcp.git
   cd cow-mcp
   ```

2. **Create virtual environment and install dependencies:**
   ```bash
   uv venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install .
   ```

3. **Find your uv binary path** (needed for configuration):
   ```bash
   which uv  # On macOS/Linux
   where uv  # On Windows
   ```

---

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `CCOW_HOST` | ComplianceCow API host URL (Ex: https://partner.compliancecow.live) | Yes |
| `CCOW_CLIENT_ID` | Your Client ID (see [Authentication section above](#authentication)) | Yes |
| `CCOW_CLIENT_SECRET` | Your Client Secret (see [Authentication section above](#authentication)) | Yes |

## MCP Host Setup

### Claude Desktop

**Configuration file location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

For detailed setup instructions, see [Claude Desktop MCP Setup](https://modelcontextprotocol.io/quickstart/user).

**Configuration template for all 4 servers:**

```json
{
  "mcpServers": {
    "ComplianceCow-Rules": {
      "command": "<UV_BIN_PATH>",
      "args": [
        "--directory",
        "<PATH_TO_COW_MCP_REPO>",
        "run",
        "main.py"
      ],
      "env": {
        "CCOW_HOST": "<YOUR_CCOW_HOST>",
        "CCOW_CLIENT_ID": "<YOUR_CLIENT_ID>",
        "CCOW_CLIENT_SECRET": "<YOUR_CLIENT_SECRET>",
        "MCP_TOOLS_TO_BE_INCLUDED": "rules"
      }
    },
    "ComplianceCow-Insights": {
      "command": "<UV_BIN_PATH>",
      "args": [
        "--directory",
        "<PATH_TO_COW_MCP_REPO>",
        "run",
        "main.py"
      ],
      "env": {
        "CCOW_HOST": "<YOUR_CCOW_HOST>",
        "CCOW_CLIENT_ID": "<YOUR_CLIENT_ID>",
        "CCOW_CLIENT_SECRET": "<YOUR_CLIENT_SECRET>",
        "MCP_TOOLS_TO_BE_INCLUDED": "insights"
      }
    },
    "ComplianceCow-Workflow": {
      "command": "<UV_BIN_PATH>",
      "args": [
        "--directory",
        "<PATH_TO_COW_MCP_REPO>",
        "run",
        "main.py"
      ],
      "env": {
        "CCOW_HOST": "<YOUR_CCOW_HOST>",
        "CCOW_CLIENT_ID": "<YOUR_CLIENT_ID>",
        "CCOW_CLIENT_SECRET": "<YOUR_CLIENT_SECRET>",
        "MCP_TOOLS_TO_BE_INCLUDED": "workflow"
      }
    },
    "ComplianceCow-Assistant": {
      "command": "<UV_BIN_PATH>",
      "args": [
        "--directory",
        "<PATH_TO_COW_MCP_REPO>",
        "run",
        "main.py"
      ],
      "env": {
        "CCOW_HOST": "<YOUR_CCOW_HOST>",
        "CCOW_CLIENT_ID": "<YOUR_CLIENT_ID>",
        "CCOW_CLIENT_SECRET": "<YOUR_CLIENT_SECRET>",
        "MCP_TOOLS_TO_BE_INCLUDED": "assistant"
      }
    }
  }
}
```

**Replace the following placeholders:**
- `UV_BIN_PATH`: Path to your uv binary (e.g., `/Users/username/.local/bin/uv`). You can find this by running `which uv` (macOS/Linux) or `where uv` (Windows).
- `PATH_TO_COW_MCP_REPO`: The absolute path to your cloned cow-mcp repository. After cloning and running `cd cow-mcp`, use `pwd` (macOS/Linux) or `cd` (Windows) to get this path.
- `YOUR_CCOW_HOST`: https://partner.compliancecow.live (or \<your_dedicated_instance_hosturl\>)
- `YOUR_CLIENT_ID`: Your ComplianceCow Client ID (see [Authentication](#authentication))
- `YOUR_CLIENT_SECRET`: Your ComplianceCow Client Secret (see [Authentication](#authentication))

---

### Goose Desktop/CLI

For detailed setup instructions, see [Goose Extensions Documentation](https://block.github.io/goose/docs/getting-started/using-extensions/).

**Configuration file location:**
- macOS/Linux: `~/.config/goose/config.yaml`
- Windows: `%APPDATA%\goose\config.yaml`

**Configuration template for all 4 servers:**

```yaml
extensions:
  ComplianceCow-Rules:
    enabled: true
    type: stdio
    name: Compliancecow-Rules
    description: 'ComplianceCow Rules - Create and manage compliance rules'
    cmd: <UV_BIN_PATH>
    args:
      - --directory
      - <PATH_TO_COW_MCP_REPO>
      - run
      - main.py
    envs:
      CCOW_HOST: <YOUR_CCOW_HOST>
      CCOW_CLIENT_ID: <YOUR_CLIENT_ID>
      CCOW_CLIENT_SECRET: <YOUR_CLIENT_SECRET>
      MCP_TOOLS_TO_BE_INCLUDED: rules
    timeout: 300

  ComplianceCow-Insights:
    enabled: true
    type: stdio
    name: Compliancecow-Insights
    description: 'ComplianceCow Insights - Query compliance data and dashboards'
    cmd: <UV_BIN_PATH>
    args:
      - --directory
      - <PATH_TO_COW_MCP_REPO>
      - run
      - main.py
    envs:
      CCOW_HOST: <YOUR_CCOW_HOST>
      CCOW_CLIENT_ID: <YOUR_CLIENT_ID>
      CCOW_CLIENT_SECRET: <YOUR_CLIENT_SECRET>
      MCP_TOOLS_TO_BE_INCLUDED: insights
    timeout: 300

  ComplianceCow-Workflow:
    enabled: true
    type: stdio
    name: Compliancecow-Workflow
    description: 'ComplianceCow Workflow - Build and execute compliance workflows'
    cmd: <UV_BIN_PATH>
    args:
      - --directory
      - <PATH_TO_COW_MCP_REPO>
      - run
      - main.py
    envs:
      CCOW_HOST: <YOUR_CCOW_HOST>
      CCOW_CLIENT_ID: <YOUR_CLIENT_ID>
      CCOW_CLIENT_SECRET: <YOUR_CLIENT_SECRET>
      MCP_TOOLS_TO_BE_INCLUDED: workflow
    timeout: 300

  ComplianceCow-Assistant:
    enabled: true
    type: stdio
    name: Compliancecow-Assistant
    description: 'ComplianceCow Assistant - Configure assessments and controls'
    cmd: <UV_BIN_PATH>
    args:
      - --directory
      - <PATH_TO_COW_MCP_REPO>
      - run
      - main.py
    envs:
      CCOW_HOST: <YOUR_CCOW_HOST>
      CCOW_CLIENT_ID: <YOUR_CLIENT_ID>
      CCOW_CLIENT_SECRET: <YOUR_CLIENT_SECRET>
      MCP_TOOLS_TO_BE_INCLUDED: assistant
    timeout: 300
```

**Replace the following placeholders:**
- `UV_BIN_PATH`: Path to your uv binary (e.g., `/Users/username/.local/bin/uv`). You can find this by running `which uv` (macOS/Linux) or `where uv` (Windows).
- `PATH_TO_COW_MCP_REPO`: The absolute path to your cloned cow-mcp repository. After cloning and running `cd cow-mcp`, use `pwd` (macOS/Linux) or `cd` (Windows) to get this path.
- `YOUR_CCOW_HOST`: https://partner.compliancecow.live (or \<your_dedicated_instance_hosturl\>)
- `YOUR_CLIENT_ID`: Your ComplianceCow Client ID (see [Authentication](#authentication))
- `YOUR_CLIENT_SECRET`: Your ComplianceCow Client Secret (see [Authentication](#authentication))

---

## Running Locally

To verify the MCP server is properly set up before configuring your MCP host:

```bash
# Navigate to the cow-mcp directory
cd /path/to/cow-mcp

# Set required environment variables
export CCOW_HOST="https://partner.compliancecow.live"
export CCOW_CLIENT_ID="<your_client_id>"
export CCOW_CLIENT_SECRET="<your_client_secret>"
export MCP_TOOLS_TO_BE_INCLUDED="rules"  # or insights, workflow, assistant

# Run the server
uv run main.py
```

If the server starts without errors, you're ready to configure your MCP host.

---

## Tools Reference

### Rules Server Tools

| Tool | Description |
|------|-------------|
| [`get_tasks_summary`](tools/rules/rules.py) | Retrieve available tasks for rule creation |
| [`get_task_details`](tools/rules/rules.py) | Get detailed task information including inputs/outputs |
| [`fetch_tasks_suggestions`](tools/rules/rules.py) | Intelligent task suggestions based on requirements |
| [`get_rules_summary`](tools/rules/rules.py) | List all available rules in the catalog |
| [`fetch_rules_suggestions`](tools/rules/rules.py) | Suggest matching rules to avoid duplicates |
| [`create_rule`](tools/rules/rules.py) | Create a new rule with tasks and I/O mapping |
| [`fetch_rule`](tools/rules/rules.py) | Retrieve complete rule structure by name |
| [`check_rule_status`](tools/rules/rules.py) | Check rule completion level |
| [`prepare_input_collection_overview`](tools/rules/rules.py) | Overview of required inputs before collection |
| [`get_template_guidance`](tools/rules/rules.py) | Guidance for template-based inputs |
| [`collect_template_input`](tools/rules/rules.py) | Collect file/template inputs with validation |
| [`confirm_template_input`](tools/rules/rules.py) | Confirm and process template input |
| [`collect_parameter_input`](tools/rules/rules.py) | Collect primitive parameter values |
| [`confirm_parameter_input`](tools/rules/rules.py) | Confirm and store parameter values |
| [`upload_file`](tools/rules/rules.py) | Upload files with format validation |
| [`verify_collected_inputs`](tools/rules/rules.py) | Verify all inputs before execution |
| [`execute_task`](tools/rules/rules.py) | Execute a specific task with collected inputs |
| [`execute_rule`](tools/rules/rules.py) | Execute complete rule with credentials |
| [`fetch_execution_progress`](tools/rules/rules.py) | Monitor live execution progress |
| [`fetch_output_file`](tools/rules/rules.py) | Fetch output files from execution |
| [`fetch_cc_rule_by_id`](tools/rules/rules.py) | Fetch rule from ComplianceCow by ID |
| [`fetch_cc_rule_by_name`](tools/rules/rules.py) | Fetch rule from ComplianceCow by name |
| [`fetch_cc_rules_list`](tools/rules/rules.py) | List published ComplianceCow rules |
| [`publish_rule`](tools/rules/rules.py) | Publish rule to ComplianceCow |
| [`fetch_assessments`](tools/rules/rules.py) | Retrieve available assessments |
| [`fetch_leaf_controls_of_an_assessment`](tools/rules/rules.py) | Fetch attachable controls from assessment |
| [`verify_control_in_assessment`](tools/rules/rules.py) | Verify control is attachable |
| [`attach_rule_to_control`](tools/rules/rules.py) | Attach published rule to control |
| [`get_applications_for_tag`](tools/rules/rules.py) | Get applications for specific tag |
| [`get_application_info`](tools/rules/rules.py) | Get application details and credential types |
| [`fetch_applications`](tools/rules/rules.py) | Fetch all available applications |
| [`prepare_applications_for_execution`](tools/rules/rules.py) | Prepare application configuration |
| [`check_applications_publish_status`](tools/rules/rules.py) | Check application publication status |
| [`publish_application`](tools/rules/rules.py) | Publish applications for rule execution |
| [`add_unique_identifier_to_task`](tools/rules/rules.py) | Add unique identifier to task |
| [`configure_rule_output_schema`](tools/rules/rules.py) | Configure standard/extended output schema |
| [`generate_design_notes_preview`](tools/rules/rules.py) | Generate Jupyter notebook design notes |
| [`create_design_notes`](tools/rules/rules.py) | Save design notes |
| [`fetch_rule_design_notes`](tools/rules/rules.py) | Fetch existing design notes |
| [`generate_rule_readme_preview`](tools/rules/rules.py) | Generate comprehensive README |
| [`create_rule_readme`](tools/rules/rules.py) | Save README |
| [`update_rule_readme`](tools/rules/rules.py) | Update existing README |
| [`list_assets`](tools/rules/rules.py) | List integration plans/assets |
| [`list_checks`](tools/rules/rules.py) | List checks for an asset |
| [`get_asset_control_hierarchy`](tools/rules/rules.py) | Get control hierarchy for asset |
| [`create_asset_and_check`](tools/rules/rules.py) | Create asset with initial check |
| [`add_check_to_asset`](tools/rules/rules.py) | Add check to existing asset |
| [`schedule_asset_execution`](tools/rules/rules.py) | Schedule automated asset execution |
| [`list_asset_schedules`](tools/rules/rules.py) | List schedules for an asset |
| [`delete_asset_schedule`](tools/rules/rules.py) | Delete asset schedule |
| [`suggest_control_config_citations`](tools/rules/rules.py) | Suggest control citations |
| [`add_citation_to_asset_control`](tools/rules/rules.py) | Attach citation to control |
| [`verify_control_automation`](tools/rules/rules.py) | Verify control automation status |
| [`create_control_note`](tools/rules/rules.py) | Create documentation note on control |
| [`list_control_notes`](tools/rules/rules.py) | List control notes |
| [`update_control_config_note`](tools/rules/rules.py) | Update control note |
| [`create_support_ticket`](tools/rules/rules.py) | Create support tickets |
| [`check_rule_publish_status`](tools/rules/rules.py) | Check rule publication status |
| [`read_file`](tools/general/general.py) | Read local file content |
| [`read_resource`](tools/general/general.py) | Read resource URI content |
| [`create_downloadable_file`](tools/general/general.py) | Create downloadable file URL |

---

### Insights Server Tools

| Tool | Description |
|------|-------------|
| [`list_all_assessment_categories`](tools/assessments/config/config.py) | List all assessment categories |
| [`list_assessments`](tools/assessments/config/config.py) | List assessments by category/name |
| [`fetch_recent_assessment_runs`](tools/assessments/run/run.py) | Fetch recent assessment runs |
| [`fetch_assessment_runs`](tools/assessments/run/run.py) | Fetch runs with pagination |
| [`fetch_assessment_run_details`](tools/assessments/run/run.py) | Get control details from run |
| [`fetch_assessment_run_leaf_controls`](tools/assessments/run/run.py) | Get leaf controls from run |
| [`fetch_run_controls`](tools/assessments/run/run.py) | Get controls by name |
| [`fetch_run_control_meta_data`](tools/assessments/run/run.py) | Get control metadata |
| [`fetch_assessment_run_leaf_control_evidence`](tools/assessments/run/run.py) | Get evidence for controls |
| [`fetch_controls`](tools/assessments/run/run.py) | Fetch control information |
| [`fetch_evidence_records`](tools/assessments/run/run.py) | Get evidence records with filtering |
| [`fetch_evidence_record_schema`](tools/assessments/run/run.py) | Get evidence schema |
| [`fetch_available_control_actions`](tools/assessments/run/run.py) | Fetch available control actions |
| [`fetch_assessment_available_actions`](tools/assessments/run/run.py) | Fetch assessment actions |
| [`fetch_evidence_available_actions`](tools/assessments/run/run.py) | Fetch evidence actions |
| [`fetch_general_available_actions`](tools/assessments/run/run.py) | Fetch general actions |
| [`fetch_automated_controls_of_an_assessment`](tools/assessments/run/run.py) | Fetch automated controls |
| [`execute_action`](tools/assessments/run/run.py) | Execute action on control/evidence |
| [`list_assets`](tools/assets/assets.py) | List all assets |
| [`fetch_assets_summary`](tools/assets/assets.py) | Get asset summary statistics |
| [`fetch_resource_types`](tools/assets/assets.py) | Get resource types with pagination |
| [`fetch_checks`](tools/assets/assets.py) | Get checks for resource type |
| [`fetch_resources`](tools/assets/assets.py) | Get resources with pagination |
| [`fetch_resources_by_check_name`](tools/assets/assets.py) | Get resources by check name |
| [`fetch_checks_summary`](tools/assets/assets.py) | Get checks summary statistics |
| [`fetch_resources_summary`](tools/assets/assets.py) | Get resources summary statistics |
| [`fetch_resources_by_check_name_summary`](tools/assets/assets.py) | Get resources summary by check |
| [`fetch_resource_types_summary`](tools/assets/assets.py) | Get resource types summary |
| [`get_dashboard_review_periods`](tools/dashboard/dashboard.py) | Get available review periods |
| [`get_dashboard_data`](tools/dashboard/dashboard.py) | Get comprehensive dashboard data |
| [`fetch_dashboard_framework_controls`](tools/dashboard/dashboard.py) | Get framework controls |
| [`fetch_dashboard_framework_summary`](tools/dashboard/dashboard.py) | Get framework summary |
| [`get_dashboard_common_controls_details`](tools/dashboard/dashboard.py) | Get common control details |
| [`get_top_over_due_controls_detail`](tools/dashboard/dashboard.py) | Get top overdue controls |
| [`get_top_non_compliant_controls_detail`](tools/dashboard/dashboard.py) | Get top non-compliant controls |
| [`fetch_unique_node_data_and_schema`](tools/graphdb/graphdb.py) | Fetch graph node data and schema |
| [`execute_cypher_query`](tools/graphdb/graphdb.py) | Execute Cypher query on graph |
| [`help`](tools/help/help.py) | Get help information |
| [`read_file`](tools/general/general.py) | Read local file content |
| [`read_resource`](tools/general/general.py) | Read resource URI content |
| [`create_downloadable_file`](tools/general/general.py) | Create downloadable file URL |

---

### Workflow Server Tools

| Tool | Description |
|------|-------------|
| [`list_workflow_event_categories`](tools/workflow/workflow.py) | List workflow event categories |
| [`list_workflow_events`](tools/workflow/workflow.py) | List available trigger events |
| [`list_workflow_activity_types`](tools/workflow/workflow.py) | List available activity types |
| [`list_workflow_function_categories`](tools/workflow/workflow.py) | List function categories |
| [`list_workflow_functions`](tools/workflow/workflow.py) | List available functions |
| [`list_workflow_tasks`](tools/workflow/workflow.py) | List available workflow tasks |
| [`list_workflow_condition_categories`](tools/workflow/workflow.py) | List condition categories |
| [`list_workflow_conditions`](tools/workflow/workflow.py) | List available conditions |
| [`list_workflow_predefined_variables`](tools/workflow/workflow.py) | List predefined variables |
| [`list_workflow_rules`](tools/workflow/workflow.py) | List available workflow rules |
| [`create_workflow`](tools/workflow/workflow.py) | Create workflow from YAML |
| [`list_workflows`](tools/workflow/workflow.py) | List all workflows |
| [`get_workflow_by_name`](tools/workflow/workflow.py) | Get workflow by name |
| [`fetch_workflow_details`](tools/workflow/workflow.py) | Fetch complete workflow details |
| [`modify_workflow`](tools/workflow/workflow.py) | Update workflow implementation |
| [`update_workflow_summary`](tools/workflow/workflow.py) | Update workflow description |
| [`update_workflow_mermaid_diagram`](tools/workflow/workflow.py) | Update workflow diagram |
| [`fetch_workflow_resource_data`](tools/workflow/workflow.py) | Fetch resource data for execution |
| [`create_workflow_custom_event`](tools/workflow/workflow.py) | Create custom trigger event |
| [`trigger_workflow`](tools/workflow/workflow.py) | Trigger workflow execution |
| [`fetch_workflow_rule`](tools/workflow/workflow.py) | Fetch workflow rule by name |
| [`fetch_task_readme`](tools/workflow/workflow.py) | Fetch task README |
| [`fetch_rule_readme`](tools/workflow/workflow.py) | Fetch rule README |

---

### Assistant Server Tools

| Tool | Description |
|------|-------------|
| [`create_assessment`](tools/assistant/assistant.py) | Create assessment from YAML |
| [`list_assessments`](tools/assistant/assistant.py) | List all assessments |
| [`list_assessment_control_configs`](tools/assistant/assistant.py) | List control configurations |
| [`create_control_config`](tools/assistant/assistant.py) | Create control configuration |
| [`update_control_config_contexts`](tools/assistant/assistant.py) | Update control context entities |
| [`attach_citation_to_control_config`](tools/assistant/assistant.py) | Attach citation to control |
| [`suggest_control_config_citations`](tools/assistant/assistant.py) | Suggest relevant citations |
| [`mark_control_ready_for_execution`](tools/assistant/assistant.py) | Mark control ready for execution |
| [`create_sql_query_evidence`](tools/assistant/assistant.py) | Create SQL-based evidence |
| [`list_sql_query_evidence`](tools/assistant/assistant.py) | List SQL evidence for control |
| [`update_sql_query_evidence`](tools/assistant/assistant.py) | Update SQL evidence |
| [`validate_sql_query`](tools/assistant/assistant.py) | Validate SQL query syntax |
| [`get_evidence_sample_data`](tools/assistant/assistant.py) | Get sample evidence data |
| [`fetch_control_source_summary`](tools/assistant/assistant.py) | Fetch evidence source summary |
| [`create_control_config_note`](tools/assistant/assistant.py) | Create control config note |
| [`list_control_config_notes`](tools/assistant/assistant.py) | List control config notes |
| [`update_control_config_note`](tools/assistant/assistant.py) | Update control config note |
| [`get_entity_hierarchy`](tools/assistant/assistant.py) | Get entity hierarchy |
| [`get_context_tables`](tools/assistant/assistant.py) | Get available context tables |
| [`fetch_rule_readme`](tools/assistant/assistant.py) | Fetch rule README |

---

## FAQ

**1. How do I sign up for ComplianceCow?**

Visit [ComplianceCow Signup](https://partner.compliancecow.live/ui/signup) to create an account using various sign-up options including Google, Microsoft, and OTP.

**2. What value does ComplianceCow deliver?**

ComplianceCow helps with automated security compliance evidence collection, analysis, and remediation challenges. It's a security GRC controls automation studio for custom controls and workflows. Learn more at [compliancecow.com](https://www.compliancecow.com/).

**3. Why are there 4 separate servers?**

MCP works best with fewer tools per server. Splitting into 4 servers (Rules, Insights, Workflow, Assistant) ensures optimal performance and allows you to enable only the tools you need for specific use cases.

**4. What if some tools have the same name across servers?**

Some tools share the same name but have different implementations. Enable only **one server at a time** to avoid conflicts. The tool behavior is determined by the `MCP_TOOLS_TO_BE_INCLUDED` env.

**5. How do I update the MCP server?**

```bash
cd /path/to/cow-mcp
git pull origin main
uv pip install .
```
Then restart your MCP host (Claude Desktop or Goose).

**6. Where can I get help?**

- Create an issue on [GitHub](https://github.com/ComplianceCow/cow-mcp/issues)
- Contact ComplianceCow support through the platform 