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

host=os.environ.get('CCOW_HOST',"https://dev.compliancecow.live/api")



# URLS
API_OVERDUE_AND_NON_COMPLIANT_CONTROLS = "/v2/aggregator/ccf-dashboard-control-details" 

#ASSESSMENTS
API_LIST_ASSESSMENT_CATEGORIES = "/v1/assessment-categories"
API_LIST_ASSESSMENTS = "/v1/plans?page=1&page_size=10&fields=basic"


# ASSETS
API_LIST_ASSETS = "/v1/plans?fields=basic&type=integration"
API_FETCH_RESOURCES = "/v1/plan-instances/fetch-resources"
API_FETCH_RESOURCE_TYPES = "/v1/plan-instances/fetch-resource-types"
API_FETCH_ASSETS_DETAIL_SUMMARY = "/v1/plan-instances/fetch-integration-detail-summary"
API_FETCH_ASSETS_SUMMARY = "/v1/plan-instances/integration-summary"
API_FETCH_CHECKS = "/v1/plan-instances/fetch-checks"
