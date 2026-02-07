# Capital Hair & Beauty - Fabric/Power BI Implementation

## Overview
Microsoft Fabric and Power BI implementation for Capital Hair & Beauty, the UK's largest independent supplier to hairdressers, beauty therapists and nail technicians (60 stores across UK & Ireland). Replacing Phocus reporting system with Power BI.

## Client
- **Company**: [Capital Hair & Beauty](../clients/capital-hb.md)
- **Primary Contact**: [Cristian Ettridge](../people/cristian-ettridge.md) - General Manager

## Contract

| Field | Value |
|-------|-------|
| **SOW** | SOW002 |
| **Date** | February 3, 2026 |
| **Signed** | February 6, 2026 |
| **Fixed Fee** | £21,700 + VAT |
| **Data Visualisation** | T&M, estimated £5,000 + VAT |
| **Contingency** | Up to 10% of contract (T&M if used) |

**Payment Terms:**
- 50% upfront (£10,850 + VAT) on signing
- 50% on completion of deliverables
- Data Visualisation billed monthly on actuals

**SharePoint:** [SOW002 Document](https://synapxltd.sharepoint.com/sites/Synapx-Contracts/Shared%20Documents/Contracts/Clients/CAPITAL%20(HAIR%20AND%20BEAUTY)%20LIMITED/SOWs/SOW002-Fabric%20%26%20PowerBI%20Implementation/CAPITAL%20(HAIR%20AND%20BEAUTY)%20LIMITED_SOW002_Fabric%20%26%20PowerBI%20Implementation_3%20February%202026.docx)

## Architecture

### Data Sources
| Source | Method | Notes |
|--------|--------|-------|
| **Business Central** | API | Daily ingestion |
| **Nav** | One-time load | Historic data |
| **Orderwise** | SQL | Via on-premises gateway |
| **iTrent** | API | Via Fabric Notebooks |

### Platform
- **Fabric SKU**: F4 (paused to reduce costs to working hours only)
- **POC Funded Subscription**: $1200 (pending Microsoft approval, up to 30 days)
- **Environments**: Dev and Prod

## Deliverables

1. Full Design and Architecture
2. iTrent data source discovery and implementation
3. Dev/Prod environment setup with POC Funded Subscription
4. Fabric Platform & Workspace setup
5. ETL for three data sources (BC, iTrent, Orderwise)
6. Testing of Data Sources
7. Data Modelling for Reports
8. Data Visualisation (Power BI) - T&M
9. Project Management
10. Phocus Report replicas
11. One-time NAV load

## Out of Scope
- iTrent discovery (Capital to conduct)
- Any items not specifically requested in SOW

## Dependencies

- Availability of key stakeholders
- Access and privileges to iTrent, Orderwise, Nav, BC
- iTrent API access and documentation
- Access to Phocus reports
- Co-ordination with 3rd party suppliers

## Rate Card

| Role | Day Rate | Hourly Rate |
|------|----------|-------------|
| *See SOW for details* | | |

## Representatives

| Party | Representative | Role |
|-------|---------------|------|
| Synapx | Jake Bowles | Global Director of Data & AI |
| Capital HB | Cristian Ettridge | General Manager |

## Current Status
- Contract signed (Feb 6, 2026)
- Kickoff meeting confirmed: **Monday 2:30 PM** (Feb 10)

## Discussion Topics from Cristian (Feb 6)

### Report & Dashboard Management
Cristian raised interest in understanding how to manage growing number of reports:
- Wants to build a logical library of reports
- Concerned about overlap and user confusion as report count grows
- Wants to establish good foundations early
- Looking for best practices on categorization and presentation to users

**Action**: Discuss report governance and organization strategy at Monday meeting

## Next Steps
1. ~~Confirm Monday meeting with Cristian~~ - Confirmed 2:30 PM
2. Prepare report governance discussion points
3. Set up Dev/Prod environments
4. Submit POC Funded Subscription request to Microsoft
5. Begin iTrent API discovery with Capital

## Related
- [Capital Hair & Beauty Client](../clients/capital-hb.md)
- [Cristian Ettridge](../people/cristian-ettridge.md)

---
*Last Updated: February 7, 2026*
