"""LLM adapter service with live provider integration, offline heuristic fallback, and prompt injection defense.

Features:
1. Live Server-Side LLM Provider Integration:
   - Supports Google Gemini and OpenAI via standard library urllib.request (zero extra dependencies).
   - Strictly bounded 5-second timeout with structured JSON schema validation.
   - Sets is_fallback=False ONLY after a live response is successfully received, validated, and used.
2. Offline Heuristic NLP Fallback:
   - Activates automatically when API keys are absent, network fails, or provider times out.
   - Explicit is_fallback=True badge displayed on the dashboard/UI.
   - Token-based word-boundary matching and negation handling.
   - Distinguishes 'I don't know' (ambiguous) from 'no' (cancel).
   - Distinguishes 'please change address' (address update) from 'ha' (confirm).
   - Prioritizes payment inquiries ('link bhejo') and address updates over simple confirmation.
   - Dynamic prepaid discount and order-specific payment URLs (never hardcoded literal '{ORDER_ID}').
3. Strict Prompt Injection & Adversarial Defense:
   - Sanitizes and neutralizes system-prompt jailbreak attempts.
   - Preserves customer content safely while flagging untrusted instructions.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try loading .env if dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


class LLMAdapterService:
    """Manages natural language interpretation of addresses and customer messages."""

    def __init__(self, api_key: Optional[str] = None):
        self.gemini_key = os.environ.get("GEMINI_API_KEY")
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.api_key = api_key or self.gemini_key or self.openai_key
        # Honest fallback state: stays True until a live call succeeds in production
        self.is_fallback: bool = True

    def sanitize_input(self, text: str) -> Tuple[str, bool]:
        """Detects and neutralizes prompt injection or system prompt override attempts.

        Returns (sanitized_text, is_injection_attempt_detected).
        """
        lower = text.lower()
        injection_patterns = [
            r"ignore (all )?previous instructions",
            r"system prompt",
            r"you are now in developer mode",
            r"override policy",
            r"mark (as )?vip",
            r"approve immediately",
            r"drop table",
            r"<script>",
            r"delete all",
        ]

        injection_found = any(re.search(pat, lower) for pat in injection_patterns)
        sanitized = re.sub(r"[\r\n\t]+", " ", text).strip()
        if injection_found:
            sanitized = f"[FLAGGED_UNTRUSTED_CONTENT: {sanitized[:60]}...]"

        return sanitized, injection_found

    def _call_live_gemini(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Invokes Gemini Flash API with bounded 5.0s timeout and JSON schema response."""
        key = self.gemini_key or self.api_key
        if not key:
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text_content)
                return parsed
        except Exception as e:
            logger.warning(f"Live Gemini API invocation failed/timed out: {e}")
            return None

    def _call_live_openai(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Invokes OpenAI gpt-4o-mini API with bounded 5.0s timeout and JSON schema response."""
        key = self.openai_key or self.api_key
        if not key:
            return None

        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a COD e-commerce WhatsApp assistant. Respond ONLY in strict JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text_content = data["choices"][0]["message"]["content"]
                parsed = json.loads(text_content)
                return parsed
        except Exception as e:
            logger.warning(f"Live OpenAI API invocation failed/timed out: {e}")
            return None

    def analyze_address_completeness(self, address: str, city: str, pincode: str) -> Dict[str, Any]:
        """Evaluates whether an address contains enough physical information for delivery."""
        sanitized, injected = self.sanitize_input(address)

        # If live provider is configured, try live analysis with 5s timeout
        if self.api_key and not injected:
            prompt = (
                f"Analyze delivery address completeness for last-mile courier fulfillment in India.\n"
                f"Address: '{sanitized}', City: '{city}', Pincode: '{pincode}'.\n"
                f"Return JSON with:\n"
                f"- completeness_score (float 0.0 to 1.0)\n"
                f"- is_deliverable (bool: true if score >= 0.50)\n"
                f"- missing_components (list of missing parts e.g. House Number, Landmark)\n"
                f"- summary (brief sentence)"
            )
            try:
                live_result = self._call_live_gemini(prompt) or self._call_live_openai(prompt)
                if isinstance(live_result, dict):
                    raw_score = live_result.get("completeness_score")
                    score_val = float(raw_score)
                    if 0.0 <= score_val <= 1.0 and not (score_val != score_val):  # not NaN
                        raw_deliv = live_result.get("is_deliverable")
                        is_deliv = bool(raw_deliv) if isinstance(raw_deliv, (bool, int)) or str(raw_deliv).lower() in ("true", "false", "1", "0") else (score_val >= 0.50)
                        if isinstance(raw_deliv, str):
                            is_deliv = raw_deliv.lower() in ("true", "1", "yes")
                        missing_comps = live_result.get("missing_components", [])
                        if not isinstance(missing_comps, list):
                            missing_comps = []
                        summary_txt = str(live_result.get("summary") or "")
                        return {
                            "completeness_score": round(score_val, 2),
                            "is_deliverable": is_deliv,
                            "missing_components": [str(c) for c in missing_comps],
                            "summary": summary_txt,
                            "prompt_injection_flag": False,
                            "is_fallback": False,
                        }
            except Exception as e:
                logger.warning(f"Live address validation failed: {e}; falling back to deterministic heuristic.")

        # Offline heuristic NLP fallback (always reports is_fallback=True)
        clean = sanitized.lower()
        has_number = bool(re.search(r"\d+", clean))
        length = len(clean)

        locality_markers = ["road", "street", "nagar", "colony", "sector", "lane", "phase", "enclave", "block", "floor", "flat"]
        has_locality = any(m in clean for m in locality_markers)

        landmark_markers = ["near", "opposite", "opp", "behind", "beside", "adjacent", "next to", "front of"]
        has_landmark = any(m in clean for m in landmark_markers)

        score = 0.5  # base
        if has_number:
            score += 0.2
        if has_locality:
            score += 0.15
        if has_landmark:
            score += 0.15
        if length < 15:
            score -= 0.35
        if injected:
            score = 0.1

        score = max(0.0, min(1.0, score))

        missing_components = []
        if not has_number:
            missing_components.append("House / Flat Number")
        if not (has_locality or has_landmark):
            missing_components.append("Prominent Landmark or Street Name")
        if length < 15:
            missing_components.append("Detailed delivery directions")

        summary = (
            "Complete and deliverable address."
            if score >= 0.70
            else "Address lacks specific building or landmark details; delivery partner may struggle."
        )

        return {
            "completeness_score": round(score, 2),
            "is_deliverable": score >= 0.50,
            "missing_components": missing_components,
            "summary": summary,
            "prompt_injection_flag": injected,
            "is_fallback": True,
        }

    def parse_customer_whatsapp_reply(
        self,
        customer_message: str,
        order_id: Optional[str] = None,
        discount_amount: float = 25.0,
    ) -> Dict[str, Any]:
        """Interprets customer WhatsApp messages in English, Hinglish, or shorthand.

        Classifies intent into:
        - CONFIRM_ORDER
        - CANCEL_ORDER
        - ASK_DISCOUNT_OR_PAYMENT
        - ADDRESS_UPDATE
        - AMBIGUOUS_OR_UNRESOLVED
        """
        sanitized, injected = self.sanitize_input(customer_message)
        if injected:
            return {
                "intent": "AMBIGUOUS_OR_UNRESOLVED",
                "confidence": 0.99,
                "bot_response": "I couldn't understand that instruction. Our support team will assist you shortly.",
                "action_recommended": "HOLD",
                "notes": "Prompt injection pattern flagged in customer chat.",
                "is_fallback": True,
            }

        target_order_id = order_id or "ORD-DEMO"
        pay_link = f"https://pay.codcompass.demo/pay/{target_order_id}"
        disc_int = int(discount_amount)

        # Step 1: Attempt live LLM classification if provider key is configured
        if self.api_key and not injected:
            prompt = (
                f"Classify the following customer WhatsApp reply for an e-commerce COD order.\n"
                f"Message: '{sanitized}'\n"
                f"Classify intent into exactly one of: ['CONFIRM_ORDER', 'CANCEL_ORDER', 'ASK_DISCOUNT_OR_PAYMENT', 'ADDRESS_UPDATE', 'AMBIGUOUS_OR_UNRESOLVED'].\n"
                f"Important Rules:\n"
                f"- Negated confirmation alone ('do not confirm', 'don't confirm') MUST be classified as AMBIGUOUS_OR_UNRESOLVED and request clarification without cancelling the order.\n"
                f"- Only explicit cancellation requests ('cancel', 'cancel it', 'no payment link, cancel it') should be CANCEL_ORDER.\n"
                f"Return JSON with:\n"
                f"- intent (string)\n"
                f"- confidence (float 0.0 to 1.0)\n"
                f"- bot_response (string reply to customer)\n"
                f"- action_recommended (one of 'SHIP_AS_IS', 'CANCEL', 'NUDGE_PREPAID', 'HOLD')"
            )
            try:
                live_result = self._call_live_gemini(prompt) or self._call_live_openai(prompt)
                if isinstance(live_result, dict):
                    intent = str(live_result.get("intent", "")).strip().upper()
                    VALID_INTENTS = {
                        "CONFIRM_ORDER", "CANCEL_ORDER", "ASK_DISCOUNT_OR_PAYMENT", "ADDRESS_UPDATE", "AMBIGUOUS_OR_UNRESOLVED"
                    }
                    VALID_ACTIONS = {"SHIP_AS_IS", "CANCEL", "NUDGE_PREPAID", "HOLD"}
                    if intent in VALID_INTENTS:
                        raw_conf = live_result.get("confidence", 0.90)
                        conf_val = float(raw_conf)
                        if 0.0 <= conf_val <= 1.0 and not (conf_val != conf_val):
                            act = str(live_result.get("action_recommended", "HOLD")).strip().upper()
                            if act not in VALID_ACTIONS:
                                intent_action_map = {
                                    "CONFIRM_ORDER": "SHIP_AS_IS",
                                    "CANCEL_ORDER": "CANCEL",
                                    "ASK_DISCOUNT_OR_PAYMENT": "NUDGE_PREPAID",
                                    "ADDRESS_UPDATE": "HOLD",
                                    "AMBIGUOUS_OR_UNRESOLVED": "HOLD",
                                }
                                act = intent_action_map[intent]

                            resp_text = str(live_result.get("bot_response", ""))
                            resp_text = resp_text.replace("{ORDER_ID}", target_order_id).replace("{DISCOUNT}", f"₹{disc_int}")
                            if intent == "ASK_DISCOUNT_OR_PAYMENT" and pay_link not in resp_text:
                                resp_text = f"You can pay online via UPI/Card to avail your instant ₹{disc_int} discount! Here is your secure payment link: {pay_link}"

                            # Safety guard: Negated confirmation alone must NOT cancel
                            has_explicit_cancel_check = bool(
                                re.search(r"\b(cancel|cancel\s+it|cancel\s+kardo|radd|order\s+nahi\s+chahiye|mat\s+bhejo|not\s+needed|stop\s+order)\b", sanitized.lower())
                            )
                            is_negated_cancel_check = bool(
                                re.search(r"\b(don'?t|dont|mat|nahi|do\s+not)\s+cancel\b", sanitized.lower())
                                or re.search(r"\bcancel\s+(mat|nahi|don'?t)\b", sanitized.lower())
                            )
                            is_neg_confirm_check = bool(
                                re.search(r"\b(don'?t|dont|mat|nahi|do\s+not)\s+confirm\b", sanitized.lower())
                                or re.search(r"\bconfirm\s+(mat|nahi)\b", sanitized.lower())
                            )
                            if intent == "CANCEL_ORDER" and not (has_explicit_cancel_check and not is_negated_cancel_check):
                                if is_neg_confirm_check:
                                    intent = "AMBIGUOUS_OR_UNRESOLVED"
                                    act = "HOLD"
                                    resp_text = (
                                        "We noted that you do not wish to confirm at this time. Could you please clarify if you would like "
                                        "to update your delivery details, switch to online payment, or cancel this order? We are holding your order safely."
                                    )

                            return {
                                "intent": intent,
                                "confidence": round(conf_val, 2),
                                "bot_response": resp_text,
                                "action_recommended": act,
                                "notes": "Classified via live server-side LLM provider.",
                                "is_fallback": False,
                            }
            except Exception as e:
                logger.warning(f"Live WhatsApp intent classification failed: {e}; falling back to deterministic heuristic.")

        # Step 2: Production-grade offline heuristic NLP with token, boundary and negation matching
        msg = sanitized.lower()

        # Negated cancel: "don't cancel" / "dont cancel" / "cancel mat karna"
        is_negated_cancel = bool(
            re.search(r"\b(don'?t|dont|mat|nahi|do\s+not)\s+cancel\b", msg)
            or re.search(r"\bcancel\s+(mat|nahi|don'?t)\b", msg)
        )

        # Negated confirm: "do not confirm" / "don't confirm" / "confirm mat karna"
        is_negated_confirm = bool(
            re.search(r"\b(don'?t|dont|mat|nahi|do\s+not)\s+confirm\b", msg)
            or re.search(r"\bconfirm\s+(mat|nahi)\b", msg)
        )

        # Negated payment inquiry: "no payment link" / "link nahi chahiye" / "no link"
        is_negated_payment = bool(
            re.search(r"\b(no|don'?t|dont|nahi|not)\s+(want\s+)?(payment\s+)?(link|upi|pay|online)\b", msg)
            or re.search(r"\b(link|payment|online)\s+(nahi|mat|not)\s*(chahiye)?\b", msg)
        )

        # Explicit cancel intent: "cancel it", "cancel kardo", "order nahi chahiye"
        has_explicit_cancel = bool(
            re.search(r"\b(cancel|cancel\s+it|cancel\s+kardo|radd|order\s+nahi\s+chahiye|mat\s+bhejo|not\s+needed|stop\s+order)\b", msg)
        )

        # Cancellation flag: Only explicit cancellation requests should cancel!
        is_cancel = has_explicit_cancel and not is_negated_cancel

        # Negated confirmation alone: "do not confirm", "don't confirm", "confirm mat karna"
        # Must return AMBIGUOUS_OR_UNRESOLVED and request clarification, without cancelling the order.
        is_negated_confirm_alone = is_negated_confirm and not is_cancel

        # Ambiguity check (prevents "I don't know" matching "no" in "know")
        is_ambiguous = (not is_cancel) and (
            is_negated_confirm_alone
            or bool(re.search(r"\b(don'?t\s+know|dont\s+know|not\s+sure|confused|dekh\s+ke|soch\s+ke|pata\s+nahi)\b", msg))
        )

        # Address change check (prevents "change" matching "ha", handles "yes, but change address")
        is_address_change = bool(
            re.search(r"\b(address\s+change|change\s+address|wrong\s+address|new\s+address|change\s+location|pata\s+badal|update\s+address|galat\s+address|pata\s+galat)\b", msg)
            or ("address" in msg and any(w in msg for w in ["change", "update", "wrong", "galat", "new", "badlo"]))
        )

        # Payment link inquiry check (handles "link bhejo", "prepaid discount", "upi payment")
        # Must NOT trigger if payment was negated (e.g. "no payment link, cancel it") or if explicit cancel took precedence
        is_payment_inquiry = (
            not is_negated_payment
            and not is_cancel
            and not is_address_change
            and bool(
                re.search(r"\b(link\s+bhejo|bhejo\s+link|payment\s+link|pay\s+link|online\s+payment|prepaid|discount|upi|gpay|phonepe|paytm|how\s+to\s+pay|qr\s+code)\b", msg)
            )
        )

        # Confirmation check (strict word boundaries, cannot be negated or address change or cancellation)
        is_confirm = (
            not is_ambiguous
            and not is_address_change
            and not is_payment_inquiry
            and not is_cancel
            and not is_negated_confirm
            and (
                is_negated_cancel  # e.g. "don't cancel, please dispatch soon"
                or bool(
                    re.search(r"\b(yes|haan|ha|bhejo|bhej\s+do|confirm|send\s+it|deliver\s+it|shi\s+hai|sahi\s+hai|ok|okay|yep|sure|please\s+dispatch|pack\s+kar\s+do|bilkul)\b", msg)
                )
            )
        )

        # Priority Intent Resolution:
        # 1. Address modification takes operational precedence
        if is_address_change:
            return {
                "intent": "ADDRESS_UPDATE",
                "confidence": 0.92,
                "bot_response": "Please reply with your updated address including House Number, Street, and Landmark so we can update your order.",
                "action_recommended": "HOLD",
                "notes": "Customer requested address modification; held for ops verification.",
                "is_fallback": True,
            }

        # 2. Explicit cancellation (Only explicit cancellation requests cancel)
        if is_cancel:
            return {
                "intent": "CANCEL_ORDER",
                "confidence": 0.95,
                "bot_response": "Understood. We have cancelled your order. No amount will be charged. Thank you for letting us know!",
                "action_recommended": "CANCEL",
                "notes": "Customer explicitly requested order cancellation.",
                "is_fallback": True,
            }

        # 3. Negated confirmation alone -> AMBIGUOUS_OR_UNRESOLVED with clarification request
        if is_negated_confirm_alone:
            return {
                "intent": "AMBIGUOUS_OR_UNRESOLVED",
                "confidence": 0.90,
                "bot_response": (
                    "We noted that you do not wish to confirm at this time. Could you please clarify if you would like "
                    "to update your delivery details, switch to online payment, or cancel this order? We are holding your order safely."
                ),
                "action_recommended": "HOLD",
                "notes": "Customer negated confirmation without explicit cancellation; order held and clarification requested.",
                "is_fallback": True,
            }

        # 4. Payment / prepaid discount inquiry
        if is_payment_inquiry:
            return {
                "intent": "ASK_DISCOUNT_OR_PAYMENT",
                "confidence": 0.92,
                "bot_response": (
                    f"You can pay online via UPI/Card to avail your instant ₹{disc_int} discount! "
                    f"Here is your secure payment link: {pay_link}"
                ),
                "action_recommended": "NUDGE_PREPAID",
                "notes": "Customer expressed interest in prepaid payment and discount.",
                "is_fallback": True,
            }

        # 4. Confirmation
        if is_confirm:
            return {
                "intent": "CONFIRM_ORDER",
                "confidence": 0.92,
                "bot_response": "Thank you for confirming! Your order has been approved and is being packed for dispatch. We will share tracking details shortly.",
                "action_recommended": "SHIP_AS_IS",
                "notes": "Customer confirmed order delivery intent via WhatsApp.",
                "is_fallback": True,
            }

        # 5. Ambiguity
        if is_ambiguous:
            return {
                "intent": "AMBIGUOUS_OR_UNRESOLVED",
                "confidence": 0.85,
                "bot_response": "Thank you for letting us know. An operations team member will reach out to help resolve your question.",
                "action_recommended": "HOLD",
                "notes": "Customer expressed ambiguity or hesitation; held for manual operations review.",
                "is_fallback": True,
            }

        # Default ambiguous
        return {
            "intent": "AMBIGUOUS_OR_UNRESOLVED",
            "confidence": 0.50,
            "bot_response": "Thank you for your message. An operations team member will verify your request shortly.",
            "action_recommended": "HOLD",
            "notes": "Ambiguous reply; escalated to manual human review.",
            "is_fallback": True,
        }
