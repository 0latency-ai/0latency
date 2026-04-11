"""
Transactional email service using Resend.
Handles welcome emails, tier limit warnings, and system notifications.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger("zerolatency.email")

try:
    import resend
    RESEND_AVAILABLE = True
except ImportError as e:
    RESEND_AVAILABLE = False
    logger.warning(f"⚠ resend SDK not available - email features disabled: {e}")

class EmailService:
    """Send transactional emails via Resend."""

    def __init__(self):
        self.api_key = os.environ.get("RESEND_API_KEY")
        self.from_email = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")
        self.support_email = os.environ.get("RESEND_SUPPORT_EMAIL", "support@0latency.ai")
        self.base_url = os.environ.get("API_BASE_URL", "https://api.0latency.ai")
        self.site_url = os.environ.get("SITE_BASE_URL", "https://0latency.ai")

        if self.api_key and RESEND_AVAILABLE:
            resend.api_key = self.api_key
            self.enabled = True
            logger.info(f"✓ Email service initialized (from: {self.from_email})")
        else:
            pass  # resend not configured
            self.enabled = False
            logger.warning("⚠ Email service disabled - RESEND_API_KEY not set")

    def send_welcome_email(self, email: str, name: str, api_key: str, tenant_id: str) -> bool:
        """
        Send welcome email to new user with API key and quickstart link.

        Args:
            email: User email address
            name: User name/display name
            api_key: Generated API key
            tenant_id: Tenant ID

        Returns: True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning(f"Email disabled - skipping welcome email to {email}")
            return False

        quickstart_url = f"{self.site_url}/quickstart?tenant={tenant_id}"
        docs_url = f"{self.site_url}/docs"
        dashboard_url = f"{self.site_url}/dashboard"

        html_body = f"""
        <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h1>Welcome to Zero Latency! 🚀</h1>

                    <p>Hi {name},</p>

                    <p>Your Zero Latency Memory API account is ready. Your API key is:</p>

                    <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; font-family: monospace; word-break: break-all; margin: 20px 0;">
                        {api_key}
                    </div>

                    <p><strong>⚠️ Keep this key secure!</strong> Anyone with this key can access your memories.</p>

                    <h2>Get Started</h2>

                    <p>1. <strong>View Quickstart</strong>: <a href="{quickstart_url}">Get up and running in 5 minutes</a></p>
                    <p>2. <strong>Read Docs</strong>: <a href="{docs_url}">Full API documentation</a></p>
                    <p>3. <strong>Dashboard</strong>: <a href="{dashboard_url}">Manage your account & API keys</a></p>

                    <h2>First Steps</h2>
                    <pre style="background: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto;">
curl -X POST https://api.0latency.ai/extract \\
  -H "X-API-Key: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "agent_id": "my_agent",
    "turns": [{{
      "human_message": "We discussed pricing for Q2",
      "agent_message": "Yes, Q2 pricing is $99/month"
    }}]
  }}'
                    </pre>

                    <p>Questions? Reply to this email or contact <a href="mailto:{self.support_email}">support</a>.</p>

                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    <p style="color: #666; font-size: 12px;">
                        © Zero Latency Memory API | <a href="{self.site_url}">Visit our site</a>
                    </p>
                </div>
            </body>
        </html>
        """

        text_body = f"""Welcome to Zero Latency! 🚀

Your API key: {api_key}

Keep this key secure! Anyone with this key can access your memories.

Get Started:
1. Quickstart: {quickstart_url}
2. Docs: {docs_url}
3. Dashboard: {dashboard_url}

Questions? Reply to this email.
"""

        try:
            response = resend.Emails.send({
     "from": self.from_email,
     "to": email,
     "subject": "Welcome to Zero Latency Memory API 🚀",
     "html": html_body,
     "text": text_body,
 })
            logger.info(f"✓ Welcome email sent to {email} (ID: {response.get('id', 'unknown')})")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to send welcome email to {email}: {e}")
            return False

    def send_tier_limit_warning(self, email: str, name: str, usage_percent: float,
                                tier_name: str, limit_mb: int, used_mb: float) -> bool:
        """
        Send warning email when user reaches 80% of memory tier limit.

        Args:
            email: User email
            name: User name
            usage_percent: Usage percentage (e.g., 80.5)
            tier_name: Tier name (e.g., "Professional", "Enterprise")
            limit_mb: Memory limit in MB
            used_mb: Memory used in MB

        Returns: True if sent successfully
        """
        if not self.enabled:
            logger.warning(f"Email disabled - skipping tier warning to {email}")
            return False

        upgrade_url = f"{self.site_url}/pricing"
        dashboard_url = f"{self.site_url}/dashboard/usage"

        html_body = f"""
        <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h1>Memory Tier Nearly Full ⚠️</h1>

                    <p>Hi {name},</p>

                    <p>You're using <strong>{usage_percent:.1f}%</strong> of your <strong>{tier_name}</strong> memory tier:</p>

                    <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 0;"><strong>Used:</strong> {used_mb:.1f} MB / {limit_mb} MB</p>
                    </div>

                    <p>When you reach your limit, older memories will be automatically archived. To continue storing memories without limits:</p>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{upgrade_url}" style="background: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                            View Upgrade Options
                        </a>
                    </div>

                    <p>Or <a href="{dashboard_url}">check your usage details</a> for a breakdown by agent and topic.</p>

                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    <p style="color: #666; font-size: 12px;">
                        © Zero Latency Memory API | <a href="{self.site_url}">Visit our site</a>
                    </p>
                </div>
            </body>
        </html>
        """

        text_body = f"""Memory Tier Nearly Full ⚠️

You're using {usage_percent:.1f}% of your {tier_name} tier:
Used: {used_mb:.1f} MB / {limit_mb} MB

View upgrade options: {upgrade_url}
Usage details: {dashboard_url}
"""

        try:
            response = resend.Emails.send({
     "from": self.from_email,
     "to": email,
     "subject": f"⚠️ Memory Tier {usage_percent:.0f}% Full - {tier_name} Plan",
     "html": html_body,
     "text": text_body,
 })
            logger.info(f"✓ Tier warning email sent to {email} ({usage_percent:.1f}% usage)")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to send tier warning to {email}: {e}")
            return False

    def send_notification(self, email: str, subject: str, html_body: str, text_body: str) -> bool:
        """
        Send custom notification email.

        Args:
            email: Recipient email
            subject: Email subject
            html_body: HTML content
            text_body: Plain text fallback

        Returns: True if sent successfully
        """
        if not self.enabled:
            logger.warning(f"Email disabled - skipping notification to {email}")
            return False

        try:
            response = resend.Emails.send({
     "from": self.from_email,
     "to": email,
     "subject": subject,
     "html": html_body,
     "text": text_body,
 })
            logger.info(f"✓ Notification sent to {email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to send notification to {email}: {e}")
            return False

# Global instance
email_service = EmailService()
