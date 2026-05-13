"""MongoDB operations for the portfolio agent."""

import os
from pymongo import MongoClient, DESCENDING
from pymongo.collection import Collection


def _db():
    client = MongoClient(os.environ["MONGODB_URI"])
    return client["portfolio_agent"]


# ── Holdings ──────────────────────────────────────────────────────────────────

def get_holdings(user_id: str) -> list[dict]:
    col: Collection = _db()["holdings"]
    return list(col.find({"user_id": user_id}, {"_id": 0}))


def upsert_holding(user_id: str, ticker: str, shares: float, avg_cost: float, sector: str = "Unknown"):
    col: Collection = _db()["holdings"]
    col.update_one(
        {"user_id": user_id, "ticker": ticker.upper()},
        {"$set": {"shares": shares, "avg_cost": avg_cost, "sector": sector}},
        upsert=True,
    )


def delete_holding(user_id: str, ticker: str):
    _db()["holdings"].delete_one({"user_id": user_id, "ticker": ticker.upper()})


# ── Transactions ──────────────────────────────────────────────────────────────

def log_transaction(user_id: str, transaction: dict):
    transaction["user_id"] = user_id
    _db()["transactions"].insert_one(transaction)


def get_transactions(user_id: str, limit: int = 50) -> list[dict]:
    col: Collection = _db()["transactions"]
    return list(
        col.find({"user_id": user_id}, {"_id": 0})
           .sort("timestamp", DESCENDING)
           .limit(limit)
    )


# ── Snapshots ─────────────────────────────────────────────────────────────────

def save_snapshot(user_id: str, total_value: float, total_cost: float):
    from datetime import datetime, timezone
    _db()["snapshots"].insert_one({
        "user_id": user_id,
        "total_value": total_value,
        "total_cost": total_cost,
        "snapshot_date": datetime.now(timezone.utc).isoformat(),
    })


def get_snapshots(user_id: str, limit: int = 30) -> list[dict]:
    col: Collection = _db()["snapshots"]
    return list(
        col.find({"user_id": user_id}, {"_id": 0})
           .sort("snapshot_date", DESCENDING)
           .limit(limit)
    )


# ── Watchlist ─────────────────────────────────────────────────────────────────

def add_to_watchlist(user_id: str, ticker: str, note: str = ""):
    col: Collection = _db()["watchlist"]
    col.update_one(
        {"user_id": user_id, "ticker": ticker.upper()},
        {"$set": {"note": note}},
        upsert=True,
    )


def get_watchlist(user_id: str) -> list[dict]:
    return list(_db()["watchlist"].find({"user_id": user_id}, {"_id": 0}))
