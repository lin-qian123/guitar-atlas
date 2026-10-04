<p align="center">
  <img src="public_site/assets/archive-cover.webp" alt="六弦漫行｜Guitar Atlas — A multi-source guitar score catalog" width="100%">
</p>

<p align="center">
  <a href="https://lin-qian123.github.io/guitar-atlas/"><strong>Live catalog</strong></a>
  · <a href="README.md">中文</a>
  · <a href="#quick-start">Quick start</a>
  · <a href="#cataloging-and-search">Method</a>
</p>

<p align="center">
  <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-17283b?style=flat-square">
  <img alt="16 catalog sources" src="https://img.shields.io/badge/sources-16-bd452f?style=flat-square">
  <img alt="Public site excludes score files" src="https://img.shields.io/badge/public_site-score_files_excluded-a67542?style=flat-square">
  <img alt="License MIT and CC BY-SA 4.0" src="https://img.shields.io/badge/license-MIT_%2B_CC_BY--SA_4.0-17283b?style=flat-square">
</p>

**Guitar Atlas**, named **六弦漫行** in Chinese, is a guitar score catalog and local offline library with 16 registered websites and collections. A shared instrumentation and purpose directory searches native titles, Chinese reference names, musicians, formats and edition metadata across sources. Each source keeps its own adapter and resumable snapshot.

Records retain their source identity, editions, and category memberships. Similar titles across websites are not automatically merged. Original titles and musician attributions remain intact; reviewed Chinese reference names assist discovery. The Chinese name is **六弦漫行**, and the original English name remains **Guitar Atlas**. The upper-left navigation displays the English name, the main heading displays the Chinese name, and the bilingual title is “六弦漫行｜Guitar Atlas”. The repository, local root directory and Python package remain `guitar-atlas`, and the Codex project remains named Guitar Atlas. The [October 3 name-change receipt](docs/research/2026-10-03-chinese-name.md) records the name change and the final display conventions.

## 2026-10-04 update

This version includes the completed 16-source catalog, Chinese title review, relevance and repertoire ranking, compact search data, bilingual naming and generated illustrations. A fresh production export preserves the decoded data; 1,256 Python and 66 Node tests plus public-boundary, translation and text audits passed. Source notices cover all 16 registered sources. Pages publishes only the score-file-free `public_site/`; repository and live deployment are verified separately in the [publication receipt](docs/research/2026-10-04-publication.md).

## Generated category illustrations: 2026-10-04

Twelve instrument and score-page vignettes were created with the built-in image model and encoded into one 58KB transparent WebP atlas shared by all 17 topics. It replaces the CSS-drawn strings and sound holes; both README covers now reuse the existing generated hero. No JavaScript, DOM elements or dependencies were added, and catalog data and 18-record pagination are unchanged. Referenced static assets total 283,302 bytes; 46 focused Python tests, 66 Node tests and public validation passed. The offline entry was refreshed. See the [artwork, prompt and validation receipt](docs/research/2026-10-04-generated-category-art.md). This is a local update; the following layout receipt retains its earlier resource budget.

## Rounded collection layout: 2026-10-04

Following the latest feedback, the page restores the guitar-and-score artwork, reduces the oversized heading and whitespace, and uses forest green/ivory, a curved image frame, rounded topic and record cards, soft shadows and clearer controls. Mobile keeps image and text side by side; secondary and placeholder text contrast is corrected.

No frameworks, fonts or animation libraries are added. The active hero is about 64KB; referenced static assets total 224,765 bytes, about 4KB below the preceding design, with unchanged catalog transport. All 46 focused Python and 66 Node tests pass, followed by 31 targeted regressions. Public/offline data, titles, ranking and score links agree. The [refinement receipt](docs/research/2026-10-04-visual-refinement.md) records the current presentation and verification; the next same-day section describes the preceding design. This local update is not deployed.

## Visual redesign: 2026-10-04

The public and offline entry pages now use a score-publication and collection-index layout: an original classical-guitar illustration, a six-string rosette mark, system Chinese serif and self-hosted Latin display fonts, numbered topics, a desktop browse sidebar and single-column mobile records. Search, filters, edition details, focus, restrained corners and micro-transitions share one design; reduced-motion preferences are respected, without new frameworks or remote font dependencies.

Referenced static assets fall from 358,126 to 228,773 bytes (−36.12%, excluding catalog JSON). Compact data, translations, ranking, source identities and offline score relationships are unchanged. All 1,256 Python and 66 Node tests pass, followed by focused regressions. Browser checks cover desktop, 390/320px mobile, long titles, empty results, source/history navigation and offline part expansion. The [design receipt](docs/research/2026-10-04-visual-redesign.md) records ten official reference sites, design details, image prompt, font license, asset accounting and verification limits. This is a local update, not a deployment.

## Complete title review: 2026-10-03 to 10-04

All **48,449 frozen source records** have new title decisions, including drafts, previous reference translations and retained originals. **47,347 use complete Chinese reference translations or supported conventional names; 1,102 intentionally retain their original names. No machine title drafts or missing title decisions remain.** Unresolved proper names, brands, wordplay and damaged transcriptions stay in the source language rather than receiving awkward phonetic substitutes.

Every decision guards the source ID, exact title and full attribution. Primary-title changes also guard the English display boundary and preceding Chinese text. Responsibility statements and review notes stay in edition details; musical numbers, keys, collection extents and parts remain intact. Research supports conventional names, opera references and historical vocabulary; complete semantic readings supply the other reference translations. Reference translations are not claims of unique authoritative Chinese names.

The [complete-title review receipt](docs/research/2026-10-03-complete-title-review.md) records methods, source counts, retained originals, evidence and verification. Review ledgers live under `metadata/translations/review_2026-10-03/`; four persistent title assets supply production display. The full review ledger is excluded from browser transport. Later sections retain their historical acceptance counts.

Public/offline fields, lossless compact decoding and all previous score links match. Refreshing 352 legacy category directories changed 1,247 unique view files across two backed-up rounds; the final dry run reports no changes. All 1,256 Python and 66 Node tests pass, translation decisions have no pending fields, and 299,758 text fields have no detected rule defects. Compact transport is 5.63MB, down 0.19%; the offline entry is 7.43MB, up 0.13%. This local title/display refresh retains preceding PDF checks and has not been pushed or deployed.

## Chinese text and bibliographic fields: 2026-10-02

This review scans all 48,449 records and 2,228 categories across 16 sources. It corrects dictionary mistranslations of opus, numbering, keys, musical forms and names, reconciles Chinese forms for identical original attributions, and repairs Chinese title punctuation. The reported Asturias example now preserves Suite No.1, Op.47 and movement No.5. Exact-original guards, changes, counts and validation appear in the [text-quality receipt](docs/research/2026-10-02-chinese-text-quality.md).

The run updates 11,509 title asset rows, 591 attribution rows and 154 category rows, and separates headline fields for 8,518 records. Rule checks cover 306,714 text values with no detected errors; 1,206 Python and 66 Node tests pass. Shared public/offline data and every retained local edition match. Offline HTML is 7.42 MB and normal compact catalog transfer 5.64 MB; canonical audit JSON remains separate. Asset updates include evidence, state and intentional retention, rather than an equal count of authoritative Chinese names.

Original titles and attributions remain intact. Separate display fields move explicit arrangement/editor credits, manuscript/holding annotations, publication transcriptions and life dates into edition details. Editorially supplied titles and musical content in brackets are preserved. Performers, editors and unspecified source roles have distinct labels; existing language, key, institution, shelfmark and catalogue-number fields are visible. Display cleanup does not merge records or change source identity.

**The 19,723 machine title drafts recorded at that snapshot have been resolved by the October 3–4 complete title review above.** Originals and complete edition text remain searchable. Checked reference translations and evidenced conventional names can supply Chinese headlines. Partial terminology fixes alone do not establish review. The publication translation gate remains strict. Public and offline editions share these rules and compact transport. This metadata refresh checks fingerprints, memberships, retained links and sizes while preserving previous PDF verification; it does not repeat PDF hashing or parsing.

## Source expansion: 2026-10-01

Fourteen additional catalogs are integrated, bringing the registry to 16 sources: Mutopia, The Guitar School, CGLIB, Delcamp, Boije, RISM, Digital Guitar Archive, Werner, GuitarDownunder, Andrew York, ClassicalGuitar.org, FreeGuitarMusic, Cantorion, and the Library of Congress. The shared directory browses instrumentation and purpose across sources; search includes Chinese reference names, native titles, musicians, edition roles, opus, formats and collection contents. Original source categories remain reachable.

The frozen catalog contains **48,449 source records (48,364 scores and 85 references), 2,228 native categories, 57,062 category memberships, 17 shared topics and 700 evidenced relationships**. Records include editions, collections and holdings; they are not a count of unique compositions across websites.

This run added **3,964 valid PDF manifest/member relationships**. Full offline hashing and parsing checked **35,385 valid relationships and 33,820 distinct PDF contents**, retaining 1,890 unavailable or excluded manifest entries. All 35,083 distinct local PDF paths and 350 legacy category-page links resolve; shared public/offline fields and search aliases agree. The 1,010 Python tests, 50 Node search tests and public validation pass. Chrome checks cover Chinese search, membership filters, all eight score/part links of a sample, and actual local PDF rendering.

The [integration receipt](docs/research/2026-10-01-integration-log.md) records frozen scopes, accepted/excluded records, metadata gaps, typed relationships, file manifests, content hashes, physical objects, translation states and validation. The [34-source policy ledger](config/source_acquisition_policies.json) distinguishes access restrictions, permission requirements and unresolved acquisition scopes. Historical September statistics below describe the preceding two-source snapshot.

Source IDs and editions remain independent. Explicit upstream file references, verified PDF content, institution/shelfmark mappings and collection structure establish different relationship types. Titles and fuzzy musician names do not establish work identity. Delcamp uses a deterministic upstream-locator digest because it has no standalone record ID; the exact PDF locator stays private.

Reviewed terminology/reference correspondences and machine translation drafts carry separate field evidence. At this integration snapshot drafts required semantic review and failed the unchanged publication audit; the October 3–4 title review resolves them. This local integration has not been pushed or deployed to Pages. Personal-use PDFs are acquired only where explicitly permitted. Metadata rights do not establish score-file reuse rights.

At the integration snapshot, Chinese coverage and evidence were counted by source and field: **24,994 machine translation fields awaited semantic review, while 10,345 fields intentionally retained original text**. The October 2 receipt records revised states. Missing attributions, unknown instrumentation and differences between directory and printed score credits remain explicit. File integrity or non-empty Chinese text does not establish instrumentation or authoritative naming.

Discovery entry points are `scripts/discover_open_sources.py`, `discover_archive_sources.py`, and `discover_additional_sources.py`. Run `python scripts/acquire_source_assets.py --source mutopia --source guitarschool --source delcamp --retry-failed` to resume eligible files, then regenerate translations, public and offline catalogs and the receipt. Each source keeps private snapshots, logs, exclusions and resumable states under `sources/<source>/`; the new immutable shared PDF pool is `sources/objects/sha256/`. Translation assets, shared search and public projection use `metadata/translations/` and `public_site/`. Private run checks remain in `work/source-expansion/2026-10-01/`.

## Search ranking and compact loading: 2026-10-01

Queries rank full names, checked aliases and name-boundary matches ahead of embedded substrings or incidental title mentions. Searching 索尔 therefore prioritizes Fernando Sor over names containing 埃索尔. Every term and same-membership filter remains required; familiarity weights only break equal relevance. Queryless category views use descending familiarity, then stable original composer/title/ID ordering.

The guarded source asset [`recognition.json`](metadata/ranking/recognition.json) covers 47 musicians through 151 exact source full-name keys and 40 specific score/collection records, backed by ten official syllabus, performance or label references. Composer weights are 8–20, record weights 40–70, and uncurated entries 0. These are maintained repertoire familiarity judgments, not measured traffic, and never work identity evidence. The [reference notes](docs/research/2026-10-01-ranking-evidence.md) document sources and limits.

Browsers load an approximately 5 MB lossless transport instead of the approximately 58 MB canonical JSON, which remains available for audit and compatibility fallback. Offline pages embed the same dictionary/gzip transport together with aliases, weights and every local part. Native browser decompression needs no framework, CDN or search service. Full-text fields and fuzzy vocabulary are built on demand; initial category browsing avoids processing every document. The first whole-catalog text query still pays its indexing cost.

Final offline HTML shrank **68.3→6.83 MB**, and normal public catalog transfer **57.9→5.05 MB**. Local Node index construction measured approximately **5.07→0.097 seconds**. Single local Chrome default-category startup observations were 0.53 seconds public and 0.80 seconds offline; first whole-catalog text indexing was around 1.1 seconds in Node, while the browser ISBN query startup was around 2.9 seconds. Cache, device load and network conditions affect timings; these are not deployment performance promises.

This display refresh preserves earlier PDF integrity results and checks current fingerprints, memberships, availability, paths and sizes. Measurements and validation are recorded in the [ranking and performance log](docs/research/2026-10-01-search-ranking-speed.md).

## Two editions

| Edition | Purpose | Score access |
| --- | --- | --- |
| **Public site** in `public_site/` | GitHub Pages search and source navigation | Links to source work or directory pages |
| **Local offline library** at the generated root page | Browsing a computer or drive holding the collection | Links verified local PDFs and preserves source pages |

Both editions share the HTML template, styles, and search logic. The public site contains no PDF, MIDI, GPX, download URLs, local paths, file hashes, or private runtime metadata. Git tracks code, configuration, review assets, and the public catalog without score files.

## Original sources and historical scope

| Source | Organization | Verification boundary |
| --- | --- | --- |
| **IMSLP** | Approved exact instrumentation categories for classical/acoustic guitar solos, ensembles, and guitar chamber music | Originals and arrangements remain separate; files must match their target sections; original category names are preserved |
| **ClassClef** | Source repertoire and musician directories, kept as separate source categories | Public score records and verifiable PDF downloads; unspecified instrumentation and original/arrangement status stay unknown; Chinese reference names are reviewed separately |

### Chinese catalog repair: 2026-09-29

| Source | Chinese titles (reference or established names) | Intentionally retained titles | Chinese musician names / distinct attributed names | Chinese categories |
| --- | ---: | ---: | ---: | ---: |
| IMSLP | 11,380 | 13 | 2,158 / 2,164 | 352 / 352 |
| ClassClef | 6,664 | 76 | 851 / 858 | 77 / 77 |

All 6,740 ClassClef titles have an explicit review disposition. The 76 retained titles have individual reasons; 2 also contain Chinese arrangement notes, so a nonempty Chinese field is not a complete translation. Seven source attributions retain their original spelling, and 4 records lack an attribution at the source. This repair corrects 92 IMSLP titles and a set of musician-name mistranslations. Other IMSLP titles retain the historical reference review; this is not a claim that every name has an authoritative Chinese form.

Both editions apply durable translations by source and stable ID. Missing review, changed originals or IDs, and stale summaries block publication; acquisition cannot replace checked text with machine drafts. See [`coverage_2026-09-29.json`](metadata/translations/coverage_2026-09-29.json) for field states and retention reasons. The audit has no unresolved machine drafts or untranslated fields; deliberate retention is reported separately.

The 849 Python tests, 34 Node search tests, public privacy validation, and translation audit pass. Browser checks cover Chinese titles and names, category filtering, and retention labels. Public/offline display data matches field for field; 31,143 local PDF paths and all 6 exclusions pass the link audit.

Repair [`f1474e0`](https://github.com/lin-qian123/guitar-atlas/commit/f1474e04eecedb1d11f62c10a3f2eddfee215492) is deployed with a successful [workflow](https://github.com/lin-qian123/guitar-atlas/actions/runs/36516382617). All 10 served public files match local SHA-256 digests, and live Chinese search passes browser checks.

This refresh synchronizes the public catalog, offline home, and display text in all 352 legacy category directories. The offline home is checked against current manifests, exclusions, memberships, links, and file sizes while retaining the preceding integrity results. Full PDF hashing and parsing are not repeated. The file-coverage gaps and instrumentation-review boundaries in the 2026-09-28 snapshot below remain open.

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

ClassClef's final full file verification passed: all 8,578 files corresponding to manifest objects were checked, `structural_valid=true`, and both errors and quarantine records are empty. The 231 confirmed HTTP 404 responses leave `complete=false` and verification exit code 2, indicating incomplete source coverage. MIDI/GPX files are indexed as metadata only.

The full offline catalog has been regenerated and verified:

| Source | PDF manifest records | Valid records | Distinct SHA-256 contents |
| --- | ---: | ---: | ---: |
| IMSLP | 22,637 | 22,566 | 21,496 |
| ClassClef | 9,088 | 8,855 | 8,578 |
| **Library total** | **31,725** | **31,421** | **29,904** |

The library retains **304 unavailable records, including 6 explicit exclusions**. IMSLP contributes 65 previously unavailable records and 6 instrumentation exclusions. Final link validation passed: 31,143 distinct local paths resolve to 30,974 linked inodes, with no broken or ineligible excluded links. The 29,904 figure counts distinct content, not physical file entities; older IMSLP duplicates have not been physically deduplicated across the whole library. Fresh cross-source checks replaced 169 duplicate copies with shared hard links, saving **60,879,123 bytes**. Two other candidates retained their ClassClef originals because the IMSLP source files failed verification.

The 741 Python tests, 32 Node search tests, and public privacy validation passed. A rebuild from final source metadata matched the exported public catalog field for field. Browser checks covered five-part expansion, absent-PDF/404 notices, instrumentation exclusions, and reference material, with zero JavaScript errors. Sample PDF HTTP responses and actual rendering passed inspection. Codex's in-app PDF preview remained blank and is not reported as a passed viewer check.

Catalog snapshot [`502db86`](https://github.com/lin-qian123/guitar-atlas/commit/502db8610994a32716ea5bda59eabe965b2c2fb3) is published in the [GitHub repository](https://github.com/lin-qian123/guitar-atlas) and [live catalog](https://lin-qian123.github.io/guitar-atlas/). The [test and deployment workflow](https://github.com/lin-qian123/guitar-atlas/actions/runs/36409900823) succeeded, and deployed file digests matched local files. IMSLP's 11,393 reviewed Chinese work titles remain intact. Outstanding coverage and follow-up work are recorded in [TODO.md](TODO.md).

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
- **Distinct PDF content** is deduplicated by internal SHA-256; path and linked-inode counts are measured separately, preserving every source attribution and category path.

Downloads are resumable and use atomic `.part` files. Verification checks the PDF header, expected byte size and upstream checksum when supplied, internal SHA-256, and parseability. HTML, login pages, CAPTCHA, error pages, and partial responses cannot become scores. Where a source supplies no independent checksum, an internal hash establishes local content identity, not a match against a publisher-provided hash. Human-verification barriers remain explicit incomplete states.

### Search and reference translations

The homepage shows categories; a query or specific category opens source records. Search covers original and Chinese titles, original and Chinese musician names, categories, and source information. Normalization handles case, accents, common punctuation, selected traditional/simplified Chinese differences, and opus spacing such as `Op.9` / `op9`. All query terms remain required; numbers match whole tokens.

Search-only aliases live in [`public_site/data/search-aliases.json`](public_site/data/search-aliases.json). Conservative typo recovery runs only when exact and alias matching return nothing, and approximate results are labeled. Suggestions, approximate matches, and displayed memberships respect active filters. Search state can be restored from the URL. All matching runs in the browser; queries are not sent to external search or AI services.

IMSLP's canonical Chinese title review is [`metadata/translations/title_overrides_reviewed_zh.json`](metadata/translations/title_overrides_reviewed_zh.json), keyed by `work_id` and taking precedence over machine-translation caches. Original names remain visible. Chinese names are reference translations; absent or unreviewed names retain their actual status.

ClassClef titles live in [`classclef_titles_zh.json`](metadata/translations/classclef_titles_zh.json), keyed by full source ID. [`musicians_zh.json`](metadata/translations/musicians_zh.json) and [`categories_zh.json`](metadata/translations/categories_zh.json) keep attribution and category translations separate for each source. Acquisition cannot erase these assets; changed original text or stale IDs stop export for review.

Each title, attribution, and category has its own status, basis, and reason. `reviewed` identifies a supported conventional name; `reference` is a checked reference rendering; `retained` records a specific reason to preserve the original. Unchecked drafts are `machine`, absent translations are `untranslated`, and `not_applicable` is reserved for missing source attribution. A populated Chinese field is not a certificate of authoritative naming, instrumentation, or file integrity. Numbered titles, stylized brands, and names whose original Chinese characters are uncertain may deliberately remain unchanged.

`python scripts/audit_translations.py` counts Chinese text, reference and conventional names, retained originals, and missing attribution separately. Unreviewed drafts or missing translations block publication. `python scripts/build_classclef_translations.py draft` resumes draft acquisition, `shards` prepares review batches, and `assemble` incorporates corrections while preserving earlier reviews. Draft caches and temporary batches stay in Git-ignored `work/`; final translation assets are versioned.

## Quick start

### Browse the public catalog

The repository includes the generated public catalog; no score download is required:

```bash
git clone https://github.com/lin-qian123/guitar-atlas.git
cd guitar-atlas
python -m http.server 8000 --directory public_site
```

Open <http://127.0.0.1:8000>. The local project directory is `/Volumes/PHILIPS/programs/muse-cache/guitar-atlas`; its offline entry point is `index.html`.

### Install and validate

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
node --test tests/search.test.cjs  # Node.js 22+, no npm dependencies
python scripts/validate_public_site.py public_site
python scripts/audit_translations.py
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

Export and validation reject identity conflicts, missing or malformed catalogs, page links outside approved sources, and fields exposing local or download information. Run the Python suite, search tests, public-site validation, and translation audit before publishing `public_site/`.

### Rebuild the local offline home page

```bash
python scripts/render_master_index.py .
```

The command checks local PDF headers, sizes, source SHA-1 when available, and parseability, then writes the root `index.html`. The previous entry is preserved in `backups/offline-ui/`.

For translation or display-only edits, use `python scripts/render_master_index.py . --metadata-only`. This compares source identities, manifests, scope, and exclusions, then checks every retained link and file size before refreshing the page. Changed manifests or file states require a full rebuild. It preserves the previous PDF integrity results; it does not repeat checksum or parsing verification.

Poppler is optional (`brew install poppler` on macOS). If pypdf cannot read a legacy PDF, the generator can use `pdfinfo` as a second parser; source files are never rewritten or repaired.

The offline home reuses the public HTML template, styles, and search engine, including category-first browsing. Catalog data and search aliases are embedded, so the root `index.html` opens directly without a server; retain the repository's relative directory structure. Work cards show local scores and parts for the active category, unavailable-file notices, and source links. Existing detailed category pages remain accessible through the full-category link unless affected by the exclusion review.

**GitHub stores the code, not the offline collection instance.** Public pages, shared assets, and offline rendering/adapter code are versioned. The generated root `index.html`, category directories, local-path data, backups, and PDFs are Git-ignored. GitHub Pages deploys only `public_site/`. Copied offline URLs point to the current computer; use the public website to share links with others.

## Adding a source

The [2026-10-01 source expansion study](docs/research/2026-10-01-source-expansion.md) (Chinese) evaluates 34 candidates. It prioritizes explicitly licensed subsets from Mutopia, Boije, and The Guitar School, with DGA/RISM for archive discovery and authority relationships. Commercial, community, and Chinese fingerstyle sources require separate scope and acquisition reviews. These are research candidates; IMSLP and ClassClef remain the registered sources.

The registry is [`config/sources.json`](config/sources.json); the shared contract and public-field projection are in [`scripts/catalog_sources.py`](scripts/catalog_sources.py). Source adapters handle discovery, parsing, downloading, and verification; normalized catalogs join through the `normalized_catalog` adapter type. A new source must define stable source and record IDs, approved scope, original attribution fields, source page URLs, and resumable snapshots with failure states. Map source-specific categories, editions, and original/arrangement information explicitly, keeping missing information unknown. Do not inherit IMSLP-specific rules, translation review status, or identity assumptions for a different website.

Every source must pass the same public-field allowlist, source URL checks, local file verification, and search tests. Identical PDF content can share a physical object by SHA-256 while source records and attributions remain separate. Adding a website does not require renaming the project; `scripts/imslp_library/` remains the IMSLP adapter's module name.

## Repository map

```text
guitar-atlas/
├── config/                         # Source scope, IMSLP categories, score exclusions
├── sources/classclef/              # Private snapshots, state, and PDFs (ignored)
├── metadata/translations/          # Source-scoped title, musician and category translations with review evidence
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
│   ├── audit_translations.py       # Translation coverage and field review gate
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
