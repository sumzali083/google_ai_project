from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class Holding:
    ticker: str
    shares: float
    avg_cost: float
    sector: str = "Unknown"

    def to_dict(self):
        return asdict(self)


@dataclass
class Transaction:
    ticker: str
    action: str          # "buy" | "sell"
    shares: float
    price: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self):
        return asdict(self)


@dataclass
class PortfolioSnapshot:
    user_id: str
    holdings: list
    total_value: float
    cash: float
    snapshot_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self):
        return asdict(self)
