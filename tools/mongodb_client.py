"""MongoDB operations for the portfolio agent."""

import os
from datetime import datetime, timezone

import certifi
from pymongo import MongoClient, DESCENDING
from pymongo.collection import Collection


def _db():
    client = MongoClient(
        os.environ["MONGODB_URI"],
        tlsCAFile=certifi.where(),
        tlsDisableOCSPEndpointCheck=True,
    )
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

def add_to_watchlist(user_id: str, ticker: str, note: str = "", added_price: float = 0.0):
    """Add or update a watchlist item. added_at and added_price are set only on insert."""
    col: Collection = _db()["watchlist"]
    col.update_one(
        {"user_id": user_id, "ticker": ticker.upper()},
        {
            "$set": {"note": note},
            "$setOnInsert": {
                "added_at": datetime.now(timezone.utc).isoformat(),
                "added_price": added_price,
            },
        },
        upsert=True,
    )


def get_watchlist(user_id: str) -> list[dict]:
    return list(_db()["watchlist"].find({"user_id": user_id}, {"_id": 0}))


def remove_from_watchlist(user_id: str, ticker: str):
    _db()["watchlist"].delete_one({"user_id": user_id, "ticker": ticker.upper()})


# ── Portfolio Rules ───────────────────────────────────────────────────────────

def get_rules(user_id: str) -> list[dict]:
    return list(_db()["rules"].find({"user_id": user_id}, {"_id": 0}))


def upsert_rule(user_id: str, rule_type: str, label: str, params: dict):
    """
    rule_type options:
      sector_max   — params: {sector: str, max_pct: float}
      position_max — params: {max_pct: float}
      min_sectors  — params: {min_count: int}
    """
    _db()["rules"].update_one(
        {"user_id": user_id, "label": label},
        {"$set": {"rule_type": rule_type, "params": params, "user_id": user_id}},
        upsert=True,
    )


def delete_rule(user_id: str, label: str):
    _db()["rules"].delete_one({"user_id": user_id, "label": label})


def get_memory_summary(user_id: str) -> dict:
    """Return counts that make MongoDB's role as agent memory visible."""
    db = _db()
    return {
        "holdings": db["holdings"].count_documents({"user_id": user_id}),
        "watchlist": db["watchlist"].count_documents({"user_id": user_id}),
        "rules": db["rules"].count_documents({"user_id": user_id}),
        "snapshots": db["snapshots"].count_documents({"user_id": user_id}),
        "collections": ["holdings", "watchlist", "rules", "snapshots", "transactions"],
    }


def seed_demo_portfolio(user_id: str):
    """Reset the demo user to a polished sample portfolio for judging."""
    db = _db()
    holdings = [
        ("AAPL", 100, 152.00, "Technology"),
        ("MSFT", 50, 285.00, "Technology"),
        ("NVDA", 20, 420.00, "Technology"),
        ("JPM", 40, 148.00, "Financial Services"),
        ("GS", 10, 335.00, "Financial Services"),
        ("JNJ", 35, 158.00, "Healthcare"),
        ("UNH", 8, 490.00, "Healthcare"),
        ("XOM", 55, 108.00, "Energy"),
        ("AMZN", 25, 135.00, "Consumer Cyclical"),
        ("BRK-B", 30, 295.00, "Financial Services"),
    ]

    for name in ("holdings", "watchlist", "rules"):
        db[name].delete_many({"user_id": user_id})

    for ticker, shares, avg_cost, sector in holdings:
        upsert_holding(user_id, ticker, shares, avg_cost, sector)

    add_to_watchlist(user_id, "VTI", "Broad US market ETF to research for diversification", 0)
    add_to_watchlist(user_id, "XLV", "Healthcare sector ETF to compare against tech exposure", 0)
    add_to_watchlist(user_id, "BND", "Bond ETF research idea for lower-volatility allocation", 0)

    upsert_rule(user_id, "sector_max", "Tech cap 45%", {"sector": "Technology", "max_pct": 45})
    upsert_rule(user_id, "position_max", "No single stock > 30%", {"max_pct": 30})
    upsert_rule(user_id, "min_sectors", "At least 4 sectors", {"min_count": 4})

    return {"status": "ok", "holdings": len(holdings), "watchlist": 3, "rules": 3}
