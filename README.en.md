<p align="center">
  <img src="public_site/assets/readme-hero.svg" alt="Guitar Atlas — A multi-source guitar score catalog" width="100%">
</p>

<p align="center">
  <a href="https://lin-qian123.github.io/guitar-atlas/"><strong>Live catalog</strong></a>
  · <a href="README.md">中文</a>
  · <a href="#quick-start">Quick start</a>
  · <a href="#cataloging-and-search">Method</a>
</p>

<p align="center">
  <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-17283b?style=flat-square">
  <img alt="Sources IMSLP and ClassClef" src="https://img.shields.io/badge/sources-IMSLP_%2B_ClassClef-bd452f?style=flat-square">
  <img alt="Public site excludes score files" src="https://img.shields.io/badge/public_site-score_files_excluded-a67542?style=flat-square">
  <img alt="License MIT and CC BY-SA 4.0" src="https://img.shields.io/badge/license-MIT_%2B_CC_BY--SA_4.0-17283b?style=flat-square">
</p>

**Guitar Atlas** is a guitar score catalog and local offline library designed for multiple sources. Its current sources are [IMSLP](https://imslp.org/) and [ClassClef](https://www.classclef.com/). It organizes source attribution, titles, musicians, and categories through independent source adapters, allowing other websites to be added later.

Records retain their source identity, editions, and category memberships. Similar titles across websites are not automatically merged. Original titles and musician attributions remain intact; reviewed Chinese reference names assist discovery. The repository has been renamed from `imslp-guitar` to `guitar-atlas`; existing local directories do not need to move.

## Two editions

| Edition | Purpose | Score access |
| --- | --- | --- |
| **Public site** in `public_site/` | GitHub Pages search and source navigation | Links to source work or directory pages |
| **Local offline library** at the generated root page | Browsing a computer or drive holding the collection | Links verified local PDFs and preserves source pages |

Both editions share the HTML template, styles, and search logic. The public site contains no PDF, MIDI, GPX, download URLs, local paths, file hashes, or private runtime metadata. Git tracks code, configuration, review assets, and the public catalog without score files.

## Current sources and scope

| Source | Organization | Verification boundary |
| --- | --- | --- |
| **IMSLP** | Approved exact instrumentation categories for classical/acoustic guitar solos, ensembles, and guitar chamber music | Originals and arrangements remain separate; files must match their target sections; original category names are preserved |
| **ClassClef** | Source repertoire and musician directories, kept as separate source categories | Public score records and verifiable PDF downloads; unspecified instrumentation, original/arrangement status, and Chinese names remain unspecified |

### Catalog snapshot: 2026-09-28

| Source | Source records | Categories | Memberships |
| --- | ---: | ---: | ---: |
| IMSLP | 11,393 | 352 | 12,548 |
| ClassClef | 6,740 | 77 | 7,025 |
| **Total** | **18,133** | **429** | **19,573** |

ClassClef includes **6,739 score records and 1 reference record**. Its frozen 5,937 posts and 126 pages yield 6,063 API records and 6,062 distinct pages. All 12,648 source rows and 23,152 format links are preserved. Source-record counts do not establish unique musical works across websites.

- **File coverage:** 8,290 of 8,521 PDF/ZIP source URLs have verified local content, including reuse of an existing IMSLP file; 231 remain HTTP 404 after retry. No pending, retryable, invalid-file, or access-blocked states remain.
- **Local content:** ClassClef references 8,578 distinct PDF contents, approximately 5.535 GB: 8,577 source objects and 1 reused IMSLP file. Of 320 score archives, 304 were successfully expanded into 638 PDF members, counted before content deduplication. These are not counts of new PDFs unique to the entire library.
- **Availability:** 2 records offer GPX/MIDI only and 68 have PDF links but no successful files, giving 70 records without a local PDF. Another 127 records have only some versions available.

Fresh cross-source checks replaced 169 duplicate copies with shared hard links, saving **60,879,123 bytes**. Two other candidates retained their ClassClef originals because the IMSLP source files failed verification. The 741 Python tests, 32 Node search tests, and public privacy validation passed. Final source verification, full offline rebuilding, and remote publication remain in progress; see [TODO.md](TODO.md).

IMSLP has 11,393 reviewed Chinese work titles. Its existing manifest contains 22,637 PDF records, including 22,572 previously validated entries and 65 unavailable entries; the new offline links additionally apply the six exact instrumentation exclusions below. Historical entry counts are neither unique physical PDF counts nor a fresh full-library acceptance result.

IMSLP's instrumentation rules apply to that source only. A ClassClef directory label does not establish verified instrumentation. Each run is measured against a frozen source snapshot; later upstream additions, removals, and broken links are reported separately.

**Current IMSLP instrumentation review:** six records with an extra bass instrument explicitly named in their source sections have been reviewed by source, category, `work_id`, and filename. They are listed in [`config/score_exclusions.json`](config/score_exclusions.json) and excluded from the new offline file links; original files remain intact. The new interface also withholds links to the two affected legacy detailed category pages. **495 `Work-level target-guitar score` records and 33 other section candidates** still await exact file-level instrumentation review. The current run does not establish a fresh category-purity pass for the entire library; PDF integrity checks do not establish instrumentation.

## Cataloging and search

### Identity and categories

A record is identified by its source and source-native record ID, represented by **`source_id` + `source_record_id`** in the public schema. IMSLP retains its native `work_id`; multiple memberships of the same source work are displayed together. Similar titles, composers, or filenames across sources help discovery but do not establish that works, arrangements, or files are identical.

IMSLP's pure-guitar scope is configured in [`config/categories.json`](config/categories.json); guitar chamber scope is configured in [`config/mixed_categories.json`](config/mixed_categories.json). Electric, bass, Hawaiian, steel, and slide guitar; voice/chorus; electronics/tape; large orchestras; and alternative-solo categories where guitar is only an `or` option are excluded. Mixed categories are grouped into strings, woodwinds, brass, keyboard/free reed, plucked instruments, percussion, and mixed chamber ensembles.

Original categories accept only original scores and parts. `(arr)` categories accept only fully matching target-instrumentation sections in the page's `FILES` area. Unicode and markup are normalized before an anchored match, excluding unconfigured additions such as voice, bass, or other instruments.

ClassClef retains source titles, musician attributions, page URLs, and directory memberships. Missing information remains unspecified; the site name, title, or link does not establish original/arrangement status, difficulty, or instrument count. Unreviewed Chinese titles are not represented as reviewed translations.

Source links prefer a confirmed dedicated score page and otherwise use a confirmed directory page. Erroneous or obsolete original `INFO` links remain in internal provenance rather than becoming public entry points.

Records offering Guitar Pro or other formats without a PDF retain their source and format metadata. Reference material such as a glossary is labeled separately. Score records, reference records, and verified local PDFs are counted separately; a record without an available PDF receives no local score link.

### Counts and file verification

- A **membership** is one source record in one category.
- A **source record** is deduplicated by its source and source-native ID, without claiming musicological deduplication across websites.
- A **manifest record** is one file entry under a category or source record; several entries may refer to the same content.
- A **unique physical PDF** is identified by internal SHA-256, retaining every source attribution and category path.

Downloads are resumable and use atomic `.part` files. Verification checks the PDF header, expected byte size and upstream checksum when supplied, internal SHA-256, and parseability. HTML, login pages, CAPTCHA, error pages, and partial responses cannot become scores. Where a source supplies no independent checksum, an internal hash establishes local content identity, not a match against a publisher-provided hash. Human-verification barriers remain explicit incomplete states.

### Search and reference translations

The homepage shows categories; a query or specific category opens source records. Search covers original and Chinese titles, original and Chinese musician names, categories, and source information. Normalization handles case, accents, common punctuation, selected traditional/simplified Chinese differences, and opus spacing such as `Op.9` / `op9`. All query terms remain required; numbers match whole tokens.

Search-only aliases live in [`public_site/data/search-aliases.json`](public_site/data/search-aliases.json). Conservative typo recovery runs only when exact and alias matching return nothing, and approximate results are labeled. Suggestions, approximate matches, and displayed memberships respect active filters. Search state can be restored from the URL. All matching runs in the browser; queries are not sent to external search or AI services.

IMSLP's canonical Chinese title review is [`metadata/translations/title_overrides_reviewed_zh.json`](metadata/translations/title_overrides_reviewed_zh.json), keyed by `work_id` and taking precedence over machine-translation caches. Original names remain visible. Chinese names are reference translations; absent or unreviewed names retain their actual status.

## Quick start

### Browse the public catalog

The repository includes the generated public catalog; no score download is required:

```bash
git clone https://github.com/lin-qian123/guitar-atlas.git
cd guitar-atlas
python -m http.server 8000 --directory public_site
```

Open <http://127.0.0.1:8000>. An existing local directory named `imslp` can continue to be used in place; its name does not define source identity.

### Install and validate

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
node --test tests/search.test.cjs  # Node.js 22+, no npm dependencies
python scripts/validate_public_site.py public_site
```

### Discover and validate ClassClef

Settings live in [`config/classclef.json`](config/classclef.json). Each stage can resume after an interruption:

```bash
python scripts/build_classclef_library.py --root . discover
python scripts/build_classclef_library.py --root . download
python scripts/build_classclef_library.py --root . verify
# Or run all stages in sequence
python scripts/build_classclef_library.py --root . all
```

Snapshots, the normalized catalog, download state, and verification reports live in `sources/classclef/`, with PDF objects under its `objects/` directory. This directory is Git-ignored; the public export selects only permitted fields from the normalized metadata. Verification determines local file availability; discovery counts are not successful-download counts.

### Share identical PDFs across sources

After ClassClef downloads have stopped and before final verification, preview the changes before applying them:

```bash
python scripts/deduplicate_source_pdfs.py --root .          # Dry run by default
python scripts/deduplicate_source_pdfs.py --root . --apply  # Apply physical deduplication
python scripts/build_classclef_library.py --root . verify
```

A ClassClef object is atomically replaced with a hard link only when fresh SHA-256, IMSLP source SHA-1, size, and PDF parsing checks establish that it exactly matches an IMSLP file within approved scope. Both paths, their metadata, and the original bytes remain intact while sharing physical storage. Metadata-only candidates do not establish completed deduplication. The `all` ingestion command does not perform this separate step; verify again after applying it.


### Re-export the public catalog

Run this in a complete library containing the source catalogs. It reads metadata only and does not copy score files:

```bash
python scripts/export_public_site.py \
  --root . \
  --output public_site/data/catalog.json
```

Export and validation reject identity conflicts, missing or malformed catalogs, page links outside approved sources, and fields exposing local or download information. Run the Python suite, search tests, and public-site validation before publishing `public_site/`.

### Rebuild the local offline home page

```bash
python scripts/render_master_index.py .
```

The command checks local PDF headers, sizes, source SHA-1 when available, and parseability, then writes the root `index.html`. The previous entry is preserved in `backups/offline-ui/`.

Poppler is optional (`brew install poppler` on macOS). If pypdf cannot read a legacy PDF, the generator can use `pdfinfo` as a second parser; source files are never rewritten or repaired.

The offline home reuses the public HTML template, styles, and search engine, including category-first browsing. Catalog data and search aliases are embedded, so the root `index.html` opens directly without a server; retain the repository's relative directory structure. Work cards show local scores and parts for the active category, unavailable-file notices, and source links. Existing detailed category pages remain accessible through the full-category link unless affected by the exclusion review.

**GitHub stores the code, not the offline collection instance.** Public pages, shared assets, and offline rendering/adapter code are versioned. The generated root `index.html`, category directories, local-path data, backups, and PDFs are Git-ignored. GitHub Pages deploys only `public_site/`. Copied offline URLs point to the current computer; use the public website to share links with others.

## Adding a source

The registry is [`config/sources.json`](config/sources.json); the shared contract and public-field projection are in [`scripts/catalog_sources.py`](scripts/catalog_sources.py). Source adapters handle discovery, parsing, downloading, and verification; normalized catalogs join through the `normalized_catalog` adapter type. A new source must define stable source and record IDs, approved scope, original attribution fields, source page URLs, and resumable snapshots with failure states. Map source-specific categories, editions, and original/arrangement information explicitly, keeping missing information unknown. Do not inherit IMSLP-specific rules, translation review status, or identity assumptions for a different website.

Every source must pass the same public-field allowlist, source URL checks, local file verification, and search tests. Identical PDF content can share a physical object by SHA-256 while source records and attributions remain separate. Adding a website does not require renaming the project; `scripts/imslp_library/` remains the IMSLP adapter's module name.

## Repository map

```text
guitar-atlas/
├── config/                         # Source scope, IMSLP categories, score exclusions
├── sources/classclef/              # Private snapshots, state, and PDFs (ignored)
├── metadata/translations/          # Reviewed IMSLP titles and musician names
├── public_site/                    # Deployable source catalog without scores
│   ├── assets/                    # Shared styles, interaction, and search
│   ├── data/catalog.json           # Memberships grouped by source identity
│   ├── data/search-aliases.json    # Search-only aliases
│   └── index.html
├── scripts/
│   ├── catalog_sources.py          # Source registry and public data contract
│   ├── build_classclef_library.py   # ClassClef discovery, download, verification
│   ├── deduplicate_source_pdfs.py   # Verified cross-source physical deduplication
│   ├── export_public_site.py       # Source metadata → public catalog
│   ├── validate_public_site.py     # Data and privacy checks
│   ├── render_master_index.py      # Local offline home page
│   ├── render_offline_site.py      # Public template and offline data adapter
│   ├── assets/                    # Offline-only adapter code
│   └── imslp_library/              # IMSLP source adapter
├── tests/
├── AGENTS.md
├── TODO.md
├── DATA_LICENSE.md
└── THIRD_PARTY_NOTICES.md
```

## Data and copyright boundaries

Guitar Atlas is an independent catalog project, unaffiliated with IMSLP or ClassClef. The public site links source pages only. Third-party scores, recordings, page content, and metadata may have their own terms. Inclusion, free download availability, or local possession does not establish public-domain status or permission to redistribute. Each file retains the copyright and licensing information from its source and its own contents.

- Software: [MIT](LICENSE)
- Project-authored catalog structure, reference translations, documentation, and visual assets: [CC BY-SA 4.0](DATA_LICENSE.md)
- Source and attribution notes: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

The project's open licenses do not cover third-party scores or grant additional rights to use or redistribute them.
