from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, get_type_hints
from urllib.parse import urlparse

import mcptypes.rule_type as vo
from constants import constants
from mcpconfig.config import mcp
from mcptypes import exception
from mcptypes.rule_type import TaskVO
from utils import rule, wsutils
from utils.debug import logger

# Phase 1: Lightweight task summary resource

if constants.ENABLE_CCOW_API_TOOLS:
    if constants.ENABLE_CONTEXTUAL_VECTOR_SEARCH:
        @mcp.tool()
        def fetch_tasks_suggestions(user_requirement: str, summary_string: str) -> Dict[str, Any]:
            
            """
            Resource for intelligent task suggestion based on user requirements.

            PURPOSE:
            - Analyze the user's requirement and generate a concise **summary string** that
            captures the intent in natural language (not bullet points, not verbatim input).
            - Use the summary string to query task suggestions via the Suggestions API.
            - Match suggested tasks with the user’s intent to prevent redundant or duplicate task creation.
            - Provide resumption options if partially developed tasks exist.

            SUMMARY STRING CREATION:
            - Always derive a clear, single-paragraph summary string from the user's input.
            - Convert it into a structured summary string that clearly outlines each step/task that must be performed.
            - Each part of the summary string should represent an atomic action that could later be mapped to an individual task.
            - The summary must express the intended goal in natural language.
            - This summary string is what will be passed to `fetch_rules_and_tasks_suggestions`.
            - Example:
                Input: "Create a rule to update CC workflow user actions that remain 'in progress' for more than one day.
                The process should first check if any workflow user actions are pending, meaning their status is still 'in progress'.
                If such actions exist and were assigned more than one day ago, they should be marked as completed. Finally,
                send a notification to the user informing them that their action has been automatically marked as completed after waiting for a long time."
                Summary: "Check for workflow user actions with status 'in progress'.
                If they were assigned more than one day ago, mark them as completed and notify the user about the auto-completion."

            DECISION LOGIC:
            - If **matching tasks** are found in the suggestions:
                * Present them to the user for selection.
                * Include explanation of purpose, description, and relevance.
            - If **no matching tasks** are found:
                * FALLBACK: Call `get_tasks_summary()` to provide a broader list of tasks for discovery.
                * Clearly inform the user that no direct match was found and present fallback results.

            AUTOMATIC WORKFLOW HANDLING:
            - Detect if suggested tasks are only intermediate steps (splitting, extraction, validation, processing).
            - If intermediate: automatically recommend additional tasks that can complete the workflow.
            - Never leave the user with incomplete workflows.
            - Ensure the final task suggestions always lead to actionable, consumable deliverables.

            MANDATORY FUNCTIONALITY:
            - Generate summary string from raw requirement.
            - Fetch task suggestions using this summary.
            - Validate suggestions and ensure workflow completeness.
            - If suggestions fail → fallback to `get_tasks_summary()`.
            - Always explain reasoning when no suggestions are found and why fallback is triggered.
            
            NEXT STEPS AFTER MATCH:
            - Once matching task suggestions are presented to the user:
                * Wait for user selection.
                * Once matching tasks are found, show to user with explanation before fetching full details using `tasks://details/{task_name}`.
                * For each selected task, fetch complete task details using `tasks://details/{task_name}`.
                * Provide the full description, input/output parameters, templates, and usage guidance.
            - Apply the same **workflow completeness enforcement** as in `get_tasks_summary`:
                * If the selected task is only an intermediate step, automatically recommend additional tasks to complete the workflow.
                * Ensure that the final set of tasks always produces actionable, consumable deliverables.

            DEDUPLICATION HANDLING:
            - The `fetch_rules_and_tasks_suggestions` API may return the same task name multiple times
            with different descriptions and purpose.
            - In such cases:
                * Consolidate results under a single task entry.
                * Merge or summarize all unique descriptions and purpose into one combined explanation.
                * Ensure the final presentation avoids duplicates while still capturing all variations.
            - Always prioritize clarity: the user should see only one task name, with a rich combined description
            that reflects all possible contexts.

            """
            try:
                task_response = rule.fetch_rules_and_tasks_suggestions(query=summary_string, identifierType="tasks")
                if not task_response:
                    return {"error": f"No task found that matches the specified requirements."}
                return task_response
            except Exception as e:
                return {
                    "error": f"An error occurred while retrieving the task with the specified details: {e}"
                }
        
        @mcp.tool()
        def fetch_rules_suggestions(user_requirement: str, summary_string: str) -> Dict[str, Any]:
            """
            Tool-based version of `fetch_rules_and_tasks_suggestions` for improved compatibility and prevention of duplicate rule creation.

            This tool serves as the initial step in the rule creation process. It helps determine whether the user's proposed use case matches any existing rule in the catalog.

            PURPOSE:
            - To analyze the user's use case and avoid duplicate rule creation by identifying the most suitable existing rule based on its name, description, and purpose.
            - **NEW: Check for partially developed rules in local system before allowing new rule creation**
            - **NEW: Present resumption options if incomplete rules are found to prevent duplicate work**

            WHEN TO USE:
            - As the first step before initiating a new rule creation process.
            - When the user wants to check if similar rules already exist by leveraging the Rules Suggestions API, instead of browsing the entire catalog manually.
            - When verifying if a suggested rule can be reused or adapted rather than creating one from scratch.
            - When checking for incomplete local rules that should be resumed instead of creating new ones.

            🚫 DO NOT USE THIS TOOL FOR:
            - Checking what rules are available in the ComplianceCow system.
            - This tool only works with the **rule catalog** (not the entire ComplianceCow system).
            - The catalog contains only rules that are published and available for reuse in the catalog.
            - For direct ComplianceCow system lookups, use dedicated system tools instead:
            - `fetch_cc_rule_by_name`
            - `fetch_cc_rule_by_id`
            
            MANDATORY STEP: CONTEXT SUMMARY
            - Before calling the rule catalog API, always rewrite the user’s raw requirement into a single-paragraph
            descriptive summary string (not bullet points, not verbatim input).
            - The summary must capture the essence of the requirement in clear, natural language.
            - This summary string is what will be passed to `fetch_rules_and_tasks_suggestions`.
            - Example:
                User input: "Use GitHub GraphQL API to fetch merged PRs and check if approvals >= 2"
                Summary: "The proposed rule validates compliance for GitHub Pull Requests by retrieving all merged PRs
                through the GitHub GraphQL API, checking whether the number of approvers meets a required threshold,
                and marking them as compliant or non-compliant."

            WHAT IT DOES:
            - Generates a concise summary string from the user's intent or requirements.
            - Calls the Rules Suggestions API with this summary string to retrieve a narrowed list of relevant rules.
            - Performs intelligent matching using metadata (name, description, purpose) from the suggested rules against the user-provided use case details.
            - Uses semantic pattern recognition to identify similar or related rules, even across different systems (e.g., AzureUserUnusedPermission vs SalesforceUserUnusedPermissions).
            - Analyzes the `readmeData` field from the `fetch_rule()` response to validate the rule's suitability for the user's use case.
            
            IF A MATCHING RULE IS FOUND:

            - Retrieves complete details via `fetch_rule()`.
            - If the readmeData field is available in the fetch_rule() response, Performs README-based validation using the `readmeData` field from the `fetch_rule()` response to assess its suitability for the user’s use case.
            - If suitable:
            - Returns the rule with full metadata, explanation, and the analysis report.
            - If not suitable:
            - Informs the user that the rule's README content does not align with the intended use case.
            - Prompts the user with clear next-step options:
                - "The rule's README content does not align with your use case. Please choose one of the following options:"
                - Customize the existing rule
                - Evaluate alternative matching rules
                - Proceed with new rule creation
            - Waits for the user's choice before proceeding.
            
            IF A SIMILAR RULE EXISTS FOR AN ALTERNATE TECHNOLOGY STACK:

            - Detects rules with the same logic but built for a different platform or system (e.g., AzureUserUnusedPermission for SalesforceUserUnusedPermissions)
            - If the readmeData field is available in the fetch_rule() response, Retrieves and analyzes the `readmeData` from the `fetch_rule()` response to compare the implementation details against the user's proposed use case
            - Based on the comparison:
                - If the README content matches or is mostly reusable, suggest using the existing rule structure and logic as a foundation to create a new rule tailored to the user's target system
                - If the README content does not match or is not suitable, clearly inform the user and recommend either modifying the logic significantly or proceeding with a completely new rule from scratch

            IF NO SUITABLE RULE IS FOUND:
            - Clearly informs the user that no relevant rule matches the proposed use case
            - Suggests continuing with new rule creation
            - Optionally highlights similar rules that can be used as a reference

            MANDATORY STEPS:
            README VALIDATION:
            - Always retrieve and analyze `readmeData` from `fetch_rule()`.
            - Ensure the rule's logic, behavior, and intended use align with the user's proposed use case.

            README ANALYSIS REPORT:
            - Generate a clear and concise report for each `readmeData` analysis that classifies the result as a full match, partially reusable, or not aligned.
            - Present this report to the user for review.

            USER CONFIRMATION BEFORE PROCEEDING:
            When analyzing a README file:
            - If no relevant rule matches the proposed use case, or if the README is deemed unsuitable, the tool must pause and request explicit user confirmation before proceeding further.
            - The tool should:
            - Clearly inform the user that no matching rule was found or the README is not appropriate.
            - Suggest creating a new rule as the next step.
            - Optionally recommend similar existing rules that can serve as references to help the user craft the new rule.

            ITERATE UNTIL MATCH:
            - Repeat the above steps until a suitable rule is found or all options are exhausted.

            CROSS-PLATFORM RULE HANDLING:
            - For rules from a different stack:
            - If reusable: suggest customization
            - If not reusable: recommend new rule creation

            Returns:
            - A single rule object with full metadata and verified README match — if an exact match is found
            - A similar rule suggestion with customization options — if a cross-system match is found (e.g., AzureUserUnusedPermission vs SalesforceUserUnusedPermissions)
            - A message indicating no suitable rule found — with next steps and guidance to create a new rule
            """

            try:
                rule_response = rule.fetch_rules_and_tasks_suggestions(query=summary_string, identifierType="rules")
                if not rule_response:
                    return {"error": f"No rule found that matches the specified requirements."}
                return rule_response
            except Exception as e:
                return {
                    "error": f"An error occurred while retrieving the rule with the specified details: {e}"
                }


    @mcp.tool()
    def create_support_ticket(subject: str, description: str, priority: str) -> Dict[str, Any]:
        """
        PURPOSE:  
        - Create structured support tickets only after strict user review and explicit approval of all descriptions.  
        - Ticket creation MUST NOT occur without explicit user confirmation at every required step.  
        - Reduce user input errors and rework by ensuring clarity and completeness before ticket submission.

        MANDATORY CONDITIONS — NO STEP MAY BE SKIPPED OR BYPASSED:

        1. BEFORE TOOL ENTRY:  
        - The tool MUST generate a detailed, pre-filled plain-text description for the task or workflow.  
        - The user MUST review this description carefully.  
        - Ticket creation MUST be blocked until the user explicitly APPROVES this description.

        2. USER VERIFICATION:  
        - The user MUST be presented with the full pre-filled description.  
        - The user MUST either confirm its correctness or provide feedback for changes.  
        - The tool MUST update the description and priority per feedback and repeat this verification step as many times as needed.  
        - Skipping or auto-approving this step is strictly prohibited.

        3. FINAL APPROVAL & FORMATTING:  
        - After user approval of the plain text, the description MUST be converted into professional HTML format (bold headings, clear structure, spacing).  
        - The user MUST explicitly approve this final HTML-formatted description.  
        - The tool MUST block ticket creation until this final approval is given.  
        - Only the fully user-approved, HTML-formatted description MAY be used to create the support ticket.

        IMPORTANT:  
        **Under no circumstances shall the tool proceed to ticket creation without explicit user approval at all mandatory steps.**  
        The process must strictly enforce these approvals, preventing any premature or automatic ticket submissions.

        MANDATORY USER INPUTS:  
        - `subject` (str) — ticket title.  
        - `description` (str) — final user-approved, HTML-formatted description.  
        - `priority` (str) — ticket priority level.  
        **Valid values:** `"High"`, `"Medium"`, `"Low"` (case-sensitive).  
        The user MUST provide one of these values to proceed.

        RETURNS:  
        - A dictionary simulating the ticket creation response for integration or testing purposes.
        """

        try:
            request_body = {
                "subject": subject,
                "description": description,
                "priority": priority
            }

            response = rule.create_support_ticket_api(request_body)
            
            if not response:
                return {"error": "Failed to create support ticket with the specified details."}

            return response

        except Exception as e:
            return {
                "error": f"An error occurred while creating the support ticket: {e}"
            }
    
    @mcp.tool()
    def get_applications_for_tag(tag_name: str) -> Dict[str, Any]:
        """
        Get available applications for a specific app tag.

        APPLICATION RETRIEVAL:
        - Fetches all existing applications configured for the specified app tag.
        - Returns a list of applications with ID, name, and app type.
        - Used during rule execution to present application choices to the user.

        Args:
            tag_name (str): The app tag name to get applications for. 
                            This parameter is mandatory and must not be empty.

        Returns:
            dict: A dictionary containing available applications for the specified tag.

        Raises:
            ValueError: If tag_name is not provided or is empty.
        """
        try:
            header = wsutils.create_header()

            params = {
                "app_type_tag": tag_name,
                "fields": "basic",
                "validated": True
            }

            applications = []

            applications_resp = wsutils.get(
                path=wsutils.build_api_url(endpoint=constants.URL_FETCH_CREDENTIAL), 
                params=params, 
                header=header
            )

            if rule.is_valid_array(applications_resp, "items"):
                for item in applications_resp["items"]:
                    app_type = item.get("appType", "")
                    if isinstance(app_type, str) and app_type.endswith("::"):
                        app_type = app_type[:-2]
                    applications.append({
                        "id": item.get("id"),
                        "name": item.get("credentialName"),
                        "appType": app_type
                    })
                return {
                    "success": True, 
                    "tag_name": tag_name, 
                    "applications": applications, 
                    "count": len(applications), 
                    "message": f"Found {len(applications)} applications for tag '{tag_name}'. User can select an existing application or create new credentials."
                }    
            else:
                return {
                    "success": False,
                    "tag_name": tag_name,
                    "applications": [],
                    "count": 0,
                    "message": f"No applications found for tag '{tag_name}'. User can create new credentials."
                }

        except Exception as e:
            return {
                "success": False, 
                "tag_name": tag_name,
                "applications": [],
                "count": 0,
                "message": f"Error occurred while fetching applications for tag '{tag_name}': {e}"
            }
        
    @mcp.tool()
    def attach_rule_to_control(rule_id: str, assessment_name: str, control_alias: str, control_id: str,create_evidence: bool = True ) -> Dict[str, Any]:

        """
        Attach a rule to a specific control in an assessment.

        🚨 CRITICAL EXECUTION BLOCKERS — DO NOT SKIP 🚨
        Before **any** part of this tool can run, five preconditions MUST be met:

        1. Control Verification:
        - You MUST verify the control exists in the assessment by calling `verify_control_in_assessment()`.
        - Verification must confirm the control is present, valid, and a leaf control.
        - If verification fails → STOP immediately. Do not proceed.

        2. Rule ID Resolution:
        - If `rule_id` is a valid UUID → proceed.
        - If `rule_id` is an alphabetic string → treat it as the rule name and resolve it to a UUID **using `fetch_cc_rule_by_name()`**.
        - If resolution fails or `rule_id` is still not a UUID after this step → STOP immediately.
        - Execution is STRICTLY PROHIBITED with a plain name.

        3. Rule Publish Validation:
        - You MUST check if the rule is published in ComplianceCow before proceeding.
        - If the rule is not published → STOP immediately.  
        - Published status is a hard requirement for attachment.

        4. Evidence Creation Acknowledgment:
        - Before proceeding, you MUST request confirmation from the user about `create_evidence`.
        - Ask: "Do you want to auto-generate evidence from the rule output? (default: True)"
        - Only proceed after the user explicitly acknowledges their choice.

        5. Override Acknowledgment:
        - If the control already has a rule attached, you MUST request user confirmation before overriding.
        - Ask: "This control already has a rule attached. Do you want to override it? (yes/no)"
        - Only proceed if the user explicitly confirms.

        RULE ATTACHMENT WORKFLOW:
        1. Perform control verification using `verify_control_in_assessment()` (MANDATORY).
        2. Resolve rule_id using the CRITICAL EXECUTION BLOCKERS above (use `fetch_cc_rule_by_name()` when needed).
        3. Validate that the rule is published in ComplianceCow.
        4. Confirm evidence creation preference from the user (acknowledgment REQUIRED).
        5. Check for existing rule attachments and request override acknowledgment if needed.
        6. Attach rule to control.
        7. Optionally create evidence for the control.

        ATTACHMENT OPTIONS:
        - create_evidence: Whether to create evidence along with rule attachment. 
        Must be confirmed by the user before proceeding.

        VALIDATION REQUIREMENTS:
        - Control must be verified and confirmed as a leaf control.
        - Rule must be published.
        - Rule ID must be a valid UUID.
        - Assessment and control must exist.
        - User must acknowledge override before replacing an existing rule.

        Args:
            rule_id: ID of the rule to attach (UUID). If an alphabetic string is provided, 
                    it MUST be resolved to a UUID using `fetch_cc_rule_by_name()` before the tool proceeds.
            assessment_name: Name of the assessment.
            control_alias: Alias of the control.
            control_id: ID of the control.
            create_evidence: Whether to create auto-generated evidence from the rule output (default: True).
                            ⚠️ MUST be confirmed by user acknowledgment before execution.

        Returns:
            Dict containing attachment status and details.
        """

        try:

            body = {
                "ruleId": rule_id,
                "createEvidence":create_evidence
            }
            
            response = rule.attach_rule_to_control_api(control_id,body)
            
            if response.get("success") or response.get("status") == "attached":
                result = {
                    "success": True,
                    "rule_id": rule_id,
                    "assessment_name": assessment_name,
                    "control_alias": control_alias,
                    "control_id": control_id,
                    "attachment_status": "attached",
                    "evidence_created": create_evidence,
                    "message": f"Rule '{rule_id}' successfully attached to control '{control_alias}' in assessment '{assessment_name}'"
                }
                
                if create_evidence:
                    result["evidence_info"] = response.get("evidenceInfo", {})
                    result["message"] += " with evidence created."
                
                return result
            else:
                return {
                    "success": False,
                    "rule_id": rule_id,
                    "assessment_name": assessment_name,
                    "control_alias": control_alias,
                    "error": response.get("error", "Failed to attach rule to control"),
                    "message": f"Failed to attach rule '{rule_id}' to control '{control_alias}'"
                }
                
        except Exception as e:
            return {
                "success": False,
                "rule_name": rule_id,
                "assessment_name": assessment_name,
                "control_alias": control_alias,
                "error": f"Failed to attach rule to control: {str(e)}",
                "message": f"Error occurred while attaching rule to control"
            }

    @mcp.tool()
    def fetch_cc_rule_by_id(rule_id: str) -> Dict[str, Any]:
        """
        Fetch rule details by rule id from the **compliancecow**.

        Args:
            rule_id: Rule Id of the rule to retrieve
            
        Returns:
            Dict containing complete rule structure and metadata
        """
        
        try:

            rule_response = rule.fetch_cc_rule_by_id(rule_id)
            logger.debug(f"fetch_cc_rule_by_id: rule_output: {rule_response}\n")

            if len(rule_response) == 0:
                return {
                    "success": False,
                    "rule_id": rule_id,
                    "error": f"Rule '{rule_id}' not found in ComplianceCow. This means the rule is not published or does not exist in ComplianceCow.",
                    "next_actions": ["publish_rule", "cancel"]
                }

            return rule_response
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to fetch rule with id '{rule_id}': {str(e)}",
                "rule_id": rule_id
            }

    @mcp.tool()
    def fetch_cc_rule_by_name(rule_name: str) -> Dict[str, Any]:
        """
        Fetch rule details by rule name from the **compliancecow**.

        Args:
            rule_name: Rule name of the rule to retrieve
            
        Returns:
            Dict containing complete rule structure and metadata
        """
        
        try:

            rule_response = rule.fetch_cc_rule_by_name(rule_name)
            logger.debug(f"fetch_cc_rule_by_name: rule_output: {rule_response}\n")

            if len(rule_response) == 0:
                return {
                    "success": False,
                    "rule_name": rule_name,
                    "error": f"Rule '{rule_name}' not found in ComplianceCow. This means the rule is not published or does not exist in ComplianceCow.",
                    "next_actions": ["publish_rule", "cancel"]
                }

            return rule_response
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to fetch rule with id '{rule_name}': {str(e)}",
                "rule_name": rule_name
            }
    
    @mcp.tool()
    def publish_rule(rule_name: str, cc_rule_name: str = None) -> Dict[str, Any]:
        """
        Publish a rule to make it available for ComplianceCow system.

        CRITICAL WORKFLOW RULES:
        - **MANDATORY: Check rule status to ensure rule is fully developed before publishing**
        - MUST FOLLOW THESE STEPS EXACTLY
        - DO NOT ASSUME OR SKIP ANY STEPS
        - APPLICATIONS FIRST, THEN RULE
        - WAIT FOR USER AT EACH STEP
        - NO SHORTCUTS OR BYPASSING ALLOWED

        RULE PUBLISHING HANDLING:

        WHEN TO USE:
        - After successful rule creation
        - User wants to make rule available for others
        - Rule has been tested and validated

        WORKFLOW (step-by-step with user confirmation):

        1. Fetch applications and check status
        - Call fetch_applications() to get available applications
        - Extract appTypes from ALL tasks in rule spec.tasks[].appTags.appType - MUST TAKE ALL THE TASKS APPTYPE AND REMOVE DUPLICATES - CRITICAL: DO NOT SKIP ANY TASK APPTYPES
        - Match ALL task appTypes with applications app_type to get application_class_name
        - Call check_applications_publish_status() for ALL matched applications

        2. Present consolidated applications with meaningful format
        Applications for your rule:
        [1] App Name | Type: xyz | Status: Published | Action: Republish
        [2] App Name | Type: abc | Status: Not Published | Action: Publish
        
        Select applications to publish: ___
        - MANDATORY: WAIT for user selection before proceeding to next step
        - DO NOT CONTINUE without explicit user input
        - BLOCK execution until user provides selection
        - STOP HERE: Cannot proceed to step 3 without user response
        - HALT WORKFLOW: Wait for user to select application numbers
        - NEVER SKIP THIS STEP: User must select applications first
        - ALWAYS ASK FOR SELECTION EVEN IF ALL APPLICATIONS ARE PUBLISHED

        3. Publish selected applications (BLOCKED until step 2 complete)
        - ENTRY REQUIREMENT: User selection from step 2 must be provided
        - PREREQUISITE CHECK: Verify user provided application numbers
        - CANNOT EXECUTE: Without completing step 2 user selection
        - Get user selection numbers
        - Call publish_application() for selected applications only
        - Inform user whether successfully published or not
        - CHECKPOINT: All applications must be published before rule steps

        4. Check rule publication status (APPLICATIONS MUST BE COMPLETE FIRST)
        - GATE KEEPER: Cannot proceed without application publishing completion
        - MANDATORY PREREQUISITE: All application steps finished
        - BLOCKED ACCESS: No rule operations until applications handled
        - Call check_rule_publish_status()
        - Check response valid field:
            - True = Already published
            - False = Not published

        5. Handle rule publishing based on status
        If valid=False (not published):
        - Show: "Rule is not published. Do you want to publish it? (yes/no)"
        - If yes: Proceed with publishing using current name
        
        If valid=True (already published):
        - Show: "Rule is already published. Choose option:"
            - [1] Republish with same name
            - [2] Publish with another name
        - Get user choice

        6. Handle alternative name logic
        If "another name" chosen:
            1. Ask: "Enter new rule name: ___"
            2. Call check_rule_publish_status(new_name)
            3. If name exists: "Name already exists. Choose option:"
                - [1] Use same name (republish)
                - [2] Enter another name
            4. If name available: Proceed with new name
            5. Keep checking until user chooses available name or decides to republish existing

        7. Final publication
        - Call publish_rule() with confirmed name
        - Inform user: "Published successfully" or "Publication failed"

        8. Rule Association:
            - Publishes the rule to make it available for control attachment
            - Ask user: "Do you want to attach this rule to a ComplianceCow control? (yes/no)"
            - If yes: Proceed to associate the rule with control and request assessment name and control alias from the user
            - If no: End workflow

        EXECUTION CONTROL MECHANISMS:
        - STEP GATE: Each step requires completion before next
        - USER GATE: Each step requires user input/confirmation
        - EXECUTION BLOCKER: No tool calls without user response
        - WORKFLOW ENFORCER: Steps cannot be skipped or assumed
        - SEQUENTIAL LOCK: Must complete in exact order

        Args:
            rule_name: Name of the rule to publish
            cc_rule_name: Optional alternative name for publishing
            
        Returns:
            Dict with publication status and details
        """
        try:
            headers = wsutils.create_header()
            
            # Prepare request data
            request_data = {
                "ruleName": rule_name
            }
            
            # Add ccRuleName only if provided
            if cc_rule_name:
                request_data["ccRuleName"] = cc_rule_name
            
            publish_resp = wsutils.post(
                path=wsutils.build_api_url(endpoint=constants.URL_PUBLISH_RULE),
                data=json.dumps(request_data),
                header=headers
            )

            if publish_resp and publish_resp.get("message") and  publish_resp.get("message") == "Rule has been published successfully":
                return {
                    "success": True,
                    "published": True,
                    "rule_info": publish_resp.get("items"),
                    "message": f"Rule '{rule_name}' published successfully"
                }
            else:
                return {
                    "success": False,
                    "published": False,
                    "error": f"Rule '{rule_name}' failed to publish: {publish_resp}",
                    "rule_info": []
                }

        except Exception as e:
            return {
                "success": False,
                "published": False,
                "error": f"Failed to publish rule: {str(e)}",
                "rule_info": []
            }
            


    @mcp.tool()
    def fetch_assessments(categoryId: str = "", categoryName: str = "", assessmentName: str = "") -> vo.AssessmentListVO:
        """
        Fetch the list of available assessments in ComplianceCow.  

        TOOL PURPOSE:
        - Retrieves a list of available assessments if no specific match is provided.  
        - Returns only basic assessment info (id, name, category) without the full control hierarchy.  
        - Used to confirm the assessment name while attaching a rule to a specific control.  

        Args:
            categoryId (Optional[str]): Assessment category ID.  
            categoryName (Optional[str]): Assessment category name.  
            assessmentName (Optional[str]): Assessment name.  

        Returns:
            - assessments (List[Assessments]): A list of assessment objects, each containing:  
                - id (str): Unique identifier of the assessment.  
                - name (str): Name of the assessment.  
                - category_name (str): Name of the category.  
            - error (Optional[str]): An error message if any issues occurred during retrieval.  
        """
        try:
            params = {
                "fields": "basic",
                "category_id": categoryId,
                "category_name_contains": categoryName,
                "name_contains": assessmentName
            }

            assessments = rule.get_assessments(params)
            logger.debug("assessment_output: {}\n".format(assessments))
            return assessments

        except Exception:
            return vo.AssessmentListVO(error="Facing internal error")

    @mcp.tool()
    def fetch_leaf_controls_of_an_assessment(assessment_id: str = "") -> Any:
        """
        To fetch the only the **leaf controls** for a given assessment.
        If assessment_id is not provided use other tools to get the assessment and its id.
        
        Args:
            - assessment_id (str, required): Assessment id or plan id.

        Returns:
            - controls (List[AutomatedControlVO]): List of controls
                - id (str): Control ID.
                - displayable (str): Displayable name or label.
                - alias (str): Alias of the control.
                - activationStatus (str): Activation status.
                - ruleName (str): Associated rule name.
                - assessmentId (str): Assessment identifier.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
        """
        try:
            params = {
                "fields": "basic",
                "skip_prereq_ctrl_priv_check": "false",
                "page": 1,
                "page_size": 100,
                "plan_id": assessment_id,
                "is_leaf_control":True
            }
        
            leaf_controls = rule.get_assessment_controls(params)
            logger.debug(f"leaf_controls_output: {leaf_controls}\n")
            
            if isinstance(leaf_controls, list):
                return leaf_controls
            else:
                return {"error": "Failed to fetch leaf controls"}
        except Exception as e:
            return  {"error": "Failed to fetch leaf controls"}

        
    @mcp.tool()
    def verify_control_in_assessment(assessment_name: str, control_alias: str) -> Dict[str, Any]:
        """
        Verify the existence of a specific control by alias within an assessment and confirm it is a leaf control.

        CONTROL VERIFICATION AND VALIDATION:
        - Confirms the control with the specified alias exists in the given assessment.
        - Validates that the control is a leaf control (eligible for rule attachment).
        - Checks if a rule is already attached to the control.
        - Returns control details and attachment status.

        LEAF CONTROL IDENTIFICATION:
        - A control is considered a leaf control if:
        - leafControl = true, OR
        - has no planControls array, OR
        - planControls array is empty.
        - Only leaf controls can have rules attached.
        - If the control is not a leaf control, an error will be returned.

        Args:
            assessment_name: Name of the assessment.
            control_alias: Alias of the control to verify.

        Returns:
            Dict containing control details, leaf status, and rule attachment info.
        """
    
        try:

            assessment_params = {
                "fields": "basic",
                "skip_prereq_ctrl_priv_check": "false",
                "name": assessment_name,
                "is_leaf_control":True
            }
            
            assessments = rule.get_assessments(assessment_params)
            logger.debug("assessment_output_for_control_checking: {}\n".format(assessments))

            if len(assessments) == 0:
                return {"error":f"The requested assessment named {assessment_name} was not found."}
            
            assessment = assessments[0]

            control_params = {
                "fields": "basic",
                "skip_prereq_ctrl_priv_check": "false",
                "page_size": 500,
                "plan_id": assessment.id,
                "is_leaf_control":True
            }

            leaf_controls = rule.get_assessment_controls(control_params)

            if not leaf_controls or not isinstance(leaf_controls, list):
                return {"error": f"No leaf controls found for assessment '{assessment_name}'."}
            logger.debug(f"leaf_controls_output: {leaf_controls}\n")

            for control in leaf_controls:
                if str(control.alias) == control_alias:
                    if control.ruleId:
                        return {
                            "success": True,
                            "assessment_name": assessment_name,
                            "control_alias": control_alias,
                            "control_info": control,
                            "warning": f"Control '{control_alias}' already has a rule attached (Rule ID: {control.ruleId})",
                            "message": f"Control found but already has rule attached. Options: 1) View existing rule details, 2) Override with new rule attachment",
                            "next_actions": ["view_existing_rule", "override_attachment", "cancel"]
                        }

                    return {
                        "success": True,
                        "assessment_name": assessment_name,
                        "control_alias": control_alias,
                        "control_info": control,
                        "message": f"Leaf control '{control_alias}' found and available for rule attachment.",
                        "ready_for_attachment": True
                    }
                
            return {
                "success": False,
                "assessment_name": assessment_name,
                "control_alias": control_alias,
                "control_info": control,
                "error": f"Control alias '{control_alias}' was not found as a leaf control in assessment '{assessment_name}'.",
                "message": f"The control alias '{control_alias}' is either not present or is not a leaf control in the specified assessment '{assessment_name}'. Please make sure you provide a valid, available leaf control alias.",
                "next_actions": ["retry_with_valid_leaf_control", "cancel"]
            }
                    
        except Exception as e:
            return {
                "success": False,
                "assessment_name": assessment_name,
                "control_alias": control_alias,
                "error": f"Failed to find control: {str(e)}",
                "message": f"Error occurred while searching for the control **'{control_alias}'** in assessment **'{assessment_name}'**."
            }

    @mcp.tool()
    def check_applications_publish_status(app_info: List[Dict]) -> Dict[str, Any]:
        """
            Check publication status for each application in the provided list.

            app_info structure is [{"name":["ACTUAL application_class_name"]}]
            
            Args:
                app_info: List of application objects to check
                
            Returns:
                Dict with publication status for each application.
                Each app will have 'published' field: True if published, False if not.
        """
        try:
            headers = wsutils.create_header()
            
            app_resp = wsutils.post(
                path=wsutils.build_api_url(endpoint=constants.URL_FETCH_CC_APPLICATIONS),
                data=json.dumps(app_info),
                header=headers
            )

            if len(app_resp) > 0:
                return {
                    "success": True,
                    "app_info": app_resp
                }
            else:
                return {
                    "success": False,
                    "error": "No application details found",
                    "app_info": []
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to fetch application information: {str(e)}",
                "app_info": []
            }


    @mcp.tool()
    def check_rule_publish_status(rule_name: str) -> Dict[str, Any]:
        """
        Check if a rule is already published.

        - If not published → publish the rule so it becomes available for control attachment  
        - Once published, prompt the user:  
        "Do you want to attach this rule to a ComplianceCow control? (yes/no)"  
        - If yes → ask for assessment name and control alias to proceed with association  
        - If no → end workflow  

        Args:
            rule_name: Name of the rule to check

        Returns:
            Dict with publication status and details
        """
        try:
            headers = wsutils.create_header()
            
            # Prepare request data
            request_data = {
                "ruleName": rule_name,
                "host": ""
            }
            
            rule_resp = wsutils.post(
                path=wsutils.build_api_url(endpoint=constants.URL_FETCH_CC_RULES),
                data=json.dumps(request_data),
                header=headers
            )

            # Check if response has items and if items list is not empty
            if rule_resp and rule_resp.get("items") and len(rule_resp.get("items", [])) > 0:
                return {
                    "success": True,
                    "published": True,
                    "rule_info": rule_resp.get("items"),
                    "message": f"Rule '{rule_name}' is already published"
                }
            else:
                return {
                    "success": True,
                    "published": False,
                    "rule_info": [],
                    "message": f"Rule '{rule_name}' is not published"
                }

        except Exception as e:
            return {
                "success": False,
                "published": False,
                "error": f"Failed to check rule publish status: {str(e)}",
                "rule_info": []
            }


    @mcp.tool()
    def publish_application(rule_name: str, app_info: List[Dict]) -> Dict[str, Any]:
        """
        Publish applications to make them available for rule execution.
        
        Args:
            rule_name: Name of the rule these applications belong to
            app_info: List of application objects to publish
            
        Returns:
            Dict with publication results for each application
        """
        try:
            headers = wsutils.create_header()
            
            # Prepare request data
            request_data = {
                "ruleName": rule_name,
                "appDetails": app_info
            }
            
            publish_resp = wsutils.post(
                path=wsutils.build_api_url(endpoint=constants.URL_PUBLISH_APPLICATIONS),
                data=json.dumps(request_data),
                header=headers
            )

            if publish_resp and len(publish_resp) > 0:
                # Separate successful and failed applications
                successful_apps = [app for app in publish_resp if "Error" not in app]
                failed_apps = [app for app in publish_resp if "Error" in app]
                
                if failed_apps:
                    failed_app_names = [app.get("appName", "Unknown") for app in failed_apps]
                    return {
                        "success": False,
                        "published": False,
                        "error": f"Failed applications: {', '.join(failed_app_names)}",
                        "successful_apps": successful_apps,
                        "failed_apps": failed_apps,
                        "message": f"Some applications failed to publish for rule '{rule_name}'"
                    }
                else:
                    return {
                        "success": True,
                        "published": True,
                        "successful_apps": successful_apps,
                        "failed_apps": [],
                        "message": f"All applications for rule '{rule_name}' published successfully"
                    }
            else:
                return {
                    "success": False,
                    "published": False,
                    "error": "No response received from publish endpoint",
                    "successful_apps": [],
                    "failed_apps": []
                }

        except Exception as e:
            return {
                "success": False,
                "published": False,
                "error": f"Failed to publish applications: {e}",
                "successful_apps": [],
                "failed_apps": []
            }
        

@mcp.tool()
def get_tasks_summary() -> str:
    """
    Resource containing minimal task information for initial selection.
    
    This tool is also used as a fallback resource when fetch_tasks_suggestions is disabled or does not return suitable matches, ensuring
    the user always has access to a broader list of available tasks for manual selection.

    This resource provides only the essential information needed for task selection:
    - Task name and display name
    - Brief description
    - Purpose and capabilities
    - Tags for categorization
    - Inputs/Outputs params with minimal details
    - Basic README summary

    Use this for initial task discovery and selection. Detailed information can be
    retrieved later using `tasks://details/{task_name}` for selected tasks only.

    AUTOMATIC OUTPUT ANALYSIS BY INTENTION:
    - MANDATORY: Analyze each task's output purpose and completion level during selection
    - IDENTIFY output intentions that require follow-up processing:
        * SPLITTING INTENTION: Outputs that divide data into separate categories → REQUIRE consolidation
        * EXTRACTION INTENTION: Outputs that pull raw data without formatting → REQUIRE transformation  
        * VALIDATION INTENTION: Outputs that check compliance without final reporting → REQUIRE analysis/reporting
        * PROCESSING INTENTION: Outputs that transform data but don't create final deliverables → REQUIRE finalization

    OUTPUT COMPLETION ASSESSMENT:
    - EVALUATE: Does this output serve as a final deliverable for end users?
    - ASSESS: Is this output consumable without additional processing?
    - DETERMINE: Does this output require combination with other outputs to be meaningful?
    - IDENTIFY: Is this output an intermediate step in a larger workflow?

    WORKFLOW COMPLETION ENFORCEMENT:
    - NEVER present task selections that end with intermediate processing outputs
    - AUTOMATICALLY suggest tasks that fulfill incomplete intentions
    - ENSURE every workflow produces actionable final deliverables
    - RECOMMEND tasks that bridge gaps between current outputs and user goals

    Mandatory functionality:
    - Retrieve a list of task summaries based on the user's request
    - Analyze task outputs and suggest additional tasks for workflow completion
    - If no matching task is found for the requested functionality, prompt user for confirmation
    - Based on user response, either proceed accordingly or create support ticket using create_support_ticket()

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
            
            inputs = [{"name":input.name,"description":input.description} for input in task.inputs]
            outputs = [{"name":output.name,"description":output.description} for output in task.outputs]


            # Minimal info for selection
            task_summary = {"name": task.name, "displayName": task.displayName, "description": task.description, "purpose": rule.extract_purpose_from_description(task.description), "tags": task.tags, "capabilities": capabilities, "input_params":inputs, "output_params": outputs, "has_templates": any(inp.templateFile for inp in task.inputs), "app_type": task.appTags.get("appType", ["generic"])[0] if task.appTags.get("appType") else "generic"}
            tasks_summary.append(task_summary)

        return json.dumps({"total_tasks": len(tasks_summary), "tasks": tasks_summary, "message": f"Found {len(tasks_summary)} available tasks - use tasks://details/{{task_name}} for full details", "categories": rule.categorize_tasks_by_tags(tasks_summary)}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"An error occurred while fetching the task summary: {e}", "tasks": []})


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

    INTENTION-BASED OUTPUT CHAINING:
    - ANALYZE output purpose: Is this meant for direct user consumption or further processing?
    - ASSESS completion level: Does this output fulfill the user's end goal or serve as a stepping stone?
    - EVALUATE consolidation needs: Are multiple outputs meant to be combined for complete picture?
    - DETERMINE transformation requirements: Does raw output need formatting for usability?

    WORKFLOW GAP DETECTION:
    - IDENTIFY outputs that represent partial solutions to user problems
    - DETECT outputs that split information requiring reunification
    - RECOGNIZE outputs that extract data without presenting insights
    - FLAG outputs that validate without providing actionable summaries

    COMPLETION INTENTION MATCHING:
    - SUGGEST tasks that transform intermediate outputs into final deliverables
    - RECOMMEND tasks that consolidate split information into unified reports
    - PROPOSE tasks that add analysis layer to raw validation results
    - ENSURE suggested tasks align with user's stated end goals

    IMPORTANT (MANDATORY BEHAVIOR):
    If the requested task is not found with the user's specification, the system MUST:
    1. Prompt the user to choose how to proceed including the below option.
    - Option: Create task development Ticket.
    2. Wait for the user's response before taking any further action.
    3. If the user chooses to create a task development ticket, call `create_support_ticket()` via the MCP tool, collecting the required input details from the user before submitting.

    Args:
    task_name: The name of the task for which to retrieve details

    Returns:
        A dictionary containing the complete task information if found,
        OR executes the user-selected alternative approach,
        OR creates a support ticket (with collected details) if chosen
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


@mcp.tool()
def get_template_guidance(task_name: str, input_name: str) -> Dict[str, Any]:
    """Get detailed guidance for filling out a template-based input.

    COMPLETE TEMPLATE HANDLING PROCESS:

    STEP 1 - TEMPLATE IDENTIFICATION:
    - Called for inputs that have a templateFile property
    - Provides decoded template content and structure explanation
    - Returns required fields, format-specific tips, and validation rules

    PREFILLING PROCESS:
    1. Analyze template structure for external dependencies
    2. Prefill template with realistic values based on the instructions

    RELEVANCE FILTERING:
    - ANALYZE task description and user use case to create targeted search queries
    - EXTRACT key terms from rule purpose and task capabilities
    - COMBINE system name with specific functionality being configured
    - PRIORITIZE documentation that matches the exact use case scenario

    STEP 3 - ENHANCED TEMPLATE PRESENTATION TO USER:
    Show the template with this EXACT format:
    "Now configuring: [X of Y inputs]

    Task: {task_name}
    Input: {input_name} - {description}

    You can:
    - Accept these prefilled values (type 'accept')
    - Modify specific sections (provide your modifications)
    - Replace entirely (provide your complete configuration)

    Please review and confirm or modify the prefilled configuration:"

    STEP 4 - FALLBACK TO ORIGINAL TEMPLATE:
    If no documentation found or prefilling fails:
    - Show original empty template with standard format
    - Include note: "No documentation found for prefilling. Please provide your configuration."
    - Continue with existing workflow

    STEP 5 - COLLECT USER CONTENT:
    - Wait for the user to provide their response (accept/modify/replace)
    - Handle "accept" by using prefilled content
    - Handle modifications by merging with prefilled baseline
    - Handle complete replacement with user content
    - Do NOT proceed until the user provides content
    - NEVER use template content as default values without documentation analysis

    STEP 6 - PROCESS TEMPLATE INPUT:
    - Call collect_template_input(task_name, input_name, user_content)
    - Include documentation source metadata
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
    - Documentation standard compliance (when applicable)

    CRITICAL TEMPLATE RULES:
    - ALWAYS call get_template_guidance() for inputs with templates
    - ALWAYS analyze documentation before showing template to user
    - ALWAYS show the prefilled template (or original if no docs found) with exact presentation format
    - ALWAYS wait for the user to provide response (accept/modify/replace)
    - ALWAYS call collect_template_input() to process user content
    - NEVER use template content directly - always use documentation-enhanced or user-provided content
    - ALWAYS use returned file URLs in rule structure

    PROGRESS TRACKING:
    - Show "Now configuring: [X of Y inputs]" for user progress
    - Include clear task and input identification
    - Provide format-specific guidance and tips
    - Include documentation analysis results and source citations

    Args:
        task_name: Name of the task
        input_name: Name of the input that has a template

    Returns:
        Dict containing template content, documentation analysis, prefilled values, and guidance
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
        available_task_inputs=[]
        for inp in task.inputs:
            available_task_inputs.append(inp.name)
            if inp.name == input_name:
                task_input = inp
                break

        if not task_input:
            return {"success": False, "error": f"Input '{input_name}' not found in task '{task_name}'. Available inputs are: {available_task_inputs}"}

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
def collect_template_input(task_name: str, input_name: str, user_content: Any) -> Dict[str, Any]:
    """Collect user input for template-based task inputs.

    TEMPLATE INPUT PROCESSING (Enhanced with Progressive Saving):
    - Validates user content against template format (JSON/TOML/YAML)
    - Handles JSON arrays and objects properly
    - Checks for required fields from template structure
    - Uploads validated content as file (ONLY for FILE dataType inputs)
    - Returns file URL for use in rule structure
    - MANDATORY: Gets final confirmation for EVERY input before proceeding
    - CRITICAL: Only processes user-provided content, never use default templates
    - NEW: Prepared for automatic rule updates in confirm step

    JSON ARRAY HANDLING (Preserved):
    - Properly validates JSON arrays: [{"key": "value"}, {"key": "value"}]
    - Validates JSON objects: {"key": "value", "nested": {"key": "value"}}
    - Handles complex nested structures with arrays and objects
    - Validates each array element and object property

    VALIDATION REQUIREMENTS (Preserved):
    - JSON: Must be valid JSON (arrays/objects) with proper brackets and quotes
    - TOML: Must follow TOML syntax with proper sections [section_name]
    - YAML: Must have correct indentation and structure
    - XML: Must be well-formed XML with proper tags
    - Required fields: All template fields must be present in user content

    STREAMLINED WORKFLOW:
    1. User provides template content
    2. Validate and process immediately
    3. Auto-proceed if validation passes

    FILE NAMING CONVENTION (Preserved):
    - Format: {task_name}_{input_name}.{extension}
    - Extensions: .json, .toml, .yaml, .xml, .txt based on format

    WORKFLOW INTEGRATION (Enhanced):
    1. Called after get_template_guidance() shows template to user
    2. User provides their actual configuration content
    3. This tool validates content (including JSON arrays)
    4. Shows content preview and asks for confirmation
    5. Only after confirmation: uploads file or stores in memory
    6. Returns file URL or memory reference for rule structure
    7. NEW: Prepared for rule update in confirm_template_input()

    CRITICAL RULES (Preserved):
    - ONLY upload files for inputs with dataType = "FILE" or "HTTP_CONFIG"
    - Template inputs and HTTP_CONFIG inputs are typically file types and need file uploads
    - Store non-FILE template content in memory
    - ALWAYS get final confirmation before proceeding
    - Handle JSON arrays properly: validate each element
    - Never use template defaults - always use user-provided content

    MANDATORY: Task-sequential collection only. Sanitize input names (alphanumeric + underscore).

    Args:
        task_name: Name of the task this input belongs to
        input_name: Name of the input parameter
        user_content: Content provided by the user based on the template

    Returns:
        Dict containing validation results and file URL or memory reference,
        prepared for progressive rule updates
    """
    try:
        task = None
        tasks_resp = rule.fetch_task_api(params={"name": task_name})
        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            task = TaskVO.from_dict(tasks_resp["items"][0])
        if not task:
            return {"success": False, "error": f"Task '{task_name}' not found in available tasks"}

        # Find the specific input
        task_input = None
        available_task_inputs=[]
        for inp in task.inputs:
            if inp.name == input_name:
                available_task_inputs.append(inp.name)
                task_input = inp
                break

        if not task_input:
            return {"success": False, "error": f"Input '{input_name}' not found in task '{task_name}'. Available inputs are: {available_task_inputs}"}
        
        # Check type and convert to string
        if isinstance(user_content, (dict, list)):
            user_content = json.dumps(user_content)
        else:
            user_content = str(user_content)

        # Validate the content including JSON arrays (preserved validation)
        validation_result = rule.validate_template_content_enhanced(task_input, user_content)
        if not validation_result["valid"]:
            return {"success": False, "error": "Content validation failed", "validation_errors": validation_result["errors"], "suggestions": validation_result["suggestions"]}

        # Generate content preview for confirmation (preserved)
        content_preview = rule.generate_content_preview(user_content, task_input.format)

        # Need final confirmation before storing/uploading
        return {
            "success": True,
            "task_name": task_name,
            "input_name": input_name,
            "validated_content": user_content,
            "content_preview": content_preview,
            "needs_final_confirmation": True,
            "data_type": task_input.dataType,
            "format": task_input.format,
            "is_file_type": task_input.dataType.upper() in ["FILE", "HTTP_CONFIG"],
            "final_confirmation_message": f"You provided this {task_input.format.upper()} content:\n\n{content_preview}\n\nIs this correct? (yes/no)",
            "message": "Template content validated - needs final confirmation before processing and rule update",
            "ready_for_rule_update": True  # NEW: Indicates this input is ready for rule progression
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to process template input: {e}"}


@mcp.tool()
def confirm_template_input(rule_name: str, task_name: str, rule_input_name: str, input_name: str, confirmed_content: str) -> Dict[str, Any]:
    """Confirm and process template input after user validation.

    CONFIRMATION PROCESSING (Enhanced with Automatic Rule Updates):
    - Handles final confirmation of template content
    - Uploads files for FILE dataType inputs
    - Stores content in memory for non-FILE inputs
    - MANDATORY step before proceeding to next input
    - NEW: Automatically updates the rule with new input after processing
    - Skips confirmation if the user accepts the suggested template

    PROCESSING RULES (Enhanced):
    - FILE dataType: Upload content as file, return file URL
    - HTTP_CONFIG dataType: Upload content as file, return file URL
    - Non-FILE dataType: Store content in memory
    - Include metadata about confirmation and timestamp
    - NEW: Automatic rule update with new input data

    AUTOMATIC RULE UPDATE PROCESS:
    After successful input processing, this tool automatically:
    1. Fetches the current rule structure
    2. Adds the new input to spec.inputs
    3. Updates spec.inputsMeta__ with input metadata
    4. Calls create_rule() to save the updated rule
    5. Rule status will be auto-detected (DRAFT → collecting_inputs → READY_FOR_CREATION)

    UI DISPLAY REQUIREMENT:
    - The file URL must ALWAYS be displayed to the user in the UI, allowing the user to view or download the file directly.
    
    Args:
        rule_name: Descriptive name for the rule based on the user's use case. 
                   Note: Use the same rule name for all inputs that belong to this rule.
                   Example: rule_name = "MeaningfulRuleName"
        task_name: Name of the task this input belongs to
        input_name: Name of the input parameter
        rule_input_name: Must be one of the values defined in the rule structure's inputs
        confirmed_content: The content user confirmed

    Returns:
        Dict containing processing results (file URL or memory reference) and rule update status
    """
    try:
        task = None
        tasks_resp = rule.fetch_task_api(params={"name": task_name})
        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            task = TaskVO.from_dict(tasks_resp["items"][0])
        if not task:
            return {"success": False, "error": f"Task '{task_name}' not found in available tasks"}

        # Find the specific input
        task_input = None
        available_task_inputs=[]
        for inp in task.inputs:
            available_task_inputs.append(inp.name)
            if inp.name == input_name:
                task_input = inp
                break

        if not task_input:
            return {"success": False, "error": f"Input '{input_name}' not found in task '{task_name}'. Available inputs are: {available_task_inputs}"}

        # Check if this is a FILE or HTTP_CONFIG type input that needs upload (preserved logic)
        if task_input.dataType.upper() in ["FILE", "HTTP_CONFIG"]:
            # Generate appropriate filename
            file_extension = rule.get_file_extension(task_input.format)
            file_name = f"{task_name}_{input_name}{file_extension}"

            # Upload the file and get URL
            upload_result = upload_file.fn(rule_name=rule_name, file_name=file_name, content=confirmed_content)

            if upload_result["success"]:
                input_value = upload_result["file_url"]
                storage_type = "FILE"
            else:
                return {"success": False, "error": f"File upload failed: {upload_result.get('error', 'Unknown error')}"}
        else:
            # For non-FILE inputs, store content in memory (don't upload)
            input_value = confirmed_content
            storage_type = "MEMORY"

        # NEW: AUTOMATIC RULE UPDATE WITH NEW INPUT
        rule_update_success = False
        rule_status = "UNKNOWN"
        rule_progress = 0
        
        try:
            # Fetch current rule
            current_rule = fetch_rule.fn(rule_name)
            logger.info(f"current_rule ::{current_rule}")
            if current_rule["success"]:
                rule_structure = current_rule["rule_structure"]

                logger.info(f"rule_structure 111 ::{rule_structure}")

                if not rule.is_valid_key(rule_structure["spec"],"inputs"):
                    rule_structure["spec"]["inputs"] = {}
                
                # Add new input to rule structure
                rule_structure["spec"]["inputs"][rule_input_name] = input_value
                
                # Add/update input metadata
                input_meta = {
                    "name": rule_input_name,
                    "dataType": task_input.dataType,
                    "required": task_input.required,
                    "defaultValue": input_value
                }
                if hasattr(task_input, 'format') and task_input.format:
                    input_meta["format"] = task_input.format

                logger.info(f"rule_structure 2222 ::{rule_structure}")

                if not rule.is_valid_key(rule_structure["spec"],"inputsMeta__"):
                    rule_structure["spec"]["inputsMeta__"] = []
                
                # Remove existing metadata for this input and add new one
                existing_meta = rule_structure["spec"]["inputsMeta__"]
                rule_structure["spec"]["inputsMeta__"] = [m for m in existing_meta if m["name"] != rule_input_name]
                rule_structure["spec"]["inputsMeta__"].append(input_meta)


                logger.info(f"rule_structure 3333 ::{rule_structure}")
                
                # Update rule - status will be auto-detected
                update_result = create_rule.fn(rule_structure)
                logger.info(f"update_result ::{update_result}")
                rule_update_success = update_result["success"]
                rule_status = update_result.get("detected_status", "UNKNOWN")
                rule_progress = update_result.get("progress_percentage", 0)
                
        except Exception as update_error:
            # Log the error but don't fail the input processing
            print(f"Warning: Rule update failed for {rule_name}: {update_error}")

        return {
            "success": True,
            "task_name": task_name,
            "input_name": input_name,
            "file_url": input_value if storage_type == "FILE" else None,
            "stored_content": input_value if storage_type == "MEMORY" else None,
            "filename": file_name if storage_type == "FILE" else None,
            "content_size": len(confirmed_content),
            "storage_type": storage_type,
            "data_type": task_input.dataType,
            "format": task_input.format,
            "timestamp": datetime.now().isoformat(),
            "rule_name": rule_name,
            "rule_updated": rule_update_success,
            "rule_status": rule_status,
            "rule_progress": rule_progress,
            "message": f"Template file {'uploaded' if storage_type == 'FILE' else 'stored'} successfully for {input_name} in {task_name}. Rule '{rule_name}' {'updated automatically' if rule_update_success else 'update failed'}."
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to confirm template input: {e}"}


@mcp.tool()
def upload_file(rule_name: str, file_name: str, content: Any, content_encoding: str = "utf-8") -> Dict[str, Any]:
    """
    Upload file content and return file URL for use in rules.

    ENHANCED FILE UPLOAD PROCESS:
    - Automatically detects file format from filename and content
    - Validates and fixes common formatting issues for JSON, YAML, TOML, CSV, XML
    - Accepts JSON arrays in various formats: raw, single-line, multi-line, or escaped (auto-formatted).
    - Normalizes CSV delimiters and whitespace
    - Reformats content with proper indentation/structure
    - No user preview required - validation happens automatically
    - Returns detailed validation results and file URL

    SUPPORTED INPUT FORMATS:
    - Raw JSON: {"key": "value"} or [{"key": "value"}]
    - Escaped JSON: "{\"key\": \"value\"}" 
    - Complex escaped: "[\{\\\"repository\\\":\\\"name\\\",\\\"owner\\\":\\\"org\\\"}]"
    - Standard strings for other formats (YAML, TOML, CSV, XML)

    AUTOMATIC FORMAT PROCESSING:
    - JSON: Detects escaped strings, unescapes, validates syntax, reformats with indentation
    - Raw JSON objects/arrays: Automatically converts to proper JSON string format
    - YAML: Validates structure, reformats with proper indentation  
    - TOML: Validates sections and key-value pairs, reformats
    - CSV: Detects delimiter, strips cell whitespace, normalizes format
    - XML: Validates well-formed structure
    - Other formats: Pass through as-is

    VALIDATION RESULTS:
    - Returns success/failure status with detailed error messages
    - Provides format-specific validation feedback
    - Indicates if content was automatically reformatted
    - Includes file metadata (size, format, etc.)

    Args:
        rule_name: Descriptive name for the rule (same across all rule inputs)
        file_name: Name of the file to upload  
        content: File content (text or base64 encoded)
                 CRITICAL: Must be stringified if JSON content   
        content_encoding: Encoding of the content (utf-8, base64)

    Returns:
        Dict containing upload results: 
        {
            success: bool,
            file_url: str,
            filename: str,
            unique_filename: str,
            file_id: str,
            file_format: str,
            content_size: int,
            validation_status: str,
            was_formatted: bool,
            message: str,
            error: Optional[str]
        }
    """
    try:
        # Validate content encoding
        if content_encoding not in ["utf-8", "base64"]:
            return {
                "success": False,
                "error": f"Unsupported encoding: {content_encoding}",
                "filename": file_name,
                "supported_encodings": ["utf-8", "base64"]
            }

        # Check type and convert to string
        if isinstance(content, (dict, list)):
            content = json.dumps(content)
        else:
            content = str(content)

        # Decode content if base64
        if content_encoding == "base64":
            try:
                decoded_content = base64.b64decode(content).decode("utf-8")
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to decode base64 content: {e}",
                    "filename": file_name
                }
        else:
            decoded_content = content

        # Auto-detect file format
        file_format = rule.detect_file_format(file_name, decoded_content)

        # Validate and format content automatically
        formatted_content, is_valid, validation_message = rule.validate_and_format_content(
            decoded_content, file_format)

        # If validation failed, return error with details
        if not is_valid:
            return {
                "success": False,
                "error": f"File validation failed: {validation_message}",
                "filename": file_name,
                "file_format": file_format,
                "suggestion": "Please check your file content and format, then try again"
            }

        # Convert formatted content to base64 for upload
        encoded_content = base64.b64encode(
            formatted_content.encode("utf-8")).decode("utf-8")

        # Generate file ID and unique filename
        file_id = f"file_{abs(hash(encoded_content)) % 100000}"
        unique_file_name = f"{file_id}_{file_name}"

        # Upload file using existing API
        headers = wsutils.create_header()
        payload = {
            "fileName": unique_file_name,
            "fileContent": encoded_content,
            "ruleName": rule_name
        }

        file_upload_resp = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_UPLOAD_FILE),
            data=json.dumps(payload),
            header=headers
        )

        if rule.is_valid_key(file_upload_resp, "fileURL"):
            return {
                "success": True,
                "file_url": file_upload_resp["fileURL"],
                "filename": file_name,
                "unique_filename": unique_file_name,
                "file_id": file_id,
                "file_format": file_format,
                "content_size": len(formatted_content),
                "validation_status": validation_message,
                "was_formatted": formatted_content != decoded_content,
                "message": f"File '{file_name}' uploaded successfully with {file_format.upper()} validation"
            }

        return {
            "success": False,
            "error": "Upload API did not return file URL",
            "filename": file_name,
            "file_format": file_format
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Upload failed: {e}",
            "filename": file_name,
            "exception_type": type(e).__name__
        }
    

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
        available_task_inputs=[]
        for inp in task.inputs:
            available_task_inputs.append(inp.name)
            if inp.name == input_name:
                task_input = inp
                break

        if not task_input:
            return {"success": False, "error": f"Input '{input_name}' not found in task '{task_name}'. Available inputs are: {available_task_inputs}"}

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
def confirm_parameter_input(task_name: str, input_name: str, rule_input_name:str, confirmed_value: str, explaination: str, confirmation_type: str = "final", rule_name: str = None) -> Dict[str, Any]:
    """Confirm and store parameter input after user validation.

    CONFIRMATION PROCESSING (Enhanced with Automatic Rule Updates):
    - Handles final confirmation of parameter values
    - Stores confirmed values in memory
    - Supports both default value confirmation and final value confirmation
    - MANDATORY step before proceeding to next input
    - NEW: Automatically updates rule with parameter if rule_name provided

    CONFIRMATION TYPES (Preserved):
    - "default": User confirmed they want to use default value
    - "final": User confirmed their entered value is correct
    - Both types require explicit user confirmation

    STORAGE RULES (Enhanced):
    - Store all confirmed values in memory (never upload files)
    - Only store after explicit user confirmation
    - Include metadata about confirmation type and timestamp
    - NEW: Automatic rule update with parameter data

    AUTOMATIC RULE UPDATE PROCESS:
    If rule_name is provided, this tool automatically:
    1. Fetches the current rule structure
    2. Adds the parameter to spec.inputs
    3. Updates spec.inputsMeta__ with parameter metadata
    4. Calls create_rule() to save the updated rule
    5. Rule status will be auto-detected based on completion

    Args:
        task_name: Name of the task this input belongs to
        input_name: Name of the input parameter
        rule_input_name: Must be one of the values defined in the rule structure's inputs
        confirmed_value: The value user confirmed
        explanation: Add explanation only if dataType is JQ_EXPRESSION or SQL_EXPRESSION. This field provides details about the confirmed_value.
        confirmation_type: Type of confirmation ("default" or "final")
        rule_name: Optional rule name for automatic rule updates

    Returns:
        Dict containing stored value confirmation and rule update status
    """
    try:
        task = None
        tasks_resp = rule.fetch_task_api(params={"name": task_name})
        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            task = TaskVO.from_dict(tasks_resp["items"][0])
        if not task:
            return {"success": False, "error": f"Task '{task_name}' not found in available tasks"}

        # Find the specific input
        task_input = None
        available_task_inputs=[]
        for inp in task.inputs:
            available_task_inputs.append(inp.name)
            if inp.name == input_name:
                task_input = inp
                break

        if not task_input:
            return {"success": False, "error": f"Input '{input_name}' not found in task '{task_name}'. Available inputs are: {available_task_inputs}"}

        # Validate the confirmed value (preserved validation)
        validation_result = rule.validate_parameter_value(confirmed_value, task_input.dataType)
        if not validation_result["valid"]:
            return {"success": False, "error": "Confirmed value is invalid", "validation_errors": validation_result["errors"]}

        # NEW: AUTOMATIC RULE UPDATE WITH NEW PARAMETER (if rule_name provided)
        rule_update_success = False
        rule_status = "UNKNOWN"
        rule_progress = 0
        
        if rule_name:
            try:
                # Fetch current rule
                current_rule = fetch_rule.fn(rule_name)
                if current_rule["success"]:
                    rule_structure = current_rule["rule_structure"]
                    
                    # Add parameter to rule structure
                    rule_structure["spec"]["inputs"][rule_input_name] = validation_result["converted_value"]
                    
                    # Add/update parameter metadata
                    input_meta = {
                        "name": rule_input_name,
                        "dataType": task_input.dataType,
                        "required": task_input.required,
                        "defaultValue": validation_result["converted_value"]
                    }

                    # Add explanation if dataType is JQ_EXPRESSION or SQL_EXPRESSION
                    if task_input.dataType in ["JQ_EXPRESSION", "SQL_EXPRESSION"]:
                        input_meta["explanation"] = explaination
                    
                    if hasattr(task_input, 'format') and task_input.format:
                        input_meta["format"] = task_input.format
                    elif task_input.dataType.upper() == "FILE" and "." in input_meta["defaultValue"]:
                        input_meta["format"] = input_meta["defaultValue"].split(".")[-1]

                    # Update metadata list
                    existing_meta = rule_structure["spec"]["inputsMeta__"]
                    rule_structure["spec"]["inputsMeta__"] = [m for m in existing_meta if m["name"] != rule_input_name]
                    rule_structure["spec"]["inputsMeta__"].append(input_meta)
                    
                    # Update rule - status auto-detected
                    update_result = create_rule.fn(rule_structure)
                    rule_update_success = update_result["success"]
                    rule_status = update_result.get("detected_status", "UNKNOWN")
                    rule_progress = update_result.get("progress_percentage", 0)
                    
            except Exception as update_error:
                # Log the error but don't fail the parameter processing
                print(f"Warning: Rule update failed for {rule_name}: {update_error}")

        # Store the confirmed value in memory (preserved logic)
        return {
            "success": True,
            "task_name": task_name,
            "input_name": input_name,
            "stored_value": validation_result["converted_value"],
            "data_type": task_input.dataType,
            "required": task_input.required,
            "storage_type": "MEMORY",
            "confirmation_type": confirmation_type,
            "timestamp": datetime.now().isoformat(),
            "rule_name": rule_name,
            "rule_updated": rule_update_success,
            "rule_status": rule_status,
            "rule_progress": rule_progress,
            "message": f"Parameter value confirmed and stored in memory for {input_name}. Rule '{rule_name}' {'updated automatically' if rule_update_success and rule_name else 'not updated (no rule_name provided)'}."
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to confirm parameter input: {e}"}


# INPUT VERIFICATION TOOLS - MANDATORY WORKFLOW STEPS
@mcp.tool()
def prepare_input_collection_overview(selected_tasks: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    INPUT COLLECTION OVERVIEW & RULE CREATION

    Prepare and present input collection overview before starting any input collection.

    MANDATORY FIRST STEP - INPUT OVERVIEW PROCESS (Enhanced):
    This tool MUST be called before collecting any inputs. It analyzes all selected tasks and presents a complete overview of what inputs will be needed.

    ENHANCED WITH AUTOMATIC RULE CREATION:
    After user confirms the input overview, this tool automatically creates the initial rule structure with selected tasks. The rule will be saved with DRAFT status and can be progressively updated as inputs are collected.

    **MANDATORY WORKFLOW ENFORCEMENT - CRITICAL INSTRUCTION:**
    - AFTER user confirms the input overview, IMMEDIATELY call create_rule() with initial structure.
    - This call is MANDATORY and CANNOT be skipped or deferred.
    - The initial rule structure MUST be created before any input collection begins.
    - BLOCK all subsequent input collection if initial rule creation fails.
    - NEVER proceed to input collection without successful initial rule creation.
    - If create_rule() fails, STOP workflow and resolve the issue before continuing.
    - The rule creation establishes the foundation for progressive updates during input collection.


    **ENFORCEMENT STEPS:**
    1. Present overview to user
    2. Get user confirmation
    3. **IMMEDIATELY call create_rule() with initial structure that MUST INCLUDE inputs and inputsMeta__ sections WITH ACTUAL INPUT DATA - DO NOT LEAVE inputs and inputsMeta__ SECTION EMPTY - INPUTS AND INPUTSMETA__ ARE MANDATORY CORE COMPONENTS THAT MUST CONTAIN THE REQUIRED INPUT MAPPINGS - THIS IS NON-NEGOTIABLE - NO EXCEPTIONS**
    4. Verify rule creation success before proceeding
    5. Only then allow input collection to begin

    TASK-BY-TASK INPUT COLLECTION & VALIDATION (CRITICAL ENFORCEMENT):
    ═══════════════════════════════════════════════════════════════════
    MANDATORY WORKFLOW FOR EACH TASK:
    
    FOR EACH TASK in selected_tasks:
        STEP 1: Collect ALL inputs for current task
                - Use collect_template_input() for file/template inputs
                - Use collect_parameter_input() for parameter inputs
                - Wait for ALL task inputs to be collected
        
        STEP 2: **MANDATORY VALIDATION** (CANNOT BE SKIPPED)
                - Call validate_task_inputs(task_name, collected_inputs_for_this_task)
                - This MUST happen IMMEDIATELY after all task inputs are collected
                - BLOCK progression if validation fails
                - If validation fails:
                  * Show validation errors to user
                  * Allow input correction
                  * Re-validate with corrected inputs
                  * Only proceed when validation passes
        
        STEP 3: Move to next task ONLY after validation passes
                - Validation success = prerequisite for next task
                - No task can start input collection without previous task validation passing
    
    VALIDATION CHECKPOINT ENFORCEMENT:
        - After collecting inputs for each task, you MUST call:
            validate_task_inputs(<TaskName>, inputs)
        - Example:
            - After Task 1 → validate_task_inputs(Task1, inputs)
            - After Task 2 → validate_task_inputs(Task2, inputs)
            - After Task 3 → validate_task_inputs(Task3, inputs)
        - These serve as mandatory validation checkpoints between tasks.
        - Validation must NEVER be skipped, even if inputs appear correct.


    **SELECTIVE INPUT INCLUSION:**
    - DO NOT automatically include ALL task inputs in initial rule creation.
    - Only include inputs that are REQUIRED or explicitly needed for the user's use case.
    - Skip optional inputs unless user specifically requests them.
    - Additional inputs can be added later if needed during execution or refinement.

    **FAILURE HANDLING:**
    - If user confirms but create_rule() fails → STOP and fix issue.
    - If user declines → End workflow, no rule creation needed.
    - If create_rule() succeeds → Proceed to task-wise input collection and validation.
    - NEVER skip the create_rule() call after user confirmation.


    HANDLES DUPLICATE INPUT NAMES WITH TASK ALIASES (Preserved):
    - Creates unique identifiers for each task-alias-input combination.
    - Format: "{task_alias}.{input_name}" for uniqueness.
    - Prevents conflicts when multiple tasks have same input names or same task used multiple times.
    - Maintains clear mapping between task aliases and their specific inputs.
    - Task aliases should be simple, meaningful step indicators (e.g., "step1", "validation", "processing").

    OVERVIEW REQUIREMENTS (Preserved):
    1. Analyze ALL selected tasks with their aliases for input requirements.
    2. Categorize inputs: templates vs parameters.
    3. Create unique identifiers for each task-alias-input combination.
    4. Count total inputs needed.
    5. Present clear overview to user.
    6. Get user confirmation before proceeding.
    7. Return structured overview for systematic collection.
    8. NEW: Automatically create initial rule after user confirmation.

    OVERVIEW PRESENTATION FORMAT (Enhanced with Validation):
    
    INPUT COLLECTION OVERVIEW:

    I've analyzed your selected tasks. Here's what we need to configure:

    TASK 1: [TaskAlias] ([TaskName])
    ───────────────────────────────────
    Template Inputs:
    • [InputName] ([Format] file) - [Description]
      Unique ID: [TaskAlias.InputName]
    
    Parameter Inputs:
    • [InputName] ([DataType]) - [Description]
      Unique ID: [TaskAlias.InputName]
      Required: [Yes/No]
    
    ⚠️  VALIDATION CHECKPOINT: After collecting all Task 1 inputs, 
        validate_task_inputs() will be called before proceeding to Task 2.

    TASK 2: [TaskAlias] ([TaskName])
    ───────────────────────────────────
    [... similar structure ...]
    
    ⚠️  VALIDATION CHECKPOINT: After collecting all Task 2 inputs,
        validate_task_inputs() will be called before proceeding to Task 3.

    SUMMARY:
    - Total inputs needed: X
    - Template files: Y ([formats])
    - Parameter values: Z
    - Estimated time: ~[X] minutes
    - Validation checkpoints: [number of tasks]

    WORKFLOW:
    1. For each task in the rule:
        - Collect all required inputs for the task
        - Validate the collected inputs
        - Mark the task as validated (✓)
    2. After all tasks are validated → proceed to final rule completion

    Ready to start task-by-task input collection with validation checkpoints?

    CRITICAL WORKFLOW RULES:
    - ALWAYS call this tool first before any input collection.
    - NEVER start collecting inputs without user seeing overview.
    - NEVER proceed without user confirmation.
    - Create unique task_alias.input identifiers to avoid conflicts.
    - Show clear task-alias-input relationships to user.
    - NEW: Collect inputs task-by-task and validate each task's inputs immediately after collection.
    - NEW: Create initial rule structure after user confirmation.

    CRITICAL REQUIREMENTS:
    - Input names: alphanumeric + underscore only (auto-sanitize with re.sub(r'[^a-zA-Z0-9_]', '_', name))
    - Collection order: Complete ALL inputs for each task one by one (Task 1 → verify Task 1 inputs → Task 2 → verify Task 2 inputs → Task 3 → verify Task 3 inputs)
    - Within each task: collect all inputs, then verify using 'validate_task_inputs()' before proceeding
    - If a task (e.g., Task 2) has input files or other inputs that are skipped or mapped from a previous task, generate a sample input file based on the previous task response, upload its content using `upload_file()`, and use the returned file URL as the input for file-type parameters during validation.

    ARGS:
    - selected_tasks: List of dicts with 'task_name' and 'task_alias'
    Example:
    [
        {"task_name": "data_validation", "task_alias": "step1"},
        {"task_name": "data_processing", "task_alias": "step2"},
        {"task_name": "data_validation", "task_alias": "final_check"}
    ]

    Returns:
        Dict containing structured input overview and collection plan with unique identifiers,
        plus automatic rule creation capability after user confirmation, with explicit
        validation checkpoints for each task
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
            "unique_input_map": {},
            "task_alias_map": {},
            "task_input_groups": {}  # NEW: Group inputs by task for validation tracking
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
            
            # Initialize task input group for validation tracking
            input_analysis["task_input_groups"][task_alias] = {
                "task_name": task_info["task_name"],
                "task_alias": task_alias,
                "inputs": [],
                "input_count": 0,
                "validation_required": True
            }

        # Get available tasks
        available_tasks = []
        tasks_resp = rule.fetch_task_api(params={"tags": "primitive"})
        if rule.is_valid_key(tasks_resp, "items", array_check=True):
            available_tasks = [TaskVO.from_dict(task) for task in tasks_resp["items"]]

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
                cleaned_input_name = validate_input_name(inp.name)
                unique_input_id = f"{task_alias}.{cleaned_input_name}"
                
                data_type = ""
                if inp.dataType:
                    data_type = inp.dataType

                input_info = {
                    "task_name": task_name,
                    "task_alias": task_alias, 
                    "task_purpose": task_purpose,
                    "input_name": inp.name,
                    "unique_input_id": unique_input_id,
                    "description": inp.description,
                    "data_type": data_type,
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
                    "task_input_obj": {
                        "name": inp.name,
                        "description": inp.description,
                        "dataType": inp.dataType,
                        "required": inp.required,
                        "format": inp.format if inp.templateFile else None,
                    }
                }
                
                # Add to task input group for validation tracking
                input_analysis["task_input_groups"][task_alias]["inputs"].append(unique_input_id)
                input_analysis["task_input_groups"][task_alias]["input_count"] += 1

                if inp.templateFile or inp.dataType.upper() in ["FILE", "HTTP_CONFIG"]:
                    input_analysis["template_inputs"].append(input_info)
                    input_analysis["template_count"] += 1
                    input_analysis["estimated_minutes"] += 3
                else:
                    input_analysis["parameter_inputs"].append(input_info)
                    input_analysis["parameter_count"] += 1
                    input_analysis["estimated_minutes"] += 0.5

        input_analysis["total_count"] = input_analysis["template_count"] + input_analysis["parameter_count"]
        
        # Generate initial inputs, inputsMeta__ for rule creation
        initial_inputs = {}
        initial_inputs_meta = []
        
        # Track duplicate input names to handle conflicts
        input_name_counts = {}

        # Process only required inputs from template_inputs and parameter_inputs
        all_required_inputs = input_analysis["template_inputs"] + input_analysis["parameter_inputs"]
        
        for input_info in all_required_inputs:
            input_name = input_info["input_name"]
            task_alias = input_info["task_alias"]
            unique_input_id = input_info["unique_input_id"]
            
            # Get the task input object from unique_input_map
            task_input_obj = input_analysis["unique_input_map"][unique_input_id]["task_input_obj"]
            
            # Handle duplicate input names by creating unique names
            if input_name in input_name_counts:
                input_name_counts[input_name] += 1
                unique_name = f"{task_alias}_{input_name}"
            else:
                input_name_counts[input_name] = 1
                duplicate_count = sum(1 for other_input in all_required_inputs 
                                    if other_input["input_name"] == input_name and other_input["required"])
                if duplicate_count > 1:
                    unique_name = f"{task_alias}_{input_name}"
                else:
                    unique_name = input_name
            
            # Set initial value based on dataType
            data_type = getattr(task_input_obj, "dataType", None)
            if data_type:
                data_type_upper = data_type.upper()
            else:
                data_type_upper = ""
            if data_type_upper in ["FILE", "HTTP_CONFIG"]:
                initial_value = ""
            elif data_type_upper == "BOOLEAN":
                initial_value = False
            elif data_type_upper in ["INT", "INTEGER"]:
                initial_value = 0
            elif data_type_upper == "FLOAT":
                initial_value = 0.0
            elif data_type_upper in ["STRING", "TEXT"]:
                initial_value = ""
            elif data_type_upper in ["DATE", "DATETIME"]:
                initial_value = ""
            else:
                initial_value = ""
            
            initial_inputs[unique_name] = initial_value
            
            input_meta = {
                "name": unique_name,
                "dataType": data_type if data_type else "",
                "defaultValue": initial_value,
                "showField": True,
                "required": getattr(task_input_obj, "required", False),
                "allowedValues": [],
                "repeated": False
            }
            
            if hasattr(task_input_obj, 'format') and getattr(task_input_obj, 'format', None):
                input_meta["format"] = getattr(task_input_obj, 'format')
            
            initial_inputs_meta.append(input_meta)

        # Generate overview presentation with validation checkpoints
        overview_text = rule.generate_input_overview_presentation_with_validation_checkpoints(
            input_analysis
        )
        
        return {
            "success": True,
            "input_analysis": input_analysis,
            "overview_presentation": overview_text,
            "task_alias_map": input_analysis["task_alias_map"],
            "task_input_groups": input_analysis["task_input_groups"],  # NEW: For validation tracking
            "mandatory_collection_plan": {
                "step1": "Collect inputs task-wise for all defined tasks. For each task, gather all required inputs (e.g., if a task has three inputs, collect all three before proceeding).",
                "step2": "After collecting all inputs for a specific task, **MANDATORY VALIDATION CHECKPOINT** - call validate_task_inputs(task_name, collected_inputs_dict) to verify all inputs are correct.",
                "step3": "If validation fails, allow user to correct inputs and re-validate. Only proceed to next task when validation passes.",
                "step4": "Once a task's inputs are successfully validated (validation passes), proceed to collect inputs for the next task and repeat the same validation process.",
                "step5": "After completing and validating inputs for all tasks, perform a final cross-task consistency check to confirm overall readiness for execution.",
                "step6": "Finally, execute the tasks sequentially, maintaining verified task alias mappings for accurate dependency tracking and rule formation.",
                "critical_note": "**VALIDATION IS MANDATORY AND CANNOT BE SKIPPED** - Each task MUST have its inputs validated before moving to the next task. This creates checkpoints ensuring data integrity throughout the workflow."
            },
            "rule_creation_ready": True,
            "selected_tasks": selected_tasks,
            "initial_inputs": initial_inputs,
            "initial_inputs_meta": initial_inputs_meta,
            "validation_checkpoint_count": len(selected_tasks),  # NEW: Number of validation checkpoints
            "message": "Input overview prepared with task aliases and validation checkpoints. Present to user and get confirmation before proceeding.",
            "next_action": "Show overview_presentation to user and wait for confirmation, then create initial rule and follow 'mandatory_collection_plan' with STRICT validation enforcement"
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to prepare input overview: {e}"}
    
@mcp.tool()
def verify_collected_inputs(collected_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Verify all collected inputs with user before rule creation.

    MANDATORY VERIFICATION STEP (Enhanced):

    This tool MUST be called after all inputs are collected but before final rule completion.
    It presents a comprehensive summary of all collected inputs for user verification.

    ENHANCED WITH AUTOMATIC RULE FINALIZATION:
    After user confirms verification, this tool can automatically finalize the rule by:
    1. Building complete I/O mapping based on task sequence and inputs
    2. Adding mandatory compliance outputs 
    3. Setting rule status to ACTIVE
    4. Completing the rule creation process

    HANDLES DUPLICATE INPUT NAMES WITH TASK ALIASES (Preserved):
    - Uses unique identifiers (TaskAlias.InputName) for each input
    - Properly maps each unique input to its specific task alias
    - Creates structured inputs for rule creation with unique names when needed
    - Maintains clear separation between inputs from different task instances

    VERIFICATION REQUIREMENTS (Preserved):
    1. Show complete summary of ALL collected inputs with unique IDs
    2. Display both template files and parameter values
    3. Show file URLs for uploaded templates
    4. Present clear verification checklist
    5. Get explicit user confirmation
    6. Allow user to modify values if needed
    7. Prepare inputs for rule structure creation with proper task alias mapping
    8. NEW: Automatically finalize rule after user confirmation

    VERIFICATION PRESENTATION FORMAT (Preserved):
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

    CRITICAL VERIFICATION RULES (Enhanced):
    - NEVER proceed to final rule creation without user verification
    - ALWAYS show complete input summary with unique identifiers
    - ALWAYS get explicit user confirmation
    - Allow input modifications using unique IDs
    - Validate completeness before approval
    - Prepare structured inputs for rule creation with proper task mapping
    - NEW: Automatically finalize rule with I/O mapping after confirmation

    Args:
        collected_inputs: Dict containing all collected template files and parameter values with unique IDs

    Returns:
        Dict containing verification status, user confirmation, and structured inputs for rule finalization
    """

    if not collected_inputs:
        return {"success": False, "error": "No inputs provided for verification"}

    try:
        # Analyze collected inputs with unique ID handling (preserved logic)
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

        # Process template files with unique IDs (preserved processing)
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
                "defaultValue": input_value,
                "format": file_info.get("format")
            })

            # Store mapping for I/O map creation
            verification_summary["task_input_mapping"][rule_input_name] = {
                "task_alias": task_alias,
                "task_name": file_info.get("task_name", ""),
                "input_name": input_name,
                "unique_id": unique_input_id,
                "rule_input_name": rule_input_name
            }

        # Process parameter values with unique IDs (preserved processing)
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

        # Generate verification presentation (preserved)
        verification_text = rule.generate_verification_presentation_with_unique_ids(verification_summary)

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
            "rule_finalization_ready": True,  # NEW: Ready for automatic rule finalization
            "message": "Input verification prepared with task aliases. Present to user for confirmation, then automatically finalize rule.",
            "next_action": "Show verification_presentation to user and wait for confirmation, then finalize rule"
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to verify collected inputs: {e}"}


@mcp.tool()
def create_rule(rule_structure: Dict[str, Any]) -> Dict[str, Any]:
    """Create a rule with the provided structure.

    COMPLETE RULE CREATION PROCESS WITH PROGRESSIVE SAVING:

    This tool now handles both initial rule creation and progressive updates during the rule creation workflow.
    It intelligently detects the completion status and sets appropriate metadata automatically.
    It returns the URL to view the rule in the UI once it is created display the URL in chat.

    ENHANCED FOR PROGRESSIVE SAVING:
    - Automatically detects rule completion status based on rule structure content
    - Determines if rule is in-progress, ready for execution, or needs more inputs
    - Handles both initial creation and updates of existing rules
    - No additional parameters needed - analyzes rule structure intelligently
    - Maintains all existing validation and creation logic
    - Preserves all original docstring instructions and requirements

    CRITICAL REQUIREMENT - INPUTS META:
    - `spec.inputsMeta__` is **mandatory** for all rules, and rule creation cannot proceed without it.

    AUTOMATIC STATUS DETECTION:
    - DRAFT: Rule has tasks but missing inputs or I/O mapping (5-85% complete)
    - READY_FOR_CREATION: All inputs collected but I/O mapping incomplete (85% complete)
    - ACTIVE: Complete rule with tasks, inputs, and I/O mapping (100% complete)

    RULE COMPLETION ANALYSIS:
    - Checks if tasks are defined in spec.tasks
    - Validates that `spec.inputsMeta__` exists
    - Counts collected inputs in spec.inputs vs spec.inputsMeta__
    - Validates I/O mapping presence and completeness in spec.ioMap
    - Analyzes outputsMeta__ for mandatory compliance outputs
    - Sets appropriate status and creation phase automatically

    PROGRESSIVE CREATION PHASES (Auto-detected):
    1. "initialized" - Basic rule info provided (5%)
    2. "tasks_selected" - Tasks chosen and defined (25%) 
    3. "collecting_inputs" - Individual inputs being collected (25-85%)
    4. "inputs_collected" - All inputs gathered, ready for I/O mapping (85%)
    5. "completed" - Final rule creation complete with I/O mapping (100%)

    ORIGINAL REQUIREMENTS MAINTAINED:
    - All existing validation rules still apply
    - Task alias validation in I/O mappings preserved
    - Primary app type determination logic maintained
    - Mandatory output requirements (CompliancePCT_, ComplianceStatus_, LogFile)
    - YAML preview and user confirmation workflow preserved
    - All existing error handling and validation checks

    CRITICAL: This tool should be called:
    1. After planning phase to create initial rule structure
    2. After each input collection to update rule progressively
    3. After input verification to finalize rule with I/O mapping
    4. Rule status and progress automatically detected each time

    PRE-CREATION REQUIREMENTS (Original):
    1. `spec.inputsMeta__` must be defined and contain valid input definitions
    2. All inputs must be collected through systematic workflow
    3. User must provide input overview confirmation  
    4. All template inputs processed via collect_template_input()
    5. All parameter values collected and verified
    6. User must confirm all input values before rule creation
    7. Primary application type must be determined
    8. Rule structure must be shown to user in YAML format for final approval

    STEP 1 - PRIMARY APPLICATION TYPE DETERMINATION (Preserved):
    Before creating rule structure, determine primary application type:
    1. Collect all unique appType tags from selected tasks
    2. Filter out 'nocredapp' (dummy placeholder value)
    3. Handle app type selection:
        - If only one valid appType: Use automatically
        - If multiple valid appTypes: Ask user to choose primary application
        - If no valid appTypes (all were nocredapp): Use 'generic' as default
    4. Set primary app type for appType, annotateType, and app fields (single value arrays)

    STEP 2 - RULE STRUCTURE WITH TASK ALIASES (Preserved):
    ```yaml
        apiVersion: rule.policycow.live/v1alpha1
        kind: rule
        meta:
            name: MeaningfulRuleName # Simple name. Without special characters and white spaces
            purpose: Clear statement based on user breakdown
            description: Detailed description combining all steps
            labels:
                appType: [PRIMARY_APP_TYPE_FROM_STEP_1] # Single value array CRITICAL: Must be extracted from spec.tasks[].appTags.appType - NEVER use random values or user requirements
                environment: [logical] # Array
                execlevel: [app] # Array
            annotations:
                annotateType: [PRIMARY_APP_TYPE_FROM_STEP_1] # Same as appType - MUST match a task's appType
        spec:
            inputs:
              InputName: [ACTUAL_USER_VALUE_OR_FILE_URL]  # Use original or unique names based on conflicts, omit duplicates
            inputsMeta__:
            - name: InputName             # unique name for the input
              description:                # purpose of the input
              dataType: FILE|HTTP_CONFIG|STRING|INT|FLOAT|BOOLEAN|DATE|DATETIME
              repeated:                   # true = multiple values allowed, false = single value
              allowedValues:              # if repeated=true: comma-separated input is split into array
              required:                   # value must be taken from task details.
              defaultValue: [ACTUAL_USER_VALUE] #values are collected from users, If the dataType is FILE or HTTP_CONFIG then the value should be filepath URL.
              format: [ACTUAL_FILE_FORMAT]      # only include for FILE types (json, yaml, toml, xml, etc.)
              showField: true                   # true = most important field, false = optional/less important
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
                environment: [logical] # Array
                execlevel: [app] # Array
              purpose: What this task does for Step 1
            - name: Step2TaskName
              alias: validation # Another meaningful alias
              type: task
              appTags:
                appType: [COPY_FROM_TASK_DEFINITION]
                environment: [logical] # Array
                execlevel: [app] # Array
              purpose: What this task does for validation
            ioMap:
            - step1.Input.TaskInput:=*.Input.InputName  # Use task aliases in I/O mapping
            - validation.Input.TaskInput:=step1.Output.TaskOutput
            # MANDATORY: Always include these three outputs from the last task
            - '*.Output.FinalOutput:=validation.Output.TaskOutput'
            - '*.Output.CompliancePCT_:=validation.Output.CompliancePCT_'    # Compliance percentage from last task
            - '*.Output.ComplianceStatus_:=validation.Output.ComplianceStatus_'  # Compliance status from last task
            - '*.Output.LogFile:=validation.Output.LogFile'  # Log file from last task
    ```

    STEP 3 - I/O MAPPING WITH TASK ALIASES (Preserved):
    - Use golang-style assignment: destination:=source
    - 3-part structure: PLACE.DIRECTION.ATTRIBUTE_NAME
    - Always use EXACT attribute names from task specifications
    - Use meaningful task aliases instead of generic names
    - Ensure sequential data flow: Rule → Task1 → Task2 → Rule
    - Mandatory compliance outputs from last task

    VALIDATION CHECKLIST (Preserved):
    □ Rule structure validation against schema
    □ Task alias validation in I/O mappings
    □ Primary app type determination
    □ Input/output specifications validation
    □ Mandatory compliance outputs present
    □ Sequential data flow in I/O mappings

    Args:
        rule_structure: Complete rule structure with any level of completion

    Returns:
        Result of rule creation including auto-detected status and completion level
    """

    try:
        if rule.is_valid_key(rule_structure,"spec") and  rule.is_valid_array(rule_structure["spec"],"tasks"):
            tasks = rule_structure["spec"]["tasks"]
            for task in tasks:
                if rule.is_valid_key(task,"aliasref") and not rule.is_valid_key(task,"alias"):
                    task["alias"] = task["aliasref"]
            rule_structure["spec"]["tasks"] = tasks
        # Validate rule structure (preserve original validation)
        validation_result = rule.validate_rule_structure(rule_structure)
        if not validation_result["valid"]:
            return {"success": False, "error": "Invalid rule structure", "validation_errors": validation_result["errors"]}

        # Additional validation for task aliases in I/O mappings (preserved from original)
        tasks_section = rule_structure.get("spec", {}).get("tasks", [])
        io_map = rule_structure.get("spec", {}).get("ioMap", [])
        
        # Extract task aliases from tasks section for validation
        valid_aliases = set()
        for task in tasks_section:
            if "alias" in task:
                valid_aliases.add(task["alias"])
        
        # Validate I/O mappings use correct task aliases (preserved validation)
        io_mapping_errors = []
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

                # Validate right side (source) output exists in task
                if not right_side.startswith("*."):
                    parts = right_side.split(".")
                    if len(parts) >= 3:  # task_alias.Output.output_name format
                        source_task_alias = parts[0]
                        direction = parts[1]
                        output_name = parts[2]
                        
                        if direction == "Output":
                            # Find the task with this alias
                            source_task = None
                            for task in tasks_section:
                                if task.get("alias") == source_task_alias:
                                    source_task = task
                                    break
                            
                            if source_task:
                                # Get task details to validate output exists
                                task_name = source_task.get("name")
                                task_details= get_task_details.fn(task_name)
                                if task_details.get("error"):
                                    io_mapping_errors.append(f"Could not validate task '{task_name}': {task_details['error']}")
                                else:
                                    # Check if the output exists in task definition
                                    task_outputs = task_details.get("outputs", [])
                                    valid_output_names = [out["name"] for out in task_outputs]
                                    
                                    if output_name not in valid_output_names:
                                        io_mapping_errors.append(
                                            f"Output '{output_name}' not found in task '{task_name}'. "
                                            f"Valid outputs: {valid_output_names}"
                                        )  

        # Return validation errors if any I/O mapping issues found
        if io_mapping_errors:
            return {
                "success": False,
                "error": "I/O mapping validation failed",
                "validation_errors": io_mapping_errors,
                "message": "Some I/O mappings reference outputs that don't exist in the specified tasks"
            }    

        # NEW: AUTOMATIC STATUS DETECTION based on rule content
        spec = rule_structure.get("spec", {})
        meta = rule_structure.get("meta", {})

        # MANDATORY: Fetch application class name for the primary app type
        primary_app_type_array = meta.get("labels", {}).get("appType", [])
        primary_app_type = primary_app_type_array[0] if primary_app_type_array else None
        applications_response = fetch_applications.fn()
        application_class_name = None

        # Find matching application class name for primary app type
        if applications_response and applications_response.get("success") and primary_app_type:
            for app in applications_response.get("applications"):
                app_type = app.get("app_type")
                # Check if any app type from primary_app_type matches any app type from the application
                if app_type == primary_app_type:
                    application_class_name = app.get("application_class_name")
                    break
            # Add app    
            rule_structure["meta"]["app"] = application_class_name     
        
           
        
        # Analyze rule completeness for auto-detection
        tasks = spec.get("tasks", [])
        inputs = spec.get("inputs", {})
        inputs_meta = spec.get("inputsMeta__", [])
        io_map = spec.get("ioMap", [])
        outputs_meta = spec.get("outputsMeta__", [])
        
        # Check for mandatory compliance outputs
        mandatory_outputs = ["CompliancePCT_", "ComplianceStatus_", "LogFile"]
        has_mandatory_outputs = all(
            any(output.get("name") == req_output for output in outputs_meta) 
            for req_output in mandatory_outputs
        )
        
        # Completion analysis
        completion_analysis = {
            "has_tasks": len(tasks) > 0,
            "has_inputs": len(inputs) > 0 and any(
                (isinstance(value, str) and value.strip() != "" and value != "<<MINIO_FILE_PATH>>" and not value.startswith("<<")) or
                (isinstance(value, bool)) or
                (isinstance(value, (int, float)) and value is not None)
                for value in inputs.values()
            ),
            "has_inputs_meta": len(inputs_meta) > 0,
            "has_io_mapping": len(io_map) > 0,
            "has_mandatory_outputs": has_mandatory_outputs,
            "tasks_count": len(tasks),
            "inputs_collected": sum(1 for value in inputs.values() if (
                (isinstance(value, str) and value.strip() != "" and value != "<<MINIO_FILE_PATH>>" and not value.startswith("<<")) or
                (isinstance(value, bool)) or
                (isinstance(value, (int, float)) and value is not None)
            )),
            "inputs_meta_count": len(inputs_meta),
            "io_mappings_count": len(io_map),
            "inputs_match_metadata": len(inputs) == len(inputs_meta),
            "total_inputs_needed": len(inputs_meta),  # Total inputs from inputsMeta__
            "inputs_completion_percentage": (sum(1 for value in inputs.values() if (
                (isinstance(value, str) and value.strip() != "" and value != "<<MINIO_FILE_PATH>>" and not value.startswith("<<")) or
                (isinstance(value, bool)) or
                (isinstance(value, (int, float)) and value is not None)
            )) / max(len(inputs_meta), 1)) * 100 if inputs_meta else 0
        }
        
        # Enhanced automatic status determination
        if (completion_analysis["has_io_mapping"] and 
            completion_analysis["inputs_collected"] == completion_analysis["inputs_meta_count"] and  # All inputsMeta__ inputs collected
            completion_analysis["has_tasks"] and
            completion_analysis["has_mandatory_outputs"] and
            completion_analysis["inputs_match_metadata"]):
            auto_status = "ACTIVE"
            creation_phase = "completed"
            progress_percentage = 100
            
        elif (completion_analysis["inputs_collected"] == completion_analysis["inputs_meta_count"] and  # All inputsMeta__ inputs collected
            completion_analysis["has_tasks"] and
            completion_analysis["has_mandatory_outputs"] and
            completion_analysis["inputs_match_metadata"]):
            auto_status = "READY_FOR_CREATION"  
            creation_phase = "inputs_collected"
            progress_percentage = 85
            
        elif completion_analysis["has_tasks"]:
            if completion_analysis["inputs_collected"] > 0:  # Some inputs have values
                auto_status = "DRAFT"
                creation_phase = "collecting_inputs"
                # Calculate progress: 25% base + (input completion percentage * 0.6)
                progress_percentage = min(25 + int(completion_analysis["inputs_completion_percentage"] * 0.6), 85)
            else:
                auto_status = "DRAFT"
                creation_phase = "tasks_selected"
                progress_percentage = 25
        else:
            auto_status = "DRAFT"
            creation_phase = "initialized"
            progress_percentage = 5

        # Set detected status in meta (don't override if explicitly provided and valid)
        if "status" not in meta or meta["status"] not in ["DRAFT", "READY_FOR_CREATION", "ACTIVE"]:
            rule_structure["meta"]["status"] = auto_status
        if "creation_phase" not in meta:
            rule_structure["meta"]["creation_phase"] = creation_phase

        # Add automatic timestamps (preserve existing if present)
        current_time = datetime.now().isoformat()
        if "created_at" not in meta:
            rule_structure["meta"]["created_at"] = current_time
        rule_structure["meta"]["last_updated"] = current_time

        # Add/update progress tracking with detailed analysis
        rule_structure["meta"]["progress"] = {
            "percentage": progress_percentage,
            "phase": creation_phase,
            "completion_analysis": completion_analysis,
            "next_steps": determine_next_steps(creation_phase, completion_analysis),
            "estimated_completion": estimate_completion_time(completion_analysis)
        }

        # Check if rule already exists (for updates vs creation)
        existing_rule = fetch_rule.fn(rule_structure["meta"]["name"])
        is_update = existing_rule["success"]

        # Generate YAML preview for user confirmation (preserved from original)
        yaml_preview = rule.generate_yaml_preview(rule_structure)

        # Call your existing create_rule_api (preserved)
        result = rule.create_rule_api(rule_structure)

        # Auto-generate design notes info (preserved from original)
        design_notes_result = {
            "auto_generated": True, 
            "message": "Design notes will be auto-generated using comprehensive internal template",
            "next_action": "Call create_design_notes(rule_name, design_notes_structure) to generate and save design notes"
        }

        readme_info = {
            "auto_generated": True, 
            "message": "README will be auto-generated using a comprehensive internal template",
            "next_action": "Call create_rule_readme(rule_name, readme_content) to generate and save the README"
        }
        
        rule_name = rule_structure["meta"]["name"]

        # Build UI URL
        base_host = constants.host.rstrip("/api") if hasattr(constants, "host") and isinstance(constants.host, str) else getattr(constants, "host", "")
        ui_url = f"{base_host}/ui/create-pc-rule?name={rule_name}&catalog=localcatalog" if base_host else ""
            
        #Add MCP tag to the rule with proper error handling
        try:
            tag_result = add_rule_tag(rule_name)
            if not tag_result.get("success", False):
                tag_message = tag_result.get("message", "Unknown error occurred")
                tag_status = {
                    "tagged": False,
                    "message": f"Rule created successfully but MCP tag addition failed: {tag_message}"
                }
            else:
                tag_status = {
                    "tagged": True,
                    "message": tag_result.get("message", "MCP tag added successfully")
                }
        except Exception as e:
            tag_status = {
                "tagged": False,
                "message": f"Rule created successfully but MCP tag addition encountered an exception: {e}"
            }

        return {
            "success": True,
            "rule_id": result["rule_id"],
            "rule_name": rule_name,
            "is_update": is_update,
            "detected_status": auto_status,
            "creation_phase": creation_phase,
            "progress_percentage": progress_percentage,
            "completion_analysis": completion_analysis,
            "message": f"Rule {'updated' if is_update else 'created'} successfully with meaningful task aliases - Status: {auto_status} ({progress_percentage}% complete)",
            "rule_structure": rule_structure,
            "yaml_preview": yaml_preview,
            "timestamp": result.get("timestamp"),
            "status": result.get("status", auto_status),
            "design_notes_info": design_notes_result,
            "readme_info": readme_info,
            "tag_status": tag_status,
            "ui_url" : ui_url,
            "next_step": determine_next_action(creation_phase, completion_analysis)
        }
        
    except exception.CCowExceptionVO as e:
        return {"success": False, "error": f"Failed to create rule: {e.to_dict()}"}
    except Exception as e:
        return {"success": False, "error": f"Failed to create rule: {e}"}
    


def add_rule_tag(rule_name: str) -> Dict[str, Any]:
    """
    Add MCP tag to a rule.
    
    Args:
        rule_name: Name of the rule to add tags to
        
    Returns:
        Dict with tag addition results
    """
    try:
        headers = wsutils.create_header()
        
        # Prepare request data for adding rule tags
        request_data = {
            "ruleNames": [rule_name],
            "tags": ["MCP"],
            "operation": "ADD"
        }
        
        wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_UPDATE_RULE_TAGS),
            data=json.dumps(request_data),
            header=headers
        )

        return {
            "success": True,
            "rule_name": rule_name,
            "message": f"MCP tag added successfully to rule '{rule_name}'"
        }

    except Exception as e:
        return {
            "success": False,
            "rule_name": rule_name,
            "message": f"Error: {e}"
        }
    

@mcp.tool()
def generate_design_notes_preview(rule_name: str) -> Dict[str, Any]:
    """
    Generate design notes preview for user confirmation before actual creation.

    ## DESIGN NOTES PREVIEW GENERATION

    This tool generates a complete Jupyter notebook structure as a dictionary for user review. The MCP will create the full notebook content with 7 standardized sections based on rule context and metadata, then return it for user confirmation.

    ## DESIGN NOTES TEMPLATE STRUCTURE REQUIREMENTS

    The MCP should generate a Jupyter notebook (.ipynb format) with exactly 7 sections:

    ### SECTION 1: Evidence Details
    **DESCRIPTION:** System identification and rule purpose documentation

    **CONTENT REQUIREMENTS:**
    - Table with columns: System | Source of data | Frameworks | Purpose
    - System: {TARGET_SYSTEM_NAME} (all lowercase")
    - Source: Always 'compliancecow'
    - Frameworks: Always '-'
    - Purpose: Use rule's purpose from metadata
    - RecommendedEvidenceName: {RULE_OUTPUT_NAME} (use rule's primary compliance output, exclude LogFile)
    - Description: Use rule description from metadata
    - Reference: Include actual API documentation links that the rule uses (extract from task specifications, no placeholder values)

    **FORMAT:** Markdown cell with table and code blocks only

    ### SECTION 2: Define the System Specific Data (Extended Data Schema)
    **DESCRIPTION:** System-specific raw data structure definition with detailed breakdown

    **CONTENT REQUIREMENTS:**

    #### Step 2a: Inputs
    - Generate numbered list from rule's spec.inputs
    - Format: "{NUMBER}. **{INPUT_NAME}({INPUT_DATA_TYPE})** - {INPUT_DESCRIPTION}"
    - Include all inputs with their types and purposes

    #### Step 2b: API & Flow
    - Generate numbered list of API endpoints based on target system
    - Format: "{NUMBER}. {HTTP_METHOD} {URL} - {BRIEF_DESCRIPTION}"
    - Include only actual API endpoints that this specific rule uses for data collection
    - Extract from task specifications, not generic templates

    #### Step 2c: Define the Extended Schema
    - Generate large JSON code block with actual API response structure
    - Use system-specific field names and realistic data values
    - Include all fields that will be processed by the rule

    **FORMAT:** Markdown headers with detailed lists + large JSON code block

    ### SECTION 3: Define the Standard Schema
    **DESCRIPTION:** Standardized compliance data format documentation

    **CONTENT REQUIREMENTS:**
    - Header explaining standard schema purpose
    - JSON code block with complete standardized structure containing:
    * System: based on target system (lowercase)
    * Source: Always 'compliancecow'
    * Resource info: ResourceID, ResourceName, ResourceType, ResourceLocation, ResourceTags, ResourceURL
    * System-specific data fields based on actual rule output columns, if unavailable then generate based on rule details
    * Compliance fields: ValidationStatusCode, ValidationStatusNotes, ComplianceStatus, ComplianceStatusReason
    * Evaluation and action fields: EvaluatedTime, UserAction, ActionStatus, ActionResponseURL (UserAction, ActionStatus, ActionResponseURL are empty by default)

    #### Step 3a: Sample Data
    - Generate markdown table with ALL standard schema columns in same order - include all columns even if empty
    - Include three complete example rows with realistic, system-specific data
    - Use proper data formatting and realistic identifiers

    **FORMAT:** JSON code block + comprehensive markdown table

    ### SECTION 4: Describe the Compliance Taxonomy
    **DESCRIPTION:** Status codes and compliance definitions

    **CONTENT REQUIREMENTS:**
    - Table with columns: ValidationStatusCode | ValidationStatusNotes | ComplianceStatus | ComplianceStatusReason
    - ValidationStatusCode: **CRITICAL FORMAT REQUIREMENT** - Rule-specific codes must strictly follow this exact format:
        * Each word must be exactly 3-4 characters long
        * Words must be separated by underscores (_)
        * Use ALL UPPERCASE letters
        * Create codes that directly relate to the rule's compliance purpose
        * Examples: CODE_OWN_HAS_PR_REV (code ownership has pull request review), REPO_SEC_SCAN_PASS (repository security scan passed), AUTH_MFA_ENBL (authentication multi-factor enabled)
        * **DO NOT** use generic codes like "PASS" or "FAIL" 
        * **DO NOT** exceed 4 characters per word
        * **DO NOT** use special characters other than underscores
        * Generate 4-6 different status codes covering various compliance scenarios
    - Detailed compliance reasons specific to the rule's purpose
    - Both COMPLIANT and NON_COMPLIANT scenarios

    **FORMAT:** Markdown cell with table

    ### SECTION 5: Calculation for Compliance Percentage and Status
    **DESCRIPTION:** Percentage calculations and status logic

    **CONTENT REQUIREMENTS:**
    - Header explaining compliance calculation methodology
    - Code cell with calculation logic:
    * TotalCount = Count of 'COMPLIANT' and 'NON_COMPLIANT' records
    * CompliantCount = Count of 'COMPLIANT' records
    * CompliancePCT = (CompliantCount / TotalCount) * 100
    * Status determination rules:
        - COMPLIANT: 100%
        - NON_COMPLIANT: 0% to less than 100%
        - NOT_DETERMINED: If no records are found

    **FORMAT:** Markdown header cell + Code cell with calculation logic

    ### SECTION 6: Describe (in words) the Remediation Steps for Non-Compliance
    **DESCRIPTION:** Non-compliance remediation procedures

    **CONTENT REQUIREMENTS:**
    - Can be "N/A" if no specific remediation steps apply
    - When applicable, provide:
    * Immediate Actions required
    * Short-term remediation steps
    * Long-term monitoring approaches
    * Responsible parties and timeframes
    - System-agnostic guidance that can be customized

    **FORMAT:** Markdown cell with detailed remediation procedures

    ### SECTION 7: Control Setup Details
    **DESCRIPTION:** Rule configuration and implementation details

    **CONTENT REQUIREMENTS:**
    - Table with two columns: Control Details | (Values)
    - Required fields (only these):
    * RuleName: Use actual rule name
    * PreRequisiteRuleNames: Default to 'N/A' or list dependencies
    * ExtendedSchemaRuleNames: Default to 'N/A' or list related rules
    * ApplicationClassName: Fetch all appType values from spec.tasks array, combine them, remove duplicates, and format as comma-separated values
    * PostSynthesizerName: Default to 'N/A' or specify if used

    **FORMAT:** Markdown table with control configuration details

    ## JUPYTER NOTEBOOK METADATA REQUIREMENTS

    - Include proper notebook metadata (colab, kernelspec, language_info)
    - Set nbformat: 4, nbformat_minor: 0
    - Use appropriate cell metadata with unique IDs for each section
    - Ensure proper markdown and code cell formatting

    ## MCP CONTENT POPULATION INSTRUCTIONS

    The MCP should extract the following information from the rule context:
    - Rule name, purpose, description from rule metadata
    - System name from appType (clean by removing connector suffixes like "-connector")
    - Task details from spec.tasks array
    - Input specifications from spec.inputs and spec.inputsMeta__
    - Output specifications from spec.outputsMeta__
    - Application connector information for control setup
    - API endpoints from task specifications (not generic placeholders)

    ## CONTENT GENERATION GUIDELINES

    - Use realistic, system-specific examples that can be customized later
    - Include comments in code sections indicating customization points
    - Provide system-agnostic content that applies broadly
    - Use consistent naming conventions throughout all sections
    - Extract actual API documentation links from task specifications
    - Generate ValidationStatusCodes that are specific to the rule's compliance purpose
    - Ensure all sample data reflects the actual system being monitored

    ## WORKFLOW

    1. MCP retrieves rule context from stored rule information
    2. MCP generates complete Jupyter notebook using template structure above
    3. MCP populates template with extracted rule metadata and calculated values
    4. MCP returns complete notebook structure as dictionary for user review
    5. User reviews and confirms the structure
    6. If approved, call create_design_notes() to actually save the notebook

    ## ARGS

    - rule_name: Name of the rule for which to generate design notes preview

    ## RETURNS

    Dict containing complete notebook structure for user review and confirmation
    """
    
    # MCP should directly construct the design notes based on the instructions above
    # No intermediate API calls needed - MCP has all the template details in the docstring
    # The MCP will use fetch_rule() internally and build the complete notebook structure
    
    return {
        "success": True, 
        "rule_name": rule_name,
        "design_notes_structure": {},  # MCP will populate this with complete notebook dictionary
        "sections_count": 7,
        "message": f"MCP should construct complete notebook structure for rule '{rule_name}' based on the detailed template instructions above",
        "next_action": "MCP should use fetch_rule() and build complete notebook dictionary, then return it in design_notes_structure"
    }


@mcp.tool()
def create_design_notes(rule_name: str, design_notes_structure: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create and save design notes after user confirmation.

    DESIGN NOTES CREATION:

    This tool actually creates and saves the design notes after the user has reviewed
    and confirmed the preview structure from generate_design_notes_preview().

    WORKFLOW:
    1. Before creating new design notes, call fetch_rule_design_notes() to check if already exist and continue the flow, if not then continue this flow
    2. User has already reviewed notebook structure from preview
    3. User confirmed the structure is acceptable
    4. This tool receives the complete design notes dictionary structure
    5. MCP saves the notebook and returns access details

    Args:
        rule_name: Name of the rule for which to create design notes
        design_notes_structure: Complete Jupyter notebook structure as dictionary

    Returns:
        Dict containing design notes creation status and access details
    """
    
    try:
        headers = wsutils.create_header()
        payload = {
            "ruleName": rule_name,
            "type": "mcp",
            "designNotesContent": rule.encode_content(design_notes_structure),  # Pass the complete notebook dictionary as an encoded string
        }
        
        save_resp = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_SAVE_DESIGN_NOTES),
            data=json.dumps(payload),
            header=headers
        )

        message = save_resp.get("message")
        if isinstance(message, str) and message == "Design notes file created successfully.":
            return {
                "success": True,
                "rule_name": rule_name,
                "filename": f"{rule_name}.ipynb",
                "sections_saved": len(design_notes_structure.get("cells", [])),
                "message": f"Design notes successfully created and saved for rule '{rule_name}'"
            }
        else:
            return {
                "success": False,
                "error": "Failed to save design notes",
                "rule_name": rule_name
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save design notes: {e}",
            "rule_name": rule_name
        }


@mcp.tool()
def fetch_rule(rule_name: str) -> Dict[str, Any]:
    """
    Fetch rule details by rule name.

    Args:
        rule_name: Name of the rule to retrieve
        
    Returns:
        Dict containing complete rule structure and metadata
    """
    
    try:
        headers = wsutils.create_header()
        
        get_rule_resp = wsutils.get(
            path=wsutils.build_api_url(endpoint=f"{constants.URL_FETCH_RULES}?name={rule_name}"),
            header=headers
        )
        
        if rule.is_valid_array(get_rule_resp, "items"):
            rule_structure = get_rule_resp["items"][0]
            if rule.is_valid_array(rule_structure["spec"],"ioMap"):
                # INFO : From the backend we're setting default values in the ioMap if the values are missing. For MCP flow, we're nullyfying this flow since we have validation for this. 
                if {'t1.Input.BucketName:=*.Input.BucketName', '*.Output.CompliancePCT_:=t1.Output.CompliancePCT_', '*.Output.ComplianceStatus_:=t1.Output.ComplianceStatus_', '*.Output.LogFile:=t1.Output.LogFile'}==set(rule_structure["spec"]["ioMap"]):
                    rule_structure["spec"]["ioMap"]=[]

            if rule.is_valid_key(rule_structure,"apiVersion") and rule_structure["apiVersion"]=="v1alpha1":
                rule_structure['apiVersion']="rule.policycow.live/v1alpha1"


            return {
                "success": True,
                "rule_name": rule_name,
                "rule_structure": rule_structure,  # Complete rule as dictionary
                "message": f"Rule '{rule_name}' retrieved successfully"
            }
        
        else:
            return {
                "success": False,
                "error": f"Rule '{rule_name}' not found",
                "rule_name": rule_name
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch rule '{rule_name}': {e}",
            "rule_name": rule_name
        }

@mcp.tool()
def fetch_rule_design_notes(rule_name: str) -> Dict[str,Any]:
    """
    Fetch and manage design notes for a rule.

    WORKFLOW:

    1. CHECK EXISTING NOTES:
    - Always check if design notes exist for the rule first (whether user wants to create or view)
    - If found: Present complete notebook to user in readable format
    - If not found: Offer to create new ones

    2. IF NOTES EXIST:
    - Show complete notebook with all sections (this serves as the VIEW)
    - Ask: "Here are your design notes. Modify or regenerate?"

    3. USER OPTIONS:
    - MODIFY: 
    1. Ask "Do you need any changes to the design notes?"
    2. If no changes needed: Get user confirmation, then call create_design_notes() to update
    3. If changes needed: Collect modifications, show preview, get confirmation, then call create_design_notes() to update
    - REGENERATE: 
    1. Generate the design notes using generate_design_notes_preview()
    2. Show preview to user
    3. Get user confirmation
    4. If confirmed: Call create_design_notes() to save the regenerated design notes
    - CANCEL: End workflow

    4. IF NO NOTES EXIST:
    - Inform user no design notes found
    - Ask: "Create comprehensive design notes for this rule?"
    - If yes: Generate the design notes using generate_design_notes_preview()
    - Show preview to user
    - Get user confirmation
    - If confirmed: Call create_design_notes() to generate

    KEY RULES:
    - MUST follow this workflow explicitly step by step
    - Always check for existing notes first whenever user asks about design notes (create or view)
    - ALWAYS get user confirmation before calling create_design_notes()
    - If any updates needed, explicitly call create_design_notes() tool to save changes
    - Present notes in Python notebook format
    - Use create_design_notes() for creation and updates

    Args:
        rule_name: Name of the rule

    Returns:
        Dict with success status, rule name, design notes content, and error details
    """

    try:
        headers = wsutils.create_header()
        payload = {
            "ruleName": rule_name,
            "type": "mcp"
        }
        design_notes_resp = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_DESIGN_NOTES),
            data=json.dumps(payload),
            header=headers
        )

        filename = design_notes_resp.get("fileName")
        design_notes_content = design_notes_resp.get("designNotesContent")
       

        if isinstance(design_notes_content,str) and design_notes_content!="":
            return {
                "success": True,
                "rule_name": rule_name,
                "filename": filename,
                "designNotesContent": rule.decode_content(design_notes_content),
                "message": f"Design notes successfully retrieved for rule {rule_name}. Displaying content to user."
            }
        else:
            return{
                "success": False,
                "rule_name": rule_name,
                "message": f"Design notes not found for rule {rule_name}. Offer to create comprehensive design notes."
            }
        
    except Exception as e:
        return {
            "success": False,
            "rule_name": rule_name,
            "message": f"Error fetching design notes for rule {rule_name}: {e}."
        }


@mcp.tool()
def generate_rule_readme_preview(rule_name: str) -> Dict[str, Any]:
    """
    Generate README.md preview for rule documentation before actual creation.

    RULE README GENERATION:

    This tool generates a complete README.md structure as a string for user review.
    The MCP will create comprehensive rule documentation with detailed sections based on 
    rule context and metadata, then return it for user confirmation.

    README TEMPLATE STRUCTURE REQUIREMENTS:

    The MCP should generate a README.md with exactly these sections:

    ## SECTION 1: Rule Header
    DESCRIPTION: Rule identification and overview
    CONTENT REQUIREMENTS:
    - Rule name as main title (# {RULE_NAME})
    - Brief description from rule metadata
    - Status badges (Version, Application Type, Environment)
    - Purpose statement
    - Last updated timestamp
    FORMAT: Markdown header with badges and overview

    ## SECTION 2: Overview
    DESCRIPTION: High-level rule explanation
    CONTENT REQUIREMENTS:
    - What this rule does (purpose and description)
    - Target system/application
    - Compliance framework alignment
    - Key benefits and use cases
    - When to use this rule
    FORMAT: Markdown sections with bullet points

    ## SECTION 3: Rule Architecture
    DESCRIPTION: Technical architecture and flow
    CONTENT REQUIREMENTS:
    - Rule flow diagram (text-based)
    - Task sequence and dependencies
    - Data flow: Input → Processing → Output
    - Integration points
    - Architecture decisions
    FORMAT: Markdown with code blocks for diagrams

    ## SECTION 4: Inputs
    DESCRIPTION: Detailed input specifications
    CONTENT REQUIREMENTS:
    - Table of all rule inputs with:
      * Input Name
      * Data Type  
      * Required/Optional
      * Description
      * Default Value
      * Example Value
    - Input validation rules
    - File format specifications (for FILE inputs)
    FORMAT: Markdown table with detailed explanations

    ## SECTION 5: Tasks
    DESCRIPTION: Individual task breakdown
    CONTENT REQUIREMENTS:
    - For each task in the rule:
      * Task name and alias
      * Purpose and functionality
      * Input requirements
      * Output specifications
      * Processing logic overview
      * Error handling
    - Task execution order
    - Dependencies between tasks
    FORMAT: Markdown subsections for each task

    ## SECTION 6: Outputs
    DESCRIPTION: Rule output specifications
    CONTENT REQUIREMENTS:
    - Table of all rule outputs with:
      * Output Name
      * Data Type
      * Description
      * Format/Structure
      * Example Value
    - Output file formats and schemas
    - Success/failure indicators
    FORMAT: Markdown table with examples

    ## SECTION 7: Configuration
    DESCRIPTION: Rule configuration and setup
    CONTENT REQUIREMENTS:
    - Application type and environment settings
    - Execution level and mode
    - Required permissions and access
    - System prerequisites
    - Configuration examples
    - Environment-specific settings
    FORMAT: Markdown with code blocks

    ## SECTION 8: Usage Examples
    DESCRIPTION: Practical usage scenarios
    CONTENT REQUIREMENTS:
    - Basic usage example
    - Advanced configuration example
    - Common use cases
    - Best practices
    - Troubleshooting tips
    FORMAT: Markdown with code examples

    ## SECTION 9: I/O Mapping
    DESCRIPTION: Data flow mapping details
    CONTENT REQUIREMENTS:
    - Complete I/O mapping visualization
    - Rule input to task input mappings
    - Task output to task input mappings  
    - Task output to rule output mappings
    - Data transformation explanations
    FORMAT: Markdown with formatted mapping table

    ## SECTION 10: Troubleshooting
    DESCRIPTION: Common issues and solutions
    CONTENT REQUIREMENTS:
    - Common error scenarios
    - Input validation failures
    - Task execution errors
    - Output generation issues
    - Performance considerations
    - Support and contact information
    FORMAT: Markdown FAQ-style sections

    ## SECTION 11: Version History
    DESCRIPTION: Change log and versioning
    CONTENT REQUIREMENTS:
    - Current version information
    - Version history table
    - Change descriptions
    - Migration notes
    - Deprecation warnings
    FORMAT: Markdown table with version details

    ## SECTION 12: References
    DESCRIPTION: Additional resources and links
    CONTENT REQUIREMENTS:
    - Related documentation links
    - Compliance framework references
    - API documentation
    - Support resources
    - Contributing guidelines
    FORMAT: Markdown bullet list with links

    MARKDOWN FORMATTING REQUIREMENTS:
    - Use proper Markdown syntax
    - Include table of contents with links
    - Use code blocks for examples
    - Include badges and shields
    - Proper heading hierarchy (H1, H2, H3)
    - Use tables for structured data
    - Include horizontal rules for section separation

    MCP CONTENT POPULATION INSTRUCTIONS:
    The MCP should extract the following information from the rule context:
    - Rule name, purpose, description from rule metadata
    - System name from appType (clean by removing connector suffixes)
    - Task details from spec.tasks array (name, alias, purpose, appTags)
    - Input specifications from spec.inputs object
    - Output specifications from spec.outputsMeta__
    - I/O mappings from spec.ioMap array
    - Environment and execution settings from labels
    - Application type and integration details

    PLACEHOLDER REPLACEMENT RULES:
    - {RULE_NAME} = meta.name
    - {RULE_PURPOSE} = meta.purpose  
    - {RULE_DESCRIPTION} = meta.description
    - {SYSTEM_NAME} = extracted from appType
    - {VERSION} = meta.version or "1.0.0"
    - {ENVIRONMENT} = meta.labels.environment[0]
    - {APP_TYPE} = meta.labels.appType[0]
    - {EXEC_LEVEL} = meta.labels.execlevel[0]
    - {TASK_COUNT} = len(spec.tasks)
    - {INPUT_COUNT} = len(spec.inputs)
    - {OUTPUT_COUNT} = len(spec.outputsMeta__)
    - {TIMESTAMP} = current ISO timestamp

    CONTENT GUIDELINES:
    - Use clear, technical language
    - Include practical examples
    - Provide comprehensive coverage
    - Make it developer-friendly
    - Include troubleshooting help
    - Keep sections well-organized
    - Use consistent formatting

    WORKFLOW:
    1. MCP retrieves rule context using fetch_rule() 
       (ensure only the fetch_rule tool is called, not fetch_cc_rule)
    2. MCP extracts metadata and technical details
    3. MCP generates complete README.md content using template above
    4. MCP populates all placeholders with actual rule data
    5. MCP returns complete README content as string for user review
    6. User reviews and confirms the content
    7. If approved, call create_rule_readme() to actually save the README

    Args:
        rule_name: Name of the rule for which to generate README preview

    Returns:
        Dict containing complete README.md content as string for user review
    """
    
    # MCP should directly construct the README based on the instructions above
    # No intermediate API calls needed - MCP has all the template details in the docstring
    # The MCP will use fetch_rule() internally and build the complete README content
    
    return {
        "success": True, 
        "rule_name": rule_name,
        "readme_content": "",  # MCP will populate this with complete README.md content
        "sections_count": 12,
        "estimated_length": "2000-3000 lines",
        "message": f"MCP should construct complete README.md content for rule '{rule_name}' based on the detailed template instructions above",
        "next_action": "MCP should use fetch_rule() and build complete README markdown content, then return it in readme_content"
    }


@mcp.tool()
def create_rule_readme(rule_name: str, readme_content: str) -> Dict[str, Any]:
    """
    Create and save README.md file after user confirmation.

    README CREATION:

    This tool actually creates and saves the README.md file after the user has reviewed
    and confirmed the preview content from generate_rule_readme_preview().

    WORKFLOW:
    1. User has already reviewed README content from preview
    2. User confirmed the content is acceptable
    3. This tool receives the complete README.md content as string
    4. MCP saves the README file and returns access details

    Args:
        rule_name: Name of the rule for which to create README
        readme_content: Complete README.md content as string

    Returns:
        Dict containing README creation status and access details
    """
    
    try:
        headers = wsutils.create_header()
        payload = {
            "ruleName": rule_name,
            "type":"rule",
            "readmeContent": rule.encode_content(readme_content),  # Pass the complete README content as an encoded string
        }

        save_resp = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_SAVE_RULE_README),
            data=json.dumps(payload),
            header=headers
        )

        message = save_resp.get("message")
        if isinstance(message, str) and message == "Read-me file created successfully.":
            return {
                "success": True,
                "rule_name": rule_name,
                "filename": "README.md",
                "content_length": len(readme_content),
                "sections_saved": readme_content.count("##"),  # Count markdown sections
                "message": f"README.md successfully created and saved for rule '{rule_name}'"
            }
        else:
            return {
                "success": False,
                "error": "Failed to save README.md",
                "rule_name": rule_name
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save README.md: {e}",
            "rule_name": rule_name
        }


@mcp.tool()
def update_rule_readme(rule_name: str, updated_readme_content: str) -> Dict[str, Any]:
    """
    Update existing README.md file with new content.

    README UPDATE:

    This tool updates an existing README.md file with new content. Useful for
    making changes after initial creation or updating documentation as rules evolve.

    Args:
        rule_name: Name of the rule for which to update README
        updated_readme_content: Updated README.md content as string

    Returns:
        Dict containing README update status and details
    """
    
    try:
        headers = wsutils.create_header()
        payload = {
            "ruleName": rule_name,
            "type":"rule",
            "readmeContent": rule.encode_content(updated_readme_content),  # Pass the complete README content as an encoded string
        }
        update_resp = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_SAVE_RULE_README),
            data=json.dumps(payload),
            header=headers
        )

        message = update_resp.get("message")
        if isinstance(message, str) and message == "Read-me file created successfully.":
            return {
                "success": True,
                "rule_name": rule_name,
                "filename": "README.md",
                "content_length": len(updated_readme_content),
                "message": f"README.md successfully updated for rule '{rule_name}'"
            }
        else:
            return {
                "success": False,
                "error": "Failed to update README.md",
                "rule_name": rule_name
            }
                     
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to update README.md: {e}",
            "rule_name": rule_name
        }


@mcp.tool()
def get_rules_summary() -> List[Dict[str, Any]]:
    """
    Tool-based version of `get_rules_summary` for improved compatibility and prevention of duplicate rule creation.

    This tool serves as the initial step in the rule creation process. It helps determine whether the user's proposed use case matches any existing rule in the catalog.

    PURPOSE:
    - To analyze the user's use case and avoid duplicate rule creation by identifying the most suitable existing rule based on its name, description, and purpose.
    - **NEW: Check for partially developed rules in local system before allowing new rule creation**
    - **NEW: Present resumption options if incomplete rules are found to prevent duplicate work**

    WHEN TO USE:
    - As the first step before initiating a new rule creation process
    - When the user wants to retrieve and review all available rules in the **catalog**
    - When verifying if a similar rule already exists that can be reused or customized
    - **NEW: When checking for incomplete local rules that should be resumed instead of creating new ones**

    🚫 DO NOT USE THIS TOOL FOR:
    - Checking what rules are available in the ComplianceCow system.
    - This tool only works with the **rule catalog** (not the entire ComplianceCow system).
    - The catalog contains only rules that are published and available for reuse in the catalog.
    - For direct ComplianceCow system lookups, use dedicated system tools instead:
    - `fetch_cc_rule_by_name`
    - `fetch_cc_rule_by_id`

    WHAT IT DOES:
    - Retrieves the full list of rules from the catalog with simplified metadata (name, purpose, description)
    - Performs intelligent matching using metadata (name, description, purpose) with user-provided use case details
    - Uses semantic pattern recognition to find similar rules, even across different systems (e.g., AzureUserUnusedPermission vs SalesforceUserUnusedPermissions)

    IF A MATCHING RULE IS FOUND:

    - Retrieves complete details via `fetch_rule()`.
    - If the readmeData field is available in the fetch_rule() response, Performs README-based validation using the `readmeData` field from the `fetch_rule()` response to assess its suitability for the user’s use case.
    - If suitable:
    - Returns the rule with full metadata, explanation, and the analysis report.
    - If not suitable:
    - Informs the user that the rule's README content does not align with the intended use case.
    - Prompts the user with clear next-step options:
        - "The rule's README content does not align with your use case. Please choose one of the following options:"
        - Customize the existing rule
        - Evaluate alternative matching rules
        - Proceed with new rule creation
    - Waits for the user's choice before proceeding.
    
    IF A SIMILAR RULE EXISTS FOR AN ALTERNATE TECHNOLOGY STACK:

    - Detects rules with the same logic but built for a different platform or system (e.g., AzureUserUnusedPermission for SalesforceUserUnusedPermissions)
    - If the readmeData field is available in the fetch_rule() response, Retrieves and analyzes the `readmeData` from the `fetch_rule()` response to compare the implementation details against the user's proposed use case
    - Based on the comparison:
        - If the README content matches or is mostly reusable, suggest using the existing rule structure and logic as a foundation to create a new rule tailored to the user's target system
        - If the README content does not match or is not suitable, clearly inform the user and recommend either modifying the logic significantly or proceeding with a completely new rule from scratch

    IF NO SUITABLE RULE IS FOUND:
    - Clearly informs the user that no relevant rule matches the proposed use case
    - Suggests continuing with new rule creation
    - Optionally highlights similar rules that can be used as a reference

    MANDATORY STEPS:
    README VALIDATION:
    - Always retrieve and analyze `readmeData` from `fetch_rule()`.
    - Ensure the rule's logic, behavior, and intended use align with the user's proposed use case.

    README ANALYSIS REPORT:
    - Generate a clear and concise report for each `readmeData` analysis that classifies the result as a full match, partially reusable, or not aligned.
    - Present this report to the user for review.

    USER CONFIRMATION BEFORE PROCEEDING:
    When analyzing a README file:
    - If no relevant rule matches the proposed use case, or if the README is deemed unsuitable, the tool must pause and request explicit user confirmation before proceeding further.
    - The tool should:
    - Clearly inform the user that no matching rule was found or the README is not appropriate.
    - Suggest creating a new rule as the next step.
    - Optionally recommend similar existing rules that can serve as references to help the user craft the new rule.

    ITERATE UNTIL MATCH:
    - Repeat the above steps until a suitable rule is found or all options are exhausted.

    CROSS-PLATFORM RULE HANDLING:
    - For rules from a different stack:
    - If reusable: suggest customization
    - If not reusable: recommend new rule creation

    Returns:
    - A single rule object with full metadata and verified README match — if an exact match is found
    - A similar rule suggestion with customization options — if a cross-system match is found (e.g., AzureUserUnusedPermission vs SalesforceUserUnusedPermissions)
    - A message indicating no suitable rule found — with next steps and guidance to create a new rule
    """

    try:

        rule_response = rule.fetch_rules_api()
        
        if not rule_response:
            return {"error": f"No rule found that matches the specified requirements."}

        return rule_response

    except Exception as e:
        return {
            "error": f"An error occurred while retrieving the rule with the specified details: {e}"
        }

@mcp.tool()
def get_application_info(tag_name: str) -> Dict[str, Any]:
    """
    Get detailed information about an application, including supported credential types.

    APPLICATION CREDENTIAL CONFIGURATION WORKFLOW:

    1. User selects "Configure new application credentials".
    2. Call this tool to retrieve application details and supported credential types.
    3. Present credential options to the user with:
       - Required attributes
       - Data type
       - If type is bytes → must be Base64-encoded
    4. Collect credential values for the selected type.
    5. Validate that all required attributes are provided.
    6. Verify that each credential value matches its expected data type.
    7. Build the credential configuration and append it to the `apps_config` array.

    DATA VALIDATION REQUIREMENTS:
    - All required attributes must be present.
    - Data type must match specification.
    - Bytes values must be Base64-encoded before saving.

    Args:
        tag_name: The app tag name for retrieving application information

    Returns:
        Dict containing application details and supported credential types
    """
    try:
        header = wsutils.create_header()

        params = {"appType": tag_name}

        app_resp = wsutils.get(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_APPLICATION_CREDENTIALS), 
            params=params, 
            header=header
        )

        if rule.is_valid_array(app_resp, "items"):
            app_info = app_resp["items"][0]
            supported_creds = app_info.get("supportedCreds")
            return {
                "success": True, 
                "app_name": tag_name,
                "supportedCreds": supported_creds,
                "message": f"Retrieved information for application '{tag_name}'. User can select credential type and provide values."
            }
        else:
            return {
                "success": False, 
                "app_name": tag_name,
                "message": f"No credential information found for application '{tag_name}'."
            }

    except Exception as e:
        return {
            "success": False, 
            "app_name": tag_name,
            "message": f"Error occurred while fetching application info for '{tag_name}': {e}"
        }


@mcp.tool()
def execute_rule(rule_name: str, from_date: str, to_date:str, rule_inputs: List[Dict[str, Any]], applications: List[Dict[str, Any]], is_application_data_provided_by_user: bool) -> Dict[str, Any]:
    """
    RULE EXECUTION WORKFLOW:

    PREREQUISITE STEPS:
    0. **MANDATORY: Check rule status to ensure rule is fully developed before execution**
    1. User chooses to execute rule after creation
    2. Extract unique appTags from selected tasks → get user confirmation
    3. MANDATORY STEP (CANNOT BE SKIPPED):
        For each tag:
        - Fetch available applications via get_applications_for_tag().
        - Present them to the user for manual selection.
        - **Tool must not auto-select.** User decides to:
            a. Use an existing application, or  
            b. Run with new credentials (not persisted or saved as an application).
        - Proceed only after user confirmation for each tag.
        ```json
        [
            {
                "applicationType": "[application_class_name from fetch_applications(appType)]",
                "applicationId": "[Actual application ID chosen by user]",
                "appTags": "[Complete object from rule spec.tasks[].appTags]"
            }
        ]
        ```
        - If new: 
            a. get_application_info(tag_name) → present credential types
            b. collect credentials for chosen type → get user confirmation
            c. ask for application URL: "Application URL for {appType} (optional - press Enter to skip):"
            d. confirm complete configuration → move to next tag
        ```json
        [
            {
                "applicationType": "[application_class_name from fetch_applications(appType)]",
                "appURL": "[Application URL from user (optional - can be empty string)]",
                "credentialType": "[User chosen credential type]",
                "credentialValues": {
                    "[User provided credentials]"
                },
                "appTags": "[Complete object from rule spec.tasks[].appTags]"
            }
        ]
        ```
    4. Build applications array → get user confirmation
    5. Additional Inputs (optional):
        - Ask user: "Do you want to specify a date range for this execution?"
        - From Date (format: YYYY-MM-DD) - optional
        - To Date (format: YYYY-MM-DD) - optional
    6. Final confirmation → execute rule
    7. If execution starts successfully → call fetch_execution_progress()
    8. Rule Output File Display Process:
        a. Extract task outputs from execution results
        b. MANDATORY: Show output in this format:
            - TaskName: [task_name]
            - Files: [list of files]
        c. Ask: "View file contents? (yes/no)"
        d. If yes: Call fetch_output_file() for each requested file
        e. Display results with formatting
    9. Rule Publication (optional):
    - Ask user: "Do you want to publish this rule to make it available in ComplianceCow system? (yes/no)"
    - If yes: Call publish_rule() to publish the rule
    - If no: End workflow    

    UI DISPLAY REQUIREMENT:
    - The file URL must ALWAYS be displayed to the user in the UI, allowing the user to view or download the file directly.

    CRITICAL: rule_inputs MUST be the complete spec.inputsMeta__ objects with ALL original fields 
    (name, description, dataType, repeated, allowedValues, required, defaultValue, format, showField, 
    explanation) plus the 'value' field. DO NOT send trimmed objects with only name/dataType/value.

    Args:
        rule_name: The name of the rule to be executed.
        from_date: (Optional) Start date provided by the user in the format YYYY-MM-DD.
        to_date: (Optional) End date provided by the user in the format YYYY-MM-DD.
        rule_inputs: Complete spec.inputsMeta__ objects with ALL fields plus 'value' field.
        applications: Application configuration details, including credentials.
        is_application_data_provided_by_user (bool): 
            This value **must be determined strictly based on actual user input** during the workflow.
            - Set to True **only if** the user has provided or configured application details 
              (such as credentials or URL) during execution.
            - Set to False **if** the application information was pre-existing or selected from saved applications.
            - The tool must **not assume or predefine** this value without user confirmation.

    Returns:
        Dict with execution results
    """
    try:

        if not is_application_data_provided_by_user:
            return {
                "success": False, 
                "error": "Application information is missing. get application detials from user and try again."
            }

        for application in applications:
            is_valid, result = False,{}
            application_id = application.get("applicationId", None)
            logger.debug("applictcation id: {}\n".format(application))

            if application_id:
                if not is_valid_uuid(application_id):
                    return {"success": False, "error": f'The provided application ID: {application_id} is not valid. Please try again with a valid application ID.'}
                
                headers = wsutils.create_header()
                params = {
                    "id": application_id,
                    "validated": True
                }

                application_resp = wsutils.get(
                    path=wsutils.build_api_url(endpoint=constants.URL_FETCH_CREDENTIAL), 
                    params=params, 
                    header=headers
                )
                logger.debug("application_resp {}\n".format(application_resp))

                if rule.is_valid_array(application_resp, "items"):
                    for item in application_resp["items"]:
                        app_type = item.get("appType", "")
                        if isinstance(app_type, str) and app_type.endswith("::"):
                            app_type = app_type[:-2]
                        cc_application={
                            "id": item.get("id"),
                            "name": item.get("credentialName"),
                            "appType": app_type,
                            "othersTags":item.get("othersTags")
                        }
                        is_valid, result = validate_application(application,cc_application)
                        logger.debug("is_valid {}\n".format(is_valid))
                        if is_valid:
                            break
            else:
                continue

            if not is_valid and result:
                return {"success": False, "result":result}
        
        # Prepare execution payload
        execution_payload = {
            "fromDate": from_date,
            "toDate": to_date,
            "ruleName": rule_name, 
            "ruleInputs": rule_inputs, 
            "applications": applications
        }

        headers = wsutils.create_header()
    
        execution_result = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_EXECUTE_RULE), 
            data=json.dumps(execution_payload), 
            header=headers
        )

        return {
            "success": True, 
            "rule_name": rule_name, 
            "execution_id": execution_result.get("id"), 
            "message": f"Rule '{rule_name}' started executing."
        }

    except Exception as e:
        return {
            "success": False, 
            "rule_name": rule_name,
            "message": f"Failed to execute rule '{rule_name}': {e}"
        }


@mcp.tool()
def fetch_execution_progress(rule_name: str, execution_id: str) -> Dict[str, Any]:
    """
    Fetch execution progress for a running rule.
    
    IMPORTANT FOR CLAUDE/CLIENT:
    ================================
    This tool returns a snapshot of current progress. To see real-time updates:
    1. Call this tool repeatedly every 1 seconds
    2. Check the "continue_polling" flag in response
    3. If continue_polling=true, call again after 1 seconds
    4. If continue_polling=false, execution is complete
    
    DISPLAY INSTRUCTIONS FOR CLAUDE:
    ================================
    When displaying progress, REPLACE the previous output (don't append):
    
    🔄 **Execution Progress** (Live)
    ─────────────────────────────────
    
    Show each task on ONE line that UPDATES in place:
    • task_name (type) [progress_bar] XX% STATUS
    
    Use these Unicode blocks for progress bars:
    - COMPLETED: 🟦 (blue blocks)
    - INPROGRESS: 🟩 (green blocks) 
    - ERROR: 🟥 (red blocks)
    - PENDING: ⬜ (white blocks)
    
    After each poll, REPLACE the entire progress display with new data.
    DO NOT show multiple versions of the same task.
    
    EXAMPLE DISPLAY SEQUENCE:
    Poll 1:
    • fetch_users (HTTP) ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0% PENDING
    • process_data (Script) ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0% PENDING
    
    Poll 2 (REPLACES above):
    • fetch_users (HTTP) 🟩🟩🟩🟩⬜⬜⬜⬜⬜⬜ 40% INPROGRESS
    • process_data (Script) ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0% PENDING
    
    Poll 3 (REPLACES above):
    • fetch_users (HTTP) 🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦 100% COMPLETED
    • process_data (Script) 🟩🟩🟩⬜⬜⬜⬜⬜⬜⬜ 30% INPROGRESS
    
    RESPONSE FLAGS:
    - continue_polling: true = keep polling every 1 seconds
    - continue_polling: false = execution complete, show final summary
    - display_mode: "replace" = replace previous display
    
    UI DISPLAY REQUIREMENT:
    - The file URL must ALWAYS be displayed to the user in the UI, allowing the user to view or download the file directly.

    Args:
        rule_name: Rule being executed
        execution_id: ID from execute_rule()
        
    Returns:
        Dict with progress data and polling instructions
    """
    
    def consolidate_task_progress(progress_array):
        """Get latest state for each unique task from transaction history."""
        task_states = {}
        task_order = []
        
        for entry in progress_array:
            # Use taskId if available, otherwise use name as identifier
            task_id = entry.get("taskId") or entry.get("name", f"task_{len(task_states)}")
            
            if task_id not in task_order:
                task_order.append(task_id)
            
            # Update to latest state
            task_states[task_id] = {
                "id": task_id,
                "name": entry.get("name", "Unknown Task"),
                "type": entry.get("type", "Unknown"),
                "status": entry.get("status", "PENDING"),
                "progressPercentage": entry.get("progressPercentage", 0),
                "error": entry.get("error"),
                "outputs": entry.get("outputs")
            }
        
        return [task_states[tid] for tid in task_order]
    
    def create_progress_bar(percentage, status, bar_length=10):
        """Create a visual progress bar with colors."""
        filled = int((percentage / 100) * bar_length)
        empty = bar_length - filled
        
        # Use emoji blocks for universal color support
        if status == "COMPLETED":
            bar_char = "🟦"
        elif status == "INPROGRESS":
            bar_char = "🟩"
        elif status == "ERROR":
            bar_char = "🟥"
        else:  # PENDING
            bar_char = "⬜"
            filled = 0  # Show empty bar for pending
            empty = bar_length
        
        return bar_char * filled + "⬜" * empty
    
    try:
        header = wsutils.create_header()
        exec_payload = {"executionID": execution_id}
        
        # Fetch current progress
        exec_progress_resp = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_EXECUTION_PROGRESS),
            data=json.dumps(exec_payload),
            header=header
        )
        
        # Extract data
        overall_status = exec_progress_resp.get("status", "PENDING")
        task_summary = exec_progress_resp.get("taskProgressSummary", {})
        progress_array = exec_progress_resp.get("progress", [])
        
        # Consolidate tasks to current state
        consolidated_tasks = consolidate_task_progress(progress_array)
        
        # Create display data
        display_lines = []
        task_stats = {"COMPLETED": 0, "INPROGRESS": 0, "ERROR": 0, "PENDING": 0}
        
        for task in consolidated_tasks:
            status = task["status"]
            percentage = task["progressPercentage"]
            
            # Create progress bar
            progress_bar = create_progress_bar(percentage, status)
            
            # Format display line
            display_line = {
                "text": f"• {task['name']} ({task['type']}) {progress_bar} {percentage}% {status}",
                "task_name": task['name'],
                "task_type": task['type'],
                "progress_bar": progress_bar,
                "percentage": percentage,
                "status": status,
                "outputs": {
                    key : value for key, value in (task.get("outputs") or {}).items()
                    if key not in ["CompliancePCT_", "ComplianceStatus_"]
                } if task.get("outputs") else None
            }
            
            if status == "ERROR" and task.get("error"):
                display_line["error"] = task['error']
            
            display_lines.append(display_line)
            task_stats[status] = task_stats.get(status, 0) + 1
        
        # Determine if polling should continue
        continue_polling = overall_status not in ["COMPLETED", "ERROR"]
        
        # Create response
        response = {
            # Polling control
            "continue_polling": continue_polling,
            "polling_interval_seconds": 1,
            "display_mode": "replace",  # Tell client to replace, not append
            
            # Current state
            "status": overall_status,
            "rule_name": rule_name,
            "execution_id": execution_id,
            
            # Progress data
            "overall_progress_percentage": task_summary.get("progressPercentage", 0),
            "task_stats": {
                "completed": task_stats["COMPLETED"],
                "in_progress": task_stats["INPROGRESS"],
                "error": task_stats["ERROR"],
                "pending": task_stats["PENDING"],
                "total": len(consolidated_tasks)
            },
            
            # Display data
            "display_lines": display_lines,
            "display_header": f"🔄 **Execution Progress** - {rule_name}",
            "display_footer": f"Status: {overall_status} | Progress: {task_stats['COMPLETED']}/{len(consolidated_tasks)} tasks",
            
            # Metadata
            "transaction_count": len(progress_array),
            "unique_task_count": len(consolidated_tasks),
            "timestamp": exec_progress_resp.get("timestamp", "")
        }
        
        # Add completion data if finished
        if not continue_polling:
            response["completion_summary"] = {
                "final_status": overall_status,
                "total_tasks": len(consolidated_tasks),
                "successful_tasks": task_stats["COMPLETED"],
                "failed_tasks": task_stats["ERROR"]
            }
            response["display_header"] = f"✅ **Execution Complete** - {rule_name}" if overall_status == "COMPLETED" else f"❌ **Execution Failed** - {rule_name}"
        
        return response
        
    except Exception as e:
        return {
            "continue_polling": False,
            "status": "ERROR",
            "rule_name": rule_name,
            "execution_id": execution_id,
            "error": str(e),
            "display_header": "❌ **Error Fetching Progress**",
            "display_lines": [{"text": f"Error: {e}"}]
        }

@mcp.tool()
def fetch_output_file(file_url: str) -> Dict[str, Any]:
    """Fetch and display content of an output file from rule execution.

    FILE OUTPUT HANDLING:

    WHEN TO USE:
    - Rule execution output contains file URLs
    - User requests to view specific file content
    - Files contain reports, logs, compliance data, or analysis results

    CONTENT DISPLAY LOGIC:
    - If file size < 1KB: Show entire file content
    - If file size >= 1KB: Show only first 3 records/lines with user-friendly message
    - Supported formats: JSON, CSV, Parquet, and other text files
    - Always return file format extracted from filename
    - Provide clear user messaging about content truncation
    - CRITICAL: If content is truncated or full content, include truncation message with the display_content
    - The file URL (file_url) must ALWAYS be displayed to the user in the UI, allowing the user to view or download the file directly.
    
    MANDATORY CONTENT DISPLAY FORMAT:
    - FileName: [extracted from file_url]
    - Format: [file format from file_format]
    - Message: [truncation status or completion message if applicable user_message]  
    - Content: [display_content based on file format show the entire display_content]
    - File URL: [always show the file_url in the UI so the user can view or download the file]
    Args:
        file_url: URL of the file to fetch and display

    Returns:
        Dict containing file content, metadata, and display information
    """
    try:
        # Fetch file from API
        headers = wsutils.create_header()
        payload = {"fileURL": file_url}
        response = wsutils.post(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_FILE), 
            data=json.dumps(payload), 
            header=headers
        )

        file_content = response.get("fileContent", "")
        filename = response.get("fileName", "")
        
        # Get file format
        file_format = filename.split('.')[-1].lower() if '.' in filename else "unknown"
        if file_format == "pq": file_format = "parquet"

        # Decode content and calculate size
        try:
            if file_format == "parquet":
                actual_content = file_content  # Keep base64 for parquet
                file_size_bytes = len(base64.b64decode(file_content))
            else:
                actual_content = base64.b64decode(file_content).decode('utf-8')
                file_size_bytes = len(actual_content.encode('utf-8'))
        except:
            actual_content = file_content
            file_size_bytes = len(file_content.encode('utf-8'))

        file_size_kb = file_size_bytes / 1024
        
        # Process content - all preview functions now handle size logic internally
        if file_format == "parquet":
            display_content, info = rule.get_parquet_preview(actual_content, file_size_kb)
            user_message = f"📊 Parquet file ({file_size_kb:.2f}KB). {info}"
        elif file_format == "json":
            display_content, info = rule.get_json_preview(actual_content, file_size_kb)
            user_message = f"📄 JSON file ({file_size_kb:.2f}KB). {info}"
        elif file_format in ["csv", "tsv"]:
            display_content, info = rule.get_csv_preview(actual_content, file_size_kb)
            user_message = f"📊 {file_format.upper()} file ({file_size_kb:.2f}KB). {info}"
        else:
            # For other text files
            lines = actual_content.split('\n')
            if file_size_kb < 1.0:
                display_content = actual_content
                user_message = f"✅ Complete file ({file_size_kb:.3f}KB)"
            else:
                display_content = '\n'.join(lines[:3])
                if len(lines) > 3:
                    display_content += "\n... (truncated)"
                user_message = f"📄 File ({file_size_kb:.2f}KB). Showing first 3 of {len(lines)} lines, You can download it using the link below."

        return {
            "success": True,
            "file_url": file_url,
            "filename": filename,
            "file_format": file_format,
            "file_size_kb": round(file_size_kb, 2),
            "display_content": display_content,
            "user_message": user_message
        }

    except Exception as e:
        return {
            "success": False,
            "file_url": file_url,
            "error": f"Failed to fetch file: {e}"
        }


@mcp.tool()
def fetch_applications() -> Dict[str, Any]:
    """ 
    Fetch all available applications from the system.
    
    Returns:
        Dict containing list of applications with their details
    """
    try:
        applications = []
        headers = wsutils.create_header()
        
        get_app_resp = wsutils.get(
            path=wsutils.build_api_url(endpoint=constants.URL_FETCH_APPLICATIONS),
            header=headers
        )
        
        # Add null safety
        items = get_app_resp.get("items", [])
        if not items:
            return {
                "success": True,
                "applications": [],
                "message": "No applications found"
            }
        
        for item in items:
            meta = item.get("meta", {})
            labels = meta.get("labels", {})
            app_types = labels.get("appType", [])
            
            # Skip if no appType available
            if not app_types:
                continue
                
            applications.append({
                "application_class_name": meta.get("name", "Unknown"),
                "app_type": app_types[0]
            })

        return {
            "success": True,
            "applications": applications
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch applications: {str(e)}",
            "applications": []
        }

@mcp.tool()
def check_rule_status(rule_name: str) -> Dict[str, Any]:
    """
    Quick status check showing what's been collected and what's missing.
    Perfect for resuming in new chat windows.

    ENHANCED WITH AUTO-INFERENCE STATUS ANALYSIS:
    - Ignores stored status/phase fields and analyzes actual rule structure
    - Auto-detects completion status based on rule content (same logic as create_rule)
    - Calculates real-time progress percentage from actual components
    - Determines next actions based on what's actually missing
    - Provides accurate resumption guidance regardless of stored metadata
    - Perfect for cross-chat resumption with reliable state detection

    AUTO-INFERENCE LOGIC:
    - Analyzes spec.tasks, spec.inputs, spec.inputsMeta__, spec.ioMap, spec.outputsMeta__
    - Calculates completion based on actual content, not stored fields
    - Determines status: DRAFT → READY_FOR_CREATION → ACTIVE
    - Provides accurate progress: 5% → 25% → 85% → 100%
    - Identifies exactly what components are missing

    Args:
        rule_name: Name of the rule to check status for

    Returns:
        Dict with auto-inferred status information and accurate next action recommendations
    """
    
    try:
        current_rule = fetch_rule.fn(rule_name)
        if not current_rule["success"]:
            return {
                "success": False, 
                "error": f"Rule '{rule_name}' not found. Start new rule creation?",
                "suggested_action": "create_new_rule"
            }
        
        rule_structure = current_rule["rule_structure"]
        meta = rule_structure.get("meta", {})
        spec = rule_structure.get("spec", {})
        
        # AUTO-INFERENCE: Analyze actual rule structure content (same logic as create_rule)
        tasks = spec.get("tasks", [])
        inputs = spec.get("inputs", {})
        inputs_meta = spec.get("inputsMeta__", [])
        io_map = spec.get("ioMap", [])
        outputs_meta = spec.get("outputsMeta__", [])
        
        # Check for mandatory compliance outputs
        mandatory_outputs = ["CompliancePCT_", "ComplianceStatus_", "LogFile"]
        has_mandatory_outputs = all(
            any(output.get("name") == req_output for output in outputs_meta) 
            for req_output in mandatory_outputs
        )
        
        # Real-time completion analysis based on actual content
        completion_analysis = {
            "has_tasks": len(tasks) > 0,
            "has_inputs": len(inputs) > 0 and any(
                (isinstance(value, str) and value.strip() != "" and value != "<<MINIO_FILE_PATH>>" and not value.startswith("<<")) or
                (isinstance(value, bool)) or
                (isinstance(value, (int, float)) and value is not None)
                for value in inputs.values()
            ),
            "has_inputs_meta": len(inputs_meta) > 0,
            "has_io_mapping": len(io_map) > 0,
            "has_mandatory_outputs": has_mandatory_outputs,
            "tasks_count": len(tasks),
            "inputs_collected": sum(1 for value in inputs.values() if (
                (isinstance(value, str) and value.strip() != "" and value != "<<MINIO_FILE_PATH>>" and not value.startswith("<<")) or
                (isinstance(value, bool)) or
                (isinstance(value, (int, float)) and value is not None)
            )), 
            "inputs_meta_count": len(inputs_meta),
            "io_mappings_count": len(io_map),
            "inputs_match_metadata": len(inputs) == len(inputs_meta),
            "outputs_count": len(outputs_meta)
        }
        
        # AUTO-DETECT status and progress - FIXED LOGIC
        if (completion_analysis["has_io_mapping"] and 
            completion_analysis["inputs_collected"] == completion_analysis["inputs_meta_count"] and 
            completion_analysis["has_tasks"] and
            completion_analysis["has_mandatory_outputs"] and
            completion_analysis["inputs_match_metadata"]):
            # Rule is complete
            inferred_status = "ACTIVE"
            inferred_phase = "completed"
            progress_percentage = 100
            
        elif completion_analysis["has_tasks"]:
            if completion_analysis["inputs_collected"] == completion_analysis["inputs_meta_count"]:
                # ALL inputs collected - ready for finalization
                inferred_status = "READY_FOR_CREATION"
                inferred_phase = "inputs_collected" 
                progress_percentage = 85
            elif completion_analysis["inputs_collected"] > 0:
                # SOME inputs collected - still collecting
                inferred_status = "DRAFT"
                inferred_phase = "collecting_inputs"
                # Calculate actual progress based on collected vs total
                input_progress = (completion_analysis["inputs_collected"] / max(completion_analysis["inputs_meta_count"], 1)) * 60
                progress_percentage = min(25 + int(input_progress), 85)
            elif completion_analysis["has_inputs_meta"]:
                # Tasks defined, inputs metadata exists but no values collected yet
                inferred_status = "DRAFT"
                inferred_phase = "collecting_inputs"
                progress_percentage = 30  # Slightly higher since metadata is prepared
            else:
                # Tasks defined but no inputs yet
                inferred_status = "DRAFT"
                inferred_phase = "tasks_selected"
                progress_percentage = 25
        else:
            # No tasks defined yet
            inferred_status = "DRAFT"
            inferred_phase = "initialized"
            progress_percentage = 5

        # Determine what's missing and next actions based on inferred state - FIXED LOGIC
        missing_components = []
        if not completion_analysis["has_tasks"]:
            missing_components.append("task_selection")
        if completion_analysis["inputs_collected"] < completion_analysis["inputs_meta_count"]:
            missing_components.append("input_collection")
        if not completion_analysis["has_io_mapping"]:
            missing_components.append("io_mapping")
        if not completion_analysis["has_mandatory_outputs"]:
            missing_components.append("mandatory_outputs")

        # Determine next action based on inferred state
        if inferred_status == "ACTIVE":
            next_action = "rule_complete"
            message = f"✅ Rule '{rule_name}' is complete and ready to use!"
            available_actions = ["execute_rule", "create_design_notes", "create_readme", "view_rule"]
            
        elif inferred_status == "READY_FOR_CREATION":
            next_action = "ready_for_finalization"
            message = f"🎯 Rule '{rule_name}' has all {completion_analysis['inputs_collected']} inputs collected. Ready for I/O mapping and finalization."
            available_actions = ["finalize_rule", "verify_inputs", "view_yaml_preview"]
            
        elif inferred_phase == "tasks_selected":
            next_action = "need_input_collection"
            message = f"📋 Rule '{rule_name}' has {completion_analysis['tasks_count']} tasks defined. Ready to collect inputs."
            available_actions = ["start_input_collection", "view_input_overview"]
            
        elif inferred_phase == "collecting_inputs":
            # FIXED: Use actual inputs_meta_count instead of estimation
            remaining = max(0, completion_analysis["inputs_meta_count"] - completion_analysis["inputs_collected"])
            next_action = "continue_input_collection"
            message = f"⏳ Rule '{rule_name}' input collection in progress: {completion_analysis['inputs_collected']} collected, {remaining} remaining. Continue where you left off."
            available_actions = ["continue_collecting_inputs", "view_collected_inputs", "input_overview"]
            
        elif inferred_phase == "initialized":
            next_action = "need_task_selection"
            message = f"🚀 Rule '{rule_name}' is initialized. Need to select tasks to continue."
            available_actions = ["select_tasks", "view_rule_info"]
            
        else:
            next_action = "unknown_state"
            message = f"❓ Rule '{rule_name}' is in unknown state. Manual review may be needed."
            available_actions = ["view_rule_details", "restart_creation"]

        # Estimate remaining time based on what's missing - FIXED LOGIC
        if inferred_status == "ACTIVE":
            estimated_time = "Complete"
        elif inferred_status == "READY_FOR_CREATION":
            estimated_time = "~5 minutes (I/O mapping and finalization)"
        elif completion_analysis["has_tasks"]:
            remaining_inputs = max(0, completion_analysis["inputs_meta_count"] - completion_analysis["inputs_collected"])
            estimated_time = f"~{remaining_inputs * 2 + 5} minutes ({remaining_inputs} inputs + finalization)"
        else:
            estimated_time = "~15-20 minutes (full setup needed)"

        # Build comprehensive status info based on auto-inference
        status_info = {
            "rule_name": rule_name,
            "inferred_status": inferred_status,  # Auto-detected, not from stored field
            "inferred_phase": inferred_phase,    # Auto-detected, not from stored field
            "progress_percentage": progress_percentage,  # Calculated from actual content
            "missing_components": missing_components,
            "has_tasks": completion_analysis["has_tasks"],
            "has_inputs": completion_analysis["has_inputs"],
            "has_inputs_meta": completion_analysis["has_inputs_meta"],
            "inputs_match_metadata": completion_analysis["inputs_match_metadata"],
            "outputs_count": completion_analysis["outputs_count"],
            "tasks_defined": completion_analysis["tasks_count"],
            "inputs_collected": completion_analysis["inputs_collected"],
            "inputs_metadata_count": completion_analysis["inputs_meta_count"],
            "has_io_mapping": completion_analysis["has_io_mapping"],
            "io_mappings_count": completion_analysis["io_mappings_count"],
            "has_mandatory_outputs": completion_analysis["has_mandatory_outputs"],
            "estimated_time_to_completion": estimated_time,
            "last_updated": meta.get("last_updated"),
            "created_at": meta.get("created_at"),
            "next_action": next_action,
            "message": message,
            "available_actions": available_actions,
            "can_resume": True,
            "resume_instructions": f"To continue, simply say 'Continue with {rule_name}' or mention the specific action needed."
        }
        
        return {
            "success": True,
            "status_info": status_info,
            "rule_structure_summary": {
                "has_tasks": completion_analysis["has_tasks"],
                "has_inputs": completion_analysis["has_inputs"],
                "has_outputs": completion_analysis["has_mandatory_outputs"],
                "has_io_mapping": completion_analysis["has_io_mapping"],
                "total_components": sum([
                    completion_analysis["has_tasks"],
                    completion_analysis["has_inputs"],
                    completion_analysis["has_mandatory_outputs"],
                    completion_analysis["has_io_mapping"]
                ]),
                "completion_percentage": progress_percentage,
                "components_missing": len(missing_components),
                "components_complete": 4 - len(missing_components)  # tasks, inputs, outputs, io_mapping
            },
            "auto_inference_details": {
                "status_source": "analyzed_rule_content",
                "progress_source": "calculated_from_components",
                "phase_source": "inferred_from_structure",
                "reliable": True,
                "analysis_timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        return {"success": False, "error": f"Failed to check rule status: {e}"}   

def create_initial_rule_from_planning(rule_name: str, purpose: str, description: str, selected_tasks: List[Dict], primary_app_type: str = None) -> Dict[str, Any]:
    """
    Create initial rule structure after planning confirmation.
    This builds a rule with tasks but empty inputs - will be auto-detected as DRAFT status.
    
    This function is called internally after user confirms the input overview.
    """
    
    # Determine primary app type from tasks if not provided
    if not primary_app_type:
        app_types = []
        for task_info in selected_tasks:
            task_details = get_task_details.fn(task_info["task_name"])
            if task_details.get("appTags", {}).get("appType"):
                app_types.extend(task_details["appTags"]["appType"])
        unique_app_types = list(set([t for t in app_types if t != "nocredapp"]))
        primary_app_type = unique_app_types[0] if unique_app_types else "generic"

    # Build initial rule structure with tasks but no inputs
    initial_rule_structure = {
        "apiVersion": "rule.policycow.live/v1alpha1",
        "kind": "rule",
        "meta": {
            "name": rule_name,
            "purpose": purpose,
            "description": description,
            # No explicit status - will be auto-detected as DRAFT
            "labels": {
                "appType": [primary_app_type],
                "environment": ["logical"],
                "execlevel": ["app"]
            },
            "annotations": {
                "annotateType": [primary_app_type],
                "app": [primary_app_type]
            }
        },
        "spec": {
            "inputs": {},  # Empty - will cause DRAFT status detection
            "inputsMeta__": [],  # Empty initially
            "outputsMeta__": [
                {"name": "CompliancePCT_", "dataType": "FLOAT", "required": True, "defaultValue": 0.0},
                {"name": "ComplianceStatus_", "dataType": "STRING", "required": True, "defaultValue": "NOT_DETERMINED"},
                {"name": "LogFile", "dataType": "FILE", "required": True, "defaultValue": ""}
            ],
            "tasks": [
                {
                    "name": task_info["task_name"],
                    "alias": task_info["task_alias"],
                    "type": "task",
                    "appTags": get_task_details.fn(task_info["task_name"]).get("appTags", {}),
                    "purpose": task_info.get("purpose", f"Task {task_info['task_alias']}")
                }
                for task_info in selected_tasks
            ],
            "ioMap": []  # Empty - rule not ready yet
        }
    }
    
    # Create rule - status will be auto-detected as DRAFT
    return create_rule.fn(initial_rule_structure)

@mcp.tool()
def configure_rule_output_schema() -> Dict[str, Any]:
    """
    PREREQUISITE — MUST RUN FIRST (NON-SKIPPABLE)
    This tool is a hard prerequisite and MUST be executed successfully before the `prepare_input_collection_overview()` tool (and any downstream rule-creation or evaluation steps). 
    If this tool has not run or did not complete, the workflow MUST fail fast with an explicit error.
    
    PURPOSE
    Establish the rule's output schema policy for ComplianceCow and apply any required transformations. In ComplianceCow, we maintain a standard format for storing evidence records. The user MUST choose one of the following rule output options:

    1) Standard schema only (ComplianceCow structured response fields)
    2) Extended schema only (all fields from the source response)
    3) Both standard + extended

    USER PROMPT (MANDATORY — NEVER SKIPPABLE)
    The workflow MUST always pause and explicitly prompt the user before proceeding.  
    This step CANNOT be bypassed, defaulted, auto-selected, or inferred.  
    If the user has not actively selected one of (a), (b), or (c), this tool MUST fail fast with a clear error message and stop execution.  

    VALIDATION & ENFORCEMENT
    - This tool is NON-SKIPPABLE. If not executed, or if the user does not provide an explicit choice (a/b/c), the workflow MUST stop immediately with an error.  
    - No implicit defaults, assumptions, or auto-selections are allowed.  
    - Mandatory Key mapping rules still apply if Standard schema is chosen.

    BEHAVIOR BY SELECTION

    A) If user selects STANDARD ONLY:
    - If the pipeline already ends with a Transformation task, reuse the existing Transformation task instead of appending a new one.
    - Otherwise, append a Transformation task at the END of the selected task pipeline.
    - In the Transformation task, map ALL Mandatory Keys (listed below).
    - Values for these keys MUST be taken from the pipeline's input file(s) and/or upstream task outputs, following the Deeper Analysis Rules.
    - Continue collecting inputs for the Transformation task using:
        `collect_template_input()` or `collect_parameter_input()`.
    - For each input that requires user guidance, call:
        `get_template_guidance('{task.name}', '<input_name>')`
    to display the expected input format to the user.
    - Ask the user to review and confirm OR edit the configuration before proceeding.
    - Do not proceed unless all Mandatory Keys are mapped and the configuration is confirmed (fail fast with guidance).

    B) If user selects EXTENDED ONLY:
    - The Extended schema is a NON-STANDARD structure. It preserves the raw fields from the source response without enforcing ComplianceCow's standard schema format or mandatory key order.
    - Use the LAST task's output directly as the Extended schema output.
    - No mandatory field ordering or schema enforcement is applied — the structure is kept as-is for completeness and traceability.

    C) If user selects BOTH:
    - Perform all steps from (A) to create the Standard schema:
    * Append a Transformation task at the END of the selected task pipeline.
    * Map ALL Mandatory Keys in the exact required order.
    * Include <AdditionalKeysBasedOnUseCase> as needed for compliance.
    - Also add the Extended schema as a NON-STANDARD structure:
    * Create exactly ONE output field named: ExtendedData_<filename>.
        <filename> MUST be determinable from the use case (e.g., source, resource, or input artifact name).
    * Map the SAME LAST task output that is used as the input to the Transformation task into ExtendedData_<filename>.
    * Do NOT create duplicate extended outputs (for example, do not add both
        ExtendedData_JSONToCSV and ConvertedCSVFile if they contain the same data).
        Only ExtendedData_<filename> must exist.
    - Continue collecting inputs for the Transformation task using:
        collect_template_input() or collect_parameter_input().
    - For each input that requires user guidance, call:
        get_template_guidance('{task.name}', '<input_name>')
    to display the expected input format to the user.
    - Ask the user to review and confirm OR edit the configuration before proceeding.
    - Do not proceed unless:
    * All Mandatory Keys are mapped and validated in order
    * Configuration is confirmed by the user

    DEEPER ANALYSIS RULES
    - Always extract and map the core Mandatory Keys required for compliance.
    - For <AdditionalKeysBasedOnUseCase>, determine the minimal required fields based on the user's specific use case and map them under the Standard schema.
    - If additional fields are critical for the use case, map them explicitly into the Standard schema.
    - If fields are non-critical but useful, preserve them under `ExtendedData_<filename>`.
    - If MCP cannot store certain fields, the tool MUST explain the omission clearly to the user before proceeding and request confirmation if needed.

    MANDATORY KEYS (MUST ALWAYS BE MAPPED — IN THIS EXACT ORDER)
    - System
    - Source
    - ResourceID
    - ResourceName
    - ResourceType
    - ResourceLocation
    - ResourceTags
    - <Important Keys Based On User's Use Case>
        (for example: fields from the response file such as user_id, username, email,
        license_type, assigned_date, last_login_date, last_activity_date)
    - ValidationStatusCode
    - ValidationStatusNotes
    - ComplianceStatus
    - ComplianceStatusReason
    - EvaluatedTime
    - UserAction
    - ActionStatus
    - ActionResponseURL

    VALIDATION & ENFORCEMENT
    - This tool is NON-SKIPPABLE. If not executed, or if any Mandatory Key mapping is missing for the chosen Standard schema path, the workflow MUST stop with an error.
    - Key names are case-sensitive and MUST NOT be renamed.
    - The tool MUST persist the chosen option and mappings so that downstream tools consume a consistent schema contract.
    - The workflow MUST NOT proceed to `prepare_input_collection_overview()` until:
        * Inputs are collected via `collect_template_input()` or `collect_parameter_input()`
        * `get_template_guidance()` has been used for each input needing guidance
        * The user has confirmed or edited the configuration
        * All Mandatory Keys are mapped and validated in order
    - Mandatory, a JS chart (Mermaid/D3) MUST be generated to visualize the rule's I/O field structure. The chart must be displayed in this chat immediately after user input, and no further processing is allowed until this step is completed.

    EXECUTION ORDER GUARANTEE
    On success, and ONLY after input collection and configuration confirmation,
    the next tool to run MUST be `prepare_input_collection_overview()`.
    """
    user_message = (
        "In ComplianceCow, evidence is stored in a structured format.\n"
        "Please select one of the following options:\n"
        "(a) Standard schema — Stores evidence in the ComplianceCow standard format (mandatory information only)\n"
        "(b) Extended schema — Stores the raw or modified response (all information, not in standard structure)\n"
        "(c) Standard + Extended — Stores evidence in both standard and extended formats"
    )

    return {
        "user_prompt": user_message,
        "message": "Proceeding to user selection: Standard schema, Extended schema, or Standard + Extended.",
        "next_step":"Generates a JS chart (Mermaid/D3) to visualize the rule's I/O fields and task structure. The chart must be shown in this chat immediately after user input. NOTE: No further processing should occur before this step."
    }


def finalize_rule_with_io_mapping(rule_name: str, task_input_mapping: Dict = None) -> Dict[str, Any]:
    """
    Finalize rule by adding I/O mapping and setting status to ACTIVE.
    Called internally after user confirms input verification.
    
    This function builds the complete I/O mapping based on task sequence and collected inputs.
    """
    
    try:
        # Fetch current rule
        current_rule = fetch_rule.fn(rule_name)
        if not current_rule["success"]:
            return {"success": False, "error": f"Rule '{rule_name}' not found"}
        
        rule_structure = current_rule["rule_structure"]
        
        # Build I/O mapping from existing rule structure
        tasks = rule_structure["spec"]["tasks"]
        inputs = rule_structure["spec"]["inputs"]
        
        io_map = []
        
        if tasks and inputs:
            # Rule inputs to first task inputs
            if len(tasks) > 0:
                first_task_alias = tasks[0]["alias"]
                for input_name in inputs.keys():
                    # Use task_input_mapping if provided for precise mapping
                    if task_input_mapping and input_name in task_input_mapping:
                        original_input_name = task_input_mapping[input_name]["input_name"]
                        io_map.append(f"{first_task_alias}.Input.{original_input_name}:=*.Input.{input_name}")
                    else:
                        # Generic mapping
                        io_map.append(f"{first_task_alias}.Input.InputData:=*.Input.{input_name}")
            
            # Sequential task-to-task flow
            for i in range(len(tasks) - 1):
                current_alias = tasks[i]["alias"]
                next_alias = tasks[i + 1]["alias"]
                io_map.append(f"{next_alias}.Input.InputData:={current_alias}.Output.OutputData")
            
            # Final outputs from last task (mandatory compliance outputs)
            if len(tasks) > 0:
                last_alias = tasks[-1]["alias"]
                io_map.extend([
                    f"'*.Output.CompliancePCT_:={last_alias}.Output.CompliancePCT_'",
                    f"'*.Output.ComplianceStatus_:={last_alias}.Output.ComplianceStatus_'",
                    f"'*.Output.LogFile:={last_alias}.Output.LogFile'"
                ])
        
        # Add I/O mapping to rule
        rule_structure["spec"]["ioMap"] = io_map
        
        # Update rule - status will be auto-detected as ACTIVE
        return create_rule.fn(rule_structure)
        
    except Exception as e:
        return {"success": False, "error": f"Failed to finalize rule: {e}"}



def determine_next_steps(creation_phase: str, completion_analysis: Dict) -> List[str]:
    """Helper function to determine next steps based on current phase."""
    
    if creation_phase == "completed":
        return ["execute_rule", "create_design_notes", "create_readme"]
    elif creation_phase == "inputs_collected":
        return ["build_io_mapping", "finalize_rule"]
    elif creation_phase == "collecting_inputs":
        return ["continue_input_collection", "collect_remaining_inputs"]
    elif creation_phase == "tasks_selected":
        return ["prepare_input_overview", "start_input_collection"]
    elif creation_phase == "initialized":
        return ["select_tasks", "define_task_aliases"]
    else:
        return ["review_rule_structure", "check_requirements"]


def determine_next_action(creation_phase: str, completion_analysis: Dict) -> str:
    """Helper function to determine the immediate next action."""
    
    if creation_phase == "completed":
        return "Call create_design_notes() to auto-generate comprehensive design notes. Call create_rule_readme() to auto-generate a comprehensive README file."
    elif creation_phase == "inputs_collected":
        return "Call finalize_rule_with_io_mapping() to build I/O mapping and complete rule creation."
    elif creation_phase == "collecting_inputs":
        return "Continue collecting remaining inputs using collect_template_input() or collect_parameter_input()."
    elif creation_phase == "tasks_selected":
        return "Call prepare_input_collection_overview() to analyze input requirements and start collection."
    elif creation_phase == "initialized":
        return "Select tasks and define task aliases, then call prepare_input_collection_overview()."
    else:
        return "Review rule requirements and current state to determine next steps."


def estimate_completion_time(completion_analysis: Dict) -> str:
    """Helper function to estimate time to completion."""
    
    if completion_analysis.get("has_io_mapping"):
        return "Complete"
    elif completion_analysis.get("has_inputs"):
        return "~5 minutes"

def validate_input_name(input_name: str) -> str:
    """Ensure input names contain only alphanumeric characters and underscores"""
    import re
    if not re.match(r'^[a-zA-Z0-9_]+$', input_name):
        # Replace invalid characters with underscores
        cleaned_name = re.sub(r'[^a-zA-Z0-9_]', '_', input_name)
        return cleaned_name
    return input_name


@mcp.tool()
def validate_task_inputs(task_name: str, task_inputs: dict) -> Dict[str, Any]:
    """
    Validate the inputs of a specific task after gathering all required data during rule input collection.

    EXECUTION CONTEXT:
    - This tool MUST be executed immediately after completing input collection for each task 
      (e.g., after Task 1 input collection, validate Task 1 inputs; after Task 2 input collection, validate Task 2 inputs).
    - Ensures that validation occurs in sequence for every task before proceeding to the next.
    - If validation errors are found, the tool should provide detailed feedback and allow retrying input collection with corrections before re-validating the task inputs.
    - THIS IS A MANDATORY CHECKPOINT - NO TASK CAN PROCEED WITHOUT VALIDATION PASSING

    ADVANCED INPUT VALIDATION LOGIC:
    - Dynamically validates and maps collected inputs for the given task
    - Ensures that all mandatory parameters are provided and correctly formatted
    - Supports validation with mapped or skipped inputs using sample input based on the previous task response

    INTER-TASK DEPENDENCY HANDLING:
    - If a task expects input from a previous task (file or data mapping):
      1. Check if the input is marked as "from_previous_task" or has dependency metadata
      2. Generate sample data based on expected format from previous task's output
      3. Upload sample file using upload_file() and get file URL
      4. Use the file URL as input value for validation purposes only
      5. Mark this input as "sample_for_validation" in response
    
    SAMPLE FILE GENERATION LOGIC:
    - For CSV files: Generate 3-5 sample rows with realistic column names
    - For JSON files: Generate sample object/array with expected structure
    - For text files: Generate representative sample content
    - Sample should be minimal but structurally valid

    VALIDATION FLOW OVERVIEW:
    1. Avoid using placeholders for missing or skipped inputs.
    2. Receive collected inputs for a specific task
    3. Identify inputs that depend on previous tasks
    4. For dependency inputs:
       a. Generate appropriate sample data based on expected format
       b. Upload sample file and get URL
       c. Replace dependency marker with sample file URL
    5. Call task validation API with all inputs (actual + sample URLs)
    6. Parse validation response
    7. Return validation results with clear success/failure indicators

    VALIDATION RESPONSE HANDLING:
    - On Success: Return validation_status="PASSED" with any output details
    - On Failure: Return validation_status="FAILED" with detailed error messages
    - Include list of which inputs failed validation and why
    - Provide actionable guidance for fixing validation errors

    ERROR HANDLING:
    - Missing required inputs: List which inputs are missing
    - Invalid format: Specify format expected vs received
    - Type mismatches: Indicate correct data type needed
    - File access errors: Report if files can't be read/processed

    Args:
        task_name: Name of the task to validate
        task_inputs: Dictionary containing key-value pairs of collected task inputs
                    Format: {"input_name": "value" or "<<FROM_PREVIOUS_TASK>>" or file_url}

    Returns:
        Dict containing:
        {
            "success": bool,
            "validation_status": "PASSED" | "FAILED",
            "task_name": str,
            "validated_inputs": dict,  # Actual inputs used for validation (with sample URLs)
            "validation_output": dict,  # Output from validation API
            "errors": list,  # List of validation errors if failed
            "inputs_with_samples": list,  # List of inputs where samples were generated
            "message": str,
            "next_action": str  # What to do next based on validation result
        }
    """

    try:
        # Step 1: Prepare inputs for validation
        validated_input_dict = {}
        inputs_with_samples = []
        generated_files = []
        
        # Get task details to understand expected input structure
        task_details = get_task_details.fn(task_name)
        if task_details.get("error"):
            return {
                "success": False,
                "validation_status": "FAILED",
                "task_name": task_name,
                "error": f"Could not fetch task details: {task_details['error']}",
                "next_action": "verify_task_name"
            }
        
        task_inputs_spec = task_details.get("inputs", [])
        
        # Step 2: Process each input
        for input_spec in task_inputs_spec:
            input_name = input_spec["name"]
            input_data_type = input_spec.get("dataType", "STRING")
            input_format = input_spec.get("format")
            
            # Check if this input was collected
            if input_name in task_inputs:
                input_value = task_inputs[input_name]
                
                # Check if this input depends on previous task
                if isinstance(input_value, str) and (
                    input_value == "<<FROM_PREVIOUS_TASK>>" or
                    input_value.startswith("<<") or
                    "previous_task" in input_value.lower() or
                    input_value.strip() == ""
                ):
                    # This input needs sample data for validation
                    logger.info(f"Generating sample data for input '{input_name}' (depends on previous task)")
                    
                    # Generate sample file based on expected format
                    sample_content = generate_sample_input_content(
                        input_name=input_name,
                        data_type=input_data_type,
                        file_format=input_format,
                        task_context=task_details
                    )
                    
                    # Upload sample file
                    sample_filename = f"sample_{task_name}_{input_name}.{input_format or 'txt'}"
                    upload_result = upload_file.fn(
                        rule_name=f"validation_{task_name}",
                        file_name=sample_filename,
                        content=sample_content,
                        content_encoding="utf-8"
                    )
                    
                    if upload_result.get("success"):
                        validated_input_dict[input_name] = upload_result["file_url"]
                        inputs_with_samples.append({
                            "input_name": input_name,
                            "sample_file_url": upload_result["file_url"],
                            "sample_filename": sample_filename,
                            "note": "Sample data generated for validation - will use actual previous task output during execution"
                        })
                        generated_files.append(upload_result["file_url"])
                    else:
                        return {
                            "success": False,
                            "validation_status": "FAILED",
                            "task_name": task_name,
                            "error": f"Failed to upload sample file for input '{input_name}': {upload_result.get('error')}",
                            "next_action": "retry_sample_generation"
                        }
                else:
                    # Use the actual collected value
                    validated_input_dict[input_name] = input_value
            else:
                # Input not collected - check if it's required
                if input_spec.get("required", False):
                    return {
                        "success": False,
                        "validation_status": "FAILED",
                        "task_name": task_name,
                        "error": f"Required input '{input_name}' is missing",
                        "missing_inputs": [input_name],
                        "next_action": "collect_missing_inputs"
                    }
        
        # Step 3: Add validation flag
        validated_input_dict["ValidateFlow"] = True
        
        # Step 4: Call validation API
        request_body = {
            "taskname": task_name,
            "taskInputs": {
                "inputs": validated_input_dict
            }
        }
        
        logger.info(f"Validating task '{task_name}' with inputs: {list(validated_input_dict.keys())}")
        
        response = rule.execute_task_api(request_body)
        
        if not response:
            return {
                "success": False,
                "validation_status": "FAILED",
                "task_name": task_name,
                "validated_inputs": validated_input_dict,
                "inputs_with_samples": inputs_with_samples,
                "error": "Validation API returned no response",
                "next_action": "retry_validation"
            }
        
        # Step 5: Parse validation response
        task_outputs = response.get("taskOutputs", {})
        outputs = task_outputs.get("Outputs", {})
        validation_status_output = outputs.get("ValidationStatus")
        errors = outputs.get("Errors", [])
        
        # Determine if validation passed
        validation_passed = False
        if validation_status_output:
            # Check if validation explicitly passed
            if isinstance(validation_status_output, dict):
                validation_passed = validation_status_output.get("status") == "success"
            elif isinstance(validation_status_output, str):
                validation_passed = "success" in validation_status_output.lower()
        
        # Also check if there are no errors
        if not errors or len(errors) == 0:
            validation_passed = True
        
        # Step 6: Build response
        if validation_passed:
            return {
                "success": True,
                "validation_status": "PASSED",
                "task_name": task_name,
                "validated_inputs": validated_input_dict,
                "validation_output": outputs,
                "inputs_with_samples": inputs_with_samples,
                "generated_sample_files": generated_files,
                "message": f"✅ Task '{task_name}' inputs validated successfully. Ready to proceed to next task.",
                "next_action": "proceed_to_next_task"
            }
        else:
            # Validation failed
            error_details = []
            if errors:
                for error in errors:
                    if isinstance(error, dict):
                        error_details.append({
                            "field": error.get("field", "unknown"),
                            "message": error.get("message", "Validation failed"),
                            "type": error.get("type", "validation_error")
                        })
                    else:
                        error_details.append({"message": str(error)})
            
            return {
                "success": False,
                "validation_status": "FAILED",
                "task_name": task_name,
                "validated_inputs": validated_input_dict,
                "validation_output": outputs,
                "errors": error_details if error_details else ["Validation failed without specific error details"],
                "inputs_with_samples": inputs_with_samples,
                "message": f"❌ Task '{task_name}' validation failed. Please review errors and correct inputs.",
                "next_action": "fix_validation_errors"
            }

    except Exception as e:
        logger.error(f"Exception during task validation: {e}")
        return {
            "success": False,
            "validation_status": "FAILED",
            "task_name": task_name,
            "error": f"Exception during validation: {str(e)}",
            "exception_type": type(e).__name__,
            "next_action": "review_exception"
        }


def generate_sample_input_content(input_name: str, data_type: str, file_format: str, task_context: dict) -> str:
    """
    Generate sample input content for validation purposes.
    
    Args:
        input_name: Name of the input
        data_type: Data type of the input (FILE, STRING, etc.)
        file_format: Format of the file (csv, json, txt, etc.)
        task_context: Task details for context
    
    Returns:
        String content for sample file
    """
    
    # Default sample content
    if not file_format:
        return "Sample data for validation purposes"
    
    file_format = file_format.lower()
    
    # Generate format-specific samples
    if file_format == "csv":
        # Generate sample CSV
        return """id,name,value,status
1,Sample Item 1,100,active
2,Sample Item 2,200,active
3,Sample Item 3,150,inactive"""
    
    elif file_format == "json":
        # Generate sample JSON
        sample_data = [
            {
                "id": "1",
                "name": "Sample Item 1",
                "value": 100,
                "status": "active",
                "timestamp": "2025-01-15T10:00:00Z"
            },
            {
                "id": "2",
                "name": "Sample Item 2",
                "value": 200,
                "status": "active",
                "timestamp": "2025-01-15T11:00:00Z"
            }
        ]
        return json.dumps(sample_data, indent=2)
    
    elif file_format in ["yaml", "yml"]:
        # Generate sample YAML
        return """items:
  - id: 1
    name: Sample Item 1
    value: 100
    status: active
  - id: 2
    name: Sample Item 2
    value: 200
    status: active"""
    
    elif file_format == "xml":
        # Generate sample XML
        return """<?xml version="1.0" encoding="UTF-8"?>
<items>
    <item>
        <id>1</id>
        <name>Sample Item 1</name>
        <value>100</value>
        <status>active</status>
    </item>
    <item>
        <id>2</id>
        <name>Sample Item 2</name>
        <value>200</value>
        <status>active</status>
    </item>
</items>"""
    
    elif file_format == "txt":
        # Generate sample text
        return """Sample Data Line 1
Sample Data Line 2
Sample Data Line 3"""
    
    else:
        # Generic sample
        return f"Sample data for {input_name} - validation purposes only"
    
def is_valid_uuid(value: str) -> bool:
    """
    Check if the given string is a valid UUID.

    Args:
        value (str): The string to validate.

    Returns:
        bool: True if the string is a valid UUID, otherwise False.
    """
    try:
        uuid_obj = uuid.UUID(str(value))
        return str(uuid_obj) == value.lower()
    except (ValueError, TypeError, AttributeError):
        return False


def validate_application(selected_application: dict, cc_application: dict):
    """
    Validates that the user-selected application matches the stored ComplianceCow application.

    Checks:
        - applicationId matches the record ID.
        - appTags and othersTags have matching keys and values (case-insensitive).
        - Identifies missing, extra, or mismatched tags.

    Returns:
        (bool, dict):
            - bool: True if valid, False otherwise.
            - dict: Details of differences and a reconfiguration message if invalid.
    """

    if selected_application.get("applicationId") != cc_application.get("id"):
        return False, {
            "error": "The provided applicationId does not match the selected application. Please try again with a valid application ID."
        }

    result = {
        "missingInOthersTags": [],
        "extraInOthersTags": [],
        "mismatchedValues": []
    }
    is_valid = True
    app_tags = selected_application.get("appTags",{})
    others_tags = cc_application.get("othersTags",{})
    # Normalize all keys and values to lowercase for comparison
    app_tags_normalized = {k.lower(): sorted([v.lower() for v in vals]) for k, vals in app_tags.items()}
    others_tags_normalized = {k.lower(): sorted([v.lower() for v in vals]) for k, vals in others_tags.items()}

    # Check missing keys
    for key in app_tags_normalized:
        if key not in others_tags_normalized:
            is_valid = False
            result["missingInOthersTags"].append(key)

    # Check extra keys
    for key in others_tags_normalized:
        if key not in app_tags_normalized:
            is_valid = True
            result["extraInOthersTags"].append(key)

    # Check mismatched values for common keys
    for key in app_tags_normalized:
        if key in others_tags_normalized:
            if app_tags_normalized[key] != others_tags_normalized[key]:
                is_valid = False
                result["mismatchedValues"].append({
                    "key": key,
                    "expected": app_tags_normalized[key],
                    "found": others_tags_normalized[key]
                })
    if not is_valid:
        result["reconfigure"] = "Reconfigure the application and rule structure, then try again."

    return is_valid, result

