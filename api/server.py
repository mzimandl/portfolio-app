import threading
from dataclasses import dataclass, asdict
from collections import defaultdict
import os
import sys
import time
import datetime
import json
import sqlite3
import webbrowser

import requests
import sanic
import sanic.response
import yfinance
import polars as pl

FILE_PATH = os.path.dirname(__file__)

yfinance_fx = {
    ('USD', 'CZK'): 'CZK=X'
}
def get_yfinance_fx_ticker(from_curr: str, to_curr: str):
    try:
        return yfinance_fx[(from_curr, to_curr)]
    except KeyError:
        return f'{from_curr}{to_curr}=X'

@dataclass
class Config:
    db: str
    base_currency: str
    language_locale: str

with open(os.path.join(FILE_PATH, '../config.json')) as f:
    config = Config(**json.load(f))

app = sanic.Sanic("PortfolioApp")
app.static('/assets', os.path.join(FILE_PATH, '../build/assets'))
db = sqlite3.connect(os.path.join(FILE_PATH, config.db))
db.row_factory = sqlite3.Row


class PDataFrame:
    df: pl.DataFrame
    query: str

    def __init__(self, query: str):
        self.query = query
        self.reload()

    def reload(self):
        self.df = pl.read_database(self.query, db)


@dataclass
class Dfs:
    instruments: PDataFrame
    trades: PDataFrame
    deposits: PDataFrame
    values: PDataFrame
    dividends: PDataFrame
    staking: PDataFrame
    historical: PDataFrame
    fx: PDataFrame


dfs = Dfs(
    instruments=PDataFrame("SELECT ticker, currency, type, dividend_currency FROM instruments"),
    trades=PDataFrame("SELECT id, date, ticker, volume, price, fee, rate FROM trades"),
    deposits=PDataFrame("SELECT id, date, ticker, amount, fee FROM deposits"),
    values=PDataFrame("SELECT date, ticker, value FROM \"values\""),
    dividends=PDataFrame("SELECT id, date, ticker, dividend FROM dividends"),
    staking=PDataFrame("SELECT id, date, ticker, volume FROM staking"),
    historical=PDataFrame("SELECT date, ticker, open, high, low, close, dividends, splits FROM historical"),
    fx=PDataFrame("SELECT date, from_curr, to_curr, open, high, low, close FROM fx"),
)


@app.get("/config/get")
async def config_get(request:sanic.Request):
    return sanic.response.json(asdict(config))


@app.get("/data/last")
async def last(request:sanic.Request):
    last_data = {}
    cursor = db.cursor()
    cursor.execute('SELECT max(date) as last_historical FROM historical')
    last_data['historical'] = cursor.fetchone()['last_historical']
    cursor.execute('SELECT max(date) as fx_historical FROM fx')
    last_data['fx'] = cursor.fetchone()['fx_historical']
    cursor.execute('SELECT max(date) as last_value FROM "values"')
    last_data['manual_value'] = cursor.fetchone()['last_value']
    return sanic.response.json(last_data)


@app.get("/historical/update")
async def historical_update(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('''
        SELECT tt.ticker, min(date) as first_date, it.evaluation, it.eval_param
        FROM trades AS tt
        JOIN instruments AS it ON it.ticker = tt.ticker
        GROUP BY tt.ticker
    ''')
    first_trades = {
        d['ticker']: {
            'first_date': datetime.datetime(*tuple(int(t) for t in d['first_date'].split('-'))),
            'evaluation': d['evaluation'],
            'eval_param': json.loads(d['eval_param']) if d['evaluation'] == 'http' else d['eval_param'],
        } for d in cursor}

    sql = '''
        INSERT OR IGNORE INTO historical(date, ticker, open, high, low, close, dividends, splits) values (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, ticker)
        DO UPDATE SET open = excluded.open, high = excluded.high, low = excluded.low, close = excluded.close, dividends = excluded.dividends, splits = excluded.splits
    '''
    for ticker, ticker_info in first_trades.items():
        try:
            if ticker_info['evaluation'] == 'yfinance':
                yticker = yfinance.Ticker(ticker_info['eval_param'] if ticker_info['eval_param'] else ticker)
                df = yticker.history(start=ticker_info['first_date'])
                cursor.executemany(sql, [
                    (date.strftime('%Y-%m-%d'), ticker, row['Open'], row['High'], row['Low'], row['Close'], row['Dividends'], row['Stock Splits'])
                    for date, row in df.iterrows()
                ])

            elif ticker_info['evaluation'] == 'http':
                resp = requests.get(ticker_info['eval_param']['url'])
                date_key = ticker_info['eval_param']['date']
                open_key = ticker_info['eval_param'].get('open')
                close_key = ticker_info['eval_param'].get('close')
                high_key = ticker_info['eval_param'].get('high')
                low_key = ticker_info['eval_param'].get('low')
                dvd_key = ticker_info['eval_param'].get('dividends')
                split_key = ticker_info['eval_param'].get('stock_splits')
                cursor.executemany(sql, [
                    (
                        d[date_key],
                        ticker,
                        d.get(open_key, 0),
                        d.get(high_key, 0),
                        d.get(low_key, 0),
                        d.get(close_key, 0),
                        d.get(dvd_key, 0),
                        d.get(split_key, 0),
                    )
                    for d in resp.json()
                ])

            db.commit()
        except Exception as e:
            print("Failed to download data", ticker, ticker_info, e)

    dfs.historical.reload()
    return sanic.response.json({'success': True})


@app.get("/fx/update")
async def fx_update(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('SELECT min(date) as first_trade FROM trades')
    first_trade = tuple(int(t) for t in (cursor.fetchone())['first_trade'].split('-'))

    cursor = db.cursor()
    cursor.execute('SELECT DISTINCT currency FROM instruments')
    currencies = [d['currency'] for d in cursor]

    sql = '''
        INSERT OR IGNORE INTO fx(date, from_curr, to_curr, open, high, low, close) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, from_curr, to_curr)
        DO UPDATE SET open = excluded.open, high = excluded.high, low = excluded.low, close = excluded.close
    '''
    for currency in currencies:
        if currency != config.base_currency:
            ticker = get_yfinance_fx_ticker(currency, config.base_currency)
            yticker = yfinance.Ticker(ticker)
            df = yticker.history(start=datetime.datetime(*first_trade))
            cursor.executemany(sql, [
                (date.strftime('%Y-%m-%d'), currency, config.base_currency, row['Open'], row['High'], row['Low'], row['Close'])
                for date, row in df.iterrows()
            ])
            db.commit()

    dfs.fx.reload()
    return sanic.response.json({'success': True})


@app.get("/overview/get")
async def overview(request:sanic.Request):  
    # valuables
    last_val_df = dfs.values.df.sort("date").group_by("ticker").agg(
        pl.col("date").last(),
        pl.col("value").last(),
    )

    valuables = (
        dfs.deposits.df.sort("date").join(last_val_df, "ticker", "left")
        .group_by("ticker").agg(
            pl.col("date").last(),
            pl.col("amount").filter(pl.col("amount") > 0).sum().alias("investment"),
            -pl.col("amount").filter(pl.col("amount") < 0).sum().alias("withdraw"),
            (pl.col("value").last() + pl.col("amount").filter(pl.col("date") >= pl.col("date_right")).sum()).alias("value"),
            pl.col("fee").sum().alias("fees"),
        )
        .join(dfs.instruments.df, "ticker", "left")
        .select(
            "ticker", "type", "currency", "investment", "withdraw", "fees", "value",
            (pl.col("withdraw") + pl.col("value") - pl.col("investment")).alias("total_profit")
        )
    )

    # tradables
    last_price = dfs.historical.df\
        .sort("date")\
        .group_by("ticker")\
        .agg(pl.col("close").last().alias("last_price"))

    last_fx = dfs.fx.df\
        .sort("date")\
        .group_by(["from_curr", "to_curr"])\
        .agg(pl.col("close").last().alias("fx_rate"))
    
    total_dividends_df = dfs.dividends.df\
        .group_by("ticker")\
        .agg(pl.col("dividend").sum().alias("dividends"))
    
    total_staking_df = dfs.staking.df\
        .group_by("ticker")\
        .agg(pl.col("volume").sum().alias("staking_volume"))
    
    tradeables = (
        dfs.trades.df
        .group_by("ticker").agg(
            pl.col("volume").sum().alias("trade_volume"),
            pl.col("volume").filter(pl.col("volume") > 0).sum().alias("buy_volume"),
            (pl.col("volume") * pl.col("price")).filter(pl.col("volume") > 0).sum().alias("fx_investment"),
            (pl.col("volume") * pl.col("price") / pl.col("rate")).filter(pl.col("volume") > 0).sum().alias("investment"),
            -(pl.col("volume") * pl.col("price") / pl.col("rate")).filter(pl.col("volume") < 0).sum().alias("withdraw"),
            pl.col("fee").sum().alias("fees"),
        )
        .join(last_price, "ticker", "left")
        .join(dfs.instruments.df, "ticker", "left")
        .join(last_fx.filter(pl.col("to_curr") == config.base_currency), left_on="currency", right_on="from_curr", how="left").with_columns(pl.col("fx_rate").fill_null(1))
        .join(total_staking_df, "ticker", "left").with_columns(pl.col("staking_volume").fill_null(0))
        .with_columns((pl.col("trade_volume") + pl.col("staking_volume")).alias("volume"))
        .select(
            "ticker", "type", "currency", "dividend_currency", "last_price",
            "investment", "withdraw", "fees", "volume",
            pl.when(pl.col("buy_volume").gt(0)).then(pl.col("fx_investment") / pl.col("buy_volume")).otherwise(None).alias("average_price"),
            (pl.col("volume") * pl.col("last_price") * pl.col("fx_rate")).alias("value"),
            (pl.col("trade_volume") * pl.col("last_price") * pl.col("fx_rate")).alias("trade_value"),
            (pl.col("fx_investment") * pl.col("fx_rate") - pl.col("investment")).alias("fx_profit"),
            (pl.col("staking_volume") * pl.col("last_price") * pl.col("fx_rate")).alias("rewards"),
        )
        .with_columns((pl.col("value") + pl.col("withdraw") - pl.col("investment")).alias("total_profit"))
        .with_columns((pl.col("total_profit") - pl.col("rewards") - pl.col("fx_profit")).alias("value_profit"))
        .join(total_dividends_df, on="ticker", how="left")
    )

    overview = pl.concat([tradeables, valuables], how="diagonal").sort("ticker")
    return sanic.response.json(overview.to_dicts())


@app.get("/performance/get")
async def performance(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('''
        select
            substr(date, 1, 4) as year,
            max(date) as date,
            ticker,
            fee,
            investment,
            (case when evaluation='manual'
                THEN fx_price*(manual_value+(case when value_correction then value_correction else 0 end))
                ELSE fx_price*last_price*volume
            END) as value,
            (case when evaluation='manual'
                THEN fx_price*(manual_value+(case when value_correction then value_correction else 0 end))
                ELSE fx_price*last_price*volume
            END)-investment-fee as profit
        from (
            select
                dt.date,
                it.ticker,
                it.evaluation,
                sum(
                    (case when tt.volume then tt.volume else 1 end)*tt.price/
                    (case when tt.rate then tt.rate else 1 end)
                ) over (PARTITION BY it.ticker ORDER BY dt.date RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as investment,
                sum(tt.volume) over (PARTITION BY it.ticker ORDER BY dt.date RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as volume,
                (select close from historical where date <= dt.date and ticker = it.ticker order by date desc) as last_price,
                (case when it.currency = ? then 1 else
                    (select close from fx where from_curr = it.currency and to_curr = ? order by date desc)
                end) as fx_price,
                sum(tt.fee) over (PARTITION BY it.ticker ORDER BY dt.date RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as fee,
                (case when it.evaluation='manual' then
                    (select value from "values" where date <= dt.date and ticker = it.ticker order by date desc)
                else null end) as manual_value,
                (case when it.evaluation='manual' then
                    (select
                        sum(
                            (case when volume then volume else 1 end)*price/
                            (case when rate then rate else 1 end)
                        ) from trades
                        where date <= dt.date and ticker = it.ticker and date >
                            (select date from "values" where date <= dt.date and ticker = it.ticker order by date desc)
                    )
                else null end) as value_correction
            from (
                select distinct date from fx UNION
                select distinct date from trades UNION
                select distinct date from historical UNION
                select distinct date from "values"
            ) as dt
            left join instruments as it
            left join fx as ft on ft.from_curr = it.currency and ft.date = dt.date
            left join trades as tt on tt.ticker = it.ticker and tt.date = dt.date
            left join historical as ht on ht.ticker = it.ticker and ht.date = dt.date
        )
        group by year, ticker
        having investment
        order by year, ticker
        ''', [config.base_currency, config.base_currency]
    )
    data = defaultdict(dict)
    for d in cursor:
        year = int(d['year'])
        ticker = d['ticker']

        prev_value = 0
        prev_fee = 0
        prev_investment = 0
        prev_profit = 0

        if year-1 in data and ticker in data[year-1]:
            prev_value = data[year-1][ticker]['value']
            prev_fee = data[year-1][ticker]['fee']
            prev_investment = data[year-1][ticker]['investment']
            prev_profit = data[year-1][ticker]['profit']

        data[year][ticker] = {
            'fee': d['fee'] - prev_fee,
            'investment': prev_value + d['investment'] - prev_investment,
            'value': d['value'],
            'profit': d['profit'] - prev_profit,
        }
    return sanic.response.json(dict(data))


@app.get("/dividends/calc")
async def dividends_calc(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('''
        SELECT
            dt.ticker,
            sum(dt.dividends) as dividends,
            it.currency
        FROM (
            SELECT
                ht.date,
                ht.ticker,
                ht.dividends * (select sum(volume) from trades where date <= ht.date and ticker = ht.ticker) as dividends
            FROM historical as ht
            WHERE dividends > 0
        ) dt
        JOIN instruments AS it ON it.ticker = dt.ticker
        GROUP BY dt.ticker
    ''')
    return sanic.response.json({d['ticker']: dict(d) for d in cursor})


@app.get("/dividends/list")
async def dividends_list(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('''
        SELECT date, ticker, dividend
        FROM dividends
        ORDER BY date DESC
    ''')
    return sanic.response.json([dict(d) for d in cursor])


@app.post("/dividends/new")
async def dividends_new(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO dividends(date, ticker, dividend)
        VALUES (?, ?, ?)''',
        [data['date'], data['ticker'], data['dividend']]
    )
    db.commit()
    dfs.dividends.reload()
    return sanic.response.json({'success': True})


@app.get("/dividends/sum")
async def dividends_sum(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('''
        SELECT
            dt.ticker,
            sum(dt.dividend) as dividends,
            it.dividend_currency as currency
        FROM dividends as dt
        JOIN instruments AS it ON it.ticker = dt.ticker
        GROUP BY dt.ticker
    ''')
    return sanic.response.json({d['ticker']: dict(d) for d in cursor})


@app.get("/charts/get")
async def charts(request:sanic.Request):
    filter = request.args.get('filter')
    cursor = db.cursor()
    cursor.execute(f'''
        select
            date,
            sum(fee) as fee,
            sum(investment) as investment,
            sum(case when evaluation='manual'
                THEN fx_price*(manual_value+(case when value_correction then value_correction else 0 end))
                ELSE fx_price*last_price*volume
            END) as value,
            sum(case when evaluation='manual'
                THEN fx_price*(manual_value+(case when value_correction then value_correction else 0 end))
                ELSE fx_price*last_price*volume
            END)-sum(investment)-sum(fee) as profit
        from (
            select
                max(tt.id),
                dt.date,
                it.ticker,
                it.evaluation,
                sum(
                    (case when tt.volume then tt.volume else 1 end)*tt.price/
                    (case when tt.rate then tt.rate else 1 end)
                ) over (PARTITION BY it.ticker ORDER BY dt.date, tt.id RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as investment,
                sum(tt.volume) over (PARTITION BY it.ticker ORDER BY dt.date, tt.id RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as volume,
                (select close from historical where date <= dt.date and ticker = it.ticker order by date desc) as last_price,
                (case when it.currency = ? then 1 else
                    (select close from fx where from_curr = it.currency and to_curr = ? order by date desc)
                end) as fx_price,
                sum(tt.fee) over (PARTITION BY it.ticker ORDER BY dt.date, tt.id RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as fee,
                (case when it.evaluation='manual' then
                    (select value from "values" where date <= dt.date and ticker = it.ticker order by date desc)
                else null end) as manual_value,
                (case when it.evaluation='manual' then
                    (select
                        sum(
                            (case when volume then volume else 1 end)*price/
                            (case when rate then rate else 1 end)
                        ) from trades
                        where date <= dt.date and ticker = it.ticker and date >
                            (select date from "values" where date <= dt.date and ticker = it.ticker order by date desc)
                    )
                else null end) as value_correction
            from (
                select distinct date from fx UNION
                select distinct date from trades UNION
                select distinct date from historical UNION
                select distinct date from "values"
            ) as dt
            left join instruments as it
            left join fx as ft on ft.from_curr = it.currency and ft.date = dt.date
            left join trades as tt on tt.ticker = it.ticker and tt.date = dt.date
            left join historical as ht on ht.ticker = it.ticker and ht.date = dt.date
            {'where it.ticker = ? or it.type = ?' if filter else ''}
            group by dt.date, it.ticker
        )
        group by date
        having sum(investment)
        order by date
    ''', [config.base_currency, config.base_currency] + ([filter, filter] if filter else []))
    return sanic.response.json([dict(row) for row in cursor])


@app.get("/prices/get")
async def prices(request:sanic.Request):
    filter = request.args.get('filter')
    cursor = db.cursor()
    cursor.execute('select * from historical where ticker = ?', [filter])
    return sanic.response.json([dict(row) for row in cursor])


@app.get("/instruments/list")
async def instruments_list(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('SELECT * FROM instruments ORDER BY ticker')
    return sanic.response.json([dict(d) for d in cursor])


@app.post("/instruments/new")
async def instruments_new(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO instruments(ticker, currency, dividend_currency, type, evaluation, eval_param)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (ticker)
        DO UPDATE SET currency = excluded.currency, dividend_currency = excluded.dividend_currency, type = excluded.type, evaluation = excluded.evaluation, eval_param = excluded.eval_param
        ''',
        [data['ticker'], data['currency'], data['dividend_currency'], data['type'], data['evaluation'], data['eval_param']]
    )
    db.commit()
    dfs.instruments.reload()
    return sanic.response.json({'success': True})


@app.get("/currencies/list")
async def curr_list(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('SELECT * FROM currencies ORDER BY name')
    return sanic.response.json([d['name'] for d in cursor])


@app.post("/currencies/new")
async def curr_new(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO currencies(name) VALUES (?)',
        [data['currency']]
    )
    db.commit()
    return sanic.response.json({'success': True})


@app.get("/types/list")
async def types_list(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('SELECT * FROM types ORDER BY name')
    return sanic.response.json([d['name'] for d in cursor])


@app.post("/types/new")
async def types_new(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO types(name) VALUES (?)',
        [data['type']]
    )
    db.commit()
    return sanic.response.json({'success': True})


@app.get("/trades/list")
async def trades_list(request:sanic.Request):
    where = []
    ticker = request.args.get('ticker', None)
    if ticker is not None:
        where.append(('ticker', ticker))
    if where:
        sql_where = ' AND '.join(f'{k} = ?' for k, _ in where)

    cursor = db.cursor()
    cursor.execute(f'''
        SELECT id, date, tt.ticker, volume, price, fee, rate, it.currency
        FROM trades AS tt
        JOIN instruments AS it ON it.ticker = tt.ticker
        {f'WHERE {sql_where}' if where else ''}
        ORDER BY date DESC''',
        [v for _, v in where]
    )

    return sanic.response.json([dict(d) for d in cursor])


@app.post("/trades/new")
async def trades_new(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO trades(date, ticker, volume, price, fee, rate)
        VALUES (?, ?, ?, ?, ?, ?)''',
        [data['date'], data['ticker'], data['volume'], data['price'], data['fee'], data['rate']]
    )
    db.commit()
    dfs.trades.reload()
    return sanic.response.json({'success': True})


@app.get("/values/list")
async def values_list(request:sanic.Request):
    where = []
    ticker = request.args.get('ticker', None)
    if ticker is not None:
        where.append(('ticker', ticker))
    if where:
        sql_where = ' AND '.join(f'{k} = ?' for k, _ in where)
    cursor = db.cursor()
    cursor.execute(f'''
        SELECT date, mvt.ticker, value, it.currency
        FROM "values" AS mvt
        JOIN instruments AS it ON it.ticker = mvt.ticker
        {f'WHERE {sql_where}' if where else ''}
        ORDER BY date DESC''',
        [v for _, v in where]
    )
    return sanic.response.json([dict(d) for d in cursor])


@app.post("/values/new")
async def values_new(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO "values"(date, ticker, value) VALUES (?, ?, ?)
        ON CONFLICT (date, ticker)
        DO UPDATE SET value = excluded.value''',
        [data['date'], data['ticker'], data['value']]
    )
    db.commit()
    dfs.values.reload()
    return sanic.response.json({'success': True})

@app.get("/deposits/list")
async def deposits_list(request:sanic.Request):
    where = []
    ticker = request.args.get('ticker', None)
    if ticker is not None:
        where.append(('ticker', ticker))
    if where:
        sql_where = ' AND '.join(f'{k} = ?' for k, _ in where)
    cursor = db.cursor()
    cursor.execute(f'''
        SELECT date, mvt.ticker, amount, fee, it.currency
        FROM "deposits" AS mvt
        JOIN instruments AS it ON it.ticker = mvt.ticker
        {f'WHERE {sql_where}' if where else ''}
        ORDER BY date DESC''',
        [v for _, v in where]
    )
    return sanic.response.json([dict(d) for d in cursor])


@app.post("/deposits/new")
async def deposits_new(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO "deposits"(date, ticker, amount, fee) VALUES (?, ?, ?, ?)',
        [data['date'], data['ticker'], data['amount'], data['fee']],
    )
    db.commit()
    dfs.deposits.reload()
    return sanic.response.json({'success': True})


@app.get("/staking/list")
async def staking_list(request:sanic.Request):
    where = []
    ticker = request.args.get('ticker', None)
    if ticker is not None:
        where.append(('ticker', ticker))
    if where:
        sql_where = ' AND '.join(f'{k} = ?' for k, _ in where)
    cursor = db.cursor()
    cursor.execute(f'''
        SELECT date, mvt.ticker, volume, it.currency
        FROM "staking" AS mvt
        JOIN instruments AS it ON it.ticker = mvt.ticker
        {f'WHERE {sql_where}' if where else ''}
        ORDER BY date DESC''',
        [v for _, v in where]
    )
    return sanic.response.json([dict(d) for d in cursor])


@app.post("/staking/new")
async def staking_new(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO "staking"(date, ticker, volume) VALUES (?, ?, ?)',
        [data['date'], data['ticker'], data['volume']],
    )
    db.commit()
    dfs.staking.reload()
    return sanic.response.json({'success': True})


@app.route("/")
async def homepage(request):
    return await sanic.response.file(os.path.join(FILE_PATH, "../build/index.html"))


def open_web_browser():
    time.sleep(1)
    webbrowser.open_new_tab('http://localhost:8000/')


if __name__ == '__main__':
    if '--browser' in sys.argv:
        threading.Thread(target=open_web_browser).start()
    app.run(host='localhost', port=8000, auto_reload=True, debug=True)