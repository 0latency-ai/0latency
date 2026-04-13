"""Promo code generation and email delivery."""

import stripe
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
from datetime import datetime

from .config import get_config
from .models import PromoCodeRequest, PromoCodeResult
from .database import db


class PromoCodeGenerator:
    """Generates Stripe promo codes and sends to contributors."""
    
    def __init__(self):
        cfg = get_config()
        stripe.api_key = cfg.get('stripe.api_key')
        self.cfg = cfg
        self.tier_config = {
            'pro-3mo': {'product': cfg.get('stripe.product_ids.pro_3mo'), 'months': 3, 'name': 'Pro 3-Month'},
            'scale-6mo': {'product': cfg.get('stripe.product_ids.scale_6mo'), 'months': 6, 'name': 'Scale 6-Month'},
            'scale-12mo': {'product': cfg.get('stripe.product_ids.scale_12mo'), 'months': 12, 'name': 'Scale 12-Month'}
        }
    
    async def generate_promo_code(self, request: PromoCodeRequest) -> PromoCodeResult:
        """Generate a Stripe promo code for the contributor."""
        tier_info = self.tier_config.get(request.tier)
        if not tier_info:
            raise ValueError(f"Unknown promo tier: {request.tier}")
        
        # Generate unique code based on contributor and timestamp
        code_suffix = request.contributor[:10].upper().replace('-', '')
        timestamp_suffix = datetime.utcnow().strftime('%m%d')
        code = f"0LAT-{code_suffix}-{timestamp_suffix}"
        
        try:
            # Create Stripe coupon (100% off for X months)
            coupon = stripe.Coupon.create(
                percent_off=100,
                duration='repeating',
                duration_in_months=tier_info['months'],
                name=f"Contributor Reward - {request.contributor}",
                metadata={
                    'contributor': request.contributor,
                    'contribution_id': request.contribution_id,
                    'reason': request.reason[:500]  # Stripe metadata limit
                }
            )
            
            # Create promotion code
            promo_code = stripe.PromotionCode.create(
                coupon=coupon.id,
                code=code,
                max_redemptions=1,
                metadata={
                    'contributor': request.contributor,
                    'contribution_id': request.contribution_id
                }
            )
            
            result = PromoCodeResult(
                code=promo_code.code,
                tier=request.tier,
                duration_months=tier_info['months']
            )
            
            # Send email
            email_sent = await self._send_email(request, result, tier_info['name'])
            result.email_status = 'sent' if email_sent else 'failed'
            result.sent_at = datetime.utcnow() if email_sent else None
            
            return result
            
        except stripe.error.StripeError as e:
            raise Exception(f"Stripe API error: {str(e)}")
    
    async def _send_email(
        self, 
        request: PromoCodeRequest, 
        result: PromoCodeResult,
        tier_name: str
    ) -> bool:
        """Send promo code to contributor via email."""
        try:
            cfg = self.cfg
            
            # Email content
            subject = "🎉 Your 0Latency Contribution Reward!"
            
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2>Thank You for Contributing to 0Latency!</h2>
                
                <p>Hi {request.contributor},</p>
                
                <p>We appreciate your contribution! As a thank you, here's your reward:</p>
                
                <div style="background: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <strong>Promo Code:</strong> <code style="font-size: 18px; color: #0066cc;">{result.code}</code><br>
                    <strong>Plan:</strong> {tier_name}<br>
                    <strong>Duration:</strong> {result.duration_months} months (100% off)
                </div>
                
                <p><strong>How to redeem:</strong></p>
                <ol>
                    <li>Visit <a href="https://0latency.ai/pricing">0latency.ai/pricing</a></li>
                    <li>Choose your plan and proceed to checkout</li>
                    <li>Enter the promo code above</li>
                    <li>Enjoy {result.duration_months} months free!</li>
                </ol>
                
                <p><em>Contribution details:</em><br>
                {request.reason}</p>
                
                <p>We're grateful to have you as part of the 0Latency community. Keep building awesome things!</p>
                
                <p>Best,<br>
                The 0Latency Team</p>
                
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="font-size: 12px; color: #666;">
                    Questions? Reply to this email or reach out at support@0latency.ai
                </p>
            </body>
            </html>
            """
            
            text_body = f"""
Thank You for Contributing to 0Latency!

Hi {request.contributor},

We appreciate your contribution! As a thank you, here's your reward:

Promo Code: {result.code}
Plan: {tier_name}
Duration: {result.duration_months} months (100% off)

How to redeem:
1. Visit https://0latency.ai/pricing
2. Choose your plan and proceed to checkout
3. Enter the promo code above
4. Enjoy {result.duration_months} months free!

Contribution details:
{request.reason}

We're grateful to have you as part of the 0Latency community. Keep building awesome things!

Best,
The 0Latency Team

---
Questions? Reply to this email or reach out at support@0latency.ai
            """
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = cfg.get('email.from_address', 'rewards@0latency.ai')
            msg['To'] = request.contributor_email
            
            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send via Microsoft Graph API
            tenant_id = cfg.get('email.microsoft_tenant_id')
            client_id = cfg.get('email.microsoft_client_id')
            client_secret = cfg.get('email.microsoft_client_secret')
            from_email = cfg.get('email.from_address', 'support@0latency.ai')
            
            # Get access token
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            token_data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'scope': 'https://graph.microsoft.com/.default',
                'grant_type': 'client_credentials'
            }
            
            async with httpx.AsyncClient() as client:
                token_response = await client.post(token_url, data=token_data)
                token_response.raise_for_status()
                access_token = token_response.json()['access_token']
                
                # Send email via Graph API
                graph_url = f"https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"
                email_payload = {
                    "message": {
                        "subject": msg['Subject'],
                        "body": {
                            "contentType": "HTML",
                            "content": html_body
                        },
                        "toRecipients": [
                            {"emailAddress": {"address": request.contributor_email}}
                        ]
                    }
                }
                
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                }
                
                email_response = await client.post(graph_url, json=email_payload, headers=headers)
                email_response.raise_for_status()
            
            return True
            
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False


# Global promo generator instance
promo_generator = PromoCodeGenerator()
