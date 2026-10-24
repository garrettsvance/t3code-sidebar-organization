# Dracula icon overlay

This optional fork variant preserves the upstream T3 mark and all original icon assets.
Its colors are background `#282a36`, T `#bd93f9`, and 3 `#ff79c6`.

Set `T3CODE_ICON_THEME=dracula` when starting development or building the desktop app:

```sh
T3CODE_ICON_THEME=dracula vp run dev:desktop --home-dir ~/.t3-sidebar-desktop-dev
T3CODE_ICON_THEME=dracula vp run dev
```

For the installed **T3 Code Sidebar** app, use the [local updater](../../docs/operations/sidebar-updates.md)
to preserve its app identity and data paths. A generic repository package build does not
apply that installation's isolation settings.

Restart the development processes after changing the setting. For the original icons,
unset the variable. Packaged apps keep the icon chosen at build time; rebuild to switch.
The web build uses the same variable and serves its added favicon assets from `/dracula/`,
so upstream branding export scripts can still update the original files.

Edit `logo.svg` and `macos.svg`, then run `node scripts/export-dracula-icons.ts` to
regenerate the PNG/ICO files and the added `apps/web/public/dracula/` assets. The macOS
source reserves a 100px transparent margin around an 824px body on a 1024px canvas.

When updating from upstream, retain this directory, the exporter, the public Dracula
directory, and the small `T3CODE_ICON_THEME` selection changes. No original icon needs
to be replaced. Native mobile and the marketing site keep their existing artwork.
