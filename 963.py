# --- START OF FILE 963.py ---

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import finnhub
import time
from datetime import datetime, timedelta

# ------------------ 页面配置 (Page Configuration) ------------------
st.set_page_config(
    page_title="美股行业板块表现-Finnhub",
    page_icon="📈",
    layout="wide"
)

# ------------------ 应用标题和说明 (App Title & Description) ------------------
st.title("📈 美股行业板块表现分析 (Finnhub)")
st.markdown("""
本应用结合了 **实时行情** 与 **历史趋势**，为您提供全面的美股行业板块分析。
- **实时表现** 反映的是ETF相对于前一交易日收盘价的涨跌。
- **历史趋势** 展示了过去一年的每日价格变化和资金流量指标(MFI)。
""")

# ------------------ 配置和常量 (Configuration & Constants) ------------------

# --- API密钥配置 (API Key Configuration) ---
try:
    API_KEY = st.secrets["FINNHUB_API_KEY"]
except KeyError:
    st.error("错误：找不到 Finnhub API 密钥。")
    st.info("请在 Streamlit Community Cloud 的 'Settings > Secrets' 中添加密钥。")
    st.stop()

client = finnhub.Client(api_key=API_KEY)

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

# ------------------ 核心数据获取函数 (Core Data Functions) ------------------

@st.cache_data(ttl=60)
def get_realtime_performance_data(etfs):
    """获取所有选定ETF的实时表现数据。"""
    performance_data = []
    for sector, ticker in etfs.items():
        try:
            quote = client.quote(ticker)
            if quote.get('c') is not None and quote.get('c') != 0:
                performance_data.append({
                    "板块": sector,
                    "代码": ticker,
                    "当前价格": quote.get('c', 0),
                    "涨跌额": quote.get('d', 0),
                    "涨跌幅 (%)": quote.get('dp', 0),
                    "昨日收盘": quote.get('pc', 0)
                })
            else:
                 st.warning(f"板块 '{sector}' ({ticker}) 返回了无效数据，已跳过。")
        except Exception as e:
            if "You don't have access to this resource" in str(e):
                 st.error(f"API密钥权限不足，无法获取 '{sector}' ({ticker}) 的数据。")
            else:
                 st.warning(f"获取板块 '{sector}' ({ticker}) 数据时出错: {e}")
    
    if not performance_data:
        return pd.DataFrame()
        
    return pd.DataFrame(performance_data)

@st.cache_data(ttl=3600) # 历史数据变化不频繁，缓存1小时
def get_historical_and_mfi_data(ticker, days_back=365):
    """
    获取指定股票代码过去一年的日线历史数据和MFI指标。
    MFI (Money Flow Index) 是一个衡量资金流入流出强度的技术指标。
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())

        # 使用 technical_indicator 一次性获取K线和MFI指标，效率更高
        res = client.technical_indicator(
            symbol=ticker, 
            resolution='D', 
            _from=start_timestamp, 
            to=end_timestamp,
            indicator='mfi',
            indicator_fields={"timeperiod": 14} # 经典的14日MFI
        )
        
        if res and res.get('t'):
            df = pd.DataFrame(res)
            df['date'] = pd.to_datetime(df['t'], unit='s')
            df.rename(columns={'c': '收盘价', 'v': '成交量', 'mfi': 'MFI'}, inplace=True)
            return df[['date', '收盘价', '成交量', 'MFI']]
        else:
            st.warning(f"未能获取 {ticker} 的历史数据或MFI指标。")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"获取 {ticker} 历史数据时出错: {e}")
        return pd.DataFrame()

# ------------------ 侧边栏和用户输入 (Sidebar & User Inputs) ------------------

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

# ------------------ 数据获取与处理 (Data Fetching & Processing) ------------------

etfs_to_fetch = {sector: SECTOR_ETFS[sector] for sector in selected_sectors}
with st.spinner('正在从 Finnhub 加载实时数据...'):
    df_performance = get_realtime_performance_data(etfs_to_fetch)

# ------------------ 页面展示 (Page Display) ------------------

if df_performance.empty:
    st.warning("未能获取任何板块的实时数据。请检查API Key权限或网络连接。")
else:
    df_sorted = df_performance.sort_values(by="涨跌幅 (%)", ascending=False).reset_index(drop=True)

    # --- Section 1: 实时表现概览 ---
    st.subheader(f"📊 截至 {pd.Timestamp.now(tz='Asia/Shanghai').strftime('%Y-%m-%d %H:%M:%S')} 的实时表现")
    
    # 领涨领跌指标和对比图
    col1, col2 = st.columns([1, 2])
    with col1:
        top_performer = df_sorted.iloc[0]
        st.metric(label=f"🟢 领涨: {top_performer['板块']}", value=f"{top_performer['涨跌幅 (%)']:.2f}%", delta=f"{top_performer['涨跌额']:.2f}")
        bottom_performer = df_sorted.iloc[-1]
        st.metric(label=f"🔴 领跌: {bottom_performer['板块']}", value=f"{bottom_performer['涨跌幅 (%)']:.2f}%", delta=f"{bottom_performer['涨跌额']:.2f}")
    with col2:
        fig_bar = px.bar(
            df_sorted, x="涨跌幅 (%)", y="板块", orientation='h', text="涨跌幅 (%)",
            color=df_sorted["涨跌幅 (%)"] > 0, color_discrete_map={True: "green", False: "red"},
            title="各板块实时涨跌幅对比"
        )
        fig_bar.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig_bar.update_layout(showlegend=False, yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # 详细数据表
    st.subheader("📋 详细数据表")
    def style_change(val):
        color = 'red' if val < 0 else 'green' if val > 0 else 'black'
        return f'color: {color}'
    st.dataframe(
        df_sorted.style.format({
            "当前价格": "${:.2f}", "涨跌额": "{:+.2f}", "涨跌幅 (%)": "{:+.2f}%", "昨日收盘": "${:.2f}",
        }).apply(lambda x: x.map(style_change), subset=['涨跌额', '涨跌幅 (%)']),
        use_container_width=True
    )

    st.d
