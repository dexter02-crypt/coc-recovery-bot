"""Extract public corroborating records. Exit codes: 0 including empty results, 2 registry or I/O.

Import is inert. All HTTP goes through net.fetch. An empty result still exits 0
but prints its reason to stderr, so a silent [] is distinguishable from a broken
run. Clan-scoped registry routes are only attempted when a clan tag is supplied.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

import coc_recover as recover
import net

TAG_RX = re.compile(r"#[A-Z0-9]{3,15}\b", re.I)
CLAN_RX = re.compile(r"\bclan\s*:\s*([^\n]{1,60})", re.I)


def schema_values(value, path):
    """Read a dotted JSON field path; * visits members of one array/object."""
    parts = str(path).split(".") if path else []

    def visit(node, rest):
        if not rest:
            if isinstance(node, list):
                return [item for item in node if isinstance(item, (str, int, float)) and not isinstance(item, bool)]
            return [node] if isinstance(node, (str, int, float)) and not isinstance(node, bool) else []
        head, tail = rest[0], rest[1:]
        if head == "*":
            values = node.values() if isinstance(node, dict) else node if isinstance(node, list) else []
            return [found for child in values for found in visit(child, tail)]
        if isinstance(node, dict) and head in node:
            return visit(node[head], tail)
        return []

    return visit(value, parts)


def extract(source, path, body):
    if source.get("json"):
        payload = json.loads(body)
        mapping = (source.get("schema") or {}).get(path)
        if not isinstance(mapping, dict):
            # gap:G16 JSON without a source-specific schema is not promoted to evidence.
            return None
        fields = {}
        for name in ("dates", "tags", "clans"):
            candidates = mapping.get(name, [])
            fields[name] = [str(found) for pointer in candidates
                            for found in schema_values(payload, pointer)]
        dates = recover.dates_in("\n".join(fields["dates"]))
        tags = sorted(set(TAG_RX.findall("\n".join(fields["tags"]))))
        clans = sorted(set(text.strip() for text in fields["clans"] if text.strip()))
        excerpt = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
        if not source.get("schema_verified", False):
            # gap:G16 Candidate schema fields need direct confirmation before support use.
            excerpt = "[unconfirmed schema mapping: G16] " + excerpt
    else:
        text = recover.text_of(body)
        dates = recover.dates_in(text)
        tags = sorted(set(TAG_RX.findall(text)))
        clans = sorted(set(match.strip() for match in CLAN_RX.findall(text) if match.strip()))
        # gap:G19 Dates in page chrome can be unrelated to this player's activity.
        excerpt = "[unconfirmed page-to-player association: G19] " + text
    return {"dates": dates[:200], "tags": tags[:50], "clans": clans[:25], "excerpt": excerpt[:1200]}


def scrape(tag, config, clan=None):
    """Return (records, stats); stats is what makes an empty run explainable."""
    tag = recover.normalize_tag(tag)[1:]
    records = []
    stats = {"paths": 0, "answered": 0, "clan_skipped": 0}
    for source in config["sources"]:
        if any(source.get(flag) for flag in ("js", "auth", "blocked")):
            continue
        if source.get("kind") not in (None, "tracker", "api"):
            continue
        for index, path in enumerate(source["paths"]):
            if source.get("tag_kind") == "clan" and not clan:
                stats["clan_skipped"] += 1
                continue
            try:
                url = recover.expand_for(source, index, tag=tag, clan=clan)
            except net.ConfigError:
                continue
            stats["paths"] += 1
            response = net.fetch(url)
            if not response.ok or net.classify(source, response) not in {"ok", "unmarked"}:
                continue
            stats["answered"] += 1
            try:
                extracted = extract(source, path, response.body)
            except (TypeError, ValueError):
                extracted = None
            if extracted is None:
                continue
            records.append({"source": source["name"], "url": url,
                            "dates": extracted["dates"], "tags": extracted["tags"],
                            "clans": extracted["clans"], "excerpt": extracted["excerpt"],
                            "fetched_at": recover.utc_now()})
    return records, stats


def empty_reason(stats) -> str:
    """Name why nothing was collected, without claiming the history is empty."""
    if not stats["paths"]:
        note = "no eligible path in the registry"
        if stats["clan_skipped"]:
            note += " (%d clan-scoped path(s) need --clan)" % stats["clan_skipped"]
        return note + "; this does not prove there is no history"
    if not stats["answered"]:
        return ("all %d attempted path(s) were unreachable, blocked, gone or unmarked; "
                "this does not prove there is no history" % stats["paths"])
    return ("%d of %d attempted path(s) answered but yielded no mapped field; "
            "this does not prove there is no history" % (stats["answered"], stats["paths"]))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Extract dated public observations; never assert ownership")
    parser.add_argument("tag")
    parser.add_argument("--sources", default=None)
    parser.add_argument("--clan", default=None,
                        help="clan tag, required by clan-scoped registry routes")
    args = parser.parse_args(argv)
    try:
        clan = recover.normalize_tag(args.clan)[1:] if args.clan else None
        live = recover.data_dir() / "sources.live.json"
        selected = args.sources or (str(live) if live.exists() else None)
        records, stats = scrape(args.tag, recover.load_sources(selected), clan)
    except (net.ConfigError, ValueError, OSError) as error:
        print("Cannot scrape: " + str(error), file=sys.stderr)
        return 2
    try:
        recover.save_json(recover.data_dir() / "external.json", records)
    except OSError as error:
        print("Could not write external.json: " + str(error), file=sys.stderr)
        return 2
    print("external.json: %d public observations" % len(records))
    if not records:
        print("No observations: " + empty_reason(stats), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
