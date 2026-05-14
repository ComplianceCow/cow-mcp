from __future__ import annotations

import copy
import traceback
from typing import Any, List, Optional

from fastmcp import Context

from constants import constants
from mcptypes import forms_tool_types as vo
from utils import utils
from utils.debug import logger


def _base_host() -> str:
    raw = getattr(constants, "host", "") or ""
    return raw.rstrip("/api") if isinstance(raw, str) else raw


def normalize_matrix_options(elements: List[Any]) -> None:
    """Sync all Matrix child rows to the first row's options. Mutates in place, recurses into nested containers."""
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
            normalize_matrix_options(child_elements)


FORM_CATEGORY_TAG_KEY = "form_category"


def parse_form_tags_from_raw(tags_raw: Any) -> Optional[list[vo.FormTagsItemVO]]:
    """Convert raw API tag dicts into typed FormTagsItemVO list. Returns None if input is not a list."""
    if not isinstance(tags_raw, list):
        return None
    tags_list: list[vo.FormTagsItemVO] = []
    for t in tags_raw:
        if isinstance(t, dict):
            idx = t.get("index")
            prim = t.get("primary")
            tags_list.append(
                vo.FormTagsItemVO(
                    key=t.get("key", ""),
                    values=t.get("values") if t.get("values") is not None else [],
                    index=idx if isinstance(idx, int) else None,
                    primary=prim if isinstance(prim, bool) else None,
                )
            )
    return tags_list if tags_list else None


def form_category_values(tags: Optional[list[vo.FormTagsItemVO]]) -> list[str]:
    """Extract category values from a form's tags by the `form_category` key."""
    if not tags:
        return []
    for t in tags:
        if (t.key or "") == FORM_CATEGORY_TAG_KEY and t.values:
            return list(t.values)
    return []


def merge_form_category_tag(
    existing: Optional[list[vo.FormTagsItemVO]], category_value: str
) -> list[vo.FormTagsItemVO]:
    """Upsert the `form_category` tag in a tags list. Creates the tag if it doesn't exist."""
    merged: list[vo.FormTagsItemVO] = []
    found = False
    if existing:
        for t in existing:
            if (t.key or "") == FORM_CATEGORY_TAG_KEY:
                merged.append(
                    vo.FormTagsItemVO(
                        key=FORM_CATEGORY_TAG_KEY,
                        values=[category_value],
                        index=t.index if t.index is not None else 0,
                        primary=t.primary if t.primary is not None else True,
                    )
                )
                found = True
            else:
                merged.append(t.model_copy())
    if not found:
        merged.append(
            vo.FormTagsItemVO(
                key=FORM_CATEGORY_TAG_KEY,
                values=[category_value],
                index=0,
                primary=True,
            )
        )
    return merged


def elements_from_raw(elements_raw: Any) -> Optional[list[vo.FormElementVO]]:
    """Convert raw API element dicts into typed FormElementVO list. Returns None if input is not a list."""
    if not isinstance(elements_raw, list):
        return None
    elements_list: list[vo.FormElementVO] = []
    for elem in elements_raw:
        if isinstance(elem, dict):
            try:
                elements_list.append(vo.FormElementVO(**elem))
            except Exception:
                pass
    return elements_list


async def fetch_form_raw(form_id: str, ctx: Context | None) -> dict | str:
    """Fetch a complete form as raw dict by form_id. Returns error string on failure."""
    payload = {"formId": form_id, "assignId": ""}
    output = await utils.make_API_call_to_CCow_and_get_response(
        constants.URL_FORMS_FETCH, "POST", payload, ctx=ctx
    )
    if isinstance(output, str):
        return output
    if isinstance(output, dict) and output.get("error"):
        return output.get("error", "Facing internal error")
    if isinstance(output, dict) and "Message" in output:
        return output.get("Description") or output.get("Message", "Request failed")
    if not isinstance(output, dict):
        return "Invalid response"
    return output


async def is_form_assigned(form_id: str, ctx: Context | None) -> bool | str:
    """Check whether a form is already assigned. Returns bool on success or an error string on failure."""
    url = f"{constants.URL_CHECK_FORM_ASSIGNED}/{form_id}"
    output = await utils.make_API_call_to_CCow_and_get_response(url, "GET", ctx=ctx)
    if isinstance(output, str):
        return output
    if isinstance(output, dict) and output.get("error"):
        return output.get("error", "Facing internal error")
    if isinstance(output, dict) and "Message" in output:
        return output.get("Description") or output.get("Message", "Request failed")
    if not isinstance(output, dict):
        return "Invalid response"
    return bool(output.get("isFormAssigned", False))


async def list_forms_impl(ctx: Context | None = None) -> vo.FormListVO:
    """Fetch all forms and return as FormListVO. Used by list, category, and search flows."""
    try:
        logger.info("list_forms: \n")

        output = await utils.make_API_call_to_CCow_and_get_response(constants.URL_FORMS, "GET", ctx=ctx)
        logger.debug("list_forms output: {}\n".format(output))
        if isinstance(output, str) or (isinstance(output, dict) and output.get("error")):
            logger.error("list_forms error: {}\n".format(output))
            return vo.FormListVO(error="Facing internal error")
        if not isinstance(output, list):
            logger.error("list_forms error: unexpected response shape\n")
            return vo.FormListVO(error="Facing internal error")

        forms: list[vo.FormVO] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            tags = parse_form_tags_from_raw(item.get("tags"))
            forms.append(
                vo.FormVO(
                    id=item.get("_id", "") or item.get("id", ""),
                    name=item.get("name", ""),
                    tags=tags,
                )
            )

        return vo.FormListVO(forms=forms)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("list_forms error: {}\n".format(e))
        return vo.FormListVO(error="Facing internal error")


async def update_form_impl(
    form_id: str,
    form: vo.UpdateFormVO,
    ctx: Context | None = None,
) -> vo.UpdateFormResponseVO:
    """Persist a form update by sending the serialized payload. Used by form update and category flows."""
    try:
        logger.info("update_form: form_id=%s", form_id)

        url = f"{constants.URL_FORMS}/{form_id}"
        payload = form.to_api_payload()
        if payload.get("elements"):
            normalize_matrix_options(payload["elements"])
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
            ),
            host=_base_host(),
        )
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("update_form error: %s", e)
        return vo.UpdateFormResponseVO(error="Facing internal error")


def is_dynamic_option_active(status) -> bool:
    """Check if a dynamic option set is active (True or "active")."""
    if status is True:
        return True
    if isinstance(status, str) and str(status).lower() == "active":
        return True
    return False


def collect_assignable_element_ids(elements: Any) -> list[str]:
    """Collect top-level element IDs, skipping Statement Blocks."""

    if not isinstance(elements, list):
        return []

    seen: set[str] = set()
    out: list[str] = []
    for elem in elements:
        if not isinstance(elem, dict):
            continue
        if (elem.get("type") or "") == "Statement Block":
            continue
        elem_id = elem.get("_id") or elem.get("id") or ""
        if elem_id and elem_id not in seen:
            out.append(str(elem_id))
            seen.add(elem_id)
    return out


async def fetch_form_elements_for_assignment(form_id: str, ctx: Context | None) -> list[Any] | str:
    """Fetch a form's raw elements list for building the assignment element ID set. Returns error string on failure."""
    try:
        payload = {"formId": form_id, "assignId": ""}
        output = await utils.make_API_call_to_CCow_and_get_response(
            constants.URL_FORMS_FETCH, "POST", payload, ctx=ctx
        )

        if isinstance(output, str):
            return output
        if isinstance(output, dict) and output.get("error"):
            return output.get("error", "Facing internal error")
        if isinstance(output, dict) and "Message" in output:
            return output.get("Description") or output.get("Message", "Request failed")
        if not isinstance(output, dict):
            return "Invalid response"

        elements_raw = output.get("elements") or []
        return elements_raw if isinstance(elements_raw, list) else []
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("fetch_form_elements_for_assignment error: %s", e)
        return "Facing internal error"


def normalize_assign_form_inputs(
    user_ids: list[str],
    due_date: str,
    purpose: str,
) -> tuple[list[str], str, str] | tuple[None, None, str]:
    """Validate and clean assign-form inputs. Returns (None, None, error) on validation failure."""
    cleaned_user_ids = [u.strip() for u in user_ids if isinstance(u, str) and u.strip()]
    if not cleaned_user_ids:
        return None, None, "No valid user IDs provided"

    due_date_clean = due_date.strip() if isinstance(due_date, str) else ""
    if not due_date_clean:
        return None, None, "due_date is required"

    purpose_clean = purpose.strip() if isinstance(purpose, str) else ""
    return cleaned_user_ids, due_date_clean, purpose_clean


def extract_assign_form_ids_and_error(output: Any) -> tuple[list[str], str]:
    """Parse created assignment IDs from the assign-form response. Returns (ids, error_string)."""
    if isinstance(output, str):
        return [], output or "Facing internal error"

    if not isinstance(output, dict):
        return [], "Invalid response"

    if output.get("error"):
        return [], output.get("error", "Facing internal error")

    if "Message" in output:
        return [], output.get("Description") or output.get("Message", "Request failed")

    ids = output.get("ids") or output.get("IDs") or output.get("ID") or []
    if not isinstance(ids, list):
        ids = []

    return [str(i) for i in ids if i is not None], ""
