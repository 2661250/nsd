# --- START OF FILE 963.py (Final Corrected Version) ---

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import finnhub
import yfinance as yf
import time
from datetime import datetime, timedelta

# ------------------ 页面配置 (Page Configuration) ------------------
st.set_page_config(
    page_title="美股行业板块表现分析",
    page_icon="💰",
    layout="wide"
)

# ------------------ 应用标题和说明 (App Title & Description) ------------------
st.title("💰 美股行业板块表现与资金流向分析")
st.markdown("""
本应用结合了 **实时行情 (来自 Finnhub)** 与 **历史资金流向 (来自 Yahoo Finance)**，为您提供全面的免费分析。
- **实时表现** 反映的是ETF相对于前一交易日收盘价的涨跌。
- **资金流向分析** 则根据选择的时间周期，估算并对比各板块的累计净资金流入/出情况。
""")

# ------------------ 配置和常量 (Configuration & Constants) ------------------

# --- API密钥配置 (仅用于Finnhub实时数据) ---
try:
    API_KEY = st.secrets["FINNHUB_API_KEY"]
    client = finnhub.Client(api_key=API_KEY)
except KeyError:
    client = None # 如果没有密钥，则将client设为None

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
    """(使用 Finnhub) 获取所有选定ETF的实时表现数据。"""
    if client is None:
        return pd.DataFrame()
        
    performance_data = []
    for sector, ticker in etfs.items():
        try:
            quote = client.quote(ticker)
            if quote.get('c') is not None and quote.get('c') != 0:
                performance_data.append({
                    "板块": sector, "代码": ticker, "当前价格": quote.get('c', 0),
                    "涨跌额": quote.get('d', 0), "涨跌幅 (%)": quote.get('dp', 0),
                    "昨日收盘": quote.get('pc', 0)
                })
        except Exception:
            pass
    return pd.DataFrame(performance_data)

@st.cache_data(ttl=3600)
def get_all_sectors_historical_data_yf(etfs, days_back=366):
    """(使用 yfinance) 获取历史数据，并处理单/多ticker返回不同结构的问题。"""
    if not etfs:
        return pd.DataFrame()
        
    ticker_list = list(etfs.values())
    sector_map = {v: k for k, v in etfs.items()}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    try:
        data = yf.download(ticker_list, start=start_date, end=end_date, progress=False)
        if data.empty:
            return pd.DataFrame()

        # [修正点] 核心修正逻辑，处理单/多ticker返回不同数据结构的问题
        if len(ticker_list) == 1:
            # 如果只下载一个ticker，手动添加“代码”列
            data['代码'] = ticker_list[0]
            df_ohlcv = data.reset_index()
        else:
            # 如果下载多个ticker，使用stack处理多层索引
            df_ohlcv = data.stack().reset_index()
        
        df_ohlcv.rename(columns={
            'level_1': '代码', 'Date': 'date', 'Open': 'o', 'High': 'h',
            'Low': 'l', 'Close': 'c', 'Adj Close': 'adj_c', 'Volume': 'v'
        }, inplace=True, errors='ignore') # errors='ignore' 增加稳健性
        
        df_ohlcv['板块'] = df_ohlcv['代码'].map(sector_map)
        df_ohlcv['date'] = pd.to_datetime(df_ohlcv['date']).dt.date
        return df_ohlcv
    except Exception as e:
        st.error(f"使用 yfinance 获取历史数据时出错: {e}")
        return pd.DataFrame()

def calculate_money_flow(df):
    """计算每日资金流量的代理指标。"""
    if df.empty or 'h' not in df.columns:
        return pd.DataFrame()
    # 确保数据按代码和日期排序，这对于 .diff() 的准确性至关重要
    df = df.sort_values(by=['代码', 'date'])
    df['typical_price'] = (df['h'] + df['l'] + df['c']) / 3
    df['price_change'] = df.groupby('代码')['typical_price'].diff()
    df['flow_direction'] = np.sign(df['price_change'])
    df['money_flow_volume'] = df['flow_direction'] * df['typical_price'] * df['v']
    return df

# ------------------ 侧边栏和用户输入 ------------------
with st.sidebar:
    st.header("⚙️ 参数设置")
    all_sectors = list(SECTOR_ETFS.keys())
    selected_sectors = st.multiselect(
        "选择要监控的板块", options=all_sectors, default=all_sectors
    )
    if st.checkbox("自动刷新实时数据（每分钟）"):
        time.sleep(60)
        st.rerun()
    if st.button("🔄 手动刷新"):
        st.cache_data.clear()
        st.rerun()

# ------------------ 数据获取与处理 ------------------
etfs_to_fetch = {sector: SECTOR_ETFS[sector] for sector in selected_sectors}
df_performance = get_realtime_performance_data(etfs_to_fetch)

# ------------------ 页面展示 ------------------

# --- Section 1: 实时表现概览 ---
# [修正点] 增加更强的保护，确保即使df_performance只有一个有效行也能正常显示
if df_performance.empty:
    st.info("未能加载实时数据。可能是未配置Finnhub API密钥。资金流向分析仍可使用。")
else:
    st.subheader(f"📊 截至 {pd.Timestamp.now(tz='Asia/Shanghai').strftime('%Y-%m-%d %H:%M:%S')} 的实时表现")
    col1, col2 = st.columns([1, 2])
    with col1:
        try:
            df_sorted_perf = df_performance.sort_values(by="涨跌幅 (%)", ascending=False).dropna()
            if not df_sorted_perf.empty:
                top_performer = df_sorted_perf.iloc[0]
                bottom_performer = df_sorted_perf.iloc[-1]
                st.metric(label=f"🟢 领涨: {top_performer['板块']}", value=f"{top_performer['涨跌幅 (%)']:.2f}%", delta=f"{top_performer['涨跌额']:.2f}")
                st.metric(label=f"🔴 领跌: {bottom_performer['板块']}", value=f"{bottom_performer['涨跌幅 (%)']:.2f}%", delta=f"{bottom_performer['涨跌额']:.2f}")
        except (IndexError, KeyError) as e:
            st.warning("实时数据不足，无法显示领涨/领跌板块。")

    with col2:
        fig_bar = px.bar(
            df_performance.sort_values(by="涨跌幅 (%)"),
            x="涨跌幅 (%)", y="板块", orientation='h', text="涨跌幅 (%)",
            color=df_performance["涨跌幅 (%)"] > 0, color_discrete_map={True: "green", False: "red"},
            title="各板块实时涨跌幅对比"
        )
        fig_bar.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig_bar.update_layout(showlegend=False, yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# --- Section 2: 板块资金流向横向对比 ---
st.subheader("🌊 板块资金流向对比 (数据源: Yahoo Finance)")

time_period = st.radio(
    "选择时间周期",
    options=[7, 30, 90, 180, 360],
    format_func=lambda x: f"{x} 天",
    horizontal=True,
)

with st.spinner('正在从 Yahoo Finance 加载历史数据并计算资金流...'):
    df_history_raw = get_all_sectors_historical_data_yf(etfs_to_fetch)
    
    if not df_history_raw.empty:
        df_history_flow = calculate_money_flow(df_history_raw)
        start_date = pd.to_datetime(datetime.now().date() - timedelta(days=time_period))
        df_filtered = df_history_flow[pd.to_datetime(df_history_flow['date']) >= start_date]
        
        if not df_filtered.empty and 'money_flow_volume' in df_filtered.columns:
            flow_summary = df_filtered.groupby('板块')['money_flow_volume'].sum().sort_values()
            
            def format_currency(value):
                if pd.isna(value): return "$0.00K"
                if abs(value) >= 1_000_000_000: return f"${value / 1_000_000_000:.2f}B"
                elif abs(value) >= 1_000_000: return f"${value / 1_000_000:.2f}M"
                else: return f"${value / 1_000:.2f}K"

            flow_summary_formatted = flow_summary.apply(format_currency)

            fig_flow = go.Figure(go.Bar(
                y=flow_summary.index, x=flow_summary.values,
                text=flow_summary_formatted, orientation='h',
                marker_color=['green' if v > 0 else 'red' for v in flow_summary.values]
            ))
            fig_flow.update_layout(
                title=f"过去 {time_period} 天各板块累计净资金流量",
                xaxis_title="净资金流量 (美元)", yaxis_title="行业板块",
                showlegend=False, height=500
            )
            st.plotly_chart(fig_flow, use_container_width=True)
            st.info("资金流量是基于每日的 (典型价格 × 成交量) 并根据价格涨跌方向 (+/-) 累计得出的估算值。")
        else:
            st.warning("在所选时间范围内无数据可供计算。")
    else:
        st.error("无法加载历史数据，资金流向分析功能不可用。")
