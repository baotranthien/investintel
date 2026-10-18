# Data Limitations

As of Phase 1, the following limitations are known and documented:

1. **Vietnam Market Data:** No real-time or historical free API exists that strictly adheres to the "official sources only" rule. The system currently relies on manual CSV imports for local data.
2. **Revisions:** While the database schema supports revisions (`vintage`, `supersedes_id`), automated providers like FRED only fetch the latest observation unless specifically configured for point-in-time extraction.
3. **News & Disclosures:** Not yet implemented in Phase 1.
4. **Corporate Actions:** Adjustment factors are currently placeholder logic in the importer. A full event-driven corporate action adjustment engine is deferred to Phase 2.
5. **No Fundamentals:** Financial statements and metrics are not ingested yet.
