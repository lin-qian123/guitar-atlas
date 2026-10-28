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
  <img alt="22 catalog sources" src="https://img.shields.io/badge/sources-22-bd452f?style=flat-square">
  <img alt="Public site excludes score files" src="https://img.shields.io/badge/public_site-score_files_excluded-a67542?style=flat-square">
  <img alt="License MIT and CC BY-SA 4.0" src="https://img.shields.io/badge/license-MIT_%2B_CC_BY--SA_4.0-17283b?style=flat-square">
</p>


**Guitar Atlas / 六弦漫行** is a source-attributed guitar score catalog and private offline library. A shared directory groups instrumentation and purpose across sources; search covers Chinese reference names, originals, musicians, sources, opus, formats and edition information. The English navigation brand remains Guitar Atlas.

## Current scope

The unified catalog contains **22 sources and 50,498 records** (50,406 scores and 92 references), with 2,337 native categories, 59,111 category memberships, 18 shared topics and 710 evidenced record relationships. Records may represent editions, collections or holdings rather than unique compositions across websites. Coverage gaps such as Cantorion pagination remain explicit. The repository and [public site](https://lin-qian123.github.io/guitar-atlas/) are synchronized.

In the previously frozen 17-source scope, 47,495 titles used reference or evidenced conventional Chinese names and 2,297 intentionally retained their originals. These historical counts exclude the current source additions, which have separate exact-original guards and translation decisions. Native titles and attributions remain intact; reference translations do not claim unique authoritative names.

The previous frozen-scope review covered all 35,802 previously unspecified formal records and 296 MuseScore candidates, accepting evidenced guitar relatedness, player counts or mixed instrument families. Source declarations, actual-score observations and inconclusive source audits have separate labels. That historical review recorded 15,235 records without sufficient instrumentation evidence and 16,885 guitar-related records with unresolved roles, instrument choices or counts. After the new source additions, the current topic counts are 15,236 and 17,362 respectively; these are current values and do not rewrite the historical review totals. Delcamp screening covers 2,890 available PDFs / 40,662 pages, while the 528 IMSLP file cases include OCR of 301 scans with explicit limits. A proven mismatched Byrd brass PDF loses only its guitar file link; its bytes are preserved. See the [unified review receipt](docs/research/2026-10-01-integration-log.md#全库宽泛编制核验2026-10-17).

Five sources add 706 records: CSUN 424, Yawnoc 5, Maikstrings 112, Derek Hasted 23, and Guitar Classroom 142 (135 scores and 7 references). PDF acquisition has stopped: all 424 CSUN PDFs are verified (421 succeeded on the first pass; the remaining three succeeded on retry at the same approved endpoint), and the other three teaching sources have 286 verified PDFs. Together these are 710 PDF associations with 710 distinct SHA-256 contents / 1,707,045,956 bytes; failed, missing and pending counts are currently zero. Yawnoc’s nine PDFs are marked CC0, but GitHub’s release-download route was denied by robots before a PDF request; no alternate route was used. Its five LilyPond source texts were used for metadata checks only. Source metadata, individual offline acquisition rights and public redistribution rights are tracked separately; the public site still exposes source pages only.

New-source translation review is complete: 96 manually reviewed title references, 103 manually reviewed category translations, and all 108 new native categories reviewed. New-source title, musician and category drafts have been refreshed, with the 17 previously published sources’ decisions preserved. All 1,145 CSUN candidate native IDs received full metadata review: 424 admitted, 8 excluded and 713 pending. Six score-file difference notes have exact guards: the original four, one/two-guitar options with unknown count for CSUN 1071, and choir plus guitar visible on page 10 of CSUN 1024 while other works and counts remain unverified. The candidate study has 47 entries, including 13 newly researched candidates. Added-source PDF deduplication processed all 7,215 objects: 10 groups / 20 paths sharing 44,365,593 bytes. The final dry run reports 32 already shared, 0 would link and 0 failed. ClassClef has 169 shared items; its two historical safety refusals remain unchanged. The public export is complete; full offline rebuild, preservation checks and all audits passed, with no failures across 40,162 local links. Audited intermediates have been cleaned and the repository/site are synchronized; see the [publication receipt](docs/research/publication.md). See the [source study](docs/research/2026-10-01-source-expansion.md), [candidate inventory](docs/research/2026-10-01-source-candidates.json), and private receipts in `sources/source-expansion/` (the canonical `verification.json` for this run, alongside `acquisition-summary.json`, `csun-acquisition-phases.json`, `new-pdf-evidence.json.gz`, `file-note-runtime-check.json`, and `file-note-binding-corrections.json`).

The original 924 MuseScore records were a historical selection. Review of 254,077 PDMX v9 metadata records and 254,035 declared MXL files now provides **1,343 formal records** in shared topics, search and offline PDF/MXL/MIDI entries. The 1,641-candidate append totals 419 admitted, 1,008 excluded and 214 with specific unresolved gaps. Published native and review values are inherited. The latest 61 admissions reuse already verified files, without new downloads; explicitly printed guitar alternatives can enter the broad guitar-related topic without asserting simultaneous players. The 42 undeclared formats and three structurally invalid MXL files remain explicit boundaries. This is not the live MuseScore corpus and supplies no native MSCZ.

| Format | Verified records | Failed / missing / unacquired | Distinct contents | Distinct-content bytes |
| --- | ---: | ---: | ---: | ---: |
| PDF | 1,343 | 0 / 0 / 0 | 1,343 | 104,613,229B |
| MXL | 1,343 | 0 / 0 / 0 | 1,343 | 18,945,773B |
| MIDI | 1,343 | 0 / 0 / 0 | 1,335 | 12,119,419B |

All formats total 4,029 associations and 4,021 distinct contents / 135,678,421B. Shared MIDI never merges work or edition identities. The 1,190 prior clear instrumentation conclusions remain, with 153 records retaining concrete limits; notation views, empty templates and auxiliary layers do not automatically add players. The 597 absent source composer attributions are separate metadata gaps, not guessed identities.

The rounded interface retains self-hosted Latin fonts, system Chinese fonts and model-generated artwork. Lists start with 18 records and build full-text/fuzzy indexes on demand. No frontend dependency or artwork was added. Complete review ledgers remain in a private compressed receipt; browsing keeps the deduplicated compact catalog and embeds no score bytes. See the [publication record](docs/research/publication.md) for full rebuilding, performance and deployment evidence, and [TODO](TODO.md) for remaining evidence gaps.

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

The final code and public data passed 2,974 Python and 83 Node tests plus the public-boundary, translation and text audits in an independent clean checkout. The compact catalog is 6,122,972 bytes, up about 1.98%; all ten referenced static assets remain byte-identical at 284,265 bytes.

## Quick start

Visit the [online catalog](https://lin-qian123.github.io/guitar-atlas/) or preview it locally:

```bash
python -m http.server 8000 --directory public_site
```

Open `http://127.0.0.1:8000/`. Browse shared topics or enter a query.

Public cards link directly to source pages. Offline cards list local score files for the active category when available, with the source page as a fallback. PDF availability, missing-format counts, and acquisition status messages stay in private receipts rather than the interface.

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

The test extra includes PyMuPDF for PDF staff and text geometry checks. Base catalog dependencies retain the pypdf text fallback.

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

The initial metadata and PDF/MXL/MIDI acquisition commands below describe the historical 924-record scope. After expansion, their overwrite guards protect the existing library; use the full-publication append route for supplementation.

```bash
python scripts/build_musescore_library.py --root . --acquire-metadata
python scripts/build_musescore_library.py --root .
python scripts/review_musescore_translations.py --root . --apply
```

The initial 924 records have exact publication PDF locators. The dedicated
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

The original 924-record instrumentation workflow uses `score_instrumentation.py`, `score_pdf_evidence.py` and `score_midi_crosscheck.py`. Frozen private visual/TAB/title decisions and exact exceptions under `metadata/instrumentation/` protect that historical baseline. Its producer and verifier are historical tools; use the append workflow below for the expanded catalog. Mechanical TAB matching does not replace reviewed visual decisions. Actual part labels, Chinese instrumentation, original declarations and conflicting printed titles share the existing lazy search. Part labels include views and auxiliary layers and are not player counts.

### Full-publication audit and append

The original 924 records were a selection. The full audit checks all 254,077 CSV/metadata records and all 254,035 declared MXL files; 42 records declare no MXL and three files have structural failures. File recall, native identity, licensing, accepted instrumentation and player counts remain separate decisions. GM programs, lyric elements and title keywords do not establish a guitar arrangement or work identity.

`config/musescore_pdmx_expansion.json` freezes the new scope. Private full-scan evidence, raw candidates, plans, extraction outcomes, reviews and recovery transactions live in `sources/musescore/expansion/`. The append pipeline reads checksum-pinned local publication archives and makes no MuseScore requests. Original work objects, acquisition journals and review entries remain intact; physical reuse is format-specific.

With the complete audit and pre-task preservation baseline present, run `expand_musescore_library.py` phases `verify-archives`, `recall`, `prepare --selection sources/musescore/expansion/selected-records.json`, then `extract --format MUSICXML`. Run `review_musescore_expansion.py --phase scope`, extract PDF and MIDI, and run its `--phase final`. Only then run the append `commit` phase and `review_musescore_translations.py --apply`. All commands accept `--root .`.

Extraction may retain the full candidate batch; only final accepted native identities enter the shared catalog. To extend a plan still in its MXL stage, stop every writer and explicitly use `prepare --extend-plan`; it requires an unchanged prior-entry subset and preserves recovery evidence. After public export, run `python scripts/verify_musescore_expansion.py --root . --precheck`. Repeat without `--precheck` after a complete offline render to check every local entry and prior-record preservation.

The earlier 759-record continuation retains its fixed 1,220-record baseline and original `remaining-review.json.gz`; do not rewrite that historical evidence.

This deep review first runs `python scripts/expand_musescore_library.py capture-deep-continuation --root .`, freezing the task's published 1,248 records and effective evidence in `deep-continuation-baseline.zip`. Reuse the immutable 1,641-record plan and three format journals; do not replay original acquisition, prepare or the historical 924-record producer. Only the exact `deep-review-scope.json` identities may be added, while all published native records, reviews, translations and file relationships are inherited. `verify-continuation` performs a read-only preservation check.

After exact case updates, rerun scope/final and use `python scripts/review_musescore_deep.py --root . --consolidate` to losslessly retain all 549 candidates, 5,709 PDF pages of text, actual MXL/MIDI evidence and complete original proposals in one private `deep-review.json.gz`. Default `--verify` rechecks actual files without temporary proposals or producer scripts; `--refresh-outcomes` only updates canonical outcomes. Remove merged copies only after compressed readback and fresh guards pass. A later exact follow-up can use `--refresh-outcomes --supplement PATH` to retain its complete guarded decisions beside the immutable original proposals; default verification needs no temporary supplement. Then commit the append, append translations, export and fully rebuild offline. A later continuation must freeze its latest published scope rather than replay this task's 1,248-record baseline.

Count independent written performing roles, distinguishing normal/TAB views, collective desks, doubling and conflicting templates. Bounded repeat/tie/trill attack correspondence can explain an exact MIDI export defect while retaining the original bytes and visible playback limitation; it does not certify durations, dynamics, timbre, import fidelity or acoustic playback.

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
