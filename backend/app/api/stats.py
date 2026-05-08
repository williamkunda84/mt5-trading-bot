from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Trade, WalletSnapshot
from app.services.mt5_connector import get_mt5

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/wallet")
async def wallet_stats(db: Session = Depends(get_db)):
    """Live wallet + trade statistics."""
    mt5 = await get_mt5()
    account = await mt5.get_account_info()

    closed = db.query(Trade).filter(Trade.status == "closed").all()
    open_trades = db.query(Trade).filter(Trade.status == "open").all()

    wins = [t for t in closed if (t.profit or 0) > 0]
    losses = [t for t in closed if (t.profit or 0) <= 0]
    total_profit = sum(t.profit or 0 for t in closed)
    total_pips = sum(t.pips or 0 for t in closed)
    avg_win = sum(t.profit for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.profit for t in losses) / len(losses) if losses else 0
    profit_factor = abs(sum(t.profit for t in wins)) / abs(sum(t.profit for t in losses)) \
        if losses and sum(t.profit for t in losses) != 0 else float("inf")

    by_symbol = {}
    for t in closed:
        s = by_symbol.setdefault(t.symbol, {"wins": 0, "losses": 0, "profit": 0.0, "pips": 0.0})
        if (t.profit or 0) > 0:
            s["wins"] += 1
        else:
            s["losses"] += 1
        s["profit"] += t.profit or 0
        s["pips"] += t.pips or 0

    return {
        "account": {
            "balance": account.balance,
            "equity": account.equity,
            "free_margin": account.free_margin,
            "currency": account.currency,
        },
        "totals": {
            "total_trades": len(closed),
            "open_trades": len(open_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
            "total_profit": round(total_profit, 2),
            "total_pips": round(total_pips, 1),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999,
        },
        "by_symbol": {
            sym: {
                "wins": d["wins"],
                "losses": d["losses"],
                "win_rate": round(d["wins"] / (d["wins"] + d["losses"]) * 100, 1)
                if (d["wins"] + d["losses"]) > 0 else 0,
                "profit": round(d["profit"], 2),
                "pips": round(d["pips"], 1),
            }
            for sym, d in by_symbol.items()
        },
    }


@router.get("/equity-curve")
async def equity_curve(limit: int = Query(60, le=365), db: Session = Depends(get_db)):
    snaps = (
        db.query(WalletSnapshot)
        .order_by(WalletSnapshot.date.desc())
        .limit(limit)
        .all()
    )
    snaps = list(reversed(snaps))
    return [
        {
            "date": s.date.isoformat(),
            "balance": s.balance,
            "equity": s.equity,
            "win_rate": s.win_rate,
            "total_profit": s.total_profit,
        }
        for s in snaps
    ]


@router.get("/recent-performance")
async def recent_performance(days: int = Query(7), db: Session = Depends(get_db)):
    """Day-by-day profit breakdown for the last N days."""
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    trades = (
        db.query(Trade)
        .filter(Trade.status == "closed", Trade.closed_at >= cutoff)
        .order_by(Trade.closed_at.asc())
        .all()
    )

    by_day: dict = {}
    for t in trades:
        day = t.closed_at.strftime("%Y-%m-%d")
        d = by_day.setdefault(day, {"profit": 0.0, "wins": 0, "losses": 0, "trades": 0})
        d["profit"] += t.profit or 0
        d["trades"] += 1
        if (t.profit or 0) > 0:
            d["wins"] += 1
        else:
            d["losses"] += 1

    return [
        {"date": day, **data, "profit": round(data["profit"], 2)}
        for day, data in sorted(by_day.items())
    ]
