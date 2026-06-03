"""
strategies/abc_institutional.py
M哥 A+B+C 策略插件 v4.0

整合五篇文章：
  文章1  A+B+C 核心架構
  文章2  光洋科：時間尺度、慣性改變、底部越墊越高
  文章3  中美晶：X型態、外資斜率加速、量縮小平台、多時間框架
  文章4  股東結構質變：散戶持股減 + 中實戶增 = 籌碼質變
  文章5  240日扣抵「價」：預測MA240走向的超前指標

新增核心：扣抵價分析
  deduction_price     = 240天前的收盤（今天被踢出去的舊價）
  above_deduction     = 今日收盤 > 扣抵價 → MA240 正在被動往上
  deduction_neg_slope = 即將踢掉的舊價格越來越低 → MA240 更容易上翹
  ma_rising_potential = 未來N天扣抵均值 < 今日收盤 → A條件即將成立的預警
"""

import numpy as np
import pandas as pd
from pathlib import Path
from strategies.base import BaseStrategy

INST_DIR = Path("data/institutional")
TDCC_DIR = Path("data/tdcc")


class ABCInstitutionalStrategy(BaseStrategy):
    name        = "A+B+C 籌碼趨勢（M哥完整版）"
    description = (
        "趨勢(MA240扣抵預測)+籌碼(外資斜率+股東質變)+賣壓消失(量縮ATR小平台)。"
        "含 X 型態預警、慣性改變、240日扣抵超前指標。"
    )
    version = "4.0"

    def get_params(self) -> dict:
        return {
            # ── A：趨勢均線 ──
            "ma_long": {
                "type": "int", "default": 240, "min": 120, "max": 300, "step": 20,
                "label": "A：長期均線週期",
            },
            "ma_mid": {
                "type": "int", "default": 60, "min": 20, "max": 120, "step": 10,
                "label": "A：中期均線週期",
            },
            "ma_short": {
                "type": "int", "default": 20, "min": 5, "max": 40, "step": 5,
                "label": "A：短期均線週期",
            },
            "high_period": {
                "type": "int", "default": 252, "min": 120, "max": 300, "step": 20,
                "label": "A：一年新高判斷週期（交易日）",
            },
            # ── 扣抵價（文章5）──
            "deduction_forecast": {
                "type": "int", "default": 20, "min": 5, "max": 60, "step": 5,
                "label": "扣抵：未來N天均線走向預測天數",
            },
            # ── X 型態（前驅訊號）──
            "x_hl_days": {
                "type": "int", "default": 20, "min": 10, "max": 40, "step": 5,
                "label": "X：底部越墊越高確認天數",
            },
            "x_vol_mult": {
                "type": "float", "default": 1.5, "min": 1.2, "max": 3.0, "step": 0.1,
                "label": "X：啟動大量倍數（相對均量）",
            },
            # ── B1：外資籌碼 ──
            "inst_days": {
                "type": "int", "default": 10, "min": 3, "max": 30, "step": 1,
                "label": "B1：外資累積淨買天數",
            },
            "inst_thresh": {
                "type": "int", "default": 3000, "min": 500, "max": 20000, "step": 500,
                "label": "B1：外資累積淨買張數門檻",
            },
            "slope_accel": {
                "type": "int", "default": 5, "min": 3, "max": 20, "step": 1,
                "label": "B1：外資斜率加速確認天數",
            },
            # ── B2：量縮小平台 ──
            "platform_days": {
                "type": "int", "default": 5, "min": 3, "max": 15, "step": 1,
                "label": "B2：量縮小平台最少天數",
            },
            "vol_shrink": {
                "type": "float", "default": 0.75, "min": 0.5, "max": 1.0, "step": 0.05,
                "label": "B2：量縮門檻（相對均量倍數）",
            },
            "atr_shrink": {
                "type": "float", "default": 0.8, "min": 0.5, "max": 1.0, "step": 0.05,
                "label": "B2：ATR收縮門檻（平台收窄）",
            },
            # ── 股東結構質變（文章4）──
            "use_tdcc": {
                "type": "select",
                "default": "自動（有資料就用）",
                "options": ["自動（有資料就用）", "強制使用", "停用"],
                "label": "股東結構質變過濾",
            },
            # ── 突破確認（新增）──
            "breakout_vol_mult": {
                "type": "float", "default": 1.5, "min": 1.0, "max": 4.0, "step": 0.25,
                "label": "突破：量能放大倍數（相對均量）",
            },
            "breakout_confirm_days": {
                "type": "int", "default": 3, "min": 1, "max": 5, "step": 1,
                "label": "突破：確認不回頭天數",
            },
            # ── 停損 ──
            "atr_stop": {
                "type": "float", "default": 2.0, "min": 1.0, "max": 3.5, "step": 0.5,
                "label": "停損：ATR倍數",
            },
        }

    def get_audit_config(self) -> dict:
        return {
            "tests":     ["A", "B", "C", "D", "E", "F"],
            "benchmark": "buy_hold",
            "monkey_n":  300,
            "wf_split":  0.5,
        }

    # ════════════════════════════════════
    # 主訊號產生
    # ════════════════════════════════════
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()

        ma_long       = int(params.get("ma_long", 240))
        ma_mid        = int(params.get("ma_mid", 60))
        ma_short      = int(params.get("ma_short", 20))
        high_period   = int(params.get("high_period", 252))
        ded_forecast  = int(params.get("deduction_forecast", 20))
        x_hl_days     = int(params.get("x_hl_days", 20))
        x_vol_mult    = float(params.get("x_vol_mult", 1.5))
        inst_days     = int(params.get("inst_days", 10))
        inst_thresh   = float(params.get("inst_thresh", 3000))
        slope_accel   = int(params.get("slope_accel", 5))
        platform_days = int(params.get("platform_days", 5))
        vol_shrink    = float(params.get("vol_shrink", 0.75))
        atr_shrink    = float(params.get("atr_shrink", 0.8))
        use_tdcc           = params.get("use_tdcc", "自動（有資料就用）")
        atr_stop           = float(params.get("atr_stop", 2.0))
        breakout_vol_mult  = float(params.get("breakout_vol_mult", 1.5))
        confirm_days       = int(params.get("breakout_confirm_days", 3))

        atr = df["ATR"] if "ATR" in df.columns else df["Close"] * 0.02

        # ════════════════════════════════
        # 均線體系
        # ════════════════════════════════
        df["MA_long"]  = df["Close"].rolling(ma_long).mean()
        df["MA_mid"]   = df["Close"].rolling(ma_mid).mean()
        df["MA_short"] = df["Close"].rolling(ma_short).mean()
        df["Vol_MA"]   = df["Volume"].rolling(20).mean()
        df["MA_long_slope"] = (
            df["MA_long"] - df["MA_long"].shift(20)
        ) / df["MA_long"].shift(20).replace(0, np.nan)

        # ════════════════════════════════
        # 240日扣抵價分析（文章5核心）
        # ════════════════════════════════
        # 扣抵價 = 今天會被踢出均線計算的舊收盤（ma_long天前）
        df["deduction_price"] = df["Close"].shift(ma_long)

        # ① 今日收盤 > 扣抵價 → 新價比舊價高 → MA往上
        df["above_deduction"] = df["Close"] > df["deduction_price"]

        # ② 未來扣抵走向：即將被踢掉的舊價格的斜率
        #    負值 = 扣抵值越來越低 = MA240更容易被動上翹（超前指標）
        ded_now       = df["Close"].shift(ma_long)
        ded_before    = df["Close"].shift(ma_long + 10)
        df["deduction_neg_slope"] = ded_now < ded_before  # 扣抵值在下降中

        # ③ 未來N天扣抵均值 < 今日收盤 → A條件即將成立的「預警」
        #    文章精髓：「未來240天前的舊價都比現在低，只要橫盤均線就會上翹」
        future_ded_avg = df["Close"].shift(ma_long).rolling(ded_forecast).mean()
        df["ma_rising_potential"] = future_ded_avg < df["Close"]

        # ④ 綜合扣抵訊號：三項中至少兩項成立
        df["deduction_ok"] = (
            df["above_deduction"].astype(int) +
            df["deduction_neg_slope"].astype(int) +
            df["ma_rising_potential"].astype(int)
        ) >= 2

        # ════════════════════════════════
        # A：趨勢條件
        # ════════════════════════════════
        df["High_N"] = df["Close"].rolling(high_period).max()

        # A完整版：MA240上翹 + 站上一年新高 + 多頭排列
        df["A_full"] = (
            (df["MA_long_slope"] > 0) &
            (df["Close"] >= df["High_N"].shift(1)) &
            (df["MA_short"] > df["MA_mid"]) &
            (df["MA_mid"]   > df["MA_long"])
        )
        # A寬鬆版：均線走平（用於XB型態與扣抵預警升級）
        df["A_flat"] = (
            (df["MA_long_slope"] > -0.002) &
            (df["MA_short"] > df["MA_long"])
        )
        # A預警版：扣抵條件好，A即將成立（文章5的核心應用）
        # 「只要股價橫盤，均線就會被動上翹」→ 現在買的基期更低
        df["A_prelude"] = (
            ~df["A_full"] &          # 還不是正式A
            df["deduction_ok"] &     # 但扣抵結構有利
            (df["MA_long_slope"] > -0.005)  # 均線沒有在急速下彎
        )

        # ════════════════════════════════
        # X 型態（文章2、3）
        # ════════════════════════════════
        df["recent_high_vol"] = df["Volume"].rolling(x_hl_days).max()
        df["low_now"]         = df["Low"].rolling(5).min()
        df["low_prev"]        = df["Low"].rolling(5).min().shift(x_hl_days)
        df["X_ok"] = (
            (df["MA_long_slope"] < 0.005) &
            (df["recent_high_vol"] >= df["Vol_MA"] * x_vol_mult) &
            (df["low_now"] > df["low_prev"]) &
            (~df["A_full"])
        )

        # ════════════════════════════════
        # B1：外資籌碼三層（文章1、2、3）
        # ════════════════════════════════
        df = self._attach_institutional(df)

        df["inst_roll"]  = df["fi_net"].rolling(inst_days).sum()
        df["inst_slope"] = df["inst_roll"] - df["inst_roll"].shift(slope_accel)

        df["B1a"] = df["inst_roll"] >= inst_thresh          # 累積達標
        df["B1b"] = df["inst_slope"] > 0                    # 斜率加速（文章3）
        price_down  = df["Close"] < df["Close"].shift(3)
        inst_buying = df["fi_net"] > 0
        df["B1c"]  = (price_down & inst_buying).rolling(10).sum() >= 3  # 慣性改變（文章2）

        df["B1_ok"] = df["B1a"] & (df["B1b"] | df["B1c"])

        # ════════════════════════════════
        # B2：量縮ATR收縮小平台（文章3）
        # ════════════════════════════════
        df["vol_roll"] = df["Volume"].rolling(platform_days).mean()
        df["atr_roll"] = atr.rolling(platform_days).mean()
        df["atr_long"] = atr.rolling(platform_days * 4).mean()

        df["B2_ok"] = (
            (df["vol_roll"] < df["Vol_MA"] * vol_shrink) &
            (df["atr_roll"] < df["atr_long"] * atr_shrink) &
            (df["Low"] >= df["Low"].rolling(platform_days).min().shift(1))
        )

        # ════════════════════════════════
        # 股東結構質變（文章4）
        # ════════════════════════════════
        df = self._attach_tdcc(df, use_tdcc)

        # ════════════════════════════════
        # 融資方向（文章3）
        # ════════════════════════════════
        if "margin_net" in df.columns:
            df["margin_ok"] = df["margin_net"] < 0
        else:
            df["margin_ok"] = True

        # ════════════════════════════════
        # 月線位階確認
        # ════════════════════════════════
        df["MA_monthly"]    = df["Close"].rolling(20).mean()
        df["above_monthly"] = df["Close"] > df["MA_monthly"]

        # ════════════════════════════════
        # 訊號分級（四級）
        # ════════════════════════════════
        df["signal"]        = "hold"
        df["stop_loss"]     = np.nan
        df["state"]         = "觀察中"
        df["signal_grade"]  = ""
        df["deduction_info"] = (
            "扣抵價=" + df["deduction_price"].round(1).astype(str) +
            " | 扣抵結構=" + df["deduction_ok"].map({True:"有利", False:"不利"})
        )

        # PRE-DEF：扣抵預警（文章5新增，最早的A條件預告）
        # 扣抵結構有利 + B1籌碼 → 「A即將成立，提前布局」
        pre_def_cond = df["A_prelude"] & df["B1_ok"]
        df.loc[pre_def_cond, "state"]        = "扣抵預警+籌碼（A即將成立）"
        df.loc[pre_def_cond, "signal_grade"] = "PRE-DEF"

        # PRE：X型態 + B1（空頭中的早期訊號）
        pre_cond = df["X_ok"] & df["B1_ok"] & ~pre_def_cond
        df.loc[pre_cond, "state"]        = "X型態+籌碼預警"
        df.loc[pre_cond, "signal_grade"] = "PRE"

        # SETUP：A+B1，等B2
        setup_cond = (
            (df["A_flat"] | df["A_full"]) &
            df["B1_ok"] & ~df["B2_ok"] & ~pre_def_cond
        )
        df.loc[setup_cond, "state"]        = "A+B1成立，等量縮平台"
        df.loc[setup_cond, "signal_grade"] = "SETUP"

        # BUY：完整進場
        #   A(趨勢) + B1(外資) + B2(賣壓) + 月線 + 融資 + 股東質變(加分)
        tdcc_bonus = df["quality_change"] | df["smart_money_in"]
        tdcc_ok    = tdcc_bonus if "tdcc_source" in df.columns \
                     else pd.Series(True, index=df.index)

        # ════════════════════════════════
        # 突破確認條件
        # ────────────────────────────────
        # 正確流程：
        #   1. 設置期：A（趨勢）+ B1（外資）+ 扣抵 + 月線
        #   2. 平台期：近期曾有量縮（比均量低，不需要全部B2子條件）
        #   3. 觸發日：量能突然放大突破
        #   4. 確認期：接下來 confirm_days 天收盤不跌破觸發日低點

        # Step 1：基礎趨勢+籌碼設置條件（不含B2）
        base_setup = (
            (df["A_flat"] | df["A_full"]) &
            df["B1_ok"] &
            df["deduction_ok"] &
            df["above_monthly"] &
            df["margin_ok"] &
            tdcc_ok
        )

        # Step 2：近期有量縮跡象（軟性平台條件）
        #   只要近 platform_days*2 天內 曾有一天量 < 均量*vol_shrink 即可
        vol_quiet = df["Volume"] < df["Vol_MA"] * vol_shrink
        df["had_quiet"] = (
            vol_quiet
            .rolling(platform_days * 2)
            .max()
            .fillna(0)
            .astype(bool)
        )

        # Step 3：今天量能放大（突破觸發）
        df["vol_surge"] = df["Volume"] > df["Vol_MA"] * breakout_vol_mult

        # Step 4：突破日 = 設置條件成立 + 近期曾量縮 + 今天放量
        df["breakout_day"] = base_setup & df["had_quiet"] & df["vol_surge"]

        # Step 5：確認不回頭
        #   記錄突破日低點
        df["breakout_low"] = df["Low"].where(df["breakout_day"]).ffill()

        # 最近 confirm_days 天內是否有突破日
        df["had_breakout"] = (
            df["breakout_day"]
            .rolling(confirm_days)
            .max()
            .fillna(0)
            .astype(bool)
        )
        # confirm_days 天內的最低收盤 >= 突破日低點
        df["min_close_since"] = df["Close"].rolling(confirm_days).min()
        df["confirmed"] = (
            df["had_breakout"] &
            (df["min_close_since"] >= df["breakout_low"] * 0.99)
        )

        # ════════════════════════════════
        # Step 6：進場時機分級
        # ────────────────────────────────
        # 原則：漲多少不是問題，問題是在突破「當下」進場
        # 用「現在離突破點多遠」判斷入場早晚
        #
        # 突破日到今天的漲幅（越小代表越早）
        df["pct_above_breakout"] = (
            (df["Close"] - df["breakout_low"]) /
            df["breakout_low"].replace(0, np.nan)
        )
        # FRESH：今天就是突破日（最早，當日收盤即發訊）
        df["is_breakout_day"] = df["breakout_day"]
        # CONFIRM：突破後 1~2 天，距突破低點 < 10%（還很近）
        df["is_confirm_early"] = (
            df["had_breakout"] &
            ~df["breakout_day"] &
            (df["pct_above_breakout"] < 0.10)
        )
        # BUY（標準確認）：突破後確認完成，距突破低點 < 20%
        df["is_confirmed"] = (
            df["confirmed"] &
            (df["pct_above_breakout"] < 0.20)
        )

        buy_cond = df["is_breakout_day"] | df["is_confirm_early"] | df["is_confirmed"]

        # 記錄進場等級
        df["entry_timing"] = "—"
        df.loc[df["is_confirmed"],    "entry_timing"] = "確認進場"
        df.loc[df["is_confirm_early"],"entry_timing"] = "早期確認"
        df.loc[df["is_breakout_day"], "entry_timing"] = "突破當日"
        df.loc[buy_cond, "signal"]    = "buy"
        df.loc[buy_cond, "stop_loss"] = df["breakout_low"]  # 停損設在突破日低點

        # 訊號等級：依入場時機分三級
        df.loc[df["is_confirmed"],    "signal_grade"] = "BUY"       # 已確認
        df.loc[df["is_confirm_early"],"signal_grade"] = "BUY★"      # 早期確認（更佳）
        df.loc[df["is_breakout_day"], "signal_grade"] = "BUY★★"     # 突破當日（最佳）

        is_full = buy_cond & df["A_full"]
        is_tdcc = buy_cond & tdcc_bonus
        is_ded  = buy_cond & df["deduction_ok"]

        # state 加入入場時機說明
        df.loc[buy_cond,             "state"] = "量大突破+站穩"
        df.loc[df["is_confirm_early"],"state"] = "早期確認（距突破<10%）"
        df.loc[df["is_breakout_day"], "state"] = "突破當日！立即關注"
        df.loc[is_full,              "state"] = df.loc[is_full, "state"] + "+A完整"
        df.loc[is_tdcc,              "state"] = df.loc[is_tdcc, "state"] + "+籌碼質變"

        # ── 出場 ────────────────────────
        slope_neg  = df["MA_long_slope"] < 0
        slope_down = (
            slope_neg &
            slope_neg.shift(1).fillna(False) &
            slope_neg.shift(2).fillna(False)
        )
        inst_flip = df["inst_roll"] < -inst_thresh

        sell_mask = slope_down | inst_flip
        no_buy    = df["signal"] != "buy"
        df.loc[sell_mask & no_buy, "signal"] = "sell"
        df.loc[slope_down & no_buy, "state"] = "均線轉下出場"
        df.loc[inst_flip  & no_buy, "state"] = "外資翻賣出場"

        # ── 進出場原因 ───────────────────
        df["entry_reason"] = np.where(
            buy_cond,
            (f"量大突破({breakout_vol_mult}x)+{confirm_days}天站穩+外資淨買+MA{ma_long}上翹"),
            ""
        )
        df["exit_reason"] = np.where(
            slope_down, "均線連3日轉下",
            np.where(inst_flip, "外資累積淨賣超", "")
        )
        return df

    # ════════════════════════════════════
    # 外資資料載入
    # ════════════════════════════════════
    def _attach_institutional(self, df: pd.DataFrame) -> pd.DataFrame:
        ticker = (df.attrs.get("ticker", "") or
                  (str(df["ticker"].iloc[0]) if "ticker" in df.columns else ""))
        if ticker:
            tc   = ticker.replace(".TW", "").replace(".TWO", "").strip()
            path = INST_DIR / f"{tc}_inst.csv"
            if path.exists():
                try:
                    inst = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()

                    # 找外資淨買欄位：優先 fi_net，其次用欄位位置（第3欄 = 買賣超）
                    if "fi_net" in inst.columns:
                        fi_net_col = inst["fi_net"]
                    else:
                        # 欄位名稱因 cp950 編碼問題保留中文，取第3個數值欄
                        num_cols = [c for c in inst.columns
                                    if c not in ("ticker","name","date")
                                    and inst[c].dtype in (float, int, "float64","int64")]
                        # 外資淨買 = 買進 - 賣出，通常是第3個欄位
                        fi_net_col = inst[num_cols[2]] if len(num_cols) >= 3 else inst[num_cols[0]]

                    fi_net = fi_net_col.reindex(df.index).ffill().fillna(0)
                    df["fi_net"]      = fi_net.values
                    df["inst_source"] = "real"

                    # 三大法人合計（已正確命名）
                    if "total_net" in inst.columns:
                        df["total_net"] = inst["total_net"].reindex(df.index).ffill().fillna(0).values

                    if "margin_buy" in inst.columns and "margin_sell" in inst.columns:
                        mg = (inst["margin_buy"] - inst["margin_sell"])\
                             .reindex(df.index).ffill().fillna(0)
                        df["margin_net"] = mg.values
                    return df
                except Exception:
                    pass

        vm = df["Volume"].rolling(20).mean()
        df["fi_net"]      = ((df["Volume"] / vm.replace(0, np.nan) - 1) * 1000).fillna(0)
        df["inst_source"] = "proxy（量能替代）"
        return df

    # ════════════════════════════════════
    # 集保股東結構資料（文章4）
    # ════════════════════════════════════
    def _attach_tdcc(self, df: pd.DataFrame, use_tdcc: str) -> pd.DataFrame:
        df["quality_change"] = False
        df["smart_money_in"] = False
        df["chips_clean"]    = False

        if use_tdcc == "停用":
            return df

        ticker = (df.attrs.get("ticker", "") or
                  (str(df["ticker"].iloc[0]) if "ticker" in df.columns else ""))
        if not ticker:
            return df

        tc   = ticker.replace(".TW", "").strip()
        path = TDCC_DIR / f"{tc}_tdcc.csv"
        if not path.exists():
            if use_tdcc == "強制使用":
                import warnings
                warnings.warn(f"集保資料不存在：{path}，請先執行 fetch_tdcc.py")
            return df

        try:
            raw   = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
            pivot = raw.pivot_table(
                index="date", columns="level",
                values=["holders", "shares", "pct"], aggfunc="first"
            )
            weekly = pd.DataFrame(index=pivot.index)

            if 16 in pivot["holders"].columns:
                weekly["total_holders"] = pivot["holders"][16]
            else:
                weekly["total_holders"] = pivot["holders"].sum(axis=1)

            r_cols  = [l for l in range(1, 5)  if l in pivot["pct"].columns]
            m_cols  = [l for l in range(9, 12) if l in pivot["pct"].columns]
            m_hcols = [l for l in range(9, 12) if l in pivot["holders"].columns]

            weekly["retail_pct"] = pivot["pct"][r_cols].sum(axis=1) if r_cols else 0
            weekly["mid_pct"]    = pivot["pct"][m_cols].sum(axis=1) if m_cols else 0
            weekly["mid_cnt"]    = pivot["holders"][m_hcols].sum(axis=1) if m_hcols else 0

            weekly["total_d"]   = weekly["total_holders"].diff()
            weekly["retail_d"]  = weekly["retail_pct"].diff()
            weekly["mid_d"]     = weekly["mid_pct"].diff()
            weekly["mid_cnt_d"] = weekly["mid_cnt"].diff()

            weekly["quality_change"] = (
                (weekly["total_d"]  > 0) &
                (weekly["retail_d"] < 0) &
                (weekly["mid_d"]    > 0)
            )
            mid_sync = (weekly["mid_d"] > 0) & (weekly["mid_cnt_d"] > 0)
            weekly["smart_money_in"] = mid_sync & mid_sync.shift(1).fillna(False)

            weekly["retail_ma4"] = weekly["retail_pct"].rolling(4).mean()
            weekly["chips_clean"] = weekly["retail_pct"] < weekly["retail_ma4"]

            for col in ["quality_change", "smart_money_in", "chips_clean"]:
                aligned    = weekly[col].reindex(df.index, method="ffill").fillna(False)
                df[col]    = aligned.values

            df["tdcc_source"] = "real"

        except Exception as e:
            import warnings
            warnings.warn(f"集保資料讀取失敗: {e}")

        return df
