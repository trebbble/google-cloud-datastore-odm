"""
To run this locally:
  - Emulator: docker compose -f docker-compose.yml up -d --build
  - Env: DATASTORE_EMULATOR_HOST=localhost:10000 and GOOGLE_CLOUD_PROJECT=google-cloud-datastore-odm-dev
"""

from pathlib import Path
from dotenv import load_dotenv
from google_cloud_datastore_odm import Model, StringProperty, IntegerProperty, Count, Sum, Avg

load_dotenv()
print("\n" + "=" * 60)
print(f"Running: {Path(__file__).name}")
print("=" * 60 + "\n")


class SaleRecord(Model):
    item = StringProperty()
    price = IntegerProperty()


print("--- Seeding Data ---")
SaleRecord.put_multi([
    SaleRecord(id='sales1', item="Laptop", price=1000),
    SaleRecord(id='sales2', item="Mouse", price=50),
    SaleRecord(id='sales3', item="Keyboard", price=150),
    SaleRecord(id='sales4', item="Monitor", price=300),
])

base_query = SaleRecord.query()

print("\n--- Individual Aggregations ---")
total_sales = base_query.count()
total_revenue = base_query.sum(SaleRecord.price)
avg_price = base_query.avg(SaleRecord.price)

print(f"[Aggregate] Total Items Sold: {total_sales}")
print(f"[Aggregate] Total Revenue: ${total_revenue}")
print(f"[Aggregate] Average Item Price: ${avg_price:.2f}")

print("\n--- Batch Aggregation (Single RPC) ---")
stats = base_query.aggregate(
    items=Count(),
    revenue=Sum(SaleRecord.price),
    average=Avg("price")
)

print(f"[Batch] Items: {stats['items']}")
print(f"[Batch] Revenue: ${stats['revenue']}")
print(f"[Batch] Average: ${stats['average']:.2f}")
