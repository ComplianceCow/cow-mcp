## Table of Contents

1. **ComplianceCow MCP Server**<br>
    1.1. [Introduction](#introduction)  
    1.2. [Glossary](#glossary)  
    1.3. [Architecture](#architecture)  
    1.4. [Getting Started](#getting-started)  
    1.4.1. [Dependencies](#dependencies)  
    1.4.2. [Authentication](#authentication)  
    1.4.3. [Configuration](#configuration)  
    1.4.4. [Usage in MCP Host](#usage-in-mcp-host)  
    1.4.5. [Running Locally](#running-locally)  
    1.5. [API Endpoints](#api-endpoints)



Model Context Protocol (MCP)
----------------------------


### Introduction


MCP servers are designed to process structured requests from AI agents, perform domain-specific operations (such as querying databases, applying business rules, or generating summaries), and return context-aware responses. Our implementation allows seamless integration with MCP-compatible hosts like Claude Desktop and Goose Desktop, enabling secure, modular, and intelligent interactions tailored to the needs of modern enterprises.

The tools and resources within the ComplianceCow MCP server are specifically designed to accomplish the following:

- Get Dashboard and Insights data
- Get Auditable responses through Compliance Graph
- Perform actions such as creating tickets, fixing policies, pushing data to external tools, etc


### Glossary


<table border="1" style="border-collapse: collapse; width: 100%; height: 442px;"><tbody><tr style="height: 24px;"><td style="width: 27.918%; height: 24px;">**Keyword**</td><td style="width: 36.041%; height: 24px;">**Description**</td><td style="width: 36.041%;">**Example(s)**</td></tr><tr style="height: 240px;"><td style="width: 27.918%; height: 240px;">Control</td><td style="width: 36.041%; height: 240px;"><span data-huuid="13667765555677333888">Refers to compliance or security control that needs to be implemented by an organization to ensure adherence to relevant laws, regulations, industry standards, and internal policies.</span></td><td style="width: 36.041%;"><span data-huuid="13667765555677333888">Ensure that MFA is enabled for all users</span></td></tr><tr style="height: 24px;"><td style="width: 27.918%; height: 24px;">Assessment</td><td style="width: 36.041%; height: 24px;">Assessment is a collection of controls, organized hierarchically. This can be an industry standard or a cybersecurity framework.</td><td style="width: 36.041%;">PCI DSS 4.0</td></tr><tr style="height: 48px;"><td style="width: 27.918%; height: 48px;">Assessment Run</td><td style="width: 36.041%; height: 48px;">An assessment run is the verification of the controls in an assessment for a given time period and for a set of inputs. This verification may include evidence either manually collecting from users or by automatically fetching data from resources such as applications and servers.</td><td style="width: 36.041%;"><span data-huuid="13667765555677333888"> </span></td></tr><tr style="height: 24px;"><td style="width: 27.918%; height: 24px;">Check</td><td style="width: 36.041%; height: 24px;">A rule or a verification for compliance or conformance.</td><td style="width: 36.041%;"><span data-huuid="13667765555677333888">Check if MFA is enabled for all AWS users in a given AWS account.</span></td></tr><tr style="height: 24px;"><td style="width: 27.918%; height: 24px;">Resource Type</td><td style="width: 36.041%; height: 24px;">Category or class of resources.</td><td style="width: 36.041%;">AWS EC2, AWS S3</td></tr><tr style="height: 24px;"><td style="width: 27.918%; height: 24px;">Resource</td><td style="width: 36.041%; height: 24px;"><span data-huuid="13667765555677333888">Instance of resource type for which we have checks performed.</span></td><td style="width: 36.041%;"><span data-huuid="13667765555677333888">Specific EC2 instances, Github repositories</span></td></tr><tr><td style="width: 27.918%;">Asset</td><td style="width: 36.041%;"><span data-huuid="13667765555677333888"> A group of resources of various types.</span></td><td style="width: 36.041%;"><span data-huuid="13667765555677333888">AWS services (spanning multiple accounts), Kubernetes, Github</span></td></tr><tr><td style="width: 27.918%;">Evidence</td><td style="width: 36.041%;">Data aggregated through checks against one or more resources, for a given control.</td><td style="width: 36.041%;"><span data-huuid="13667765555677333888">A CSV file containing the list of AWS users, their details including their MFA status and compliance details (such as score).</span></td></tr><tr style="height: 24px;"><td style="width: 27.918%; height: 24px;">Action</td><td style="width: 36.041%; height: 24px;">Any activity (automated or manual) that can be run to respond or to remediate based on conditions. These actions are bound to some specific resources such as assessment, control, evidence or resource in ComplianceCow.</td><td style="width: 36.041%;">Create a JIRA ticket for a non compliant EC2 instance with SLA not met for remediating a critical vulnerability.</td></tr></tbody></table>


### Architecture


We support the STDIO transport mechanism to allow seamless local integration of our server with your MCP host. At the core of our backend is the Compliance Graph, which continuously ingests data such as assessment runs, evidence, and more. Additionally, our server actively pulls information from diverse sources including vector stores, relational databases, and file storage systems.

<image src="https://www.compliancecow.com/wp-content/uploads/2025/06/Architecture.png" title="Architecture" align="center" />


### Getting Started

#### Dependencies

Python and UV (package manager) are required to run the MCP server.

- Visit [this](https://www.python.org/downloads/) page to download and install python for your operation system. Recommended version: 3.11 or higher.
- Visit [this](https://docs.astral.sh/uv/getting-started/installation/) page to download and install UV.

#### Authentication

The MCP tools and resources of ComplianceCow can be accessed through the <span>OAuth 2.0 mechanism with client\_credentials grant type</span>. Follow the instructions below to get yourself a client id and a secret.

1\. Sign up for an account (if you don’t have one) by visiting this URL: <https://partner.compliancecow.live/ui/signup>. Replace the hostname with your own if you have a dedicated ComplianceCow instance deployed.

2\. Click on the ‘Manage Client Credentials’ option in the top-right user profile menu.

3\. Fill out the form to obtain a client ID and secret.

#### Configuration

1\. Clone the git repo

> git clone https://github.com/ComplianceCow/cow-mcp.git

2\. Run the following commands to install the dependencies. Only then, the MCP Host will be able to start the MCP server successfully.

> <span data-teams="true">uv venv .venv</span>
> 
> <span data-teams="true">source .venv/bin/activate</span>
> 
> <span data-teams="true">uv pip install .</span>
> 
> <span data-teams="true"></span>
> 
> <span data-teams="true"></span>

3\. Use the following configuration JSON as a reference to update your MCP host. Before saving the configuration, make sure to update the highlighted fields and adjust the folder path syntax to match your operating system.

> MCP\_SERVER\_CODE\_PATH:- Replace with the repository path (cloned in a step above).
> 
> UV\_BIN\_PATH:- Replace with uv bin path (something like uv(Homebrew) or /Users/UserXYZ/.local/bin/uv(script) in MacOS)
> 
> CCOW\_CLIENT\_ID &amp; CCOW\_CLIENT\_SECRET: As explained in the “Authentication" section above.
> 
> CCOW\_HOST: You can replace the default hostname with the hostname of the dedicated ComplianceCow instance deployed for you.<span style="font-size: 16px;"> </span>


```{
  "mcpServers": {
    "ComplianceCow": {
      "args": [
        "--directory",
        "<<MCP_SERVER_CODE_PATH>>",
        "run",
        "main.py"
      ],
      "command": "<<UV_BIN_PATH>>",
      "env": {
        "CCOW_HOST": "https://partner.compliancecow.live/api",
        "CCOW_CLIENT_ID": "<<YOUR_CCOW_CLIENT_ID>>",
        "CCOW_CLIENT_SECRET": "<<YOUR_CCOW_CLIENT_SECRET>>"
      }
    }
  }
}
```


#### Usage in MCP Host

The usage of the MCP server may vary across different hosts. You can use the configuration data provided above by following the host-specific instructions. Instructions for two such hosts—Claude and Goose desktops—are provided below.

**Claude Desktop**: Update the config ( &lt;*Claude desktop installation path*&gt;/<span data-teams="true">claude\_desktop\_config.json</span>) of Claude desktop by following the instruction given above in the “Configuration" Section.

**Goose Desktop**: Follow the steps given in this [link](https://block.github.io/goose/docs/getting-started/using-extensions/#adding-extensions).

#### Running Locally

To verify that the MCP server is properly set up with all dependencies and can be started by the MCP host without issues, you can run the command to check if the server runs correctly in a local environment.  
<span data-teams="true"></span>

> <span data-teams="true">uv run main.py</span>


### API Endpoints


<span data-teams="true"><figure class="wp-block-table"><table class="has-fixed-layout"><thead><tr><th>Name</th><th>Purpose</th><th>Input(s)</th><th>Output(s)</th></tr></thead><tbody><tr><td>fetch\_unique\_node\_data\_and\_schema</td><td>Fetch unique node data and schema</td><td>**Question**\* (`string`)-user question</td><td>**node\_names** (`List`)-graph node names  
**unique\_property\_values** (`List`)-unique value of each property of nodes  
**neo4j\_schema** (`string`)-graph node schema details</td></tr><tr><td>execute\_cypher\_query</td><td>Given a question and query, execute a cypher query and transform result to human readable format. Args: query: query to execute in graph DB</td><td>**Query**\* (`string`)-query to execute in graph DB</td><td>**result** (`dict or str`)</td></tr><tr><td>list\_all\_assessment\_categories</td><td>Get all assessment categories</td><td></td><td>**result** (`list or str`)</td></tr><tr><td>list\_assessments</td><td>Get all assessments Function accepts category id as ‘categoryId’ and category name as ‘categoryName’</td><td>**Payload**\* (`object`)</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_recent\_assessment\_runs</td><td>Get recent assessment run for given assessment id Args: id: assessment id</td><td>**Id**\* (`string`)-assessment id</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_assessment\_runs</td><td>Get all assessment run for given assessment id Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize, default page is 1 If the request times out retry with pagination, increasing pageSize from 5 to 10. use this tool when expected run is got in fetch recent assessment runs tool Args: id: assessment id</td><td>**Id**\* (`string`)-assessment id  
**Page** (`integer`)  
**Pagesize** (`integer`)</td><td>**result** (`list or str`)</td></tr><tr><td>fetch\_assessment\_run\_details</td><td>Get assessment run details for given assessment run id. This api will return many contorls, use page to get details pagewise. If output is large store it in a file. Args: id: assessment run id</td><td>**Id**\* (`string`)-assessment run id</td><td>**result** (`list`)</td></tr><tr><td>fetch\_assessment\_available\_actions</td><td>Get actions available on assessment for given assessment name. Args: name: assessment name</td><td>**Name**\* (`string`)-assessment name</td><td>**result** (`list or str`)</td></tr><tr><td>execute\_action</td><td>Execute or trigger a specific action on an assessment run. use assessment id, assessment run id and action binding id. use fetch assessment available actions to get action binding id. Args: assessmentId assessmentRunId actionBindingId</td><td>**Assessmentid**\* (`string`)  
**Assessmentrunid**\* (`string`)  
**Actionbindingid**\* (`string`)</td><td>**result** (`dict or str`)</td></tr><tr><td>list\_integrations</td><td>Get all integrations</td><td></td><td>**result** (`list`)</td></tr><tr><td>fetch\_integration\_summary</td><td>Get integration summary for given assessment id Args: id: assessment id</td><td>**Id**\* (`string`)-assessment id</td><td>**result** (`dict`)</td></tr><tr><td>fetch\_resource\_types</td><td>Get resource types for given integration run id. Use ‘fetch\_integration\_summary’ tool to get integration run id Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize. If the request times out retry with pagination, increasing pageSize from 50 to 100. 1. Call fetch\_resource\_types with page=1, pageSize=50 2. Note the totalPages from the response 3. Continue calling each page until complete 4. Summarize all results together Args: id: integration run id</td><td>**Id**\* (`string`)-integration run id  
**Page** (`integer`)  
**Pagesize** (`integer`)</td><td>**result** (`dict`)</td></tr><tr><td>fetch\_checks</td><td>Get checks for given integration run id and resource type. Use this function to get all checks for given integration run id and resource type Use ‘fetch\_integration\_summary’ tool to get integration run id Use ‘fetch\_resource\_types’ tool to get all resource types Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize. If the request times out retry with pagination, increasing pageSize from 5 to 10. If the check data set is large to fetch efficiently or results in timeouts, it is recommended to use the ‘summary tool’ instead to get a summarized view of the checks. 1. Call fetch\_checks with page=1, pageSize=10 2. Note the totalPages from the response 3. Continue calling each page until complete 4. Summarize all results together Args: id: integration run id resourceType: resource type</td><td>**Id**\* (`string`)-integration run id  
**Resourcetype**\* (`string`)  
**Page** (`integer`)  
**Pagesize** (`integer`)</td><td>**result** (`dict or str`)</td></tr><tr><td>fetch\_resources</td><td>Get resources for given integration run id and resource type Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize, default page is 1 If the request times out retry with pagination, increasing pageSize from 5 to 10. If the resource data set is large to fetch efficiently or results in timeouts, it is recommended to use the ‘summary tool’ instead to get a summarized view of the resource. 1. Call fetch\_resources with page=1, pageSize=10 2. Note the totalPages from the response 3. Continue calling each page until complete 4. Summarize all results together Args: id: integration run id resourceType: resource type</td><td>**Id**\* (`string`)-integration run id  
**Resourcetype**\* (`string`)  
**Page** (`integer`)  
**Pagesize** (`integer`)</td><td>**result** (`dict or str`)</td></tr><tr><td>fetch\_resources\_with\_this\_check</td><td>Get checks for given integration run id, resource type and check Function accepts page number (page) and page size (pageSize) for pagination. If MCP client host unable to handle large response use page and pageSize. If the request times out retry with pagination, increasing pageSize from 10 to 50. If the resource data set is large to fetch efficiently or results in timeouts, it is recommended to use the ‘summary tool’ instead to get a summarized view of the resource. 1. Call fetch\_resources\_for\_check with page=1, pageSize=10 2. Note the totalPages from the response 3. Continue calling each page until complete 4. Summarize all results together Args: id: integration run id resourceType: resource type</td><td>**Id**\* (`string`)-integration run id  
**Resourcetype**\* (`string`)  
**Check**\* (`string`)  
**Page** (`integer`)  
**Pagesize** (`integer`)</td><td>**result** (`dict or str`)</td></tr><tr><td>get\_dashboard\_data</td><td>Function accepts compliance period as ‘period’. Period donates for which quarter of year dashboard data is needed. Format: Q1 2024. Dashboard contains summary data of Common Control Framework (CCF). For any related to contorl category, framework, assignment status use this function. This contains details of control status such as ‘Completed’, ‘In Progress’, ‘Overdue’, ‘Pending’. The summarization levels are ‘overall control status’, ‘control category wise’, ‘control framework wise’, ‘overall control status’ can be fetched from ‘controlStatus’ ‘control category wise’ can be fetched from ‘controlSummary’ ‘control framework wise’ can be fetched from ‘frameworks’</td><td>**Payload**\* (`object`)</td><td>**result** (`dict`)</td></tr><tr><td>fetch\_checks\_summary</td><td>Use this to get the summary on checks Use this when total items in ‘fetch\_checks’ is high Get checks summary for given integration run id and resource type. Get a summarized view of resources based on – Compliance breakdown for checks – Total Checks available – Total compliant checks – Total non-compliant checks Args: id: integration run id resourceType: resource type</td><td>**Id**\* (`string`)-integration run id  
**Resourcetype**\* (`string`)</td><td>**result** (`dict or str`)</td></tr><tr><td>fetch\_resources\_summary</td><td>Use this to get the summary on resource Use this when total items in ‘fetch\_resources’ is high Fetch a summary of resources for a given integration run id and resource type. Get a summarized view of resources include – Compliance breakdown for resource – Total Resources available – Total compliant resources – Total non-compliant resources Args: id: integration run ID resourceType: resource type</td><td>**Id**\* (`string`)-integration run ID  
**Resourcetype**\* (`string`)-resource type</td><td>**result** (`dict or str`)</td></tr><tr><td>fetch\_resources\_with\_this\_check\_summary</td><td>Use this to get the summary on check resources Use this when total items in ‘fetch\_resources\_for\_check’ is high Get check resources summary for given integration run id, resource type and check Paginated data is enough for summary Get a summarized view of check resources based on – Compliance breakdown for resources – Total Resources available – Total compliant resources – Total non-compliant resources Args: id: integration run id resourceType: resource type</td><td>**Id**\* (`string`)-integration run id  
**Resourcetype**\* (`string`)  
**Check**\* (`string`)</td><td>**result** (`dict or str`)</td></tr><tr><td>get\_top\_over\_due\_controls\_detail</td><td>Fetch controls with top over due (over-due) Function accepts count as ‘count’ Function accepts compliance period as ‘period’. Period donates for which quarter of year dashboard data is needed. Format: Q1 2024.</td><td>**Payload**\* (`object`)</td><td>**result** (`dict or str`)</td></tr><tr><td>get\_top\_non\_compliant\_controls\_detail</td><td>Fetch controls with low compliant score Function accepts count as ‘count’ Function accepts compliance period as ‘period’. Period donates for which quarter of year dashboard data is needed. Format: Q1 2024.</td><td>**Payload**\* (`object`)</td><td>**result** (`dict or str`)</td></tr></tbody></table>

</figure></span>
