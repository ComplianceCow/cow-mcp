
from mcpconfig.config import mcp


@mcp.prompt()
def ccow_workflow_knowelege() -> str:

    prompt = """
            WORKFLOW OVERVIEW
            =================

            A Workflow is a predefined sequence of logical steps or operations that are triggered by a specific event and executed according to a flowchart of nodes.

            Workflows are used in automation system, business logic engines, or compliance platforms to define how tasks, decisions, and wait times should be handled after a trigger.

            ------------------------------------------------------------
            TRIGGER EVENTS
            --------------
            Workflows begin execution when specific events occur, such as:
            - Completion of an assessment run
            - Passage of a defined time period (e.g., 7 days after submission)
            - Manual user action (e.g., form submission or approval)

            ------------------------------------------------------------
            NODE TYPES IN WORKFLOW
            -----------------------
            A Workflow consists of three core node types, each playing a specific role in the flow:

            1. STATE NODE
            -------------
            Definition:
            A State node is a passive node where the workflow waits until a specific event occurs.

            Purpose:
            - Marks the start and end of the workflow
            - Can be used mid-flow to pause execution

            Triggers:
            - User actions (e.g., submit, approve)
            - Time-based events (e.g., wait 2 days)


            2. ACTIVITY NODE
            ----------------
            Definition:
            An Activity node performs actions, calculations, or task invocations. It produces output based on provided inputs.

            Purpose:
            - Execute rules, functions, or tasks
            - Interface with APIs or other workflows

            Subtypes:
            - Pre-built Function: Executes predefined logic
            - Pre-built Rule: Execute a rule
            - Pre-built Task: Triggers a predefined task
            - Existing Workflow: Invokes another saved workflow

    
            3. CONDITION NODE
            -----------------
            Definition:
            A Condition node is a decision point where the workflow chooses a path based on a CL expression.

            Purpose:
            - Route logic dynamically
            - Handle yes/no branching

            Outcomes:
            - Yes path: If the condition is satisfied
            - No path: If the condition is not satisfied


            IMPORTANT 
            ----------------

            ## Must Only use activity, condition, state within compliancecow to create workflow,
                -  Prebuild function, Prebuild task, Prebuild rule used inside activites
                -  Custom label can be given to activity, state and conditon (Mostly try to use custom label)

            ## Prompt the user to enter input required and not available in previous node's output without this dont generate complete workflow
                
            ## Always get the required events, functioms, tasks, rules, conditions and everyting required to build workflow, Then use them to build the workflow

            1) The output edge of a State node always represents an event. This means that some event (e.g., user action or time-based trigger) will occur before moving to the next node.

            2) A State node can only connect to either an Activity node or a Condition node or state node.

            3) In an Activity node, some processing or execution takes place. After completion, the Activity node can connect to:
            - Another Activity node
            - A Condition node
            - A State node

            4) A Condition node uses a conditional (Boolean/CL) expression to determine the path forward. It always has two possible branches:
            - Yes path (if the condition is true)
            - No path (if the condition is false)

            Both paths can lead to any type of next node:
            - Activity
            - State
            - Another Condition
            
            5) Node Inputs:
            → Mandatory:
            For each node, inputs must be mapped from the outputs of previous nodes.
            If a particular input is not available from any previous node's output, prompt the user to provide that input manually.

            → Example of Input Mapping: (from event)
            -----------------------------------------------

            inputs:
            - name: AssessmentRunID
                type: Text
                desc: >- 
                    This is the unique identifier for the assessment run whose
                    details are to be fetched.
                optional: false
                mapValueFrom:
                    outputField: runId
                    source:
                        label: When assessment run completed
                        id: {{id}}
                        displayable: When an assessment run is completed
                        categoryId: '3'
                        type: RESOURCE_BASED_EVENT
                        specInput:
                            expr: >-
                                assessmentName == "{{assessment_name}}"
                        payload:
                            - name: assessmentName
                              type: Text
                              desc: The name of the assessment.
                            - name: runName
                              type: Text
                              desc: The name of the assessment run.
                            - name: controlNumber
                              type: Text
                              desc: The unique number of the assessment run control.
                            - name: evidenceName
                              type: Text
                              desc: The name of the evidence.
                            - name: runId
                              type: Text
                              desc: The unique ID of the completed assessment run.
                            - name: runControlId
                              type: Text
                              desc: The unique ID of the control that was completed.
                            - name: evidenceId
                              type: Text
                              desc: The unique ID of the control evidence.
                    type: Event

            → Example of Input Mapping: (from activity)
            -----------------------------------------------

            inputs:
            - name: DataFile
              type: File
              desc: The input file from which the field will be extracted.
              optional: false
              mapValueFrom:
                outputField: AssessmentRunDetails
                source:
                  label: Activity 1
                  id: {{id}}
                  displayable: FetchAssessmentRunDetails
                  name: FetchAssessmentRunDetails
                  desc: FetchAssessmentRunDetails
                  appScopeName: ComplianceCowAppScope
                  inputs:
                    - name: AssessmentRunID
                      type: Text
                      desc: >-
                        This is the unique identifier for the assessment run
                        whose details are to be fetched.
                      optional: false
                      mapValueFrom:
                        outputField: runId
                        source:
                          label: When assessment run completed
                          id: {{id}}
                          displayable: When an assessment run is completed
                          categoryId: '3'
                          type: RESOURCE_BASED_EVENT
                          specInput:
                            expr: >-
                              assessmentName ==
                              "{{assessment_name}}"
                          payload:
                            - name: assessmentName
                              type: Text
                              desc: The name of the assessment.
                            - name: runName
                              type: Text
                              desc: The name of the assessment run.
                            - name: controlNumber
                              type: Text
                              desc: The unique number of the assessment run control.
                            - name: evidenceName
                              type: Text
                              desc: The name of the evidence.
                            - name: runId
                              type: Text
                              desc: The unique ID of the completed assessment run.
                            - name: runControlId
                              type: Text
                              desc: The unique ID of the control that was completed.
                            - name: evidenceId
                              type: Text
                              desc: The unique ID of the control evidence.
                        type: Event
                  outputs:
                    - name: AssessmentDetails
                      type: File
                      desc: >-
                        This output contains detailed metadata regarding the
                        overall assessment for the provided AssessmentRunID.
                    - name: AssessmentRunDetails
                      type: File
                      desc: >-
                        This output contains detailed metadata regarding the
                        assessment run for the provided AssessmentRunID.
                    - name: Error
                      type: Text
                      desc: Error that have occurred while executing rule.
                type: Activity
            
            6) You can reference outputs from previous nodes within any value or expr field. These will be automatically filled when the workflow runs.
            EXAMPLE
            --------------------
            expr: '{{Activity.Activity 2.ExtractedValue}} == "FALSE"'
            value: Assessment {{Event.Assessment Run Completed.assessmentName}} has been completed.
            value: Form assigned with ID {{Activity.Assign Form.formAssignmentID}}.

            7) User Actions:
            use below user action example as reference and use this know for create further workflow
            → Example of User action for Get File:
            ----------------------------------------------------
            (event - transition):
            ----------------------
            
          - from: State 1
            to: Activity 4
            label: Event 6
            type: Event
            event:
                id: {{id}}
                displayable: When the user action is completed
                categoryId: '6'
                status: Active
                desc: >-
                This event will be triggered when the user action is completed. It
                accepts an action.
                type: RESOURCE_BASED_EVENT
                payload:
                - name: action
                    type: Text
                    desc: This action should be the user-selected action name.
                - name: userActionId
                    type: Text
                    desc: The ID of the Requested user action.
                - name: comments
                    type: Text
                    desc: >-
                    User-provided comments explaining the reason for their chosen
                    action.
                - name: uploadedFileHash
                    type: File
                    desc: User-provided file uploaded as part of their action.
                - name: attachments
                    type: File
                    desc: User-provided files uploaded as part of their action.
                - name: payload
                    type: MultilineText
                    desc: User-provided inputs as part of their action.
                helpText: >-
                This event will be triggered when the user action is completed. It
                accepts an action.
                specInput:
                expr: action == "Ready to upload"

            (Actitivy)
            ----------
            Activity 3:
                groupName: Ungrouped
                action:
                    type: Function
                    reference:
                    id: '6.1'
                    displayable: Initiate user action request
                    name: RequestUserAction
                    desc: >-
                        **Initiate user action request**  is an activity used to send a
                        Slack notification that prompts specified users to choose an action
                        from a list of available options.
                    status: Active
                    categoryId: '6'
                    inputs:
                        - name: actionList
                        type: TextArray
                        desc: 'Commas separated: a list of actions for the user to trigger.'
                        value: Ready to upload
                        - name: recipients
                        type: TextArray
                        desc: 'Commas separated: List of users to receive the notification.'
                        value: {{user_email}}
                        - name: messageContent
                        type: MultilineText
                        desc: Markdown-supported content to display to the user(s).
                        value: Kindly the upload the Evidence CSV File
                        - name: helpLink
                        type: MultilineText
                        desc: >-
                            Markdown-supported content to display a reference link with the
                            message.
                        optional: true
                        - name: attachment
                        type: File
                        desc: >-
                            Attachment to be sent along with the message, which will be
                            displayed to the recipient(s).
                        optional: true
                        - name: commentPreference
                        type: DropDown
                        desc: >-
                            Choose if adding a comment is mandatory, optional, or not
                            required.
                        options: required,optional,not_required
                        value: not_required
                        - name: fileUploadPreference
                        type: DropDown
                        desc: >-
                            Specify whether uploading a file is mandatory, optional, or not
                            required.
                        options: required,optional,not_required
                        value: required
                        - name: disableReassignment
                        type: Boolean
                        desc: >-
                            Indicates whether reassignment is allowed. Set to true to
                            disable reassignment.
                        possibleValues:
                            - 'true'
                            - 'false'
                        value: 'false'
                        - name: tags
                        type: Json
                        desc: >-
                            Stores reference data as key-value pairs in the format {"key":
                            ["value"]}.
                        value: '{}'
                    helpText: >-
                        **Initiate user action request**  is an activity used to send a
                        Slack notification that prompts specified users to choose an action
                        from a list of available options.

                        
            INPUT GUIDENCE :
            ------------------------
                - For type textarray use string seprated by comma's 

            EXAMPLE
            --------------------
            Below is the workflow sample yaml for send notification to user after assessment run completed, Use this as reference to create further workflows (Always show the workflow diagram)

            generalvo:
                domainid: ""
                orgid: ""
                groupid: ""
            apiVersion: v3
            kind: kind
            metadata:
                name: workflowName
                description: workflowDescription
            spec:
                states:
                    End:
                    groupName: Ungrouped
                    Start:
                    groupName: Ungrouped
                activities:
                    Activity 1:
                    groupName: Ungrouped
                    action:
                        type: Function
                        reference:
                        id: "7.1"
                        displayable: Send Email Notification (in HTML)
                        desc: '**Send Email Notification (HTML)** is an activity used to send a
                            notification with HTML content to users.'
                        name: SendEmailNotification
                        categoryId: "7"
                        inputs:
                        - name: messageHeader
                            type: Text
                            desc: The header text to be displayed as part of the message content.
                            value: Header_Title
                        - name: recipients
                            type: TextArray
                            desc: Comma-separated list of users who will receive the notification.
                            value: userEmails
                        - name: messageContent
                            type: MultilineText
                            desc: HTML-formatted content that will be displayed to the recipient(s).
                            value: Body_Content
                        - name: attachment
                            type: File
                            desc: Attachment to be sent along with the message, which will be displayed
                            to the recipient(s).
                            optional: true
                conditions: {}
                transitions:
                - from: Start
                    to: Activity 1
                    type: Event
                    label: Event 1
                    event:
                    id: {{id}}
                    displayable: When an assessment run is completed
                    categoryId: "3"
                    type: RESOURCE_BASED_EVENT
                    specInput:
                        expr: assessmentName == "{{assessment_name}}"
                - from: Activity 1
                    to: End
                    type: PassThrough
                       
    """
    
    return prompt