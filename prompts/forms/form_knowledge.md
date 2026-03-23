FORM OVERVIEW
=================
 A form in complianceow is a tool that collects structured inputs using question types.

 A form is primarily used for conducting surveys, feedback, and security/compliance questionnaires.

------------------------------------------------------------
QUESTIONS
--------------
A question is the atomic building block of a form.

Each question has:
- a label (title) shown to the user
- a question type (how input is captured)
- optional helper text (footer)
- requiredness
- an order position (sequence)
- additional behavior that depends on the question type (for example: containers, grids, option-jumps, scoring)

------------------------------------------------------------
QUESTION TYPES
--------------
Forms support the following question types. Use the appropriate type based on the kind of input or content you need.

1. BLOCK
-------------
Definition:
A structural container or section used to group related questions or content. Does not collect a direct answer, It may holds child question types.

2. STATEMENT BLOCK
-------------
Definition:
A block that displays static text, instructions, or statements. Used to provide context or guidance without requiring user input.

3. SHORT TEXT
-------------
Definition:
Single-line free text input. Accepts a short string (e.g. name, ID, code, single phrase).

4. PARAGRAPH
-------------
Definition:
Multi-line free text input. Accepts longer prose, descriptions, or comments.

5. RADIO BUTTON
-------------
Definition:
Single-choice selection from a fixed list of options. Only one option can be selected.


6. CHECKBOX
-------------
Definition:
Multi-choice selection from a fixed list. One or more options can be selected.

7. DROPDOWN
-------------
Definition:
Single-choice selection from a list presented in a dropdown menu. Compact alternative to radio when many options exist. Also supports write-in input when write-in is enabled.


8. FILE UPLOAD
-------------
Definition:
Control that allows the respondent to attach or upload one or more files (e.g. documents, images).

9. MATRIX
-------------
- A matrix is a grid-like container where each row is an answerable sub-question.
- Row question type is restricted: every row must be either `Radio Button` or `Checkbox` only (one type per matrix; do not mix).
- All rows in a Matrix must have the **same option set** (same order and meaning; point values apply consistently for quiz scoring).

When to use Matrix question type:
- Use a Matrix when the form needs to capture the **same set of options** for multiple, related items, using either `Radio Button` or `Checkbox`.
- **Compliance example (radio)**: quarterly access certification where an approver must `Approve` / `Revoke` each user’s role across a list of applications.
- **Security posture example (checkbox)**: periodic privilege review where a security admin selects which entitlements (e.g. `Read`, `Write`, `Admin`) should remain for each service account.

10. DATE
-------------
Definition: 
Single date picker. Captures a calendar date (day, month, year), the date format is MM/DD/YYYY.

11. DATE RANGE
-------------
Definition:
Start and end date pickers. Captures a period (e.g. project duration, validity window), the date format is MM/DD/YYYY.

------------------------------------------------------------
FORM CREATION RULES
--------------------

Dynamic options
--------------
- Dynamic options provide a reusable preset list of options for option-type questions (Radio Button, Checkbox, Dropdown).
- Always include a static fallback options list. Dynamic options may be unavailable, but the form must remain usable.

Jump configuration
--------------
- Jump configuration redirects the next step based on the option selected.
- Example: Jump configuration reference (design-time)
  - Question configuration indicates that options may contain jump directives.
  - At runtime, each option’s directive is interpreted as:
    - `nextInSequence: -2` => jump directly to submission
    - `nextInSequence: -3` => treat as “no jump”; follow default traversal order
    - `nextInSequence: <n>` => jump to the question whose configured sequence matches `<n>`

Enable write in
--------------
- Write-in is supported only for `Dropdown` questions.
- When write-in is enabled, the respondent can choose an option or enter a custom value.

Example: Write-in flag (design-time)
- `isWriteInEnabled: true`

Form quiz
--------------
- Quiz/scoring mode enables point-based scoring for option selections.
- When quiz mode is enabled, each option should define its point value.

Example: Quiz/scoring mode (design-time)
- `isQuiz: true`
- Each option includes `points`



Example: Single question payload (Radio Button, design-time)
---------------------------------------------------------------
Use this structure when defining a Radio Button question inside a form. Placeholders are values you set while creating the form.

```json
{
  "type": "Radio Button",
  "title": "{{question_title}}",
  "footer": "{{question_footer}}",
  "isRequired": {{is_required}},
  "sequence": {{sequence_index}},
  "tags": ["{{tag_value_1}}", "{{tag_value_2}}"],
  "points": {{question_points_max}},
  "nextInSequence": {{question_level_jump_flag}},
  "options": [
    {
      "value": "{{option_value_string_index}}",
      "label": "{{option_label}}",
      "points": {{option_points}},
      "defaultChecked": {{default_checked}},
      "nextInSequence": {{option_level_jump_directive}}
    }
  ]
}
```

Field meanings (placeholders)
- `type`: Question type. Use `"Radio Button"`.
- `title`: Question label shown to the user (`{{question_title}}`).
- `footer`: Helper text shown under the question (`{{question_footer}}`).
- `isRequired`: Whether the user must answer (`{{is_required}}`).
- `sequence`: Ordering position within the form (`{{sequence_index}}`).
- `tags`: Optional metadata list (`{{tag_value_1}}`, `{{tag_value_2}}`).
- `points`: Maximum points for quiz scoring (`{{question_points_max}}`).
- `nextInSequence`: Question-level jump configuration flag (`{{question_level_jump_flag}}`).
- `options`: Selectable answers list.
  - `value`: Stored option identifier saved as the answer (`{{option_value_string_index}}`). This is the string index/value.
  - `label`: Option text shown to the user (`{{option_label}}`).
  - `points`: Points awarded if selected in quiz mode (`{{option_points}}`).
  - `defaultChecked`: Whether this option is pre-selected (`{{default_checked}}`).
  - `nextInSequence`: Option-level navigation directive (`{{option_level_jump_directive}}`).

OPERATIONAL RULES FOR FORM CREATION / UPDATES
------------------------------------------------
- Before creating or changing a form, prepare a plan (purpose, question types, order, scoring/jump logic) and ask for explicit user confirmation.
- After creating a form, show the form name and form id; keep the form id for later modifications.
- When modifying an existing form, update that form instead of creating a new one.
- If the request to “update/change the form” is ambiguous, ask which form to modify (by name or by id) or use the form id from the current conversation.
- If the requirement is vague (e.g. “add some questions”, “make a survey”), do not guess: ask the minimum clarifying question(s), one at a time; after each answer, acknowledge and continue.
- Use only question types and structures documented in this file.
- For `Radio Button`, `Checkbox`, and `Dropdown`, always provide options; use dynamic options only when intended; keep sequence consistent when adding/reordering.
- For `Matrix`, ensure every child row uses the same option set; when you change an option label/meaning in one row, apply it to all rows in that matrix.

FORM SUBMISSION RULES
-----------------------

PRE-SUBMISSION CONFIRMATION RULE
- Before final submission, show a human-readable summary of what the user filled so far.
- Proceed with submission ONLY after the user explicitly confirms.

RESUME / START-OVER RULE
- Load the saved progress for the current form and assignment.
- If no answers have been saved yet:
  - Start collecting from the first answerable question in traversal order.
- If some answers have been saved already:
  - Ask whether the user wants to `continue` (resume) or `start over`.
  - If the user chooses `continue`:
    - Traverse the form in declared order to build the ordered list of answerable question identifiers.
    - Start from the first answerable identifier that has no saved answer yet.
  - If the user chooses `start over`:
    - Start from the first answerable question again.
    - Overwrite previously saved answers as the user re-enters them.

TRAVERSAL RULES (STRUCTURE)
- `Block` and `Statement Block`:
  - Do not ask for a direct answer.
  - Recursively traverse nested questions in declared order.
- `Matrix`:
  - Treat each child row question as answerable.
  - Collect each row’s answer in increasing order.

INPUT COLLECTION RULES (ONE QUESTION AT A TIME)
- Ask exactly one question per step.
- After the user answers a question:
  - Persist ONLY that single answer into the current in-progress response mapping.
  - Update the local “answered set” so navigation decisions are correct.
- Do not batch multiple question answers in a single step.

NEXT-QUESTION SELECTION RULE (JUMP LOGIC)
- Default: always follow traversal order to the next answerable question.
- Jump logic applies only to option-type questions: `Radio Button` and `Dropdown`.
- When jump directives are enabled for the selected option:
  - If the directive indicates “jump to submission”, end the traversal and submit.
  - If the directive indicates “no jump”, fall back to default traversal order.
  - Otherwise, jump to the question whose configured sequence/order matches the directive target.

FILE UPLOAD RULE
- Never request raw file bytes inside chat.
- For the current `File Upload` question:
  - Provide the user the UI upload URL:
    - `host+"/ui/display-form?assign_id={{assign_id}}"`
  - Ask the user to complete the upload in the UI.
  - After upload completion is confirmed by the user:
    - Reload saved progress.
    - Proceed only once the saved answer for this upload question is available.

SUBMIT RULE
- When traversal ends (or jump indicates submission):
  - Build a human-readable summary using the form’s question labels and the user’s saved selections.
  - Show the summary and request explicit confirmation.
  - If confirmed: submit the form for the current user + assignment.
  - If declined: ask whether to `continue editing` (resume) or `start over`.

EXAMPLES (wire-format only; keep these details out of normal explanations)
- Saved progress view:
  - `progress.items`: mapping of answered `element_id` -> stored answer
  - `progress.formResponseId`: the saved response/session identifier used while saving answers
- Option answer encoding:
  - For option-type questions, persist the selected option’s configured `value` (string index/value), not the label.
- Jump directive reference (runtime interpretation):
  - `nextInSequence: -2` => jump to submission
  - `nextInSequence: -3` => no jump; use default traversal
  - `nextInSequence: <n>` => jump to question sequence/order `<n>`

 
