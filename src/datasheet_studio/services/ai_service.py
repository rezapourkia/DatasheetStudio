"""AI service with real HTTP provider support for Datasheet Studio.

Supports DeepSeek, OpenAI, Anthropic, Google Gemini, and custom OpenAI-
compatible / Anthropic endpoints using only the Python standard library.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("datasheet_studio.ai")


class AIServiceError(Exception):
    """Raised when an AI provider request fails."""


DEFAULT_BASE_URLS = {
    "DeepSeek": "https://api.deepseek.com/v1",
    "OpenAI": "https://api.openai.com/v1",
    "Anthropic": "https://api.anthropic.com",
    "Google Gemini": "https://generativelanguage.googleapis.com/v1beta",
    "Custom": "",
}


class AIService:
    """Thin client for chat-completion style AI providers."""

    def __init__(self) -> None:
        self.provider: Optional[str] = None
        self.api_key: Optional[str] = None
        self.base_url: str = ""
        self.model: str = ""
        self.protocol: str = "OpenAI Compatible"

    def configure(
        self,
        provider: str,
        api_key: str,
        base_url: str = "",
        model: str = "",
        protocol: str = "OpenAI Compatible",
    ) -> None:
        """Configure the AI service with provider details."""
        self.provider = provider
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "").strip()
        self.model = (model or "").strip()
        self.protocol = protocol or "OpenAI Compatible"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: List[Dict[str, str]],
        context: Optional[str] = None,
        tools: Optional[List[dict]] = None,
        tool_executor=None,
    ) -> str:
        """Send a chat request to the configured provider and return its reply.

        When ``tools`` and ``tool_executor`` are provided, the provider's
        function-calling protocol is used: tool calls in the model reply are
        executed through ``tool_executor(name, args)`` and the results are fed
        back to the model until it returns a final text answer.
        """
        self._require_config()
        system_text = (
            "You are Datasheet Studio, an assistant that helps electronics "
            "engineers work with electronic component datasheets."
        )
        if context:
            system_text += "\n\nContext from the selected datasheet pages:\n" + context
        all_messages = [{"role": "system", "content": system_text}] + list(messages)

        LOG.info(
            "AI chat request: provider=%s model=%s messages=%d context_chars=%d",
            self.provider,
            self.model,
            len(all_messages),
            len(context or ""),
        )

        if self.provider == "Anthropic":
            return self._call_anthropic(all_messages)
        if self.provider == "Google Gemini":
            return self._call_gemini(all_messages)
        if self.provider == "Custom" and self.protocol == "Anthropic API":
            return self._call_anthropic(all_messages)
        # DeepSeek, OpenAI, and Custom (OpenAI Compatible / Custom REST) share
        # the /chat/completions contract.
        return self._call_openai_compatible(all_messages, tools, tool_executor)

    def generate_summary(self, content: str) -> str:
        """Generate a structured summary of the given content."""
        self._require_config()
        prompt = (
            "Summarize the following datasheet content in a clear, structured "
            "way. Highlight the most important specifications, sections, and "
            "any warnings or caveats.\n\n" + content
        )
        return self.chat([{"role": "user", "content": prompt}])

    def generate_report(self, content: str) -> str:
        """Generate a detailed technical report of the given content."""
        self._require_config()
        prompt = (
            "Write a detailed technical report about the following datasheet "
            "content: document structure, key findings, extracted "
            "specifications, and any caveats.\n\n" + content
        )
        return self.chat([{"role": "user", "content": prompt}])

    def test_connection(self) -> str:
        """Send a minimal request to verify the provider credentials."""
        self._require_config()
        return self.chat([{"role": "user", "content": "Reply with exactly: OK"}])

    def fetch_models(self) -> List[str]:
        """Fetch the available model list (OpenAI-compatible endpoints)."""
        self._require_config()
        base = self._effective_base_url()
        if not base:
            raise AIServiceError("Base URL is empty for this provider.")
        url = base + "/models"
        LOG.info("AI fetch_models url=%s", url)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        raw = self._http_get(url, headers)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise AIServiceError("Invalid JSON response while fetching models.")
        models = [m.get("id") for m in data.get("data", []) if m.get("id")]
        LOG.info("AI fetch_models received %d models", len(models))
        return models

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    def _require_config(self) -> None:
        if not self.api_key:
            raise AIServiceError(
                "No API key configured. Please set up your AI provider in Settings."
            )
        if not self.model:
            LOG.warning("AI model is empty; provider may reject the request.")

    def _effective_base_url(self) -> str:
        if self.base_url:
            return self.base_url.rstrip("/")
        return DEFAULT_BASE_URLS.get(self.provider or "", "")

    # ------------------------------------------------------------------
    # Provider request builders
    # ------------------------------------------------------------------

    def _call_openai_compatible(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[dict]] = None,
        tool_executor=None,
    ) -> str:
        base = self._effective_base_url()
        if not base:
            raise AIServiceError("Base URL is empty for this provider.")
        url = base + "/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model or "gpt-3.5-turbo",
            "messages": messages,
            "stream": False,
            "temperature": 0.2,
            # Allow long answers (e.g. a full 48-pin pinout table) without the
            # provider truncating them at its default output limit.
            "max_tokens": 8192,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = self._http_post_json(url, payload, headers)
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            raise AIServiceError(
                f"Unexpected response from provider: {str(data)[:300]}"
            )
        LOG.info(
            "AI raw response: message_fields=%s",
            sorted(message.keys()),
        )
        LOG.info(
            "AI response preview: %s",
            str(self._extract_message_content(message))[:500],
        )

        for _ in range(8):
            tool_calls = message.get("tool_calls")
            if tool_calls:
                if tool_executor is None:
                    raise AIServiceError(
                        "The model requested a tool but no tool executor was provided."
                    )
                messages.append(
                    {
                        "role": "assistant",
                        "content": self._extract_message_content(message) or "",
                        "tool_calls": tool_calls,
                    }
                )
                for call in tool_calls:
                    name = call.get("function", {}).get("name", "")
                    try:
                        args = json.loads(
                            call.get("function", {}).get("arguments") or "{}"
                        )
                    except json.JSONDecodeError:
                        args = {}
                    LOG.info("AI tool call: %s %s", name, args)
                    result = tool_executor(name, args)
                    if not isinstance(result, str):
                        result = json.dumps(result, ensure_ascii=False)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id", ""),
                            "content": result,
                        }
                    )
                payload["messages"] = messages
                data = self._http_post_json(url, payload, headers)
                try:
                    message = data["choices"][0]["message"]
                except (KeyError, IndexError, TypeError):
                    raise AIServiceError(
                        f"Unexpected response from provider: {str(data)[:300]}"
                    )
                continue

            content = self._extract_message_content(message)
            if isinstance(content, str) and content.strip():
                return content.strip()
            if len(str(content).strip()) > 0:
                return str(content).strip()

        content = self._extract_message_content(message)
        if isinstance(content, str) and content.strip():
            return content.strip()
        if len(str(content).strip()) > 0:
            return str(content).strip()
        raise AIServiceError("Model returned an empty response.")

    @staticmethod
    def _extract_message_content(message: Dict[str, Any]) -> str:
        """Extract plain text content from OpenAI-compatible chat messages."""
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue
                block_content = item.get("content")
                if isinstance(block_content, str):
                    parts.append(block_content)
            if parts:
                return "\n".join(parts).strip()
        return ""

    def _call_anthropic(self, messages: List[Dict[str, str]]) -> str:
        base = self._effective_base_url()
        if not base:
            raise AIServiceError("Base URL is empty for this provider.")
        url = base + "/v1/messages"
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        anthropic_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m["role"] != "system"
        ]
        payload: Dict[str, Any] = {
            "model": self.model or "claude-3-5-sonnet-20241022",
            "max_tokens": 2048,
            "messages": anthropic_messages,
        }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        data = self._http_post_json(url, payload, headers)
        try:
            parts = data.get("content") or []
            return "\n".join(
                block.get("text", "")
                for block in parts
                if block.get("type") == "text"
            )
        except (KeyError, TypeError):
            raise AIServiceError(
                f"Unexpected response from provider: {str(data)[:300]}"
            )

    def _call_gemini(self, messages: List[Dict[str, str]]) -> str:
        base = self._effective_base_url()
        if not base:
            raise AIServiceError("Base URL is empty for this provider.")
        model = self.model or "gemini-2.0-flash"
        url = f"{base}/models/{model}:generateContent"
        contents = []
        for m in messages:
            if m["role"] == "system":
                continue
            role = "user" if m["role"] != "assistant" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        payload = {"contents": contents}
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        data = self._http_post_json(url, payload, headers)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            raise AIServiceError(
                f"Unexpected response from provider: {str(data)[:300]}"
            )

    # ------------------------------------------------------------------
    # HTTP primitives
    # ------------------------------------------------------------------

    def _http_post_json(self, url: str, payload: dict, headers: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, headers=headers, method="POST"
        )
        raw = self._open(request)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise AIServiceError(f"Invalid JSON response from provider: {raw[:200]}")

    def _http_get(self, url: str, headers: dict) -> str:
        request = urllib.request.Request(url, headers=headers, method="GET")
        return self._open(request)

    def _open(self, request: urllib.request.Request) -> str:
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:  # noqa: BLE001
                pass
            raise AIServiceError(
                f"HTTP {exc.code} error from provider: {detail or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None) or exc
            raise AIServiceError(f"Network error contacting provider: {reason}") from exc
        except TimeoutError:
            raise AIServiceError("Request timed out contacting provider.") from None
