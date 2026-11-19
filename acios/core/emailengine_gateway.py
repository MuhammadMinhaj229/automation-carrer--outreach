"""
ACIOS EmailEngine & Postal Delivery Gateway.

Native EmailEngine mailbox and delivery events are classified conservatively.
A newly observed mailbox message or delivery failure is a review item, not
proof of a reply or authorization to suppress a recipient.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from acios.core.repository import CareerRepository
from acios.core.suppression import SuppressionEngine


class EmailEngineGateway:
    """Manages webhook-shaped events without making unreviewed identity decisions."""

    def __init__(self, repo: Optional[CareerRepository] = None, supp: Optional[SuppressionEngine] = None):
        self.repo = repo or CareerRepository()
        self.supp = supp or SuppressionEngine()

    def process_webhook_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify EmailEngine / legacy normalized events.

        EmailEngine's native messageNew is any new mailbox message, not
        necessarily a reply. Native bounce and delivery events remain
        review-only until durable, idempotent suppression and correlation
        are implemented.
        """
        event_type = event_data.get("event") or event_data.get("type", "unknown")
        if not isinstance(event_type, str):
            event_type = "unknown"

        data = event_data.get("data") or {}
        if not isinstance(data, dict):
            return {"status": "IGNORED", "action": "NONE", "message": "Invalid webhook data."}

        sender = data.get("from") or {}
        if not isinstance(sender, dict):
            sender = {}
        from_email = sender.get("address") or data.get("recipient") or ""
        if not isinstance(from_email, str):
            from_email = ""
        clean_email = from_email.strip().lower()

        subject = data.get("subject", "")
        if not isinstance(subject, str):
            subject = ""

        if event_type == "messageNew":
            # EmailEngine emits this for any newly observed mailbox message,
            # including bounce/complaint notifications and unrelated mail.
            # It is not sufficient evidence that an outreach recipient replied.
            return {
                "status": "REVIEW_REQUIRED",
                "action": "REVIEW_INBOUND_MESSAGE",
                "sender": clean_email,
                "message_id": data.get("messageId") if isinstance(data.get("messageId"), str) else None,
                "message": "New mailbox message received; correlate with a staged message and review before changing contact status.",
            }

        if event_type == "messageBounce":
            response = data.get("response") or {}
            if not isinstance(response, dict):
                response = {}
            recipient = data.get("recipient")
            if not isinstance(recipient, str):
                recipient = ""
            message_id = data.get("messageId")
            if not isinstance(message_id, str):
                message_id = ""
            bounce_action = data.get("action")
            if not isinstance(bounce_action, str):
                bounce_action = ""

            return {
                "status": "REVIEW_REQUIRED",
                "action": "REVIEW_BOUNCE",
                "recipient": recipient.strip().lower(),
                "message_id": message_id,
                "bounce_action": bounce_action,
                "response_status": response.get("status") if isinstance(response.get("status"), str) else None,
                "response_category": response.get("category") if isinstance(response.get("category"), str) else None,
                "recommended_action": response.get("recommendedAction") if isinstance(response.get("recommendedAction"), str) else None,
                "message": "EmailEngine reported a delivery-status notification; verify correlation and review before changing suppression state.",
            }

        if event_type in {"messageDeliveryError", "messageFailed"}:
            return {
                "status": "REVIEW_REQUIRED",
                "action": "REVIEW_DELIVERY_FAILURE",
                "queue_id": data.get("queueId") if isinstance(data.get("queueId"), str) else None,
                "message_id": data.get("messageId") if isinstance(data.get("messageId"), str) else None,
                "error_code": data.get("errorCode") if isinstance(data.get("errorCode"), str) else None,
                "message": "EmailEngine reported a delivery attempt or terminal failure; this is not by itself a confirmed mailbox bounce.",
            }

        if event_type == "messageComplaint":
            return {
                "status": "REVIEW_REQUIRED",
                "action": "REVIEW_COMPLAINT",
                "message_id": data.get("messageId") if isinstance(data.get("messageId"), str) else None,
                "message": "EmailEngine reported a complaint; require operator review and a durable suppression decision.",
            }

        if event_type in {"reply", "incoming_message"}:
            # These are explicit legacy/internal normalized event names. Do
            # not map EmailEngine's generic messageNew event to this branch.
            if clean_email:
                self.repo.update_contact_status(clean_email, "REPLIED")
                self.repo.record_outreach_event(
                    recipient_email=clean_email,
                    action_type="REPLY_RECEIVED",
                    status="SUCCESS",
                    status_message=f"Human reply detected via normalized webhook event: '{subject[:40]}'",
                )
            return {
                "status": "PROCESSED",
                "action": "HALT_FUTURE_SEQUENCES",
                "recipient": clean_email,
                "message": f"Explicitly normalized reply from {clean_email} processed.",
            }

        elif event_type in ["bounce", "delivery_failed", "dsn"]:
            # Legacy normalized adapter only. This block is process-local;
            # native EmailEngine messageBounce events above remain review-only.
            bounce_type = str(data.get("bounce_type") or "").strip().lower()
            if bounce_type not in {"hard", "permanent"}:
                return {
                    "status": "IGNORED",
                    "action": "REVIEW_BOUNCE",
                    "recipient": clean_email,
                    "message": "Bounce is not explicitly classified as permanent; manual review required.",
                }
            if not clean_email:
                return {
                    "status": "IGNORED",
                    "action": "REVIEW_BOUNCE",
                    "message": "Permanent bounce has no recipient address.",
                }
            self.supp.block(clean_email)
            self.repo.update_contact_status(clean_email, "BOUNCED")
            self.repo.record_outreach_event(
                recipient_email=clean_email,
                action_type="BOUNCE_DETECTED",
                status="SUPPRESSED",
                status_message="Permanent bounce: recipient blocked in current process.",
            )
            return {
                "status": "PROCESSED",
                "action": "SUPPRESS_RECIPIENT",
                "recipient": clean_email,
                "message": "Recipient blocked in this process; persistent suppression is not configured.",
            }

        elif event_type in ["messageSent", "sent", "delivered", "staged"]:
            return {
                "status": "PROCESSED",
                "action": "LOG_DELIVERY",
                "recipient": clean_email,
                "message": "Provider accepted or staged the message; final inbox delivery is not implied.",
            }

        return {
            "status": "IGNORED",
            "action": "NONE",
            "message": f"Unhandled event type '{event_type}'.",
        }

    def get_gateway_status(self) -> Dict[str, Any]:
        """Returns the operational status of the EmailEngine / Postal gateway."""
        return {
            "engine": "EmailEngine Webhook Listener",
            "status": "ACTIVE_LISTENING",
            "webhook_path": "/api/webhooks/emailengine",
            "bounce_guard": "Native EmailEngine bounce events require human review; legacy normalized suppression is process-local",
            "reply_guard": "Only explicitly normalized reply events change contact status",
        }
