// Generates src/schema.d.ts from openapi.json. With --check, fails if the file is out of date.
import { readFile, writeFile } from "node:fs/promises";
import openapiTS, { astToString } from "openapi-typescript";

const contract = new URL("../openapi.json", import.meta.url);
const output = new URL("../src/schema.d.ts", import.meta.url);

const generated = astToString(await openapiTS(contract));

if (process.argv.includes("--check")) {
  const current = await readFile(output, "utf8").catch(() => "");
  if (current !== generated) {
    console.error("src/schema.d.ts is out of date. Run `pnpm api:generate`.");
    process.exitCode = 1;
  }
} else {
  await writeFile(output, generated);
}
