create table currencies(
	name TEXT NOT NULL UNIQUE
);

create table types(
	name TEXT NOT NULL UNIQUE
);

create table instruments(
	ticker TEXT NOT NULL UNIQUE,
	currency TEXT NOT NULL,
	type TEXT NOT NULL,
	evaluation TEXT CHECK (evaluation IN ('yfinance', 'manual', 'http')) NOT NULL,
	eval_param TEXT,
	FOREIGN KEY(currency) REFERENCES currencies(name),
	FOREIGN KEY(type) REFERENCES types(name)
);

create table trades(
	id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	date TEXT NOT NULL,
	ticker TEXT NOT NULL,
	volume REAL,
	price REAL,
	fee REAL,
	rate REAL,
	FOREIGN KEY(ticker) REFERENCES instruments(ticker)
);

create table historical(
	date TEXT NOT NULL,
	ticker TEXT NOT NULL,
	open REAL,
	high REAL,
	low REAL,
	close REAL,
	dividends REAL,
	splits REAL,
	UNIQUE(date, ticker),
	FOREIGN KEY(ticker) REFERENCES instruments(ticker)
);

create table fx(
	date TEXT NOT NULL,
	from_curr TEXT NOT NULL,
	to_curr TEXT NOT NULL,
	open REAL,
	high REAL,
	low REAL,
	close REAL,
	UNIQUE(date, from_curr, to_curr),
	FOREIGN KEY(from_curr) REFERENCES currencies(name),
	FOREIGN KEY(to_curr) REFERENCES currencies(name)
);

create table manual_values(
	date text NOT NULL,
	ticker text NOT NULL,
	value real NOT NULL,
	UNIQUE(date, ticker),
	FOREIGN KEY(ticker) REFERENCES instruments(ticker)
);