# Personal Second Brain

This repository is a markdown-based second brain that integrates with Microsoft 365 and Harvest via MCP (Model Context Protocol). Claude Code is the primary interface for accessing work data and managing knowledge.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file with:
```bash
# Microsoft 365 OAuth (required)
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id

# App Settings
APP_SECRET_KEY=your-secret-key-for-token-encryption
APP_BASE_URL=http://localhost:8000

# Harvest (optional)
HARVEST_ACCOUNT_ID=your-account-id
HARVEST_ACCESS_TOKEN=your-access-token
```

### 3. Authenticate with Microsoft 365
```bash
python auth_server.py            # Opens browser automatically
python auth_server.py --headless # For headless/remote servers
```
For headless mode, copy the printed auth URL and open it in any browser.
Requires `APP_BASE_URL` to be a publicly accessible URL (e.g., ngrok).
Tokens are stored in `tokens.db`.

### 4. MCP Server Configuration
The MCP server is already configured in `.mcp.json` in this repo. When you open the project in Claude Code, you'll be prompted to approve the `personal-tools` MCP server.

To auto-approve it, add to `.claude/settings.local.json`:
```json
{
  "enableAllProjectMcpServers": true
}
```

## MCP Tools Available

### Calendar
- `get_calendar_events` - Get events (past and/or future)
- `get_today_events` - Today's schedule
- `get_events_for_date` - Events for a specific date
- `get_past_events` - Recent past events

### Email
- `get_emails` - Emails from any folder (inbox, sentitems, drafts, etc.)
- `get_sent_emails` - Emails you have sent
- `get_email_details` - Full email content by ID
- `get_messages_from_person` - Emails and Teams messages from a person

### Teams
- `get_teams_chats` - Recent chat conversations
- `get_chat_messages` - Messages from a specific chat
- `get_my_teams_messages` - Teams messages you have sent

### Files (OneDrive/SharePoint)
- `search_files` - Search for documents
- `get_recent_files` - Recently accessed files
- `read_document` - Search and read document content
- `get_file_content` - Get file by ID

### Meetings & Transcripts
- `get_recent_meetings` - Teams meetings from calendar
- `get_meeting_summary` - Copilot AI insights + transcript
- `get_all_transcripts` - Available transcripts
- `get_transcript_by_meeting_id` - Transcript for specific meeting
- `get_meetings_for_date` - Meetings on a specific date

### Harvest Time Tracking
- `harvest_get_projects` - Active projects
- `harvest_get_project_details` - Project with budget status
- `harvest_get_time_entries` - Time entries with filters
- `harvest_get_team` - Team members
- `harvest_get_team_member` - Member with assignments
- `harvest_team_report` - Team utilization
- `harvest_project_report` - Project hours summary
- `harvest_today_tracking` - Today's time entries
- `harvest_my_time` - Current user's entries
- `harvest_running_timers` - Active timers
- `harvest_client_report` - Time by client

### Utility
- `check_connection_status` - Check Microsoft/Harvest connection

## Knowledge Base

Store your notes in the `knowledge/` directory:

```
knowledge/
├── index.md         # Quick reference and overview
├── projects/        # Project notes and context
├── people/          # Information about colleagues
├── clients/         # Client profiles and history
├── meetings/        # Meeting notes and action items
├── decisions/       # Key decisions with reasoning
└── processes/       # Workflows and procedures
```

### Conventions

**File Naming:**
- Projects: `project-name.md`
- People: `firstname-lastname.md`
- Meetings: `YYYY-MM-DD-meeting-topic.md`
- Decisions: `YYYY-MM-decision-topic.md`

**Cross-Linking:**
Use relative markdown links: `[Project X](projects/project-x.md)`

## Custom Agents

Specialized agents for common workflows. Use with `/agent <name>` or ask naturally.

| Agent | Purpose | Example Prompts |
|-------|---------|-----------------|
| `weekly-summary` | Summarize a full week's activities | "Summarize last week", "What happened this week?" |
| `daily-briefing` | Morning overview of the day | "Brief me", "What's on today?" |
| `meeting-prep` | Prepare for an upcoming meeting | "Prep me for the Midwich call", "What do I need for my 2pm?" |
| `meeting-notes` | Extract and save meeting notes | "Document yesterday's standup", "Save notes from the client call" |
| `person-context` | Gather context about someone | "Tell me about Joe Thompson", "What's my history with Tayo?" |
| `project-status` | Status report for a project | "Status on Nimans Slipstream", "How's the Euroleague RFP going?" |
| `triage` | Prioritize incoming work | "Triage my inbox", "What should I focus on?" |
| `time-review` | Analyze time tracking data | "Review last week's time", "How's the team's utilization?" |

### Using Agents

```bash
# Explicit agent invocation
/agent weekly-summary
/agent meeting-prep for the 3pm with Joe

# Or just ask naturally - Claude will use appropriate agent
"Give me a weekly summary"
"Prep me for my next meeting"
"What's the status on Project X?"
```

Agents combine MCP tools with knowledge base context to generate comprehensive responses.

## Architecture

```
personal-agent/
├── mcp_server.py          # MCP server entry point
├── auth_server.py         # OAuth authentication server
├── tokens.db              # Encrypted OAuth tokens
├── .mcp.json              # MCP server config for Claude Code
├── .claude/
│   └── agents/            # Custom Claude Code agents
│       ├── weekly-summary.md
│       ├── daily-briefing.md
│       ├── meeting-prep.md
│       ├── meeting-notes.md
│       ├── person-context.md
│       ├── project-status.md
│       ├── triage.md
│       └── time-review.md
├── knowledge/             # Markdown knowledge base
└── src/
    ├── config.py          # Settings from .env
    ├── mcp/
    │   ├── server.py      # MCP server implementation
    │   └── tools.py       # Tool handlers
    ├── microsoft/
    │   ├── auth.py        # OAuth + token storage
    │   ├── graph_client.py    # Graph API client
    │   └── copilot_client.py  # Meeting transcripts + AI
    └── harvest/
        └── client.py      # Harvest API client
```
```

## Troubleshooting

### "Microsoft 365 not connected" Error
Run `python auth_server.py` to re-authenticate (or `--headless` for remote servers).

### "Harvest not configured" Error
Set `HARVEST_ACCOUNT_ID` and `HARVEST_ACCESS_TOKEN` in `.env`.

### Token Refresh Issues
Delete `tokens.db` and re-authenticate with `python auth_server.py`.

### MCP Server Not Connecting
1. Ensure you approved the MCP server when prompted by Claude Code
2. Check that Python and dependencies are installed
3. Run `python mcp_server.py` manually to see errors
4. Verify `.mcp.json` exists in the project root
