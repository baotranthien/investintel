# Free Data Sources Registry

This registry tracks the status and licensing of free data sources used in the platform.

| Name | Country | Dataset | API? | Cost | Terms / License | Automation | Status |
|---|---|---|---|---|---|---|---|
| FRED | US | Macro, Yields | Yes (Key required) | Free | Personal use permitted | Active | IMPLEMENTED |
| BLS | US | CPI, Labor | Yes (Public V2) | Free | Public domain | Active | IMPLEMENTED |
| NSO | VN | GDP, CPI | No (Excel/HTML) | Free | Public data | Manual Import | PARTIAL |
| SBV | VN | FX, Rates | No | Free | Public data | Manual Import | PARTIAL |
| MarketData | VN | EOD Prices | No (CSV Import) | Free | Dependent on source | Manual Import | IMPLEMENTED (Mock/CSV) |

**Notes on Vietnam Market Data:**
No official free EOD API exists without undocumented usage. Using CSV importer (`MarketDataCsvProvider`) as fallback to maintain architecture integrity in V1.

**Note on FRED:**
API key required. FRED allows app creation using a subset of data for personal use. Must provide attribution.
