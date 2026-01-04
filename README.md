# Telecode

[![Tests](https://github.com/polinom/telecode/actions/workflows/tests.yml/badge.svg)](https://github.com/polinom/telecode/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/telecode.svg)](https://pypi.org/project/telecode/)

**Telecode** is a Telegram webhook server that bridges your Telegram conversations with AI-powered code execution engines (Claude Code and Codex). It allows you to interact with AI assistants directly through Telegram, execute shell commands on your server, process images, transcribe voice messages, and even get text-to-speech audio responses.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [How It Works](#how-it-works)
  - [Architecture](#architecture)
  - [Communication Flow](#communication-flow)
  - [Session Management](#session-management)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
  - [Configuration Files](#configuration-files)
  - [Configuration Keys](#configuration-keys)
- [Usage](#usage)
  - [Telegram Commands](#telegram-commands)
  - [Text Messages](#text-messages)
  - [Image Processing](#image-processing)
  - [Voice Messages](#voice-messages)
  - [Text-to-Speech (TTS)](#text-to-speech-tts)
- [Tunnel & Webhook Setup](#tunnel--webhook)
- [Access Control](#access-control)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Overview

Telecode creates a bridge between Telegram and AI code execution engines, allowing you to:

- **Chat with AI assistants** (Claude Code or Codex) directly from Telegram
- **Execute shell commands** on your server remotely
- **Process images** with vision-capable AI models
- **Transcribe voice messages** using Whisper
- **Get audio responses** via text-to-speech (Fish Audio)
- **Manage persistent conversations** with session tracking
- **Control access** with user whitelisting

## Features

### Core Features

- **Dual Engine Support**: Switch between Claude Code and Codex engines on-the-fly
- **Per-Chat Engine Selection**: Different Telegram chats can use different engines
- **Persistent Sessions**: Conversations are preserved across messages using session IDs
- **Webhook-Based**: Efficient, real-time message processing via Telegram webhooks
- **Auto-Tunneling**: Automatic ngrok tunnel creation for local development

### Communication Features

- **Text Messages**: Send prompts and receive AI-generated responses
- **Image Support**: Send photos or image documents for AI analysis
- **Voice Messages**: Record voice notes that are automatically transcribed via Whisper
- **TTS Responses**: Optional text-to-speech audio replies using Fish Audio API
- **Command Execution**: Run shell commands on the server via `/cli` command

### Security & Control

- **User Whitelisting**: Restrict access by Telegram user ID or username
- **Webhook Secret**: Secure webhook endpoint with auto-generated secrets
- **Per-Chat Configuration**: Engine preferences stored per-chat for multi-user scenarios

### Developer Features

- **Verbose Logging**: Detailed console output for debugging
- **Configuration Management**: Global and local config file support
- **Auto-Reload**: Development mode with auto-reload capability
- **Session Locking**: Thread-safe session management for concurrent requests

## How It Works

### Architecture

Telecode is built on a webhook-based architecture using FastAPI:

```
┌──────────────┐
│   Telegram   │
│   Bot API    │
└──────┬───────┘
       │ HTTPS Webhook
       ▼
┌──────────────────────┐
│   Public Tunnel      │
│   (ngrok/custom)     │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  FastAPI Server      │
│  (telecode.server)   │
└──────┬───────────────┘
       │
       ├─────────────────┐
       │                 │
       ▼                 ▼
┌─────────────┐   ┌──────────────┐
│ Claude Code │   │    Codex     │
│   Engine    │   │   Engine     │
└─────────────┘   └──────────────┘
```

### Communication Flow

1. **Message Reception**:
   - User sends a message in Telegram
   - Telegram API delivers the message to your webhook endpoint
   - FastAPI server receives and validates the webhook request

2. **User Authorization**:
   - Server checks if user is in the allowed list (if configured)
   - Unauthorized users receive a "Not authorized" message

3. **Message Processing**:
   - **Text messages**: Checked for commands first, then routed to AI engine
   - **Voice messages**: Downloaded and transcribed with Whisper, then processed
   - **Images**: Downloaded to `.telecode_tmp/` and sent to AI with the caption
   - **Commands**: Executed immediately (e.g., `/cli`, `/engine`, `/tts_on`)

4. **Engine Execution**:
   - Session lock is acquired to prevent concurrent access
   - Session ID is retrieved or created for the chat
   - AI engine is invoked with the prompt and optional image paths
   - Response is captured and processed

5. **Response Delivery**:
   - AI response is sent back to Telegram chat
   - Optional TTS audio is generated and sent if enabled
   - Session state is persisted for future messages

### Session Management

Telecode maintains conversation context using session IDs:

- **Claude Code**: Sessions are persistent across conversations. Session ID is passed via `--session-id` or `--resume` flags
- **Codex**: Sessions can be created and resumed, with session IDs extracted from the output
- **Storage**: Session IDs are stored in `.telecode` file (JSON or key-value format)
- **Per-Engine**: Separate session IDs for Claude and Codex
- **Thread-Safe**: Session locks prevent race conditions in multi-user scenarios

### Message Routing

```python
# Message flow pseudocode
if message.contains_voice:
    audio = download_voice(message)
    text = transcribe_with_whisper(audio)
    response = send_to_engine(text)

elif message.contains_photo:
    image_path = download_image(message)
    response = send_to_engine(caption, images=[image_path])

elif message.contains_text:
    if is_command(message.text):
        response = handle_command(message.text)
    else:
        response = send_to_engine(message.text)

send_telegram_message(response)
if tts_enabled:
    send_telegram_audio(text_to_speech(response))
```

## Installation

### From PyPI

```bash
pip install telecode
```

### From Source

```bash
git clone https://github.com/polinom/telecode.git
cd telecode
pip install -e .
```

### Optional Dependencies

For voice message support:
```bash
pip install openai-whisper
```

For TTS support (Fish Audio), ensure you have an API token from [Fish Audio](https://fish.audio).

### System Dependencies

Voice messages require `ffmpeg`:

**macOS**:
```bash
brew install ffmpeg
```

**Ubuntu/Debian**:
```bash
sudo apt-get install ffmpeg
```

**Windows**:
Download from [ffmpeg.org](https://ffmpeg.org/download.html)

## Quick Start

### 1. Run the Server in root your project folder, where you have CLAUDE.MD or / ANGENTS.MD

```bash
> telecode
```

On first run, Telecode will prompt you for:
- **Telegram Bot Token** (from [@BotFather](https://t.me/BotFather))
- **ngrok Auth Token** (if using auto-tunneling)

Configuration is saved to `./.telecode` or `~/.telecode`.

### 2. Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Paste it when Telecode prompts for `TELEGRAM_BOT_TOKEN`

### 3. Start Chatting

1. Find your bot in Telegram (search for the username you created)
2. Send `/start` to begin
3. Send any message to interact with the AI engine
4. Use `/engine` to check or switch engines

## Configuration

### Configuration Files

Telecode reads configuration from two locations (local overrides global):

1. **Global**: `~/.telecode` - User-wide settings
2. **Local**: `./.telecode` - Project-specific settings

When you run interactive commands (e.g., `/engine claude`), settings are saved to the local config.

### Configuration Keys

| Key | Description | Default |
|-----|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | *Required* |
| `TELEGRAM_TUNNEL_URL` | Public tunnel URL (e.g., `https://xxxx.ngrok-free.app`) | Auto-generated via ngrok |
| `TELEGRAM_WEBHOOK_SECRET` | Webhook security secret | Auto-generated on startup |
| `TELECODE_ENGINE` | Default engine: `claude` or `codex` | `claude` |
| `TELECODE_HOST` | Server bind address | `0.0.0.0` |
| `TELECODE_PORT` | Server port | `8000` |
| `TELECODE_ALLOWED_USERS` | Comma/space-separated user IDs or `@usernames` | *(empty = allow all)* |
| `TELECODE_VERBOSE` | Enable verbose logging: `1` or `0` | `0` |
| `TELECODE_NGROK` | Auto-start ngrok: `1` or `0` | `1` |
| `TELECODE_TTS` | Enable TTS responses: `1` or `0` | `0` |
| `NGROK_AUTHTOKEN` | ngrok authentication token | *(required for ngrok)* |
| `TTS_TOKEN` | Fish Audio API token | *(required for TTS)* |
| `TTS_MODEL` | Fish Audio model | `s1` |
| `CLAUDE_TIMEOUT_S` | Claude command timeout in seconds | `None` |
| `TELECODE_SESSION_CLAUDE` | Stored session ID for Claude | Auto-managed |
| `TELECODE_SESSION_CODEX` | Stored session ID for Codex | Auto-managed |
| `TELECODE_ENGINE_OVERRIDE_<chat_id>` | Per-chat engine override | Auto-managed |

### Example Configuration

`.telecode`:
```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_TUNNEL_URL=https://abc123.ngrok-free.app
TELECODE_ENGINE=claude
TELECODE_ALLOWED_USERS=12345678,@username,987654321
TELECODE_TTS=1
TTS_TOKEN=your_fish_audio_token
TELECODE_VERBOSE=1
```

## Usage

### Telegram Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/engine` | Show current engine | `/engine` |
| `/engine <name>` | Switch engine | `/engine claude`<br>`/engine codex` |
| `/claude` | Switch to Claude (shortcut) | `/claude` |
| `/codex` | Switch to Codex (shortcut) | `/codex` |
| `/cli <command>` | Run shell command on server | `/cli ls -la`<br>`/cli git status` |
| `/tts_on` | Enable TTS audio responses | `/tts_on` |
| `/tts_off` | Disable TTS audio responses | `/tts_off` |

### Text Messages

Simply send any text message to interact with the current AI engine:

```
You: Write a Python function to calculate fibonacci numbers

Bot: Here's a Python function to calculate Fibonacci numbers:

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

This is a recursive implementation. For better performance
with larger values, consider using dynamic programming or
iterative approach.
```

### Image Processing

Send images to the bot for AI analysis:

1. **Photo**: Send any photo directly
2. **Document**: Send an image file as a document
3. **Caption**: Add a caption to specify what you want the AI to analyze

Example:
```
[Send screenshot of error message]
Caption: "What's causing this error?"

Bot: This error is a NullPointerException occurring at line 42...
```

**How it works**:
- Images are downloaded to `./.telecode_tmp/`
- For Claude Code: Images are passed via `--add-dir` flag with file paths
- For Codex: Images are passed via `--image` flag
- Original prompt/caption is included with image references

### Voice Messages

Record and send voice messages for hands-free interaction:

1. Hold the microphone button in Telegram
2. Speak your prompt
3. Release to send

**Requirements**:
- `openai-whisper` package installed
- `ffmpeg` available in system PATH

**How it works**:
- Voice note is downloaded as `.ogg` audio file
- Whisper `base` model transcribes the audio
- Transcribed text is sent to the AI engine
- Response is sent back as text (and audio if TTS is enabled)

### Text-to-Speech (TTS)

Enable audio responses using Fish Audio API:

1. **Enable TTS**:
   ```
   /tts_on
   ```

2. **Configure Fish Audio Token**:
   Add to `.telecode`:
   ```bash
   TTS_TOKEN=your_fish_audio_api_token
   TTS_MODEL=s1
   ```

3. **Get Audio Responses**:
   Every AI response will be followed by an audio message with the spoken version.

**How it works**:
- AI response text is cleaned (removes markdown `**` formatting)
- Text is sent to Fish Audio TTS API
- Audio file is saved to `./.telecode_tmp/`
- Audio is sent to Telegram as a voice message

## Tunnel & Webhook

Telegram webhooks require a public HTTPS URL. Telecode supports two approaches:

### Auto-Tunneling with ngrok (Default)

Telecode automatically starts an ngrok tunnel if `TELEGRAM_TUNNEL_URL` is not set:

1. **First-time setup**:
   - Sign up at [ngrok.com](https://ngrok.com)
   - Get your auth token from the dashboard
   - Telecode will prompt for it on first run
   - Token is saved to `~/.telecode`

2. **Limitations**:
   - Subject to [ngrok free plan limits](https://ngrok.com/docs/pricing-limits/free-plan-limits)
   - Tunnel URL changes on each restart

### Manual Tunnel Setup

Disable auto-tunneling and provide your own URL:

```bash
# Set in .telecode or environment
TELECODE_NGROK=0
TELEGRAM_TUNNEL_URL=https://your-domain.com
```

Or use ngrok manually:
```bash
ngrok http 8000
# Copy the HTTPS URL to TELEGRAM_TUNNEL_URL
```

### Webhook Security

Telecode generates a fresh webhook secret on each startup:
```
Webhook URL: https://xxx.ngrok-free.app/telegram/{secret}
```

The secret is verified on every incoming request to prevent unauthorized access.

## Access Control

Restrict bot access to specific users:

### By User ID

```bash
TELECODE_ALLOWED_USERS=123456789,987654321
```

To find your Telegram user ID:
- Message [@userinfobot](https://t.me/userinfobot)
- It will reply with your user ID

### By Username

```bash
TELECODE_ALLOWED_USERS=@alice,@bob
```

### Mixed

```bash
TELECODE_ALLOWED_USERS=123456789,@alice,987654321
```

### Allow All (Default)

Leave `TELECODE_ALLOWED_USERS` empty or unset to allow any user.

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/polinom/telecode.git
cd telecode

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in editable mode
pip install -e .
```

### Run with Auto-Reload

```bash
telecode --reload
```

### Enable Verbose Logging

```bash
telecode -v
```

Or set in configuration:
```bash
TELECODE_VERBOSE=1
```

### Run Tests

```bash
pytest -q
```

### Project Structure

```
telecode/
├── telecode/           # Main package
│   ├── __init__.py
│   ├── server.py       # FastAPI webhook server
│   ├── claude.py       # Claude Code engine integration
│   ├── codex.py        # Codex engine integration
│   ├── telegram.py     # Telegram API client
│   └── cli.py          # CLI entry point
├── tests/              # Test suite
│   └── test_server_messages.py
├── .telecode           # Local configuration (git-ignored)
├── .telecode_tmp/      # Temporary files (git-ignored)
├── pyproject.toml      # Package metadata
├── requirements.txt    # Dependencies
├── README.md           # This file
└── AGENTS.md           # Developer guidelines
```

## Troubleshooting

### Bot doesn't respond

- **Check webhook**: Ensure `TELEGRAM_TUNNEL_URL` is set and accessible
- **Check logs**: Run with `-v` flag for verbose output
- **Verify bot token**: Test token with Telegram API
- **Check user access**: Ensure your user ID is in `TELECODE_ALLOWED_USERS` (if set)

### Voice messages fail

```
Error: Whisper is not installed
```

**Solution**:
```bash
pip install openai-whisper
```

Ensure `ffmpeg` is installed:
```bash
ffmpeg -version
```

### TTS not working

```
TTS enabled but TTS_TOKEN is missing
```

**Solution**:
Add Fish Audio token to `.telecode`:
```bash
TTS_TOKEN=your_token_here
```

### ngrok authentication failed

```
Failed to start ngrok tunnel
```

**Solution**:
1. Get auth token from [ngrok.com/signup](https://dashboard.ngrok.com/get-started/your-authtoken)
2. Run telecode and paste the token when prompted
3. Or add to `~/.telecode`:
   ```bash
   NGROK_AUTHTOKEN=your_token_here
   ```

### Command timeout

```
Command timed out after 30s
```

**Solution**:
Increase timeout in `.telecode`:
```bash
CLAUDE_TIMEOUT_S=120
```

### Session ID conflicts

```
Claude failed: Session ID is already in use
```

**Solution**:
Telecode automatically retries up to 5 times with 2-second delays. If this persists:
- Wait a few seconds and try again
- Check if another Telecode instance is using the same session

### Permission denied on /cli

```
Command failed: Permission denied
```

**Solution**:
- Ensure the server process has appropriate permissions
- Avoid running sensitive commands without proper access control
- Use `TELECODE_ALLOWED_USERS` to restrict `/cli` access

## License

MIT

---

**Contributing**: Issues and pull requests are welcome on [GitHub](https://github.com/polinom/telecode).

**Security**: Never expose your bot token or API keys. Use environment variables or config files that are git-ignored.
