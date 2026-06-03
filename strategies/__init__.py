"""
strategies/__init__.py
自動掃描 strategies/ 資料夾，載入所有繼承 BaseStrategy 的策略
新增策略只需放入資料夾，不需修改此檔案
"""
import importlib, inspect, pkgutil
from pathlib import Path
from strategies.base import BaseStrategy


def load_all_strategies() -> dict[str, BaseStrategy]:
    """
    掃描 strategies/ 下所有 .py 檔（排除 base.py, __init__.py）
    找出所有繼承 BaseStrategy 的 class，實例化後回傳
    格式：{ "策略名稱": <instance> }
    """
    strategies = {}
    pkg_dir = Path(__file__).parent

    for _, module_name, _ in pkgutil.iter_modules([str(pkg_dir)]):
        if module_name in ("base", "__init__"):
            continue
        try:
            mod = importlib.import_module(f"strategies.{module_name}")
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if (issubclass(obj, BaseStrategy)
                        and obj is not BaseStrategy
                        and not inspect.isabstract(obj)):
                    instance = obj()
                    strategies[instance.name] = instance
        except Exception as e:
            print(f"[策略載入失敗] {module_name}: {e}")

    return strategies
