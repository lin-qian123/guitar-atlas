# Guitar Atlas project instructions

Guitar Atlas is a reproducible, source-attributed guitar score catalog and
local offline library. The current sources are IMSLP and ClassClef; the
architecture must allow additional websites without renaming the project or
conflating their identities, categories, licensing, or review status. The GitHub
repository is `guitar-atlas`; the existing local directory may remain `imslp`.

## Shared source and storage contract

- Register sources and approved page hosts in `config/sources.json`. Keep each
  source's discovery, extraction, and validation rules in its own adapter.
- Identify records with a source and its native record ID; the public schema
  uses `source_id` plus `source_record_id`. Preserve native IDs such as IMSLP
  `work_id`. Merge category memberships within that identity.
  Similar titles or musician names across websites do not establish the same
  work, arrangement, edition, or file and must not trigger automatic merging.
- Preserve source titles and musician attributions verbatim as source fields.
  Chinese names are reference translations and never replace original names.
  Unknown instrumentation, original/arrangement status, or translation review
  status must remain unknown; do not infer them from a site or directory name.
- Never accept HTML, CAPTCHA, login, error, partial, or non-PDF responses as
  scores. Validate PDF header, expected byte size and upstream checksum when
  supplied, internal SHA-256, and parseability. Do not claim upstream-checksum
  verification when a source supplies no checksum.
- Keep metadata and download work resumable. Use atomic `.part` files,
  descriptive requests and polite rate limits. Stop when human verification is
  required, keeping a clear failure or pending state rather than bypassing it.
- Deduplicate physical PDFs by internal SHA-256, preserving every source
  attribution, manifest relationship, and category-local view. Keep IMSLP SHA-1
  when available. Verified objects are immutable; category views must not
  create duplicate PDF entities.
- Run `python scripts/deduplicate_source_pdfs.py --root .` after ClassClef
  downloads stop and before final verification. It is a dry run by default;
  `--apply` permits changes. Atomically hard-link a ClassClef object to an
  approved IMSLP file only after fresh SHA-256, IMSLP source SHA-1, size, and
  PDF parsing checks establish identical content. Preserve both paths,
  metadata, and original bytes. Metadata-only candidates are not completed
  physical deduplication. Re-run verification after applying changes.
- Generated catalogs and verification output must distinguish category
  memberships, source records, manifest records, and unique physical PDFs.
  A count of valid manifest entries is not a count of unique PDF objects.
- Measure coverage against a frozen source snapshot and approved scope/config
  version. Report upstream drift separately. Do not claim complete coverage
  until manifests, available files, hashes, applicable category rules,
  translation status, and local links have been freshly checked; retain all
  unavailable entries and explicitly state incomplete boundaries.
- When extending the library, use resumable production pipelines directly.
  Do not add specification or review gates unless scope, permissions, or
  destructive changes genuinely require them.
- Use `python`, not the system `python3`, for project commands.
- Keep `README.md`, `README.en.md`, `TODO.md`, and this file current.
- Do not commit PDFs, MIDI, GPX, caches, partial downloads, logs, private source
  snapshots, or generated category/offline catalogs. Reviewed translation
  source files and the compiled work-ID catalog under `metadata/translations/`
  remain versioned review assets, not generated category catalogs.

## IMSLP adapter

- Preserve each included IMSLP category name exactly as its directory name.
- Include pure-guitar categories configured in `config/categories.json` and
  mixed/chamber categories configured in `config/mixed_categories.json`. Do
  not infer scope from the mere presence of the word `guitar`.
- Exclude electric, bass, Hawaiian, steel, and slide guitar; voice/chorus;
  electronics/tape; large orchestra; and alternative-solo categories where
  guitar is only an `or` option.
- Group mixed categories as strings, woodwinds, brass, keyboard/free reed,
  plucked instruments, percussion, or mixed chamber ensemble.
- Treat original and `(arr)` categories separately. Original categories may
  use only original scores/parts; arrangement categories may use only the
  exact target instrumentation subsection in the page `FILES` area.
- Instrumentation matches must be fully anchored after Unicode/markup
  normalization. A target prefix followed by bass, voice, another instrument,
  `and`, `with`, a list, or an unconfigured `or` is not a match.
- Treat `metadata/translations/title_overrides_reviewed_zh.json` as the
  canonical work-ID keyed Chinese-title review. It takes precedence over
  title-keyed machine-translation caches during metadata rebuilds and renders.
- Keep `scripts/imslp_library/` as the IMSLP source adapter. Its name does not
  define the scope of the whole project.
- Apply reviewed score exclusions from `config/score_exclusions.json` only
  within the IMSLP adapter, matching the exact category, native `work_id`, and
  filename. Preserve the source section and reason as audit evidence; do not
  generalize an exclusion to other versions or category memberships.
- The 2026-09-28 review excludes six records whose source sections explicitly
  include an extra bass instrument from the new offline file links. Keep the
  original files. Do not link the two affected legacy detailed category pages
  from the new interface until those pages apply the same exclusions.
- Separate PDF integrity from instrumentation review. The current review still
  has 495 `Work-level target-guitar score` records and 33 other section
  candidates awaiting exact file-level instrumentation verification. Historical
  audit completions do not establish that the entire current library has freshly
  passed category-purity review; retain these pending boundaries in reports.

## ClassClef adapter

- Use `config/classclef.json` for source scope and request settings, and the
  resumable `scripts/build_classclef_library.py` production entrypoint.
- Keep snapshots, download state, verification reports, normalized catalog,
  and local file objects under the Git-ignored `sources/classclef/` directory.
- Preserve every discovered in-scope score entry, its original attribution,
  source page, and directory relationships. Separate source categories from
  IMSLP's verified instrumentation categories.
- Record absent instrumentation, original/arrangement labels, and Chinese
  review data as unspecified. A site offering guitar scores does not establish
  the number of players or edition details for each record.
- Prefer a confirmed dedicated score page for public source navigation;
  otherwise use a confirmed directory page. Keep erroneous or obsolete raw
  `INFO` links in internal provenance, without presenting them as public links.
- Preserve unavailable or failed downloads in the resumable catalog. Expose
  local links only for successfully verified PDFs; source links remain useful
  for records with no verified local file.
- Keep records that provide Guitar Pro or other score formats without a PDF;
  retain their source/format metadata without inventing a local PDF link.
  Preserve `resource_type` through public export and display. Label reference
  material such as the glossary separately and report score/reference record
  counts separately from PDF availability and physical file counts.
- Free download availability does not imply public-domain status or permission
  to republish source files. The public export contains source-page links only.

## Public and offline editions

- Keep the offline library and public web export as separate products. The
  offline root may link to verified local PDFs. `public_site/` must contain no
  PDFs, MIDI, GPX, file/download URLs, local paths, hashes, or private filesystem
  metadata.
- Keep their presentation and search behavior synchronized: render the offline
  root from the public template and shared assets using the offline-only adapter
  under `scripts/assets/`. Embed offline data for direct file opening; never
  place that data or adapter in `public_site/`. Local score links must respect
  the active category memberships. Preserve all parts and label unavailable
  records without generating broken score links. Back up the old root entry
  before replacing it; keep generated offline pages Git-ignored.
- Build the public catalog only from approved source configuration and validated
  catalogs. Deduplicate results by `source_id` plus `source_record_id`, preserve every
  category membership, and link records directly to validated HTTPS pages on
  their corresponding source websites. Keep legacy IMSLP IDs stable.
- Regenerate `public_site/data/catalog.json` with
  `scripts/export_public_site.py` and run `scripts/validate_public_site.py`
  plus the test suite before publishing the public site.
- Keep public-facing copy brief, objective, and grounded in the catalog's
  purpose. Avoid slogans and conversational recommendations. Put methodology
  in the README. Default to the category directory; show work lists for a
  query or specific category. Preserve original titles alongside available
  Chinese display titles and keep every source category reachable.
- Keep search-only aliases in `public_site/data/search-aliases.json`, keyed by
  canonical full composer names or stable work IDs. Preserve compatibility for
  existing IMSLP work-ID aliases. Never rewrite catalog identities from a fuzzy
  match. Preserve all query terms and same-membership filters; use labeled fuzzy
  recovery only when exact/alias matching returns no works.
- Run `node --test tests/search.test.cjs` (Node.js 22+) alongside the Python suite
  when changing or publishing public search behavior.
- Publish GitHub Pages from `public_site/` only. Verify the pushed Git commit
  and deployed page separately; local output does not establish remote success.
