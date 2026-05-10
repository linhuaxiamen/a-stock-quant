"""数据管理 — 缓存文件查看/下载/删除"""

import os
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

import config

data_bp = Blueprint("data_mgmt", __name__)


@data_bp.before_request
@login_required
def guard():
    pass


def _cache_dir():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")


def _list_cache():
    cache_dir = _cache_dir()
    files = []
    total_size = 0
    if os.path.isdir(cache_dir):
        for fname in sorted(os.listdir(cache_dir)):
            if fname.endswith(".parquet"):
                fpath = os.path.join(cache_dir, fname)
                stat = os.stat(fpath)
                total_size += stat.st_size
                files.append({
                    "name": fname,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
    return files, total_size


@data_bp.route("/data/")
def cache():
    files, total_size = _list_cache()
    return render_template("data/cache.html", files=files, total_size_mb=round(total_size / 1048576, 2))


@data_bp.route("/data/download", methods=["POST"])
def download():
    symbol = request.form.get("symbol", "").strip()
    start = request.form.get("start", "20240101").strip()
    end = request.form.get("end", "20241231").strip()
    if not symbol:
        flash("请输入股票代码", "danger")
        return redirect(url_for("data_mgmt.cache"))

    try:
        from data.fetcher import fetch_daily
        df = fetch_daily(symbol, start, end, use_cache=True)
        flash(f"下载完成: {symbol} ({len(df)}条)", "success")
    except Exception as e:
        flash(f"下载失败: {e}", "danger")
    return redirect(url_for("data_mgmt.cache"))


@data_bp.route("/data/delete/<filename>", methods=["POST"])
def delete(filename):
    cache_dir = _cache_dir()
    fpath = os.path.join(cache_dir, filename)
    if os.path.isfile(fpath) and filename.endswith(".parquet"):
        os.remove(fpath)
        flash(f"已删除: {filename}", "success")
    else:
        flash("文件不存在或格式不正确", "danger")
    return redirect(url_for("data_mgmt.cache"))
