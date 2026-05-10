"""回测模块 — 表单 + 结果页"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from web.bg import bg_manager
from web.blueprints.strategy import STRATEGY_REGISTRY

bt_bp = Blueprint("backtest", __name__)


@bt_bp.before_request
@login_required
def guard():
    pass


@bt_bp.route("/backtest/")
def form():
    strategies = [(k, v["display_name"]) for k, v in STRATEGY_REGISTRY.items()]
    return render_template("backtest/form.html", strategies=strategies)


@bt_bp.route("/backtest/run", methods=["POST"])
def run():
    stock = request.form.get("stock", "000001").strip()
    start = request.form.get("start", "20240101").strip()
    end = request.form.get("end", "20241231").strip()
    strategy_name = request.form.get("strategy", "ma_cross")
    initial_cash = float(request.form.get("initial_cash", "1000000"))

    reg = STRATEGY_REGISTRY.get(strategy_name)
    if not reg:
        flash("策略不存在", "danger")
        return redirect(url_for("backtest.form"))

    # 收集策略参数
    params = {}
    for p in reg["params"]:
        val = request.form.get(f"param_{p['key']}", str(p["default"]))
        if p["type"] == "int":
            params[p["key"]] = int(val)
        elif p["type"] == "float":
            params[p["key"]] = float(val)
        else:
            params[p["key"]] = val

    task_id = bg_manager.start_backtest(stock, start, end, strategy_name, params, initial_cash)
    return redirect(url_for("backtest.result_page", task_id=task_id))


@bt_bp.route("/backtest/result/<task_id>")
def result_page(task_id):
    task = bg_manager.get_backtest_task(task_id)
    if not task:
        flash("回测任务不存在", "danger")
        return redirect(url_for("backtest.form"))
    return render_template("backtest/result.html", task_id=task_id)
