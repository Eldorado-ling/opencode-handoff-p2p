import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import verify_inbox as verifier


class SkillMetadataTests(unittest.TestCase):
    def test_opencode_frontmatter_stays_discoverable(self):
        skill_path = Path(__file__).resolve().parents[1] / "SKILL.md"
        lines = skill_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "---")
        end = lines.index("---", 1)
        fields = dict(line.split(": ", 1) for line in lines[1:end])
        self.assertEqual(fields["name"], skill_path.parent.name)
        self.assertRegex(fields["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertGreaterEqual(len(fields["description"]), 1)
        self.assertLessEqual(len(fields["description"]), 1024)


class InputValidationTests(unittest.TestCase):
    def test_accepts_valid_github_usernames(self):
        for username in ("a", "Alice", "alice-2", "a" * 39):
            with self.subTest(username=username):
                self.assertTrue(verifier.is_valid_username(username))

    def test_rejects_invalid_github_usernames(self):
        for username in ("", "-alice", "alice-", "alice--bob", "alice_bob", "a" * 40):
            with self.subTest(username=username):
                self.assertFalse(verifier.is_valid_username(username))

    def test_parses_repo_and_supported_remote_forms(self):
        expected = ("alice", "handoff.inbox")
        self.assertEqual(verifier.parse_repo("Alice/Handoff.Inbox"), expected)
        for remote in (
            "https://github.com/Alice/Handoff.Inbox.git",
            "git@github.com:Alice/Handoff.Inbox.git",
            "ssh://git@github.com/Alice/Handoff.Inbox.git",
        ):
            with self.subTest(remote=remote):
                self.assertEqual(verifier.parse_github_remote(remote), expected)

    def test_rejects_malformed_repo_values(self):
        for repo in ("alice", "alice/a/b", "-alice/inbox", "alice/..", "alice/in box"):
            with self.subTest(repo=repo):
                self.assertIsNone(verifier.parse_repo(repo))

    def test_tier_1_requires_root_file_real_timestamp_and_valid_sender(self):
        valid = "2026-07-11T12-34-56Z--from-Alice-2.txt"
        self.assertEqual(verifier.verify_tier_1(valid), "alice-2")
        for filename in (
            f"nested/{valid}",
            f"nested\\{valid}",
            "2026-02-30T12-34-56Z--from-alice.txt",
            "2026-07-11T25-34-56Z--from-alice.txt",
            "2026-07-11T12-34-56Z--from-alice--2.txt",
        ):
            with self.subTest(filename=filename):
                self.assertIsNone(verifier.verify_tier_1(filename))

    def test_accepts_current_and_legacy_share_urls(self):
        for url in (
            b"https://opncd.ai/share/Abc_123-xyz\n",
            b"https://opncd.ai/s/Abc123\r\n",
            b"https://opencode.ai/s/Abc123/\n",
        ):
            with self.subTest(url=url):
                self.assertIsNotNone(verifier.URL_RE.fullmatch(url))

    def test_rejects_non_https_or_unapproved_share_hosts(self):
        for url in (
            b"http://opncd.ai/share/abc\n",
            b"https://evil.example/share/abc\n",
            b"https://opncd.ai/share/abc?x=1\n",
            b"https://opncd.ai/share/abc\nextra\n",
        ):
            with self.subTest(url=url):
                self.assertIsNone(verifier.URL_RE.fullmatch(url))


class TrustConfigurationTests(unittest.TestCase):
    def write_trust(self, value):
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / "trust.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        self.addCleanup(temp.cleanup)
        return path

    def test_loads_and_normalizes_valid_trust_config(self):
        path = self.write_trust(
            {"trusted_senders": ["Alice", "bob"], "require_signed_commits": True}
        )
        self.assertEqual(verifier.load_trust(path), ({"alice", "bob"}, True))

    def test_rejects_invalid_trusted_sender(self):
        path = self.write_trust(
            {"trusted_senders": ["alice--bob"], "require_signed_commits": True}
        )
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            verifier.load_trust(path)

    def test_rejects_non_boolean_signature_setting(self):
        path = self.write_trust(
            {"trusted_senders": ["alice"], "require_signed_commits": "true"}
        )
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            verifier.load_trust(path)


class FailureHandlingTests(unittest.TestCase):
    @mock.patch.object(verifier, "run", return_value=(1, b"", b"fatal: broken index"))
    def test_git_list_failure_is_not_reported_as_empty_inbox(self, _run):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            verifier.list_inbox_files(Path("inbox"))
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["skill_status"], "git_list_fail")
        self.assertIn("broken index", payload["skill_status_detail"])

    @mock.patch("verify_inbox.subprocess.run")
    def test_command_timeout_has_distinct_exit_code(self, run_mock):
        run_mock.side_effect = subprocess.TimeoutExpired(["gh", "api"], 1)
        rc, _stdout, stderr = verifier.run(["gh", "api"], timeout=1)
        self.assertEqual(rc, 124)
        self.assertIn(b"timed out", stderr)

    @mock.patch.object(verifier, "run", return_value=(0, b"not-a-sha\n", b""))
    def test_rejects_invalid_git_log_sha(self, _run):
        self.assertIsNone(verifier.get_last_modifying_sha(Path("inbox"), "message.txt"))


class PipelineTests(unittest.TestCase):
    def test_untrusted_sender_is_deleted_without_reading_content(self):
        with mock.patch.object(verifier, "verify_tier_3") as tier_3:
            result = verifier.process_file(
                Path("inbox"),
                "owner/inbox",
                "2026-07-11T12-34-56Z--from-mallory.txt",
                {"alice"},
                True,
            )
        self.assertEqual(result["action"], "delete")
        self.assertEqual(result["tier_failed"], 2)
        tier_3.assert_not_called()

    @mock.patch.object(verifier, "verify_tier_5", return_value=True)
    @mock.patch.object(verifier, "verify_tier_4", return_value=(True, "alice", "alice"))
    @mock.patch.object(verifier, "get_last_modifying_sha", return_value="a" * 40)
    @mock.patch.object(
        verifier,
        "verify_tier_3",
        return_value=(True, "https://opncd.ai/s/Abc_123"),
    )
    def test_valid_signed_handoff_is_consumed(self, _tier_3, _sha, _tier_4, _tier_5):
        result = verifier.process_file(
            Path("inbox"),
            "owner/inbox",
            "2026-07-11T12-34-56Z--from-alice.txt",
            {"alice"},
            True,
        )
        self.assertEqual(result["action"], "consume")
        self.assertTrue(result["signature_verified"])
        self.assertEqual(result["url"], "https://opncd.ai/s/Abc_123")


class GitInboxIntegrationTests(unittest.TestCase):
    def git(self, repo, *args):
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            check=True,
        )
        return completed.stdout.decode("utf-8", "replace").strip()

    def test_real_git_blob_and_last_modifying_commit_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "inbox"
            repo.mkdir()
            self.git(repo, "init", "-b", "main")
            self.git(repo, "config", "user.name", "Alice")
            self.git(repo, "config", "user.email", "alice@example.test")
            self.git(repo, "config", "commit.gpgsign", "false")
            self.git(
                repo,
                "remote",
                "add",
                "origin",
                "https://github.com/alice/opencode-handoff-inbox.git",
            )

            filename = "2026-07-11T12-34-56Z--from-alice.txt"
            message = repo / filename
            message.write_bytes(b"https://opncd.ai/s/Abc_123\n")
            self.git(repo, "add", "--", filename)
            self.git(repo, "commit", "-m", "handoff 1")
            first_sha = self.git(repo, "rev-parse", "HEAD")

            self.assertEqual(verifier.list_inbox_files(repo), [filename])
            self.assertEqual(
                verifier.verify_tier_3(repo, filename),
                (True, "https://opncd.ai/s/Abc_123"),
            )
            self.assertEqual(
                verifier.get_origin_repo(repo),
                ("alice", "opencode-handoff-inbox"),
            )

            with mock.patch.object(
                verifier,
                "verify_tier_4",
                return_value=(True, "alice", "alice"),
            ), mock.patch.object(verifier, "verify_tier_5", return_value=True):
                result = verifier.process_file(
                    repo,
                    "alice/opencode-handoff-inbox",
                    filename,
                    {"alice"},
                    True,
                )
            self.assertEqual(result["action"], "consume")
            self.assertTrue(result["signature_verified"])

            message.write_bytes(b"https://opncd.ai/share/Next-2\n")
            self.git(repo, "add", "--", filename)
            self.git(repo, "commit", "-m", "handoff modified")
            second_sha = self.git(repo, "rev-parse", "HEAD")
            self.assertNotEqual(first_sha, second_sha)
            self.assertEqual(
                verifier.get_last_modifying_sha(repo, filename),
                second_sha,
            )

            nested = "quarantine/2026-07-11T12-35-00Z--from-alice.txt"
            (repo / "quarantine").mkdir()
            (repo / nested).write_bytes(b"https://opncd.ai/s/Nested\n")
            self.git(repo, "add", "--", nested)
            self.git(repo, "commit", "-m", "nested path")
            nested_result = verifier.process_file(
                repo,
                "alice/opencode-handoff-inbox",
                nested,
                {"alice"},
                True,
            )
            self.assertEqual(nested_result["action"], "keep")
            self.assertEqual(nested_result["tier_failed"], 1)


if __name__ == "__main__":
    unittest.main()
