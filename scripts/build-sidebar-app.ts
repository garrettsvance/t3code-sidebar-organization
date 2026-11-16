// @effect-diagnostics nodeBuiltinImport:off globalConsole:off globalDate:off - Standalone build wrapper drives Node filesystem, processes and the console directly.
import * as NodeChildProcess from "node:child_process";
import * as NodeFS from "node:fs";
import * as NodeOS from "node:os";
import * as NodePath from "node:path";

const root = NodePath.resolve(import.meta.dirname, "..");

const APP_ID = "local.t3code.sidebar";
const PRODUCT_NAME = "T3 Code Sidebar";
const DATA_HOME_DIRECTORY = ".t3-sidebar-fork";
const USER_DATA_DIRECTORY = "t3code-sidebar-fork";
const URL_SCHEME = "t3code-sidebar-fork";

export interface SourceOverlay {
  readonly file: string;
  readonly find: string;
  readonly replace: string;
  readonly occurrences?: number;
}

// Gives the packaged app its own identity, data and update policy so it never touches an
// installed official T3 Code. Each `find` must match upstream source exactly.
export const sidebarOverlays: ReadonlyArray<SourceOverlay> = [
  {
    file: "apps/desktop/src/boot.ts",
    find: 'require("./compileCache.cjs");',
    replace: `process.env.T3CODE_HOME = require("node:path").join(require("node:os").homedir(), ${JSON.stringify(DATA_HOME_DIRECTORY)});
process.env.T3CODE_DISABLE_AUTO_UPDATE = "true";
delete process.env.VITE_DEV_SERVER_URL;
require("./compileCache.cjs");`,
  },
  {
    file: "apps/desktop/src/app/DesktopUserData.ts",
    find: '{ current: "t3code-v2", legacy: "T3 Code (Alpha)" }',
    replace: `{ current: ${JSON.stringify(USER_DATA_DIRECTORY)}, legacy: ${JSON.stringify(`${PRODUCT_NAME} (Legacy)`)} }`,
  },
  {
    file: "apps/desktop/src/app/DesktopEnvironment.ts",
    find: 'const APP_BASE_NAME = "T3 Code";',
    replace: `const APP_BASE_NAME = ${JSON.stringify(PRODUCT_NAME)};`,
  },
  {
    file: "scripts/build-desktop-artifact.ts",
    find: 'const DESKTOP_APP_ID = "com.t3tools.t3code";',
    replace: `const DESKTOP_APP_ID = ${JSON.stringify(APP_ID)};`,
  },
  {
    file: "scripts/build-desktop-artifact.ts",
    find: "productName: resolveDesktopProductName(version),",
    replace: `productName: ${JSON.stringify(PRODUCT_NAME)},`,
  },
  {
    file: "scripts/build-desktop-artifact.ts",
    find: 'schemes: ["t3code", "t3code-dev"],',
    replace: `schemes: [${JSON.stringify(URL_SCHEME)}],`,
    occurrences: 2,
  },
];

const countOccurrences = (source: string, find: string) => source.split(find).length - 1;

export function checkOverlays(repoRoot: string, overlays = sidebarOverlays): string[] {
  const problems: string[] = [];
  for (const { file, find, occurrences = 1 } of overlays) {
    const source = NodeFS.readFileSync(NodePath.join(repoRoot, file), "utf8");
    const found = countOccurrences(source, find);
    if (found !== occurrences) {
      problems.push(
        `${file}: expected ${occurrences} match(es) of ${JSON.stringify(find)}, found ${found}`,
      );
    }
  }
  return problems;
}

export function applyOverlays(repoRoot: string, overlays = sidebarOverlays) {
  const problems = checkOverlays(repoRoot, overlays);
  if (problems.length > 0) {
    throw new Error(
      `Upstream source drifted from the Sidebar build overlay:\n${problems.join("\n")}`,
    );
  }
  const originals = new Map<string, string>();
  for (const { file, find, replace } of overlays) {
    const path = NodePath.join(repoRoot, file);
    const current = NodeFS.readFileSync(path, "utf8");
    if (!originals.has(path)) originals.set(path, current);
    NodeFS.writeFileSync(
      path,
      current.replaceAll(find, () => replace),
    );
  }
  return () => {
    for (const [path, source] of originals) NodeFS.writeFileSync(path, source);
  };
}

function resolveBuildVersion(repoRoot: string) {
  const tags = NodeChildProcess.spawnSync("git", ["tag", "--merged", "HEAD"], {
    cwd: repoRoot,
    encoding: "utf8",
  }).stdout;
  const newest = tags
    .split("\n")
    .map((tag) => /^v(\d+)\.(\d+)\.(\d+)$/.exec(tag))
    .filter((match) => match !== null)
    .map((match) => ({ tag: match[0].slice(1), parts: match.slice(1).map(Number) }))
    .toSorted(
      (a, b) => b.parts[0]! - a.parts[0]! || b.parts[1]! - a.parts[1]! || b.parts[2]! - a.parts[2]!,
    )[0];
  const base =
    newest?.tag ??
    (
      JSON.parse(
        NodeFS.readFileSync(NodePath.join(repoRoot, "apps/desktop/package.json"), "utf8"),
      ) as { version: string }
    ).version;
  const date = new Date().toISOString().slice(0, 10).replaceAll("-", "");
  return `${base}-preview.${date}.1`;
}

// Fresh staging has no lockfile, so pin node-pty to the version the checked-in patch targets.
function nodePtyOverlay(repoRoot: string): SourceOverlay | undefined {
  const patch = NodeFS.readdirSync(NodePath.join(repoRoot, "patches")).find((name) =>
    /^node-pty@.+\.patch$/.test(name),
  );
  if (!patch) return undefined;
  return {
    file: "scripts/build-desktop-artifact.ts",
    find: "  const stagePatchedDependencies = createStagePatchedDependencies(",
    replace: `  stageDependencies["node-pty"] = ${JSON.stringify(patch.slice("node-pty@".length, -".patch".length))};\n  const stagePatchedDependencies = createStagePatchedDependencies(`,
  };
}

function main(argv: ReadonlyArray<string>) {
  const nodePty = nodePtyOverlay(root);
  const overlays = nodePty ? [...sidebarOverlays, nodePty] : sidebarOverlays;
  if (argv.includes("--check")) {
    const problems = checkOverlays(root, overlays);
    console.log(
      problems.length === 0 ? "Sidebar build overlay matches this source." : problems.join("\n"),
    );
    return problems.length === 0 ? 0 : 1;
  }
  // oxlint-disable-next-line t3code/no-global-process-runtime -- Standalone Node tooling has no Effect runtime.
  if (NodeOS.platform() !== "darwin") {
    console.error("The Sidebar build wrapper supports macOS only.");
    return 1;
  }
  const outputFlag = argv.indexOf("--output-dir");
  const outputDirectory = NodePath.resolve(
    outputFlag >= 0
      ? (argv[outputFlag + 1] ?? "")
      : NodePath.join(root, "release", `sidebar-${Date.now()}`),
  );
  const version = resolveBuildVersion(root);
  const restore = applyOverlays(root, overlays);
  const onSignal = () => {
    restore();
    process.exit(130);
  };
  process.on("SIGINT", onSignal);
  process.on("SIGTERM", onSignal);
  try {
    console.log(`Building ${PRODUCT_NAME} ${version} into ${outputDirectory}`);
    const result = NodeChildProcess.spawnSync(
      "node",
      [
        "scripts/build-desktop-artifact.ts",
        "--platform",
        "mac",
        "--target",
        "zip",
        "--arch",
        // oxlint-disable-next-line t3code/no-global-process-runtime -- Standalone Node tooling has no Effect runtime.
        NodeOS.arch() === "x64" ? "x64" : "arm64",
        "--build-version",
        version,
        "--output-dir",
        outputDirectory,
        "--verbose",
        ...(argv.includes("--skip-build") ? ["--skip-build"] : []),
      ],
      {
        cwd: root,
        stdio: "inherit",
        env: {
          ...process.env,
          PATH: [
            NodePath.join(root, "node_modules/.bin"),
            NodePath.join(NodeOS.homedir(), ".cargo/bin"),
            process.env.PATH ?? "",
          ].join(NodePath.delimiter),
          CSC_IDENTITY_AUTO_DISCOVERY: "false",
          VITE_HTTP_URL: undefined,
          VITE_WS_URL: undefined,
          VITE_DEV_SERVER_URL: undefined,
          T3CODE_DESKTOP_DEV: undefined,
        },
      },
    );
    return result.status ?? 1;
  } finally {
    restore();
  }
}

if (import.meta.main) {
  process.exitCode = main(process.argv.slice(2));
}
