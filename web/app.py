"""Flask 应用工厂"""

from flask import Flask
from flask_login import LoginManager

import config

login_manager = LoginManager()


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["SECRET_KEY"] = config.WEB["secret_key"]

    # Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # 注册 Blueprint
    from web.auth import auth_bp
    from web.blueprints.dashboard import dash_bp
    from web.blueprints.backtest import bt_bp
    from web.blueprints.live import live_bp
    from web.blueprints.strategy import strat_bp
    from web.blueprints.data_mgmt import data_bp
    from web.blueprints.trades import trades_bp
    from web.api.backtest_api import bt_api
    from web.api.live_api import live_api
    from web.api.data_api import data_api
    from web.api.quote_api import quote_api

    app.register_blueprint(auth_bp)
    app.register_blueprint(dash_bp)
    app.register_blueprint(bt_bp)
    app.register_blueprint(live_bp)
    app.register_blueprint(strat_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(trades_bp)
    app.register_blueprint(bt_api, url_prefix="/api/backtest")
    app.register_blueprint(live_api, url_prefix="/api/live")
    app.register_blueprint(data_api, url_prefix="/api/data")
    app.register_blueprint(quote_api, url_prefix="/api/quote")

    return app
