"""实盘交易 API — 启动/停止/状态"""

from flask import Blueprint, jsonify, request
from flask_login import login_required

from live.trader import LiveTrader
from live.paper_broker import PaperBroker
from web.bg import bg_manager
from web.blueprints.strategy import STRATEGY_REGISTRY

live_api = Blueprint("live_api", __name__)


@live_api.before_request
@login_required
def guard():
    pass


@live_api.route("/start", methods=["POST"])
def start():
    if bg_manager.live_running:
        return jsonify({"ok": False, "error": "实盘已在运行中"})

    data = request.get_json(silent=True) or {}
    symbols_str = data.get("symbols", "000001")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
    strategy_name = data.get("strategy", "ma_cross")
    broker_mode = data.get("broker", "paper")
    initial_cash = float(data.get("initial_cash", 1000000))
    poll_interval = int(data.get("poll_interval", 60))
    max_position_pct = float(data.get("max_position_pct", 0.3))
    stop_loss_pct = float(data.get("stop_loss_pct", 0.07))

    reg = STRATEGY_REGISTRY.get(strategy_name)
    if not reg:
        return jsonify({"ok": False, "error": f"策略不存在: {strategy_name}"})

    # 收集策略参数
    params = {}
    for p in reg["params"]:
        val = data.get(f"param_{p['key']}", p["default"])
        if p["type"] == "int":
            params[p["key"]] = int(val)
        elif p["type"] == "float":
            params[p["key"]] = float(val)
        else:
            params[p["key"]] = val

    cfg = reg["config_class"](**params)
    strategy = reg["class"](cfg)

    if broker_mode == "qmt":
        from live.qmt_broker import QMTBroker
        account_id = data.get("account_id", "")
        qmt_path = data.get("qmt_path", "")
        broker = QMTBroker(account_id=account_id, qmt_path=qmt_path)
    else:
        broker = PaperBroker(initial_cash=initial_cash)

    trader = LiveTrader(
        strategy=strategy,
        broker=broker,
        symbols=symbols,
        poll_interval=poll_interval,
        max_position_pct=max_position_pct,
        stop_loss_pct=stop_loss_pct,
    )

    ok = bg_manager.start_live(trader)
    return jsonify({"ok": ok})


@live_api.route("/stop", methods=["POST"])
def stop():
    ok = bg_manager.stop_live()
    return jsonify({"ok": ok})


@live_api.route("/status")
def status():
    if not bg_manager.live_running:
        return jsonify({"running": False})

    try:
        trader = bg_manager.live_session.trader
        account = trader.broker.get_account()
        positions = trader.broker.get_positions()

        pos_list = []
        for p in positions:
            pnl_pct = 0
            if p.cost_price > 0:
                pnl_pct = (p.current_price - p.cost_price) / p.cost_price
            pos_list.append({
                "symbol": p.symbol,
                "name": p.name,
                "quantity": p.quantity,
                "available": p.available,
                "cost_price": round(p.cost_price, 2),
                "current_price": round(p.current_price, 2),
                "pnl": round(p.pnl, 2),
                "pnl_pct": round(pnl_pct, 4),
            })

        return jsonify({
            "running": True,
            "strategy": trader.strategy.config.name,
            "symbols": trader.symbols,
            "account": {
                "total_assets": round(account.total_assets, 2),
                "cash": round(account.cash, 2),
                "market_value": round(account.market_value, 2),
                "today_pnl": round(account.today_pnl, 2),
            },
            "positions": pos_list,
        })
    except Exception as e:
        return jsonify({"running": True, "error": str(e)})
