"""Exercise audit branch updates without network access."""

import json
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from record_check import BRANCH, GitHubAPI, record_check


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 21, tzinfo=timezone.utc)
        self.calls = []
        self.responses = {}

    def api(self, method, path, body=None):
        self.calls.append((method, path, body))
        return self.responses[(method, path)]

    def run_check(self):
        return record_check(
            self.api,
            "FastLED/dox",
            "416153555",
            "3.10.8",
            False,
            "https://github.com/FastLED/dox/actions/runs/123",
            self.now,
        )

    def prepare_write(self):
        self.responses["POST", "git/trees"] = {"sha": "tree123"}
        self.responses["POST", "git/commits"] = {"sha": "commit123"}

    def test_missing_branch_creates_orphan_snapshot(self):
        self.responses["GET", ""] = {"full_name": "FastLED/dox"}
        self.responses["GET", "git/ref/heads/automation/release-checks"] = None
        self.prepare_write()
        self.responses["POST", "git/refs"] = {}
        self.assertTrue(self.run_check())
        tree = next(body for method, path, body in self.calls if path == "git/trees")
        self.assertEqual(len(tree["tree"]), 1)
        self.assertEqual(tree["tree"][0]["path"], "release-check.json")
        snapshot = json.loads(tree["tree"][0]["content"])
        self.assertEqual(snapshot["release_id"], 416153555)
        self.assertEqual(snapshot["tag"], "3.10.8")
        self.assertFalse(snapshot["changed"])
        commit = next(
            body for method, path, body in self.calls if path == "git/commits"
        )
        self.assertEqual(commit["parents"], [])
        self.assertEqual(
            self.calls[-1],
            (
                "POST",
                "git/refs",
                {
                    "ref": "refs/heads/automation/release-checks",
                    "sha": "commit123",
                },
            ),
        )
        self.assertEqual(self.calls[0], ("GET", "", None))

    def existing_branch(self, age):
        self.responses["GET", ""] = {"full_name": "FastLED/dox"}
        self.responses["GET", "git/ref/heads/automation/release-checks"] = {
            "object": {"sha": "previous"},
        }
        self.responses["GET", "git/commits/previous"] = {
            "committer": {"date": (self.now - age).isoformat()},
        }

    def test_recent_snapshot_does_not_write(self):
        self.existing_branch(timedelta(days=29, hours=23, minutes=59))
        self.assertFalse(self.run_check())
        self.assertTrue(all(method == "GET" for method, _, _ in self.calls))

    def test_thirty_day_snapshot_updates_without_force(self):
        self.existing_branch(timedelta(days=30))
        self.prepare_write()
        self.responses["PATCH", "git/refs/heads/automation/release-checks"] = {}
        self.assertTrue(self.run_check())
        commit = next(
            body for method, path, body in self.calls if path == "git/commits"
        )
        self.assertEqual(commit["parents"], ["previous"])
        self.assertEqual(
            self.calls[-1],
            (
                "PATCH",
                "git/refs/heads/automation/release-checks",
                {"sha": "commit123", "force": False},
            ),
        )

    def test_authentication_error_prevents_creation(self):
        # An unsuccessful repository lookup raises before any missing-ref handling.
        with self.assertRaises(KeyError):
            self.run_check()
        self.assertEqual(self.calls, [("GET", "", None)])


class APIErrorTests(unittest.TestCase):
    def test_only_missing_audit_ref_is_optional(self):
        api = GitHubAPI("FastLED/dox", "fixture-token")
        for method, path, status, optional in (
            ("GET", f"git/ref/heads/{BRANCH}", 404, True),
            ("GET", "", 404, False),
            ("GET", f"git/ref/heads/{BRANCH}", 403, False),
            ("POST", "git/refs", 404, False),
        ):
            with self.subTest(method=method, path=path, status=status):
                error = urllib.error.HTTPError(
                    "https://api.github.com", status, "fixture", {}, None
                )
                with patch("urllib.request.urlopen", side_effect=error):
                    if optional:
                        self.assertIsNone(api(method, path))
                    else:
                        with self.assertRaises(urllib.error.HTTPError):
                            api(method, path)


if __name__ == "__main__":
    unittest.main()
