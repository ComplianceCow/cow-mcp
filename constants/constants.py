import os
import base64


headers = {"X-CALLER": "mcp_server-user_intent"}
cid = os.environ.get('CCOW_CLIENT_ID', "")
cs = os.environ.get('CCOW_CLIENT_SECRET', "")
t = os.environ.get('CCOW_TOKEN', "710ffde6-43ac-4ac0-b5ce-d4f606e5e45f")
if cid == "" or cs == "":
    headers = {"Authorization": t}
else:
    headers = {"Authorization": "Basic " +
               base64.b64encode((cid+":"+cs).encode("ascii")).decode("ascii")}

host = os.environ.get('CCOW_HOST', "https://dev.compliancecow.live")
if not host.endswith("/api"):
    host += "/api"


# DASHBOARD
URL_CCF_DASHBOARD_CONTROL_DETAILS = "/v2/aggregator/ccf-dashboard-control-details"
URL_CCF_DASHBOARD_FRAMEWORK_SUMMARY = "/v2/aggregator/ccf-dashboard-framework-summary"


# ASSESSMENTS
URL_ASSESSMENT_CATEGORIES = "/v1/assessment-categories"
URL_PLANS = "/v1/plans"

# ASSESSMENT CONTROLS
URL_PLAN_CONTROLS = "/v1/plan-controls"

# ASSESSMENT RUNS
URL_PLAN_INSTANCES = "/v1/plan-instances"
URL_PLAN_INSTANCE_CONTROLS = "/v1/plan-instance-controls"
URL_PLAN_INSTANCE_EVIDENCES = "/v1/plan-instance-evidences"

URL_DATAHANDLER_FETCH_DATA = "/v1/datahandler/fetch-data"

# ACTIONS
URL_FETCH_AVAILABLE_ACTIONS = "/v1/actions/fetch-available-actions"
URL_ACTIONS_EXECUTIONS = "/v1/actions/executions"


# GRAPHDB
URL_RETRIEVE_UNIQUE_NODE_DATA_AND_SCHEMA = "/v1/llm/retrieve_unique_node_data_and_schema"
URL_EXECUTE_CYPHER_QUERY = "/v1/llm/execute_cypher_query"
URL_RETRIEVE_GRAPH_SCHEMA_RELATIONSHIP = "/v1/llm/retrieve_schema_and_relationship"


# ASSETS
URL_ASSETS = URL_PLANS + "?fields=basic&type=integration"
URL_FETCH_RESOURCES = "/v1/plan-instances/fetch-resources"
URL_FETCH_RESOURCE_TYPES = "/v1/plan-instances/fetch-resource-types"
URL_FETCH_ASSETS_DETAIL_SUMMARY = "/v1/plan-instances/fetch-integration-detail-summary"
URL_FETCH_ASSETS_SUMMARY = "/v1/plan-instances/integration-summary"
URL_FETCH_CHECKS = "/v1/plan-instances/fetch-checks"


# WORKFLOW

URL_WORKFLOW_EVENT_CATEGORIES = "/v1/workflow-catalog/event-categories"
URL_WORKFLOW_EVENTS = "/v1/workflow-catalog/events"
URL_WORKFLOW_ACTIVITY_CATEGORIES = "/v1/workflow-catalog/activity-categories"
URL_WORKFLOW_ACTIVITIES = "/v1/workflow-catalog/activities"
URL_WORKFLOW_CONDITION_CATEGORIES = "/v1/workflow-catalog/condition-categories"
URL_WORKFLOW_CONDITIONS = "/v1/workflow-catalog/conditions"
URL_WORKFLOW_PREBUILD_TASKS = "/v1/workflow-catalog/tasks"
URL_WORKFLOW_PREBUILD_RULES = "/v1/rules"
URL_WORKFLOW_PREDEFINED_VARIABLES = "/v1/workflow-catalog/predefined-variables"

URL_WORKFLOW_CREATE = "/v3/workflow-configs"

URL_WORKFLOW_RESOURCE_DATA = "/v2/aggregator/fetch-resource-data"


# RULES
MCP_GET_RULES_TAG = "MCP"
URL_FETCH_RULES = "/v5/partner/pc/rules"
URL_FETCH_TASKS = "/pc-api/v1/tasks"
URL_CREATE_RULE = "/pc-api/v2/rules"
URL_EXECUTE_RULE = "/pc-api/v2/rules/execute-rule"
URL_FETCH_EXECUTION_PROGRESS = "/pc-api/v2/rules/fetch-execution-progress"
URL_FETCH_FILE = "/pc-api/v1/storage/fetch-file"
URL_PUBLISH_RULE = "/pc-api/v1/rules/publish-rule"
URL_FETCH_CC_RULES = "/pc-api/v1/rules/fetch-cc-rules"
URL_UPDATE_RULE_TAGS ="/v5/partner/pc/rules/update-tags"

#CC RULES
URL_GET_CC_RULE = "/v1/rules"
URL_GET_CC_RULE_BY_ID = "/v1/rules/{id}"
URL_LINK_CC_RULE_TO_CONTROL = "/v1/plan-controls/{control_id}/link-rule"

# STORAGE
URL_UPLOAD_FILE = "/pc-api/v1/storage/upload-file"

# DESIGN NOTES
URL_SAVE_DESIGN_NOTES = "/pc-api/v1/design-notes/save-file"
URL_FETCH_DESIGN_NOTES = "/pc-api/v1/design-notes/fetch-file"

# README
URL_SAVE_RULE_README = "/pc-api/v2/rules/upsert-readme"

# CREDENTIAL
URL_FETCH_CREDENTIAL = "/v1/credential"
URL_FETCH_APPLICATION_CREDENTIALS = "/pc-api/v1/application-credentials"
URL_FETCH_APPLICATIONS = "/pc-api/v1/applications"
URL_PUBLISH_APPLICATIONS = "/pc-api/v1/applications/publish-application"
URL_FETCH_CC_APPLICATIONS = "/pc-api/v1/applications/fetch-cc-applications"

#SUPPORT TICKET
URL_CREATE_TICKET = "/v5/partner/support/ticket"
