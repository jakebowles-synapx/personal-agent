# Leadenhall - LemonEdge Fabric Integration POC

## Overview
Proof of concept for integrating LemonEdge financial data with Microsoft Fabric, starting with FX rates import.

## Client
- **Company**: [Leadenhall Capital Partners](../clients/leadenhall-capital.md)
- **Primary Contact**: [Tayo Eletu-Odibo](../people/tayo-eletu-odibo.md) - Operations

## Vendor
- **LemonEdge** (financial software)
- **Contact**: Swapna Deshpande (LemonEdge support)

## Technical Details

### Current Work
- FX rates import via GraphQL API
- Integration with Microsoft Fabric

### Known Issues
1. **Pagination errors** - GraphQL pagination not working correctly
2. **Negative rates** - Need to exclude negative FX rates from import

### API Details
- GraphQL endpoint for data extraction
- Authentication via API tokens

## Recent Progress (Feb 6, 2026)

### FX Rates Import
- Exchange rates (204 records) for 30/01/2026 and 03/02/2026 successfully imported into LemonEdge UAT via API
- Tayo confirmed: **exclude negative rates from Fabric data going forward**
- LemonEdge application change required (Swapna working on it)
- Nandan filtering out negative records

### Outstanding Questions
- Need confirmation: filter GraphQL to only get latest FX Rates?

## Status
- **Phase**: POC Development - FX Rates testing
- **Progress**: UAT import successful
- **Action**: Nandan implementing negative rate filter

## Next Steps
1. ~~Resolve GraphQL pagination errors~~
2. Implement filter for negative rates - IN PROGRESS
3. Complete FX rates import POC
4. Review results with Tayo

## Related
- [Leadenhall Capital Partners Client](../clients/leadenhall-capital.md)
- [Tayo Eletu-Odibo](../people/tayo-eletu-odibo.md)

---
*Last Updated: February 2026*
