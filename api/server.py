import os
import time
import datetime
import json
import sqlite3
from typing import NamedTuple
import webbrowser

import requests
import sanic
import sanic.response
import yfinance

FILE_PATH = os.path.dirname(__file__)

yfinance_fx = {
    ('USD', 'CZK'): 'CZK=X'
}
def get_yfinance_fx_ticker(from_curr: str, to_curr: str):
    try:
        return yfinance_fx[(from_curr, to_curr)]
    except KeyError:
        return f'{from_curr}{to_curr}=X'

class Config(NamedTuple):
    base_currency: str

with open(os.path.join(FILE_PATH, '../config.json')) as f:
    config = Config(**json.load(f))

app = sanic.Sanic("PortfolioApp")
app.static('/static', os.path.join(FILE_PATH, '../build/static'))
#app.ctx.db = sqlite3.connect(os.path.join(FILE_PATH, '../portfolio.db'))
db = sqlite3.connect(os.path.join(FILE_PATH, '../portfolio.db'))
db.row_factory = sqlite3.Row


@app.get("/data/last")
async def handler(request:sanic.Request):
    last_data = {}
    cursor = db.cursor()
    cursor.execute('SELECT max(date) as last_historical FROM historical')
    last_data['historical'] = cursor.fetchone()['last_historical']
    cursor.execute('SELECT max(date) as fx_historical FROM fx')
    last_data['fx'] = cursor.fetchone()['fx_historical']
    cursor.execute('SELECT max(date) as last_manual_value FROM manual_values')
    last_data['manual_value'] = cursor.fetchone()['last_manual_value']
    return sanic.response.json(last_data)


@app.get("/historical/update")
async def handler(request:sanic.Request):
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
            'eval_param': d['eval_param'],
        } for d in cursor}

    sql = '''
        INSERT OR IGNORE INTO historical(date, ticker, open, high, low, close, dividends, splits) values (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, ticker)
        DO UPDATE SET open = excluded.open, high = excluded.high, low = excluded.low, close = excluded.close, dividends = excluded.dividends, splits = excluded.splits
    '''
    for ticker, ticker_info in first_trades.items():
        if ticker_info['evaluation'] == 'yfinance':
            yticker = yfinance.Ticker(ticker_info['eval_param'] if ticker_info['eval_param'] else ticker)
            df = yticker.history(start=ticker_info['first_date'])
            cursor.executemany(sql, [
                (date.strftime('%Y-%m-%d'), ticker, row['Open'], row['High'], row['Low'], row['Close'], row['Dividends'], row['Stock Splits'])
                for date, row in df.iterrows()
            ])

        # only FFGLOB for now
        elif ticker_info['evaluation'] == 'http':
            resp = requests.get('https://www.fiofondy.cz/cs/podilove-fondy/globalni-akciovy-fond?do=getFundChartData')
            cursor.executemany(sql, [
                (d['x'], ticker, 0, 0, 0, d['value'], 0, 0)
                for d in resp.json()
            ])

        db.commit()

    return sanic.response.json({'success': True})


@app.get("/fx/update")
async def handler(request:sanic.Request):
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

    return sanic.response.json({'success': True})


@app.get("/overview/get")
async def handler(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('''
        SELECT
            tt.ticker,
            it.currency,
            sum(volume) as volume,
            sum(CASE WHEN fee THEN fee ELSE 0 END) as fee,
            sum(price*(CASE WHEN volume THEN volume ELSE 1 END)/(CASE WHEN rate THEN rate ELSE 1 END)) as invested,
            (select close from historical where ticker = it.ticker order by date desc) as last_price,
            (case when it.evaluation = 'manual' then
                (case when it.currency = ? then 1 else
                    (select close from fx where from_curr = it.currency and to_curr = ? order by date desc)
                end)*(
                    (select value from manual_values where ticker = it.ticker order by date desc)
                )
            else
                (select close from historical where ticker = it.ticker order by date desc)*
                (case when it.currency = ? then 1 else
                    (select close from fx where from_curr = it.currency and to_curr = ? order by date desc)
                end)*
                sum(volume)
            end) as value,
            (case when it.evaluation='manual' then
                (select
                    sum(
                        (case when volume then volume else 1 end)*price/
                        (case when rate then rate else 1 end)
                    ) from trades
                    where ticker = it.ticker and date >
                        (select date from manual_values where ticker = it.ticker order by date desc)
                )
            else null end) as manual_value_correction
        FROM trades as tt
        JOIN instruments as it on it.ticker = tt.ticker
        GROUP BY tt.ticker
        ORDER BY tt.ticker
        ''', [config.base_currency, config.base_currency, config.base_currency, config.base_currency]
    )
    return sanic.response.json({
        'base_currency': config.base_currency,
        'overview': [{
            **dict(d),
            'value': d['value'] + (d['manual_value_correction'] if d['manual_value_correction'] else 0),
            'profit': d['value'] - d['invested'] - d['fee'] + (d['manual_value_correction'] if d['manual_value_correction'] else 0),
        } for d in cursor]
    })


@app.get("/charts/get")
async def handler(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('''
        select
            date,
            sum(fee) as fee,
            sum(investment) as investment,
            sum(case when evaluation='manual'
                THEN fx_price*(manual_value+(case when manual_value_correction then manual_value_correction else 0 end))
                ELSE fx_price*last_price*volume
            END) as value,
            sum(case when evaluation='manual'
                THEN fx_price*(manual_value+(case when manual_value_correction then manual_value_correction else 0 end))
                ELSE fx_price*last_price*volume
            END)-sum(investment)-sum(fee) as profit
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
                    (select value from manual_values where date <= dt.date and ticker = it.ticker order by date desc)
                else null end) as manual_value,
                (case when it.evaluation='manual' then
                    (select
                        sum(
                            (case when volume then volume else 1 end)*price/
                            (case when rate then rate else 1 end)
                        ) from trades
                        where date <= dt.date and ticker = it.ticker and date >
                            (select date from manual_values where date <= dt.date and ticker = it.ticker order by date desc)
                    )
                else null end) as manual_value_correction
            from (
                select distinct date from fx UNION
                select distinct date from trades UNION
                select distinct date from historical UNION
                select distinct date from manual_values
            ) as dt
            left join instruments as it
            left join fx as ft on ft.from_curr = it.currency and ft.date = dt.date
            left join trades as tt on tt.ticker = it.ticker and tt.date = dt.date
            left join historical as ht on ht.ticker = it.ticker and ht.date = dt.date
        )
        group by date
        having sum(investment)
        order by date
    ''', [config.base_currency, config.base_currency])
    return sanic.response.json({
        'base_currency': config.base_currency,
        'data': [dict(row) for row in cursor],
    })


@app.get("/instruments/list")
async def handler(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('SELECT * FROM instruments ORDER BY ticker')
    return sanic.response.json([dict(d) for d in cursor])


@app.post("/instruments/new")
async def handler(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO instruments(ticker, currency, type, evaluation, eval_param)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (ticker)
        DO UPDATE SET currency = excluded.currency, type = excluded.type, evaluation = excluded.evaluation, eval_param = excluded.eval_param
        ''',
        [data['ticker'], data['currency'], data['type'], data['evaluation'], data['eval_param']]
    )
    db.commit()
    return sanic.response.json({'success': True})


@app.get("/currencies/list")
async def handler(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('SELECT * FROM currencies ORDER BY name')
    return sanic.response.json({
        'base_currency': config.base_currency,
        'currencies': [d['name'] for d in cursor],
    })


@app.post("/currencies/new")
async def handler(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO currencies(name) VALUES (?)',
        [data['currency']]
    )
    db.commit()
    return sanic.response.json({'success': True})


@app.get("/types/list")
async def handler(request:sanic.Request):
    cursor = db.cursor()
    cursor.execute('SELECT * FROM types ORDER BY name')
    return sanic.response.json([d['name'] for d in cursor])


@app.post("/types/new")
async def handler(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO types(name) VALUES (?)',
        [data['type']]
    )
    db.commit()
    return sanic.response.json({'success': True})


@app.get("/trades/list")
async def handler(request:sanic.Request):
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
        ORDER BY date''',
        [v for _, v in where]
    )

    return sanic.response.json({
        'base_currency': config.base_currency,
        'trades': [dict(d) for d in cursor],
    })


@app.post("/trades/new")
async def handler(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO trades(date, ticker, volume, price, fee, rate)
        VALUES (?, ?, ?, ?, ?, ?)''',
        [data['date'], data['ticker'], data['volume'], data['price'], data['fee'], data['rate']]
    )
    db.commit()
    return sanic.response.json({'success': True})


@app.get("/values/list")
async def handler(request:sanic.Request):
    where = []
    ticker = request.args.get('ticker', None)
    if ticker is not None:
        where.append(('ticker', ticker))
    if where:
        sql_where = ' AND '.join(f'{k} = ?' for k, _ in where)
    cursor = db.cursor()
    cursor.execute(f'''
        SELECT date, mvt.ticker, value, it.currency
        FROM manual_values AS mvt
        JOIN instruments AS it ON it.ticker = mvt.ticker
        {f'WHERE {sql_where}' if where else ''}
        ORDER BY date''',
        [v for _, v in where]
    )
    return sanic.response.json({
        'base_currency': config.base_currency,
        'values': [dict(d) for d in cursor],
    })


@app.post("/values/new")
async def handler(request:sanic.Request):
    data = request.json
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO manual_values(date, ticker, value) VALUES (?, ?, ?)
        ON CONFLICT (date, ticker)
        DO UPDATE SET value = excluded.value''',
        [data['date'], data['ticker'], data['value']]
    )
    db.commit()
    return sanic.response.json({'success': True})


@app.route("/<path:path>")
async def handler(request, path):
    return await sanic.response.file(os.path.join(FILE_PATH, "../build/index.html"))


def open_web_browser():
    time.sleep(1)
    # TODO why it opens two tabs
    webbrowser.open_new_tab('http://localhost:8000/')


if __name__ == '__main__':
    # threading.Thread(target=open_web_browser).start()
    app.run(host='localhost', port='8000', auto_reload=True, debug=True)