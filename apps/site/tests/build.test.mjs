// Builds the site as production does, and checks what a browser gets: static HTML that needs
// no script, with no heavy library.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { createRequire } from "node:module";
import { dirname, join, relative } from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";

const SITE_DIR = fileURLToPath(new URL("..", import.meta.url));
const MATH_DIR = fileURLToPath(new URL("fixtures/math", import.meta.url));
// Astro's own script, run with this Node, as the shell shim in node_modules/.bin is not on every
// system or install layout.
const ASTRO = join(
  dirname(
    createRequire(join(SITE_DIR, "package.json")).resolve("astro/package.json"),
  ),
  "bin",
  "astro.mjs",
);
const outDir = mkdtempSync(join(tmpdir(), "seeband-site-build-"));
const mathOutDir = mkdtempSync(join(tmpdir(), "seeband-site-math-"));
// The same site built for a public address: the one above is for a host closed to search.
const publicOutDir = mkdtempSync(join(tmpdir(), "seeband-site-public-"));
const SITE_URL = "https://seeband.example";

function build(root, out, siteUrl) {
  const env = { ...process.env, ASTRO_TELEMETRY_DISABLED: "1" };
  delete env.SEEBAND_SITE_URL;
  if (siteUrl !== undefined) env.SEEBAND_SITE_URL = siteUrl;
  const built = spawnSync(
    process.execPath,
    [ASTRO, "build", "--root", root, "--outDir", out],
    {
      cwd: SITE_DIR,
      encoding: "utf8",
      env,
    },
  );
  assert.equal(built.status, 0, built.stderr + built.stdout);
}

function files(dir) {
  return readdirSync(dir, { recursive: true })
    .map((name) => join(dir, name))
    .filter((path) => statSync(path).isFile());
}

const page = (path) => readFileSync(join(outDir, path), "utf8");
const publicPage = (path) => readFileSync(join(publicOutDir, path), "utf8");

before(() => {
  build(SITE_DIR, outDir);
  build(MATH_DIR, mathOutDir);
  build(SITE_DIR, publicOutDir, SITE_URL);
});

after(() => {
  rmSync(outDir, { recursive: true, force: true });
  rmSync(mathOutDir, { recursive: true, force: true });
  rmSync(publicOutDir, { recursive: true, force: true });
});

test("has its pages in English, as static HTML", () => {
  for (const path of ["index.html", "404.html"]) {
    assert.match(page(path), /<html lang="en"/, path);
  }
  assert.match(
    page("index.html"),
    /<h1>Parabolic band models for transport measurements<\/h1>/,
  );
  assert.match(page("index.html"), /<link rel="icon" href="\/favicon.svg"/);
  assert.match(page("index.html"), /<link rel="icon" href="\/favicon.ico"/);
  assert.match(
    page("index.html"),
    /<link rel="apple-touch-icon" href="\/apple-touch-icon.png"/,
  );
  for (const icon of ["favicon.svg", "favicon.ico", "apple-touch-icon.png"]) {
    assert.ok(statSync(join(outDir, icon)).isFile(), icon);
  }
  // The header's link to the overview is named by what it shows, then where it goes (WCAG 2.5.3).
  const label = /class="sb-header__home"[^>]*aria-label="([^"]*)"/.exec(
    page("index.html"),
  )?.[1];
  const name = /<span class="sb-header__name"[^>]*>([^<]*)<\/span>/.exec(
    page("index.html"),
  )?.[1];
  assert.ok(name, "the header shows a name");
  assert.ok(label?.startsWith(name), `${String(label)} starts with ${name}`);
  assert.match(
    page("index.html"),
    /<a href="\/"[^>]*aria-current="page"[^>]*>Overview<\/a>/,
  );
  // One language for now, so no switch, and no page in another.
  assert.doesNotMatch(page("index.html"), /sb-header__languages|hreflang/);
  assert.equal(
    files(outDir).some((path) => relative(outDir, path).startsWith("de/")),
    false,
  );
});

test("links to the app and the original SeeBand", () => {
  const html = page("index.html");
  assert.match(html, /class="button" href="\/fit"/);
  assert.match(html, /<a href="\/fit" class="sb-header__link">Model fit/);
  assert.match(html, /<a href="\/results" class="sb-header__link">Results/);
  assert.match(html, /href="https:\/\/github.com\/pdasya\/seeband-web"/);
  assert.match(html, /href="https:\/\/github.com\/xAngelswordx\/SeeBand"/);
  assert.match(
    html,
    /href="https:\/\/github.com\/pdasya\/seeband-web\/issues"/,
  );
});

const textOfPage = (html) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

/** The page's main content, without the shared header and footer. */
const mainOf = (html) => html.match(/<main[\s\S]*<\/main>/)?.[0] ?? "";
// Visible text, with tags and Astro's attributes out of the way.
const textOf = (html) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

test("the overview says where data go, and promises only what the app does", () => {
  const main = mainOf(page("index.html"));
  const text = textOf(main);
  // F4: the data go to the server, are used only for the calculation, and are not saved or logged.
  assert.match(
    text,
    /Your data Calculations run on our server, so your measurements are sent to it\./,
  );
  assert.match(text, /does not save them/);
  assert.match(text, /not your data/);
  // Not delivered, or no longer offered: the browser, AI summaries, residual plots, acPhDis.
  assert.doesNotMatch(
    text,
    /runs in the browser|\bAI\b|residuals|acPhDis|\[Repository/i,
  );
  // F8: the E(k) sketch, inline and labelled as one case, with no image file.
  assert.match(
    main,
    /<svg[^>]*role="img"[^>]*aria-label="Schematic of one DPB case/,
  );
  assert.match(text, /Schematic, not to scale/);
  assert.match(main, /href="\/fit\?demo=1"/);
  assert.match(main, /href="\/results-changed\/"/);
});

test("the overview's structure holds together", () => {
  const html = page("index.html");
  assert.equal(html.match(/<h1[\s>]/g)?.length, 1);
  const ids = new Set(
    [...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]),
  );
  const labelled = [...html.matchAll(/aria-labelledby="([^"]+)"/g)].map(
    (match) => match[1],
  );
  assert.ok(labelled.length >= 5);
  for (const id of labelled) {
    assert.ok(ids.has(id), id);
  }
  // A table that can scroll can be reached by keyboard.
  assert.match(html, /class="table-scroll"[^>]*tabindex="0"/);
});

test("has the Conventions and results-changed pages, linked from the header", () => {
  for (const path of ["index.html", "conventions/index.html"]) {
    assert.match(
      page(path),
      /<a href="\/conventions\/"[^>]*>Conventions<\/a>/,
      path,
    );
  }
  const conventions = page("conventions/index.html");
  assert.match(conventions, /<title>Conventions and model · SeeBand<\/title>/);
  assert.match(
    conventions,
    /<a href="\/conventions\/"[^>]*aria-current="page"/,
  );
  assert.match(
    conventions,
    /<h2[^>]*>Thermal conductivity and Lorenz number<\/h2>/,
  );
  assert.match(conventions, /href="\/results-changed\/"/);
  assert.match(page("results-changed/index.html"), /<table>/);
  // Links into the repository go to GitHub, as relative paths do not exist on the site.
  for (const path of ["conventions/index.html", "results-changed/index.html"]) {
    assert.doesNotMatch(page(path), /href="\.\.?\//, path);
    assert.match(
      page(path),
      /href="https:\/\/github.com\/pdasya\/seeband-web\/blob\/main\/packages\//,
      path,
    );
  }
});

test("Conventions renders its formulas, lists its sections and ties issues to the registry", () => {
  const conventions = page("conventions/index.html");
  // KaTeX at build time: math as HTML, no failures, and the page's own styles for it.
  assert.ok((conventions.match(/class="katex"/g) ?? []).length >= 40);
  assert.doesNotMatch(conventions, /katex-error/);
  // MathML stays beside the visible formula, for screen readers.
  assert.match(conventions, /class="katex-mathml"/);
  // Wide tables and formulas scroll in a box a keyboard can reach, and tables stay tables.
  const tables = (conventions.match(/<table>/g) ?? []).length;
  assert.ok(tables >= 5);
  assert.equal(
    (conventions.match(/<div class="scroll-box" tabindex="0"><table>/g) ?? [])
      .length,
    tables,
  );
  assert.match(conventions, /class="katex-display" tabindex="0"/);
  // Each section is in the side list, by its anchor.
  const anchors = [...conventions.matchAll(/<h2[^>]*\sid="([^"]+)"/g)].map(
    (m) => m[1],
  );
  assert.ok(anchors.length >= 10);
  for (const anchor of anchors) {
    assert.match(conventions, new RegExp(`<a href="#${anchor}">`), anchor);
  }
  // The registry's issues, each with its tracking issue; a core test checks they match it.
  for (const id of [
    "dpb_loop_degeneracy",
    "collapsed_m_eff",
    "fermi_energy_in_gap",
    "no_chemical_potential",
    "hall_dis_no_reference",
    "interpolation_extrapolates",
  ]) {
    assert.match(conventions, new RegExp(`<code>${id}</code>`), id);
  }
  assert.match(conventions, /<h2 id="band-diagram">Band diagram<\/h2>/);
  // No mixed scattering is offered any more; the page says so where it names it.
  assert.match(textOfPage(conventions), /acPhDis[^.]*not offered/);
});

test("the user guide is a page of the site, with its screenshots and corrections", () => {
  const guide = page("guide/index.html");
  assert.match(guide, /<title>User guide · SeeBand<\/title>/);
  assert.match(guide, /<a href="\/guide\/"[^>]*aria-current="page"/);
  assert.match(page("index.html"), /<a href="\/guide\/"[^>]*>Guide<\/a>/);
  // Every screenshot it shows is built with the site, and has its size and a description.
  const images = [...guide.matchAll(/<img([^>]*)>/g)].map((match) => match[1]);
  assert.ok(images.length >= 5);
  for (const image of images) {
    const source = /src="([^"]+)"/.exec(image)?.[1] ?? "";
    assert.ok(statSync(join(outDir, source)).isFile(), source);
    assert.match(image, /width="\d+"/, source);
    assert.match(image, /height="\d+"/, source);
    assert.match(image, /alt="[^"]{20,}"/, source);
  }
  // The desktop guide's mistakes: 641 K is 0.055 eV, and κ_e is not also λ_e.
  const text = textOf(mainOf(guide));
  assert.match(text, /641 K, which is 0\.055 eV/);
  assert.doesNotMatch(text, /λ_?e|λbp|Ref\. \?|\?\?/);
  assert.doesNotMatch(guide, /katex-error/);
});

test("the worked examples are pages of the site, each with its screenshots and limits", () => {
  const index = page("examples/index.html");
  assert.match(page("guide/index.html"), /<a href="\/examples\/">/);
  for (const name of ["fe2val", "si-p", "awi32"]) {
    assert.match(index, new RegExp(`<a href="/examples/${name}/">`), name);
    const example = page(`examples/${name}/index.html`);
    // Filed under the guide in the header.
    assert.match(example, /<a href="\/guide\/"[^>]*aria-current="page"/, name);
    const images = [...example.matchAll(/<img([^>]*)>/g)].map((m) => m[1]);
    assert.ok(images.length >= 1, name);
    for (const image of images) {
      const source = /src="([^"]+)"/.exec(image)?.[1] ?? "";
      assert.ok(statSync(join(outDir, source)).isFile(), source);
      assert.match(image, /width="\d+"/, source);
      assert.match(image, /height="\d+"/, source);
      assert.match(image, /alt="[^"]{20,}"/, source);
    }
    // Each says what it rests on and how far to trust it.
    for (const heading of ["Data", "Interpretation", "Limits", "Reproduce"]) {
      assert.match(
        example,
        new RegExp(`<h2[^>]*>${heading}</h2>`),
        `${name}: ${heading}`,
      );
    }
    assert.doesNotMatch(example, /katex-error/, name);
  }
  // The known issues the pictured fits carry.
  assert.match(
    page("examples/awi32/index.html"),
    /<code>hall_dis_no_reference<\/code>/,
  );
  for (const name of ["fe2val", "awi32"]) {
    assert.match(page(`examples/${name}/index.html`), /issues\/247/, name);
  }
  // Every screenshot in public/examples is shown on a page.
  const shown = ["fe2val", "si-p", "awi32"]
    .map((name) => page(`examples/${name}/index.html`))
    .join("");
  for (const file of readdirSync(join(SITE_DIR, "public", "examples"))) {
    assert.match(shown, new RegExp(`src="/examples/${file}"`), file);
  }
});

/** Each page's built HTML file, and its address on the site. */
const pagesOf = (dir) =>
  files(dir)
    .filter((path) => path.endsWith(".html"))
    .map((path) => {
      const file = relative(dir, path);
      const address = `/${file.replace(/(^|\/)index\.html$/, "$1").replace(/\.html$/, "")}`;
      return { file, address };
    });

test("a build without a site address keeps every page out of search", () => {
  assert.equal(page("robots.txt"), "User-agent: *\nDisallow: /\n");
  assert.doesNotMatch(page("sitemap.xml"), /<url>/);
  for (const { file } of pagesOf(outDir)) {
    const html = page(file);
    assert.match(html, /<meta name="robots" content="noindex">/, file);
    // Absolute addresses need the site's.
    assert.doesNotMatch(html, /rel="canonical"|og:url/, file);
  }
});

/**
 * Whether robots.txt keeps a crawler out of a path, as Google reads it: a rule matches the start
 * of the path, `*` matches anything and a last `$` ends it, which a RegExp reads the same way.
 */
function disallows(robots, path) {
  return [...robots.matchAll(/^Disallow: (.+)$/gm)].some(([, rule]) => {
    const pattern = rule
      .replace(/[.+?^{}()|[\]\\]/g, "\\$&")
      .replace(/\*/g, ".*");
    return new RegExp(`^${pattern}`).test(path);
  });
}

test("a public build lists its pages and keeps the app and the API out of search", () => {
  const robots = publicPage("robots.txt");
  for (const path of [
    "/fit",
    "/fit?demo=1",
    "/fit/",
    "/results",
    "/results/",
    "/api/fit",
    "/licenses/Geist-OFL.txt",
  ]) {
    assert.ok(disallows(robots, path), path);
  }
  // The app's scripts and styles stay open, for a search engine to render its pages.
  assert.ok(!disallows(robots, "/assets/index.js"));
  assert.match(robots, new RegExp(`^Sitemap: ${SITE_URL}/sitemap.xml$`, "m"));

  const sitemap = publicPage("sitemap.xml");
  const listed = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
  const titles = new Map();
  const descriptions = new Map();
  for (const { file, address } of pagesOf(publicOutDir)) {
    const html = publicPage(file);
    const title = /<title>([^<]+)<\/title>/.exec(html)?.[1];
    const description = /<meta name="description" content="([^"]+)"/.exec(
      html,
    )?.[1];
    assert.ok(title, file);
    assert.ok(description, file);
    assert.match(html, /<meta property="og:title" content="[^"]+">/, file);
    assert.match(
      html,
      /<meta property="og:description" content="[^"]+">/,
      file,
    );
    if (file === "404.html") {
      assert.match(html, /<meta name="robots" content="noindex">/);
      assert.ok(!listed.some((url) => url.includes("404")));
      continue;
    }
    // Every other page is indexable, listed, and names itself as its canonical address, with a
    // description long enough to say what it holds.
    assert.ok(description.length >= 50, file);
    const url = `${SITE_URL}${address}`;
    assert.doesNotMatch(html, /name="robots"/, file);
    assert.match(
      html,
      new RegExp(`<link rel="canonical" href="${url}">`),
      file,
    );
    assert.match(
      html,
      new RegExp(`<meta property="og:url" content="${url}">`),
      file,
    );
    assert.ok(listed.includes(url), url);
    assert.ok(!disallows(robots, address), `robots.txt closes ${address}`);
    // Unique, so that search results tell the pages apart.
    assert.ok(
      !titles.has(title),
      `${file} has the title of ${titles.get(title)}`,
    );
    assert.ok(!descriptions.has(description), `${file} repeats a description`);
    titles.set(title, file);
    descriptions.set(description, file);
  }
  assert.equal(listed.length, titles.size);
});

test("a site address with a path, or no address at all, fails the build", () => {
  for (const value of ["https://seeband.example/sub/", "seeband.example"]) {
    const built = spawnSync(
      process.execPath,
      [
        ASTRO,
        "build",
        "--outDir",
        mkdtempSync(join(tmpdir(), "seeband-site-bad-")),
      ],
      {
        cwd: SITE_DIR,
        encoding: "utf8",
        env: {
          ...process.env,
          ASTRO_TELEMETRY_DISABLED: "1",
          SEEBAND_SITE_URL: value,
        },
      },
    );
    assert.notEqual(built.status, 0, value);
    assert.match(
      built.stderr + built.stdout,
      /SEEBAND_SITE_URL must be/,
      value,
    );
  }
});

test("the overview describes the app for search engines", () => {
  const json = /<script type="application\/ld\+json">([\s\S]*?)<\/script>/.exec(
    publicPage("index.html"),
  )?.[1];
  const application = JSON.parse(json ?? "null");
  assert.equal(application["@type"], "SoftwareApplication");
  assert.equal(application.name, "SeeBand Web");
  assert.equal(application.url, `${SITE_URL}/`);
  assert.equal(application.offers.price, "0");
  assert.match(application.description, /parabolic band/);
});

test("needs no script but the header's, and loads no heavy library", () => {
  const all = files(outDir);
  assert.deepEqual(
    all.filter((path) => path.endsWith(".js")),
    [],
    "no script files",
  );
  for (const path of all.filter((path) => path.endsWith(".html"))) {
    const html = readFileSync(path, "utf8");
    // Only the shared header's language script, which does nothing with one language. Data for
    // search engines is not a script.
    const scripts = (html.match(/<script[\s\S]*?<\/script>/g) ?? []).filter(
      (script) => !script.includes('type="application/ld+json"'),
    );
    assert.equal(scripts.length, 1, relative(outDir, path));
    assert.match(scripts[0], /seeband_language/);
    assert.ok(scripts[0].length < 1000, relative(outDir, path));
    assert.doesNotMatch(html, /plotly|pyodide/i, relative(outDir, path));
  }
});

test("serves its fonts itself, and asks no other host", () => {
  const css = files(outDir)
    .filter((path) => path.endsWith(".css"))
    .map((path) => readFileSync(path, "utf8"))
    .join("");
  assert.match(css, /Geist Variable/);
  assert.match(css, /url\(\/_astro\/geist-latin-wght-normal\.[\w-]+\.woff2\)/);
  for (const path of files(outDir).filter((p) => /\.(html|css)$/.test(p))) {
    assert.doesNotMatch(
      readFileSync(path, "utf8"),
      // What a browser loads: a link to another site is only followed when clicked.
      /\s(?:src|srcset)=["']?https?:|<link[^>]*\shref=["']?https?:|url\(\s*["']?https?:|@import\s*["']https?:/,
      relative(outDir, path),
    );
  }
  // KaTeX's styles and fonts come only with pages of text and formulas.
  const homeCss = [
    ...page("index.html").matchAll(/<link rel="stylesheet" href="([^"]+)"/g),
  ]
    .map((match) => readFileSync(join(outDir, match[1]), "utf8"))
    .join("");
  assert.doesNotMatch(homeCss, /KaTeX_Main|\.katex/);
});

test("renders formulas in MDX when built, with KaTeX's styles and no script", () => {
  const html = readFileSync(join(mathOutDir, "index.html"), "utf8");
  assert.match(html, /class="katex"/);
  assert.match(html, /class="katex-display"/);
  assert.match(
    html,
    /<annotation encoding="application\/x-tex">L = \\frac\{\\kappa_e\}\{\\sigma T\}/,
  );
  const css = files(mathOutDir)
    .filter((path) => path.endsWith(".css"))
    .map((path) => readFileSync(path, "utf8"))
    .join("");
  assert.match(css, /KaTeX_Main/);
  assert.equal(
    files(mathOutDir).filter((path) => path.endsWith(".js")).length,
    0,
  );
  // Each size of a subscript or superscript has its rule: KaTeX renamed the class between
  // versions, and with no rule an index is drawn at full size and clipped.
  const sizes = new Set(
    [
      ...html.matchAll(/class="((?:katex-)?sizing) (reset-size\d+) (size\d+)/g),
    ].map((m) => `.${m[1]}.${m[2]}.${m[3]}{`),
  );
  assert.ok(sizes.size > 0);
  for (const rule of sizes) {
    assert.ok(css.replaceAll(" ", "").includes(rule), rule);
  }
});

test("KaTeX's styles come from the version that renders the formulas", () => {
  const site = createRequire(join(SITE_DIR, "package.json"));
  const renderer = createRequire(site.resolve("rehype-katex"));
  assert.equal(site("katex").version, renderer("katex").version);
});
