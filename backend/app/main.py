import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.config import settings
from app.database import init_db, SessionLocal
from app.services.trading_bot import tick

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("Database initialised")
    _seed_config()

    # Bot tick every 30 s
    scheduler.add_job(_scheduled_tick, "interval", seconds=30, id="bot_tick")
    # Setup scanner every 60 s
    scheduler.add_job(_scheduled_setup_scan, "interval", seconds=60, id="setup_scan")
    scheduler.start()
    log.info("Scheduler started (bot=30s, setups=60s)")

    yield

    scheduler.shutdown(wait=False)
    log.info("Scheduler stopped")


async def _scheduled_tick():
    db = SessionLocal()
    try:
        await tick(db)
    except Exception as exc:
        log.error("Bot tick failed: %s", exc)
    finally:
        db.close()


async def _scheduled_setup_scan():
    from app.api.setups import run_setup_scan
    from app.api.ws import maybe_broadcast_alerts
    db = SessionLocal()
    try:
        await run_setup_scan(db)
        await maybe_broadcast_alerts(db)
    except Exception as exc:
        log.error("Setup scan failed: %s", exc)
    finally:
        db.close()


def _seed_config():
    from app.models import BotConfig
    db = SessionLocal()
    try:
        if not db.query(BotConfig).first():
            db.add(BotConfig(
                is_running=False,
                symbols=settings.default_symbols,
                risk_percent=settings.default_risk_percent,
                max_open_trades=settings.default_max_trades,
                timeframe=settings.default_timeframe,
            ))
            db.commit()
    finally:
        db.close()


app = FastAPI(
    title="ForexBot API",
    version="1.1.0",
    description="AI-powered MetaTrader 5 trading bot with market analytics",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import trades, bot, analysis, stats, ws, setups  # noqa: E402

app.include_router(trades.router, prefix="/api")
app.include_router(bot.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(setups.router, prefix="/api")
app.include_router(ws.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "mode": settings.trading_mode}


# Serve built frontend (Railway single-service deployment)
frontend_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
