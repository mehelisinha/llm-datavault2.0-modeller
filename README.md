# DWA - Data Warehouse Automation Project

Framework on creating Data Vault v2 model dynamically.
| Layer | Description |
|------|-------------|
| Bronze | Raw CDC landing zone — append-only Delta tables with I/U/D flags |
| Staging | AutomateDV stage macro — adds hash keys, hashdiffs, derived columns |
| Raw Vault | Hubs, Links, Satellites — immutable historised vault tables |
| Business Vault | PIT tables, Bridge tables, derived business rules |

**Table of content**:
- [Enironment Setup](./documentation/docs/env_setup.md)

