# Weekly Summary Agent

Generate a comprehensive summary of the past week's activities.

## Instructions

When the user asks for a weekly summary, gather data from all sources and compile a structured report.

### Data Collection

1. **Calendar** - Use `get_calendar_events` with `past_days=7` to get all meetings from the past week
2. **Emails** - Use `get_emails` with search/pagination to get key emails
3. **Time Tracking** - Use `harvest_team_report` and `harvest_project_report` for the week
4. **Meeting Notes** - Check `knowledge/meetings/` for any documented meetings

### Output Format

Structure the summary as:

```markdown
# Week Summary: [Date Range]

## Meetings ([count])
- List key meetings with brief outcomes
- Note any action items that emerged

## Email Highlights
- Important threads or decisions
- Items needing follow-up

## Time Tracking
- Total hours logged
- Hours by project/client
- Team utilization highlights

## Key Accomplishments
- What got done this week

## Carry Forward
- Outstanding items for next week
- Upcoming deadlines

## Notes
- Any patterns or observations
```

### Tips

- Focus on outcomes, not just activities
- Highlight decisions made and action items
- Note any blockers or concerns
- If meetings have transcripts, use `get_meeting_summary` for key ones
