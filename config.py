"""全局配置"""

# 数据源设置
DATA_SOURCE = "akshare"  # akshare (免费) / tushare (需token)

# Tushare token (如果用tushare)
TUSHARE_TOKEN = ""

# 默认回测参数
BACKTEST = {
    "initial_cash": 1_000_000,  # 初始资金 100万
    "commission_rate": 0.0003,  # 佣金万三
    "stamp_tax_rate": 0.001,   # 印花税千一（卖出）
    "slippage": 0.001,         # 滑点 0.1%
}

# 数据缓存目录
CACHE_DIR = "data/cache"

# Web管理后台配置
WEB = {
    "admin_username": "admin",
    "admin_password_hash": "pbkdf2:sha256:1000000$q6bAhiiCHjxUugJc$60375ee30781c2748483ef7815cbe869ecccc75f6b2cfb7a77f15ed878804e18",  # 默认密码: admin
    "secret_key": "a-stock-quant-change-me-in-production",
    "host": "0.0.0.0",
    "port": 5000,
    "debug": False,
}
