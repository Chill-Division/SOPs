# Chill Division — Cultivation Facility SOPs

This repository holds Chill Division's Standard Operating Procedures and design
guidance for a soilless-media medicinal cannabis cultivation facility in New
Zealand. At the request of the Medicinal Cannabis Agency, the material is being
split from a single combined document into a suite of focused documents.

**Read online: [sops.chilldivision.co.nz](https://sops.chilldivision.co.nz/)**.
The published site has every document viewable in the browser and downloadable
as an A4 PDF. It is rebuilt and deployed automatically from `main`, so it always
reflects the latest merged version. (`chill-division.github.io/SOPs` redirects
here.)

> **You're welcome to use and adapt these, just don't take the credit.** The
> SOP documents are licensed under [CC BY-SA 4.0](LICENSE): use them, adapt them
> to your own facility, even commercially. In return you must **keep the Chill
> Division attribution**, note what you changed, and share any public
> derivative under the same open license. "Chill Division", the logo, and the
> letterhead are trademarks. Reuse the content, not the brand, and don't pass
> the work off as your own. See [`NOTICE`](NOTICE) for the details.

## Documents

| Document | Status | Purpose |
| --- | --- | --- |
| **Site Design Guidelines** (`v3.0.1`) | Current | Site selection, build, fit-out and design of the facility. |
| **Cultivation Procedures** (`v3.0.1`) | Current, from v2.6.1 §1-12 | Day-to-day growing: propagation, veg, flower, harvest, drying, trimming, IPM, nutrients, testing. |
| **Security Policies & Procedures** (`v3.0.1`) | Current, from v2.6.1 §13-37 | Access control, surveillance, staff / visitor procedures, records, disposal, inward / outward goods. |
| **Advertising SOPs** (`v3.0.1`) | In progress, not yet published on the website | Advertising and promotion within the New Zealand regulatory constraints. |
| **Automations Guide** (`v3.0.1`, bonus) | Current, from a working HA config | How to set up the automations referenced in the other docs: sensors, Home Assistant helpers, ESPHome vs Home Assistant logic. |
| **How to use these documents** (`v3.0.1`) | Framework only, content to come | The basics for new readers: what these documents are, how to read them, and where to start. |

A licence application is expected to include the Site Design, Cultivation, and
Security documents together. The first chapter (building/security requirements)
is intentionally shared between the Site Design and Security documents.

## Important: these SOPs alone will not get you a licence

Submitting these documents with a licence application does not, in and of
itself, result in a Medicinal Cannabis Licence being granted. The Medicinal
Cannabis Agency assesses the totality of your arrangements, and what matters
most is your **implementation**: that your facility, security arrangements, and
day-to-day operations actually follow what these documents describe. Treat the
SOPs as the blueprint you will be audited against, not as a form to be filed. You
should seek formal
[regulatory consultation](https://chilldivision.co.nz/contact.html) on
implementation of them.

## Conventions

- **Terminology** follows [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119)
  (MUST / SHOULD / MAY). Use these keywords deliberately — a "should" is a strong
  recommendation, a "must" is a hard requirement. Please don't use them loosely.
- **Versioning** uses Semantic Versioning (`Major.Minor.Patch`) or ISO 8601 dates,
  as required by the SOPs themselves. Bump the version and add a changelog entry
  in the same change that alters content.
- **Changelog** — every document keeps a changelog / document-history section at
  the end. Summarise what changed and why, referencing the affected section (e.g.
  `§2.10`).

## Contributing via pull request

We want changes to these SOPs to go through pull requests so they can be
reviewed, discussed, and traced over time.

**Keep changes small.** Versions of these documents are cleared with the
Medicinal Cannabis Agency ahead of time, so large rewrites are strongly
discouraged — every substantial change has to be re-reviewed against what the
Agency has already accepted. Small, incremental, well-reasoned PRs are far more
likely to be merged than sweeping restructures. If you believe a large change is
warranted, open an issue to discuss it *before* writing it.

**How releases work.** `main` is the current release, the version the Medicinal
Cannabis Agency has approved, and it is what the live website publishes.
Proposed changes for the next version are gathered on the `staging` branch,
which is published separately as a clearly marked draft at `/staging/`. Once the
Agency approves a proposed version, `staging` becomes the new release on `main`
and is tagged (e.g. `v3.1.0`). Until then, follow the released documents, not
the draft. **Pull requests should target `staging`, not `main`.**

1. **Branch** off `staging`, using a short descriptive name such as
   `site-design/wall-lining` or `security/duress-buttons`.
2. **Make focused changes.** One topic per PR where possible, as it makes review
   and rollback far easier.
3. **Update the version and changelog** in any document you change.
4. **Open a PR into `staging`** describing what changed and, importantly, *why*.
   Cite the section number(s) affected. If a change is driven by a regulatory
   requirement, link or quote the source.
5. **Review & merge.** A maintainer reviews for correctness, regulatory alignment,
   and clarity before merging.

### Commit messages

Keep the subject line short and imperative ("Reword wall-lining expectations for
chiller panels"). Put the reasoning in the body.

## On the use of AI

**No AI use.** These SOPs were written by a human. The underlying framework for
displaying and formatting these SOPs online has been done with AI, but not the
content itself. We won't accept commits, contributions or suggestions from LLMs.
There is a lot of nuance in all of these, and the last thing that we need is some
AI suggesting cultivation facilities are run under GACP / GMP or other such
mistakes, due to a lack of that context-specific awareness.

The content comes from real hands-on cultivation and facility experience. This is
a regulated, safety-critical domain where a confident-sounding hallucination can
cost a crop, fail an audit, or put someone at risk, so we ask you to hold the same
line. Contributions that are clearly predominantly AI-generated will not be
accepted.

## Publishing (website + PDF)

`publish/build.py` turns every root-level document into:

1. a **self-contained single-file HTML** site in `dist/` — responsive
   (desktop / tablet / phone), light mode with blue accents by default plus a
   dark-mode toggle, a table-of-contents sidebar, and a switch between
   chapter-by-chapter and single-page viewing;
2. an **A4 print-quality PDF** of each document, rendered from the single-page
   layout via a headless Chromium-based browser (Edge / Chrome / Chromium).

Styling lives in `publish/style.css` (inlined at build time) and the page shell
in `publish/template.html`.

The site has two channels:

- **Live** (site root) is the Agency-approved release, built from `main`.
- **Staging** (`/staging/`) is the proposed next version, built from the
  `staging` branch. Every page carries a "not yet approved" banner and PDFs are
  suffixed `-draft` so they can't be mistaken for the approved ones. The staging
  PDF bundle is what gets submitted to the Agency for approval.

Documents that are still being written can be kept off the website entirely
(no page, PDF, index card or search results) by listing them in
`UNPUBLISHED_DOCS` at the top of `publish/build.py`. This needs no version bump,
and removing a document from the list publishes it.

Run locally (WSL or any Linux/macOS/Windows with Python 3.10+):

```sh
pip install markdown-it-py
python3 publish/build.py          # HTML + PDFs into dist/
python3 publish/build.py --no-pdf # HTML only
python3 publish/build.py --channel staging --out dist/staging  # draft site
python3 publish/build.py --include-unpublished  # preview unpublished docs too
```

Once the Agency approves the proposed version, a maintainer squashes `staging`
into `main` as the new release, tags it, and resets `staging` on top of it:

```sh
git checkout staging && git checkout --orphan _release
git commit -m "v3.1 unified release"
git branch -M main && git tag v3.1.0
git push --force origin main v3.1.0
git branch -f staging main && git push --force origin staging
```

PDF generation auto-detects an installed browser (on WSL it borrows the Windows
Chrome / Edge, preferring Chrome). Set `CHROME_BIN` to override. If PDFs fail
with "browser exit code 0" and no stderr, that is Edge silently handing the job
to an already-open Edge browser. Close Edge or install Chrome. In CI, the
[`publish.yml`](.github/workflows/publish.yml) workflow builds both channels on
every push and pull request to `main` or `staging` (and on manual dispatch),
uploads `dist/` as an artifact, and deploys the site to GitHub Pages at
[sops.chilldivision.co.nz](https://sops.chilldivision.co.nz/). Only `main` is
allowed to deploy, so a push to `staging` asks GitHub to run the deploy from
`main`, which rebuilds both channels.

## Licensing

Two kinds of material, two licenses:

- **The SOP documents** (the Markdown in the repo root and the generated
  HTML/PDF) — **[CC BY-SA 4.0](LICENSE)**. Standard, unmodified. You may use,
  adapt, and redistribute them (including commercially) provided you keep the
  Chill Division attribution, indicate changes, and license public derivatives
  under the same terms.
- **The publishing tooling** (`publish/`, `.github/`) — **[MIT](publish/LICENSE)**.

[`NOTICE`](NOTICE) adds the parts that live *alongside* the license without
restricting it: the trademark reservation ("Chill Division", logo, and
letterhead are not licensed — reuse the content, not the brand), the "this does
not itself grant you a licence / no warranty" statement, and a provenance note.

Contributions are accepted under the same licenses, certified with a Developer
Certificate of Origin sign-off — commit with `git commit -s` to add the
`Signed-off-by:` line.
