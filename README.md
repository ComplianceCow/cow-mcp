## Table of Contents

1. **ComplianceCow MCP Server**  
    1.1. [Introduction](#introduction)  
    1.2. [Glossary](#glossary)  
    1.3. [Architecture](#architecture)  
    1.4. [Getting Started](#getting-started)  
&nbsp;&nbsp;&nbsp;&nbsp;1.4.1. [Dependencies](#dependencies)  
&nbsp;&nbsp;&nbsp;&nbsp;1.4.2. [Authentication](#authentication)  
&nbsp;&nbsp;&nbsp;&nbsp;1.4.3. [Server setup](#server-setup)  
&nbsp;&nbsp;&nbsp;&nbsp;1.4.4. [Server configuration](#server-configuration)  
&nbsp;&nbsp;&nbsp;&nbsp;1.4.5. [Examples](#examples)  
&nbsp;&nbsp;&nbsp;&nbsp;1.4.6. [Running Locally](#running-locally)  
    1.5. [API Endpoints](#api-endpoints)  
    1.6. [FAQ](#faq)



### Introduction

MCP servers are designed to process structured requests from AI agents, perform domain-specific operations (such as querying databases, applying business rules, or generating summaries), and return context-aware responses. Our implementation allows seamless integration with MCP-compatible hosts like Claude Desktop and Goose Desktop, enabling secure, modular, and intelligent interactions tailored to the needs of modern enterprises.

The tools and resources within the ComplianceCow MCP server are specifically designed to accomplish the following:

- Get Dashboard and Insights data
- Get Auditable responses through Compliance Graph
- Perform actions such as creating tickets, fixing policies, pushing data to external tools, etc


### Glossary


<table border="1" style="border-collapse: collapse; width: 100%; height: 442px;"><tbody><tr style="height: 24px;"><td style="width: 15%; height: 24px; text-align: center;">**Keyword**</td><td style="width: 36.041%; height: 24px; text-align: center;">**Description**</td><td style="width: 36.041%; text-align: center;">**Example(s)**</td></tr><tr style="min-height: 24px;"><td style="min-height: 24px; width: 15%; text-align: left;">**Control**</td><td style="width: 36.041%; min-height: 24px; text-align: left;"><span data-huuid="13667765555677333888">Refers to compliance or security control that needs to be implemented by an organization to ensure adherence to relevant laws, regulations, industry standards, and internal policies.</span></td><td style="width: 36.041%; text-align: left;"><span data-huuid="13667765555677333888">Ensure that MFA is enabled for all users</span></td></tr><tr style="height: 24px; text-align: left;"><td style="height: 24px; width: 15%;">**Assessment**</td><td style="width: 36.041%; height: 24px;">Assessment is a collection of controls, organized hierarchically. This can be an industry standard or a cybersecurity framework.</td><td style="width: 36.041%;">PCI DSS 4.0</td></tr><tr style="height: 48px; text-align: left;"><td style="height: 48px; width: 15%;">**Assessment Run**</td><td style="width: 36.041%; height: 48px;">An assessment run is the verification of the controls in an assessment for a given time period and for a set of inputs. This verification may include evidence either by manually collecting from users or by automatically fetching data from resources such as applications and servers.</td><td style="width: 36.041%;"><span data-huuid="13667765555677333888"> </span></td></tr><tr style="height: 24px; text-align: left;"><td style="height: 24px; width: 15%;">**Check**</td><td style="width: 36.041%; height: 24px;">A rule or a verification for compliance or conformance.</td><td style="width: 36.041%;"><span data-huuid="13667765555677333888">Check if MFA is enabled for all AWS users in a given AWS account</span></td></tr><tr style="height: 24px; text-align: left;"><td style="height: 24px; width: 15%;">**Resource Type**</td><td style="width: 36.041%; height: 24px;">Category or class of resources.</td><td style="width: 36.041%;">AWS EC2, AWS S3</td></tr><tr style="height: 24px; text-align: left;"><td style="height: 24px; width: 15%;">**Resource**</td><td style="width: 36.041%; height: 24px;"><span data-huuid="13667765555677333888">Instance of resource type for which we have checks performed.</span></td><td style="width: 36.041%;"><span data-huuid="13667765555677333888">Specific EC2 instances, Github repositories</span></td></tr><tr style="text-align: left;"><td style="width: 15%;">**Asset**</td><td style="width: 36.041%;"><span data-huuid="13667765555677333888"> A group of resources, of various types.</span></td><td style="width: 36.041%;"><span data-huuid="13667765555677333888">AWS services (spanning multiple accounts), Kubernetes, Github</span></td></tr><tr style="text-align: left;"><td style="width: 15%;">**Evidence**</td><td style="width: 36.041%;">Data aggregated through checks against one or more resources, for a given control.</td><td style="width: 36.041%;"><span data-huuid="13667765555677333888">A CSV file containing the list of AWS users, their details including their MFA status and compliance details (such as score).</span></td></tr><tr style="height: 24px; text-align: left;"><td style="height: 24px; width: 15%;">**Action**</td><td style="width: 36.041%; height: 24px;">Any activity (automated or manual) that can be run to respond or to remediate based on conditions. These actions are bound to some specific resources such as assessment, control, evidence or resource in ComplianceCow.</td><td style="width: 36.041%;">Create a JIRA ticket for a non compliant EC2 instance with SLA not met for remediating a critical vulnerability.</td></tr></tbody></table>


### Architecture


We support the STDIO transport mechanism to allow seamless local integration of our server with your MCP host. At the core of our backend is the Compliance Graph, which continuously ingests data such as assessment runs, evidence, and more. Additionally, our server actively pulls information from diverse sources including vector stores, relational databases, and file storage systems.


### Getting Started


#### Dependencies

1\. You’ll need an MCP host like Claude Desktop, Goose Desktop/CLI, or similar. Below are the installation links for Claude Desktop and Goose.

- [ Claude Desktop](https://claude.ai/download)
- [Goose Desktop/CLI](https://block.github.io/goose/docs/getting-started/installation/)

2\. Python and **uv** (package manager) are required to run the MCP server.

- Visit [this](https://www.python.org/downloads/) page to download and install python for your operating system. Recommended version: 3.11 or higher.
- Visit [this](https://docs.astral.sh/uv/getting-started/installation/) page to download and install **uv**.


#### Authentication

The MCP tools and resources of ComplianceCow can be accessed through the <span>OAuth 2.0 mechanism with client\_credentials grant type</span>. Follow the instructions below to get yourself a client ID and a secret.

1\. Sign up for an account (if you don’t have one) by visiting this URL: <https://partner.compliancecow.live/ui/signup>. Replace the hostname with your own if you have a dedicated ComplianceCow instance deployed.

2\. Click on the ‘Manage Client Credentials’ option in the top-right user profile menu.

3\. Fill out the form to obtain a client ID and a secret.


#### Server setup

1\. In your terminal/console, go to a folder of your choice and clone the git repo.

> ```
> git clone https://github.com/ComplianceCow/cow-mcp.git
> ```

2\. Switch to the repository’s main folder.

> ```
> cd cow-mcp
> ```

This directory will be referred to as **PATH\_TO\_THE\_MCP\_SERVER\_REPO\_CLONE** in the subsequent sections.

3\. Run the following commands to install the dependencies. Only then, the MCP Host will be able to start the MCP server successfully.

> ```
> uv venv .venv
> ```

> ```
> source .venv/bin/activate
> ```

> ```
> uv pip install .
> ```

#### Server configuration

Below are the key details required to configure our MCP server on your host.

<span style="text-decoration: underline;">**command**</span>

We use **uv** as the package manager. You can specify the **uv** command along with its path, which will be referred to as **`UV_BIN_PATH`** in the following sections. For example, on macOS: `/Users/UserXYZ/.local/bin/uv`.

<span style="text-decoration: underline;">**args**</span>

> ```
> −−directory <PATH_TO_THE_MCP_SERVER_REPO_CLONE> run main.py
> ```

PATH\_TO\_THE\_MCP\_SERVER\_REPO\_CLONE: The folder/path in which you have cloned the ComplianceCow MCP Github repo (in a step above). Example: /Users/UserXYZ/Documents/code/cow-mcp

<span style="text-decoration: underline;">**env**</span>

Our MCP server needs the following environment variables set:

- CCOW\_CLIENT\_ID: Please refer to the “Authentication” section above.
- CCOW\_CLIENT\_SECRET: Please refer to the “Authentication” section above.
- CCOW\_HOST: The hostname of the ComplianceCow instance, which could be a dedicated one for you or a default one such as ‘https://partner.compliancecow.live’.

The next section provides examples of how to use the above configuration values with Claude Desktop and Goose Desktop. For other hosts, you may refer to these examples as a guide for configuring accordingly.\[/et\_pb\_text\]\[et\_pb\_text \_builder\_version=”4.22.1″ \_module\_preset=”default” header\_4\_font=”|700|||||||” header\_4\_font\_size=”22px” header\_5\_font=”|700|||||||” header\_5\_font\_size=”20px” global\_colors\_info=”{}”\]


#### Examples

The steps to configure MCP servers may vary across different hosts. You can use the configuration data provided above by following the host-specific instructions. Instructions for two such hosts—Claude and Goose desktops—are provided below.

<span style="text-decoration: underline;">**Claude Desktop**</span>

Update the following json in the Claude desktop config file ( &lt;*Claude desktop installation path*&gt;/<span data-teams="true">claude\_desktop\_config.json</span>). Before saving the configuration, make sure to update these placeholders (as described in the section above) in the json: **PATH\_TO\_THE\_MCP\_SERVER\_REPO\_CLONE**, **UV\_BIN\_PATH**, **YOUR\_CCOW\_HOST**, **YOUR\_CCOW\_CLIENT\_ID and** **YOUR\_****CCOW\_CLIENT\_SECRET .**


```
{
  "mcpServers": {
    "ComplianceCow": {
      "args": [
        "--directory",
        "PATH_TO_THE_MCP_SERVER_REPO_CLONE",
        "run",
        "main.py"
      ],
      "command": "UV_BIN_PATH",
      "env": {
        "CCOW_HOST": "YOUR_CCOW_HOST",
        "CCOW_CLIENT_ID": "YOUR_CCOW_CLIENT_ID",
        "CCOW_CLIENT_SECRET": "YOUR_CCOW_CLIENT_SECRET"
      }
    }
  }
}
```

<span style="text-decoration: underline;">**Goose Desktop**</span>

Follow the steps given in this [link](https://block.github.io/goose/docs/getting-started/using-extensions/) to add our MCP server as a Goose extension.

#### Running Locally

To verify that the MCP server is properly set up with all dependencies and can be started by the MCP host without issues, you can run the command to check if the server runs correctly in a local environment.

> ```
> uv run main.py
> ```


### API Endpoints

<span data-teams="true"><figure class="wp-block-table"><table class="has-fixed-layout"><thead><tr><th>Name</th><th>Purpose</th><th>Input(s)</th><th>Output(s)</th></tr></thead><tbody><tr><td>list\_all\_assessment\_categories</td><td>Get all assessment categories</td><td></td><td>**result** (`list or str`)</td></tr><tr><td>list\_assessments</td><td>Get all assessments Args: categoryId: assessment category id (Optional) categoryName: assessment category name (Optional)</td><td>**Categoryid** (`string`)-assessment category id (Optional)  
**Categoryname** (`string`)</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_unique\_node\_data\_and\_schema</td><td>Fetch unique node data and schema</td><td>**Question**\* (`string`)-user question</td><td>**result**(`tuple[list, list, str]`)</td></tr><tr><td>execute\_cypher\_query</td><td>Given a question and query, execute a cypher query and transform result to human readable format. Args: query: query to execute in graph DB</td><td>**Query**\* (`string`)-query to execute in graph DB</td><td>**result** (`dict or str`)</td></tr><tr><td>fetch\_recent\_assessment\_runs</td><td>Get recent assessment run for given assessment id Args: id: assessment id</td><td>**Id**\* (`string`)-assessment id</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_assessment\_runs</td><td>Get all assessment run for given assessment id Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize, default page is 1 If the request times out retry with pagination, increasing pageSize from 5 to 10. use this tool when expected run is got in fetch recent assessment runs tool Args: id: assessment id</td><td>**Id**\* (`string`)-assessment id  
**Page** (`integer`)  
**Pagesize** (`integer`)</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_assessment\_run\_details</td><td>Get assessment run details for given assessment run id. This api will return many contorls, use page to get details pagewise. If output is large store it in a file. Args: id: assessment run id</td><td>**Id**\* (`string`)-assessment run id</td><td>**result**(`list`)</td></tr><tr><td>fetch\_assessment\_run\_leaf\_controls</td><td>Get leaf controls for given assessment run id. If output is large store it in a file. Args: id: assessment run id</td><td>**Id**\* (`string`)-assessment run id</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_run\_controls</td><td>use this tool when you there is no result from the tool “execute\_cypher\_query”. use this tool to get all controls that matches the given name. Next use fetch control meta data tool if need assessment name, assessment Id, assessment run name, assessment run Id Args: name: control name</td><td>**Name**\* (`string`)-control name</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_run\_control\_meta\_data</td><td>Use this tool to retrieve control metadata for a given `control_id`, including: – **Control details**: control name – **Assessment details**: assessment name and ID – **Assessment run details**: assessment run name and ID Args: id: control id</td><td>**Id**\* (`string`)-control id</td><td>**result** (`dict or str`)</td></tr><tr><td>fetch\_assessment\_run\_leaf\_control\_evidence</td><td>Get leaf control evidence for given assessment run control id. Args: id: assessment run control id</td><td>**Id**\* (`string`)-assessment run control id</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_controls</td><td>To fetch controls. Args: control\_name (str): name of the control. Using the control name</td><td>**Control Name** (`string`)</td><td>**result**(`dict`)</td></tr><tr><td>fetch\_evidence\_records</td><td>Get evidence record for given evidence id. Args: id: evidence id</td><td>**Id**\* (`string`)-evidence id</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_available\_control\_actions</td><td>This tool should be used for handling control-related actions such as create, update, or to retrieve available actions for a given control. If no control details are given use the tool “fetch\_controls” to get the control details. 1. Fetch the available actions. 2. Prompt the user to confirm the intended action. 3. Once confirmed, use the `execute_action` tool with the appropriate parameters to carry out the operation. ### Args: – `assessmentName`: Name of the assessment (**required**) – `controlNumber`: Identifier for the control (**required**) – `controlAlias`: Alias of the control (**required**) If the above arguments are not available: – Use the `fetch_controls` tool to retrieve control details. – Then generate and execute a query to fetch the related assessment information before proceeding.</td><td>**Assessmentname**\* (`string`)  
**Controlnumber** (`string`)  
**Controlalias** (`string`)  
**Evidencename** (`string`)</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_assessment\_available\_actions</td><td>Get **actions available on assessment** for given assessment name. Once fetched, ask user to confirm to execute the action, then use ‘execute\_action’ tool with appropriate parameters to execute the action. Args: name: assessment name</td><td>**Name** (`string`)-assessment name</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_evidence\_available\_actions</td><td>Get actions available on evidence for given evidence name. If the required parameters are not provided, use the existing tools to retrieve them. Once fetched, ask user to confirm to execute the action, then use ‘execute\_action’ tool with appropriate parameters to execute the action. Args: assessment\_name: assessment name (required) control\_number: control number (required) control\_alias: control alias (required) evidence\_name: evidence name (required)</td><td>**Assessment Name** (`string`)-assessment name (required)  
**Control Number** (`string`)  
**Control Alias** (`string`)  
**Evidence Name** (`string`)</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_automated\_controls\_of\_an\_assessment</td><td>To fetch the only the **automated controls** for a given assessment. If assessment\_id is not provided use other tools to get the assessment and its id. Args: – assessment\_id (str, required): assessment id or plan id.</td><td>**Assessment Id** (`string`)</td><td>**result**(`dict`)</td></tr><tr><td>execute\_action</td><td>Execute or trigger a specific action on an assessment run. use assessment id, assessment run id and action binding id. Execute or trigger a specific action on an control run. use assessment id, assessment run id, action binding id and assessment run control id . Execute or trigger a specific action on an evidence level. use assessment id, assessment run id, action binding id, assessment run control evidence id and evidence record ids. Use fetch assessment available actions to get action binding id. Only once action can be triggered at a time, assessment level or control level or evidence level based on user preference. Use this to trigger action for assessment level or control level or evidence level. Please also provide the intended effect when executing actions. Args: assessmentId assessmentRunId actionBindingId assessmentRunControlId – needed for control level action assessmentRunControlEvidenceId – needed for evidence level action evidenceRecordIds – needed for evidence level action</td><td>**Assessmentid**\* (`string`)  
**Assessmentrunid**\* (`string`)  
**Actionbindingid**\* (`string`)  
**Assessmentruncontrolid**(`string`)  
**Assessmentruncontrolevidenceid**(`string`)  
**Evidencerecordids** (`array`)</td><td>**result** (`dict or str`)</td></tr><tr><td>get\_dashboard\_data</td><td>Function accepts compliance period as ‘period’. Period denotes for which quarter of year dashboard data is needed. Format: Q1 2024. Dashboard contains summary data of Common Control Framework (CCF). For any related to contorl category, framework, assignment status use this function. This contains details of control status such as ‘Completed’, ‘In Progress’, ‘Overdue’, ‘Pending’. The summarization levels are ‘overall control status’, ‘control category wise’, ‘control framework wise’, ‘overall control status’ can be fetched from ‘controlStatus’ ‘control category wise’ can be fetched from ‘controlSummary’ ‘control framework wise’ can be fetched from ‘frameworks’ Args: – period (str, required) – Period denotes for which quarter of year dashboard data is needed. Format: Q1 2024.</td><td>**Period** (`string`)</td><td>**result**(`dict`)</td></tr><tr><td>fetch\_dashboard\_framework\_controls</td><td>\### Function Overview: Retrieve Control Details for a Given CCF and Review Period This function retrieves detailed control-level data for a specified **Common Control Framework (CCF)** during a specific **review period**. #### Parameters – **`review_period`**: The compliance period (typically a quarter) for which the control-level data is requested. **Format**: `"Q1 2024"` – **`framework_name`**: The name of the Common Control Framework to fetch data for. #### Purpose This function is used to fetch a list of controls and their associated data for a specific CCF and review period. It does not return an aggregated overview — instead, it retrieves detailed, item-level data for each control via an API call. The results are displayed in the MCP host with **client-side pagination**, allowing users to navigate through the control list efficiently without making repeated API calls. #### Output Fields Each control entry in the output includes the following attributes: – **Name** — from `controlName` – **Assigned To** — extracted from the email ID in `lastAssignedTo`, if available – **Assignment Status**— from `status`, if available – **Compliance Status** — from `complianceStatus` – **Due Date**— from `dueDate` – **Score** — from `score` – **Priority** — from `priority`</td><td>**Period**\* (`string`)  
**Framework Name**\* (`string`)</td><td>**result**(`dict`)</td></tr><tr><td>fetch\_dashboard\_framework\_summary</td><td>\### Function Overview: CCF Dashboard Summary Retrieval This function returns a summary dashboard for a specified **compliance period** and **Common Control Framework (CCF)**. It is designed to provide a high-level view of control statuses within a given framework and period, making it useful for compliance tracking, reporting, and audits. #### Parameters – **`period`**: The compliance quarter for which the dashboard data is requested. **Format**: `"Q1 2024"` – **`framework_name`**: The name of the Common Control Framework whose data is to be retrieved. #### Dashboard Overview The dashboard provides a consolidated view of all controls under the specified framework and period. It includes key information such as assignment status, compliance progress, due dates, and risk scoring to help stakeholders monitor and manage compliance posture. #### Output Fields Each control entry in the output includes the following attributes: – **Name** — from `controlName` – **Assigned To** — extracted from the email ID in `lastAssignedTo`, if available – **Assignment Status** — from `status`, if available – **Compliance Status** — from `complianceStatus` – **Due Date**— from `dueDate` – **Score** — from `score` – **Priority** — from `priority`</td><td>**Period**\* (`string`)  
**Framework Name**\* (`string`)</td><td>**result**(`dict`)</td></tr><tr><td>get\_dashboard\_common\_controls\_details</td><td>Function accepts compliance period as ‘period’. Period donates for which quarter of year dashboard data is needed. Format: Q1 2024. Use this tool to get Common Control Framework (CCF) dashboard data for a specific compliance period with filters. This function provides detailed information about common controls, including their compliance status, control status, and priority. Use pagination if controls count is more than 50 then use page and pageSize to get control data pagewise, Once 1st page is fetched,then more pages available suggest to get next page data then increase page number. Args: period (str): Compliance period for which dashboard data is needed. Format: ‘Q1 2024’. (Required) complianceStatus (str): Compliance status filter (Optional, possible values: ‘COMPLIANT’, ‘NON\_COMPLIANT’, ‘NOT\_DETERMINED”). Default is empty string (fetch all Compliance statuses). controlStatus (str): Control status filter (Optional, possible values: ‘Pending’, ‘InProgress’, ‘Completed’, ‘Unassigned’, ‘Overdue’). Default is empty string (fetch all statuses). priority (str): Priority of the controls. (Optional, possible values: ‘High’, ‘Medium’, ‘Low’). Default is empty string (fetch all priorities). controlCategoryName (str): Control category name filter (Optional). Default is empty string (fetch all categories). page (int): Page number for pagination (Optional). Default is 1 (fetch first page). pageSize (int): Number of items per page (Optional). Default is 50.</td><td>**Period**\* (`string`)  
**Compliancestatus** (`string`)  
**Controlstatus** (`string`)  
**Priority** (`string`)  
**Controlcategoryname** (`string`)  
**Page** (`integer`)  
**Pagesize** (`integer`)</td><td>**result**(`dict`)</td></tr><tr><td>get\_top\_over\_due\_controls\_detail</td><td>Fetch controls with top over due (over-due) Function accepts count as ‘count’ Function accepts compliance period as ‘period’. Period donates for which quarter of year dashboard data is needed. Format: Q1 2024. Args: – period (str, required) – Compliance period – count (int, required) – page content size, defaults to 10</td><td>**Period** (`string`)  
**Count** (`integer`)</td><td>**result** (`dict or str`)</td></tr><tr><td>get\_top\_non\_compliant\_controls\_detail</td><td>Function overview: Fetch control with low compliant score or non compliant controls. Arguments: 1. period: Compliance period which denotes quarter of the year whose dashboard data is needed. By default: Q1 2024. 2. count: 3. page: If the user asks of next page use smartly decide the page.</td><td>**Period**\* (`string`)  
**count** (`string`)  
**page** (`string`)</td><td>**result** (`dict or str`)</td></tr><tr><td>list\_assets</td><td>Get all assets</td><td></td><td>**result**(`list`)</td></tr><tr><td>fetch\_assets\_summary</td><td>Get assets summary for given assessment id Args: id: assessment id</td><td>**Id**\* (`string`)-assessment id</td><td>**result**(`dict`)</td></tr><tr><td>fetch\_resource\_types</td><td>Get resource types for given asset run id. Use ‘fetch\_assets\_summary’ tool to get assets run id Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize. If the request times out retry with pagination, increasing pageSize from 50 to 100. 1. Call fetch\_resource\_types with page=1, pageSize=50 2. Note the totalPages from the response 3. Continue calling each page until complete 4. Summarize all results together Args: id: asset run id</td><td>**Id**\* (`string`)-asset run id  
**Page** (`integer`)  
**Pagesize** (`integer`)</td><td>**result**(`dict`)</td></tr><tr><td>fetch\_checks</td><td>Get checks for given assets run id and resource type. Use this function to get all checks for given assets run id and resource type Use ‘fetch\_assets\_summary’ tool to get asset run id Use ‘fetch\_resource\_types’ tool to get all resource types Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize. If the request times out retry with pagination, increasing pageSize from 5 to 10. If the check data set is large to fetch efficiently or results in timeouts, it is recommended to use the ‘summary tool’ instead to get a summarized view of the checks. 1. Call fetch\_checks with page=1, pageSize=10 2. Note the totalPages from the response 3. Continue calling each page until complete 4. Summarize all results together Args: id: asset run id resourceType: resource type complianceStatus</td><td>**Id**\* (`string`)-asset run id  
**Resourcetype**\* (`string`)  
**Page** (`integer`)  
**Pagesize** (`integer`)  
**Compliancestatus** (`string`)</td><td>**result** (`dict or str`)</td></tr><tr><td>fetch\_resources</td><td>Get resources for given asset run id and resource type Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize, default page is 1 If the request times out retry with pagination, increasing pageSize from 5 to 10. If the resource data set is large to fetch efficiently or results in timeouts, it is recommended to use the ‘summary tool’ instead to get a summarized view of the resource. 1. Call fetch\_resources with page=1, pageSize=10 2. Note the totalPages from the response 3. Continue calling each page until complete 4. Summarize all results together Args: id: asset run id resourceType: resource type complianceStatus</td><td>**Id**\* (`string`)-asset run id  
**Resourcetype**\* (`string`)  
**Page** (`integer`)  
**Pagesize** (`integer`)  
**Compliancestatus** (`string`)</td><td>**result** (`dict or str`)</td></tr><tr><td>fetch\_resources\_with\_this\_check</td><td>Get checks for given asset run id, resource type and check Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize. If the request times out retry with pagination, increasing pageSize from 10 to 50. If the resource data set is large to fetch efficiently or results in timeouts, it is recommended to use the ‘summary tool’ instead to get a summarized view of the resource. 1. Call fetch\_resources\_for\_check with page=1, pageSize=10 2. Note the totalPages from the response 3. Continue calling each page until complete 4. Summarize all results together Args: id: asset run id resourceType: resource type</td><td>**Id**\* (`string`)-asset run id  
**Resourcetype**\* (`string`)  
**Check**\* (`string`)  
**Page** (`integer`)  
**Pagesize** (`integer`)</td><td>**result** (`dict or str`)</td></tr><tr><td>fetch\_checks\_summary</td><td>Use this to get the summary on checks Use this when total items in ‘fetch\_checks’ is high Get checks summary for given asset run id and resource type. Get a summarized view of resources based on – Compliance breakdown for checks – Total Checks available – Total compliant checks – Total non-compliant checks Args: id: asset run id resourceType: resource type</td><td>**Id**\* (`string`)-asset run id  
**Resourcetype**\* (`string`)</td><td>**result** (`dict or str`)</td></tr><tr><td>fetch\_resources\_summary</td><td>Use this to get the summary on resource Use this when total items in ‘fetch\_resources’ is high Fetch a summary of resources for a given asset run id and resource type. Get a summarized view of resources include – Compliance breakdown for resource – Total Resources available – Total compliant resources – Total non-compliant resources Args: id: asset run ID resourceType: resource type</td><td>**Id**\* (`string`)-asset run ID  
**Resourcetype**\* (`string`)-resource type</td><td>**result** (`dict or str`)</td></tr><tr><td>fetch\_resources\_with\_this\_check\_summary</td><td>Use this to get the summary on check resources Use this when total items in ‘fetch\_resources\_for\_check’ is high Get check resources summary for given asset run id, resource type and check Paginated data is enough for summary Get a summarized view of check resources based on – Compliance breakdown for resources – Total Resources available – Total compliant resources – Total non-compliant resources Args: id: asset run id resourceType: resource type</td><td>**Id**\* (`string`)-asset run id  
**Resourcetype**\* (`string`)  
**Check**\* (`string`)</td><td>**result** (`dict or str`)</td></tr></tbody></table>

</figure></span>

### FAQ

**1. How do I signup for ComplianceCow?**

Visit our [product site](https://demo.partner.compliancecow.live/ui/signup) to create an account using various sign-up options, including Google, Microsoft, OTP, and more.

**2. What value does ComplianceCow deliver?**

ComplianceCow is designed to help with automated security compliance evidence collection, analysis and remediation challenges faced by large enterprises and compliance, GRC and security teams. We are a security GRC controls automation studio for your custom controls and workflows. For more information, please visit our [corporate site](https://www.compliancecow.com/).
