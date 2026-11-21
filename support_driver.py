"""Prepare an offline worksheet for one owner-operated in-game support ticket.

Exit codes: 0 = complete or forced draft; 1 = required preparation blanks;
2 = malformed input or local I/O error. Importing this module performs no I/O.
"""

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Question:
    id: str
    label: str
    hint: str
    required: bool
    step: int
    source: str


# gap:G01 This is a preparation order, not a verified universal chatbot sequence.
# gap:G19 Public dates cannot establish an exact creation answer.
# gap:G20 Location labels cannot establish the account's origin.
QS = [
    Question("tag", "Player tag", "Copy the exact identifier from the public profile.", True, 1, "official_player_tag"),
    Question("name", "Account name", "Use the current name; keep previous names for corroboration.", True, 2, "official_lost_account"),
    Question("th", "Town Hall level", "Check the current public level.", True, 3, "official_lost_account"),
    Question("clan", "Current clan", "Write none explicitly if the village has no clan.", True, 4, "official_lost_account"),
    Question("email_new", "Replacement email address", "Use an inbox you control that is not linked to another Supercell ID.", True, 5, "official_lost_account"),
    Question("email_code", "Code from the replacement inbox", "Enter the code only in the genuine in-game flow; never write it in this sheet.", True, 6, "G01"),
    Question("date", "Approximate creation date", "Use your own records and label an estimate; public activity gives only an existence bound.", False, 7, "G19"),
    Question("location", "Owner-observed account origin", "Do not copy a ranking location or egress country as creation evidence.", False, 8, "G20"),
    Question("devices", "Devices used", "List devices you personally used; do not infer them from public stats.", False, 9, "G14"),
    Question("receipts", "Purchase references", "Use genuine owner-held receipts when requested; no purchase is an honest answer.", False, 10, "official_lost_account"),
    Question("names", "Previous names", "Distinguish your recollection from recorded public changes.", False, 11, "G16"),
    Question("ap", "Account Protection", "Record yes, no or unknown; keep SMS and recovery codes out of this sheet.", False, 12, "official_account_protection"),
    Question("notes", "Other owner notes", "Include facts you can substantiate; omit passwords and all verification codes.", False, 13, "G14"),
]


def _empty(value):
    return value is None or value == "" or value == 0 or value == []


def _display(value):
    if isinstance(value, list):
        value = "; ".join(str(item) for item in value)
    elif isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return " ".join(str(value).split())


def required_missing(prof):
    return [q.id for q in QS if q.required and q.id != "email_code" and _empty(prof.get(q.id))]


def render(prof, force=False):
    """Render preparation and a manual ladder; never create a ticket or retain a code."""
    missing = required_missing(prof)
    state = "COMPLETE PREPARATION SHEET" if not missing else ("FORCED INCOMPLETE DRAFT" if force else "BLOCKED DRAFT")
    lines = [
        state,
        "Entry path: game Settings > Help and Support > upper-right contact control > account access shown on screen.",
        "Entry source: official_lost_account; select the actual current controls in your game.",
        "Order: unconfirmed (G01). This numbered order is a worksheet, not a transcript of the support assistant.",
        "The support screen outranks this file. Answer only the question it actually asks.",
        "Legend: * required at that stage; ! blank. The inbox code stays blank until entered privately in game.",
        "",
        "NUMBERED SHEET",
    ]
    for question in QS:
        value = prof.get(question.id)
        if question.id == "email_code":
            blank = True
            shown = "[enter privately in game; never save here]"
        else:
            blank = _empty(value)
            shown = "[blank]" if blank else _display(value)
        marks = ("*" if question.required else "") + ("!" if blank else "")
        lines.append("%d. %s %s: %s | %s | source=%s" % (
            question.step, marks or "-", question.label, shown, question.hint, question.source))
    if missing:
        lines.extend(["", "Preparation blanks: " + ", ".join(missing)])
    # gap:G14 Public documentation does not publish the handoff/validation predicate.
    # gap:G05 The 31-day pause is local policy; no helper lock duration is assumed.
    # gap:G09 No measured queue improvement from a language switch is established.
    # gap:G16 Historical public records are incomplete and do not prove ownership.
    lines.extend([
        "",
        "LADDER",
        "1. If you still control the linked email, use the normal Supercell ID sign-in offered by the game. source=official_lost_account",
        "2. If protection is enabled, follow the SMS or recovery-code option shown in the same official flow. source=official_account_protection",
        "3. After reviewing readiness, run attempts.py start once and manually open one in-game support ticket. This command only records your intent locally. source=G14",
        "4. Stay in that ticket. Answer its actual prompts honestly; provide owner-held evidence when requested. No known phrase guarantees a human handoff. source=G14",
        "5. Record the outcome with attempts.py log. If closed, locked or refused, stop; the local cooldown is 31 days. The toolkit never starts another ticket automatically. source=G05",
        "",
        "RULES",
        "The numbered sheet is preparation, not proof of ownership or a verified question order. source=G01",
        "Public names, clan history and dates are public context; do not present them as private owner memories. source=G16",
        "Never fabricate a receipt, device, country, creation date or answer. Missing information remains unknown. source=G14",
        "Keep inbox codes, SMS codes, recovery codes, passwords and API tokens out of the dossier and transcript. source=official_account_protection",
        "No alternate-account ticket loops, duplicate tickets, automated submission or language switching to seek a different result. source=G09",
        "A forced draft does not override a readiness blocker, a cooldown or the single-ticket limit. source=G21",
    ])
    return "\n".join(lines) + "\n"


def write_transcript(prof, path):
    """Write a private local worksheet; unknown extra code/token fields are ignored."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    safe = {q.id: prof.get(q.id) for q in QS if q.id != "email_code"}
    text = render(safe, True) + "\nOWNER RECORD\nTicket reference: [record locally]\nActual support question: [transcribe; omit every code]\nYour factual answer: [record without secrets]\nOutcome: unknown\n"
    fd, temporary = tempfile.mkstemp(prefix=".transcript-", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, str(target))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return str(target.resolve())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--out", "--transcript", dest="transcript")
    args = parser.parse_args(argv)
    from coc_recover import load_profile
    try:
        prof = load_profile(args.profile)
        if args.transcript:
            print(write_transcript(prof, args.transcript))
        else:
            print(render(prof, args.force), end="")
        return 1 if required_missing(prof) and not args.force else 0
    except (OSError, ValueError, TypeError) as exc:
        print("worksheet error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
