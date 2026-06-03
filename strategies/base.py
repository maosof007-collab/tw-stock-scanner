"""
strategies/base.py
所有策略的共同介面
新增策略只需繼承 BaseStrategy，實作三個方法即可
"""
from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):

    # ── 子類別必須定義這些屬性 ──────────────────────
    name: str = "未命名策略"          # 顯示在 APP 側欄的名稱
    description: str = ""             # 簡短描述（顯示在 APP 說明區）
    version: str = "1.0"

    # ── 子類別必須實作這三個方法 ────────────────────
    @abstractmethod
    def get_params(self) -> dict:
        """
        回傳策略參數定義，格式：
        {
            "param_name": {
                "type": "int" | "float" | "select",
                "default": ...,
                "min": ..., "max": ..., "step": ...,   # 給 int/float
                "options": [...],                        # 給 select
                "label": "顯示名稱",
            }
        }
        Streamlit 會根據這個 dict 自動生成對應的 UI 元件
        """
        ...

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """
        核心邏輯：輸入 OHLCV + 指標 DataFrame，輸出訊號

        輸入 df 已包含：Open, High, Low, Close, Volume, ATR, Vol_MA, RS, RS_MA, SH, SL
        
        必須回傳 df，並加上以下欄位：
            "signal"   : "buy" | "sell" | "hold"
            "stop_loss": 停損價格（浮點數，無停損填 NaN）
            "state"    : 任意字串，說明當前趨勢狀態（顯示在訊號面板）
        
        選擇性加上：
            "entry_reason": 進場原因說明
            "exit_reason" : 出場原因說明
        """
        ...

    @abstractmethod
    def get_audit_config(self) -> dict:
        """
        稽核設定：告訴稽核引擎這個策略適合哪些測試

        回傳：
        {
            "tests": ["A","B","C","D","E","F"],  # 要跑哪些稽核
            "benchmark": "buy_hold",              # 比較基準
            "monkey_n": 300,                      # 猴子測試次數
            "wf_split": 0.5,                      # Walk-Forward 切割比例
        }
        """
        ...

    # ── 共用工具方法（子類別可直接使用）────────────
    def validate_df(self, df: pd.DataFrame) -> bool:
        """確認 df 有必要欄位"""
        required = ["Open", "High", "Low", "Close", "Volume"]
        return all(c in df.columns for c in required)

    def get_info(self) -> dict:
        """回傳策略基本資訊"""
        return {
            "name":        self.name,
            "description": self.description,
            "version":     self.version,
            "params":      self.get_params(),
            "audit":       self.get_audit_config(),
        }
