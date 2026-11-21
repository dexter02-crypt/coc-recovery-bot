#!/usr/bin/env python3
"""Apply the SCID + transport changes to coc-recovery-bot.

Run from the repo root after the zips are unpacked. Idempotent.
"""
import ast
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(".").resolve()

NEW_SCID = '''SCID = "https://ingame.id.supercell.com/api"
COC = "magic"
SCID_GAMES = {"magic": "Clash of Clans", "scroll": "Clash Royale",
              "laser": "Brawl Stars", "soil": "Hay Day", "reef": "Boom Beach"}


def _scid_post(path, form, token=None):
    h = {"Content-Type": "application/x-www-form-urlencoded",
         "Accept": "application/json", "User-Agent": "coc-recover/1.0"}
    if token:
        h["Authorization"] = "Bearer " + token
    body = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(SCID + path, data=body, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode() or "{}")
        except Exception:
            return {"ok": False, "error": "http_%s" % e.code}
    except Exception as e:
        return {"ok": False, "error": "transport_%s" % type(e).__name__}


def _data(r):
    d = r.get("data")
    return d if isinstance(d, dict) else {}


def scid(email, pin=None, game=COC, lang="en", quiet=False):
    """Probe an email against Supercell ID and report the bound tag.

    Returns {"email","game","stage","ok","error","isValid","isBound","tag",
    "name","scid","created","links"}. login alone only proves the address is
    accepted; tag and name come back from login.validate, and only if isBound.
    """
    out = {"email": email, "game": game, "stage": "login", "ok": False,
           "error": None, "tag": None, "name": None, "created": None}
    base = {"email": email, "env": "prod", "game": game, "lang": lang}

    r = _scid_post("/account/login", base)
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

    # doc specifies email+pin only here; game context is undocumented, so try
    # minimal first and only widen if the minimal body is rejected
    out["stage"] = "validate"
    v = _scid_post("/account/login.validate", {"email": email, "pin": pin})
    if not v.get("ok"):
        v = _scid_post("/account/login.validate", dict(base, pin=pin))
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
            print("\\nBOUND TAG: %s  NAME: %s" % (out["tag"], out["name"]))
        if not quiet and not d.get("isBound"):
            print("isBound false - address is valid but nothing hangs off it")
    elif not v.get("ok"):
        out["error"] = v.get("error") or "validate_failed"

    if not d.get("isBound"):
        return out

    out["stage"] = "confirm"
    c = _scid_post("/account/login.confirm", {"email": email, "pin": pin})
    if not c.get("ok"):
        c = _scid_post("/account/login.confirm", dict(base, pin=pin))
    cd = _data(c)
    tok = cd.get("scid")
    if not tok:
        out["error"] = c.get("error") or "confirm_failed"
        return out
    out["scid"] = tok
    if not quiet:
        print("\\nscid:", tok[:40] + "...")

    hdr = {"scid_token": cd.get("scidToken", "")}
    s = _scid_post("/account/settings.get", hdr, token=tok)
    out["created"] = _data(s).get("created")
    if out["created"] and not quiet:
        print("SCID CREATED: " + out["created"])

    l = _scid_post("/account/links.get", hdr, token=tok)
    links = _data(l).get("links")
    if isinstance(links, list):
        out["links"] = [x.get("system") for x in links if isinstance(x, dict)]
        if not quiet:
            print("links:", out["links"])
    return out


'''

NEW_NET = '''
# --- clashking failover -----------------------------------------------------
# api.clashk.ing is behind Cloudflare and returns 522 under load. A 522 is not
# a dead account: retry it, then fail over to the official API. Redirects are
# never followed off-host, because urllib would drop the bearer header on a
# cross-host hop.
CK = "https://api.clashk.ing"
OFFICIAL = "https://api.clashofclans.com/v1"
RETRYABLE = {408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}
REDIRECT = {301, 302, 303, 307, 308}
BACKOFF = (0.6, 1.5, 3.5)
CK_COOLDOWN = 90.0

_ck_slots = threading.BoundedSemaphore(2)   # clashlens caps at two; respect it
_ck_until = [0.0]
_ck_lock = threading.Lock()


class OffHostRedirect(Exception):
    pass


class _SameHost(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        a = urllib.parse.urlsplit(req.full_url)
        b = urllib.parse.urlsplit(newurl)
        if a.netloc.lower() != b.netloc.lower():
            return None          # None -> urllib raises HTTPError carrying the 3xx
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SameHost)


def _ck_up():
    with _ck_lock:
        return time.time() >= _ck_until[0]


def _ck_trip():
    with _ck_lock:
        _ck_until[0] = time.time() + CK_COOLDOWN


def _call(base, path, token, method="GET", body=None):
    h = {"Accept": "application/json", "User-Agent": "coc-recover/1.0",
         "Authorization": "Bearer " + token}
    if body is not None:
        h["Content-Type"] = "application/json"
        body = json.dumps(body).encode()
    last = None
    for wait in (0.0,) + BACKOFF:
        if wait:
            time.sleep(wait + random.random() / 3)
        try:
            req = urllib.request.Request(base + path, data=body,
                                         headers=h, method=method)
            with _opener.open(req, timeout=20) as r:
                return r.status, json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            if e.code in REDIRECT:
                raise OffHostRedirect("%s -> %s" % (path, e.headers.get("Location")))
            if e.code in RETRYABLE:
                last = e
                continue
            try:
                return e.code, json.loads(e.read().decode() or "{}")
            except Exception:
                return e.code, {"ok": False, "error": "http_%s" % e.code}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            continue
    raise last


def __NAME__(path, token, allow_official=True):
    """GET an official-shaped path, e.g. "/players/%23TAG"."""
    if _ck_up():
        with _ck_slots:
            try:
                return _call(CK, path, token)
            except OffHostRedirect:
                _ck_trip()
            except Exception:
                _ck_trip()
    if not allow_official:
        raise RuntimeError("clashking unavailable, failover disabled")
    return _call(OFFICIAL, path, token)
'''

SOURCES = [
    {"name": "scid", "base": "https://ingame.id.supercell.com", "json": True,
     "paths": ["/api/account/login", "/api/account/login.validate"],
     "verified_how": "docs-page", "date_checked": "2026-11-21", "blocking": "yes",
     "note": "form-encoded only; game=magic is CoC per the doc's own table; "
             "validate returns application.account/username = tag+name. "
             "Doc is 2022, drift unverified"},
    {"name": "fwastats-player", "base": "https://fwastats.com",
     "paths": ["/Player/%TAG%"], "auth": True,
     "verified_how": "github-code-reference", "date_checked": "2026-11-21",
     "note": "class-level [Authorize] on PlayersController; %TAG% is bare, "
             "LinkIdToTag strips # and maps O->0; renders NameChange and "
             "TH-upgrade events"},
    {"name": "fwastats-data", "base": "https://fwastats.com",
     "paths": ["/Clan/%TAG%/Members.json"], "auth": False, "json": True,
     "verified_how": "github-code-reference", "date_checked": "2026-11-21",
     "note": "NO login: DataController has no class-level [Authorize], only "
             "Index() does. README's 'Data requires auth' is the docs page"},
]


def one(pattern, required=True):
    hits = sorted((p for p in ROOT.rglob(pattern) if ".git" not in p.parts),
                  key=lambda p: len(p.parts))
    if not hits:
        if required:
            sys.exit("missing %s - unpack the zip first" % pattern)
        return None
    return hits[0]


def ensure_imports(src):
    need = ["json", "random", "sys", "threading", "time",
            "urllib.error", "urllib.parse", "urllib.request"]
    tree = ast.parse(src)
    present, last = set(), 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last = max(last, node.end_lineno)
            if isinstance(node, ast.Import):
                present.update(a.name for a in node.names)
    add = ["import " + m for m in need if m not in present]
    if not add:
        return src, []
    lines = src.splitlines(keepends=True)
    lines.insert(last, "".join(a + "\n" for a in add))
    return "".join(lines), [a.split()[-1] for a in add]


def rewrite_scid(path):
    src = path.read_text()
    if "def _scid_post(" in src:
        return "already patched"
    tree = ast.parse(src)
    fn = next((n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == "scid"), None)
    if fn is None:
        sys.exit("no top-level scid() in %s" % path)
    start = fn.lineno - 1
    if fn.decorator_list:
        start = min(d.lineno for d in fn.decorator_list) - 1
    lines = src.splitlines(keepends=True)
    path.write_text("".join(lines[:start]) + NEW_SCID + "".join(lines[fn.end_lineno:]))

    src, added = ensure_imports(path.read_text())

    if "--pin" not in src:
        args = list(re.finditer(r"^[ \t]*(\w+)\.add_argument\(", src, re.M))
        if args:
            pname = args[-1].group(1)
            at = src[:args[-1].start()].count("\n") + 1
            ins = ('    %s.add_argument("--pin", help="six-digit code from the inbox")\n'
                   '    %s.add_argument("--game", default=COC, choices=sorted(SCID_GAMES),\n'
                   '    %s               help="game codename, default magic (Clash of Clans)")\n'
                   '    %s.add_argument("--json", action="store_true",\n'
                   '    %s               help="dump the result dict")\n'
                   % ((pname,) * 5))
            lines = src.splitlines(keepends=True)
            lines.insert(at, ins)
            src = "".join(lines)
        else:
            print("  ! no add_argument calls found - add --pin by hand")

    m = re.search(r"^([ \t]*)elif\s+n\.cmd\s*==\s*[\"']scid[\"']\s*:[ \t]*\n", src, re.M)
    if m:
        indent = m.group(1)
        after = src[m.end():]
        body = []
        for line in after.splitlines(keepends=True):
            if line.strip() and not line.startswith(indent + " "):
                break
            body.append(line)
        new_body = (indent + "    _r = scid(n.arg, n.pin, n.game)\n"
                    + indent + "    if n.json:\n"
                    + indent + "        print(json.dumps(_r, indent=2))\n"
                    + indent + '    sys.exit(0 if _r["ok"] else 1)\n')
        src = src[:m.end()] + new_body + after[sum(len(b) for b in body):]
    else:
        print('  ! no \'elif n.cmd == "scid"\' dispatch - wire --pin by hand')

    path.write_text(src)
    return "rewrote scid(); imports %s" % (", ".join(added) or "none needed")


def patch_net(path):
    src = path.read_text()
    if "class OffHostRedirect" in src:
        return "already patched"
    name = "get_api" if re.search(r"^def get\(", src, re.M) else "get"
    src, added = ensure_imports(src.rstrip("\n") + "\n" + NEW_NET.replace("__NAME__", name))
    path.write_text(src)
    if name == "get_api":
        hits = subprocess.run(
            ["grep", "-rn", "--include=*.py", "net.get(", "."],
            capture_output=True, text=True).stdout.strip()
        return "added as get_api() (net.get exists); switch callers:\n" + (hits or "  none found")
    return "appended transport as get()"


def patch_sources():
    out = []
    for f in [p for p in ROOT.rglob("sources*.json") if ".git" not in p.parts]:
        try:
            data = json.loads(f.read_text() or "[]")
        except json.JSONDecodeError:
            print("  ! %s is not valid JSON, skipped" % f)
            continue
        if isinstance(data, dict):
            data = data.get("sources", [])
        names = {d.get("name") for d in data if isinstance(d, dict)}
        add = [s for s in SOURCES if s["name"] not in names]
        if not add:
            out.append("%s: current" % f)
            continue
        f.write_text(json.dumps(data + add, indent=2) + "\n")
        out.append("%s: +%d" % (f, len(add)))
    return "; ".join(out) or "no sources file found"


def main():
    rec = one("coc_recover.py")
    net = one("net.py", required=False)
    print("coc_recover.py:", rewrite_scid(rec))
    if net:
        print("net.py:", patch_net(net))
    print("sources:", patch_sources())
    (ROOT / ".gitignore").write_text("__pycache__/\n*.pyc\n*.sqlite\n.env\nlogs/\n")
    r = subprocess.run([sys.executable, "-m", "py_compile", str(rec)]
                       + ([str(net)] if net else []), capture_output=True, text=True)
    if r.returncode:
        sys.exit("compile failed:\n" + r.stderr)
    print("compile ok")


main()