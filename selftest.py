#!/usr/bin/env python3
"""Offline contract checks. Exit codes: 0 all passed, 1 any failed, 2 usage.

No token, network, browser, or external package is needed. Import checks run in
fresh processes, prevent network and import-time writes, and reject configuration
reads during import. Fetch tests replace the sole transport boundary with fakes.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import csv
import datetime as dt
import importlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Dict, List, Optional, Sequence
from unittest import mock


MODULES = (
    "net", "coc", "coc_recover", "readiness", "support_driver",
    "attempts", "probe", "scrape", "selftest", "build",
)
WEIGHTS = {
    "identity_match": 25, "egress_country": 20, "replacement_email": 15,
    "protection_known": 15, "receipts": 15, "devices": 10,
}
GAP_HEADER = (
    "id", "area", "what_is_missing", "why_it_matters", "how_to_get_it",
    "blocking", "affects_files",
)
SOURCE_METHODS = {
    "browser-loads", "browser-403", "docs-page",
    "github-code-reference", "unverified",
}
STATES = {"pass", "fail", "warn", "skip"}
VERDICTS = {
    "ok", "ok-js", "blocked", "gone", "auth", "empty", "badjson",
    "unmarked", "unreachable",
}
UTC = dt.timezone.utc


class Suite:
    """Small assertion runner; failures remain visible instead of being skipped."""

    def __init__(self) -> None:
        self.total = 0
        self.failures = []  # type: List[str]

    def check(self, name: str, action: Callable[[], object]) -> None:
        self.total += 1
        try:
            action()
        except Exception as exc:
            self.failures.append(name)
            print("FAIL " + name + ": " + type(exc).__name__ + ": " + str(exc))


def require(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def equal(actual: object, expected: object) -> None:
    require(actual == expected, repr(actual) + " != " + repr(expected))


def raises(kind: type, action: Callable[[], object]) -> None:
    try:
        action()
    except kind:
        return
    except Exception as exc:
        raise AssertionError("Expected " + kind.__name__ + ", got " + type(exc).__name__) from exc
    raise AssertionError("Expected " + kind.__name__ + ", but no exception was raised")


def _deny_network(event: str, args: object) -> None:
    if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
        raise RuntimeError("Network is forbidden in selftest")


def _clean_import(root: Path, name: str) -> None:
    script = r'''
import importlib
import os
import sys
violations = []
def audit(event, args):
    bad = event in ("socket.connect", "socket.getaddrinfo", "socket.bind",
                    "sqlite3.connect", "subprocess.Popen", "os.system")
    if event == "open":
        path, mode, flags = args
        mode = mode or ""
        path = str(path)
        write = any(letter in mode for letter in "wax+") or bool(
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        config_read = path.endswith((".json", ".csv", ".sqlite", ".sqlite3", ".db"))
        bad = bad or write or config_read
    if bad:
        violations.append(event)
        raise RuntimeError("Import-time work: " + event)
sys.addaudithook(audit)
importlib.import_module(sys.argv[1])
if violations:
    raise RuntimeError("Import-time side effects were caught and suppressed: " + repr(violations))
'''
    env = dict(os.environ)
    env.pop("COC_API_BASE", None)
    env.pop("COC_API_TOKEN", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="coc-import-") as temporary:
        env["COC_DATA_DIR"] = temporary
        env["COC_CACHE_PATH"] = str(Path(temporary) / "cache.sqlite3")
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, name], cwd=str(root),
            env=env, capture_output=True, text=True, timeout=20,
        )
        require(result.returncode == 0,
                "import process exited " + str(result.returncode) + ": " + result.stderr.strip())
        equal(result.stdout, "")
        equal(result.stderr, "")
        equal(list(Path(temporary).iterdir()), [])


def _source_schema(config: dict) -> None:
    require(isinstance(config, dict), "sources.json must be an object")
    rows = config.get("sources")
    require(isinstance(rows, list) and bool(rows), "sources must be a nonempty array")
    names = set()
    for row in rows:
        require(isinstance(row, dict), "source is not an object")
        required = {"name", "base", "paths", "markers", "verified_how", "date_checked"}
        require(required.issubset(row), "missing source fields: " + repr(required - set(row)))
        name = row["name"]
        require(isinstance(name, str) and bool(name), "empty source name")
        require(name not in names, "duplicate source name: " + name)
        names.add(name)
        require(isinstance(row["base"], str) and bool(row["base"]), "empty base")
        scheme = row["base"].split(":", 1)[0]
        require(scheme in ("http", "https"), "base is not an HTTP URL")
        require(isinstance(row["paths"], list) and bool(row["paths"]), "paths must be a nonempty array")
        require(all(isinstance(path, str) for path in row["paths"]), "non-string path")
        require(isinstance(row["markers"], list), "markers must be an array")
        require(all(isinstance(marker, str) for marker in row["markers"]), "non-string marker")
        require(row["verified_how"] in SOURCE_METHODS, "invalid verification method")
        dt.date.fromisoformat(row["date_checked"])
        for flag in ("json", "js", "auth", "blocked"):
            if flag in row:
                require(isinstance(row[flag], bool), "flag must be boolean: " + flag)


def _obstacle_schema(data: dict) -> None:
    for key in ("markers", "structural"):
        rows = data.get(key)
        require(isinstance(rows, list), key + " must be an array")
        dates = []
        for row in rows:
            require(isinstance(row, dict), "obstacle must be an object")
            require(isinstance(row.get("name"), str) and bool(row["name"]), "missing obstacle name")
            dates.append(dt.date.fromisoformat(row["date"]))
        equal(dates, sorted(dates))


def _url_literal_audit(root: Path) -> None:
    pattern = re.compile(r"\bhttps?" + ":" + "/" + "/")
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 9))
        allowed = set()
        if path.name == "net.py":
            for statement in tree.body:
                if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    value = statement.value
                    if any(isinstance(target, ast.Name) and target.id.endswith("_API_BASE") for target in targets):
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            allowed.add(id(value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and pattern.search(node.value):
                require(id(node) in allowed, "URL literal in " + path.name + ":" + str(getattr(node, "lineno", 0)))


def _only_net_http(root: Path) -> None:
    for path in root.glob("*.py"):
        if path.name == "net.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                require(not any(alias.name.startswith(("urllib", "http.client")) for alias in node.names),
                        "HTTP import outside net: " + path.name)
            if isinstance(node, ast.ImportFrom):
                require(not (node.module or "").startswith(("urllib", "http.client")),
                        "HTTP import outside net: " + path.name)


def _config_call_sites(root: Path) -> None:
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            name = function.id if isinstance(function, ast.Name) else (
                function.attr if isinstance(function, ast.Attribute) else ""
            )
            if name == "raise_for_config":
                require(path.name in ("coc.py", "readiness.py"), "Config check called in " + path.name)


def _fixture_profile() -> dict:
    return {
        "tag": "#P0Y2LQRR", "name": "Fixture Owner", "th": 12, "xp": 100,
        "clan": "Fixture Clan", "date": "manual: unknown",
        "devices": ["Owner's test device"], "location": "India",
        "country_code": "IN", "email": "old@invalid.test",
        "email_new": "replacement@invalid.test", "ap": "yes",
        "receipts": ["Owner possesses original store receipt; no identifier stored"],
        "names": [], "notes": "",
    }


def _fixture_live() -> dict:
    return {
        "tag": "#P0Y2LQRR", "name": "Fixture Owner", "townHallLevel": 12,
        "expLevel": 100, "clan": {"name": "Fixture Clan", "tag": "#P0Y2LQ"},
    }


def _find_check(report: object, check_id: str) -> object:
    matches = [check for check in report.checks if check.id == check_id]
    require(len(matches) == 1, "expected one check " + check_id)
    return matches[0]


def _assert_blocker(report: object, check_id: str) -> None:
    check = _find_check(report, check_id)
    equal(check.state, "fail")
    equal(check.weight, 0)
    require(report.blockers, "missing blocker list")
    require(report.score <= 69, "blocker did not cap score below the minimum floor")
    equal(report.verdict, "no-go")


def _dossier_checks(suite: Suite, recover: object, net: object, template: dict, temp: Path) -> None:
    requested = []
    histories = {
        "join-leave": {"items": [{"time": "2018-06-01T12:00:00Z", "type": "join",
                                  "clan": {"name": "Older Clan"}}]},
        "history/changes": {"items": [{"time": "2020-01-01", "type": "name",
                                       "item": {"name": "Earlier Name"},
                                       "previous": True, "current": False}]},
        "rankings": {"location": {"name": "Leaderboard Country", "countryCode": "US"}},
        "war/attacks": {"items": [{"warEndTime": "20200101T120000.000Z",
                                   "defendingClanTag": "#P0Y2LQ", "stars": 3,
                                   "destructionPercentage": 100}]},
        "war/stats": {"items": [{"attacks": 1}]},
        "cwl/history": {"items": [{"season": "2020-01"}]},
    }

    def history(tag, path, **query):
        requested.append(path)
        return copy.deepcopy(histories[path])

    def page(url, **options):
        return net.Response(200, "<html>clan history war player records</html>",
                            True, "ok", 0.0, url, False)

    def provenance():
        with mock.patch.object(recover, "official", return_value=_fixture_live()), \
                mock.patch.object(recover, "ck", side_effect=history), \
                mock.patch.object(net, "fetch", side_effect=page):
            data, rendered = recover.dossier("#P0Y2LQRR")
        require(type(rendered) is str, "dossier text was not a string")
        equal(set(requested), set(histories))
        equal(set(data["pages"]), {"clashofstats", "clashspot"})
        equal(data["floor"], None)
        equal(data["ceiling"], "2018-06-01")
        for key in ("tag", "profile", "join_leave", "changes", "rankings", "war_attacks",
                    "war_stats", "cwl", "pages", "name", "th", "xp", "clan", "names",
                    "ranking_location", "floor", "ceiling", "counts"):
            fact = data["provenance"][key]
            equal(set(fact), {"value", "source", "at", "confidence"})
            require(bool(fact["source"]), "missing provenance source for " + key)
            dt.datetime.fromisoformat(fact["at"].replace("Z", "+00:00"))
            require(fact["confidence"] in {"observed", "derived", "manual"},
                    "invalid confidence for " + key)
        equal(data["provenance"]["tag"]["confidence"], "manual")
        equal(data["provenance"]["ceiling"]["confidence"], "derived")
    suite.check("dossier: complete collection and per-field provenance", provenance)

    def only_empty_fields():
        directory = temp / "fill-profile"
        directory.mkdir()
        path = directory / "profile.json"
        profile = copy.deepcopy(template)
        profile.update({"tag": "#P0Y2LQRR", "name": "Owner's saved spelling",
                        "th": 0, "xp": 0,
                        "date": "manual date", "location": "Owner's country", "country_code": "IN"})
        path.write_text(json.dumps(profile), encoding="utf-8")
        incoming = {"tag": "#P0Y2LQRR", "profile": _fixture_live(),
                    "changes": [{"value": "Previous Name"}], "floor": "2018-01-01",
                    "ceiling": "2020-01-01", "rankings": histories["rankings"]}
        with mock.patch.dict(os.environ, {"COC_DATA_DIR": str(directory)}):
            missing = recover.fill_profile(incoming)
            saved = json.loads(path.read_text(encoding="utf-8"))
            equal(saved["name"], "Owner's saved spelling")
            equal(saved["th"], 12)
            equal(saved["xp"], 100)
            equal(saved["date"], "manual date")
            equal(saved["location"], "Owner's country")
            equal(saved["country_code"], "IN")
            equal(saved["names"], ["Previous Name"])
            require(isinstance(missing, list) and "devices" in missing and "email_new" in missing,
                    "still-missing fields were not returned")
            before = path.read_bytes()
            incoming["tag"] = "#P0Y2LQRY"
            raises(ValueError, lambda: recover.fill_profile(incoming))
            equal(path.read_bytes(), before)
            path.write_text(json.dumps(template), encoding="utf-8")
            blank_before = path.read_bytes()
            raises(ValueError, lambda: recover.fill_profile(incoming))
            equal(path.read_bytes(), blank_before)
    suite.check("fill_profile: empty fields only and mismatched tag refusal", only_empty_fields)

    def official_tag_match():
        tag = "#P0Y2LQRR"
        source = recover.get_source("official_api")
        url = recover.source_url("official_api", TAG=tag[1:])
        mismatched = _fixture_live()
        mismatched["tag"] = "#P0Y2LQRY"
        matched = _fixture_live()
        responses = [net.Response(200, json.dumps(payload), True, "ok", 0.0, url, False)
                     for payload in (mismatched, matched)]
        with mock.patch.dict(os.environ, {"COC_API_BASE": source["base"],
                                           "COC_API_TOKEN": "synthetic-offline-fixture"}), \
                mock.patch.object(net, "fetch", side_effect=responses) as fetch:
            equal(recover.official(tag), None)
            equal(recover.official(tag.lower()), matched)
        equal(fetch.call_count, 2)
        require(all(call.args[0] == url for call in fetch.call_args_list),
                "official request did not use the registered source")
    suite.check("official: mismatched player rejected and matching player retained", official_tag_match)


def _readiness_checks(suite: Suite, readiness: object, net: object) -> None:
    profile = _fixture_profile()
    live = _fixture_live()

    def assess(changes=None, current=None, egress=None):
        owned = copy.deepcopy(profile)
        owned.update(changes or {})
        fetched = copy.deepcopy(live) if current is None else current
        country = {"country_code": "IN"} if egress is None else egress
        return readiness.assess(owned, lambda tag: fetched, lambda: country)

    base = assess()
    suite.check("readiness: complete fixture is 100/go", lambda: (
        equal(base.score, 100), equal(base.verdict, "go"), equal(base.blockers, []),
        require(all(check.state != "fail" for check in base.checks), "fail in go report"),
    ))
    suite.check("readiness: exact weighted checks", lambda: equal(
        {check.id: check.weight for check in base.checks if check.weight}, WEIGHTS
    ))
    suite.check("readiness: every check state is valid", lambda: require(
        all(check.state in STATES for check in base.checks), "invalid check state"
    ))
    suite.check("readiness: seven excluded countries", lambda: equal(
        set(readiness.EXCLUDED), {"BY", "RU", "CN", "IR", "VN", "CU", "KP"}
    ))
    for field, check_id, value in (
        ("name", "name_drift", "Different Name"),
        ("th", "th_drift", 13),
        ("clan", "clan_drift", "Different Clan"),
        ("tag", "tag_drift", "#P0Y2LQRY"),
    ):
        suite.check("readiness: " + check_id, lambda field=field, check_id=check_id, value=value:
                    _assert_blocker(assess({field: value}), check_id))
    suite.check("readiness: egress mismatch", lambda:
                _assert_blocker(assess(egress={"country_code": "US"}), "egress_mismatch"))
    suite.check("readiness: replacement missing", lambda:
                _assert_blocker(assess({"email_new": ""}), "missing_replacement_email"))
    suite.check("readiness: original and replacement equal", lambda:
                _assert_blocker(assess({"email_new": profile["email"]}), "replacement_equals_original"))
    suite.check("readiness: malformed replacement address", lambda:
                _assert_blocker(assess({"email_new": "not-an-address"}), "invalid_replacement_email"))
    for code in sorted(readiness.EXCLUDED):
        suite.check("readiness: excluded " + code, lambda code=code:
                    _assert_blocker(assess({"country_code": code}, egress={"country_code": code}), "excluded_country"))
    for changes, check_id, expected_score in (
        ({"ap": "unknown"}, "protection_known", 85),
        ({"receipts": []}, "receipts", 85),
        ({"devices": []}, "devices", 90),
    ):
        def warning_check(changes=changes, check_id=check_id, expected_score=expected_score):
            report = assess(changes)
            equal(_find_check(report, check_id).state, "warn")
            require(not any(check.state == "fail" for check in report.checks), "warning became failure")
            equal(report.score, expected_score)
            # gap:G21 Score policy is locally selected; this does not validate support acceptance.
            equal(report.verdict, "no-go")
        suite.check("readiness: warning " + check_id, warning_check)
    suite.check("readiness: single decoration warns", lambda: equal(
        _find_check(assess({"decorations": ["one dated decoration"]}), "single_decoration").state, "warn"
    ))
    suite.check("readiness: unknown live identity cannot pass", lambda: (
        equal(_find_check(assess(current={}), "identity_match").state, "warn"),
        equal(assess(current={}).verdict, "no-go"),
    ))
    suite.check("readiness: unknown egress cannot pass", lambda: (
        equal(_find_check(assess(egress={}), "egress_country").state, "warn"),
        equal(assess(egress={}).verdict, "no-go"),
    ))
    suite.check("readiness: no-go even if a caller constructs score100 plus fail", lambda: equal(
        readiness.Report(100, [readiness.Check("fixture_fail", 0, "fail", "synthetic blocker")], []).verdict,
        "no-go",
    ))
    suite.check("readiness: no-go when explicit blockers exist", lambda: equal(
        readiness.Report(100, [], ["synthetic blocker"]).verdict, "no-go"
    ))
    for score in (0, 69, 70, 85, 99):
        suite.check("readiness: only100 is go; score" + str(score), lambda score=score: equal(
            readiness.Report(score, [], []).verdict, "no-go"
        ))

    def json_cli():
        binding = readiness if hasattr(readiness, "raise_for_config") else net
        with mock.patch.object(binding, "raise_for_config", return_value=None), \
                mock.patch.object(readiness, "assess", return_value=base), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            code = readiness.main(["--json"])
        equal(code, 0)
        equal(json.loads(output.getvalue()), base.to_dict())

    def no_go_cli():
        report = assess({"devices": []})
        binding = readiness if hasattr(readiness, "raise_for_config") else net
        with mock.patch.object(binding, "raise_for_config", return_value=None), \
                mock.patch.object(readiness, "assess", return_value=report), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            code = readiness.main(["--json"])
        equal(code, 1)
        equal(json.loads(output.getvalue()), report.to_dict())

    def missing_config_cli():
        with mock.patch.dict(os.environ, {}, clear=False), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            os.environ.pop("COC_API_BASE", None)
            os.environ.pop("COC_API_TOKEN", None)
            equal(readiness.main(["--json"]), 2)

    suite.check("readiness: --json is exact Report serialization", json_cli)
    suite.check("readiness: no-go CLI exits1", no_go_cli)
    suite.check("readiness: missing config CLI exits2", missing_config_cli)


class FakeClock:
    """Advancing clock: retries and throttling never sleep in real time."""

    def __init__(self) -> None:
        self.value = 10000.0
        self.sleeps = []  # type: List[float]

    def monotonic(self) -> float:
        return self.value

    def time(self) -> float:
        return 1800000000.0 + self.value

    def sleep(self, seconds: float) -> None:
        require(seconds >= 0, "negative sleep")
        self.sleeps.append(seconds)
        self.value += seconds


def _net_checks(suite: Suite, net: object, sources: dict, temp: Path) -> None:
    selected = next(row for row in sources["sources"] if row["name"] == "clashking")
    url = selected["base"].rstrip("/") + selected["paths"][0].replace("%TAG%", "P0Y2LQRR")
    clock = FakeClock()
    calls = []
    statuses = []
    serial = [0]

    def transport(target, method, headers, data, timeout):
        serial[0] += 1
        calls.append((clock.value, method, target, data, dict(headers)))
        status = statuses.pop(0) if statuses else 200
        return status, json.dumps({"request": serial[0]}), target

    with mock.patch.dict(os.environ, {"COC_CACHE_PATH": str(temp / "net-cache.sqlite3")}), \
            mock.patch.object(net, "_request_once", side_effect=transport), \
            mock.patch.object(net, "_last_request_at", None), \
            mock.patch.object(net.time, "monotonic", side_effect=clock.monotonic), \
            mock.patch.object(net.time, "time", side_effect=clock.time), \
            mock.patch.object(net.time, "sleep", side_effect=clock.sleep):

        def cache_hit():
            before = len(calls)
            first = net.fetch(url, data={"fixture": "cache-hit"}, ttl=30)
            second = net.fetch(url, data={"fixture": "cache-hit"}, ttl=30)
            equal(len(calls) - before, 1)
            require(not first.cached and second.cached, "cached flag is incorrect")
            equal(first.body, second.body)
            require(second.ok and second.status == 200, "cached response metadata changed")
            require(second.elapsed >= 0, "negative elapsed")
        suite.check("net: public cache hit", cache_hit)

        def cache_key():
            before = len(calls)
            net.fetch(url, data={"fixture": "body-one"})
            net.fetch(url, data={"fixture": "body-two"})
            net.fetch(url, method="HEAD", data={"fixture": "body-one"})
            equal(len(calls) - before, 3)
        suite.check("net: cache key separates method and body", cache_key)

        def expiry():
            data = {"fixture": "expiry"}
            net.fetch(url, data=data, ttl=2)
            before = len(calls)
            clock.value += 3
            response = net.fetch(url, data=data, ttl=2)
            equal(len(calls) - before, 1)
            require(not response.cached, "expired cache was reused")
        suite.check("net: TTL expiry", expiry)

        def bypass_ttl():
            before = len(calls)
            net.fetch(url, ttl=0)
            net.fetch(url, ttl=0)
            equal(len(calls) - before, 2)
        suite.check("net: ttl0 bypasses cache", bypass_ttl)

        def unsuccessful_not_cached():
            before = len(calls)
            statuses[:] = [503, 200]
            data = {"fixture": "unsuccessful-cache"}
            equal(net.fetch(url, data=data, retries=0).status, 503)
            require(not net.fetch(url, data=data, retries=0).cached, "failure was cached")
            require(net.fetch(url, data=data, retries=0).cached, "successful response was not cached")
            equal(len(calls) - before, 2)
        suite.check("net: failed responses are never cached", unsuccessful_not_cached)

        def bypass_headers():
            for header in ("Authorization", "Cookie"):
                before = len(calls)
                net.fetch(url, headers={header: "synthetic-test-only"}, data={"fixture": header})
                net.fetch(url, headers={header: "synthetic-test-only"}, data={"fixture": header})
                equal(len(calls) - before, 2)
        suite.check("net: authenticated requests bypass cache", bypass_headers)

        def post_once():
            before = len(calls)
            statuses[:] = [503]
            response = net.fetch(url, method="POST", data={"fixture": "unsafe-retry"}, ttl=0, retries=3)
            equal(response.status, 503)
            equal(len(calls) - before, 1)
            before = len(calls)
            net.fetch(url, method="POST", data={"fixture": "post-cache"})
            net.fetch(url, method="POST", data={"fixture": "post-cache"})
            equal(len(calls) - before, 2)
        suite.check("net: POST is neither retried nor cached", post_once)

        for status in (0, 429, 502, 503, 504, 520, 522):
            def retry_case(status=status):
                before = len(calls)
                statuses[:] = [status, 200]
                response = net.fetch(url, ttl=0, retries=1)
                equal(response.status, 200)
                equal(len(calls) - before, 2)
            suite.check("net: safe request retries " + str(status), retry_case)

        def retry_backoff():
            before = len(clock.sleeps)
            statuses[:] = [503, 503, 200]
            response = net.fetch(url, ttl=0, retries=2)
            equal(response.status, 200)
            waits = clock.sleeps[before:]
            require(any(abs(wait - 1.0) < 1e-8 for wait in waits), "missing first exponential backoff")
            require(any(abs(wait - 2.0) < 1e-8 for wait in waits), "missing second exponential backoff")
        suite.check("net: retry backoff is1 then2", retry_backoff)

        for status in (400, 401, 403, 404, 500, 501):
            def no_retry_case(status=status):
                before = len(calls)
                statuses[:] = [status]
                response = net.fetch(url, ttl=0, retries=3)
                equal(response.status, status)
                equal(len(calls) - before, 1)
            suite.check("net: no retry for " + str(status), no_retry_case)

        suite.check("net: every physical request has0.4s spacing", lambda: require(
            all(b[0] - a[0] >= 0.4 - 1e-8 for a, b in zip(calls, calls[1:])),
            "physical request spacing below0.4 seconds",
        ))
        suite.check("net: real desktop browser User-Agent is sent", lambda: require(
            bool(calls) and all(
                "Mozilla/5.0" in call[4].get("User-Agent", "")
                and "Chrome/" in call[4].get("User-Agent", "")
                for call in calls
            ), "browser User-Agent missing",
        ))

    def response(status, body):
        return net.Response(
            status=status, body=body, ok=200 <= status < 300, verdict="ok",
            elapsed=0.0, url=url, cached=False,
        )

    cases = [
        ("json-short", {"json": True}, 200, "{}", "ok"),
        ("json-public-login-text", {"json": True}, 200, '{"name":"Login Password"}', "ok"),
        ("html-public-login-text", {"markers": ["owners"]}, 200,
         "<p>Login and password advice for owners</p>", "ok"),
        ("json-invalid", {"json": True}, 200, "{broken", "badjson"),
        ("unreachable", {}, 0, "", "unreachable"),
        ("forbidden", {}, 403, "denied", "blocked"),
        ("rate-limit", {}, 429, "limited", "blocked"),
        ("gone", {}, 404, "missing", "gone"),
        ("empty", {}, 200, " \n ", "empty"),
        ("auth", {"auth": True}, 200, "<form>Login Password</form>", "auth"),
        ("js", {"js": True, "markers": ["player"]}, 200, "<html>player</html>", "ok-js"),
        ("marked", {"markers": ["clan"]}, 200, "<html>Clan records</html>", "ok"),
        ("unmarked", {"markers": ["clan"]}, 200, "<html>Nothing recorded</html>", "unmarked"),
    ]
    for name, src, status, body, verdict in cases:
        suite.check("classify: " + name, lambda src=src, status=status, body=body, verdict=verdict:
                    equal(net.classify(src, response(status, body)), verdict))
    suite.check("classify: output vocabulary is fixed", lambda: require(
        all(net.classify(src, response(status, body)) in VERDICTS for _, src, status, body, _ in cases),
        "undocumented verdict",
    ))

    def malformed_response():
        opener = mock.Mock()
        opener.open.side_effect = net.http.client.BadStatusLine("synthetic invalid status")
        with mock.patch.object(net.urllib.request, "build_opener", return_value=opener):
            equal(net._request_once(url, "GET", {"User-Agent": net.UA}, None, 20), (0, "", url))
        equal(opener.open.call_count, 1)
    suite.check("net: malformed HTTP response becomes status0", malformed_response)

    def partial_response():
        opener = mock.Mock()
        reply = mock.MagicMock()
        reply.__enter__.return_value = reply
        reply.read.side_effect = net.http.client.IncompleteRead(b"partial", 100)
        opener.open.return_value = reply
        with mock.patch.object(net.urllib.request, "build_opener", return_value=opener):
            equal(net._request_once(url, "GET", {"User-Agent": net.UA}, None, 20), (0, "", url))
        equal(opener.open.call_count, 1)
    suite.check("net: partial successful body becomes status0", partial_response)

    def truncated_404():
        error = net.urllib.error.HTTPError(url, 404, "synthetic missing", {}, io.BytesIO(b"partial"))
        opener = mock.Mock()
        opener.open.side_effect = error
        with mock.patch.object(net.urllib.request, "build_opener", return_value=opener), \
                mock.patch.object(error, "read", side_effect=net.http.client.IncompleteRead(b"partial", 100)), \
                mock.patch.object(net, "_last_request_at", None):
            fetched = net.fetch(url, ttl=0, retries=3)
        equal(fetched.status, 404)
        equal(fetched.verdict, "gone")
        equal(opener.open.call_count, 1)
    suite.check("net: truncated404 retains its status and is never retried", truncated_404)


def _public_fetch_checks(suite: Suite, probe: object, scraper: object,
                         recover: object, net: object, config: dict, temp: Path) -> None:
    candidate = copy.deepcopy(next(source for source in config["sources"]
                                   if source["name"] == "clashking"))
    candidate["paths"] = candidate["paths"][:3]
    candidate.update({"json": True, "js": False, "auth": False, "blocked": True,
                      "verified_how": "unverified"})

    def observed(url, status=200, body="{}"):
        return net.Response(status, body, 200 <= status < 300, "ok", 0.0, url, False)

    def every_path_and_flags():
        statuses = iter((200, 404, 200))
        before = copy.deepcopy(candidate)
        with mock.patch.object(net, "fetch", side_effect=lambda url, **kwargs:
                               observed(url, next(statuses))) as fetch:
            rows, survivors, skipped = probe.probe("#P0Y2LQRR", {"sources": [candidate]})
        equal(skipped, 0)
        equal(len(rows), 3)
        equal(fetch.call_count, 3)
        equal([row["verdict"] for row in rows], ["ok", "gone", "ok"])
        require(all(set(row) == {"name", "url", "status", "verdict", "len"} for row in rows),
                "probe row schema changed")
        equal(len(survivors), 1)
        expected = copy.deepcopy(before)
        expected["paths"] = [before["paths"][0], before["paths"][2]]
        equal(survivors[0], expected)
        equal(candidate, before)
    suite.check("probe: one result per path and survivor flags preserved", every_path_and_flags)

    directory = temp / "public-fetch-cli"
    directory.mkdir()
    source_file = directory / "sources.json"
    single = copy.deepcopy(candidate)
    single["paths"] = single["paths"][:1]
    source_file.write_text(json.dumps({"sources": [single]}), encoding="utf-8")

    def probe_cli():
        with mock.patch.dict(os.environ, {"COC_DATA_DIR": str(directory)}), \
                mock.patch.object(net, "fetch", side_effect=lambda url, **kwargs: observed(url)), \
                contextlib.redirect_stdout(io.StringIO()):
            equal(probe.main(["#P0Y2LQRR", "--sources", str(source_file), "--write-sources"]), 0)
        with (directory / "probe_results.csv").open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            equal(reader.fieldnames, ["name", "url", "status", "verdict", "len"])
            equal(len(list(reader)), 1)
        saved = json.loads((directory / "sources.live.json").read_text(encoding="utf-8"))
        equal(saved["sources"], [single])
    suite.check("probe: CLI writes CSV and complete survivor metadata", probe_cli)

    def strict_gate():
        with mock.patch.dict(os.environ, {"COC_DATA_DIR": str(directory)}), \
                mock.patch.object(net, "fetch", side_effect=lambda url, **kwargs: observed(url)), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            equal(probe.main(["#P0Y2LQRR", "--sources", str(source_file), "--strict"]), 1)
    suite.check("probe: strict rejects an unverified source despite HTTP success", strict_gate)

    def zero_ok():
        with mock.patch.dict(os.environ, {"COC_DATA_DIR": str(directory)}), \
                mock.patch.object(net, "fetch", side_effect=lambda url, **kwargs: observed(url, 403)), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            equal(probe.main(["#P0Y2LQRR", "--sources", str(source_file)]), 1)
    suite.check("probe: zero ok responses exit1", zero_ok)

    structured = copy.deepcopy(single)
    structured.update({"blocked": False, "schema_verified": False})
    path = structured["paths"][0]
    structured["schema"] = {path: {"dates": ["events.*.date"], "tags": ["events.*.tag"],
                                    "clans": ["events.*.clan"]}}
    page = copy.deepcopy(next(source for source in config["sources"] if source["name"] == "clashspot"))
    page["paths"] = page["paths"][:1]
    page.update({"json": False, "js": False, "auth": False, "blocked": False,
                 "markers": ["clan"], "kind": "tracker"})
    blocked_sources = []
    for flag in ("js", "auth", "blocked"):
        skipped = copy.deepcopy(page)
        skipped["name"] = "fixture_skip_" + flag
        skipped[flag] = True
        blocked_sources.append(skipped)

    def extract_sources():
        json_url = recover.expand_source(structured, TAG="P0Y2LQRR")
        html_url = recover.expand_source(page, TAG="P0Y2LQRR")
        payload = json.dumps({"events": [{"date": "2025-02-03", "tag": "#P0Y2LQRR",
                                          "clan": "Mapped Clan"}],
                              "unmapped": "2020-01-01 #UNMAPPED"})
        markup = ("<html><script>2001-01-01 #BADSCRIPT</script>"
                  "<style>#BADSTYLE{display:none}</style><p>Clan: Test &amp; Co</p>"
                  "<p>2025-02-03 #P0Y2LQRR</p></html>")
        content = {json_url: payload, html_url: markup}
        sources = {"sources": blocked_sources + [structured, page]}
        with mock.patch.object(net, "fetch", side_effect=lambda url, **kwargs:
                               observed(url, body=content[url])) as fetch:
            records, stats = scraper.scrape("#P0Y2LQRR", sources)
        equal(fetch.call_count, 2)
        equal(stats["answered"], 2)
        equal(len(records), 2)
        by_name = {record["source"]: record for record in records}
        json_record, html_record = by_name[structured["name"]], by_name[page["name"]]
        for record in records:
            equal(set(record), {"source", "url", "dates", "tags", "clans", "excerpt", "fetched_at"})
            equal(record["dates"], ["2025-02-03"])
            equal(record["tags"], ["#P0Y2LQRR"])
            dt.datetime.fromisoformat(record["fetched_at"].replace("Z", "+00:00"))
        equal(json_record["clans"], ["Mapped Clan"])
        equal(html_record["clans"], ["Test & Co"])
        require("BADSCRIPT" not in html_record["excerpt"] and "BADSTYLE" not in html_record["excerpt"],
                "script or style content became evidence")
        require("unconfirmed" in json_record["excerpt"], "candidate schema was presented as confirmed")
    suite.check("scrape: flags, schema selection, HTML stripping, and output schema", extract_sources)

    def empty_scrape():
        empty_file = directory / "skipped-sources.json"
        empty_file.write_text(json.dumps({"sources": blocked_sources}), encoding="utf-8")
        errors = io.StringIO()
        with mock.patch.dict(os.environ, {"COC_DATA_DIR": str(directory)}), \
                mock.patch.object(net, "fetch", side_effect=AssertionError("flagged source was fetched")), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
            equal(scraper.main(["#P0Y2LQRR", "--sources", str(empty_file)]), 0)
        equal(json.loads((directory / "external.json").read_text(encoding="utf-8")), [])
        require("does not prove" in errors.getvalue(), "empty result was not explained")
    suite.check("scrape: all skipped writes empty array, explains it and exits0", empty_scrape)

    def bad_tag_kind():
        broken = copy.deepcopy(single)
        broken["tag_kind"] = "village"
        bad_file = directory / "bad-kind-sources.json"
        bad_file.write_text(json.dumps({"sources": [broken]}), encoding="utf-8")
        raises(net.ConfigError, lambda: recover.load_sources(str(bad_file)))
    suite.check("schema: sources tag_kind must be player or clan", bad_tag_kind)

    def unreadable_registry():
        with mock.patch.dict(os.environ, {"COC_DATA_DIR": str(directory)}), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            equal(scraper.main(["#P0Y2LQRR", "--sources", str(directory / "absent.json")]), 2)
    suite.check("scrape: unreadable registry exits2 instead of writing empty", unreadable_registry)

    clan_source = copy.deepcopy(page)
    clan_source["name"] = "fixture_clan"
    clan_source["paths"] = ["/Clan/%TAG%/Members.json"]
    clan_source.update({"json": True, "tag_kind": "clan"})

    def clan_without_flag():
        with mock.patch.object(net, "fetch", side_effect=AssertionError("clan source was fetched")):
            records, stats = scraper.scrape("#P0Y2LQRR", {"sources": [clan_source]})
        equal(records, [])
        equal(stats["clan_skipped"], 1)
        require("--clan" in scraper.empty_reason(stats), scraper.empty_reason(stats))
    suite.check("scrape: clan-scoped source waits for --clan", clan_without_flag)

    def clan_with_flag():
        seen = []
        with mock.patch.object(net, "fetch", side_effect=lambda url, **kwargs:
                               seen.append(url) or observed(url, body="{}")):
            scraper.scrape("#P0Y2LQRR", {"sources": [clan_source]}, "2PP")
        equal(len(seen), 1)
        require(seen[0].endswith("/Clan/2PP/Members.json"), seen[0])
    suite.check("scrape: --clan fills the clan route", clan_with_flag)

    def probe_skips_clan():
        with mock.patch.object(net, "fetch", side_effect=AssertionError("clan source was fetched")):
            rows, survivors, skipped = probe.probe("#P0Y2LQRR", {"sources": [clan_source]})
        equal((rows, survivors, skipped), ([], [], 1))
    suite.check("probe: clan-scoped source waits for --clan", probe_skips_clan)

    def probe_uses_clan():
        seen = []
        with mock.patch.object(net, "fetch", side_effect=lambda url, **kwargs:
                               seen.append(url) or observed(url)):
            rows, _, _ = probe.probe("#P0Y2LQRR", {"sources": [clan_source]}, "2PP")
        equal(len(rows), 1)
        require(seen[0].endswith("/Clan/2PP/Members.json"), seen[0])
    suite.check("probe: --clan fills the clan route", probe_uses_clan)

    def both_gates_message():
        attempts_module = importlib.import_module("attempts")
        gate = temp / "both-gates"
        gate.mkdir()
        now = dt.datetime.now(dt.timezone.utc)
        history = [{"at": (now - dt.timedelta(days=26)).isoformat(), "outcome": "unknown",
                    "event": "start", "ticket_id": "t", "note": ""},
                   {"at": (now - dt.timedelta(days=5)).isoformat(), "outcome": "closed",
                    "event": "status", "ticket_id": "t", "note": ""}]
        (gate / "attempts.json").write_text(json.dumps(history), encoding="utf-8")
        with mock.patch.dict(os.environ, {"COC_DATA_DIR": str(gate)}):
            try:
                attempts_module.start_ticket("second")
            except attempts_module.AttemptError as error:
                text = str(error)
            else:
                raise AssertionError("a second ticket was accepted")
        require("already recorded" in text and "cooldown" in text, text)
    suite.check("attempts: both gates name the cooldown and the single ticket", both_gates_message)



def _run(root: Path, suite: Suite, temp: Path) -> None:
    for name in MODULES:
        suite.check("import: " + name, lambda name=name: _clean_import(root, name))
    modules = {name: importlib.import_module(name) for name in MODULES}
    net, recover = modules["net"], modules["coc_recover"]
    readiness, attempts = modules["readiness"], modules["attempts"]
    driver, builder = modules["support_driver"], modules["build"]

    for name in ("sources.json", "obstacles.json", "profile.json", "gaps.csv"):
        shutil.copyfile(root / name, temp / name)

    for path in sorted(root.glob("*.py")):
        def syntax_and_doc(path=path):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 9))
            documentation = ast.get_docstring(tree) or ""
            require("exit" in documentation.lower() and "code" in documentation.lower(),
                    "module docstring must name its exit codes")
        suite.check("Python3.9 syntax and exit docs: " + path.name, syntax_and_doc)

    config = json.loads((root / "sources.json").read_text(encoding="utf-8"))
    if isinstance(config, list):
        config = {"sources": config}
    if isinstance(config, list):
        config = {"sources": config}
    obstacles = json.loads((root / "obstacles.json").read_text(encoding="utf-8"))
    template = json.loads((root / "profile.json").read_text(encoding="utf-8"))
    with (root / "gaps.csv").open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        gaps = list(reader)

    suite.check("schema: sources", lambda: _source_schema(config))
    suite.check("schema: obstacles ascending", lambda: _obstacle_schema(obstacles))
    suite.check("schema: reversed obstacle dates are rejected", lambda: raises(
        AssertionError, lambda: _obstacle_schema({
            "markers": [{"name": "later", "date": "2020-01-02"}, {"name": "earlier", "date": "2020-01-01"}],
            "structural": [],
        })
    ))
    suite.check("schema: profile template exact fields", lambda: equal(set(template), set(_fixture_profile())))
    suite.check("schema: profile AP defaults unknown", lambda: equal(template["ap"], "unknown"))
    suite.check("schema: profile lists", lambda: require(
        all(isinstance(template[key], list) for key in ("devices", "receipts", "names")), "profile list expected"
    ))
    suite.check("schema: gaps exact header", lambda: equal(header, GAP_HEADER))
    suite.check("schema: gaps count and four nonblocking", lambda: (
        require(len(gaps) >= 18, "fewer than18 gaps"),
        equal(sum(row["blocking"] == "no" for row in gaps), 4),
        require(all(row["blocking"] in ("yes", "no") for row in gaps), "invalid blocking flag"),
    ))
    gap_ids = {row["id"] for row in gaps}
    suite.check("schema: unique nonempty gap IDs", lambda: (
        equal(len(gap_ids), len(gaps)), require("" not in gap_ids, "blank gap ID")
    ))
    suite.check("schema: affected files exist", lambda: require(
        all(row["affects_files"] and all((root / name).is_file() for name in row["affects_files"].split("|"))
            for row in gaps), "gap refers to a missing file"
    ))
    source_names = {row["name"] for row in config["sources"]}
    suite.check("source audit: no external URL literals outside API-base constants", lambda: _url_literal_audit(root))
    suite.check("source audit: HTTP imports only in net", lambda: _only_net_http(root))
    suite.check("source audit: config call sites", lambda: _config_call_sites(root))

    booleans = recover.parse_changes([{
        "time": "2026-01-02T03:04:05Z", "type": "name", "item": {"name": "Latest"},
        "previous": True, "current": False,
    }])
    suite.check("parse_changes: boolean values preserved", lambda: (
        equal(len(booleans), 1), equal(booleans[0]["value"], "Latest"),
        require(booleans[0]["previous"] is True, "previous boolean lost"),
        require(booleans[0]["current"] is False, "current false lost"),
        equal(set(booleans[0]), {"time", "type", "value", "previous", "current"}),
    ))
    strings = recover.parse_changes([{
        "time": "2025-01-01", "type": "name", "item": {"name": "Second"},
        "previous": "First", "current": "Second",
    }])
    suite.check("parse_changes: string schema", lambda: (
        equal(strings[0]["previous"], "First"), equal(strings[0]["current"], "Second"),
        equal(strings[0]["value"], "Second"),
    ))
    suite.check("parse_changes: empty input", lambda: equal(recover.parse_changes([]), []))
    war = recover.parse_war([{
        "warEndTime": "20260102T030405.000Z", "defendingClanTag": "#P0Y2LQ",
        "stars": 0, "destructionPercentage": 0.0, "extra": "ignored",
    }])
    suite.check("parse_war: zero values and exact keys", lambda: (
        equal(len(war), 1), equal(war[0]["stars"], 0),
        equal(war[0]["destructionPercentage"], 0.0),
        equal(set(war[0]), {"warEndTime", "defendingClanTag", "stars", "destructionPercentage"}),
    ))
    suite.check("parse_war: empty input", lambda: equal(recover.parse_war([]), []))
    suite.check("bracket: unknown endpoints", lambda: equal(recover.bracket([], []), (None, None)))
    suite.check("bracket: tightest bounds", lambda: equal(
        recover.bracket(["2020-01-01", "2021-01-01"], ["2025-01-01", "2024-01-01"]),
        ("2021-01-01", "2024-01-01"),
    ))
    suite.check("bracket: additional floor moves only forward", lambda: equal(
        recover.bracket(["2020-01-01", "2022-01-01"], ["2025-01-01"]),
        ("2022-01-01", "2025-01-01"),
    ))
    suite.check("bracket: additional ceiling moves only backward", lambda: equal(
        recover.bracket(["2020-01-01"], ["2025-01-01", "2023-01-01"]),
        ("2020-01-01", "2023-01-01"),
    ))
    suite.check("bracket: contradiction rejected", lambda: raises(
        ValueError, lambda: recover.bracket(["2026-01-01"], ["2025-01-01"])
    ))
    suite.check("bracket: invalid calendar date rejected", lambda: raises(
        ValueError, lambda: recover.bracket(["2025-02-30"], [])
    ))

    _dossier_checks(suite, recover, net, template, temp)
    _readiness_checks(suite, readiness, net)

    now = dt.datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
    suite.check("attempts: COSTLY exact membership", lambda: equal(
        attempts.COSTLY, {"closed", "locked", "refused"}
    ))
    suite.check("attempts: no history", lambda: equal(attempts.remaining_days([], now), 0))
    for age, expected in ((0, 31), (12, 19), (31, 0), (40, 0)):
        def cooldown_case(age=age, expected=expected):
            entries = [{"timestamp": (now - dt.timedelta(days=age)).isoformat(), "outcome": "closed", "note": ""}]
            equal(attempts.remaining_days(entries, now), expected)
            require(type(attempts.cooldown(entries, now)) is str, "cooldown is not text")
        suite.check("attempts: cooldown age" + str(age), cooldown_case)
    suite.check("attempts: fractional days round upward", lambda: equal(
        attempts.remaining_days([{
            "timestamp": (now - dt.timedelta(days=12, hours=1)).isoformat(),
            "outcome": "locked", "note": "",
        }], now), 19
    ))
    suite.check("attempts: newest costly entry wins; later success ignored", lambda: equal(
        attempts.remaining_days([
            {"timestamp": (now - dt.timedelta(days=40)).isoformat(), "outcome": "closed"},
            {"timestamp": now.isoformat(), "outcome": "recovered"},
            {"timestamp": (now - dt.timedelta(days=12)).isoformat(), "outcome": "refused"},
        ], now), 19
    ))
    suite.check("attempts: non-costly outcomes do not start cooldown", lambda: equal(
        attempts.remaining_days([
            {"timestamp": now.isoformat(), "outcome": outcome, "note": ""}
            for outcome in ("recovered", "abandoned", "unknown")
        ], now), 0
    ))
    suite.check("attempts: malformed costly timestamp blocks arithmetic", lambda: raises(
        attempts.AttemptError, lambda: attempts.remaining_days([{"outcome": "closed", "timestamp": "bad"}], now)
    ))
    suite.check("attempts: malformed costly timestamp returns unresolved text", lambda: require(
        "unresolved" in attempts.cooldown([{"outcome": "locked"}], now),
        "invalid history was reported as ready",
    ))

    def one_ticket():
        directory = temp / "one-ticket"
        directory.mkdir()
        with mock.patch.dict(os.environ, {"COC_DATA_DIR": str(directory)}), \
                contextlib.redirect_stdout(io.StringIO()):
            first = attempts.start_ticket("owner's one support ticket")
            equal(attempts.current_ticket()["ticket_id"], first["ticket_id"])
            raises(attempts.AttemptError, lambda: attempts.start_ticket("duplicate"))
            equal(attempts.log("unknown", "still in progress"), 0)
            equal(attempts.current_ticket()["ticket_id"], first["ticket_id"])
            equal(attempts.log("recovered", "owner confirmed outcome"), 0)
            equal(attempts.current_ticket(), None)
            raises(attempts.AttemptError, lambda: attempts.start_ticket("second after success"))
            entries = attempts.read_entries()
            equal(sum(entry.get("event") == "start" for entry in entries), 1)
            require(not (directory / ".attempts.lock").exists(), "local mutation lock leaked")
    suite.check("attempts: only one ticket, including after its closure", one_ticket)

    questions = driver.QS
    ids = [question.id for question in questions]
    suite.check("support: required identity first", lambda: (
        equal(ids[:4], ["tag", "name", "th", "clan"]),
        require(all(question.required for question in questions[:4]), "identity question not required"),
    ))
    suite.check("support: email then inbox code before corroboration", lambda: equal(ids[4:6], ["email_new", "email_code"]))
    suite.check("support: steps are ordered", lambda: equal(
        [question.step for question in questions], sorted(question.step for question in questions)
    ))
    suite.check("support: all question sources resolve", lambda: require(
        all(question.source in source_names | gap_ids for question in questions), "unresolved question source"
    ))
    suite.check("support: question IDs unique", lambda: equal(len(set(ids)), len(ids)))

    def transcript_redaction():
        profile = _fixture_profile()
        profile["email_code"] = "synthetic_secret_do_not_store"
        rendered = driver.render(profile, True)
        require(type(rendered) is str, "render did not return text")
        require(profile["email_code"] not in rendered, "inbox code leaked into worksheet")
        output_path = temp / "worksheet.txt"
        driver.write_transcript(profile, output_path)
        text = output_path.read_text(encoding="utf-8")
        require(profile["email_code"] not in text, "inbox code persisted")
        require("*" in rendered, "required marker absent")
        require(all(question.source in rendered for question in questions), "per-line source not printed")
    suite.check("support: worksheet sources and secret exclusion", transcript_redaction)
    suite.check("support: blank marker", lambda: require("!" in driver.render(template, True), "blank marker absent"))
    suite.check("paste_block: returns text", lambda: require(
        type(recover.paste_block(_fixture_profile())) is str, "paste_block returned non-text"
    ))

    def missing_build_files():
        directory = temp / "missing-build"
        directory.mkdir()
        raises(builder.BuildError, lambda: builder.build(directory, allow_gaps=True))
        require(not (directory / builder.ARCHIVE_NAME).exists(), "archive written despite missing files")
        require(not (directory / builder.MANIFEST_NAME).exists(), "manifest written despite missing files")
    suite.check("build: missing files refuse without artifacts", missing_build_files)

    def blocking_build_gaps():
        directory = temp / "blocked-build"
        directory.mkdir()
        for name in builder.REQUIRED:
            shutil.copyfile(root / name, directory / name)
        raises(builder.BuildError, lambda: builder.build(directory))
        require(not (directory / builder.ARCHIVE_NAME).exists(), "archive written despite blocking gaps")
        require(not (directory / builder.MANIFEST_NAME).exists(), "manifest written despite blocking gaps")
        with contextlib.redirect_stdout(io.StringIO()):
            equal(builder.main(["--root", str(directory)]), 1)
    suite.check("build: blocking gaps refuse by default", blocking_build_gaps)
    suite.check("build: exact17-file source allowlist", lambda: equal(len(builder.REQUIRED), 17))
    _net_checks(suite, net, config, temp)
    _public_fetch_checks(suite, modules["probe"], modules["scrape"], recover, net, config, temp)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run all offline checks; always preserve failure lines and a failing exit."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        print("Usage: python selftest.py")
        return 2
    root = Path(__file__).resolve().parent
    suite = Suite()
    previous_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.addaudithook(_deny_network)
    with tempfile.TemporaryDirectory(prefix="coc-selftest-") as directory:
        temporary = Path(directory)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COC_API_BASE", None)
            os.environ.pop("COC_API_TOKEN", None)
            os.environ["COC_DATA_DIR"] = str(temporary)
            os.environ["COC_CACHE_PATH"] = str(temporary / "isolated-cache.sqlite3")
            try:
                _run(root, suite, temporary)
            except Exception as exc:
                suite.total += 1
                suite.failures.append("suite setup")
                print("FAIL suite setup: " + type(exc).__name__ + ": " + str(exc))
            finally:
                sys.dont_write_bytecode = previous_bytecode
    if suite.total < 25:
        suite.failures.append("minimum check count")
        print("FAIL minimum check count: " + str(suite.total))
    if suite.failures:
        print("FAIL " + str(len(suite.failures)) + " of " + str(suite.total) + " checks")
        return 1
    print("PASS " + str(suite.total) + " offline checks; network disabled; no token used")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

