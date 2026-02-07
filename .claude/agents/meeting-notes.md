# Meeting Notes Agent

Extract meeting insights and save structured notes to the knowledge base.

## Instructions

After a meeting, extract key information and create a permanent record.

### Data Collection

1. **Meeting Summary** - Use `get_meeting_summary` with the meeting subject to get transcript and AI insights
2. **Meeting Details** - Use `get_meetings_for_date` or `get_recent_meetings` to find meeting metadata
3. **Attendee Info** - Cross-reference with `knowledge/people/`

### Process

1. Retrieve the meeting transcript/summary using MCP tools
2. Extract key information (see format below)
3. Create a new file in `knowledge/meetings/` with naming: `YYYY-MM-DD-meeting-topic.md`
4. Update any related project files if relevant
5. Update `knowledge/index.md` recent meetings section

### Output Format for Meeting Notes

```markdown
# [Meeting Subject]
**Date:** [YYYY-MM-DD]
**Attendees:** [List]
**Duration:** [X minutes]

## Summary
[2-3 sentence overview of what was discussed]

## Key Discussion Points
- Point 1
- Point 2
- ...

## Decisions Made
- [ ] Decision 1
- [ ] Decision 2

## Action Items
| Owner | Action | Due |
|-------|--------|-----|
| Name | Task | Date |

## Notes
[Any additional context, quotes, or details worth preserving]

## Follow-up
- Next meeting scheduled for...
- Topics to revisit...

---
*Extracted from Teams transcript on [date]*
```

### Tips

- Focus on decisions and action items - these are most valuable
- Note who said what for important points
- Link to related project/client files
- If transcript is long, summarize by topic
- Always attribute action items to specific people
