import base64
import os

from cachetools import TTLCache

headers = {"X-CALLER": "mcp_server-user_intent"}
cid = os.environ.get("CCOW_CLIENT_ID", "")
cs = os.environ.get("CCOW_CLIENT_SECRET", "")
t = os.environ.get("CCOW_TOKEN", "")
basic_auth_flow = False
if cid == "" or cs == "":
    headers["Authorization"] = t
else:
    basic_auth_flow = True
    headers["Authorization"]= "Basic " + base64.b64encode((cid + ":" + cs).encode("ascii")).decode("ascii")

host = os.environ.get("CCOW_HOST", "https://dev.compliancecow.live")
if not host.endswith("/api"):
    host += "/api"

ENABLE_CONTEXTUAL_VECTOR_SEARCH = os.environ.get("ENABLE_CONTEXTUAL_VECTOR_SEARCH", "false").lower() == "true"

# DASHBOARD
URL_CCF_DASHBOARD_CONTROL_DETAILS = "/v2/aggregator/ccf-dashboard-control-details"
URL_CCF_DASHBOARD_FRAMEWORK_SUMMARY = "/v2/aggregator/ccf-dashboard-framework-summary"
URL_CCF_DASHBOARD_REVIEW_PERIODS = "/v2/aggregator/fetch-ccf-dashboard-review-periods"


# ASSESSMENTS
URL_ASSESSMENT_CATEGORIES = "/v1/assessment-categories"
URL_PLANS = "/v1/plans"
URL_ASSESSMENTS = "/v1/assessments"
URL_GET_ASSESSMENT_CONTEXT = "/v1/servicenow/entities"

# ASSESSMENT CONTROLS
URL_PLAN_CONTROLS = "/v1/plan-controls"
URL_PLAN_CONTROLS_FETCH_SOURCE_SUMMARY = "/v1/plan-controls/fetch-source-summary"
URL_PLAN_CONTROLS_FETCH_SAMPLE_EVIDENCE_DATA = "/v1/plan-controls/fetch-sample-evidence-data"
URL_GET_SIMILAR_CONTROLS = "/v1/llm/get-similar-controls"
URL_PLAN_CONTROL_CITATIONS_BATCH = "/v1/plan-controls/assessment-control-citations/batch"
URL_PLANS_SYNC_CCFID = "/v1/plans/sync-ccfid"
URL_PLAN_CONTROL_NOTES = "/v1/plan-controls/{controlConfigId}/notes"

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

# WORKFLOW SPECS & BINDINGS
URL_WORKFLOW_SPECS = "/v2/workflow-specs"
URL_WORKFLOW_BINDINGS = "/v2/workflow-bindings"
URL_WORKFLOW_BINDINGS_EXECUTE = "/v2/workflow-bindings/execute"

URL_FETCH_TASK_README = "/pc-api/v1/tasks"
URL_FETCH_RULE_README = "/v1/rules"
URL_FETCH_FILE_BY_HASH = "/url-hash/download"


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
URL_UPDATE_RULE_TAGS = "/pc-api/v2/rules/update-tags"
URL_FETCH_RULES_AND_TASKS_SUGGESTIONS = "/v1/llm/rule-and-task/suggestions/fetch"

# TASK
URL_EXECUTE_TASK = "/pc-api/v1/tasks/execute-task"

# CC RULES
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

# SUPPORT TICKET
URL_CREATE_TICKET = "/v5/partner/support/ticket"

# AUTH-TOKEN GENERATION
URL_AUTH_TOKEN_GENERATION = "/v1/oauth2/token"

# cache support added
mcp_cache_ttl_in_seconds = int(os.getenv("MCP_CACHE_TTL_IN_SECONDS", "82800"))
cow_cache = TTLCache(maxsize=300, ttl=mcp_cache_ttl_in_seconds)
