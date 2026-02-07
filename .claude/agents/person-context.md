# Person Context Agent

Gather comprehensive context about a specific person.

## Instructions

When asked about a person, compile all relevant information and recent interactions.

### Data Collection

1. **Knowledge Base** - Check `knowledge/people/[name].md` for existing notes
2. **Recent Messages** - Use `get_messages_from_person` with their name
3. **Shared Meetings** - Use `get_calendar_events` and filter for meetings with them
4. **Meeting Notes** - Search `knowledge/meetings/` for meetings they attended
5. **Shared Documents** - Use `search_files` for documents they've shared or are mentioned in
6. **Client/Project Links** - Check if they're associated with any client or project

### Output Format

```markdown
# Context: [Person Name]

## Profile
- **Role:** [Title at Company]
- **Company:** [Organization]
- **Relationship:** [Client contact / Team member / Partner / etc.]
- **Key Projects:** [Projects they're involved with]

## Recent Interactions (Last 30 Days)

### Meetings
| Date | Meeting | Key Points |
|------|---------|------------|
| ... | ... | ... |

### Email/Teams Messages
- [Date]: [Brief summary of conversation]
- ...

## Communication Style
- [Notes on how they communicate, preferences, etc.]

## Key Topics
- What they care about
- Current priorities/concerns
- Expertise areas

## Action Items
- Outstanding items with them
- Things promised to them
- Things they promised

## Notes
- [Any other relevant context]
```

### Tips

- Include both formal meetings and informal chats
- Note their communication preferences if known
- Track what they've asked for or mentioned needing
- Update their person file in knowledge base if you learn new info
