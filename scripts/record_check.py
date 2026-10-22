"""Record a successful release check monthly without rebuilding documentation."""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BRANCH = "automation/release-checks"


def record_check(api, repository, release_id, tag, changed, run_url, now):
    # Authenticate against the repository before treating a missing ref as new.
    api("GET", "")
    ref = api("GET", f"git/ref/heads/{BRANCH}")
    previous = ref["object"]["sha"] if ref else None
    if previous:
        commit = api("GET", f"git/commits/{previous}")
        committed = datetime.fromisoformat(
            commit["committer"]["date"].replace("Z", "+00:00")
        )
        if now - committed < timedelta(days=30):
            print("Release check audit is current; no repository write needed.")
            return False

    snapshot = {
        "checked_at": now.isoformat().replace("+00:00", "Z"),
        "release_id": int(release_id),
        "tag": tag,
        "changed": changed,
        "run_url": run_url,
    }
    # A tree with no base_tree contains only this small audit, never site HTML.
    tree = api(
        "POST",
        "git/trees",
        {
            "tree": [
                {
                    "path": "release-check.json",
                    "mode": "100644",
                    "type": "blob",
                    "content": json.dumps(snapshot, indent=2) + "\n",
                }
            ]
        },
    )
    commit = api(
        "POST",
        "git/commits",
        {
            "message": "chore: record successful release check",
            "tree": tree["sha"],
            "parents": [previous] if previous else [],
        },
    )
    if previous:
        api("PATCH", f"git/refs/heads/{BRANCH}", {"sha": commit["sha"], "force": False})
    else:
        api("POST", "git/refs", {"ref": f"refs/heads/{BRANCH}", "sha": commit["sha"]})
    print(f"Recorded successful release check on {repository}:{BRANCH}.")
    return True


class GitHubAPI:
    def __init__(self, repository, token):
        self.base = f"{os.environ.get('GITHUB_API_URL', 'https://api.github.com')}/repos/{repository}"
        self.token = token

    def __call__(self, method, path, body=None):
        request = urllib.request.Request(
            self.base + ("/" + path if path else ""),
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if (
                error.code == 404
                and method == "GET"
                and path == f"git/ref/heads/{BRANCH}"
            ):
                return None
            raise


def main():
    repository = os.environ["GITHUB_REPOSITORY"]
    record_check(
        GitHubAPI(repository, os.environ["GH_TOKEN"]),
        repository,
        os.environ["RELEASE_ID"],
        os.environ["RELEASE_TAG"],
        os.environ["RELEASE_CHANGED"] == "true",
        f"{os.environ['GITHUB_SERVER_URL']}/{repository}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
        datetime.now(timezone.utc),
    )


if __name__ == "__main__":
    main()
