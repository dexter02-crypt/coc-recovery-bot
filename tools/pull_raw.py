"""Dump raw ClashKing bodies for review. Dev-only; not part of the distribution.

Every request goes through net.fetch so pacing, retries and the ClashKing
cooldown apply. history/changes needs a type, and type is limited to names or
IDs 1-15; the caller supplies them.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time

import net

BASE = net.CLASHKING_API_BASE
UA = {"User-Agent": "coc-recovery-bot"}


def get(path, params):
    url = BASE + path
    if params:
        url = net.add_query(url, params)
    return net.fetch(url, headers=UA, ttl=0, retries=2), url


def dump(name, path, params, cursor, cap):
    before, page = None, 0
    types = collections.Counter()
    while page < cap:
        query = dict(params)
        if before:
            query["time[before]"] = before
        response, url = get(path, query)
        if not response.ok:
            print("%-22s page %02d HTTP %s %s" % (name, page, response.status,
                                                 response.body[:120]), file=sys.stderr)
            break
        payload = json.loads(response.body)
        open("raw/%s-%02d.json" % (name, page), "w").write(json.dumps(payload, ensure_ascii=False))
        items = payload.get("items") or []
        for item in items:
            if isinstance(item, dict) and item.get("type"):
                types[item["type"]] += 1
        print("%-22s page %02d n=%d keys=%s" % (name, page, len(items), list(payload)[:8]))
        if not items:
            break
        stamps = [item.get(cursor) for item in items if isinstance(item, dict) and item.get(cursor)]
        if not stamps or stamps[-1] == before:
            break
        before, page = stamps[-1], page + 1
        time.sleep(0.4)
    if types:
        print("   types: " + ", ".join("%s=%d" % pair for pair in types.most_common()))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dump raw ClashKing history bodies")
    ap.add_argument("tag")
    ap.add_argument("--clan", default=None)
    ap.add_argument("--cap", type=int, default=40)
    a = ap.parse_args(argv)
    tag = a.tag.lstrip("#").upper()

    for change_type in ("7", "3", "10", "14"):
        dump("changes-type-%s" % change_type, "/player/%%23%s/history/changes" % tag,
             {"type": change_type, "limit": 100}, "time", a.cap)
    dump("join-leave", "/player/%%23%s/join-leave" % tag, {"limit": 100}, "time", a.cap)
    dump("history-stats", "/player/%%23%s/history/stats" % tag,
         {"type": "donated", "limit": 100}, "eventTime", a.cap)
    dump("battlelog", "/player/%%23%s/battlelog/history" % tag, {"limit": 100}, "battleTime", a.cap)

    for name, path in (("rankings", "/player/%s/rankings" % tag),
                       ("cwl-history", "/player/%%23%s/cwl/history?limit=100" % tag),
                       ("league-history", "/player/%%23%s/league/history?limit=100" % tag)):
        response, _ = get(path.split("?")[0], {"limit": 100} if "?" in path else {})
        if response.ok:
            open("raw/%s-00.json" % name, "w").write(response.body)
            print("%-22s single page n/a" % name)
        else:
            print("%-22s HTTP %s" % (name, response.status), file=sys.stderr)

    if a.clan:
        clan = a.clan.lstrip("#").upper()
        response, _ = get("/clan/%%23%s/member-joins" % clan, {"limit": 100})
        if response.ok:
            open("raw/clan-member-joins-00.json", "w").write(response.body)
            print("clan-member-joins      single page")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
