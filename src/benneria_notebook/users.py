"""
benneria-user: the notebook's accounts, made and managed from the command line (the site has no
sign-up page). Works on the same database as the server ($BENNERIA_NOTEBOOK_DB, see store.py),
which can keep running meanwhile.

    uv run benneria-user add NAME        # asks for the password twice
    uv run benneria-user passwd NAME     # a new password; logs out the account's sessions
    uv run benneria-user remove NAME     # the account and all its notebooks, after confirmation
    uv run benneria-user list

In the container: docker compose exec benneria benneria-user add NAME

The notes written before accounts existed belong to the first account added.
"""

import argparse
import getpass
import sys

from .store import FIRST_USER, Store

MIN_PASSWORD = 8
MAX_NAME = 64


def check_name(name):
    name = name.strip()
    if not name or len(name) > MAX_NAME or any(not c.isprintable() for c in name):
        sys.exit(f"A name is 1 to {MAX_NAME} printable characters")
    return name


def ask_password():
    password = getpass.getpass("Password: ")
    if len(password) < MIN_PASSWORD:
        sys.exit(f"A password has at least {MIN_PASSWORD} characters")
    if getpass.getpass("Again: ") != password:
        sys.exit("The two passwords differ")
    return password


def main(argv=None):
    ap = argparse.ArgumentParser(prog="benneria-user",
                                 description="Manage Benneria Notebook accounts")
    commands = ap.add_subparsers(dest="command", required=True)
    commands.add_parser("add", help="create an account").add_argument("name")
    commands.add_parser("passwd", help="change an account's password").add_argument("name")
    remove = commands.add_parser("remove", help="delete an account and all its notebooks")
    remove.add_argument("name")
    remove.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    commands.add_parser("list", help="list the accounts")
    args = ap.parse_args(argv)
    store = Store()

    if args.command == "add":
        name = check_name(args.name)
        try:
            uid = store.add_user(name, ask_password())
        except ValueError as e:
            sys.exit(str(e))
        print(f"Account {name!r} created" + (", with any notes written before accounts existed"
                                              if uid == FIRST_USER else ""))
    elif args.command == "passwd":
        if not store.set_password(args.name, ask_password()):
            sys.exit(f"No account named {args.name!r}")
        print(f"Password changed; {args.name!r} is logged out everywhere")
    elif args.command == "remove":
        question = f"Delete {args.name!r} and all its notebooks? [y/N] "
        if not args.yes and input(question).strip().lower() != "y":
            sys.exit("Nothing deleted")
        removed = store.remove_user(args.name)
        if removed is None:
            sys.exit(f"No account named {args.name!r}")
        print(f"Deleted {args.name!r}: {removed['chapters']} notebooks, {removed['notes']} notes, "
              f"{removed['tables']} tables")
    else:
        for name, created, chapters in store.users():
            print(f"{name}\t{chapters} notebooks\tsince {created[:10]}")


if __name__ == "__main__":
    main()
