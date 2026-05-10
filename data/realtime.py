"""东方财富实时行情模块

支持两种模式:
1. HTTP 模式 — 批量轮询，简单可靠，适合低频策略
2. WebSocket 模式 — 服务端推送，延迟更低，适合需要实时盯盘的场景

东方财富行情接口是公开的 Web 接口，无需注册和鉴权。
"""

import json
import struct
import threading
import time
from typing import Callable, Optional

import requests

# ─── 股票代码格式转换 ───────────────────────────────────────

def _to_em_code(symbol: str) -> str:
    """000001 -> 0.000001, 600519 -> 1.600519"""
    clean = symbol.replace("SH.", "").replace("SZ.", "").replace("sh", "").replace("sz", "")
    market = "1" if clean.startswith("6") else "0"
    return f"{market}.{clean}"

def _from_em_code(em_code: str) -> str:
    """0.000001 -> 000001, 1.600519 -> 600519"""
    return em_code.split(".")[-1]


# ─── HTTP 模式 ──────────────────────────────────────────────

EM_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"

# 字段ID映射 (东方财富f字段编号)
EM_FIELDS = {
    "f43": "price",         # 最新价
    "f44": "high",          # 最高
    "f45": "low",           # 最低
    "f46": "open",          # 开盘
    "f47": "volume",        # 成交量(手)
    "f48": "amount",        # 成交额
    "f57": "code",          # 代码
    "f58": "name",          # 名称
    "f60": "pre_close",     # 昨收
    "f170": "change_pct",   # 涨跌幅
    "f171": "amplitude",    # 振幅
    "f168": "turnover",     # 换手率
    "f164": "pe",           # 市盈率
}


def fetch_realtime(symbols: list[str]) -> dict[str, dict]:
    """
    批量获取实时行情 (HTTP)

    Parameters
    ----------
    symbols : list[str]
        股票代码列表，如 ["000001", "600519"]

    Returns
    -------
    dict  {symbol: {"price": 12.34, "open": ..., "high": ..., ...}}
    """
    results = {}
    for symbol in symbols:
        try:
            em_code = _to_em_code(symbol)
            params = {
                "secid": em_code,
                "fields": ",".join(EM_FIELDS.keys()),
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            }
            r = requests.get(EM_QUOTE_URL, params=params, timeout=5)
            r.raise_for_status()
            data = r.json().get("data", {})
            if data:
                item = {}
                for fid, fname in EM_FIELDS.items():
                    val = data.get(fid)
                    if fid == "f57":
                        item[fname] = str(val)
                    elif val is not None:
                        # 价格字段需要除以1000（东方财富返回的价是千分位）
                        if fname in ("price", "high", "low", "open", "pre_close"):
                            item[fname] = val / 1000
                        else:
                            item[fname] = val
                results[symbol] = item
        except Exception as e:
            print(f"  ⚠️ {symbol} 行情获取失败: {e}")
    return results


def fetch_price(symbol: str) -> float:
    """获取单只股票最新价 (HTTP)"""
    data = fetch_realtime([symbol])
    return data.get(symbol, {}).get("price", 0.0)


# ─── WebSocket 模式 ─────────────────────────────────────────

EM_WS_URL = "wss://push2.eastmoney.com/ws"

# 东方财富 WebSocket 二进制协议的回调类型
CB_QUOTE = 0   # 行情推送
CB_PING = 1    # 心跳


class EMWebSocket:
    """
    东方财富 WebSocket 实时行情

    协议说明:
    - 连接 wss://push2.eastmoney.com/ws
    - 发送 JSON 订阅消息注册关注的股票
    - 接收二进制帧: 前4字节为回调类型+压缩标记，后面是 JSON payload
    - 服务端约每3秒推送一次行情快照

    用法:
        ws = EMWebSocket(on_quote=callback)
        ws.start()
        ws.subscribe(["000001", "600519"])
        # ... 运行中 ...
        ws.stop()
    """

    def __init__(
        self,
        on_quote: Optional[Callable[[str, dict], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ):
        """
        Parameters
        ----------
        on_quote : callable
            行情回调 fn(symbol: str, quote: dict)
            quote 包含: price, open, high, low, pre_close, volume, amount, ...
        on_status : callable
            连接状态回调 fn(status: str)  如 "connected", "disconnected", "error:..."
        """
        self.on_quote = on_quote
        self.on_status = on_status
        self._ws = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._subscribed: set[str] = set()
        self._latest: dict[str, dict] = {}

    def start(self):
        """启动 WebSocket 连接（后台线程）"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止 WebSocket"""
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)

    def subscribe(self, symbols: list[str]):
        """订阅股票行情"""
        self._subscribed.update(symbols)
        if self._ws:
            self._send_subscribe(symbols)

    def unsubscribe(self, symbols: list[str]):
        """取消订阅"""
        self._subscribed -= set(symbols)
        if self._ws:
            self._send_unsubscribe(symbols)

    def get_price(self, symbol: str) -> float:
        """获取最新缓存价格"""
        return self._latest.get(symbol, {}).get("price", 0.0)

    def get_quote(self, symbol: str) -> dict:
        """获取最新缓存行情"""
        return self._latest.get(symbol, {})

    # ─── 内部实现 ───────────────────────────────────

    def _loop(self):
        """WebSocket 主循环（自动重连）"""
        import websocket

        while self._running:
            try:
                self._ws = websocket.WebSocketApp(
                    EM_WS_URL,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever(
                    ping_interval=10,
                    ping_timeout=5,
                )
            except Exception as e:
                self._notify_status(f"error: {e}")

            if self._running:
                self._notify_status("reconnecting")
                time.sleep(3)

    def _on_open(self, ws):
        self._notify_status("connected")
        if self._subscribed:
            self._send_subscribe(list(self._subscribed))

    def _on_message(self, ws, message):
        """处理二进制消息帧"""
        if isinstance(message, bytes) and len(message) >= 4:
            cb_type = message[0] & 0x0F
            is_gzip = (message[0] & 0xF0) >> 4

            payload = message[2:]  # 跳过2字节头
            if is_gzip:
                payload = self._decompress(payload)

            try:
                data = json.loads(payload)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return

            if cb_type == CB_QUOTE:
                self._handle_quote(data)
            elif cb_type == CB_PING:
                ws.send(message[:2] + b'\\x01', opcode=0x9)  # pong

    def _on_error(self, ws, error):
        self._notify_status(f"error: {error}")

    def _on_close(self, ws, close_status, close_msg):
        self._notify_status("disconnected")

    def _handle_quote(self, data: dict):
        """解析行情推送"""
        # 东方财富 WS 推送格式: {"rc": 0, "rt": 6, "data": {"secid": "0.000001", ...}}
        items = data.get("data", [])
        if isinstance(items, dict):
            items = [items]

        for item in items:
            secid = item.get("secid", "")
            symbol = _from_em_code(secid)
            quote = {}

            # 价格字段(千分位)
            for key, field in [("price", "price"), ("open", "open263"),
                               ("high", "high"), ("low", "low"),
                               ("pre_close", "preClose")]:
                val = item.get(field)
                if val is not None:
                    quote[key] = val / 1000 if val > 100 else val

            for key, field in [("volume", "volume"), ("amount", "amount")]:
                val = item.get(field)
                if val is not None:
                    quote[key] = val

            name = item.get("name", "")
            if name:
                quote["name"] = name

            if quote:
                self._latest[symbol] = quote
                if self.on_quote:
                    self.on_quote(symbol, quote)

    def _send_subscribe(self, symbols: list[str]):
        """发送订阅消息"""
        if not self._ws:
            return
        secids = [_to_em_code(s) for s in symbols]
        msg = {
            "op": "subscribe",
            "secids": ",".join(secids),
            "fields": "price,open,high,low,preClose,volume,amount",
        }
        try:
            self._ws.send(json.dumps(msg))
        except Exception:
            pass

    def _send_unsubscribe(self, symbols: list[str]):
        """发送取消订阅"""
        if not self._ws:
            return
        secids = [_to_em_code(s) for s in symbols]
        msg = {"op": "unsubscribe", "secids": ",".join(secids)}
        try:
            self._ws.send(json.dumps(msg))
        except Exception:
            pass

    def _notify_status(self, status: str):
        if self.on_status:
            self.on_status(status)

    @staticmethod
    def _decompress(data: bytes) -> bytes:
        import gzip
        return gzip.decompress(data)


# ─── 兼容接口：可直接替换 trader.py 中的 _fetch_prices ──────

def fetch_prices_em(symbols: list[str]) -> dict[str, float]:
    """
    批量获取实时价格，返回 {symbol: price}

    可直接替换 trader.py 中的 LiveTrader._fetch_prices()
    """
    data = fetch_realtime(symbols)
    return {s: v.get("price", 0.0) for s, v in data.items() if v.get("price", 0) > 0}


# ─── 独立测试 ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("东方财富 HTTP 行情测试")
    print("=" * 50)

    symbols = ["000001", "600519", "300750"]
    data = fetch_realtime(symbols)
    for s, q in data.items():
        name = q.get("name", "")
        price = q.get("price", 0)
        pct = q.get("change_pct", 0) / 100
        print(f"  {s} {name:10s}  现价: {price:>8.2f}  涨跌幅: {pct:+.2%}")

    print()
    print("=" * 50)
    print("东方财富 WebSocket 行情测试 (10秒)")
    print("=" * 50)

    def on_quote(symbol, quote):
        price = quote.get("price", 0)
        name = quote.get("name", "")
        print(f"  [推送] {symbol} {name}  现价: {price:.2f}")

    def on_status(status):
        print(f"  [状态] {status}")

    ws = EMWebSocket(on_quote=on_quote, on_status=on_status)
    ws.start()
    ws.subscribe(symbols)

    time.sleep(10)
    ws.stop()
    print("测试结束")
