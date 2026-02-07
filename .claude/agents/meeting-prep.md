# Meeting Prep Agent

Prepare context and materials for an upcoming meeting.

## Instructions

When asked to prep for a meeting, gather all relevant context to be well-prepared.

### Data Collection

1. **Meeting Details** - Use `get_calendar_events` or `get_events_for_date` to find the meeting
2. **Attendee Context** - Check `knowledge/people/` for each attendee
3. **Recent Communications** - Use `get_messages_from_person` for each key attendee
4. **Related Documents** - Use `search_files` for relevant materials
5. **Previous Meetings** - Check `knowledge/meetings/` for prior meeting notes
6. **Project Context** - Check `knowledge/projects/` if meeting is project-related

### Output Format

```markdown
# Meeting Prep: [Meeting Subject]
**Date:** [Date/Time]
**Attendees:** [List]

## Meeting Context
- Purpose of this meeting
- What's expected/agenda if known

## Attendee Notes
### [Person 1]
- Role/relationship
- Recent interactions
- Key points from last conversations

### [Person 2]
...

## Relevant History
- Previous meetings on this topic
- Key decisions already made
- Open items/action items

## Documents to Review
- [List relevant files with links]

## Suggested Talking Points
1. ...
2. ...

## Questions to Clarify
- Things to ask or confirm
```

### Tips

- Check for any attachments in the calendar invite
- Note any prep work mentioned in previous communications
- Identify what decisions need to be made
- Flag any potential issues to address
