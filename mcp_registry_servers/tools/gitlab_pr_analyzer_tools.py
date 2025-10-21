
import os
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests


class MergeRequestAnalyzer:
    """Analyzer for GitLab Merge Requests (MRs)."""

    def __init__(self, gitlab_token: Optional[str] = None, gitlab_host: str = 'https://gitlab.com'):
        self.gitlab_token = gitlab_token or os.environ.get('GITLAB_TOKEN')
        if not self.gitlab_token:
            raise ValueError('GitLab token required (GITLAB_TOKEN env var or parameter)')

        self.host = gitlab_host.rstrip('/')
        self._headers = {
            'PRIVATE-TOKEN': self.gitlab_token,
            'Accept': 'application/json'
        }

    def analyze_mr_from_url(self, repo_url: str, mr_iid: int) -> Dict:
        mr_text = self._fetch_mr_text(repo_url, mr_iid)
        return self._analyze_mr_text(mr_text)

    def get_mr_formatted_text(self, repo_url: str, mr_iid: int) -> str:
        return self._fetch_mr_text(repo_url, mr_iid)

    def validate_access(self) -> bool:
        try:
            resp = requests.get(f'{self.host}/api/v4/user', headers=self._headers)
            return resp.status_code == 200
        except Exception:
            return False

    def _parse_repo_url(self, repo_url: str) -> Tuple[str, str]:
        # returns (namespace, project)
        if repo_url.startswith('git@'):
            path = repo_url.split(':', 1)[1].replace('.git', '')
            parts = path.split('/')
            return parts[0], parts[1]
        parsed = urlparse(repo_url)
        parts = parsed.path.strip('/').replace('.git', '').split('/')
        if len(parts) < 2:
            raise ValueError('Invalid GitLab repo URL')
        return parts[0], parts[1]

    def _project_id(self, repo_url: str) -> str:
        # GitLab API uses URL-encoded namespace/project as id in many endpoints
        parsed = urlparse(repo_url)
        project = parsed.path.strip('/').replace('.git', '')
        return requests.utils.quote(project, safe='')

    def _fetch_mr_text(self, repo_url: str, mr_iid: int) -> str:
        project = self._project_id(repo_url)
        url = f"{self.host}/api/v4/projects/{project}/merge_requests/{mr_iid}"
        resp = requests.get(url, headers=self._headers)
        resp.raise_for_status()
        mr = resp.json()

        # get changes
        changes_url = f"{self.host}/api/v4/projects/{project}/merge_requests/{mr_iid}/changes"
        changes_resp = requests.get(changes_url, headers=self._headers)
        changes_resp.raise_for_status()
        changes = changes_resp.json()

        # format similar to GitHub PR text used by analyzer
        files = []
        total_additions = 0
        total_deletions = 0
        for change in changes.get('changes', changes.get('diffs', [])):
            filename = change.get('new_path') or change.get('old_path')
            additions = change.get('additions', 0)
            deletions = change.get('deletions', 0)
            total_additions += additions
            total_deletions += deletions
            status = 'modified'
            if change.get('new_file'):
                status = 'added'
            if change.get('deleted_file'):
                status = 'removed'
            files.append({'filename': filename, 'additions': additions, 'deletions': deletions, 'status': status, 'patch': change.get('diff') or change.get('patch', '')})

        formatted = []
        formatted.append(f"Merge Request !{mr.get('iid')}: {mr.get('title')}")
        formatted.append(f"Total changes: +{total_additions} -{total_deletions}")
        formatted.append(f"Files changed: {len(files)}")
        formatted.append(f"Commits: {mr.get('commit_count', 'unknown')}")
        formatted.append('')
        formatted.append('Files modified:')
        for f in files:
            emoji = '📝'
            if f['status'] == 'added':
                emoji = '🆕'
            if f['status'] == 'removed':
                emoji = '❌'
            formatted.append(f"  {emoji} {f['filename']} (+{f['additions']} -{f['deletions']})")
        formatted.append('')

        for f in files:
            formatted.append(f"Detailed changes in {f['filename']}:")
            patch = f.get('patch', '')
            if patch:
                formatted.append(patch)
            else:
                formatted.append('  (Binary file or no changes to display)')
            formatted.append('')

        return '\n'.join(formatted)

    def _analyze_mr_text(self, mr_text: str) -> Dict:
        # naive reuse of GitHub analyzer text parsing expectations
        # basic extraction
        title_match = re.search(r'Merge Request !?(\d+):\s*(.*)', mr_text)
        title = title_match.group(2).strip() if title_match else ''
        return {'merge_request_info': {'title': title}, 'raw_text': mr_text}
