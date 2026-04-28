"""
================================================================================
Jerry The Customer Service Bot — ConversationEngine Service
================================================================================
File:     app/services/conversation_engine.py
Version:  1.3.0 (WonderwallAi Shield Integrated)
Session:  4 (February 2026)
================================================================================
"""

import os
import re
import json
import asyncio
import logging
import requests  # Required for WonderwallAi API calls
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from groq import Groq, RateLimitError
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Logging & Observability
# ---------------------------------------------------------------------------
logger = logging.getLogger("sunsetbot.conversation_engine")

from app.core.observability import log_decision, log_llm_call, Timer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_SIZE = 50
MAX_VIEWED_PRODUCTS = 200
MAX_PRICE_VALUE = 1_000_000

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_groq_format(self) -> dict:
        return {"role": self.role, "content": self.content}

@dataclass
class Product:
    id: str
    title: str
    price: float
    category: str = ""
    description: str = ""
    image_url: Optional[str] = None
    url: Optional[str] = None
    inventory: int = 99
    relevance_score: float = 1.0
    final_score: float = 1.0

    def to_display_string(self) -> str:
        stock_note = f" (only {self.inventory} left!)" if self.inventory < 10 else ""
        return f"{self.title} — ${self.price:.2f}{stock_note}"

@dataclass
class CartItem:
    product_id: str
    title: str
    price: float
    quantity: int = 1

@dataclass
class StoreConfig:
    store_id: str
    name: str = "Jerry The Customer Service Bot Demo Store"
    description: str = "A premium e-commerce store"
    shipping_policy: str = "Free shipping on orders over $50. Standard delivery 3-5 business days."
    return_policy: str = "30-day hassle-free returns. Items must be unworn with original tags."
    payment_methods: str = "Visa, Mastercard, PayPal, Apple Pay"

@dataclass
class ConversationContext:
    session_id: str
    store_id: str
    store: StoreConfig = field(default_factory=lambda: StoreConfig(store_id="default"))
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    lifetime_value: Decimal = field(default_factory=lambda: Decimal("0.00"))
    history: list[Message] = field(default_factory=list)
    intent: str = "browsing"
    sentiment: str = "neutral"
    message_count: int = 0
    viewed_products: list[str] = field(default_factory=list)
    cart_items: list[CartItem] = field(default_factory=list)
    cart_total: Decimal = field(default_factory=lambda: Decimal("0.00"))
    current_page: str = "home"
    referrer: Optional[str] = None
    escalated: bool = False
    escalation_reason: Optional[str] = None
    canary_token: Optional[str] = None
    canary_prompt_block: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str) -> None:
        self.history.append(Message(role=role, content=content))
        if len(self.history) > MAX_HISTORY_SIZE:
            self.history = self.history[-MAX_HISTORY_SIZE:]
        self.last_activity = datetime.now()
        self.message_count += 1

    def get_recent_history(self, n: int = 10) -> list[Message]:
        return self.history[-n:]

    def is_vip(self) -> bool:
        return self.lifetime_value > Decimal("500.00")

    def to_json(self) -> str:
        try:
            data = {
                "session_id": self.session_id,
                "store_id": self.store_id,
                "customer_id": self.customer_id,
                "customer_email": self.customer_email,
                "lifetime_value": str(self.lifetime_value),
                "history": [
                    {"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()}
                    for m in self.history
                ],
                "intent": self.intent,
                "sentiment": self.sentiment,
                "message_count": self.message_count,
                "viewed_products": self.viewed_products,
                "cart_items": [
                    {"product_id": i.product_id, "title": i.title, "price": i.price, "quantity": i.quantity}
                    for i in self.cart_items
                ],
                "cart_total": str(self.cart_total),
                "current_page": self.current_page,
                "escalated": self.escalated,
                "escalation_reason": self.escalation_reason,
                "started_at": self.started_at.isoformat(),
                "last_activity": self.last_activity.isoformat(),
            }
            return json.dumps(data)
        except Exception as e:
            logger.error(f"Failed to serialize context: {e}")
            raise

    @classmethod
    def from_json(cls, json_str: str) -> "ConversationContext":
        data = json.loads(json_str)
        ctx = cls(session_id=data["session_id"], store_id=data["store_id"])
        ctx.customer_id = data.get("customer_id")
        ctx.customer_email = data.get("customer_email")
        ctx.lifetime_value = Decimal(data.get("lifetime_value", "0.00"))
        ctx.intent = data.get("intent", "browsing")
        ctx.sentiment = data.get("sentiment", "neutral")
        ctx.message_count = data.get("message_count", 0)
        ctx.viewed_products = data.get("viewed_products", [])
        ctx.cart_items = [CartItem(**item) for item in data.get("cart_items", [])]
        ctx.cart_total = Decimal(data.get("cart_total", "0.00"))
        ctx.current_page = data.get("current_page", "home")
        ctx.escalated = data.get("escalated", False)
        ctx.escalation_reason = data.get("escalation_reason")
        ctx.history = [Message(role=m["role"], content=m["content"]) for m in data.get("history", [])]
        return ctx

@dataclass
class EngineResponse:
    text: str
    intent: str
    entities: dict
    products: list[Product] = field(default_factory=list)
    escalated: bool = False
    escalation_reason: Optional[str] = None
    session_id: str = ""

    def to_dict(self) -> dict:
        return {
            "text": self.text, "intent": self.intent, "entities": self.entities,
            "products": [{"id": p.id, "title": p.title, "price": p.price, "image_url": p.image_url, "url": p.url} for p in self.products],
            "escalated": self.escalated, "escalation_reason": self.escalation_reason, "session_id": self.session_id,
        }

@dataclass
class EscalationTrigger:
    reason: str
    priority: str
    details: str = ""

# ============================================================================
# COMPONENT CLASSES (Intent, Entity, Escalation, Response)
# ============================================================================

class IntentClassifier:
    INTENT_KEYWORDS = {
        "product_search": ["show me", "find", "looking for", "do you have", "recommend"],
        "order_tracking": ["where is my order", "track my order", "order status"],
        "support": ["help me", "problem with", "refund", "return"],
        "sizing": ["what size", "true to size", "fit", "measurements"],
        "policy": ["shipping policy", "return policy", "warranty"],
    }
    def classify(self, message: str, context: ConversationContext) -> str:
        msg = message.lower()
        matched_intent = "general"
        matched_keyword = None
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for k in keywords:
                if k in msg:
                    matched_intent = intent
                    matched_keyword = k
                    break
            if matched_keyword:
                break

        log_decision(
            "intent_classification",
            input_summary=message[:100],
            options_considered=list(self.INTENT_KEYWORDS.keys()) + ["general"],
            chosen=matched_intent,
            reason=f"keyword_match:{matched_keyword}" if matched_keyword else "no_match:default_general",
            confidence=1.0 if matched_keyword else 0.5,
        )
        return matched_intent

class EntityExtractor:
    PATTERNS = {
        "price_single": r"\$\s*(\d+(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s*(?:dollars?|\$)",
        "price_range": r"\$?(\d+(?:\.\d{1,2})?)\s*(?:to|-|and)\s*\$?(\d+(?:\.\d{1,2})?)",
        "size_explicit": r"\bsiz(?:e|es)\s+(\d{1,2}(?:\.\d)?|(?:xx?)?[smlx]{1,3})\b",
        "size_letter": r"\b((?:xx?)[sl]|[sml]|x{1,2}l)\b",
        "color": r"\b(red|blue|green|black|white|pink|yellow|orange|purple|grey|gray|brown|navy)\b",
        "order_number": r"#?\b(\d{4,})\b",
    }
    def extract(self, message: str) -> dict:
        entities = {}
        msg = message.lower()
        # Price
        range_m = re.search(self.PATTERNS["price_range"], msg)
        if range_m:
            entities["min_price"], entities["max_price"] = sorted([float(range_m.group(1)), float(range_m.group(2))])
        # Sizes
        s_exp = re.findall(self.PATTERNS["size_explicit"], msg)
        s_let = re.findall(self.PATTERNS["size_letter"], msg)
        if s_exp or s_let: entities["size"] = list(set(s.upper() for s in s_exp + s_let))
        # Colors
        colors = re.findall(self.PATTERNS["color"], msg)
        if colors: entities["colors"] = list(set(colors))
        # Order
        order = re.search(self.PATTERNS["order_number"], msg)
        if order: entities["order_number"] = order.group(1)

        if entities:
            log_decision(
                "entity_extraction",
                input_summary=message[:100],
                chosen=str(entities),
                reason="regex_patterns",
                metadata={"entity_count": len(entities)},
            )
        return entities

class EscalationHandler:
    PROFANITY = ["fuck", "shit", "damn", "asshole", "bitch"]
    def check(self, message: str, response: str, context: ConversationContext) -> Optional[EscalationTrigger]:
        msg = message.lower()
        trigger = None
        if any(w in msg for w in self.PROFANITY):
            trigger = EscalationTrigger("customer_frustration", "high", "Profanity detected")
        elif "manager" in msg:
            trigger = EscalationTrigger("keyword_trigger", "high", "Asked for manager")

        if trigger:
            log_decision(
                "escalation",
                input_summary=message[:100],
                chosen="escalate",
                reason=trigger.reason,
                metadata={"priority": trigger.priority, "details": trigger.details},
            )
        return trigger
    def _keyword_sentiment(self, text: str) -> float:
        neg = ["disappointed", "bad", "useless", "broken"]
        pos = ["love", "great", "thanks", "happy"]
        t = text.lower()
        n_count = sum(1 for w in neg if w in t)
        p_count = sum(1 for w in pos if w in t)
        return (p_count - n_count) / (p_count + n_count) if (p_count + n_count) > 0 else 0.0

class ResponseGenerator:
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", self.DEFAULT_MODEL)

    async def generate(self, message, context, intent, entities, products, extra_context=None) -> str:
        store_name = getattr(context.store, "name", None) or "this store"
        product_block = ""
        if products:
            try:
                lines = []
                for p in products[:5]:
                    title = getattr(p, "title", None) or (p.get("title") if isinstance(p, dict) else "Product")
                    price = getattr(p, "price", None) or (p.get("price") if isinstance(p, dict) else "")
                    lines.append(f"- {title} ({price})" if price else f"- {title}")
                product_block = "\n\nMatching products:\n" + "\n".join(lines)
            except Exception:
                product_block = ""

        system_prompt = f"""You are Jerry, the AI customer service assistant for {store_name}.

PERSONALITY: Friendly, concise, helpful. Talk like a real shop assistant — warm but efficient. Short replies (1-3 sentences usually). No corporate jargon.

CONVERSATION RULES:
- ALWAYS use the conversation history. If the customer just gave you an order number after you asked for one, treat the number as their order number — do NOT ask again or change topic.
- If the customer replies with a short answer (a number, "yes", "no", a colour, a size), interpret it in the context of YOUR previous question.
- Never repeat the welcome greeting. Never restart the conversation.
- If asked about refunds/returns: this store offers 30-day returns with a prepaid label by email. Refunds are issued to the original payment method ONCE the item is received back. We don't refund before receiving the item, but reassure the customer the label is fast and the refund is processed within 2 business days of receipt.
- For order tracking: once the customer gives you an order number, confirm you'll look it up and (in this demo) tell them their order is on the way and will arrive in 2-3 business days.
- For product questions: be helpful, suggest options, ask clarifying questions about size/colour/budget.

CURRENT TURN INTENT: {intent}{product_block}"""

        messages = [
            {"role": "system", "content": system_prompt},
            *[m.to_groq_format() for m in context.get_recent_history(12)],
            {"role": "user", "content": message}
        ]
        try:
            loop = asyncio.get_running_loop()
            with Timer() as t:
                res = await loop.run_in_executor(
                    None,
                    lambda: self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.3,
                        max_tokens=400,
                    ),
                )
            completion_text = res.choices[0].message.content

            # LLM call instrumentation — tokens, latency, summaries
            usage = getattr(res, "usage", None)
            log_llm_call(
                model=self.model,
                prompt_summary=f"{message[:80]}",
                completion_summary=completion_text[:120] if completion_text else "",
                tokens_in=getattr(usage, "prompt_tokens", 0) if usage else 0,
                tokens_out=getattr(usage, "completion_tokens", 0) if usage else 0,
                latency_ms=t.ms,
            )
            return completion_text
        except Exception as e:
            logger.error(f"Groq error: {e}")
            log_llm_call(model=self.model, prompt_summary=message[:80], error=str(e), latency_ms=0)
            return "I'm having a slight technical glitch. One of our humans will be with you shortly!"

# ============================================================================
# FALLBACK STUBS (replaced at runtime by real services in main.py)
# ============================================================================

class _MockProductIntelligence:
    """No-op product search until real Pinecone service is wired in."""
    async def search(self, query: str, store_id: str, entities: dict) -> list:
        return []

class _InMemoryContextManager:
    """Simple dict-based context store for development/fallback."""
    def __init__(self):
        self._contexts: dict[str, Any] = {}

    def get(self, session_id: str):
        return self._contexts.get(session_id)

    def set(self, session_id: str, context):
        self._contexts[session_id] = context


class _RedisContextManager:
    """
    Redis-backed context store — persists conversation history across
    Railway redeploys and server restarts so Jerry remembers the full
    chat when a user reconnects mid-conversation.

    Falls back to a fresh context on any Redis error (fail-open).
    TTL: 24 hours (matching the JWT token lifetime).
    """
    TTL = 86_400  # 24 h

    def __init__(self, redis_url: str):
        import redis.asyncio as aioredis
        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._prefix = "jerry:ctx:"

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    async def get_async(self, session_id: str):
        try:
            raw = await self._redis.get(self._key(session_id))
            if raw:
                return ConversationContext.from_json(raw)
        except Exception as e:
            logger.warning(f"Redis context get failed (using fresh context): {e}")
        return None

    async def set_async(self, session_id: str, context: "ConversationContext"):
        try:
            await self._redis.setex(self._key(session_id), self.TTL, context.to_json())
        except Exception as e:
            logger.warning(f"Redis context set failed: {e}")

    async def delete_async(self, session_id: str):
        try:
            await self._redis.delete(self._key(session_id))
        except Exception as e:
            logger.warning(f"Redis context delete failed: {e}")

# ============================================================================
# CONVERSATION ENGINE — THE MAIN ORCHESTRATOR
# ============================================================================

class ConversationEngine:
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.response_generator = ResponseGenerator()
        self.escalation_handler = EscalationHandler()
        self._product_intelligence = _MockProductIntelligence()
        # Try Redis first; fall back to in-memory
        redis_url = os.getenv("REDIS_URL", "")
        if redis_url:
            try:
                self._redis_manager = _RedisContextManager(redis_url)
                self._context_manager = _InMemoryContextManager()  # local cache
                logger.info("ConversationEngine: Redis context store active")
            except Exception as e:
                logger.warning(f"Redis context store unavailable, using in-memory: {e}")
                self._redis_manager = None
                self._context_manager = _InMemoryContextManager()
        else:
            self._redis_manager = None
            self._context_manager = _InMemoryContextManager()

    async def get_or_create_context(self, session_id: str, store_id: str) -> ConversationContext:
        # Check local cache first (fast path)
        existing = self._context_manager.get(session_id)
        if existing:
            return existing
        # Try Redis (survives redeploys)
        if self._redis_manager:
            existing = await self._redis_manager.get_async(session_id)
            if existing:
                self._context_manager.set(session_id, existing)
                return existing
        context = ConversationContext(session_id=session_id, store_id=store_id)
        self._context_manager.set(session_id, context)
        return context

    async def _save_context(self, context: ConversationContext) -> None:
        """Persist context to Redis after each message."""
        if self._redis_manager:
            await self._redis_manager.set_async(context.session_id, context)

    async def end_session(self, session_id: str) -> None:
        self._context_manager._contexts.pop(session_id, None)
        if self._redis_manager:
            await self._redis_manager.delete_async(session_id)

    async def process_message(self, message: str, context: ConversationContext) -> EngineResponse:
        # Firewall scanning is handled in main.py (single scan point, fully
        # logged). process_message receives only pre-approved messages.

        # ── STEP 1: VALIDATION ──
        if len(message) > MAX_MESSAGE_LENGTH:
            return EngineResponse(
                text="Message too long!",
                intent="general",
                entities={},
                session_id=context.session_id,
            )

        # ── STEP 2: LOGIC PIPELINE ──
        intent = self.intent_classifier.classify(message, context)
        context.intent = intent
        entities = self.entity_extractor.extract(message)

        products = []
        if intent == "product_search":
            products = await self._product_intelligence.search(
                message, context.store_id, entities
            )

        response_text = await self.response_generator.generate(
            message, context, intent, entities, products
        )

        # ── STEP 3: ESCALATION & HISTORY ──
        escalation = self.escalation_handler.check(message, response_text, context)
        if escalation:
            response_text += f"\n\nConnecting you to a human ({escalation.reason})..."
            context.escalated = True

        context.add_message("user", message)
        context.add_message("assistant", response_text)

        # Outbound firewall scan is handled in main.py (single scan point).

        # ── STEP 4: PERSIST CONTEXT TO REDIS (survives redeploys) ──
        await self._save_context(context)

        # ── STEP 6: SAVE FULL INTERACTION TO DB ──
        if hasattr(self, "analytics") and self.analytics is not None:
            await self.analytics.track_conversation(
                store_id=context.store_id,
                session_id=context.session_id,
                message=message,
                response_text=response_text,
                intent=intent,
                entities=entities,
                products_shown=len(products),
                escalated=bool(escalation),
                turn_number=context.message_count,
                # latency_ms and firewall_verdict are logged at the main.py level
            )

        return EngineResponse(
            text=response_text,
            intent=intent,
            entities=entities,
            products=products,
            escalated=bool(escalation),
            session_id=context.session_id,
        )
