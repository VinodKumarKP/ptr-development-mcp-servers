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

import nest_asyncio

nest_asyncio.apply()

from mcp_registry_servers.tools.gitlab_tools import GitLabTools
from oai_mcp_server_core.core.base_mcp_server import BaseMCPServer
from mcp_registry_servers.tools.gitlab_pr_analyzer_tools import MergeRequestAnalyzer

class GitLabToolsServer(BaseMCPServer):
    def __init__(self):
        super().__init__(self.base_directory(__file__), object_list=[GitLabTools(), MergeRequestAnalyzer()], source_file=__file__)


def main():
    server = GitLabToolsServer()
    server.main()


if __name__ == '__main__':
    main()
