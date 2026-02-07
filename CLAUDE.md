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
- `get_emails` - Recent inbox emails (with search/pagination)
- `get_email_details` - Full email content by ID
- `get_messages_from_person` - Emails and Teams messages from a person

### Teams
- `get_teams_chats` - Recent chat conversations
- `get_chat_messages` - Messages from a specific chat

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

## Workflow Examples

### Prepare for a Meeting
```
1. Use get_calendar_events to see upcoming meetings
2. Use get_messages_from_person to review recent communications with attendees
3. Use search_files to find relevant documents
4. Check knowledge/people/ for context on attendees
```

### Document a Meeting
```
1. Use get_meeting_summary to get transcript and AI insights
2. Create a new file in knowledge/meetings/
3. Extract action items and decisions
4. Update relevant project files if needed
```

### Review Team Time
```
1. Use harvest_team_report for utilization overview
2. Use harvest_project_report for project allocation
3. Check specific team members with harvest_get_team_member
```

## Architecture

```
personal-agent/
├── mcp_server.py          # MCP server entry point
├── auth_server.py         # OAuth authentication server
├── tokens.db              # Encrypted OAuth tokens
├── knowledge/             # Markdown knowledge base
├── src/
│   ├── config.py          # Settings from .env
│   ├── mcp/
│   │   ├── server.py      # MCP server implementation
│   │   └── tools.py       # Tool handlers
│   ├── microsoft/
│   │   ├── auth.py        # OAuth + token storage
│   │   ├── graph_client.py    # Graph API client
│   │   └── copilot_client.py  # Meeting transcripts + AI
│   ├── harvest/
│   │   └── client.py      # Harvest API client
│   └── agent/
│       └── tools.py       # Tool definitions (legacy)
└── requirements.txt
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
