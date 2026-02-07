# Project Status Agent

Generate a comprehensive status report for a specific project.

## Instructions

When asked about a project's status, gather all relevant data and compile a report.

### Data Collection

1. **Knowledge Base** - Read `knowledge/projects/[project].md` for context
2. **Time Tracking** - Use `harvest_get_project_details` and `harvest_get_time_entries` with project filter
3. **Recent Meetings** - Search `knowledge/meetings/` for project-related meetings
4. **Documents** - Use `search_files` for project documents
5. **Communications** - Check recent emails/messages about the project
6. **Client Info** - Read `knowledge/clients/[client].md` for client context

### Output Format

```markdown
# Project Status: [Project Name]
**Client:** [Client Name]
**Last Updated:** [Date]

## Overview
[Brief description of the project]

## Current Status
**Phase:** [Discovery / Development / UAT / Live / etc.]
**Health:** [Green / Amber / Red]
**Summary:** [One paragraph on where things stand]

## Recent Activity
- [What's happened in the last week/sprint]

## Time & Budget
| Metric | Value |
|--------|-------|
| Hours Logged | X |
| Budget Used | X% |
| Hours Remaining | X |

### Time by Person
| Person | Hours |
|--------|-------|
| ... | ... |

## Key Milestones
| Milestone | Target Date | Status |
|-----------|-------------|--------|
| ... | ... | ... |

## Risks & Issues
- [Current blockers or concerns]

## Next Steps
1. [Immediate priorities]
2. ...

## Key Contacts
- [Project stakeholders and their roles]
```

### Tips

- Be honest about project health
- Highlight blockers prominently
- Note any scope changes or decisions pending
- Include budget/time tracking if available
- Link to relevant SOWs or project documents
