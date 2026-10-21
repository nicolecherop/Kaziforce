# Skill standardization

KaziForce resolves manually entered skills against a local English ESCO catalogue. It retains the entered name and attaches a recognized concept only when exactly one concept has the same normalized preferred or alternative label. It does not infer a skill from a CV, qualification, job title or similar-looking word. Matching scores and rankings are a separate stage.

## Reference data and source

The pinned reference release is ESCO v1.2.0, explicitly supported by the [European Commission web-service API](https://esco.ec.europa.eu/en/use-esco/use-esco-services-api/esco-web-service-api). This is a chosen reproducible release, not a claim that it is the latest ESCO publication. The [official download service](https://esco.ec.europa.eu/en/use-esco/download) also provides CSV packages. Its [dataset structure](https://esco.ec.europa.eu/en/structure-esco-downloadable-datasets) identifies skills_en as the English skill list and concept URIs as the keys connecting ESCO data.

`scripts/download_esco.py` explicitly exports released concepts from the official bulk skill API with language=en and selectedVersion=v1.2.0. It keeps at most three public requests in flight and preserves page order. ESCO's offset parameter is a page number; generated next links are not used to infer that convention. The export validates consistent totals, page sizes, unique URIs, released status and full embedded concepts before publishing a CSV and JSON manifest. The manifest records the source, selected release, retrieval time, count and SHA-256 checksum. Normal requests never call this download script or the external API.

`data/esco/` retains this public reference export and provenance. User records, uploads and credentials are never placed in this directory. Preferred labels, alternative labels and descriptions originate from ESCO, developed by the European Commission; the downloader exports only English fields in the standard CSV column names.

The reference contains 13,939 individual skills and knowledge concepts. The bulk response also contains 640 hierarchy groups. Those group identifiers were verified against the official skills-hierarchy concept collection and excluded from the prepared CSV. The manifest records the bulk total, excluded count and group-source checksum. Future downloads filter individual concepts through their member-skills scheme membership before publishing the CSV.

The reference CSV has Git text conversion disabled in .gitattributes so its recorded SHA-256 remains valid across Windows and other checkouts.

## Import and activation

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py import_esco data/esco/esco-v1.2.0-en.csv --release v1.2.0 --source-url https://ec.europa.eu/esco/api/resource/skill --activate
```

`matching/catalogue.py` validates the complete UTF-8 CSV, columns, skill URI format, duplicates, label lengths, row limits and content size before writing anything. It imports the release and all labels inside one transaction. A failure preserves the previous active catalogue. Reimporting the same release/checksum is idempotent; different content under an existing release is rejected instead of overwriting historical reference data. Release names with or without a leading v are stored with v. The import command uses --release because Django reserves --version for its own version output.

Only one catalogue is active. New releases can be imported without --activate and activated later by rerunning the same command with --activate. Old versions are retained. Reference data is view-only in Django admin; maintenance goes through the import command. The application role owns these reference tables in the existing PostgreSQL database.

## Resolution and review

`matching/normalization.py` defines labels-v1: Unicode NFKC normalization, case folding and whitespace collapsing. It preserves symbols such as +, # and periods so C, C++ and C# remain different. It does not strip accents, stem words, fuzzy-match misspellings or manufacture aliases.

`matching/skills.py` resolves all supplied terms in one batch. A unique preferred/alternative label produces mapped, several candidate concepts produce ambiguous, no label produces unrecognized, and an unavailable active catalogue produces not_checked. Ambiguous terms do not receive an arbitrary concept URI. Original names are always returned, including unknown terms. Resolution is deterministic for unchanged input, catalogue and normalization version. Several entered terms may resolve to the same URI; scoring deduplicates concepts so aliases cannot inflate a score. See [matching](matching.md) for the scoring baseline.

Pages retain each entered skill name. Recognized skills have no extra status message. Unrecognized skills or an unavailable catalogue show “Skill added.” Ambiguous skills show “Skill added. A more specific name may improve matching.” Recruiters can review saved skill names in the job editor. These messages do not verify competence or change the underlying resolution and scoring rules. The authenticated GET endpoint /skills/search/ returns at most ten local reference suggestions for bounded prefixes. It never searches candidate/recruiter records. Names longer than the profile/job field's 80-character limit are excluded from suggestions. Typed terms remain valid without JavaScript, when no suggestion exists or when a request fails.

The browser helper uses delegated input events, so newly added skill rows also work. It debounces requests, aborts superseded requests and checks sequence/focus before displaying suggestions. Suggestions are inserted using DOM text/value properties. Each editor keeps its existing named page template and includes shared suggestion/review components.

## Application provenance

At submission, candidate and job skill names are resolved together against the same selected catalogue. profile_snapshot.skill_standardization and job_snapshot.structured_requirements.skill_standardization contain original names, statuses, mapped URIs/labels, catalogue version/language/source/checksum and normalization version. Later profile edits, job edits and catalogue activations do not change those stored JSON copies. Older applications without these keys remain readable without invented historical mappings. No new extraction or document parsing is involved.

## Verification

Run the PostgreSQL suite with manage.py test tests --keepdb and the suggestion tests with node --test tests/skills.test.cjs. Tests cover immutable versions, failed-import rollback, activation, aliases, ambiguous labels, technical punctuation, Unicode, unknown terms, unavailable catalogues, bounded lookups, authentication, private-record exclusion, output escaping, frozen application provenance, API page-number handling and incomplete-download rejection. Browser checks verify suggestions in dynamically added rows and visible review statuses.
