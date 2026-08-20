import json
import traceback

from utils import utils
from utils.debug import logger
from mcpconfig.config import mcp

from constants import constants
from mcptypes import assets_tools_type as vo
from fastmcp import Context


@mcp.tool()
async def list_application_types(name: str | None = None, version: str | None = None, ctx: Context | None = None) -> dict:

    """
    Recommend and retrieve ComplianceCow application types based on the user's integration requirements.

    -------------------------------------------------------------------------
    PURPOSE
    -------------------------------------------------------------------------

    This tool is the first step whenever a user wants to create a new
    ComplianceCow application.

    Users are NOT expected to know ComplianceCow application type names.

    Instead of asking users to choose from internal application types,
    first understand what they are trying to connect and what they want
    to accomplish.

    Use the returned application's shortDescription and longDescription
    to identify the application type that best matches the user's
    requirement.

    -------------------------------------------------------------------------
    WHEN TO CALL
    -------------------------------------------------------------------------

    Always call this tool before creating an application.

    -------------------------------------------------------------------------
    USER REQUIREMENT DETECTION
    -------------------------------------------------------------------------

    Determine whether the user's request already identifies the intended
    application type.

    Examples

    • Connect AWS
    • Create GitHub application
    • Connect Okta
    • Connect Salesforce
    • Connect Jira
    • Connect REST API

    If the user clearly identifies a specific platform, service,
    product, or technology:

    • Do NOT ask additional discovery questions.
    • Call this tool.
    • Compare the returned application types.
    • If exactly one application type is the best match,
    recommend only that application type.
    • Explain why it matches the user's requirement.
    • Ask for confirmation before continuing.
    • After the user confirms the application type, invoke
    list_applications() to determine whether a suitable application of
    this type already exists.
    • Do not immediately continue with create_application().

    Examples

    "Connect AWS"
    → Recommend AWS Connector

    "Connect GitHub"
    → Recommend GitHub Connector

    "Connect REST API"
    → Recommend API Connector

    Do NOT perform broad recommendations when a single application
    type is clearly identified.

    -------------------------------------------------------------------------

    If the user's request is ambiguous

    Examples

    • Microsoft
    • Google
    • Cloud
    • Database

    Determine the best matching application types.

    Present at most the top three recommendations.

    Explain the differences before asking the user to choose.

    -------------------------------------------------------------------------

    If multiple returned application types represent different ways
    of connecting the same platform, explain the purpose of each.

    Example

    AWS Connector
    Connect a single AWS account.

    AWS Organization Connector
    Connect multiple AWS accounts managed through AWS Organizations.

    AWS Security Hub Connector
    Integrate with AWS Security Hub findings.

    -------------------------------------------------------------------------
    WORKFLOW
    -------------------------------------------------------------------------

    Case 1 - User has not yet described what they want to connect

    Example

    User:
        Create an application.

    Assistant:

    Do NOT immediately present application types.

    Instead, understand the user's goal.

    Ask what system, service, platform, or application they want
    to connect and what they want to accomplish.

    Provide a few simple examples.

    Examples

    • Connect an AWS, Azure, or GCP cloud account
    • Integrate with GitHub, GitLab, or Bitbucket
    • Connect an identity provider such as Okta or Microsoft Entra ID
    • Connect a REST API or another third-party application

    Do NOT ask the user to choose an application type at this stage.

    Wait until the user describes their requirement before calling
    this tool.
    
    **IMPORTANT** Provide a few simple examples with detailed explanation to user to understand better.
    **IMPORTANT** At the end ask the user to describes their requirement

    -------------------------------------------------------------------------

    Case 2 - User describes their requirement

    Examples

    "I want to connect GitHub."

    "I need to connect a REST API."

    "I want to scan my AWS account."

    "I want to integrate Microsoft 365."

    Call this tool without specifying an application name.

    Retrieve every available application type.

    Compare the user's requirement against

    • shortDescription
    • longDescription

    Estimate how well each application type satisfies the user's
    requirement.
    
    Once the best matching application type has been determined and
    confirmed by the user, invoke list_applications() before creating a new
    application.

    This helps identify existing applications that can be reused, edited, or
    validated, avoiding unnecessary duplicate applications.

    -------------------------------------------------------------------------
    RECOMMENDATION
    -------------------------------------------------------------------------

    Do NOT expose internal descriptions verbatim.

    Summarize recommendations in simple business language.

    If one application type is clearly the best match:

    • Recommend only that application.
    • Explain why it matches the user's goal.
    • Explain the recommendation using business language,
    not technical implementation details.
    • Ask whether the user would like to continue.

    Example

    "Based on your requirement, API Connector appears to be the
    best match because it is designed to securely connect REST APIs,
    which matches your requirement to integrate with a third-party
    service."

    Do NOT continue without confirmation.

    -------------------------------------------------------------------------

    If multiple application types are relevant:

    Present at most the top three ranked recommendations.

    For each recommendation include

    • Display Name
    • Short explanation
    • Why it matches the user's requirement

    Explain the differences between them.

    Wait for the user to choose one.

    -------------------------------------------------------------------------

    If no good recommendation exists:

    Inform the user that no strong match was found.

    Present the complete list of available application types for
    manual selection.

    -------------------------------------------------------------------------
    AFTER APPLICATION SELECTION
    -------------------------------------------------------------------------

    Once an application type has been confirmed:

    Invoke list_applications() to determine whether one or more existing
    applications already use the selected application type.

    If matching applications are found,

    • Present a concise summary of each application including
    • Credential Name
    • Application URL
    • Validation Status

    • Recommend reusing validated applications whenever appropriate.

    • Allow the user to choose whether to
    • Reuse an existing application
    • Edit or validate an existing application
    • Create a new application

    If the user chooses to edit or validate an existing application,

    Provide the application's redirect URL and explain that the application
    must be configured and successfully validated before it can be used in
    future Assessments, Rule executions, Workflows, or other ComplianceCow
    operations.

    If the user chooses to reuse an existing validated application,

    Continue with the existing application.

    If the application will be used in an Assessment, ask whether the user
    would like to create an Application Scope.

    Do not invoke create_application().

    If no suitable application exists, or if the user explicitly chooses to
    create a new application,

    Retrieve the selected application's complete configuration.

    Read

    status.internal.credentialTypes

    If multiple credential types are available,

    Explain each authentication method before asking the user to choose one.

    Never guess the credential type.

    -------------------------------------------------------------------------
    IMPORTANT
    -------------------------------------------------------------------------

    Never assume the application type.

    Never invent an application type that was not returned by
    this tool.

    Recommendations must always be based on the returned
    application types.

    Always base recommendations on

    • shortDescription
    • longDescription

    Prefer the application's displayName when communicating with
    the user.

    Do not expose internal application names unless they are
    identical to the display name.

    Do not repeat shortDescription or longDescription verbatim.

    Summarize the recommendation in simple business language.

    Never overwhelm the user with every available application
    type.

    Behave like a recommendation assistant, not a catalog browser.

    Present the complete list only when no meaningful recommendation
    can be made.

    Only continue after the user explicitly confirms the selected
    application type.
    Always check for existing applications using list_applications() before
    invoking create_application().

    Avoid creating duplicate applications whenever a suitable existing
    application can be reused.

    """
    try:
        logger.info("list_application_types")
        query_params = {
            "validApplication": "true",
        }

        if name:
            query_params["name"] = name
            query_params["isStatusToBeIncluded"] = "true"

        if version:
            query_params["version"] = version

        logger.debug("query params : %s", json.dumps(query_params))
        output = await utils.make_GET_API_call_to_CCow(
            constants.URL_APPLICATION_CONFIGS,
            ctx=ctx,
            query_params=query_params,
        )

        logger.debug("output : %s", json.dumps(output))
        if isinstance(output, str) or "error" in output:
            logger.error("list_application_types error : %s",output)
            return {
                "error": "Facing internal error"
            }

        items = output.get("items", [])
        if name or version:
            if not items:
                return {
                    "error": "Application type not found"
                }
            return items[0]

        application_types = [
            {
                "name": item.get("meta", {}).get("name", ""),
                "displayName": item.get("meta", {}).get("displayName", ""),
                "shortDescription": item.get("meta", {}).get("shortDescription", ""),
                "longDescription": item.get("meta", {}).get("longDescription", ""),
            }
            for item in items
        ]

        return {
            "applicationTypes": application_types
        }

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_application_types error : %s", e)
        return {
            "error": "Facing internal error"
        }


@mcp.tool()
async def fetch_credential_config(name: str,version: str,ctx: Context | None = None) -> dict:
    
    """
    Retrieve the credential configuration required to create a ComplianceCow application.
    
    Call this tool only after a single credential type has been determined. If multiple credential types are available, 
    present them to the user and wait for a selection before invoking this tool.

    -------------------------------------------------------------------------
    PURPOSE
    -------------------------------------------------------------------------

    Every application type supports one or more credential types.

    This tool is used to retrieve the credential configuration for the
    selected application.

    This tool does not collect credential values from the user.

    Its purpose is to determine which credential type should be used and
    retrieve the corresponding credential schema required for application
    creation.

    -------------------------------------------------------------------------
    WHEN TO CALL
    -------------------------------------------------------------------------

    Always call this tool after a single application type has been selected.

    The selected application configuration contains
        status.internal.credentialTypes

    Call this tool using the credential type selected from that list.

    -------------------------------------------------------------------------
    WORKFLOW
    -------------------------------------------------------------------------

    Case 1 - Only one credential type is available

    Application Configuration
        credentialTypes
            OAuth
    ↓
    Call
        fetch_credential_config(
            name="OAuth",
            version="1.0.0"
        )
    ↓
    Continue to create_application().

    -------------------------------------------------------------------------
    Case 2 - Multiple credential types are available

    Application Configuration
        credentialTypes

            OAuth
            APIKey
            BasicAuthentication

    ↓

    Present the credential types as a searchable and scrollable selection list.

    Allow the user to select exactly one credential type.

    Do not ask the user to manually type the credential type if it is
    available in the list.

    Wait until one credential type has been selected.

    ↓

    Call

        fetch_credential_config(
            name="<selected credential type>",
            version="<selected version>"
        )

    ↓

    Continue to create_application().

    -------------------------------------------------------------------------
    USER INTERACTION
    -------------------------------------------------------------------------
    
    If only one credential type is available:

    • Select it automatically.
    • Continue without asking the user to choose.
    
    If multiple credential types are available:
    
    Explain each authentication method in simple language.

    Examples

    OAuth

    Use when the application allows you to sign in securely without sharing
    your password.

    API Key

    Use when the application provides an API Key for authentication.

    Basic Authentication

    Use when the application requires a username and password.

    Help the user determine which authentication method matches
    their application.

    Wait until exactly one credential type has been selected.

    Only then call this tool.

    Do not ask users to choose using internal terminology alone.
    
    If the user's previous messages already clearly indicate
    the authentication method
    (for example,
    "I have an API Key"
    or
    "We authenticate using OAuth"),

    recommend that credential type automatically
    and ask for confirmation
    instead of explaining every authentication method.

    -------------------------------------------------------------------------

    -------------------------------------------------------------------------
    HOW TO USE THE RESPONSE
    -------------------------------------------------------------------------

    The returned credential configuration contains
        status.attributes

    Use these attributes to construct
        userDefinedData

    Preserve every attribute exactly as returned.
    Populate
        value

    with an empty string ("") for every attribute.

    Example

    Returned

    {
        "name": "ClientID",
        "displayName": "Client ID",
        "required": true,
        "secret": false,
        "dataType": "STRING"
    }

    Create

    {
        "name": "ClientID",
        "displayName": "Client ID",
        "required": true,
        "secret": false,
        "dataType": "STRING",
        "value": ""
    }

    Do not prompt the user for credential values.

    Credential values will remain empty during application creation and can
    be updated later.

    -------------------------------------------------------------------------
    IMPORTANT
    -------------------------------------------------------------------------

    Never guess credential types.
    Never guess credential attributes.
    Never remove or rename any attribute.

    Always preserve

        name
        displayName
        required
        secret
        dataType

    Only initialize
        value

    as an empty string.
    -------------------------------------------------------------------------
    ARGS
    -------------------------------------------------------------------------

    name
        Credential type name.

    version
        Credential type version.

    -------------------------------------------------------------------------
    RETURNS
    -------------------------------------------------------------------------

    Returns the complete credential configuration for the selected credential
    type.

    The returned configuration will be used by create_application() to build
    userDefinedData with empty values.
    """

    try:
        logger.info("fetch_credential_config")
        query_params = {
            "name": name,
            "version": version,
            "isStatusToBeIncluded": "true",
        }

        logger.debug("query params : {}".format(json.dumps(query_params)))

        output = await utils.make_GET_API_call_to_CCow(
            constants.URL_CREDENTIAL_CONFIGS,
            ctx=ctx,
            query_params=query_params,
        )

        logger.debug("output : {}".format(json.dumps(output)))

        if isinstance(output, str) or "error" in output:
            logger.error("fetch_credential_config error : {}".format(output))
            return {
                "error": "Facing internal error"
            }

        items = output.get("items", [])
        if len(items) == 0:
            return {
                "error": "Credential configuration not found"
            }
        return items[0]

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_credential_config error : {}".format(e))
        return {
            "error": "Facing internal error"
        }

@mcp.tool()
async def create_application(application_name: str, application_version: str, credential_type: str, credential_version: str, 
                            credential_name: str, application_url: str, ctx: Context | None = None):
    """
    Create a new ComplianceCow application.
    -------------------------------------------------------------------------
    PURPOSE
    -------------------------------------------------------------------------

    This tool creates a new ComplianceCow application using the selected
    application type and credential type.

    It constructs the application payload automatically using

    • the selected application configuration
    • the selected credential configuration
    • the application details provided by the user

    Credential values are not collected during application creation.

    All credential values are initialized as empty strings.
    -------------------------------------------------------------------------
    WHEN TO CALL
    -------------------------------------------------------------------------

    Call this tool only after

    1. An application type has been selected.
    2. Existing applications have been checked using list_applications().
    3. The user explicitly chooses to create a new application.
    4. A credential type has been selected.
    5. The credential configuration has been retrieved using
    fetch_credential_config().

    -------------------------------------------------------------------------
    USER INTERACTION
    -------------------------------------------------------------------------

    Before creating the application, collect the following information
    in a single interaction.

    Required

    • Credential Name
    • Application URL

    Explain why these values are needed.

    Credential Name

    A friendly name used to identify this credential later.

    Application URL

    The base URL of the application or service you want ComplianceCow
    to connect to.

    Do NOT ask for API Keys, Passwords, Client Secrets,
    Access Tokens, Certificates, Access Keys, Secret Keys, or any other
    sensitive credential values.

    At this stage, only collect the Credential Name and Application URL.

    After the application has been created, provide a link to the newly
    created application in the ComplianceCow UI in this conversation, where
    the user can configure the required credentials, validate the
    application, and complete the setup.

    Do not ask the user to provide credential values in the chat.

    -------------------------------------------------------------------------
    PAYLOAD CONSTRUCTION
    -------------------------------------------------------------------------

    Construct the request payload using the following mapping.
    
    credentialName
        User supplied Credential Name

    ------------------------------------------------

    appURL
        User supplied Application URL

    ------------------------------------------------

    appHost
        Same value as appURL

    ------------------------------------------------

    appPort
        null.

    ------------------------------------------------

    credentialType
        Selected Credential Type

    ------------------------------------------------

    appType

        Construct from the selected application configuration.
        
        Format:
            <meta.name>::<meta.version>

        If meta.version is empty, construct
            <meta.name>::
        
        Note: Always construct appType using the selected application configuration.
        Do not hardcode appType.
    ------------------------------------------------

    othersTags
        Populate from the selected application configuration.

    ------------------------------------------------

    userDefinedData

    Construct from the credential configuration returned by
    fetch_credential_config().

    For every attribute returned in the credential configuration,
    create an entry preserving

    • name
    • displayName
    • required
    • secret
    • dataType

    Initialize
        value

    as an empty string.

    Example
    Credential Configuration
    {
        "name": "ClientID",
        "displayName": "Client ID",
        "required": true,
        "secret": false,
        "dataType": "STRING"
    }

    Construct
    {
        "name": "ClientID",
        "displayName": "Client ID",
        "required": true,
        "secret": false,
        "dataType": "STRING",
        "value": ""
    }

    Repeat this for every credential attribute.

    -------------------------------------------------------------------------
    IMPORTANT
    -------------------------------------------------------------------------

    Never ask the user for credential values.

    Never modify the credential schema returned by
    fetch_credential_config().

    Always preserve

    • name
    • displayName
    • required
    • secret
    • dataType

    Only initialize
        value

    with an empty string.
    Always populate

    • credentialType
    • appType
    • othersTags

    using the selected application and credential configuration.
    -------------------------------------------------------------------------
    RESULT
    -------------------------------------------------------------------------

    - **MANDATORY:** Before I create the application, please confirm the following:

    Application Type:
    Credential Type:
    Credential Name:
    Application URL:

    - **MANDATORY:** Would you like me to create the application?

    Return the API response to the user.
    If the API returns a successful response, inform the user that the
    application has been created successfully.

    If the API returns an error, return the error message without modifying
    or interpreting it.
    
    -------------------------------------------------------------------------
    VALIDATION ERRORS
    -------------------------------------------------------------------------

    If create_application() returns

    retryRequired = true

    • Inform the user of the validation error.
    • Ask the user only for the field identified by retryField.
    • Do not ask again for the Application Type.
    • Do not ask again for the Credential Type.
    • Do not ask again for the Application URL.
    • Invoke create_application() again using the updated value while preserving all previously selected values.
    
    -------------------------------------------------------------------------
    POST-CREATION GUIDANCE
    -------------------------------------------------------------------------

    If the application is created successfully and the response indicates
    "isValidated" is false:

    • Inform the user that the application was created successfully.
    • Clearly state that the application is NOT ready for use until it has been configured and successfully validated.
    • Explain that validation is a mandatory post-creation step to ensure the application can be used reliably in future ComplianceCow operations.
    • Explain that if this step is skipped, any future assessments, rule executions, workflows, or tasks that depend on this application are likely to fail due to missing or invalid credentials.
    • Do NOT ask the user to provide credential values (such as API Keys, Client Secrets, Passwords, Access Keys, Secret Keys, Tokens, Certificates, JSON files, etc.) in the chat.
    • Do NOT list, enumerate, or describe the required credential fields, even if they are present in the tool response.
    • If the response contains a "redirectURL", present that URL and instruct the user to use it to complete the application setup.
    • Always use the "redirectURL" returned by the tool response. Never display placeholder URLs.

    Instruct the user to complete the following steps in the ComplianceCow UI:

    1. Open the newly created application using the provided redirect URL.
    2. Edit the application by supplying the required credential information.
    3. Validate the application to verify the configured credentials.
    4. Save/Submit the application.

    Explain that once the application has been successfully validated, it will be ready for use in future assessments, rule executions, workflows, and any other ComplianceCow operations that require this application.
    Completing this validation now helps prevent authentication and execution failures when the application is used later. 
    
    Do not invoke create_application()
    until the user explicitly confirms
    the summarized information.
    
    **MANDATORY:** The purpose of the provided redirection link must always be clearly explained. Inform the user that this link is to complete the post-creation
    application setup by configuring, validating, and submitting the application so it is ready for future assessments, rule executions, workflows, and other ComplianceCow operations.
    
    -------------------------------------------------------------------------
    MANDATORY
    -------------------------------------------------------------------------

    Before invoking create_application_scope(), summarize:

    • Application Scope Name
    • Description
    • Applications Included

    Ask the user:

    "Would you like me to create this Application Scope?"

    Only invoke create_application_scope() after the user explicitly confirms.
    
    -------------------------------------------------------------------------
    APPLICATION SCOPE (POST-CREATION)
    -------------------------------------------------------------------------

    After the application has been created successfully, ask the user whether
    they would like to create an Application Scope.

    Explain that an Application Scope is recommended when the application will
    be used in ComplianceCow assessments.

    Application Scope allows one or more applications (credentials) to be
    grouped together for assessment execution.

    During an assessment:

    • Different controls may execute different rules.
    • Different rules may require different applications.
    • The Application Scope provides the collection of applications that can
    be used during assessment execution.

    Without an appropriate Application Scope, future assessment executions may
    not be able to locate the required applications for rule execution.

    If the user chooses not to create an Application Scope,
    consider the application creation workflow complete.

    Do not repeatedly prompt the user to create an Application Scope.

    The user may create one later if needed.

    If the user chooses to create one, invoke create_application_scope().

    Pass the newly created application ID as the initial credential reference.

    Do not ask the user to provide the application ID.
    Use the application ID returned from create_application().
    
    Inform the user that the Application Scope has been created successfully.

    Explain that it can now be selected when configuring or running
    Assessments.

    Future Assessment Controls and Rules will be able to use the
    applications contained in this Application Scope without selecting
    individual applications for each Rule.
    """

    try:
        logger.info("create_application")
        application_output = await utils.make_GET_API_call_to_CCow(
            constants.URL_APPLICATION_CONFIGS,
            ctx=ctx,
            query_params={
                "validApplication": "true",
                "name": application_name,
                "version": application_version,
                "isStatusToBeIncluded": "true",
            },
        )

        if (
            isinstance(application_output, str)
            or "error" in application_output
            or not application_output.get("items")
        ):
            return {
                "error": "Unable to retrieve application configuration."
            }

        application_config = application_output["items"][0]
        
        credential_output = await utils.make_GET_API_call_to_CCow(
            constants.URL_CREDENTIAL_CONFIGS,
            ctx=ctx,
            query_params={
                "name": credential_type,
                "version": credential_version,
                "isStatusToBeIncluded": "true",
            },
        )

        if (
            isinstance(credential_output, str)
            or "error" in credential_output
            or not credential_output.get("items")
        ):
            return {
                "error": "Unable to retrieve credential configuration."
            }

        credential_config = credential_output["items"][0]

        app_name = (
            application_config.get("meta", {}).get("name") or ""
        ).strip()

        app_version = (
            application_config.get("meta", {}).get("version") or ""
        ).strip()

        app_type = (
            f"{app_name}::{app_version}"
            if app_version
            else f"{app_name}::"
        )

        labels = (
            application_config
            .get("meta", {})
            .get("labels", {})
        )

        attributes = (
            credential_config
            .get("status", {})
            .get("attributes", [])
        )

        user_defined_data = []

        for attribute in attributes:
            user_defined_data.append(
                {
                    "name": attribute.get("name"),
                    "displayName": attribute.get("displayName"),
                    "secret": attribute.get("secret", False),
                    "required": attribute.get("required", False),
                    "dataType": attribute.get("dataType"),
                    "value": "",
                }
            )

        payload = {
            "credentials": [
                {
                    "skipValidation": True,
                    "credentialName": credential_name,
                    "appURL": application_url,
                    "appHost": application_url,
                    "appPort": None,
                    "credentialType": credential_type,
                    "appType": app_type,
                    "userDefinedData": user_defined_data,
                    "referencedCredentialIds": None,
                    "status": "true",
                    "othersTags": labels,
                }
            ]
        }

        logger.debug("payload : %s", json.dumps(payload))
        output = await utils.make_API_call_to_CCow_v2(
            payload,
            constants.URL_CREATE_APPLICATION,
            ctx=ctx,
        )

        logger.debug("output : %s", json.dumps(output))
        if isinstance(output, str):
            logger.error("create_application error : %s", output)
            return {"error": output}

        if "error" in output:
            logger.error("create_application error : %s", output)
            error_message = output.get("error", "")
            if "already in use" in error_message.lower():
                return {
                    "error": error_message,
                    "retryRequired": True,
                    "retryField": "credential_name",
                }
            return output
        
        if not output or not isinstance(output, list):
            return {
                "error": "Unexpected response from Create Application API."
            }

        application = output[0]
        return {
            "applicationId": application["id"],
            "credentialName": application["credentialName"],
            "applicationType": application["appType"],
            "credentialType": application["credentialType"],
            "applicationURL": application["appURL"],
            "isValidated": application.get("isValidated", False),
            "redirectURL": f"{constants.COW_BASE_URL}/ui/applications-catalog?applicationId="+application["id"],
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_application error : %s", e)
        return {
            "error": "Facing internal error"
        }
        
@mcp.tool()
async def create_application_scope(scope_name: str,description: str, credential_ref: list[str], ctx: Context | None = None) -> dict:
    """
    Create a new ComplianceCow Application Scope.

    -------------------------------------------------------------------------
    PURPOSE
    -------------------------------------------------------------------------

    Application Scope groups one or more ComplianceCow applications together.

    Application Scopes are primarily used during Assessment execution.

    An Assessment may contain multiple Controls.

    Each Control may execute one or more Rules.

    Different Rules may require different Applications.

    Instead of selecting individual applications for every rule execution,
    ComplianceCow uses an Application Scope that contains all applications
    required by the Assessment.

    -------------------------------------------------------------------------
    WHEN TO CALL
    -------------------------------------------------------------------------
    Call this tool only after one or more applications have been selected.

    Applications may be

    • Newly created using create_application().

    • Existing applications selected using list_applications().

    This tool is typically invoked immediately after create_application()
    when the user confirms that the application will be used in future
    Assessments.

    It may also be invoked later to create an Application Scope using one or
    more existing applications returned by list_applications().

    Do not require a new application to be created before creating an
    Application Scope.

    -------------------------------------------------------------------------
    USER INTERACTION
    -------------------------------------------------------------------------

    Before creating the Application Scope, collect the following information
    in a single interaction.

    Required

    • Application Scope Name
    • Description

    Explain why these values are needed.

    Application Scope Name

    A friendly name used to identify the Application Scope later.

    Description

    A short description explaining the purpose of this Application Scope.

    Do NOT ask the user for

    • Application ID
    • Credential Reference
    • Type
    • Cloud Type

    These values are automatically populated.

    -------------------------------------------------------------------------
    PAYLOAD CONSTRUCTION
    -------------------------------------------------------------------------

    Construct the request payload using the following mapping.

    name
        User supplied Application Scope Name.

    ------------------------------------------------

    description
        User supplied Description.

    ------------------------------------------------
    type

        Always
        generic

    ------------------------------------------------

    cloudType
        Always
        generic

    ------------------------------------------------

    credentialRef

        Populate automatically using the application IDs supplied to this
        tool.

        These IDs must come from previously created applications.

        Never ask the user to manually enter application IDs.

        If multiple applications should belong to the same Application Scope,
        include every application ID.

    Example
        credentialRef
        [
            "<application-id-1>",
            "<application-id-2>"
        ]

    -------------------------------------------------------------------------
    IMPORTANT
    -------------------------------------------------------------------------

    Never ask the user to manually provide application IDs.

    Always reuse the application IDs returned from create_application().

    Always preserve every application ID exactly as returned.

    Always populate

        type = "generic"
        cloudType = "generic"

    -------------------------------------------------------------------------
    CONFIRMATION
    -------------------------------------------------------------------------

    Before creating the Application Scope, summarize the information.

    Application Scope Name:

    Description:

    Applications Included:

    Ask the user to confirm before continuing.

    Do not invoke create_application_scope() until the user explicitly
    confirms.

    -------------------------------------------------------------------------
    RESULT
    -------------------------------------------------------------------------

    If the API returns a successful response,

    Inform the user that the Application Scope has been created successfully.

    Explain that this Application Scope can now be selected when creating or
    running Assessments.

    Future Assessment Controls and Rules will be able to use the applications
    contained in this Application Scope.

    If the API returns an error,

    Return the error exactly as received without modifying or interpreting it.
    """

    try:
        logger.info("create_application_scope")
        payload = {
            "name": scope_name,
            "description": description,
            "type": "generic",
            "cloudType": "generic",
            "credentialRef": credential_ref,
        }

        logger.debug("payload : %s", json.dumps(payload))
        output = await utils.make_API_call_to_CCow_v2(payload, constants.URL_CREATE_APPLICATION_SCOPE,ctx=ctx)
        logger.debug("output : %s", json.dumps(output))

        if isinstance(output, str):
            logger.error("create_application_scope error : %s", output)
            return {"error": output}
        if "error" in output:
            logger.error("create_application_scope error : %s", output)
            return output

        return output
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_application_scope error : %s", e)
        return {
            "error": "Facing internal error"
        }


@mcp.tool()
async def list_applications(application_name: str,application_version: str,validated_only: bool | None = None,ctx: Context | None = None) -> dict:
    """
    Retrieve existing ComplianceCow applications.

    -------------------------------------------------------------------------
    PURPOSE
    -------------------------------------------------------------------------

    This tool retrieves existing ComplianceCow applications that match the
    selected application type.

    Its primary purpose is to avoid creating duplicate applications by
    identifying existing applications that can be reused.

    This tool automatically determines the appropriate application type tag
    from the selected application configuration.

    Users should never be asked to provide an application type tag.

    The application type tag is used internally to retrieve only
    applications that belong to the selected application type.

    This tool should normally be invoked immediately after
    list_application_types() and before create_application().

    -------------------------------------------------------------------------
    WHEN TO CALL
    -------------------------------------------------------------------------

    Call this tool only after a single application type has been selected.

    Always invoke this tool before create_application().

    -------------------------------------------------------------------------
    WORKFLOW
    -------------------------------------------------------------------------

    1. Retrieve the selected application configuration using the supplied
        application name and version.

    2. Read
        meta.labels.appType

    3. Use the first value from
        meta.labels.appType
        
        as
        
        app_type_tag

    Example
        labels
            appType
                ["aws"]

    Invoke

        GET /credential?app_type_tag=aws

    4. Retrieve every existing application matching that application type.

    5. Present the matching applications to the user.

    Never ask the user for the application type tag.

    Never guess the application type tag.

    Always retrieve it from the selected application configuration.

    -------------------------------------------------------------------------
    USER INTERACTION
    -------------------------------------------------------------------------

    If no matching applications exist,

    Inform the user that no existing application was found for the selected
    application type.

    Continue with create_application().

    If one or more matching applications exist,

    Present a concise summary for each application including

    • Credential Name
    • Application URL
    • Validation Status

    Never expose

    • Credential values
    • Secret values
    • Secret paths
    • Vault paths
    • userDefinedData
    • sensitiveDataPath

    If an application has not been validated,

    Clearly explain that it must be configured and validated before it can
    be used reliably for Assessments, Rule executions, Workflows, Tasks,
    or any other ComplianceCow operations.

    -------------------------------------------------------------------------
    USER CHOICE
    -------------------------------------------------------------------------

    Allow the user to choose one of the following.

    • Reuse an existing application.

    • Edit or validate an existing application.

    • Create a new application.

    If the user chooses to reuse an existing validated application,

    Do not invoke create_application().

    Reuse the selected application's ID in subsequent operations.

    If the application will be used in an Assessment,

    Ask whether the user would like to create an Application Scope.

    If the user chooses to edit or validate an existing application,

    Provide the application's redirect URL.

    Explain that the user should

    1. Open the application.

    2. Configure or update the credentials.

    3. Validate the application.

    4. Save the application.

    Until validation succeeds, future Assessments, Rule executions,
    Workflows, and Tasks using this application may fail.

    If the user chooses to create a new application,

    Continue with fetch_credential_config().

    -------------------------------------------------------------------------
    APPLICATION SCOPE
    -------------------------------------------------------------------------

    If the user chooses to create an Application Scope,

    Invoke create_application_scope().

    Automatically reuse the selected application's ID as the initial
    credentialRef.

    Never ask the user to manually provide the application ID.

    -------------------------------------------------------------------------
    IMPORTANT
    -------------------------------------------------------------------------

    Always retrieve the application type tag from

        meta.labels.appType

    Never construct, infer, or guess the application type tag.

    Never ask the user to provide it.

    Always use the first value returned by

        meta.labels.appType

    when querying existing applications.

    Recommend reuse whenever a suitable validated application already
    exists.

    Only recommend creating a new application when

    • no suitable application exists

    or

    • the user explicitly requests a separate application.

    -------------------------------------------------------------------------
    RETURNS
    -------------------------------------------------------------------------

    Return only the information required for user decision making.

    For each application return

    • applicationId
    • credentialName
    • applicationType
    • credentialType
    • applicationURL
    • isValidated
    • redirectURL

    Never return internal metadata or sensitive credential information.
    """

    try:
        logger.info("list_applications")
        application_output = await utils.make_GET_API_call_to_CCow(
            constants.URL_APPLICATION_CONFIGS,
            ctx=ctx,
            query_params={
                "validApplication": "true",
                "name": application_name,
                "version": application_version,
                "isStatusToBeIncluded": "true",
            },
        )

        if (
            isinstance(application_output, str) or "error" in application_output or not application_output.get("items")):
            logger.error("Unable to retrieve application configuration: %s",application_output)
            return {
                "error": "Unable to retrieve application configuration."
            }
        application_config = application_output["items"][0]
        labels = (
            application_config
            .get("meta", {})
            .get("labels", {})
        )

        app_type_tags = labels.get("appType", [])
        if not app_type_tags:
            return {
                "error": "Application type tag not found."
            }

        app_type_tag = app_type_tags[0]
        query_params = {
            "app_type_tag": app_type_tag,
        }

        output = await utils.make_GET_API_call_to_CCow(
            constants.URL_CREATE_APPLICATION,
            ctx=ctx,
            query_params=query_params,
        )

        logger.debug("output : %s", json.dumps(output))
        if isinstance(output, str) or "error" in output:
            logger.error("list_applications error : %s", output)
            return {
                "error": "Facing internal error"
            }

        items = output.get("items", [])
        applications = []
        for item in items:
            if validated_only is True and not item.get("isValidated", False):
                continue
            applications.append(
                {
                    "applicationId": item.get("id"),
                    "credentialName": item.get("credentialName"),
                    "applicationType": item.get("appType"),
                    "credentialType": item.get("credentialType"),
                    "applicationURL": item.get("appURL"),
                    "isValidated": item.get("isValidated", False),
                    "redirectURL": (
                        f"{constants.COW_BASE_URL}"
                        f"/ui/applications-catalog?applicationId={item.get('id')}"
                    ),
                }
            )

        return {
            "applications": applications
        }

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_applications error : %s", e)
        return {
            "error": "Facing internal error"
        }