from mcpconfig.config import mcp
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

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

