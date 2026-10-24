// @effect-diagnostics nodeBuiltinImport:off - Standalone asset exporter uses Node filesystem alongside Sharp.
import * as NodeFSP from "node:fs/promises";
import sharp from "sharp";

import { encodePngIco, WINDOWS_ICON_SIZES } from "./lib/icon-export.ts";

const root = new URL("../", import.meta.url);
const directory = new URL("assets/dracula/", root);
const logo = await NodeFSP.readFile(new URL("logo.svg", directory));
const macos = await NodeFSP.readFile(new URL("macos.svg", directory));
const render = (svg: Buffer, size: number) => sharp(svg).resize(size, size).png().toBuffer();

await NodeFSP.writeFile(new URL("macos-1024.png", directory), await render(macos, 1024));
await NodeFSP.writeFile(new URL("universal-1024.png", directory), await render(logo, 1024));
await NodeFSP.writeFile(
  new URL("windows.ico", directory),
  encodePngIco(
    await Promise.all(
      WINDOWS_ICON_SIZES.map(async (size) => ({ size, contents: await render(logo, size) })),
    ),
  ),
);

const publicDirectory = new URL("apps/web/public/dracula/", root);
await NodeFSP.mkdir(publicDirectory, { recursive: true });
await NodeFSP.writeFile(
  new URL("favicon.ico", publicDirectory),
  encodePngIco(
    await Promise.all(
      [16, 32, 48].map(async (size) => ({ size, contents: await render(logo, size) })),
    ),
  ),
);
await NodeFSP.writeFile(new URL("apple-touch-icon.png", publicDirectory), await render(logo, 180));
