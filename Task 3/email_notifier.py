#!/usr/bin/env python3
"""
Automated Email Notification System
=====================================
Tech stack: Python, smtplib, email.mime, python-dotenv, csv

Reads a list of customers (name, email) from a CSV file and sends each
one a personalized booking-confirmation email via Gmail SMTP.

SECURITY:
    Credentials (Gmail address + App Password) are never hardcoded in
    this script. They are loaded at runtime from a local ".env" file
    (via python-dotenv), which is excluded from version control by
    .gitignore. See README.md for how to generate a Gmail App Password.

Usage:
    python3 email_notifier.py customers.csv
    python3 email_notifier.py customers.csv --dry-run
    python3 email_notifier.py customers.csv --delay 2
"""

import argparse
import csv
import re
import smtplib
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
import os


EMAIL_PATTERN = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")


# ---------------------------------------------------------------------------
# EMAIL TEMPLATE - customize the message here
# ---------------------------------------------------------------------------
SUBJECT_TEMPLATE = "Your Tour Booking Confirmation"

BODY_TEMPLATE = """\
Hi {name},

Thank you for booking with us! This email confirms we've received your
tour enquiry/booking.

Our team will be in touch shortly with further details. If you have any
questions in the meantime, just reply to this email.

Best regards,
{sender_name}
"""


# ---------------------------------------------------------------------------
# STEP 1: LOAD CONFIG / CREDENTIALS FROM .env
# ---------------------------------------------------------------------------
def load_config() -> dict:
    load_dotenv()  # reads .env in the current directory into os.environ

    config = {
        "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", "587")),
        "email_address": os.getenv("EMAIL_ADDRESS"),
        "email_app_password": os.getenv("EMAIL_APP_PASSWORD"),
        "sender_name": os.getenv("SENDER_NAME", "Tour Bookings Team"),
    }

    missing = [k for k in ("email_address", "email_app_password") if not config[k]]
    if missing:
        print(
            "Error: missing required environment variable(s): "
            f"{', '.join(missing)}\n"
            "Create a '.env' file (see .env.example) with your Gmail address "
            "and App Password before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    return config


# ---------------------------------------------------------------------------
# STEP 2: READ CUSTOMER LIST FROM CSV
# ---------------------------------------------------------------------------
def read_customers(csv_path: str) -> tuple[list[dict], list[dict]]:
    """
    Returns (valid_customers, invalid_rows).
    Expects a CSV with "name" and "email" columns (case-insensitive).
    """
    valid, invalid = [], []

    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Normalize header names to lowercase so "Name"/"NAME"/"name" all work
            reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]

            for row_num, row in enumerate(reader, start=2):  # row 1 = header
                name = (row.get("name") or "").strip()
                email = (row.get("email") or "").strip()

                if not name or not email or not EMAIL_PATTERN.match(email):
                    invalid.append({"row": row_num, "name": name, "email": email})
                    continue

                valid.append({"name": name, "email": email})
    except FileNotFoundError:
        print(f"Error: customer file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error reading customer file: {e}", file=sys.stderr)
        sys.exit(1)

    return valid, invalid


# ---------------------------------------------------------------------------
# STEP 3: BUILD PERSONALIZED EMAIL
# ---------------------------------------------------------------------------
def build_message(customer: dict, config: dict) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"] = f"{config['sender_name']} <{config['email_address']}>"
    msg["To"] = customer["email"]
    msg["Subject"] = SUBJECT_TEMPLATE

    body = BODY_TEMPLATE.format(name=customer["name"], sender_name=config["sender_name"])
    msg.attach(MIMEText(body, "plain"))
    return msg


# ---------------------------------------------------------------------------
# STEP 4: SEND EMAILS
# ---------------------------------------------------------------------------
def send_emails(customers: list[dict], config: dict, dry_run: bool, delay: float) -> list[dict]:
    """
    Sends one email per customer. Returns a list of result dicts:
    {"email": ..., "status": "sent"/"failed", "error": Optional[str]}
    """
    results = []

    if dry_run:
        print("[DRY RUN] No real emails will be sent.\n")
        for customer in customers:
            msg = build_message(customer, config)
            print(f"--- Would send to: {customer['email']} ---")
            print(f"Subject: {msg['Subject']}")
            print(msg.get_payload()[0].get_payload())
            print("-" * 50)
            results.append({"email": customer["email"], "status": "dry-run", "error": None})
        return results

    try:
        server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
        server.starttls()  # upgrade the connection to TLS before authenticating
        server.login(config["email_address"], config["email_app_password"])
    except smtplib.SMTPAuthenticationError:
        print(
            "Error: SMTP authentication failed. Check EMAIL_ADDRESS and "
            "EMAIL_APP_PASSWORD in your .env file. Note: Gmail requires an "
            "App Password (not your normal password) -- see README.md.",
            file=sys.stderr,
        )
        sys.exit(1)
    except (smtplib.SMTPException, OSError) as e:
        print(f"Error connecting to SMTP server: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        for customer in customers:
            msg = build_message(customer, config)
            try:
                server.sendmail(config["email_address"], customer["email"], msg.as_string())
                results.append({"email": customer["email"], "status": "sent", "error": None})
                print(f"  Sent -> {customer['email']}")
            except smtplib.SMTPException as e:
                results.append({"email": customer["email"], "status": "failed", "error": str(e)})
                print(f"  FAILED -> {customer['email']} ({e})")

            if delay > 0:
                time.sleep(delay)  # avoid tripping Gmail's rate limits
    finally:
        server.quit()

    return results


# ---------------------------------------------------------------------------
# STEP 5: LOG RESULTS
# ---------------------------------------------------------------------------
def write_log(results: list[dict], log_path: str = "send_log.csv") -> None:
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["email", "status", "error"])
        writer.writeheader()
        writer.writerows(results)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="email_notifier.py",
        description="Send personalized confirmation emails to a list of "
                     "customers read from a CSV file, via Gmail SMTP.",
    )
    parser.add_argument("customer_csv", help="Path to CSV file with 'name' and 'email' columns")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview the emails that would be sent, without actually sending them "
             "or connecting to any SMTP server",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Seconds to wait between sends, to avoid rate limits (default: 1.0)",
    )
    parser.add_argument(
        "--log", default="send_log.csv",
        help="Path to write the send-results log CSV (default: send_log.csv)",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    customers, invalid_rows = read_customers(args.customer_csv)

    if invalid_rows:
        print(f"Skipping {len(invalid_rows)} invalid row(s) in {args.customer_csv}:")
        for row in invalid_rows:
            print(f"  - row {row['row']}: name={row['name']!r} email={row['email']!r}")
        print()

    if not customers:
        print("No valid customers to email. Exiting.")
        sys.exit(0)

    print(f"Loaded {len(customers)} valid customer(s) from {args.customer_csv}\n")

    config = load_config() if not args.dry_run else {
        "smtp_server": "smtp.gmail.com", "smtp_port": 587,
        "email_address": "preview@example.com", "email_app_password": "N/A",
        "sender_name": "Tour Bookings Team",
    }

    results = send_emails(customers, config, dry_run=args.dry_run, delay=args.delay)
    write_log(results, args.log)

    sent = sum(1 for r in results if r["status"] in ("sent", "dry-run"))
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"\nDone. {sent} succeeded, {failed} failed. Log written to {args.log}")


if __name__ == "__main__":
    main()
