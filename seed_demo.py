"""Seed a realistic demo portfolio with 10 stocks across 5 sectors + 30-day history."""

import os, sys, random
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

from pymongo import MongoClient
from tools import mongodb_client as mongo, market_data

USER_ID = "demo_user"

HOLDINGS = [
    ("AAPL",  100, 152.00, "Technology"),
    ("MSFT",   50, 285.00, "Technology"),
    ("NVDA",   20, 420.00, "Technology"),
    ("JPM",    40, 148.00, "Financial Services"),
    ("GS",     10, 335.00, "Financial Services"),
    ("JNJ",    35, 158.00, "Healthcare"),
    ("UNH",     8, 490.00, "Healthcare"),
    ("XOM",    55, 108.00, "Energy"),
    ("AMZN",   25, 135.00, "Consumer Cyclical"),
    ("BRK-B",  30, 295.00, "Financial Services"),
]

db = MongoClient(os.environ["MONGODB_URI"])["portfolio_agent"]
db["holdings"].delete_many({"user_id": USER_ID})
db["snapshots"].delete_many({"user_id": USER_ID})
print("Cleared existing holdings and snapshots.")

total_cost = sum(sh * ac for _, sh, ac, _ in HOLDINGS)

for ticker, shares, avg_cost, sector in HOLDINGS:
    mongo.upsert_holding(USER_ID, ticker, shares, avg_cost, sector)
    print(f"  {ticker:6s} {shares:4d} sh @ ${avg_cost:.2f}  [{sector}]")

print(f"\nFetching live prices...")
prices = {}
for ticker, shares, _, _ in HOLDINGS:
    try:
        p = market_data.get_price(ticker).get("price", 0)
        prices[ticker] = p
        print(f"  {ticker}: ${p:.2f}")
    except Exception as e:
        print(f"  {ticker}: failed ({e})")
        prices[ticker] = dict(HOLDINGS)[ticker] if ticker in dict(HOLDINGS) else 0

current_value = sum(sh * prices.get(t, ac) for t, sh, ac, _ in HOLDINGS)
print(f"\nPortfolio cost: ${total_cost:,.2f}  |  Current value: ${current_value:,.2f}")

# Generate 30 days of snapshots with a realistic random walk
random.seed(42)
start_value = total_cost * 0.97  # started slightly underwater
for i in range(30, 0, -1):
    day = datetime.now(timezone.utc) - timedelta(days=i)
    progress = (30 - i) / 30
    trend = start_value + (current_value - start_value) * progress
    noise = trend * random.uniform(-0.015, 0.015)
    value = round(trend + noise, 2)
    db["snapshots"].insert_one({
        "user_id": USER_ID,
        "total_value": value,
        "total_cost": total_cost,
        "snapshot_date": day.isoformat(),
    })

mongo.save_snapshot(USER_ID, round(current_value, 2), total_cost)
print("Generated 31 daily snapshots (30 days history + today).")
print("\nSeed complete.")
