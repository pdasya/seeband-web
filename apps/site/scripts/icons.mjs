// Draws `favicon.ico` and `apple-touch-icon.png` from `public/favicon.svg`, the header's logo.
// Run it after changing the SVG, and commit what it writes:
//   pnpm --filter @seeband/site icons
// sharp comes with Astro, which uses it for images, so it is found through Astro.
import { readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const sharp = createRequire(require.resolve("astro/package.json"))("sharp");

const publicDir = new URL("../public/", import.meta.url);
const svg = await readFile(new URL("favicon.svg", publicDir), "utf8");

// sharp draws an SVG at 72 dpi for each of its units, so the density for `size` pixels follows
// from the SVG's own size, read from its square viewBox.
const viewBox = /viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"/.exec(svg);
if (viewBox === null || viewBox[1] !== viewBox[2]) {
  throw new Error('favicon.svg needs a square viewBox="0 0 n n"');
}
const svgSize = Number(viewBox[1]);

/** The SVG drawn square at `size` pixels, as PNG. */
function png(source, size) {
  return sharp(Buffer.from(source), { density: (72 * size) / svgSize })
    .resize(size, size)
    .png({ compressionLevel: 9 })
    .toBuffer();
}

// An ICO file holding PNG images, which every browser since 2007 reads.
const sizes = [16, 32, 48];
const images = await Promise.all(sizes.map((size) => png(svg, size)));
const header = Buffer.alloc(6 + 16 * images.length);
header.writeUInt16LE(0, 0);
header.writeUInt16LE(1, 2);
header.writeUInt16LE(images.length, 4);
let offset = header.length;
images.forEach((image, index) => {
  const entry = 6 + 16 * index;
  header.writeUInt8(sizes[index], entry);
  header.writeUInt8(sizes[index], entry + 1);
  header.writeUInt16LE(1, entry + 4);
  header.writeUInt16LE(32, entry + 6);
  header.writeUInt32LE(image.length, entry + 8);
  header.writeUInt32LE(offset, entry + 12);
  offset += image.length;
});
await writeFile(
  new URL("favicon.ico", publicDir),
  Buffer.concat([header, ...images]),
);

// iOS rounds the corners itself and fills transparent ones with black, so the square is full.
const square = svg.replace(/ rx="[^"]*"/, "");
if (square === svg) {
  throw new Error(
    'favicon.svg has no rounded background (rx="…") to square for the touch icon',
  );
}
await writeFile(
  new URL("apple-touch-icon.png", publicDir),
  await png(square, 180),
);

console.log(
  "Wrote public/favicon.ico (16, 32, 48 px) and public/apple-touch-icon.png (180 px)",
);
