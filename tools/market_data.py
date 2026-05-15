"""Fetch live market data via yfinance (free, no API key needed)."""

import logging
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import yfinance as yf

logging.getLogger("yfinance").disabled = True

_PRICE_CACHE = {}
_PRICE_TTL_SECONDS = 60
_DEMO_FALLBACK_PRICES = {
    "AAPL": 302.21,
    "MSFT": 424.91,
    "NVDA": 228.31,
    "JPM": 298.16,
    "GS": 954.96,
    "JNJ": 228.59,
    "UNH": 393.12,
    "XOM": 155.96,
    "AMZN": 262.49,
    "BRK-B": 483.76,
    "SPY": 680.0,
    "VTI": 350.0,
    "XLV": 150.0,
    "BND": 73.0,
}


def get_price(ticker: str) -> dict:
    """Return current price, day change %, and market cap for a ticker."""
    ticker = ticker.upper()
    cached = _PRICE_CACHE.get(ticker)
    if cached and time.time() - cached["time"] < _PRICE_TTL_SECONDS:
        return cached["data"]

    try:
        data = _get_price_from_yahoo_chart(ticker)
    except Exception:
        data = _get_price_from_stooq(ticker)

    if data.get("price", 0) <= 0:
        data = _fallback_price(ticker)

    _PRICE_CACHE[ticker] = {"time": time.time(), "data": data}
    return data


def get_prices(tickers: list[str]) -> dict:
    """Fetch prices for many tickers in parallel, using the short in-process cache."""
    unique = sorted({ticker.upper() for ticker in tickers if ticker})
    if not unique:
        return {}

    prices = {}
    max_workers = min(8, len(unique))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(get_price, ticker): ticker for ticker in unique}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                prices[ticker] = future.result().get("price", 0)
            except Exception:
                prices[ticker] = 0
    return prices


def _get_price_from_yahoo_chart(ticker: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    try:
        response = requests.get(url, params={"range": "2d", "interval": "1d"}, timeout=5)
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
    except Exception:
        return _get_price_from_stooq(ticker)

    meta = result["meta"]
    closes = [c for c in result["indicators"]["quote"][0].get("close", []) if c is not None]
    if not closes:
        return _get_price_from_stooq(ticker)

    current = meta.get("regularMarketPrice") or closes[-1]
    prev_close = meta.get("chartPreviousClose") or (closes[-2] if len(closes) >= 2 else current)
    change_pct = round((current - prev_close) / prev_close * 100, 2) if prev_close else 0

    return {
        "ticker": ticker,
        "price": round(float(current), 2),
        "change_pct": change_pct,
        "market_cap": meta.get("marketCap"),
        "currency": meta.get("currency", "USD"),
    }


def _get_price_from_stooq(ticker: str) -> dict:
    try:
        symbol = ticker if "." in ticker else f"{ticker}.US"
        response = requests.get(
            "https://stooq.com/q/l/",
            params={"s": symbol.lower(), "f": "sd2t2ohlcv", "h": "", "e": "csv"},
            timeout=4,
        )
        response.raise_for_status()
        lines = [line.strip() for line in response.text.splitlines() if line.strip()]
        if len(lines) >= 2:
            headers = lines[0].split(",")
            values = lines[1].split(",")
            data = dict(zip(headers, values))
            close = data.get("Close")
            if close and close != "N/D":
                return {
                    "ticker": ticker,
                    "price": round(float(close), 2),
                    "change_pct": 0,
                    "market_cap": None,
                    "currency": "USD",
                }
    except Exception:
        pass
    return {"ticker": ticker, "price": 0, "change_pct": 0, "market_cap": None, "currency": "USD", "error": "Price unavailable"}


def _fallback_price(ticker: str) -> dict:
    """Keep demos useful when external market APIs throttle or time out."""
    price = _DEMO_FALLBACK_PRICES.get(ticker.upper())
    if price:
        return {
            "ticker": ticker,
            "price": price,
            "change_pct": 0,
            "market_cap": None,
            "currency": "USD",
            "source": "demo_fallback",
        }
    return {"ticker": ticker, "price": 0, "change_pct": 0, "market_cap": None, "currency": "USD", "error": "Price unavailable"}


def get_history(ticker: str, period: str = "1y") -> list[dict]:
    """Return OHLCV history as a list of dicts. period: 1mo, 3mo, 6mo, 1y, 2y."""
    hist = yf.Ticker(ticker).history(period=period)
    if hist.empty:
        return []
    return [
        {
            "date": str(idx.date()),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"]),
        }
        for idx, row in hist.iterrows()
    ]


def get_news(ticker: str, limit: int = 5) -> dict:
    """Return recent headlines for a ticker when the data provider exposes them."""
    ticker = ticker.upper()
    try:
        raw_items = yf.Ticker(ticker).news or []
    except Exception as exc:
        raw_items = []

    headlines = []
    for item in raw_items[:limit]:
        content = item.get("content", item)
        title = content.get("title") or item.get("title")
        publisher = content.get("provider", {}).get("displayName") or item.get("publisher")
        url = content.get("canonicalUrl", {}).get("url") or item.get("link")
        published = content.get("pubDate") or item.get("providerPublishTime")
        if title:
            headlines.append({
                "title": title,
                "publisher": publisher,
                "url": url,
                "published": published,
            })

    if headlines:
        return {"ticker": ticker, "headlines": headlines}

    return _get_news_from_google_rss(ticker, limit)


def _get_news_from_google_rss(ticker: str, limit: int) -> dict:
    try:
        response = requests.get(
            "https://news.google.com/rss/search",
            params={"q": f"{ticker} stock", "hl": "en-US", "gl": "US", "ceid": "US:en"},
            timeout=10,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception as exc:
        return {"ticker": ticker, "headlines": [], "error": f"News unavailable: {exc}"}

    headlines = []
    for item in root.findall("./channel/item")[:limit]:
        headlines.append({
            "title": item.findtext("title"),
            "publisher": None,
            "url": item.findtext("link"),
            "published": item.findtext("pubDate"),
        })

    return {"ticker": ticker, "headlines": [h for h in headlines if h["title"]]}


def get_info(ticker: str) -> dict:
    """Return company info: name, sector, industry, P/E, beta, 52w range."""
    ticker = ticker.upper()
    try:
        info = yf.Ticker(ticker).info
    except Exception as exc:
        return {
            "ticker": ticker,
            "name": ticker,
            "sector": "Unknown",
            "industry": "Unknown",
            "error": f"Company info unavailable: {exc}",
        }

    return {
        "ticker": ticker,
        "name": info.get("longName", ticker),
        "sector": info.get("sector", "Unknown"),
        "industry": info.get("industry", "Unknown"),
        "pe_ratio": info.get("trailingPE"),
        "beta": info.get("beta"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "description": info.get("longBusinessSummary", "")[:300],
    }
