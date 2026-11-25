# GitHub Actions Workflow Setup

This workflow runs the library due date checker automatically every day at 8:00 AM UTC.

## Required GitHub Secrets

To use this workflow, you need to configure the following secrets in your GitHub repository:

### Library Account Credentials
- `LIBRARY_USERNAME_1` - Username/card number for the first library account
- `LIBRARY_PASSWORD_1` - Password/PIN for the first library account
- `LIBRARY_USERNAME_2` - (Optional) Username for the second library account
- `LIBRARY_PASSWORD_2` - (Optional) Password for the second library account

### Email Configuration (Mailgun)
- `RECIPIENT_EMAIL` - Email address to receive notifications
- `MAILGUN_DOMAIN` - Your Mailgun domain (e.g., mg.yourdomain.com)
- `MAILGUN_SENDER_EMAIL` - Sender email address (e.g., noreply@mg.yourdomain.com)
- `MAILGUN_API_KEY` - Your Mailgun API key

## Optional GitHub Variables

You can also configure these as repository variables (Settings → Secrets and variables → Actions → Variables):

- `NOTIFY_BEFORE_DUE_DAYS` - Number of days before due date to send notifications (default: 2)
- `NOTIFICATIONS_ENABLED` - Enable/disable notifications (default: true)

## How to Set Up Secrets

1. Go to your GitHub repository
2. Click on **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with its corresponding value
5. Save the secrets

## Manual Trigger

You can manually trigger the workflow:
1. Go to the **Actions** tab in your repository
2. Select **Check Library Due Dates** workflow
3. Click **Run workflow**
4. Select the branch and click **Run workflow**

## Schedule

The workflow is scheduled to run:
- **Every day at 8:00 AM UTC**
- This is 9:00 AM CET (Stockholm winter time) or 10:00 AM CEST (Stockholm summer time)

To change the schedule, modify the `cron` expression in the workflow file:
- Format: `'minute hour day month day-of-week'`
- Example for 7:00 AM UTC: `'0 7 * * *'`
- Example for 12:00 PM UTC: `'0 12 * * *'`

## Timezone Reference

- Stockholm (CET): UTC+1 (winter) / UTC+2 (summer)
- To run at 8:00 AM Stockholm time:
  - Winter (CET): Use `'0 7 * * *'` (7:00 AM UTC)
  - Summer (CEST): Use `'0 6 * * *'` (6:00 AM UTC)

## Artifacts

The workflow saves email notification files as artifacts for 30 days, which you can download from the workflow run page if needed.
