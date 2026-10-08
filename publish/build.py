#!/usr/bin/env python3
"""
Chill Division SOP publisher.

Converts the Markdown SOP documents in the repository root into:
  1. Self-contained single-file HTML (responsive website with TOC navigation,
     light/dark mode, and chapter vs single-page viewing) in dist/
  2. A4-print-quality PDFs rendered from the single-page layout via a headless
     Chromium-based browser (Edge / Chrome), in dist/

Usage:
  python3 publish/build.py            # build HTML + PDF for all root *.md docs
  python3 publish/build.py --no-pdf   # HTML only
  python3 publish/build.py --docs "Chill Division Security*.md"

Dependencies: pip install markdown-it-py
PDF rendering: any installed Chromium-based browser (Edge, Chrome, Chromium).
Works on Windows, Linux, and WSL (uses the Windows browser from inside WSL).
"""

import argparse
import datetime
import glob
import html as html_lib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

try:
    from markdown_it import MarkdownIt
except ImportError:
    sys.exit("markdown-it-py is required: pip install markdown-it-py")

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLISH_DIR = Path(__file__).resolve().parent
DIST_DIR = REPO_ROOT / "dist"

# Publishing channel. "live" is the Agency-approved release (built from the
# latest v* tag). "staging" is the proposed next version built from the main
# branch: every page carries a draft banner and PDFs get a -draft suffix.
DRAFT = False
BANNER = ""

DRAFT_BANNER = """<div class="channel-banner"><strong>Proposed draft.</strong>
This version has not yet been approved by the Medicinal Cannabis Agency and may
still change or be withdrawn.
<a href="../index.html">View the current approved release</a>.</div>"""

VERSION_RE = re.compile(r"\s*v(\d+\.\d+(?:\.\d+)?)\s*(?:\(DRAFT\s*\d*\))?", re.I)
HEADING_RE = re.compile(r"<h([1-4])>(.*?)</h\1>", re.S)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "section"


def doc_meta(md_path: Path):
    """Derive title, version and output slug from the filename."""
    stem = md_path.stem
    m = VERSION_RE.search(stem)
    version = f"v{m.group(1)}" if m else ""
    title = VERSION_RE.sub("", stem).strip()
    slug_source = re.sub(r"^Chill Division\s+", "", title, flags=re.I)
    return title, version, slugify(slug_source)


def strip_leading_comment(md_text: str) -> str:
    return re.sub(r"^\s*<!--.*?-->\s*", "", md_text, count=1, flags=re.S)


SECNUM_RE = re.compile(r"^\s*(\d+)\.")
LIST_ITEM_NUM_RE = re.compile(r"^\s*(\d+)[.)]")


def apply_hierarchical_numbering(tokens, src_lines):
    """Stamp each ordered-list item with its full SOP number (e.g. 12.4.1).

    The section prefix comes from the nearest numbered heading ("12. General
    site standards ..."). Each item's own number is read from the *source line*
    that authored it, so the numbering reproduces the numbers actually written
    in the Markdown (important for Google-Docs-derived docs whose list nesting
    is irregular and whose continuation numbers CommonMark would otherwise
    renumber). Unnumbered headings at or above the prefix's level clear it;
    deeper unnumbered headings (e.g. "Battery replacement" inside section 8)
    keep it.
    """
    prefix = None
    prefix_level = None
    stack = []  # one entry per open list; {"ul": bool, "current": str|None}
    seen_ids = {}  # deduplicate item ids (authored numbers can repeat)

    for idx, tok in enumerate(tokens):
        if tok.type == "heading_open":
            level = int(tok.tag[1])
            inline = tokens[idx + 1].content if idx + 1 < len(tokens) else ""
            m = SECNUM_RE.match(inline or "")
            if m:
                prefix, prefix_level = m.group(1), level
            elif prefix_level is None or level <= prefix_level:
                prefix, prefix_level = None, None
            stack = []
        elif tok.type == "ordered_list_open":
            stack.append({"ul": False, "current": None})
            tok.attrJoin("class", "num-ol")
        elif tok.type == "bullet_list_open":
            stack.append({"ul": True, "current": None})
        elif tok.type in ("ordered_list_close", "bullet_list_close"):
            if stack:
                stack.pop()
        elif tok.type == "list_item_open" and stack and not stack[-1]["ul"]:
            num = None
            if tok.map:
                line = src_lines[tok.map[0]] if tok.map[0] < len(src_lines) else ""
                mm = LIST_ITEM_NUM_RE.match(line)
                if mm:
                    num = mm.group(1)
            stack[-1]["current"] = num
            parts = ([prefix] if prefix else []) + [
                e["current"] for e in stack if not e["ul"] and e["current"]
            ]
            if parts:
                num = ".".join(parts)
                tok.attrSet("data-num", num)
                # Anchor id so search results (and deep links) can target items.
                base = "i-" + num.replace(".", "-")
                n = seen_ids.get(base, 0)
                seen_ids[base] = n + 1
                tok.attrSet("id", base if n == 0 else f"{base}-{n}")


def render_markdown(md_text: str) -> str:
    md = MarkdownIt("commonmark", {"html": True, "linkify": False, "typographer": False})
    md.enable("table")
    tokens = md.parse(md_text)
    apply_hierarchical_numbering(tokens, md_text.split("\n"))
    return md.renderer.render(tokens, md.options, {})


def assign_heading_ids(html: str):
    """Give every h1-h4 a unique id. Returns (html, [(level, id, text), ...])."""
    seen = {}
    headings = []

    def repl(m):
        level, inner = int(m.group(1)), m.group(2)
        base = slugify(inner)
        n = seen.get(base, 0)
        seen[base] = n + 1
        hid = base if n == 0 else f"{base}-{n}"
        text = html_lib.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        headings.append((level, hid, text))
        return f'<h{level} id="{hid}">{inner}</h{level}>'

    return HEADING_RE.sub(repl, html), headings


def chapterize(html: str, headings):
    """Split rendered HTML into <section class="chapter"> blocks at the
    document's top structural heading level. Returns (html, chapter_level)."""
    if not headings:
        return f'<section class="chapter">{html}</section>', 2
    chapter_level = min(level for level, _, _ in headings)
    parts = re.split(rf"(?=<h{chapter_level}\b)", html)
    preamble = parts[0] if parts and not parts[0].startswith(f"<h{chapter_level}") else ""
    bodies = parts[1:] if preamble or not parts[0] else parts
    if not bodies:  # document had no chapter-level headings after all
        return f'<section class="chapter">{html}</section>', chapter_level
    sections = []
    for i, chunk in enumerate(bodies):
        lead = preamble if i == 0 else ""
        sections.append(f'<section class="chapter">{lead}{chunk}</section>')
    return "\n".join(sections), chapter_level


def build_toc(headings, chapter_level):
    """Nested TOC covering chapter-level and one level below, each entry
    annotated with the chapter index it belongs to."""
    items, chapter_idx = [], -1
    for level, hid, text in headings:
        if level == chapter_level:
            chapter_idx += 1
            items.append(("ch", chapter_idx, hid, text))
        elif level == chapter_level + 1 and chapter_idx >= 0:
            items.append(("sub", chapter_idx, hid, text))

    out = ["<ul>"]
    open_sub = False
    for kind, ch, hid, text in items:
        esc = html_lib.escape(text)
        if kind == "ch":
            if open_sub:
                out.append("</ul></li>")
                open_sub = False
            elif len(out) > 1:
                out.append("</li>")
            out.append(f'<li><a href="#{hid}" data-ch="{ch}">{esc}</a>')
        else:
            if not open_sub:
                out.append("<ul>")
                open_sub = True
            out.append(f'<li><a href="#{hid}" data-ch="{ch}">{esc}</a></li>')
    if open_sub:
        out.append("</ul></li>")
    elif len(out) > 1:
        out.append("</li>")
    out.append("</ul>")
    return "\n".join(out)


def shown(path: Path) -> Path:
    """A path for log output: repo-relative when inside the repo (the usual
    dist/ case), otherwise as given, since --out may point anywhere."""
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def fill(template: str, mapping: dict) -> str:
    for key, value in mapping.items():
        template = template.replace(f"@@{key}@@", value)
    return template


# ---------------------------------------------------------------------------
# Search index
# ---------------------------------------------------------------------------

# Short labels for search-result chips on the index page.
SHORT_NAMES = {
    "site-design-guidelines": "Site Design",
    "security-policies-and-procedures": "Security",
    "cultivation-procedures": "Cultivation",
    "advertising-sops": "Advertising",
    "automations-guide": "Automations",
    "how-to-use-these-documents": "How to use",
}

# The reader-orientation document the "How to use" modal links to.
HOWTO_SLUG = "how-to-use-these-documents"

# Documents kept off the published site entirely (no page, PDF, index card or
# search entries) while they are still being written. Remove a slug to publish
# it. Build with --include-unpublished to preview them locally.
UNPUBLISHED_DOCS = {"advertising-sops"}


class SearchIndexExtractor(HTMLParser):
    """Extract search entries from a document's rendered HTML.

    Emits one entry per heading ("h"), numbered list item ("i"), and body
    block ("b": paragraphs, bullet items, table rows). Each entry carries the
    nearest anchor id so cross-document results can deep-link straight to it.
    Text before the first heading (the cover block) has no anchor and is
    skipped. Numbered items capture their direct text only; nested items
    become their own entries.
    """

    HEADING_TAGS = {"h1", "h2", "h3", "h4"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.entries = []
        self.anchor = None   # id of the nearest preceding heading
        self._h = None       # (id, buf) while inside a heading
        self._li = []        # stack of open <li> frames
        self._p = None       # buf while inside a top-level <p>
        self._tr = None      # buf while inside a table row
        self._thead = False  # header rows are labels, not content

    def _emit(self, kind, anchor, text, num=None):
        text = " ".join(text.split())
        if len(text) < 3 or not anchor:
            return
        entry = {"k": kind, "id": anchor, "t": text}
        if num:
            entry["n"] = num
        self.entries.append(entry)

    def _append(self, s):
        if self._h is not None:
            self._h[1].append(s)
        elif self._tr is not None:
            self._tr.append(s)
        elif self._p is not None:
            self._p.append(s)
        elif self._li and self._li[-1]["depth"] == 0:
            self._li[-1]["buf"].append(s)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.HEADING_TAGS:
            self._h = (a.get("id"), [])
        elif tag == "li":
            self._li.append({"id": a.get("id"), "num": a.get("data-num"),
                             "buf": [], "depth": 0})
        elif tag in ("ol", "ul") and self._li:
            self._li[-1]["depth"] += 1
        elif tag == "p" and not self._li and self._h is None and self._tr is None:
            self._p = []
        elif tag == "thead":
            self._thead = True
        elif tag == "tr" and not self._thead:
            self._tr = []
        elif tag == "br":
            self._append(" ")

    def handle_endtag(self, tag):
        if tag in self.HEADING_TAGS and self._h is not None:
            hid, buf = self._h
            self._h = None
            self._emit("h", hid, "".join(buf))
            if hid:
                self.anchor = hid
        elif tag == "li" and self._li:
            frame = self._li.pop()
            anchor = frame["id"] or next(
                (f["id"] for f in reversed(self._li) if f["id"]), self.anchor)
            if frame["num"]:
                self._emit("i", anchor, "".join(frame["buf"]), frame["num"])
            else:
                self._emit("b", anchor, "".join(frame["buf"]))
        elif tag in ("ol", "ul") and self._li:
            self._li[-1]["depth"] -= 1
        elif tag == "p":
            if self._p is not None:
                self._emit("b", self.anchor, "".join(self._p))
                self._p = None
            else:
                self._append(" ")  # block boundary inside li / tr
        elif tag == "thead":
            self._thead = False
        elif tag == "tr" and self._tr is not None:
            self._emit("b", self.anchor, "".join(self._tr))
            self._tr = None
        elif tag in ("td", "th"):
            self._append(" ")

    def handle_data(self, data):
        self._append(data)


def extract_search_entries(body_html: str):
    extractor = SearchIndexExtractor()
    extractor.feed(body_html)
    extractor.close()
    return extractor.entries


# ---------------------------------------------------------------------------
# Standalone forms
# ---------------------------------------------------------------------------

# Sections lifted out of their parent document at build time into their own
# print-ready page + PDF. The fragment runs from the given heading id to the
# next heading of the same or higher level.
EXTRACT_FORMS = [
    {
        "doc": "security-policies-and-procedures",
        "heading_id": "chill-division-universal-shipping-manifest",
        "slug": "shipping-manifest",
    },
]


def extract_fragment(body_html: str, heading_id: str):
    """Cut a section out of rendered HTML. Returns (fragment, title) with the
    section heading promoted to h1 for standalone use, or (None, None)."""
    m = re.search(rf'<h([1-4]) id="{re.escape(heading_id)}">', body_html)
    if not m:
        return None, None
    level = int(m.group(1))
    nxt = re.search(rf"<h[1-{level}]\b", body_html[m.end():])
    end = m.end() + nxt.start() if nxt else len(body_html)
    frag = body_html[m.start():end]
    tm = re.search(r">(.*?)</h", frag, re.S)
    title = html_lib.unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip()
    frag = re.sub(rf"^<h{level}", "<h1", frag, count=1)
    frag = frag.replace(f"</h{level}>", "</h1>", 1)
    return frag, title


def build_form(form, body_html, version, template, css, generated):
    """Build a standalone page for an extracted form. Returns (title, version,
    slug) for the index and PDF steps, or None if the heading wasn't found."""
    frag, title = extract_fragment(body_html, form["heading_id"])
    if not frag:
        print(f"!! form heading not found: {form['heading_id']}", file=sys.stderr)
        return None
    content = f'<section class="chapter current">{frag}</section>'
    toc = (f'<ul><li><a href="#{form["heading_id"]}" data-ch="0">'
           f"{html_lib.escape(title)}</a></li></ul>")
    page = fill(template, {
        "TITLE": html_lib.escape(title),
        "VERSION": version,
        "BODYCLASS": "is-form",
        "CSS": css,
        "TOC": toc,
        "CONTENT": content,
        "GENERATED": generated,
        "SEARCHDATA": "",
        "SEARCHPH": "Search this form",
        "BANNER": BANNER,
    })
    out_html = DIST_DIR / f"{form['slug']}.html"
    out_html.write_text(page, encoding="utf-8")
    print(f"  HTML  {shown(out_html)}")
    return title, version, form["slug"]


# ---------------------------------------------------------------------------
# PDF via headless Chromium (Edge / Chrome)
# ---------------------------------------------------------------------------

# Chrome is preferred over Edge: Edge's launcher can silently hand a headless
# invocation to a running Edge browser and exit 0 without printing anything.
WINDOWS_BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def is_wsl() -> bool:
    if sys.platform != "linux":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def find_browser():
    """Returns (path, kind) where kind is 'windows' or 'native'."""
    env = os.environ.get("CHROME_BIN") or os.environ.get("SOP_BROWSER")
    if env and Path(env).exists():
        kind = "windows" if env.lower().endswith(".exe") and sys.platform == "linux" else "native"
        return env, kind
    if sys.platform == "win32":
        for p in WINDOWS_BROWSERS:
            if Path(p).exists():
                return p, "native"
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            p = shutil.which(name)
            if p:
                return p, "native"
        if is_wsl():
            for p in WINDOWS_BROWSERS:
                wsl_p = "/mnt/c/" + p[3:].replace("\\", "/")
                if Path(wsl_p).exists():
                    return wsl_p, "windows"
    return None, None


def html_to_pdf(html_path: Path, pdf_path: Path, browser: str, kind: str) -> bool:
    """Print a built HTML file to PDF. When the browser is a Windows exe used
    from WSL, point it straight at the WSL filesystem over \\\\wsl.localhost:
    it reads the HTML from dist/ in place and writes the PDF back there, so
    nothing is staged on the Windows side. The throwaway browser profile is a
    fresh temp dir per conversion: killing a timed-out Windows browser from
    WSL only kills the interop wrapper, and a survivor holding a shared
    profile would swallow every later launch."""
    cleanup_dir = None
    if kind == "windows" and sys.platform == "linux":
        distro = os.environ.get("WSL_DISTRO_NAME")
        if distro:
            cleanup_dir = Path(tempfile.mkdtemp(prefix="sop-pdf-profile-"))
            unc_root = rf"\\wsl.localhost\{distro}"
            url = f"file://wsl.localhost/{distro}" + quote(str(html_path.resolve()))
            out_arg = unc_root + str(pdf_path.resolve()).replace("/", "\\")
            staged_pdf = pdf_path
            profile = unc_root + str(cleanup_dir).replace("/", "\\")
        else:
            # Not in WSL proper (no distro name): stage on the Windows side.
            stage = Path(tempfile.mkdtemp(prefix="sop-pdf-", dir="/mnt/c/Users/Public"))
            cleanup_dir = stage
            shutil.copy2(html_path, stage / html_path.name)
            win_stage = "C:\\Users\\Public\\" + stage.name
            url = f"file:///C:/Users/Public/{stage.name}/{html_path.name}"
            out_arg = f"{win_stage}\\{pdf_path.name}"
            staged_pdf = stage / pdf_path.name
            profile = f"{win_stage}\\profile"
    else:
        url = html_path.resolve().as_uri()
        out_arg = str(pdf_path.resolve())
        staged_pdf = pdf_path
        profile = str(Path(tempfile.gettempdir()) / "sop-publish-profile")

    base_flags = [
        "--disable-gpu",
        "--disable-extensions",
        "--no-first-run",
        f"--user-data-dir={profile}",
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",  # older Chromium name; unknown flags are ignored
        f"--print-to-pdf={out_arg}",
        url,
    ]
    if sys.platform == "linux" and kind == "native":
        base_flags.insert(0, "--no-sandbox")

    ok = False
    result = None
    for headless in ("--headless=new", "--headless"):
        try:
            staged_pdf.unlink(missing_ok=True)
            result = subprocess.run(
                [browser, headless] + base_flags,
                check=False, capture_output=True, timeout=180,
            )
            if staged_pdf.exists() and staged_pdf.stat().st_size > 0:
                ok = True
                break
        except subprocess.TimeoutExpired:
            print(f"!! {pdf_path.name}: {headless} timed out after 180s "
                  "(a stray browser process may still be running)", file=sys.stderr)
        except OSError as exc:
            print(f"!! {pdf_path.name}: could not launch browser: {exc}",
                  file=sys.stderr)

    if not ok and result is not None:
        tail = (result.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-3:]
        detail = " | ".join(line.strip() for line in tail) or "(no stderr)"
        print(f"!! {pdf_path.name}: browser exit code {result.returncode}: {detail}",
              file=sys.stderr)

    if ok and staged_pdf != pdf_path:
        shutil.copy2(staged_pdf, pdf_path)
    if cleanup_dir is not None:
        shutil.rmtree(cleanup_dir, ignore_errors=True)
    return ok


# ---------------------------------------------------------------------------
# Index page
# ---------------------------------------------------------------------------

INDEX_BODY = """
<div class="print-only print-title">
  <div class="pt-brand">Chill Division</div>
  <h1>Standard Operating Procedures</h1>
</div>
<section class="chapter current">
<h2 id="documents">Documents</h2>
<p>Chill Division Standard Operating Procedures and design guidance for a
soilless-media medicinal cannabis cultivation facility in New Zealand.</p>

<p><strong>These SOPs won't get you licensed in and of themselves.</strong>
Licensing turns on your implementation, which the Medicinal Cannabis Agency
assesses as a whole, so every site needs judgement these documents can't make for
you. A formal
<a href="https://chilldivision.co.nz/contact.html">regulatory consultation</a> can
review your location and floorplan, pressure-test your security arrangements
against the Agency's expectations, identify gaps before they become problems, and
help you engage the Agency and Police with confidence. Engage early, ideally
before you sign a lease or start your fit-out. New here?
<a href="how-to-use-these-documents.html" data-howto>See how to use these
documents</a>.</p>

<div class="doc-cards">
{cards}
</div>
{forms}
<blockquote class="notice">
<p><strong>You're welcome to use and adapt these, just don't take the credit.</strong>
The SOP documents are licensed under
<a href="https://github.com/Chill-Division/SOPs/blob/main/LICENSE">CC BY-SA 4.0</a>:
use them, adapt them to your own facility, even commercially. In return you must
<strong>keep the Chill Division attribution</strong>, note what you changed, and
share any public derivative under the same open license. "Chill Division", the
logo, and the letterhead are trademarks. Reuse the content, not the brand, and
don't pass the work off as your own. See
<a href="https://github.com/Chill-Division/SOPs/blob/main/NOTICE"><code>NOTICE</code></a>
for the details.</p>
</blockquote>

<blockquote class="notice">
<p><strong>No AI use.</strong> These SOPs were written by a human. The underlying
framework for displaying and formatting these SOPs online has been done with AI,
but not the content itself. We won't accept commits, contributions or suggestions
from LLMs. There is a lot of nuance in all of these, and the last thing that we
need is some AI suggesting cultivation facilities are run under GACP / GMP or
other such mistakes, due to a lack of that context-specific awareness.</p>
</blockquote>

<blockquote class="notice">
<p><strong>Improvements are welcome.</strong> These documents are maintained
openly at
<a href="https://github.com/Chill-Division/SOPs">github.com/Chill-Division/SOPs</a>.
Corrections, clarifications and regulatory updates are all fair game. Open an
issue to discuss anything substantial before writing it, or send a small,
focused pull request. The
<a href="https://github.com/Chill-Division/SOPs/blob/main/README.md">README</a>
covers how: keep changes tightly scoped, and bump the document version and
changelog in the same change.</p>
</blockquote>
</section>
"""


ROBOTS_TXT = """# Chill Division SOPs.
# These documents are licensed CC BY-SA 4.0 but we ask that they not be indexed
# by search engines or ingested for AI training. robots.txt is advisory only;
# a per-page <meta name="robots" content="noindex"> is also set on every page.
User-agent: *
Disallow: /

# Named AI / dataset crawlers (explicit, in addition to the blanket rule above)
User-agent: GPTBot
Disallow: /

User-agent: OAI-SearchBot
Disallow: /

User-agent: ChatGPT-User
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: anthropic-ai
Disallow: /

User-agent: Claude-Web
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: PerplexityBot
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: Amazonbot
Disallow: /

User-agent: Applebot-Extended
Disallow: /

User-agent: meta-externalagent
Disallow: /
"""


def write_robots():
    (DIST_DIR / "robots.txt").write_text(ROBOTS_TXT, encoding="utf-8")


def pdf_name(slug: str, version: str) -> str:
    """PDFs are downloaded as files, so carry the version in the filename.
    The HTML pages are only viewed online and stay unversioned. Staging PDFs
    are additionally marked -draft so they can't be mistaken for approved."""
    parts = [slug] + ([version] if version else []) + (["draft"] if DRAFT else [])
    return "-".join(parts) + ".pdf"


def doc_card(title, version, slug):
    display = re.sub(r"^Chill Division\s+", "", title, flags=re.I)
    return (
        f'<div class="doc-card"><h3>{html_lib.escape(display)}</h3>'
        f'<span class="version-badge">{version or "draft"}</span>'
        f'<div class="doc-links"><a class="primary" href="{slug}.html">View online</a>'
        f'<a href="{pdf_name(slug, version)}">PDF</a></div></div>'
    )


def build_index(docs, template, css, generated, search_index, forms=()):
    cards = [doc_card(*doc) for doc in docs]
    forms_html = ""
    if forms:
        forms_html = (
            '\n<h3 id="forms">Forms</h3>\n'
            "<p>Print-ready forms, extracted from the documents above at build time.</p>\n"
            '<div class="doc-cards">\n'
            + "\n".join(doc_card(*form) for form in forms)
            + "\n</div>\n"
        )
    body = INDEX_BODY.format(cards="\n".join(cards), forms=forms_html)
    toc = '<ul><li><a href="#documents" data-ch="0">Documents</a></li></ul>'
    payload = json.dumps(search_index, ensure_ascii=False,
                         separators=(",", ":")).replace("</", "<\\/")
    page = fill(template, {
        "TITLE": "Chill Division SOPs",
        "VERSION": "",
        "BODYCLASS": "is-index",
        "CSS": css,
        "TOC": toc,
        "CONTENT": body,
        "GENERATED": generated,
        "SEARCHDATA": f"<script>window.SEARCH_INDEX = {payload};</script>",
        "SEARCHPH": "Search all documents",
        "BANNER": BANNER,
    })
    (DIST_DIR / "index.html").write_text(page, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build SOP website + PDFs")
    parser.add_argument("--docs", default="*.md",
                        help="Glob (relative to repo root) selecting documents")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    parser.add_argument("--include-unpublished", action="store_true",
                        help="Also build the documents listed in UNPUBLISHED_DOCS, "
                             "for previewing them locally")
    parser.add_argument("--channel", choices=("live", "staging"), default="live",
                        help="live (default) = the approved release; staging adds "
                             "a draft banner to every page and -draft PDF names")
    parser.add_argument("--out", default="dist",
                        help="Output directory, relative to the repo root "
                             "(default: dist; staging typically uses dist/staging)")
    args = parser.parse_args()

    global DIST_DIR, DRAFT, BANNER
    DRAFT = args.channel == "staging"
    BANNER = DRAFT_BANNER if DRAFT else ""
    out = Path(args.out)
    DIST_DIR = out if out.is_absolute() else REPO_ROOT / out

    css = (PUBLISH_DIR / "style.css").read_text(encoding="utf-8")
    template = (PUBLISH_DIR / "template.html").read_text(encoding="utf-8")
    generated = datetime.date.today().isoformat()

    candidates = [
        p for p in (REPO_ROOT / f for f in glob.glob(args.docs, root_dir=REPO_ROOT))
        if p.suffix == ".md" and p.name.lower() != "readme.md" and p.parent == REPO_ROOT
    ]

    # Explicit reading order for the index and build; unknown docs fall to the
    # end, sorted alphabetically by slug.
    doc_order = [
        "site-design-guidelines",
        "security-policies-and-procedures",
        "cultivation-procedures",
        "advertising-sops",
        "automations-guide",
        "how-to-use-these-documents",
    ]

    def order_key(path):
        slug = doc_meta(path)[2]
        return (doc_order.index(slug), "") if slug in doc_order else (len(doc_order), slug)

    md_files = sorted(candidates, key=order_key)
    if not args.include_unpublished:
        for path in md_files:
            if doc_meta(path)[2] in UNPUBLISHED_DOCS:
                print(f"  SKIP  {path.name} (unpublished)")
        md_files = [p for p in md_files if doc_meta(p)[2] not in UNPUBLISHED_DOCS]
    if not md_files:
        sys.exit(f"No documents matched {args.docs!r} in {REPO_ROOT}")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    built = []
    forms_built = []
    search_docs, search_entries = [], []

    for md_path in md_files:
        title, version, slug = doc_meta(md_path)
        raw = strip_leading_comment(md_path.read_text(encoding="utf-8"))
        body = render_markdown(raw)
        body, headings = assign_heading_ids(body)

        display = re.sub(r"^Chill Division\s+", "", title, flags=re.I)
        doc_idx = len(search_docs)
        search_docs.append({"s": slug, "n": SHORT_NAMES.get(slug, display)})
        for entry in extract_search_entries(body):
            entry["d"] = doc_idx
            search_entries.append(entry)

        content, chapter_level = chapterize(body, headings)
        toc = build_toc(headings, chapter_level)
        page = fill(template, {
            "TITLE": html_lib.escape(title),
            "VERSION": version,
            "BODYCLASS": "is-howto" if slug == HOWTO_SLUG else "",
            "CSS": css,
            "TOC": toc,
            "CONTENT": content,
            "GENERATED": generated,
            "SEARCHDATA": "",
            "SEARCHPH": "Search this document",
            "BANNER": BANNER,
        })
        out_html = DIST_DIR / f"{slug}.html"
        out_html.write_text(page, encoding="utf-8")
        built.append((title, version, slug))
        print(f"  HTML  {shown(out_html)}")

        for form in EXTRACT_FORMS:
            if form["doc"] == slug:
                result = build_form(form, body, version, template, css, generated)
                if result:
                    forms_built.append(result)

    build_index(built, template, css, generated,
                {"docs": search_docs, "entries": search_entries}, forms_built)
    print(f"  HTML  {shown(DIST_DIR / 'index.html')}")

    if args.channel == "live":
        # robots.txt only belongs at the site root; the staging subdirectory
        # is covered by the root file's blanket Disallow.
        write_robots()
        print(f"  META  {shown(DIST_DIR / 'robots.txt')}")

    if not args.no_pdf:
        browser, kind = find_browser()
        if not browser:
            print("!! No Chromium-based browser found - skipping PDFs. "
                  "Set CHROME_BIN to a Chrome/Edge/Chromium binary.", file=sys.stderr)
        else:
            print(f"  PDF engine: {browser}")
            for title, version, slug in built + forms_built:
                out_pdf = DIST_DIR / pdf_name(slug, version)
                if html_to_pdf(DIST_DIR / f"{slug}.html", out_pdf, browser, kind):
                    print(f"  PDF   {shown(out_pdf)}")
                else:
                    print(f"!! PDF failed for {slug}", file=sys.stderr)

    print("Done.")


if __name__ == "__main__":
    main()
