import { afterEach, describe, expect, test, vi } from "vitest";

import { download } from "@/model/useExport";

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("download", () => {
  test("clicks a link in the page, takes it away, and frees the file later", () => {
    vi.useFakeTimers();
    const create = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:file");
    const revoke = vi.spyOn(URL, "revokeObjectURL").mockReturnValue();
    const clicked: { inPage: boolean; name: string; href: string }[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push({
        inPage: document.body.contains(this),
        name: this.download,
        href: this.href,
      });
    });

    download("a.txt", "text");

    expect(create).toHaveBeenCalledTimes(1);
    expect(clicked).toEqual([
      { inPage: true, name: "a.txt", href: "blob:file" },
    ]);
    expect(document.querySelectorAll("a")).toHaveLength(0);
    expect(revoke).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(revoke).toHaveBeenCalledWith("blob:file");
  });
});
