# --- START OF FILE 963.py ---

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import finnhub
import time
from datetime import datetime, timedelta

# ------------------ 页面配置 (Page Configuration) ------------------
st.set_page_config(
    page_title="美股行业板块表现分析-Finnhub",
    page_icon="💰",
    layout="wide"
)

# ------------------ 应用标题和说明 (App Title & Description) ------------------
st.title("💰 美股行业板块表现与资金流向分析")
st.markdown("""
本应用结合了 **实时行情** 与 **历史资金流向**，为您提供全面的美股行业板块分析。
- **实时表现** 反映的是ETF相对于前一交易日收盘价的涨跌。
- **资金流向分析** 则根据选择的时间周期，估算并对比各板块的累计净资金流入/流出情况。
""")

# ------------------ 配置和常量 (Configuration & Constants) ------------------

# --- API密钥配置 ---
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

# ------------------ 核心数据获取函数 ------------------

@st.cache_data(ttl=60)
def get_realtime_performance_data(etfs):
    """获取所有选定ETF的实时表现数据。"""
    # (此函数与之前版本相同，保持不变)
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
        except Exception as e:
            st.warning(f"获取板块 '{sector}' ({ticker}) 实时数据时出错: {e}")
    if not performance_data: return pd.DataFrame()
    return pd.DataFrame(performance_data)

@st.cache_data(ttl=3600) # 历史数据缓存1小时
def get_all_sectors_historical_data(etfs, days_back=366):
    """
    一次性获取所有板块ETF过去一年的历史日线数据(OHLCV)。
    """
    all_data = []
    end_timestamp = int(datetime.now().timestamp())
    start_timestamp = int((datetime.now() - timedelta(days=days_back)).timestamp())

    for sector, ticker in etfs.items():
        try:
            res = client.stock_candles(ticker, 'D', start_timestamp, end_timestamp)
            if res['s'] == 'ok' and len(res['t']) > 0:
                df = pd.DataFrame(res)
                df['板块'] = sector
                df['代码'] = ticker
                all_data.append(df)
        except Exception as e:
            st.warning(f"获取板块 '{sector}' ({ticker}) 历史数据时出错: {e}")
    
    if not all_data: return pd.DataFrame()
    
    # 合并所有数据到一个DataFrame
    full_df = pd.concat(all_data, ignore_index=True)
    full_df['date'] = pd.to_datetime(full_df['t'], unit='s').dt.date
    return full_df

def calculate_money_flow(df):
    """
    计算每日资金流量的代理指标。
    算法: (典型价格 * 成交量) * (价格变动方向)
    """
    # 计算典型价格 (Typical Price)
    df['typical_price'] = (df['h'] + df['l'] + df['c']) / 3
    
    # 计算每日价格变动
    # 使用 groupby('代码')确保每个ETF的价格变动是独立计算的
    df['price_change'] = df.groupby('代码')['typical_price'].diff()
    
    # 确定资金流向 (+1 for inflow, -1 for outflow)
    df['flow_direction'] = np.sign(df['price_change'])
    
    # 计算每日资金流量 (Money Flow Volume)
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

with st.spinner('正在从 Finnhub 加载实时数据...'):
    df_performance = get_realtime_performance_data(etfs_to_fetch)

# ------------------ 页面展示 ------------------

if df_performance.empty:
    st.warning("未能获取任何板块的实时数据。请检查API Key权限或网络连接。")
else:
    df_sorted = df_performance.sort_values(by="涨跌幅 (%)", ascending=False).reset_index(drop=True)

    # --- Section 1: 实时表现概览 (与之前版本相同) ---
    st.subheader(f"📊 截至 {pd.Timestamp.now(tz='Asia/Shanghai').strftime('%Y-%m-%d %H:%M:%S')} 的实时表现")
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
    
    st.divider()

    # --- Section 2: 板块资金流向横向对比 (新功能) ---
    st.subheader("🌊 板块资金流向对比")

    # 时间周期选择器
    time_period = st.radio(
        "选择时间周期",
        options=[7, 30, 90, 180, 360],
        format_func=lambda x: f"{x} 天",
        horizontal=True,
    )

    with st.spinner('正在加载并计算所有板块的历史资金流...'):
        # 获取所有历史数据并计算资金流
        df_history_raw = get_all_sectors_historical_data(etfs_to_fetch)
        
        if not df_history_raw.empty:
            df_history_flow = calculate_money_flow(df_history_raw)

            # 根据选择的时间周期筛选数据
            start_date = pd.to_datetime(datetime.now().date() - timedelta(days=time_period))
            df_filtered = df_history_flow[pd.to_datetime(df_history_flow['date']) >= start_date]

            # 按板块分组并汇总资金流量
            flow_summary = df_filtered.groupby('板块')['money_flow_volume'].sum().sort_values()
            
            # 数据格式化，方便阅读 (转换为百万/十亿)
            def format_currency(value):
                if abs(value) >= 1_000_000_000:
                    return f"${value / 1_000_000_000:.2f}B" # 十亿
                elif abs(value) >= 1_000_000:
                    return f"${value / 1_000_000:.2f}M" # 百万
                else:
                    return f"${value / 1_000:.2f}K" # 千

            flow_summary_formatted = flow_summary.apply(format_currency)

            # 创建图表
            fig_flow = go.Figure()
            fig_flow.add_trace(go.Bar(
                y=flow_summary.index,
                x=flow_summary.values,
                text=flow_summary_formatted,
                orientation='h',
                marker_color=['green' if v > 0 else 'red' for v in flow_summary.values]
            ))

            fig_flow.update_layout(
                title=f"过去 {time_period} 天各板块累计净资金流量",
                xaxis_title="净资金流量 (美元)",
                yaxis_title="行业板块",
                showlegend=False,
                height=500
            )
            st.plotly_chart(fig_flow, use_container_width=True)

            st.info("""
            **如何解读图表?**
            - **绿色条**: 表示在该时间周期内，该板块的 **净资金流入** 为正。通常意味着市场对该板块看好，买方力量更强。
            - **红色条**: 表示在该时间周期内，该板块的 **净资金流出** 为负。通常意味着市场对该板块看淡，卖方力量更强。
            - **条的长度**: 代表了资金流动的绝对规模。
            - **计算方法**: 资金流量是基于每日的 **(典型价格 × 成交量)** 并根据价格涨跌方向 (+/-) 累计得出的估算值。
            """)
        else:
            st.warning("未能加载历史数据，无法计算资金流向。")
