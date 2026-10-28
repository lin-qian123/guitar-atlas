# 六弦漫行 / Guitar Atlas project instructions

## Directory maintenance

- Update the existing canonical documentation and final receipts when work
  continues; do not accumulate dated replacements, repeated README histories,
  temporary screenshots, trial checkouts or duplicate export/HTML backups.
- Keep source research and frozen integration evidence, exact translation
  decisions and compiler inputs, publication receipts, artwork provenance,
  current score manifests and native category directories. Preserve one recent
  offline-entry rollback copy. Do not rewrite Git history to remove old versions.
- `metadata/.cache/pages/` contains guarded source revisions.
  `work/title-review/2026-10-03/before/metadata/translations/` and review corpora
  are required application/compilation inputs. Deduplication journals and final
  source reports are evidence, not disposable caches.
- Remove only audited, unreferenced artifacts. Check source/score metadata,
  reviewed translation bytes, active web assets and offline links before/after;
  run complete tests and publication audits before synchronizing the remote.

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
- Do not commit PDFs, MXL/MusicXML, MIDI, GPX, caches, partial downloads, logs, private source
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
- Only PDF asset/member hashes enter `identical_pdf` relationships. Shared
  MXL/MIDI content is format-specific physical reuse and never a PDF identity
  or a reason to merge works; preserve its typed private evidence separately.
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

- The 2026-10-17 whole-library classification review is compiled with
  `scripts/review_library_classification.py` into
  `metadata/instrumentation/source_classification_reviewed.json`.
  `catalog_classification.py` checks every complete native-record digest and
  exact source-field, category, frozen-page or actual-file guard before applying
  this display/topic overlay. Never edit native records to fit an overlay.
  Source declarations, actual score review, and inconclusive source audits have
  separate evidence labels. A completed audit may still have unknown instruments
  or players; `guitar_unspecified` means guitar-related, not a confirmed pure
  acoustic ensemble. Explicit alternative instruments are choices, not players
  sounding together. Keep the lossless private receipt and full gaps under
  `sources/classification/review.json.gz`; merged proposals can be restored from
  it by the compiler. `verify_library_classification.py` checks the captured
  formal scope, exact allowed public changes and the full offline render.
  The CMS post ID must match both the native record and its exact URL; category
  and tag term IDs are a different namespace even when their numbers coincide.
  Approved extended-string solo and multi-digit guitar-ensemble grammar also
  adds exact category-topic memberships to already classified works. Verify
  those per-edition membership additions, not just changes from unspecified;
  string count is never performing-player count.

### Institutional and author supplement

- `scripts/discover_supplement_sources.py` resumes the separately scoped CSUN,
  yawnoc, Maikstrings, Derek Hasted and Guitar Classroom adapters. Keep source
  registration append-only. Their current source IDs, scope receipts, original
  credit context and native locator maps remain distinct; a source directory is
  an approved human fallback only when no dedicated record page exists.
  Maikstrings, Derek Hasted and Guitar Classroom have no native record ID; use
  `pdf:<SHA-256 of the exact original href UTF-8 bytes>` and keep the lossless
  locator/identity map privately. Preserve case and encoding; an explicit bundle
  uses its confirmed primary score href. Filename stems are not public IDs.
- CSUN discovery pins the 1,145 native IDs from the documented CONTENTdm query;
  that count is not the entire guitar collection. The query's five 100-byte
  fields are discovery evidence, never complete native titles or attributions.
  Use complete singleitem metadata for the current 424 admitted records and
  retain all excluded/pending outcomes and initial proposals privately. Native
  pointer zero is valid. Resolve the exact same-ID `/api/collection/.../download`
  URI against the confirmed `/digital` frontend mount, preserving the raw URI;
  an OCLC 404 redirect is not a score or an approved new asset host. Keep the
  endpoint-correction ledger and original failed requests. Metadata and PDF
  writers must stop before another pipeline uses the source's one-second clock.
- Treat explicit teaching-site download permission as personal offline
  acquisition, independently of public redistribution. Public pages contain no
  score bytes. Yawnoc's CC0 edition licence does not override its release-file
  robots prohibition; do not retry or switch routes after that denial. Keep its
  source-code evidence separate from acquired PDF availability.
- Group explicit Score/Parts/TAB bundles within one source edition; keep clearly
  labelled different versions distinct. Reference books are not score records.
  Source headings such as `3 Guitars` establish a declared count, whereas a
  software staff, file count, flexible ensemble or collection of 24 solos does
  not. A choral work title and a mixed vocal/instrumental series do not prove
  singers in the current arrangement. Bare Bass and unspecified orchestra sizes
  retain their actual uncertainty.
- Keep parser, acquisition and normalization commentary in private provenance.
  The source-scoped `project_source_public_notes` projection retains actual
  credits and concise rights facts for Maikstrings and yawnoc without changing
  native metadata or previously published source details.
- Append translations with `append_source_translations.py`; do not replay the
  historical global title review. Exact new-title decisions live in
  `source_supplement_reviewed_zh.json`. Preserve every earlier entry. The private
  `sources/source-expansion/baseline.zip` pins the previous publication;
  `verify_source_supplement.py` checks old native inputs, translation decisions,
  public fields, complete offline mappings and legacy category navigation after
  a fresh full render.
- `catalog_file_notes.py` applies only the exact cases in
  `metadata/instrumentation/source_file_notes_reviewed.json`; retain complete
  native/PDF/evidence-packet guards. Keep the original teaching PDF packet and
  later CSUN visual sample separate. Source declarations, actual printed
  alternatives and uncertain player counts must remain visible. Include both
  private packets in the offline input fingerprint; changed evidence requires
  a new full render.
- Classification snapshot caching is per source and per identical guarded path.
  Keep all per-record semantic/native checks and finish with fresh resolution
  and full stat guards of every unique snapshot. A changed path, file or guard
  must fail; cached filesystem work never establishes a different record's
  instrumentation or identity.

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
- Separate PDF integrity from instrumentation review. The 495 work-level and
  33 other section cases now have a complete broad evidence audit: 129 support a
  source/cover declaration, 36 a broad instrument family, 362 still lack exact
  current-role evidence, and one is a proven mismatched brass PDF. The first
  165 are not complete player-count or category-purity verification. Preserve
  the mismatched original but exclude only its exact local link. The third
  affected legacy page, `For 3 guitars (arr)`, remains unlinked alongside the
  two earlier pages until it applies the same exclusions. Historical audits and
  fresh integrity checks never establish library-wide instrumentation purity.

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

## MuseScore through the PDMX publication

- LibreScore is a search/download application, not an independent score source.
  `scripts/build_musescore_library.py` imports only the frozen PDMX v9 metadata
  publication configured in `config/musescore_pdmx.json`. Use MuseScore native
  record IDs and retain PDMX/Zenodo publication and per-record licensing evidence.
- The metadata route acquires two metadata files from approved Zenodo file
  endpoints and never requests MuseScore or score files. The separately
  authorized `scripts/acquire_musescore_pdfs.py` route uses
  `config/musescore_pdmx_assets.json` to retrieve the frozen PDMX PDF publication;
  dataset licensing, per-record score licensing and live source access remain
  separate policy entries. Do not give the generic single-PDF downloader a TAR
  endpoint or broaden MuseScore page hosts to Zenodo.
- The fixed publication file page is a separately approved Range route. Its
  two-stream downloader keeps existing prefix bytes, checks exact offsets and
  all range responses, shares the robots request clock, and verifies the whole
  archive before publication. An access refusal stops the source; never change
  routes after a challenge or 401/403/429. Keep only the current segment plan
  during interruption and the verified final download receipt afterward.
- For the MXL/MIDI route, `--rebalance-ranges` is a local-only recovery after
  every HTTP writer exits: validate the original two-half plan, actual prefix
  and partial lower bytes, and a complete upper tail with independent SHA
  guards. Preserve them through a resumable prepared transaction, split only
  the gap into fixed 64 MiB jobs (at most 32), and retain the two-stream limit.
  Never replan after source refusal; whole-archive size/MD5 remain mandatory.
- Verify the complete publication archive's exact size, upstream MD5 and internal
  SHA-256 before streaming its TAR members. Check every member's path, type,
  duplication and expansion bounds; retain only exact existing record locators.
  Validate selected PDF bytes and parsing independently. An archive checksum is
  not a publisher-supplied per-PDF checksum. Label files as PDMX exported PDFs,
  not original MSCZ files; preserve the frozen native metadata and roles.
- Keep interruption journals, per-record success/failure/missing decisions and
  verified SHA-256 objects under `sources/musescore/`. Resume the dedicated
  acquisition pipeline; the metadata builder refuses to overwrite an acquired
  or active file snapshot for every acquired format.
- `scripts/acquire_musescore_formats.py` extends only the same frozen 924
  native identities with MXL and MIDI, using `config/musescore_pdmx_formats.json`.
  Bind both format locators to the checksum-pinned authoritative CSV. Keep the
  existing PDF assets and all non-target fields unchanged. The separately
  verified MXL/MIDI archives, extraction journals and receipts are private;
  preserve the original PDF journal and acquisition report.
- Validate MXL ZIP paths/types, CRC and expansion limits, container root and
  complete MusicXML notation; never fetch external DTDs or resolve entities.
  Validate MIDI header/chunk bounds, tracks, event lengths, VLQs and end markers.
  These checks establish structural integrity, not note-by-note correspondence,
  faithful import into MuseScore or acoustic playback. Do not convert or claim
  native MSCZ files. Deduplicate immutable content within each format, retain
  every native-record relationship, and report PDF/MXL/MIDI counts separately.
  Metadata-only, failed or missing assets produce no local file link.
- GM programs establish candidates only. Source instrument names, exact native
  IDs/URLs, title/composer transcriptions and conflict flags establish the accepted
  subset. Track/staff counts and generic auto `Solo`/`Mixed Duet` labels do not
  establish guitar player counts. Preserve excluded/pending rows and reasons.
- Review the existing 924 downloaded records with `score_instrumentation.py`,
  `score_pdf_evidence.py`, `score_midi_crosscheck.py` and
  `review_musescore_instrumentation.py`. Keep the full private PDF, TAB-view,
  actual-file-title and exceptional-case review evidence under
  `sources/musescore/verification/`; mechanical TAB extraction does not recreate
  the frozen visual decisions. Preserve exact exceptional decisions in
  `metadata/instrumentation/musescore_reviewed.json`. The guarded private
  `instrumentation-review.json` overlays runtime display/topics without editing
  native metadata, IDs, assets, licensing or translated titles. Missing review
  preserves legacy metadata; present incomplete/stale review must fail closed.
- Instrumentation review schema 1 keeps its complete-catalog byte guard and
  complete coverage. Schema 2 permits a completed reviewed scope within an
  appended native catalog: `native_record_sha256` maps exactly the reviewed IDs
  to `catalog_instrumentation.per_record_guard` of every original native field,
  including all asset and licensing fields. Keep the corresponding `works`
  entries and prior review values unchanged; each entry still requires fresh
  PDF, MXL and MIDI file guards. Unreviewed appended records receive no file
  conclusion. Only the reader may emit `_applied_instrumentation_review_ids`;
  reject that marker in native catalogs and restrict public review fields and
  `file_crosscheck` topics to its exact IDs. Do not rebase historical proof
  hashes or overwrite the original 924-record acquisition/review receipts.
- Count independent written performing roles after normal/TAB view review,
  not software parts, staves, tracks, instrument IDs or playback patches.
  Harmony-only or rhythmic-slash accompaniment can be an active guitar role;
  all-rest placeholders and confirmed auxiliary layers do not add performers.
  Collective desks, alternatives, doubling and conflicting labels retain
  explicit limits; a confirmed guitar ensemble may have unspecified desk sizes.
  Keep known non-guitar/voice/electric/bass scope exceptions in the shared
  `other_instrumentation` topic rather than calling a known arrangement unknown
  or silently deleting its native record. File-title conflicts have a visible
  warning and searchable actual title; source titles remain verbatim. Internal
  MusicXML template headings alone do not establish a different work.
- Append translations with `scripts/review_musescore_translations.py`; retain all
  other source decisions byte-for-byte at the entry level. Keep unsupported names
  in their original language. Do not replay the global historical title review.
- MuseScore-only encoding recovery requires complete, reversible UTF-8 byte
  fragments and explicit C1 evidence. Keep native text and exact review guards;
  incomplete fragments retain the original. Exact full-name title credits may
  move to details, but a surname or title keyword cannot establish that boundary.
- Public/offline projections share search and topics. The public edition exposes
  historical metadata and human source pages. Only freshly verified publication
  PDFs produce offline file links; source access restrictions and metadata-only
  assets never establish local score availability. Preserve all unrelated
  records, categories, translation bytes and old local-edition mappings.

### PDMX full-publication supplement

- The original 924 records are a historical selection, not the complete guitar
  scope of the 254,077-row PDMX v9 publication. Preserve their original import,
  three acquisition journals, native work objects and completed review values.
  Do not relax or replay the historical fixed-scope acquisition commands.
- `config/musescore_pdmx_expansion.json` and
  `scripts/expand_musescore_library.py` own the separately authorized append.
  Audit every original CSV/metadata record and every MXL member, including
  records without GM 24/25 or a guitar keyword in their metadata. Bind exact
  native identities and all format locators to the checksum-pinned CSV.
- Full-file recall is not acceptance. Keep electric/bass/voice/large-ensemble
  exclusions and ambiguous instrument identities separate; TAB and tuning can
  also describe other fretted instruments. Lyrics elements may be annotations.
  Explicit instrumental roles establish scope; playback patches alone do not.
  Uncertain player counts may retain an accepted guitar scope with a visible
  unnumbered classification, rather than inventing solo/duo/trio counts.
- Preserve every title/URL equivalence decision. A single reversible HTML
  entity representation and URLs independently verified against the same native
  score and uploader IDs may establish equivalent representations, without
  changing any raw title, original URL, uploader or source transcription.
- Keep the append plan, extraction/review outcomes, rejected/pending records,
  fresh archive integrity, transaction and preservation evidence privately in
  `sources/musescore/expansion/`. Old journals remain historical evidence.
  Finalize `integration.json` before a complete offline render; publication
  receipts belong outside that fingerprinted input. Only new translation
  entries may be appended, retaining all earlier decisions exactly.
- Exact expansion decisions live in
  `metadata/instrumentation/musescore_expansion_reviewed.json`. Guard each
  appended decision with the complete planned native-record digest, original
  identity fields, MXL bytes and all part names; PDF-based decisions also guard
  the exact PDF. Source-scoped exclusions must retain their specific source and
  active-file evidence, automatic result and unknown player counts. Never turn
  bare Bass, Alto, Primo/Secondo or a playback patch into a global identity rule.
- Use the separately typed expansion vocabulary and official instrument-name
  references without changing the frozen 924-record producer. Collective names
  retain unknown counts. Only finite known drum-kit components may share that
  exemption; a named percussion instrument does not suppress cross-family
  conflicts. Keep actual non-rest instrument changes when reviewing scope.
- A reviewed MIDI template-name explanation additionally requires exact MIDI
  and PDF bytes, a resolved actual part and a single-part, verbatim track-name
  correspondence. Preserve its automatic conflict and original labels; this
  explanation never clears unrelated name or playback conflicts. New or changed
  instrumentation decisions require a complete offline rebuild.
- For this fixed 759-candidate continuation, run the idempotent
  `expand_musescore_library.py capture-continuation` phase. The single private
  `continuation-baseline.zip` preserves the published 1,220 records, all prior
  native/review/translation and offline mappings, and exact earlier evidence.
  Reuse the immutable 1,641-record plan and format journals. New admissions must
  belong to `remaining-review-scope.json`; inherit every published review value
  rather than replaying it under new terminology. Keep the original 924-record
  baseline and acquisition receipts intact.
  Consolidate all 759 records, complete PDF-page text and original review
  proposals losslessly with `review_musescore_remaining.py`; verify the gzip
  readback and fresh format guards before removing merged temporary files.
  Uncertain written-row counts must not appear as confirmed player numbers
  in either displayed instrumentation string.
  A later continuation must first freeze its latest published scope and roll
  the stage guards forward; this task's 1,220-record baseline must not silently
  stand in for the subsequently published 1,248-record library.
- An exact MIDI channel-collision review may explain a known export playback
  defect only with complete native and PDF/MXL/MIDI guards, every conflicting
  group, its distinct named program-origin role, and complete target note-count
  correspondence. Preserve the automatic conflict and original MIDI bytes;
  show the unresolved playback quality in the public review summary. This does
  not certify note sequences or infer performer counts from MIDI patches.
  Independent Contra Guitar roles count in the acoustic-guitar family while
  retaining their specific type; Mandola, Balalaika, Bagpipe and Tin Whistle
  remain distinct instruments with their native names and written roles.
- The separately authorized deep review starts from the published 1,248-record
  library and exactly the 549 pending IDs in `deep-review-scope.json`. Use
  `capture-deep-continuation` and `verify-continuation` before editing published
  inputs. `deep-continuation-baseline.zip` pins that publication, reuses its
  checksum-pinned parent archive and preserves the original 759-record review
  and acquisition journals. Never replay either older baseline over later
  admissions. Further stages require a new current-publication baseline and
  explicit stage guards.
- The subsequent broad review starts from the published 1,282-record library and
  exactly 296 pending candidates. Its immutable
  `broad-continuation-baseline.zip` and `broad-review-scope.json` take precedence
  over the older baselines. `review_musescore_broad.py` compiles the exact guarded
  decisions in `metadata/instrumentation/musescore_broad_reviewed.json` under
  `config/library_classification.json`, using the existing source locks and a
  resumable two-report transaction. It preserves all published native/review
  values and original automatic conflicts; guitar presence or a printed guitar
  option can establish relatedness while other roles, subtypes, title identity
  and counts remain explicitly uncertain. Empty templates establish no activity.
  This stage adds 61 records (1,343 total), excludes 21 and retains 214 with
  concrete gaps. Future admissions require a new baseline of that current
  publication; never reuse the 1,282-record baseline as a later published scope.
- Preserve deep-review proposals and full PDF-page evidence losslessly in the
  single `deep-review.json.gz` receipt before deleting merged intermediates.
  Keep proposal decisions distinct from current production scope/final results;
  every unresolved record needs its actual remaining evidence gap.
  A later exact follow-up may use `review_musescore_deep.py --refresh-outcomes
  --supplement PATH`: retain the complete supplement, original byte/semantic
  guards and all earlier proposal values. Bind each supplemental identity,
  three-format asset and complete exact case to current production outcomes;
  default verification must work after the temporary supplement is removed.
  Do not replace an embedded supplement with different content.
- Exact playback-defect cases may use `score_mxl_playback_correspondence.py`
  only with a fresh guarded complete target attack match. Its bounded grammar
  validates repeats/endings and tie chains, and permits extra attacks only
  inside explicitly printed trill windows with matching pitches and onsets.
  Unsupported notation, dangling ties or unmatched attacks fail closed. This
  proves the stated attack correspondence, not durations, timbre or repaired
  MIDI. Keep the original automatic conflict and visible playback limitation.
- Exact acoustic-bass template reviews require complete source declarations,
  actual PDF/MXL activity and the official instrument definition. A default
  plucked orchestral-contrabass template does not globally resolve bare Bass,
  bass-guitar/TAB conflicts or subsequent instrument changes. Rabeca and Viola
  Amarantina retain distinct types and original names. Explicit string/brass
  sections keep unknown player counts even after their instrument family is
  resolved; one software part never establishes one section player.
  Exact old-polyphony Tenor/Contratenor labels can denote written registers;
  inspect the full source and current score-instrument declarations, PDF and
  lyrics context before asserting a singer. Lyrics on a named instrument do
  not change its identity. Potential nonoverlapping doubling is not an author
  declaration or a confirmed eight-player ensemble.

## Public and offline editions

- Maintain the shared score-publication/collection-index presentation: system
  Chinese serif and self-hosted Latin display type, fine rules, layered rounded
  collection cards, legible controls, responsive records and reduced-motion support.
  Keep font licenses and illustration provenance. Update CSS/app cache versions
  when their bytes change; offline script injection must support those query
  strings. Measure actually referenced assets separately from historical files
  and catalog data. Design evidence is in
  `docs/research/presentation.md` and the preceding rounded
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
  PDFs, MXL/MusicXML, MSCZ/MSCX, MIDI, GPX, file/download URLs, local paths, hashes, or private filesystem
  metadata.
- Keep their presentation and search behavior synchronized: render the offline
  root from the public template and shared assets using the offline-only adapter
  under `scripts/assets/`. Embed offline data for direct file opening; never
  place that data or adapter in `public_site/`. Local score links must respect
  the active category memberships. Preserve all parts; show local file links
  only for available editions and retain the source-page link as the fallback.
  Do not display PDF acquisition/availability states, missing-format counters,
  or exclusion-processing messages in cards or version details. Keep those
  states in private acquisition and verification records. Back up the old root entry
  before replacing it; keep generated offline pages Git-ignored.
- Offline MuseScore entries expose verified PDF, MXL and MIDI files together
  under the existing work and category membership. Keep prior PDF file fields
  and counts stable; new format counts and unavailable states are separate.
  Hash-version the offline adapter assets and keep file bytes outside the HTML.
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
