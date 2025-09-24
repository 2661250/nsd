# --- START OF FILE 963.py ---

import streamlit as st
import pandas as pd
import plotly.express as px
import finnhub
import time

# ------------------ 页面配置 (Page Configuration) ------------------
st.set_page_config(
    page_title="美股行业板块实时表现-Finnhub",
    page_icon="📈",
    layout="wide"
)

# ------------------ 应用标题和说明 (App Title & Description) ------------------
st.title("📈 美股行业板块实时表现 (Finnhub)")
st.markdown("""
本应用通过 Finnhub 的免费API 实时跟踪各大行业板块ETF的 **当前市场表现**。
- **数据** 反映的是ETF相对于 **前一交易日收盘价** 的实时涨跌情况。
- **绿色** 代表上涨，**红色** 代表下跌。
- 数据会进行缓存，可手动或自动刷新以获取最新报价。
""")

# ------------------ 配置和常量 (Configuration & Constants) ------------------

# --- API密钥配置 (API Key Configuration) ---
# [修改点 1] 使用 Streamlit 的 Secrets 管理功能，这是部署时安全读取密钥的最佳方式。
try:
    # 尝试从 Streamlit Cloud 的 secrets 中读取密钥
    API_KEY = st.secrets["FINNHUB_API_KEY"]
except KeyError:
    # 如果找不到密钥，则显示错误信息并停止应用
    st.error("错误：找不到 Finnhub API 密钥。")
    st.info("""
        请在 Streamlit Community Cloud 的 'Settings > Secrets' 中添加密钥：\n
        ```toml
        FINNHUB_API_KEY = "你的真实API密钥"
        ```
    """)
    st.stop() # 停止应用运行

# 使用获取到的密钥初始化 Finnhub 客户端
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

# ------------------ 核心数据获取函数 (Core Data Function) ------------------

@st.cache_data(ttl=60) # 缓存60秒，适合实时数据
def get_realtime_performance_data(etfs):
    """
    使用 Finnhub 的 quote API 获取所有选定ETF的实时表现数据。
    """
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
                 st.error(f"API密钥权限不足，无法获取 '{sector}' ({ticker}) 的数据。请检查您的Finnhub订阅计划。")
            else:
                 st.warning(f"获取板块 '{sector}' ({ticker}) 数据时出错: {e}")
    
    if not performance_data:
        return pd.DataFrame()
        
    return pd.DataFrame(performance_data)

# ------------------ 侧边栏和用户输入 (Sidebar & User Inputs) ------------------

with st.sidebar:
    st.header("⚙️ 参数设置")
    
    all_sectors = list(SECTOR_ETFS.keys())
    selected_sectors = st.multiselect(
        "选择要监控的板块",
        options=all_sectors,
        default=all_sectors
    )
    
    if st.checkbox("自动刷新（每分钟）"):
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
    st.warning("未能获取任何板块的实时数据。请检查API Key权限或网络连接，并尝试手动刷新。")
else:
    df_sorted = df_performance.sort_values(by="涨跌幅 (%)", ascending=False).reset_index(drop=True)

    st.subheader(f"📊 截至 {pd.Timestamp.now(tz='Asia/Shanghai').strftime('%Y-%m-%d %H:%M:%S')} 的实时表现")
    
    # [修改点 2] 移除 st.columns(2) 双栏布局，改为单栏垂直布局，以优化移动端体验。
    # 指标和图表将从上到下依次显示。
    
    # 显示领涨和领跌板块指标
    top_performer = df_sorted.iloc[0]
    st.metric(
        label=f"🟢 领涨板块: {top_performer['板块']}",
        value=f"{top_performer['涨跌幅 (%)']:.2f}%",
        delta=f"{top_performer['涨跌额']:.2f}"
    )
    
    bottom_performer = df_sorted.iloc[-1]
    st.metric(
        label=f"🔴 领跌板块: {bottom_performer['板块']}",
        value=f"{bottom_performer['涨跌幅 (%)']:.2f}%",
        delta=f"{bottom_performer['涨跌额']:.2f}"
    )
    
    st.divider()

    # 显示条形图
    st.subheader("各板块实时涨跌幅对比")
    fig_bar = px.bar(
        df_sorted,
        x="涨跌幅 (%)",
        y="板块",
        orientation='h',
        text="涨跌幅 (%)",
        color=df_sorted["涨跌幅 (%)"] > 0,
        color_discrete_map={True: "green", False: "red"},
        labels={"板块": "行业板块", "涨跌幅 (%)": "实时涨跌幅 (%)"}
    )
    fig_bar.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    fig_bar.update_layout(
        showlegend=False, 
        yaxis={'categoryorder':'total ascending'}
    )
    st.plotly_chart(fig_bar, use_container_width=True)
    
    st.divider()

    # 显示详细数据表
    st.subheader("📋 详细数据表")
    
    def style_change(val):
        color = 'red' if val < 0 else 'green' if val > 0 else 'black'
        return f'color: {color}'

    st.dataframe(
        df_sorted.style.format({
            "当前价格": "${:.2f}",
            "涨跌额": "{:+.2f}",
            "涨跌幅 (%)": "{:+.2f}%",
            "昨日收盘": "${:.2f}",
        }).apply(lambda x: x.map(style_change), subset=['涨跌额', '涨跌幅 (%)']),
        use_container_width=True
    )