#!/usr/bin/env python3
"""Repair the merged scid/net/sources work. Exit codes: 0 fixed, 1 aborted."""
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(".").resolve()


def read(name):
    return (ROOT / name).read_text()


def write(name, text):
    (ROOT / name).write_text(text)


def sub(text, old, new, label):
    if old not in text:
        sys.exit("missing anchor: " + label)
    return text.replace(old, new, 1)


# ---------------------------------------------------------------- net.py -----
net = read("net.py")
net = sub(net, "RETRY_STATUSES = frozenset({0, 429, 502, 503, 504})",
          "RETRY_STATUSES = frozenset(\n"
          "    {0, 408, 425, 429, 502, 503, 504, 520, 521, 522, 523, 524})",
          "retry set")
net = sub(net, 'OFFICIAL_API_BASE = "https://api.clashofclans.com/v1"',
          'OFFICIAL_API_BASE = "https://api.clashofclans.com/v1"\n'
          'SCID_API_BASE = "https://ingame.id.supercell.com/api"', "scid base")
net = sub(net, "from typing import Optional\nimport random\nimport sys\n",
          "from typing import Optional\n", "stray imports")
net = sub(net, 'def add_query(url: str, values: dict) -> str:',
          'def form(values: dict) -> str:\n'
          '    """Encode a form body; the only place form encoding is spelled out."""\n'
          '    return urllib.parse.urlencode(values)\n\n\n'
          'def add_query(url: str, values: dict) -> str:', "form helper")
cut = net.index("\n# --- clashking failover")
net = net[:cut] + '''
# --- clashking failover -----------------------------------------------------
CLASHKING_COOLDOWN = 90.0
CLASHKING_SLOTS = threading.BoundedSemaphore(2)
_clashking_until = [0.0]
_clashking_lock = threading.Lock()


def clashking_available() -> bool:
    with _clashking_lock:
        return time.monotonic() >= _clashking_until[0]


def _clashking_trip() -> None:
    with _clashking_lock:
        _clashking_until[0] = time.monotonic() + CLASHKING_COOLDOWN


def fetch_clashking(url, *, official_url=None, ttl=300, retries=2, timeout=20) -> Response:
    """GET a ClashKing URL, retrying 522-class failures, then failing over.

    The public host sits behind Cloudflare and answers 522 under load; a 522 is
    not a dead account. After a retryable failure the host is parked for a
    cooldown so later calls do not each rediscover the outage. Only an
    official-shaped route has an official equivalent, so a history route returns
    status 0 rather than a fabricated answer.
    """
    url = validate_url(url)
    if not clashking_available():
        if official_url is not None:
            return fetch(validate_url(official_url), ttl=ttl, timeout=timeout)
        return Response(0, "", False, "unreachable", 0.0, url, False)
    with CLASHKING_SLOTS:
        response = fetch(url, ttl=ttl, retries=retries, timeout=timeout)
    if response.status in RETRY_STATUSES:
        _clashking_trip()
        if official_url is not None:
            return fetch(validate_url(official_url), ttl=ttl, timeout=timeout)
    return response
'''
write("net.py", net)

# --------------------------------------------------------- coc_recover.py ----
rec = read("coc_recover.py")
rec = sub(rec, "import net\nimport random\nimport sys\nimport threading\n"
               "import time\nimport urllib.error\nimport urllib.parse\n"
               "import urllib.request\n", "import net\n", "coc_recover imports")
rec = sub(rec, 'SCID = "https://ingame.id.supercell.com/api"\n', "", "scid literal")
old_post = rec[rec.index("def _scid_post(path, form, token=None):"):rec.index("def _data(r):")]
rec = rec.replace(old_post, '''def _scid_post(path, form, token=None):
    headers = {"Content-Type": "application/x-www-form-urlencoded",
               "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    response = net.fetch(net.SCID_API_BASE + path, method="POST",
                         headers=headers, data=net.form(form), ttl=0, timeout=25)
    try:
        payload = json.loads(response.body or "{}")
    except (TypeError, ValueError):
        return {"ok": False, "error": "http_%s" % response.status
                if response.status else "transport"}
    return payload if isinstance(payload, dict) else {"ok": False, "error": "badjson"}


''')
write("coc_recover.py", rec)

# --------------------------------------------------------------- coc.py -----
coc = read("coc.py")
coc = sub(coc, "import argparse\nimport sys\n", "import argparse\nimport json\nimport sys\n",
          "coc import")
coc = sub(coc, 'help="Explain the manual Supercell ID sign-in step"',
          'help="Probe an address against the private Supercell ID routes"', "scid help")
coc = sub(coc,
          '    scid_parser.add_argument("--code", default=None, '
          'help="Ignored; enter inbox codes only in the game")\n',
          '    scid_parser.add_argument("--pin", "--code", dest="pin", default=None,\n'
          '                             help="six-digit inbox code; omit to only request it")\n'
          '    scid_parser.add_argument("--game", default=coc_recover.COC,\n'
          '                             choices=sorted(coc_recover.SCID_GAMES),\n'
          '                             help="game codename, default magic (Clash of Clans)")\n'
          '    scid_parser.add_argument("--json", action="store_true",\n'
          '                             help="machine-readable result only")\n', "scid args")
coc = sub(coc,
          '        elif args.command == "scid":\n'
          '            # gap:G17 This command does not call private Supercell ID APIs.\n'
          '            print(coc_recover.scid(args.email, args.code))\n'
          '            return 1\n',
          '        elif args.command == "scid":\n'
          '            # gap:G17 Documented private routes; not a supported API.\n'
          '            result = coc_recover.scid(args.email, args.pin, args.game,\n'
          '                                      quiet=args.json)\n'
          '            if args.json:\n'
          '                print(json.dumps(result, indent=2, ensure_ascii=False))\n'
          '            return 0 if result["ok"] else 1\n', "scid dispatch")
write("coc.py", coc)

# ----------------------------------------------------------- sources.json ---
raw = json.loads(read("sources.json"))
rows = raw["sources"] if isinstance(raw, dict) else raw
by_name = {row["name"]: row for row in rows}
for row in rows:
    row.setdefault("markers", [])
    row.setdefault("js", False)
    row.setdefault("blocked", False)
    if "note" in row:
        row["notes"] = row.pop("note")
    row.setdefault("kind", "api" if row.get("json") else "tracker")
by_name["scid"].update({
    "kind": "api", "gaps": ["G17"],
    "source_url": "https://github.com/ZeroBone/ScidApi/blob/master/APIDoc.MD",
    "notes": "Documented private routes, form-encoded only; game=magic is CoC per the "
             "doc's own table. login.validate returns application.account/username, "
             "i.e. the tag and name bound to the address. The document is dated 2022 "
             "and live field drift is unverified."})
by_name["fwastats-player"].update({
    "kind": "tracker", "gaps": ["G16"], "blocked": False,
    "source_url": "https://github.com/ptim74/fwastats/blob/master/src/FWAStatsWeb/"
                  "Controllers/PlayersController.cs"})
by_name["fwastats-data"].update({
    "kind": "api", "gaps": ["G04", "G16"],
    "source_url": "https://github.com/ptim74/fwastats/blob/master/src/FWAStatsWeb/"
                  "Controllers/DataController.cs"})
by_name["fwastats"]["notes"] += " See fwastats-player for the sourced per-player route."
write("sources.json", json.dumps({"sources": rows}, indent=2, ensure_ascii=False) + "\n")

# --------------------------------------------------------------- README -----
rd = read("README.md")
rd = sub(rd, "Every network request is centralized in `net.fetch`.",
         "Every network request is centralized in `net.fetch`; ClashKing history "
         "calls go through `net.fetch_clashking`, which retries and then parks the "
         "host.", "readme centralization")
rd = sub(rd, "Retries are limited to transport failures/status 0 and HTTP 429, 502, "
             "503 and 504 for safe requests; other statuses are returned.",
         "Retries are limited to transport failures/status 0 and HTTP 408, 425, 429, "
         "502, 503, 504 and the Cloudflare 520-524 range for safe requests; other "
         "statuses are returned. A 522 is an outage, not a dead account.",
         "readme retries")
rd = sub(rd, "The `scid` and `verify` helpers are fail-closed manual guidance until "
             "supported endpoints, token types and response meaning are documented "
             "(G12/G17). Do not supply an inbox code to a CLI.",
         "The `scid` command probes an address against the private Supercell ID "
         "routes (G17): documented, but not a supported API. "
         "`python coc.py scid you@example.com` requests the code; rerun with "
         "`--pin 123456` to read the reply. `login.validate` returns `isValid`, "
         "`isBound` and, when bound, `application.account` and "
         "`application.username` — the tag and name attached to that address, an "
         "email-to-tag join the owner does not have to supply. `binding_not_found` "
         "is the clean negative. Running `--pin` through to `confirm` exchanges the "
         "code for SCID tokens, so the code is spent for a game login afterwards. "
         "`--game` picks the codename (`magic` is Clash of Clans); `--json` prints "
         "the result only. The `verify` helper stays fail-closed (G12).",
         "readme scid")
rd = sub(rd, "| `net.py` | Lazy configuration, centralized HTTP, safe retry/spacing "
             "behavior and SQLite TTL cache. |",
         "| `net.py` | Lazy configuration, centralized HTTP, safe retry/spacing "
         "behavior, SQLite TTL cache and ClashKing retry/cooldown. |", "readme netmap")
rd = rd.rstrip("\n") + "\n\n`tools/` is repository scaffolding, not part of the 17-file distribution.\n"
write("README.md", rd)

# --------------------------------------------------------------- workflow ---
wf = ROOT / ".github" / "workflows"
wf.mkdir(parents=True, exist_ok=True)
(wf / "checks.yml").write_text('''name: checks
on:
  push:
    branches: [main]
  pull_request:
jobs:
  offline:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python: ["3.9", "3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - name: offline contract suite
        run: python selftest.py
      - name: package with gaps allowed
        run: python build.py --allow-gaps
      - name: archive is the 17 sources plus the manifest
        run: |
          python - <<'PY'
          import zipfile
          names = zipfile.ZipFile("coc-recover.zip").namelist()
          assert len(names) == 18, len(names)
          assert "MANIFEST.sha256" in names
          print("archive ok:", len(names), "members")
          PY
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check --select E9,F63,F7,F82 .
''')

# ---------------------------------------------------------------- tidy ------
tools = ROOT / "tools"
tools.mkdir(exist_ok=True)
for name in ("patch.py", "fix.py"):
    if (ROOT / name).exists():
        shutil.move(str(ROOT / name), str(tools / name))
print("fixed. next: python selftest.py")