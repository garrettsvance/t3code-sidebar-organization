#!/usr/bin/env python3
"""Update the local Sidebar installation using its existing isolated build setup."""

import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parent.parent
SETUP = Path.home() / "Library/Application Support/T3 Code Sidebar Setup"
APP = Path.home() / "Applications/T3 Code Sidebar.app"
DATA_HOME = Path.home() / ".t3-sidebar"
BUNDLE_ID = "com.garrettsvance.t3code.sidebar"
FORK = "github.com:garrettsvance/t3code-sidebar-organization.git"


class UpdateError(Exception):
    pass


def run(*args, cwd=None, env=None, capture=False):
    result = subprocess.run(
        [str(arg) for arg in args], cwd=cwd, env=env, check=True,
        text=True, stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else None


def git(repo, *args):
    return run("git", "-C", repo, *args, capture=True)


def preflight(repo, setup, app):
    if sys.platform != "darwin":
        raise UpdateError("This updater requires macOS.")
    for tool in ("git", "node", "codesign", "ditto", "osascript", "open"):
        if not shutil.which(tool):
            raise UpdateError(f"Missing required command: {tool}")
    for name in ("build.py", "snapshot.py", "export-chats.py"):
        if not (setup / name).is_file():
            raise UpdateError(f"Missing existing Sidebar setup tool: {setup / name}")
    if app.is_symlink() or not app.is_dir():
        raise UpdateError(f"Expected an installed app directory, not a symlink: {app}")
    validate_identity(app)
    remote = git(repo, "remote", "get-url", "--push", "origin")
    if remote not in (f"git@{FORK}", f"https://{FORK.replace(':', '/', 1)}"):
        raise UpdateError(f"origin must be Garrett's Sidebar GitHub fork; found {remote}")
    branch = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    if git(repo, "ls-files", "--unmerged"):
        raise UpdateError("Resolve merge conflicts before updating.")
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        if Path(git(repo, "rev-parse", "--path-format=absolute", "--git-path", marker)).exists():
            raise UpdateError("Finish the Git merge/rebase/cherry-pick before updating.")
    return branch


def publish_source(repo, branch, message):
    changes = git(repo, "status", "--short")
    if changes:
        print("Source changes to commit and push:\n" + changes, flush=True)
        if message is None:
            message = input("Commit message [chore(desktop): update sidebar app]: ").strip()
        message = message or "chore(desktop): update sidebar app"
        run("git", "-C", repo, "add", "--all")
        run("git", "-C", repo, "commit", "-m", message)
    sha = git(repo, "rev-parse", "HEAD")
    print(f"Pushing {branch} to origin before building…", flush=True)
    run("git", "-C", repo, "push", "origin", f"HEAD:refs/heads/{branch}")
    published = git(repo, "ls-remote", "origin", f"refs/heads/{branch}")
    if not published or published.split()[0] != sha:
        raise UpdateError("Could not verify the built commit on GitHub; stopping before build.")
    require_clean_source(repo, sha)
    return sha


def require_clean_source(repo, sha):
    if git(repo, "rev-parse", "HEAD") != sha or git(repo, "status", "--porcelain"):
        raise UpdateError("Source changed during the update. Nothing further will be installed; retry after saving your work.")


def build_app(setup, repo, env, sha):
    print("Building Sidebar; do not edit this checkout until the build finishes.", flush=True)
    output = None
    with subprocess.Popen(
        [sys.executable, str(setup / "build.py")], cwd=repo, env=env,
        text=True, stdout=subprocess.PIPE,
    ) as process:
        for line in process.stdout:
            print(line, end="", flush=True)
            candidate = Path(line.strip())
            if candidate.parent == setup and candidate.name.startswith("build-"):
                output = candidate
                print(f"Build progress: {output / 'build.log'}", flush=True)
        if process.wait() != 0:
            raise UpdateError("Build failed. The installed app is unchanged; inspect the build.log above.")
    require_clean_source(repo, sha)
    if output is None:
        raise UpdateError("Build did not report an output directory.")
    metadata = json.loads((output / "build-info.json").read_text())
    if metadata["commit"] != sha:
        raise UpdateError("Build metadata does not match the pushed commit.")
    archives = list((output / "release").glob("*.zip"))
    if len(archives) != 1:
        raise UpdateError(f"Expected one app ZIP in {output / 'release'}.")
    extracted = output / "updater-prepared"
    run("ditto", "-x", "-k", archives[0], extracted)
    prepared = extracted / "T3 Code Sidebar.app"
    validate_identity(prepared)
    run("codesign", "--force", "--deep", "--sign", "-", prepared)
    run("codesign", "--verify", "--deep", "--strict", prepared)
    return prepared


def validate_identity(app):
    with (app / "Contents/Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    if info.get("CFBundleIdentifier") != BUNDLE_ID:
        raise UpdateError(f"Refusing to replace/install an app with a different bundle ID: {app}")


def sidebar_is_running():
    # NSWorkspace reads running apps without controlling them or asking System Events for access.
    script = '''ObjC.import('AppKit');
const apps = $.NSWorkspace.sharedWorkspace.runningApplications;
let running = false;
for (let i = 0; i < apps.count; i++) {
  if (ObjC.unwrap(apps.objectAtIndex(i).bundleIdentifier) === 'com.garrettsvance.t3code.sidebar') running = true;
}
JSON.stringify(running);'''
    result = run("osascript", "-l", "JavaScript", "-e", script, capture=True)
    if result not in ("true", "false"):
        raise UpdateError("Could not determine whether Sidebar is running.")
    return result == "true"


def ensure_closed(data_home):
    if sidebar_is_running():
        raise UpdateError("Sidebar is still running. Finish active turns and quit Sidebar normally.")
    descriptor = data_home / "userdata/server-runtime.json"
    if descriptor.exists():
        state = json.loads(descriptor.read_text())
        pid = state.get("pid")
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 1:
            raise UpdateError("Invalid Sidebar server PID; inspect server-runtime.json before updating.")
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        # A stale but reused PID is deliberately conservative; never signal or stop it.
        raise UpdateError("Sidebar's recorded server is still running. Wait for normal shutdown, then retry.")


def wait_for_close(data_home):
    while True:
        try:
            ensure_closed(data_home)
            return
        except UpdateError as error:
            print(f"\n{error}", flush=True)
            if not sys.stdin.isatty():
                raise
            input("Once Sidebar is closed, press Return to back up and install (Ctrl-C cancels): ")


def backup_data(setup, data_home, stamp):
    destination = setup / "backups" / f"sidebar-update-{stamp}"
    run(sys.executable, setup / "snapshot.py", data_home, destination)
    run(sys.executable, setup / "export-chats.py", destination)
    return destination


def install_app(prepared, app, setup, stamp):
    if app.is_symlink():
        raise UpdateError(f"Refusing to replace a symlink: {app}")
    validate_identity(app)
    recovery = setup / "recovery" / f"before-update-{stamp}"
    recovery.mkdir(parents=True, exist_ok=False)
    previous = recovery / app.name
    # Both renames must stay on one filesystem; never delete the installed app to make room.
    if recovery.stat().st_dev != app.parent.stat().st_dev:
        raise UpdateError("App and recovery directory must be on the same filesystem.")
    with tempfile.TemporaryDirectory(prefix=".sidebar-update-", dir=app.parent) as staging:
        candidate = Path(staging) / app.name
        run("ditto", prepared, candidate)
        validate_identity(candidate)
        run("codesign", "--verify", "--deep", "--strict", candidate)
        try:
            app.rename(previous)
            candidate.rename(app)
            run("codesign", "--verify", "--deep", "--strict", app)
        except BaseException:
            if previous.exists():
                if app.exists():
                    app.rename(Path(staging) / "failed-install.app")
                previous.rename(app)
            raise
    return previous


def install_launcher(repo):
    launcher = Path.home() / "Applications/Update T3 Code Sidebar.command"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(
        '#!/bin/zsh\n'
        'export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.cargo/bin:$PATH"\n'
        f'{shlex.quote(sys.executable)} {shlex.quote(str(repo / "scripts/update-sidebar.py"))}\n'
        'sidebar_result=$?\n'
        'printf "\\nPress Return to close this window."\n'
        'read -r sidebar_reply\n'
        'exit "$sidebar_result"\n'
    )
    launcher.chmod(0o755)
    print(f"Installed launcher: {launcher}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only setup check; no commit, push, build, or install")
    parser.add_argument("--install-launcher", action="store_true", help="Install the double-click launcher only")
    parser.add_argument("--message", help="Commit message; otherwise ask when there are local changes")
    parser.add_argument("--no-open", action="store_true", help="Leave Sidebar closed after installation")
    args = parser.parse_args()
    if args.install_launcher:
        install_launcher(REPO)
        return
    branch = preflight(REPO, SETUP, APP)
    if args.check:
        print(f"Ready: {REPO}\nPush: origin/{branch}\nApp: {APP}\nData: {DATA_HOME}")
        print("Plan: commit → push → build Dracula variant → quit → backup → sign/replace → reopen")
        print(git(REPO, "status", "--short") or "Source is clean.")
        return
    env = dict(os.environ)
    env["T3CODE_ICON_THEME"] = "dracula"
    # Finder/Terminal and agent shells can carry Electron-only bootstrap flags.
    env.pop("ELECTRON_RUN_AS_NODE", None)
    env["PATH"] = f"{REPO / 'node_modules/.bin'}:{Path.home() / '.cargo/bin'}:/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"
    with (SETUP / "updater.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise UpdateError("Another Sidebar updater is already running.")
        sha = publish_source(REPO, branch, args.message)
        prepared = build_app(SETUP, REPO, env, sha)
        wait_for_close(DATA_HOME)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = backup_data(SETUP, DATA_HOME, stamp)
        ensure_closed(DATA_HOME)
        require_clean_source(REPO, sha)
        previous = install_app(prepared, APP, SETUP, stamp)
        receipt = {"commit": sha, "branch": branch, "app": str(APP), "previous_app": str(previous), "data_backup": str(backup)}
        receipt_path = SETUP / "last-update.json"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        print(f"\nSidebar updated to {sha[:12]}.\nData backup: {backup}\nPrevious app: {previous}", flush=True)
        if not args.no_open:
            run("open", APP)


if __name__ == "__main__":
    try:
        main()
    except (UpdateError, subprocess.CalledProcessError, OSError, ValueError, EOFError) as error:
        print(f"\nUpdate stopped: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nUpdate cancelled.", file=sys.stderr)
        sys.exit(130)
