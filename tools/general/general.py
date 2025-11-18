from mcpconfig.config import mcp
import mimetypes
from pathlib import Path
from urllib.parse import urlparse
from utils.debug import logger
import os
from utils import utils
from constants import constants
import re
import time
from typing import Any
import traceback
from fastmcp import Context

mcp_tools_to_be_included = os.getenv("MCP_TOOLS_TO_BE_INCLUDED", "").lower().strip()


@mcp.tool()
def read_file(uri: str, max_chars: int = 8000) -> dict:
    """
    Read content from a local file given a file:// URI or file path.
    
    Args:
        uri: File URI (file://) or local file path to read
        max_chars: Maximum characters to return (default: 8000, roughly 2000 tokens)
        
    Returns:
        Dictionary containing file content or error message
    """
    try:
        # Handle file:// URI or direct path
        if uri.startswith("file://"):
            parsed = urlparse(uri)
            file_path = Path(parsed.path)
        else:
            file_path = Path(uri)
        
        # Security checks
        if not file_path.exists():
            return {"error": f"File not found: {file_path}", "uri": uri}
        
        if not file_path.is_file():
            return {"error": f"Path is not a file: {file_path}", "uri": uri}
        
        if ".." in str(file_path):
            return {"error": "Path traversal not allowed", "uri": uri}
        
        # File size check (10MB limit)
        MAX_FILE_SIZE = 10 * 1024 * 1024
        if file_path.stat().st_size > MAX_FILE_SIZE:
            return {
                "error": f"File too large: {file_path.stat().st_size} bytes (max: {MAX_FILE_SIZE})",
                "uri": uri
            }
        
        # Read file content
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = file_path.read_text(encoding='utf-8', errors='replace')
        
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "text/plain"
        
        # Check if content is too large
        if len(content) > max_chars:
            return {
                "error": f"File content too large to display: {len(content):,} characters (max: {max_chars:,})",
                "uri": uri,
                "file_name": file_path.name,
                "file_size": len(content)
            }
        
        # Return full content if within limits
        return {
            "content": content,
            "uri": uri,
            "mime_type": mime_type,
            "file_size": file_path.stat().st_size,
            "file_name": file_path.name,
            "character_count": len(content)
        }
        
    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}", "uri": uri}

@mcp.tool()
def read_resource(uri: str, max_chars: int = 8000) -> dict:
    """
    Read content from a resource URI (primarily for local files).
    
    Args:
        uri: Resource URI to read
        max_chars: Maximum characters to return (default: 8000, roughly 2000 tokens)
        
    Returns:
        Dictionary containing resource content or error message
    """
    return read_file(uri, max_chars)

if mcp_tools_to_be_included:
    @mcp.tool()
    async def create_downloadable_file(filename: str, content: str, ctx: Context | None = None) -> dict:
        """
        Use this tool whenever the user asks to “download as file” or “save as file.”

        Accepts file content, uploads it to a storage bucket,
        and returns a URL the UI will use to show a downloadable file attachment.

        Output Specification:
        After the tool returns the URL, display it to the user in this format:
        File :
            <file_url> (Displayed as file Attachment in UI)
        
        Args:
            filename: File name including extension (e.g. "report.pdf")
            content: Raw or encoded file content

        Returns:
            {
                "filename": "<filename>",
                "url": "<public_url>"
            }
        """

        try:
            logger.info("create_downloadable_file:\n fileName: {} \n content: \n{}".format(filename, content))

            file_bytes = content.encode("utf-8")

            name, ext = os.path.splitext(filename)
            ext = ext if ext else ".txt"
            
            timestamp = str(int(time.time()))

            # Remove any special character or numbers
            folder = re.sub(r"[^a-zA-Z]", "", mcp_tools_to_be_included)
            
            updated_file_name = f'{name}_{timestamp}{ext}'

            path = f"{folder}/{updated_file_name}"

            upload_payload = {
                "FileName": path,
                "FileType": ext,
                "FileContent": list(file_bytes), 
            }

            logger.info("payload: {}".format(upload_payload))

            output = await utils.make_API_call_to_CCow_and_get_response(constants.URL_STORAGE_UPLOAD, "POST", upload_payload, ctx=ctx)
            logger.debug("create_downloadable_file output: {}\n".format(output))

            if isinstance(output, str) and utils.isFileHash(output):
                file_url = f'http://cowfile/hash/{output}/{updated_file_name}'
                return {
                    "filename": filename,
                    "url": file_url
                }
            
            return { "error": "Unable to download the file"}           

        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error("create_downloadable_file: {}\n".format(e))
            return {"error": "Facing internal error"}