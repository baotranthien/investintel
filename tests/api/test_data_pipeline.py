import pytest
import datetime
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from services.ingestion.base import MacroDataPoint
from services.ingestion.market_data import MarketDataCsvProvider

def test_market_data_csv_provider(tmp_path):
    # Setup test file
    d = tmp_path / "sub"
    d.mkdir()
    p = d / "test_data.csv"
    p.write_text("Date,Open,High,Low,Close,Volume\n2023-01-01,10,12,9,11,1000\n2023-01-02,11,13,10,12,2000")
    
    # Run test
    import asyncio
    provider = MarketDataCsvProvider()
    results = asyncio.run(provider.fetch_market_data(
        symbol="TEST",
        start_date=datetime.date(2023, 1, 1),
        end_date=datetime.date(2023, 1, 31),
        file_path=str(p)
    ))
    
    assert len(results) == 2
    assert results[0].close == 11.0
    assert results[1].close == 12.0
