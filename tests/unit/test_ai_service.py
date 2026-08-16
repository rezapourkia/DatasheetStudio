"""Unit tests for the real HTTP AI service."""

import json
import urllib.error
import unittest.mock as mock

import pytest

from datasheet_studio.services.ai_service import AIService, AIServiceError


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _make(provider="DeepSeek", api_key="sk-test", base_url="", model="deepseek-chat"):
    service = AIService()
    service.configure(provider, api_key, base_url, model)
    return service


def test_openai_compatible_chat_request_and_parse():
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = {k: v for k, v in req.header_items()}
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse({"choices": [{"message": {"content": "Hello back"}}]})

    service = _make()
    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = service.chat([{"role": "user", "content": "hi"}])

    assert result == "Hello back"
    assert captured["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["body"]["model"] == "deepseek-chat"
    assert captured["body"]["messages"][-1]["content"] == "hi"


def test_chat_includes_selected_pages_context():
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse({"choices": [{"message": {"content": "x"}}]})

    service = _make()
    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        service.chat([{"role": "user", "content": "question"}], context="PAGE TEXT")

    system_msg = captured["body"]["messages"][0]
    assert system_msg["role"] == "system"
    assert "PAGE TEXT" in system_msg["content"]


def test_chat_requires_api_key():
    service = _make(api_key="")
    with pytest.raises(AIServiceError):
        service.chat([{"role": "user", "content": "hi"}])


def test_chat_http_error_raises_aiserviceerror():
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    service = _make()
    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(AIServiceError):
            service.chat([{"role": "user", "content": "hi"}])


def test_anthropic_uses_own_endpoint():
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse({"content": [{"type": "text", "text": "An answer"}]})

    service = _make(provider="Anthropic", model="claude-3-5-sonnet-20241022")
    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = service.chat([{"role": "user", "content": "hi"}])

    assert result == "An answer"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "sk-test"
    assert captured["body"]["messages"][-1]["content"] == "hi"


def test_gemini_uses_generate_content_endpoint():
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(
            {"candidates": [{"content": {"parts": [{"text": "Gem text"}]}}]}
        )

    service = _make(provider="Google Gemini", model="gemini-2.0-flash")
    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = service.chat([{"role": "user", "content": "hi"}])

    assert result == "Gem text"
    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash:generateContent"
    )
    assert captured["body"]["contents"][0]["parts"][0]["text"] == "hi"


def test_fetch_models_parses_list():
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return _FakeResponse({"data": [{"id": "model-a"}, {"id": "model-b"}]})

    service = _make()
    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        models = service.fetch_models()

    assert models == ["model-a", "model-b"]
    assert captured["url"] == "https://api.deepseek.com/v1/models"


def test_summary_builds_prompt():
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse({"choices": [{"message": {"content": "sum"}}]})

    service = _make()
    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        service.generate_summary("DATASHEET TEXT")

    user_msg = captured["body"]["messages"][-1]["content"]
    assert "DATASHEET TEXT" in user_msg


def test_chat_executes_tools_and_returns_final():
    calls = []
    responses = iter(
        [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "add_pages_to_selection",
                                        "arguments": '{"page_numbers": [35, 36]}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
            {"choices": [{"message": {"role": "assistant", "content": "Done"}}]},
        ]
    )

    def fake_urlopen(req, timeout=None):
        calls.append(json.loads(req.data.decode("utf-8")))
        return _FakeResponse(next(responses))

    executed = {}

    def executor(name, args):
        executed[name] = args
        return {"added": args["page_numbers"]}

    service = _make()
    tools = [
        {
            "type": "function",
            "function": {
                "name": "add_pages_to_selection",
                "parameters": {"type": "object"},
            },
        }
    ]
    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = service.chat(
            [{"role": "user", "content": "add uart pages"}],
            context="outline...",
            tools=tools,
            tool_executor=executor,
        )

    assert result == "Done"
    assert executed == {"add_pages_to_selection": {"page_numbers": [35, 36]}}
    assert "tools" in calls[0]
    assert calls[1]["messages"][-1]["role"] == "tool"
    assert calls[1]["messages"][-1]["tool_call_id"] == "call_1"


def test_chat_tool_call_without_executor_raises():
    responses = iter(
        [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_bookmarks",
                                        "arguments": "{}",
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    )

    def fake_urlopen(req, timeout=None):
        return _FakeResponse(next(responses))

    service = _make()
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_bookmarks",
                "parameters": {"type": "object"},
            },
        }
    ]
    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(AIServiceError):
            service.chat(
                [{"role": "user", "content": "hi"}],
                tools=tools,
                tool_executor=None,
            )
