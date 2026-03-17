"""
CodeDebt Guardian — AI Gateway
Secure model key vault, multi-model routing, token metering, circuit breaker.
No model API keys are exposed to client code — only the gateway holds keys.
"""

import logging
import os
import time
from enum import Enum
from typing import Any, Dict, List, Optional

from config import settings

logger = logging.getLogger(__name__)


class AIModel(str, Enum):
    """Available AI models with their routing profiles."""

    OLLAMA_QWEN = "ollama-qwen2.5-coder:7b"  # free, local, no limits
    OLLAMA_MISTRAL = "ollama-mistral:7b"  # free, local, fast
    GROQ_LLAMA = "groq-llama-3.3-70b"  # free tier: 14,400 RPD
    GEMINI_FLASH = "gemini-2.0-flash"  # free tier: 1,500 RPD
    OPENAI_GPT4O = "gpt-4o"  # paid: last resort only
    EMBEDDING = "text-embedding-3-small"


class TaskType(str, Enum):
    """AI task types that determine model routing."""

    CODE_ANALYSIS = "code_analysis"
    FIX_GENERATION = "fix_generation"
    COMPLEX_REFACTOR = "complex_refactor"
    PRIORITY_RANKING = "priority_ranking"
    EMBEDDING = "embedding"
    CHAT = "chat"


# ── Model Routing Table ─────────────────────────────────────────────────
MODEL_ROUTES: Dict[TaskType, List[AIModel]] = {
    TaskType.CODE_ANALYSIS: [
        AIModel.OLLAMA_QWEN,
        AIModel.GROQ_LLAMA,
        AIModel.GEMINI_FLASH,
    ],
    TaskType.FIX_GENERATION: [
        AIModel.GROQ_LLAMA,
        AIModel.OLLAMA_QWEN,
        AIModel.GEMINI_FLASH,
    ],
    TaskType.COMPLEX_REFACTOR: [
        AIModel.GROQ_LLAMA,
        AIModel.GEMINI_FLASH,
        AIModel.OPENAI_GPT4O,
    ],
    TaskType.PRIORITY_RANKING: [AIModel.OLLAMA_MISTRAL, AIModel.GROQ_LLAMA],
    TaskType.EMBEDDING: [AIModel.EMBEDDING],
    TaskType.CHAT: [AIModel.GEMINI_FLASH, AIModel.GROQ_LLAMA],
}


class OllamaClient:
    """Zero-cost local LLM via Ollama. Falls back gracefully if not running."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self._available = False

    def health_check(self) -> bool:
        """Check if Ollama is running with a 2-second timeout."""
        import httpx

        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            self._available = resp.status_code == 200
            return self._available
        except Exception:
            self._available = False
            return False

    def chat_sync(
        self,
        model: str,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        """Send a chat completion request to Ollama. Raises on failure."""
        import httpx

        try:
            resp = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "content": data["message"]["content"],
                "tokens_input": 0,
                "tokens_output": 0,
            }
        except Exception as e:
            raise RuntimeError(f"Ollama unavailable ({self.base_url}): {e}")


class CircuitState:
    """Simple circuit breaker per model."""

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 60.0):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = 0.0
        self.is_open = False

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.warning("Circuit breaker OPEN")

    def record_success(self) -> None:
        self.failure_count = 0
        self.is_open = False

    def can_attempt(self) -> bool:
        if not self.is_open:
            return True
        if time.time() - self.last_failure_time > self.reset_timeout:
            self.is_open = False
            self.failure_count = 0
            return True
        return False


class TokenMeter:
    """Track token usage per org per model."""

    def __init__(self):
        self._usage: Dict[str, Dict[str, int]] = {}
        try:
            import redis as _r
            from config import settings
            self._redis = _r.from_url(settings.REDIS_URL, decode_responses=True)
            self._redis.ping()
        except Exception:
            self._redis = None

    def record(
        self, org_id: str, model: str, input_tokens: int, output_tokens: int
    ) -> None:
        key = f"{org_id}:{model}"
        if key not in self._usage:
            self._usage[key] = {"input": 0, "output": 0, "calls": 0}
        self._usage[key]["input"] += input_tokens
        self._usage[key]["output"] += output_tokens
        self._usage[key]["calls"] += 1
        if getattr(self, "_redis", None):
            try:
                rk = f"token_meter:{key}"
                self._redis.hincrby(rk, "input", input_tokens)
                self._redis.hincrby(rk, "output", output_tokens)
                self._redis.hincrby(rk, "calls", 1)
                self._redis.expire(rk, 86400 * 30)
            except Exception:
                pass

    def get_usage(self, org_id: str) -> Dict[str, Any]:
        result = {}
        for key, data in self._usage.items():
            if key.startswith(f"{org_id}:"):
                model = key.split(":", 1)[1]
                result[model] = data.copy()
        return result


class AIGateway:
    """
    Central AI Gateway — the ONLY component that touches model API keys.

    Responsibilities:
    1. Key Vault: Holds API keys, injects them at call time
    2. Model Router: Routes requests to optimal model based on task type
    3. Token Meter: Tracks usage per org for billing
    4. Circuit Breaker: Automatic failover on provider errors
    """

    def __init__(self):
        self._circuits: Dict[str, CircuitState] = {}
        self._meter = TokenMeter()
        self._clients: Dict[str, Any] = {}
        self._ollama: Optional[OllamaClient] = None
        self._init_clients()

    def _init_clients(self) -> None:
        """Initialize AI provider clients (keys never leave this class)."""
        # Ollama (local, free, zero-config)
        ollama = OllamaClient()
        if ollama.health_check():
            self._ollama = ollama
            logger.info(f"Ollama client initialized at {ollama.base_url}")
        else:
            logger.info("Ollama not available — will use cloud providers")

        # Groq
        if settings.GROQ_API_KEY:
            try:
                from groq import Groq

                self._clients["groq"] = Groq(api_key=settings.GROQ_API_KEY)
                logger.info("Groq client initialized")
            except Exception as e:
                logger.warning(f"Groq client init failed: {e}")

        # Gemini
        if settings.GOOGLE_API_KEY:
            try:
                import google.generativeai as genai

                genai.configure(api_key=settings.GOOGLE_API_KEY)
                self._clients["gemini"] = genai.GenerativeModel("gemini-2.0-flash")
                logger.info("Gemini client initialized")
            except Exception as e:
                logger.warning(f"Gemini client init failed: {e}")

        # OpenAI
        if settings.OPENAI_API_KEY:
            try:
                import openai

                self._clients["openai"] = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.warning(f"OpenAI client init failed: {e}")

    def _get_circuit(self, model: str) -> CircuitState:
        if model not in self._circuits:
            self._circuits[model] = CircuitState()
        return self._circuits[model]

    async def complete(
        self,
        prompt: str,
        task_type: TaskType,
        org_id: str = "system",
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Route an AI completion request through the gateway.

        Returns:
            {"content": "...", "model": "...", "tokens_input": N, "tokens_output": N, "latency_ms": N}
        """
        models = MODEL_ROUTES.get(task_type, [AIModel.GEMINI_FLASH])
        last_error = None

        for model in models:
            circuit = self._get_circuit(model.value)
            if not circuit.can_attempt():
                logger.warning(f"Circuit open for {model.value}, skipping")
                continue

            try:
                start = time.time()
                result = await self._call_model(
                    model, prompt, system_prompt, temperature, max_tokens
                )
                latency = (time.time() - start) * 1000

                circuit.record_success()
                self._meter.record(
                    org_id,
                    model.value,
                    result.get("tokens_input", 0),
                    result.get("tokens_output", 0),
                )

                result["model"] = model.value
                result["latency_ms"] = round(latency, 1)
                return result

            except Exception as e:
                circuit.record_failure()
                last_error = e
                logger.warning(f"Model {model.value} failed: {e}, trying fallback")
                continue

        raise RuntimeError(f"All AI models failed. Last error: {last_error}")

    async def _call_model(
        self,
        model: AIModel,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """Dispatch to specific provider."""
        import asyncio

        # Ollama models
        if model in (AIModel.OLLAMA_QWEN, AIModel.OLLAMA_MISTRAL):
            if not self._ollama:
                raise RuntimeError(f"Ollama not available for {model.value}")
            # Extract the model name after "ollama-"
            ollama_model = model.value.replace("ollama-", "")
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            return await asyncio.to_thread(
                self._ollama.chat_sync, ollama_model, messages, temperature, max_tokens
            )

        elif model in (AIModel.GROQ_LLAMA,) and "groq" in self._clients:
            return await asyncio.to_thread(
                self._call_groq, prompt, system_prompt, temperature, max_tokens
            )
        elif model == AIModel.GEMINI_FLASH and "gemini" in self._clients:
            return await asyncio.to_thread(
                self._call_gemini, prompt, system_prompt, temperature, max_tokens
            )
        elif model == AIModel.OPENAI_GPT4O and "openai" in self._clients:
            return await asyncio.to_thread(
                self._call_openai, prompt, system_prompt, temperature, max_tokens
            )
        else:
            raise RuntimeError(f"No client available for {model.value}")

    def _call_groq(
        self, prompt: str, system_prompt: str, temperature: float, max_tokens: int
    ) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        resp = self._clients["groq"].chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return {
            "content": resp.choices[0].message.content,
            "tokens_input": resp.usage.prompt_tokens if resp.usage else 0,
            "tokens_output": resp.usage.completion_tokens if resp.usage else 0,
        }

    def _call_gemini(
        self, prompt: str, system_prompt: str, temperature: float, max_tokens: int
    ) -> dict:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        resp = self._clients["gemini"].generate_content(
            full_prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        content = resp.text if resp and hasattr(resp, "text") else ""
        return {
            "content": content,
            "tokens_input": 0,
            "tokens_output": 0,
        }

    def _call_openai(
        self, prompt: str, system_prompt: str, temperature: float, max_tokens: int
    ) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        resp = self._clients["openai"].chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return {
            "content": resp.choices[0].message.content,
            "tokens_input": resp.usage.prompt_tokens if resp.usage else 0,
            "tokens_output": resp.usage.completion_tokens if resp.usage else 0,
        }

    def get_usage(self, org_id: str) -> Dict[str, Any]:
        """Get token usage for an organization."""
        return self._meter.get_usage(org_id)

    async def get_embedding(self, text: str) -> List[float]:
        """Get semantic embedding for text.
        Priority:
        1. OpenAI text-embedding-3-small
        2. Ollama nomic-embed-text
        3. Gemini text-embedding-004
        """
        import asyncio

        if "openai" in self._clients:
            try:
                return await asyncio.to_thread(self._openai_embedding, text)
            except Exception as e:
                logger.warning(f"OpenAI embedding failed: {e}")

        if self._ollama:
            try:
                return await asyncio.to_thread(self._ollama_embedding, text)
            except Exception as e:
                logger.warning(f"Ollama embedding failed: {e}")

        if "gemini" in self._clients:
            try:
                return await asyncio.to_thread(self._gemini_embedding, text)
            except Exception as e:
                logger.warning(f"Gemini embedding failed: {e}")

        raise RuntimeError("No embedding providers available or all failed.")

    def _openai_embedding(self, text: str) -> List[float]:
        resp = self._clients["openai"].embeddings.create(
            input=[text], model="text-embedding-3-small"
        )
        return resp.data[0].embedding

    def _ollama_embedding(self, text: str) -> List[float]:
        import httpx

        resp = httpx.post(
            f"{self._ollama.base_url}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    def _gemini_embedding(self, text: str) -> List[float]:
        import google.generativeai as genai

        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]

    def health(self) -> Dict[str, bool]:
        """Check which providers are available."""
        return {
            "ollama": self._ollama is not None and self._ollama._available,
            "groq": "groq" in self._clients,
            "gemini": "gemini" in self._clients,
            "openai": "openai" in self._clients,
        }


# Singleton gateway instance
ai_gateway = AIGateway()
