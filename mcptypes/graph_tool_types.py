

from dataclasses import dataclass
from typing import List,Any, Optional

@dataclass
class UniqueNodeDataVO:
    node_names: Optional[list[str]] = None
    unique_property_values: Optional[list] = None
    neo4j_schema: Optional[str] = ""
    error: Optional[str]  = None
    
@dataclass
class CypherQueryVO:
    result: Optional[Any] = None
    error: Optional[str] = ""

