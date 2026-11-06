export const ACCEPTED_EXTENSIONS = [".txt", ".csv", ".dat"] as const;

// As `POST /api/parse` takes, and the request's limit. A larger file is refused before reading.
const MAX_TEXT_CHARACTERS = 2_000_000;
const MAX_FILE_BYTES = 8_000_000;

export type FileProblem = "wrong_file_type" | "file_too_large" | "read_failed";

export class FileReadError extends Error {
  constructor(readonly problem: FileProblem) {
    super(problem);
    this.name = "FileReadError";
  }
}

function hasAcceptedExtension(name: string): boolean {
  const lower = name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((extension) => lower.endsWith(extension));
}

function encodingOf(bytes: Uint8Array): "utf-16le" | "utf-16be" | "utf-8" {
  if (bytes[0] === 0xff && bytes[1] === 0xfe) {
    return "utf-16le";
  }
  if (bytes[0] === 0xfe && bytes[1] === 0xff) {
    return "utf-16be";
  }
  return "utf-8";
}

/**
 * The text of a file, for the server to read. Spreadsheets on Windows often save UTF-16 with a
 * byte order mark. Anything else is read as UTF-8, and the server reports what that spoils.
 */
export async function readFileText(file: File): Promise<string> {
  if (!hasAcceptedExtension(file.name)) {
    throw new FileReadError("wrong_file_type");
  }
  if (file.size > MAX_FILE_BYTES) {
    throw new FileReadError("file_too_large");
  }
  let bytes: Uint8Array;
  try {
    bytes = new Uint8Array(await file.arrayBuffer());
  } catch {
    // A dropped folder looks like a file until it is read.
    throw new FileReadError("read_failed");
  }
  const text = new TextDecoder(encodingOf(bytes)).decode(bytes);
  if (text.length > MAX_TEXT_CHARACTERS) {
    throw new FileReadError("file_too_large");
  }
  return text;
}
