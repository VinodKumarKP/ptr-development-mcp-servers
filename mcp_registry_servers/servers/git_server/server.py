import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

file_root = os.path.dirname(os.path.abspath(__file__))
path_list = [
    file_root,
    os.path.dirname(file_root),
    os.path.dirname(os.path.dirname(file_root))
]
for path in path_list:
    if path not in sys.path:
        sys.path.append(path)


import nest_asyncio  # Added import

nest_asyncio.apply()  # Added call

from mcp_registry_servers.tools.git_tools import GitTools
from mcp_server_core.core.base_mcp_server import BaseMCPServer


class GitToolsServer(BaseMCPServer):
    """Git tools MCP server implementation."""

    def __init__(self):
        """
        Initialize the Git tools server.
        """
        super().__init__(self.base_directory(__file__),
                         object_list=[GitTools()],
                         source_file=__file__)

def main():
    """Main function to run the Git tools server."""
    server = GitToolsServer()
    server.main()


if __name__ == "__main__":
    main()
