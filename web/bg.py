"""后台线程管理器 — 管理回测和实盘的后台任务"""

import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class BacktestTask:
    task_id: str
    stock: str = ""
    strategy_name: str = ""
    status: str = "pending"  # pending / running / done / error
    progress: int = 0
    result: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class LiveSession:
    trader: object = None
    thread: Optional[threading.Thread] = None
    running: bool = False


class BackgroundManager:
    def __init__(self):
        self._backtest_tasks: Dict[str, BacktestTask] = {}
        self._live_session: Optional[LiveSession] = None
        self._lock = threading.Lock()
        self._last_backtest_result: dict = {}

    # ─── 回测 ────────────────────────────────────

    def start_backtest(self, stock, start, end, strategy_name, params, initial_cash) -> str:
        task_id = uuid.uuid4().hex[:8]
        task = BacktestTask(task_id=task_id, stock=stock, strategy_name=strategy_name)
        self._backtest_tasks[task_id] = task

        def _run():
            task.status = "running"
            try:
                from data.fetcher import fetch_daily
                from backtest.engine import BacktestEngine, BacktestConfig
                from web.blueprints.strategy import STRATEGY_REGISTRY

                df = fetch_daily(stock, start, end)
                task.progress = 30
                if df.empty:
                    task.status = "error"
                    task.error = "数据为空，请检查股票代码和日期"
                    return

                reg = STRATEGY_REGISTRY[strategy_name]
                cfg = reg["config_class"](**params)
                strategy = reg["class"](cfg)
                task.progress = 40

                bt_cfg = BacktestConfig(initial_cash=initial_cash)
                engine = BacktestEngine(strategy, bt_cfg)
                result = engine.run(df)
                task.progress = 90

                task.result = self._serialize_result(result)
                task.status = "done"
                task.progress = 100
                self._last_backtest_result = task.result
            except Exception as e:
                task.status = "error"
                task.error = str(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return task_id

    def get_backtest_task(self, task_id) -> Optional[BacktestTask]:
        return self._backtest_tasks.get(task_id)

    @property
    def last_backtest_result(self) -> dict:
        return self._last_backtest_result

    def _serialize_result(self, result) -> dict:
        metrics = result["metrics"]
        trades = [
            {
                "date": str(t.date),
                "action": "买入" if "BUY" in str(t.action) else "卖出",
                "price": round(t.price, 2),
                "shares": t.shares,
                "reason": t.reason,
            }
            for t in result["trades"]
        ]
        results_df = result["results"]
        dates = [d.strftime("%Y-%m-%d") for d in results_df["date"]]
        portfolio = (results_df["portfolio"] / 1e6).round(4).tolist()
        benchmark = (results_df["benchmark"] / 1e6).round(4).tolist()
        volume = (results_df["volume"] / 1e6).round(2).tolist()

        return {
            "stock": result.get("stock", ""),
            "metrics": {k: round(v, 4) if isinstance(v, float) else v
                        for k, v in metrics.items()},
            "trades": trades,
            "equity": {
                "dates": dates,
                "portfolio": portfolio,
                "benchmark": benchmark,
                "volume": volume,
            },
        }

    # ─── 实盘 ────────────────────────────────────

    def start_live(self, trader) -> bool:
        with self._lock:
            if self._live_session and self._live_session.running:
                return False
            session = LiveSession(trader=trader)

            def _run():
                trader.start()

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            session.thread = t
            session.running = True
            self._live_session = session
            return True

    def stop_live(self) -> bool:
        with self._lock:
            if not self._live_session or not self._live_session.running:
                return False
            self._live_session.trader.stop()
            self._live_session.running = False
            return True

    @property
    def live_session(self) -> Optional[LiveSession]:
        return self._live_session

    @property
    def live_running(self) -> bool:
        return self._live_session is not None and self._live_session.running


bg_manager = BackgroundManager()
