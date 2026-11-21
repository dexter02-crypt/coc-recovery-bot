"""Dossier and local evidence helpers. Exit codes: 0 success, 1 no-go, 2 configuration.

Import is inert. Live CLI commands are dispatched by coc.py. Public records are
corroboration, never proof that the person running this program owns a village.
All HTTP leaves through net.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

import net

TEMPLATE = {"tag": "", "name": "", "th": "", "xp": "", "clan": "", "date": "",
            "devices": [], "location": "", "country_code": "", "email": "",
            "email_new": "", "ap": "unknown", "receipts": [], "names": [], "notes": ""}
SOURCE_METHODS = {"browser-loads", "browser-403", "docs-page",
                  "github-code-reference", "unverified"}
COC = "magic"
SCID_GAMES = {"magic": "Clash of Clans", "scroll": "Clash Royale",
              "laser": "Brawl Stars", "soil": "Hay Day", "reef": "Boom Beach"}


def data_dir() -> Path:
    return Path(os.environ.get("COC_DATA_DIR", str(Path(__file__).resolve().parent))).expanduser()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def atomic_write(path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=str(path.parent), delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(str(temporary), str(path))
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def save_json(path, value) -> None:
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def normalize_tag(tag) -> str:
    value = str(tag or "").strip().lstrip("#").upper()
    if not re.fullmatch(r"[A-Z0-9]{3,15}", value):
        raise ValueError("A player tag must contain 3 to 15 letters/digits, with optional #")
    return "#" + value


def load_profile(path=None) -> dict:
    target = Path(path) if path is not None else data_dir() / "profile.json"
    with target.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise net.ConfigError("profile.json must contain an object")
    result = copy.deepcopy(TEMPLATE)
    result.update(value)
    if result.get("ap") in (None, ""):
        result["ap"] = "unknown"
    if result.get("ap") not in {"yes", "no", "unknown"}:
        raise net.ConfigError("profile.ap must be yes, no or unknown")
    for key in ("devices", "receipts", "names"):
        if not isinstance(result.get(key), list):
            raise net.ConfigError("profile.%s must be an array" % key)
    return result


def save_profile(prof, path=None) -> None:
    save_json(Path(path) if path is not None else data_dir() / "profile.json", prof)


def load_sources(path=None) -> dict:
    """Load the registry; a bare array is accepted as shorthand for {"sources": [...]}."""
    target = Path(path) if path is not None else data_dir() / "sources.json"
    with target.open(encoding="utf-8") as stream:
        config = json.load(stream)
    if isinstance(config, list):
        config = {"sources": config}
    if not isinstance(config, dict) or not isinstance(config.get("sources"), list):
        raise net.ConfigError("sources.json requires a sources array")
    seen = set()
    for source in config["sources"]:
        if not isinstance(source, dict):
            raise net.ConfigError("Incomplete source entry")
        source.setdefault("markers", [])
        required = {"name", "base", "paths", "markers", "verified_how", "date_checked"}
        if not required <= set(source):
            raise net.ConfigError("Incomplete source entry")
        name = source["name"]
        if not isinstance(name, str) or not name or name in seen:
            raise net.ConfigError("Source names must be nonempty and unique")
        seen.add(name)
        net.validate_url(source["base"])
        if source["verified_how"] not in SOURCE_METHODS:
            raise net.ConfigError("Invalid source verification method")
        try:
            dt.date.fromisoformat(source["date_checked"])
        except (TypeError, ValueError):
            raise net.ConfigError("Source date_checked must be an ISO date")
        for key in ("paths", "markers"):
            if not isinstance(source[key], list) or not all(isinstance(v, str) for v in source[key]):
                raise net.ConfigError("Source paths and markers must be string arrays")
        for path_value in source["paths"]:
            if path_value and not path_value.startswith("/"):
                raise net.ConfigError("Source paths must be relative to their declared base")
        for flag in ("json", "js", "auth", "blocked"):
            if flag in source and not isinstance(source[flag], bool):
                raise net.ConfigError("Source flags must be boolean")
    return config


def get_source(name, config=None) -> dict:
    for source in (config if config is not None else load_sources())["sources"]:
        if source["name"] == name:
            return source
    raise net.ConfigError("Missing source: " + str(name))


def _relative(source, path_index=0, **values) -> str:
    """Expand placeholders into a base-relative path, refusing unfilled ones."""
    paths = source.get("paths") or []
    if path_index < 0 or path_index >= len(paths):
        raise net.ConfigError("Source has no requested path")
    path = paths[path_index]
    for key, value in values.items():
        path = path.replace("%" + str(key).upper() + "%", net.quote(value))
    if re.search(r"%[A-Z_]+%", path):
        raise net.ConfigError("Unfilled source URL placeholder")
    return path


def expand_source(source, path_index=0, **values) -> str:
    return net.validate_url(source["base"].rstrip("/") + _relative(source, path_index, **values))


def source_url(name, path_index=0, **values) -> str:
    return expand_source(get_source(name), path_index, **values)


def _json_response(response) -> Optional[dict]:
    if not response.ok:
        return None
    try:
        obj = json.loads(response.body)
    except (TypeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def official(tag) -> Optional[dict]:
    """Read the configured official API, or return None for unavailable evidence."""
    base = os.environ.get("COC_API_BASE", "").strip().rstrip("/")
    token = os.environ.get("COC_API_TOKEN", "").strip()
    if not base or not token:
        return None
    source = get_source("official_api")
    configured = dict(source, base=base)
    requested_tag = normalize_tag(tag)
    url = expand_source(configured, TAG=requested_tag[1:])
    payload = _json_response(net.fetch(url, headers={"Authorization": "Bearer " + token}, ttl=0))
    try:
        matches = payload is not None and normalize_tag(payload.get("tag")) == requested_tag
    except ValueError:
        matches = False
    return payload if matches else None


def ck(tag, path, **q) -> Optional[dict]:
    """Read one registered history route, failing over where an official route exists."""
    source = get_source("clashking")
    suffix = "/" + str(path).strip("/")
    index = next((i for i, p in enumerate(source["paths"]) if p.endswith(suffix)), None)
    if index is None:
        # gap:G16 New history routes need documented coverage and schema.
        raise net.ConfigError("ClashKing path is not registered in sources.json")
    relative = net.add_query(_relative(source, index, TAG=normalize_tag(tag)[1:]), q)
    token = os.environ.get("COC_API_TOKEN", "").strip()
    status, payload = net.api_get(relative, token, base=source["base"])
    if status and not 200 <= status < 300:
        return None
    return payload if isinstance(payload, dict) else None


def parse_changes(items) -> list[dict]:
    out = []
    for row in items if isinstance(items, list) else []:
        if not isinstance(row, dict):
            continue
        item = row.get("item") if isinstance(row.get("item"), dict) else {}
        current = row.get("current")
        previous = row.get("previous")
        value = item.get("name")
        if not isinstance(value, str):
            value = current if isinstance(current, str) else ""
        out.append({"time": str(row.get("time") or ""), "type": str(row.get("type") or ""),
                    "value": value,
                    "previous": previous if isinstance(previous, (str, bool)) else None,
                    "current": current if isinstance(current, (str, bool)) else None})
    return out


def parse_war(items) -> list[dict]:
    out = []
    for row in items if isinstance(items, list) else []:
        if not isinstance(row, dict):
            continue
        stars = row.get("stars")
        destruction = row.get("destructionPercentage")
        out.append({"warEndTime": str(row.get("warEndTime") or ""),
                    "defendingClanTag": row.get("defendingClanTag")
                    if isinstance(row.get("defendingClanTag"), str) else None,
                    "stars": stars if type(stars) is int and 0 <= stars <= 3 else None,
                    "destructionPercentage": destruction
                    if type(destruction) in (int, float) and 0 <= destruction <= 100 else None})
    return out


def _as_date(value) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    if re.fullmatch(r"\d{8}T\d{6}(?:\.\d+)?Z", text):
        return dt.datetime.strptime(text[:8], "%Y%m%d").date()
    return dt.date.fromisoformat(text[:10])


def bracket(floors, ceils) -> tuple[Optional[str], Optional[str]]:
    """Intersect inclusive calendar-date bounds; reject contradictory evidence."""
    lower = [_as_date(value) for value in floors if value not in (None, "")]
    upper = [_as_date(value) for value in ceils if value not in (None, "")]
    floor = max(lower) if lower else None
    ceiling = min(upper) if upper else None
    if floor and ceiling and floor > ceiling:
        raise ValueError("Contradictory date bounds: lower exceeds upper")
    return floor.isoformat() if floor else None, ceiling.isoformat() if ceiling else None


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.suppressed += 1
        elif not self.suppressed:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.suppressed:
            self.suppressed -= 1
        elif not self.suppressed:
            self.parts.append("\n")

    def handle_data(self, text):
        if not self.suppressed:
            self.parts.append(text)


def text_of(body) -> str:
    parser = _TextOnly()
    parser.feed(str(body))
    parser.close()
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


def dates_in(text) -> list[str]:
    candidates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b|\b20\d{6}T\d{6}(?:\.\d+)?Z\b", str(text))
    dates = set()
    for candidate in candidates:
        try:
            dates.add(_as_date(candidate).isoformat())
        except ValueError:
            continue
    return sorted(dates)


def _items(value) -> list:
    return value.get("items", []) if isinstance(value, dict) and isinstance(value.get("items"), list) else []


def _fact(value, source, at, confidence="observed") -> dict:
    return {"value": value, "source": source, "at": at, "confidence": confidence}


def dossier(tag) -> tuple[dict, str]:
    tag = normalize_tag(tag)
    at = utc_now()
    errors, provenance, result = [], {}, {"fetched_at": at}

    def put(key, value, source, confidence="observed"):
        result[key] = value
        provenance[key] = _fact(value, source, at, confidence)

    def get_history(path, **query):
        value = ck(tag, path, **query)
        if value is None:
            errors.append({"source": "clashking", "path": path, "detail": "unavailable or non-object JSON"})
        return value or {}

    profile = official(tag) or {}
    if not profile:
        errors.append({"source": "official_api", "detail": "profile unavailable; no ownership inference"})
    put("tag", tag, "owner input", "manual")
    put("profile", profile, "official_api")
    put("join_leave", _items(get_history("join-leave", limit=200)), "clashking")
    put("changes", parse_changes(_items(get_history("history/changes", type="name", limit=100))), "clashking", "derived")
    put("rankings", get_history("rankings"), "clashking")
    put("war_attacks", parse_war(_items(get_history("war/attacks", limit=100))), "clashking", "derived")
    put("war_stats", _items(get_history("war/stats", limit=50)), "clashking")
    put("cwl", _items(get_history("cwl/history", limit=50)), "clashking")
    pages = {}
    for name in ("clashofstats", "clashspot"):
        source = get_source(name)
        url = expand_source(source, TAG=tag[1:])
        response = net.fetch(url, ttl=3600)
        verdict = net.classify(source, response)
        pages[name] = {"url": url, "status": response.status, "verdict": verdict,
                       "cached": response.cached, "excerpt": text_of(response.body)[:800] if response.ok else ""}
        if verdict not in {"ok", "ok-js"}:
            errors.append({"source": name, "detail": verdict})
    put("pages", pages, ["clashofstats", "clashspot"], "derived")
    for key, value in (("name", profile.get("name")), ("th", profile.get("townHallLevel")),
                       ("xp", profile.get("expLevel")),
                       ("clan", (profile.get("clan") or {}).get("name") or ("none" if profile else None))):
        provenance[key] = _fact(value, "official_api", at)
    names = list(dict.fromkeys(change["value"] for change in result["changes"] if change["value"]))
    provenance["names"] = _fact(names, "clashking", at, "derived")
    # gap:G20 A ranking location is not the account owner's creation country.
    put("ranking_location", result["rankings"].get("location"), "clashking")
    event_dates = []
    for row in result["join_leave"] + result["war_attacks"]:
        if not isinstance(row, dict):
            continue
        value = row.get("time") or row.get("warEndTime")
        if value:
            try:
                day = _as_date(value)
                if day <= dt.datetime.now(dt.timezone.utc).date():
                    event_dates.append(day)
            except (TypeError, ValueError):
                continue
    # gap:G19 Activity establishes existence by a date, never a creation lower bound.
    # gap:G11 Feature release and Town Hall dates are deliberately not creation bounds.
    floor, ceiling = bracket([], event_dates)
    put("floor", floor, "clashking recorded events", "derived")
    put("ceiling", ceiling, "clashking recorded events", "derived")
    put("counts", {"join_leave": len(result["join_leave"]), "changes": len(result["changes"]),
                   "war_records": len(result["war_attacks"])}, "clashking", "derived")
    result["errors"] = errors
    result["provenance"] = provenance
    lines = ["# Ownership evidence worksheet", "", "Player tag: " + tag,
             "Name: " + str(profile.get("name") or "unconfirmed"),
             "Town Hall: " + str(profile.get("townHallLevel") or "unconfirmed"),
             "Clan: " + str(provenance["clan"]["value"] or "unconfirmed"),
             "Evidence read at: " + at, "",
             "Earliest recorded existence: " + str(ceiling or "unconfirmed"),
             "Creation date: unconfirmed. Recorded activity does not establish the first day of the account.",
             "Public history does not establish ownership.", "", "## Source results", ""]
    for name, page in pages.items():
        lines.append("- %s: %s (HTTP %s; cached=%s)" % (name, page["verdict"], page["status"], page["cached"]))
    for error in errors:
        lines.append("- Unavailable evidence: %s — %s" % (error["source"], error["detail"]))
    lines.extend(["", "Provenance for every derived fact is in dossier.json.",
                  "The live support screen outranks this file. Follow one ticket only."])
    return result, "\n".join(lines) + "\n"


def fill_profile(d) -> list[str]:
    def empty(key, value):
        return value in (None, "", [], {}) or (key in {"th", "xp"} and value == 0)

    target = data_dir() / "profile.json"
    prof = load_profile() if target.exists() else copy.deepcopy(TEMPLATE)
    incoming = d.get("profile") or {}
    tag = d.get("tag") or incoming.get("tag")
    if d.get("tag") and incoming and (not incoming.get("tag") or
            normalize_tag(d["tag"]) != normalize_tag(incoming["tag"])):
        raise ValueError("Dossier and public profile tags disagree; no fields were written")
    if prof.get("tag") and tag and normalize_tag(prof["tag"]) != normalize_tag(tag):
        raise ValueError("Existing profile belongs to a different tag; no fields were written")
    auto = {"tag": tag, "name": incoming.get("name"), "th": incoming.get("townHallLevel"),
            "xp": incoming.get("expLevel"),
            "clan": (incoming.get("clan") or {}).get("name") or ("none" if incoming else None),
            "names": [c.get("value") for c in d.get("changes", []) if isinstance(c, dict) and c.get("value")]}
    # gap:G19 Never auto-fill an account-creation answer from public history.
    # gap:G20 Never auto-fill owner location from a leaderboard or IP lookup.
    for key, value in auto.items():
        if empty(key, prof.get(key)) and not empty(key, value):
            prof[key] = value
    save_profile(prof)
    fields = ("tag", "name", "th", "xp", "clan", "date", "devices", "location",
              "country_code", "email", "email_new", "ap", "receipts", "names")
    return [key for key in fields if empty(key, prof.get(key)) or prof.get(key) == "unknown"]


def paste_block(prof) -> str:
    def scalar(key):
        return str(prof.get(key) or "unconfirmed")

    def entries(key):
        values = prof.get(key) or []
        return "; ".join(str(v) if not isinstance(v, dict) else
                         str(v.get("description") or v.get("file") or "owner-held evidence")
                         for v in values) or "unconfirmed"

    return "\n".join(["I lost access to my Clash of Clans account and request ownership review.",
                      "Player tag: " + scalar("tag"), "Account name: " + scalar("name"),
                      "Town Hall: " + scalar("th"), "Current clan: " + scalar("clan"),
                      "Creation date, from my own records or recollection: " + scalar("date"),
                      "My account-creation country: " + scalar("location"),
                      "Devices I used: " + entries("devices"),
                      "Purchase evidence I hold: " + entries("receipts"),
                      "Previous names to check against my records: " + entries("names"),
                      "Replacement email, only when support requests it: " + scalar("email_new"),
                      "I will supply additional owner-held evidence in this same ticket."])


def report(tag, open_it=False) -> str:
    existing = load_profile()
    if existing.get("tag") and normalize_tag(existing["tag"]) != normalize_tag(tag):
        raise ValueError("Use a separate directory for another account")
    data, text = dossier(tag)
    save_json(data_dir() / "dossier.json", data)
    atomic_write(data_dir() / "dossier.md", text)
    missing = fill_profile(data)
    if open_it:
        import webbrowser
        webbrowser.open((data_dir() / "dossier.md").resolve().as_uri())
    return text + "\nStill owner-supplied: " + ", ".join(missing) + "\n"


def _data(r) -> dict:
    d = r.get("data")
    return d if isinstance(d, dict) else {}


def scid(email, pin=None, game=COC, lang="en", quiet=False):
    """Probe an address against Supercell ID and report the bound tag.

    gap:G17 The route set is undocumented. login alone only proves the address is
    accepted; tag and name come back from login.validate, and only if isBound.
    Returns {"email","game","stage","ok","error","isValid","isBound","tag","name",
    "scid","created","links"}. No code is written to disk.
    """
    out = {"email": email, "game": game, "stage": "login", "ok": False,
           "error": None, "isValid": None, "isBound": None, "tag": None,
           "name": None, "created": None}
    base = {"email": email, "env": "prod", "game": game, "lang": lang}

    r = net.scid_post("/account/login", base)
    if not r.get("ok"):
        out["error"] = r.get("error") or "unknown"
        if not quiet:
            if out["error"] == "binding_not_found":
                print("no SCID on %s - clean negative" % email)
            else:
                print("login failed: %r" % out["error"])
        return out

    if not pin:
        out["stage"] = "pin_needed"
        if not quiet:
            print("code sent to %s - rerun with --pin" % email)
        return out

    # The documented body is email+pin only; game context is undocumented, so try
    # the minimal body first and widen only if it is rejected.
    out["stage"] = "validate"
    v = net.scid_post("/account/login.validate", {"email": email, "pin": pin})
    if not v.get("ok"):
        v = net.scid_post("/account/login.validate", dict(base, pin=pin))
    if not quiet:
        print("validate:", json.dumps(v, indent=2)[:1200])

    d = _data(v)
    out["isValid"] = d.get("isValid")
    out["isBound"] = d.get("isBound")
    if v.get("ok") and d.get("isValid"):
        app = d.get("application") or {}
        out["tag"], out["name"] = app.get("account"), app.get("username")
        out["ok"] = True
        if not quiet and out["tag"]:
            print("\nBOUND TAG: %s  NAME: %s" % (out["tag"], out["name"]))
        if not quiet and not d.get("isBound"):
            print("isBound false - address is valid but nothing hangs off it")
    elif not v.get("ok"):
        out["error"] = v.get("error") or "validate_failed"

    if not d.get("isBound"):
        return out

    out["stage"] = "confirm"
    c = net.scid_post("/account/login.confirm", {"email": email, "pin": pin})
    if not c.get("ok"):
        c = net.scid_post("/account/login.confirm", dict(base, pin=pin))
    cd = _data(c)
    tok = cd.get("scid")
    if not tok:
        out["error"] = c.get("error") or "confirm_failed"
        return out
    out["scid"] = tok
    if not quiet:
        print("\nscid:", tok[:40] + "...")

    hdr = {"scid_token": cd.get("scidToken", "")}
    s = net.scid_post("/account/settings.get", hdr, token=tok)
    out["created"] = _data(s).get("created")
    if out["created"] and not quiet:
        print("SCID CREATED: " + out["created"])

    l = net.scid_post("/account/links.get", hdr, token=tok)
    links = _data(l).get("links")
    if isinstance(links, list):
        out["links"] = [x.get("system") for x in links if isinstance(x, dict)]
        if not quiet:
            print("links:", out["links"])
    return out


def verify(tag, token) -> str:
    # gap:G12 Current availability and authorization of verifytoken are unconfirmed.
    normalize_tag(tag)
    return ("BLOCKED [G12]. The token-verification endpoint is not enabled. "
            "No token was sent, stored or echoed; no ownership result was produced.")


def takeout(root) -> str:
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Takeout root must be an existing local directory")
    # gap:G18 Owner-supplied receipt evidence has no verified acceptance weight.
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink() and path.suffix.lower() in {".json", ".html", ".csv", ".txt", ".pdf"}:
            name = str(path.relative_to(root))
            if any(word in name.casefold() for word in ("clash", "purchase", "order", "google play")):
                rows.append({"file": name, "bytes": path.stat().st_size,
                             "source": "owner-provided local export", "at": utc_now(),
                             "confidence": "manual"})
        if len(rows) >= 500:
            break
    save_json(data_dir() / "takeout_index.json", rows)
    return "Indexed %d candidate local files in takeout_index.json; contents were not uploaded or treated as verified receipts." % len(rows)


def main(argv=None) -> int:
    from coc import main as cli_main
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
