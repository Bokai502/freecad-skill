"""
FreeCAD XML-RPC client helper module.
Provides connection management and result formatting for FreeCAD RPC calls.
"""

import json
import os
import sys
import xmlrpc.client
from typing import Any, Dict, Optional


DEFAULT_HOST = os.getenv("FREECAD_RPC_HOST", "localhost")
DEFAULT_PORT = int(os.getenv("FREECAD_RPC_PORT", "9875"))


class FreeCADConnection:
    """Connection manager for FreeCAD RPC server."""
    
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.server = xmlrpc.client.ServerProxy(f"http://{host}:{port}", allow_none=True)
        self.host = host
        self.port = port
    
    def ping(self) -> bool:
        """Check if the server is reachable."""
        try:
            return self.server.ping()
        except Exception:
            return False
    
    # Document operations
    def create_document(self, name: str) -> Dict[str, Any]:
        return self.server.create_document(name)
    
    def list_documents(self) -> list:
        return self.server.list_documents()
    
    # Object operations
    def create_object(self, doc_name: str, obj_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.server.create_object(doc_name, obj_data)
    
    def edit_object(self, doc_name: str, obj_name: str, obj_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.server.edit_object(doc_name, obj_name, obj_data)
    
    def delete_object(self, doc_name: str, obj_name: str) -> Dict[str, Any]:
        return self.server.delete_object(doc_name, obj_name)
    
    def get_object(self, doc_name: str, obj_name: str) -> Dict[str, Any]:
        return self.server.get_object(doc_name, obj_name)
    
    def get_objects(self, doc_name: str) -> list:
        return self.server.get_objects(doc_name)
    
    # Library operations
    def get_parts_list(self) -> list:
        return self.server.get_parts_list()
    
    def insert_part_from_library(self, relative_path: str) -> Dict[str, Any]:
        return self.server.insert_part_from_library(relative_path)
    
    # Code execution
    def execute_code(self, code: str) -> Dict[str, Any]:
        return self.server.execute_code(code)
    
    # View operations
    def get_active_screenshot(
        self, 
        view_name: str = "Isometric", 
        width: Optional[int] = None, 
        height: Optional[int] = None, 
        focus_object: Optional[str] = None
    ) -> Optional[str]:
        return self.server.get_active_screenshot(view_name, width, height, focus_object)


def add_connection_args(parser: Any) -> None:
    """Add common FreeCAD RPC connection args to an argparse parser."""
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"FreeCAD RPC host (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"FreeCAD RPC port (default: {DEFAULT_PORT})",
    )


def get_connection(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> FreeCADConnection:
    """Create and verify connection to FreeCAD RPC server."""
    conn = FreeCADConnection(host, port)
    try:
        if not conn.ping():
            raise ConnectionError(f"Cannot ping FreeCAD RPC server at {host}:{port}")
    except Exception as e:
        print(f"ERROR: Cannot connect to FreeCAD RPC server at {host}:{port}", file=sys.stderr)
        print(f"Make sure the FreeCAD MCP addon is running.", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        sys.exit(1)
    return conn


def print_result(result: Any) -> None:
    """Print RPC result as formatted JSON."""
    print(json.dumps(result, indent=2, ensure_ascii=False))
