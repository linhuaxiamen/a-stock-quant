"""登录认证 — 单管理员用户，密码从 config.WEB 读取"""

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import UserMixin, login_user, logout_user, login_required
from werkzeug.security import check_password_hash

import config
from web.app import login_manager

auth_bp = Blueprint("auth", __name__)


class AdminUser(UserMixin):
    id = "admin"
    username = config.WEB["admin_username"]


@login_manager.user_loader
def load_user(user_id):
    if user_id == "admin":
        return AdminUser()
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if (username == config.WEB["admin_username"]
                and check_password_hash(config.WEB["admin_password_hash"], password)):
            login_user(AdminUser())
            next_page = request.args.get("next", url_for("dashboard.index"))
            return redirect(next_page)
        flash("用户名或密码错误", "danger")
    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
