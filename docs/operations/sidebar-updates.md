# Updating the local Sidebar app

Double-click `~/Applications/Update T3 Code Sidebar.command`; it asks `[y/N]` whether to
merge the newest stable upstream release first (see `--upstream` below). To install that launcher
again from this checkout, run `python3 scripts/update-sidebar.py --install-launcher`;
it keeps an existing `export GIT_SSH_COMMAND=` line, which the push may need.

The updater lists local changes and asks for a commit message when needed, commits all
non-ignored changes, and pushes the current branch to `origin` (Garrett's Sidebar fork).
A rejected push stops the update; resolve the branch normally and retry. It never force
pushes or pulls. Check the listed files before proceeding; keep private files ignored and
run it after other agents/editors finish changing this checkout.

By default it does not touch upstream. With `--upstream` it first commits your local
changes, fetches the official `upstream` remote, and merges the newest stable release tag
(`vX.Y.Z`; nightly and preview tags are ignored) with a merge commit, after saving a
`backup/sidebar-before-upstream-*` branch at your previous commit. It does nothing if that
release is already merged. On conflicts it aborts the merge, lists the files, and stops
before pushing or building; resolve with `git merge refs/tags/<tag>`, commit, and rerun.
It warns when the release adds database migrations, since an app that has run them cannot
be downgraded. The merged tag is recorded as `upstream_tag` in `last-update.json`.

It then makes a full build with the Dracula icons through the existing `build.py` in
`~/Library/Application Support/T3 Code Sidebar Setup`. That script preserves Sidebar's
bundle identity, separate data home and browser profile, and disabled official updates.
The updater requires those existing setup tools; it does not initialize or migrate an
installation from the official app. Keep the setup directory in machine backups.

You can leave Sidebar open during compilation. Before installation the updater waits
for you to finish active turns and quit Sidebar normally. Leave it closed until the
update finishes; the updater never terminates the app or agents. It backs up the current
Sidebar data using the setup's snapshot and chat-export tools, verifies the locally
signed app, replaces the installed bundle, and reopens it. No Finder copying is needed.
The existing `~/.t3-sidebar` home and browser profile remain in place.

Only the installed app is kept: after a successful update the previous bundle and the
build's app copies are deleted, because macOS lists every bundle with Sidebar's ID as
another copy of the app. Rebuild an older version from Git if needed. The data backup is
under `backups/sidebar-update-*`; `last-update.json` records its path and the pushed commit.
A failure while swapping/verifying the app restores the
previous bundle. If a newly launched version has already migrated data, restoring its
old executable alone may not be sufficient; follow the setup README's data recovery
procedure. Backups are local and inherit the existing backup tool's scope and limits.

For a read-only setup check, run `python3 scripts/update-sidebar.py --check`. For a
terminal update use `python3 scripts/update-sidebar.py` (add `--upstream` to merge the
latest stable release); `--message "…"` supplies the commit message and `--no-open`
leaves the installed app closed. Builds log progress
to the setup directory's timestamped `build-*/build.log`.

Run the updater's isolated tests with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -p 'test_update_sidebar.py'
```
