#!/usr/bin/env python3
"""Build the committed PR272 review ZIP; requires installed pnpm/Chromium deps.

Run from any directory with --output /tmp/seeband-band-composition-v0.7-review.zip.
Use --figures-dir /tmp/review-figures to retain the six regenerated previews.
Run --self-test for the offline-link and deterministic-archive checks.
"""

import argparse
import hashlib
import io
import json
import posixpath
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

SPECS = "docs/superpowers/specs"
KIT = f"{SPECS}/band-composition-v0.7"
TDD = f"{SPECS}/2026-11-21-band-composition-design.md"
RENDERER = f"{SPECS}/figures/render-reviewed-figures.mjs"
FIGURES = (
    "three-band-edges.png",
    "fit-parameters-and-model.png",
    "fit-mixed-kane-model.png",
    "parameters-fit-locks.png",
    "parameters-guide-matrix.png",
    "three-band-gap-parameters.png",
)
RELEASE = "https://github.com/pdasya/seeband-web/releases/download/review-pr272-v0.7-kane-scope/"
LINK = re.compile(r"(?<=\]\()([^\s)]+)(?=\))")


def command(root, *args):
    return subprocess.check_output(args, cwd=root).decode().strip()


def rewrite_links(name, data, members, revision):
    """Keep bundled review links local; pin other repository references."""

    def replace(match):
        target = match.group(0)
        parts = urlsplit(target)
        if target.startswith(RELEASE) and parts.path.rsplit("/", 1)[-1] in FIGURES:
            resolved = f"{SPECS}/figures/{parts.path.rsplit('/', 1)[-1]}"
        elif parts.scheme or parts.netloc or not parts.path:
            return target
        else:
            resolved = posixpath.normpath(
                posixpath.join(posixpath.dirname(name), unquote(parts.path))
            )
            if resolved.startswith("../") or resolved.startswith("/"):
                raise ValueError(f"Unsafe repository link in {name}: {target}")
        suffix = f"#{parts.fragment}" if parts.fragment else ""
        if resolved in members:
            return posixpath.relpath(resolved, posixpath.dirname(name)) + suffix
        return f"https://github.com/pdasya/seeband-web/blob/{revision}/{resolved}{suffix}"

    return LINK.sub(replace, data.decode()).encode()


def archive_bytes(files):
    """Stable member order, metadata and compression for identical inputs."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return output.getvalue()


def self_test():
    members = {TDD, f"{SPECS}/figures/three-band-edges.png", f"{KIT}/REVIEW.md"}
    original = (
        f"[guide](band-composition-v0.7/REVIEW.md#checks) "
        f"![figure]({RELEASE}three-band-edges.png) "
        "[code](../../../apps/web/src/strings.ts) [section](#local) "
        f"[download]({RELEASE}seeband-band-composition-v0.7-review.zip)"
    ).encode()
    result = rewrite_links(TDD, original, members, "a" * 40).decode()
    assert "(band-composition-v0.7/REVIEW.md#checks)" in result
    assert "(figures/three-band-edges.png)" in result
    assert f"/blob/{'a' * 40}/apps/web/src/strings.ts)" in result
    assert "[section](#local)" in result
    assert f"({RELEASE}seeband-band-composition-v0.7-review.zip)" in result
    files = {TDD: result.encode(), "README.md": b"Review"}
    first = archive_bytes(files)
    assert first == archive_bytes(dict(reversed(list(files.items()))))
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        assert archive.testzip() is None
        assert archive.read(TDD) == files[TDD]
    sys.stdout.write("PASS: offline review links, pinned source links, deterministic ZIP\n")


def build(args):
    root = Path(command(Path(__file__).resolve().parent, "git", "rev-parse", "--show-toplevel"))
    subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=root, check=True)
    revision = command(root, "git", "rev-parse", "HEAD")
    tracked = set(command(root, "git", "ls-tree", "-r", "--name-only", "HEAD").splitlines())
    names = {
        TDD,
        f"{KIT}/REVIEW.md",
        f"{KIT}/fit-guide.html",
        f"{KIT}/evidence.json",
        f"{SPECS}/band-parameter-labels.json",
        RENDERER,
        "apps/site/public/guide/dpb-fit.png",
    }
    # Keep the evidence transcripts, fixtures and their replay scripts.
    names.update(
        p
        for p in tracked
        if p.startswith(f"{KIT}/evidence/")
        and (
            Path(p).suffix in {".txt", ".json", ".py", ".mjs"}
            or p.startswith(f"{KIT}/evidence/chasapis/")
        )
        and not p.endswith((".py.txt", ".tsx.txt"))
    )
    names.update(
        f"scripts/{p}.py"
        for p in (
            "verify_band_composition_design",
            "verify_spb_design_coefficients",
            "verify_skb_design_reference",
            "verify_mixed_scattering_design",
            "verify_parabolic_mass_identifiability",
            "verify_three_band_s_profile",
        )
    )
    if missing := names - tracked:
        raise ValueError(f"Required committed files are missing: {sorted(missing)}")
    output = Path(args.output).resolve()
    if output.is_relative_to(root) or output.exists():
        raise ValueError("Choose a new ZIP output path outside the repository")
    files = {
        p: subprocess.check_output(["git", "show", f"{revision}:{p}"], cwd=root) for p in names
    }
    with tempfile.TemporaryDirectory(prefix="seeband-review-") as temporary:
        directory = Path(args.figures_dir).resolve() if args.figures_dir else Path(temporary)
        if directory.is_relative_to(root):
            raise ValueError("Choose a figures directory outside the repository")
        directory.mkdir(parents=True, exist_ok=True)
        if any(directory.iterdir()):
            raise ValueError("The figures output directory must be empty")
        subprocess.run(["node", RENDERER, "--output-dir", str(directory)], cwd=root, check=True)
        if {p.name for p in directory.iterdir()} != set(FIGURES):
            raise ValueError("Renderer must produce exactly the six current PNG figures")
        for figure in FIGURES:
            data = (directory / figure).read_bytes()
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError(f"Renderer output is not PNG: {figure}")
            files[f"{SPECS}/figures/{figure}"] = data
    # Ship the individual observations in the review asset without tracking generated rows.
    files[f"{KIT}/evidence/scattering-cases.jsonl"] = subprocess.check_output(
        ["node", f"{KIT}/evidence/verify_scattering_matrix.mjs", "--cases"], cwd=root
    )
    for name in list(files):
        if name.endswith(".md"):
            files[name] = rewrite_links(name, files[name], files, revision)
    files["README.md"] = f"""# SeeBand band-composition v0.7 review

Source revision: `{revision}` ([immutable source](https://github.com/pdasya/seeband-web/tree/{revision})).

1. Read the [English technical design]({TDD}).
2. Follow the [review guide and recorded replay instructions]({KIT}/REVIEW.md).
3. Open the [interactive Fit/Guide HTML]({KIT}/fit-guide.html) directly in a browser.
4. Inspect the [evidence index]({KIT}/evidence.json) and
   [parameter dictionary]({SPECS}/band-parameter-labels.json).
5. Compare the [baseline guide screenshot](apps/site/public/guide/dpb-fit.png)
   with the six current synthetic illustrations in `{SPECS}/figures/`.

Extract the whole ZIP before opening links. Repository-relative paths are preserved.
Review-document and figure links work offline; source/architecture links outside this
bundle point to the immutable source revision. External publications need internet.
The evidence index and recorded transcripts/fixtures are copied unchanged; its
SHA-256 values identify those saved outputs, not newly executed numerical checks.
The six PNGs were regenerated with the committed renderer and local locked Chromium.
The [576 editor outcomes]({KIT}/evidence/scattering-cases.jsonl) were replayed for this archive.
This bundle does not claim a new numerical replay or production integration result.

Verification helpers are supplied for inspection and copying into a full source
checkout with its locked Python/pnpm dependencies; this ZIP is not a standalone
runtime. The Fit/Guide verifier covers the Model controls in the interactive HTML.

`PROVENANCE.json` records the source revision and renderer environment.
`SHA256SUMS` covers every other archive member. ZIP metadata and ordering are fixed;
identical committed inputs and renderer environment produce identical archives.
""".encode()
    files["PROVENANCE.json"] = (
        json.dumps(
            {
                "source_revision": revision,
                "source_commit_time": command(root, "git", "show", "-s", "--format=%cI", revision),
                "renderer": RENDERER,
                "node": command(root, "node", "--version"),
                "browser": json.loads(
                    command(
                        root,
                        "node",
                        "--input-type=module",
                        "-e",
                        "import {createRequire} from 'node:module'; "
                        "const r=createRequire(process.cwd()+'/apps/web/package.json'); "
                        "const {chromium}=r('@playwright/test'); "
                        "const b=await chromium.launch({headless:true}); "
                        "console.log(JSON.stringify({playwright:r('@playwright/test/package.json').version,"
                        "chromium:b.version()})); await b.close();",
                    )
                ),
                "rewrites": "Bundled Markdown links local; source links pinned",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    files["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as destination:
        destination.write(archive_bytes(files))
    sys.stdout.write(f"Built {output} ({len(files)} members), source {revision}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="New ZIP path outside the repository")
    parser.add_argument(
        "--figures-dir", help="Empty external directory for regenerated PNG previews"
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif not args.output:
        parser.error("--output is required unless using --self-test")
    else:
        try:
            build(args)
        except (ValueError, subprocess.CalledProcessError) as error:
            parser.exit(1, f"Review bundle failed: {error}\n")


if __name__ == "__main__":
    main()
