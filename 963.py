# --- START OF FILE 963.py (Final Chart Inside Text Version) ---

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go # 导入 graph_objects 以便更精细地控制图表
import finnhub
import yfinance as yf
import time
from datetime import datetime

# ------------------ 页面配置 (Page Configuration) ------------------
st.set_page_config(
    page_title="S&P 500 行业板块实时表现",
    page_icon="📈",
    layout="wide"
)

# ------------------ 应用标题和说明 (App Title & Description) ------------------
st.title("📈 S&P 500 行业板块实时表现")
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

@st.cache_data(ttl=300)
def get_today_volume_yf(etfs):
    if not etfs: return pd.DataFrame()
    ticker_list = list(etfs.values())
    try:
        data = yf.download(ticker_list, period="1d", progress=False)
        if data.empty: return pd.DataFrame()
        
        if len(ticker_list) == 1:
            volume_series = data['Volume']
        else:
            volume_series = data['Volume'].iloc[-1] if not data['Volume'].empty else data['Volume']
            
        volume_data = volume_series.reset_index()
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
    if not df_volume.empty:
        df_merged = pd.merge(df_performance, df_volume, on="代码", how="left")
    else:
        df_merged = df_performance
        df_merged['成交量'] = 0
    df_merged['成交量'] = df_merged['成交量'].fillna(0)

    def format_volume(v):
        if v is None or pd.isna(v) or v == 0: return "N/A"
        if v > 1_000_000: return f"{v / 1_000_000:.2f}M"
        if v > 1_000: return f"{v / 1_000:.2f}K"
        return str(int(v))
        
    df_merged['chart_text'] = df_merged.apply(
        lambda row: f" {row['涨跌幅 (%)']:.2f}% (成交量: {format_volume(row['成交量'])}) " if row['涨跌幅 (%)'] >= 0 else f" {row['涨跌幅 (%)']:.2f}% (成交量: {format_volume(row['成交量'])}) ",
        axis=1
    )

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

        # [核心修改] 使用更强大的 go.Figure() 来创建图表，以实现更精细的控制
        fig_bar = go.Figure()

        # 分别为上涨和下跌的板块添加条形
        for index, row in df_sorted_for_chart.iterrows():
            is_positive = row['涨跌幅 (%)'] >= 0
            color = 'green' if is_positive else 'red'
            
            fig_bar.add_trace(go.Bar(
                y=[row['板块']],
                x=[row['涨跌幅 (%)']],
                name=row['板块'],
                orientation='h',
                marker_color=color,
                text=row['chart_text'],
                textposition='inside', # 文本位置在条形内部
                textfont=dict(color='white'),
                insidetextanchor='end' if is_positive else 'start' # 上涨时文本靠右，下跌时文本靠左
            ))
        
        # [核心修改] 更新图表布局
        fig_bar.update_layout(
            title_text="各板块实时涨跌幅与成交量对比",
            showlegend=False,
            barmode='stack', # 确保条形图正确堆叠（虽然这里只有一个）
            yaxis={'categoryorder':'total ascending'},
            xaxis_title="涨跌幅 (%)",
            yaxis_title="板块",
            margin=dict(l=150, r=20, t=80, b=50) # 优化边距
        )
        st.plotly_chart(fig_bar, use_container_width=True)
