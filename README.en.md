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
  <img alt="17 catalog sources" src="https://img.shields.io/badge/sources-17-bd452f?style=flat-square">
  <img alt="Public site excludes score files" src="https://img.shields.io/badge/public_site-score_files_excluded-a67542?style=flat-square">
  <img alt="License MIT and CC BY-SA 4.0" src="https://img.shields.io/badge/license-MIT_%2B_CC_BY--SA_4.0-17283b?style=flat-square">
</p>


**Guitar Atlas / 六弦漫行** is a source-attributed guitar score catalog and private offline library. A shared directory groups instrumentation and purpose across sources; search covers Chinese reference names, originals, musicians, sources, opus, formats and edition information. The English navigation brand remains Guitar Atlas.

## Current scope

The frozen catalog contains **17 sources and 49,373 source records** (49,288 scores and 85 references), 2,229 native categories, 57,986 memberships, 17 shared topics and 700 evidenced relationships. Records include works, editions, collections and holdings; they are not unique compositions across websites. Discovery gaps such as Cantorion pagination remain explicit.

Exact title decisions cover every record: 47,469 reference or evidenced conventional Chinese titles, 1,904 intentional original-title retentions, and no machine title drafts or missing title decisions. Native titles and attributions remain intact. Reference translations are not claims of unique authoritative Chinese names.

The current rounded collection interface uses self-hosted Latin display fonts, system Chinese fonts and model-generated illustrations. Lists start with 18 records and build full-text/fuzzy indexes on demand. Referenced static assets total 283,302B; compact transport is 5,767,964B, with canonical JSON retained for audit and compatibility fallback.

The published October 13 PDF version was pushed and deployed, adding 924 PDMX exported PDFs to the existing offline entry. The current MXL/MIDI extension has completed file acquisition, full offline rebuilding and independent mapping verification: all 38,202 local links are valid, with existing source records, PDF mappings and translation decisions preserved. Remote synchronization and deployment checks are in progress. See the [publication and maintenance record](docs/research/publication.md) for evidence and deployment status, and [TODO](TODO.md) for open work.

The 924 historical MuseScore records from the author-published PDMX v9 subset share existing search and topics. Corresponding PDF, MXL (compressed MusicXML) and MIDI files are now acquired. The following counts describe verified local files; the public catalog retains format metadata and source navigation only:

| Format | Verified record associations | Failed / missing / pending | Unique content objects | Unique content bytes |
| --- | ---: | --- | ---: | ---: |
| PDF | 924 | 0 / 0 / 0 | 924 | 63,081,172B |
| MXL | 924 | 0 / 0 / 0 | 924 | 10,772,167B |
| MIDI | 924 | 0 / 0 / 0 | 921 | 7,072,991B |

This extension adds 1,848 format-file associations and 1,845 unique content objects totaling 17,845,158B. Three duplicate MIDI contents reuse SHA-256 objects while preserving every record association. Existing PDFs, native metadata and translation decisions are unchanged. LibreScore is a retrieval tool; this frozen historical subset does not cover the live site and provides no native MSCZ. See the [source supplement](docs/research/2026-10-01-integration-log.md#musescore--pdmx-补记2026-10-11) for scope, exclusions, translation decisions and file acquisition.

## Two editions

| Edition | Purpose | Score links |
| --- | --- | --- |
| `public_site/` | Online search and source navigation; the only Pages deployment input | Validated source pages |
| Root `index.html` | Private offline library with embedded catalog, aliases and ranking | Verified local scores/parts, MXL and MIDI for active category memberships, plus source pages |

The public export contains no score files such as PDF, MXL/MusicXML, MIDI, MSCZ or GPX, and no download endpoints, local paths, hashes or private inventory. Format metadata and human source pages remain searchable. Cloning this repository provides the public catalog, not the private library. Preserve relative paths when using the offline edition.

## Cataloging and search

- Records use `source_id + source_record_id`. Similar titles or musician names do not merge identities. Native category memberships and shared topics remain separate.
- Relationships require explicit file references, verified PDF content, institution/shelfmark evidence or typed collection membership. Every source attribution is retained.
- Search relevance precedes curated familiarity weights. Full names, explicit aliases and name boundaries outrank substring mentions; no-query browsing uses familiarity with stable ties. Weights are not measured traffic.
- Title, attribution and category evidence have independent review states. Keep originals when an unsupported phonetic translation would be misleading. Responsibility statements, archival locations and review notes belong in edition details.
- Manifest relationships, file paths, content hashes within each format and inodes are separate counts. Shared MIDI/MXL bytes do not establish an identical-PDF relationship. Metadata-only refreshes do not establish fresh file integrity or instrumentation review.

## Evidence and documentation

| Record | Content |
| --- | --- |
| [Source research](docs/research/2026-10-01-source-expansion.md) and [candidate ledger](docs/research/2026-10-01-source-candidates.json) | Candidate value, interfaces, terms and authorization boundaries |
| [Frozen integration](docs/research/2026-10-01-integration-log.md) | Accepted scopes, failures, acquisition/deduplication and verification |
| [Title review](docs/research/title-review.md) | Final decisions, older exact corrections, naming, references and guards |
| [Ranking references](docs/research/2026-10-01-ranking-evidence.md) and [performance](docs/research/2026-10-01-search-ranking-speed.md) | Familiarity weights, relevance and dated measurements |
| [Presentation](docs/research/presentation.md) | Current design, inspiration, image provenance/prompts and font license |
| [Publication](docs/research/publication.md) | Valid release commits, workflows, live byte parity and cleanup results |

## Quick start

Visit the [online catalog](https://lin-qian123.github.io/guitar-atlas/) or preview it locally:

```bash
python -m http.server 8000 --directory public_site
```

Open `http://127.0.0.1:8000/`. Browse shared topics or enter a query.

Install and validate with Python 3.12+ and Node.js 22+:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
node --test tests/*.test.cjs
python scripts/validate_public_site.py public_site
python scripts/audit_translations.py
python scripts/audit_catalog_text.py
```

Production discovery is resumable and restricted to approved configurations:

```bash
python scripts/discover_open_sources.py --help
python scripts/discover_archive_sources.py --help
python scripts/discover_additional_sources.py --help
python scripts/build_classclef_library.py --root . discover
python scripts/build_classclef_library.py --root . download
python scripts/build_classclef_library.py --root . verify
```

MuseScore uses the licensed PDMX v9 publication rather than live-site scraping.
The following commands perform initial metadata import and source-scoped title
review. A PDF, MXL or MIDI acquisition journal or verified file protects the existing
snapshot from metadata rebuilds; resume files through the dedicated route below:

```bash
python scripts/build_musescore_library.py --root . --acquire-metadata
python scripts/build_musescore_library.py --root .
python scripts/review_musescore_translations.py --root . --apply
```

The existing 924 records have exact publication PDF locators. The dedicated
pipeline downloads the frozen archive atomically, resumes supported byte ranges,
checks its exact size and MD5, then safely streams only the selected members.
Every PDF is independently parsed and stored as an immutable SHA-256 object with
source-local hard links. It never requests a MuseScore download service.

```bash
python scripts/acquire_musescore_pdfs.py --root . --acquire-archive
python scripts/acquire_musescore_pdfs.py --root . --parallel-archive
python scripts/acquire_musescore_pdfs.py --root . --cached-archive
```

If the first range is complete while the following range is slow, stop every
download writer before using `--consolidate-prefix`, then resume with
`--parallel-archive`. This local step verifies and retains all contiguous bytes
before replanning the remainder. It does not certify the complete archive and
rejects gaps or source-access refusals.

Per-record success, failure, missing and pending states are private in
`sources/musescore/acquisition_report.json`; interrupted extraction resumes through
`sources/musescore/pdmx/pdf-extraction.json`. These are PDMX exported PDFs, not
original MSCZ files. An archive MD5 is not a publisher-provided per-file checksum.

The same 924 native records have a separate MXL/MIDI pipeline. Its exact archive
members are bound to the authoritative CSV and associated with existing PDFs.
Run formats sequentially; a source refusal stops acquisition without changing routes:

```bash
python scripts/acquire_musescore_formats.py --root . --format MIDI --parallel-archive
python scripts/acquire_musescore_formats.py --root . --format MUSICXML --parallel-archive
python scripts/acquire_musescore_formats.py --root . --format MIDI --cached-archive
python scripts/acquire_musescore_formats.py --root . --format MUSICXML --cached-archive
```

If a lower range is interrupted while the upper range is complete, stop every
download writer before using `--rebalance-ranges` for that format. This purely
local transaction verifies and retains the contiguous prefix and complete tail,
divides only the gap into 64 MiB jobs, then resumes through `--parallel-archive`
on the same endpoint with at most two streams. Source refusals cannot be
replanned or retried; replanning does not establish complete-archive integrity.

Format outcomes are in `sources/musescore/formats-acquisition-report.json`, with
per-record journals in `pdmx/mid-extraction.json` and `pdmx/mxl-extraction.json`.
Whole archives require exact size, upstream MD5 and internal SHA-256 checks plus
a safe complete TAR scan. Each selected MXL requires ZIP/CRC/container/MusicXML
checks; MIDI requires valid tracks, events and end markers. Immutable SHA-256
objects deduplicate content within each format. These checks do not establish
note-level equivalence, faithful MuseScore import or acoustic playback, and no
native MSCZ is produced. Only verified files receive offline links; the public
edition retains metadata and human source pages.

After downloads stop, run each applicable deduplicator as a dry run. Only freshly verified candidates permit `--apply`, followed by verification; original bytes, paths and source manifests remain intact.

```bash
python scripts/deduplicate_source_pdfs.py --root .
python scripts/deduplicate_added_pdfs.py --root .
```

A production export requires the private frozen source metadata and copies no score files:

```bash
python scripts/export_public_site.py --root . --output public_site/data/catalog.json
python scripts/render_master_index.py .
```

Full offline rendering checks file content and manifest relationships: PDFs are hashed and parsed again, MXL files are hashed and checked for ZIP/CRC/container/MusicXML structure, and MIDI files are hashed and checked for tracks, events and end markers. For display changes to an unchanged source/file snapshot, `python scripts/render_master_index.py . --metadata-only` checks fingerprints, memberships, links and sizes while retaining prior file-validation results. It does not repeat hashing, parsing or format-structure validation.

## Repository and retention

```text
config/                       Approved sources, scopes, policies and exclusions
scripts/                      Production entry points and source adapters
tests/                        Python and Node regressions
metadata/translations/        Reviewed titles, exact guards and compilation inputs
metadata/ranking/             Guarded familiarity references
docs/research/                Effective source, title, design and publication records
public_site/                  Deployable catalog and active frontend assets
sources/                      Private frozen data, state, objects and manifests
For */ and for3guitars/        Native category directories, current views and scores
metadata/.cache/pages/        Fixed source revisions used by snapshot guards
work/                         Required review corpora, journals and final evidence
backups/offline-ui/            One recent offline-entry rollback copy
index.html                    Private offline entry
```

`work/title-review/.../before/metadata/translations/` is an application guard input, not a disposable UI backup. Preserve frozen source revisions, current manifests, score objects, review inputs and effective final reports. Remove unreferenced views, trial checkouts, duplicate exports, process screenshots and bytecode. Update existing canonical documents and final reports rather than accumulating round-by-round copies.

Private data, generated offline pages, logs and scores remain Git-ignored. GitHub Pages publishes only `public_site/`.

## Rights

This is an independent catalog and does not represent source websites. Open metadata or free download access does not establish score redistribution rights. Individual source and file terms remain applicable.

- Software: [MIT](LICENSE)
- Original catalog structure, reference translations, documents and visual assets: [CC BY-SA 4.0](DATA_LICENSE.md)
- Source attribution and third-party terms: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
