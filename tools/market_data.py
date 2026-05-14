"""Fetch live market data via yfinance (free, no API key needed)."""

import logging

import requests
import yfinance as yf

logging.getLogger("yfinance").disabled = True


def get_price(ticker: str) -> dict:
    """Return current price, day change %, and market cap for a ticker."""
    ticker = ticker.upper()
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        hist = t.history(period="2d")
    except Exception:
        hist = None

    if hist is not None and not hist.empty:
        prev_close = hist["Close"].iloc[-2] if len(hist) >= 2 else hist["Close"].iloc[-1]
        current = hist["Close"].iloc[-1]
        change_pct = round((current - prev_close) / prev_close * 100, 2)

        return {
            "ticker": ticker,
            "price": round(float(current), 2),
            "change_pct": change_pct,
            "market_cap": getattr(info, "market_cap", None),
            "currency": getattr(info, "currency", "USD"),
        }

    return _get_price_from_yahoo_chart(ticker)


def _get_price_from_yahoo_chart(ticker: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    try:
        response = requests.get(url, params={"range": "2d", "interval": "1d"}, timeout=10)
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
    symbol = ticker if "." in ticker else f"{ticker}.US"
    response = requests.get(
        "https://stooq.com/q/l/",
        params={"s": symbol.lower(), "f": "sd2t2ohlcv", "h": "", "e": "csv"},
        timeout=10,
    )
    response.raise_for_status()
    lines = [line.strip() for line in response.text.splitlines() if line.strip()]
    if len(lines) < 2:
        return {"ticker": ticker, "error": f"No data for {ticker}"}

    headers = lines[0].split(",")
    values = lines[1].split(",")
    data = dict(zip(headers, values))
    close = data.get("Close")
    if not close or close == "N/D":
        return {"ticker": ticker, "error": f"No data for {ticker}"}

    return {
        "ticker": ticker,
        "price": round(float(close), 2),
        "change_pct": 0,
        "market_cap": None,
        "currency": "USD",
    }


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
        return {"ticker": ticker, "headlines": [], "error": f"News unavailable: {exc}"}

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

    return {"ticker": ticker, "headlines": headlines}


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
