"""Command-line entry point. Exit codes: 0 success, 1 manual-only/no-go, 2 configuration.

Importing this module performs no configuration checks, file access or requests.
"""
from __future__ import annotations

import argparse
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
    scid_parser = commands.add_parser("scid", help="Explain the manual Supercell ID sign-in step")
    scid_parser.add_argument("email")
    scid_parser.add_argument("--code", default=None, help="Ignored; enter inbox codes only in the game")
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
            # gap:G17 This command does not call private Supercell ID APIs.
            print(coc_recover.scid(args.email, args.code))
            return 1
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
