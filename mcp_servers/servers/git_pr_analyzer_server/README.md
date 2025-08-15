# Git PR Analyzer MCP Server

A specialized Model Context Protocol (MCP) server that provides comprehensive GitHub Pull Request analysis capabilities. This server enables AI assistants to fetch, analyze, and extract detailed insights from GitHub pull requests, including code changes, title-content mismatch detection, and automated recommendations.

## Features

### Pull Request Analysis
- **Direct PR analysis** from GitHub repository URL and PR number
- **Text-based PR analysis** for formatted PR content
- **Code pattern detection** including new classes, methods, and imports
- **Title-content mismatch analysis** to identify inconsistencies between PR titles and actual changes

### Code Analysis
- **Programming language detection** with detailed code structure analysis
- **API integration detection** for external service connections
- **Configuration file changes** identification
- **Functionality addition tracking** for new features and capabilities

### Automated Insights
- **Comprehensive PR summaries** with change scope and primary purpose identification
- **Automated recommendations** for code review, security considerations, and PR improvements
- **Detailed statistics** including lines added/removed, files changed, and commit counts

### GitHub Integration
- **Full GitHub API integration** with token-based authentication
- **Repository URL parsing** supporting both HTTPS and SSH formats
- **Complete PR data fetching** including files, commits, and detailed changes

## Installation

### Option 1: Direct UV Run (Recommended)
Use uv to run the server directly without local installation:

```json
{
  "git-pr-analyzer-server": {
    "command": "uv",
    "args": [
      "run",
      "--with",
      "git+https://github.com/Capgemini-Innersource/ptr_mcp_servers_registry.git",
      "git-pr-analyzer-server"
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
  "git-pr-analyzer-server": {
    "command": "git-pr-analyzer-server",
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
  "git-pr-analyzer-server": {
    "command": "uv",
    "args": [
      "run",
      "--directory",
      "/path/to/ptr_mcp_servers_registry",
      "git-pr-analyzer-server"
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
   make start-git-pr-analyzer-server
   ```

4. **List available services:**
   ```bash
   make list-services
   ```

5. **Configure your client to use the local server:**
   In your client configuration (e.g., Claude Desktop), add the server with the local URL:
   ```json
   {
     "git-pr-analyzer-server": {
       "command":"npx",
    	"args":["mcp-remote@latest","http://localhost:8006/mcp", "--allow-http"]
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
   # Allow traffic on port 8006
   # Check the servers_config/git_pr_analyzer_server.json for the list of ports to be opened
   sudo ufw allow 8006
   ```

3. **Configure your client to use the remote server:**
   In your client configuration, use the remote server URL:
   ```json
   {
     "git-pr-analyzer-server": {
       "command":"npx",
    	"args":["mcp-remote@latest","http://remote-ip:8006/mcp", "--allow-http"]
     }
   }
   ```

## Configuration

### Prerequisites
Before using the Git PR Analyzer MCP Server, you need to set up GitHub authentication:

1. **Create a GitHub Personal Access Token:**
   - Go to GitHub Settings > Developer settings > Personal access tokens
   - Generate a new token with `repo` permissions
   - Copy the token for configuration

2. **Set the environment variable:**
   ```bash
   export GITHUB_TOKEN=your_github_token_here
   ```

### Claude Desktop
Add to your `claude_desktop_config.json`:

Using uv command

```json
{
  "mcpServers": {
    "git-pr-analyzer-server": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "git+https://github.com/Capgemini-Innersource/ptr_mcp_servers_registry.git",
        "git-pr-analyzer-server"
      ],
      "env": {
        "GITHUB_TOKEN": "your_github_token_here"
      }
    }
  }
}
```

Using npx command and remote server

```json
{
  "mcpServers": {
    "git-pr-analyzer-server": {
      "command":"npx",
    	"args":["mcp-remote@latest","http://<<remote-ip>>:8006/mcp", "--allow-http"],
      "env": {
        "GITHUB_TOKEN": "your_github_token_here"
      }
    }
  }
}
```

### Other MCP Clients
The server follows the standard MCP protocol and can be integrated with any MCP-compatible client using the installation methods above.

## Available Tools

### Pull Request Analysis

#### `analyze_pr_from_url`
Analyze a GitHub pull request directly from repository URL and PR number.
- **Parameters:**
  - `repo_url` (string): GitHub repository URL (e.g., 'https://github.com/owner/repo')
  - `pr_number` (integer): Pull request number
- **Returns:** Complete PR analysis structure with code patterns, mismatch analysis, and recommendations

#### `analyze_pr_from_text`
Analyze pull request from formatted text content.
- **Parameters:**
  - `pr_text` (string): Formatted PR text (from GitHub or similar format)
- **Returns:** Complete PR analysis structure with detailed insights

#### `get_pr_formatted_text`
Get formatted PR text for external analysis or manual review.
- **Parameters:**
  - `repo_url` (string): GitHub repository URL
  - `pr_number` (integer): Pull request number
- **Returns:** Formatted PR text with file changes and statistics

### GitHub Integration

#### `validate_github_access`
Validate GitHub token and API access to ensure proper authentication.
- **Parameters:** None
- **Returns:** Boolean indicating whether the GitHub token is valid and API is accessible

## Usage Examples

### Basic PR Analysis
```python
# Analyze a pull request directly from GitHub
analysis = await analyze_pr_from_url(
    "https://github.com/owner/repo", 
    123
)

# Get formatted PR text for manual review
pr_text = await get_pr_formatted_text(
    "https://github.com/owner/repo", 
    123
)

# Analyze PR from existing text
text_analysis = await analyze_pr_from_text(pr_text)
```

### Comprehensive Analysis Example
```python
# Validate GitHub access first
is_valid = await validate_github_access()

if is_valid:
    # Perform complete PR analysis
    analysis = await analyze_pr_from_url(
        "https://github.com/microsoft/vscode", 
        12345
    )
    
    # Extract key insights
    pr_info = analysis['pull_request_info']
    code_analysis = analysis['code_analysis']
    mismatch_analysis = analysis['mismatch_analysis']
    recommendations = analysis['recommendations']
    
    print(f"PR #{pr_info['pr_number']}: {pr_info['title']}")
    print(f"Mismatch severity: {mismatch_analysis['severity']}")
    print(f"New classes added: {len(code_analysis['new_classes'])}")
    print(f"Recommendations: {len(recommendations)}")
```

## Analysis Output Structure

The PR analysis returns a comprehensive dictionary with the following structure:

### `pull_request_info`
- PR number and title
- Statistics (lines added/removed, files changed, commits)

### `files_changed`
- List of modified files with change types
- Lines added/removed per file

### `file_details`
- Detailed line-by-line changes for each file
- Added, removed, and context lines with line numbers

### `code_analysis`
- New classes, methods, and imports detected
- Configuration changes identified
- API integrations discovered
- Functionality additions categorized

### `mismatch_analysis`
- Mismatch score and severity level
- Specific issues between title and content
- Comparison of title suggestions vs. actual changes

### `summary`
- Change scope (major/minor)
- Primary purpose inference
- Key additions summary

### `recommendations`
- Prioritized recommendations for improvement
- Security, code review, and title suggestions
- Action items for PR optimization

## Error Handling

The server includes comprehensive error handling for:
- Invalid GitHub repository URLs
- Missing or invalid GitHub tokens
- Network connectivity issues
- Non-existent pull requests
- API rate limiting
- Authentication failures

All errors are logged and returned with descriptive messages to help with debugging and resolution.

## Requirements

- Python 3.11+
- Valid GitHub Personal Access Token with repo permissions
- Network access for GitHub API calls
- Sufficient memory for processing large pull requests

## Security Considerations

- GitHub tokens are sensitive credentials - store them securely
- Use environment variables for token configuration
- Consider token rotation for production deployments
- Review API permissions regularly

## License

This MCP server is part of the Capgemini Innersource MCP Servers Registry. Please refer to the repository for licensing information.

## Contributing

This server is maintained as part of the larger MCP servers registry. For issues, feature requests, or contributions, please visit the [main repository](https://github.com/Capgemini-Innersource/ptr_mcp_servers_registry).