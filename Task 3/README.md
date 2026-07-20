# Automated Email Notification System

Reads a list of customers from a CSV file and sends each one a personalized
booking-confirmation email via Gmail SMTP, with credentials kept out of the
codebase using `.env` + `python-dotenv`.

## Files
- `email_notifier.py` — the main script
- `customers.csv` — sample customer list (`name,email`)
- `.env.example` — template for your credentials file (safe to commit)
- `.gitignore` — keeps your real `.env` and generated logs out of git
- `requirements.txt` — dependencies

## 1. Install dependencies
```bash
pip install -r requirements.txt
```

## 2. Generate a Gmail App Password (do this, not your real password)
Gmail blocks plain-password SMTP login by default. You need an **App
Password** instead:

1. Turn on 2-Step Verification on the Google account (required first):
   https://myaccount.google.com/security
2. Go to https://myaccount.google.com/apppasswords
3. Create a new app password (name it e.g. "tour-notifier"), Google gives
   you a 16-character password.
4. Use that 16-character password in `.env` — **never** your normal Gmail
   login password.

## 3. Set up your `.env` file
```bash
cp .env.example .env
```
Then edit `.env` and fill in:
```
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_APP_PASSWORD=the_16_char_app_password
SENDER_NAME=Your Name or Company
```
`.env` is already listed in `.gitignore` — **never commit this file**. Only
`.env.example` (with placeholder values) should go into version control.

## 4. Prepare your customer list
Edit `customers.csv` (or point at your own file) with two columns:
```csv
name,email
Aisha Khan,aisha.khan@example.com
Robert Chen,robert.chen@example.com
```
Rows with a missing name, missing email, or invalid email format are
automatically skipped and reported — they won't crash the run.

## 5. Preview before sending (recommended)
```bash
python3 email_notifier.py customers.csv --dry-run
```
This prints exactly what would be sent to each customer **without**
connecting to Gmail or sending anything — good for checking your
message wording and customer list before going live.

## 6. Send for real
```bash
python3 email_notifier.py customers.csv
```
Options:
- `--delay 2` — seconds to wait between sends (default 1s), to avoid
  Gmail rate-limiting/flagging you as spam on large lists
- `--log myresults.csv` — where to write the send-results log
  (default `send_log.csv`)

After running, check `send_log.csv` for a per-recipient `sent`/`failed`
status and any error messages.

## Security notes (why it's built this way)
- Credentials are **never hardcoded** in `email_notifier.py` — they're
  loaded at runtime from `.env` via `load_dotenv()`.
- `.env` is git-ignored, so secrets can't accidentally get pushed to
  GitHub. Only `.env.example` (placeholders, no real values) is committed.
- The script uses an **App Password**, not the real Gmail account
  password — App Passwords can be individually revoked from the Google
  Account without changing your main password, and they can't be used to
  log into the account itself (SMTP/IMAP access only).
- The connection uses `starttls()` to encrypt the SMTP session before
  login credentials are sent.

## Customizing the email content
Edit `SUBJECT_TEMPLATE` and `BODY_TEMPLATE` near the top of
`email_notifier.py`. `{name}` and `{sender_name}` are available as
placeholders in the body. To add more personalization fields (e.g. tour
name, date), add the corresponding column to `customers.csv` and reference
it the same way.

## Gmail sending limits
Free Gmail accounts are capped at **500 emails/day**. For larger lists,
consider Google Workspace (2,000/day) or a transactional email service
(SendGrid, Amazon SES, Mailgun, etc.) — smtplib-based sending isn't
meant for high-volume bulk email.
