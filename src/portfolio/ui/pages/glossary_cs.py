"""The glossary in Czech: the same terms, in the same order, as ``glossary.SECTIONS``."""

from portfolio.ui.pages.glossary import Term

SECTIONS_CS: dict[str, list[Term]] = {
    "Vaše peníze": [
        Term(
            "Hodnota",
            "Kolik má dnes cenu to, co držíte: množství × poslední cena × kurz toho dne. U "
            "účtů oceňovaných ručně poslední zadaná hodnota plus vklady a minus výběry od té "
            "doby.",
            "Chybějící ceny nebo kurzy jsou uvedené nad součty; takové instrumenty se tam "
            "počítají jako nula.",
            "Přehled, Grafy",
        ),
        Term(
            "Pořizovací cena",
            "Kolik vás stály kusy, které ještě držíte, v kurzech dnů, kdy jste je koupili.",
            "Prodeje spotřebují nejstarší kusy jako první (FIFO), takže po prodeji je to "
            "pořizovací cena novějších kusů, které zůstaly.",
            "Přehled",
        ),
        Term(
            "FIFO",
            "First in, first out: prodej bere kusy koupené jako první.",
            "Rozhoduje o tom, které nákupy prodej realizuje, a tím o realizovaném zisku a o "
            "době držení pro daně.",
        ),
        Term(
            "Nerealizovaný zisk",
            "Hodnota − pořizovací cena toho, co ještě držíte. Zisk, který byste měli, kdybyste "
            "dnes prodali.",
            "Procento vedle něj je vztažené k pořizovací ceně.",
            "Přehled",
        ),
        Term(
            "Z ceny, z kurzu, odměny ze stakingu",
            "Nerealizovaný zisk rozdělený podle toho, odkud pochází. Z kurzu: kolik stály vaše "
            "kusy v jejich vlastní měně při dnešním kurzu, minus kolik jste zaplatili. Odměny "
            "ze stakingu: kusy zdarma, které ještě držíte, za dnešní cenu. Z ceny: zbytek.",
            "Akcie v EUR může v eurech ztrácet a v korunách přesto vydělávat, když euro "
            "posílilo, a naopak.",
            "Přehled",
        ),
        Term(
            "Realizovaný zisk",
            "U prodaných kusů: kolik jste za ně dostali − kolik stály.",
            "Ztracené kusy (prodané za cenu 0) se počítají celou pořizovací cenou jako ztráta.",
            "Přehled (Prodeje)",
        ),
        Term(
            "Zisk, čistý zisk",
            "Zisk = nerealizovaný + realizovaný. Čistý zisk = zisk + dividendy − poplatky.",
            "Čistý zisk je to, co vám investice opravdu vydělaly celkem.",
            "Přehled, Grafy",
        ),
        Term(
            "Stále investováno",
            "Dosavadní nákupy a vklady minus prodeje a výběry.",
            "Hodnota nad touto čarou znamená zisk; mezera mezi oběma čarami v Grafech je zisk.",
            "Grafy",
        ),
    ],
    "Výnosy": [
        Term(
            "Výnos (časově vážený)",
            "Jak si vedly samotné investice, jako by se žádné peníze nepřidávaly ani "
            "nevybíraly. Dny se řetězí jeden za druhým.",
            "Hodí se pro srovnání s fondem nebo s benchmarkem. Malý účet na začátku ho může "
            "hodně zvětšit: +100 % z 10 000 se počítá stejně jako z 1 000 000. Není ročně.",
            "Výkonnost",
        ),
        Term(
            "Roční výnos vašich peněz (XIRR)",
            "Roční úroková sazba, která by z vašich plateb, ve dnech, kdy jste je udělali, "
            "vytvořila to, co máte dnes.",
            "Tohle jste na svých penězích opravdu vydělali. Je nižší než časově vážený výnos, "
            "když jste hodně peněz přidali těsně před poklesem. Ukazuje se pro období od tří "
            "měsíců.",
            "Výkonnost",
        ),
        Term(
            "Nejhlubší propad (drawdown)",
            "Největší pokles časově váženého výnosu od maxima k minimu v daném období. „Nyní "
            "pod maximem“ říká, jak daleko pod svým nejlepším bodem je dnes.",
            "Ukazuje, jak zle bylo, což o riziku řekne víc než průměrné výkyvy. Měří se na "
            "výnosu, takže nové peníze pokles neschovají.",
            "Výkonnost, Grafy",
        ),
        Term(
            "Po měsících",
            "Časově vážený výnos každého kalendářního měsíce.",
            "Zelené měsíce vydělaly, červené prodělaly.",
            "Výkonnost",
        ),
        Term(
            "Podíl na zisku",
            "Čistý zisk instrumentu jako podíl na čistém zisku všeho zobrazeného.",
            "Které pozice udělaly výsledek. Prázdné, když celý výběr prodělal.",
            "Výkonnost",
        ),
        Term(
            "Inflace",
            "O kolik vzrostly spotřebitelské ceny v daném období, podle harmonizovaného indexu "
            "Eurostatu pro zemi nastavenou v konfiguračním souboru (výchozí CZ).",
            "Index vychází asi dva týdny po konci měsíce; do té doby se ceny počítají jako "
            "nezměněné od posledního zveřejněného měsíce a stránka to uvádí.",
            "Výkonnost",
        ),
        Term(
            "Výnos po inflaci (reálný výnos)",
            "Kolik je výnos v dnešních cenách: (1 + výnos) / (1 + inflace) − 1. 10 % při "
            "4% inflaci je 5,8 %.",
            "O tolik si můžete koupit víc než dřív. Blízko nule: peníze si jen udržely "
            "hodnotu, což je u spořicích účtů běžné.",
            "Výkonnost",
        ),
        Term(
            "Výnos benchmarku",
            "Co by vyneslo držení benchmarku (indexového fondu nastaveného v konfiguračním "
            "souboru) po celé období, s reinvestovanými dividendami.",
            "Porovnávejte ho s časově váženým výnosem.",
            "Výkonnost",
        ),
        Term(
            "Vaše peníze v benchmarku, náskok nebo ztráta",
            "Stejné částky vložené a vybrané ve stejné dny, ale vložené do benchmarku. "
            "„Jste napřed o“ je vaše dnešní hodnota minus to, kolik by měly ony.",
            "Nejférovější srovnání vašich rozhodnutí s prostým nákupem indexu. Strana "
            "benchmarku neplatí poplatky ani daně, takže má malou výhodu.",
            "Výkonnost",
        ),
    ],
    "Ocenění firmy": [
        Term(
            "EPS",
            "Zisk na akcii: čistý zisk firmy vydělený počtem jejích akcií.",
            "Všechny ukazatele níže porovnávají cenu jedné akcie s takovým číslem na akcii.",
            "Fundamenty",
        ),
        Term(
            "Posledních dvanáct měsíců (TTM)",
            "Součet posledních čtyř čtvrtletí, nebo poslední rok, když čtvrtletí chybí.",
            "Používá se pro zisk a tržby, aby ukazatel nevychýlilo jedno silné nebo slabé "
            "čtvrtletí.",
            "Fundamenty",
        ),
        Term(
            "P/E",
            "Cena / zisk na akcii za posledních dvanáct měsíců. Kolik let dnešního zisku cena "
            "zaplatí.",
            "Nižší je levnější. Běžné je zhruba 10–20, rostoucí firmy mívají víc, banky a "
            "energetika méně. Prázdné, když firma byla ve ztrátě. Jednorázový zisk nebo ztráta "
            "ho zkreslí.",
            "Fundamenty",
        ),
        Term(
            "Obvyklé P/E",
            "Medián denního P/E za všechny dny, kdy se dalo spočítat (od „Od“ do dneška).",
            "Dnešní P/E pod ním: akcie je vzhledem ke svému zisku levnější, než bývala. "
            "Historie je asi 15 let u amerických firem (SEC), u ostatních jen asi 3, takže "
            "porovnávejte akcii samu se sebou, ne s jinou.",
            "Fundamenty",
        ),
        Term(
            "Forward P/E",
            "Cena / zisk, který analytici čekají na příští rok (podle Yahoo).",
            "Nižší než P/E: analytici čekají růst zisku; vyšší: pokles; záporné: očekávaná "
            "ztráta. Je to předpověď a často se mýlí, a malé firmy ji nemají.",
            "Fundamenty",
        ),
        Term(
            "P/B",
            "Cena / účetní hodnota na akcii; účetní hodnota je to, co firma vlastní, minus "
            "to, co dluží (vlastní kapitál).",
            "Kolem 1 znamená, že akcie stojí tolik, co firma vlastní. Užitečné u bank a "
            "průmyslu; u softwaru nebo značek účetní hodnota mnoho neříká, takže P/B je vysoké.",
            "Fundamenty",
        ),
        Term(
            "P/S",
            "Cena / tržby na akcii za posledních dvanáct měsíců.",
            "Funguje i u firem, které ještě nemají zisk. Porovnávejte v rámci jednoho oboru: "
            "obchody s tenkými maržemi mají nízké P/S, software vysoké.",
            "Fundamenty",
        ),
        Term(
            "EV/EBITDA",
            "Hodnota celé firmy včetně dluhu (enterprise value: tržní hodnota + dluh − "
            "hotovost) / její provozní zisk před úroky, daněmi a odpisy (EBITDA). Podle Yahoo.",
            "Na rozdíl od P/E počítá s dluhem, takže porovná firmy financované různě. Běžné "
            "je zhruba 6–10, podle oboru. Nemá smysl u bank a pojišťoven a když je záporné "
            "(provozní ztráta).",
            "Fundamenty",
        ),
        Term(
            "Tržní kapitalizace",
            "Cena všech akcií firmy dohromady.",
            "Velikost firmy, jak ji oceňuje trh.",
            "Fundamenty",
        ),
        Term(
            "Depozitní certifikát, třída akcií",
            "Obchodovaná jednotka, která není jedna akcie firmy: certifikát může odpovídat "
            "čtvrtině akcie, akcie třídy B 1/1500 akcie třídy A.",
            "Aplikace dopočítá poměr z tržní hodnoty, kterou hlásí Yahoo, a uvede ho na "
            "stránce, takže ukazatele jsou na jednotku, kterou držíte.",
            "Fundamenty",
        ),
    ],
    "Dividendy": [
        Term(
            "Dividendový výnos",
            "Dividendy za posledních dvanáct měsíců / dnešní cena.",
            "Kolik akcie každý rok vyplácí, v procentech toho, co stojí teď. Velmi vysoký "
            "výnos často znamená, že cena spadla, protože se čeká snížení dividendy.",
            "Fundamenty, Dividendy",
        ),
        Term(
            "Výnos z pořizovací ceny",
            "Dividendy za posledních dvanáct měsíců / kolik jste za akcie zaplatili.",
            "Kolik vám vyplácí váš vlastní nákup. Roste, když firma zvyšuje dividendu.",
            "Dividendy",
        ),
        Term(
            "Očekávané dividendy",
            "Co podle cenových dat bylo vyplaceno na kusy, které jste drželi, před zdaněním.",
            "Víc očekávaných než zapsaných může znamenat dividendu, kterou jste zapomněli "
            "zadat. Platby přicházejí několik týdnů po datu v cenových datech.",
            "Dividendy, Kontroly",
        ),
    ],
    "Rozložení": [
        Term(
            "Podíl",
            "Část hodnoty všech investic připadající na instrument, typ nebo měnu.",
            "Měna je ta, ve které je instrument oceněn: ETF v EUR držící americké akcie se "
            "počítá jako EUR.",
            "Přehled",
        ),
        Term(
            "Sektor, země",
            "Čím se firma zabývá (Technology, Utilities, …) a kde sídlí, podle Yahoo. Přehled "
            "podle obou sčítá hodnotu.",
            "Fondy a mince vlastní nemají a ukazují se podle typu v závorce; jejich můžete "
            "nastavit v Nastavení. Rozložení uvnitř světového fondu se nezkoumá.",
            "Přehled, Nastavení",
        ),
        Term(
            "Cíl, do cíle, koupit teď",
            "Cíl: podíl, který má typ mít (nastavuje se v Nastavení). Do cíle: kolik dokoupit "
            "(záporné: o kolik je ho moc). Koupit teď: jak rozdělit nové peníze, které zadáte.",
            "Nové peníze jdou do typů nejvíc pod cílem; nic se neprodává.",
            "Přehled",
        ),
    ],
    "Daně": [
        Term(
            "Drženo déle, drženo kratší dobu",
            "Kusy držené déle než doba držení v konfiguračním souboru (výchozí 3 roky) a ostatní.",
            "Prodej kusů držených déle se počítá jako osvobozený. „Další“ je den, kdy tam "
            "dojde nejstarší z ostatních.",
            "Daně",
        ),
        Term(
            "V limitu",
            "Zda roční příjmy ze všech prodejů zůstanou pod limitem v konfiguračním souboru "
            "(výchozí 100 000), počítáno zvlášť pro cenné papíry a kryptoměny.",
            "V limitu se všechny prodeje roku počítají jako osvobozené.",
            "Daně",
        ),
        Term(
            "Neosvobozený zisk",
            "Zisk z kusů držených kratší dobu v roce nad limitem.",
            "Výchozí bod, ne daňové přiznání: poplatky se neodečítají, kurzy jsou ty, které "
            "jste zadali, a na každý rok se použijí stejná pravidla.",
            "Daně",
        ),
    ],
    "Kurzy pro daně": [
        Term(
            "Kurz ČNB",
            "Kurz, který Česká národní banka vyhlašuje každý pracovní den. České daňové "
            "přiznání jím přepočítává cizí měny.",
            "Na víkend nebo svátek platí poslední kurz vyhlášený před ním.",
            "Daně",
        ),
        Term(
            "Jednotný kurz",
            "Jeden kurz na měnu pro celý rok: průměr kurzů ČNB platných poslední den každého "
            "měsíce, jak ho zveřejňuje Finanční správa.",
            "Použijete buď denní kurzy, nebo jednotné, pro celý rok. Nákup z dřívějšího roku "
            "se počítá jednotným kurzem toho roku. Známý až po skončení roku.",
            "Daně",
        ),
    ],
    "Data": [
        Term(
            "Split",
            "Firma rozdělí každou akcii na několik (10 za 1: deset nových akcií za jednu "
            "starou). Nic se nezíská ani neztratí.",
            "Stažené ceny jsou přepočítané na dnešní akcie. Když je hlášen split, aplikace se "
            "zeptá, zda ho potřebují vaše množství.",
            "každá stránka, když nějaký čeká",
        ),
        Term(
            "Kontroly",
            "Záznamy, které vypadají špatně nebo zastarale: staré ceny, ceny obchodů nebo "
            "kurzy daleko od trhu, drobné zbytky, chybějící dividendy.",
            "Nález může být v pořádku: označte ho jako zkontrolovaný a zůstane skrytý, dokud "
            "se záznam nezmění.",
            "Kontroly",
        ),
    ],
}
