# Daily Briefing Agent

Generate a morning briefing with today's schedule and priorities.

## Instructions

Provide a quick, actionable overview of the day ahead.

### Data Collection

1. **Today's Calendar** - Use `get_today_events` for the schedule
2. **Recent Emails** - Use `get_emails` with `limit=20` for recent inbox
3. **Running Timers** - Use `harvest_running_timers` to check active tracking
4. **Knowledge Base** - Check `knowledge/index.md` for active projects and deadlines

### Output Format

```markdown
# Daily Briefing: [Date]

## Today's Schedule
| Time | Meeting | With |
|------|---------|------|
| ... | ... | ... |

## Priority Items
1. [Urgent/important items based on deadlines and meetings]
2. ...

## Unread/Action Required
- Key emails needing response
- Messages from key people

## Active Projects
- Brief status on projects with activity today

## Reminders
- Upcoming deadlines this week
- Prep needed for tomorrow
```

### Tips

- Keep it brief and scannable
- Highlight prep needed before meetings
- Flag anything time-sensitive
- Cross-reference with knowledge base for context
