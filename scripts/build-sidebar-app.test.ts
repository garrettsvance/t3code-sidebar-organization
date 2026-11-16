// @effect-diagnostics nodeBuiltinImport:off - Test fixtures use Node filesystem and the real source tree.
import * as NodeFS from "node:fs";
import * as NodeOS from "node:os";
import * as NodePath from "node:path";
import { assert, it } from "@effect/vitest";

import { applyOverlays, checkOverlays, sidebarOverlays } from "./build-sidebar-app.ts";

const repoRoot = NodePath.resolve(import.meta.dirname, "..");

it("the Sidebar overlay anchors still match upstream source", () => {
  assert.deepStrictEqual(checkOverlays(repoRoot), []);
});

it("applies every overlay and restores the original files", () => {
  const directory = NodeFS.mkdtempSync(NodePath.join(NodeOS.tmpdir(), "sidebar-overlay-"));
  try {
    const files = [...new Set(sidebarOverlays.map((overlay) => overlay.file))];
    for (const file of files) {
      NodeFS.mkdirSync(NodePath.join(directory, NodePath.dirname(file)), { recursive: true });
      NodeFS.copyFileSync(NodePath.join(repoRoot, file), NodePath.join(directory, file));
    }
    const restore = applyOverlays(directory);
    const patched = NodeFS.readFileSync(
      NodePath.join(directory, "scripts/build-desktop-artifact.ts"),
      "utf8",
    );
    assert.notInclude(patched, 'const DESKTOP_APP_ID = "com.t3tools.t3code";');
    assert.notInclude(patched, 'schemes: ["t3code", "t3code-dev"]');
    restore();
    for (const file of files) {
      assert.strictEqual(
        NodeFS.readFileSync(NodePath.join(directory, file), "utf8"),
        NodeFS.readFileSync(NodePath.join(repoRoot, file), "utf8"),
      );
    }
  } finally {
    NodeFS.rmSync(directory, { recursive: true, force: true });
  }
});
