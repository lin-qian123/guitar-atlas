# 六弦漫行 / Guitar Atlas project instructions

Guitar Atlas, named **六弦漫行** in Chinese, is a reproducible,
source-attributed guitar score catalog and local offline library. Use
`六弦漫行` for the Chinese name and `Guitar Atlas` for the unchanged English
name. The page's upper-left navigation brand displays `Guitar Atlas`; the
Chinese main heading displays `六弦漫行`, and the bilingual page title is
`六弦漫行｜Guitar Atlas`. Approved sources and frozen scopes are registered in
`config/sources.json`; the architecture supports additional websites without renaming the project or
conflating their identities, categories, licensing, or review status. The GitHub
repository, local root directory and Python package remain `guitar-atlas`.
The existing Codex project remains named `Guitar Atlas`.
Display-name changes do not rename repositories, directories, source IDs,
native titles or record identities. Historical receipts may retain
the name used at their date. `imslp` remains only where it identifies the actual
source or adapter.

## Shared source and storage contract

- Register sources and approved page hosts in `config/sources.json`. Keep each
  source's discovery, extraction, and validation rules in its own adapter.
- Keep source-discovery studies and candidate inventories in `docs/research/`.
  Research candidates are not registered sources or acquisition authorization;
  preserve separate evidence for metadata reuse and file acquisition.
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

## Additional adapters and unified catalog

- Use `scripts/discover_open_sources.py`, `scripts/discover_archive_sources.py`,
  and `scripts/discover_additional_sources.py` for the approved adapters under
  `scripts/source_adapters/`. Freeze raw discovery and exclusion evidence under
  `sources/<source>/`; distinguish discovered scope, accepted records, and
  successful details. Candidate policies remain in
  `config/source_acquisition_policies.json` and are not acquisition permission.
- `scripts/catalog_unification.py` owns shared topics and typed relationships.
  Shared topics are independent of native source categories; preserve exact
  category memberships when applying source/kind/category/topic filters.
  Bare `Guitar`, `Classical Guitar`, or RISM `guit` establishes an instrument,
  not a solo player count. Pending scope declarations remain unclassified.
- Relationships require explicit upstream file references, freshly verified
  PDF content, exact DGA institution/native shelfmark evidence, or explicitly
  typed source collection membership. Empty URLs, generic site pages, names,
  titles, and untyped parent IDs are never holding/file identity evidence.
- Where a directory has no native record ID, use a documented deterministic
  locator digest (Delcamp and four GuitarDownunder file locators use
  `pdf:<SHA-256 of the exact original locator>`). Keep the
  exact locator and the identity map privately; do not expose score paths as
  public record IDs. Preserve existing native IDs at other sources.
- `scripts/acquire_source_assets.py` processes only adapter-approved `pending`
  PDF assets, with wildcard-aware robots rules, approved endpoint hosts,
  shared request clocks and at most two streamed responses per source.
  Challenges/401/403/429 stop that source; untouched jobs remain pending.
  ZIPs must validate every PDF member and reject unsafe paths/expansion.
  Store verified bytes immutably in `sources/objects/sha256/` and retain
  source-local hard links and receipts. This does not establish complete
  physical deduplication of the legacy IMSLP library.
- After acquisition stops, run `python scripts/deduplicate_added_pdfs.py --root .`
  before `--apply`. Only fresh SHA-1/size upstream candidate matching plus
  SHA-256, PDF parsing and complete path checks permit hard links. Re-run the
  dry check after applying. The original ClassClef deduplicator remains separate.
  `verified_source_relations.py` exposes only known record-ID pairs from a
  current, completed journal after rechecking inputs and files. Stale, active or
  incomplete evidence cannot establish public content relationships. Include
  that journal in the offline input fingerprint and do a full render afterward.
- Keep exact original guards in `metadata/translations/source_titles_zh.json`
  and source-scoped musician/category assets. The reference terminology asset
  is `expansion_terminology_zh.json`; its source guards and contexts apply.
  `review_source_translations.py` preserves reviewed exact correspondences,
  constrained reference terminology, and explicitly marked machine drafts.
  A translation service result is never semantic review. Machine drafts
  remain a failed publication audit until reviewed; retain uncertain names
  with a concrete reason instead of claiming a conventional Chinese identity.
- Public projections may contain source edition/role/license descriptors but
  never private local inventory, download endpoints, hashes or filesystem
  fields. Source metadata availability and local file integrity are separate.
  A site's compiler is not every edition's editor; library contributors are
  not composers unless the source supplies that role.
- Record source scope, exclusion/detail/download failures, translation states,
  typed graph edges, manifest members, content hashes, paths and inodes in the
  private run reports. Maintain a human-readable receipt in `docs/research/`
  with `scripts/report_source_expansion.py`; do not claim source-wide coverage
  for partial pagination or imply local changes were pushed/deployed.

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

- Maintain the shared score-publication/collection-index presentation: system
  Chinese serif and self-hosted Latin display type, fine rules, layered rounded
  collection cards, legible controls, responsive records and reduced-motion support.
  Keep font licenses and illustration provenance. Update CSS/app cache versions
  when their bytes change; offline script injection must support those query
  strings. Measure actually referenced assets separately from historical files
  and catalog data. Design evidence is in
  `docs/research/2026-10-04-generated-category-art.md` and the preceding rounded
  layout receipt. Prefer model-generated artwork for meaningful illustrations;
  keep prompts/provenance and use a compressed shared atlas for category art.
  Decoration does not establish instrumentation or player-count evidence. Prefer
  in-place CSS edits, one optimized hero and one reusable category atlas; do not
  accumulate complete style overrides or decorative libraries.
- Audit text with `scripts/audit_catalog_text.py` as well as the translation
  coverage audit. Inspect every record, category, edition-detail and collection
  text field; distinguish detected defects, semantic review clues and legitimate
  bibliographic annotations. This audit is not authoritative-name certification.
- Keep machine title drafts available for review and retrieval, but use the
  source title as the primary heading until a supported reference or conventional
  Chinese title exists. Contextual repairs do not by themselves upgrade a draft.
  A complete constrained music grammar or an exact title/attribution review may
  establish a reference translation; preserve guards and review evidence.
- Separate primary display titles/names from source bibliographic transcriptions
  with explicit display fields and typed detail notes. Preserve original guards,
  source identities, full searchable provenance and legitimate supplied titles.
  Never delete all brackets, invent missing characters, infer a composer from a
  book title, or treat source-author/editor/performer labels as composer evidence.
- Keep the complete frozen title decisions under
  `metadata/translations/review_2026-10-03/`. Apply them with
  `scripts/apply_title_review.py` only after full source-ID, original-title and
  attribution coverage checks. Exact primary-title decisions additionally guard
  `display_original`; a new projection boundary requires review rather than
  silently dropping a checked Chinese heading. Detailed review ledgers and
  references stay outside the compact browser payload.
- Display-only whitespace normalization keeps native titles verbatim. The
  exact 2026-10-04 spacing-boundary rebase is recorded in
  `review_2026-10-03/display_spacing_guard_rebase.json`; never replace an exact
  display guard with fuzzy or normalized-string acceptance at publication.
- Apply the final credit/display supplement only after its exact preceding
  `before_zh` and `before_display_zh` agree with the full semantic decision.
  Keep complete reference transcriptions in edition details after the final
  primary-title override. Reading notes and source responsibility labels are
  not title words; real supplied titles, numbering and musical content remain.
- Final production-projection supplements are sequential reviews of the
  preceding complete/display Chinese values. Exact reasons may retain an
  unsupported phonetic name or ambiguous source title in its original language;
  neither Chinese metadata labels nor a mechanical display fallback establishes
  a translated primary title. Refresh legacy category views with
  `scripts/refresh_legacy_category_display.py`, preserving source manifests and
  every existing link; its default is a dry run.
- Run the actual-headline supplements after the final projection stage, with
  the same exact native/display and preceding Chinese guards. Move review
  labels and archival folio locations to complete edition transcriptions;
  keep actual book numbers and musical catalogue identifiers. The text audit
  rejects explicit review labels in primary headings while preserving them in
  details. A passing terminology scan alone is not semantic certification.
- Delcamp source attributions sometimes contain actual title words. Only the
  frozen exact display mappings in `catalog_display.py` may separate them;
  never consume a title merely because it equals the contaminated attribution.
  Preserve the original attribution and unspecified source role. In archival
  slash-separated transcriptions, require an explicit responsibility boundary,
  not a surname mentioned somewhere later in the string.
- Wrap Chinese titles using balanced title marks. Strip only an actual outer
  enclosure; never use character-set stripping that removes nested closing marks.

- Keep recognition references in `metadata/ranking/recognition.json`, with
  exact source full-name keys and stable work IDs guarded by original title
  and attribution. Compile small numeric display weights through
  `catalog_ranking.py` into public `data/ranking.json`; weights are curated
  repertoire familiarity, not measured traffic or identity evidence.
  Search relevance always precedes these weights; no-query browsing uses
  descending weight with stable composer/title/ID ties. Preserve all query
  terms and same-membership filters, including strong name boundaries.
- Use `catalog_payload.py` and `assets/catalog-codec.js` for lossless compact
  browser transport. Keep canonical JSON for audit and compatibility fallback.
  Validate decoded compact public data against the canonical catalog and reject
  unused transport table entries; compression never exempts privacy checks.
  Offline snapshots embed catalog, aliases and ranking without remote fetches;
  decode both compact and legacy snapshots before metadata refresh guards.
  Build full-text fields and fuzzy vocabulary lazily; do not inflate initial
  category browsing with whole-catalog tokenization or large DOM result lists.

- Keep persistent display translations in `metadata/translations/`: IMSLP
  work-ID title overrides, ClassClef full-ID title entries, source-scoped
  `musicians_zh.json`, and source-scoped `categories_zh.json`. Apply them after
  discovery and before export. Guard every entry with its exact original text;
  stale IDs or changed source text must fail instead of silently relabeling data.
- Public translation schema 1 records title, composer, and category evidence
  separately. `reviewed` means a supported conventional name; `reference` is a
  checked reference translation; `retained` requires a concrete reason for
  keeping the original. Unchecked drafts remain `machine`; absent translations
  are `untranslated`; `not_applicable` is only for absent source attribution.
  Derive the aggregate work status from its fields. Never infer review from
  non-empty Chinese text or from another field's status.
- Keep raw source text in the internal snapshot. Remove malformed inline
  download-link markup from display text without changing source IDs or the
  title's actual wording; do not expose embedded download URLs as title text.
- Run `python scripts/audit_translations.py` before publication, alongside the
  public validator and search tests. Its coverage/status check does not prove
  authoritative-name accuracy or PDF integrity. Report retained originals and
  missing source attributions separately from translated fields.
- For display-only refreshes of an unchanged file/source snapshot,
  `python scripts/render_master_index.py . --metadata-only` preserves verified
  local editions and backs up the old entry. It checks identities, manifest/configuration fingerprints, current
  exclusion and availability mappings, existing links, and file sizes, not PDF
  hashes. Legacy pages bootstrap a fingerprint only after their complete mapping
  agrees with the current source manifests. Run a full render after acquisition, manifest, file,
  category, or instrumentation changes; never describe a metadata refresh as
  fresh full PDF verification.

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
- Before publication, run the complete Python suite, every `tests/*.test.cjs`
  Node test, both translation/text audits and the public boundary validator.
  Inspect the staged file set for private source snapshots, local catalogs,
  downloads and credentials. Keep the canonical catalog compatibility fallback.
  Record the exact remote ref, successful Pages workflow head and live asset
  byte parity in the publication receipt before reporting success.
