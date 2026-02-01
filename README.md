# Personal Business Agent

A personal AI assistant accessible via Telegram that integrates with Microsoft 365 to help you manage your work life.

## Features

- **Telegram Interface** - Chat with your assistant through Telegram
- **Microsoft 365 Integration** - Access calendar, emails, Teams chats, and OneDrive files
- **Long-term Memory** - Remembers important details from past conversations using Mem0 + Qdrant
- **Conversation History** - Maintains context within sessions
- **Meeting Insights** - Get meeting summaries, transcripts, and Copilot-generated notes

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│    Telegram     │────▶│   FastAPI App    │────▶│  Azure OpenAI   │
│      User       │◀────│   (Webhook)      │◀────│    (GPT-4)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
              ┌──────────┐ ┌───────┐ ┌─────────────┐
              │ MS Graph │ │ Mem0  │ │   Qdrant    │
              │   API    │ │       │ │ (Vector DB) │
              └──────────┘ └───────┘ └─────────────┘
```

## Prerequisites

- Python 3.11+
- Docker & Docker Compose (for Qdrant)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Azure OpenAI deployment
- Microsoft Azure AD app registration (for M365 integration)

## Setup

### 1. Clone and Install

```bash
git clone <repository-url>
cd personal-agent
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_DEPLOYMENT=gpt-4
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

# Azure AD (Microsoft Graph) - Optional
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret
AZURE_TENANT_ID=your_tenant_id

# Memory
QDRANT_HOST=localhost
QDRANT_PORT=6333

# App
APP_SECRET_KEY=your_secret_key
ALLOWED_TELEGRAM_USERS=123456789,987654321  # Comma-separated user IDs, empty = allow all
```

### 3. Start Services

```bash
# Start Qdrant vector database
docker-compose up -d qdrant

# Run the application
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Or run everything with Docker:

```bash
docker-compose up -d
```

### 4. Set Up Telegram Webhook

The application automatically sets the webhook on startup. Ensure your `TELEGRAM_WEBHOOK_URL` is publicly accessible (use ngrok for local development).

## Azure AD Configuration

To enable Microsoft 365 integration, register an Azure AD application:

1. Go to [Azure Portal](https://portal.azure.com) > Azure Active Directory > App registrations
2. Create a new registration
3. Add a redirect URI: `https://your-domain.com/auth/callback`
4. Create a client secret under "Certificates & secrets"
5. Add API permissions:
   - `Calendars.Read`
   - `Mail.Read`
   - `Chat.Read`
   - `Files.Read.All`
   - `OnlineMeetings.Read`
   - `OnlineMeetingTranscript.Read.All`

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and available commands |
| `/status` | Check bot status and connections |
| `/connect` | Connect your Microsoft 365 account |
| `/disconnect` | Disconnect Microsoft 365 |
| `/memories` | View stored memories |
| `/clear` | Clear all memories and conversation history |

## Available Tools

When Microsoft 365 is connected, the agent can use these tools:

### Calendar
- `get_calendar_events` - Get upcoming/past calendar events
- `get_today_events` - Get today's events
- `get_events_for_date` - Get events for a specific date
- `get_past_events` - Get events from recent days

### Email
- `get_emails` - Get recent emails (with optional search)
- `get_email_details` - Get full content of a specific email

### Teams
- `get_teams_chats` - Get recent Teams chat conversations
- `get_chat_messages` - Get messages from a specific chat

### Files
- `search_files` - Search OneDrive and SharePoint
- `get_recent_files` - Get recently accessed files
- `get_file_content` - Download and read file content (supports .docx, .xlsx, .pptx, .pdf, .txt, .md, .csv, .json, etc.)

### Meetings
- `get_recent_meetings` - Get Teams meetings from calendar
- `get_meeting_summary` - Get Copilot insights and transcript for a meeting
- `get_all_transcripts` - List available meeting transcripts
- `get_transcript_by_meeting_id` - Get transcript by meeting ID
- `list_meetings_with_transcripts` - Debug transcript availability

### People
- `get_messages_from_person` - Get recent emails and Teams messages from a specific person

## Project Structure

```
src/
├── main.py                 # FastAPI app entry point
├── config.py               # Environment configuration
├── agent/
│   ├── orchestrator.py     # Main agent logic with agentic loop
│   ├── prompts.py          # System prompts
│   └── tools.py            # Tool definitions and executor
├── bot/
│   ├── telegram_handler.py # Telegram webhook handler
│   └── commands.py         # Bot command handlers
├── llm/
│   └── azure_openai.py     # Azure OpenAI client
├── memory/
│   ├── mem0_client.py      # Long-term memory (Mem0)
│   └── conversation_history.py # Short-term conversation context
└── microsoft/
    ├── auth.py             # Microsoft OAuth flow
    ├── graph_client.py     # MS Graph API client
    └── copilot_client.py   # Meeting insights client
```

## How It Works

1. **User sends a message** via Telegram
2. **Webhook receives update** and passes to TelegramHandler
3. **AgentOrchestrator processes** the message:
   - Searches long-term memory for relevant context
   - Retrieves recent conversation history
   - Builds system prompt with memory and M365 status
   - Sends to Azure OpenAI with available tools
4. **Agentic loop** executes if tools are needed (max 5 rounds)
5. **Response sent back** to user via Telegram
6. **Exchange stored** in both conversation history and long-term memory

## Development

### Running Locally

For local development with webhook, use ngrok:

```bash
ngrok http 8000
```

Update `TELEGRAM_WEBHOOK_URL` with the ngrok URL.

### Logs

Logs are written to stdout with INFO level by default. Check logs for:
- Message processing
- Tool execution
- Memory operations
- OAuth flow

## License

MIT
