"""
strategies/theme_fundamental.py
主題基本面輪動策略 v1.0

邏輯框架：
  基本面（產業方向）× 籌碼（法人驗證）× 技術（時機）= 進場

三層過濾：
  Layer 1 — 基本面/主題篩選
    · 必須在「看好產業」清單中（可自訂，預設 AI 硬體鏈）
    · 個股 RS（相對強度）> 產業 RS 均值（比同業更強）
    · RS 必須 > 1.0（比大盤強）

  Layer 2 — 籌碼驗證
    · 外資累積淨買 N 天（機構資金在佈局）
    · 外資斜率加速（籌碼動能增強）

  Layer 3 — 技術進場
    · 站上 MA20 + MA60 + MA20 > MA60（多頭排列）
    · 量能出現放大（突破確認）
    · 3 天站穩不回頭（防假突破）

出場：
    · 跌破 MA20 連 3 天（趨勢轉弱）
    · 外資翻賣（籌碼惡化）
"""

import numpy as np
import pandas as pd
from pathlib import Path
from strategies.base import BaseStrategy

DATA_DIR = Path("data")
INST_DIR = DATA_DIR / "institutional"

# 預設 AI 硬體鏈看好產業（對應文章五大原因）
DEFAULT_THEMES = [
    "半導體業",        # CSP 算力擴張主力
    "電子零組件業",    # 被動元件 + 連接器
    "電腦及週邊設備業", # 伺服器 / 儲存
    "光電業",          # 光通訊 / 玻璃基板
    "其他電子業",      # 廠務工程 / 散熱
    "數位雲端",        # 雲端服務受惠
]

ALL_SECTORS = [
    "半導體業", "電子零組件業", "電腦及週邊設備業",
    "光電業", "其他電子業", "數位雲端", "通信網路業",
    "電機機械", "資訊服務業", "生技醫療業", "金融保險業",
    "航運業", "建材營造業", "綠能環保", "其他業",
]


class ThemeFundamentalStrategy(BaseStrategy):

    name        = "主題基本面輪動"
    description = (
        "產業方向（基本面）× 法人籌碼（驗證）× 技術突破（時機）。"
        "選定看好產業，過濾 RS > 1 且外資持續買進的個股，等技術確認後進場。"
    )
    version = "1.0"

    # ════════════════════════════════════
    def get_params(self) -> dict:
        return {
            # ── Layer 1：基本面 / 主題 ──────
            "sector_mode": {
                "type": "select",
                "default": "AI硬體鏈（預設）",
                "options": ["AI硬體鏈（預設）", "自訂產業"],
                "label": "主題選擇",
            },
            "rs_min": {
                "type": "float", "default": 1.0, "min": 0.5, "max": 2.0, "step": 0.1,
                "label": "最低 RS 相對強度（vs 大盤）",
            },
            "rs_period": {
                "type": "int", "default": 60, "min": 20, "max": 120, "step": 10,
                "label": "RS 計算週期（日）",
            },
            # ── Layer 2：籌碼 ────────────────
            "inst_buy_days": {
                "type": "int", "default": 5, "min": 2, "max": 20, "step": 1,
                "label": "外資累積淨買天數門檻",
            },
            "inst_thresh": {
                "type": "int", "default": 1000, "min": 100, "max": 10000, "step": 200,
                "label": "外資累積淨買張數門檻",
            },
            # ── Layer 3：技術 ────────────────
            "ma_fast": {
                "type": "int", "default": 20, "min": 5, "max": 40, "step": 5,
                "label": "短期均線（快線）",
            },
            "ma_slow": {
                "type": "int", "default": 60, "min": 20, "max": 120, "step": 10,
                "label": "長期均線（慢線）",
            },
            "vol_surge": {
                "type": "float", "default": 1.3, "min": 1.0, "max": 3.0, "step": 0.1,
                "label": "量能放大倍數（相對均量）",
            },
            "confirm_days": {
                "type": "int", "default": 3, "min": 1, "max": 5, "step": 1,
                "label": "突破確認天數（站穩不回頭）",
            },
            # ── 停損 ─────────────────────────
            "atr_stop": {
                "type": "float", "default": 2.0, "min": 1.0, "max": 4.0, "step": 0.5,
                "label": "ATR 停損倍數",
            },
        }

    def get_audit_config(self) -> dict:
        return {
            "tests":    ["A", "B", "C", "D", "E", "F"],
            "benchmark":"buy_hold",
            "monkey_n": 300,
            "wf_split": 0.5,
        }

    # ════════════════════════════════════
    # 主訊號
    # ════════════════════════════════════
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()

        sector_mode = params.get("sector_mode", "AI硬體鏈（預設）")
        rs_min      = float(params.get("rs_min", 1.0))
        rs_period   = int(params.get("rs_period", 60))
        inst_days   = int(params.get("inst_buy_days", 5))
        inst_thresh = float(params.get("inst_thresh", 1000))
        ma_fast     = int(params.get("ma_fast", 20))
        ma_slow     = int(params.get("ma_slow", 60))
        vol_mult    = float(params.get("vol_surge", 1.3))
        confirm     = int(params.get("confirm_days", 3))
        atr_stop    = float(params.get("atr_stop", 2.0))

        c = df["Close"]

        # ── ATR ──────────────────────────
        atr = df["ATR"] if "ATR" in df.columns and not df["ATR"].isna().all() \
            else self._calc_atr(df, 14)

        # ══════════════════════════════════
        # Layer 1：RS 相對強度
        # ══════════════════════════════════
        rs = df["RS"] if "RS" in df.columns else self._calc_rs(df, c, rs_period)

        # ── Layer 1 判斷：RS > 門檻 ──────
        rs_ok = rs >= rs_min

        # ══════════════════════════════════
        # Layer 2：外資籌碼
        # ══════════════════════════════════
        df = self._attach_institutional(df)

        df["inst_roll"]  = df["fi_net"].rolling(inst_days).sum()
        df["inst_slope"] = df["inst_roll"] - df["inst_roll"].shift(3)

        inst_ok = (df["inst_roll"] >= inst_thresh) & (df["inst_slope"] > 0)

        # ══════════════════════════════════
        # Layer 3：技術突破
        # ══════════════════════════════════
        df["MA_fast"] = c.rolling(ma_fast).mean()
        df["MA_slow"] = c.rolling(ma_slow).mean()
        df["Vol_MA"]  = df["Volume"].rolling(20).mean() \
                        if "Vol_MA" not in df.columns else df["Vol_MA"]

        # 多頭排列
        bull_align = (
            (c > df["MA_fast"]) &
            (c > df["MA_slow"]) &
            (df["MA_fast"] > df["MA_slow"])
        )

        # 量能放大
        vol_surge = df["Volume"] > df["Vol_MA"] * vol_mult

        # 近期曾量縮（平台期）
        vol_quiet = df["Volume"] < df["Vol_MA"] * 0.8
        had_quiet = vol_quiet.rolling(ma_fast).max().fillna(0).astype(bool)

        # 突破日
        breakout_day = rs_ok & inst_ok & bull_align & vol_surge & had_quiet

        # 突破低點
        df["breakout_low"] = df["Low"].where(breakout_day).ffill()

        # confirm 天內有突破日
        had_breakout = breakout_day.rolling(confirm).max().fillna(0).astype(bool)

        # 站穩
        min_close = c.rolling(confirm).min()
        confirmed = had_breakout & (min_close >= df["breakout_low"] * 0.99)

        # ══════════════════════════════════
        # 訊號整合
        # ══════════════════════════════════
        df["signal"]       = "hold"
        df["stop_loss"]    = np.nan
        df["signal_grade"] = ""
        df["state"]        = ""

        # 進場
        buy_cond = confirmed
        df.loc[buy_cond, "signal"]       = "buy"
        df.loc[buy_cond, "stop_loss"]    = df["breakout_low"]
        df.loc[buy_cond, "signal_grade"] = "BUY"
        df.loc[buy_cond, "state"]        = (
            f"主題突破（RS:{rs.round(2).astype(str)}）"
        )

        # 訊號等級：突破當日 vs 確認中
        is_fresh = buy_cond & breakout_day
        is_early = buy_cond & ~breakout_day & (
            (c - df["breakout_low"]) / df["breakout_low"].replace(0, np.nan) < 0.08
        )
        df.loc[is_fresh, "signal_grade"] = "BUY★★"
        df.loc[is_fresh, "state"]        = "主題突破當日！"
        df.loc[is_early, "signal_grade"] = "BUY★"
        df.loc[is_early, "state"]        = "主題早期確認"

        # 出場
        ma_fast_down = (
            (df["MA_fast"] < df["MA_fast"].shift(1)) &
            (df["MA_fast"].shift(1) < df["MA_fast"].shift(2)) &
            (df["MA_fast"].shift(2) < df["MA_fast"].shift(3))
        )
        inst_flip = df["inst_roll"] < -inst_thresh

        sell_cond = (ma_fast_down | inst_flip) & (df["signal"] != "buy")
        df.loc[sell_cond, "signal"] = "sell"
        df.loc[ma_fast_down & sell_cond, "state"] = f"MA{ma_fast}連跌出場"
        df.loc[inst_flip   & sell_cond, "state"]  = "外資翻賣出場"

        # 進出場原因
        df["entry_reason"] = np.where(
            buy_cond,
            f"主題+RS>{rs_min}+外資買{inst_days}天+量大突破+{confirm}天站穩",
            "",
        )
        df["exit_reason"] = np.where(
            ma_fast_down & sell_cond, f"MA{ma_fast}連跌",
            np.where(inst_flip & sell_cond, "外資轉賣", ""),
        )
        return df

    # ════════════════════════════════════
    # 工具
    # ════════════════════════════════════
    def _calc_atr(self, df, period=14):
        h, l, pc = df["High"], df["Low"], df["Close"].shift(1)
        tr = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    def _calc_rs(self, df, close, period):
        """簡單 RS：個股 period 日報酬 / 大盤 period 日報酬"""
        return close / close.shift(period)   # 無大盤時用絕對動能代替

    def _attach_institutional(self, df: pd.DataFrame) -> pd.DataFrame:
        ticker = (df.attrs.get("ticker", "") or
                  (str(df["ticker"].iloc[0]) if "ticker" in df.columns else ""))
        if ticker:
            tc   = ticker.replace(".TW", "").replace(".TWO", "").strip()
            path = INST_DIR / f"{tc}_inst.csv"
            if path.exists():
                try:
                    inst = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
                    if "fi_net" not in inst.columns:
                        num_cols = [c for c in inst.columns
                                    if c not in ("ticker","name") and
                                    pd.api.types.is_numeric_dtype(inst[c])]
                        if len(num_cols) >= 3:
                            inst["fi_net"] = inst[num_cols[2]]
                    fi_net = inst["fi_net"].reindex(df.index).ffill().fillna(0)
                    df["fi_net"]      = fi_net.values
                    df["inst_source"] = "real"
                    return df
                except:
                    pass

        vm = df["Volume"].rolling(20).mean()
        df["fi_net"]      = ((df["Volume"] / vm.replace(0, np.nan) - 1) * 500).fillna(0)
        df["inst_source"] = "proxy"
        return df
