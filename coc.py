"""Command-line entry point. Exit codes: 0 success, 1 manual-only/no-go, 2 configuration.

Importing this module performs no configuration checks, file access or requests.
"""
from __future__ import annotations

import argparse
import json
import sys

import coc_recover
import net


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Prepare owner-held evidence for one recovery ticket")
    commands = parser.add_subparsers(dest="command", required=True)
    report_parser = commands.add_parser("report", help="Collect public records and write a local dossier")
    report_parser.add_argument("tag")
    report_parser.add_argument("--open", action="store_true", dest="open_it")
    commands.add_parser("paste", help="Print the owner's evidence statement")
    scid_parser = commands.add_parser("scid", help="Probe an address against the private Supercell ID routes")
    scid_parser.add_argument("email")
    scid_parser.add_argument("--pin", "--code", dest="pin", default=None,
                             help="six-digit inbox code; omit to only request it")
    scid_parser.add_argument("--game", default=coc_recover.COC,
                             choices=sorted(coc_recover.SCID_GAMES),
                             help="game codename, default magic (Clash of Clans)")
    scid_parser.add_argument("--json", action="store_true",
                             help="machine-readable result only")
    verify_parser = commands.add_parser("verify", help="Explain the disabled token-verification operation")
    verify_parser.add_argument("tag")
    verify_parser.add_argument("token", help="Never sent, saved or echoed")
    takeout_parser = commands.add_parser("takeout", help="Index candidate files in an owner-provided local export")
    takeout_parser.add_argument("root")
    args = parser.parse_args(argv)
    try:
        if args.command == "report":
            net.raise_for_config()
            print(coc_recover.report(args.tag, args.open_it), end="")
        elif args.command == "paste":
            print(coc_recover.paste_block(coc_recover.load_profile()))
        elif args.command == "scid":
            # gap:G17 Documented private routes; not a supported API.
            result = coc_recover.scid(args.email, args.pin, args.game,
                                      quiet=args.json)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["ok"] else 1
        elif args.command == "verify":
            # gap:G12 An unconfirmed verification route cannot assert ownership.
            print(coc_recover.verify(args.tag, args.token))
            return 1
        elif args.command == "takeout":
            print(coc_recover.takeout(args.root))
    except (net.ConfigError, ValueError, OSError) as error:
        print("Configuration error: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
