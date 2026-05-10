"""仪表盘首页"""

import json
import os

from flask import Blueprint, render_template
from flask_login import login_required

from web.bg import bg_manager

dash_bp = Blueprint("dashboard", __name__)


@dash_bp.before_request
@login_required
def guard():
    pass


@dash_bp.route("/")
def index():
    # 实盘状态
    live_status = {"running": False}
    if bg_manager.live_running:
        try:
            trader = bg_manager.live_session.trader
            account = trader.broker.get_account()
            positions = trader.broker.get_positions()
            live_status = {
                "running": True,
                "strategy": trader.strategy.config.name,
                "symbols": trader.symbols,
                "total_assets": account.total_assets,
                "cash": account.cash,
                "market_value": account.market_value,
                "position_count": len(positions),
            }
        except Exception:
            pass

    # 最近回测结果
    last_bt = bg_manager.last_backtest_result

    # 最近交易日志 (最后10条)
    recent_trades = []
    log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "live", "trade_log.jsonl")
    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                lines = f.readlines()
            for line in lines[-10:]:
                try:
                    recent_trades.append(json.loads(line.strip()))
                except (json.JSONDecodeError, ValueError):
                    pass
            recent_trades.reverse()
        except Exception:
            pass

    return render_template("dashboard.html", live_status=live_status, last_bt=last_bt, recent_trades=recent_trades)
