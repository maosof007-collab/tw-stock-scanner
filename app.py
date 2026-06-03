"""
app.py — 主程式
台股多策略回測 & 稽核系統
執行：streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os, glob, warnings
from pathlib import Path
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

import sys
sys.path.insert(0, str(Path(__file__).parent))
from strategies import load_all_strategies
from updater import update_all, DATA_DIR, LOG_FILE

# ════════════════════════════════════════
# 頁面設定
# ════════════════════════════════════════
st.set_page_config(
    page_title="台股多策略回測系統",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("""
<style>
[data-testid="stMetricValue"]{font-size:1.5rem;font-weight:500}
.stTabs [data-baseweb="tab"]{font-size:14px;padding:6px 18px}
</style>
""", unsafe_allow_html=True)

CAPITAL  = 1_000_000
POS_RISK = 0.02
ATR_PER, VOL_PER, RS_PER = 14, 20, 60
DARK="#0d1117"; GRID="#1e2d3d"; TEXT="#c9d1d9"
GREEN="#1D9E75"; RED="#E24B4A"; GOLD="#BA7517"; BLUE="#378ADD"
PAL=[GREEN,BLUE,GOLD,RED,"#9F77DD","#5DCAA5","#F0997B"]

# ════════════════════════════════════════
# 資料工具
# ════════════════════════════════════════
@st.cache_data(ttl=300)
def load_csv(path):
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    idx = pd.to_datetime(df.index)
    df.index = idx.tz_convert(None) if idx.tz is not None else idx
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Close"])

@st.cache_data(ttl=300)
def load_benchmark(data_dir):
    p = Path(data_dir) / "benchmark_TWII.csv"
    if not p.exists():
        return pd.Series(dtype=float, name="TWII")
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    idx = pd.to_datetime(df.index)
    df.index = idx.tz_convert(None) if idx.tz is not None else idx
    return df.iloc[:, 0]

def list_stocks(data_dir):
    return {Path(f).stem: str(f) for f in sorted(Path(data_dir).glob("*.TW.csv"))}

def get_update_status(data_dir):
    log_p = Path(data_dir) / "update_log.csv"
    if not log_p.exists():
        return {"last_run":"從未更新","ok":0,"err":0,"skip":0}
    df   = pd.read_csv(log_p)
    last = df.tail(20)
    return {
        "last_run": str(df["timestamp"].iloc[-1])[:16] if "timestamp" in df.columns else "未知",
        "ok":   (last["status"]=="OK").sum(),
        "err":  (last["status"]=="ERROR").sum(),
        "skip": (last["status"]=="SKIP").sum(),
    }

# ════════════════════════════════════════
# 指標計算
# ════════════════════════════════════════
def calc_common_indicators(df, bm_close):
    df = df.copy()
    h,l,c = df["High"],df["Low"],df["Close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h-l),(h-prev_c).abs(),(l-prev_c).abs()],axis=1).max(axis=1)
    df["ATR"]    = tr.rolling(ATR_PER).mean()
    df["Vol_MA"] = df["Volume"].rolling(VOL_PER).mean()
    bm = bm_close.reindex(df.index).ffill()
    df["RS"]     = (c/c.shift(RS_PER)) / (bm/bm.shift(RS_PER)).replace(0,np.nan)
    df["RS_MA"]  = df["RS"].rolling(10).mean()
    return df

# ════════════════════════════════════════
# 回測引擎（策略無關）
# ════════════════════════════════════════
def run_backtest(df_sig, ticker, atr_mult=1.5, fee=0.001, slip=0.001):
    c   = df_sig["Close"].values
    sig = df_sig["signal"].values
    sl_s= df_sig["stop_loss"].values if "stop_loss" in df_sig.columns else np.full(len(df_sig),np.nan)
    at  = df_sig["ATR"].values if "ATR" in df_sig.columns else np.full(len(df_sig),c*0.03)
    dt  = df_sig.index; n = len(df_sig)
    trades=[]; cash=CAPITAL; eq=[CAPITAL]
    pos=ep=sl=0; ed=None; itr=False

    for i in range(1,n):
        cv=c[i]; sv=sig[i]; av=at[i] if not np.isnan(at[i]) else cv*0.03
        if itr:
            if cv<=sl:
                xp=cv*(1-slip-fee)
                trades.append(dict(ticker=ticker,entry_date=ed,exit_date=dt[i],
                    entry_price=round(ep,2),exit_price=round(xp,2),shares=pos,
                    pnl=round((xp-ep)*pos,0),exit_reason="停損",
                    hold_days=(dt[i]-ed).days))
                cash+=xp*pos; pos=itr=0
            elif sv=="sell":
                xp=cv*(1-slip-fee)
                rsn=df_sig["exit_reason"].iloc[i] if "exit_reason" in df_sig.columns else "訊號出場"
                trades.append(dict(ticker=ticker,entry_date=ed,exit_date=dt[i],
                    entry_price=round(ep,2),exit_price=round(xp,2),shares=pos,
                    pnl=round((xp-ep)*pos,0),exit_reason=rsn,
                    hold_days=(dt[i]-ed).days))
                cash+=xp*pos; pos=itr=0
            else:
                risk=ep-sl
                if cv>=ep+risk and av>0: sl=max(sl,cv-av*atr_mult)
        elif sv=="buy" and not itr:
            sl_v=sl_s[i] if not np.isnan(sl_s[i]) else cv-av*atr_mult
            risk=cv-sl_v
            if risk>0 and sl_v>0:
                ml=cash*POS_RISK
                shares=int(ml/risk/1000)*1000; shares=max(shares,1000)
                enp=cv*(1+slip+fee)
                if shares*enp<=cash:
                    cash-=shares*enp; pos=shares; ep=enp; sl=sl_v; ed=dt[i]; itr=True
        eq.append(cash+pos*cv)

    if itr:
        xp=c[-1]*(1-fee-slip)
        trades.append(dict(ticker=ticker,entry_date=ed,exit_date=dt[-1],
            entry_price=round(ep,2),exit_price=round(xp,2),shares=pos,
            pnl=round((xp-ep)*pos,0),exit_reason="回測結束",
            hold_days=(dt[-1]-ed).days))

    return pd.DataFrame(trades), pd.Series(eq, index=[dt[0]]+list(dt[1:]))

def calc_stats(tdf, eq):
    empty=dict(ret=0,ann=0,dd=0,sh=0,wr=0,pf=0,trades=0,
               avg_win=0,avg_loss=0,avg_days=0,final=CAPITAL)
    if tdf is None or tdf.empty: return empty
    w=tdf[tdf["pnl"]>0]; l=tdf[tdf["pnl"]<=0]
    ret=(eq.iloc[-1]-CAPITAL)/CAPITAL*100
    days=max((eq.index[-1]-eq.index[0]).days,1)
    ann=((eq.iloc[-1]/CAPITAL)**(365/days)-1)*100
    dd=((eq-eq.cummax())/eq.cummax()*100).min()
    dr=eq.pct_change().dropna()
    sh=dr.mean()/dr.std()*np.sqrt(252) if dr.std()>0 else 0
    wr=len(w)/len(tdf)*100
    pf=(w["pnl"].sum()/abs(l["pnl"].sum())
        if len(l)>0 and l["pnl"].sum()!=0 else 99.0)
    return dict(ret=round(ret,2),ann=round(ann,2),dd=round(dd,2),
                sh=round(sh,2),wr=round(wr,1),pf=round(min(pf,99),2),
                trades=len(tdf),
                avg_win=round(w["pnl"].mean(),0) if len(w) else 0,
                avg_loss=round(l["pnl"].mean(),0) if len(l) else 0,
                avg_days=round(tdf["hold_days"].mean(),1),
                final=round(eq.iloc[-1],0))

def buy_hold_eq(df):
    sh=int(CAPITAL/df["Close"].iloc[0]/1000)*1000
    cash=CAPITAL-sh*df["Close"].iloc[0]
    return pd.Series(cash+sh*df["Close"].values, index=df.index)

# ════════════════════════════════════════
# 稽核引擎
# ════════════════════════════════════════
def run_audit(all_df_sig, all_eq, all_trades, bm_eq, strategy, params, fee, slip):
    results={}
    tickers=list(all_df_sig.keys())
    audit_cfg=strategy.get_audit_config()
    avg_s=np.mean([(eq.iloc[-1]-CAPITAL)/CAPITAL*100 for eq in all_eq.values()])
    avg_b=np.mean([(buy_hold_eq(df).iloc[-1]-CAPITAL)/CAPITAL*100
                   for df in all_df_sig.values()])

    # A: 策略 vs 買入持有
    if "A" in audit_cfg["tests"]:
        results["A"]={"title":"策略 vs 買入持有","pass":avg_s>avg_b,"warn":False,
            "detail":f"策略均報酬 {avg_s:.1f}%  買入持有 {avg_b:.1f}%",
            "verdict":"策略勝出" if avg_s>avg_b else "買入持有勝出",
            "strat_ret":avg_s,"bh_ret":avg_b}

    # B: 參數敏感度
    if "B" in audit_cfg["tests"]:
        param_defs=strategy.get_params()
        tunable={k:v for k,v in param_defs.items() if v["type"] in ("int","float")}
        heat_vals=[]
        ref_df=list(all_df_sig.values())[0].copy()
        for pname,pdef in list(tunable.items())[:2]:
            row=[]
            for delta in [-1,0,1]:
                p2=dict(params); p2[pname]=params[pname]+delta*pdef["step"]
                try:
                    sig_df=strategy.generate_signals(ref_df,p2)
                    _,eq=run_backtest(sig_df,"X",fee=fee,slip=slip)
                    row.append((eq.iloc[-1]-CAPITAL)/CAPITAL*100)
                except: row.append(0.0)
            heat_vals.append(row)
        heat=np.array(heat_vals) if heat_vals else np.array([[avg_s]])
        spread=float(heat.max()-heat.min())
        results["B"]={"title":"參數敏感度",
            "pass":spread<30,"warn":30<=spread<50,
            "detail":f"報酬分散度 {spread:.1f}%（最高{heat.max():.1f}% / 最低{heat.min():.1f}%）",
            "verdict":"穩健" if spread<30 else ("中度敏感" if spread<50 else "高度參數依賴"),
            "heat":heat}

    # C: 分段績效
    if "C" in audit_cfg["tests"]:
        idx=list(all_eq.values())[0].index; n3=len(idx)//3
        segs=[("牛市",idx[:n3]),("震盪",idx[n3:2*n3]),("熊市",idx[2*n3:])]
        seg_res={}
        for label,sidx in segs:
            ss,bs=[],[]
            for t in tickers:
                eq=all_eq[t]; bh=buy_hold_eq(all_df_sig[t])
                se=eq.reindex(sidx).dropna(); be=bh.reindex(sidx).dropna()
                if len(se)<2: continue
                ss.append((se.iloc[-1]-se.iloc[0])/se.iloc[0]*100)
                bs.append((be.iloc[-1]-be.iloc[0])/be.iloc[0]*100)
            seg_res[label]={"strat":np.mean(ss) if ss else 0,"bh":np.mean(bs) if bs else 0}
        bear_ok=seg_res["熊市"]["strat"]>seg_res["熊市"]["bh"]
        results["C"]={"title":"分段績效（牛/震盪/熊）",
            "pass":bear_ok,"warn":not bear_ok and seg_res["熊市"]["strat"]>-5,
            "detail":" | ".join([f"{k}: 策略{v['strat']:.1f}% BH{v['bh']:.1f}%"
                                  for k,v in seg_res.items()]),
            "verdict":"熊市有防禦效果" if bear_ok else "熊市防禦不足","seg_res":seg_res}

    # D: 猴子對照
    if "D" in audit_cfg["tests"]:
        np.random.seed(42)
        ref_c=list(all_df_sig.values())[0]["Close"].values
        monkey=[]
        for _ in range(audit_cfg.get("monkey_n",300)):
            cash=CAPITAL; p=ep=0; itr=False
            for i in range(1,len(ref_c)):
                if itr:
                    if ref_c[i]<=ep*0.97 or np.random.rand()<0.02:
                        cash+=ref_c[i]*p; p=itr=0
                elif np.random.rand()<0.05:
                    risk=ref_c[i]*0.03; sh=int(cash*POS_RISK/risk/1000)*1000
                    sh=max(sh,1000)
                    if sh*ref_c[i]<=cash:
                        cash-=sh*ref_c[i]; p=sh; ep=ref_c[i]; itr=True
            monkey.append((cash+(p*ref_c[-1] if itr else 0)-CAPITAL)/CAPITAL*100)
        monkey=np.array(monkey)
        pct_beat=float((monkey>avg_s).mean()*100)
        results["D"]={"title":"猴子亂買對照",
            "pass":pct_beat<40,"warn":40<=pct_beat<55,
            "detail":f"策略{avg_s:.1f}%  猴子中位數{np.median(monkey):.1f}%  {pct_beat:.0f}%猴子勝過策略",
            "verdict":f"策略勝過{100-pct_beat:.0f}%猴子" if pct_beat<50 else f"{pct_beat:.0f}%猴子打敗策略",
            "monkey":monkey,"strat_ret":avg_s}

    # E: 交易成本
    if "E" in audit_cfg["tests"]:
        cases=[("零成本",0.0,0.0),("低",0.001,0.001),("一般",0.002,0.002),("高",0.003,0.003)]
        ref_df=list(all_df_sig.values())[0]; fee_res=[]
        for label,fr,sl_r in cases:
            try:
                _,eq_f=run_backtest(ref_df,"X",fee=fr,slip=sl_r)
                fee_res.append((label,(eq_f.iloc[-1]-CAPITAL)/CAPITAL*100))
            except: fee_res.append((label,0.0))
        pos_cnt=sum(1 for _,r in fee_res if r>0)
        results["E"]={"title":"交易成本衝擊",
            "pass":pos_cnt>=3,"warn":pos_cnt==2,
            "detail":"  ".join([f"{l}:{r:.1f}%" for l,r in fee_res]),
            "verdict":f"{pos_cnt}/{len(cases)}情境正報酬","fee_res":fee_res}

    # F: Walk-Forward
    if "F" in audit_cfg["tests"]:
        split=audit_cfg.get("wf_split",0.5); wf_rows=[]
        for t,df in all_df_sig.items():
            n=len(df); half=int(n*split)
            try:
                df_in=strategy.generate_signals(df.iloc[:half].copy(),params)
                df_out=strategy.generate_signals(df.iloc[half:].copy(),params)
                _,ei=run_backtest(df_in,t,fee=fee,slip=slip)
                _,eo=run_backtest(df_out,t,fee=fee,slip=slip)
                ri=(ei.iloc[-1]-CAPITAL)/CAPITAL*100
                ro=(eo.iloc[-1]-CAPITAL)/CAPITAL*100
                wf_rows.append({"股票":t,"樣本內(%)":round(ri,1),
                                 "樣本外(%)":round(ro,1),"衰退":round(ri-ro,1)})
            except: wf_rows.append({"股票":t,"樣本內(%)":0,"樣本外(%)":0,"衰退":0})
        wf_df=pd.DataFrame(wf_rows)
        out_pos=(wf_df["樣本外(%)"]>0).mean(); avg_dec=wf_df["衰退"].mean()
        wf_ok=out_pos>0.5 and avg_dec<20
        results["F"]={"title":"過擬合 / Walk-Forward",
            "pass":wf_ok,"warn":out_pos>0.5 and avg_dec>=20,
            "detail":f"樣本外正報酬率{out_pos*100:.0f}%  平均衰退{avg_dec:.1f}%",
            "verdict":"樣本外穩健" if wf_ok else "疑似過擬合","wf_df":wf_df}

    score=sum(1 for v in results.values() if isinstance(v,dict) and v.get("pass"))
    results["_score"]=score; results["_total"]=len(results)-1
    return results

# ════════════════════════════════════════
# 圖表
# ════════════════════════════════════════
def sax(ax,title=""):
    ax.set_facecolor(DARK); ax.tick_params(colors=TEXT,labelsize=8)
    ax.grid(True,color=GRID,linewidth=0.4); ax.spines[:].set_color(GRID)
    if title: ax.set_title(title,color=TEXT,fontsize=10,pad=8)

def fmt_m(x,_): return f"{x/1e4:.0f}萬"

def plot_equity(all_eq,all_trades,bm_eq):
    fig,ax=plt.subplots(figsize=(11,3.5))
    fig.patch.set_facecolor(DARK); sax(ax,"權益曲線")
    if bm_eq is not None and not bm_eq.empty:
        bm_n=(bm_eq/bm_eq.iloc[0]*CAPITAL).reindex(list(all_eq.values())[0].index,method="ffill")
        ax.plot(bm_n.index,bm_n.values,color="#555",lw=1.2,ls="--",label="大盤",alpha=0.7)
    for (t,eq),col in zip(all_eq.items(),PAL):
        ax.plot(eq.index,eq.values,color=col,lw=1.6,label=t)
        tdf=all_trades.get(t,pd.DataFrame())
        if not tdf.empty:
            for _,r in tdf.iterrows():
                if r["entry_date"] in eq.index:
                    ax.scatter(r["entry_date"],eq.loc[r["entry_date"]],
                               marker="^",color=col,s=40,zorder=5,alpha=0.8)
                if r["exit_date"] in eq.index:
                    ax.scatter(r["exit_date"],eq.loc[r["exit_date"]],
                               marker=("v" if r["pnl"]<0 else "o"),
                               color=col,s=40,zorder=5,alpha=0.8)
    ax.axhline(CAPITAL,color="#444",ls=":",lw=1)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(fmt_m))
    ax.set_ylabel("資產",color=TEXT)
    ax.legend(loc="upper left",facecolor="#161b22",edgecolor=GRID,labelcolor=TEXT,fontsize=8,ncol=4)
    plt.tight_layout(); return fig

def plot_drawdown(all_eq):
    fig,ax=plt.subplots(figsize=(11,2.4))
    fig.patch.set_facecolor(DARK); sax(ax,"回撤曲線")
    for (t,eq),col in zip(all_eq.items(),PAL):
        dd=(eq-eq.cummax())/eq.cummax()*100
        ax.fill_between(dd.index,dd.values,0,alpha=0.15,color=col)
        ax.plot(dd.index,dd.values,color=col,lw=1,label=t)
    ax.set_ylabel("回撤 (%)",color=TEXT)
    ax.legend(loc="lower left",facecolor="#161b22",edgecolor=GRID,labelcolor=TEXT,fontsize=8,ncol=4)
    plt.tight_layout(); return fig

def plot_monthly(eq):
    m=eq.resample("ME").last().pct_change().dropna()*100
    fig,ax=plt.subplots(figsize=(11,2.4))
    fig.patch.set_facecolor(DARK); sax(ax,"月報酬率")
    pos=m[m>=0]; neg=m[m<0]
    ax.bar(pos.index,pos.values,width=20,color=GREEN,alpha=0.8,label=f"獲利月{len(pos)}")
    ax.bar(neg.index,neg.values,width=20,color=RED,alpha=0.8,label=f"虧損月{len(neg)}")
    ax.axhline(0,color="#555",lw=1)
    ax.set_ylabel("月報酬 (%)",color=TEXT)
    ax.legend(facecolor="#161b22",edgecolor=GRID,labelcolor=TEXT,fontsize=8)
    plt.tight_layout(); return fig

# ════════════════════════════════════════
# 側欄
# ════════════════════════════════════════
def render_sidebar(strategies_map, stocks_map):
    cfg={}
    st.sidebar.markdown("## 📈 多策略回測系統")
    st.sidebar.divider()

    upd=get_update_status(str(DATA_DIR))
    st.sidebar.markdown("**資料狀態**")
    st.sidebar.caption(f"最後更新：{upd['last_run']}")
    col1,col2=st.sidebar.columns(2)
    col1.metric("成功",upd["ok"]); col2.metric("失敗",upd["err"])

    if st.sidebar.button("🔄 立即更新資料",use_container_width=True):
        with st.spinner("更新中..."):
            load_csv.clear(); load_benchmark.clear()
            update_all(DATA_DIR)
        st.sidebar.success("更新完成！"); st.rerun()

    st.sidebar.divider()

    # 策略選擇（自動偵測）
    st.sidebar.markdown("**策略選擇**")
    if not strategies_map:
        st.sidebar.error("找不到任何策略！請確認 strategies/ 資料夾"); st.stop()
    strategy_name=st.sidebar.selectbox("選擇策略",list(strategies_map.keys()),
                                        label_visibility="collapsed")
    strategy=strategies_map[strategy_name]
    st.sidebar.caption(strategy.description)
    cfg["strategy"]=strategy; cfg["strategy_name"]=strategy_name

    # 動態參數（由策略 get_params() 自動生成 UI）
    st.sidebar.markdown("**策略參數**")
    param_defs=strategy.get_params(); user_params={}
    for pname,pdef in param_defs.items():
        label=pdef.get("label",pname); default=pdef.get("default")
        if pdef["type"]=="int":
            user_params[pname]=st.sidebar.slider(label,pdef["min"],pdef["max"],
                                                  default,pdef.get("step",1))
        elif pdef["type"]=="float":
            user_params[pname]=st.sidebar.slider(label,float(pdef["min"]),
                float(pdef["max"]),float(default),float(pdef.get("step",0.1)))
        elif pdef["type"]=="select":
            user_params[pname]=st.sidebar.selectbox(label,pdef["options"],
                index=pdef["options"].index(default) if default in pdef["options"] else 0)
    cfg["params"]=user_params

    st.sidebar.divider()

    # 股票選擇
    st.sidebar.markdown("**選股**")
    all_tickers=list(stocks_map.keys())
    if not all_tickers:
        st.sidebar.error("找不到 CSV！先執行 download_tw_stocks.py"); st.stop()
    cfg["selected"]=st.sidebar.multiselect("股票代碼",all_tickers,
        default=all_tickers[:5] if len(all_tickers)>=5 else all_tickers,
        label_visibility="collapsed")

    st.sidebar.markdown("**回測設定**")
    cfg["fee"] =st.sidebar.slider("手續費 (%)",0.0,0.5,0.1,0.05)/100
    cfg["slip"]=st.sidebar.slider("滑點 (%)",0.0,0.5,0.1,0.05)/100

    st.sidebar.divider()
    cfg["run"]=st.sidebar.button("🚀 執行回測 + 稽核",type="primary",use_container_width=True)
    return cfg

# ════════════════════════════════════════
# 各分頁 render
# ════════════════════════════════════════
def render_backtest_tab(all_eq,all_trades,bm_eq,all_stats,selected):
    st.pyplot(plot_equity(all_eq,all_trades,bm_eq))
    st.pyplot(plot_drawdown(all_eq))
    c1,c2=st.columns(2)
    with c1: st.pyplot(plot_monthly(list(all_eq.values())[0]))
    with c2:
        fig,ax=plt.subplots(figsize=(5.5,3))
        fig.patch.set_facecolor(DARK); sax(ax,"損益分布")
        for (t,tdf),col in zip(all_trades.items(),PAL):
            if not tdf.empty:
                ax.hist(tdf["pnl"]/1000,bins=16,alpha=0.55,label=t,color=col,edgecolor="none")
        ax.axvline(0,color="white",ls="--",lw=1)
        ax.set_xlabel("損益（千元）",color=TEXT)
        ax.legend(facecolor="#161b22",edgecolor=GRID,labelcolor=TEXT,fontsize=7)
        plt.tight_layout(); st.pyplot(fig); plt.close()

    st.markdown("#### 各股績效")
    rows=[]
    for t in selected:
        s=all_stats.get(t,{})
        if s: rows.append({"股票":t,"報酬(%)":s["ret"],"年化(%)":s["ann"],
            "回撤(%)":s["dd"],"夏普":s["sh"],"勝率(%)":s["wr"],
            "獲利因子":s["pf"],"交易次數":s["trades"],"平均持倉天":s["avg_days"]})
    if rows:
        df_perf=pd.DataFrame(rows).set_index("股票")
        st.dataframe(df_perf.style
            .format("{:.2f}",subset=["報酬(%)","年化(%)","回撤(%)","夏普","勝率(%)","獲利因子"])
            .background_gradient("RdYlGn",subset=["報酬(%)","年化(%)"])
            .background_gradient("RdYlGn_r",subset=["回撤(%)"]),
            use_container_width=True)

def render_audit_tab(audit, all_df_sig, all_eq):
    score=audit["_score"]; total=audit["_total"]
    banner={5:"success",4:"success",3:"warning"}.get(score,"error")
    msg={5:f"🏆 {score}/{total}：具備統計優勢",4:f"✅ {score}/{total}：表現良好",
         3:f"⚠️ {score}/{total}：需優化"}.get(score,f"❌ {score}/{total}：優勢不明顯")
    getattr(st,banner)(msg)

    keys=[k for k in audit if not k.startswith("_")]
    for key in keys:
        r=audit[key]
        icon="✅" if r["pass"] else ("⚠️" if r.get("warn") else "❌")
        with st.expander(f"{icon}  {key}. {r['title']} — {r['verdict']}",expanded=False):
            st.caption(r["detail"])

            if key=="C" and "seg_res" in r:
                seg=r["seg_res"]; labels=list(seg.keys())
                fig,ax=plt.subplots(figsize=(5,2.8))
                fig.patch.set_facecolor(DARK); sax(ax)
                x=np.arange(len(labels))
                ax.bar(x-0.2,[seg[l]["strat"] for l in labels],0.35,
                       label="策略",color=[GREEN,GOLD,RED],alpha=0.85)
                ax.bar(x+0.2,[seg[l]["bh"] for l in labels],0.35,
                       label="買入持有",color=[GREEN,GOLD,RED],alpha=0.4)
                ax.axhline(0,color="#888",lw=1)
                ax.set_xticks(x); ax.set_xticklabels(labels,color=TEXT)
                ax.set_ylabel("報酬率 (%)",color=TEXT)
                ax.legend(facecolor="#161b22",edgecolor=GRID,labelcolor=TEXT,fontsize=8)
                plt.tight_layout(); st.pyplot(fig); plt.close()

            elif key=="D" and "monkey" in r:
                monkey=r["monkey"]
                fig,ax=plt.subplots(figsize=(7,2.8))
                fig.patch.set_facecolor(DARK); sax(ax)
                ax.hist(monkey,bins=40,color="#ff6b6b",alpha=0.65,edgecolor="none",label="隨機分布")
                ax.axvline(r["strat_ret"],color=BLUE,lw=2,label=f"策略{r['strat_ret']:.1f}%")
                ax.axvline(np.median(monkey),color=GOLD,lw=1.5,ls="--",
                           label=f"猴子中位數{np.median(monkey):.1f}%")
                ax.set_xlabel("報酬率 (%)",color=TEXT)
                ax.legend(facecolor="#161b22",edgecolor=GRID,labelcolor=TEXT,fontsize=8)
                plt.tight_layout(); st.pyplot(fig); plt.close()

            elif key=="E" and "fee_res" in r:
                labels=[l for l,_ in r["fee_res"]]; vals=[v for _,v in r["fee_res"]]
                fig,ax=plt.subplots(figsize=(5,2.8))
                fig.patch.set_facecolor(DARK); sax(ax)
                colors=[GREEN if v>0 else RED for v in vals]
                bars=ax.bar(labels,vals,color=colors,alpha=0.85,edgecolor="none")
                ax.axhline(0,color="#888",lw=1)
                for bar,val in zip(bars,vals):
                    ax.text(bar.get_x()+bar.get_width()/2,val+(1 if val>0 else -3),
                            f"{val:.1f}%",ha="center",color=TEXT,fontsize=9)
                ax.set_ylabel("報酬率 (%)",color=TEXT)
                plt.tight_layout(); st.pyplot(fig); plt.close()

            elif key=="F" and "wf_df" in r:
                st.dataframe(r["wf_df"].set_index("股票").style
                    .background_gradient("RdYlGn",subset=["樣本內(%)","樣本外(%)"])
                    .background_gradient("RdYlGn_r",subset=["衰退"])
                    .format("{:.1f}"),use_container_width=True)

    st.markdown("#### 稽核總覽")
    audit_rows=[{"項目":f"{k}. {r['title']}",
                 "裁決":("✅ " if r["pass"] else "⚠️ " if r.get("warn") else "❌ ")+r["verdict"],
                 "數據":r["detail"][:70]}
                for k,r in audit.items()
                if not k.startswith("_") and isinstance(r,dict)]
    st.dataframe(pd.DataFrame(audit_rows).set_index("項目"),use_container_width=True)

def render_signals_tab(all_df_sig, strategy_name):
    st.markdown(f"#### 今日訊號掃描 — {strategy_name}")
    rows=[]
    for t,df in all_df_sig.items():
        if df.empty or "signal" not in df.columns: continue
        last=df.iloc[-1]
        rows.append({"股票":t,
            "收盤價":round(float(last["Close"]),1),
            "訊號":last["signal"],
            "趨勢狀態":last.get("state","—") if "state" in df.columns else "—",
            "RS強度":round(float(last["RS"]),2) if "RS" in df.columns and not np.isnan(last["RS"]) else "—",
            "ATR停損":round(float(last["stop_loss"]),1)
                     if "stop_loss" in df.columns and not np.isnan(last["stop_loss"]) else "—"})

    if rows:
        sig_df=pd.DataFrame(rows).set_index("股票")
        sig_df["_ord"]=sig_df["訊號"].map({"buy":0,"sell":1,"hold":2})
        sig_df=sig_df.sort_values("_ord").drop(columns=["_ord"])
        def color_sig(val):
            if val=="buy":  return "color:#1D9E75;font-weight:600"
            if val=="sell": return "color:#E24B4A;font-weight:600"
            return "color:#888"
        st.dataframe(sig_df.style.applymap(color_sig,subset=["訊號"]),use_container_width=True)
        buy_cnt=(sig_df["訊號"]=="buy").sum()
        st.success(f"🔔 今日共 {buy_cnt} 檔買入訊號") if buy_cnt>0 else st.info("今日無買入訊號")

# ════════════════════════════════════════
# 主程式
# ════════════════════════════════════════
def main():
    strategies_map=load_all_strategies()
    stocks_map=list_stocks(str(DATA_DIR))
    cfg=render_sidebar(strategies_map,stocks_map)
    strategy=cfg["strategy"]; strategy_name=cfg["strategy_name"]
    params=cfg["params"]; selected=cfg.get("selected",[]); fee=cfg["fee"]; slip=cfg["slip"]

    st.title("台股多策略回測 & 稽核系統")
    st.caption(f"當前策略：**{strategy_name}**  v{strategy.version}  |  "
               f"手續費 {fee*100:.2f}%  滑點 {slip*100:.2f}%")

    if not cfg["run"]:
        st.info("👈 左側選擇策略與股票後，點「執行回測 + 稽核」")
        st.markdown("---")
        st.markdown("### 新增策略只需 3 步驟")
        st.code("""# 1. 在 strategies/ 新建 my_strategy.py
from strategies.base import BaseStrategy

class MyStrategy(BaseStrategy):
    name        = "我的策略"       # 側欄自動顯示
    description = "策略說明"

    def get_params(self):          # 定義參數 → 自動生成滑桿
        return {
            "period": {"type":"int","default":20,
                       "min":5,"max":60,"step":1,"label":"週期"},
        }

    def generate_signals(self, df, params):
        df["signal"]    = "hold"   # buy / sell / hold
        df["stop_loss"] = float("nan")
        df["state"]     = "unknown"
        # ... 你的邏輯 ...
        return df

    def get_audit_config(self):
        return {"tests":["A","B","C","D","E","F"],
                "benchmark":"buy_hold","monkey_n":300,"wf_split":0.5}

# 2. 存檔
# 3. 重啟 streamlit run app.py → 側欄自動出現新策略 ✅""", language="python")

        st.markdown("### 已載入策略")
        for name,s in strategies_map.items():
            st.markdown(f"- **{name}** v{s.version} — {s.description}")
        return

    if not selected:
        st.warning("請至少選擇一檔股票"); return

    bm_eq=load_benchmark(str(DATA_DIR))
    progress=st.progress(0,text="處理中...")
    all_df_sig,all_eq,all_trades,all_stats={},{},{},{}

    for i,ticker in enumerate(selected):
        progress.progress((i+1)/len(selected),text=f"[{i+1}/{len(selected)}] {ticker}")
        try:
            df=load_csv(stocks_map[ticker])
            bm_s=bm_eq if not bm_eq.empty else pd.Series(1.0,index=df.index)
            df=calc_common_indicators(df,bm_s)
            df=strategy.generate_signals(df,params)
            tdf,eq=run_backtest(df,ticker,fee=fee,slip=slip)
            all_df_sig[ticker]=df; all_eq[ticker]=eq
            all_trades[ticker]=tdf; all_stats[ticker]=calc_stats(tdf,eq)
        except Exception as e:
            st.warning(f"{ticker}: {e}")

    progress.empty()
    if not all_eq: st.error("所有股票處理失敗"); return

    with st.spinner("執行稽核中..."):
        audit=run_audit(all_df_sig,all_eq,all_trades,bm_eq,strategy,params,fee,slip)

    # KPI 卡
    vals=[s for s in all_stats.values() if s["trades"]>0]
    avg=lambda k: np.mean([s[k] for s in vals]) if vals else 0
    score=audit["_score"]; total=audit["_total"]
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("平均報酬率",f"{avg('ret'):.1f}%")
    c2.metric("最大回撤",  f"{avg('dd'):.1f}%")
    c3.metric("夏普比率",  f"{avg('sh'):.2f}")
    c4.metric("勝率",      f"{avg('wr'):.1f}%")
    emoji="🟢" if score>=4 else ("🟡" if score>=3 else "🔴")
    c5.metric("稽核評分",  f"{emoji} {score}/{total}")
    st.divider()

    tab1,tab2,tab3,tab4=st.tabs(["📊 回測報告","🔍 稽核報告","🔔 今日訊號","📋 交易明細"])
    with tab1: render_backtest_tab(all_eq,all_trades,bm_eq,all_stats,selected)
    with tab2: render_audit_tab(audit,all_df_sig,all_eq)
    with tab3: render_signals_tab(all_df_sig,strategy_name)
    with tab4:
        _tlist=[d for d in all_trades.values() if d is not None and not d.empty]
        all_t=pd.concat(_tlist,ignore_index=True) if _tlist else pd.DataFrame()
        if not all_t.empty:
            all_t["entry_date"]=pd.to_datetime(all_t["entry_date"]).dt.date
            all_t["exit_date"] =pd.to_datetime(all_t["exit_date"]).dt.date
            st.dataframe(all_t.style
                .background_gradient("RdYlGn",subset=["pnl"])
                .format({"entry_price":"{:.1f}","exit_price":"{:.1f}","pnl":"{:,.0f}"}),
                use_container_width=True,height=480)
            st.download_button("⬇️ 下載 CSV",
                data=all_t.to_csv(index=False,encoding="utf-8-sig").encode("utf-8-sig"),
                file_name=f"{strategy_name}_trades.csv",mime="text/csv")

if __name__=="__main__":
    main()
