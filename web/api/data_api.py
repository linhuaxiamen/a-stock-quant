"""数据管理 API — 缓存统计 + 下载触发"""

import json
import os
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import login_required

data_api = Blueprint("data_api", __name__)


@data_api.before_request
@login_required
def guard():
    pass


def _cache_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "cache")


@data_api.route("/cache_stats")
def cache_stats():
    cache_dir = _cache_dir()
    files = []
    total_size = 0
    if os.path.isdir(cache_dir):
        for fname in os.listdir(cache_dir):
            if fname.endswith(".parquet"):
                fpath = os.path.join(cache_dir, fname)
                stat = os.stat(fpath)
                total_size += stat.st_size
                files.append({
                    "name": fname,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
    return jsonify({
        "file_count": len(files),
        "total_size_mb": round(total_size / 1048576, 2),
        "files": files,
    })


@data_api.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").strip()
    start = data.get("start", "20240101")
    end = data.get("end", "20241231")

    if not symbol:
        return jsonify({"ok": False, "error": "请输入股票代码"})

    try:
        from data.fetcher import fetch_daily
        df = fetch_daily(symbol, start, end, use_cache=True)
        return jsonify({"ok": True, "rows": len(df)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
