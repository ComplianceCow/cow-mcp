from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from typing import Any, List, Literal, Optional

FormElementType = Literal[
    "",
    "Block",
    "Statement Block",
    "Short Text",
    "Paragraph",
    "Radio Button",
    "Checkbox",
    "Dropdown",
    "File Upload",
    "Matrix",
    "Date",
    "Date Range"
]


class FormElementOptionVO(BaseModel):
    value: Optional[str] = "" 
    points: Optional[int] = 0
    label: Optional[str] = ""
    defaultChecked: Optional[bool] = False
    nextInSequence: Optional[int] = None

    model_config = {"extra": "ignore"}


class FormElementVO(BaseModel):
    id: Optional[str] = Field(default="", alias="_id")
    type: FormElementType = ""
    sequence: Optional[int] = 0
    isWriteInEnabled: Optional[bool] = False
    title: Optional[str] = ""
    points: Optional[int] = 0
    footer: Optional[str] = ""
    tags: Optional[List[Any]] = None
    elements: Optional[List[FormElementVO]] = None
    value: Optional[str] = ""
    dynamicOptionsId: Optional[str] = ""
    videoUrl: Optional[str] = ""
    options: Optional[List[FormElementOptionVO]] = None
    nextInSequence: Optional[int] = None
    isRequired: Optional[bool] = False

    model_config = {"extra": "ignore"}


FormElementVO.model_rebuild()


class FormVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = ""

    model_config = {
        "extra": "ignore"
    }


class FormListVO(BaseModel):
    forms: Optional[List[FormVO]] = None
    error: Optional[str] = ""


class FormTagVO(BaseModel):
    index: Optional[int] = 0
    key: Optional[str] = ""
    primary: Optional[bool] = False
    values: Optional[List[str]] = None

    model_config = {"extra": "ignore"}


class FormTagsItemVO(BaseModel):
    key: Optional[str] = ""
    values: Optional[List[str]] = None

    model_config = {"extra": "ignore"}


class CreateFormVO(BaseModel):
    name: str  # required; keep same as form title
    title: Optional[str] = None
    elements: Optional[List[Any]] = None
    type: Optional[str] = ""
    tag: Optional[List[FormTagVO]] = None
    isQuiz: Optional[bool] = False
    totalPoints: Optional[int] = 0
    # scoringLogic: Optional[List[Any]] = None

    model_config = {"extra": "ignore"}

    @model_validator(mode="after")
    def sync_title_with_name(self) -> "CreateFormVO":
        """Keep form title same as form name when title is not set."""
        if self.title is None or self.title == "":
            object.__setattr__(self, "title", self.name)
        return self

    def to_payload(self) -> dict:
        """Build API payload with defaults for missing fields."""
        tag_payload = (
            [
                {
                    "index": t.index or 0,
                    "key": t.key or "",
                    "primary": t.primary if t.primary is not None else False,
                    "values": t.values if t.values is not None else [],
                }
                for t in self.tag
            ]
            if self.tag is not None
            else []
        )
        title = self.title if self.title else self.name
        elements_payload: list[dict[str, Any]] = []
        if self.elements is not None:
            for e in self.elements:
                if isinstance(e, FormElementVO):
                    elements_payload.append(
                        e.model_dump(exclude_none=False, exclude={"id"})
                    )
                elif isinstance(e, dict):
                    elements_payload.append(
                        FormElementVO(**e).model_dump(
                            exclude_none=False, exclude={"id"}
                        )
                    )
                else:
                    raise TypeError(
                        "Invalid element type in CreateFormVO.elements: "
                        f"{type(e).__name__}"
                    )
        return {
            "name": self.name,
            "title": title,
            "elements": elements_payload,
            "type": self.type or "",
            "tag": tag_payload,
            "isQuiz": self.isQuiz if self.isQuiz is not None else False,
            "totalPoints": self.totalPoints if self.totalPoints is not None else 0,
            "scoringLogic": [],
        }


class CreateFormResponseVO(BaseModel):
    form: Optional[FormVO] = None
    error: Optional[str] = ""


class UpdateFormVO(BaseModel):
    name: str  # required; keep same as form title
    title: Optional[str] = None
    isQuiz: Optional[bool] = False
    totalPoints: Optional[int] = 0
    elements: Optional[List[FormElementVO]] = None
    type: Optional[str] = ""
    tags: Optional[List[FormTagsItemVO]] = None

    model_config = {"extra": "ignore"}

    def to_payload(self) -> dict:
        """Build API payload (no _id). Serializes elements and tags."""
        elements_payload: list[dict[str, Any]] = []
        if self.elements is not None:
            for e in self.elements:
                if isinstance(e, FormElementVO):
                    elements_payload.append(
                        e.model_dump(exclude_none=False, exclude={"id"})
                    )
                elif isinstance(e, dict):
                    elements_payload.append(
                        FormElementVO(**e).model_dump(
                            exclude_none=False, exclude={"id"}
                        )
                    )
                else:
                    raise TypeError(
                        "Invalid element type in UpdateFormVO.elements: "
                        f"{type(e).__name__}"
                    )
        tags_payload = (
            [{"key": t.key or "", "values": t.values if t.values is not None else []} for t in self.tags]
            if self.tags is not None
            else None
        )
        title = self.title if self.title else self.name
        return {
            "name": self.name,
            "title": title,
            "isQuiz": self.isQuiz if self.isQuiz is not None else False,
            "totalPoints": self.totalPoints if self.totalPoints is not None else 0,
            "elements": elements_payload,
            "type": self.type or "",
            "tags": tags_payload,
        }


class UpdateFormResponseVO(BaseModel):
    form: Optional[FormVO] = None
    error: Optional[str] = ""


class DynamicOptionVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = ""
    status: Optional[Any] = None  # True or "active" means active

    model_config = {"extra": "ignore"}


class DynamicOptionListVO(BaseModel):
    items: Optional[List[DynamicOptionVO]] = None
    error: Optional[str] = ""


class DynamicOptionDetailVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = ""
    status: Optional[Any] = None
    options: Optional[List[FormElementOptionVO]] = None

    model_config = {"extra": "ignore"}


class DynamicOptionDetailResponseVO(BaseModel):
    dynamic_option: Optional[DynamicOptionDetailVO] = None
    error: Optional[str] = ""


class AssignedFormVO(BaseModel):
    id: Optional[str] = ""  # form assignment id
    formID: Optional[str] = ""
    formName: Optional[str] = ""
    dueDate: Optional[str] = ""
    displayableDueDate: Optional[str] = ""
    displayableAssignedOn: Optional[str] = ""
    assignedBy: Optional[str] = ""
    purpose: Optional[str] = ""
    createdAt: Optional[str] = ""
    tags: Optional[Any] = None
    elements: Optional[List[str]] = None 

    model_config = {"extra": "ignore"}


class AssignedFormListVO(BaseModel):
    items: Optional[List[AssignedFormVO]] = None
    error: Optional[str] = ""


class FormDetailVO(BaseModel):
    id: Optional[str] = ""
    name: Optional[str] = ""
    title: Optional[str] = ""
    isQuiz: Optional[bool] = False
    totalPoints: Optional[int] = 0
    elements: Optional[List[FormElementVO]] = None
    type: Optional[str] = ""
    tags: Optional[List[FormTagsItemVO]] = None

    model_config = {"extra": "ignore"}


class FormDetailResponseVO(BaseModel):
    form: Optional[FormDetailVO] = None
    error: Optional[str] = ""


class FormProgressVO(BaseModel):
    items: Optional[dict[str, Any]] = None
    totalQuestions: Optional[int] = None
    formResponseId: Optional[str] = ""
    totalScore: Optional[int] = None
    totalPoints: Optional[int] = None
    status: Optional[str] = ""

    model_config = {"extra": "ignore"}


class FormProgressResponseVO(BaseModel):
    progress: Optional[FormProgressVO] = None
    error: Optional[str] = ""


class CreateFormResponsePayloadVO(BaseModel):
    formId: str
    userId: str
    assignId: str

    model_config = {"extra": "ignore"}


class CreateFormResponseResultVO(BaseModel):
    id: Optional[str] = ""

    model_config = {"extra": "ignore"}


class CreateFormResponseResponseVO(BaseModel):
    form_response: Optional[CreateFormResponseResultVO] = None
    error: Optional[str] = ""


class CurrentUserVO(BaseModel):
    ID: Optional[str] = ""
    emailid: Optional[str] = ""
    username: Optional[str] = ""

    model_config = {"extra": "ignore"}


class CurrentUserResponseVO(BaseModel):
    user: Optional[CurrentUserVO] = None
    error: Optional[str] = ""


class SaveFormResponsesPayloadVO(BaseModel):
    formResponseId: str
    formResponses: dict[str, Any]  # element_id -> str | {toDate, fromDate} | list[{bucketName, filePath, fileName, fileHash}]

    model_config = {"extra": "ignore"}


class SaveFormResponsesResponseVO(BaseModel):
    success: Optional[bool] = None
    error: Optional[str] = ""


class SubmitUserFormPayloadVO(BaseModel):

    userID: str
    myformID: str  # assign_id
    formID: str

    model_config = {"extra": "ignore"}


class SubmitUserFormResponseVO(BaseModel):
    success: Optional[bool] = None
    error: Optional[str] = ""


class FormElementFileUploadResultVO(BaseModel):
    bucketName: Optional[str] = ""
    filePath: Optional[str] = ""
    fileName: Optional[str] = ""
    fileHash: Optional[str] = ""

    model_config = {"extra": "ignore"}


class FormElementFileUploadResponseVO(BaseModel):
    files: Optional[List[FormElementFileUploadResultVO]] = None
    error: Optional[str] = ""