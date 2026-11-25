"""Library Due Date Checker for Stockholm Library."""

import base64
import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests

# Try to load environment variables from .env file
try:
    print("Script started at:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), " ----------------------")
    from load_env import load_env_file
    load_env_file()
except ImportError:
    pass

GRAPHQL_URL = "https://biblioteket.stockholm.se/graphql/"
REPORT_OUTPUT_DIR = "public"
REPORT_INDEX_FILE = "index.html"
REPORT_DATA_FILE = "encrypted-report.json"
REPORT_PASSPHRASE_ENV = "REPORT_PASSPHRASE"
REPORT_KEY_ITERATIONS = 200_000


def get_due_status(due_date: str) -> Dict[str, Any]:
    """Return display metadata for a loan due date."""
    today = datetime.now().date()

    try:
        due_date_obj = datetime.strptime(due_date, "%Y-%m-%d").date()
    except ValueError:
        return {
            "daysUntilDue": None,
            "status": "unknown",
            "statusLabel": "Unknown due date",
        }

    days_until_due = (due_date_obj - today).days
    if days_until_due < 0:
        status = "overdue"
        label = f"{abs(days_until_due)} days overdue"
    elif days_until_due == 0:
        status = "due-today"
        label = "Due today"
    elif days_until_due == 1:
        status = "due-tomorrow"
        label = "Due tomorrow"
    elif days_until_due <= 3:
        status = "soon"
        label = f"{days_until_due} days left"
    else:
        status = "upcoming"
        label = f"{days_until_due} days left"

    return {
        "daysUntilDue": days_until_due,
        "status": status,
        "statusLabel": label,
    }


def should_redact_loan_titles() -> bool:
    """Return whether loan titles should be hidden from console logs."""
    configured_value = os.getenv("REDACT_LOAN_TITLES")
    if configured_value is not None:
        return configured_value.lower() == "true"

    return os.getenv("GITHUB_ACTIONS", "").lower() == "true"


def build_report_account(
    account_name: str,
    loan_info: List[tuple[str, str, bool]],
    error: str | None = None,
) -> Dict[str, Any]:
    """Build a serializable report entry for one library account."""
    loans = []
    for title, due_date, is_renewable in sorted(loan_info, key=lambda item: item[1]):
        due_status = get_due_status(due_date)
        loans.append(
            {
                "title": title,
                "dueDate": due_date,
                "isRenewable": is_renewable,
                **due_status,
            }
        )

    return {
        "name": account_name,
        "loanCount": len(loans),
        "error": error,
        "loans": loans,
    }


def encrypt_report_payload(report: Dict[str, Any], passphrase: str) -> Dict[str, Any]:
    """Encrypt report data for client-side decryption on GitHub Pages."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    salt = os.urandom(16)
    nonce = os.urandom(12)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=REPORT_KEY_ITERATIONS,
    )
    key = kdf.derive(passphrase.encode("utf-8"))
    aesgcm = AESGCM(key)
    plaintext = json.dumps(report, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    return {
        "version": 1,
        "cipher": "AES-GCM",
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": REPORT_KEY_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def write_report_index(output_dir: str) -> None:
    """Write the static GitHub Pages shell used to decrypt the report."""
    os.makedirs(output_dir, exist_ok=True)
    index_path = os.path.join(output_dir, REPORT_INDEX_FILE)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(
            """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Library Loans</title>
  <style>
    :root {
      color-scheme: light dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f7fb;
      color: #1f2937;
    }
    body { margin: 0; }
    main { max-width: 960px; margin: 0 auto; padding: 32px 18px 48px; }
    header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-end; margin-bottom: 24px; }
    h1 { margin: 0; font-size: clamp(2rem, 6vw, 4rem); line-height: 1; letter-spacing: 0; }
    h2 { margin: 28px 0 12px; font-size: 1.1rem; }
    .muted { color: #64748b; }
    .auth, .account, .empty { background: #fff; border: 1px solid #dbe3ef; border-radius: 8px; padding: 18px; }
    .auth form { display: grid; grid-template-columns: 1fr auto; gap: 10px; margin-top: 12px; }
    input, button { font: inherit; border-radius: 6px; min-height: 42px; }
    input { border: 1px solid #cbd5e1; padding: 0 12px; }
    button { border: 0; background: #0f766e; color: #fff; padding: 0 18px; cursor: pointer; }
    button:disabled { opacity: .7; cursor: wait; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 12px 10px; border-bottom: 1px solid #e2e8f0; text-align: left; vertical-align: top; }
    th { font-size: .8rem; color: #64748b; text-transform: uppercase; }
    .badge { display: inline-block; border-radius: 999px; padding: 4px 9px; font-size: .85rem; font-weight: 650; white-space: nowrap; }
    .overdue, .due-today { background: #fee2e2; color: #991b1b; }
    .due-tomorrow, .soon { background: #fef3c7; color: #92400e; }
    .upcoming { background: #dcfce7; color: #166534; }
    .unknown { background: #e2e8f0; color: #475569; }
    .error { color: #b91c1c; }
    @media (prefers-color-scheme: dark) {
      :root { background: #111827; color: #f9fafb; }
      .auth, .account, .empty { background: #1f2937; border-color: #374151; }
      input { background: #111827; color: #f9fafb; border-color: #4b5563; }
      th, td { border-bottom-color: #374151; }
      .muted { color: #9ca3af; }
    }
    @media (max-width: 680px) {
      header { display: block; }
      .auth form { grid-template-columns: 1fr; }
      table, thead, tbody, th, td, tr { display: block; }
      thead { display: none; }
      tr { border-bottom: 1px solid #e2e8f0; padding: 10px 0; }
      td { border: 0; padding: 4px 0; }
      td::before { content: attr(data-label); display: block; color: #64748b; font-size: .78rem; text-transform: uppercase; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Library Loans</h1>
        <p class="muted" id="summary">Encrypted report</p>
      </div>
    </header>

    <section class="auth" id="auth">
      <strong>Enter passcode</strong>
      <p class="muted">Book data is encrypted and decrypted only in this browser.</p>
      <form id="passcode-form">
        <input id="passcode" type="password" autocomplete="current-password" placeholder="Passcode" required autofocus>
        <button id="unlock" type="submit">Unlock</button>
      </form>
      <p class="error" id="error" role="alert"></p>
    </section>

    <section id="report" hidden></section>
  </main>

  <script>
    const form = document.getElementById("passcode-form");
    const passcodeInput = document.getElementById("passcode");
    const unlockButton = document.getElementById("unlock");
    const errorEl = document.getElementById("error");
    const reportEl = document.getElementById("report");
    const summaryEl = document.getElementById("summary");
    let encryptedReport;

    function base64ToBytes(value) {
      const binary = atob(value);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
      }
      return bytes;
    }

    async function decryptReport(passcode) {
      const encoder = new TextEncoder();
      const keyMaterial = await crypto.subtle.importKey(
        "raw",
        encoder.encode(passcode),
        "PBKDF2",
        false,
        ["deriveKey"]
      );
      const key = await crypto.subtle.deriveKey(
        {
          name: "PBKDF2",
          salt: base64ToBytes(encryptedReport.salt),
          iterations: encryptedReport.iterations,
          hash: "SHA-256",
        },
        keyMaterial,
        { name: "AES-GCM", length: 256 },
        false,
        ["decrypt"]
      );
      const plaintext = await crypto.subtle.decrypt(
        { name: "AES-GCM", iv: base64ToBytes(encryptedReport.nonce) },
        key,
        base64ToBytes(encryptedReport.ciphertext)
      );
      return JSON.parse(new TextDecoder().decode(plaintext));
    }

    function textCell(row, label, value) {
      const cell = document.createElement("td");
      cell.dataset.label = label;
      cell.textContent = value;
      row.appendChild(cell);
      return cell;
    }

    function renderReport(report) {
      document.getElementById("auth").hidden = true;
      reportEl.hidden = false;
      summaryEl.textContent = `${report.totalLoans} loans updated ${new Date(report.generatedAt).toLocaleString()}`;
      reportEl.replaceChildren();

      if (report.accounts.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "No accounts were included in this report.";
        reportEl.appendChild(empty);
        return;
      }

      report.accounts.forEach((account) => {
        const section = document.createElement("section");
        section.className = "account";
        const heading = document.createElement("h2");
        heading.textContent = `${account.name} (${account.loanCount})`;
        section.appendChild(heading);

        if (account.error) {
          const error = document.createElement("p");
          error.className = "error";
          error.textContent = account.error;
          section.appendChild(error);
        } else if (account.loans.length === 0) {
          const empty = document.createElement("p");
          empty.className = "muted";
          empty.textContent = "No active loans.";
          section.appendChild(empty);
        } else {
          const table = document.createElement("table");
          table.innerHTML = "<thead><tr><th>Title</th><th>Due date</th><th>Status</th><th>Renewable</th></tr></thead>";
          const body = document.createElement("tbody");
          account.loans.forEach((loan) => {
            const row = document.createElement("tr");
            textCell(row, "Title", loan.title);
            textCell(row, "Due date", loan.dueDate);
            const status = textCell(row, "Status", "");
            const badge = document.createElement("span");
            badge.className = `badge ${loan.status}`;
            badge.textContent = loan.statusLabel;
            status.appendChild(badge);
            textCell(row, "Renewable", loan.isRenewable ? "Yes" : "No");
            body.appendChild(row);
          });
          table.appendChild(body);
          section.appendChild(table);
        }
        reportEl.appendChild(section);
      });
    }

    async function loadEncryptedReport() {
      const response = await fetch("encrypted-report.json", { cache: "no-store" });
      if (!response.ok) {
        throw new Error("Encrypted report data is missing. Configure REPORT_PASSPHRASE and rerun the workflow.");
      }
      encryptedReport = await response.json();
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      errorEl.textContent = "";
      unlockButton.disabled = true;
      try {
        if (!encryptedReport) {
          await loadEncryptedReport();
        }
        renderReport(await decryptReport(passcodeInput.value));
        passcodeInput.value = "";
      } catch (error) {
        errorEl.textContent = error.message.includes("missing")
          ? error.message
          : "Unable to unlock the report. Check the passcode and try again.";
      } finally {
        unlockButton.disabled = false;
      }
    });
  </script>
</body>
</html>
"""
        )


def write_web_report(accounts: List[Dict[str, Any]]) -> None:
    """Write encrypted report data and its static web page shell."""
    write_report_index(REPORT_OUTPUT_DIR)
    passphrase = os.getenv(REPORT_PASSPHRASE_ENV)
    if not passphrase:
        print(f"Warning: {REPORT_PASSPHRASE_ENV} is not set; encrypted web report was not written")
        return

    report = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "totalLoans": sum(account["loanCount"] for account in accounts),
        "accounts": accounts,
    }
    encrypted_report = encrypt_report_payload(report, passphrase)
    report_path = os.path.join(REPORT_OUTPUT_DIR, REPORT_DATA_FILE)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(encrypted_report, f, indent=2)
        f.write("\n")

    print(f"Encrypted web report written to {report_path}")


def load_config() -> Dict | None:
    """Load configuration from environment variables or config.json file as fallback."""
    # Try environment variables first
    if os.getenv('LIBRARY_USERNAME_1'):
        accounts = []
        
        # Load first account
        username1 = os.getenv('LIBRARY_USERNAME_1')
        password1 = os.getenv('LIBRARY_PASSWORD_1')
        if username1 and password1:
            accounts.append({
                "username": username1,
                "password": password1,
                "recipient_email": os.getenv('RECIPIENT_EMAIL', ''),
                "enabled": True,
                "name": "Primary Account"
            })
        
        # Load second account if exists
        username2 = os.getenv('LIBRARY_USERNAME_2')
        password2 = os.getenv('LIBRARY_PASSWORD_2')
        if username2 and password2:
            accounts.append({
                "username": username2,
                "password": password2,
                "recipient_email": os.getenv('RECIPIENT_EMAIL', ''),
                "enabled": True,
                "name": "Secondary Account"
            })
        
        if not accounts:
            print("❌ No valid credentials found in environment variables")
            return None
        
        config = {
            "accounts": accounts,
            "email": {
                "mailgun_domain": os.getenv('MAILGUN_DOMAIN', ''),
                "sender_email": os.getenv('MAILGUN_SENDER_EMAIL', ''),
                "sender_api_key": os.getenv('MAILGUN_API_KEY', '')
            },
            "notifications": {
                "notifyBeforeDueDateDays": int(os.getenv('NOTIFY_BEFORE_DUE_DAYS', '2')),
                "enabled": os.getenv('NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
            }
        }
        
        # print("✅ Configuration loaded from environment variables")
        return config
    
    # Fallback to config.json
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            print("⚠️ Configuration loaded from config.json (consider using environment variables)")
            return config
    except FileNotFoundError:
        print("❌ No configuration found. Please set environment variables or create config.json")
        print("💡 See .env.template for required environment variables")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in config file: {e}")
        return None


def create_session() -> requests.Session:
    """Create a requests session with appropriate headers."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    })
    return session


def perform_graphql_login(session: requests.Session, username: str, password: str) -> str | None:
    """Perform GraphQL login and return qid cookie if successful."""
    session.cookies.set('SERVERUSED', 'check', domain='biblioteket.stockholm.se')
    
    login_mutation = {
        "query": """
mutation loginPatron($loginInput: InputLogin!) {
loginPatron(input: $loginInput) {
status
statusMessage
}
}
""",
        "variables": {
            "__operation": "loginPatron",
            "loginInput": {
                "cardNumber": username,
                "pinCode": password
            }
        }
    }
    
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.6',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://biblioteket.stockholm.se',
        'Referer': 'https://biblioteket.stockholm.se/logga-in',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-GPC': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }
    
    try:
        response = session.post(GRAPHQL_URL, json=login_mutation, headers=headers, timeout=15)
        
        if response.status_code == 200:
            json_response = response.json()
            
            if "data" in json_response:
                login_result = json_response["data"].get("loginPatron", {})
                status = login_result.get("status")
                
                if status:
                    qid_cookie = session.cookies.get('qid')
                    if qid_cookie:
                        return qid_cookie
                    
                    set_cookies = response.headers.get('Set-Cookie', '')
                    if 'qid=' in set_cookies:
                        qid_match = re.search(r'qid=([^;]+)', set_cookies)
                        if qid_match:
                            qid_value = qid_match.group(1)
                            session.cookies.set('qid', qid_value, domain='biblioteket.stockholm.se')
                            return qid_value
                else:
                    status_message = login_result.get("statusMessage", "")
                    print(f"❌ Login failed: {status_message}")
            
            if "errors" in json_response:
                for error in json_response["errors"]:
                    print(f"❌ Login error: {error.get('message', 'Unknown error')}")
        else:
            print(f"❌ Login failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Login request failed: {e}")
    
    return None


def fetch_loans_via_graphql(session: requests.Session) -> List[tuple[str, str, bool]]:
    """Fetch loan data using GraphQL API. Returns list of (title, due_date, is_renewable) tuples."""
    qid_cookie = session.cookies.get('qid')
    if not qid_cookie:
        print("❌ No authentication cookie found")
        return []
    
    graphql_query = {
        "query": """
fragment loan on Loan {
loanId
loanDate
loanDueDate
loanDateDiff
remainingRenewals
loanPerProduct
isRenewable
status
branch {
name
}
media {
key
title
author
image
mediaTypeDisplay
mediaSubTypeDisplay
}
}

query {
patron {
... on Patron {
patronName
patronId
loans {
physicalLoans {
catalogueRecordId
...loan
}
}
}
... on Response {
status
statusMessage
}
}
}
""",
        "variables": {"__operation": "getProfile"}
    }
    
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.6',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://biblioteket.stockholm.se',
        'Referer': 'https://biblioteket.stockholm.se/mina-sidor',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-GPC': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }
    
    try:
        response = session.post(GRAPHQL_URL, json=graphql_query, headers=headers, timeout=15)
        
        if response.status_code == 200:
            json_response = response.json()
            
            if "errors" in json_response:
                for error in json_response["errors"]:
                    print(f"❌ GraphQL error: {error.get('message', 'Unknown error')}")
                return []
            
            patron = json_response.get("data", {}).get("patron")
            if patron is None:
                print("❌ No patron data returned")
                return []
            
            if "status" in patron and "statusMessage" in patron:
                print(f"❌ Error: {patron.get('statusMessage')}")
                return []
            
            loans = patron.get("loans", {})
            physical_loans = loans.get("physicalLoans", [])
            
            loan_info = []
            for loan in physical_loans:
                loan_due_date = loan.get("loanDueDate")
                if loan_due_date:
                    media = loan.get("media", {})
                    title = media.get("title", "Unknown title")
                    author = media.get("author")
                    is_renewable = loan.get("isRenewable", False)
                    
                    if author and author != "None":
                        full_title = f"{title} by {author}"
                    else:
                        full_title = title
                        
                    loan_info.append((full_title, loan_due_date, is_renewable))
            
            return loan_info
        else:
            print(f"❌ GraphQL request failed with status {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ GraphQL request failed: {e}")
        return []


def send_email_reminder(loan_info: List[tuple[str, str, bool]], config: Dict, account: Dict) -> None:
    """Send email reminder using Mailgun API."""
    email_config = config.get("email", {})
    mailgun_domain = email_config.get("mailgun_domain")
    sender_email = email_config.get("sender_email")
    sender_api_key = email_config.get("sender_api_key")
    recipient_email = account.get("recipient_email")
    
    if not all([mailgun_domain, sender_email, sender_api_key, recipient_email]):
        print("❌ Email configuration incomplete. Please check config.json")
        return
    
    # Create email content
    subject = "Library Books Due Soon - Reminder"
    body = "The following books are due soon:\n\n"
    
    today = datetime.now().date()
    
    for title, due_date, is_renewable in sorted(loan_info, key=lambda x: x[1]):
        # Calculate days until due date
        try:
            due_date_obj = datetime.strptime(due_date, "%Y-%m-%d").date()
            days_until_due = (due_date_obj - today).days
            
            if days_until_due < 0:
                days_text = f"{abs(days_until_due)} days OVERDUE"
                urgency = "🚨 "
            elif days_until_due == 0:
                days_text = "DUE TODAY"
                urgency = "⏰ "
            elif days_until_due == 1:
                days_text = "due tomorrow"
                urgency = "⚠️ "
            elif days_until_due <= 3:
                days_text = f"{days_until_due} days left"
                urgency = "⚠️ "
            else:
                days_text = f"{days_until_due} days left"
                urgency = "📅 "
        except ValueError:
            days_text = "unknown"
            urgency = "❓ "
        
        # Use different icon for non-renewable books as first character
        if not is_renewable:
            line_icon = "🔴 "
        else:
            line_icon = urgency
        
        body += f"{line_icon}{due_date} - {days_text} - {title}\n"
    
    body += f"\nTotal books: {len(loan_info)}"
    body += "\n\nPlease return or renew them before the due date."
    
    # Send email using Mailgun API
    try:
        mailgun_url = f"https://api.mailgun.net/v3/{mailgun_domain}/messages"
        
        response = requests.post(
            mailgun_url,
            auth=("api", sender_api_key),
            data={
                "from": sender_email,
                "to": f"Martin Pabis <{recipient_email}>",
                "subject": subject,
                "text": body
            },
            timeout=15
        )
        
        if response.status_code == 200:
            print(f"✅ Email reminder sent successfully to {recipient_email}")
            print(f"📋 Summary: {len(loan_info)} books due soon")
        else:
            print(f"❌ Failed to send email. Status: {response.status_code}")
            print(f"❌ Response: {response.text}")
            
        # Also save to file as backup
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"email_notification_{timestamp}.txt"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"To: {recipient_email}\n")
            f.write(f"Subject: {subject}\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Status: Email sent via Mailgun API\n")
            f.write("-" * 50 + "\n\n")
            f.write(body)
        
        print(f"📧 Backup notification saved to: {filename}")
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        
        # Save to file as fallback
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"email_notification_{timestamp}.txt"
        
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"To: {recipient_email}\n")
                f.write(f"Subject: {subject}\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Status: Email failed, saved to file\n")
                f.write("-" * 50 + "\n\n")
                f.write(body)
            
            print(f"📧 Fallback notification saved to: {filename}")
        except Exception as file_error:
            print(f"❌ Failed to save fallback notification: {file_error}")


def check_and_send_reminder(loan_info: List[tuple[str, str, bool]], config: Dict, account: Dict) -> None:
    """Check if any book is due within notification threshold and send email reminder."""
    notifications_config = config.get("notifications", {})
    notify_days = notifications_config.get("notifyBeforeDueDateDays", 3)
    notifications_enabled = notifications_config.get("enabled", True)
    
    if not notifications_enabled:
        return
    
    today = datetime.now().date()
    notification_threshold = today + timedelta(days=notify_days)
    
    earliest_due_date = None
    for _, due_date_str, _ in loan_info:
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            if earliest_due_date is None or due_date < earliest_due_date:
                earliest_due_date = due_date
        except ValueError:
            continue
    
    if earliest_due_date and earliest_due_date <= notification_threshold:
        days_until_due = (earliest_due_date - today).days
        if days_until_due <= 0:
            print(f"⚠️ Books are overdue! Sending email reminder...")
        else:
            print(f"⚠️ Books due in {days_until_due} day(s)! Sending email reminder...")
        
        send_email_reminder(loan_info, config, account)


def check_due_dates() -> List[str]:
    """Main function to check library due dates for all enabled accounts."""
    config = load_config()
    if not config:
        return []

    accounts = config.get("accounts", [])
    enabled_accounts = [acc for acc in accounts if acc.get("enabled", True)]
    
    if not enabled_accounts:
        print("❌ No enabled accounts found in config.json")
        return []

    all_due_dates = []
    report_accounts = []
    
    for i, account in enumerate(enabled_accounts, 1):
        username = account.get("username", "")
        password = account.get("password", "")
        account_name = account.get("name", "") or f"Account {i}"
        
        print(f"\nAccount: {account_name}")
        
        if not username or not password:
            print(f"❌ Missing credentials for account: {account_name}")
            report_accounts.append(
                build_report_account(account_name, [], "Missing account credentials")
            )
            continue

        session = create_session()
        qid_cookie = perform_graphql_login(session, username, password)
        
        if qid_cookie:
            loan_info = fetch_loans_via_graphql(session)
            
            if loan_info:
                print(f"Found {len(loan_info)} loan(s):")
                
                # Calculate days until first due date
                today = datetime.now().date()
                earliest_due_date = None
                redact_titles = should_redact_loan_titles()
                
                for title, due_date, is_renewable in loan_info:
                    renewable_status = "      " if is_renewable else "\033[31mreturn\033[0m"
                    title_for_log = "[hidden in automation logs]" if redact_titles else title
                    print(f"  {due_date}  {renewable_status}  {title_for_log}")
                    try:
                        due_date_obj = datetime.strptime(due_date, "%Y-%m-%d").date()
                        if earliest_due_date is None or due_date_obj < earliest_due_date:
                            earliest_due_date = due_date_obj
                    except ValueError:
                        print(f"  ⚠️ Invalid date format: {due_date}")
                        continue
                
                if earliest_due_date:
                    days_until_due = (earliest_due_date - today).days
                    if days_until_due < 0:
                        print(f"  🚨 OVERDUE: First book was due {abs(days_until_due)} day(s) ago!")
                    elif days_until_due == 0:
                        print(f"  ⏰ URGENT: First book is due TODAY!")
                    elif days_until_due == 1:
                        print(f"  ⚠️ WARNING: First book is due TOMORROW!")
                    else:
                        print(f"  📅 Next due date: {days_until_due} day(s) from now")
                else:
                    print(f"  ❓ Could not determine earliest due date")
                
                check_and_send_reminder(loan_info, config, account)
                all_due_dates.extend([due_date for _, due_date, _ in loan_info])
                report_accounts.append(build_report_account(account_name, loan_info))
            else:
                print(f"📖 No loans found for {account_name}")
                report_accounts.append(build_report_account(account_name, []))
        else:
            print(f"❌ Authentication failed for {account_name}")
            report_accounts.append(
                build_report_account(account_name, [], "Authentication failed")
            )

    print()
    write_web_report(report_accounts)

    return all_due_dates


if __name__ == "__main__":
    due_dates = check_due_dates()
