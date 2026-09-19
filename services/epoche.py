"""Mondo EPOCHE: guerre storiche."""

from services.models import card

ITEMS = (
    card(
        id="greco",
        kind="war",
        world="epoche",
        emoji="🏛️",
        title="Guerre greco-persiane",
        subtitle="inizio V secolo a.C.",
        era="ant",
        tags=("antichità", "grecia", "persia", "maratona"),
        aliases=("persiani", "termeopili", "salamina", "serse", "dario"),
        summary=(
            "Serie di scontri tra le città-stato greche e l'Impero achemenide. "
            "Restano tra i primi conflitti di cui abbiamo narrazioni storiche articolate, "
            "da Erodoto in poi."
        ),
        fields=(
            ("📅 Date", "circa 499–449 a.C."),
            ("🌍 Teatri", "Grecia, Egeo, Ionia, Cipro"),
            ("👥 Attori", "città greche (Atene, Sparta) · Impero persiano"),
        ),
        sections=(
            ("Andamento",
             "Dopo la rivolta ionica, due spedizioni persiane verso la Grecia continentale. "
             "La prima si ferma a Maratona; la seconda, sotto Serse, occupa Atene ma viene "
             "contenuta in mare a Salamina e sulla terra a Platea."),
            ("Conseguenze",
             "Le poleis greche conservano l'autonomia. Atene rafforza la propria flotta e "
             "la Lega delio-attica. Il racconto di queste guerre diventa un mito politico "
             "sulla libertà delle città contro un grande impero."),
        ),
        related=("maratona", "erodoto"),
    ),
    card(
        id="punic",
        kind="war",
        world="epoche",
        emoji="⚓",
        title="Guerre puniche",
        subtitle="264–146 a.C.",
        era="ant",
        tags=("roma", "cartagine", "mediterraneo"),
        aliases=("annibale", "canne", "scipione", "cartagine", "punica"),
        summary=(
            "Tre guerre tra Roma e Cartagine per il controllo del Mediterraneo occidentale. "
            "Cambiano la scala della potenza romana: da città italica a potenza marittima."
        ),
        fields=(
            ("📅 Date", "264–241 · 218–201 · 149–146 a.C."),
            ("🌍 Teatri", "Sicilia, Italia, Hispania, Africa, mare"),
            ("👥 Attori", "Repubblica romana · Cartagine"),
        ),
        sections=(
            ("Andamento",
             "La prima guerra è soprattutto navale, intorno alla Sicilia. La seconda è la "
             "campagna di Annibale in Italia, con Canne e la successiva controffensiva di "
             "Scipione in Africa. La terza si chiude con la distruzione di Cartagine."),
            ("Conseguenze",
             "Roma resta sola sul Mediterraneo occidentale. Il bottino, le province e le "
             "tensioni interne preparano le trasformazioni della tarda Repubblica."),
        ),
        related=("canne", "annibale", "roma"),
    ),
    card(
        id="gall",
        kind="war",
        world="epoche",
        emoji="🐺",
        title="Guerre galliche",
        subtitle="58–50 a.C.",
        era="ant",
        tags=("roma", "gallia", "cesare"),
        aliases=("cesare", "alesia", "vercingetorige", "commentarii"),
        summary=(
            "Campagne di Gaio Giulio Cesare in Gallia, narrate da lui stesso nei "
            "Commentarii. Sono insieme conquista, propaganda politica e documento letterario."
        ),
        fields=(
            ("📅 Date", "58–50 a.C."),
            ("🌍 Teatri", "Gallia, Belgio, Britannia, Germania di confine"),
            ("👥 Attori", "Cesare e le legioni · coalizioni galliche"),
        ),
        sections=(
            ("Andamento",
             "Interventi successivi contro elvezi, belgi, veneti e, nel 52 a.C., la rivolta "
             "guidata da Vercingetorige, chiusa ad Alesia. Cesare racconta spedizioni oltre "
             "il Reno e in Britannia come dimostrazione di portata."),
            ("Conseguenze",
             "La Gallia entra nell'orbita romana. Il prestigio e le risorse di Cesare "
             "pesano sulla crisi della Repubblica. I Commentarii restano una fonte, da "
             "leggere come resoconto di parte."),
        ),
        related=("alesia", "cesare", "roma"),
    ),
    card(
        id="croci",
        kind="war",
        world="epoche",
        emoji="✝️",
        title="Crociate",
        subtitle="XI–XIII secolo",
        era="med",
        tags=("medioevo", "mediterraneo", "gerusalemme"),
        aliases=("gerusalemme", "saladino", "templari", "crociata"),
        summary=(
            "Spedizioni militari e pellegrinaggi armati promossi da poteri occidentali "
            "verso il Levante, con obiettivi religiosi, politici e commerciali intrecciati."
        ),
        fields=(
            ("📅 Date", "soprattutto 1096–1291"),
            ("🌍 Teatri", "Anatolia, Siria, Palestina, Egitto, anche Balcani e Baltikum"),
            ("👥 Attori", "papato, principati franchi, Bisanzio, dinastie islamiche"),
        ),
        sections=(
            ("Andamento",
             "La prima crociata porta alla nascita di Stati latini in Oriente. Le successive "
             "tentano di difenderli o di riprenderli, con esiti diversi: dalla ripresa di "
             "Gerusalemme da parte di Saladino alla Quarta crociata che sackeggia Costantinopoli."),
            ("Conseguenze",
             "Contatti, scambi e ostilità durature tra Mediterraneo latino, bizantino e "
             "islamico. In Europa, rafforzamento di ordini militari e di reti commerciali. "
             "Oggi il termine va usato con cura storica, non come etichetta polemica."),
        ),
        related=("gerusalemme", "medioevo"),
    ),
    card(
        id="100y",
        kind="war",
        world="epoche",
        emoji="👑",
        title="Guerra dei Cent'anni",
        subtitle="1337–1453",
        era="med",
        tags=("francia", "inghilterra", "medioevo"),
        aliases=("azincourt", "giovanna", "crecy", "poitiers", "plantageneti"),
        summary=(
            "Lungo conflitto dinastico tra i re d'Inghilterra e di Francia per la corona "
            "francese e i feudi continentali. Non è una guerra continua: è fatta di tregue, "
            "riprese e guerre civili interne."
        ),
        fields=(
            ("📅 Date", "1337–1453"),
            ("🌍 Teatri", "Francia settentrionale e sud-ovest, Canale, Fiandre"),
            ("👥 Attori", "Plantageneti, Valois, Borgogna, alleati scozzesi e imperiali"),
        ),
        sections=(
            ("Andamento",
             "Vittorie inglesi a Crécy, Poitiers e Azincourt; poi la ripresa francese, "
             "segnata anche dalla figura di Giovanna d'Arco, fino all'uscita inglese dal "
             "continente salvo Calais."),
            ("Conseguenze",
             "Si definiscono identità monarchiche più territoriali. In Francia si rafforza "
             "la corona; in Inghilterra le tensioni interne preludono alla Guerra delle Due Rose."),
        ),
        related=("azincourt", "giovanna", "francia"),
    ),
    card(
        id="mongo",
        kind="war",
        world="epoche",
        emoji="🐎",
        title="Espansione mongola",
        subtitle="XIII secolo",
        era="med",
        tags=("steppa", "asia", "europa"),
        aliases=("gengis", "khan", "mongoli", "orda"),
        summary=(
            "Le campagne dell'Impero mongolo uniscono, in pochi decenni, spazi dalla Cina "
            "all'Europa orientale. È una storia di mobilità, diplomazia della paura e "
            "amministrazione degli spazi conquistati."
        ),
        fields=(
            ("📅 Date", "soprattutto 1206–1279"),
            ("🌍 Teatri", "Asia centrale, Cina, Persia, Rus', Ungheria, Medio Oriente"),
            ("👥 Attori", "linee di Gengis Khan · Stati cinesi, islamici, slavi, europei"),
        ),
        sections=(
            ("Andamento",
             "Unificazione delle steppe, poi ondate successive verso nord della Cina, "
             "Khwarezm, Rus' e, nel 1241, Ungheria e Polonia. L'impero si frammenta in khanati."),
            ("Conseguenze",
             "Rotte commerciali più sicure in alcuni tratti dell'Eurasia (la cosiddetta "
             "Pax mongolica), scambi di saperi e tecnologie, e al tempo stesso distruzioni "
             "documentate di città. Non è un blocco unico: ogni khanato ha una storia propria."),
        ),
        related=("logistica",),
    ),
    card(
        id="30y",
        kind="war",
        world="epoche",
        emoji="✝️",
        title="Guerra dei Trent'anni",
        subtitle="1618–1648",
        era="mod",
        tags=("germania", "europa", "westfalia"),
        aliases=("westfalia", "boemia", "gustavo adolfo", "trenta anni"),
        summary=(
            "Conflitto europeo che parte da una crisi boema e religiosa e diventa una "
            "guerra tra dinastie per l'equilibrio del Sacro Romano Impero e d'Europa."
        ),
        fields=(
            ("📅 Date", "1618–1648"),
            ("🌍 Teatri", "Impero, Paesi Bassi, Italia settentrionale, Penisola iberica"),
            ("👥 Attori", "Asburgo, principi tedeschi, Svezia, Francia, Spagna, Danimarca"),
        ),
        sections=(
            ("Andamento",
             "Fasi boema, danese, svedese e francese. Armate mercenarie, saccheggi e "
             "carestie pesano sulla popolazione civile più delle battaglie campali."),
            ("Conseguenze",
             "I trattati di Westfalia (1648) ridisegnano diritti dei principi e diplomazia "
             "europea. In molte regioni tedesche il bilancio demografico resta un trauma "
             "lungo decenni."),
        ),
        related=("westfalia", "logistica"),
    ),
    card(
        id="napo",
        kind="war",
        world="epoche",
        emoji="🦅",
        title="Guerre napoleoniche",
        subtitle="1803–1815",
        era="mod",
        tags=("francia", "europa", "coalizioni"),
        aliases=("napoleone", "waterloo", "austerlitz", "mosca", "wagram"),
        summary=(
            "Guerre tra la Francia di Napoleone e successive coalizioni europee. "
            "Mescolano rivoluzione istituzionale, leva di massa e diplomazia dei congressi."
        ),
        fields=(
            ("📅 Date", "1803–1815 (con radici nelle guerre rivoluzionarie)"),
            ("🌍 Teatri", "Europa, Egitto, Atlantico, Caraibi"),
            ("👥 Attori", "Francia imperiale · Gran Bretagna, Austria, Prussia, Russia, Spagna"),
        ),
        sections=(
            ("Andamento",
             "Vittorie francesi fino al 1809 circa, blocco continentale, campagna di Russia "
             "del 1812, crollo del 1814, Cento giorni e Waterloo."),
            ("Conseguenze",
             "Il Congresso di Vienna tenta un ordine restaurato. Restano il Code civil, "
             "la leva nazionale e l'idea di guerra tra Stati-nazione. L'Italia napoleonica "
             "cambia mappe e amministrazioni."),
        ),
        related=("waterloo", "napoleone", "vienna"),
    ),
    card(
        id="ww1",
        kind="war",
        world="epoche",
        emoji="🪖",
        title="Prima guerra mondiale",
        subtitle="1914–1918",
        era="con",
        tags=("trincee", "europa", "imperi"),
        aliases=("grande guerra", "somme", "verdun", "piave", "1914", "1918"),
        summary=(
            "Guerra industriale tra alleanze europee, poi mondiale. Trincee, artiglieria "
            "e mobilitazione totale delle società. Il fronte italiano corre sulle Alpi e sul Piave."
        ),
        fields=(
            ("📅 Date", "28 luglio 1914 – 11 novembre 1918"),
            ("🌍 Teatri", "Francia-Belgio, Alpi, Balcani, Medio Oriente, Africa, mari"),
            ("👥 Attori", "Triplice Intesa e alleati · Imperi centrali"),
        ),
        sections=(
            ("Andamento",
             "Guerra di movimento nel 1914, poi stallo sul fronte occidentale. A est e in "
             "Medio Oriente i fronti sono più mobili. L'Italia entra nel 1915. Nel 1917–18 "
             "arrivano gli Stati Uniti e crollano gli imperi centrali e russo."),
            ("Conseguenze",
             "Milioni di morti, influenza spagnola, nuovi Stati in Europa orientale, "
             "trattati di pace controversi. La «vittoria mutilata» pesa sulla politica italiana."),
        ),
        related=("somme", "trincee", "versailles", "genio"),
    ),
    card(
        id="ww2",
        kind="war",
        world="epoche",
        emoji="🌍",
        title="Seconda guerra mondiale",
        subtitle="1939–1945",
        era="con",
        tags=("mondiale", "shoah", "resistenza"),
        aliases=("stalingrado", "normandia", "midway", "hitler", "1940", "1945", "elalamein"),
        summary=(
            "Conflitto planetario tra Asse e Alleati. Comprende guerra convenzionale, "
            "occupazione, sterminio e resistenze. È il conflitto più documentato del XX secolo."
        ),
        fields=(
            ("📅 Date", "1 settembre 1939 – 2 settembre 1945"),
            ("🌍 Teatri", "Europa, Nordafrica, Atlantico, Pacifico, Asia orientale, URSS"),
            ("👥 Attori", "Germania, Italia, Giappone · Regno Unito, URSS, USA, Cina, governi in esilio"),
        ),
        sections=(
            ("Andamento",
             "Espansione dell'Asse 1939–41; invasione dell'URSS e attacco a Pearl Harbor; "
             "svolta 1942–43 (Stalingrado, El Alamein, Midway); aperture in Italia e in "
             "Normandia; resa tedesca a maggio 1945 e giapponese a settembre."),
            ("Conseguenze",
             "Shoah e crimini di massa processati a Norimberga e Tokyo. ONU, bipolarismo, "
             "decolonizzazione. In Italia: 8 settembre, Resistenza, Repubblica."),
        ),
        related=("stlg", "normandia", "midway", "onu", "t34", "spitfire"),
    ),
    card(
        id="cold",
        kind="war",
        world="epoche",
        emoji="❄️",
        title="Guerra fredda",
        subtitle="circa 1947–1991",
        era="con",
        tags=("usa", "urss", "nucleare", "blocchi"),
        aliases=("nato", "patto di varsavia", "cuba", "muro", "berlino"),
        summary=(
            "Confronto politico, ideologico e militare tra Stati Uniti e Unione Sovietica "
            "senza guerra diretta tra le due superpotenze, ma con crisi, corse agli armamenti "
            "e guerre per procura."
        ),
        fields=(
            ("📅 Date", "convenzionalmente 1947–1991"),
            ("🌍 Teatri", "Europa, Corea, Vietnam, Cuba, Afghanistan, spazio, mare"),
            ("👥 Attori", "USA e alleati NATO · URSS e Patto di Varsavia · non allineati"),
        ),
        sections=(
            ("Andamento",
             "Blocco di Berlino, NATO, Corea, crisi di Cuba, distensione, nuova corsa negli "
             "anni Ottanta, riforme sovietiche e dissoluzione dell'URSS."),
            ("Conseguenze",
             "Istituzioni di sicurezza durature, proliferazione nucleare regolamentata a "
             "trattati, corsa spaziale. La memoria è ancora politica: va letta sui documenti, "
             "non sui miti dei due campi."),
        ),
        related=("nato", "sputnik", "onu", "usa", "satcom"),
    ),
)
