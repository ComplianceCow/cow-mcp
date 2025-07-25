import os
import base64


headers={"X-CALLER":"mcp_server-user_intent"}
cid=os.environ.get('CCOW_CLIENT_ID',"")
cs=os.environ.get('CCOW_CLIENT_SECRET',"")
t=os.environ.get('CCOW_TOKEN',"710ffde6-43ac-4ac0-b5ce-d4f606e5e45f")
if cid == "" or cs == "" :
    headers={"Authorization": t}
else :
    headers={"Authorization": "Basic "+base64.b64encode((cid+":"+cs).encode("ascii")).decode("ascii")}

host=os.environ.get('CCOW_HOST',"https://dev.compliancecow.live")
if not host.endswith("/api"):
    host += "/api"


# DASHBOARD
URL_CCF_DASHBOARD_CONTROL_DETAILS= "/v2/aggregator/ccf-dashboard-control-details" 
URL_CCF_DASHBOARD_FRAMEWORK_SUMMARY = "/v2/aggregator/ccf-dashboard-framework-summary"


#ASSESSMENTS
URL_ASSESSMENT_CATEGORIES = "/v1/assessment-categories"
URL_PLANS = "/v1/plans"

# ASSESSMENT CONTROLS
URL_PLAN_CONTROLS = "/v1/plan-controls"

# ASSESSMENT RUNS
URL_PLAN_INSTANCES = "/v1/plan-instances"
URL_PLAN_INSTANCE_CONTROLS = "/v1/plan-instance-controls"
URL_PLAN_INSTANCE_EVIDENCES = "/v1/plan-instance-evidences"

URL_DATAHANDLER_FETCH_DATA = "/v1/datahandler/fetch-data" 

#ACTIONS
URL_FETCH_AVAILABLE_ACTIONS = "/v1/actions/fetch-available-actions"
URL_ACTIONS_EXECUTIONS = "/v1/actions/executions"


#GRAPHDB
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
URL_WORKFLOW_PREBUILD_RULES= "/v1/rules?name_contains=fet"
