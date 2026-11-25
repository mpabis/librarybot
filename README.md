# Library Due Date Checker

A Python script to check due dates for Stockholm Library books and send email reminders.

## Features

- ✅ Multi-account support (check multiple library cards)
- 📧 Email notifications via Mailgun
- 🔒 Encrypted GitHub Pages report for current loans
- 🔄 Renewal status checking (shows which books can be renewed)
- 🎨 Color-coded output (red text for books that must be returned)
- 📅 Days until due date calculation
- 🔐 Secure credential management via environment variables

## Setup

### 1. Install Dependencies

```bash
pip install requests beautifulsoup4
```

### 2. Configure Credentials

**Option A: Environment Variables (Recommended for production)**

1. Copy the template file:
   ```bash
   cp .env.template .env
   ```

2. Edit `.env` and fill in your actual values:
   ```bash
   # Library account credentials
   LIBRARY_USERNAME_1=your_first_card_number
   LIBRARY_PASSWORD_1=your_first_pin_code
   
   LIBRARY_USERNAME_2=your_second_card_number  # optional
   LIBRARY_PASSWORD_2=your_second_pin_code     # optional
   
   # Email configuration
   MAILGUN_DOMAIN=your_mailgun_domain
   MAILGUN_SENDER_EMAIL=your_sender_email
   MAILGUN_API_KEY=your_mailgun_api_key
   RECIPIENT_EMAIL=your_email_address
   
   # Notification settings
   NOTIFY_BEFORE_DUE_DAYS=2
   NOTIFICATIONS_ENABLED=true

   # Web report encryption
   REPORT_PASSPHRASE=your_private_report_passcode

   # Optional privacy setting
   REDACT_LOAN_TITLES=false
   ```

**Option B: JSON Config File (for development only)**

Create `config.json` with your credentials (see `config.template.json` for format).

⚠️ **Never commit `config.json` or `.env` files to git!**

### 3. Set up Mailgun (Optional)

If you want email notifications:
1. Sign up at [Mailgun](https://www.mailgun.com/)
2. Get your domain and API key
3. Add them to your `.env` file

## Usage

### Run the Script

```bash
python check-due-dates.py
```

Each run also writes a static web report to `public/`. The page shell is public,
but the loan data is encrypted in `public/encrypted-report.json` and can only be
opened with `REPORT_PASSPHRASE`.

### Publish the GitHub Pages Report

The GitHub Actions workflow publishes `public/` to GitHub Pages after the bot
runs. Configure these repository secrets before enabling Pages:

- `REPORT_PASSPHRASE`: passcode used to encrypt the web report. Store the same
  value in Bitwarden and enter it when opening the page.
- Existing library and Mailgun secrets: `LIBRARY_USERNAME_1`,
  `LIBRARY_PASSWORD_1`, `RECIPIENT_EMAIL`, `MAILGUN_DOMAIN`,
  `MAILGUN_SENDER_EMAIL`, and `MAILGUN_API_KEY`.
- Optional repository variable `UPLOAD_EMAIL_ARTIFACTS=true` uploads plaintext
  backup notification files. Leave it unset unless you need those artifacts.

Static GitHub Pages cannot provide server-side authentication. This project
protects the book list by encrypting the report data before upload; do not
replace this with a plain JavaScript password prompt over unencrypted data.
Workflow logs redact loan titles by default in GitHub Actions.

### Example Output

```
Account: Primary Account

Found 2 loan(s):
  2025-08-10        The Great Gatsby by F. Scott Fitzgerald
  2025-08-12  return  1984 by George Orwell
  📅 Next due date: 4 day(s) from now

Account: Secondary Account

Found 1 loan(s):
  2025-08-06  return  Dune by Frank Herbert
  ⏰ URGENT: First book is due TODAY!
```

### Status Indicators

- **Blank space**: Book can be renewed
- **`return`** (in red): Book must be returned (cannot be renewed)
- 🚨 **OVERDUE**: Books are past due
- ⏰ **URGENT**: Books due today
- ⚠️ **WARNING**: Books due tomorrow
- 📅 **Normal**: Days until next due date

## Security Best Practices

### For Development
- Use `.env` file for local development
- Never commit `.env` or `config.json` files
- Use `.env.template` to document required variables

### For Production
- Set environment variables directly on your server
- Use secure secret management (AWS Secrets Manager, Azure Key Vault, etc.)
- Consider using encrypted environment files

### Git Repository Safety
The `.gitignore` file excludes:
- `config.json`
- `.env`
- `email_notification_*.txt`
- `*.html`
- `public/`

## Common Environment Variable Approaches

### 1. System Environment Variables
```bash
# Linux/Mac
export LIBRARY_USERNAME_1="your_card_number"
export LIBRARY_PASSWORD_1="your_pin"

# Windows
set LIBRARY_USERNAME_1=your_card_number
set LIBRARY_PASSWORD_1=your_pin
```

### 2. Docker Environment
```dockerfile
ENV LIBRARY_USERNAME_1=your_card_number
ENV LIBRARY_PASSWORD_1=your_pin
```

### 3. GitHub Actions Secrets
Store as repository secrets and access via:
```yaml
env:
  LIBRARY_USERNAME_1: ${{ secrets.LIBRARY_USERNAME_1 }}
  LIBRARY_PASSWORD_1: ${{ secrets.LIBRARY_PASSWORD_1 }}
```

## Troubleshooting

### Authentication Issues
- Verify your library card number and PIN code
- Check that your library account is active
- Try logging in manually on the Stockholm Library website

### Email Issues
- Verify Mailgun domain and API key
- Check your Mailgun account limits
- Emails are also saved as backup files (`email_notification_*.txt`)

### Environment Variable Issues
- Ensure `.env` file exists and is properly formatted
- Check that `load_env.py` is in the same directory
- Verify environment variables are set: `echo $LIBRARY_USERNAME_1`

## License

This project is for personal use with Stockholm Library system.
