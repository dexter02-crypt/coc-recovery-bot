# Clash of Clans owner dossier toolkit

A Python 3.9+ standard-library toolkit for the legitimate owner to organize public account history, personal evidence and one manual support conversation. It prepares a dossier; it does not establish ownership, recover an account, submit a support ticket or implement an undocumented login service.

The source bundle has 17 files. It contains **21 unresolved research gaps: G01–G17 block an ordinary build; G18–G21 are nonblocking research limitations**. Explicitly packaging those gaps does not resolve them or establish that recovery integrations work. The inherited research inventory has 17 dated public support-quotation records and **zero complete end-to-end transcripts**; the requested minimum of 20 complete transcripts remains unmet.

## First run: validate, build, then create a private working copy

Use Python 3.9 or later. No package installation is needed. In the distribution directory, the required order is:

```bash
python selftest.py
python build.py --allow-gaps
```

Stop if the self-test fails. The build creates `coc-recover.zip` and `MANIFEST.sha256`. The archive is flat: the 17 source/configuration/documentation files plus the generated manifest. `--allow-gaps` permits packaging an explicitly incomplete toolkit. Running `python build.py` without that flag is expected to refuse while G01–G17 remain blocking, before writing or replacing build outputs.

Unpack the archive into a private working directory **after building**, then fill that copy of `profile.json` from your own records. Keep the blank distribution separate. Do not rebuild or share a filled working copy: the archive includes `profile.json` verbatim. Runtime logs, cache databases, extracted account data and manually written transcripts are private working material and are not part of the 17-file distribution.

Configuration and data paths are resolved when a command runs, never during module import. The default data directory is the module directory; `COC_DATA_DIR` can select a separate private data directory. Put the required configuration files there when using that override. The offline self-test uses temporary fixtures and must make no real network calls.

## Fill the profile honestly

| Field | Value to record | Important limit |
|---|---|---|
| `tag` | Your exact player tag, with or without the leading hash. | A tag identifies a public account; it does not prove ownership. |
| `name`, `th`, `xp` | Current account name, Town Hall level and experience level. | Template empty strings mean unfilled. Reconcile changes against the current public profile. |
| `clan` | Current clan name; write `none` explicitly when unclanned. | Blank means unknown, not unclanned. A clan change is a discrepancy to explain, not proof of wrongdoing. |
| `date` | Your own supported creation-date estimate, if known. | State uncertainty in notes. Do not substitute a feature-release date or earliest tracker entry. |
| `devices` | A JSON list of devices you personally used. | Do not infer private device history from public account data. |
| `location` | Your own recollection or record of account origin, if known. | Label recollection versus documentary evidence. |
| `country_code` | The two-letter country you intend to use for the current consistency check. | This is compared with present egress geolocation; it is not automatically creation country. |
| `email` | The original/linked address you know, if available. | Keep it private. A blank or masked address is not evidence that another address is different. |
| `email_new` | A different inbox you control and have checked is not already linked to another Supercell ID. | Syntax checks cannot verify delivery, inbox control or existing linkage. |
| `ap` | `yes`, `no`, or blank/`unknown`. | The template uses `unknown`; blank owner input is normalized to unknown. Check authenticated owner settings if accessible; there is no verified public tag-only lookup. |
| `receipts` | A list of references to genuine receipts you possess. | Presence is scored; authenticity, matching and acceptance are not verified. No purchases is an honest answer. |
| `names` | A list of earlier names, with provenance in notes. | Separate your recollection from public history. |
| `notes` | Factual context, evidence dates and uncertainties. | Never put passwords, API tokens, email codes, SMS codes or recovery codes here. |

For the optional single-decoration warning, put one owner-observed item on each separate notes line using `decoration: item name`. A single nonblank line triggers a warning. The name does not validate a release date or prove support will accept it. The shipped `obstacles.json` has empty `markers` and `structural` arrays because no release dates were admitted with adequate primary-source verification; G10 and G11 remain open.

## Public-data workflow

Live official-profile commands need **both** `COC_API_BASE` and `COC_API_TOKEN` set privately in the shell. Copy the base from the `official_api` entry in `sources.json`; do not put a token in that file, the profile, a transcript or a command argument. An authenticated API token is optional for preparing the offline worksheet and required for the CLI's live profile/readiness checks. No private Supercell ID endpoint is supplied.

Once the offline self-test has passed, optional public-data commands are:

```bash
python coc.py report '#YOUR_TAG'
python probe.py '#YOUR_TAG'
python scrape.py '#YOUR_TAG'
python readiness.py --json
python support_driver.py --out transcript.md
```

Replace `#YOUR_TAG` with your own tag. `report` collects public records, writes `dossier.json` and `dossier.md`, and fills only empty public identity fields in the profile; review those values yourself. Its `--open` flag opens the local Markdown dossier. `probe` records one unauthenticated observation per registered path in `probe_results.csv`, without following redirects or bypassing access gates. Its `--strict` mode exits 1 if any source is marked `unverified`; it is not a guarantee that every route works. `--write-sources` writes a separate `sources.live.json` containing usable paths while preserving existing flags and verification claims. `scrape` uses that derived registry when present, skips login/JavaScript/blocked sources, and writes `external.json`; an empty result can still exit successfully and does not prove there is no history. Use probe observations to inspect access limits. `readiness` compares the owner record with available live public identity and current egress-country evidence. The worksheet command writes local text only.

Every network request is centralized in `net.fetch`. Public safe GET/HEAD requests can use the TTL cache keyed by method, URL and body. Authenticated requests and methods other than GET/HEAD bypass the shared cache. POSTs are not retried. Retries are limited to transport failures/status 0 and HTTP 429, 502, 503 and 504 for safe requests; other statuses are returned. Actual attempts are spaced at least 0.4 seconds apart. Redirects are disabled. An inaccessible page is not permission to evade its gate, and a sampled 404 or 503 does not establish that an entire service is permanently unavailable.

Source addresses live in `sources.json`, apart from declared official API-base constants in `net.py`. Named references in these documents resolve through that registry. `%TAG%` means the normalized tag without its leading hash; a path containing `%23%TAG%` supplies the hash encoding itself. The source `date_checked` records the saved research check, not a new probe or a guarantee of availability today. A documented route, a working page, a login gate and a verified payload are different observations.

ClashKing JSON extraction maps are **candidate dotted field paths** and carry `schema_verified: false`; wildcard paths support nested lists. The saved evidence does not validate every candidate field or full history coverage. Preserve source, route, retrieval time, observation time and uncertainty when using extracted facts. A month/season label must not silently become an exact day.

## Readiness policy and its limits

| Category | Weight | What a pass means locally |
|---|---:|---|
| Identity | 25 | Current public tag/name/Town Hall/clan reconcile with the owner record. |
| Egress country | 20 | Current geolocation country matches the declared consistency country. |
| Replacement email | 15 | An address with plausible local syntax is present and differs from the recorded original. |
| Protection knowledge | 15 | The owner has recorded `yes` or `no`; no public verification is implied. |
| Receipts | 15 | At least one owner-supplied receipt reference is present. |
| Devices | 10 | At least one owner-supplied device entry is present. |

The specification contains two thresholds: at least 70 with no failures, and a test requiring `go` only at 100 with no failures. This toolkit takes the conservative local interpretation: **`go` requires 100/100 and no failed check**. Seventy is necessary but insufficient. Any failure also caps the displayed score at 69. These weights, thresholds and caps are local policy, not a Supercell score, success probability or published recovery requirement (G21).

Zero-weight failure checks independently stop readiness when current identity drifts, egress differs, the replacement address is absent/invalid/equal to the recorded original, or an excluded country is detected. Unknown protection status, no receipts, no devices and a single recorded decoration remain warnings. Warnings that lose weighted points still prevent reaching the local 100-point gate. A legitimate owner who never purchased anything can therefore receive `no-go`; do not invent a receipt to change that result.

The excluded-country check applies the local conservative gate to Belarus, Russia, China, Iran, Vietnam, Cuba and North Korea, based on the documented Account Protection availability list. **It is not a universal claim that every recovery route is unavailable in those countries** (G03). Egress and ranking locations do not prove account origin (G20). Reconcile discrepancies honestly; the tool supplies no routing or region bypass.

Exit codes for `readiness.py` are 0 for local `go`, 1 for `no-go`, and 2 for a configuration/input/I/O error. A 100-point result establishes preparation completeness under this implementation, not original ownership or permission to skip the genuine support checks.

## One manual support conversation

Read the worksheet before opening support. Its numbered order is an organization aid; the current live in-game screen outranks it. Use the official owner-facing sign-in or Account Protection route when available. If support is needed, open it through the current game settings and help controls described by `official_lost_account`.

When you actually decide to begin the single owner-operated conversation, record that decision locally:

```bash
python attempts.py start --note 'Owner beginning one manual in-game conversation'
```

This command does not contact Supercell. Stay in that conversation and answer only its actual prompts with facts you can substantiate. Keep inbox/SMS/recovery codes in the genuine in-game flow; the worksheet intentionally leaves its code slot blank and does not store a supplied `email_code` field.

Record the actual outcome afterward, for example:

```bash
python attempts.py log closed --note 'Conversation closed; reason recorded privately without secrets'
python attempts.py cooldown
python attempts.py list
```

Allowed outcomes are `closed`, `locked`, `refused`, `recovered`, `abandoned` and `unknown`. Closed/locked/refused outcomes trigger a **local 31-day pause**, not a claimed Supercell rule. A 30-day report is not silently converted to 31 days, and disciplinary suspensions are not described as security locks. Generating a dossier or worksheet does not start the pause. Only one `start` is allowed in a workspace, and expiry does not authorize a second ticket. Do not delete or reset the history to manufacture permission for repeated contacts.

`support_driver.py --force` prints an explicitly incomplete preview; it does not override readiness, clear a cooldown, submit a ticket or turn a blank into an answer. `--out` writes a private worksheet/record template; `--transcript` is its alias. The generated text is not a transcript of a conversation that happened. The tool does not verify that a claimed agent is human or guarantee a handoff.

The `scid` and `verify` helpers are fail-closed manual guidance until supported endpoints, token types and response meaning are documented (G12/G17). Do not supply an inbox code to a CLI. The local `takeout` helper inventories owner-provided export metadata only; it does not obtain an export from an account. No Frida offsets or private endpoint guesses are included (G13).

## Dating: preserve what the evidence can actually say

Combine independently justified creation lower bounds using the latest bound (`max` of floors), and creation upper bounds using the earliest (`min` of ceilings). Reject a lower bound later than the upper bound. Retain precision: a year or month should remain a range, not silently become a day.

A dated attack, clan membership event, receipt or screenshot can establish that the account existed **by** that observation. It does not prove the account was created then. A feature's release date does not establish when an older account began. Earliest known history is not necessarily first-ever history, and the absence of an old decoration or tracker row is not proof the account did not exist.

## Proven versus assumed

Every unresolved gap appears below and in `gaps.csv`. “Blocking” controls ordinary packaging; a nonblocking gap still limits interpretation.

| Gap | Established basis | What remains assumed or unknown | Blocking |
|---|---|---|---|
| G01 | Official articles describe a preparation route; fragments were located. | Exact current question order, branches and 20 complete transcripts. | yes |
| G02 | Public failure reports mention spending and receipts. | A spending threshold or privileged support queue. | yes |
| G03 | Official documentation limits Account Protection availability. | Eligibility and code behavior across every recovery route by country. | yes |
| G04 | The former maintainer identifies an FWA successor index. | A current observed per-player result route behind the access denial. | yes |
| G05 | Reports distinguish security locks and disciplinary penalties. | A universal helper penalty, fixed 31-day lock or official cooldown. | yes |
| G06 | Authenticated owner settings describe protection controls. | A public tag-only protection-status API. | yes |
| G07 | Historical GFL-related service references exist. | A current verified GFL-specific tracker and player payload. | yes |
| G08 | Farm-war FWL is mentioned in a community listing. | A current verified FWL-specific tracker, without acronym substitution. | yes |
| G09 | Official support offers multiple languages. | A measured faster language or shorter-queue hour. | yes |
| G10 | Owners may record decorations they personally observe. | A sourced date catalogue and support acceptance of that evidence. | yes |
| G11 | Structural releases and account observations are distinct events. | A sourced structural catalogue or valid creation inference from it. | yes |
| G12 | An in-game token is conceptually distinct from an inbox code. | A documented permitted verification endpoint and schema. | yes |
| G13 | No supported instrumentation is implemented. | Any verified need, build offsets or permitted integration. | yes |
| G14 | A public comment quotes part of an agent-assignment message. | Actual universal handoff criteria or whether assignment completed. | yes |
| G15 | Public not-found/rejection wording was quoted. | The private lookup, rejection or closure predicate. | yes |
| G16 | Routes and a limited sample response are recorded. | Complete historical coverage, pagination and every live JSON schema. | yes |
| G17 | Official owner-facing recovery routes exist. | A supported private Supercell ID API usable by this toolkit. | yes |
| G18 | The local score counts receipt references. | Authenticity, support acceptance and predictive receipt weight. | no |
| G19 | Activity supplies an existence upper bound. | A validated creation estimate from sparse observations. | no |
| G20 | Current egress and ranking locations can be observed. | Their equivalence to the account-creation location. | no |
| G21 | Weights and the 100/no-fail rule are explicit local policy. | Empirical calibration or any Supercell endorsement. | no |

## File map and verification scope

| File | Responsibility |
|---|---|
| `net.py` | Lazy configuration, centralized HTTP, safe retry/spacing behavior and SQLite TTL cache. |
| `coc.py` | Public report and local dossier CLI; fail-closed helper entry points. |
| `coc_recover.py` | Lazy profile/source loading and shared preparation helpers. |
| `readiness.py` | Weighted completeness checks and independent blockers. |
| `support_driver.py` | Offline manual worksheet and single-conversation guidance. |
| `attempts.py` | Durable local attempt/outcome record and cooldown display. |
| `probe.py` | Permitted public-source reachability observations. |
| `scrape.py` | Public HTML/JSON extraction with source and coverage limits. |
| `selftest.py` | Offline tests for imports, parsers, scoring, cooldowns, schemas, build gates and URL centralization. |
| `build.py` | Flat deterministic archive and checksum manifest; rejects blocking gaps by default. |
| `sources.json` | URL registry, access observations and explicitly qualified extraction candidates. |
| `obstacles.json` | Empty pending verified marker/structural dates; no fictional chronology. |
| `profile.json` | Blank private owner-input template. |
| `gaps.csv` | Complete unresolved research register. |
| `README.md` | Operation, contracts and policy limits. |
| `report.md` | Evidence-based confirmed, unconfirmed and failure-mode tables. |
| `research_prompt.md` | Reusable instructions for closing the research gaps honestly. |

The delivered revision passed **149 offline checks** on Python 3.12.14. The suite also parses every module using the Python 3.9 grammar; a native Python 3.9 interpreter was unavailable in the build environment. See the Offline verification table in `report.md` for the observed commands and limits. Passing fixtures does not verify an authenticated API response, a blocked tracker, support-question order, recovery eligibility or account ownership. No account recovery or ticket submission is part of the test suite.
