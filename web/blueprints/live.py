"""实盘交易模块 — 启动/停止/状态"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from live.trader import LiveTrader
from live.paper_broker import PaperBroker
from web.bg import bg_manager
from web.blueprints.strategy import STRATEGY_REGISTRY

live_bp = Blueprint("live", __name__)


@live_bp.before_request
@login_required
def guard():
    pass


@live_bp.route("/live/")
def control():
    strategies = [(k, v["display_name"]) for k, v in STRATEGY_REGISTRY.items()]
    return render_template("live/control.html", strategies=strategies, live_running=bg_manager.live_running)


@live_bp.route("/live/status")
def status():
    return render_template("live/status.html")
