"""策略管理 — 策略注册表 + 列表/详情页"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required

from strategy.ma_cross import MACrossStrategy, MACrossConfig
from strategy.rsi_reversal import RSIStrategy, RSIConfig

strat_bp = Blueprint("strategy", __name__)

STRATEGY_REGISTRY = {
    "ma_cross": {
        "class": MACrossStrategy,
        "config_class": MACrossConfig,
        "display_name": "双均线交叉策略",
        "description": "短均线上穿长均线买入，下穿卖出。经典趋势跟踪策略。",
        "params": [
            {"key": "short_window", "label": "短均线周期", "type": "int", "default": 5},
            {"key": "long_window", "label": "长均线周期", "type": "int", "default": 20},
        ],
    },
    "rsi_reversal": {
        "class": RSIStrategy,
        "config_class": RSIConfig,
        "display_name": "RSI均值回归策略",
        "description": "RSI低于超卖阈值买入，高于超买阈值卖出。均值回归策略。",
        "params": [
            {"key": "period", "label": "RSI周期", "type": "int", "default": 14},
            {"key": "oversold", "label": "超卖阈值", "type": "float", "default": 30.0},
            {"key": "overbought", "label": "超买阈值", "type": "float", "default": 70.0},
        ],
    },
}


@strat_bp.before_request
@login_required
def guard():
    pass


@strat_bp.route("/strategy/")
def list():
    strategies = []
    for key, reg in STRATEGY_REGISTRY.items():
        strategies.append({
            "key": key,
            "display_name": reg["display_name"],
            "description": reg["description"],
            "param_count": len(reg["params"]),
        })
    return render_template("strategy/list.html", strategies=strategies)


@strat_bp.route("/strategy/<name>", methods=["GET", "POST"])
def detail(name):
    reg = STRATEGY_REGISTRY.get(name)
    if not reg:
        flash("策略不存在", "danger")
        return redirect(url_for("strategy.list"))

    if request.method == "POST":
        params = {}
        for p in reg["params"]:
            val = request.form.get(p["key"], str(p["default"]))
            if p["type"] == "int":
                params[p["key"]] = int(val)
            elif p["type"] == "float":
                params[p["key"]] = float(val)
            else:
                params[p["key"]] = val
        try:
            cfg = reg["config_class"](**params)
            flash(f"策略参数已更新: {reg['display_name']}", "success")
        except Exception as e:
            flash(f"参数错误: {e}", "danger")
        return redirect(url_for("strategy.detail", name=name))

    return render_template("strategy/detail.html", name=name, reg=reg)
