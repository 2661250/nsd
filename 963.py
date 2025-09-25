# --- START OF FILE 963.py (Final Simplified & Enhanced Version) ---

import streamlit as st
import pandas as pd
import plotly.express as px
import finnhub
import yfinance as yf
import time
from datetime import datetime

# ------------------ 页面配置 (Page Configuration) ------------------
st.set_page_config(
    page_title="美股行业板块实时表现",
    page_icon="📈",
    layout="wide"
)

# ------------------ 应用标题和说明 (App Title & Description) ------------------
st.title("📈 美股行业板块实时表现")
st.markdown("""
本应用结合 **实时行情 (来自 Finnhub)** 与 **实时成交量 (来自 Yahoo Finance)**，为您提供简洁高效的板块表现监控。
- **数据** 反映的是ETF相对于 **前一交易日收盘价** 的实时涨跌情况。
- **条形图** 同时展示了 **涨跌幅** 与 **当日累计成交量**。
""")

# ------------------ 配置和常量 (Configuration & Constants) ------------------

# --- API密钥配置 ---
try:
    API_KEY = st.secrets["FINNHUB_API_KEY"]
    client = finnhub.Client(api_key=API_KEY)
except KeyError:
    client = None

# 板块ETF映射
SECTOR_ETFS = {
    "科技 (Technology)": "XLK",
    "金融 (Financials)": "XLF",
    "医疗保健 (Healthcare)": "XLV",
    "非必需消费品 (Consumer Discretionary)": "XLY",
    "日常消费品 (Consumer Staples)": "XLP",
    "能源 (Energy)": "XLE",
    "公用事业 (Utilities)": "XLU",
    "房地产 (Real Estate)": "XLRE",
    "工业 (Industrials)": "XLI",
    "原材料 (Materials)": "XLB",
    "通信服务 (Communication)": "XLC"
}

# ------------------ 核心数据获取函数 ------------------

@st.cache_data(ttl=60)
def get_realtime_performance_data(etfs):
    """(使用 Finnhub) 获取实时行情数据。"""
    if client is None: return pd.DataFrame()
    performance_data = []
    for sector, ticker in etfs.items():
        try:
            quote = client.quote(ticker)
            if quote.get('c') is not None and quote.get('c') != 0:
                performance_data.append({
                    "板块": sector, "代码": ticker, "当前价格": quote.get('c', 0),
                    "涨跌额": quote.get('d', 0), "涨跌幅 (%)": quote.get('dp', 0),
                })
        except Exception: pass
    return pd.DataFrame(performance_data)

# [新功能] 获取当日成交量
@st.cache_data(ttl=300) # 成交量数据缓存5分钟
def get_today_volume_yf(etfs):
    """(使用 yfinance) 获取当日实时成交量。"""
    if not etfs: return pd.DataFrame()
    ticker_list = list(etfs.values())
    try:
        # 只获取当天的数据
        data = yf.download(ticker_list, period="1d", progress=False)
        if data.empty: return pd.DataFrame()
        
        # 提取成交量数据并整理
        volume_data = data['Volume'].iloc[-1].reset_index()
        volume_data.columns = ['代码', '成交量']
        return volume_data
    except Exception:
        return pd.DataFrame()

# ------------------ 侧边栏和用户输入 ------------------
with st.sidebar:
    st.header("⚙️ 参数设置")
    all_sectors = list(SECTOR_ETFS.keys())
    selected_sectors = st.multiselect("选择要监控的板块", options=all_sectors, default=all_sectors)
    if st.checkbox("自动刷新（每分钟）"): time.sleep(60); st.rerun()
    if st.button("🔄 手动刷新"): st.cache_data.clear(); st.rerun()

# ------------------ 数据获取与处理 ------------------
etfs_to_fetch = {sector: SECTOR_ETFS[sector] for sector in selected_sectors if sector in SECTOR_ETFS}

with st.spinner('正在加载实时数据...'):
    df_performance = get_realtime_performance_data(etfs_to_fetch)
    df_volume = get_today_volume_yf(etfs_to_fetch)

# ------------------ 页面展示 ------------------

if df_performance.empty:
    st.error("无法加载实时行情数据。请检查您的 Finnhub API 密钥是否已正确配置。")
else:
    # --- 合并数据 ---
    if not df_volume.empty:
        df_merged = pd.merge(df_performance, df_volume, on="代码", how="left")
    else:
        df_merged = df_performance
        df_merged['成交量'] = 0 # 如果成交量获取失败，则填充为0
    
    df_merged['成交量'] = df_merged['成交量'].fillna(0) # 确保没有NaN值

    # --- 格式化图表文本 ---
    def format_volume(v):
        if v is None or pd.isna(v) or v == 0: return "N/A"
        if v > 1_000_000: return f"{v / 1_000_000:.2f}M"
        if v > 1_000: return f"{v / 1_000:.2f}K"
        return str(int(v))
        
    df_merged['chart_text'] = df_merged.apply(
        lambda row: f"{row['涨跌幅 (%)']:.2f}% (成交量: {format_volume(row['成交量'])})",
        axis=1
    )

    # --- 实时表现概览 ---
    st.subheader(f"📊 截至 {pd.Timestamp.now(tz='Asia/Shanghai').strftime('%Y-%m-%d %H:%M:%S')} 的实时表现")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        try:
            df_sorted_perf = df_merged.sort_values(by="涨跌幅 (%)", ascending=False).dropna(subset=['涨跌幅 (%)'])
            if not df_sorted_perf.empty:
                top_performer = df_sorted_perf.iloc[0]
                bottom_performer = df_sorted_perf.iloc[-1]
                st.metric(label=f"🟢 领涨: {top_performer['板块']}", value=f"{top_performer['涨跌幅 (%)']:.2f}%", delta=f"{top_performer['涨跌额']:.2f}")
                st.metric(label=f"🔴 领跌: {bottom_performer['板块']}", value=f"{bottom_performer['涨跌幅 (%)']:.2f}%", delta=f"{bottom_performer['涨跌额']:.2f}")
        except (IndexError, KeyError): pass

    with col2:
        df_sorted_for_chart = df_merged.sort_values(by="涨跌幅 (%)")
        fig_bar = px.bar(
            df_sorted_for_chart,
            x="涨跌幅 (%)",
            y="板块",
            orientation='h',
            text="chart_text",  # [核心修改] 使用我们新创建的组合文本
            color=df_sorted_for_chart["涨跌幅 (%)"] > 0,
            color_discrete_map={True: "green", False: "red"},
            title="各板块实时涨跌幅与成交量对比"
        )
        # [核心修改] 更新文本模板以显示完整的自定义字符串
        fig_bar.update_traces(texttemplate='%{text}', textposition='outside')
        fig_bar.update_layout(showlegend=False, yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)
