#!/usr/bin/env python3
"""Send individual emails to names listed in a file using sendmail."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

LOCALPART_RE = re.compile(r"^[^@\s]+$")


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return config


def read_lines(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def read_message(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def resolve_recipient(name: str, email_domain: str) -> str:
    if "@" in name:
        return name
    if not email_domain:
        raise ValueError(f"Name '{name}' is not an email address and email_domain is not set")
    if not LOCALPART_RE.match(name):
        raise ValueError(f"Invalid recipient name or local part: {name!r}")
    return f"{name}@{email_domain}"


def build_message(
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    reply_to: str | None = None,
) -> str:
    headers = (
        f"To: {to_addr}\r\n"
        f"From: {from_addr}\r\n"
        f"Subject: {subject}\r\n"
    )
    if reply_to:
        headers += f"Reply-To: {reply_to}\r\n"
    return (
        headers
        + "MIME-Version: 1.0\r\n"
        + "Content-Type: text/plain; charset=utf-8\r\n"
        + "\r\n"
        + f"{body}"
    )


def send_email(sendmail: str, envelope_from: str, message: str) -> None:
    subprocess.run(
        [sendmail, "-f", envelope_from, "-t", "-oi"],
        input=message,
        text=True,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send individual emails to names listed in a file via sendmail."
    )
    parser.add_argument(
        "names_file",
        type=Path,
        help="File with one recipient name or email address per line",
    )
    parser.add_argument(
        "message_file",
        type=Path,
        help="File containing the email message body",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.ini"),
        help="YAML config file (default: config.ini)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Print recipients and message preview without sending",
    )
    args = parser.parse_args()

    for path in (args.config, args.names_file, args.message_file):
        if not path.is_file():
            print(f"error: file not found: {path}", file=sys.stderr)
            return 1

    try:
        config = load_config(args.config)
        names = read_lines(args.names_file)
        body = read_message(args.message_file)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    required = ("from", "envelope_from", "subject", "sendmail")
    missing = [key for key in required if not config.get(key)]
    if missing:
        print(f"error: missing required config keys: {', '.join(missing)}", file=sys.stderr)
        return 1

    from_addr = str(config["from"])
    envelope_from = str(config["envelope_from"])
    subject = str(config["subject"])
    sendmail = str(config["sendmail"])
    email_domain = str(config.get("email_domain", ""))
    reply_to = config.get("reply_to")
    reply_to = str(reply_to).strip() if reply_to else None

    failures = 0
    for name in names:
        try:
            recipient = resolve_recipient(name, email_domain)
            message = build_message(from_addr, recipient, subject, body, reply_to)
            if args.dry_run:
                print(f"[dry-run] would send to {recipient}")
                continue
            send_email(sendmail, envelope_from, message)
            print(f"sent to {recipient}")
        except (ValueError, subprocess.CalledProcessError, OSError) as exc:
            failures += 1
            print(f"error sending to {name!r}: {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
