"""Exercise the updater with temporary repositories and fake application bundles."""

import sys
sys.dont_write_bytecode = True

import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("update_sidebar", Path(__file__).parents[1] / "update-sidebar.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


def bundle(path, marker, bundle_id=updater.BUNDLE_ID):
    (path / "Contents").mkdir(parents=True)
    with (path / "Contents/Info.plist").open("wb") as stream:
        plistlib.dump({"CFBundleIdentifier": bundle_id}, stream)
    (path / "marker").write_text(marker)
    return path


class AppInstallationTests(unittest.TestCase):
    def test_success_retains_previous_app_and_leaves_data_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = bundle(root / "Applications/T3 Code Sidebar.app", "old")
            prepared = bundle(root / "build/T3 Code Sidebar.app", "new")
            data = root / "userdata"
            data.mkdir()
            (data / "chat").write_text("existing conversation")
            def command(*args, **kwargs):
                if args[0] == "ditto":
                    shutil.copytree(args[1], args[2])
            with patch.object(updater, "run", side_effect=command):
                previous = updater.install_app(prepared, app, root / "setup", "test")
            self.assertEqual((app / "marker").read_text(), "new")
            self.assertEqual((previous / "marker").read_text(), "old")
            self.assertEqual((data / "chat").read_text(), "existing conversation")

    def test_verification_failure_restores_installed_app(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = bundle(root / "Applications/T3 Code Sidebar.app", "old")
            prepared = bundle(root / "build/T3 Code Sidebar.app", "new")
            def command(*args, **kwargs):
                if args[0] == "ditto":
                    shutil.copytree(args[1], args[2])
                if args[0] == "codesign" and args[-1] == app:
                    raise subprocess.CalledProcessError(1, "codesign")
            with patch.object(updater, "run", side_effect=command):
                with self.assertRaises(subprocess.CalledProcessError):
                    updater.install_app(prepared, app, root / "setup", "test")
            self.assertEqual((app / "marker").read_text(), "old")

    def test_wrong_bundle_is_rejected_before_installed_app_is_moved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = bundle(root / "Applications/T3 Code Sidebar.app", "old")
            prepared = bundle(root / "build/T3 Code Sidebar.app", "wrong", "com.t3tools.t3code")
            def command(*args, **kwargs):
                if args[0] == "ditto":
                    shutil.copytree(args[1], args[2])
            with patch.object(updater, "run", side_effect=command):
                with self.assertRaises(updater.UpdateError):
                    updater.install_app(prepared, app, root / "setup", "test")
            self.assertEqual((app / "marker").read_text(), "old")


class RetireBundlesTests(unittest.TestCase):
    def test_only_installed_app_remains(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            previous = bundle(root / "recovery/before-update-test/T3 Code Sidebar.app", "old")
            prepared = bundle(root / "build/updater-prepared/T3 Code Sidebar.app", "new")
            (root / "build/release").mkdir()
            (root / "build/build.log").write_text("log")
            with patch.object(updater.subprocess, "run"):
                updater.retire_bundles(previous, prepared)
            self.assertFalse((root / "recovery/before-update-test").exists())
            self.assertFalse((root / "build/updater-prepared").exists())
            self.assertFalse((root / "build/release").exists())
            self.assertTrue((root / "build/build.log").exists())


class ShutdownTests(unittest.TestCase):
    def test_open_app_prevents_installation_without_signalling_it(self):
        with patch.object(updater, "sidebar_is_running", return_value=True), patch.object(updater.os, "kill") as signal:
            with self.assertRaises(updater.UpdateError):
                updater.ensure_closed(Path("/unused"))
            signal.assert_not_called()

    def test_server_must_be_stopped_even_when_window_is_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / "userdata").mkdir()
            (home / "userdata/server-runtime.json").write_text(json.dumps({"pid": 12345}))
            with patch.object(updater, "sidebar_is_running", return_value=False), patch.object(updater.os, "kill") as signal:
                with self.assertRaises(updater.UpdateError):
                    updater.ensure_closed(home)
                signal.assert_called_once_with(12345, 0)
            with patch.object(updater, "sidebar_is_running", return_value=False), patch.object(updater.os, "kill", side_effect=ProcessLookupError):
                updater.ensure_closed(home)


class PublishingTests(unittest.TestCase):
    def test_commits_and_pushes_source_and_stops_on_rejected_push(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote = root / "remote.git"
            repo = root / "checkout"
            upstream = root / "other-checkout"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-b", "sidebar-test", str(repo)], check=True, capture_output=True)
            for key, value in (("user.name", "Updater Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false")):
                updater.git(repo, "config", key, value)
            updater.git(repo, "remote", "add", "origin", str(remote))
            (repo / ".gitignore").write_text(".env.local\n")
            (repo / ".env.local").write_text("private fixture")
            (repo / "source.txt").write_text("first change")
            sha = updater.publish_source(repo, "sidebar-test", "feat: test update")
            self.assertEqual(updater.git(repo, "ls-remote", "origin", "refs/heads/sidebar-test").split()[0], sha)
            self.assertNotIn(".env.local", updater.git(repo, "ls-files").splitlines())
            self.assertEqual(updater.git(repo, "status", "--porcelain"), "")
            subprocess.run(["git", "clone", "-b", "sidebar-test", str(remote), str(upstream)], check=True, capture_output=True)
            for key, value in (("user.name", "Updater Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false")):
                updater.git(upstream, "config", key, value)
            (upstream / "source.txt").write_text("remote update")
            updater.git(upstream, "commit", "-am", "remote change")
            updater.git(upstream, "push", "origin", "sidebar-test")
            (repo / "source.txt").write_text("local update")
            with self.assertRaises(subprocess.CalledProcessError):
                updater.publish_source(repo, "sidebar-test", "feat: local change")
            self.assertEqual((repo / "source.txt").read_text(), "local update")

    def test_source_changes_after_publish_are_detected(self):
        with patch.object(updater, "git", side_effect=["expected", " M source.txt"]):
            with self.assertRaises(updater.UpdateError):
                updater.require_clean_source(Path("/unused"), "expected")


def init_repo(path, branch):
    subprocess.run(["git", "init", "-b", branch, str(path)], check=True, capture_output=True)
    for key, value in (("user.name", "Updater Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false")):
        updater.git(path, "config", key, value)


def commit_file(repo, name, text, tag=None):
    (repo / name).write_text(text)
    updater.git(repo, "add", name)
    updater.git(repo, "commit", "-m", f"change {name}")
    if tag:
        updater.git(repo, "tag", tag)


class UpstreamMergeTests(unittest.TestCase):
    def fork_of_upstream(self, root):
        upstream = root / "upstream"
        init_repo(upstream, "main")
        commit_file(upstream, "base.txt", "base", "v0.1.0")
        fork = root / "fork"
        subprocess.run(["git", "clone", "-b", "main", str(upstream), str(fork)], check=True, capture_output=True)
        init_repo(fork, "main")
        updater.git(fork, "remote", "add", "upstream", str(upstream))
        updater.git(fork, "switch", "-c", "sidebar")
        return upstream, fork

    def test_merges_newest_stable_tag_and_ignores_prereleases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            upstream, fork = self.fork_of_upstream(root)
            commit_file(fork, "custom.txt", "mine")
            commit_file(upstream, "nine.txt", "9", "v0.1.9")
            commit_file(upstream, "ten.txt", "10", "v0.1.10")
            commit_file(upstream, "nightly.txt", "n", "v0.1.11-nightly.20261027.1")
            mine = updater.git(fork, "rev-parse", "HEAD")
            with patch.object(updater, "UPSTREAM_URLS", (str(upstream),)):
                self.assertEqual(updater.merge_upstream(fork), "v0.1.10")
                files = set(updater.git(fork, "ls-files").splitlines())
                self.assertEqual(files, {"base.txt", "custom.txt", "nine.txt", "ten.txt"})
                self.assertEqual(len(updater.git(fork, "rev-list", "--parents", "-1", "HEAD").split()), 3)
                self.assertEqual(updater.git(fork, "rev-parse", f"backup/sidebar-before-upstream-{updater.datetime.date.today():%Y%m%d}-{mine[:8]}"), mine)
                head = updater.git(fork, "rev-parse", "HEAD")
                self.assertEqual(updater.merge_upstream(fork), "v0.1.10")
                self.assertEqual(updater.git(fork, "rev-parse", "HEAD"), head)

    def test_conflict_aborts_merge_and_leaves_checkout_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            upstream, fork = self.fork_of_upstream(root)
            commit_file(fork, "base.txt", "fork edit")
            commit_file(upstream, "base.txt", "upstream edit", "v0.1.1")
            mine = updater.git(fork, "rev-parse", "HEAD")
            with patch.object(updater, "UPSTREAM_URLS", (str(upstream),)):
                with self.assertRaisesRegex(updater.UpdateError, "base.txt"):
                    updater.merge_upstream(fork)
            self.assertEqual(updater.git(fork, "rev-parse", "HEAD"), mine)
            self.assertEqual(updater.git(fork, "status", "--porcelain"), "")
            self.assertEqual((fork / "base.txt").read_text(), "fork edit")

    def test_refuses_an_unofficial_upstream_remote(self):
        with tempfile.TemporaryDirectory() as temp:
            upstream, fork = self.fork_of_upstream(Path(temp))
            with self.assertRaises(updater.UpdateError):
                updater.merge_upstream(fork)


class PipelineTests(unittest.TestCase):
    def test_push_failure_prevents_build_backup_and_install(self):
        with patch.object(sys, "argv", ["update-sidebar.py", "--message", "test"]), \
             patch.object(updater, "preflight", return_value="test"), \
             tempfile.TemporaryDirectory() as temp, \
             patch.object(updater, "SETUP", Path(temp)), \
             patch.object(updater, "publish_source", side_effect=updater.UpdateError("push failed")), \
             patch.object(updater, "build_app") as build, \
             patch.object(updater, "backup_data") as backup, \
             patch.object(updater, "install_app") as install:
            with self.assertRaises(updater.UpdateError):
                updater.main()
            build.assert_not_called()
            backup.assert_not_called()
            install.assert_not_called()

    def test_backup_failure_preserves_installed_app(self):
        with patch.object(sys, "argv", ["update-sidebar.py", "--message", "test"]), \
             patch.object(updater, "preflight", return_value="test"), \
             tempfile.TemporaryDirectory() as temp, \
             patch.object(updater, "SETUP", Path(temp)), \
             patch.object(updater, "publish_source", return_value="abc123"), \
             patch.object(updater, "build_app", return_value=Path(temp) / "prepared.app"), \
             patch.object(updater, "wait_for_close"), \
             patch.object(updater, "backup_data", side_effect=updater.UpdateError("backup failed")), \
             patch.object(updater, "install_app") as install:
            with self.assertRaises(updater.UpdateError):
                updater.main()
            install.assert_not_called()

    def test_merge_conflict_prevents_push_build_and_install(self):
        with patch.object(sys, "argv", ["update-sidebar.py", "--upstream", "--message", "test"]), \
             patch.object(updater, "preflight", return_value="test"), \
             tempfile.TemporaryDirectory() as temp, \
             patch.object(updater, "SETUP", Path(temp)), \
             patch.object(updater, "commit_source"), \
             patch.object(updater, "merge_upstream", side_effect=updater.UpdateError("conflict")), \
             patch.object(updater, "publish_source") as publish, \
             patch.object(updater, "build_app") as build, \
             patch.object(updater, "install_app") as install:
            with self.assertRaises(updater.UpdateError):
                updater.main()
            publish.assert_not_called()
            build.assert_not_called()
            install.assert_not_called()


class LauncherTests(unittest.TestCase):
    def test_regenerating_launcher_keeps_git_ssh_setting(self):
        with tempfile.TemporaryDirectory() as temp:
            launcher = Path(temp) / "Applications/Update T3 Code Sidebar.command"
            launcher.parent.mkdir()
            launcher.write_text("#!/bin/zsh\nexport GIT_SSH_COMMAND='ssh -i key'\nexport PATH=old\n")
            with patch.object(updater.Path, "home", return_value=Path(temp)):
                updater.install_launcher(Path("/repo"))
            text = launcher.read_text()
            self.assertIn("export GIT_SSH_COMMAND='ssh -i key'\n", text)
            self.assertNotIn("PATH=old", text)
            self.assertIn("/repo/scripts/update-sidebar.py", text)

    def test_launcher_asks_whether_to_merge_upstream(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            stub = home / "python-stub"
            stub.write_text('#!/bin/sh\necho "args:$*"\n')
            stub.chmod(0o755)
            with patch.object(updater.Path, "home", return_value=home), patch.object(updater.sys, "executable", str(stub)):
                updater.install_launcher(Path("/repo"))
            launcher = home / "Applications/Update T3 Code Sidebar.command"
            def answer(reply):
                return subprocess.run(["zsh", str(launcher)], input=f"{reply}\n\n", text=True,
                                      capture_output=True, check=True).stdout
            self.assertIn("args:/repo/scripts/update-sidebar.py --upstream", answer("y"))
            self.assertIn("args:/repo/scripts/update-sidebar.py\n", answer("n"))
            self.assertIn("args:/repo/scripts/update-sidebar.py\n", answer(""))


if __name__ == "__main__":
    unittest.main()
