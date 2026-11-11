#!/usr/bin/env python3
"""Read-only report on merging the newest stable upstream T3 Code release into this fork.

Never changes the worktree, refs or index (only `git fetch`, unless --no-fetch).
  analyze.py [vX.Y.Z] [--no-fetch] [--anchors-at REF]
"""
import argparse, ast, re, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SETUP_BUILD = Path.home() / "Library/Application Support/T3 Code Sidebar Setup/build.py"
STABLE = re.compile(r"v(\d+)\.(\d+)\.(\d+)")
MIGRATIONS = "apps/server/src/persistence/Migrations"
SCHEMES = 'schemes: ["t3code", "t3code-dev"],'


def git(*args, check=True):
    r = subprocess.run(["git", "-C", str(REPO), *args], text=True, capture_output=True)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr}")
    return r


def lines(result):
    return [l for l in result.stdout.splitlines() if l]


def stable_tags():
    out = lines(git("tag", "--list", "v*", "--merged", "refs/remotes/upstream/main"))
    return sorted(((tuple(map(int, m.groups())), t) for t in out if (m := STABLE.fullmatch(t))))


def anchors(ref):
    """Each exact-match string setup/build.py patches at build time must still exist exactly once."""
    if not SETUP_BUILD.is_file():
        return [("(setup build.py missing)", str(SETUP_BUILD), 0, 0)]
    rows = []
    for node in ast.walk(ast.parse(SETUP_BUILD.read_text())):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "replace"
                and len(node.args) >= 2 and all(isinstance(a, ast.Constant) for a in node.args[:2])):
            path, old = node.args[0].value, node.args[1].value
            shown = git("show", f"{ref}:{path}", check=False)
            count = shown.stdout.count(old) if shown.returncode == 0 else 0
            rows.append((path, old.strip().splitlines()[0][:90], count, 2 if old == SCHEMES else 1))
    return rows


def report_anchors(at):
    print(f"\nBuild overlay anchors (setup build.py patches these exact strings) at {at}:")
    bad = 0
    for path, old, count, want in anchors(at):
        ok = count == want
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} {count}/{want}  {path}: {old}")
    if bad:
        print(f"  {bad} anchor(s) will make build.py fail; build.py needs updating after the merge.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tag", nargs="?")
    p.add_argument("--no-fetch", action="store_true")
    p.add_argument("--anchors-at", help="ref to check build.py anchors against (default: the tag)")
    args = p.parse_args()

    if not args.no_fetch:
        git("fetch", "upstream", "--tags", "--quiet")
    tags = stable_tags()
    if not tags:
        sys.exit("No stable vX.Y.Z tag on upstream/main.")
    tag = args.tag or tags[-1][1]
    ref = f"refs/tags/{tag}"
    print(f"Newest stable upstream: {tags[-1][1]}   Target: {tag}")
    print(f"Branch: {git('branch', '--show-current').stdout.strip()}   HEAD: {git('rev-parse', '--short', 'HEAD').stdout.strip()}")
    dirty = lines(git("status", "--short"))
    print("Worktree: " + ("DIRTY (commit or stash before merging)\n  " + "\n  ".join(dirty[:15]) if dirty else "clean"))

    if git("merge-base", "--is-ancestor", ref, "HEAD", check=False).returncode == 0:
        print(f"\nAlready includes {tag}. Nothing to merge.")
        if args.anchors_at:
            report_anchors(args.anchors_at)
        return
    newer = [t for _, t in tags if git("merge-base", "--is-ancestor", f"refs/tags/{t}", "HEAD", check=False).returncode != 0]
    print(f"Unmerged stable releases: {', '.join(newer)}")

    base = git("merge-base", "HEAD", ref).stdout.strip()
    ours = set(lines(git("diff", "--name-only", base, "HEAD")))
    theirs = set(lines(git("diff", "--name-only", base, ref)))
    both = sorted(ours & theirs)
    print(f"\nMerge base {base[:10]}: fork changed {len(ours)} files, upstream changed {len(theirs)}, both touched {len(both)}")
    for f in both:
        o = git("diff", "--shortstat", base, "HEAD", "--", f).stdout.strip()
        t = git("diff", "--shortstat", base, ref, "--", f).stdout.strip()
        print(f"  {f}\n      fork: {o}\n      upstream: {t}")

    r = git("merge-tree", "--write-tree", "--name-only", "HEAD", ref, check=False)
    conflicts = []
    if r.returncode == 1:
        for l in r.stdout.splitlines()[1:]:
            if not l:
                break
            conflicts.append(l)
    elif r.returncode > 1:
        print(f"\nmerge-tree failed: {r.stderr.strip()}")
    print(f"\nTextual conflicts a merge would hit: {len(conflicts)}")
    for f in conflicts:
        print(f"  CONFLICT {f}")
    if not conflicts:
        print("  (none; the merge can still break typecheck/tests, so verify after merging)")

    added = lines(git("diff", "--name-only", "--diff-filter=A", f"HEAD...{ref}", "--", MIGRATIONS))
    print("\nNew database migrations: " + ("YES, the app cannot be downgraded afterwards\n  " + "\n  ".join(added) if added else "none"))
    for name in ("pnpm-lock.yaml", "package.json", "patches"):
        if name in " ".join(theirs):
            print(f"Upstream changed dependency inputs ({name}...): run `vp i` after merging.")
            break

    report_anchors(args.anchors_at or ref)


if __name__ == "__main__":
    main()
