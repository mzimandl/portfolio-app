"""The terms the app uses and how to read them."""

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class Term:
    name: str
    meaning: str
    reading: str = ""  # how to read it, and what to watch out for
    where: str = ""  # the pages that show it


SECTIONS: dict[str, list[Term]] = {
    "Your money": [
        Term(
            "Value",
            "What you hold is worth today: quantity × the latest price × the exchange rate "
            "of the day. For accounts valued by hand, the last value you entered plus the "
            "deposits and minus the withdrawals since.",
            "Missing prices or rates are pointed out above the totals; such instruments "
            "count as zero there.",
            "Overview, Charts",
        ),
        Term(
            "Cost",
            "What the units you still hold cost you, at the exchange rates of the days you "
            "bought them.",
            "Sales use up the oldest units first (FIFO), so after a sale the cost is that of "
            "the newer units that are left.",
            "Overview",
        ),
        Term(
            "FIFO",
            "First in, first out: a sale takes the units bought first.",
            "It decides which purchases a sale realises, and so the realised profit and the "
            "holding period for taxes.",
        ),
        Term(
            "Unrealised profit",
            "Value − cost of what you still hold. A profit you would make by selling today.",
            "The percentage beside it is relative to the cost.",
            "Overview",
        ),
        Term(
            "From price, from exchange rate, staking rewards",
            "The unrealised profit split by where it came from. From exchange rate: what "
            "your units cost in their own currency at today's rate, minus what you paid. "
            "Staking rewards: the free units you still hold, at today's price. From price: "
            "the rest.",
            "A share priced in EUR can lose in EUR and still gain in CZK when the euro "
            "strengthened, and the other way round.",
            "Overview",
        ),
        Term(
            "Realised profit",
            "On units sold: what you got for them − what they had cost.",
            "Units lost (sold at price 0) count their cost as a loss.",
            "Overview (Sales)",
        ),
        Term(
            "Profit, net profit",
            "Profit = unrealised + realised. Net profit = profit + dividends − fees.",
            "Net profit is what the investments really earned you in total.",
            "Overview, Charts",
        ),
        Term(
            "Still invested",
            "Buys and deposits minus sales and withdrawals, so far.",
            "Value above it means a profit; the gap between the two lines in Charts is the profit.",
            "Charts",
        ),
    ],
    "Returns": [
        Term(
            "Return (time-weighted)",
            "How the investments themselves did, as if no money had been added or taken "
            "out. Days are chained one after another.",
            "Use it to compare with a fund or the benchmark. A small account early on can "
            "make it large: +100 % on 10 000 counts as much as on 1 000 000. Not per year.",
            "Performance",
        ),
        Term(
            "Yearly return on your money (XIRR)",
            "The yearly interest rate that would turn your payments, on the days you made "
            "them, into what you have today.",
            "This is what you actually earned on your money. It is lower than the "
            "time-weighted return when you added a lot of money just before a fall. Shown "
            "for periods of three months or more.",
            "Performance",
        ),
        Term(
            "Deepest drop (drawdown)",
            "The largest fall of the time-weighted return from a high to a low in the "
            "period. 'Now below the high' is how far it is under its best point today.",
            "It shows how bad it got, which says more about risk than ups and downs on "
            "average. Measured on the return, so new money does not hide a fall.",
            "Performance, Charts",
        ),
        Term(
            "By month",
            "The time-weighted return of each calendar month.",
            "Green months gained, red ones lost.",
            "Performance",
        ),
        Term(
            "Part of the profit",
            "An instrument's net profit as a share of the net profit of everything shown.",
            "Which holdings made the result. Empty when the whole selection lost money.",
            "Performance",
        ),
        Term(
            "Inflation",
            "How much consumer prices rose in the period, by Eurostat's harmonised index of "
            "the country set in the config file (CZ by default).",
            "The index comes out about two weeks after each month; until then prices count "
            "as unchanged since the last month published, and the page says so.",
            "Performance",
        ),
        Term(
            "Return after inflation (real return)",
            "What a return is worth in today's prices: (1 + return) / (1 + inflation) − 1. "
            "10 % with 4 % inflation is 5.8 %.",
            "This is what you can buy more than before. Close to zero: the money only kept "
            "its value, which is common for savings accounts.",
            "Performance",
        ),
        Term(
            "Benchmark return",
            "What holding the benchmark (an index fund, set in the config file) for the "
            "whole period would have returned, dividends reinvested.",
            "Compare it with the time-weighted return.",
            "Performance",
        ),
        Term(
            "Your money in the benchmark, ahead or behind",
            "The same amounts paid in and taken out on the same days, but put into the "
            "benchmark. 'Ahead by' is your value today minus what that would be worth.",
            "The fairest comparison of your choices with simply buying the index. The "
            "benchmark side pays no fees or taxes, so it has a small advantage.",
            "Performance",
        ),
    ],
    "Valuation of a company": [
        Term(
            "EPS",
            "Earnings per share: the company's net profit divided by its number of shares.",
            "All the ratios below compare the price of one share with such a per-share number.",
            "Fundamentals",
        ),
        Term(
            "Last twelve months (TTM)",
            "The sum of the last four quarters, or the last year when quarters are missing.",
            "Used for earnings and revenue, so a ratio is not thrown off by one strong or "
            "weak quarter.",
            "Fundamentals",
        ),
        Term(
            "P/E",
            "Price / earnings per share of the last twelve months. How many years of today's "
            "profit the price pays for.",
            "Lower is cheaper. Around 10–20 is common, growing companies are often higher, "
            "banks and utilities lower. Empty when the company made a loss. A one-off gain "
            "or loss distorts it.",
            "Fundamentals",
        ),
        Term(
            "Typical P/E",
            "The median of the daily P/E over all days it could be worked out (from 'Since' "
            "to today).",
            "Today's P/E below it: the share is cheaper than it used to be, relative to its "
            "profit. The history is about 15 years for US companies (SEC), only about 3 for "
            "others, so compare a share with itself, not with another one.",
            "Fundamentals",
        ),
        Term(
            "Forward P/E",
            "Price / the profit analysts expect for the next year (by Yahoo).",
            "Lower than the P/E: analysts expect the profit to grow; higher: to fall; "
            "negative: a loss expected. It is a forecast and often wrong, and small "
            "companies have none.",
            "Fundamentals",
        ),
        Term(
            "P/B",
            "Price / book value per share; book value is what the company owns minus what "
            "it owes (equity).",
            "Around 1 means the share costs what the company owns. Useful for banks and "
            "industry; for software or brands the book value says little, so P/B is high.",
            "Fundamentals",
        ),
        Term(
            "P/S",
            "Price / revenue per share of the last twelve months.",
            "Works also for companies without a profit yet. Compare within one field: shops "
            "with thin margins have a low P/S, software a high one.",
            "Fundamentals",
        ),
        Term(
            "EV/EBITDA",
            "The value of the whole company including its debt (enterprise value: market "
            "value + debt − cash) / its operating profit before interest, taxes and "
            "depreciation (EBITDA). By Yahoo.",
            "Unlike P/E it counts debt, so it compares companies financed differently. "
            "Around 6–10 is common, depending on the field. Meaningless for banks and "
            "insurers, and when negative (an operating loss).",
            "Fundamentals",
        ),
        Term(
            "Market cap",
            "The price of all the company's shares together.",
            "The size of the company as the market values it.",
            "Fundamentals",
        ),
        Term(
            "Depositary receipt, share class",
            "A traded unit that is not one share of the company: a receipt can stand for a "
            "quarter of a share, a class B share for 1/1500 of a class A one.",
            "The app works out the ratio from the market value Yahoo reports and lists it "
            "on the page, so the ratios are per unit you hold.",
            "Fundamentals",
        ),
    ],
    "Dividends": [
        Term(
            "Dividend yield",
            "Dividends of the last twelve months / today's price.",
            "What the share pays out each year, as a percentage of what it costs now. A very "
            "high yield often means the price fell because a cut is expected.",
            "Fundamentals, Dividends",
        ),
        Term(
            "Yield on cost",
            "Dividends of the last twelve months / what you paid for the shares.",
            "What your own purchase pays you. It grows when a company raises its dividend.",
            "Dividends",
        ),
        Term(
            "Expected dividends",
            "What the price data says was paid for the units you held, before tax.",
            "More expected than recorded can mean a dividend you forgot to enter. Payments "
            "come some weeks after the date in the price data.",
            "Dividends, Checks",
        ),
    ],
    "Allocation": [
        Term(
            "Share",
            "An instrument's, type's or currency's part of the value of all investments.",
            "The currency is the one the instrument is priced in: an ETF in EUR holding US "
            "shares counts as EUR.",
            "Overview",
        ),
        Term(
            "Sector, country",
            "What a company does (Technology, Utilities, …) and where it is based, as Yahoo "
            "says. The Overview adds up the value by both.",
            "Funds and coins have none of their own and are shown by type in brackets; set "
            "theirs in Settings. A world fund's own spread is not looked into.",
            "Overview, Settings",
        ),
        Term(
            "Target, to be on target, buy now",
            "Target: the share you want a type to have (set in Settings). To be on target: "
            "what to buy (negative: how much too many). Buy now: how to split the new money "
            "you enter.",
            "New money goes to the types furthest below their target; nothing is sold.",
            "Overview",
        ),
    ],
    "Taxes": [
        Term(
            "Held longer, held shorter",
            "Units held longer than the holding period in the config file (3 years by "
            "default) and the rest.",
            "A sale of units held longer counts as exempt. 'Next' is the day the oldest of "
            "the others gets there.",
            "Taxes",
        ),
        Term(
            "Within the limit",
            "Whether the year's proceeds of all sales stay under the limit in the config "
            "file (100 000 by default), counted apart for securities and crypto.",
            "Within it, all sales of the year count as exempt.",
            "Taxes",
        ),
        Term(
            "Profit not exempt",
            "The profit on units held shorter, in a year over the limit.",
            "A starting point, not a tax return: fees are not deducted, the rates are the "
            "ones you entered, and the same rules are applied to every year.",
            "Taxes",
        ),
    ],
    "Exchange rates for taxes": [
        Term(
            "ČNB rate",
            "The exchange rate the Czech National Bank publishes each working day. A Czech "
            "tax return converts foreign money with it.",
            "For a weekend or holiday the last rate published before it applies.",
            "Taxes",
        ),
        Term(
            "Unified rate (jednotný kurz)",
            "One rate per currency for a whole year: the average of the ČNB rates valid on "
            "the last day of each month, as the Financial Administration publishes it.",
            "You use either the daily rates or the unified ones for the whole year. A "
            "purchase from an earlier year counts at that year's unified rate. Known only "
            "once the year is over.",
            "Taxes",
        ),
    ],
    "Data": [
        Term(
            "Split",
            "A company divides each share into several (10 for 1: ten new shares for one "
            "old). Nothing is gained or lost.",
            "Downloaded prices are converted to today's shares. When a split is reported, "
            "the app asks whether your quantities need it.",
            "every page, when one is pending",
        ),
        Term(
            "Checks",
            "Records that look wrong or out of date: old prices, trade prices or rates far "
            "from the market, tiny leftovers, missing dividends.",
            "A finding may be fine as it is: mark it as checked and it stays hidden until "
            "the record changes.",
            "Checks",
        ),
    ],
}


def _matches(term: Term, query: str) -> bool:
    text = " ".join((term.name, term.meaning, term.reading, term.where)).lower()
    return all(word in text for word in query.lower().split())


def render() -> None:
    st.title("Glossary")
    st.caption("What the numbers in this app mean and how to read them.")
    query = st.text_input("Search", placeholder="e.g. P/E, dividend, drop", key="glossary_q")
    found = 0
    for section, terms in SECTIONS.items():
        shown = [t for t in terms if not query or _matches(t, query)]
        if not shown:
            continue
        st.subheader(section)
        for term in shown:
            found += 1
            with st.container(border=True):
                st.markdown(f"**{term.name}**")
                st.write(term.meaning)
                if term.reading:
                    st.caption(term.reading)
                if term.where:
                    st.caption(f"Shown on: {term.where}")
    if not found:
        st.info("Nothing found. Try another word.")
