"""实时行情 API — 代理东方财富行情接口"""

from flask import Blueprint, jsonify, request
from flask_login import login_required

from data.realtime import fetch_realtime

quote_api = Blueprint("quote_api", __name__)


@quote_api.before_request
@login_required
def guard():
    pass


@quote_api.route("/realtime")
def realtime():
    symbols_str = request.args.get("symbols", "")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
    if not symbols:
        return jsonify({})
    try:
        data = fetch_realtime(symbols)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
