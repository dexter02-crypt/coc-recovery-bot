# Account Protection: four questions

date_checked: 2026-11-22

`observed` describes public source content, not independent verification of a player's private account. `unconfirmed` preserves missing evidence. No login POST, address submission, inbox-code request or authenticated account inspection was performed. No credentials are included.

## 1. Does the country restriction block recovery outright, or only SMS?

| issue | finding | status | source_url | date_checked |
|---|---|---|---|---|
| Restricted feature | Protection availability excludes Belarus, Russia, China, Iran, Vietnam, Cuba and North Korea. This is broader than an SMS-delivery statement. | observed | https://sc-clashofclans.zendesk.com/hc/en-us/articles/54567842057755-Account-Protection | 2026-11-22 |
| Receiving SMS | The article separately requires the player to be in a supported region to receive verification messages. | observed | https://sc-clashofclans.zendesk.com/hc/en-us/articles/54567842057755-Account-Protection | 2026-11-22 |
| Every recovery route prohibited by country | A universal recovery prohibition is not established. | unconfirmed | https://sc-clashofclans.zendesk.com/hc/en-us/articles/54567842057755-Account-Protection | 2026-11-22 |
| Existing recovery codes used from an excluded region | This regional scenario is not specified. | unconfirmed | https://sc-clashofclans.zendesk.com/hc/en-us/articles/54567842057755-Account-Protection | 2026-11-22 |

## 2. Is protection status readable before contact?

| proposed method | finding | status | source_url | date_checked |
|---|---|---|---|---|
| Owner's authenticated settings | The in-game Supercell ID settings expose protection activation/reset controls. No owner account was inspected here. | observed documentation | https://sc-clashofclans.zendesk.com/hc/en-us/articles/54567842057755-Account-Protection | 2026-11-22 |
| Public player tag alone | No validated public tag-only protection-status response was located. The documentation URL exposed only an iframe in the text retrieval; its API field list could not be inspected. This does not prove that no endpoint exists. | unconfirmed | https://developer.clashofclans.com/#/documentation | 2026-11-22 |
| Requested email-only POST | Not performed: no owner-controlled test address was supplied; the placeholder is not a valid test account. HTTP status, actual response body, field types and meanings remain unconfirmed. No address was sent and no login-code request was initiated. | unconfirmed | https://ingame.id.supercell.com/api/account/login | 2026-11-22 |
| Public code-reference distinction | A third-party document describes a form-encoded login request, and places `isValid` and `isBound` in a later login-validation response requiring an inbox PIN. It does not document these as Account Protection flags. This is a repository claim, not current official API documentation or a tested service response. | observed code reference; current service behavior unconfirmed | https://github.com/ZeroBone/ScidApi/blob/master/APIDoc.MD | 2026-11-22 |
| Public code-reference limitation | A separate repository labels its response values as placeholders and describes login as sending an inbox PIN. Its descriptions concern Brawl Stars' usage, not a verified Clash of Clans protection lookup. | observed code reference; current service behavior unconfirmed | https://github.com/stealdev/SupercellID-Endpoints | 2026-11-22 |
| Exact live response shape | None observed. No example is presented as a live response, and neither field name alone establishes protection status. | unconfirmed | https://ingame.id.supercell.com/api/account/login | 2026-11-22 |

## 3. Does a protected account skip the questionnaire?

| evidence | finding | status | source_url | date_checked |
|---|---|---|---|---|
| Official recovery article | It distinguishes protected code verification from the unprotected evidence checklist. It does not promise that every preliminary identification question disappears. | observed documentation; universal skip unconfirmed | https://support.supercell.com/clash-of-clans/en/articles/ive-lost-access-to-my-account-2.html | 2026-11-22 |
| AP-C01, 2026-09-16, TH10 | The author says protection was enabled, yet tag, Town Hall, name and clan were requested before a phone/SMS step. The account-recovery outcome was failure at that point. This is a first-person description, not verbatim bot prompts or independent proof of protection status. | unconfirmed private event; indexed first-person report observed | https://www.reddit.com/r/ClashOfClans/comments/1whqgql/supercell_ai_is_so_ducking_useless/ | 2026-11-22 |
| Complete protected-flow transcript | None was observed showing every beginning prompt, every answer and a final result. | unconfirmed | https://www.reddit.com/r/ClashOfClans/comments/1whqgql/supercell_ai_is_so_ducking_useless/ | 2026-11-22 |

## 4. Does losing email, phone and codes end recovery?

| evidence | finding | status | source_url | date_checked |
|---|---|---|---|---|
| Official announcement, published 2022-12-09 | The announcement explicitly warns that losing the registered phone number, registered email and backup recovery code together prevents recovery. Its ending says `you will NOT be able to recover your account.` This is a dated official warning, not an independently tested 2026 case. | observed official warning | https://supercell.com/en/games/clashofclans/blog/news/upcoming-scid-changes/ | 2026-11-22 |
| Directly documented 2025–2026 triple-loss outcome | No located case simultaneously establishes all three losses, a completed official support decision and the eventual outcome. Related reports below do not fill that gap. | unconfirmed | https://supercell.com/en/games/clashofclans/blog/news/upcoming-scid-changes/ | 2026-11-22 |

## Related first-person cases and their limits

| case | date_seen | described access/evidence | reported result | does it establish loss of all three? | status | source_url | date_checked |
|---|---|---|---|---|---|---|---|
| AP-C01 | 2026-09-16 | TH10; original email forgotten; author says protection enabled and phone still available. Tag, level, name, clan and a received SMS code were reportedly entered. | Bot rejected the attempt. The exact pictured rejection text was not readable in the indexed text and is not reconstructed. | No; the phone remained available. | unconfirmed private event; indexed first-person report observed | https://www.reddit.com/r/ClashOfClans/comments/1whqgql/supercell_ai_is_so_ducking_useless/ | 2026-11-22 |
| AP-C02 | 2026-10-05 | Commenter says they enabled protection, retain the linked phone and no longer have a recovery code. Inbox access is unstated. | Repeated automated ownership rejection, with no resolved result visible. This is a comment dated October 5 under a July 20 post. | No; the phone remained available and inbox access is unknown. | unconfirmed private event; indexed comment observed | https://www.reddit.com/r/ClashOfClans/comments/1v19bnb/supercell_support_keeps_rejecting_my_account/ | 2026-11-22 |
| AP-C03 | 2026-06-09 | Author says account email was changed, phone suffix was supplied and recovery codes were retained. | A rate-limit response reportedly appeared before the author could submit further evidence. | No; the codes were retained. | unconfirmed private event; indexed first-person report observed | https://www.reddit.com/r/COC/comments/1u0v3s9/stuck_in_automated_bot_loop_after_account_hack/ | 2026-11-22 |
| AP-C04 | 2025-01-15 | Author says they photographed displayed codes but did not finish enabling protection. | Codes were reportedly invalid; recovery also looped through account-identification/rejection messages. | No; valid completed protection and triple loss are not established. | unconfirmed private event; indexed first-person report observed | https://www.reddit.com/r/ClashOfClans/comments/1i1zdqo/ | 2026-11-22 |
| AP-C05 | 2025-02-08 | Author says they enabled protection through Brawl Stars after the Clash account was already locked. They say codes then failed to help. | Still locked in the visible account of events; no completed controlled comparison. | No; this is activation after a lock, not documented loss of all three factors. | unconfirmed private event; indexed first-person report observed | https://www.reddit.com/r/ClashOfClans/comments/1ikugrn/ | 2026-11-22 |

### Exact support wording available for AP-C03

Source: https://www.reddit.com/r/COC/comments/1u0v3s9/stuck_in_automated_bot_loop_after_account_hack/ ; date_seen: 2026-06-09; date_checked: 2026-11-22; status: unconfirmed as a private exchange, observed as the author's indexed quotation.

> `It seems that you have sent requests through this service too many times in a short period. Please try again later.`

The quotation preserves the author's text. It supplies no exact waiting duration, retry threshold or cause for that particular account.
