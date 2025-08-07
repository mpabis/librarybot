"""Library Due Date Checker for Stockholm Library."""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List

import requests

# Try to load environment variables from .env file
try:
    from load_env import load_env_file
    load_env_file()
except ImportError:
    pass

GRAPHQL_URL = "https://biblioteket.stockholm.se/graphql/"


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
        
        print("✅ Configuration loaded from environment variables")
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
    
    for title, due_date, is_renewable in sorted(loan_info, key=lambda x: x[1]):
        renewable_text = " (Renewable)" if is_renewable else " (Not renewable)"
        body += f"• {due_date} - {title}{renewable_text}\n"
    
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
    
    for i, account in enumerate(enabled_accounts, 1):
        username = account.get("username", "")
        password = account.get("password", "")
        account_name = account.get("name", "")
        
        print(f"\nAccount: {account_name}")
        
        if not username or not password:
            print(f"❌ Missing credentials for account: {account_name}")
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
                
                for title, due_date, is_renewable in loan_info:
                    renewable_status = "      " if is_renewable else "\033[31mreturn\033[0m"
                    print(f"  {due_date}  {renewable_status}  {title}")
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
            else:
                print(f"📖 No loans found for {account_name}")
        else:
            print(f"❌ Authentication failed for {account_name}")
        
    return all_due_dates


if __name__ == "__main__":
    due_dates = check_due_dates()