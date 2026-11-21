"""Probe registered public paths. Exit codes: 0 usable, 1 none/strict gap, 2 configuration.

Only net.fetch performs HTTP. Probes never send API tokens or follow redirects.
"""
from __future__ import annotations

import argparse
import copy
import csv
import io
import sys

import coc_recover as recover
import net


def probe(tag, config):
    """Return one observation per path and sources with their usable paths retained."""
    tag = recover.normalize_tag(tag)[1:]
    rows, survivors = [], []
    for source in config["sources"]:
        retained = []
        for index, path in enumerate(source["paths"]):
            url = recover.expand_source(source, index, TAG=tag)
            # gap:G04 A reachable successor index does not establish a player URL.
            response = net.fetch(url, ttl=0, retries=0 if source.get("blocked") or source.get("auth") else 3)
            verdict = net.classify(source, response)
            rows.append({"name": source["name"], "url": url, "status": response.status,
                         "verdict": verdict, "len": len(response.body)})
            if verdict in {"ok", "ok-js"}:
                retained.append(path)
        if retained:
            survivor = copy.deepcopy(source)
            survivor["paths"] = retained
            # gap:G16 Successful HTTP does not prove completeness or field semantics.
            survivors.append(survivor)
    return rows, survivors


def write_results(rows, path) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["name", "url", "status", "verdict", "len"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    recover.atomic_write(path, buffer.getvalue())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Classify public source responses without authentication")
    parser.add_argument("tag")
    parser.add_argument("--sources", default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--write-sources", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = recover.load_sources(args.sources)
        rows, survivors = probe(args.tag, config)
        write_results(rows, recover.data_dir() / "probe_results.csv")
        if args.write_sources:
            recover.save_json(recover.data_dir() / "sources.live.json", {
                "_note": "Reachable paths only. Original flags and verification claims are preserved; live HTTP does not verify semantics.",
                "sources": survivors})
    except (net.ConfigError, ValueError, OSError) as error:
        print("Configuration error: " + str(error), file=sys.stderr)
        return 2
    for row in rows:
        print("{name:24} {status:3} {verdict:11} {len:7} {url}".format(**row))
    usable = sum(row["verdict"] == "ok" for row in rows)
    unverified = any(source["verified_how"] == "unverified" for source in config["sources"])
    print("%d/%d paths classify ok; probe_results.csv written." % (usable, len(rows)))
    if args.strict and unverified:
        print("Strict check failed: the registry contains unverified sources.", file=sys.stderr)
    return 1 if usable == 0 or (args.strict and unverified) else 0


if __name__ == "__main__":
    raise SystemExit(main())
