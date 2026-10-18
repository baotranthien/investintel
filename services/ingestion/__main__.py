import argparse
import asyncio
from datetime import datetime
from services.ingestion.fred import FredProvider
from services.ingestion.bls import BlsProvider
from services.ingestion.nso import NsoProvider
from services.ingestion.http_client import shared_http_client

async def main():
    parser = argparse.ArgumentParser(description="Run data ingestion")
    parser.add_argument("command", help="Command to run (e.g. run)")
    parser.add_argument("--provider", required=True, help="Provider name (fred, bls, nso, sbv)")
    
    args = parser.parse_args()
    
    if args.command != "run":
        print("Invalid command")
        return
        
    print(f"Starting ingestion for provider: {args.provider}")
    
    provider = None
    if args.provider.lower() == "fred":
        provider = FredProvider()
        try:
            # Example: Fetch 10-Year Treasury Constant Maturity Rate
            print("Fetching DGS10...")
            data = await provider.fetch_macro_series("DGS10", start_date="2023-01-01")
            print(f"Success! Fetched {len(data)} records.")
        except Exception as e:
            print(f"Error fetching from FRED: {e}")
            
    elif args.provider.lower() == "bls":
        provider = BlsProvider()
        try:
            # Example: Fetch CPI (CUUR0000SA0)
            print("Fetching CUUR0000SA0...")
            data = await provider.fetch_macro_series("CUUR0000SA0", start_year="2023")
            print(f"Success! Fetched {len(data)} records.")
        except Exception as e:
            print(f"Error fetching from BLS: {e}")
            
    elif args.provider.lower() == "nso":
        provider = NsoProvider()
        try:
            await provider.fetch_macro_series("VNM_GDP")
        except Exception as e:
            print(f"NSO limits: {e}")
            
    elif args.provider.lower() == "sbv":
        print("SBV Provider currently requires manual Excel/CSV import due to lack of official API.")
        
    else:
        print(f"Unknown provider: {args.provider}")

    await shared_http_client.close()

if __name__ == "__main__":
    asyncio.run(main())
