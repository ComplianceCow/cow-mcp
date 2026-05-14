import json
import traceback
from typing import Any, Dict, List, Optional

from fastmcp import Context

from constants import constants
from mcpconfig.config import mcp
from mcptypes import forms_tool_types as vo
from utils import utils
from utils.debug import logger
from utils.forms import (
    _base_host,
    collect_assignable_element_ids,
    elements_from_raw,
    extract_assign_form_ids_and_error,
    fetch_form_elements_for_assignment,
    fetch_form_raw,
    form_category_values,
    is_form_assigned,
    is_dynamic_option_active,
    list_forms_impl,
    merge_form_category_tag,
    normalize_assign_form_inputs,
    normalize_matrix_options,
    parse_form_tags_from_raw,
    update_form_impl,
)


@mcp.tool()
async def list_forms(ctx: Context | None = None) -> vo.FormListVO:
    """
        Get all forms

        Returns:
            - forms (list[FormVO]): A list of forms. Each form has:
                - id (str): Form id.
                - name (str): Form name.
                - tags (Optional[list[FormTagsItemVO]]): Form-level tags when the list API returns them (e.g. key form_category). Category tools require tags on each item from GET /v1/forms.
            - error (Optional[str]): An error message if any issues occurred during retrieval.
    """
    return await list_forms_impl(ctx)


@mcp.tool()
async def get_configurations_for_forms(
    ctx: Context | None = None,
) -> vo.GetFormConfigurationsResponseVO:
    """
    Get all form configuration options available globally for UI customization.

    Returns:
        - configurations (Optional[FormConfigurationsVO]): Catalog with fontFamilies, fontSizes, colors, layouts, settings.
        - error (Optional[str]): Error message if the request failed.
    """
    try:
        logger.info("get_configurations_for_forms")

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_FORMS_CONFIGURATIONS, "GET", ctx=ctx
        )
        logger.debug("get_configurations_for_forms output: %s", output)

        if isinstance(output, str):
            logger.error("get_configurations_for_forms error: %s", output)
            return vo.GetFormConfigurationsResponseVO(
                error=output or "Facing internal error"
            )
        if isinstance(output, dict) and output.get("error"):
            return vo.GetFormConfigurationsResponseVO(
                error=output.get("error", "Facing internal error")
            )
        if isinstance(output, dict) and "Message" in output:
            return vo.GetFormConfigurationsResponseVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )
        if not isinstance(output, dict):
            return vo.GetFormConfigurationsResponseVO(error="Invalid response")

        return vo.GetFormConfigurationsResponseVO(
            configurations=vo.FormConfigurationsVO(**output)
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("get_configurations_for_forms error: %s", e)
        return vo.GetFormConfigurationsResponseVO(error="Facing internal error")

@mcp.tool()
async def create_form(form: vo.CreateFormVO, ctx: Context | None = None) -> vo.CreateFormResponseVO:
    """
    Create a form

    Args:
        form: Form creation payload with:
            - name (str): Form name (required). Keep form name same as form title.
            - title (Optional[str]): Form title; when omitted, kept same as name.
            - elements (Optional[list[FormElementVO]]): Form elements (questions/widgets). Each element has:
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
            - tags (Optional[list[FormTagsItemVO]]): Tags for the form. Each item has:
                - index (int): Tag index.
                - key (str): Tag key.
                - primary (bool): Whether this tag is primary.
                - values (list[str]): Tag values (e.g. ["asdf"]).
            - isQuiz (Optional[bool]): Whether the form is a quiz (default False).
            - totalPoints (Optional[int]): Total points (default 0).

    Returns:
        - form (Optional[FormVO]): Created form with id and name.
        - host (Optional[str]): Platform host URL for building UI links.
        - error (Optional[str]): Error message if creation failed.
    """
    try:
        logger.info("create_form: name=%s", form.name or form.title)

        payload = form.to_api_payload()
        if payload.get("elements"):
            normalize_matrix_options(payload["elements"])
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

        created = output if isinstance(output, dict) else {}
        form_id = created.get("_id") or created.get("id", "")
        form_name = created.get("name") or created.get("title", "")

        return vo.CreateFormResponseVO(
            form=vo.FormVO(id=form_id, name=form_name),
            host=_base_host(),
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("create_form error: %s", e)
        return vo.CreateFormResponseVO(error="Facing internal error")


@mcp.tool()
async def clone_form(
    form_id: str,
    form_clone_name: str,
    ctx: Context | None = None,
) -> vo.CreateFormResponseVO:
    """
    Clone an existing form using a new form name.

    Args:
        form_id: Source form ID to clone.
        form_clone_name: Name for the cloned form.

    Returns:
        - form (Optional[FormVO]): Cloned form with id and name.
        - error (Optional[str]): Error message if cloning failed.
    """
    try:
        logger.info("clone_form: form_id=%s, clone_name=%s", form_id, form_clone_name)

        clone_name = form_clone_name.strip()
        if not clone_name:
            return vo.CreateFormResponseVO(error="form_clone_name is required")

        raw = await fetch_form_raw(form_id, ctx)
        if isinstance(raw, str):
            return vo.CreateFormResponseVO(error=raw)
        if not isinstance(raw, dict):
            return vo.CreateFormResponseVO(error="Invalid source form response")

        source_tags = raw.get("tags")
        tag_items: list[vo.FormTagVO] = []
        if isinstance(source_tags, list):
            for t in source_tags:
                if not isinstance(t, dict):
                    continue
                idx = t.get("index")
                prim = t.get("primary")
                vals = t.get("values")
                tag_items.append(
                    vo.FormTagVO(
                        index=idx if isinstance(idx, int) else 0,
                        key=t.get("key", "") or "",
                        primary=prim if isinstance(prim, bool) else False,
                        values=vals if isinstance(vals, list) else [],
                    )
                )

        clone_vo = vo.CreateFormVO(
            name=clone_name,
            title=clone_name,
            elements=raw.get("elements") if isinstance(raw.get("elements"), list) else [],
            type=raw.get("type", "") or "",
            tag=tag_items,
            isQuiz=raw.get("isQuiz", False),
            totalPoints=raw.get("totalPoints", 0),
            configuration=raw.get("configuration"),
        )

        payload = clone_vo.to_api_payload()
        if payload.get("elements"):
            normalize_matrix_options(payload["elements"])

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_FORMS, "POST", payload, ctx=ctx
        )
        logger.debug("clone_form output: %s", output)

        if isinstance(output, str):
            return vo.CreateFormResponseVO(error=output or "Facing internal error")
        if isinstance(output, dict) and output.get("error"):
            return vo.CreateFormResponseVO(
                error=output.get("error", "Facing internal error")
            )
        if isinstance(output, dict) and "Message" in output:
            return vo.CreateFormResponseVO(
                error=output.get("Description") or output.get("Message", "Request failed")
            )

        created = output if isinstance(output, dict) else {}
        created_id = created.get("_id") or created.get("id", "")
        created_name = created.get("name") or created.get("title", "")
        return vo.CreateFormResponseVO(
            form=vo.FormVO(id=created_id, name=created_name),
            host=_base_host(),
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("clone_form error: %s", e)
        return vo.CreateFormResponseVO(error="Facing internal error")


@mcp.tool()
async def update_form(
    form_id: str,
    form: vo.UpdateFormVO,
    ctx: Context | None = None,
) -> vo.UpdateFormResponseVO:
    """
    Update an existing form.

    Args:
        form_id: Form ID to update.
        form: Update payload with:
            - name (str): Form name (required). Keep form name same as form title.
            - title (Optional[str]): Form title; when omitted, kept same as name.
            - isQuiz (Optional[bool]): Whether the form is a quiz (default False).
            - totalPoints (Optional[int]): Total points (default 0).
            - elements (Optional[list[FormElementVO]]): Form elements (questions/widgets). Each element has:
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
            - tags (Optional[list[FormTagsItemVO]]): Tags for the form. Each item has:
                - index (int): Tag index.
                - key (str): Tag key.
                - primary (bool): Whether this tag is primary.
                - values (list[str]): Tag values (e.g. ["asdf"]).

    Returns:
        - form (Optional[FormVO]): Updated form with id and name (from request; API returns no body).
        - host (Optional[str]): Platform host URL for building UI links.
        - error (Optional[str]): Error message if update failed.
    """
    assigned_state = await is_form_assigned(form_id, ctx)
    if isinstance(assigned_state, str):
        return vo.UpdateFormResponseVO(error=assigned_state)
    if assigned_state is True:
        return vo.UpdateFormResponseVO(
            error="This form is already assigned and cannot be edited."
        )
    return await update_form_impl(form_id, form, ctx)


@mcp.tool()
async def update_form_configuration(
    form_id: str,
    config: vo.FormConfigurationVO,
    ctx: Context | None = None,
) -> vo.UpdateFormConfigurationResponseVO:
    """
    Update a form's UI-only configuration (display/styles).

    Args:
        form_id: Form ID to update.
        config: UI configuration payload to save under form `configuration`.
            - config.styles.typography.fontColor: must be the `cssVar` from the colors
              configuration options (e.g. "--color-destructive-400"), not the hex `value`.

    Returns:
        - form (Optional[FormVO]): Updated form id/name.
        - configuration (Optional[FormConfigurationVO]): Saved configuration.
        - message (Optional[str]): Success message.
        - error (Optional[str]): Error message if update failed.
    """
    try:
        logger.info("update_form_configuration: form_id=%s", form_id)

        raw = await fetch_form_raw(form_id, ctx)
        if isinstance(raw, str):
            return vo.UpdateFormConfigurationResponseVO(error=raw)
        if not isinstance(raw, dict):
            return vo.UpdateFormConfigurationResponseVO(error="Invalid form response")

        elements = elements_from_raw(raw.get("elements"))
        if elements is None:
            elements = []
        tags = parse_form_tags_from_raw(raw.get("tags"))

        uf = vo.UpdateFormVO(
            name=raw.get("name", "") or "",
            title=raw.get("title"),
            isQuiz=raw.get("isQuiz", False),
            totalPoints=raw.get("totalPoints", 0),
            elements=elements,
            type=raw.get("type", "") or "",
            tags=tags,
            configuration=config,
        )

        updated = await update_form_impl(form_id, uf, ctx=ctx)
        if updated.error:
            return vo.UpdateFormConfigurationResponseVO(error=updated.error)

        return vo.UpdateFormConfigurationResponseVO(
            form=vo.FormVO(id=form_id, name=uf.name),
            configuration=config,
            message="Form configuration updated.",
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_form_configuration error: %s", e)
        return vo.UpdateFormConfigurationResponseVO(error="Facing internal error")


@mcp.tool()
async def list_form_categories(ctx: Context | None = None) -> vo.FormCategoryListVO:
    """
    List distinct form category names derived from the form tag key `form_category`.

    Uses a single GET /v1/forms (same as list_forms). Each form must include `tags` on the
    list response for its category to appear; otherwise that form is skipped for category discovery.

    Returns:
        - categories (Optional[list[str]]): Sorted unique category values from all forms' `form_category` tags.
        - error (Optional[str]): Error message if the request failed.
    """
    try:
        logger.info("list_form_categories")
        listed = await list_forms_impl(ctx=ctx)
        if listed.error:
            return vo.FormCategoryListVO(categories=[], error=listed.error)
        seen: set[str] = set()
        out: list[str] = []
        for f in listed.forms or []:
            for v in form_category_values(f.tags):
                if v not in seen:
                    seen.add(v)
                    out.append(v)
        out.sort()
        return vo.FormCategoryListVO(categories=out)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_form_categories error: %s", e)
        return vo.FormCategoryListVO(error="Facing internal error")


@mcp.tool()
async def fetch_form_category(
    category: str,
    ctx: Context | None = None,
) -> vo.FormCategoryMembersVO:
    """
    List forms that belong to a given category (exact match on a value in the `form_category` tag).

    Uses a single GET /v1/forms. Requires `tags` on each list item to detect membership.

    Args:
        category: Category name to match exactly against tag values.

    Returns:
        - category (str): The requested category.
        - forms (Optional[list[FormVO]]): Matching forms (id, name, tags when present).
        - error (Optional[str]): Error message if the request failed.
    """
    try:
        logger.info("fetch_form_category: category=%s", category)
        listed = await list_forms_impl(ctx=ctx)
        if listed.error:
            return vo.FormCategoryMembersVO(category=category, error=listed.error)
        matched: list[vo.FormVO] = []
        for f in listed.forms or []:
            vals = form_category_values(f.tags)
            if category in vals:
                matched.append(f)
        return vo.FormCategoryMembersVO(category=category, forms=matched)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_form_category error: %s", e)
        return vo.FormCategoryMembersVO(category=category, error="Facing internal error")


@mcp.tool()
async def set_form_category(
    form_name: str,
    form_category: str,
    ctx: Context | None = None,
) -> vo.SetFormCategoryResponseVO:
    """
    Set or update the `form_category` tag on a form by form name.

    Resolves the form via list_forms (GET /v1/forms), then loads the full definition with
    POST /v1/forms/fetch (assignId empty) and PUT /v1/forms/{id} so elements are preserved.

    Args:
        form_name: Exact form name to update.
        form_category: Category value to store (e.g. Compliance).

    Returns:
        - form (Optional[FormVO]): id, name, and merged tags on success.
        - message (Optional[str]): Short success message.
        - error (Optional[str]): Error message if resolution or update failed.
    """
    try:
        logger.info("set_form_category: form_name=%s category=%s", form_name, form_category)
        if not form_name.strip():
            return vo.SetFormCategoryResponseVO(error="form_name is required")
        if not form_category.strip():
            return vo.SetFormCategoryResponseVO(error="form_category is required")

        listed = await list_forms_impl(ctx=ctx)
        if listed.error:
            return vo.SetFormCategoryResponseVO(error=listed.error)
        matches = [f for f in (listed.forms or []) if (f.name or "") == form_name]
        if len(matches) == 0:
            return vo.SetFormCategoryResponseVO(
                error=f"No form found with name {form_name!r}."
            )
        if len(matches) > 1:
            return vo.SetFormCategoryResponseVO(
                error=f"Multiple forms match name {form_name!r}; resolve duplicates in the system."
            )
        form_id = matches[0].id or ""
        if not form_id:
            return vo.SetFormCategoryResponseVO(error="Form id missing for matched form.")
        assigned_state = await is_form_assigned(form_id, ctx)
        if isinstance(assigned_state, str):
            return vo.SetFormCategoryResponseVO(error=assigned_state)
        if assigned_state is True:
            return vo.SetFormCategoryResponseVO(
                error="This form is already assigned and cannot be edited."
            )

        raw = await fetch_form_raw(form_id, ctx)
        if isinstance(raw, str):
            return vo.SetFormCategoryResponseVO(error=raw)

        elements = elements_from_raw(raw.get("elements"))
        if elements is None:
            elements = []

        existing_tags = parse_form_tags_from_raw(raw.get("tags"))
        merged_tags = merge_form_category_tag(existing_tags, form_category.strip())

        uf = vo.UpdateFormVO(
            name=raw.get("name", "") or form_name,
            title=raw.get("title"),
            isQuiz=raw.get("isQuiz", False),
            totalPoints=raw.get("totalPoints", 0),
            elements=elements,
            type=raw.get("type", "") or "",
            tags=merged_tags,
            configuration=raw.get("configuration"),
        )

        updated = await update_form_impl(form_id, uf, ctx=ctx)
        if updated.error:
            return vo.SetFormCategoryResponseVO(error=updated.error)

        return vo.SetFormCategoryResponseVO(
            form=vo.FormVO(
                id=form_id,
                name=uf.name or "",
                tags=merged_tags,
            ),
            message="Form category updated.",
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("set_form_category error: %s", e)
        return vo.SetFormCategoryResponseVO(error="Facing internal error")


@mcp.tool()
async def list_dynamic_options(ctx: Context | None = None) -> vo.DynamicOptionListVO:
    """
    List dynamic options. Returns only id, name, and status.
    Only includes dynamic option sets with status active.

    Returns:
        - items (list[DynamicOptionVO]): Each item has id, name, status.
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

        items: list[vo.DynamicOptionVO] = []
        for item in items_raw:
            if not isinstance(item, dict):
                continue
            status = item.get("status")
            if not is_dynamic_option_active(status):
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
        if not is_dynamic_option_active(status):
            return vo.DynamicOptionDetailResponseVO(
                error="Dynamic option is not active; only active dynamic option sets can be used."
            )

        options_raw = output.get("options") or []
        options_list: list[vo.FormElementOptionVO] = []
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
        - items (list[AssignedFormVO]): Each item has: id (form assignment id), formID (unique form id),
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

        items: list[vo.AssignedFormVO] = []
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
        elements_list: list[vo.FormElementVO] = []
        if isinstance(elements_raw, list):
            for elem in elements_raw:
                if isinstance(elem, dict):
                    try:
                        # `FormElementVO.id` is sourced from the API's `_id`.
                        elements_list.append(vo.FormElementVO(**elem))
                    except Exception:
                        pass

        tags_list = parse_form_tags_from_raw(output.get("tags"))

        form_detail = vo.FormDetailVO(
            id=output.get("_id", ""),
            name=output.get("name", ""),
            title=output.get("title", ""),
            isQuiz=output.get("isQuiz", False),
            totalPoints=output.get("totalPoints", 0),
            type=output.get("type", ""),
            tags=tags_list,
            configuration=output.get("configuration"),
            elements=elements_list,
        )
        return vo.FormDetailResponseVO(form=form_detail, host=_base_host())
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
    assign_id: str,
    form_response_id: str,
    form_responses: dict[str, Any],
    ctx: Context | None = None,
) -> vo.SaveFormResponsesResponseVO:
    """
    Save the state of the form. Sends element answers for the given form response.
    Call this to persist answers before submitting.

    Args:
        form_id: The form id.
        assign_id: The form assignment id.
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
            "save_form_responses: form_id=%s, assign_id=%s, form_response_id=%s",
            form_id,
            assign_id,
            form_response_id,
        )

        url = f"{constants.URL_FORMS}/{form_id}/responses/{form_response_id}/elements"
        payload = {
            "assignId": assign_id,
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
        return vo.SaveFormResponsesResponseVO(success=True, host=_base_host())
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


@mcp.tool()
async def list_user_blocks(
    ctx: Context | None = None,
) -> list[vo.UserBlockVO] | str:
    """
    List active user blocks/groups.
    Returns:
        - List of items with:
          - userBlockName
          - userBlockDesc
          - id
          - users (list of user email ids)
        - str on error
    """
    try:
        logger.info("list_user_blocks")

        payload = {"isStatusToBeIncluded": True, "state": "active"}
        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_USER_BLOCKS, "GET", payload, ctx=ctx
        )
        logger.debug("list_user_blocks output: %s", output)

        if isinstance(output, str):
            logger.error("list_user_blocks error: %s", output)
            return output or "Facing internal error"

        if not isinstance(output, dict):
            return "Invalid response"

        if output.get("error"):
            return output.get("error", "Facing internal error")
        if "Message" in output:
            return output.get("Description") or output.get("Message", "Request failed")

        items_raw = output.get("items", [])
        if not isinstance(items_raw, list):
            items_raw = []

        result: list[vo.UserBlockVO] = []
        for item in items_raw:
            if not isinstance(item, dict):
                continue

            metadata = item.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}

            status = item.get("status", {})
            if not isinstance(status, dict):
                status = {}

            matching_users = status.get("matchingUsers", [])
            if not isinstance(matching_users, list):
                matching_users = []

            result.append(
                vo.UserBlockVO(
                    userBlockName=metadata.get("name", "") or "",
                    userBlockDesc=metadata.get("description", "") or "",
                    id=item.get("id", "") or "",
                    users=[str(u) for u in matching_users if u is not None],
                )
            )

        return result
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_user_blocks error: %s", e)
        return "Facing internal error"


@mcp.tool()
async def search_users_by_email_ids(
    email_ids: list[str],
    ctx: Context | None = None,
) -> list[vo.UserSearchResultVO] | str:
    """
    Search users by email ids.
    Args:
        email_ids: List of email ids to search.

    Returns:
        - List of { id, username, emailId }
        - str on error
    """
    try:
        logger.info("search_users_by_email_ids")

        normalized_emails = [e.strip() for e in email_ids if isinstance(e, str) and e.strip()]
        if not normalized_emails:
            return []

        emails_csv = ",".join(normalized_emails)
        payload = {"include_user_mediums": True, "emails": emails_csv}

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_USERS_SEARCH_BY_EMAILS, "GET", payload, ctx=ctx
        )
        logger.debug("search_users_by_email_ids output: %s", output)

        if isinstance(output, str):
            logger.error("search_users_by_email_ids error: %s", output)
            return output or "Facing internal error"

        if not isinstance(output, dict):
            return "Invalid response"

        if output.get("error"):
            return output.get("error", "Facing internal error")
        if "Message" in output:
            return output.get("Description") or output.get("Message", "Request failed")

        items_raw = output.get("items", [])
        if not isinstance(items_raw, list):
            items_raw = []

        result: list[vo.UserSearchResultVO] = []
        for item in items_raw:
            if not isinstance(item, dict):
                continue

            result.append(
                vo.UserSearchResultVO(
                    id=item.get("ID", "") or item.get("id", "") or "",
                    username=item.get("username", "") or "",
                    emailId=item.get("emailid", "") or item.get("emailId", "") or "",
                )
            )

        return result
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("search_users_by_email_ids error: %s", e)
        return "Facing internal error"


@mcp.tool()
async def validate_user_ids(
    user_identifiers: list[str],
    ctx: Context | None = None,
) -> vo.ValidateUserIdentifiersResponseVO:
    """
    Validate user identifiers before assigning a form (step 3).

    Args:
        user_identifiers: User emails or identifiers to validate.
        ctx: Optional request context.

    Returns:
        - validUserIds (list[str]): Resolved valid user IDs.
        - inValidUserIdentifiers (list[str]): Identifiers that did not resolve.
        - errorMsg (str): Optional backend validation message.
        - error (Optional[str]): Error message if validation failed.
    """
    try:
        logger.info("validate_user_ids")

        cleaned = [u.strip() for u in user_identifiers if isinstance(u, str) and u.strip()]
        payload = {"userIdentifiers": cleaned}

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_USERS_CREATE_IDENTIFIERS, "POST", payload, ctx=ctx
        )
        logger.debug("validate_user_ids output: %s", output)

        if isinstance(output, str):
            return vo.ValidateUserIdentifiersResponseVO(error=output or "Facing internal error")

        if not isinstance(output, dict):
            return vo.ValidateUserIdentifiersResponseVO(error="Invalid response")

        if output.get("error"):
            return vo.ValidateUserIdentifiersResponseVO(
                validUserIds=output.get("validUserIds", []),
                inValidUserIdentifiers=output.get("inValidUserIdentifiers", []),
                errorMsg=output.get("errorMsg", ""),
                error=output.get("error", "Facing internal error"),
            )

        if "Message" in output:
            return vo.ValidateUserIdentifiersResponseVO(
                error=output.get("Description") or output.get("Message", "Request failed"),
                validUserIds=output.get("validUserIds", []),
                inValidUserIdentifiers=output.get("inValidUserIdentifiers", []),
                errorMsg=output.get("errorMsg", ""),
            )

        valid_user_ids = output.get("validUserIds") or []
        invalid_user_ids = output.get("inValidUserIdentifiers") or output.get("invalidUserIdentifiers") or []
        error_msg = output.get("errorMsg") or ""

        if not isinstance(valid_user_ids, list):
            valid_user_ids = []
        if not isinstance(invalid_user_ids, list):
            invalid_user_ids = []

        return vo.ValidateUserIdentifiersResponseVO(
            validUserIds=[str(x) for x in valid_user_ids if x is not None],
            inValidUserIdentifiers=[str(x) for x in invalid_user_ids if x is not None],
            errorMsg=str(error_msg) if error_msg is not None else "",
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("validate_user_ids error: %s", e)
        return vo.ValidateUserIdentifiersResponseVO(error="Facing internal error")


@mcp.tool()
async def assign_form(
    user_ids: list[str],
    form_id: str,
    due_date: str,
    purpose: str,
    assign_tags: Optional[list[vo.FormTagVO] | str] = None,
    ctx: Context | None = None,
) -> vo.AssignFormResponseVO:
    """
    Assign a form to users (step 4).

    Args:
        user_ids: User IDs to assign.
        form_id: Target form ID.
        due_date: Assignment due date string.
        purpose: Assignment purpose text.
        assign_tags: Optional assignment tags. Ask the user explicitly whether they want to add tags while assigning.
            Can be either a list of tag objects or a JSON string encoding that list. If there are more than one tag ask for primary tag.
            Each item should follow:
            - key (str): tag name.
            - primary (bool): at most one tag can be true.
            - values (list[str]): one or more values for that tag.
        ctx: Optional request context.

    Returns:
        - ids (List[str]): Created assignment IDs.
        - host (Optional[str]): Platform host URL for building UI links.
        - error (Optional[str]): Error message if assignment failed.
    """
    try:
        logger.info("assign_form: form_id=%s, users=%d", form_id, len(user_ids or []))

        normalized = normalize_assign_form_inputs(user_ids, due_date, purpose)
        cleaned_user_ids, due_date_clean, purpose_clean = normalized
        if cleaned_user_ids is None:
            return vo.AssignFormResponseVO(error=purpose_clean or "Facing internal error")
        elements_raw = await fetch_form_elements_for_assignment(form_id, ctx=ctx)
        if isinstance(elements_raw, str):
            return vo.AssignFormResponseVO(error=elements_raw or "Facing internal error")

        element_ids = collect_assignable_element_ids(elements_raw)

        payload = {
            "userID": cleaned_user_ids,
            "formID": form_id,
            "dueDate": due_date_clean,
            "shouldPreserveResponse": True,
            "elementID": element_ids,
            "freshAssignment": True,
            "purpose": purpose_clean,
            "enableSelfDelegate": True,
        }
        parsed_assign_tags: list[vo.FormTagVO] = []
        if isinstance(assign_tags, str):
            try:
                parsed_raw = json.loads(assign_tags)
            except Exception:
                return vo.AssignFormResponseVO(error="assign_tags must be valid JSON")
            if not isinstance(parsed_raw, list):
                return vo.AssignFormResponseVO(error="assign_tags must be a list")
            try:
                parsed_assign_tags = [vo.FormTagVO.model_validate(t) for t in parsed_raw]
            except Exception:
                return vo.AssignFormResponseVO(
                    error="assign_tags items must have key, primary, and values"
                )
        elif assign_tags:
            parsed_assign_tags = assign_tags

        if parsed_assign_tags:
            primary_count = sum(1 for tag in parsed_assign_tags if bool(tag.primary))
            if primary_count > 1:
                return vo.AssignFormResponseVO(
                    error="Only one assign tag can have primary=true"
                )
            payload["tags"] = [
                tag.model_dump(exclude_none=True) for tag in parsed_assign_tags
            ]

        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_USER_FORMS_ASSIGN, "POST", payload, ctx=ctx
        )
        logger.debug("assign_form output: %s", output)

        ids, err = extract_assign_form_ids_and_error(output)
        return vo.AssignFormResponseVO(ids=ids, host=_base_host(), error=err)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("assign_form error: %s", e)
        return vo.AssignFormResponseVO(error="Facing internal error")


