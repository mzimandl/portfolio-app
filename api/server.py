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
from sanic_ext import Config
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
class PortfolioConfig:
    db: str
    base_currency: str
    language_locale: str

with open(os.path.join(FILE_PATH, '../config.json')) as f:
    config = PortfolioConfig(**json.load(f))

app = sanic.Sanic("PortfolioApp")
app.static('/assets', os.path.join(FILE_PATH, '../build/assets'))
app.extend(config=Config(templating_path_to_templates=os.path.join(FILE_PATH, "../build")))
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


@app.get("/data/last")
async def last(request:sanic.Request):
    return sanic.response.json({
        'historical': dfs.historical.df.select(pl.col('date').max()).to_dicts()[0]['date'],
        'fx': dfs.fx.df.select(pl.col('date').max()).to_dicts()[0]['date'],
        'manual_value': dfs.values.df.select(pl.col('date').max()).to_dicts()[0]['date'],
    })


@app.get("/historical/update")
async def historical_update(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('''
        SELECT tt.ticker, min(date) as first_date, sum(volume) as volume, it.evaluation, it.eval_param
        FROM trades AS tt
        JOIN instruments AS it ON it.ticker = tt.ticker
        WHERE it.evaluation = 'yfinance' OR it.evaluation = 'http'
        GROUP BY tt.ticker
        HAVING volume > 0
    ''')
    first_trades = {
        d['ticker']: {
            'first_date': datetime.datetime(*tuple(int(t) for t in d['first_date'].split('-'))) - datetime.timedelta(days=7),
            'evaluation': d['evaluation'],
            'eval_param': json.loads(d['eval_param']) if d['evaluation'] == 'http' else d['eval_param'],
        } for d in cursor
    }

    cursor.execute('''
        SELECT tt.ticker, max(date) as last_date
        FROM historical AS tt
    ''')
    for d in cursor:
        if d['ticker'] in first_trades:
            first_trades[d['ticker']]['last_date'] = datetime.datetime(*tuple(int(t) for t in d['last_date'].split('-')))

    sql = '''
        INSERT OR IGNORE INTO historical(date, ticker, open, high, low, close, dividends, splits) values (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, ticker)
        DO UPDATE SET open = excluded.open, high = excluded.high, low = excluded.low, close = excluded.close, dividends = excluded.dividends, splits = excluded.splits
    '''
    for ticker, ticker_info in first_trades.items():
        try:
            if ticker_info['evaluation'] == 'yfinance':
                yticker = yfinance.Ticker(ticker_info['eval_param'] if ticker_info['eval_param'] else ticker)
                df = yticker.history(start=ticker_info['first_date'] if 'last_date' not in ticker_info else ticker_info['last_date'])
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
        else:
            print("Downloaded data", ticker)

    dfs.historical.reload()
    return sanic.response.json({'success': True})


@app.get("/fx/update")
async def fx_update(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('SELECT min(date) as first_trade FROM trades')
    first_trade = datetime.datetime(*tuple(int(t) for t in (cursor.fetchone())['first_trade'].split('-')))

    cursor.execute('SELECT DISTINCT currency FROM instruments')
    currencies = [d['currency'] for d in cursor]

    cursor.execute('SELECT from_curr, to_curr, max(date) as last_date FROM fx GROUP BY from_curr, to_curr')
    last_fx = {
        get_yfinance_fx_ticker(d['from_curr'], d['to_curr']): datetime.datetime(*tuple(int(t) for t in d['last_date'].split('-')))
        for d in cursor
    }

    sql = '''
        INSERT OR IGNORE INTO fx(date, from_curr, to_curr, open, high, low, close) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, from_curr, to_curr)
        DO UPDATE SET open = excluded.open, high = excluded.high, low = excluded.low, close = excluded.close
    '''
    for currency in currencies:
        if currency != config.base_currency:
            try:
                ticker = get_yfinance_fx_ticker(currency, config.base_currency)
                yticker = yfinance.Ticker(ticker)
                df = yticker.history(start=first_trade if ticker not in last_fx else last_fx[ticker])
                cursor.executemany(sql, [
                    (date.strftime('%Y-%m-%d'), currency, config.base_currency, row['Open'], row['High'], row['Low'], row['Close'])
                    for date, row in df.iterrows()
                ])
                db.commit()
            except Exception as e:
                print("Failed to download data", currency, e)
            else:
                print("Downloaded data", ticker)

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
            -pl.col("amount").filter(pl.col("amount") < 0).sum().alias("return"),
            (pl.col("value").last() + pl.col("amount").filter(pl.col("date") >= pl.col("date_right")).sum()).alias("value"),
            pl.col("fee").sum().alias("fees"),
        )
        .join(dfs.instruments.df, "ticker", "left")
        .select(
            "ticker", "type", "currency", "investment", "return", "fees", "value",
            (pl.col("return") + pl.col("value") - pl.col("investment")).alias("total_profit")
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
        .agg(pl.col("close").last().alias("fx_rate"))\
        .filter(pl.col("to_curr") == config.base_currency)
    
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
            -(pl.col("volume") * pl.col("price") / pl.col("rate")).filter(pl.col("volume") < 0).sum().alias("return"),
            pl.col("fee").sum().alias("fees"),
        )
        .join(last_price, "ticker", "left")
        .join(dfs.instruments.df, "ticker", "left")
        .join(last_fx, None, "left", left_on="currency", right_on="from_curr").with_columns(pl.col("fx_rate").fill_null(1))
        .join(total_staking_df, "ticker", "left").with_columns(pl.col("staking_volume").fill_null(0))
        .with_columns((pl.col("trade_volume") + pl.col("staking_volume")).alias("volume"))
        .select(
            "ticker", "type", "currency", "dividend_currency", "last_price",
            "investment", "return", "fees", "volume",
            pl.when(pl.col("buy_volume").gt(0)).then(pl.col("fx_investment") / pl.col("buy_volume")).otherwise(None).alias("average_price"),
            (pl.col("volume") * pl.col("last_price") * pl.col("fx_rate")).alias("value"),
            (pl.col("trade_volume") * pl.col("last_price") * pl.col("fx_rate")).alias("trade_value"),
            (pl.col("fx_investment") * pl.col("fx_rate") - pl.col("investment")).alias("fx_profit"),
            (pl.col("staking_volume") * pl.col("last_price") * pl.col("fx_rate")).alias("rewards"),
        )
        .with_columns((pl.col("value") + pl.col("return") - pl.col("investment")).alias("total_profit"))
        .with_columns((pl.col("total_profit") - pl.col("rewards") - pl.col("fx_profit")).alias("value_profit"))
        .join(total_dividends_df, on="ticker", how="left")
    )

    overview = pl.concat([tradeables, valuables], how="diagonal").sort("ticker")
    return sanic.response.json(overview.to_dicts())


@app.get("/performance/get")
async def performance(request:sanic.Request):
    last_price = (
        dfs.historical.df
        .with_columns(year=pl.col('date').str.to_date().dt.year().alias('year'))
        .sort('date')
        .group_by('ticker', 'year')
        .agg(pl.col('close').last())
        .sort('year', 'ticker')
    )

    last_fx = (
        dfs.fx.df
        .filter(pl.col("to_curr") == config.base_currency)
        .with_columns(pl.col('date').str.to_date().dt.year().alias('year'))
        .sort('date')
        .group_by(pl.col('from_curr').alias('currency'), 'year')
        .agg(pl.col('close').last().alias('fx_close'))
        .sort('year', 'currency')
    )

    year_trades = (
        last_price
        .join(
            dfs.trades.df
            .with_columns(pl.col('date').str.to_date().dt.year().alias('year'))
            .group_by('ticker', 'year')
            .agg(
                pl.col("volume").sum(),
                (pl.col("volume") * pl.col("price") / pl.col("rate")).filter(pl.col("volume") > 0).sum().alias("investment"),
                -(pl.col("volume") * pl.col("price") / pl.col("rate")).filter(pl.col("volume") < 0).sum().alias("return"),
                pl.col("fee").sum(),
            ),
            ['ticker', 'year'],
            'left',
        )
        .with_columns(
            pl.col('volume').fill_null(0),
            pl.col('investment').fill_null(0),
            pl.col('return').fill_null(0),
            pl.col('fee').fill_null(0),
        ).rename({
            'volume': 'volume_change',
            'investment': 'investment_change',
            'return': 'return_change',
            'fee': 'fee_change'
        })
        .with_columns(
            pl.col('volume_change').cum_sum().over('ticker', order_by='year').alias('volume_total'),
            pl.col('investment_change').cum_sum().over('ticker', order_by='year').alias('investment_total'),
            pl.col('return_change').cum_sum().over('ticker', order_by='year').alias('return_total'),
            pl.col('fee_change').cum_sum().over('ticker', order_by='year').alias('fee_total'),
        )
        .filter(pl.col("volume_total").ne(0) | pl.col("investment_total").ne(0) | pl.col("return_total").ne(0) | pl.col("fee_total").ne(0))
        .sort('ticker', 'year')
    )

    performance = (
        year_trades
        .join(dfs.instruments.df, 'ticker', 'left')
        .join(last_fx, ['currency', 'year'], 'left')
        .with_columns(
            pl.col('fx_close').fill_null(pl.when(pl.col('currency').eq(config.base_currency)).then(1).otherwise(None))
        )
        .with_columns(
            (pl.col('volume_total') * pl.col('close') * pl.col('fx_close')).alias('value_total'),
        )
        .select(
            'ticker', 'year',
            'volume_change', 'investment_change', 'return_change', 'fee_change', pl.col('value_total').diff().over('ticker', order_by='year').fill_null(pl.col('value_total')).alias('value_change'),
            'volume_total', 'investment_total', 'return_total', 'fee_total', 'value_total',
        )
        .with_columns(
            (pl.col('value_total') + pl.col('return_total') - pl.col('investment_total')).alias('profit_total'),
            #(100 * (pl.col('value') - pl.col('investment')) / (pl.col('total_value') - pl.col('value'))).alias('perc')
        )
        .with_columns(
            pl.col('profit_total').diff().over('ticker', order_by='year').fill_null(pl.col('profit_total')).alias('profit_change'),
            #pl.col('perc').fill_null(0),
        )
    )

    data = defaultdict(dict)
    for d in performance.to_dicts():
        data[d['year']][d['ticker']] = d
        del d['year']
        del d['ticker']
    return sanic.response.json(data)


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
    return sanic.response.json(dfs.dividends.df.sort('date', descending=True).to_dicts())


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
    return sanic.response.json(dfs.historical.df.filter(pl.col('ticker').eq(filter)).sort('date').to_dicts())


@app.get("/instruments/list")
async def instruments_list(request:sanic.Request):
    return sanic.response.json(dfs.instruments.df.sort('ticker').to_dicts())


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
    resp = dfs.trades.df.join(dfs.instruments.df, on='ticker').select('id', 'date', 'ticker', 'volume', 'price', 'fee', 'rate', 'currency')
    return sanic.response.json(resp.sort('date', descending=True).to_dicts())


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
    resp = dfs.values.df.join(dfs.instruments.df, on='ticker').select('date', 'ticker', 'value', 'currency')
    return sanic.response.json(resp.sort('date', descending=True).to_dicts())


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
    resp = dfs.deposits.df.join(dfs.instruments.df, on='ticker').select('date', 'ticker', 'amount', 'fee', 'currency')
    return sanic.response.json(resp.sort('date', descending=True).to_dicts())


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
    return sanic.response.json(dfs.staking.df.sort('date', descending=True).to_dicts())


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
@app.ext.template("index.html")
async def homepage(request):
    return asdict(config)


def open_web_browser():
    time.sleep(1)
    webbrowser.open_new_tab('http://localhost:8000/')


if __name__ == '__main__':
    if '--browser' in sys.argv:
        threading.Thread(target=open_web_browser).start()
    app.run(host='localhost', port=8000, auto_reload=True, debug=True)