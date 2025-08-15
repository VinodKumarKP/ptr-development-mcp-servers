# Git Server MCP Server

A comprehensive Model Context Protocol (MCP) server that provides advanced Git repository analysis and management capabilities. This server enables AI assistants to clone, analyze, and extract detailed information from Git repositories.

## Features

### Repository Management
- **Clone repositories** from any Git URL with branch selection
- **Clean up** temporary repositories after analysis
- **Get file listings** with intelligent filtering (excludes binary and hidden files)

### Repository Analysis
- **Comprehensive statistics** including commit counts, contributors, branches, and more
- **Programming language detection** with detailed breakdown and statistics
- **Repository structure visualization** with configurable depth traversal
- **Contributor analysis** with detailed statistics and contributions

### Commit Analysis
- **Commit history** with detailed information and date filtering
- **Commit search** by message content with configurable limits
- **Contributor statistics** with detailed breakdowns

## Installation

### Option 1: Direct UV Run (Recommended)
Use uv to run the server directly without local installation:

```json
{
  "git-server": {
    "command": "uv",
    "args": [
      "run",
      "--with",
      "git+https://github.com/Capgemini-Innersource/ptr_mcp_servers_registry.git",
      "git-mcp-server"
    ]
  }
}
```

### Option 2: Pip Install + Run
Install the package first, then run the server:

```bash
pip install git+https://github.com/Capgemini-Innersource/ptr_mcp_servers_registry.git
```

Then configure your MCP client:
```json
{
  "git-server": {
    "command": "git-mcp-server",
    "args": []
  }
}
```

### Option 3: Local Clone + UV Run
Clone the repository locally and run with uv:

```bash
git clone https://github.com/Capgemini-Innersource/ptr_mcp_servers_registry.git
```

Then configure your MCP client:
```json
{
  "git-server": {
    "command": "uv",
    "args": [
      "run",
      "--directory",
      "/path/to/ptr_mcp_servers_registry",
      "git-mcp-server"
    ]
  }
}
```

### Option 4: Local Docker Compose Setup

You can run the MCP server registry locally using Docker Compose. This is ideal for development and testing purposes.

#### Prerequisites
- Docker and Docker Compose installed
- Make utility installed
- `jq` command-line JSON processor

#### Setup Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Capgemini-Innersource/ptr_mcp_servers_registry.git
   cd ptr_mcp_servers_registry
   ```

2. **Build and start all services:**
   ```bash
   make start-all
   ```

3. **Or start a specific service:**
   ```bash
   make start-git_server
   ```

4. **List available services:**
   ```bash
   make list-services
   ```

5. **Configure your client to use the local server:**
   In your client configuration (e.g., Claude Desktop), add the server with the local URL:
   ```json
   {
     "git-server": {
       "command":"npx",
    	"args":["mcp-remote@latest","http://localhost:8000/mcp", "--allow-http"]
     }
   }
   ```

#### Available Make Commands

- `make start-all` - Start all services using Docker Compose
- `make stop-all` - Stop all services
- `make start-<service>` - Start a specific service
- `make stop-<service>` - Stop a specific service
- `make restart-<service>` - Restart a specific service
- `make list-services` - List all available services
- `make docker-build` - Build the Docker image
- `make generate-compose` - Generate Docker Compose file

### Option 5: Remote Server Deployment

For production use or when you want to share the MCP server with multiple users, you can deploy it to a remote server.

#### Prerequisites
- Remote server with Docker and Docker Compose installed
- SSH access to the remote server
- Domain name or public IP address

#### Deployment Steps

1. **Deploy to your remote server:**
   ```bash
   # SSH into your remote server
   ssh user@your-remote-server.com
   
   # Clone the repository
   git clone https://github.com/Capgemini-Innersource/ptr_mcp_servers_registry.git
   cd ptr_mcp_servers_registry
   
   # Build and start services
   make start-all
   ```

2. **Configure firewall (if needed):**
   ```bash
   # Allow traffic on port 8000
   # Check the servers_config/git_server.json for the list of ports to be opened
   sudo ufw allow 8000
   ```

3. **Configure your client to use the remote server:**
   In your client configuration, use the remote server URL:
   ```json
   {
     "git-server": {
       "command":"npx",
    	"args":["mcp-remote@latest","http://remote-ip:8000/mcp", "--allow-http"]
     }
   }
   ```

## Configuration

### Claude Desktop
Add to your `claude_desktop_config.json`:

Using uv command

```json
{
  "mcpServers": {
    "git-server": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "git+https://github.com/Capgemini-Innersource/ptr_mcp_servers_registry.git",
        "git-mcp-server"
      ]
    }
  }
}
```

Using npx command and remote server

```json
{
  "mcpServers": {
    "git-server": {
      "command":"npx",
    	"args":["mcp-remote@latest","http://<<remote-ip>>:8000/mcp", "--allow-http"]
    }
  }
}
```

### Other MCP Clients
The server follows the standard MCP protocol and can be integrated with any MCP-compatible client using the installation methods above.

## Available Tools

### Repository Management

#### `clone_repository`
Clone a Git repository to analyze it.
- **Parameters:**
  - `git_url` (string): Git repository URL
  - `branch` (string, optional): Branch to checkout (default: "main")
- **Returns:** Path to the cloned repository

#### `cleanup_repository`
Remove a cloned repository to free up disk space.
- **Parameters:**
  - `repo_path` (string): Path to the repository to clean up
- **Returns:** Boolean indicating success

### Repository Analysis

#### `get_file_list`
Get a list of all files in the repository, excluding binary and hidden files.
- **Parameters:**
  - `repo_path` (string): Path to repository
- **Returns:** List of file paths relative to repository root

#### `get_git_stats`
Get comprehensive statistics about the repository.
- **Parameters:**
  - `repo_path` (string): Path to the Git repository
- **Returns:** Dictionary with repository statistics including commits, contributors, branches, etc.

#### `identify_programming_languages`
Analyze the repository to identify programming languages used.
- **Parameters:**
  - `repo_path` (string): Path to the Git repository
- **Returns:** Dictionary with language statistics and breakdown

#### `get_repository_structure`
Get the directory structure of the repository.
- **Parameters:**
  - `repo_path` (string): Path to the Git repository
  - `max_depth` (integer, optional): Maximum depth to traverse (default: 3)
- **Returns:** Dictionary with repository structure information

### Commit Analysis

#### `get_commit_history`
Retrieve detailed commit history with optional date filtering.
- **Parameters:**
  - `repo_path` (string): Path to the Git repository
  - `limit` (integer, optional): Maximum number of commits to return (default: 20)
  - `since_days` (integer, optional): Only return commits from the last N days
- **Returns:** List of commit information dictionaries

#### `search_commits`
Search commits by message content.
- **Parameters:**
  - `repo_path` (string): Path to the Git repository
  - `search_term` (string): Term to search for in commit messages
  - `limit` (integer, optional): Maximum number of results to return (default: 10)
- **Returns:** List of matching commits

#### `get_contributor_stats`
Get detailed contributor statistics.
- **Parameters:**
  - `repo_path` (string): Path to the Git repository
- **Returns:** Dictionary with contributor statistics


## Usage Examples

### Basic Repository Analysis
```python
# Clone a repository
repo_path = await clone_repository("https://github.com/user/repo.git", "main")

# Get basic statistics
stats = await get_git_stats(repo_path)

# Identify programming languages
languages = await identify_programming_languages(repo_path)

# Get repository structure
structure = await get_repository_structure(repo_path, max_depth=3)

# Clean up when done
await cleanup_repository(repo_path)
```

### Commit Analysis
```python
# Get recent commit history
commits = await get_commit_history(repo_path, limit=50, since_days=30)

# Search for specific commits
bug_fixes = await search_commits(repo_path, "bug fix", limit=10)

# Get contributor statistics
contributors = await get_contributor_stats(repo_path)
```

## Error Handling

The server includes comprehensive error handling for common Git operations:
- Invalid repository URLs
- Network connectivity issues
- Permission errors
- Missing branches or commits
- Repository cleanup failures

All errors are logged and returned with descriptive messages to help with debugging.

## Requirements

- Python 3.11+
- Git installed and accessible in PATH
- Network access for cloning repositories
- Sufficient disk space for temporary repository storage

## License

This MCP server is part of the Capgemini Innersource MCP Servers Registry. Please refer to the repository for licensing information.

## Contributing

This server is maintained as part of the larger MCP servers registry. For issues, feature requests, or contributions, please visit the [main repository](https://github.com/Capgemini-Innersource/ptr_mcp_servers_registry).

