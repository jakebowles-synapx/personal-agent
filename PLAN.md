# Personal Business Agent - Implementation Plan

## Overview
A personal AI assistant accessible via Telegram that understands your business context through Microsoft 365 integration and maintains persistent memory using Mem0.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER (Mobile)                           │
│                              │                                  │
│                         Telegram App                            │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT SERVER (VPS)                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Telegram Bot Handler                   │   │
│  │              (python-telegram-bot + webhook)             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                               │                                 │
│                               ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Agent Orchestrator                    │   │
│  │         (Routes requests, manages conversation)          │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                   │                   │             │
│           ▼                   ▼                   ▼             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐     │
│  │   Memory    │    │     LLM     │    │   Microsoft     │     │
│  │   (Mem0)    │    │  (Azure OAI)│    │   Tools         │     │
│  └─────────────┘    └─────────────┘    └─────────────────┘     │
│           │                                     │               │
│           ▼                                     ▼               │
│  ┌─────────────┐                    ┌─────────────────────┐    │
│  │  Qdrant     │                    │  Microsoft Graph    │    │
│  │  (Vector DB)│                    │  + Copilot APIs     │    │
│  └─────────────┘                    └─────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | Best library support for all integrations |
| Web Framework | FastAPI | Async, modern, easy webhooks |
| Telegram | python-telegram-bot | Official, well-maintained |
| LLM | Azure OpenAI (GPT-4) | Integrates with Microsoft ecosystem |
| Memory | Mem0 | Hybrid vector + graph memory |
| Vector DB | Qdrant (Docker) | Fast, easy self-hosted, Mem0 compatible |
| Microsoft Auth | MSAL Python | Official Microsoft auth library |
| Task Queue | None (MVP) | Add Celery later if needed |

## Project Structure

```
personal-agent/
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Environment configuration
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── telegram_handler.py # Telegram webhook + message handling
│   │   └── commands.py         # Bot commands (/start, /status, etc.)
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # Main agent logic
│   │   ├── prompts.py          # System prompts and templates
│   │   └── tools.py            # Tool definitions for the agent
│   ├── memory/
│   │   ├── __init__.py
│   │   └── mem0_client.py      # Mem0 integration
│   ├── microsoft/
│   │   ├── __init__.py
│   │   ├── auth.py             # Azure AD OAuth flow
│   │   ├── graph_client.py     # Microsoft Graph API wrapper
│   │   └── copilot_client.py   # Copilot APIs (Meeting Insights, etc.)
│   └── llm/
│       ├── __init__.py
│       └── azure_openai.py     # Azure OpenAI client
├── tests/
├── docker-compose.yml          # Qdrant + app services
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Implementation Phases

### Phase 1: Foundation (MVP) ✅ COMPLETE
**Goal**: Working Telegram bot with basic conversation memory

1. **Project setup** ✅
   - Initialize Python project with FastAPI
   - Set up configuration management (.env)
   - Create Docker Compose for Qdrant

2. **Telegram bot** ✅
   - Create bot via @BotFather
   - Implement webhook handler with FastAPI
   - Basic message receive/send

3. **Azure OpenAI integration** ✅
   - Set up Azure OpenAI resource
   - Implement chat completion client
   - Basic conversation flow

4. **Mem0 memory** ✅
   - Initialize Mem0 with Qdrant backend
   - Store/retrieve conversation memories
   - User context persistence

**Deliverable**: Chat with your agent on Telegram, it remembers previous conversations

### Phase 2: Microsoft Integration ✅ COMPLETE
**Goal**: Agent can access your Microsoft 365 data

1. **Azure AD App Registration** ✅
   - Register app in Azure Portal
   - Configure OAuth permissions (Mail.Read, Calendars.Read, etc.)
   - Implement auth flow with MSAL

2. **Microsoft Graph tools** ✅
   - Email: List recent emails, search, read specific emails
   - Calendar: Get upcoming events, find free time
   - Teams: Access chat history, channel messages
   - Files: Search OneDrive/SharePoint

3. **Copilot API tools** (E5 Copilot) - Stubs created
   - Meeting Insights: Get AI summaries of Teams meetings
   - Retrieval API: Search across M365 content

4. **Agent tool integration** ✅
   - Define tools for the LLM to call
   - Implement tool execution flow (agentic loop)
   - Response synthesis

**Deliverable**: Ask "What meetings do I have today?" or "Any important emails?"

### Phase 3: Intelligence Enhancement
**Goal**: Smarter, more proactive agent

1. **Enhanced memory**
   - Enable Mem0 graph memory for relationships
   - Track people, projects, topics
   - Cross-reference information

2. **Proactive features**
   - Daily briefing (morning summary)
   - Meeting prep (relevant context before meetings)
   - Task tracking from conversations

3. **Better context handling**
   - Longer conversation windows
   - Document summarization
   - Smart context retrieval

**Deliverable**: Agent proactively provides relevant information and remembers complex relationships

### Phase 4: Production Hardening (Optional)
**Goal**: Reliable, secure production deployment

1. Security: Token encryption, rate limiting, audit logging
2. Reliability: Error handling, retries, health checks
3. Observability: Logging, metrics, alerting
4. Backup: Memory export/import

## Authentication Flow (Phase 2)

```
1. User sends /connect command in Telegram
2. Bot returns Microsoft OAuth URL
3. User authenticates in browser, grants permissions
4. Callback receives auth code
5. Exchange code for tokens
6. Store refresh token (encrypted) linked to Telegram user ID
7. Future requests use refresh token to get access tokens
```

## Required Azure Resources

1. **Azure OpenAI Service**
   - Deploy GPT-4 or GPT-4-turbo model
   - Deploy text-embedding-ada-002 (or similar) for embeddings
   - Note endpoint and API key

2. **Azure AD App Registration** (Phase 2)
   - Redirect URI: `https://your-vps-domain/auth/callback`
   - API Permissions:
     - `Mail.Read` - Read emails
     - `Calendars.Read` - Read calendar
     - `Chat.Read` - Read Teams chats
     - `Files.Read.All` - Read OneDrive/SharePoint
     - `OnlineMeetings.Read` - Meeting details
     - `Notes.Read` - OneNote access
     - For Copilot APIs: Additional permissions as documented

## Environment Variables

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_DEPLOYMENT=gpt-4
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

# Azure AD (Microsoft Graph) - Phase 2
AZURE_CLIENT_ID=your_app_client_id
AZURE_CLIENT_SECRET=your_app_client_secret
AZURE_TENANT_ID=your_tenant_id

# Memory
QDRANT_HOST=localhost
QDRANT_PORT=6333

# App
APP_SECRET_KEY=generate_a_random_secret_key_here
ALLOWED_TELEGRAM_USERS=your_telegram_user_id
```

## VPS Requirements

- **Minimum**: 2 vCPU, 4GB RAM, 40GB SSD
- **OS**: Ubuntu 22.04 LTS
- **Software**: Docker, Docker Compose, nginx (for SSL)
- **Domain**: Required for HTTPS webhook
- **SSL**: Let's Encrypt (free)

## Verification Plan

### Phase 1 Testing
1. Send message to Telegram bot, receive response
2. Have a multi-turn conversation
3. Close app, reopen, ask "what did we talk about?" - should remember

### Phase 2 Testing
1. Complete /connect flow, verify OAuth success
2. Ask "What's on my calendar today?" - should list real events
3. Ask "Any important emails?" - should summarize recent mail
4. Ask "Summarize my last Teams meeting" - should use Copilot Meeting Insights

### Phase 3 Testing
1. Mention a person/project multiple times across days
2. Later ask "What do I know about [person/project]?" - should aggregate
3. Check morning briefing arrives

## Local Development

### Quick Start

1. **Copy and configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Create Telegram bot**: Message @BotFather on Telegram, run `/newbot`

3. **Start Qdrant**:
   ```bash
   docker-compose up -d qdrant
   ```

4. **Install dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Run the app locally**:
   ```bash
   python -m uvicorn src.main:app --reload
   ```

6. **For local testing**, use ngrok to expose webhook:
   ```bash
   ngrok http 8000
   # Set TELEGRAM_WEBHOOK_URL to the ngrok URL + /webhook
   ```

### Bot Commands
- `/start` - Welcome message
- `/status` - Check bot status and memory count
- `/memories` - View stored memories
- `/clear` - Clear all memories
- `/connect` - Microsoft 365 (Phase 2 placeholder)

## Dependencies

```
# Web framework
fastapi>=0.109.0
uvicorn>=0.27.0

# Telegram
python-telegram-bot>=21.0

# LLM
openai>=1.12.0
azure-identity>=1.15.0

# Memory
mem0ai>=0.1.0
qdrant-client>=1.7.0

# Microsoft (Phase 2)
msal>=1.26.0
httpx>=0.26.0

# Configuration
pydantic-settings>=2.1.0
python-dotenv>=1.0.0

# Security
cryptography>=42.0.0
```

## Phase 2 Implementation Details

### Files to Implement

1. **src/microsoft/auth.py** - Full MSAL OAuth implementation
   - `get_auth_url(user_id, state)` - Generate OAuth URL
   - `handle_callback(code, state)` - Exchange code for tokens
   - `get_access_token(user_id)` - Get/refresh access token
   - Token storage (encrypted in SQLite or similar)

2. **src/microsoft/graph_client.py** - Microsoft Graph API
   - `get_emails(limit, search)` - List/search emails
   - `get_email(email_id)` - Get specific email
   - `get_calendar_events(days)` - Get upcoming events
   - `get_teams_chats(limit)` - List Teams chats
   - `search_files(query)` - Search OneDrive/SharePoint

3. **src/microsoft/copilot_client.py** - Copilot APIs
   - `get_meeting_insights(meeting_id)` - Meeting AI insights
   - `get_meeting_transcript(meeting_id)` - Meeting transcript
   - `search_content(query)` - Semantic search across M365

4. **src/agent/tools.py** - LLM tool definitions
   - Define function schemas for each Microsoft capability
   - Tool execution routing

5. **src/bot/commands.py** - Update /connect command
   - Generate and send OAuth URL
   - Handle auth state management

6. **src/main.py** - Update auth callback endpoint
   - Handle OAuth redirect
   - Store tokens securely

### Azure AD App Setup

1. Go to Azure Portal > Azure Active Directory > App registrations
2. New registration:
   - Name: "Personal Business Agent"
   - Supported account types: Single tenant
   - Redirect URI: Web, `https://your-domain/auth/callback`
3. Note the Application (client) ID and Directory (tenant) ID
4. Certificates & secrets > New client secret > Note the value
5. API permissions > Add permissions:
   - Microsoft Graph > Delegated permissions
   - Add: Mail.Read, Calendars.Read, Chat.Read, Files.Read.All, User.Read
6. Grant admin consent (if required by your tenant)

## Phase 3 Implementation Details

### Graph Memory Setup

Update Mem0 config to enable graph memory:

```python
config = {
    # ... existing config ...
    "graph_store": {
        "provider": "neo4j",  # or other supported provider
        "config": {
            "url": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password",
        },
    },
}
```

### Proactive Features

1. **Daily Briefing**
   - Scheduled task (e.g., 8 AM)
   - Fetch calendar, emails, Teams activity
   - Generate summary with LLM
   - Send via Telegram

2. **Meeting Prep**
   - Monitor calendar for upcoming meetings
   - 15 min before: gather relevant memories, recent emails with attendees
   - Send context summary

3. **Task Extraction**
   - After each conversation, extract action items
   - Store in memory with "task" metadata
   - Allow querying "what tasks do I have?"
