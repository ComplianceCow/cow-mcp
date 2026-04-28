# FORM OVERVIEWS

## What is a form
A form in ComplianceCow is a tool that collects structured inputs using question types.
A form is primarily used for conducting surveys, feedback, and security/compliance questionnaires.

## Questions
A question is the atomic building block of a form.

Each question has:
- a label (title) shown to the user
- a question type (how input is captured)
- optional helper text (footer)
- requiredness
- an order position index (`sequence`; see below)
- additional behavior that depends on the question type (for example: containers, grids, option-jumps, scoring)

## Sequence (order index)
`sequence` is the **zero-based index of an element within its parent's `elements` array** -- it marks that element's position among its siblings at that level only.

- At the top level of a form, each root question/section is listed in `elements` in order; each has `sequence` `0`, `1`, `2`, ... matching its position in that list.
- **Nested containers** (for example a `Block` with child questions): the children have their **own** `elements` list, and each child's `sequence` is `0`, `1`, `2`, ... **within that nested list**, not the global form index. So numbering restarts under each parent.

Example (structure only):

```text
elements: [
  { sequence: 0 },
  { sequence: 1, elements: [ { sequence: 0 }, ... ] },
  { sequence: 2 }
]
```

Here the outer array has three siblings at positions `0`, `1`, and `2`. The middle item's nested `elements` start again at `sequence: 0` for the first child inside that block.

Jump logic (for example `nextInSequence` targeting a question) refers to the **configured sequence value** of a question in the form definition, which must stay consistent with this ordering when you add, remove, or reorder items.

## Question types
Forms support the following question types. Use the appropriate type based on the kind of input or content you need.

1. **Block** -- A structural container or section used to group related questions or content. Does not collect a direct answer. It may hold child question types.

2. **Statement Block** -- A block that displays static text, instructions, or statements. Used to provide context or guidance without requiring user input.

3. **Short Text** -- Single-line free text input. Accepts a short string (e.g. name, ID, code, single phrase).

4. **Paragraph** -- Multi-line free text input. Accepts longer prose, descriptions, or comments.

5. **Radio Button** -- Single-choice selection from a fixed list of options. Only one option can be selected.

6. **Checkbox** -- Multi-choice selection from a fixed list. One or more options can be selected.

7. **Dropdown** -- Single-choice selection from a list presented in a dropdown menu. Compact alternative to radio when many options exist. Also supports write-in input when write-in is enabled.

8. **File Upload** -- Control that allows the respondent to attach or upload one or more files (e.g. documents, images).

9. **Matrix** -- A grid-like container where each row is an answerable sub-question.
   - Row question type is restricted: every row must be either `Radio Button` or `Checkbox` only (one type per matrix; do not mix).
   - All rows in a Matrix must have the **same option set** (same order and meaning; point values apply consistently for quiz scoring).
   - Use a Matrix when the form needs to capture the **same set of options** for multiple, related items.
   - **Compliance example (radio)**: quarterly access certification where an approver must `Approve` / `Revoke` each user's role across a list of applications.
   - **Security posture example (checkbox)**: periodic privilege review where a security admin selects which entitlements (e.g. `Read`, `Write`, `Admin`) should remain for each service account.

10. **Date** -- Single date picker. Captures a calendar date (day, month, year), the date format is MM/DD/YYYY.

11. **Date Range** -- Start and end date pickers. Captures a period (e.g. project duration, validity window), the date format is MM/DD/YYYY.

## Form category
A **form category** is a label that groups related forms together. There is no separate category object in the API: the category **name** is stored as a form-level tag.

- Add a tag on the form with **`key`: `form_category`**. The **`values`** array holds the category name (for example `["Compliance"]`).
- At least **one** form must use this tag for a given category name before that category can appear when listing categories (categories are **derived** from tags, not created empty).
- Tag shape (example):

```json
[
  {
    "key": "form_category",
    "index": 0,
    "primary": true,
    "values": ["Compliance"]
  }
]
```

Use the MCP tools `list_form_categories`, `fetch_form_category`, and `set_form_category` to list category names, list forms in a category, or assign/update the `form_category` tag on a form.

## Form assignment
- A form can be assigned to any set of valid users.
- Upon assigning a form, you can also set `dueDate` and provide a `purpose` for that form assignment.

## Form configuration (optional, UI specific)
Form configuration customizes how a form is rendered in UI (look and feel + display behavior). It does not change question semantics or response meaning.

- Available global configuration catalogs include:
  - style catalogs: `fontFamilies`, `fontSizes`, `colors`, `layouts`
  - display-behavior catalog: `settings`
- A form-level `configuration` object can be added or updated after form creation, and can also be updated later for already-assigned forms.
- `configuration` is optional and is stored on the form under the `configuration` key.
- `configuration.display` holds settings values as string booleans (`"true"` / `"false"`), e.g. `showPagination`, `showOneByOne`, `showQuestionProgress`, `showQuestionNumber`.
- `configuration.styles` holds visual style selections:
  - `typography`: `font`, `fontSize`, `fontColor`
    - `fontColor` must be the `cssVar` from the colors config options (e.g. `"--color-destructive-400"`), not the hex value. Show the color `label` to the user; save the `cssVar`.
  - `layout`: `value`, `spacing`, `width`, `lineHeight`

Example:
```json
{
  "configuration": {
    "display": {
      "showPagination": "true",
      "showOneByOne": "false",
      "showQuestionProgress": "false",
      "showQuestionNumber": "false"
    },
    "styles": {
      "typography": {
        "font": "Inter, sans-serif",
        "fontSize": 10,
        "fontColor": "--color-constructive-100"
      },
      "layout": {
        "value": "compact",
        "spacing": 8,
        "width": 750,
        "lineHeight": 1.4
      }
    }
  }
}
```

## Form creation design concepts

### Dynamic options
- Dynamic options provide a reusable preset list of options for option-type questions (Radio Button, Checkbox, Dropdown).
- Always include a static fallback options list. Dynamic options may be unavailable, but the form must remain usable.

### Jump configuration
- Jump configuration redirects the next step based on the option selected.
- Question configuration indicates that options may contain jump directives.
- At runtime, each option's directive is interpreted as:
  - `nextInSequence: -2` => jump directly to submission
  - `nextInSequence: -3` => treat as "no jump"; follow default traversal order
  - `nextInSequence: <n>` => jump to the question whose configured sequence matches `<n>`

### Write-in
- Write-in is supported only for `Dropdown` questions.
- When write-in is enabled, the respondent can choose an option or enter a custom value.
- Enable with `isWriteInEnabled: true`.

### Quiz mode
- Quiz/scoring mode enables point-based scoring for option selections.
- When quiz mode is enabled, each option should define its point value.
- Enable with `isQuiz: true`; each option includes `points`.

### Example question payload (Radio Button, design-time)
Use this structure when defining a Radio Button question inside a form. Placeholders are values you set while creating the form.

```json
{
  "type": "Radio Button",
  "title": "{question_title}",
  "footer": "{question_footer}",
  "isRequired": {is_required},
  "sequence": {sequence_index},
  "tags": ["{tag_value_1}", "{tag_value_2}"],
  "points": {question_points_max},
  "nextInSequence": {question_level_jump_flag},
  "options": [
    {
      "value": "{option_value_string_index}",
      "label": "{option_label}",
      "points": {option_points},
      "defaultChecked": {default_checked},
      "nextInSequence": {option_level_jump_directive}
    }
  ]
}
```

Field meanings (placeholders):
- `type`: Question type. Use `"Radio Button"`.
- `title`: Question label shown to the user (`{question_title}`).
- `footer`: Helper text shown under the question (`{question_footer}`).
- `isRequired`: Whether the user must answer (`{is_required}`).
- `sequence`: Zero-based index of this element within its parent's `elements` array (sibling order at that level; nested lists each start at `0` again) (`{sequence_index}`).
- `tags`: Optional metadata list (`{tag_value_1}`, `{tag_value_2}`).
- `points`: Maximum points for quiz scoring (`{question_points_max}`).
- `nextInSequence`: Question-level jump configuration flag (`{question_level_jump_flag}`) default value should be -1.
- `options`: Selectable answers list.
  - `value`: Stored option identifier saved as the answer (`{option_value_string_index}`). This is the string index/value.
  - `label`: Option text shown to the user (`{option_label}`).
  - `points`: Points awarded if selected in quiz mode (`{option_points}`).
  - `defaultChecked`: Whether this option is pre-selected (`{default_checked}`).
  - `nextInSequence`: Option-level navigation directive (`{option_level_jump_directive}`) default value should be -3.

# OPERATIONAL RULES

## Form Preview URL guidelines
- Whenever you show a form URL, you MUST output the full URL as a clickable HTML anchor tag using the correct `host`.
- You MUST NOT show partial, relative, placeholder, or guessed URLs.
- After form creation or form update, you MUST show: `<a href="{host}/ui/manage-forms?id={form_id}" target="_blank">{host}/ui/manage-forms?id={form_id}</a>`.
- Before form submission, you MUST show: `<a href="{host}/ui/display-form?assign_id={form_assign_id}" target="_blank">{host}/ui/display-form?assign_id={form_assign_id}</a>`.

## Form creation and update guardrails
- Before creating or changing a form, prepare a plan (purpose, question types, order, scoring/jump logic) and ask for explicit user confirmation.
- After creating a form, show the form name and form id; keep the form id for later modifications.
- When modifying an existing form, update that form instead of creating a new one.
- If the request to "update/change the form" is ambiguous, ask which form to modify (by name or by id) or use the form id from the current conversation.
- If the user tries to update a form that does not exist, explicitly mention that the form they are trying to update does not exist.
- If the requirement is vague (e.g. "add some questions", "make a survey"), do not guess: ask the minimum clarifying question(s), one at a time; after each answer, acknowledge and continue.
- Use only question types and structures documented in this file.
- For `Radio Button`, `Checkbox`, and `Dropdown`, always provide options; use dynamic options only when intended; keep sequence consistent when adding/reordering.
- For `Matrix`, ensure every child row uses the same option set; when you change an option label/meaning in one row, apply it to all rows in that matrix.
- The `create_form`, `update_form`, and `assign_form` tools return a `host` field in their response. Use this `host` value to build any URLs shown to the user.
- Once form is created, you MUST show the full verification URL to the created form as a clickable HTML anchor tag: `<a href="{host}/ui/manage-forms?id={form_id}" target="_blank">{host}/ui/manage-forms?id={form_id}</a>`. Use the `host` from the create_form response. Do not show a relative path.
- Once form is updated, you MUST show the full verification URL to the updated form as a clickable HTML anchor tag: `<a href="{host}/ui/manage-forms?id={form_id}" target="_blank">{host}/ui/manage-forms?id={form_id}</a>`. Use the `host` from the update_form response. Do not show a relative path.
- After form creation optionally ask user for form configuration preferences.

## Form submission behavior

### Pre-submission confirmation
- If the user wants to check form progress, show the full preview URL and do not show the response from the `check_form_progress` tool.
- Proceed with submission ONLY after the user explicitly confirms.
- Before final submission, you MUST show a human-readable summary with only the form name, purpose, and assignment tags (if any). Do not show question counts or progress details; instead, show the full preview URL as mentioned below.
- Always show the full preview URL as a clickable HTML anchor tag: `<a href="{host}/ui/display-form?assign_id={form_assign_id}" target="_blank">{host}/ui/display-form?assign_id={form_assign_id}</a>`. Do not show a relative path.

### Resume / Start from the Beginning
- Load the saved progress for the current form and assignment.
- If no answers have been saved yet (Don't ask for ):

  - Start collecting from the first answerable question in traversal order.
- If some answers have been saved already:
  - Ask whether the user wants to `Start from the Beginning` or `Resume`.
  - If the user chooses `Resume`:
    - Traverse the form in declared order to build the ordered list of answerable question identifiers.
    - Start from the first answerable identifier that has no saved answer yet.
  - If the user chooses `Start from the Beginning`:
    - Start from the first answerable question again.
    - Overwrite previously saved answers as the user re-enters them.

### Traversal rules
- `Block` and `Statement Block`:
  - Do not ask for a direct answer.
  - Recursively traverse nested questions in declared order.
- `Matrix`:
  - Treat each child row question as answerable.
  - Collect each row's answer in increasing order.

### Input collection rules (one question at a time)
- Ask exactly one question per step.
- If the form is already fully or partially filled, you MUST run the `Resume / Start from the Beginning` flow before continuing to collect answers.
- For `Radio Button`, `Checkbox`, and `Dropdown`, you MUST show dynamic options when they are configured; if they are not available, you MUST use the fallback options from the question definition.
- After the user answers a question:
  - Persist ONLY that single answer into the current in-progress response mapping.
  - Update the local "answered set" so navigation decisions are correct.
- Do not batch multiple question answers in a single step.

### Form Quiz rules
- Quiz confidentiality: if the form is in quiz mode, do not reveal any answers while collecting; do not show the correct option(s)/answer key; do not provide correctness feedback or scoring before submission.
- While form creation only ask for quiz points for `Radio Button`,`Checkbox`,`Dropdown` and also ignore asking quiz points if dynamic options and jump config invovled
- For showing quiz total points use the `totalPoints` field from the form details response.
 
### Next-question selection (jump logic)
- Default: always follow traversal order to the next answerable question.
- Jump logic applies only to option-type questions: `Radio Button` and `Dropdown`.
- When jump directives are enabled for the selected option:
  - If the directive indicates "jump to submission", end the traversal and submit.
  - If the directive indicates "no jump", fall back to default traversal order.
  - Otherwise, jump to the question whose configured sequence/order matches the directive target.

### File upload behavior
- Never request raw file bytes inside chat.
- For the current `File Upload` question:
  - Provide the user the UI upload URL: `host+"/ui/display-form?assign_id={assign_id}"`.
  - Ask the user to complete the upload in the UI.
  - After upload completion is confirmed by the user:
    - Reload saved progress.
    - Proceed only once the saved answer for this upload question is available.

### Final submit behavior
- When traversal ends (or jump indicates submission):
  - Build a human-readable summary using the form's question labels and the user's saved selections.
  - Always include the full preview URL in that summary as a clickable HTML anchor tag: `<a href="{host}/ui/display-form?assign_id={form_assign_id}" target="_blank">{host}/ui/display-form?assign_id={form_assign_id}</a>`.
  - Show the summary and request explicit confirmation.
  - If confirmed: submit the form for the current user + assignment.
  - If declined: ask whether to `continue editing` (resume) or `start over`.

## Form assignment behavior
- First, ask for a list of user emails or user groups to assign the form to.
- Once collected, convert the emails to the corresponding user IDs and validate the user IDs.
- Assign the form to the valid user IDs and return a summary of the assignments to the users (including any failures, if available).

## Wire-format operational references
- Saved progress view:
  - `progress.items`: mapping of answered `element_id` -> stored answer
  - `progress.formResponseId`: the saved response/session identifier used while saving answers
- Option answer encoding:
  - For option-type questions, persist the selected option's configured `value` (string index/value), not the label.
- Jump directive reference (runtime interpretation):
  - `nextInSequence: -2` => jump to submission
  - `nextInSequence: -3` => no jump; use default traversal
  - `nextInSequence: <n>` => jump to question sequence/order `<n>`
