import traceback
from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings
from typing import List
from typing import Tuple
import os
import json
import base64
import signal
import sys
from random import randint
import asyncio

from mcp.server.auth.provider import OAuthAuthorizationServerProvider,AccessTokenT,AccessToken
from mcp.server.auth.middleware.auth_context import get_access_token

from constants import constants
from utils import utils
from utils.debug import logger
from utils.auth import CCowOAuthProvider


mcp = FastMCP("ComplianceCow")
