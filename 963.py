# --- START OF FILE 963.py (Final Upgraded Version) ---

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
    page_icon="🚀",
    layout="wide"
)

# ------------------ 应用标题和说明 (App Title & Description) ------------------
st.title("🚀 美股行业板块表现与资金流向分析")
st.markdown("""
本应用结合了 **实时行情 (来自 Finnhub)** 与 **历史资金流向 (来自 Yahoo Finance)**，为您提供全面的免费分析。
- **实时表现** 反映的是ETF相对于前一交易日收盘价的涨跌。
- **资金流向分析** 则从 **强度、趋势、稳定性** 等多个维度，深度剖析各板块的资金动态。
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
    if client is None: return pd.DataFrame()
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
        except Exception: pass
    return pd.DataFrame(performance_data)

@st.cache_data(ttl=3600)
def get_all_sectors_historical_data_yf(etfs, days_back=366):
    if not etfs: return pd.DataFrame()
    all_clean_dfs = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    for sector, ticker in etfs.items():
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=False, back_adjust=False)
            if not df.empty:
                df.reset_index(inplace=True)
                df.rename(columns={'Date': 'date', 'Open': 'o', 'High': 'h', 'Low': 'l', 'Close': 'c', 'Volume': 'v'}, inplace=True)
                df['代码'] = ticker
                df['板块'] = sector
                required_cols = ['date', 'h', 'l', 'c', 'v', '代码', '板块']
                df_clean = df[required_cols]
                all_clean_dfs.append(df_clean)
        except Exception: pass
    if not all_clean_dfs: return pd.DataFrame()
    full_df = pd.concat(all_clean_dfs, ignore_index=True)
    full_df['date'] = pd.to_datetime(full_df['date']).dt.date
    return full_df

def calculate_money_flow(df):
    if df.empty or 'h' not in df.columns: return pd.DataFrame()
    df_copy = df.copy()
    df_copy = df_copy.sort_values(by=['代码', 'date'])
    df_copy['typical_price'] = (df_copy['h'] + df_copy['l'] + df_copy['c']) / 3
    df_copy['price_change'] = df_copy.groupby('代码')['typical_price'].diff()
    df_copy['flow_direction'] = np.sign(df_copy['price_change'])
    df_copy['money_flow_volume'] = df_copy['flow_direction'] * df_copy['typical_price'] * df_copy['v']
    return df_copy

# [新功能] 获取ETF市值
@st.cache_data(ttl=86400) # 市值一天更新一次即可
def get_etf_market_caps(etfs):
    caps = {}
    for sector, ticker_code in etfs.items():
        try:
            ticker_obj = yf.Ticker(ticker_code)
            # 市值 = 总资产 * 最新价格 (ETF的市值通常这样计算)
            market_cap = ticker_obj.info.get('totalAssets', 0)
            if market_cap > 0:
                caps[sector] = market_cap
        except Exception:
            pass # 如果获取失败则跳过
    return caps

# ------------------ 侧边栏和用户输入 ------------------
with st.sidebar:
    st.header("⚙️ 参数设置")
    all_sectors = list(SECTOR_ETFS.keys())
    selected_sectors = st.multiselect("选择要监控的板块", options=all_sectors, default=all_sectors)
    if st.checkbox("自动刷新实时数据（每分钟）"): time.sleep(60); st.rerun()
    if st.button("🔄 手动刷新"): st.cache_data.clear(); st.rerun()

# ------------------ 数据获取与处理 ------------------
etfs_to_fetch = {sector: SECTOR_ETFS[sector] for sector in selected_sectors if sector in SECTOR_ETFS}
df_performance = get_realtime_performance_data(etfs_to_fetch)

# ------------------ 页面展示 ------------------

# --- Section 1: 实时表现概览 ---
if not df_performance.empty:
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
        except (IndexError, KeyError): pass
    with col2:
        df_sorted_for_chart = df_performance.sort_values(by="涨跌幅 (%)")
        fig_bar = px.bar(df_sorted_for_chart, x="涨跌幅 (%)", y="板块", orientation='h', text="涨跌幅 (%)",
                         color=df_sorted_for_chart["涨跌幅 (%)"] > 0, color_discrete_map={True: "green", False: "red"},
                         title="各板块实时涨跌幅对比")
        fig_bar.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig_bar.update_layout(showlegend=False, yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)
    st.divider()

# --- Section 2: 板块资金流向横向对比 ---
st.subheader("🌊 板块资金流向深度分析 (数据源: Yahoo Finance)")
time_period = st.radio("选择时间周期", options=[7, 30, 90, 180, 360], format_func=lambda x: f"{x} 天", horizontal=True)

with st.spinner('正在加载历史数据、市值并计算所有指标...'):
    df_history_raw = get_all_sectors_historical_data_yf(etfs_to_fetch)
    market_caps = get_etf_market_caps(etfs_to_fetch)
    
    if not df_history_raw.empty:
        df_history_flow = calculate_money_flow(df_history_raw)
        start_date = pd.to_datetime(datetime.now().date() - timedelta(days=time_period))
        df_filtered = df_history_flow[pd.to_datetime(df_history_flow['date']) >= start_date].copy()
        
        if not df_filtered.empty and 'money_flow_volume' in df_filtered.columns:
            # --- [新功能] 1. 计算所有稳定性指标 ---
            summary_agg = {
                '累计净流量': ('money_flow_volume', 'sum'),
                '日均流量': ('money_flow_volume', 'mean'),
                '流量波动': ('money_flow_volume', 'std'),
                '净流入天数': ('money_flow_volume', lambda x: (x > 0).sum()),
                '净流出天数': ('money_flow_volume', lambda x: (x < 0).sum())
            }
            df_summary = df_filtered.groupby('板块').agg(**summary_agg).reset_index()

            # --- [新功能] 2. 计算资金流强度 ---
            df_summary['市值'] = df_summary['板块'].map(market_caps)
            # 防止除以0的错误
            df_summary['市值'].replace(0, np.nan, inplace=True)
            df_summary['资金流强度(%)'] = (df_summary['累计净流量'] / df_summary['市值']) * 100
            
            # --- 3. 创建选项卡 ---
            tab1, tab2, tab3, tab4 = st.tabs(["📊 数据总览", " L 累计流量对比", "💪 流量强度对比", "📈 趋势分析"])

            with tab1: # 数据总览 (稳定性表格)
                st.write(f"**过去 {time_period} 天资金流向稳定性概览**")
                # 格式化函数
                def format_currency_flow(value):
                    if pd.isna(value): return "N/A"
                    if abs(value) >= 1_000_000_000: return f"${value / 1_000_000_000:.2f}B"
                    elif abs(value) >= 1_000_000: return f"${value / 1_000_000:.2f}M"
                    else: return f"${value / 1_000:.2f}K"
                
                # 准备展示用的DataFrame
                df_display = df_summary.sort_values(by='资金流强度(%)', ascending=False).set_index('板块')
                st.dataframe(df_display.style.format({
                    '累计净流量': format_currency_flow,
                    '日均流量': format_currency_flow,
                    '流量波动': format_currency_flow,
                    '市值': "{:,.0f}",
                    '资金流强度(%)': "{:,.2f}%"
                }).background_gradient(cmap='RdYlGn', subset=['资金流强度(%)']), use_container_width=True)

            with tab2: # 累计流量对比 (条形图)
                df_sorted_total = df_summary.sort_values(by='累计净流量')
                fig_total_flow = go.Figure(go.Bar(
                    y=df_sorted_total['板块'], x=df_sorted_total['累计净流量'],
                    text=df_sorted_total['累计净流量'].apply(format_currency_flow),
                    orientation='h', marker_color=['green' if v > 0 else 'red' for v in df_sorted_total['累计净流量']]
                ))
                fig_total_flow.update_layout(title_text=f"过去 {time_period} 天累计净资金流量", showlegend=False)
                st.plotly_chart(fig_total_flow, use_container_width=True)

            with tab3: # 流量强度对比 (条形图)
                df_sorted_strength = df_summary.dropna(subset=['资金流强度(%)']).sort_values(by='资金流强度(%)')
                fig_strength_flow = go.Figure(go.Bar(
                    y=df_sorted_strength['板块'], x=df_sorted_strength['资金流强度(%)'],
                    text=df_sorted_strength['资金流强度(%)'].apply(lambda x: f"{x:.2f}%"),
                    orientation='h', marker_color=['green' if v > 0 else 'red' for v in df_sorted_strength['资金流强度(%)']]
                ))
                fig_strength_flow.update_layout(title_text=f"过去 {time_period} 天资金流强度 (占总市值%)", xaxis_ticksuffix='%', showlegend=False)
                st.plotly_chart(fig_strength_flow, use_container_width=True)

            with tab4: # 趋势分析 (折线图)
                df_filtered['cumulative_flow'] = df_filtered.groupby('板块')['money_flow_volume'].cumsum()
                fig_trend = px.line(df_filtered, x='date', y='cumulative_flow', color='板块', title="每日累计资金流趋势对比")
                fig_trend.update_layout(yaxis_title="累计资金流量 (美元)", xaxis_title="日期")
                st.plotly_chart(fig_trend, use_container_width=True)
            
            st.info("""
            **如何解读各项指标?**
            - **数据总览**: 综合展示了资金流的各项核心指标，**资金流强度** 是关键，它反映了资金变动相对于板块规模的显著性。
            - **累计流量对比**: 直观展示了各板块资金流入/出的 **绝对规模**。
            - **流量强度对比**: 揭示了哪些板块正在经历最 **剧烈** 的资金变动，即使其绝对规模不大。
            - **趋势分析**: 可视化了资金 **持续流入/出** 的过程，帮助判断趋势的稳定性。
            """)
        else:
            st.warning("在所选时间范围内无数据可供计算。")
    else:
        if selected_sectors:
            st.error("无法加载历史数据，资金流向分析功能不可用。")
