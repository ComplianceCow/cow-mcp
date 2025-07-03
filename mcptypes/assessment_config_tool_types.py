

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class CategoryVO:
    id: Optional[str]
    name: Optional[str]

@dataclass
class CategoryListVO:
    categories: Optional[List[CategoryVO]] = None
    error: Optional[str] = ""


@dataclass
class AssessmentVO:
    id: Optional[str]
    name: Optional[str]
    category_name: Optional[str]

@dataclass
class AssessmentListVO:
    assessments: Optional[List[AssessmentVO]] = None
    error: Optional[str] = ""