# T3 Code Sidebar fork

An unofficial fork of [T3 Code](https://github.com/pingdotgg/t3code) with a more organized thread sidebar. It tracks stable upstream releases and is not affiliated with the T3 Code maintainers.

## What it adds

On web and desktop, **Settings → Custom** turns these on (they are enabled by default):

- **Group by project** in the Active section, with draggable groups and saved group names.
- **Group pins** that stay inside their project group, alongside the usual pin to top.
- **Attention indicators** on threads that need you.
- **Sort by status**, optionally.
- An optional Dracula icon theme (`T3CODE_ICON_THEME=dracula`).

Native mobile keeps its own sidebar and is unchanged.

## Build the macOS app

You need macOS, Node, the Rust toolchain, and the repo's dependencies (`vp i`).

```sh
vp i
node scripts/build-sidebar-app.ts
```

The app lands in `release/sidebar-<timestamp>/` as a zip. It is not signed or notarized, so unzip it, then run
`codesign --force --deep --sign - "T3 Code Sidebar.app"` and open it with right-click → Open the first time.

The build gives the app its own identity, so it can sit next to the official T3 Code: a separate bundle ID (`local.t3code.sidebar`),
a separate data folder (`~/.t3-sidebar-fork`), and automatic updates turned off. Your official T3 Code data is never touched.
Set `T3CODE_ICON_THEME=dracula` when building to get the Dracula icons.

`node scripts/build-sidebar-app.ts --check` verifies the build overlay still matches the source without building.

## Stay on the latest stable release

```sh
git remote add upstream https://github.com/pingdotgg/t3code.git   # once
git fetch upstream --tags
git merge <newest vX.Y.Z tag>
node scripts/build-sidebar-app.ts --check
```

Only stable `vX.Y.Z` tags are worth merging; nightly and preview tags are not. Expect occasional conflicts in the sidebar files.
If `--check` reports a drifted anchor, update `sidebarOverlays` in `scripts/build-sidebar-app.ts`.
A release that adds database migrations cannot be downgraded afterward, so keep a backup of the data folder first.
