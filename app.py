import re

import pandas as pd
import streamlit as st
import yfinance as yf


SECTOR_POOLS = {
    "科技": {
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "NVDA": "NVIDIA",
        "GOOGL": "Alphabet",
        "META": "Meta Platforms",
        "AVGO": "Broadcom",
        "AMD": "AMD",
        "ORCL": "Oracle",
        "CRM": "Salesforce",
        "ADBE": "Adobe",
        "QCOM": "Qualcomm",
        "NOW": "ServiceNow",
    },
    "医疗": {
        "LLY": "Eli Lilly",
        "UNH": "UnitedHealth",
        "JNJ": "Johnson & Johnson",
        "ABBV": "AbbVie",
        "MRK": "Merck",
        "TMO": "Thermo Fisher",
        "ABT": "Abbott Laboratories",
        "AMGN": "Amgen",
        "GILD": "Gilead Sciences",
        "ISRG": "Intuitive Surgical",
    },
    "消费": {
        "AMZN": "Amazon",
        "TSLA": "Tesla",
        "WMT": "Walmart",
        "COST": "Costco",
        "HD": "Home Depot",
        "MCD": "McDonald's",
        "NKE": "Nike",
        "SBUX": "Starbucks",
        "PG": "Procter & Gamble",
        "PEP": "PepsiCo",
    },
    "金融": {
        "JPM": "JPMorgan Chase",
        "BAC": "Bank of America",
        "WFC": "Wells Fargo",
        "GS": "Goldman Sachs",
        "MS": "Morgan Stanley",
        "V": "Visa",
        "MA": "Mastercard",
        "AXP": "American Express",
        "BLK": "BlackRock",
        "SCHW": "Charles Schwab",
    },
    "工业": {
        "GE": "GE Aerospace",
        "CAT": "Caterpillar",
        "RTX": "RTX",
        "HON": "Honeywell",
        "UPS": "UPS",
        "BA": "Boeing",
        "DE": "Deere & Company",
        "LMT": "Lockheed Martin",
        "UNP": "Union Pacific",
        "ETN": "Eaton",
    },
    "能源": {
        "XOM": "Exxon Mobil",
        "CVX": "Chevron",
        "COP": "ConocoPhillips",
        "SLB": "SLB",
        "EOG": "EOG Resources",
        "MPC": "Marathon Petroleum",
        "PSX": "Phillips 66",
        "OXY": "Occidental Petroleum",
        "KMI": "Kinder Morgan",
    },
}

RISK_WEIGHTS = {
    "稳健": {"超额收益得分": 0.30, "低波动得分": 0.30, "回撤控制得分": 0.30, "趋势得分": 0.10},
    "均衡": {"超额收益得分": 0.45, "低波动得分": 0.20, "回撤控制得分": 0.20, "趋势得分": 0.15},
    "进取": {"超额收益得分": 0.60, "低波动得分": 0.10, "回撤控制得分": 0.10, "趋势得分": 0.20},
}


def parse_agent_request(text):
    """从自然语言中提取资金、风险、行业、数量和研究周期。"""
    compact_text = text.replace("，", ",").replace("。", ".")
    brief = {
        "amount": 100_000,
        "risk": "均衡",
        "sector": "科技",
        "candidate_count": 3,
        "period": "1y",
        "period_label": "近1年",
    }

    amount_wan = re.search(r"(\d+(?:\.\d+)?)\s*万(?:元)?", compact_text)
    amount_yuan = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*元", compact_text)
    if amount_wan:
        brief["amount"] = float(amount_wan.group(1)) * 10_000
    elif amount_yuan:
        brief["amount"] = float(amount_yuan.group(1).replace(",", ""))

    risk_text = re.sub(r"\s+", "", compact_text)
    high_risk_pattern = (
        r"风险(?:承受能力|偏好)?(?:为|是|:|：)?(?:较高|偏高|高)"
        r"|(?:较高|偏高|高)(?:的)?风险|进取|激进"
    )
    low_risk_pattern = (
        r"风险(?:承受能力|偏好)?(?:为|是|:|：)?(?:较低|偏低|低)"
        r"|(?:较低|偏低|低)(?:的)?风险|稳健|保守"
    )
    balanced_risk_pattern = (
        r"风险(?:承受能力|偏好)?(?:为|是|:|：)?(?:中等|适中|均衡)"
        r"|(?:中等|适中)(?:的)?风险|均衡"
    )

    if re.search(high_risk_pattern, risk_text):
        brief["risk"] = "进取"
    elif re.search(low_risk_pattern, risk_text):
        brief["risk"] = "稳健"
    elif re.search(balanced_risk_pattern, risk_text):
        brief["risk"] = "均衡"

    sector_keywords = {
        "科技": ["科技", "AI", "人工智能", "软件", "芯片", "半导体"],
        "医疗": ["医疗", "医药", "生物", "制药", "健康"],
        "消费": ["消费", "零售", "电商", "餐饮"],
        "金融": ["金融", "银行", "保险", "支付"],
        "工业": ["工业", "制造", "航空", "军工"],
        "能源": ["能源", "石油", "天然气"],
    }
    for sector, keywords in sector_keywords.items():
        if any(keyword in compact_text for keyword in keywords):
            brief["sector"] = sector
            break

    count_match = re.search(r"(\d+)\s*(?:只|支|个)(?:美股|股票|候选)?", compact_text)
    if count_match:
        brief["candidate_count"] = max(1, min(5, int(count_match.group(1))))

    month_match = re.search(r"(\d+)\s*个?月", compact_text)
    year_match = re.search(r"(\d+)\s*年", compact_text)
    if month_match:
        months = int(month_match.group(1))
        if months <= 3:
            brief["period"], brief["period_label"] = "3mo", "近3个月"
        elif months <= 6:
            brief["period"], brief["period_label"] = "6mo", "近6个月"
        else:
            brief["period"], brief["period_label"] = "1y", "近1年"
    elif year_match:
        years = int(year_match.group(1))
        if years <= 1:
            brief["period"], brief["period_label"] = "1y", "近1年"
        elif years <= 2:
            brief["period"], brief["period_label"] = "2y", "近2年"
        else:
            brief["period"], brief["period_label"] = "5y", "近5年"
    elif "短期" in compact_text or "短线" in compact_text:
        brief["period"], brief["period_label"] = "3mo", "近3个月"
    elif "长期" in compact_text or "长线" in compact_text:
        brief["period"], brief["period_label"] = "5y", "近5年"

    return brief


def get_universe(sector):
    if sector in SECTOR_POOLS:
        return SECTOR_POOLS[sector]

    combined = {}
    for pool in SECTOR_POOLS.values():
        combined.update(dict(list(pool.items())[:5]))
    return combined


@st.cache_data(ttl=3600, show_spinner=False)
def download_prices(symbols, period):
    return yf.download(
        list(symbols),
        period=period,
        auto_adjust=True,
        progress=False,
        threads=True,
    )


def analyze_universe(universe, brief):
    benchmark = "SPY"
    symbols = list(dict.fromkeys(list(universe.keys()) + [benchmark]))
    data = download_prices(tuple(symbols), brief["period"])

    if data.empty:
        raise ValueError("数据服务没有返回价格，请稍后重试。")

    if "Close" in data.columns:
        prices = data["Close"].copy()
    else:
        prices = data.copy()

    if prices.ndim == 1:
        prices = prices.to_frame(name=symbols[0])

    prices.columns = [str(column).upper() for column in prices.columns]
    prices = prices.sort_index().dropna(how="all")

    if benchmark not in prices.columns or prices[benchmark].dropna().empty:
        raise ValueError("没有取得标普500基准数据。")

    rows = []
    for ticker, company_name in universe.items():
        if ticker not in prices.columns or prices[ticker].dropna().empty:
            continue

        aligned = pd.concat(
            [prices[ticker], prices[benchmark]],
            axis=1,
            keys=["stock", "benchmark"],
        ).dropna()

        if len(aligned) < 40:
            continue

        stock_prices = aligned["stock"]
        benchmark_prices = aligned["benchmark"]
        daily_returns = stock_prices.pct_change().dropna()
        total_return = stock_prices.iloc[-1] / stock_prices.iloc[0] - 1
        benchmark_return = benchmark_prices.iloc[-1] / benchmark_prices.iloc[0] - 1
        annual_volatility = daily_returns.std() * (252 ** 0.5)
        drawdown = stock_prices / stock_prices.cummax() - 1
        max_drawdown = drawdown.min()
        moving_average = stock_prices.tail(min(50, len(stock_prices))).mean()
        trend = stock_prices.iloc[-1] / moving_average - 1

        rows.append(
            {
                "股票代码": ticker,
                "公司": company_name,
                "区间收益率": total_return,
                "相对SPY超额收益": total_return - benchmark_return,
                "年化波动率": annual_volatility,
                "最大回撤": max_drawdown,
                "短期趋势": trend,
            }
        )

    metrics = pd.DataFrame(rows)
    if metrics.empty:
        raise ValueError("候选池没有足够的数据完成研究。")

    metrics["超额收益得分"] = metrics["相对SPY超额收益"].rank(pct=True) * 100
    metrics["低波动得分"] = metrics["年化波动率"].rank(pct=True, ascending=False) * 100
    metrics["回撤控制得分"] = metrics["最大回撤"].rank(pct=True) * 100
    metrics["趋势得分"] = metrics["短期趋势"].rank(pct=True) * 100

    weights = RISK_WEIGHTS[brief["risk"]]
    metrics["Agent评分"] = sum(
        metrics[score_name] * weight for score_name, weight in weights.items()
    )

    metrics = metrics.sort_values("Agent评分", ascending=False).reset_index(drop=True)
    metrics.insert(0, "排名", range(1, len(metrics) + 1))

    # 风险偏好不仅改变权重，也会应用一道风险约束。
    if brief["risk"] == "稳健":
        eligible = metrics[
            (metrics["年化波动率"] <= metrics["年化波动率"].quantile(0.60))
            & (metrics["最大回撤"] >= metrics["最大回撤"].quantile(0.35))
        ]
        policy = "优先保留波动和回撤较低的股票"
    elif brief["risk"] == "均衡":
        eligible = metrics[
            metrics["年化波动率"] <= metrics["年化波动率"].quantile(0.85)
        ]
        policy = "在收益与风险之间保持平衡，并排除极端高波动股票"
    else:
        eligible = metrics
        policy = "更重视超额收益和趋势，同时接受更高波动"

    if len(eligible) < brief["candidate_count"]:
        eligible = metrics
        policy += "；因通过约束的股票不足，使用风险加权评分补足候选"

    candidates = eligible.head(brief["candidate_count"]).copy().reset_index(drop=True)

    chart_symbols = list(candidates["股票代码"]) + [benchmark]
    chart_prices = prices[[symbol for symbol in chart_symbols if symbol in prices.columns]].copy()
    normalized = chart_prices.copy()
    for symbol in normalized.columns:
        clean = normalized[symbol].dropna()
        if not clean.empty:
            normalized[symbol] = normalized[symbol] / clean.iloc[0] * 100
    normalized = normalized.rename(columns={benchmark: "SPY（标普500基准）"})

    return {
        "brief": brief,
        "universe_size": len(universe),
        "analyzed_size": len(metrics),
        "metrics": metrics,
        "candidates": candidates,
        "normalized": normalized,
        "weights": weights,
        "policy": policy,
        "data_date": prices.index.max().strftime("%Y-%m-%d"),
    }


def build_candidate_notes(candidate, metrics):
    median_volatility = metrics["年化波动率"].median()
    median_drawdown = metrics["最大回撤"].median()
    reasons = []
    risks = []

    if candidate["相对SPY超额收益"] > 0:
        reasons.append(f'所选周期跑赢SPY {candidate["相对SPY超额收益"]:.2%}')
    else:
        risks.append(f'所选周期跑输SPY {abs(candidate["相对SPY超额收益"]):.2%}')

    if candidate["年化波动率"] <= median_volatility:
        reasons.append("波动率低于候选池中位数")
    else:
        risks.append("波动率高于候选池中位数")

    if candidate["最大回撤"] >= median_drawdown:
        reasons.append("历史回撤控制优于候选池中位数")
    else:
        risks.append("历史最大回撤较深")

    if candidate["短期趋势"] > 0:
        reasons.append("当前价格位于近50个交易日均价上方")
    else:
        risks.append("当前价格位于近50个交易日均价下方")

    if not reasons:
        reasons.append("在当前风险权重下，综合相对排名靠前")
    if not risks:
        risks.append("历史数据无法覆盖突发事件和未来基本面变化")

    return reasons, risks


st.set_page_config(
    page_title="Yao analysis",
    page_icon="🧭",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp { background: #f6f8fb; }
    .agent-hero {
        padding: 2.2rem 2.4rem;
        border-radius: 22px;
        color: white;
        background: linear-gradient(125deg, #101b3a 0%, #173a6f 55%, #146c73 100%);
        box-shadow: 0 16px 40px rgba(16, 27, 58, 0.16);
        margin-bottom: 1.25rem;
    }
    .agent-badge {
        display: inline-block;
        padding: 0.35rem 0.7rem;
        border-radius: 999px;
        background: rgba(255,255,255,0.14);
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        margin-bottom: 0.9rem;
    }
    .agent-hero h1 { margin: 0; font-size: 2.35rem; }
    .agent-hero p { margin: 0.75rem 0 0; color: #d9e7ff; font-size: 1.05rem; }
    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #e3e8f0;
        padding: 1rem;
        border-radius: 14px;
    }
    div[data-testid="stForm"] {
        background: white;
        border: 1px solid #e3e8f0;
        border-radius: 18px;
        padding: 0.8rem 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="agent-hero">
        <div class="agent-badge">YAO RESEARCH AGENT · V1</div>
        <h1>Yao analysis</h1>
        <p>用一句话描述目标，由 Agent 自主建立股票池、执行风险约束并给出研究候选。</p>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Agent 工作原则")
    st.write("1. 理解资金、风险、行业和周期")
    st.write("2. 自主选择行业候选池")
    st.write("3. 与SPY比较并执行风险约束")
    st.write("4. 输出候选、原因和主要风险")
    st.divider()
    st.caption("当前版本使用历史价格和风险数据。下一版本将加入估值、盈利和现金流。")

st.subheader("把研究任务交给 Agent")
with st.form("agent_request_form"):
    request_text = st.text_area(
        "用自然语言描述你的目标",
        value="我有10万元，风险偏好中等，比较看好科技行业，计划持有1年，帮我找3只值得进一步研究的美股。",
        height=120,
        help="目前支持识别资金、稳健/均衡/进取风险、行业、候选数量和研究周期。",
    )
    st.caption("修改任务后，请再次点击下面的按钮，Agent 才会重新理解并生成新结果。")
    submitted = st.form_submit_button(
        "启动 Yao Agent",
        type="primary",
        use_container_width=True,
    )

if submitted:
    brief = parse_agent_request(request_text)
    universe = get_universe(brief["sector"])

    try:
        with st.status("Yao Agent 正在执行研究任务……", expanded=True) as agent_status:
            agent_status.write("✓ 已理解用户目标和风险偏好")
            agent_status.write(f'✓ 已建立{brief["sector"]}行业候选池，共 {len(universe)} 只股票')
            agent_status.write("⏳ 正在获取行情并与标普500基准比较")
            result = analyze_universe(universe, brief)
            agent_status.write("✓ 已完成收益、波动、回撤和趋势评估")
            agent_status.write("✓ 已应用风险约束并生成候选解释")
            agent_status.update(label="Yao Agent 已完成研究任务", state="complete", expanded=False)

        result["request_text"] = request_text
        st.session_state["agent_result"] = result
    except Exception as error:
        st.error("Agent 暂时无法完成研究，请检查网络后重试。")
        st.caption(f"详细信息：{error}")

if "agent_result" in st.session_state:
    result = st.session_state["agent_result"]
    brief = result["brief"]
    candidates = result["candidates"]
    metrics = result["metrics"]

    st.subheader("Agent 对任务的理解")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("研究资金", f'¥{brief["amount"]:,.0f}')
    col2.metric("风险偏好", brief["risk"])
    col3.metric("目标行业", brief["sector"])
    col4.metric("研究周期", brief["period_label"])
    st.caption(
        f'Agent 从 {result["universe_size"]} 只行业股票中成功分析 {result["analyzed_size"]} 只；'
        f'价格数据截至 {result["data_date"]}。资金金额仅用于理解任务，不直接改变公司质量排名。'
    )

    st.subheader(f'Agent 决策：{len(candidates)} 只值得进一步研究的候选')
    st.info(f'本次风险策略：{result["policy"]}。')

    for index, candidate in candidates.iterrows():
        reasons, risks = build_candidate_notes(candidate, metrics)
        with st.container(border=True):
            st.markdown(
                f'### #{index + 1} · {candidate["股票代码"]} — {candidate["公司"]}'
            )
            score_col, return_col, excess_col, drawdown_col = st.columns(4)
            score_col.metric("Agent评分", f'{candidate["Agent评分"]:.1f} / 100')
            return_col.metric("区间收益", f'{candidate["区间收益率"]:.2%}')
            excess_col.metric("跑赢SPY", f'{candidate["相对SPY超额收益"]:+.2%}')
            drawdown_col.metric("最大回撤", f'{candidate["最大回撤"]:.2%}')

            reason_col, risk_col = st.columns(2)
            with reason_col:
                st.markdown("**入选原因**")
                for reason in reasons:
                    st.write(f"- {reason}")
            with risk_col:
                st.markdown("**主要风险**")
                for risk in risks:
                    st.write(f"- {risk}")

    with st.expander("查看 Agent 的完整排名和数据依据"):
        ranking_columns = [
            "排名",
            "股票代码",
            "公司",
            "Agent评分",
            "区间收益率",
            "相对SPY超额收益",
            "年化波动率",
            "最大回撤",
            "短期趋势",
        ]
        st.dataframe(
            metrics[ranking_columns].style.format(
                {
                    "Agent评分": "{:.1f}",
                    "区间收益率": "{:.2%}",
                    "相对SPY超额收益": "{:+.2%}",
                    "年化波动率": "{:.2%}",
                    "最大回撤": "{:.2%}",
                    "短期趋势": "{:+.2%}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("**候选与SPY走势对照（起始值 = 100）**")
        st.line_chart(result["normalized"])

    with st.expander("查看 Agent 的评分规则"):
        weights = result["weights"]
        st.write(
            f'- 超额收益：{weights["超额收益得分"]:.0%}\n'
            f'- 低波动：{weights["低波动得分"]:.0%}\n'
            f'- 回撤控制：{weights["回撤控制得分"]:.0%}\n'
            f'- 短期趋势：{weights["趋势得分"]:.0%}'
        )
        st.caption("评分是本次行业候选池内的相对排名；改变行业、周期或风险偏好会改变结果。")

    st.warning(
        "Agent 输出的是研究候选，不是买入或卖出指令。历史表现不代表未来收益；"
        "在采取行动前仍需检查公司财报、估值、重大事件和个人承受能力。"
    )

st.divider()
st.caption("Yao analysis · Autonomous research, explainable decisions · 不构成投资建议")
