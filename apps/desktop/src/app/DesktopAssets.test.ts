import * as NodePath from "@effect/platform-node/NodePath";
import * as NodeServices from "@effect/platform-node/NodeServices";
import { assert, describe, it } from "@effect/vitest";
import * as Effect from "effect/Effect";
import * as FileSystem from "effect/FileSystem";
import * as Layer from "effect/Layer";
import * as Option from "effect/Option";
import * as PlatformError from "effect/PlatformError";

import * as DesktopAssets from "./DesktopAssets.ts";
import * as DesktopConfig from "./DesktopConfig.ts";
import * as DesktopEnvironment from "./DesktopEnvironment.ts";

const layerEnvironment = DesktopEnvironment.layer({
  dirname: "/repo/apps/desktop/dist-electron",
  homeDirectory: "/Users/alice",
  platform: "darwin",
  processArch: "arm64",
  appVersion: "1.2.3",
  appPath: "/Applications/T3 Code.app/Contents/Resources/app.asar",
  isPackaged: true,
  resourcesPath: "/Applications/T3 Code.app/Contents/Resources",
  runningUnderArm64Translation: false,
}).pipe(
  Layer.provide(
    Layer.mergeAll(NodeServices.layer, NodePath.layerPosix, DesktopConfig.layerTest({})),
  ),
);

describe("DesktopAssets", () => {
  it.effect.each([
    {
      platform: "linux",
      theme: undefined,
      directory: "dev",
      png: "blueprint-universal-1024.png",
      ico: "blueprint-windows.ico",
    },
    {
      platform: "darwin",
      theme: "dracula",
      directory: "dracula",
      png: "macos-1024.png",
      ico: "windows.ico",
    },
    {
      platform: "linux",
      theme: "dracula",
      directory: "dracula",
      png: "universal-1024.png",
      ico: "windows.ico",
    },
    {
      platform: "win32",
      theme: "dracula",
      directory: "dracula",
      png: "universal-1024.png",
      ico: "windows.ico",
    },
  ] as const)(
    "uses $directory source-tree icons on $platform",
    ({ platform, theme, directory, png, ico }) =>
      Effect.gen(function* () {
        const layerDevelopmentEnvironment = DesktopEnvironment.layer({
          dirname: "/repo/apps/desktop/dist-electron",
          homeDirectory: "/Users/alice",
          platform,
          processArch: "x64",
          appVersion: "1.2.3",
          appPath: "/repo",
          isPackaged: false,
          resourcesPath: "/repo/apps/desktop/resources",
          runningUnderArm64Translation: false,
        }).pipe(
          Layer.provide(
            Layer.mergeAll(
              NodeServices.layer,
              NodePath.layerPosix,
              DesktopConfig.layerTest({
                VITE_DEV_SERVER_URL: "http://localhost:5733",
                T3CODE_ICON_THEME: theme,
              }),
            ),
          ),
        );
        const layerFileSystem = FileSystem.layerNoop({
          exists: (path) => Effect.succeed(String(path).includes(`/assets/${directory}/`)),
        });
        const assets = yield* DesktopAssets.DesktopAssets.pipe(
          Effect.provide(
            DesktopAssets.layer.pipe(
              Layer.provide(Layer.merge(layerFileSystem, layerDevelopmentEnvironment)),
            ),
          ),
        );

        const icons = yield* assets.iconPaths;

        assert.equal(Option.getOrThrow(icons.ico), `/repo/assets/${directory}/${ico}`);
        assert.equal(Option.getOrThrow(icons.png), `/repo/assets/${directory}/${png}`);
        assert.isTrue(Option.isNone(icons.icns));
      }),
  );

  it.effect("preserves the failed asset candidate and filesystem cause", () =>
    Effect.gen(function* () {
      const fileName = "custom.bin";
      const candidatePath = "/repo/apps/desktop/resources/custom.bin";
      const cause = PlatformError.systemError({
        _tag: "PermissionDenied",
        module: "FileSystem",
        method: "exists",
        pathOrDescriptor: candidatePath,
        description: "private filesystem diagnostic",
      });
      const layerFileSystem = FileSystem.layerNoop({
        exists: (path) => (path === candidatePath ? Effect.fail(cause) : Effect.succeed(false)),
      });
      const layerAssets = DesktopAssets.layer.pipe(
        Layer.provide(Layer.merge(layerFileSystem, layerEnvironment)),
      );
      const assets = yield* DesktopAssets.DesktopAssets.pipe(Effect.provide(layerAssets));

      const error = yield* assets.resolveResourcePath(fileName).pipe(Effect.flip);

      assert.instanceOf(error, DesktopAssets.DesktopAssetProbeError);
      assert.equal(error.fileName, fileName);
      assert.equal(error.candidatePath, candidatePath);
      assert.strictEqual(error.cause, cause);
      assert.equal(
        error.message,
        `Failed to probe desktop asset "${fileName}" at ${candidatePath}.`,
      );
      assert.notInclude(error.message, "private filesystem diagnostic");
    }),
  );
});
