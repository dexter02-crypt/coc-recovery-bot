"""Record one owner-controlled ticket and a conservative local waiting interval.

Exit codes: 0 = completed log/list/cooldown/start command; 2 = bad input or I/O.
No ticket is submitted by this module, and importing it performs no I/O.
"""

import argparse
import json
import math
import os
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


OUTCOMES = ("closed", "locked", "refused", "recovered", "abandoned", "unknown")
COSTLY = {"closed", "locked", "refused"}
TERMINAL = set(OUTCOMES) - {"unknown"}
WAIT_DAYS = 31


class AttemptError(ValueError):
    """Local ticket history is invalid or its single-ticket gate is closed."""


def _root():
    return Path(os.environ.get("COC_DATA_DIR", str(Path(__file__).resolve().parent))).expanduser()


def _path():
    return _root() / "attempts.json"


def _when(value):
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, date):
        result = datetime.combine(value, datetime.min.time())
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        result = datetime.fromtimestamp(value, timezone.utc)
    elif isinstance(value, str) and value.strip():
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise AttemptError("missing or malformed timestamp")
    return (result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc))


def _costly_times(entries):
    times = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise AttemptError("ticket history contains a non-object entry")
        if entry.get("outcome") in COSTLY:
            value = next((entry[key] for key in ("at", "date", "time", "timestamp") if key in entry), None)
            try:
                times.append(_when(value))
            except (ValueError, TypeError, OverflowError, OSError) as exc:
                raise AttemptError("costly entry has an invalid timestamp; cooldown is unresolved") from exc
    return times


def remaining_days(entries, now):
    """Ceiling of days until the newest costly event plus 31 days; never negative."""
    # gap:G05 This interval is a local guardrail, not a documented helper-ban rule.
    times = _costly_times(entries)
    if not times:
        return 0
    seconds = (max(times) + timedelta(days=WAIT_DAYS) - _when(now)).total_seconds()
    return max(0, int(math.ceil(seconds / 86400.0)))


def cooldown(entries, now):
    """Return a human-readable waiting status, including unresolved timestamps."""
    try:
        times = _costly_times(entries)
        days = remaining_days(entries, now)
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        return "unresolved: " + str(exc)
    if times and max(times) > _when(now):
        return "unresolved: future costly timestamp; %d days remain to its recorded local expiry" % days
    if not days:
        return "ready: no local cooldown remains; this does not authorize a second ticket"
    return "%d day%s remaining in the local 31-day cooldown" % (days, "" if days == 1 else "s")


def read_entries():
    path = _path()
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise AttemptError("attempts.json must contain an array of objects")
    return value


@contextmanager
def _locked():
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".attempts.lock"
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise AttemptError("ticket history is locked by another operation; inspect the existing lock before retrying") from exc
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def _write(entries):
    path = _path()
    fd, temporary = tempfile.mkstemp(prefix=".attempts-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(entries, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def current_ticket(entries=None):
    entries = read_entries() if entries is None else entries
    starts = [item for item in entries if item.get("event") == "start"]
    if not starts:
        return None
    ticket = starts[-1]
    for item in entries:
        if item.get("ticket_id") == ticket.get("ticket_id") and item.get("outcome") in TERMINAL:
            return None
    return dict(ticket)


def start_ticket(note=""):
    """Mark the owner's one ticket locally; never open or submit a support page."""
    with _locked():
        entries = read_entries()
        recorded = any(item.get("event") == "start" for item in entries)
        now = datetime.now(timezone.utc)
        # The cooldown is evaluated first: when both gates apply, the remaining wait
        # is the actionable fact and the single-ticket wording alone would hide it.
        if remaining_days(entries, now):
            message = cooldown(entries, now)
            if recorded:
                message = ("one ticket is already recorded; " + message +
                           "; this toolkit will not start another")
            raise AttemptError(message)
        if recorded:
            raise AttemptError("one ticket is already recorded in this workspace; this toolkit will not start another")
        entry = {"at": now.isoformat(), "outcome": "unknown", "event": "start",
                 "ticket_id": uuid.uuid4().hex, "note": str(note)}
        entries.append(entry)
        _write(entries)
    return entry


def log(outcome, note=""):
    if outcome not in OUTCOMES:
        raise AttemptError("unknown outcome")
    with _locked():
        entries = read_entries()
        starts = [item for item in entries if item.get("event") == "start"]
        entry = {"at": datetime.now(timezone.utc).isoformat(), "outcome": outcome,
                 "event": "status", "note": str(note)}
        if starts:
            entry["ticket_id"] = starts[-1]["ticket_id"]
        entries.append(entry)
        _write(entries)
    print("recorded: " + outcome)
    return 0


def list_():
    print(json.dumps(read_entries(), ensure_ascii=False, indent=2))
    return 0


def cooldown_cmd():
    print(cooldown(read_entries(), datetime.now(timezone.utc)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    starter = sub.add_parser("start", help="record the one ticket locally; submit it yourself in game")
    starter.add_argument("--note", default="")
    logger = sub.add_parser("log")
    logger.add_argument("outcome", choices=OUTCOMES)
    logger.add_argument("--note", default="")
    sub.add_parser("list")
    sub.add_parser("cooldown")
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            print(json.dumps(start_ticket(args.note), ensure_ascii=False, indent=2))
            return 0
        if args.command == "log":
            return log(args.outcome, args.note)
        if args.command == "list":
            return list_()
        return cooldown_cmd()
    except (OSError, ValueError, TypeError) as exc:
        print("attempt history error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
