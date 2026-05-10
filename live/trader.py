"""实时交易引擎

将策略与券商对接，实现实时行情驱动的自动交易。
启动时自动加载历史数据，让策略有足够的上下文计算指标。
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from strategy.base import BaseStrategy, Signal
from .broker import BaseBroker, OrderSide, OrderStatus
from .paper_broker import PaperBroker


# A股交易时间 (周一至周五)
MORNING_OPEN = (9, 30)
MORNING_CLOSE = (11, 30)
AFTERNOON_OPEN = (13, 0)
AFTERNOON_CLOSE = (15, 0)


def is_trading_time() -> bool:
    """判断当前是否在交易时间"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = (now.hour, now.minute)
    return (MORNING_OPEN <= t <= MORNING_CLOSE) or (AFTERNOON_OPEN <= t <= AFTERNOON_CLOSE)


class LiveTrader:
    """实时交易引擎"""

    def __init__(
        self,
        strategy: BaseStrategy,
        broker: Optional[BaseBroker] = None,
        symbols: list = None,
        poll_interval: int = 60,
        max_position_pct: float = 0.3,
        stop_loss_pct: float = 0.07,
        log_file: str = "",
        history_days: int = 120,  # 加载多少天历史数据
    ):
        self.strategy = strategy
        self.broker = broker or PaperBroker()
        self.symbols = symbols or ["000001"]
        self.poll_interval = poll_interval
        self.max_position_pct = max_position_pct
        self.stop_loss_pct = stop_loss_pct
        self.history_days = history_days
        self.log_file = log_file or os.path.join(
            os.path.dirname(__file__), "trade_log.jsonl"
        )
        self._running = False
        self._log = []
        # 每只股票的历史数据 + 实时数据
        self._hist_data: dict[str, pd.DataFrame] = {}

    def start(self):
        """启动实时交易"""
        if not self.broker.connect():
            print("❌ 券商连接失败，无法启动")
            return

        # 加载历史数据（策略需要历史K线计算均线等指标）
        self._load_history()

        self._running = True
        print(f"\n🚀 实时交易已启动")
        print(f"   策略: {self.strategy.config.name}")
        print(f"   监控: {self.symbols}")
        print(f"   历史: {self.history_days}天")
        print(f"   轮询: {self.poll_interval}s")
        print(f"   单股上限: {self.max_position_pct:.0%}")
        print(f"   止损线: {self.stop_loss_pct:.0%}")
        print(f"   按 Ctrl+C 停止\n")

        try:
            while self._running:
                if is_trading_time():
                    self._tick()
                    time.sleep(self.poll_interval)
                else:
                    # 非交易时间
                    now = datetime.now()
                    t = (now.hour, now.minute)
                    if t < MORNING_OPEN:
                        wait = (MORNING_OPEN[0] - now.hour) * 60 + (MORNING_OPEN[1] - now.minute)
                    elif MORNING_CLOSE < t < AFTERNOON_OPEN:
                        wait = (AFTERNOON_OPEN[0] - now.hour) * 60 + (AFTERNOON_OPEN[1] - now.minute)
                    else:
                        wait = 5

                    status = "休市" if now.weekday() < 5 else "周末"
                    print(f"  ⏸ {status}... {wait}分钟后检查", flush=True)
                    time.sleep(min(wait * 60, 300))

        except KeyboardInterrupt:
            print("\n⏹ 收到停止信号")
        finally:
            self.stop()

    def stop(self):
        self._running = False
        self.broker.disconnect()
        print("🛑 实时交易已停止")

    def _load_history(self):
        """加载历史K线数据"""
        from data.fetcher import fetch_daily

        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=self.history_days)).strftime("%Y%m%d")

        for symbol in self.symbols:
            try:
                df = fetch_daily(symbol, start, end)
                self._hist_data[symbol] = df
                print(f"  ✓ {symbol} 历史数据: {len(df)}天")
            except Exception as e:
                print(f"  ⚠️ {symbol} 历史数据加载失败: {e}")

    def _tick(self):
        """一次行情轮询 + 策略驱动"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prices = self._fetch_prices()

        for symbol in self.symbols:
            try:
                price = prices.get(symbol, 0)
                if price <= 0:
                    continue

                print(f"  💰 {symbol} 现价: {price:.2f}", flush=True)

                # 止损检查
                if self._check_stop_loss(symbol, price):
                    self._log_trade(now_str, symbol, "STOP_LOSS", price, 0)
                    continue

                # 把实时价格追加到历史数据末尾
                hist = self._hist_data.get(symbol)
                if hist is not None and len(hist) > 0:
                    # 用今天的实时价更新最后一根K线（或新增）
                    today = pd.Timestamp.now().normalize()
                    if hist["date"].iloc[-1] == today:
                        # 今天已有K线，更新close
                        hist.iloc[-1, hist.columns.get_loc("close")] = price
                    else:
                        # 新增今日K线
                        new_row = pd.DataFrame([{
                            "date": today, "open": price, "high": price,
                            "low": price, "close": price, "volume": 0,
                        }])
                        hist = pd.concat([hist, new_row], ignore_index=True)
                        self._hist_data[symbol] = hist

                    # 把完整历史数据绑定到策略上
                    self.strategy.df = hist
                    idx = len(hist) - 1

                    # 获取账户 & 持仓
                    account = self.broker.get_account()
                    positions = self.broker.get_positions()
                    pos_qty = 0
                    for p in positions:
                        if p.symbol == symbol:
                            pos_qty = p.quantity

                    # 策略信号（有完整历史数据，均线等指标能正常计算）
                    bar = hist.iloc[idx]
                    signal = self.strategy.on_bar(idx, bar, pos_qty, account.cash)

                    # 执行交易
                    if signal == Signal.BUY and pos_qty == 0:
                        buy_amount = account.total_assets * self.max_position_pct
                        buy_qty = int(buy_amount / price / 100) * 100
                        if buy_qty >= 100:
                            self.broker.buy(symbol, price, buy_qty)
                            self._log_trade(now_str, symbol, "BUY", price, buy_qty)

                    elif signal == Signal.SELL and pos_qty > 0:
                        sell_qty = pos_qty
                        self.broker.sell(symbol, price, sell_qty)
                        self._log_trade(now_str, symbol, "SELL", price, sell_qty)

                    # 更新持仓现价
                    for p in positions:
                        if p.symbol == symbol:
                            p.current_price = price

            except Exception as e:
                print(f"  ⚠️ {symbol} 处理异常: {e}")
                self._log_trade(now_str, symbol, "ERROR", 0, 0, str(e))

    def _check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """止损检查"""
        positions = self.broker.get_positions()
        for p in positions:
            if p.symbol == symbol and p.cost_price > 0:
                loss_pct = (p.cost_price - current_price) / p.cost_price
                if loss_pct >= self.stop_loss_pct:
                    print(f"  🛑 {symbol} 触发止损! 亏损{loss_pct:.1%}, 成本{p.cost_price:.2f} → 现价{current_price:.2f}")
                    sell_qty = min(p.available, p.quantity)
                    if sell_qty > 0:
                        self.broker.sell(symbol, current_price, sell_qty)
                    return True
        return False

    def _log_trade(self, timestamp, symbol, action, price, quantity, msg=""):
        entry = {
            "time": timestamp, "symbol": symbol, "action": action,
            "price": price, "quantity": quantity, "msg": msg,
        }
        self._log.append(entry)
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def status(self) -> str:
        account = self.broker.get_account()
        positions = self.broker.get_positions()
        lines = [
            f"📊 实时交易状态",
            f"   策略: {self.strategy.config.name}",
            f"   总资产: ¥{account.total_assets:,.0f}",
            f"   现金:   ¥{account.cash:,.0f}",
            f"   市值:   ¥{account.market_value:,.0f}",
            f"   持仓:   {len(positions)}只",
        ]
        for p in positions:
            pnl_pct = (p.current_price - p.cost_price) / p.cost_price if p.cost_price > 0 else 0
            emoji = "🟢" if pnl_pct >= 0 else "🔴"
            lines.append(f"   {emoji} {p.symbol}: {p.quantity}股  成本{p.cost_price:.2f}  现价{p.current_price:.2f}  {pnl_pct:+.2%}")
        return "\n".join(lines)

    def _fetch_prices(self) -> dict:
        """批量获取实时价格（优先东方财富，降级新浪）"""
        from data.realtime import fetch_prices_em
        prices = fetch_prices_em(self.symbols)
        if prices:
            return prices

        # 降级到新浪
        print("  ⚠️ 东方财富行情失败，降级新浪")
        try:
            import requests
            codes = []
            for s in self.symbols:
                prefix = "sh" if s.startswith("6") else "sz"
                codes.append(f"{prefix}{s}")
            code_str = ",".join(codes)
            url = f"http://hq.sinajs.cn/list={code_str}"
            headers = {"Referer": "http://finance.sina.com.cn"}
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                for line in r.text.strip().split("\n"):
                    try:
                        code_part = line.split("=")[0].split("_")[-1]
                        data = line.split('="')[1].rstrip('";').split(',')
                        if len(data) > 3:
                            symbol = code_part[2:]
                            prices[symbol] = float(data[3])
                    except:
                        pass
        except Exception as e:
            print(f"  ⚠️ 新浪行情也失败: {e}")
        return prices
