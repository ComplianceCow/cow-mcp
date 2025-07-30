
from mcpconfig.config import mcp


@mcp.prompt()
def ccow_workflow_knowledge() -> str:

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
            A Condition node is a decision point where the workflow chooses a path based on a CEL expression.

            Purpose:
            - Route logic dynamically
            - Handle yes/no branching

            Outcomes:
            - Yes path: If the condition is satisfied
            - No path: If the condition is not satisfied


            IMPORTANT 
            ----------------

            ## Summarize the workflow and prompt the user to enter the required details or inputs one by one to build the workflow.
            
            ## You are building a workflow interactively. First, ask the user only for the first required input. After the user responds, ask for the next input. Continue this step-by-step until all required inputs are collected. Do not ask for all inputs at once.

            ## Use Custom label to make workflow more meaningful and easy to understand
            
            ## Must Only use activity, condition, state within compliancecow to create workflow,
                -  Use only the exisitng inputs and outputs available on them
                -  Prebuild function, Prebuild task, Prebuild rule used inside activites
                -  Custom label can be given to activity, state and conditon (Mostly try to use custom label)

            ## Prompt the user to enter input required and not available in previous node's output without this dont generate complete workflow
                
            ## Always get the required events, functioms, tasks, rules, conditions and everyting required to build workflow, Then use them to build the workflow

            ## All the placeholder <<>> this should be replace only with responses dont specify on your own, ex: input_name,input_desc,input_type, event_type,..etc
            ## Include all the field from input,output filed response of activity,event tools ex: options,resource,possible_values,..etc fields.
            ## Don't Create any extra state, activity, event that not used anywhere in workflow.
            ## If the input field is required or optional is set to false, then it must not be left empty.
            
            ## If a resource field is available in the input, use that resource to retrieve the resource data, and then use the data for the input.

            1) The output edge of a State node always represents an event. This means that some event (e.g., user action or time-based trigger) will occur before moving to the next node.

            2) A State node can only connect to either an Activity node or a Condition node or state node.

            3) In an Activity node, some processing or execution takes place. After completion, the Activity node can connect to:
            - Another Activity node
            - A Condition node
            - A State node

            4) A Condition node uses a conditional CEL expression to determine the path forward. It always has two possible branches:
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
            Event inputs can be given in specinput
            Include all the inputs & outputs nodes in yaml don't miss any & don't change displayable, description & type

            → Examplfe of Event Input
            -----------------------------------------------
            specInput:
              <payload_name>: <payload_value>  

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
                        label: <<event_label>>
                        id: <<event_id>>
                        displayable: <<event_displayable>>
                        categoryId: <<category_id>>
                        type: <<type>>
                        specInput:
                            expr: >-
                                assessmentName == "[[assessment_name]]"
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
                  id: <<activity_id>>
                  displayable: FetchAssessmentRunDetails
                  name: FetchAssessmentRunDetails
                  desc: FetchAssessmentRunDetails
                  appScopeName: <<appscope>>
                type: Activity
            
            6) You can reference outputs from previous nodes within any value or expr field. These will be automatically filled when the workflow runs.
            EXAMPLE
            --------------------
            expr: '{{Activity.Activity 2.ExtractedValue}} == "FALSE"'
            value: Assessment {{Event.Assessment Run Completed.assessmentName}} has been completed.
            value: Form assigned with ID {{Activity.Assign Form.formAssignmentID}}.

            7) User Actions:
            use below user action example as reference and use this knowledge for create further workflow
            → Example of User action for Get File:
            ----------------------------------------------------
            (event - transition):
            ----------------------
            
          - from: State 1
            to: Activity 4
            label: Event 6
            type: Event
            event:
                id: <<event_id>
                displayable: <<event_displayable>>
                categoryId: <<category_id>>
                status: Active
                desc: <<event_description>>
                type: <<event_type>>
                payload:
                  - name: <<payload_name>>
                    type: <<payload_data_type>>
                    desc: <<payload_desc_type>>

                specInput:
                   expr: action == "[[action_input_value_from_user_action]]"

            (Activity)
            ----------
            Activity 3:
                groupName: Ungrouped
                action:
                    type: Function
                    reference:
                    id: <<function_id>>
                    displayable: Initiate user action request
                    name: RequestUserAction
                    desc: <<function_description>>
                    status: Active
                    categoryId: <<category_id>>
                    inputs:
                        - name: <<input_name>>
                          type: <<input_data_type>>
                          desc: <<input_desc_type>>
                          options: <<input_available_options_if_available>>
                          resource: <<input_resource_if_available>>
                          value: [[input_value]]


            8) Condition Mapping
            use below condition example as reference and use this knowledge for create further workflow
            Two ways of condition available functions & Conditional expression
            For functions then outcomevalue of condtition transitions match with possible values of funtion outputs
            If isPrimaryOutcome is true, the only allowed output should be from the possible values.

            Example: (Conditional expression)
            ----------------------------------------------------
            conditions:
                Condition 1:
                groupName: Ungrouped
                action:
                    type: Expression
                    expr: {{Event.Event 4.formName}} == "[[form_name]]"
            transitions:
                - from: Activity 1
                    to: Condition 1
                    label: ''
                    type: PassThrough
                - from: Condition 1
                    to: Activity 2
                    label: 'Yes'
                    type: Outcome
                    outcomeValue: 'Yes'
                - from: Condition 1
                    to: Activity 3
                    label: 'No'
                    type: Outcome
                    outcomeValue: 'No'

            Example: (Funtions)
            ---------------------------------------

                  Condition 2:
                    groupName: Ungrouped
                    action:
                      type: Function
                      reference:
                        categoryId: <<category_id>>
                        displayable: <<displayable>>
                        id: <<condition_id>>
                        name: <<condition_name>>
                        inputs:                                         
                        - name: <<input_name>>
                          type: <<input_datatype>>
                          mapValueFrom:
                            outputField: <<output_name>>
                            source:
                                categoryId: <<category_id>>
                                displayable: <<displayable>>
                                id: <<event_id>>
                                label: <<label>>
                            type: Event

                        - name: <<input_name>>
                          resource: <<resource_name>>
                          type: <<input_datatype>>
                          value: [[input_value]]
                        
                        outputs:
                        - name: <<output_name>>
                            type: <<type>>
                            desc: <<description>>
                            possible_values:
                            - <possible_value_1>
                            - <possible_value_2>
                            isPrimaryOutcome: true

            9) Event
            Always a workflow is triggered when an event is occur


            10) Rules
            use below rule example as reference and use this knowledge for create further workflow
            → Example of get assessment run details:
            ----------------------------------------------------
            Activity 1:
                groupName: Ungrouped
                action:
                  type: Rule
                  reference:
                    id: <<activity_id>>
                    displayable: FetchAssessmentRunDetails
                    name: FetchAssessmentRunDetails
                    desc: FetchAssessmentRunDetails
                    appScopeName: ComplianceCowAppScope
                    inputs:
                      - name: <<input_name>>
                        type: <<input_type>>
                        desc: <<input_desc>>
                        optional: false
                        options: <<input_available_options_if_available>>
                        mapValueFrom:
                          outputField: <<output_name>>
                          source:
                            label: <<event_label>>
                            id: <<event_id>>
                            displayable: <<event_displayable>
                            categoryId: <<category_id>>
                            type: <<event_type>
                            specInput:
                              expr: >-
                                assessmentName ==
                                "[[assessment_name]]"
                        type: Event
                    outputs:
                      - name: <<output_name>>
                        type: <<output_type>>
                        desc: <<output_desc>>
                                
            INPUT GUIDENCE :
            ------------------------
                - For type textarray use string seprated by comma's 
                - Send all options if available

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
                        id: <<function_id>>
                        displayable: Send Email Notification (in HTML)
                        desc: <<function_desc>>
                        name: SendEmailNotification
                        categoryId: <<category_id>>
                        inputs:
                          - name: <<input_value>>
                            type: <<input_type>>
                            desc: <<input_desc>>
                            optional: true
                conditions: {}
                transitions:
                - from: Start
                    to: Activity 1
                    type: Event
                    label: Event 1
                    event:
                    id: <<event_id>>
                    displayable: <<event_displayable>>
                    categoryId: <<category_id>>
                    type: <<event_type>>
                    specInput:
                        expr: assessmentName == "[[assessment_name]]"
                - from: Activity 1
                    to: End
                    type: PassThrough
                       
    """
    
    return prompt