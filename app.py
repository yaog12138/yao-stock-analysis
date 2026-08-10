import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(
    page_title="Yao analysis",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Yao analysis")
st.write("比较不同美股的收益和风险，寻找值得进一步研究的候选股票。")

stock_codes = st.text_input(
    "请输入美股代码，用英文逗号分隔",
    value="AAPL, MSFT, NVDA",
)

period = st.selectbox(
    "选择分析时间",
    ["近3个月", "近6个月", "近1年", "近3年"],
)

if st.button("开始分析"):
    # 把用户输入的内容整理成股票代码列表。
    tickers = [code.strip().upper() for code in stock_codes.split(",") if code.strip()]

    if not tickers:
        st.warning("请至少输入一个股票代码。")
    elif len(tickers) > 10:
        st.warning("为了避免下载太慢，请一次最多分析10只股票。")
    else:
        benchmark = "SPY"
        download_symbols = list(dict.fromkeys(tickers + [benchmark]))

        period_map = {
            "近3个月": "3mo",
            "近6个月": "6mo",
            "近1年": "1y",
            "近3年": "3y",
        }

        with st.spinner("正在获取美股价格，请稍候……"):
            data = yf.download(
                download_symbols,
                period=period_map[period],
                auto_adjust=True,
                progress=False,
            )

        if data.empty:
            st.error("没有获取到数据，请检查股票代码或网络连接。")
        else:
            # yfinance 返回的数据可能包含多层表头，这里只取收盘价。
            if "Close" in data.columns:
                prices = data["Close"]
            else:
                prices = data

            if len(download_symbols) == 1 and prices.ndim == 1:
                prices = prices.to_frame(name=download_symbols[0])

            prices = prices.dropna(how="all")

            if benchmark not in prices.columns or prices[benchmark].dropna().empty:
                st.error("没有获取到标普500基准数据，请稍后重试。")
                st.stop()

            # 把每只股票的起始价格统一设为100，方便公平比较涨跌表现。
            normalized_prices = prices.copy()
            for ticker in normalized_prices.columns:
                first_price = normalized_prices[ticker].dropna().iloc[0]
                normalized_prices[ticker] = normalized_prices[ticker] / first_price * 100

            st.success("价格数据获取成功！")
            st.subheader("与标普500基准比较（起始值 = 100）")
            chart_prices = normalized_prices.rename(
                columns={benchmark: "SPY（标普500基准）"}
            )
            st.line_chart(chart_prices)
            st.caption("图表只用于历史表现比较，历史表现不代表未来收益。")

            # 计算每只股票的收益和风险指标。
            metrics = []
            for ticker in tickers:
                if ticker not in prices.columns or prices[ticker].dropna().empty:
                    continue

                # 只比较股票和基准都有价格的交易日。
                aligned_prices = pd.concat(
                    [prices[ticker], prices[benchmark]],
                    axis=1,
                    keys=["stock", "benchmark"],
                ).dropna()

                if len(aligned_prices) < 2:
                    continue

                ticker_prices = aligned_prices["stock"]
                benchmark_prices = aligned_prices["benchmark"]
                daily_returns = ticker_prices.pct_change().dropna()

                total_return = ticker_prices.iloc[-1] / ticker_prices.iloc[0] - 1
                benchmark_return = benchmark_prices.iloc[-1] / benchmark_prices.iloc[0] - 1
                excess_return = total_return - benchmark_return
                annual_volatility = daily_returns.std() * (252 ** 0.5)
                drawdown = ticker_prices / ticker_prices.cummax() - 1
                max_drawdown = drawdown.min()

                metrics.append(
                    {
                        "股票代码": ticker,
                        "区间收益率": total_return,
                        "相对SPY超额收益": excess_return,
                        "年化波动率": annual_volatility,
                        "最大回撤": max_drawdown,
                    }
                )

            metrics_df = pd.DataFrame(metrics)

            if metrics_df.empty:
                st.error("没有足够的数据计算指标，请检查股票代码。")
                st.stop()

            spy_prices = prices[benchmark].dropna()
            spy_return = spy_prices.iloc[-1] / spy_prices.iloc[0] - 1

            st.subheader("收益与风险对比")
            st.info(f"同期标普500 ETF（SPY）区间收益率：{spy_return:.2%}")
            st.dataframe(
                metrics_df.style.format(
                    {
                        "区间收益率": "{:.2%}",
                        "相对SPY超额收益": "{:+.2%}",
                        "年化波动率": "{:.2%}",
                        "最大回撤": "{:.2%}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            best_return = metrics_df.loc[metrics_df["区间收益率"].idxmax()]
            lowest_volatility = metrics_df.loc[metrics_df["年化波动率"].idxmin()]
            smallest_drawdown = metrics_df.loc[metrics_df["最大回撤"].idxmax()]

            col1, col2, col3 = st.columns(3)
            col1.metric(
                "区间收益最高",
                best_return["股票代码"],
                f'{best_return["区间收益率"]:.2%}',
            )
            col2.metric(
                "波动率最低",
                lowest_volatility["股票代码"],
                f'{lowest_volatility["年化波动率"]:.2%}',
                delta_color="off",
            )
            col3.metric(
                "最大回撤最小",
                smallest_drawdown["股票代码"],
                f'{smallest_drawdown["最大回撤"]:.2%}',
                delta_color="off",
            )

            with st.expander("这些指标是什么意思？"):
                st.write("**区间收益率**：在所选时间内，股票总共上涨或下跌了多少。")
                st.write("**相对SPY超额收益**：股票收益率减去同期标普500 ETF收益率；正数表示跑赢基准。")
                st.write("**年化波动率**：价格波动的程度；数值越高，通常表示不确定性越大。")
                st.write("**最大回撤**：这段时间内，从某个高点到之后低点的最大跌幅。")

            # 第一阶段评分：比较用户输入的股票，不代表对全市场的排名。
            metrics_df["收益得分"] = (
                metrics_df["相对SPY超额收益"].rank(pct=True) * 100
            )
            metrics_df["低波动得分"] = (
                metrics_df["年化波动率"].rank(pct=True, ascending=False) * 100
            )
            metrics_df["回撤控制得分"] = (
                metrics_df["最大回撤"].rank(pct=True) * 100
            )
            metrics_df["综合评分"] = (
                metrics_df["收益得分"] * 0.50
                + metrics_df["低波动得分"] * 0.25
                + metrics_df["回撤控制得分"] * 0.25
            )

            ranking_df = metrics_df.sort_values("综合评分", ascending=False).reset_index(
                drop=True
            )
            ranking_df.insert(0, "排名", range(1, len(ranking_df) + 1))

            st.subheader("第一阶段综合评分")
            st.caption(
                "评分权重：相对SPY收益50% + 低波动25% + 回撤控制25%。"
                "分数只用于比较本次输入的股票。"
            )
            st.dataframe(
                ranking_df[
                    [
                        "排名",
                        "股票代码",
                        "综合评分",
                        "收益得分",
                        "低波动得分",
                        "回撤控制得分",
                    ]
                ].style.format(
                    {
                        "综合评分": "{:.1f}",
                        "收益得分": "{:.1f}",
                        "低波动得分": "{:.1f}",
                        "回撤控制得分": "{:.1f}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            st.bar_chart(
                ranking_df.set_index("股票代码")["综合评分"],
                horizontal=True,
            )

            candidate = ranking_df.iloc[0]
            st.success(
                f'本次值得进一步研究的候选：{candidate["股票代码"]} '
                f'（综合评分 {candidate["综合评分"]:.1f}）'
            )
            st.write(
                f'- 相对SPY超额收益：{candidate["相对SPY超额收益"]:+.2%}'
            )
            st.write(f'- 年化波动率：{candidate["年化波动率"]:.2%}')
            st.write(f'- 最大回撤：{candidate["最大回撤"]:.2%}')
            st.warning(
                "这只是基于历史价格的第一阶段筛选。加入估值、盈利增长、负债和现金流后，"
                "才适合形成更完整的研究结论。"
            )

st.divider()
st.caption("仅供学习和数据分析，不构成投资建议。")
