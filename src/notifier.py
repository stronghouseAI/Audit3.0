import os
from twilio.rest import Client as TwilioClient

def send_batch_whatsapp_summary(summary_data: dict):
    """
    Dispatches a single corporate summary alert detailing batch metrics.
    Easily maps directly to verified Meta Business Identity templates using ContentSid parameters.
    """
    try:
        account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        
        if not account_sid or not auth_token or "your_" in account_sid:
            print("[Alert Warning] Live Twilio credentials missing. Skipping WhatsApp notification.")
            return

        client = TwilioClient(account_sid, auth_token)

        total = summary_data.get("total_files", 0)
        breaches = summary_data.get("breach_count", 0)
        flagged = summary_data.get("flagged_teams", "None")

        # Enterprise Batch Template Mock-Up (Uses clean markdown blocks inside Sandbox proxy)
        message_body = (
            f"📊 *DAILY AUDIT PIPELINE EXECUTIVE REPORT* 📊\n\n"
            f"• *Total Files Swept:* {total}\n"
            f"• *Confirmed Structural Breaches:* {breaches}\n"
            f"• *Critical Team Outliers:* {flagged}\n\n"
            f"👉 _Please review the generated automated CSV snapshot file inside the repository root for granular insights._"
        )

        # Configured to hit your verified testing endpoint
        message = client.messages.create(
            body=message_body,
            from_='whatsapp:+14155238886',  # Official Twilio Sandbox Proxy
            to='whatsapp:+447869693004'     # Verified Destination Phone Number
        )
        print(f"🚀 [WhatsApp Enterprise Alert] Consolidated report delivered successfully. (SID: {message.sid})")
    except Exception as e:
        print(f"[WhatsApp Error] Failed to route aggregated batch summary: {str(e)}")
