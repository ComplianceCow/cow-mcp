
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

            

            VARIABLES IN WORKFLOW
            ----------------------
            Workflows support two types of variables:

            1. PREDEFINED VARIABLES
            -----------------------
            System-level variables mapped to specific operations. When you set a value for a predefined variable, 
            it automatically triggers the associated system operation (like notifications).

            2. CUSTOM VARIABLES
            --------------------
            User-defined variables for storing and passing values between activities. They don't trigger 
            system operations, just hold data for your workflow logic.
            
            Example - Variable:
            ---------------------------------------------------------
            Activity:
              groupName: Ungrouped
              action:
                type: Function
                reference:
                  categoryId: <<category_id>>
                  desc: <<desc>>
                  displayable: <<displayable>>
                  id: <<id>>
                  name: SetVariable
                  inputs:
                    - name: variableName
                      type: Text
                      desc: <<input_desc>>
                      mapValueFrom:                
                        type: PreDefinedVariable   
                      value: <<predefinded_or_custom_varaible_name>>
                    - name: variableType
                      type: DropDown
                      desc: <<input_desc>>
                      options: <<varaible_type_options>>
                      value: [[type_value]]
                    - name: variableValue
                      type: Text
                      desc: The value to assign to the variable.
                      dynamicTypeFrom: variableType
                      value: [[varaible_value]]
      
            spec:
              variables:
                - name: <<predefinded_or_custom_varaible_name>>
                  type: [[type_value]]

            IMPORTANT 
            ----------------

            ## Each time after getting all required complianceCow components, show your plan to the user and ask for confirmation or if they would like to make changes. If they choose to modify the plan, then ask for the required details.

            ## You can suggest improvements to the workflow, but make it clear that these are your suggestions based on the user's requirements.

            ## Summarize the workflow and prompt the user to enter the required details or inputs one by one to build the workflow.
            
            ## You are building a workflow interactively. First, ask the user only for the first required input. After the user responds, ask for the next input. Continue this step-by-step until all required inputs are collected. Do not ask for all inputs at once.

            ## Indicate which activity, condition or state need this input.
            
            ## Ensure a clear plan with all necessary mappings is in place before generating the YAML.
            
            ## Use Custom label to make workflow more meaningful and easy to understand.
            
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
              - name: <<input_name>>
                type: <<input_datatype>>
                desc: <<input_desc>>
                optional: false
                mapValueFrom:
                    outputField: <<output_name>>
                    source:
                        label: <<event_label>>
                        id: <<event_id>>
                        displayable: <<event_displayable>>
                        categoryId: <<category_id>>
                        type: <<type>>
                        specInput:
                            expr: >-
                                <<payload_name>> == "[[payload_value]]"
                    type: Event

            → Example of Input Mapping: (from activity)
            -----------------------------------------------

            inputs:
            - name: <<input_name>>
              type: <<input_datatype>>
              desc: <<input_desc>>
              optional: false
              mapValueFrom:
                outputField: <<output_name>>
                source:
                  label: <<activity_label>>
                  id: <<activity_id>>
                  displayable: <<activity_displayable>>
                  name: <<activity_name>>
                  desc: <<activity_desc>>
                  appScopeName: <<appscope>>
                type: Activity
            
            6) You can reference outputs from previous nodes within any value or expr field. These will be automatically filled when the workflow runs.
            EXAMPLE
            --------------------
            expr: '{{Activity.<<activity_customlabel>>.ExtractedValue}} == "FALSE"'
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
              <<condition_customlabel>>:
                groupName: Ungrouped
                action:
                    type: Expression
                    expr: {{Event.<<event_customlabel>>.formName}} == "[[form_name]]"
            transitions:
                - from: <<activity_customlabel>
                    to: <condition_customlabel>
                    label: ''
                    type: PassThrough
                - from: <condition_customlabel>
                    to: <<activity_customlabel>
                    label: 'Yes'
                    type: Outcome
                    outcomeValue: 'Yes'
                - from: <condition_customlabel>
                    to: <<activity_customlabel>
                    label: 'No'
                    type: Outcome
                    outcomeValue: 'No'

            Example: (Funtions)
            ---------------------------------------

                  <<condition_customlabel>>:
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
            A workflow is always triggered when an event occurs. Select one of the available events from the event tool list.
            Each event includes a payload, which becomes available at runtime and can be used as output for other nodes in the workflow.
            The Start Event acts as the foundation of the workflow—when an external system triggers the workflow, the payload data is passed in and can be used directly.
            Ask the user to confirm the selected event, or show a list of suitable events and let the user choose one. Then, use the selected event's payload to plan the workflow.

            10) Rules
            use below rule example as reference and use this knowledge for create further workflow
            → Example of get assessment run details:
            ----------------------------------------------------
            <<activity_customlabel>>:
                groupName: Ungrouped
                action:
                  type: Rule
                  reference:
                    id: <<rule_id>>
                    displayable: <<rule_displayable>>
                    name: <<rule_name>>
                    desc: <<rule__desc>>
                    appScopeName: <<app_scope>>
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
                                <<payload_name>> == "[[payload_value]]"
                        type: Event
                    outputs:
                      - name: <<output_name>>
                        type: <<output_type>>
                        desc: <<output_desc>>

            11) Workflows
            use below example as reference to add existing workflow to create further workflow
            ----------------------------------------------------
            <<activity_customlabel>>:
                groupName: Ungrouped
                action:
                  type: Rule
                  reference:
                    id: <<workflow_id>>
                    displayable: <<workflow_name>>
                    name: <<workflow_name>>
                    desc: <<workflow_desc>>
                    eventName: <<workflow_start_event>>
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
                                <<payload_name>> == "[[payload_value]]"
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
            Below is the workflow sample yaml, Use this as reference to create further workflows (Always show the workflow diagram)

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
                        displayable: <<function_displayable>
                        desc: <<function_desc>>
                        name: <<function_name>>
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
                        expr: <<payload_name>> == "[[payload_value]]"
                - from: Activity 1
                    to: End
                    type: PassThrough
                       
    """
    
    return prompt