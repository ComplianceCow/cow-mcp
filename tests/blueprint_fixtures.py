"""Locates the real PolicyCow Jira blueprint, for the tests that check the blueprint tools against it."""
import glob
import os

import yaml

FOLDER = os.path.join("catalog", "globalcatalog", "workflowyamls", "JiraGenericWorkflow_PlaybookVersion")
HINT = "set BLUEPRINT_FIXTURE_DIR to the JiraGenericWorkflow_PlaybookVersion folder of a PolicyCow checkout"


def jira_dir() -> str | None:
    """BLUEPRINT_FIXTURE_DIR, else a PolicyCow checkout next to this repository, else None."""
    sibling = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "PolicyCow", FOLDER)
    path = os.environ.get("BLUEPRINT_FIXTURE_DIR") or sibling
    return path if glob.glob(os.path.join(path, "*.yaml")) else None


def load_jira(path: str) -> tuple[dict, dict[str, dict]]:
    """The folder's definition (-Config.yaml) and the workflows it starts (-Subworkflow.yaml, by file name), as PolicyCow's workflows call returns them."""
    config, subworkflows = None, {}
    for file in sorted(glob.glob(os.path.join(path, "*.yaml"))):
        with open(file) as handle:
            doc = yaml.safe_load(handle)
        if file.endswith("-Config.yaml"):
            config = doc
        elif file.endswith("-Subworkflow.yaml"):
            subworkflows[os.path.basename(file)[: -len(".yaml")]] = doc
    return config, subworkflows
