
import copy
import traceback
from typing import Any, Dict, List

from fastmcp import Context

from constants import constants
from mcpconfig.config import mcp
from mcptypes import forms_tool_types as vo
from utils import utils
from utils.debug import logger


def _normalize_matrix_options(elements: List[Any]) -> None:
    """For each Matrix element, sync all children's options to the first child's options (mutates in place). Recurses into Block/Statement Block/Matrix."""
    if not elements:
        return
    for item in elements:
        if not isinstance(item, dict):
            continue
        child_elements = item.get("elements")
        if isinstance(child_elements, list):
            if item.get("type") == "Matrix" and len(child_elements) > 0:
                first_options = child_elements[0].get("options")
                if first_options is not None:
                    first_options_copy = copy.deepcopy(first_options)
                    for child in child_elements[1:]:
                        if isinstance(child, dict) and child.get("type") in (
                            "Radio Button",
                            "Checkbox",
                        ):
                            child["options"] = copy.deepcopy(first_options_copy)
            _normalize_matrix_options(child_elements)


@mcp.tool()
async def list_forms(ctx: Context | None = None) -> vo.FormListVO:
    """
        Get all forms

        Returns:
            - forms (List[FormVO]): A list of forms. Each form has:
                - id (str): Form id.
                - name (str): Form name.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    try:
        logger.info("list_forms: \n")

        output = await utils.make_API_call_to_CCow_and_get_response(constants.URL_FORMS, "GET", ctx)
        logger.debug("list_forms output: {}\n".format(output))
        if isinstance(output, str) or "error" in output:
            logger.error("list_forms error: {}\n".format(output))
            return vo.FormListVO(error="Facing internal error")

        forms: List[vo.FormVO] = []
        for item in output:
            forms.append(
                vo.FormVO(
                    id=item.get("_id", ""),
                    name=item.get("name", ""),
                )
            )

        return vo.FormListVO(forms=forms)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_forms error: {}\n".format(e))
        return vo.FormListVO(error="Facing internal error")

@mcp.tool()
async def create_form(form: vo.CreateFormVO, ctx: Context | None = None) -> vo.CreateFormResponseVO:
    """
    Create a form

    Args:
        form: Form creation payload with:
            - name (str): Form name (required). Keep form name same as form title.
            - title (Optional[str]): Form title; when omitted, kept same as name.
            - elements (Optional[List[FormElementVO]]): Form elements (questions/widgets). Each element has:
               - type (str): Only allowed values: "Block", "Statement Block", "Short Text", "Paragraph", "Radio Button", "Checkbox", "Dropdown", "File Upload", "Matrix", "Date", "Date Range".
               - title (str): The question label or heading shown to the user (do not put this in footer).
               - footer (str): Optional helper or hint text shown below the question (e.g. instructions); separate from title.
               - sequence (int): Order of the element (0, 1, 2, ...).
               - isRequired (bool): Whether the question must be answered.
               - points (int): Max points for quiz; for option types, points can also be on each option.
               - elements (list): Nested child elements for "Block" or "Statement Block"; for "Matrix", must be list of "Radio Button" or "Checkbox" only; each child must have the same set of options; changing an option label in one child must be reflected in all children of that matrix.
               - options (list): For "Radio Button", "Checkbox", "Dropdown": list of {value (index as string which identifies the option item), label, points, defaultChecked, nextInSequence}; list.
               - isWriteInEnabled (bool): For "Dropdown" only; allows free-text input.
               - nextInSequence (int): For option types, -3 means options have jump config; in options, -2 means jump to form submission.
               - videoUrl (str): Optional; when set, holds a video URL to be rendered as an embedded video card for that element.
               - tags, value, dynamicOptionsId: Optional; use when relevant.
            - tags (Optional[List[FormTagsItemVO]]): Tags for the form. Each item has:
                - index (int): Tag index.
                - key (str): Tag key.
                - primary (bool): Whether this tag is primary.
                - values (List[str]): Tag values (e.g. ["asdf"]).
            - isQuiz (Optional[bool]): Whether the form is a quiz (default False).
            - totalPoints (Optional[int]): Total points (default 0).

    Returns:
        - form (Optional[FormVO]): Created form with id and name.
        - error (Optional[str]): Error message if creation failed.
    """
    try:
        logger.info("create_form: name=%s", form.name or form.title)

        payload = form.to_payload()
        if payload.get("elements"):
            _normalize_matrix_options(payload["elements"])
        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_FORMS, "POST", payload, ctx=ctx
        )
        logger.debug("create_form output: %s", output)

        if isinstance(output, str):
            logger.error("create_form error: %s", output)
            return vo.CreateFormResponseVO(error=output or "Facing internal error")
        if isinstance(output, dict) and output.get("error"):
            logger.error("create_form error: %s", output)
            return vo.CreateFormResponseVO(error=output.get("error", "Facing internal error"))
        if isinstance(output, dict) and "Message" in output:
            return vo.CreateFormResponseVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )

        # Success: response may be the created form object (e.g. _id, name)
        created = output if isinstance(output, dict) else {}
        form_id = created.get("_id") or created.get("id", "")
        form_name = created.get("name") or created.get("title", "")

        return vo.CreateFormResponseVO(
            form=vo.FormVO(id=form_id, name=form_name)
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_form error: %s", e)
        return vo.CreateFormResponseVO(error="Facing internal error")


@mcp.tool()
async def update_form(
    form_id: str,
    form: vo.UpdateFormVO,
    ctx: Context | None = None,
) -> vo.UpdateFormResponseVO:
    """
    Update an existing form.

    This function is used to update an existing form using form id and payload.

    Args:
        form_id: Form ID to update.
        form: Update payload with:
            - name (str): Form name (required). Keep form name same as form title.
            - title (Optional[str]): Form title; when omitted, kept same as name.
            - isQuiz (Optional[bool]): Whether the form is a quiz (default False).
            - totalPoints (Optional[int]): Total points (default 0).
            - elements (Optional[List[FormElementVO]]): Form elements (questions/widgets). Each element has:
               - type (str): Only allowed values: "Block", "Statement Block", "Short Text", "Paragraph", "Radio Button", "Checkbox", "Dropdown", "File Upload", "Matrix", "Date", "Date Range".
               - title (str): The question label or heading shown to the user (do not put this in footer).
               - footer (str): Optional helper or hint text shown below the question (e.g. instructions); separate from title.
               - sequence (int): Order of the element (0, 1, 2, ...).
               - isRequired (bool): Whether the question must be answered.
               - points (int): Max points for quiz; for option types, points can also be on each option.
               - elements (list): Nested child elements for "Block"; for "Matrix", must be list of "Radio Button" or "Checkbox" only; each child must have the same set of options; changing an option label in one child must be reflected in all children of that matrix.
               - options (list): For "Radio Button", "Checkbox", "Dropdown": list of {value (index as string which identifies the option item), label, points, defaultChecked, nextInSequence}; list.
               - isWriteInEnabled (bool): For "Dropdown" only; allows free-text input along with the options.
               - dynamicOptionsId (str): Dynamic option set id (e.g. from list_dynamic_options), if provided, the options will be replaced with the dynamic options for option type questions such as (Radio Button, Checkbox, Dropdown).
               - nextInSequence (int):(Jump configuration) For option types, -3 means options have jump config; in options, -2 means jump to submit, to jump to specific question use `nextInSequence`: `{sequence_of_the_next_question_to_jump_to}`.
               - videoUrl (str): Optional; when set, holds a video URL to be rendered as an embedded video card for that element.
               - tags, value.
            - type (Optional[str]): Form type (default "").
            - tags (Optional[List[FormTagsItemVO]]): Tags for the form. Each item has:
                - index (int): Tag index.
                - key (str): Tag key.
                - primary (bool): Whether this tag is primary.
                - values (List[str]): Tag values (e.g. ["asdf"]).

    Returns:
        - form (Optional[FormVO]): Updated form with id and name (from request; API returns no body).
        - error (Optional[str]): Error message if update failed.
    """
    try:
        logger.info("update_form: form_id=%s", form_id)

        url = f"{constants.URL_FORMS}/{form_id}"
        payload = form.to_payload()
        if payload.get("elements"):
            _normalize_matrix_options(payload["elements"])
        output = await utils.make_API_call_to_CCow_and_get_response(
            url, "PUT", payload, ctx=ctx
        )
        logger.debug("update_form output: %s", output)

        if isinstance(output, str):
            logger.error("update_form error: %s", output)
            return vo.UpdateFormResponseVO(error=output or "Facing internal error")
        if isinstance(output, dict) and output.get("error"):
            logger.error("update_form error: %s", output)
            return vo.UpdateFormResponseVO(
                error=output.get("error", "Facing internal error")
            )
        if isinstance(output, dict) and "Message" in output:
            return vo.UpdateFormResponseVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )

        return vo.UpdateFormResponseVO(
            form=vo.FormVO(
                id=form_id,
                name=form.name or form.title or "",
            )
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_form error: %s", e)
        return vo.UpdateFormResponseVO(error="Facing internal error")


def _is_dynamic_option_active(status) -> bool:
    """True if status indicates active dynamic option"""
    if status is True:
        return True
    if isinstance(status, str) and str(status).lower() == "active":
        return True
    return False


@mcp.tool()
async def list_dynamic_options(ctx: Context | None = None) -> vo.DynamicOptionListVO:
    """
    List dynamic options. Returns only id, name, and status.
    Only includes dynamic option sets with status active.

    Returns:
        - items (List[DynamicOptionVO]): Each item has id, name, status.
        - error (Optional[str]): Error message if the request failed.
    """
    try:
        logger.info("list_dynamic_options")

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_FORMS_DYNAMIC_OPTIONS, "GET", ctx=ctx
        )
        logger.debug("list_dynamic_options output: %s", output)

        if isinstance(output, str) or (isinstance(output, dict) and "error" in output):
            logger.error("list_dynamic_options error: %s", output)
            return vo.DynamicOptionListVO(error="Facing internal error")
        if isinstance(output, dict) and "Message" in output:
            return vo.DynamicOptionListVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )

        items_raw = output.get("items") if isinstance(output, dict) else []
        if not isinstance(items_raw, list):
            items_raw = []

        items: List[vo.DynamicOptionVO] = []
        for item in items_raw:
            if not isinstance(item, dict):
                continue
            status = item.get("status")
            if not _is_dynamic_option_active(status):
                continue
            items.append(
                vo.DynamicOptionVO(
                    id=item.get("_id", ""),
                    name=item.get("name", ""),
                    status=status,
                )
            )

        return vo.DynamicOptionListVO(items=items)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_dynamic_options error: %s", e)
        return vo.DynamicOptionListVO(error="Facing internal error")


@mcp.tool()
async def fetch_dynamic_option(
    dynamic_option_id: str,
    ctx: Context | None = None,
) -> vo.DynamicOptionDetailResponseVO:
    """
    Fetch a single dynamic option by id. Only returns data when the dynamic option set has status active.

    Args:
        dynamic_option_id: The dynamic option set id (e.g. from list_dynamic_options).

    Returns:
        - dynamic_option (Optional[DynamicOptionDetailVO]): id, name, status, options. Present only when status is active.
        - error (Optional[str]): Error message if the request failed or the option is not active.
    """
    try:
        logger.info("fetch_dynamic_option: id=%s", dynamic_option_id)

        url = f"{constants.URL_FORMS_DYNAMIC_OPTIONS}/{dynamic_option_id}"
        output = await utils.make_API_call_to_CCow_and_get_response(url, "GET", ctx=ctx)
        logger.debug("fetch_dynamic_option output: %s", output)

        if isinstance(output, str):
            logger.error("fetch_dynamic_option error: %s", output)
            return vo.DynamicOptionDetailResponseVO(error=output or "Facing internal error")
        if isinstance(output, dict) and output.get("error"):
            return vo.DynamicOptionDetailResponseVO(
                error=output.get("error", "Facing internal error")
            )
        if isinstance(output, dict) and "Message" in output:
            return vo.DynamicOptionDetailResponseVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )

        if not isinstance(output, dict):
            return vo.DynamicOptionDetailResponseVO(error="Invalid response")

        status = output.get("status")
        if not _is_dynamic_option_active(status):
            return vo.DynamicOptionDetailResponseVO(
                error="Dynamic option is not active; only active dynamic option sets can be used."
            )

        options_raw = output.get("options") or []
        options_list: List[vo.FormElementOptionVO] = []
        if isinstance(options_raw, list):
            for opt in options_raw:
                if isinstance(opt, dict):
                    try:
                        options_list.append(vo.FormElementOptionVO(**opt))
                    except Exception:
                        options_list.append(vo.FormElementOptionVO())

        return vo.DynamicOptionDetailResponseVO(
            dynamic_option=vo.DynamicOptionDetailVO(
                id=output.get("_id", ""),
                name=output.get("name", ""),
                status=status,
                options=options_list,
            )
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_dynamic_option error: %s", e)
        return vo.DynamicOptionDetailResponseVO(error="Facing internal error")


@mcp.tool()
async def list_forms_assigned_to_me(ctx: Context | None = None) -> vo.AssignedFormListVO:
    """
    List forms assigned to the current user. Use this when the user asks to fill a form
    assigned to them or to see their assigned forms.

    Returns:
        - items (List[AssignedFormVO]): Each item has: id (form assignment id), formID (unique form id),
          formName, dueDate, displayableDueDate, displayableAssignedOn, assignedBy, purpose, createdAt, tags.
        - error (Optional[str]): Error message if the request failed.
    """
    try:
        logger.info("list_forms_assigned_to_me")

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_MY_FORMS, "GET", ctx=ctx
        )
        logger.debug("list_forms_assigned_to_me output: %s", output)

        if isinstance(output, str):
            logger.error("list_forms_assigned_to_me error: %s", output)
            return vo.AssignedFormListVO(error=output or "Facing internal error")
        if isinstance(output, dict) and output.get("error"):
            return vo.AssignedFormListVO(error=output.get("error", "Facing internal error"))
        if isinstance(output, dict) and "Message" in output:
            return vo.AssignedFormListVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )

        items_raw = output.get("items") if isinstance(output, dict) else []
        if not isinstance(items_raw, list):
            items_raw = []

        items: List[vo.AssignedFormVO] = []
        for item in items_raw:
            if not isinstance(item, dict):
                continue
            items.append(
                vo.AssignedFormVO(
                    id=item.get("id", ""),
                    formID=item.get("formID", ""),
                    formName=item.get("formName", ""),
                    dueDate=item.get("dueDate", ""),
                    displayableDueDate=item.get("displayableDueDate", ""),
                    displayableAssignedOn=item.get("displayableAssignedOn", ""),
                    assignedBy=item.get("assignedBy", ""),
                    purpose=item.get("purpose", ""),
                    createdAt=item.get("createdAt", ""),
                    tags=item.get("tags"),
                )
            )

        return vo.AssignedFormListVO(items=items)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_forms_assigned_to_me error: %s", e)
        return vo.AssignedFormListVO(error="Facing internal error")


@mcp.tool()
async def fetch_complete_form(
    form_id: str,
    assign_id: str,
    ctx: Context | None = None,
) -> vo.FormDetailResponseVO:
    """
    Fetch the complete form definition by form id, including all elements (questions/widgets).

    Args:
        form_id: The form id (e.g. formID from an item returned by list_forms_assigned_to_me).

    Returns:
        - form (Optional[FormDetailVO]): Full form with id, name, title, isQuiz, totalPoints, elements, type, tags.
        - error (Optional[str]): Error message if the request failed.
    """
    try:
        logger.info("fetch_complete_form: form_id=%s, assign_id=%s", form_id, assign_id)

        payload = {"formId": form_id, "assignId": assign_id}
        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_FORMS_FETCH, "POST", payload, ctx=ctx
        )
        logger.debug("fetch_complete_form output: %s", output)

        if isinstance(output, str):
            logger.error("fetch_complete_form error: %s", output)
            return vo.FormDetailResponseVO(error=output or "Facing internal error")
        if isinstance(output, dict) and output.get("error"):
            return vo.FormDetailResponseVO(
                error=output.get("error", "Facing internal error")
            )
        if isinstance(output, dict) and "Message" in output:
            return vo.FormDetailResponseVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )

        if not isinstance(output, dict):
            return vo.FormDetailResponseVO(error="Invalid response")

        elements_raw = output.get("elements") or []
        elements_list: List[vo.FormElementVO] = []
        if isinstance(elements_raw, list):
            for elem in elements_raw:
                if isinstance(elem, dict):
                    try:
                        # `FormElementVO.id` is sourced from the API's `_id`.
                        elements_list.append(vo.FormElementVO(**elem))
                    except Exception:
                        pass

        tags_raw = output.get("tags") or []
        tags_list: List[vo.FormTagsItemVO] = []
        if isinstance(tags_raw, list):
            for t in tags_raw:
                if isinstance(t, dict):
                    tags_list.append(
                        vo.FormTagsItemVO(
                            key=t.get("key", ""),
                            values=t.get("values") if t.get("values") is not None else [],
                        )
                    )

        form_detail = vo.FormDetailVO(
            id=output.get("_id", ""),
            name=output.get("name", ""),
            title=output.get("title", ""),
            isQuiz=output.get("isQuiz", False),
            totalPoints=output.get("totalPoints", 0),
            type=output.get("type", ""),
            tags=tags_list if tags_list else None,
            elements=elements_list,
        )
        return vo.FormDetailResponseVO(form=form_detail)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_complete_form error: %s", e)
        return vo.FormDetailResponseVO(error="Facing internal error")


@mcp.tool()
async def check_form_progress(
    form_id: str,
    assign_id: str,
    ctx: Context | None = None,
) -> vo.FormProgressResponseVO:
    """
    Check form progress: answers filled so far for the given form and assignment.
    If items has length > 0, the form has been at least partially filled by the assigned user.

    Args:
        form_id: The form id (e.g. formID from list_forms_assigned_to_me).
        assign_id: The form assignment id (id from list_forms_assigned_to_me).

    Returns:
        - progress (Optional[FormProgressVO]): items (element id -> answer), totalQuestions,
          formResponseId, totalScore, totalPoints, status.
        - error (Optional[str]): Error message if the request failed.
    """
    try:
        logger.info("check_form_progress: form_id=%s, assign_id=%s", form_id, assign_id)

        url = f"{constants.URL_FORMS}/{form_id}/response/{assign_id}/progress"
        output = await utils.make_API_call_to_CCow_and_get_response(url, "GET", ctx=ctx)
        logger.debug("check_form_progress output: %s", output)

        if isinstance(output, str):
            logger.error("check_form_progress error: %s", output)
            return vo.FormProgressResponseVO(error=output or "Facing internal error")
        if isinstance(output, dict) and output.get("error"):
            return vo.FormProgressResponseVO(
                error=output.get("error", "Facing internal error")
            )
        if isinstance(output, dict) and "Message" in output:
            return vo.FormProgressResponseVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )

        if not isinstance(output, dict):
            return vo.FormProgressResponseVO(error="Invalid response")

        progress = vo.FormProgressVO(
            items=output.get("items"),
            totalQuestions=output.get("totalQuestions"),
            formResponseId=output.get("formResponseId", ""),
            totalScore=output.get("totalScore"),
            totalPoints=output.get("totalPoints"),
            status=output.get("status", ""),
        )
        return vo.FormProgressResponseVO(progress=progress)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("check_form_progress error: %s", e)
        return vo.FormProgressResponseVO(error="Facing internal error")


@mcp.tool()
async def create_form_response(
    form_id: str,
    user_id: str,
    assign_id: str,
    ctx: Context | None = None,
) -> vo.CreateFormResponseResponseVO:
    """
    Create a form response id for the given form, user, and assignment.the returned response ID is used to save the form response.

    Args:
        form_id: The form id.
        user_id: The user id (e.g. from get_current_user).
        assign_id: The form assignment id (id from list_forms_assigned_to_me).

    Returns:
        - form_response (Optional[CreateFormResponseResultVO]): id (the new form response id).
        - error (Optional[str]): Error message if the request failed.
    """
    try:
        logger.info(
            "create_form_response: form_id=%s, user_id=%s, assign_id=%s",
            form_id,
            user_id,
            assign_id,
        )

        url = f"{constants.URL_FORMS}/{form_id}/responses"
        payload = {"formId": form_id, "userId": user_id, "assignId": assign_id}
        output = await utils.make_API_call_to_CCow_and_get_response(
            url, "POST", payload, ctx=ctx
        )
        logger.debug("create_form_response output: %s", output)

        if isinstance(output, str):
            logger.error("create_form_response error: %s", output)
            return vo.CreateFormResponseResponseVO(
                error=output or "Facing internal error"
            )
        if isinstance(output, dict) and output.get("error"):
            return vo.CreateFormResponseResponseVO(
                error=output.get("error", "Facing internal error")
            )
        if isinstance(output, dict) and "Message" in output:
            return vo.CreateFormResponseResponseVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )

        if not isinstance(output, dict):
            return vo.CreateFormResponseResponseVO(error="Invalid response")

        form_response = vo.CreateFormResponseResultVO(
            id=output.get("_id", ""),
        )
        return vo.CreateFormResponseResponseVO(form_response=form_response)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_form_response error: %s", e)
        return vo.CreateFormResponseResponseVO(error="Facing internal error")


@mcp.tool()
async def get_current_user(ctx: Context | None = None) -> vo.CurrentUserResponseVO:
    """
    Get the current authenticated user (id, email, username).
    Use when creating form responses or when the flow needs the current user id.

    Returns:
        - user (Optional[CurrentUserVO]): ID, emailid, username.
        - error (Optional[str]): Error message if the request failed.
    """
    try:
        logger.info("get_current_user")

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_USERS_ME, "GET", ctx=ctx
        )
        logger.debug("get_current_user output: %s", output)

        if isinstance(output, str):
            logger.error("get_current_user error: %s", output)
            return vo.CurrentUserResponseVO(error=output or "Facing internal error")
        if isinstance(output, dict) and output.get("error"):
            return vo.CurrentUserResponseVO(
                error=output.get("error", "Facing internal error")
            )
        if isinstance(output, dict) and "Message" in output:
            return vo.CurrentUserResponseVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )

        if not isinstance(output, dict):
            return vo.CurrentUserResponseVO(error="Invalid response")

        user = vo.CurrentUserVO(
            ID=output.get("ID", ""),
            emailid=output.get("emailid", ""),
            username=output.get("username", ""),
        )
        return vo.CurrentUserResponseVO(user=user)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_current_user error: %s", e)
        return vo.CurrentUserResponseVO(error="Facing internal error")


@mcp.tool()
async def save_form_responses(
    form_id: str,
    form_response_id: str,
    form_responses: Dict[str, Any],
    ctx: Context | None = None,
) -> vo.SaveFormResponsesResponseVO:
    """
    Save the state of the form. Sends element answers for the given form response.
    Call this to persist answers before submitting.

    Args:
        form_id: The form id.
        form_response_id: The form response id (from create_form_response).
        form_responses: Map of element id -> answer value.
            - String value for text/date answers. For option-type questions, pass the string index of the selected option (Radio Button, Checkbox, Dropdown).
            - Date Range object: {toDate, fromDate}.
            - File Upload value: list of objects with {bucketName, filePath, fileName, fileHash}.

    Returns:
        - success (bool): True if save succeeded (204).
        - error (Optional[str]): Error message if the request failed.
    """
    try:
        logger.info(
            "save_form_responses: form_id=%s, form_response_id=%s",
            form_id,
            form_response_id,
        )

        url = f"{constants.URL_FORMS}/{form_id}/responses/{form_response_id}/elements"
        payload = {
            "formResponseId": form_response_id,
            "formResponses": form_responses,
        }
        output = await utils.make_API_call_to_CCow_and_get_response(
            url, "PUT", payload, ctx=ctx
        )
        logger.debug("save_form_responses output: %s", output)

        if isinstance(output, str):
            logger.error("save_form_responses error: %s", output)
            return vo.SaveFormResponsesResponseVO(error=output or "Facing internal error")
        if isinstance(output, dict) and output.get("error"):
            return vo.SaveFormResponsesResponseVO(
                error=output.get("error", "Facing internal error")
            )
        if isinstance(output, dict) and "Message" in output:
            return vo.SaveFormResponsesResponseVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )

        # 204 No Content returns {} from utils
        return vo.SaveFormResponsesResponseVO(success=True)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("save_form_responses error: %s", e)
        return vo.SaveFormResponsesResponseVO(error="Facing internal error")


@mcp.tool()
async def submit_user_form(
    user_id: str,
    assign_id: str,
    form_id: str,
    ctx: Context | None = None,
) -> vo.SubmitUserFormResponseVO:
    """
    Submit the form on behalf of the user. Call this after saving form responses when the user
    is done filling the form.

    Args:
        user_id: The user id (e.g. from get_current_user).
        assign_id: The form assignment id (id from list_forms_assigned_to_me).
        form_id: The form id.

    Returns:
        - success (Optional[bool]): True if submit succeeded.
        - error (Optional[str]): Error message if the request failed.
    """
    try:
        logger.info(
            "submit_user_form: user_id=%s, assign_id=%s, form_id=%s",
            user_id,
            assign_id,
            form_id,
        )

        payload = {
            "userID": user_id,
            "myformID": assign_id,
            "formID": form_id,
        }
        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_USER_FORMS_SUBMIT, "POST", payload, ctx=ctx
        )
        logger.debug("submit_user_form output: %s", output)

        if isinstance(output, str):
            logger.error("submit_user_form error: %s", output)
            return vo.SubmitUserFormResponseVO(
                error=output or "Facing internal error"
            )
        if isinstance(output, dict) and output.get("error"):
            return vo.SubmitUserFormResponseVO(
                error=output.get("error", "Facing internal error")
            )
        if isinstance(output, dict) and "Message" in output:
            return vo.SubmitUserFormResponseVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )

        return vo.SubmitUserFormResponseVO(success=True)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("submit_user_form error: %s", e)
        return vo.SubmitUserFormResponseVO(error="Facing internal error")


