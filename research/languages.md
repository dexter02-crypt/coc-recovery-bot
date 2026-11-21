# Language switches, waiting time and bot-language handling

date_checked: 2026-11-22

**No measured cases were found.** The located Clash of Clans reports do not provide both a numerical wait before switching language and a numerical wait afterward. This is a finding about the located evidence, not proof that language never affects routing.

## Located language-switch evidence

| case | date_seen | change described | wait before | wait after | reported result | status | source_url | date_checked |
|---|---|---|---|---|---|---|---|---|
| L01 | 2025-07-14 | Commenter says they changed the game from English to French and used translation. | unconfirmed; no duration supplied | unconfirmed; no duration supplied | Account reportedly unlocked; no complete support transcript or timestamps shown. The comment is dated July 14 under a July 13 post. Direct page retrieval failed; its text was available in indexed extraction. | unconfirmed causal effect/private result; indexed first-person claim observed | https://www.reddit.com/r/ClashOfClans/comments/1lyyc39/ | 2026-11-22 |
| L02, historical advice | 2020-12-29 | A commenter recommends Finnish or Portuguese after an automated rejection. | unconfirmed; no duration supplied | unconfirmed; no duration supplied | Advice only; no personal measured comparison. Outside the 2025-onward window. Direct page retrieval failed; indexed text was readable. | unconfirmed | https://www.reddit.com/r/ClashOfClans/comments/kmda4g/ | 2026-11-22 |
| L03, referenced video | 2025-07-14 | L01's commenter attributes the French suggestion to a YouTube video. | unconfirmed | unconfirmed | No video identifier or inspectable comment thread was supplied in the located text; no separate video case is counted. | unconfirmed | https://www.reddit.com/r/ClashOfClans/comments/1lyyc39/ | 2026-11-22 |

### L01: exact published first-person statement

Source: https://www.reddit.com/r/ClashOfClans/comments/1lyyc39/ ; date_seen: 2025-07-14; date_checked: 2026-11-22; status: unconfirmed private event, observed indexed comment. This is the player's prose, not a support message.

> `I had to change the game language to french to get my account unlocked. English just wasn't working for me. Google translate turned out to be quite useful xD.`

The author later describes the different-language response as more responsive, without quantifying it. No control for a new ticket, elapsed time, different agent or different answers was supplied. Causation and minutes saved remain unconfirmed.

## Non-English answers and English fallback

| question | finding | status | source_url | date_checked |
|---|---|---|---|---|
| Does the recovery bot accept answers written in a non-English language? | The French anecdote reports use of translation but does not show the actual bot prompts and answers. Acceptance rules, supported answer languages and mixed-language handling are not established. | unconfirmed | https://www.reddit.com/r/ClashOfClans/comments/1lyyc39/ | 2026-11-22 |
| Does the recovery bot fall back to English? | No observed recovery dialogue demonstrates that fallback. Official multilingual staff availability is not a bot language-routing specification. | unconfirmed | https://supercell.com/en/parents/ | 2026-11-22 |
| Does a language parameter prove bot fallback? | A third-party API document describes an email-language parameter and an English fallback for unsupported email languages. That concerns outgoing login email, not recovery-chat replies; current service behavior was not tested. | observed code reference; bot implication unconfirmed | https://github.com/ZeroBone/ScidApi/blob/master/APIDoc.MD | 2026-11-22 |
| Does changing device language have the same effect as changing game language? | L01 explicitly describes game language; it provides no device-language comparison. | unconfirmed | https://www.reddit.com/r/ClashOfClans/comments/1lyyc39/ | 2026-11-22 |

## Official availability and unresolved queue claims

| issue | observed evidence or gap | status | source_url | date_checked |
|---|---|---|---|---|
| Support languages | The parent guide describes round-the-clock staff availability in Arabic, both Chinese variants, English, Finnish, French, German, Indonesian, Italian, Japanese, Korean, Portuguese, Russian, Spanish and Turkish. | observed official documentation | https://supercell.com/en/parents/ | 2026-11-22 |
| Best language or measured saving | No numerical before/after comparison was located. Staff-language availability provides no ranking or guaranteed waiting time. | unconfirmed | https://supercell.com/en/parents/ | 2026-11-22 |
| Best hour and timezone | No account-recovery queue measurements by hour or timezone were located. Continuous availability is not a response-time distribution. | unconfirmed | https://supercell.com/en/parents/ | 2026-11-22 |
| Historical English/F2P restriction claim | A 2020 commenter alleges an English-support restriction. The thread provides no primary policy or measured comparison establishing it, and it must not be treated as current routing behavior. | unconfirmed | https://www.reddit.com/r/ClashOfClans/comments/kmda4g/ | 2026-11-22 |
