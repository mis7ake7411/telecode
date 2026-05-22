import os
import asyncio

import pytest
from fastapi import BackgroundTasks

import telecode.server as server


def _dummy_telegram():
    return server.TelegramConfig(bot_token="test-token")


def _set_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.environ.pop("TELEGRAM_TUNNEL_URL", None)
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    os.environ.pop("TELECODE_CODEX_MODEL_ALLOWLIST", None)
    os.environ.pop("TELECODE_CODEX_MODEL_DEFAULT", None)
    os.environ.pop("TELECODE_CODEX_MODEL", None)
    with server._CODEX_EMPTY_OUTPUT_COUNTS_GUARD:
        server._CODEX_EMPTY_OUTPUT_COUNTS.clear()
    with server._IMAGE_GEN_PENDING_GUARD:
        server._IMAGE_GEN_PENDING_REQUESTS.clear()


def test_handle_text_message_calls_prompt(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    captured = {}

    def fake_handle_prompt(prompt, chat_id, message_id, timeout_s, telegram, sessions_file, engine):
        captured["prompt"] = prompt

    monkeypatch.setattr(server, "_handle_prompt", fake_handle_prompt)
    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: 1)
    os.environ["TELECODE_ALLOWED_USERS"] = ""

    msg = {
        "message_id": 1,
        "chat": {"id": 111},
        "text": "hello",
        "from": {"id": 111, "username": "tester"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "claude")

    assert captured["prompt"] == "hello"


def test_engine_command_persists_to_local_file(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    sent = []

    def fake_send(*args, **kwargs):
        sent.append(kwargs.get("text") or args[2])
        return 1

    monkeypatch.setattr(server, "_send_message", fake_send)

    msg = {
        "message_id": 2,
        "chat": {"id": 222},
        "text": "/engine codex",
        "from": {"id": 222, "username": "tester"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "claude")

    config_path = tmp_path / ".telecode"
    assert config_path.exists()
    content = config_path.read_text()
    assert "TELECODE_ENGINE=codex" in content
    assert any("Switched engine" in line for line in sent)


def test_model_command_persists_to_local_file(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    os.environ["TELECODE_CODEX_MODEL_ALLOWLIST"] = "gpt-5.5,gpt-5.4,gpt-5.4-mini,gpt-5.3-codex,gpt-5.2"
    os.environ["TELECODE_CODEX_MODEL_DEFAULT"] = "gpt-5.2"
    sent = []

    def fake_send(*args, **kwargs):
        sent.append(kwargs.get("text") or args[2])
        return 1

    monkeypatch.setattr(server, "_send_message", fake_send)

    msg = {
        "message_id": 21,
        "chat": {"id": 221},
        "text": "/model gpt-5.4-mini",
        "from": {"id": 221, "username": "tester"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "codex")

    config_path = tmp_path / ".telecode"
    assert config_path.exists()
    content = config_path.read_text()
    assert "TELECODE_CODEX_MODEL_OVERRIDE_221=gpt-5.4-mini" in content
    assert "TELECODE_CODEX_MODEL_DEFAULT=" not in content
    assert any("Switched Codex model to gpt-5.4-mini for this chat." in line for line in sent)


def test_model_command_rejects_not_in_allowlist(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    os.environ["TELECODE_CODEX_MODEL_ALLOWLIST"] = "gpt-5.5,gpt-5.4,gpt-5.4-mini,gpt-5.3-codex,gpt-5.2"
    sent = []

    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)
    monkeypatch.setattr(server, "_handle_prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError))

    msg = {
        "message_id": 22,
        "chat": {"id": 222},
        "text": "/model gpt-6",
        "from": {"id": 222, "username": "tester"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "codex")

    assert len(sent) == 1
    assert "unsupported model" in sent[0].lower()


def test_model_command_without_args_shows_current(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    os.environ["TELECODE_CODEX_MODEL_ALLOWLIST"] = "gpt-5.5,gpt-5.4,gpt-5.4-mini,gpt-5.3-codex,gpt-5.2"
    os.environ["TELECODE_CODEX_MODEL_DEFAULT"] = "gpt-5.2"
    sent = []

    server._set_codex_model_for_chat(223, "gpt-5.3-codex", ".telecode")
    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)
    monkeypatch.setattr(server, "_handle_prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError))

    msg = {
        "message_id": 23,
        "chat": {"id": 223},
        "text": "/model",
        "from": {"id": 223, "username": "tester"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "codex")

    assert len(sent) == 1
    assert "Current Codex model: gpt-5.3-codex" in sent[0]


def test_allow_command_adds_username_to_allowlist(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = "224"
    sent = []

    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)
    monkeypatch.setattr(server, "_handle_prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError))

    msg = {
        "message_id": 25,
        "chat": {"id": 224},
        "text": "/allow @friend_tester",
        "from": {"id": 224, "username": "owner"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "codex")

    assert sent == ["Allowed @friend_tester."]
    assert server._is_user_allowed_by_meta(None, "friend_tester") is True
    content = (tmp_path / ".telecode").read_text()
    assert "TELECODE_ALLOWED_USERS=224,@friend_tester" in content


def test_deny_command_removes_username_from_allowlist(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = "225,@friend_tester"
    sent = []

    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)
    monkeypatch.setattr(server, "_handle_prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError))

    msg = {
        "message_id": 26,
        "chat": {"id": 225},
        "text": "/deny @friend_tester",
        "from": {"id": 225, "username": "owner"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "codex")

    assert sent == ["Removed: @friend_tester."]
    assert server._is_user_allowed_by_meta(None, "friend_tester") is False
    content = (tmp_path / ".telecode").read_text()
    assert "TELECODE_ALLOWED_USERS=225" in content


def test_allow_command_invalid_argument_shows_usage(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = "226"
    sent = []

    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)
    monkeypatch.setattr(server, "_handle_prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError))

    msg = {
        "message_id": 27,
        "chat": {"id": 226},
        "text": "/allow ???",
        "from": {"id": 226, "username": "owner"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "codex")

    assert len(sent) == 1
    assert "Usage: /allow <user_id|@username> or /deny <user_id|@username>" == sent[0]


def test_cli_command_runs_without_prompt(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    os.environ["TELECODE_ENABLE_CLI"] = "1"
    captured = {"ran": False}
    sent = []

    def fake_run(cmd):
        captured["ran"] = True
        return "ok"

    monkeypatch.setattr(server, "_run_cli_command", fake_run)
    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)
    monkeypatch.setattr(server, "_handle_prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError))

    msg = {
        "message_id": 3,
        "chat": {"id": 333},
        "text": "/cli pwd",
        "from": {"id": 333, "username": "tester"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "claude")

    assert captured["ran"] is True
    assert sent == ["ok"]


def test_cli_command_blocked_when_disabled(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    os.environ["TELECODE_ENABLE_CLI"] = "0"
    sent = []

    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)
    monkeypatch.setattr(server, "_run_cli_command", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError))

    msg = {
        "message_id": 31,
        "chat": {"id": 331},
        "text": "/cli pwd",
        "from": {"id": 331, "username": "tester"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "claude")

    assert len(sent) == 1
    assert "disabled" in sent[0].lower()


def test_handle_photo_message_passes_image_path(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    captured = {}

    def fake_download(config, file_id):
        return b"fake", "image.jpg"

    def fake_handle_prompt(prompt, chat_id, message_id, timeout_s, telegram, sessions_file, engine, image_paths=None):
        captured["paths"] = image_paths

    monkeypatch.setattr(server, "telegram_download_file", fake_download)
    monkeypatch.setattr(server, "_handle_prompt", fake_handle_prompt)
    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: 1)

    msg = {
        "message_id": 4,
        "chat": {"id": 444},
        "caption": "What is this?",
        "photo": [{"file_id": "file1", "file_size": 10}],
        "from": {"id": 444, "username": "tester"},
    }
    server.handle_photo_message(msg, None, _dummy_telegram(), ".telecode", "claude")

    assert captured["paths"]
    assert not os.path.exists(captured["paths"][0])


def test_handle_document_image_passes_image_path(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    captured = {}

    def fake_download(config, file_id):
        return b"fake", "image.png"

    def fake_handle_prompt(prompt, chat_id, message_id, timeout_s, telegram, sessions_file, engine, image_paths=None):
        captured["paths"] = image_paths

    monkeypatch.setattr(server, "telegram_download_file", fake_download)
    monkeypatch.setattr(server, "_handle_prompt", fake_handle_prompt)
    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: 1)

    msg = {
        "message_id": 5,
        "chat": {"id": 555},
        "caption": "What is this?",
        "document": {"file_id": "file2", "mime_type": "image/png"},
        "from": {"id": 555, "username": "tester"},
    }
    server.handle_document_message(msg, None, _dummy_telegram(), ".telecode", "claude")

    assert captured["paths"]
    assert not os.path.exists(captured["paths"][0])


def test_disallowed_user_is_blocked(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = "1234"
    sent = []

    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)
    monkeypatch.setattr(server, "_handle_prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError))

    msg = {
        "message_id": 6,
        "chat": {"id": 666},
        "text": "hello",
        "from": {"id": 9999, "username": "tester"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "claude")

    assert sent == ["Not authorized."]


def test_allowed_username_is_accepted(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = "testuser"
    captured = {}

    def fake_handle_prompt(prompt, chat_id, message_id, timeout_s, telegram, sessions_file, engine):
        captured["prompt"] = prompt

    monkeypatch.setattr(server, "_handle_prompt", fake_handle_prompt)
    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: 1)

    msg = {
        "message_id": 7,
        "chat": {"id": 777},
        "text": "hi",
        "from": {"id": 777, "username": "TestUser"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "claude")

    assert captured["prompt"] == "hi"


def test_codex_empty_output_returns_friendly_message(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    sent = []

    monkeypatch.setattr(
        server,
        "ask_codex_exec",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("Codex returned empty output.")),
    )
    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)

    msg = {
        "message_id": 8,
        "chat": {"id": 888},
        "text": "continue",
        "from": {"id": 888, "username": "tester"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "codex")

    assert len(sent) == 1
    assert "returned no output" in sent[0].lower()
    assert not sent[0].startswith("Error:")


def test_codex_empty_output_auto_reset_after_threshold(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    os.environ["TELECODE_CODEX_EMPTY_OUTPUT_RESET_N"] = "2"
    os.environ["TELECODE_CODEX_EMPTY_OUTPUT_RETRY_DELAY_S"] = "0"
    sent = []

    server._save_sessions(".telecode", {"claude": None, "codex": "old-session"})

    calls = {"n": 0}

    def fake_codex(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] <= 4:
            raise RuntimeError("Codex returned empty output.")
        return ("Recovered after reset", "new-session", "logs")

    monkeypatch.setattr(server, "ask_codex_exec", fake_codex)
    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)

    msg = {
        "message_id": 9,
        "chat": {"id": 889},
        "text": "continue",
        "from": {"id": 889, "username": "tester"},
    }

    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "codex")
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "codex")

    assert calls["n"] == 5
    assert len(sent) == 2
    assert "auto-reset after 2 consecutive empty outputs" in sent[0].lower()
    assert "automatically reset" in sent[1].lower()
    assert "Recovered after reset" in sent[1]

    sessions = server._load_sessions(".telecode")
    assert sessions["codex"] == "new-session"


def test_handle_prompt_passes_codex_model_override(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    os.environ["TELECODE_CODEX_MODEL_ALLOWLIST"] = "gpt-5.5,gpt-5.4,gpt-5.4-mini,gpt-5.3-codex,gpt-5.2"
    os.environ["TELECODE_CODEX_MODEL_DEFAULT"] = "gpt-5.2"
    captured = {}

    server._set_codex_model_for_chat(990, "gpt-5.4", ".telecode")

    def fake_codex(prompt, session_id, timeout_s, image_paths=None, model=None):
        captured["model"] = model
        return ("ok", "s1", "logs")

    monkeypatch.setattr(server, "ask_codex_exec", fake_codex)
    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: 1)

    msg = {
        "message_id": 24,
        "chat": {"id": 990},
        "text": "hello",
        "from": {"id": 990, "username": "tester"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "codex")

    assert captured["model"] == "gpt-5.4"


def test_image_generation_request_returns_guidance(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    sent = []

    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)
    monkeypatch.setattr(server, "_handle_prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError))

    msg = {
        "message_id": 10,
        "chat": {"id": 901},
        "text": "幫我生成一張海報",
        "from": {"id": 901, "username": "tester"},
    }
    server.handle_text_message(msg, None, _dummy_telegram(), ".telecode", "claude")

    assert len(sent) == 1
    assert "還不能直接把新生成的圖片回傳到 Telegram" in sent[0]
    assert "1. 產生 prompt" in sent[0]
    assert "2. 產生本機執行指令" in sent[0]


def test_image_generation_followup_option_one_returns_prompt(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    sent = []

    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)
    monkeypatch.setattr(server, "_handle_prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError))

    first = {
        "message_id": 11,
        "chat": {"id": 902},
        "text": "generate an image of a fox in snow",
        "from": {"id": 902, "username": "tester"},
    }
    second = {
        "message_id": 12,
        "chat": {"id": 902},
        "text": "1",
        "from": {"id": 902, "username": "tester"},
    }
    server.handle_text_message(first, None, _dummy_telegram(), ".telecode", "claude")
    server.handle_text_message(second, None, _dummy_telegram(), ".telecode", "claude")

    assert len(sent) == 2
    assert "圖片提示詞草稿" in sent[1]


def test_image_generation_followup_option_two_returns_local_command(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELECODE_ALLOWED_USERS"] = ""
    sent = []

    monkeypatch.setattr(server, "_send_message", lambda *args, **kwargs: sent.append(args[2]) or 1)
    monkeypatch.setattr(server, "_handle_prompt", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError))

    first = {
        "message_id": 13,
        "chat": {"id": 903},
        "text": "幫我畫一張產品情境圖",
        "from": {"id": 903, "username": "tester"},
    }
    second = {
        "message_id": 14,
        "chat": {"id": 903},
        "text": "2",
        "from": {"id": 903, "username": "tester"},
    }
    server.handle_text_message(first, None, _dummy_telegram(), ".telecode", "claude")
    server.handle_text_message(second, None, _dummy_telegram(), ".telecode", "claude")

    assert len(sent) == 2
    assert "本機執行指令" in sent[1]
    assert "codex exec" in sent[1]


class _DummyRequest:
    def __init__(self, payload: dict, headers: dict[str, str]):
        self._payload = payload
        self.headers = headers

    async def json(self):
        return self._payload


def test_webhook_header_secret_token_rejected(monkeypatch, tmp_path):
    _set_cwd(tmp_path, monkeypatch)
    os.environ["TELEGRAM_WEBHOOK_SECRET"] = "path-secret"
    os.environ["TELEGRAM_WEBHOOK_SECRET_TOKEN"] = "header-secret"
    os.environ["TELEGRAM_BOT_TOKEN"] = "token"
    os.environ["TELECODE_ENGINE"] = "claude"
    os.environ["TELECODE_ALLOWED_USERS"] = "123"

    req = _DummyRequest({"message": None}, headers={})
    with pytest.raises(server.HTTPException) as exc_info:
        asyncio.run(server.telegram_webhook("path-secret", req, BackgroundTasks()))

    assert exc_info.value.status_code == 401
