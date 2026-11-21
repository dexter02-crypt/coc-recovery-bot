"""Score dossier completeness using public identity and owner-supplied evidence.

Exit codes: 0 = go, 1 = no-go, 2 = configuration, input or local I/O error.
Importing this module performs no file, environment or network reads.
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List


EXCLUDED = {
    "BY": "Belarus",
    "RU": "Russia",
    "CN": "China",
    "IR": "Iran",
    "VN": "Vietnam",
    "CU": "Cuba",
    "KP": "North Korea",
}
STATES = {"pass", "fail", "warn", "skip"}


@dataclass
class Check:
    id: str
    weight: int
    state: str
    detail: str

    def __post_init__(self):
        if self.state not in STATES:
            raise ValueError("invalid check state")
        if not isinstance(self.weight, int) or self.weight < 0:
            raise ValueError("check weight must be a non-negative integer")


@dataclass
class Report:
    score: int
    checks: List[Check]
    blockers: List[str]

    def __post_init__(self):
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")
        if self.blockers or any(c.state == "fail" for c in self.checks):
            self.score = min(self.score, 69)

    @property
    def verdict(self):
        # gap:G21 The 100-point gate is local policy, not a success prediction.
        # The specification's >=70 condition remains necessary; it is not sufficient.
        return "go" if (self.score == 100 and not self.blockers
                        and not any(c.state == "fail" for c in self.checks)) else "no-go"

    def to_dict(self):
        result = asdict(self)
        result["verdict"] = self.verdict
        return result


def _text(value):
    return "" if value is None else str(value).strip()


def _tag(value):
    return _text(value).lstrip("#").upper()


def _clan(value):
    if isinstance(value, dict):
        value = value.get("name", "")
    text = _text(value)
    return "" if text.casefold() in {"none", "no clan", "not in a clan"} else text


def _integer(value):
    try:
        return int(value) if not isinstance(value, bool) else 0
    except (TypeError, ValueError):
        return 0


def _country(value):
    value = _text(value).upper()
    return value if re.fullmatch(r"[A-Z]{2}", value) else ""


def _items(value):
    return [v for v in value if v and _text(v)] if isinstance(value, list) else []


def _decoration_count(prof):
    for key in ("decorations", "markers"):
        if isinstance(prof.get(key), list):
            return len(_items(prof[key]))
    return sum(bool(line.partition(":")[2].strip())
               for line in _text(prof.get("notes")).splitlines()
               if line.strip().casefold().startswith("decoration:"))


def assess(prof, live_fn: Callable, egress_fn: Callable) -> Report:
    """Assess one profile; only injected callbacks can obtain external evidence."""
    prof = dict(prof)
    checks = []
    blockers = []

    def check(id_, weight, state, detail):
        checks.append(Check(id_, weight, state, detail))

    def block(id_, detail):
        check(id_, 0, "fail", detail)
        blockers.append(id_)

    live = None
    if _tag(prof.get("tag")):
        try:
            candidate = live_fn(prof["tag"])
            live = candidate if isinstance(candidate, dict) and candidate else None
        except Exception:
            live = None

    identity_complete = all((_tag(prof.get("tag")), _text(prof.get("name")),
                             _integer(prof.get("th")) > 0, _text(prof.get("clan"))))
    identity_drift = False
    if live is not None:
        comparisons = (
            ("tag_drift", _tag(prof.get("tag")), _tag(live.get("tag")),
             bool(_tag(prof.get("tag"))) and bool(_tag(live.get("tag")))),
            ("name_drift", _text(prof.get("name")), _text(live.get("name")),
             bool(_text(prof.get("name"))) and bool(_text(live.get("name")))),
            ("th_drift", _integer(prof.get("th")), _integer(live.get("townHallLevel")),
             _integer(prof.get("th")) > 0 and _integer(live.get("townHallLevel")) > 0),
            ("clan_drift", _clan(prof.get("clan")), _clan(live.get("clan")),
             bool(_text(prof.get("clan")))),
        )
        for id_, expected, actual, comparable in comparisons:
            if comparable and expected != actual:
                identity_drift = True
                block(id_, "Owner record differs from the current public profile; reconcile the discrepancy.")
        identity_complete = identity_complete and all((
            _tag(live.get("tag")), _text(live.get("name")),
            _integer(live.get("townHallLevel")) > 0))
    identity_ok = live is not None and identity_complete and not identity_drift
    check("identity_match", 25, "pass" if identity_ok else "warn",
          "Public tag, name, Town Hall and clan match; this is not ownership proof."
          if identity_ok else "Complete and reconcile the public identity fields; live evidence is missing or differs.")

    try:
        egress = egress_fn()
    except Exception:
        egress = None
    current = _country(egress.get("country_code") or egress.get("countryCode")) if isinstance(egress, dict) else ""
    declared = _country(prof.get("country_code"))
    # gap:G20 Egress geography is a consistency signal, not creation-country proof.
    egress_ok = bool(current and declared and current == declared)
    check("egress_country", 20, "pass" if egress_ok else "warn",
          "Observed egress country matches the owner's declared country."
          if egress_ok else "Country consistency is unconfirmed or differs; egress does not prove account origin.")
    if current and declared and current != declared:
        block("egress_mismatch", "Observed egress differs from the owner's declared country; reconcile it before contact.")
    # gap:G03 This conservative regional gate is not a universal Supercell recovery ban.
    excluded = sorted({code for code in (current, declared) if code in EXCLUDED})
    if excluded:
        block("excluded_country", "Local regional gate: " + ", ".join(EXCLUDED[c] for c in excluded)
              + ". All recovery routes being barred there is unconfirmed.")

    original = _text(prof.get("email"))
    replacement = _text(prof.get("email_new"))
    valid_email = bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", replacement))
    same_email = bool(original and replacement and original.casefold() == replacement.casefold())
    email_ok = valid_email and not same_email
    check("replacement_email", 15, "pass" if email_ok else "warn",
          "Replacement address is present and differs from the original; inbox access and SCID uniqueness still require owner confirmation."
          if email_ok else "Provide a different replacement address with an inbox you control.")
    if not replacement:
        block("missing_replacement_email", "Replacement email is missing.")
    elif not valid_email:
        block("invalid_replacement_email", "Replacement email has an invalid local format.")
    if same_email:
        block("replacement_equals_original", "Replacement and original email addresses are equal.")

    # gap:G06 No public tag-only Account Protection lookup is established.
    protection = _text(prof.get("ap")).casefold()
    check("protection_known", 15, "pass" if protection in {"yes", "no"} else "warn",
          "Owner has recorded protection status; no public-tag verification was performed."
          if protection in {"yes", "no"} else "Protection status is unknown; check your authenticated settings if accessible.")
    # gap:G18 Receipt presence is scored; authenticity and sufficiency are not inferred.
    receipts = _items(prof.get("receipts"))
    check("receipts", 15, "pass" if receipts else "warn",
          "Owner supplied receipt references; this tool has not validated them."
          if receipts else "No purchase receipts recorded; do not invent purchases or order details.")
    devices = _items(prof.get("devices"))
    check("devices", 10, "pass" if devices else "warn",
          "Owner supplied device history." if devices else "No owner-observed device history recorded.")
    # gap:G10 A lone decoration is not established as accepted ownership evidence.
    if _decoration_count(prof) == 1:
        check("single_decoration", 0, "warn", "Only one decoration is recorded; its dating and acceptance are unconfirmed.")
    score = sum(c.weight for c in checks if c.state == "pass")
    return Report(score, checks, blockers)


def _live_egress():
    import net
    from coc_recover import source_url
    response = net.fetch(source_url("egress_country"), ttl=0)
    if not response.ok:
        return None
    try:
        return json.loads(response.body)
    except (TypeError, ValueError):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    import net
    from coc_recover import load_profile, official
    try:
        net.raise_for_config()
        report = assess(load_profile(args.profile), official, _live_egress)
    except (net.ConfigError, OSError, ValueError, TypeError) as exc:
        if args.json:
            print(json.dumps({"error": "config", "detail": str(exc)}, ensure_ascii=False))
        else:
            print("configuration error: " + str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("%s: %d/100 (local completeness gate)" % (report.verdict, report.score))
        for check in report.checks:
            print("%-4s %-30s %2d  %s" % (check.state, check.id, check.weight, check.detail))
    return 0 if report.verdict == "go" else 1


if __name__ == "__main__":
    sys.exit(main())
