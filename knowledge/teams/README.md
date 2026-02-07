# Teams Message Archive

This folder contains archived Teams messages organized by date, with key conversations preserved as timestamped quotations for future reference.

## Structure

```
teams/
├── YYYY-MM-DD/
│   ├── chat-name.md
│   └── another-chat.md
└── README.md
```

## Conventions

- **Folder naming**: `YYYY-MM-DD` format (e.g., `2026-02-06`)
- **File naming**: Lowercase chat/topic name with hyphens (e.g., `jensten-proposal.md`)
- **Timestamps**: UTC format from Teams API
- **Quotations**: Block quotes with attribution

## Message Format

```markdown
> **HH:MM UTC** - Person Name
> Message content here

> **HH:MM UTC** - Another Person
> Reply content
```

## Current Archives

### February 2026
- [2026-02-06](./2026-02-06/) - Friday messages (8 chats archived)

## Usage

These archives serve as:
1. **Reference material** for project decisions and context
2. **Source of truth** for commitments and deadlines mentioned in chat
3. **Cross-reference** for updating other knowledge articles
4. **Historical record** of key conversations

## Related Knowledge Articles

When archiving messages, update related articles:
- `projects/` - Project-specific updates
- `clients/` - Client contact info, engagement details
- `people/` - Role changes, recognition, travel plans
- `meetings/` - Meeting outcomes referenced in chat
