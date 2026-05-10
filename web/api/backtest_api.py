"""回测 API — 状态查询 + 结果获取"""

from flask import Blueprint, jsonify
from flask_login import login_required

from web.bg import bg_manager

bt_api = Blueprint("backtest_api", __name__)


@bt_api.before_request
@login_required
def guard():
    pass


@bt_api.route("/status/<task_id>")
def status(task_id):
    task = bg_manager.get_backtest_task(task_id)
    if not task:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "status": task.status,
        "progress": task.progress,
        "error": task.error,
    })


@bt_api.route("/result/<task_id>")
def result(task_id):
    task = bg_manager.get_backtest_task(task_id)
    if not task:
        return jsonify({"error": "not found"}), 404
    if task.status != "done":
        return jsonify({"error": "not ready", "status": task.status}), 400
    return jsonify(task.result)
