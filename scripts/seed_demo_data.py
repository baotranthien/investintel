import os
import csv
from datetime import datetime, timedelta

def create_demo_csv(symbol, filename, base_price):
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        start_date = datetime(2023, 1, 1)
        for i in range(100):
            date_str = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            writer.writerow([
                date_str,
                base_price,
                base_price * 1.05,
                base_price * 0.95,
                base_price * 1.02,
                1000000
            ])
            base_price = base_price * 1.02

if __name__ == '__main__':
    data_dir = os.path.join(os.path.dirname(__file__), '../data')
    os.makedirs(data_dir, exist_ok=True)
    
    print("Seeding demo CSV files...")
    create_demo_csv('FPT', os.path.join(data_dir, 'FPT_demo.csv'), 80000)
    create_demo_csv('VCB', os.path.join(data_dir, 'VCB_demo.csv'), 90000)
    create_demo_csv('MWG', os.path.join(data_dir, 'MWG_demo.csv'), 40000)
    print("Done!")
