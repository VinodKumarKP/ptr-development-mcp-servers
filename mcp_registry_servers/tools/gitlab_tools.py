import logging
import os
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlparse, quote

from git import Repo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GitLabError(Exception):
    pass


SKIP_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip',
    '.jar', '.class', '.pyc', '.exe', '.dll', '.so',
    '.md', '.json', '.xml', '.txt'
}


LANGUAGE_EXTENSIONS = {
    '.py': 'Python',
    '.js': 'JavaScript',
    '.ts': 'TypeScript',
    '.java': 'Java',
    '.go': 'Go',
    '.rs': 'Rust',
    '.rb': 'Ruby',
    '.php': 'PHP',
    '.sh': 'Shell',
    '.ps1': 'PowerShell',
    '.yaml': 'YAML',
    '.yml': 'YAML',
}


class GitLabTools:
    """Utility tools targeted at GitLab repositories intended for MCP exposure.

    This module mirrors the shape of existing GitHub helpers but targets GitLab
    APIs and URL formats where applicable.
    """

    def validate_git_url(self, git_url: str) -> bool:
        try:
            if git_url.startswith('git@'):
                # SSH form: git@host:namespace/project.git
                return True
            parsed = urlparse(git_url)
            return parsed.scheme in ('https', 'http', 'ssh', 'git') and bool(parsed.netloc)
        except Exception:
            return False

    def _ensure_dir(self, directory_path: Optional[str]) -> str:
        if directory_path:
            os.makedirs(directory_path, exist_ok=True)
            return directory_path
        return tempfile.mkdtemp()

    def clone_repository(self, git_url: str, branch: str = 'main', directory_path: Optional[str] = None) -> str:
        """Clone a Git repository with optional branch checkout and HTTPS token injection.

        - Supports HTTPS, HTTP, SSH URLs.
        - If HTTPS and no credentials present, injects oauth2 token from GITLAB_TOKEN (or GITLABTOKEN) when available.
        - Tries to clone directly with the requested branch; on failure, clones default branch and checks out origin/<branch> if present.
        """
        # Build destination
        dest = self._ensure_dir(directory_path)

        # Optionally inject token into HTTPS URL when no userinfo present
        try:
            parsed = urlparse(git_url)
            if parsed.scheme in ('https', 'http') and '@' not in git_url:
                token = os.environ.get('GITLAB_TOKEN') or os.environ.get('GITLABTOKEN')
                if token:
                    netloc = parsed.netloc
                    git_url = f"{parsed.scheme}://oauth2:{token}@{netloc}{parsed.path}"
        except Exception:
            # Best-effort; do not block clone on URL parsing issues
            pass

        # Sanitize URL for logs
        safe_url = git_url
        if 'oauth2:' in safe_url and '@' in safe_url:
            try:
                prefix, rest = safe_url.split('oauth2:', 1)
                token_part, suffix = rest.split('@', 1)
                safe_url = prefix + 'oauth2:' + '***' + '@' + suffix
            except Exception:
                pass

        logger.info(f"Cloning repo {safe_url} (branch={branch}) into {dest}")

        try:
            # Attempt clone with branch directly
            Repo.clone_from(git_url, dest, branch=branch)
            return dest
        except Exception as e_primary:
            logger.info(f"Direct clone with branch failed, trying default then checkout: {e_primary}")
            try:
                repo = Repo.clone_from(git_url, dest)
                try:
                    repo.git.fetch('--all')
                except Exception:
                    pass
                try:
                    repo.git.checkout('-B', branch, f'origin/{branch}')
                except Exception:
                    logger.info('Requested branch not found on remote, keeping default branch')
                return dest
            except Exception as e_fallback:
                # Cleanup on failure
                try:
                    if os.path.exists(dest):
                        shutil.rmtree(dest, ignore_errors=True)
                except Exception:
                    pass
                raise GitLabError(f"Repository cloning failed: {e_primary}") from e_fallback


    def get_file_list_helper(self, repo_path: str) -> List[str]:
        file_list = []
        repo_path = Path(repo_path)
        try:
            for path in repo_path.rglob('*'):
                if path.is_dir():
                    continue
                if '.git' in path.parts:
                    continue
                if any(part.startswith('.') for part in path.parts):
                    continue
                if path.suffix.lower() in SKIP_EXTENSIONS:
                    continue
                file_list.append(str(path.relative_to(repo_path)))
            return file_list
        except Exception as e:
            logger.error(f'Error getting file list: {e}')
            return []

    def get_git_stats(self, repo_path: str) -> Dict[str, Any]:
        try:
            repo = Repo(repo_path)
            commits = list(repo.iter_commits())
            contributors = {c.author.email for c in commits}

            file_list = self.get_file_list_helper(repo_path)

            stats = {
                'repository_path': repo_path,
                'current_branch': getattr(repo.head, 'reference', None) and repo.head.reference.name or None,
                'total_commits': len(commits),
                'total_contributors': len(contributors),
                'total_files': len(file_list),
            }
            if commits:
                stats['first_commit_date'] = commits[-1].committed_datetime.isoformat()
                stats['last_commit_date'] = commits[0].committed_datetime.isoformat()
            return stats
        except Exception as e:
            logger.error(f'Error getting git stats: {e}')
            raise GitLabError('Failed to get git stats') from e

    def identify_programming_languages(self, repo_path: str) -> Dict[str, Any]:
        file_list = self.get_file_list_helper(repo_path)
        language_stats = Counter()
        for file in file_list:
            ext = Path(file).suffix.lower()
            if ext in LANGUAGE_EXTENSIONS:
                language_stats[LANGUAGE_EXTENSIONS[ext]] += 1

        total = sum(language_stats.values())
        result = {
            'total_code_files': total,
            'languages': {k: {'files': v, 'percentage': round((v / total) * 100, 2) if total else 0} for k, v in language_stats.items()},
            'primary_language': max(language_stats, key=language_stats.get) if language_stats else None
        }
        return result

    def cleanup_repository(self,
                           repo_path: str,
                           remove_git_dir: bool = True,
                           remove_large_files_over_mb: Optional[int] = None,
                           remove_repo_dir: bool = False,
                           preserve_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Perform safe cleanup operations on a cloned repository directory.

        Args:
            repo_path: Path to the cloned repository.
            remove_git_dir: If True, remove the .git directory.
            remove_large_files_over_mb: If set, remove files larger than this many MB.
            remove_repo_dir: If True, remove the entire repository directory (use with caution).
            preserve_files: Optional list of file names to skip when removing large files.

        Returns:
            dict: Summary with keys: removed_files_count, removed_bytes, removed_git_dir (bool), removed_repo_dir (bool), errors (list)
        """
        p = Path(repo_path)
        summary = {
            'removed_files_count': 0,
            'removed_bytes': 0,
            'removed_git_dir': False,
            'removed_repo_dir': False,
            'errors': []
        }

        try:
            if not p.exists():
                raise GitLabError(f"Path does not exist: {repo_path}")

            # Remove large files if requested
            if remove_large_files_over_mb is not None:
                threshold = int(remove_large_files_over_mb) * 1024 * 1024
                for f in p.rglob('*'):
                    try:
                        if not f.is_file():
                            continue
                        if preserve_files and f.name in preserve_files:
                            continue
                        size = f.stat().st_size
                        if size > threshold:
                            summary['removed_files_count'] += 1
                            summary['removed_bytes'] += size
                            f.unlink()
                    except Exception as e:
                        summary['errors'].append(str(e))

            # Remove .git directory
            git_dir = p / '.git'
            if remove_git_dir and git_dir.exists():
                try:
                    shutil.rmtree(git_dir)
                    summary['removed_git_dir'] = True
                except Exception as e:
                    summary['errors'].append(str(e))

            # Optionally remove entire repo directory
            if remove_repo_dir:
                # Safety: don't allow deleting root or home directories
                resolved = p.resolve()
                home = Path.home().resolve()
                if resolved == Path('/') or resolved == home or resolved.parents.__len__() == 0:
                    raise GitLabError('Refusing to remove protected directory')
                try:
                    shutil.rmtree(p)
                    summary['removed_repo_dir'] = True
                except Exception as e:
                    summary['errors'].append(str(e))

            return summary

        except Exception as e:
            summary['errors'].append(str(e))
            return summary

    # Helpers for GitLab API
    def _project_path_from_url(self, repo_url: str) -> str:
        # normalize to path used by GitLab API (URL-encoded namespace/project)
        if repo_url.startswith('git@'):
            # git@gitlab.com:namespace/project.git
            path = repo_url.split(':', 1)[1].replace('.git', '')
        else:
            parsed = urlparse(repo_url)
            path = parsed.path.strip('/').replace('.git', '')
        return quote_plus(path)

    # --- Minimal GitLab API helpers and branch creation tool ---
    def _api_base(self) -> str:
        host = os.environ.get('GITLAB_HOST', 'https://gitlab.com')
        return host.rstrip('/') + '/api/v4'

    def _token(self) -> str:
        token = os.environ.get('GITLAB_TOKEN') or os.environ.get('GITLABTOKEN')
        if not token:
            raise GitLabError('GITLAB_TOKEN is not set')
        return token

    def _headers(self) -> Dict[str, str]:
        return {
            'PRIVATE-TOKEN': self._token(),
            'Accept': 'application/json'
        }

    def _request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None):
        url = f"{self._api_base()}{path}"
        try:
            resp = requests.request(method=method, url=url, headers=self._headers(), params=params, json=json, timeout=30)
            if resp.status_code >= 400:
                raise GitLabError(f"GitLab API {method} {path} failed: {resp.status_code} {resp.text[:300]}")
            return resp
        except requests.RequestException as e:
            raise GitLabError(f"GitLab request error: {e}") from e

    def create_branch(self, repo: str, branch: str, ref: str = 'main') -> Dict[str, Any]:
        """Create a branch in a GitLab project.

        Args:
            repo: Repository URL (https/ssh) or 'namespace/project' path.
            branch: New branch name to create.
            ref: Source branch or commit SHA to branch from (default 'main').

        Returns:
            Dict with key 'branch' containing the branch payload.
        """
        # Resolve project path without double-encoding
        if repo.startswith('http') or repo.startswith('git@'):
            project_id = self._project_path_from_url(repo)
        else:
            project_id = quote_plus(repo.strip('/'))

        params = {
            'branch': branch,
            'ref': ref,
        }
        resp = self._request('POST', f'/projects/{project_id}/repository/branches', params=params)
        return {'branch': resp.json()}

    def list_branches(self, repo: str, search: Optional[str] = None) -> Dict[str, Any]:
        """List branches in a GitLab project.

        Args:
            repo: Repository URL or 'namespace/project'.
            search: Optional filter string.

        Returns:
            {'branches': [...]} list of branch objects.
        """
        if repo.startswith('http') or repo.startswith('git@'):
            project_id = self._project_path_from_url(repo)
        else:
            project_id = quote_plus(repo.strip('/'))

        params = {'search': search} if search else None
        resp = self._request('GET', f'/projects/{project_id}/repository/branches', params=params)
        return {'branches': resp.json()}

    def get_branch(self, repo: str, branch: str) -> Dict[str, Any]:
        """Get a single branch by name.

        Returns {'branch': {...}}
        """
        if repo.startswith('http') or repo.startswith('git@'):
            project_id = self._project_path_from_url(repo)
        else:
            project_id = quote_plus(repo.strip('/'))
        branch_enc = quote(branch, safe='')
        resp = self._request('GET', f'/projects/{project_id}/repository/branches/{branch_enc}')
        return {'branch': resp.json()}

    def delete_branch(self, repo: str, branch: str) -> Dict[str, Any]:
        """Delete a branch.

        Returns {'deleted': True, 'branch': name}
        """
        if repo.startswith('http') or repo.startswith('git@'):
            project_id = self._project_path_from_url(repo)
        else:
            project_id = quote_plus(repo.strip('/'))
        branch_enc = quote(branch, safe='')
        resp = self._request('DELETE', f'/projects/{project_id}/repository/branches/{branch_enc}')
        # GitLab typically returns 204 No Content on success
        return {'deleted': resp.status_code in (200, 202, 204), 'branch': branch}

    def clone_project(self, repo: str, branch: str = 'main', directory_path: Optional[str] = None) -> Dict[str, Any]:
        """Clone a GitLab project by URL or 'namespace/project' path.

        - If 'repo' is a URL (https/ssh), it's used as-is.
        - If 'repo' is a path like 'group/subgroup/project', an HTTPS URL is built using
          GITLAB_HOST (default https://gitlab.com). If GITLAB_TOKEN is set, it will be
          embedded as https://oauth2:<token>@host/... for private repo access.

        Returns: {'path': <local_path>, 'branch': <branch>} on success.
        """
        # Determine the git URL
        if repo.startswith('http') or repo.startswith('git@'):
            git_url = repo
        else:
            host = os.environ.get('GITLAB_HOST', 'https://gitlab.com').rstrip('/')
            parsed = urlparse(host)
            netloc = parsed.netloc or parsed.path  # tolerate hosts like 'gitlab.company.com'
            token = os.environ.get('GITLAB_TOKEN') or os.environ.get('GITLABTOKEN')
            # Only embed token for https; skip for ssh or plain http
            if parsed.scheme in ('https', 'http') and token:
                git_url = f"{parsed.scheme}://oauth2:{token}@{netloc}/{repo.strip('/')}.git"
            else:
                scheme = parsed.scheme if parsed.scheme else 'https'
                git_url = f"{scheme}://{netloc}/{repo.strip('/')}.git"

        local_path = self.clone_repository(git_url, branch=branch, directory_path=directory_path)
        return {'path': local_path, 'branch': branch}

    # --- Minimal GitLab API helpers ---
    def _api_base(self) -> str:
        host = os.environ.get('GITLAB_HOST', 'https://gitlab.com')
        # ensure no trailing slash
        return host.rstrip('/') + '/api/v4'

    def _token(self) -> str:
        token = os.environ.get('GITLAB_TOKEN') or os.environ.get('GITLABTOKEN')
        if not token:
            raise GitLabError('GITLAB_TOKEN is not set')
        return token

    def _headers(self) -> Dict[str, str]:
        return {
            'PRIVATE-TOKEN': self._token(),
            'Accept': 'application/json'
        }

    def _request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None):
        url = f"{self._api_base()}{path}"
        try:
            resp = requests.request(method=method, url=url, headers=self._headers(), params=params, json=json, timeout=30)
            if resp.status_code >= 400:
                # include a short message but avoid huge payloads
                msg = resp.text[:500]
                raise GitLabError(f"GitLab API {method} {path} failed: {resp.status_code} {msg}")
            return resp
        except requests.RequestException as e:
            raise GitLabError(f"GitLab request error: {e}") from e

    # --- Tool: create a merge request ---
    def create_merge_request(
        self,
        repo: str,
        source_branch: str,
        target_branch: str,
        title: str,
        description: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a Merge Request in GitLab.

        Args:
            repo: Repository URL (https/ssh) or 'namespace/project' path.
            source_branch: The branch you want to merge from.
            target_branch: The branch you want to merge into.
            title: Merge request title.
            description: Optional description/body.
            options: Optional fields such as assignee_ids, reviewer_ids, labels,
                     remove_source_branch, draft, squash, milestone_id, etc.

        Returns:
            Dict with key 'merge_request' containing the GitLab MR payload.
        """
        # Determine project id/path without double-encoding
        if repo.startswith('http') or repo.startswith('git@'):
            project_id = self._project_path_from_url(repo)
        else:
            # assume already a namespace/project path
            project_id = quote_plus(repo.strip('/'))

        payload: Dict[str, Any] = {
            'source_branch': source_branch,
            'target_branch': target_branch,
            'title': title,
        }
        if description:
            payload['description'] = description
        if options:
            # shallow merge, allow only known-safe primitives
            for k, v in options.items():
                payload[k] = v

        resp = self._request('POST', f'/projects/{project_id}/merge_requests', json=payload)
        data = resp.json()
        return {'merge_request': data, 'web_url': data.get('web_url')}

    # ---------------- Issue Management Tools ----------------
    def create_issue(
        self,
        repo: str,
        title: str,
        description: Optional[str] = None,
        labels: Optional[str] = None,
        assignee_ids: Optional[str] = None,
        milestone_id: Optional[int] = None,
        due_date: Optional[str] = None,
        confidential: bool = False,
    ) -> Dict[str, Any]:
        """Create an issue in a GitLab project.

        Args:
            repo: Repository URL (https/ssh) or 'namespace/project' path.
            title: Issue title (required).
            description: Issue description/body (optional).
            labels: Comma-separated label names, e.g., "bug,urgent" (optional).
            assignee_ids: Comma-separated assignee user IDs, e.g., "123,456" (optional).
            milestone_id: Milestone ID to associate with the issue (optional).
            due_date: Due date in YYYY-MM-DD format (optional).
            confidential: Mark issue as confidential (default False).

        Returns:
            Dict with keys 'issue' (full issue data) and 'web_url'.
        """
        project_id = self._resolve_project_id(repo)

        payload: Dict[str, Any] = {
            'title': title,
        }
        
        if description:
            payload['description'] = description
        if labels:
            payload['labels'] = labels
        if assignee_ids:
            # Convert comma-separated string to list of integers
            try:
                payload['assignee_ids'] = [int(id.strip()) for id in assignee_ids.split(',') if id.strip()]
            except ValueError:
                raise GitLabError("assignee_ids must be comma-separated integers")
        if milestone_id is not None:
            payload['milestone_id'] = milestone_id
        if due_date:
            payload['due_date'] = due_date
        if confidential:
            payload['confidential'] = True

        resp = self._request('POST', f'/projects/{project_id}/issues', json=payload)
        data = resp.json()
        return {
            'issue': data,
            'web_url': data.get('web_url'),
            'iid': data.get('iid'),
            'id': data.get('id')
        }

    def update_issue(
        self,
        repo: str,
        issue_iid: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        labels: Optional[str] = None,
        state_event: Optional[str] = None,
        assignee_ids: Optional[str] = None,
        milestone_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Update an existing issue.

        Args:
            repo: Repository URL or 'namespace/project' path.
            issue_iid: Issue IID (internal ID visible in UI).
            title: New title (optional).
            description: New description (optional).
            labels: Comma-separated labels to set (replaces existing).
            state_event: 'close' or 'reopen' (optional).
            assignee_ids: Comma-separated assignee user IDs (optional).
            milestone_id: Milestone ID (optional).

        Returns:
            Dict with updated issue data.
        """
        project_id = self._resolve_project_id(repo)

        payload: Dict[str, Any] = {}
        if title:
            payload['title'] = title
        if description:
            payload['description'] = description
        if labels:
            payload['labels'] = labels
        if state_event in ['close', 'reopen']:
            payload['state_event'] = state_event
        if assignee_ids:
            try:
                payload['assignee_ids'] = [int(id.strip()) for id in assignee_ids.split(',') if id.strip()]
            except ValueError:
                raise GitLabError("assignee_ids must be comma-separated integers")
        if milestone_id is not None:
            payload['milestone_id'] = milestone_id

        resp = self._request('PUT', f'/projects/{project_id}/issues/{issue_iid}', json=payload)
        return {'issue': resp.json()}

    def close_issue(self, repo: str, issue_iid: int) -> Dict[str, Any]:
        """Close an issue.

        Args:
            repo: Repository URL or 'namespace/project' path.
            issue_iid: Issue IID.

        Returns:
            Dict with updated issue data.
        """
        return self.update_issue(repo, issue_iid, state_event='close')

    def list_issues(
        self,
        repo: str,
        state: str = 'opened',
        labels: Optional[str] = None,
        milestone: Optional[str] = None,
        assignee_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List issues in a project.

        Args:
            repo: Repository URL or 'namespace/project' path.
            state: 'opened', 'closed', or 'all' (default 'opened').
            labels: Comma-separated label names to filter.
            milestone: Milestone title to filter.
            assignee_id: Filter by assignee user ID.

        Returns:
            Dict with 'issues' list.
        """
        project_id = self._resolve_project_id(repo)

        params: Dict[str, Any] = {'state': state}
        if labels:
            params['labels'] = labels
        if milestone:
            params['milestone'] = milestone
        if assignee_id is not None:
            params['assignee_id'] = assignee_id

        resp = self._request('GET', f'/projects/{project_id}/issues', params=params)
        return {'issues': resp.json()}

    # ---------------- Discussion/Notes Management Tools ----------------
    def create_issue_note(
        self,
        repo: str,
        issue_iid: int,
        body: str,
        confidential: bool = False,
    ) -> Dict[str, Any]:
        """Add a new note (comment) to an issue.

        Args:
            repo: Repository URL or 'namespace/project' path.
            issue_iid: Issue IID.
            body: Note content (markdown supported).
            confidential: Make note confidential (default False).

        Returns:
            Dict with 'note' containing the created note data.
        """
        project_id = self._resolve_project_id(repo)

        payload = {
            'body': body,
            'confidential': confidential,
        }

        resp = self._request('POST', f'/projects/{project_id}/issues/{issue_iid}/notes', json=payload)
        return {'note': resp.json()}

    def create_merge_request_note(
        self,
        repo: str,
        merge_request_iid: int,
        body: str,
        confidential: bool = False,
    ) -> Dict[str, Any]:
        """Add a new note (comment) to a merge request.

        Args:
            repo: Repository URL or 'namespace/project' path.
            merge_request_iid: Merge request IID.
            body: Note content (markdown supported).
            confidential: Make note confidential (default False).

        Returns:
            Dict with 'note' containing the created note data.
        """
        project_id = self._resolve_project_id(repo)

        payload = {
            'body': body,
            'confidential': confidential,
        }

        resp = self._request('POST', f'/projects/{project_id}/merge_requests/{merge_request_iid}/notes', json=payload)
        return {'note': resp.json()}

    def list_merge_request_discussions(
        self,
        repo: str,
        merge_request_iid: int,
    ) -> Dict[str, Any]:
        """List discussion items for a merge request.

        Args:
            repo: Repository URL or 'namespace/project' path.
            merge_request_iid: Merge request IID.

        Returns:
            Dict with 'discussions' list containing all discussion threads.
        """
        project_id = self._resolve_project_id(repo)
        resp = self._request('GET', f'/projects/{project_id}/merge_requests/{merge_request_iid}/discussions')
        return {'discussions': resp.json()}

    def list_issue_discussions(
        self,
        repo: str,
        issue_iid: int,
    ) -> Dict[str, Any]:
        """List discussion items for an issue.

        Args:
            repo: Repository URL or 'namespace/project' path.
            issue_iid: Issue IID.

        Returns:
            Dict with 'discussions' list containing all discussion threads.
        """
        project_id = self._resolve_project_id(repo)
        resp = self._request('GET', f'/projects/{project_id}/issues/{issue_iid}/discussions')
        return {'discussions': resp.json()}

    def update_merge_request_discussion_note(
        self,
        repo: str,
        merge_request_iid: int,
        discussion_id: str,
        note_id: int,
        body: str,
    ) -> Dict[str, Any]:
        """Modify an existing merge request thread note.

        Args:
            repo: Repository URL or 'namespace/project' path.
            merge_request_iid: Merge request IID.
            discussion_id: Discussion thread ID.
            note_id: Note ID within the discussion.
            body: Updated note content.

        Returns:
            Dict with updated note data.
        """
        project_id = self._resolve_project_id(repo)

        payload = {'body': body}

        resp = self._request(
            'PUT',
            f'/projects/{project_id}/merge_requests/{merge_request_iid}/discussions/{discussion_id}/notes/{note_id}',
            json=payload
        )
        return {'note': resp.json()}

    def create_merge_request_discussion_note(
        self,
        repo: str,
        merge_request_iid: int,
        discussion_id: str,
        body: str,
    ) -> Dict[str, Any]:
        """Add a new note to an existing merge request discussion thread.

        Args:
            repo: Repository URL or 'namespace/project' path.
            merge_request_iid: Merge request IID.
            discussion_id: Discussion thread ID to reply to.
            body: Note content.

        Returns:
            Dict with 'note' containing the created note data.
        """
        project_id = self._resolve_project_id(repo)

        payload = {'body': body}

        resp = self._request(
            'POST',
            f'/projects/{project_id}/merge_requests/{merge_request_iid}/discussions/{discussion_id}/notes',
            json=payload
        )
        return {'note': resp.json()}

    def create_merge_request_draft_note(
        self,
        repo: str,
        merge_request_iid: int,
        body: str,
        line_code: Optional[str] = None,
        file_path: Optional[str] = None,
        line_type: Optional[str] = None,
        new_line: Optional[int] = None,
        old_line: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a draft note for a merge request.

        Args:
            repo: Repository URL or 'namespace/project' path.
            merge_request_iid: Merge request IID.
            body: Draft note content.
            line_code: Line code for inline comments (optional).
            file_path: File path for file-specific comments (optional).
            line_type: 'new' or 'old' for diff comments (optional).
            new_line: New line number for diff comments (optional).
            old_line: Old line number for diff comments (optional).

        Returns:
            Dict with 'draft_note' containing the created draft data.
        """
        project_id = self._resolve_project_id(repo)

        payload = {'body': body}
        if line_code:
            payload['line_code'] = line_code
        if file_path:
            payload['file_path'] = file_path
        if line_type:
            payload['line_type'] = line_type
        if new_line is not None:
            payload['new_line'] = new_line
        if old_line is not None:
            payload['old_line'] = old_line

        resp = self._request('POST', f'/projects/{project_id}/merge_requests/{merge_request_iid}/draft_notes', json=payload)
        return {'draft_note': resp.json()}

    def update_merge_request_draft_note(
        self,
        repo: str,
        merge_request_iid: int,
        draft_note_id: int,
        body: str,
    ) -> Dict[str, Any]:
        """Update an existing draft note.

        Args:
            repo: Repository URL or 'namespace/project' path.
            merge_request_iid: Merge request IID.
            draft_note_id: Draft note ID to update.
            body: Updated draft note content.

        Returns:
            Dict with updated draft note data.
        """
        project_id = self._resolve_project_id(repo)

        payload = {'body': body}

        resp = self._request(
            'PUT',
            f'/projects/{project_id}/merge_requests/{merge_request_iid}/draft_notes/{draft_note_id}',
            json=payload
        )
        return {'draft_note': resp.json()}

    def delete_merge_request_draft_note(
        self,
        repo: str,
        merge_request_iid: int,
        draft_note_id: int,
    ) -> Dict[str, Any]:
        """Delete a draft note.

        Args:
            repo: Repository URL or 'namespace/project' path.
            merge_request_iid: Merge request IID.
            draft_note_id: Draft note ID to delete.

        Returns:
            Dict indicating deletion success.
        """
        project_id = self._resolve_project_id(repo)

        resp = self._request(
            'DELETE',
            f'/projects/{project_id}/merge_requests/{merge_request_iid}/draft_notes/{draft_note_id}'
        )
        return {'deleted': resp.status_code in (200, 202, 204), 'draft_note_id': draft_note_id}

    def publish_merge_request_draft_note(
        self,
        repo: str,
        merge_request_iid: int,
        draft_note_id: int,
    ) -> Dict[str, Any]:
        """Publish a single draft note.

        Args:
            repo: Repository URL or 'namespace/project' path.
            merge_request_iid: Merge request IID.
            draft_note_id: Draft note ID to publish.

        Returns:
            Dict with published note data.
        """
        project_id = self._resolve_project_id(repo)

        resp = self._request(
            'PUT',
            f'/projects/{project_id}/merge_requests/{merge_request_iid}/draft_notes/{draft_note_id}/publish'
        )
        return {'note': resp.json()}

    def list_merge_request_draft_notes(
        self,
        repo: str,
        merge_request_iid: int,
    ) -> Dict[str, Any]:
        """List all draft notes for a merge request.

        Args:
            repo: Repository URL or 'namespace/project' path.
            merge_request_iid: Merge request IID.

        Returns:
            Dict with 'draft_notes' list.
        """
        project_id = self._resolve_project_id(repo)
        resp = self._request('GET', f'/projects/{project_id}/merge_requests/{merge_request_iid}/draft_notes')
        return {'draft_notes': resp.json()}

    def publish_all_merge_request_draft_notes(
        self,
        repo: str,
        merge_request_iid: int,
    ) -> Dict[str, Any]:
        """Publish all draft notes for a merge request.

        Args:
            repo: Repository URL or 'namespace/project' path.
            merge_request_iid: Merge request IID.

        Returns:
            Dict indicating publish success.
        """
        project_id = self._resolve_project_id(repo)

        resp = self._request('POST', f'/projects/{project_id}/merge_requests/{merge_request_iid}/draft_notes/bulk_publish')
        return {'published': resp.status_code in (200, 201, 202)}

    # ---------------- Commit / File Change Tools ----------------
    def _resolve_project_id(self, repo: str) -> str:
        if repo.startswith('http') or repo.startswith('git@'):
            return self._project_path_from_url(repo)
        return quote_plus(repo.strip('/'))

    def _file_exists(self, project_id: str, branch: str, file_path: str) -> bool:
        fp_enc = quote_plus(file_path)
        try:
            _ = self._request('GET', f'/projects/{project_id}/repository/files/{fp_enc}', params={'ref': branch})
            return True
        except GitLabError:
            return False

    def commit_single_file(
        self,
        repo: str,
        branch: str,
        file_path: str,
        content: str,
        commit_message: str,
        action: str = 'upsert',  # create|update|delete|upsert
        encoding: str = 'text',  # text|base64
    ) -> Dict[str, Any]:
        """Commit a single file change to a branch.

        If action='upsert', the tool decides create vs update automatically.
        """
        project_id = self._resolve_project_id(repo)
        if action not in {'create', 'update', 'delete', 'upsert'}:
            raise GitLabError("Invalid action. Use create|update|delete|upsert")
        final_action = action
        if action == 'upsert':
            exists = self._file_exists(project_id, branch, file_path)
            final_action = 'update' if exists else 'create'

        if final_action == 'delete':
            actions = [{
                'action': 'delete',
                'file_path': file_path,
            }]
        else:
            actions = [{
                'action': final_action,
                'file_path': file_path,
                'content': content,
                'encoding': encoding,
            }]

        payload = {
            'branch': branch,
            'commit_message': commit_message,
            'actions': actions,
        }
        resp = self._request('POST', f'/projects/{project_id}/repository/commits', json=payload)
        return {'commit': resp.json(), 'branch': branch, 'file_path': file_path, 'action': final_action}

    def commit_files(
        self,
        repo: str,
        branch: str,
        commit_message: str,
        changes_json: str,
    ) -> Dict[str, Any]:
        """Commit multiple file changes in one commit.

        changes_json: JSON array of action objects, each:
          {
            "action": "create|update|delete|move|chmod",
            "file_path": "path/to/file",
            "content": "..." (omit for delete/move),
            "previous_path": "old/path" (for move),
            "encoding": "text|base64" (optional)
          }
        """
        project_id = self._resolve_project_id(repo)
        try:
            actions = json.loads(changes_json)
            if not isinstance(actions, list):
                raise ValueError('changes_json must decode to a list')
        except Exception as e:
            raise GitLabError(f'Invalid changes_json: {e}') from e

        # Basic validation and filtering of fields
        cleaned_actions: List[Dict[str, Any]] = []
        allowed_actions = {'create', 'update', 'delete', 'move', 'chmod'}
        for idx, act in enumerate(actions):
            if not isinstance(act, dict):
                raise GitLabError(f'Action at index {idx} is not an object')
            kind = act.get('action')
            if kind not in allowed_actions:
                raise GitLabError(f'Unsupported action "{kind}" at index {idx}')
            file_path = act.get('file_path')
            if not file_path:
                raise GitLabError(f'Missing file_path at index {idx}')
            cleaned: Dict[str, Any] = {'action': kind, 'file_path': file_path}
            if kind in {'create', 'update'}:
                if 'content' not in act:
                    raise GitLabError(f'Missing content for action {kind} at index {idx}')
                cleaned['content'] = act['content']
                if act.get('encoding') in {'text', 'base64'}:
                    cleaned['encoding'] = act['encoding']
            if kind == 'move':
                prev = act.get('previous_path')
                if not prev:
                    raise GitLabError(f'Missing previous_path for move at index {idx}')
                cleaned['previous_path'] = prev
            if kind == 'chmod':
                # GitLab expects 'execute_filemode' boolean for chmod; allow pass-through
                if 'execute_filemode' not in act:
                    raise GitLabError(f'Missing execute_filemode for chmod at index {idx}')
                cleaned['execute_filemode'] = bool(act['execute_filemode'])
            cleaned_actions.append(cleaned)

        payload = {
            'branch': branch,
            'commit_message': commit_message,
            'actions': cleaned_actions,
        }
        resp = self._request('POST', f'/projects/{project_id}/repository/commits', json=payload)
        return {'commit': resp.json(), 'branch': branch, 'actions_count': len(cleaned_actions)}
