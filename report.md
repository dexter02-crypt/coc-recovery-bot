# Research and implementation report

Evidence review date: **2026-11-22**, inherited from the saved research records. The toolkit's packaging step did not re-run account recovery or authenticate to an owner account. `egress_country` additionally has an integration-owner check of the primary API documentation on that date. Source publication dates and source access dates are distinct; an undated article does not acquire a publication date from this review date.

Each research-table row below contains one named reference resolved by `sources.json`. The final verification table cites the local file that owns each check. A reference can establish that a document or public report exists without authenticating the private event it describes. Documentation, reported outcomes, route observations, local implementation choices and unknown internal rules must remain separate.

The prior corpus contains **17 distinct dated public support-quotation records and zero complete end-to-end support transcripts**. Fragments, closing messages and UI errors are not silently counted as complete transcripts. The requested minimum of 20 complete transcripts remains unmet (G01). No inaccessible screenshot was reconstructed and no account ownership, receipt authenticity or private support decision was independently established.

## Confirmed

“Confirmed” here is limited to the stated public observation. It does not mean a recovery was attempted or an account was verified.

| Observation | What the evidence supports | Limit | Source |
|---|---|---|---|
| Official lost-account guidance was readable through public search extraction. | Owner-facing sign-in, Account Protection and in-game support routes; preparation of account identification and purchase references. | The article is not a current ordered chatbot transcript; its revision date was not observed. | `official_lost_account` |
| Official tag guidance describes locating the player identifier. | A tag helps identify the account. | A tag alone does not prove ownership. | `official_player_tag` |
| The official account index groups account/security help. | Navigation to relevant articles. | It does not publish the recovery decision tree. | `official_account_index` |
| Account Protection documentation describes phone/recovery-code verification and authenticated settings. | The feature is unavailable in the seven countries named in the article. | This does not establish that every recovery route is barred there. | `official_account_protection` |
| The protection announcement is dated 2022-12-09. | A historical official warning addresses losing phone, email and recovery codes together. | It is not a newly dated 2026 policy test or a region-specific observation. | `official_ap_announcement` |
| Official safety guidance tells the actual player to contact support. | Recovering another player's account is described as phishing. | No universal fixed helper-account penalty duration is specified. | `official_keep_safe` |
| Official penalty guidance discusses severity and repetition. | Penalties are not described as having one universal duration. | Internal recovery thresholds are not disclosed. | `official_penalties` |
| The prior ClashKing sample returned an encoded-tag war/attacks response with one defense. | That specific public request supplied recorded war data; several related routes appeared in OpenAPI. | Complete history, every route and every extraction field were not validated. | `clashking` |
| The former ChocolateClash host displayed its retirement/migration notice. | It names the FWA-hosted successor and gives a 2025-01-01 shutdown date. | The partly undated non-FWA update does not validate a GFL or FWL successor. | `chocolateclash_notice` |
| The FWA successor loaded an access-denied page before lookup. | The saved attempt reached a gate. | No search was submitted and no player-result address was obtained. | `fwacc` |
| FWA Stats redirected its Players entry to a login form. | That entry requires authentication in the observed flow. | It is not a verified individual-player pattern or proof of a successor relationship. | `fwastats` |
| War Report's publisher documents player pages and war-history features. | The route pattern is documented and the app requires JavaScript. | A sampled player fetch returned 404; a live result was not validated. | `warreport` |
| Official support material describes multilingual availability. | Multiple support languages are offered. | Availability is not a measured queue length or speed advantage. | `official_parents` |
| Primary IP-geolocation documentation describes a JSON country_code field. | The documented field can supply the local current-country comparison. | Current egress is not the account's creation country. | `egress_country` |

## Unconfirmed

Every row is explicitly **unconfirmed**. The local implementation must not turn these open questions into asserted service behavior.

| Gap | Unconfirmed claim or missing evidence | Consequence for the toolkit | Source |
|---|---|---|---|
| G01 | **unconfirmed** — Exact current prompt sequence, branches, retries and a corpus of 20 complete dated transcripts. | Numbering is worksheet order only; the live screen takes precedence. | `official_lost_account` |
| G02 | **unconfirmed** — A spend threshold, privileged queue or purchase amount that improves routing. | No spending recommendation or guaranteed human access. | `q_spend` |
| G03 | **unconfirmed** — Universal regional recovery exclusions or behavior of existing codes from restricted regions. | The excluded-country readiness rule is a conservative local stop. | `official_account_protection` |
| G04 | **unconfirmed** — Exact current successor player endpoint and payload. | Keep the known index only; do not fabricate PHP routes or bypass access denial. | `fwacc` |
| G05 | **unconfirmed** — Fixed 31-day security locks, universal 30/31-day helper penalties or an official 31-day cooldown. | Preserve reported durations and penalty types; the 31-day pause is local policy. | `official_penalties` |
| G06 | **unconfirmed** — A public tag-only Account Protection lookup. | Use owner-recorded status from authenticated settings when available. | `official_account_protection` |
| G07 | **unconfirmed** — A current GFL-specific tracker successor and live player record. | State no verified successor found within the located evidence. | `gfl_historical_listing` |
| G08 | **unconfirmed** — A current farm-war FWL tracker successor. | Do not substitute another league merely sharing the initials. | `fwl_community_listing` |
| G09 | **unconfirmed** — A faster support language or best hour established by measured recent comparisons. | No language-switch or timing trick is recommended. | `official_parents` |
| G10 | **unconfirmed** — A primary-verified marker catalogue and support's acceptance of decorations as ownership evidence. | The shipped marker array remains empty; a single decoration produces only a warning. | `official_lost_account` |
| G11 | **unconfirmed** — A primary-verified structural date catalogue or creation-date inference from Town Hall eras. | The structural array remains empty; feature release is not a creation lower bound. | `official_lost_account` |
| G12 | **unconfirmed** — Supported verification-token endpoint, request schema and response meaning. | `verify` remains manual-only and makes no guessed request. | `official_api` |
| G13 | **unconfirmed** — Any required client instrumentation, valid Frida offsets or supported offset-based workflow. | No instrumentation is implemented; prefer documented owner routes. | `official_account_index` |
| G14 | **unconfirmed** — Human-handoff predicate or completed assignment after a quoted promise. | No phrase, sequence or worksheet completion guarantees a person will take over. | `q_handoff` |
| G15 | **unconfirmed** — The private account-not-found, rejection or closure predicate. | Record messages without inventing a mismatch rule or score. | `q_rejection` |
| G16 | **unconfirmed** — Full historical coverage, pagination and every current tracker schema. | Extraction maps remain qualified candidates and findings retain provenance. | `clashking` |
| G17 | **unconfirmed** — A publicly supported Supercell ID private API for this workflow. | `scid` remains manual guidance; no login or inbox-code request is automated. | `official_lost_account` |
| G18 | **unconfirmed** — Receipt authenticity, acceptance or a calibrated outcome benefit from the local receipt weight. | Genuine references are preparation evidence, not a success guarantee. | `q_receipt_rejection` |
| G19 | **unconfirmed** — A calibrated creation-date estimate from sparse public observations. | Use justified bounds, retain date precision and reject contradictions. | `clashking` |
| G20 | **unconfirmed** — Equivalence of egress, ranking country and original account location. | Compare like signals and do not label geolocation as origin proof. | `egress_country` |
| G21 | **unconfirmed** — A connection between the local score and Supercell's private checks or recovery success. | The 100/no-fail decision is local completeness policy only. | `official_lost_account` |

## Failure modes

Public anecdotes below establish what an author reported, not why support decided as it did. They cannot establish prevalence or a universal penalty. Implementation rows describe defensive behavior rather than claiming those failures occurred in a live account.

| Failure or confusion | Evidence or concrete risk | Required handling | Source |
|---|---|---|---|
| Repeated automated rejection despite reported spending/receipts. | A dated author report describes substantial spending and failed recovery; private evidence validity is unknown. | Do not promise success from spending or recommend additional purchases. | `q_spend` |
| Rate-limit wording after repeated service requests. | A public author quotes a too-many-requests message; its threshold/window is unknown. | Stop repeated contact, record the observed wording and preserve the local attempt log. | `q_rate_limit` |
| A disciplinary ban mislabeled as a timed security lock. | One author reports 31 days for account sharing, followed by a permanent suspension. | Preserve type, duration and attribution; do not infer VPN causation or a universal lock. | `q_ban31` |
| Temporary rejection mistaken for a universal waiting rule. | One edited report says recovery later succeeded after about 24 hours. | Do not generalize that elapsed time into a guaranteed cooldown. | `q_lock_recovered` |
| Receipt submission treated as accepted ownership proof. | An author reports an Apple receipt followed by rejection; matching and authenticity were not verified. | Keep receipt provenance private and leave acceptance unknown. | `q_receipt_rejection` |
| Support impersonation presented as an official recovery path. | A thread's author later acknowledged apparent impersonation involving other members' recovery codes. | Exclude the alleged procedure from official instructions; never collect another person's codes. | `q_phishing_incident` |
| Old helper-account reports presented as current policy. | A 2021 author describes a 31-day ban after trying to recover a friend's account. | Keep its historical date and require the actual owner to contact support. | `q_helper_historical` |
| Guessed legacy player URLs treated as verified. | The known successor blocked access before a lookup could produce a result address. | Preserve G04, register only the observed index and do not bypass the gate. | `fwacc` |
| JavaScript or login gates treated as absent history. | The observed Players route redirects to authentication. | Record access limits without inferring the account has no records. | `fwastats` |
| Shared-cache leakage or request replay. | The official API uses credentials, while an unscoped cache tuple does not contain credential identity. | Bypass shared caching for authenticated requests or methods other than GET/HEAD; never retry POST; never log secrets. | `official_api` |
| Egress treated as historical origin or a region-bypass target. | The country field describes the present request's geolocation. | Keep current-country consistency separate from owner origin and reconcile differences honestly. | `egress_country` |
| Public observation transformed into a fabricated creation date. | A tracker can record activity after its own collection starts. | Activity provides only an existence upper bound; preserve gaps and source times. | `clashking` |

## Delivery and evidence boundary

The 17-file source contract is implemented as a flat package. `build.py` generates an additional checksum manifest and archive. Default packaging remains blocked by the 17 blocking research gaps; `--allow-gaps` is an explicit packaging override, not research completion or endpoint verification. Runtime data and private owner evidence do not belong in the shared distribution.

The readiness categories total 100 points: identity 25, current-country consistency 20, replacement email 15, protection knowledge 15, receipts 15 and devices 10. The conservative `go` rule is 100 with no failures; zero-weight blockers operate independently. Missing receipts/devices/protection knowledge remain warnings even when their missing weight prevents local `go`. The 31-day pause, single-ticket rule and excluded-country readiness stop are local safeguards.

## Offline verification

Checks performed on **2026-11-22**. The initial suite passed 143 checks; focused regression coverage for review findings increased the final suite to 149. No live source fetching, authenticated API request or support conversation was executed as part of this build.

| Check | Observed result | Scope and limit | Source |
|---|---|---|---|
| `python selftest.py` | Exit 0; `PASS 149 offline checks; network disabled; no token used`. | Python 3.12.14 runtime. Every module also parses under the Python 3.9 grammar; a native 3.9 interpreter was unavailable. | `selftest.py` |
| Independent imports and HTTP boundary | Ten modules imported independently without operational I/O; mocked cache, TTL, retry, pacing and response-classification checks passed. | Fixtures establish local behavior; they do not validate live service availability. | `selftest.py` |
| Readiness and one-ticket behavior | All weighted checks, zero-weight blockers, 100/no-failure gate, cooldown arithmetic and duplicate-start refusal passed. | The score and waiting interval remain local policies. | `selftest.py` |
| Source and evidence integrity | Source/schema checks, gap identifiers, URL centralization, profile-tag consistency, provenance and extraction checks passed. | Unknown endpoint semantics and history coverage remain G16. | `selftest.py` |
| Default build refusal | Missing-source and blocking-gap fixtures refused before creating outputs. | An ordinary build remains blocked by G01–G17. | `selftest.py` |
| `python build.py --allow-gaps` | Exit 0; flat archive and external checksum manifest created. | Archive contains the 17 requested source files plus `MANIFEST.sha256`; the override permits packaging only. | `build.py` |

A passing offline suite does not validate an external endpoint or a recovery result. No automatic support submission, private-endpoint probing, code collection or account recovery is part of the deliverable.
