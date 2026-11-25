"""Czech texts of the app: the English text as written in the code -> its Czech translation.

``tests/test_i18n.py`` checks that every text marked with ``tr()`` or ``N_()`` is here, with
the same ``{placeholders}``, and that nothing here is left over.
"""

# fmt: off
CS: dict[str, str] = {
    # --- navigation and sidebar -----------------------------------------------------------
    "Overview": "Přehled",
    "Performance": "Výkonnost",
    "Charts": "Grafy",
    "Dividends": "Dividendy",
    "Fundamentals": "Fundamenty",
    "Taxes": "Daně",
    "Transactions": "Transakce",
    "Prices": "Ceny",
    "Checks": "Kontroly",
    "Import / export": "Import / export",
    "Settings": "Nastavení",
    "Glossary": "Slovník pojmů",
    "never": "nikdy",
    "Update prices": "Aktualizovat ceny",
    "Prices up to **{day}**": "Ceny do **{day}**",
    "Rates up to **{day}**": "Kurzy do **{day}**",
    "Dismiss": "Zavřít",
    "Downloading prices, exchange rates and company data…":
        "Stahuji ceny, kurzy a údaje o firmách…",
    "Series updated: {series}, days saved: {days}.":
        "Aktualizované řady: {series}, uložené dny: {days}.",
    "Company data for shares: {n}.": "Údaje o firmách pro akcie: {n}.",
    "SEC results: {n}.": "Výsledky ze SEC: {n}.",
    "New split for {ticker}: its price history was downloaded again.":
        "Nový split u {ticker}: jeho historie cen byla stažena znovu.",
    "**{ticker}** had a split of **{ratio} for 1** on {day}. Until you decide, its value is "
    "wrong. Add the split if your recorded quantities are from before it; dismiss it if you "
    "already rewrote them.":
        "**{ticker}** měl {day} split **{ratio} za 1**. Dokud nerozhodnete, je jeho hodnota "
        "špatně. Přidejte split, pokud jsou vaše zapsaná množství z doby před ním; zavřete "
        "ho, pokud jste je už přepsali.",
    "Add split": "Přidat split",

    # --- common words and choices ---------------------------------------------------------
    "Buy": "Nákup",
    "Sell": "Prodej",
    "Deposit": "Vklad",
    "Withdrawal": "Výběr",
    "Dividend": "Dividenda",
    "Staking reward": "Odměna ze stakingu",
    "Staking correction": "Oprava stakingu",
    "Split": "Split",
    "Fee only": "Jen poplatek",
    "Since start": "Od začátku",
    "This year": "Letos",
    "Last 12 months": "Posledních 12 měsíců",
    "Last 3 years": "Poslední 3 roky",
    "Last 5 years": "Posledních 5 let",
    "All active": "Všechny aktivní",
    "Everything, including inactive": "Vše včetně neaktivních",
    "Investments (without {what})": "Investice (bez: {what})",
    "Type: {name}": "Typ: {name}",
    "(inactive)": "(neaktivní)",
    "Show": "Zobrazit",
    "Period": "Období",
    "Nothing to show for this selection.": "Pro tento výběr není co zobrazit.",
    "Ticker": "Ticker",
    "Name": "Název",
    "Type": "Typ",
    "Currency": "Měna",
    "Sector": "Sektor",
    "Country": "Země",
    "Date": "Datum",
    "Year": "Rok",
    "Instrument": "Instrument",
    "Instruments": "Instrumenty",
    "Quantity": "Množství",
    "Value": "Hodnota",
    "Cost": "Pořizovací cena",
    "Profit": "Zisk",
    "Net profit": "Čistý zisk",
    "Fees": "Poplatky",
    "Received": "Přijato",
    "Payments": "Platby",
    "Tax withheld": "Sražená daň",
    "Bought": "Koupeno",
    "Sold": "Prodáno",
    "Share": "Podíl",
    "Return": "Výnos",
    "Inflation": "Inflace",
    "Benchmark": "Benchmark",
    "By year": "Po letech",
    "By month": "Po měsících",
    "By type": "Podle typu",
    "By instrument": "Podle instrumentu",
    "Total": "Celkem",
    "yes": "ano",
    "no": "ne",
    "year": "rok",
    "month": "měsíc",
    "Jan": "led",
    "Feb": "úno",
    "Mar": "bře",
    "Apr": "dub",
    "May": "kvě",
    "Jun": "čvn",
    "Jul": "čvc",
    "Aug": "srp",
    "Sep": "zář",
    "Oct": "říj",
    "Nov": "lis",
    "Dec": "pro",
    "number": "číslo",
    "value": "hodnota",
    "fee": "poplatek",
    "rate": "kurz",
    "'{text}' is not a valid {field}": "„{text}“ není platná hodnota: {field}",

    # --- overview ---------------------------------------------------------------------------
    "Include inactive instruments": "Včetně neaktivních instrumentů",
    "No transactions yet. Add instruments in Settings, then transactions.":
        "Zatím žádné transakce. Přidejte instrumenty v Nastavení, pak transakce.",
    "All amounts in {currency}. Sales use up the oldest units first. Net profit = unrealised "
    "+ realised + dividends − fees.":
        "Všechny částky v {currency}. Prodeje spotřebují nejstarší kusy jako první. Čistý "
        "zisk = nerealizovaný + realizovaný + dividendy − poplatky.",
    "{what} is not included here.": "{what} zde není zahrnuto.",
    "All amounts in {currency}.": "Všechny částky v {currency}.",
    "Cost of holdings": "Pořizovací cena pozic",
    "Unrealised profit": "Nerealizovaný zisk",
    "Realised profit": "Realizovaný zisk",
    "Still deposited": "Stále vloženo",
    "Value minus cost of what you still hold. The percentage is of that cost.":
        "Hodnota minus pořizovací cena toho, co ještě držíte. Procento je z této ceny.",
    "Value minus the money still deposited; the percentage is relative to it.":
        "Hodnota minus stále vložené peníze; procento je vztažené k nim.",
    "No price or exchange rate for: {tickers}. They count as zero in the totals.":
        "Chybí cena nebo kurz pro: {tickers}. V součtech se počítají jako nula.",
    "Last price": "Poslední cena",
    "Average buy price": "Průměrná nákupní cena",
    "Of the bought units you still hold.": "Z koupených kusů, které ještě držíte.",
    "Of the value of all investments.": "Z hodnoty všech investic.",
    "What the units you still hold cost. Oldest units are sold first.":
        "Kolik stály kusy, které ještě držíte. Nejstarší kusy se prodávají první.",
    "Unrealised": "Nerealizovaný",
    "Value minus cost of what you still hold.":
        "Hodnota minus pořizovací cena toho, co ještě držíte.",
    "From price": "Z ceny",
    "Part of the unrealised profit.": "Část nerealizovaného zisku.",
    "From exchange rate": "Z kurzu",
    "Staking rewards": "Odměny ze stakingu",
    "Staking units you still hold, at today's price.":
        "Kusy ze stakingu, které ještě držíte, za dnešní cenu.",
    "Realised": "Realizovaný",
    "On units sold: what you got minus what they cost.":
        "U prodaných kusů: kolik jste dostali minus kolik stály.",
    "Unrealised plus realised.": "Nerealizovaný plus realizovaný.",
    "Profit plus dividends minus fees.": "Zisk plus dividendy minus poplatky.",
    "Bought / deposited": "Koupeno / vloženo",
    "Sold / withdrawn": "Prodáno / vybráno",
    "Sales": "Prodeje",
    "Every sale and what it realised: what you received minus what those units had cost, "
    "oldest units first. Units lost (sold at price 0) show their cost as a loss.":
        "Každý prodej a co realizoval: kolik jste dostali minus kolik ty kusy stály, "
        "nejstarší kusy první. Ztracené kusy (prodané za cenu 0) ukazují svou pořizovací "
        "cenu jako ztrátu.",
    "Held (days)": "Drženo (dní)",
    "Against the target": "Oproti cíli",
    "New money to invest ({currency})": "Nové peníze k investování ({currency})",
    "Target": "Cíl",
    "Difference": "Rozdíl",
    "To be on target": "Do cíle",
    "Buy now": "Koupit teď",
    "Set in Settings.": "Nastavuje se v Nastavení.",
    "Share minus target, in percentage points.": "Podíl minus cíl, v procentních bodech.",
    "What to buy to reach the target share at today's value; negative means there is that "
    "much too many.":
        "Kolik dokoupit, aby se dosáhlo cílového podílu při dnešní hodnotě; záporné číslo "
        "znamená, že je toho o tolik víc.",
    "How to split the new money: it goes to the types that would still be below their "
    "target, in proportion to how far below. Nothing is sold.":
        "Jak rozdělit nové peníze: jdou do typů, které by byly stále pod cílem, v poměru "
        "k tomu, jak daleko pod ním. Nic se neprodává.",
    "Spread": "Rozložení",
    "By currency": "Podle měny",
    "By sector": "Podle sektoru",
    "By country": "Podle země",
    "The currency each instrument is quoted in.": "Měna, ve které je instrument oceněn.",
    "Where each company is based.": "Kde firma sídlí.",
    "Sector and country come from Yahoo for shares. Funds and coins have none of their own "
    "and are listed by type in brackets; you can set theirs in Settings.":
        "Sektor a země u akcií pocházejí z Yahoo. Fondy a mince vlastní nemají a jsou "
        "uvedené podle typu v závorce; jejich můžete nastavit v Nastavení.",
    "Purchases still held": "Nákupy, které stále držíte",
    "What you hold, purchase by purchase, oldest first. Sales used up the oldest units, so "
    "these are what remains. The age is what a holding-period rule for tax would look at.":
        "Co držíte, nákup po nákupu, od nejstaršího. Prodeje spotřebovaly nejstarší kusy, "
        "takže tohle zbývá. Stáří je to, na co by se dívalo pravidlo o době držení pro daně.",
    "Show staking rewards": "Zobrazit odměny ze stakingu",
    "Age (years)": "Stáří (roky)",

    # --- performance ------------------------------------------------------------------------
    "Return (time-weighted)": "Výnos (časově vážený)",
    "Yearly return on your money": "Roční výnos vašich peněz",
    "Net profit in the period": "Čistý zisk za období",
    "The time-weighted return shows how the investments did, whenever money was added. The "
    "yearly return on your money (XIRR) takes the timing of your payments into account. Both "
    "include dividends and are after fees.":
        "Časově vážený výnos ukazuje, jak si vedly investice, bez ohledu na to, kdy se "
        "přidávaly peníze. Roční výnos vašich peněz (XIRR) bere v úvahu načasování vašich "
        "plateb. Oba zahrnují dividendy a jsou po poplatcích.",
    "Time-weighted return of each calendar month, dividends included, after fees.":
        "Časově vážený výnos každého kalendářního měsíce, včetně dividend, po poplatcích.",
    "Deepest drop": "Nejhlubší propad",
    "Now below the high": "Nyní pod maximem",
    "The largest fall of the time-weighted return from a high, in the period. New money does "
    "not hide it.":
        "Největší pokles časově váženého výnosu od maxima v daném období. Nové peníze ho "
        "neschovají.",
    "How far the return is today below its highest point in the period.":
        "Jak daleko je výnos dnes pod svým nejvyšším bodem v daném období.",
    "back at the high on {day}": "zpět na maximu {day}",
    "not yet back at that high": "na to maximum se ještě nevrátil",
    "The deepest drop ran from {peak} to {trough} ({days} days); {after}.":
        "Nejhlubší propad trval od {peak} do {trough} ({days} dní); {after}.",
    "No inflation figures for {region} yet. Use Update prices.":
        "Pro {region} zatím nejsou údaje o inflaci. Použijte Aktualizovat ceny.",
    "Return after inflation": "Výnos po inflaci",
    "Yearly return after inflation": "Roční výnos po inflaci",
    "Inflation ({region})": "Inflace ({region})",
    "The time-weighted return in today's prices: what it bought more than at the start.":
        "Časově vážený výnos v dnešních cenách: o kolik víc se za něj dá koupit než na začátku.",
    "The yearly return on your money minus the yearly inflation of the period.":
        "Roční výnos vašich peněz minus roční inflace za období.",
    "How much consumer prices rose in the period (Eurostat's harmonised index).":
        "O kolik vzrostly spotřebitelské ceny za období (harmonizovaný index Eurostatu).",
    "Inflation is published up to {month}; prices are taken as unchanged since then.":
        "Inflace je zveřejněná do {month}; od té doby se ceny berou jako nezměněné.",
    "Against {symbol}": "Oproti {symbol}",
    "No prices for {symbol} yet. Use Update prices.":
        "Pro {symbol} zatím nejsou ceny. Použijte Aktualizovat ceny.",
    "{symbol} return": "Výnos {symbol}",
    "Of holding it for the whole period, dividends reinvested.":
        "Při držení po celé období, s reinvestovanými dividendami.",
    "Yearly return of your money in {symbol}": "Roční výnos vašich peněz v {symbol}",
    "Comparable with the yearly return on your money above.":
        "Srovnatelný s ročním výnosem vašich peněz výše.",
    "You are ahead by": "Jste napřed o",
    "You are behind by": "Zaostáváte o",
    "Your value today minus what the same money would be worth in {symbol}: {value}.":
        "Vaše dnešní hodnota minus kolik by měly stejné peníze v {symbol}: {value}.",
    "The same money on the same days, put into {symbol} instead: what you held at the start "
    "of the period, then every payment in and out, fees and dividends included. No fees or "
    "taxes are charged on the benchmark side.":
        "Stejné peníze ve stejné dny, vložené místo toho do {symbol}: co jste drželi na "
        "začátku období, pak každá platba dovnitř i ven, včetně poplatků a dividend. Na "
        "straně benchmarku se neúčtují poplatky ani daně.",
    "{symbol} has prices only from {day}; money paid before that waits as cash until then.":
        "{symbol} má ceny až od {day}; peníze vložené dřív do té doby čekají jako hotovost.",
    "Start value": "Počáteční hodnota",
    "Put in": "Vloženo",
    "Taken out": "Vybráno",
    "End value": "Konečná hodnota",
    "After inflation": "Po inflaci",
    "Instruments, {period}": "Instrumenty, {period}",
    "Part of the profit": "Podíl na zisku",
    "Yearly return": "Roční výnos",
    "This instrument's net profit as a part of the net profit of the whole selection in the "
    "period. Empty when the selection made a loss.":
        "Čistý zisk instrumentu jako část čistého zisku celého výběru za období. Prázdné, "
        "když výběr skončil ve ztrátě.",
    "New money": "Nové peníze",
    "Per": "Za",
    "Buys and deposits minus sells and withdrawals, by instrument type, for all instruments.":
        "Nákupy a vklady minus prodeje a výběry, podle typu instrumentu, pro všechny "
        "instrumenty.",
    "Buys and deposits minus sells and withdrawals, by instrument type, for active "
    "instruments.":
        "Nákupy a vklady minus prodeje a výběry, podle typu instrumentu, pro aktivní "
        "instrumenty.",

    # --- charts -----------------------------------------------------------------------------
    "Value and money invested": "Hodnota a investované peníze",
    "Still invested": "Stále investováno",
    "Net profit (with dividends, after fees)": "Čistý zisk (s dividendami, po poplatcích)",
    "Drop from the high": "Propad od maxima",
    "Below the high (%)": "Pod maximem (%)",
    "How far the time-weighted return is below its highest point so far in the period. New "
    "money does not move it.":
        "Jak daleko je časově vážený výnos pod svým dosavadním nejvyšším bodem v období. "
        "Nové peníze s ním nepohnou.",
    "Each day uses the prices and exchange rates of that day. Profit = value − money still "
    "invested.":
        "Každý den používá ceny a kurzy toho dne. Zisk = hodnota − stále investované peníze.",
    "Drawn with one point every {days} days; pick a shorter period for more detail.":
        "Vykresleno s jedním bodem každých {days} dní; pro víc podrobností zvolte kratší "
        "období.",

    # --- dividends --------------------------------------------------------------------------
    "No dividends recorded yet. Add them in Transactions.":
        "Zatím žádné zapsané dividendy. Přidejte je v Transakcích.",
    "Received in total": "Přijato celkem",
    "In the last 12 months": "Za posledních 12 měsíců",
    "Yield on cost": "Výnos z pořizovací ceny",
    "The last 12 months of dividends, relative to what the holdings that paid them cost.":
        "Dividendy za posledních 12 měsíců vůči pořizovací ceně pozic, které je vyplatily.",
    "Net amounts as recorded, in {currency} at the exchange rate of each payment. Tax is "
    "counted only where you entered it.":
        "Čisté částky, jak jsou zapsané, v {currency} v kurzu každé platby. Daň se počítá "
        "jen tam, kde jste ji zadali.",
    "Cost of holding": "Pořizovací cena pozice",
    "What the units you hold now cost.": "Kolik stály kusy, které držíte teď.",
    "Yield on value": "Výnos z hodnoty",
    "The last 12 months, relative to the cost.":
        "Posledních 12 měsíců vůči pořizovací ceně.",
    "The last 12 months, relative to today's value.":
        "Posledních 12 měsíců vůči dnešní hodnotě.",
    "Possibly missing": "Možná chybí",
    "Payments the price data reports for units you held, beyond the ones recorded. Reports "
    "from the last two months are not counted.":
        "Platby, které cenová data hlásí pro kusy, jež jste drželi, nad rámec zapsaných. "
        "Hlášení z posledních dvou měsíců se nepočítají.",
    "Recorded and expected": "Zapsané a očekávané",
    "Expected is what the price data reports for the units you held the day before, before "
    "tax. It is dated by the day of that report; the payment comes some weeks later, so "
    "around New Year the two can fall into different years. Not every instrument has such "
    "data.":
        "Očekávané je to, co cenová data hlásí pro kusy, které jste drželi den předtím, před "
        "zdaněním. Je datované dnem toho hlášení; platba přijde o několik týdnů později, "
        "takže kolem Nového roku mohou obě spadnout do různých let. Ne každý instrument "
        "taková data má.",
    "Received (net)": "Přijato (čistého)",
    "Expected (gross)": "Očekáváno (hrubého)",
    "Expected payments": "Očekávané platby",

    # --- fundamentals -----------------------------------------------------------------------
    "No company data yet. Update prices downloads it for the shares you hold; funds and "
    "coins have none.":
        "Zatím žádné údaje o firmách. Aktualizovat ceny je stáhne pro akcie, které držíte; "
        "fondy a mince žádné nemají.",
    "Ratios worked out for every day from the reported results and the price of that day, "
    "and the ones Yahoo reports, saved on every day you update prices. Results count from "
    "the end of their period; earnings and revenue are those of the last twelve months. "
    "Yahoo keeps results of about the last five years; with SEC EDGAR set up in the config "
    "file, US companies reach back to about 2009.":
        "Ukazatele spočítané pro každý den z vykázaných výsledků a ceny toho dne, a ty, které "
        "hlásí Yahoo, uložené v každý den, kdy aktualizujete ceny. Výsledky platí od konce "
        "svého období; zisk a tržby jsou za posledních dvanáct měsíců. Yahoo uchovává "
        "výsledky zhruba posledních pěti let; s SEC EDGAR nastaveným v konfiguračním souboru "
        "sahají americké firmy zhruba do roku 2009.",
    "Your shares": "Vaše akcie",
    "Typical P/E": "Obvyklé P/E",
    "Dividend yield": "Dividendový výnos",
    "Forward P/E": "Forward P/E",
    "P/E by Yahoo": "P/E podle Yahoo",
    "Since": "Od",
    "Results from": "Výsledky z",
    "Price / earnings per share of the last twelve months.":
        "Cena / zisk na akcii za posledních dvanáct měsíců.",
    "The median P/E over the days it could be worked out.":
        "Medián P/E za dny, kdy se dalo spočítat.",
    "Price / equity per share.": "Cena / vlastní kapitál na akcii.",
    "Price / revenue per share of the last twelve months.":
        "Cena / tržby na akcii za posledních dvanáct měsíců.",
    "Dividends of the last twelve months / price.":
        "Dividendy za posledních dvanáct měsíců / cena.",
    "By Yahoo: price / expected earnings of the next year.":
        "Podle Yahoo: cena / očekávaný zisk příštího roku.",
    "By Yahoo.": "Podle Yahoo.",
    "For comparison; Yahoo may count earnings differently.":
        "Pro srovnání; Yahoo může zisk počítat jinak.",
    "First day with a P/E worked out.": "První den se spočítaným P/E.",
    "Empty where a company made a loss, or where results are missing or too old.":
        "Prázdné, kde firma byla ve ztrátě nebo kde výsledky chybí či jsou příliš staré.",
    "The P/E worked out differs from Yahoo's by more than 30 % for {tickers}. Usually a "
    "quarter missing in Yahoo's results, a one-off gain or loss, or results reported in "
    "other units: look at the reported results below before relying on it.":
        "Spočítané P/E se od Yahoo liší o víc než 30 % u {tickers}. Obvykle chybí čtvrtletí "
        "ve výsledcích Yahoo, jde o jednorázový zisk či ztrátu nebo o výsledky vykázané v "
        "jiných jednotkách: než se na ně spolehnete, podívejte se níže na vykázané výsledky.",
    "Traded units that are not one reported share each (depositary receipts, other share "
    "classes) are counted with the ratio Yahoo's market value implies: {ratios}.":
        "Obchodované jednotky, které nejsou každá jedna vykázaná akcie (depozitní "
        "certifikáty, jiné třídy akcií), se počítají s poměrem, který vyplývá z tržní "
        "hodnoty od Yahoo: {ratios}.",
    "{ticker} {ratio} per share": "{ticker} {ratio} na akcii",
    "Price / earnings": "Cena / zisk",
    "Price / book and price / sales": "Cena / účetní hodnota a cena / tržby",
    "No results to work ratios out from in this period.":
        "V tomto období nejsou výsledky, ze kterých by šlo ukazatele spočítat.",
    "As reported by Yahoo": "Jak hlásí Yahoo",
    "Market cap": "Tržní kapitalizace",
    "Saved on every day you update prices, so this grows from the first update on.":
        "Ukládá se v každý den, kdy aktualizujete ceny, takže to roste od první aktualizace.",
    "Reported results": "Vykázané výsledky",
    "In {currency}, as the company reports them in its SEC filings; per-share numbers "
    "converted to today's share units.":
        "V {currency}, jak je firma vykazuje v podáních u SEC; čísla na akcii přepočtená na "
        "dnešní akcie.",
    "In {currency}, as the company reports them, from Yahoo.":
        "V {currency}, jak je firma vykazuje, z Yahoo.",
    "The share is priced in {currency}; ratios convert at the day's rate.":
        "Akcie je oceněná v {currency}; ukazatele se přepočítávají kurzem dne.",
    "By quarter": "Po čtvrtletích",
    "Period end": "Konec období",
    "Revenue": "Tržby",
    "Net income": "Čistý zisk",
    "Margin": "Marže",
    "Equity": "Vlastní kapitál",
    "Shares": "Akcie",

    # --- taxes ------------------------------------------------------------------------------
    "securities": "cenné papíry",
    "crypto": "kryptoměny",
    "ČNB, rate of each day": "ČNB, kurz každého dne",
    "ČNB, unified rate of the year": "ČNB, jednotný kurz roku",
    "As recorded": "Jak je zapsáno",
    "Exchange rates": "Kurzy",
    "at the exchange rates you entered": "kurzy, které jste zadali",
    "at the ČNB rate of the day of each payment": "kurzem ČNB ze dne každé platby",
    "at the ČNB unified rate of the year of each payment (purchases in earlier years at that "
    "year's)":
        "jednotným kurzem ČNB roku každé platby (nákupy z dřívějších let kurzem toho roku)",
    "A Czech tax return converts with the rates of the Czech National Bank: either the rate "
    "of the day of each payment, or the unified rate of the year (the average of the rates "
    "on the last day of each month) for all of them. Use one way for the whole year.":
        "České daňové přiznání přepočítává kurzy České národní banky: buď kurzem ze dne každé "
        "platby, nebo jednotným kurzem roku (průměr kurzů k poslednímu dni každého měsíce) "
        "pro všechny. Pro celý rok použijte jeden způsob.",
    "Unified rates {year}: {rates}.": "Jednotné kurzy {year}: {rates}.",
    "The unified rates of {year} are known once the year is over.":
        "Jednotné kurzy roku {year} jsou známé až po jeho skončení.",
    "Figures from your records in {currency}. Two rules are applied, both set in the config "
    "file: a sale of units held longer than {years} years is exempt, and so are all sales of "
    "a year whose proceeds do not exceed {limit}, counted apart for securities and for "
    "{crypto}. Units are sold oldest first. This is an overview to work from, not tax "
    "advice: check the rules that apply to the year and to you.":
        "Čísla z vašich záznamů v {currency}. Použijí se dvě pravidla, obě nastavená v "
        "konfiguračním souboru: prodej kusů držených déle než {years} r. je osvobozený, "
        "stejně jako všechny prodeje roku, jejichž příjmy nepřesáhnou {limit}, počítáno "
        "zvlášť pro cenné papíry a pro {crypto}. Kusy se prodávají od nejstarších. Je to "
        "přehled k práci, ne daňové poradenství: ověřte si pravidla, která platí pro daný "
        "rok a pro vás.",
    "No sales, dividends or staking recorded yet.":
        "Zatím nejsou zapsané žádné prodeje, dividendy ani staking.",
    "Money below is converted {how}.": "Částky níže jsou přepočtené: {how}.",
    "Sales in {year}": "Prodeje v roce {year}",
    "Nothing was sold.": "Nic se neprodalo.",
    "Group": "Skupina",
    "Proceeds": "Příjmy",
    "Within the limit": "V limitu",
    "Held longer: proceeds": "Drženo déle: příjmy",
    "Held longer: profit": "Drženo déle: zisk",
    "Held shorter: proceeds": "Drženo kratší dobu: příjmy",
    "Held shorter: profit": "Drženo kratší dobu: zisk",
    "Profit not exempt": "Neosvobozený zisk",
    "Everything received for sales in the year.": "Vše přijaté za prodeje v roce.",
    "Whether the proceeds do not exceed {limit}.": "Zda příjmy nepřesáhnou {limit}.",
    "Proceeds minus what the sold units had cost.":
        "Příjmy minus pořizovací cena prodaných kusů.",
    "Zero within the limit; otherwise the profit on units held shorter. Fees are not "
    "deducted here.":
        "V limitu nula; jinak zisk z kusů držených kratší dobu. Poplatky se zde neodečítají.",
    "Held longer": "Drženo déle",
    "One line for every purchase a sale took units from.":
        "Jeden řádek pro každý nákup, ze kterého prodej vzal kusy.",
    "Dividends in {year}": "Dividendy v roce {year}",
    "None recorded.": "Nic zapsáno.",
    "Paid in": "Vyplaceno v",
    "Before tax": "Před zdaněním",
    "Received plus the tax you recorded as withheld.":
        "Přijato plus daň, kterou jste zapsali jako sraženou.",
    "Only where you entered it with the dividend.": "Jen tam, kde jste ji zadali s dividendou.",
    "Staking in {year}": "Staking v roce {year}",
    "Value when received": "Hodnota při přijetí",
    "Units received, less the ones taken back.": "Přijaté kusy, bez těch vzatých zpět.",
    "Each reward at the closing price of its day.":
        "Každá odměna za zavírací cenu svého dne.",
    "Lines using the rate you entered: {count}. The chosen rates have none for that currency "
    "or year (a unified rate is known only once its year is over).":
        "Řádky s kurzem, který jste zadali: {count}. Zvolené kurzy pro tu měnu nebo rok "
        "žádný nemají (jednotný kurz je známý až po skončení roku).",
    "What you hold today": "Co držíte dnes",
    "Held longer: quantity": "Drženo déle: množství",
    "Held longer: value": "Drženo déle: hodnota",
    "Held shorter: quantity": "Drženo kratší dobu: množství",
    "Held shorter: value": "Drženo kratší dobu: hodnota",
    "Next": "Další",
    "Next quantity": "Další množství",
    "Units held longer than {years} years: a sale of them today would be exempt.":
        "Kusy držené déle než {years} r.: jejich dnešní prodej by byl osvobozený.",
    "The first day the oldest of the units held shorter can be sold exempt.":
        "První den, kdy lze nejstarší z kusů držených kratší dobu prodat osvobozeně.",
    "How many units that is.": "Kolik je to kusů.",
    "Sales take the oldest units first, so the units held longer are the ones a sale would "
    "use up first.":
        "Prodeje berou nejstarší kusy jako první, takže kusy držené déle by prodej "
        "spotřeboval první.",

    # --- transactions -----------------------------------------------------------------------
    "Ledger": "Deník",
    "Manual valuations": "Ruční ocenění",
    "Add an instrument in Settings first.": "Nejdřív přidejte instrument v Nastavení.",
    "All": "Vše",
    "Kind": "Druh",
    "From": "Od",
    "To": "Do",
    "Transactions: {count}. Select a row to edit or delete it.":
        "Transakcí: {count}. Vyberte řádek, který chcete upravit nebo smazat.",
    "Price": "Cena",
    "Amount": "Částka",
    "Rate": "Kurz",
    "Fee": "Poplatek",
    "Tax": "Daň",
    "Note": "Poznámka",
    "Price per unit": "Cena za kus",
    "New units per old unit": "Nových kusů za starý",
    "Edit transaction": "Upravit transakci",
    "Add transaction": "Přidat transakci",
    "(optional)": "(nepovinné)",
    "{base} per 1 {currency}": "{base} za 1 {currency}",
    "Empty: the market rate of that day is used.": "Prázdné: použije se tržní kurz toho dne.",
    "Fee ({currency})": "Poplatek ({currency})",
    "Save changes": "Uložit změny",
    "Add": "Přidat",
    "{kind} of {ticker} on {day} changed.": "Změněno: {kind} {ticker} ze dne {day}.",
    "{kind} of {ticker} on {day} added.": "Přidáno: {kind} {ticker} ze dne {day}.",
    "Really delete": "Opravdu smazat",
    "Delete": "Smazat",
    "Transaction deleted.": "Transakce smazána.",
    "No instrument is valued by hand. Set that in Settings.":
        "Žádný instrument se neoceňuje ručně. Nastavte to v Nastavení.",
    "The total value of an instrument on a day, in its own currency. Deposits and "
    "withdrawals made on that day or later are added on top automatically.":
        "Celková hodnota instrumentu v daný den, v jeho vlastní měně. Vklady a výběry z toho "
        "dne a pozdější se k ní přičtou automaticky.",
    "Save": "Uložit",
    "Enter a value.": "Zadejte hodnotu.",
    "Value of {ticker} on {day} saved.": "Hodnota {ticker} ke dni {day} uložena.",
    "Some values share their day with a deposit or withdrawal, which is added on top of the "
    "value. If the value you entered already contained it, it is counted twice until the "
    "next value: lower the value by that amount, or move the value one day later.":
        "Některé hodnoty mají stejný den jako vklad nebo výběr, který se k hodnotě přičte. "
        "Pokud ho zadaná hodnota už obsahovala, počítá se dvakrát až do další hodnoty: "
        "snižte hodnotu o tu částku, nebo ji posuňte o den později.",
    "Added on top": "Přičteno navíc",
    "Deposits minus withdrawals recorded on the same day.":
        "Vklady minus výběry zapsané ve stejný den.",
    "Delete the value from {day}": "Smazat hodnotu ze dne {day}",
    "Valuation deleted.": "Ocenění smazáno.",

    # --- prices -----------------------------------------------------------------------------
    "No prices stored yet. Use Update prices in the sidebar.":
        "Zatím nejsou uložené žádné ceny. Použijte Aktualizovat ceny v postranním panelu.",
    "No exchange rates stored yet.": "Zatím nejsou uložené žádné kurzy.",
    "{currency} in {base}": "{currency} v {base}",
    "Close": "Zavírací cena",
    "The chart draws one point for every {days} stored days; the table has all of them.":
        "Graf kreslí jeden bod za každých {days} uložených dní; tabulka má všechny.",
    "Days: {count}, from {first} to {last}.": "Dní: {count}, od {first} do {last}.",

    # --- checks -----------------------------------------------------------------------------
    "Prices out of date": "Zastaralé ceny",
    "Manual values out of date": "Zastaralé ruční hodnoty",
    "Trade price far from the market": "Cena obchodu daleko od trhu",
    "Exchange rate far from the market": "Kurz daleko od trhu",
    "Tiny leftovers": "Drobné zbytky",
    "More sold than held": "Prodáno víc, než bylo drženo",
    "Dividends possibly not recorded": "Možná nezapsané dividendy",
    "Manual value on the day of a deposit": "Ruční hodnota v den vkladu",
    "Instruments you hold whose newest price or exchange rate is more than a week old. Their "
    "value is counted with that old number.":
        "Instrumenty, které držíte a jejichž nejnovější cena nebo kurz je starší než týden. "
        "Jejich hodnota se počítá s tím starým číslem.",
    "Instruments valued by hand whose newest value is more than three months old.":
        "Ručně oceňované instrumenty, jejichž nejnovější hodnota je starší než tři měsíce.",
    "Buys and sells whose price differs from that day's closing price by more than 15 %. "
    "Often a typing mistake, or a price entered in another currency.":
        "Nákupy a prodeje, jejichž cena se od zavírací ceny toho dne liší o víc než 15 %. "
        "Často překlep nebo cena zadaná v jiné měně.",
    "Trades whose exchange rate differs from that day's market rate by more than 3 %.":
        "Obchody, jejichž kurz se od tržního kurzu toho dne liší o víc než 3 %.",
    "Positions with less than a thousandth of what was ever acquired left. Usually a "
    "rounding remainder of a sale.":
        "Pozice, ve kterých zbývá méně než tisícina všeho, co bylo kdy pořízeno. Obvykle "
        "zbytek po zaokrouhlení prodeje.",
    "Instruments whose sales add up to more than was bought.":
        "Instrumenty, jejichž prodeje dávají dohromady víc, než bylo koupeno.",
    "The price data reports more dividends for the units you held than you recorded. "
    "Reports from the last two months are not counted.":
        "Cenová data hlásí pro kusy, které jste drželi, víc dividend, než jste zapsali. "
        "Hlášení z posledních dvou měsíců se nepočítají.",
    "A deposit or withdrawal on the day of a manual value is added on top of it. If the "
    "value already contained it, it is counted twice until the next value.":
        "Vklad nebo výběr v den ruční hodnoty se k ní přičte. Pokud ho hodnota už "
        "obsahovala, počítá se dvakrát až do další hodnoty.",
    "{recorded} recorded, {expected} expected": "zapsáno {recorded}, očekáváno {expected}",
    "newest value is from {day}": "nejnovější hodnota je z {day}",
    "{kind} of {amount} {currency}": "{kind} {amount} {currency}",
    "quantity is {quantity}": "množství je {quantity}",
    "no price at all": "žádná cena",
    "newest price is from {day}": "nejnovější cena je z {day}",
    "newest {currency} rate is from {day}": "nejnovější kurz {currency} je z {day}",
    "no {currency} rate at all": "žádný kurz {currency}",
    "{quantity} left": "zbývá {quantity}",
    "{quantity} left, worth {worth} {currency}": "zbývá {quantity} v hodnotě {worth} {currency}",
    "{kind} at {off} against the close ({price} {currency})":
        "{kind} o {off} oproti zavírací ceně ({price} {currency})",
    "{kind} at {rate}, market {market} ({off})": "{kind} za kurz {rate}, trh {market} ({off})",
    "Looked for in the active instruments every time this page opens. Nothing in your "
    "records is changed; correct what is really wrong in Transactions. What you looked at "
    "and found in order, mark as checked: it stays hidden unless the record changes.":
        "Hledá se v aktivních instrumentech při každém otevření stránky. Ve vašich záznamech "
        "se nic nemění; co je opravdu špatně, opravte v Transakcích. Co jste prohlédli a "
        "shledali v pořádku, označte jako zkontrolované: zůstane skryté, dokud se záznam "
        "nezmění.",
    "What": "Co",
    "Check": "Kontrola",
    "Mark the selected as checked ({count})": "Označit vybrané jako zkontrolované ({count})",
    "Mark all as checked ({count})": "Označit vše jako zkontrolované ({count})",
    "Nothing to look at.": "Není na co se dívat.",
    "Nothing found.": "Nic nenalezeno.",
    "Nothing found for: {checks}.": "Nic nenalezeno pro: {checks}.",
    "Checked ({count})": "Zkontrolováno ({count})",
    "Findings you marked as checked. Select rows to show them again.":
        "Nálezy, které jste označili jako zkontrolované. Vyberte řádky, které chcete znovu "
        "zobrazit.",
    "Show selected again": "Znovu zobrazit vybrané",

    # --- import / export --------------------------------------------------------------------
    "Export": "Export",
    "The database file is a complete backup: to restore it, put it where the config file "
    "points. The CSV files hold the same data in a form any spreadsheet can open.":
        "Soubor databáze je úplná záloha: k obnovení ho dejte tam, kam ukazuje konfigurační "
        "soubor. Soubory CSV obsahují stejná data ve tvaru, který otevře každá tabulka.",
    "Automatic backups are switched off (`backup_keep = 0` in the config file).":
        "Automatické zálohy jsou vypnuté (`backup_keep = 0` v konfiguračním souboru).",
    "Automatic backups: a copy is made before the first use on every day the data changed, "
    "and the last {keep} are kept. Copies in `{folder}`: {count}.":
        "Automatické zálohy: kopie se dělá před prvním použitím v každý den, kdy se data "
        "změnila, a uchovává se posledních {keep}. Kopií v `{folder}`: {count}.",
    "The newest is {name}.": "Nejnovější je {name}.",
    "Database file": "Soubor databáze",
    "All tables as CSV (zip)": "Všechny tabulky jako CSV (zip)",
    "Import transactions": "Import transakcí",
    "A CSV file with the columns {columns}. Only `date`, `ticker` and `kind` are always "
    "needed. Kinds: {kinds}. Files separated by semicolons may use decimal commas. The "
    "exported `transactions.csv` has exactly this layout. Instruments must exist already.":
        "Soubor CSV se sloupci {columns}. Vždy jsou potřeba jen `date`, `ticker` a `kind`. "
        "Druhy: {kinds}. Soubory oddělené středníky mohou používat desetinné čárky. "
        "Exportovaný `transactions.csv` má přesně tento tvar. Instrumenty už musí existovat.",
    "CSV file": "Soubor CSV",
    "The file has no rows.": "Soubor nemá žádné řádky.",
    "Rows read: **{rows}**. Usable: **{usable}**, with errors: **{bad}**, already in the "
    "database: **{duplicates}**.":
        "Načteno řádků: **{rows}**. Použitelných: **{usable}**, s chybami: **{bad}**, už v "
        "databázi: **{duplicates}**.",
    "Line {line}": "Řádek {line}",
    "…and {count} more.": "…a dalších {count}.",
    "already there": "už existuje",
    "Skip the rows that are already in the database ({count})":
        "Přeskočit řádky, které už jsou v databázi ({count})",
    "Nothing can be imported until every row is right. Fix the file and upload it again.":
        "Nic nelze importovat, dokud nejsou všechny řádky v pořádku. Opravte soubor a "
        "nahrajte ho znovu.",
    "Import transactions ({count})": "Importovat transakce ({count})",
    "Transactions imported: {count}.": "Importováno transakcí: {count}.",

    # --- settings ---------------------------------------------------------------------------
    "Database: `{path}` · Base currency: **{currency}** · Benchmark: **{benchmark}** (set in "
    "the config file)":
        "Databáze: `{path}` · Základní měna: **{currency}** · Benchmark: **{benchmark}** "
        "(nastavuje se v konfiguračním souboru)",
    "not set": "nenastaven",
    "Currencies": "Měny",
    "Code, e.g. USD": "Kód, např. USD",
    "Instrument types": "Typy instrumentů",
    "Name, e.g. etf": "Název, např. etf",
    "Sector and country": "Sektor a země",
    "Used for the spread on the Overview. Update prices fills them in from Yahoo for shares; "
    "funds and coins have none, so give them your own (e.g. World, Crypto). What you enter "
    "here is kept; clear both cells to let Yahoo fill them again.":
        "Používá se pro rozložení v Přehledu. Aktualizovat ceny je u akcií doplní z Yahoo; "
        "fondy a mince žádné nemají, takže jim dejte vlastní (např. Svět, Krypto). Co zde "
        "zadáte, se zachová; vymažte obě buňky, aby je Yahoo zase doplnilo.",
    "hand": "ručně",
    "Entered by": "Zadal",
    "Save sector and country": "Uložit sektor a zemi",
    "Sector and country saved for instruments: {count}.":
        "Sektor a země uloženy pro instrumentů: {count}.",
    "No changes.": "Žádné změny.",
    "Target allocation": "Cílové rozložení",
    "The share of your investments each type should have, in percent. The Overview then "
    "shows how far you are from it and where new money should go. Leave everything at 0 "
    "for no target.":
        "Podíl, který má mít každý typ ve vašich investicích, v procentech. Přehled pak "
        "ukáže, jak daleko od něj jste a kam mají jít nové peníze. Pro žádný cíl nechte vše "
        "na 0.",
    "Together {total} %.": "Dohromady {total} %.",
    "They have to add up to 100.": "Dohromady musí dát 100.",
    "Save targets": "Uložit cíle",
    "Target allocation saved.": "Cílové rozložení uloženo.",
    "Target allocation removed.": "Cílové rozložení odstraněno.",
    "Dividends in": "Dividendy v",
    "Valued by": "Oceňováno",
    "Yahoo symbol": "Symbol na Yahoo",
    "Active": "Aktivní",
    "Add at least one currency and one instrument type first.":
        "Nejdřív přidejte alespoň jednu měnu a jeden typ instrumentu.",
    "Add or edit": "Přidat nebo upravit",
    "New instrument": "Nový instrument",
    "Dividends paid in": "Dividendy vyplácené v",
    "Same as instrument": "Stejně jako instrument",
    "Quantity × price from Yahoo": "Množství × cena z Yahoo",
    "Value entered by hand": "Hodnota zadaná ručně",
    "Only if it differs from the ticker, e.g. BTC-EUR.":
        "Jen pokud se liší od tickeru, např. BTC-EUR.",
    "Add instrument": "Přidat instrument",
    "{ticker} saved.": "Uloženo: {ticker}.",
    "{ticker} still has transactions. Delete them first, or just make the instrument "
    "inactive.":
        "{ticker} má ještě transakce. Nejdřív je smažte, nebo instrument jen nastavte jako "
        "neaktivní.",
    "{ticker} deleted, with its stored prices and valuations.":
        "Smazáno: {ticker}, i s uloženými cenami a oceněními.",
    "An instrument with ticker '{ticker}' already exists.":
        "Instrument s tickerem „{ticker}“ už existuje.",
    "The ticker must not be empty.": "Ticker nesmí být prázdný.",
    "Could not save: {error}": "Nelze uložit: {error}",
    "'{value}' is not valid or already exists.": "„{value}“ není platné nebo už existuje.",
    "{value} added.": "Přidáno: {value}.",
    "Delete {item}": "Smazat {item}",
    "{item} is in use and cannot be deleted.": "{item} se používá a nelze smazat.",
    "{item} deleted.": "Smazáno: {item}.",

    # --- glossary ---------------------------------------------------------------------------
    "What the numbers in this app mean and how to read them.":
        "Co čísla v této aplikaci znamenají a jak je číst.",
    "Search": "Hledat",
    "e.g. P/E, dividend, drop": "např. P/E, dividenda, propad",
    "Shown on: {pages}": "Zobrazeno na: {pages}",
    "Nothing found. Try another word.": "Nic nenalezeno. Zkuste jiné slovo.",

    # --- messages from the core -------------------------------------------------------------
    "{ticker} {day}: no {currency} exchange rate known for this {kind}; counted with rate 1":
        "{ticker} {day}: pro tento {kind} není známý kurz {currency}; počítáno s kurzem 1",
    "date '{text}' is not YYYY-MM-DD or DD.MM.YYYY":
        "datum „{text}“ není RRRR-MM-DD ani DD.MM.RRRR",
    "The file needs the columns: {columns}": "Soubor potřebuje sloupce: {columns}",
    "Unknown columns: {unknown}. Allowed: {allowed}":
        "Neznámé sloupce: {unknown}. Povolené: {allowed}",
    "Fix the errors first (lines {lines}).": "Nejdřív opravte chyby (řádky {lines}).",
    "{column} '{text}' is not a number": "{column} „{text}“ není číslo",
    "more values than columns": "víc hodnot než sloupců",
    "unknown instrument '{ticker}'": "neznámý instrument „{ticker}“",
    "unknown currency '{currency}'": "neznámá měna „{currency}“",
    "unknown kind '{kind}'": "neznámý druh „{kind}“",
    "A fee transaction needs a 'fee' greater than zero":
        "Transakce poplatku potřebuje 'fee' větší než nula",
    "'{field}' must be a finite decimal number": "'{field}' musí být konečné desetinné číslo",
    "A {kind} transaction cannot have '{field}'": "Transakce {kind} nemůže mít '{field}'",
    "'{field}' must be greater than zero": "'{field}' musí být větší než nula",
    "'{field}' must be zero or more": "'{field}' musí být nula nebo víc",
    "A {kind} transaction needs '{field}'": "Transakce {kind} potřebuje '{field}'",
    "A target share cannot be negative": "Cílový podíl nemůže být záporný",
    "The target shares must add up to 100, not {total}":
        "Cílové podíly musí dát dohromady 100, ne {total}",
    "A valuation must be a finite number, zero or more":
        "Ocenění musí být konečné číslo, nula nebo víc",
    "inflation {region}": "inflace {region}",
    "benchmark {symbol}": "benchmark {symbol}",
    "ČNB rates {year}": "kurzy ČNB {year}",
    "sector and country {ticker}": "sektor a země {ticker}",
    "fundamentals {ticker}": "fundamenty {ticker}",
    "older prices {ticker}": "starší ceny {ticker}",
}
# fmt: on
