"""交易日志查看 — 读取 JSONL 文件，过滤+分页"""

import json
import os

from flask import Blueprint, render_template, request
from flask_login import login_required

trades_bp = Blueprint("trades", __name__)

PAGE_SIZE = 50


@trades_bp.before_request
@login_required
def guard():
    pass


def _log_file():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "live", "trade_log.jsonl")


def _read_trades():
    log_file = _log_file()
    trades = []
    if not os.path.exists(log_file):
        return trades
    try:
        with open(log_file, "r") as f:
            for line in f:
                try:
                    trades.append(json.loads(line.strip()))
                except (json.JSONDecodeError, ValueError):
                    pass
    except Exception:
        pass
    return trades


@trades_bp.route("/trades/")
def list():
    all_trades = _read_trades()

    # 过滤
    symbol = request.args.get("symbol", "").strip()
    action = request.args.get("action", "").strip()
    date_start = request.args.get("date_start", "").strip()
    date_end = request.args.get("date_end", "").strip()

    filtered = all_trades
    if symbol:
        filtered = [t for t in filtered if symbol in t.get("symbol", "")]
    if action:
        filtered = [t for t in filtered if t.get("action", "") == action]
    if date_start:
        filtered = [t for t in filtered if t.get("time", "") >= date_start]
    if date_end:
        filtered = [t for t in filtered if t.get("time", "") <= date_end + " 23:59:59"]

    # 分页
    page = max(1, int(request.args.get("page", 1)))
    total = len(filtered)
    start_idx = (page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_trades = filtered[start_idx:end_idx]
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    return render_template("trades/list.html",
                           trades=page_trades,
                           page=page,
                           total_pages=total_pages,
                           total=total,
                           symbol=symbol,
                           action=action,
                           date_start=date_start,
                           date_end=date_end)
