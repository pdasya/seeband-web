// @vitest-environment node
import { describe, expect, test } from "vitest";

import { FileReadError, readFileText } from "@/data/readFile";

const file = (parts: BlobPart[], name = "a.txt") => new File(parts, name);

async function problem(input: File): Promise<string> {
  const error = await readFileText(input).catch((caught: unknown) => caught);
  expect(error).toBeInstanceOf(FileReadError);
  return (error as FileReadError).problem;
}

describe("readFileText", () => {
  test.each(["a.txt", "a.csv", "a.dat", "A.TXT", "a.b.Dat"])(
    "reads %s",
    async (name) => {
      expect(await readFileText(file(["T S\n"], name))).toBe("T S\n");
    },
  );

  test.each(["a.xlsx", "a", "txt", "a.txt.pdf"])("refuses %s", async (name) => {
    expect(await problem(file(["x"], name))).toBe("wrong_file_type");
  });

  test("refuses a large file by its size, before reading", async () => {
    const large = file(["x"]);
    Object.defineProperty(large, "size", { value: 8_000_001 });
    Object.defineProperty(large, "arrayBuffer", {
      value: () => {
        throw new Error("It should not read this");
      },
    });

    expect(await problem(large)).toBe("file_too_large");
  });

  test("refuses text over the API's limit, and takes it at the limit", async () => {
    expect(await problem(file(["x".repeat(2_000_001)]))).toBe("file_too_large");
    expect(await readFileText(file(["x".repeat(2_000_000)]))).toHaveLength(
      2_000_000,
    );
  });

  test("a file that cannot be read says so", async () => {
    const broken = file(["x"]);
    Object.defineProperty(broken, "arrayBuffer", {
      value: () => Promise.reject(new Error("SECRET-VALUE")),
    });

    expect(await problem(broken)).toBe("read_failed");
  });

  test("decodes by the byte order mark, and drops it", async () => {
    const text = "T S\nρ";
    const units = [...text].map((c) => c.charCodeAt(0));
    const little = new Uint8Array(
      [0xff, 0xfe].concat(units.flatMap((u) => [u & 0xff, u >> 8])),
    );
    const big = new Uint8Array(
      [0xfe, 0xff].concat(units.flatMap((u) => [u >> 8, u & 0xff])),
    );
    const utf8 = new Uint8Array([
      0xef,
      0xbb,
      0xbf,
      ...new TextEncoder().encode(text),
    ]);

    expect(await readFileText(file([little]))).toBe(text);
    expect(await readFileText(file([big]))).toBe(text);
    expect(await readFileText(file([utf8]))).toBe(text);
  });

  test("an empty file is text for the server to judge", async () => {
    expect(await readFileText(file([]))).toBe("");
  });
});
