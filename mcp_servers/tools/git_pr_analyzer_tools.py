import os
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests


class PullRequestAnalyzer:
    """
    Pull Request Analyzer for GitHub repositories.
    Designed to be used as an MCP server for automated PR analysis.
    """

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize the PR Analyzer.

        Args:
            github_token: GitHub personal access token. If None, uses GITHUB_TOKEN env var.

        Raises:
            ValueError: If no GitHub token is provided
        """
        self.github_token = github_token or os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError(
                "GitHub token is required. Set GITHUB_TOKEN environment variable or pass token directly."
            )

        self._headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

    def analyze_pr_from_url(self, repo_url: str, pr_number: int) -> Dict:
        """
        Analyze a GitHub pull request directly from repository URL and PR number.

        Args:
            repo_url: GitHub repository URL (e.g., 'https://github.com/owner/repo')
            pr_number: Pull request number

        Returns:
            dict: Complete PR analysis structure

        Raises:
            Exception: If PR fetching or analysis fails
        """
        try:
            pr_text = self._fetch_pr_text(repo_url, pr_number)
            return self._analyze_pr_text(pr_text)
        except Exception as e:
            raise Exception(f"Failed to analyze PR: {str(e)}")

    def analyze_pr_from_text(self, pr_text: str) -> Dict:
        """
        Analyze pull request from formatted text.

        Args:
            pr_text: Formatted PR text (from GitHub or similar format)

        Returns:
            dict: Complete PR analysis structure
        """
        return self._analyze_pr_text(pr_text)

    def get_pr_formatted_text(self, repo_url: str, pr_number: int) -> str:
        """
        Get formatted PR text for external analysis.

        Args:
            repo_url: GitHub repository URL
            pr_number: Pull request number

        Returns:
            str: Formatted PR text
        """
        return self._fetch_pr_text(repo_url, pr_number)

    def validate_github_access(self) -> bool:
        """
        Validate GitHub token and API access.

        Returns:
            bool: True if token is valid and API is accessible
        """
        try:
            response = requests.get('https://api.github.com/user', headers=self._headers)
            return response.status_code == 200
        except Exception:
            return False

    # Private methods

    def _fetch_pr_text(self, repo_url: str, pr_number: int) -> str:
        """Fetch and format PR text from GitHub API."""
        try:
            owner, repo = self._parse_repo_url(repo_url)

            # Get PR data
            pr_data = self._get_pr_details(owner, repo, pr_number)
            files_data = self._get_pr_files(owner, repo, pr_number)
            commits_data = self._get_pr_commits(owner, repo, pr_number)

            return self._format_pr_text(pr_data, files_data, commits_data)

        except Exception as e:
            raise Exception(f"Failed to fetch PR text: {str(e)}")

    def _parse_repo_url(self, repo_url: str) -> Tuple[str, str]:
        """Parse GitHub repository URL to extract owner and repo name."""
        try:
            if repo_url.startswith('git@'):
                # SSH format: git@github.com:owner/repo.git
                parts = repo_url.split(':')[1].split('/')
                owner = parts[0]
                repo = parts[1].replace('.git', '')
            else:
                # HTTPS format: https://github.com/owner/repo
                parsed = urlparse(repo_url)
                path_parts = parsed.path.strip('/').split('/')
                if len(path_parts) < 2:
                    raise ValueError("Invalid repository URL format")
                owner = path_parts[0]
                repo = path_parts[1].replace('.git', '')

            return owner, repo

        except Exception as e:
            raise ValueError(f"Could not parse repository URL: {str(e)}")

    def _get_pr_details(self, owner: str, repo: str, pr_number: int) -> Dict:
        """Get pull request details from GitHub API."""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        response = requests.get(url, headers=self._headers)
        response.raise_for_status()
        return response.json()

    def _get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Get pull request files from GitHub API."""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        response = requests.get(url, headers=self._headers)
        response.raise_for_status()
        return response.json()

    def _get_pr_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Get pull request commits from GitHub API."""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        response = requests.get(url, headers=self._headers)
        response.raise_for_status()
        return response.json()

    def _format_pr_text(self, pr_data: Dict, files_data: List[Dict], commits_data: List[Dict]) -> str:
        """Format the PR data into the expected text format."""
        # Calculate statistics
        total_additions = sum(file['additions'] for file in files_data)
        total_deletions = sum(file['deletions'] for file in files_data)
        files_changed = len(files_data)
        commits_count = len(commits_data)

        formatted_text = []

        # Header
        formatted_text.append(f"Pull Request #{pr_data['number']}: {pr_data['title']}")
        formatted_text.append(f"Total changes: +{total_additions} -{total_deletions}")
        formatted_text.append(f"Files changed: {files_changed}")
        formatted_text.append(f"Commits: {commits_count}")
        formatted_text.append("")

        # Files modified section
        formatted_text.append("Files modified:")
        for file_data in files_data:
            status_emoji = self._get_status_emoji(file_data['status'])
            filename = file_data['filename']
            additions = file_data['additions']
            deletions = file_data['deletions']
            formatted_text.append(f"  {status_emoji} {filename} (+{additions} -{deletions})")
        formatted_text.append("")

        # Detailed changes for each file
        for file_data in files_data:
            filename = file_data['filename']
            formatted_text.append(f"Detailed changes in {filename}:")

            patch = file_data.get('patch', '')
            if patch:
                formatted_changes = self._format_patch(patch)
                formatted_text.extend(formatted_changes)
            else:
                if file_data['status'] == 'added':
                    formatted_text.append("  (New file added)")
                elif file_data['status'] == 'removed':
                    formatted_text.append("  (File removed)")
                else:
                    formatted_text.append("  (Binary file or no changes to display)")

            formatted_text.append("")

        return '\n'.join(formatted_text)

    def _get_status_emoji(self, status: str) -> str:
        """Get emoji for file status."""
        emoji_map = {
            'added': '🆕',
            'modified': '📝',
            'removed': '❌',
            'renamed': '📋'
        }
        return emoji_map.get(status, '📝')

    def _format_patch(self, patch: str) -> List[str]:
        """Format git patch into readable line-by-line changes."""
        lines = patch.split('\n')
        formatted_lines = []
        line_number = 0

        for line in lines:
            if line.startswith('@@'):
                match = re.search(r'@@\s*-(\d+)(?:,\d+)?\s*\+(\d+)(?:,\d+)?\s*@@', line)
                if match:
                    line_number = int(match.group(2))
                continue

            if line.startswith('+') and not line.startswith('+++'):
                content = line[1:]
                formatted_lines.append(f"  {line_number} + {content}")
                line_number += 1
            elif line.startswith('-') and not line.startswith('---'):
                content = line[1:]
                formatted_lines.append(f"  {line_number} - {content}")
            elif line.startswith(' '):
                content = line[1:]
                formatted_lines.append(f"  {line_number}   {content}")
                line_number += 1

        return formatted_lines

    def _analyze_pr_text(self, pr_text: str) -> Dict:
        """Analyze pull request text and return structured data."""
        # Extract basic PR information
        pr_info = self._extract_pr_info(pr_text)

        # Extract file changes
        files_changed = self._extract_file_changes(pr_text)

        # Extract detailed file changes
        file_details = self._extract_file_details(pr_text)

        # Analyze code patterns
        code_analysis = self._analyze_code_changes(file_details)

        # Check for title-content mismatch
        mismatch_analysis = self._analyze_title_content_mismatch(
            pr_info.get('title', ''), file_details, code_analysis
        )

        return {
            'pull_request_info': pr_info,
            'files_changed': files_changed,
            'file_details': file_details,
            'code_analysis': code_analysis,
            'mismatch_analysis': mismatch_analysis,
            'summary': self._generate_summary(pr_info, files_changed, code_analysis),
            'recommendations': self._generate_recommendations(mismatch_analysis, code_analysis)
        }

    def _extract_pr_info(self, pr_text: str) -> Dict:
        """Extract basic PR information from text."""
        pr_info = {}

        # Extract PR number and title
        pr_match = re.search(r'Pull Request #(\d+):(.*)', pr_text)
        if pr_match:
            pr_info['pr_number'] = int(pr_match.group(1))
            pr_info['title'] = pr_match.group(2).strip()

        # Extract summary statistics
        stats_pattern = r'Total changes: \+(\d+) -(\d+)\nFiles changed: (\d+)\nCommits: (\d+)'
        stats_match = re.search(stats_pattern, pr_text)

        if stats_match:
            pr_info['statistics'] = {
                'lines_added': int(stats_match.group(1)),
                'lines_removed': int(stats_match.group(2)),
                'files_changed': int(stats_match.group(3)),
                'commits': int(stats_match.group(4))
            }

        return pr_info

    def _extract_file_changes(self, pr_text: str) -> List[Dict]:
        """Extract file changes from PR text."""
        files_changed = []

        file_patterns = [
            (r'🆕 ([^\s]+) \(\+(\d+) -(\d+)\)', 'new'),
            (r'📝 ([^\s]+) \(\+(\d+) -(\d+)\)', 'modified'),
            (r'❌ ([^\s]+) \(\+(\d+) -(\d+)\)', 'removed'),
            (r'📋 ([^\s]+) \(\+(\d+) -(\d+)\)', 'renamed')
        ]

        for pattern, change_type in file_patterns:
            matches = re.findall(pattern, pr_text)
            for match in matches:
                files_changed.append({
                    'filepath': match[0],
                    'change_type': change_type,
                    'lines_added': int(match[1]),
                    'lines_removed': int(match[2])
                })

        return files_changed

    def _extract_file_details(self, pr_text: str) -> Dict:
        """Extract detailed file changes from PR text."""
        file_details = {}

        sections = re.split(r'Detailed changes in ([^:]+):', pr_text)

        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                filepath = sections[i].strip()
                content = sections[i + 1].strip()

                changes = []
                lines = content.split('\n')

                for line in lines:
                    # Added lines
                    add_match = re.match(r'\s*(\d+)\s*\+\s*(.*)', line)
                    if add_match:
                        changes.append({
                            'line_number': int(add_match.group(1)),
                            'type': 'added',
                            'content': add_match.group(2)
                        })
                        continue

                    # Removed lines
                    remove_match = re.match(r'\s*(\d+)\s*-\s*(.*)', line)
                    if remove_match:
                        changes.append({
                            'line_number': int(remove_match.group(1)),
                            'type': 'removed',
                            'content': remove_match.group(2)
                        })
                        continue

                    # Context lines
                    context_match = re.match(r'\s*(\d+)\s+(.*)', line)
                    if context_match:
                        changes.append({
                            'line_number': int(context_match.group(1)),
                            'type': 'context',
                            'content': context_match.group(2)
                        })

                if changes:
                    file_details[filepath] = changes

        return file_details

    def _analyze_code_changes(self, file_details: Dict) -> Dict:
        """Analyze code patterns and functionality from file changes."""
        analysis = {
            'new_classes': [],
            'new_methods': [],
            'new_imports': [],
            'configuration_changes': [],
            'api_integrations': [],
            'functionality_additions': []
        }

        for filepath, changes in file_details.items():
            added_lines = [change['content'] for change in changes if change['type'] == 'added']
            content = '\n'.join(added_lines)

            # Detect new classes
            class_matches = re.findall(r'class\s+(\w+)', content)
            analysis['new_classes'].extend([{'name': cls, 'file': filepath} for cls in class_matches])

            # Detect new methods/functions
            method_matches = re.findall(r'def\s+(\w+)', content)
            analysis['new_methods'].extend([{'name': method, 'file': filepath} for method in method_matches])

            # Detect new imports
            import_matches = re.findall(r'import\s+(\w+)', content)
            from_import_matches = re.findall(r'from\s+[\w.]+\s+import\s+([\w,\s]+)', content)
            all_imports = import_matches + [imp.strip() for match in from_import_matches for imp in match.split(',')]
            analysis['new_imports'].extend([{'name': imp.strip(), 'file': filepath} for imp in all_imports])

            # Detect configuration files
            if filepath.endswith('.json'):
                analysis['configuration_changes'].append({'file': filepath, 'type': 'json_config'})

            # Detect API integrations
            if 'requests.' in content or 'api.github.com' in content:
                analysis['api_integrations'].append({'type': 'github_api', 'file': filepath})

            # Detect specific functionality
            if 'pull_request' in content.lower():
                analysis['functionality_additions'].append({'type': 'pull_request_management', 'file': filepath})

            if 'branch' in content.lower() and ('create' in content.lower() or 'checkout' in content.lower()):
                analysis['functionality_additions'].append({'type': 'branch_management', 'file': filepath})

        return analysis

    def _analyze_title_content_mismatch(self, title: str, file_details: Dict, code_analysis: Dict) -> Dict:
        """Analyze if PR title matches the actual changes made."""
        title_lower = title.lower()

        title_suggests = {
            'configuration_only': 'config' in title_lower and 'add' in title_lower,
            'minor_change': len(title.split()) <= 6,
            'setup_only': 'add' in title_lower or 'setup' in title_lower
        }

        actual_changes = {
            'has_new_classes': len(code_analysis['new_classes']) > 0,
            'has_new_methods': len(code_analysis['new_methods']) > 5,
            'has_api_integration': len(code_analysis['api_integrations']) > 0,
            'has_major_functionality': len(code_analysis['functionality_additions']) > 1,
            'lines_added': sum(len([c for c in changes if c['type'] == 'added'])
                               for changes in file_details.values())
        }

        mismatch_score = 0
        issues = []

        if title_suggests['configuration_only'] and actual_changes['has_api_integration']:
            mismatch_score += 3
            issues.append("Title suggests configuration only, but API integration was added")

        if title_suggests['minor_change'] and actual_changes['lines_added'] > 100:
            mismatch_score += 2
            issues.append(f"Title suggests minor change, but {actual_changes['lines_added']} lines were added")

        if title_suggests['setup_only'] and actual_changes['has_major_functionality']:
            mismatch_score += 3
            issues.append("Title suggests setup only, but major functionality was implemented")

        return {
            'mismatch_score': mismatch_score,
            'severity': 'high' if mismatch_score >= 6 else 'medium' if mismatch_score >= 3 else 'low',
            'issues': issues,
            'title_suggests': title_suggests,
            'actual_changes': actual_changes
        }

    def _generate_summary(self, pr_info: Dict, files_changed: List, code_analysis: Dict) -> Dict:
        """Generate a concise summary of changes."""
        return {
            'change_scope': 'major' if pr_info.get('statistics', {}).get('lines_added', 0) > 100 else 'minor',
            'primary_purpose': self._infer_primary_purpose(code_analysis),
            'key_additions': [
                f"{len(code_analysis['new_classes'])} new classes",
                f"{len(code_analysis['new_methods'])} new methods",
                f"{len(code_analysis['api_integrations'])} API integrations"
            ]
        }

    def _generate_recommendations(self, mismatch_analysis: Dict, code_analysis: Dict) -> List[Dict]:
        """Generate recommendations based on analysis."""
        recommendations = []

        if mismatch_analysis['severity'] in ['high', 'medium']:
            recommendations.append({
                'type': 'title_improvement',
                'priority': 'high',
                'message': 'PR title should be updated to better reflect the scope of changes'
            })

        if len(code_analysis['new_methods']) > 10:
            recommendations.append({
                'type': 'code_review',
                'priority': 'medium',
                'message': 'Large number of new methods added - consider splitting into multiple PRs'
            })

        if code_analysis['api_integrations']:
            recommendations.append({
                'type': 'security_review',
                'priority': 'high',
                'message': 'API integration added - ensure proper authentication and error handling'
            })

        return recommendations

    def _infer_primary_purpose(self, code_analysis: Dict) -> str:
        """Infer the primary purpose based on code changes."""
        if code_analysis['api_integrations']:
            return 'api_integration'
        elif len(code_analysis['new_classes']) > 0:
            return 'feature_implementation'
        elif code_analysis['configuration_changes']:
            return 'configuration'
        else:
            return 'maintenance'
