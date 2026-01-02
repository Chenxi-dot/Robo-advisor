import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import re
import os
from agents import FundamentalAnalyst, TechnicalAnalyst, NewsAnalyst, RiskManager
from llm_utils import call_llm

# 设置页面配置
st.set_page_config(
    page_title="智能投资研究平台",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
    <style>
    .main {
        padding-top: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

import requests
from bs4 import BeautifulSoup
import json
import re

# --- 辅助爬虫函数 ---

def get_guba_comments(code):
    """爬取东方财富股吧评论 (包含阅读、评论、标题、作者、最后更新)"""
    url = f"https://guba.eastmoney.com/list,{code}.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    comments_list = []
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 新版结构: tr.listitem
            items = soup.find_all('tr', class_='listitem')
            
            # 如果没找到 tr.listitem，尝试旧版结构 (兼容性)
            if not items:
                items = soup.find_all('div', class_='article-h')

            for item in items:
                try:
                    # 判断是新版还是旧版
                    if item.name == 'tr':
                        # 新版结构
                        read_div = item.find('div', class_='read')
                        reply_div = item.find('div', class_='reply')
                        title_div = item.find('div', class_='title')
                        author_div = item.find('div', class_='author')
                        update_div = item.find('div', class_='update')
                        
                        if title_div and title_div.a:
                            title = title_div.a.get_text(strip=True)
                            href = title_div.a['href']
                            full_link = "https://guba.eastmoney.com" + href if href.startswith("/") else href
                            
                            read_count = read_div.get_text(strip=True) if read_div else "0"
                            comment_count = reply_div.get_text(strip=True) if reply_div else "0"
                            author = author_div.get_text(strip=True) if author_div else "未知作者"
                            time_val = update_div.get_text(strip=True) if update_div else ""
                            
                            comments_list.append({
                                "标题": title,
                                "链接": full_link,
                                "阅读": read_count,
                                "评论": comment_count,
                                "作者": author,
                                "时间": time_val
                            })
                    else:
                        # 旧版结构 (保留以防万一)
                        l1 = item.find(class_='l1') # 阅读
                        l2 = item.find(class_='l2') # 评论
                        l3 = item.find(class_='l3') # 标题
                        l4 = item.find(class_='l4') # 作者
                        l5 = item.find(class_='l5') # 时间
                        
                        if l3 and l3.a:
                            title = l3.a.get_text(strip=True)
                            href = l3.a['href']
                            full_link = "https://guba.eastmoney.com" + href if href.startswith("/") else href
                            
                            read_count = l1.get_text(strip=True) if l1 else "0"
                            comment_count = l2.get_text(strip=True) if l2 else "0"
                            author = l4.get_text(strip=True) if l4 else "未知作者"
                            time_val = l5.get_text(strip=True) if l5 else ""
                            
                            comments_list.append({
                                "标题": title,
                                "链接": full_link,
                                "阅读": read_count,
                                "评论": comment_count,
                                "作者": author,
                                "时间": time_val
                            })
                except:
                    continue
            
            # 去重
            seen = set()
            unique_comments = []
            for item in comments_list:
                if item['标题'] not in seen:
                    seen.add(item['标题'])
                    unique_comments.append(item)
            return pd.DataFrame(unique_comments[:20])
    except Exception as e:
        print(f"Guba scraping error: {e}")
    return pd.DataFrame()

def get_stock_notices(code):
    """获取公司公告 (使用东方财富API)"""
    try:
        # 构造API URL
        url = f"https://np-anotice-stock.eastmoney.com/api/security/ann?cb=jQuery123&page_index=1&page_size=20&ann_type=A&client_source=web&stock_list={code}&f_node=1&s_node=1"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://data.eastmoney.com/"
        }
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            # 解析JSONP
            text = response.text
            start = text.find('(') + 1
            end = text.rfind(')')
            if start > 0 and end > 0:
                json_str = text[start:end]
                data = json.loads(json_str)
                if 'data' in data and 'list' in data['data']:
                    notices = []
                    for item in data['data']['list']:
                        # 修正字段获取
                        title = item.get('title', item.get('art_title', '公告'))
                        date = item.get('notice_date', '')[:10]
                        art_code = item.get('art_code')
                        
                        # 尝试获取股票代码
                        stock_code = code
                        if item.get('codes'):
                            stock_code = item.get('codes')[0].get('stock_code', code)
                            
                        # 修正链接格式: stock_code/art_code.html
                        link = f"https://data.eastmoney.com/notices/detail/{stock_code}/{art_code}.html"
                        
                        # 获取公告类型
                        ann_type = "公告"
                        if item.get('columns'):
                            ann_type = item.get('columns')[0].get('column_name', '公告')
                            
                        notices.append({
                            "公告标题": title,
                            "公告类型": ann_type,
                            "公告日期": date,
                            "链接": link
                        })
                    return pd.DataFrame(notices)
    except Exception as e:
        print(f"Notices API error: {e}")
    return pd.DataFrame()

def get_stock_reports(code):
    """获取机构研报 (使用AkShare)"""
    try:
        df = ak.stock_research_report_em(symbol=code)
        if not df.empty:
            # 筛选需要的列
            # 实际列名: '报告名称', '机构', '东财评级', '日期', '报告PDF链接'
            # 重命名以匹配UI
            df = df.rename(columns={
                "报告名称": "研报标题",
                "机构": "机构",
                "东财评级": "评级",
                "日期": "研报日期",
                "报告PDF链接": "链接"
            })
            return df.head(20) # 只取前20条
    except Exception as e:
        print(f"Reports API error: {e}")
    return pd.DataFrame()


def get_financial_report_em(code, report_type='zcfzb'):
    """获取详细财务报表 (zcfzb=资产负债表, xjllb=现金流量表, lrb=利润表)"""
    try:
        # 转换代码格式: 000001 -> SZ000001
        market = "SZ" if code.startswith(('0', '3')) else "SH" if code.startswith('6') else "BJ"
        symbol = f"{market}{code}"
        
        url = f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/{report_type}Ajax?companyType=4&reportDateType=0&reportType=1&endDate=&code={symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code={symbol}"
        }
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            try:
                data = response.json()
                if 'data' in data and data['data']:
                    df = pd.DataFrame(data['data'])
                    # 简单的列名映射 (示例，实际列名很多)
                    # 东方财富返回的key通常是英文缩写，如 REPORT_DATE
                    # 我们直接返回原始数据，让 Pandas 展示
                    return df
            except ValueError:
                pass
    except Exception as e:
        print(f"Financial API error ({report_type}): {e}")
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_industry_peers(stock_code, stock_name):
    """获取同行业对比数据及行业指数历史"""
    try:
        # 1. 获取所属行业
        info = ak.stock_individual_info_em(symbol=stock_code)
        industry_row = info[info['item'] == '行业']
        if industry_row.empty:
            return None, pd.DataFrame(), pd.DataFrame()
        
        industry = industry_row['value'].values[0]
        
        # 2. 获取行业内成分股
        peers = ak.stock_board_industry_cons_em(symbol=industry)
        
        # 3. 获取行业指数历史
        industry_hist = pd.DataFrame()
        try:
            # 获取当前年份
            current_year = datetime.now().year
            start_date = f"{current_year}0101"
            end_date = f"{current_year}1231"
            industry_hist = ak.stock_board_industry_hist_em(symbol=industry, start_date=start_date, end_date=end_date, period="日k", adjust="qfq")
        except Exception as e:
            print(f"Industry hist error: {e}")

        # 确保代码列为字符串，避免 pyarrow 转换错误
        if not peers.empty and '代码' in peers.columns:
            peers['代码'] = peers['代码'].astype(str)
        
        # 确保其他可能混淆的列也为字符串
        for col in peers.columns:
            if peers[col].dtype == 'object':
                peers[col] = peers[col].astype(str)

        return industry, peers, industry_hist
    except Exception as e:
        print(f"Industry API error: {e}")
        return None, pd.DataFrame(), pd.DataFrame()
        
        # 3. 清洗数据
        # 确保数值列为数值类型
        numeric_cols = ['最新价', '涨跌幅', '换手率', '市盈率-动态', '市净率', '总市值']
        for col in numeric_cols:
            if col in peers.columns:
                peers[col] = pd.to_numeric(peers[col], errors='coerce')
        
        # 计算总市值 (如果接口没返回，可以用 最新价 * 总股本，这里假设接口返回了或我们只用PE/PB)
        # 注意：stock_board_industry_cons_em 返回的列可能不包含总市值，需检查
        # 如果没有总市值，我们可能需要额外获取，或者仅比较PE/PB/涨跌幅
        
        return industry, peers
    except Exception as e:
        print(f"Peer analysis error: {e}")
        return None, pd.DataFrame()

# --- 数据获取函数 ---

@st.cache_data(ttl=3600*24)  # 缓存24小时
def get_stock_list():
    """获取A股所有股票列表 (带本地缓存)"""
    file_path = "stock_list.csv"
    
    # 1. 尝试从本地读取
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path, dtype={'code': str})
            return df
        except Exception:
            pass # 读取失败则重新下载
            
    # 2. 本地没有或读取失败，从网络下载
    try:
        with st.spinner('正在初始化股票列表，请稍候...'):
            stock_info = ak.stock_info_a_code_name()
            # 确保code是字符串
            stock_info['code'] = stock_info['code'].astype(str)
            # 保存到本地
            stock_info.to_csv(file_path, index=False)
            return stock_info
    except:
        # 3. 下载失败，返回示例数据
        return pd.DataFrame({
            'code': ['000001', '000002', '600000', '600036'],
            'name': ['平安银行', '万科A', '浦发银行', '招商银行']
        })

@st.cache_data(ttl=60)  # 缓存1分钟
def get_market_indices():
    """获取主要指数实时行情"""
    try:
        # 使用新浪接口获取指数数据 (更稳定)
        df = ak.stock_zh_index_spot_sina()
        # 筛选主要指数
        target_indices = ['上证指数', '深证成指', '创业板指', '科创50']
        filtered_df = df[df['名称'].isin(target_indices)].copy()
        return filtered_df
    except Exception as e:
        return pd.DataFrame()

def safe_dataframe(df):
    """
    辅助函数：确保DataFrame可以被Streamlit安全渲染，避免PyArrow错误
    将所有object类型的列强制转换为string
    """
    if df is None or df.empty:
        return df
    
    df_out = df.copy()
    for col in df_out.columns:
        if df_out[col].dtype == 'object':
            df_out[col] = df_out[col].astype(str)
    return df_out

# --- 页面组件 ---

def show_market_overview():
    st.title("🌏 市场全景")
    st.markdown("### 主要指数实时行情")
    
    indices_df = get_market_indices()
    
    if not indices_df.empty:
        cols = st.columns(4)
        for i, row in indices_df.iterrows():
            col_idx = i % 4
            with cols[col_idx]:
                try:
                    name = row['名称']
                    price = row['最新价']
                    change = row['涨跌额']
                    pct_change = row['涨跌幅']
                    
                    st.metric(
                        label=name,
                        value=f"{price:.2f}",
                        delta=f"{change:.2f} ({pct_change:.2f}%)"
                    )
                except:
                    st.error(f"解析指数数据出错: {row}")
    else:
        st.warning("无法获取实时指数数据，请检查网络连接。")

    st.markdown("---")
    st.markdown("### 市场热点与资金流向")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔥 行业板块涨幅 Top 5")
        try:
            # 获取行业板块实时行情
            df_industry = ak.stock_board_industry_name_em()
            # 按涨跌幅排序
            if not df_industry.empty and '涨跌幅' in df_industry.columns:
                # 确保涨跌幅是数值
                df_industry['涨跌幅'] = pd.to_numeric(df_industry['涨跌幅'], errors='coerce')
                top_industries = df_industry.sort_values('涨跌幅', ascending=False).head(5)
                
                # 展示
                for _, row in top_industries.iterrows():
                    st.markdown(f"**{row['板块名称']}**: <span style='color:red'>+{row['涨跌幅']}%</span> (领涨: {row['领涨股票']})", unsafe_allow_html=True)
            else:
                st.info("暂无行业数据")
        except Exception as e:
            st.error(f"获取行业数据失败: {e}")

    with col2:
        st.subheader("💡 北向资金流向")
        try:
            # 获取北向资金概览
            # 注意：akshare接口变动频繁，这里使用 stock_hsgt_fund_flow_summary_em
            df_flow = ak.stock_hsgt_fund_flow_summary_em()
            if not df_flow.empty:
                # 只需要展示最新的几条或者当天的
                # 假设返回包含 '日期', '北向资金', etc.
                # 实际上这个接口返回的是历史数据还是实时？
                # 让我们只取最后一行作为今日/最新
                latest = df_flow.iloc[0] # 通常第一行是最新? 需确认，通常是按时间倒序或正序
                # 假设第一行是最新
                
                # 构造展示数据
                # 接口返回列名可能为: date, value, etc. 
                # 让我们先简单展示整个表格的前几行
                st.dataframe(safe_dataframe(df_flow.head(5)), use_container_width=True, hide_index=True)
            else:
                st.info("暂无资金流向数据")
        except Exception as e:
            st.error(f"获取资金流向失败: {e}")

def show_stock_research(stock_list):
    st.title("🔍 个股深度研究")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        search_method = st.radio("搜索方式", ["股票代码", "公司名称"], horizontal=True)
        
        selected_stock_code = "000001"
        selected_stock_name = "平安银行"
        
        if search_method == "公司名称":
            selected_stock_name = st.selectbox("输入/选择公司", stock_list['name'].tolist())
            selected_stock_code = stock_list[stock_list['name'] == selected_stock_name]['code'].iloc[0]
        else:
            code_input = st.text_input("输入6位代码", "000001")
            code_clean = re.sub(r'\D', '', code_input)
            if code_clean in stock_list['code'].values:
                selected_stock_code = code_clean
                selected_stock_name = stock_list[stock_list['code'] == selected_stock_code]['name'].iloc[0]
            else:
                st.warning("未找到该代码")
    
    with col2:
        st.markdown(f"## {selected_stock_name} ({selected_stock_code})")
        st.caption(f"当前查看: {selected_stock_name}")

    # 标签页
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📈 股价走势", "📊 基本面分析", "💰 财务报表", "📰 舆情新闻", "🏢 行业对比", "🤖 AI 投顾分析"])
    
    with tab1:
        st.subheader("K线走势与技术分析")
        try:
            # 获取日线数据 (使用Sina接口作为备选)
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
            
            # 构建带前缀的代码
            prefix = ""
            if selected_stock_code.startswith('6'): prefix = "sh"
            elif selected_stock_code.startswith(('0', '3')): prefix = "sz"
            elif selected_stock_code.startswith(('8', '4')): prefix = "bj"
            
            symbol_with_prefix = prefix + selected_stock_code
            
            try:
                # 尝试使用 stock_zh_a_daily (Sina源)
                df_hist = ak.stock_zh_a_daily(symbol=symbol_with_prefix, start_date=start_date, end_date=end_date)
                # 重命名列以匹配后续逻辑
                df_hist = df_hist.rename(columns={
                    'date': '日期', 'open': '开盘', 'high': '最高', 'low': '最低', 'close': '收盘', 'volume': '成交量'
                })
            except:
                # 如果Sina失败，尝试原接口 (可能修复)
                df_hist = ak.stock_zh_a_hist(symbol=selected_stock_code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")

            if not df_hist.empty:
                # 计算均线
                df_hist['MA5'] = df_hist['收盘'].rolling(window=5).mean()
                df_hist['MA20'] = df_hist['收盘'].rolling(window=20).mean()
                
                # K线图
                fig = go.Figure()
                
                # K线
                fig.add_trace(go.Candlestick(
                    x=df_hist['日期'],
                    open=df_hist['开盘'],
                    high=df_hist['最高'],
                    low=df_hist['最低'],
                    close=df_hist['收盘'],
                    name='日K'
                ))
                
                # 均线
                fig.add_trace(go.Scatter(x=df_hist['日期'], y=df_hist['MA5'], mode='lines', name='MA5', line=dict(color='orange', width=1)))
                fig.add_trace(go.Scatter(x=df_hist['日期'], y=df_hist['MA20'], mode='lines', name='MA20', line=dict(color='blue', width=1)))
                
                fig.update_layout(
                    xaxis_rangeslider_visible=False,
                    height=500,
                    title_text=f"{selected_stock_name} 日K线图",
                    yaxis_title="价格",
                    dragmode='pan'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # 成交量图
                fig_vol = go.Figure()
                fig_vol.add_trace(go.Bar(x=df_hist['日期'], y=df_hist['成交量'], name='成交量', marker_color='lightblue'))
                fig_vol.update_layout(height=200, title_text="成交量", margin=dict(t=30))
                st.plotly_chart(fig_vol, use_container_width=True)
                
                # 最新行情数据
                latest = df_hist.iloc[-1]
                prev = df_hist.iloc[-2] if len(df_hist) > 1 else latest
                change = latest['收盘'] - prev['收盘']
                pct = (change / prev['收盘']) * 100 if prev['收盘'] != 0 else 0
                
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("最新收盘", f"{latest['收盘']:.2f}", f"{pct:.2f}%")
                m2.metric("开盘", f"{latest['开盘']:.2f}")
                m3.metric("最高", f"{latest['最高']:.2f}")
                m4.metric("最低", f"{latest['最低']:.2f}")
                m5.metric("成交量", f"{latest['成交量']/10000:.0f} 万手")
                
            else:
                st.warning("暂无行情数据")
        except Exception as e:
            st.error(f"获取行情失败: {e}")

    with tab2:
        st.subheader("公司概况")
        try:
            # 尝试获取详细信息，如果失败则使用实时行情中的简要信息
            try:
                info = ak.stock_individual_info_em(symbol=selected_stock_code)
                # 确保 value 列为字符串，避免 PyArrow 混合类型错误
                info['value'] = info['value'].astype(str)
                info_dict = dict(zip(info['item'], info['value']))
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**上市日期:** {info_dict.get('上市日期', '-')}")
                    st.markdown(f"**所属行业:** {info_dict.get('行业', '-')}")
                    st.markdown(f"**总市值:** {info_dict.get('总市值', '-')}")
                with c2:
                    st.markdown(f"**流通市值:** {info_dict.get('流通市值', '-')}")
                    st.markdown(f"**总股本:** {info_dict.get('总股本', '-')}")
                    st.markdown(f"**流通股:** {info_dict.get('流通股', '-')}")
                st.divider()
                st.dataframe(safe_dataframe(info), use_container_width=True, hide_index=True)
                
            except Exception:
                # 备用方案：从实时行情中获取
                spot_df = ak.stock_zh_a_spot_em()
                stock_spot = spot_df[spot_df['代码'] == selected_stock_code]
                if not stock_spot.empty:
                    row = stock_spot.iloc[0]
                    st.info("详细资料获取受限，显示实时概况：")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("总市值", f"{row['总市值']/100000000:.2f} 亿")
                    c2.metric("流通市值", f"{row['流通市值']/100000000:.2f} 亿")
                    c3.metric("市盈率(TTM)", f"{row['市盈率-动态']}")
                    
                    c4, c5, c6 = st.columns(3)
                    c4.metric("市净率", f"{row['市净率']}")
                    c5.metric("换手率", f"{row['换手率']}%")
                    c6.metric("量比", f"{row['量比']}")
                else:
                    st.warning("无法获取公司概况")
        except:
            st.error("获取基本信息失败")

    with tab3:
        st.subheader("财务数据全览")
        
        # 使用 stock_financial_abstract 作为主要数据源
        try:
            abstract_df = ak.stock_financial_abstract(symbol=selected_stock_code)
        except:
            abstract_df = pd.DataFrame()

        ft1, ft2, ft3, ft4 = st.tabs(["关键指标", "利润表", "资产负债表", "现金流量表"])
        
        with ft1:
            if not abstract_df.empty:
                st.markdown("#### 核心财务指标趋势")
                
                # 数据清洗与转置
                # 假设结构: 选项, 指标, 日期1, 日期2...
                # 我们需要提取 '常用指标'
                main_indicators = abstract_df[abstract_df['选项'] == '常用指标'].copy()
                if not main_indicators.empty:
                    # 设置索引为指标名，删除选项列
                    main_indicators = main_indicators.set_index('指标').drop(columns=['选项'])
                    # 转置: 行变日期，列变指标
                    df_T = main_indicators.T
                    df_T.index.name = '日期'
                    
                    # 转换索引为 datetime 对象，以便正确绘图
                    # 确保索引是字符串格式的日期
                    df_T.index = df_T.index.astype(str)
                    df_T.index = pd.to_datetime(df_T.index, errors='coerce')
                    
                    # 只取最近的N个报告期 (前10列 -> 前10行)
                    df_recent = df_T.head(10)
                    
                    st.dataframe(safe_dataframe(df_recent), use_container_width=True)
                    
                    # 绘图
                    cols = df_recent.columns.tolist()
                    # 模糊匹配列名
                    rev_col = next((c for c in cols if '营收' in c or '收入' in c), None)
                    profit_col = next((c for c in cols if '净利润' in c and '扣非' not in c), None)
                    
                    if rev_col and profit_col:
                        # 确保数据是数值型
                        try:
                            # 使用 .loc 避免 SettingWithCopyWarning
                            df_recent = df_recent.copy()
                            df_recent[rev_col] = pd.to_numeric(df_recent[rev_col], errors='coerce')
                            df_recent[profit_col] = pd.to_numeric(df_recent[profit_col], errors='coerce')
                            
                            # 按日期升序排列以绘图
                            plot_df = df_recent.sort_index(ascending=True)
                            
                            fig_fin = go.Figure()
                            fig_fin.add_trace(go.Bar(x=plot_df.index, y=plot_df[rev_col], name=rev_col))
                            fig_fin.add_trace(go.Bar(x=plot_df.index, y=plot_df[profit_col], name=profit_col))
                            
                            fig_fin.update_layout(title="近期营收与净利润趋势", barmode='group')
                            st.plotly_chart(fig_fin, use_container_width=True)
                        except Exception as e:
                            st.warning(f"绘图数据转换失败: {e}")
                else:
                    st.info("未找到常用指标数据")
            else:
                st.info("暂无财务摘要数据")

        with ft2:
            st.markdown("#### 利润表摘要")
            if not abstract_df.empty:
                # 尝试筛选利润表相关 (这里简单展示所有数据，或者筛选特定行)
                # 由于abstract包含所有，我们展示原始表格的转置版本，方便查看
                st.dataframe(safe_dataframe(abstract_df), use_container_width=True)
            else:
                st.info("暂无数据")

        with ft3:
            st.markdown("#### 资产负债表 (近期)")
            try:
                balance_df = get_financial_report_em(selected_stock_code, 'zcfzb')
                if not balance_df.empty:
                    # 筛选关键列 (示例)
                    # 假设我们只展示前几列和日期
                    cols = [c for c in balance_df.columns if 'DATE' in c or 'ASSET' in c or 'LIAB' in c or 'EQUITY' in c]
                    # 如果没有匹配到英文列名，可能返回的是中文key或者其他
                    # 直接展示前20列
                    st.dataframe(balance_df.iloc[:, :20], use_container_width=True)
                else:
                    st.info("暂无资产负债表数据")
                    st.markdown(f"[点击查看东方财富详细报表](https://data.eastmoney.com/bbsj/{selected_stock_code}.html)")
            except:
                st.info("获取失败")

        with ft4:
            st.markdown("#### 现金流量表 (近期)")
            try:
                cash_df = get_financial_report_em(selected_stock_code, 'xjllb')
                if not cash_df.empty:
                    st.dataframe(cash_df.iloc[:, :20], use_container_width=True)
                else:
                    st.info("暂无现金流量表数据")
                    st.markdown(f"[点击查看东方财富详细报表](https://data.eastmoney.com/bbsj/{selected_stock_code}.html)")
            except:
                st.info("获取失败")

    with tab4:
        st.subheader("资讯与公告")
        nt1, nt2, nt3 = st.tabs(["🗣️ 股民评论", "📢 公司公告", "📑 机构研报"])
        
        with nt1:
            st.markdown("#### 东方财富股吧热帖")
            try:
                comments_df = get_guba_comments(selected_stock_code)
                if not comments_df.empty:
                    for i, row in comments_df.iterrows():
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.markdown(f"[{row['标题']}]({row['链接']})")
                            # 显示更多信息: 作者, 时间, 阅读, 评论
                            st.caption(f"作者: {row.get('作者', '未知')} | 时间: {row['时间']} | 阅读: {row['阅读']} | 评论: {row['评论']}")
                        with col2:
                            pass # 占位
                        st.divider()
                else:
                    st.info("暂无评论数据")
            except Exception as e:
                st.error(f"获取评论失败: {e}")
                
            st.markdown(f"🔗 [前往 {selected_stock_name} 股吧](https://guba.eastmoney.com/list,{selected_stock_code}.html)")
        
        with nt2:
            try:
                notices = get_stock_notices(selected_stock_code)
                if not notices.empty:
                    # 格式化显示
                    for i, row in notices.iterrows():
                        with st.expander(f"{row['公告日期']} | {row['公告标题']}"):
                            st.write(f"类型: {row['公告类型']}")
                            if row['链接']:
                                st.markdown(f"[查看公告详情]({row['链接']})")
                else:
                    st.info("暂无公告")
            except Exception as e:
                st.info(f"公告获取服务暂时不可用: {e}")
                st.markdown(f"🔗 [点击查看公告](https://data.eastmoney.com/notices/stock/{selected_stock_code}.html)")

        with nt3:
            try:
                reports = get_stock_reports(selected_stock_code)
                if not reports.empty:
                    # 展示研报列表
                    for i, row in reports.iterrows():
                        with st.expander(f"{row['研报日期']} | {row['研报标题']}"):
                            st.write(f"机构: {row['机构']} | 评级: {row['评级']}")
                            if row['链接']:
                                st.markdown(f"[查看研报PDF]({row['链接']})")
                else:
                    st.info("暂无研报")
            except Exception as e:
                st.info(f"研报获取服务暂时不可用: {e}")
                st.markdown(f"🔗 [点击查看研报](https://data.eastmoney.com/report/{selected_stock_code}.html)")

    with tab5:
        st.subheader("行业对比分析")
        industry, peers, industry_hist = get_industry_peers(selected_stock_code, selected_stock_name)
        
        if industry and not peers.empty:
            st.info(f"当前所属行业: {industry} (共 {len(peers)} 只成分股)")
            
            # 初始化 curr_row，防止后续引用报错
            curr_row = None
            if '代码' in peers.columns:
                current_stock = peers[peers['代码'] == selected_stock_code]
                if not current_stock.empty:
                    curr_row = current_stock.iloc[0]

            # 数据预处理
            if '总市值' in peers.columns and '市盈率-动态' in peers.columns:
                # 估算净利润 (市值 / PE)
                peers['估算净利润'] = peers.apply(lambda x: x['总市值'] / x['市盈率-动态'] if x['市盈率-动态'] > 0 else 0, axis=1)
                
                # 计算排名
                peers['市值排名'] = peers['总市值'].rank(ascending=False)
                peers['净利润排名'] = peers['估算净利润'].rank(ascending=False)
                
                # 获取当前股票数据
                # current_stock = peers[peers['代码'] == selected_stock_code]
                # curr_row = None
                # if not current_stock.empty:
                #     curr_row = current_stock.iloc[0]
                    
                total_peers = len(peers)
                    
                # 1. 行业指数走势
                if not industry_hist.empty:
                    st.markdown("#### 📈 行业指数走势 (今年以来)")
                    fig_ind = px.line(industry_hist, x='日期', y='收盘', title=f"{industry}行业指数趋势")
                    fig_ind.update_layout(xaxis_title="日期", yaxis_title="指数点位")
                    st.plotly_chart(fig_ind, use_container_width=True)

                st.divider()

                # 2. 核心排名指标
                if curr_row is not None:
                    st.markdown("#### 🏆 核心指标排名")
                    c1, c2, c3 = st.columns(3)
                    
                    # 市值排名
                    mkt_rank = int(curr_row['市值排名'])
                    mkt_pct = (total_peers - mkt_rank + 1) / total_peers * 100
                    c1.metric("市值排名", f"{mkt_rank} / {total_peers}", f"超过 {mkt_pct:.1f}% 同行")
                    
                    # 净利润排名
                    profit_rank = int(curr_row['净利润排名'])
                    profit_pct = (total_peers - profit_rank + 1) / total_peers * 100
                    c2.metric("净利润排名(估)", f"{profit_rank} / {total_peers}", f"超过 {profit_pct:.1f}% 同行")
                    
                    # 涨跌幅排名
                    if '涨跌幅' in peers.columns:
                        peers['涨跌幅排名'] = peers['涨跌幅'].rank(ascending=False)
                        chg_rank = int(peers[peers['代码'] == selected_stock_code]['涨跌幅排名'].iloc[0])
                        chg_pct = (total_peers - chg_rank + 1) / total_peers * 100
                        c3.metric("今日涨跌幅排名", f"{chg_rank} / {total_peers}", f"超过 {chg_pct:.1f}% 同行")
                else:
                    st.warning("当前股票不在行业成分股列表中，无法显示排名。")

            st.divider()
            
            # 3. 行业全景图 (Treemap)
            if '总市值' in peers.columns and '涨跌幅' in peers.columns:
                st.markdown("#### 🗺️ 行业市值全景图")
                # 准备数据: 过滤掉市值过小的，避免图太碎
                treemap_data = peers[peers['总市值'] > 0].copy()
                # 增加一列用于根节点
                treemap_data['行业'] = industry
                
                fig_tree = px.treemap(
                    treemap_data,
                    path=['行业', '名称'],
                    values='总市值',
                    color='涨跌幅',
                    color_continuous_scale='RdGn_r', # 红绿配色 (红跌绿涨? A股是红涨绿跌)
                    # A股习惯: 红涨(正) 绿跌(负). Plotly RdGn 是红(高)到绿(低).
                    # 我们需要: 负数(跌) -> 绿色, 正数(涨) -> 红色.
                    # Plotly RdGn: Red(High) -> Green(Low)? No.
                    # Let's use a custom scale or 'RdYlGn' reversed?
                    # Usually 'RdYlGn': Red(Low) -> Green(High).
                    # We want Red(High) -> Green(Low). That is 'RdYlGn_r'.
                    # Wait, A股: Red is Positive (High), Green is Negative (Low).
                    # So we want Green(Low) -> Red(High). That is 'RdYlGn'.
                    color_continuous_midpoint=0,
                    hover_data=['代码', '最新价', '涨跌幅'],
                    title=f"{industry}行业个股市值与涨跌幅分布"
                )
                fig_tree.update_layout(margin=dict(t=30, l=10, r=10, b=10))
                st.plotly_chart(fig_tree, use_container_width=True)

            st.divider()

            # 4. 榜单分析
            st.markdown("#### 📊 行业榜单")
            
            # 涨跌幅榜
            col_top, col_bottom = st.columns(2)
            with col_top:
                st.markdown("**🚀 涨幅榜 Top 5**")
                if '涨跌幅' in peers.columns:
                    top_gainers = peers.sort_values('涨跌幅', ascending=False).head(5)
                    st.dataframe(
                        top_gainers[['代码', '名称', '最新价', '涨跌幅', '换手率']], 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={
                            "涨跌幅": st.column_config.NumberColumn(
                                "涨跌幅",
                                format="%.2f%%",
                            ),
                        }
                    )
            
            with col_bottom:
                st.markdown("**📉 跌幅榜 Top 5**")
                if '涨跌幅' in peers.columns:
                    top_losers = peers.sort_values('涨跌幅', ascending=True).head(5)
                    st.dataframe(
                        top_losers[['代码', '名称', '最新价', '涨跌幅', '换手率']], 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={
                            "涨跌幅": st.column_config.NumberColumn(
                                "涨跌幅",
                                format="%.2f%%",
                            ),
                        }
                    )

            # 成交额榜
            st.markdown("**💰 成交额榜 Top 5**")
            if '成交额' in peers.columns:
                top_volume = peers.sort_values('成交额', ascending=False).head(5)
                # 格式化成交额
                top_volume['成交额(亿)'] = top_volume['成交额'].apply(lambda x: x / 1e8)
                st.dataframe(
                    top_volume[['代码', '名称', '最新价', '涨跌幅', '成交额(亿)', '换手率']], 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "成交额(亿)": st.column_config.ProgressColumn(
                            "成交额(亿)",
                            format="%.2f 亿",
                            min_value=0,
                            max_value=float(top_volume['成交额(亿)'].max()),
                        ),
                        "涨跌幅": st.column_config.NumberColumn(
                            "涨跌幅",
                            format="%.2f%%",
                        ),
                    }
                )

            st.divider()

            # 5. 估值分布 (Box Plot + Scatter)
            st.markdown("#### 🎯 估值分布")
            col_box, col_scatter = st.columns(2)
            
            with col_box:
                if '市盈率-动态' in peers.columns:
                    # 过滤异常值
                    pe_data = peers[(peers['市盈率-动态'] > 0) & (peers['市盈率-动态'] < 100)]
                    fig_box = px.box(pe_data, y="市盈率-动态", points="all", title="行业PE分布 (剔除负值及>100)")
                    # 标记当前股票
                    if curr_row is not None:
                        curr_pe = curr_row['市盈率-动态']
                        if 0 < curr_pe < 100:
                            fig_box.add_hline(y=curr_pe, line_dash="dash", line_color="red", annotation_text=f"当前: {curr_pe}")
                    st.plotly_chart(fig_box, use_container_width=True)

            with col_scatter:
                if '总市值' in peers.columns and '市盈率-动态' in peers.columns:
                    # 过滤掉异常值
                    plot_data = peers[
                        (peers['市盈率-动态'] > 0) & 
                        (peers['市盈率-动态'] < 200) &
                        (peers['总市值'] > 0)
                    ].copy()
                    
                    # 标记当前股票
                    plot_data['color'] = plot_data['代码'].apply(lambda x: 'red' if x == selected_stock_code else 'blue')
                    plot_data['size'] = plot_data['代码'].apply(lambda x: 15 if x == selected_stock_code else 8)
                    
                    fig_scatter = px.scatter(
                        plot_data, 
                        x='总市值', 
                        y='市盈率-动态', 
                        hover_name='名称',
                        color='color',
                        size='size',
                        labels={'总市值': '总市值 (元)', '市盈率-动态': 'PE (动态)'},
                        color_discrete_map={'red': 'red', 'blue': 'lightblue'},
                        title="市值 vs PE"
                    )
                    fig_scatter.update_layout(showlegend=False)
                    st.plotly_chart(fig_scatter, use_container_width=True)
            
            # 6. 排名图表
            st.markdown("#### 🏆 行业龙头对比")
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                if '总市值' in peers.columns:
                    # 市值 Top 10
                    top10_mkt = peers.sort_values('总市值', ascending=False).head(10)
                    # 确保当前股票在图中
                    if selected_stock_code not in top10_mkt['代码'].values and not current_stock.empty:
                        top10_mkt = pd.concat([top10_mkt, current_stock])
                    
                    top10_mkt['color'] = top10_mkt['代码'].apply(lambda x: 'red' if x == selected_stock_code else 'lightblue')
                    
                    fig_bar = px.bar(
                        top10_mkt,
                        x='名称',
                        y='总市值',
                        title=f"市值排名 Top10",
                        text_auto='.2s'
                    )
                    fig_bar.update_traces(marker_color=top10_mkt['color'])
                    st.plotly_chart(fig_bar, use_container_width=True)
            
            with col_chart2:
                if '估算净利润' in peers.columns:
                    # 净利润 Top 10
                    top10_profit = peers.sort_values('估算净利润', ascending=False).head(10)
                    # 确保当前股票在图中
                    if selected_stock_code not in top10_profit['代码'].values and not current_stock.empty:
                        top10_profit = pd.concat([top10_profit, current_stock])
                        
                    top10_profit['color'] = top10_profit['代码'].apply(lambda x: 'red' if x == selected_stock_code else 'lightgreen')
                    
                    fig_bar2 = px.bar(
                        top10_profit,
                        x='名称',
                        y='估算净利润',
                        title=f"估算净利润排名 Top10",
                        text_auto='.2s'
                    )
                    fig_bar2.update_traces(marker_color=top10_profit['color'])
                    st.plotly_chart(fig_bar2, use_container_width=True)

            # 7. 数据表
            with st.expander("查看完整行业数据"):
                st.dataframe(peers, use_container_width=True)
            
        else:
            st.warning("无法获取行业对比数据")

    with tab6:
        st.subheader("🤖 AI 智能投顾团队分析")
        st.info("本模块由 Qwen-2.5-7B 模型驱动，模拟多角色投顾团队为您提供全方位分析。")
        
        if st.button("🚀 开始 AI 深度分析"):
            with st.spinner("AI 投顾团队正在召开研讨会，请稍候..."):
                # 1. 收集数据上下文
                data_context = {}
                
                # 基础信息
                try:
                    info = ak.stock_individual_info_em(symbol=selected_stock_code)
                    data_context['basic_info'] = info.to_markdown()
                except:
                    data_context['basic_info'] = "获取失败"
                
                # 财务摘要
                try:
                    abstract_df = ak.stock_financial_abstract(symbol=selected_stock_code)
                    if not abstract_df.empty:
                        # 取最近几期常用指标
                        main_indicators = abstract_df[abstract_df['选项'] == '常用指标'].head(20)
                        data_context['financial_summary'] = main_indicators.to_markdown()
                    else:
                        data_context['financial_summary'] = "暂无数据"
                except:
                    data_context['financial_summary'] = "获取失败"
                
                # 行业对比 (复用之前的函数)
                try:
                    ind, peers_df, _ = get_industry_peers(selected_stock_code, selected_stock_name)
                    if ind and not peers_df.empty:
                        # 简化的行业数据
                        simple_peers = peers_df[['代码', '名称', '最新价', '涨跌幅', '市盈率-动态', '总市值']].head(10)
                        data_context['industry_comparison'] = f"行业: {ind}\n" + simple_peers.to_markdown()
                    else:
                        data_context['industry_comparison'] = "暂无行业数据"
                except:
                    data_context['industry_comparison'] = "获取失败"
                
                # 行情数据
                try:
                    end_date = datetime.now().strftime("%Y%m%d")
                    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
                    df_hist = ak.stock_zh_a_hist(symbol=selected_stock_code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                    if not df_hist.empty:
                        data_context['price_action'] = df_hist.tail(5).to_markdown()
                        data_context['volume_info'] = f"最新成交量: {df_hist.iloc[-1]['成交量']}"
                        # 简单计算均线
                        df_hist['MA5'] = df_hist['收盘'].rolling(window=5).mean()
                        df_hist['MA20'] = df_hist['收盘'].rolling(window=20).mean()
                        data_context['moving_averages'] = df_hist[['日期', 'MA5', 'MA20']].tail(5).to_markdown()
                    else:
                        data_context['price_action'] = "暂无行情"
                except:
                    data_context['price_action'] = "获取失败"
                
                # 资讯数据
                try:
                    notices = get_stock_notices(selected_stock_code)
                    data_context['notices'] = notices.head(5).to_markdown() if not notices.empty else "无近期公告"
                    
                    comments = get_guba_comments(selected_stock_code)
                    data_context['comments'] = comments[['标题', '阅读', '评论']].head(10).to_markdown() if not comments.empty else "无近期评论"
                except:
                    data_context['notices'] = "获取失败"
                    data_context['comments'] = "获取失败"

                # 2. 初始化 Agents
                agents = [
                    FundamentalAnalyst(),
                    TechnicalAnalyst(),
                    NewsAnalyst(),
                    RiskManager()
                ]
                
                # 3. 并行或顺序执行分析 (这里用顺序简单实现，Streamlit不支持简单的多线程UI更新)
                cols = st.columns(2)
                
                # 保存分析结果到 session_state 以便后续对话使用
                if 'ai_analysis_results' not in st.session_state:
                    st.session_state.ai_analysis_results = {}
                
                # 清空旧的分析结果 (如果是重新点击按钮)
                st.session_state.ai_analysis_results = {}

                for i, agent in enumerate(agents):
                    with cols[i % 2]:
                        with st.chat_message(agent.name, avatar="🧑‍💼" if i % 2 == 0 else "👩‍💻"):
                            st.write(f"**{agent.role} ({agent.name})** 正在分析...")
                            try:
                                analysis = agent.analyze(selected_stock_name, selected_stock_code, data_context)
                                st.markdown(analysis)
                                st.session_state.ai_analysis_results[agent.name] = analysis
                            except Exception as e:
                                st.error(f"分析出错: {e}")
        
        # 4. 综合总结与问答
        st.divider()
        st.subheader("💬 与投顾团队对话")
        
        if 'ai_analysis_results' in st.session_state and st.session_state.ai_analysis_results:
            # 综合总结
            if 'summary' not in st.session_state:
                with st.spinner("正在生成综合投资建议..."):
                    summary_prompt = f"""
                    Based on the following analyses for {selected_stock_name} ({selected_stock_code}), provide a comprehensive investment summary and a final rating (Buy/Hold/Sell).
                    
                    Analyses:
                    {json.dumps(st.session_state.ai_analysis_results, ensure_ascii=False)}
                    
                    Output format: Markdown.
                    """
                    st.session_state.summary = call_llm(summary_prompt, "You are a Chief Investment Officer (CIO). Synthesize the reports from your team.")
            
            with st.expander("📋 查看首席投资官 (CIO) 综合报告", expanded=True):
                st.markdown(st.session_state.summary)

            # 聊天界面
            if "messages" not in st.session_state:
                st.session_state.messages = []

            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input("向投顾团队提问 (例如: 风险点主要在哪里？)"):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    with st.spinner("团队正在讨论..."):
                        # 构建上下文
                        context_str = f"""
                        Stock: {selected_stock_name} ({selected_stock_code})
                        Data Context: {str(data_context) if 'data_context' in locals() else 'N/A'}
                        Previous Analyses: {json.dumps(st.session_state.ai_analysis_results, ensure_ascii=False)}
                        CIO Summary: {st.session_state.summary}
                        """
                        
                        chat_prompt = f"""
                        Context:
                        {context_str}
                        
                        User Question: {prompt}
                        
                        Answer the user's question based on the team's analysis.
                        """
                        response = call_llm(chat_prompt, "You are the representative of the investment committee.")
                        st.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
        else:
            st.info("请先点击上方按钮开始分析，生成报告后即可开启对话功能。")

def show_portfolio_tool(stock_list):
    st.title("💼 投资组合模拟器")
    st.markdown("根据您的预算，计算可以购买的股票数量，并提供风险对冲建议。")
    
    col1, col2 = st.columns(2)
    with col1:
        budget = st.number_input("请输入您的总预算 (元)", min_value=1000.0, value=50000.0, step=1000.0)
        
        stock_name = st.selectbox("选择拟投资股票", stock_list['name'].tolist(), key="portfolio_stock")
        stock_code = stock_list[stock_list['name'] == stock_name]['code'].iloc[0]
        
    with col2:
        st.markdown("### 计算结果")
        if st.button("计算可买股数"):
            try:
                # 获取最新价格
                df = ak.stock_zh_a_spot_em()
                price_row = df[df['代码'] == stock_code]
                
                if not price_row.empty:
                    current_price = price_row['最新价'].values[0]
                    
                    if current_price > 0:
                        # A股一手=100股
                        max_shares = int(budget // current_price)
                        max_hands = max_shares // 100
                        buyable_shares = max_hands * 100
                        cost = buyable_shares * current_price
                        balance = budget - cost
                        
                        st.success(f"当前价格: {current_price} 元")
                        st.metric("最大可买手数", f"{max_hands} 手 ({buyable_shares} 股)")
                        st.metric("预计花费", f"{cost:.2f} 元")
                        st.metric("剩余资金", f"{balance:.2f} 元")
                    else:
                        st.error("获取到的价格无效")
                else:
                    st.error("无法获取实时价格")
            except Exception as e:
                st.error(f"计算出错: {e}")

    st.divider()
    st.subheader("🛡️ 风险对冲建议")
    st.info("基于当前市场环境，AI 为您推荐的对冲策略。")
    
    if st.button("获取近期对冲策略"):
        with st.spinner("正在分析市场风险并生成对冲建议..."):
            try:
                # 获取主要指数数据作为市场背景
                indices = get_market_indices()
                indices_str = indices.to_markdown() if not indices.empty else "无法获取指数数据"
                
                prompt = f"""
                Current Market Indices (A-Share):
                {indices_str}
                
                Please provide 3-5 hedging strategies or stock categories suitable for the current A-share market environment to reduce portfolio risk.
                
                Please structure your answer as follows:
                1. **Market Risk Assessment**: Analyze the current market sentiment and risk level (High/Medium/Low) based on the indices.
                2. **Hedging Strategies**:
                   *   **Strategy 1**: [Strategy Name]
                       *   **Logic**: Why this works in the current environment.
                       *   **Target Assets**: Specific sectors (e.g., Utilities, Banking), ETFs (e.g., Gold, Bond), or defensive stocks.
                       *   **Action**: Buy/Hold/Reduce exposure.
                   *   **Strategy 2**: ...
                   *   **Strategy 3**: ...
                
                Consider factors like market volatility, sector rotation, and macro conditions.
                Output format: Markdown. Please answer in Chinese.
                """
                response = call_llm(prompt, "You are a professional risk management expert specializing in the Chinese stock market.")
                st.markdown(response)
            except Exception as e:
                st.error(f"获取建议失败: {e}")

# --- 主程序逻辑 ---

def main():
    # 侧边栏导航
    st.sidebar.title("功能导航")
    page = st.sidebar.radio("前往", ["市场全景", "个股研究", "投资组合助手"])
    
    st.sidebar.markdown("---")
    st.sidebar.info("数据来源: AkShare\n\n仅供学习研究，不构成投资建议。")
    
    # 获取股票列表（缓存）
    stock_list = get_stock_list()
    
    if page == "市场全景":
        show_market_overview()
    elif page == "个股研究":
        show_stock_research(stock_list)
    elif page == "投资组合助手":
        show_portfolio_tool(stock_list)

if __name__ == "__main__":
    main()
