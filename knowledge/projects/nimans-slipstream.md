# Nimans Slipstream - AI Extraction Project

## Overview
AI-powered extraction system for Midwich/Nimans to process inbound emails and extract structured data for EDI integration.

## Client
- **Company**: [Midwich Group](../clients/midwich.md) (via Nimans subsidiary)
- **Primary Contact**: [Joe Thompson](../people/joe-thompson.md) - Chief Transformation Officer
- **Project Lead (Synapx)**: [Charlie Phipps-Bennett](../people/charlie-phipps-bennett.md)

## Scope (Refined Feb 6, 2026)

### Core Components
1. **Outlook Plugin Updates**
   - Database Separation & File Check - extract embedded database layer, prevent duplicate uploads
   - Company Selection Logic - dropdown for multi-entity users based on Entra ID/AD Group membership
   - SharePoint Repository Mapping - each entity maps to AD-group-controlled SharePoint library

2. **Azure AI Foundry Updates**
   - Incorporate Nimans-specific key values
   - Train on sample PDFs

3. **AI Extraction Process & Manual Review App** (NEW - Feb 6)
   - Lightweight app for viewing documents when AI cannot extract all fields
   - Review extracted fields, amend incorrect values, populate missing mandatory fields
   - Data written directly to Excel spreadsheet
   - If AI succeeds on all mandatory fields → data written straight to Excel without intervention

4. **Power Automate - CSV Generation for EDI**
   - Build flow to format CSV per Nimans' EDI specification
   - EDI API Trigger Flow - NOT in scope for this phase

5. **Testing**
   - Functional testing across all components

### USA Entity Work
- Work for USA entity is **fully discounted** (not charged)

## Commercials

| Item | Amount |
|------|--------|
| Original Quote (Jan 30) | £18,200 + VAT |
| Manual Review App Addition | +£2,750 |
| **Final Cost** | **£20,950 + VAT** |
| USA Entity Work | Discounted (£0) |

## Status
- **Current Phase**: SOW preparation
- **Action Required**: Jake to prepare Statement of Work
- **Latest Update**: Charlie sent refined scope to Joe (Feb 6)

## Key Decisions
- USA entity work to be included at no additional cost
- Price adjustment to £20,950 agreed (Feb 6)
- Outlook plugin benefits whole Midwich Group
- Using existing EDI validation (products, pricing, carriage) rather than replicating Masterpack data

## Key Contacts at Nimans
- Tom Woodley - Coordination
- Holly Mayston
- John Bird
- Craig Willcocks
- Mark Crossley

## Related
- [Midwich Client Profile](../clients/midwich.md)
- [Joe Thompson](../people/joe-thompson.md)
- [Charlie Phipps-Bennett](../people/charlie-phipps-bennett.md)

---
*Last Updated: February 7, 2026*
