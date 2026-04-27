"""FastAPI app: REST control + websocket stream for the live UI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from mm_sim.logging_config import configure
from mm_sim.types import (
    ExperimentConfig,
    ScenarioEvent,
    ScenarioEventKind,
)
from runner.manifest import expand, load_manifest
from server.session import Session

configure()

app = FastAPI(title="Market Maker Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MANIFEST_PATH = Path("backend/experiments.yaml")
SESSION: Session | None = None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/experiments")
def list_experiments() -> list[dict[str, Any]]:
    raw = load_manifest(MANIFEST_PATH)
    return [
        {
            "id": e.get("id"),
            "finding": e.get("finding"),
            "description": e.get("description", ""),
        }
        for e in raw
    ]


@app.post("/api/session/start")
async def start_session(payload: dict[str, Any]) -> dict[str, Any]:
    """payload may be either: { 'experiment_id': str } or { 'config': ExperimentConfig dict }"""
    global SESSION
    if SESSION and SESSION.running:
        raise HTTPException(409, "session already running; stop it first")
    if "experiment_id" in payload:
        raw = load_manifest(MANIFEST_PATH)
        entry = next((e for e in raw if e.get("id") == payload["experiment_id"]), None)
        if entry is None:
            raise HTTPException(404, f"experiment {payload['experiment_id']!r} not found")
        cfgs = expand(entry)
        cfg = cfgs[0]
    else:
        cfg = ExperimentConfig.model_validate(payload["config"])
    speed = float(payload.get("speed", 5.0))
    SESSION = Session(cfg=cfg, speed=speed)
    SESSION.start(asyncio.get_running_loop())
    return {"ok": True, "experiment_id": cfg.id}


@app.post("/api/session/stop")
async def stop_session() -> dict[str, Any]:
    global SESSION
    if SESSION:
        SESSION.stop()
        SESSION = None
    return {"ok": True}


@app.post("/api/session/pause")
async def pause_session(payload: dict[str, bool]) -> dict[str, Any]:
    if SESSION:
        SESSION.pause(payload.get("paused", True))
    return {"ok": True}


@app.patch("/api/session/parameters")
async def patch_parameters(patch: dict[str, Any]) -> dict[str, Any]:
    if SESSION:
        SESSION.update_quoter(patch)
    return {"ok": True}


@app.patch("/api/session/interventions")
async def patch_interventions(patch: dict[str, Any]) -> dict[str, Any]:
    if SESSION:
        SESSION.update_interventions(patch["name"], bool(patch["enabled"]))
    return {"ok": True}


@app.post("/api/session/inject_event")
async def inject_event(payload: dict[str, Any]) -> dict[str, Any]:
    if SESSION:
        SESSION.inject_event(
            ScenarioEvent(
                at_seconds=0.0,
                kind=ScenarioEventKind(payload["kind"]),
                params=payload.get("params", {}),
            )
        )
    return {"ok": True}


@app.get("/api/session/state")
async def get_state() -> dict[str, Any]:
    if not SESSION or not SESSION.engine:
        return {"running": False}
    e = SESSION.engine
    return {
        "running": SESSION.running,
        "paused": SESSION.paused,
        "experiment_id": SESSION.cfg.id,
        "sim_t": e.sim_t,
        "inventory": e.pnl.inventory,
        "total_pnl": e.pnl.total_pnl,
        "spread_pnl": e.pnl.realised_spread_pnl,
        "inventory_pnl": e.pnl.unrealised_pnl,
        "sigma_est": e.vol.sigma,
        "gamma": e.quoter.gamma,
        "k": e.quoter.k,
        "tau": e.quoter.tau,
        "interventions": {
            n: getattr(e.intervention_ctx.cfg, n)
            for n in (
                "adaptive_spread",
                "kill_switch",
                "news_detector",
                "hedge_on_threshold",
                "per_counterparty_penalty",
            )
        },
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    if not SESSION:
        await ws.send_json({"error": "no session running"})
        await ws.close()
        return
    q = SESSION.subscribe()
    try:
        while True:
            msg = await q.get()
            await ws.send_text(msg.model_dump_json())
    except WebSocketDisconnect:
        pass
    finally:
        if SESSION:
            SESSION.unsubscribe(q)
