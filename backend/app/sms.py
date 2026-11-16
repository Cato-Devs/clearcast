"""Phone numbers and SMS alerts, sent through Africa's Talking."""
import re

import httpx

from app.config import AT_API_KEY, AT_SENDER_ID, AT_USERNAME

LIVE_URL = "https://api.africastalking.com/version1/messaging"
SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"

# Two SMS parts. Longer messages are cut short, so one alert never costs more than two SMS.
MAX_SMS_LENGTH = 306

# Kenyan mobile numbers: 9 digits after the country code, starting with 7 or 1 (e.g. 0712..., 0110...)
KENYAN_MOBILE = re.compile(r"(?:\+?254|0)?([71]\d{8})")


def normalise_phone(text):
    """The number as +254XXXXXXXXX, or None if it isn't a Kenyan mobile number.
    Accepts 0712 345 678, 712345678, 254712345678 and +254-712-345-678."""
    digits = re.sub(r"[\s\-().]", "", text or "")
    match = KENYAN_MOBILE.fullmatch(digits)
    return f"+254{match[1]}" if match else None


def sms_enabled():
    return bool(AT_USERNAME and AT_API_KEY)


def sms_text(title, body):
    """The alert as one short message, for example
    "ClearCast: Heavy rain likely in Westlands. Predicted for Mon 16 Nov, 3:00 pm to 9:00 pm EAT."
    """
    text = f"ClearCast: {title}. {body}"
    return text if len(text) <= MAX_SMS_LENGTH else text[: MAX_SMS_LENGTH - 3].rstrip() + "..."


def send_sms(phone, text):
    """Send one SMS. Raises RuntimeError if Africa's Talking doesn't accept it."""
    data = {"username": AT_USERNAME, "to": phone, "message": text}
    if AT_SENDER_ID:
        data["from"] = AT_SENDER_ID
    response = httpx.post(
        SANDBOX_URL if AT_USERNAME == "sandbox" else LIVE_URL,
        data=data,
        headers={"apiKey": AT_API_KEY, "Accept": "application/json"},
        timeout=15,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Africa's Talking answered {response.status_code}: {response.text[:200]}")
    recipients = response.json().get("SMSMessageData", {}).get("Recipients", [])
    if not recipients or recipients[0].get("status") != "Success":
        raise RuntimeError(f"SMS not accepted: {response.text[:200]}")
