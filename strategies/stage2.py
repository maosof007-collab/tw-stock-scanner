"""
strategies/stage2.py
詩魂影片策略：變盤三部曲 × 三重確認 × ATR移動停損
繼承 BaseStrategy，符合插件介面
"""
import numpy as np
import pandas as pd
from strategies.base import BaseStrategy


class Stage2Strategy(BaseStrategy):
    name        = "Stage 2 突破（變盤三部曲）"
    description = "Stan Weinstein 四階段理論。突破末跌高→打底→破平台，三重確認（趨勢+RS+量能）進場，ATR移動停損。"
    version     = "1.1"

    def get_params(self) -> dict:
        return {
            "swing_n": {
                "type": "int", "default": 10, "min": 5, "max": 20, "step": 1,
                "label": "SWING_N（高低點級別）",
            },
            "atr_mult": {
                "type": "float", "default": 1.5, "min": 0.8, "max": 3.0, "step": 0.1,
                "label": "ATR 停損倍數",
            },
            "vol_confirm": {
                "type": "float", "default": 1.1, "min": 1.0, "max": 2.0, "step": 0.1,
                "label": "量能確認倍數（相對均量）",
            },
        }

    def get_audit_config(self) -> dict:
        return {
            "tests":     ["A", "B", "C", "D", "E", "F"],
            "benchmark": "buy_hold",
            "monkey_n":  300,
            "wf_split":  0.5,
        }

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df       = df.copy()
        swing_n  = int(params.get("swing_n", 10))
        atr_mult = float(params.get("atr_mult", 1.5))
        vol_conf = float(params.get("vol_confirm", 1.1))

        # 局部高低點（若尚未加入）
        if "SH" not in df.columns:
            df["SH"] = self._find_sh(df["Close"], swing_n)
        if "SL" not in df.columns:
            df["SL"] = self._find_sl(df["Close"], swing_n)

        c   = df["Close"].values
        h   = df["High"].values
        l   = df["Low"].values
        vol = df["Volume"].values
        vma = df["Vol_MA"].values if "Vol_MA" in df.columns else np.full(len(df), np.nan)
        rs  = df["RS"].values     if "RS"     in df.columns else np.full(len(df), np.nan)
        rsm = df["RS_MA"].values  if "RS_MA"  in df.columns else np.full(len(df), np.nan)
        atr = df["ATR"].values    if "ATR"    in df.columns else np.full(len(df), np.nan)
        n   = len(df)

        state  = ["downtrend"] * n
        signal = ["hold"] * n
        sl_arr = [np.nan] * n
        reason = [""] * n

        lh = blo = plh = np.nan
        for i in range(swing_n, n):
            if not np.isnan(df["SH"].iloc[i]):
                lh = df["SH"].iloc[i]; break

        for i in range(1, n):
            ps = state[i-1]

            if ps == "downtrend":
                if not np.isnan(lh) and c[i] > lh:
                    state[i] = "stage1"; blo = l[i]; plh = h[i]
                else:
                    state[i] = "downtrend"
                    if not np.isnan(df["SH"].iloc[i]): lh = df["SH"].iloc[i]

            elif ps == "stage1":
                if c[i] < blo:
                    state[i] = "downtrend"
                    if not np.isnan(df["SH"].iloc[i]): lh = df["SH"].iloc[i]
                else:
                    state[i] = "basing"; blo = min(blo, l[i]); plh = max(plh, h[i])

            elif ps == "basing":
                if c[i] < blo:
                    state[i] = "downtrend"
                    if not np.isnan(df["SH"].iloc[i]): lh = df["SH"].iloc[i]
                elif c[i] > plh:
                    rs_ok  = (not np.isnan(rs[i]) and not np.isnan(rsm[i])
                              and rs[i] > rsm[i])
                    vol_ok = (not np.isnan(vma[i]) and vma[i] > 0
                              and vol[i] > vma[i] * vol_conf)
                    if rs_ok and vol_ok:
                        state[i]   = "stage2"
                        sl_v       = c[i] - (atr[i] if not np.isnan(atr[i]) else c[i]*0.03) * atr_mult
                        signal[i]  = "buy"
                        sl_arr[i]  = sl_v
                        reason[i]  = "三部曲完成+三重確認"
                    else:
                        state[i] = "stage2_weak"
                        reason[i] = "破平台但確認不足"
                    blo = l[i]; plh = h[i]
                else:
                    state[i] = "basing"; blo = min(blo, l[i]); plh = max(plh, h[i])

            elif ps in ("stage2", "stage2_weak"):
                rsl = df["SL"].iloc[max(0, i-swing_n*2):i].dropna()
                if len(rsl) > 0 and c[i] < rsl.iloc[-1]:
                    state[i]  = "stage3"
                    signal[i] = "sell"
                    reason[i] = "翻多為空（HL被破）"
                    if not np.isnan(df["SH"].iloc[i]): lh = df["SH"].iloc[i]
                    continue
                if c[i] > plh: plh = h[i]
                state[i] = "stage2"

            elif ps == "stage3":
                state[i] = "downtrend"
                if not np.isnan(df["SH"].iloc[i]): lh = df["SH"].iloc[i]
            else:
                state[i] = ps

        df["state"]        = state
        df["signal"]       = signal
        df["stop_loss"]    = sl_arr
        df["entry_reason"] = reason
        df["exit_reason"]  = reason
        return df

    @staticmethod
    def _find_sh(s, n=10):
        r, a = pd.Series(np.nan, index=s.index), s.values
        for i in range(n, len(a)-n):
            if a[i] == a[i-n:i+n+1].max(): r.iloc[i] = a[i]
        return r

    @staticmethod
    def _find_sl(s, n=10):
        r, a = pd.Series(np.nan, index=s.index), s.values
        for i in range(n, len(a)-n):
            if a[i] == a[i-n:i+n+1].min(): r.iloc[i] = a[i]
        return r
