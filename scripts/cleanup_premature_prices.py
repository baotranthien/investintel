import sys, os
sys.path.insert(0, os.path.abspath("."))
from database.connection import engine
from sqlalchemy import text

with engine.connect() as conn:
    trans = conn.begin()
    try:
        # Check count of 2026-11-10 records
        cnt = conn.execute(text("SELECT count(*) FROM prices WHERE observation_date = '2026-11-10';")).scalar()
        print(f"Records on 2026-11-10 to clean up: {cnt}")

        if cnt > 0:
            # Verify that every asset has an observation on 2026-11-09
            missing_09 = conn.execute(text("""
                SELECT p10.id, a.symbol
                FROM prices p10
                JOIN assets a ON a.id = p10.asset_id
                LEFT JOIN prices p09 ON p09.asset_id = p10.asset_id AND p09.observation_date = '2026-11-09'
                WHERE p10.observation_date = '2026-11-10' AND p09.id IS NULL;
            """)).fetchall()
            if missing_09:
                print(f"Warning: {len(missing_09)} symbols missing 2026-11-09 row. Updating those to 2026-11-09 instead of deleting:")
                for r in missing_09:
                    print("Updating to 2026-11-09:", r)
                    conn.execute(text("UPDATE prices SET observation_date = '2026-11-09' WHERE id = :id"), {"id": r[0]})

            # Delete the remaining duplicate 2026-11-10 records
            del_res = conn.execute(text("DELETE FROM prices WHERE observation_date = '2026-11-10';"))
            print(f"Deleted {del_res.rowcount} premature rows from prices table.")

        trans.commit()
        print("Database transaction committed successfully.")
    except Exception as exc:
        trans.rollback()
        print("Error during cleanup:", exc)
        raise

with engine.connect() as conn:
    max_date = conn.execute(text("SELECT max(observation_date) FROM prices;")).scalar()
    print("New maximum observation date in prices table:", max_date)
