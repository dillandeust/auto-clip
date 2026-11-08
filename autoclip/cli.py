from __future__ import annotations
import argparse
from .config import load

def main() -> None:
    parser = argparse.ArgumentParser(prog="autoclip")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_login = sub.add_parser("login", help="connexion persistante à une plateforme")
    p_login.add_argument("platform", choices=["tiktok", "instagram", "youtube"])
    p_login.add_argument("--profile", default="default")

    p_worker = sub.add_parser("worker", help="démarre le worker de publication")
    p_worker.add_argument("--poll", type=int, default=15)

    args = parser.parse_args()
    cfg = load()
    if args.cmd == "login":
        from .poster.login import login
        login(args.platform, cfg, profile=args.profile)
    elif args.cmd == "worker":
        from .worker import run_forever
        run_forever(poll_seconds=args.poll)
