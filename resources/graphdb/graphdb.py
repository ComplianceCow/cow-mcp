

import traceback
import json
import traceback
from typing import List
from typing import Tuple

from utils import utils
from utils.debug import logger
# from tools.mcpconfig import mcp
from mcpconfig.config import mcp
from constants import constants


# @mcp.resource("graph_schema://{nodeNames}")
@mcp.resource("graphschema://node")
async def get_graph_schema_relationship() -> dict | str:
    """
    Retrieve the complete graph database schema and relationship structure for ComplianceCow.
    
    This resource provides essential information about the Neo4j compliance database structure,
    including node types, relationships, and hierarchical patterns.
    
    CRITICAL INFORMATION FOR QUERY CONSTRUCTION:
    
    1. CONTROL HIERARCHY ANALYSIS:
       Before querying controls, ALWAYS determine the hierarchy depth using:
       
       MATCH (root:Control)
       WHERE NOT ()-[:HAS_CHILD]->(root)
       WITH root
       MATCH path = (root)-[:HAS_CHILD*]->(leaf)
       WHERE NOT (leaf)-[:HAS_CHILD]->()
       RETURN root.id, leaf.id, length(path) as depth
       ORDER BY depth DESC
       LIMIT 1
    
    2. RECURSIVE QUERY PATTERNS:
       - Use [HAS_CHILD*] for variable-length traversal
       - Use [HAS_CHILD*1..n] to limit depth
       - Example: MATCH (parent)-[:HAS_CHILD*]->(descendant)
    
    3. EVIDENCE LOCATION:
       Evidence is ONLY available on leaf controls (controls with no children):
       MATCH (control:Control)-[:HAS_EVIDENCE]->(evidence:Evidence)
       WHERE NOT (control)-[:HAS_CHILD]->()
    
    4. APOC PROCEDURES (if available):
       - apoc.path.subgraphAll() for complex traversals
       - apoc.path.expandConfig() for conditional expansion

    5. CONTROL STATUS INFORMATION:
       - status: ["Completed", "In Progress", "Pending", "Unassigned"]
       - complianceStatus: ["COMPLIANT", "NON_COMPLIANT", "NOT_DETERMINED"]
       - Overdue controls: due_date < current_date & status is [In process, Pending] (manual check required) 
    
    6. PERFORMANCE CONSIDERATIONS:
       - For large datasets, use LIMIT clauses
       - Consider using aggregation functions for summaries
       - Use WHERE clauses to filter early in the query

    7. INTELLIGENT QUERY REFINEMENT FOR LARGE DATASETS:
       When queries return large datasets, implement smart refinement:
       
       a) BROAD QUERY DETECTION:
          - Detect queries with vague parameters like "all", "list everything", empty values
          - Check dataset size before returning overwhelming results
          - Use summary queries to provide meaningful overviews first
       
       b) REFINEMENT SUGGESTION CATEGORIES:
          
          For CONTROLS - suggest filtering by:
          - Status: pending, completed, in progress, unassigned, overdue
          - Compliance: compliant, non-compliant, needs determination
          - Priority: high, medium, low priority controls
          - Time: due dates, recent updates, specific quarters
       
       c) USER GUIDANCE APPROACH:
          - Provide summary statistics instead of overwhelming lists
          - Offer specific example queries users can immediately try
          - Use clear, actionable language with practical suggestions
          - Format responses with visual hierarchy for easy scanning
    
    8. SUMMARY QUERY APPROACH FOR LARGE DATASETS:
       Instead of returning overwhelming full record sets, use aggregation patterns:
       - Count totals by status, compliance state, framework, assignment
       - Provide breakdown statistics rather than individual records
       - Show distribution patterns and key metrics
       - Offer sample records alongside summary statistics
       - Guide users toward more specific queries based on summary insights
   
    
    Schema Information:
    - Node types and their properties
    - Relationship types and directions
    - Constraints and indexes
    - Hierarchy depth patterns
    
    Use this schema information to construct accurate Cypher queries that respect
    the hierarchical nature of compliance controls.
    
    Returns:
        dict: Complete database schema with structural patterns and query guidelines
        str: Error message if schema retrieval fails
    """
    
    try:
        logger.info("\nget_schema_form_control: \n")
        output=await utils.make_API_call_to_CCow({},constants.URL_RETRIEVE_GRAPH_SCHEMA_RELATIONSHIP)
        logger.debug("output: {}\n".format(output))
        enhanced_guidance = {
            "control_status_values": {
                "status": ["Completed", "In Progress", "Pending", "Unassigned"],
                "complianceStatus": ["COMPLIANT", "NON_COMPLIANT", "NOT_DETERMINED"],
                "priority(case insensitive)": ["Low", "Medium", "High"],
                "overdue_logic": "Controls are overdue when due_date < current_date is [In progress, Pending] (requires manual date comparison)"
            },
            "query_best_practices": {
                "large_datasets": "Use LIMIT clauses and aggregation functions for performance",
                "hierarchy_traversal": "Always determine depth before complex recursive queries",
                "evidence_queries": "Evidence only exists on leaf controls - filter accordingly",
                "performance_tips": [
                    "Use WHERE clauses early in queries for filtering",
                    "Prefer specific relationship patterns over generic traversal",
                    "Use PROFILE or EXPLAIN for query optimization"
                ]
            },
            "common_patterns": {
                "find_roots": "MATCH (c:Control) WHERE NOT ()-[:HAS_CHILD]->(c)",
                "find_leaves": "MATCH (c:Control) WHERE NOT (c)-[:HAS_CHILD]->()",
                "full_hierarchy": "MATCH (root)-[:HAS_CHILD*]->(descendant)",
                "evidence_with_controls": "MATCH (c:Control)-[:HAS_EVIDENCE]->(e:Evidence) WHERE NOT (c)-[:HAS_CHILD]->()"
            },
            "large_dataset_handling": {
                "description": "Strategies for managing overwhelming query results",
                "detection_approach": "Identify broad queries through parameter analysis and keyword detection", 
                "response_strategy": "Provide summary statistics and guided refinement suggestions",
                "user_experience_goals": [
                    "Prevent information overload",
                    "Guide users to actionable insights", 
                    "Offer immediate value through summaries",
                    "Enable progressive query refinement"
                ]
            },
            "refinement_suggestions": {
                "controls": {
                    "status_based": "Filter by completion state, progress status, assignment status, or overdue conditions",
                    "compliance_status_based": "Focus on compliance outcomes", 
                    "framework_based": "Narrow by specific regulatory frameworks or compliance standards",
                    "priority_based": "Filter by control prioriy",
                    "time_period_based": "control on specific date, date range, or review period"
                },
            },
            "user_guidance_approach": {
                "summary_first": "Always provide high-level statistics and patterns before detailed results",
                "contextual_suggestions": "Offer refinement options specific to the data and user context",
                "progressive_refinement": "Enable users to iteratively narrow their focus through guided questions",
                "actionable_examples": "Provide concrete, ready-to-use query phrases that users can immediately apply",
                "visual_formatting": "Use clear structure, emojis, and hierarchy to make responses scannable"
            }
        }

        # return {"Important": "If you need to check control, find try to find how much nested level of controls available then query according", "output": output}
        return {
         "output": output,
         "guidance": enhanced_guidance
         }
    except Exception as e:
        logger.error("get_schema_form_control error: {}\n".format(e))
        return "Facing internal error"
