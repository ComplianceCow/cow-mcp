from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import datetime
from typing import Any, Dict, List, get_type_hints


def _to_dict(obj: Any) -> Any:
    """Recursively turn dataclasses/lists/primitives into plain dicts/lists."""
    if is_dataclass(obj):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def _from_dict(cls: type, data: Any) -> Any:
    """Recursively reconstruct dataclasses from plain dicts/lists."""
    if data is None:
        return data
    if cls == datetime:
        return datetime.fromisoformat(data)
    if getattr(cls, "__origin__", None) == list:
        element_type = cls.__args__[0]
        return [_from_dict(element_type, item) for item in data]
    if getattr(cls, "__origin__", None) == dict:
        return data  # dict[str, Any] -> already plain dict
    if is_dataclass(cls):
        kwargs = {}
        type_hints = get_type_hints(cls)
        for f in fields(cls):
            value = data.get(f.name, f.default)
            kwargs[f.name] = _from_dict(type_hints[f.name], value)
        return cls(**kwargs)
    # primitive type
    return data


@dataclass
class TaskInputVO:
    name: str
    description: str
    dataType: str
    defaultValue: str
    showField: bool
    required: bool
    allowUserValues: bool = True
    allowedValues: List[Any] = None
    templateFile: str = ""
    format: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskInputVO":
        return _from_dict(cls, data)


@dataclass
class TaskOutputVO:
    name: str
    description: str
    dataType: str

    def to_dict(self) -> Dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskOutputVO":
        return _from_dict(cls, data)


@dataclass
class TaskVO:
    name: str
    displayName: str
    version: str
    description: str
    type: str
    tags: List[str]
    applicationType: str
    inputs: List[TaskInputVO]
    outputs: List[TaskOutputVO]
    appTags: Dict[str, List[str]]
    readmeData: str

    def to_dict(self) -> Dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskVO":
        return _from_dict(cls, data)
