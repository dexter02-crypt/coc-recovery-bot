"""Reduce raw/ to derived.json. Every fact carries source, path and observation date."""
from __future__ import annotations

import glob
import json
import os

OBS = "2026-11-22"
LOCATION = None
NAMES, TH, ACTIVITY, CLANS, NOTES = [], [], [], {}, []


def load(pattern):
    for path in sorted(glob.glob(pattern)):
        try:
            yield path, json.load(open(path))
        except (OSError, ValueError):
            continue


for path, payload in load("raw/changes-type-*.json"):
    for item in payload.get("items") or []:
        if item.get("type") == "townhall_level":
            TH.append({"time": item["time"], "from": item.get("previous"), "to": item.get("current")})
            NOTES.append("[src=clashking path=%s seen=%s] th %s->%s"
                         % (path, OBS, item.get("previous"), item.get("current")))
        if item.get("type") in ("name", "name_change"):
            NAMES.append({"time": item["time"], "name": item.get("current")})
            NOTES.append("[src=clashking path=%s seen=%s] name -> %s"
                         % (path, OBS, item.get("current")))

for path, payload in load("raw/battlelog-*.json"):
    for item in payload.get("items") or []:
        if item.get("battleTime"):
            ACTIVITY.append(item["battleTime"])

for path, payload in load("raw/history-stats-*.json"):
    for item in payload.get("items") or []:
        if item.get("eventTime"):
            ACTIVITY.append(item["eventTime"])

for path, payload in load("raw/join-leave-*.json"):
    for item in payload.get("items") or []:
        if item.get("time"):
            ACTIVITY.append(item["time"])
        clan = item.get("clan") or {}
        if clan.get("tag"):
            row = CLANS.setdefault(clan["tag"], {"name": clan.get("name"), "first": item["time"],
                                                 "last": item["time"], "visits": 0})
            row["visits"] += 1
            row["first"] = min(row["first"], item["time"])
            row["last"] = max(row["last"], item["time"])

for path, payload in load("raw/rankings-*.json"):
    location = payload.get("location") or {}
    if location.get("countryCode"):
        LOCATION = {"countryCode": location["countryCode"], "name": location.get("name"),
                    "isCountry": location.get("isCountry")}
        NOTES.append("[src=clashking path=%s seen=%s] ranking location %s (%s), not origin"
                     % (path, OBS, location.get("name"), location["countryCode"]))

TH.sort(key=lambda row: row["time"])
NAMES.sort(key=lambda row: row["time"])
out = {
    "observed_at": OBS,
    "location": LOCATION,
    "names_oldest_first": [row["name"] for row in NAMES if row.get("name")],
    "name_source": "clashking name change" if NAMES else
                   "none observed; use the Supercell data request",
    "th_ladder": TH,
    "earliest_activity": min(ACTIVITY) if ACTIVITY else None,
    "activity_observations": len(ACTIVITY),
    "clan_history": sorted(({"tag": tag, **row} for tag, row in CLANS.items()),
                           key=lambda row: row["first"]),
    "provenance": NOTES,
}
json.dump(out, open("derived.json", "w"), indent=2, ensure_ascii=False)
print(json.dumps({k: out[k] for k in ("location", "earliest_activity", "activity_observations",
                                     "name_source")}, indent=2, ensure_ascii=False))
print("names: %d  th changes: %d  clans: %d  notes: %d"
      % (len(out["names_oldest_first"]), len(TH), len(out["clan_history"]), len(NOTES)))
