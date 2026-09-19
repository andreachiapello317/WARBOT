"""Mondo FERRO: equipaggiamento, mezzi, fortificazioni."""

from services.models import card

ITEMS = (
    card(
        id="elmetto",
        kind="gear",
        world="ferro",
        emoji="🪖",
        title="Elmetto",
        subtitle="dalla cresta all'acciaio",
        era="",
        tags=("individuale", "protezione"),
        aliases=("casco", "adrian", "stahlhelm", "brodie"),
        summary=(
            "Protezione della testa. Elmi antichi in bronzo e ferro, celate medievali, "
            "poi elmetti d'acciaio di massa nella Grande Guerra (Adrian, Brodie, Stahlhelm)."
        ),
        fields=(
            ("Epoche", "bronzo · medioevo · 1915–oggi"),
            ("Funzione storica", "colpi di sciabola, schegge, crolli di trincea"),
        ),
        sections=(
            ("Storia",
             "L'elmo è status e protezione. Nel 1915 gli eserciti europei lo reintroducono "
             "in acciaio perché le schegge di artiglieria uccidono più delle baionette. "
             "I modelli diventano icone nazionali."),
            ("Nota",
             "Niente spessori, materiali contemporanei o prove balistiche: solo storia visibile."),
        ),
        related=("fanteria", "ww1"),
    ),
    card(
        id="uniforme",
        kind="gear",
        world="ferro",
        emoji="🧥",
        title="Uniforme",
        subtitle="riconoscersi, nascondersi, appartenere",
        era="",
        tags=("individuale", "simbolo"),
        aliases=("panno", "kaki", "feldgrau", "grigioverde"),
        summary=(
            "L'abito di un esercito racconta politica e tecnologia: livree d'ancien régime, "
            "blu e rosso da parata, poi kaki e grigioverde quando il fucile a ripetizione "
            "rende visibile chi si veste da teatro."
        ),
        fields=(
            ("Funzione", "identità di corpo, grado, mimetismo d'epoca"),
        ),
        sections=(
            ("Evoluzione",
             "Dal panno colorato al mimetico. Distintivi, alamari, fregi: un linguaggio. "
             "I musei di uniformologia sono una porta seria sulla storia sociale degli eserciti."),
        ),
        related=("fanteria", "ufficiali"),
    ),
    card(
        id="armatura",
        kind="gear",
        world="ferro",
        emoji="🛡️",
        title="Armature e scudi",
        subtitle="protezione pre-polvere da sparo",
        era="med",
        tags=("storico", "metallo"),
        aliases=("lorica", "usbergo", "scudo", "cotta"),
        summary=(
            "Lorica romana, cotte di maglia, piastre tardomedievali, scudi oplitici e "
            "pavesi. Oggetti di mestiere, di rango e di parata."
        ),
        fields=(
            ("Periodo", "antichità – XVI secolo (poi cerimoniale)"),
        ),
        sections=(
            ("Storia",
             "La piastra completa è tarda e costosa. L'arrivo delle armi da fuoco la rende "
             "gradualmente inutile in campo, non in corteo. Gli scudi spariscono quando "
             "le due mani servono al fucile."),
            ("Nota",
             "Descriviamo pezzi da museo, non come ricostruire protezioni."),
        ),
        related=("fanteria", "azincourt"),
    ),
    card(
        id="arcieri",
        kind="gear",
        world="ferro",
        emoji="🏹",
        title="Archi e lance",
        subtitle="armi lunghe della pre-modernità",
        era="med",
        tags=("storico",),
        aliases=("longbow", "picca", "lancia", "giavellotto"),
        summary=(
            "Arco lungo inglese, arco composito delle steppe, picche svizzere e lance da "
            "cavalleria. Per secoli decidono distanze e formazioni."
        ),
        sections=(
            ("Impiego documentato",
             "Azincourt e Crécy per l'arco lungo; falangi e tercios per le picche. "
             "Sono capitoli di storia sociale (addestramento degli arcieri inglesi) "
             "oltre che militare. Niente istruzioni di tiro."),
        ),
        related=("azincourt", "100y", "cavalleria"),
    ),
    card(
        id="radioeq",
        kind="gear",
        world="ferro",
        emoji="📻",
        title="Radio da campo",
        subtitle="filo e etere",
        era="con",
        tags=("moderno", "comunicazioni"),
        aliases=("walkie", "marconi", "telefono da campo"),
        summary=(
            "Dal telefono di trincea alla radio portatile. Cambia la velocità del comando "
            "e la vulnerabilità alle intercettazioni — tema di storia, non di procedura."
        ),
        related=("radio", "comando", "ww2"),
    ),
    card(
        id="razioni",
        kind="gear",
        world="ferro",
        emoji="🥫",
        title="Razioni e zaini",
        subtitle="cosa porta un soldato",
        era="",
        tags=("individuale", "logistica"),
        aliases=("gavetta", "k-ration", "zaino"),
        summary=(
            "Peso sulle spalle: pane, acqua, coperta, attrezzi. Le razioni in scatola del "
            "Novecento sono un capitolo di industria alimentare tanto quanto di guerra."
        ),
        related=("logi", "logistica", "fanteria"),
    ),
    card(
        id="t34",
        kind="vehicle",
        world="ferro",
        emoji="🛡️",
        title="T-34",
        subtitle="carro sovietico · 1940",
        era="con",
        tags=("carro", "urss"),
        aliases=("t34", "t-34", "carro sovietico"),
        summary=(
            "Carro medio sovietico, prodotto in enorme serie. Simbolo della guerra sul "
            "fronte orientale e della fabbrica di massa."
        ),
        fields=(
            ("📅 Anno", "1940 (ingresso in servizio)"),
            ("🌍 Paese", "Unione Sovietica"),
            ("🏭 Produttore", "KhPZ / UZTM e altri stabilimenti evacuati"),
            ("🌎 Utilizzatori storici", "Armata Rossa e, dopo, molti eserciti"),
        ),
        sections=(
            ("Caratteristiche generali",
             "Corazza inclinata, cannone da 76 poi 85 mm, cingoli larghi per la neve. "
             "Cifre di produzione da manuale storico, non schede tecniche d'impiego."),
            ("Storia",
             "Sorpresa nel 1941, poi colonna della controffensiva. Resta nei musei e "
             "nei monumenti di mezza Europa orientale."),
        ),
        related=("stlg", "carristi", "ww2"),
    ),
    card(
        id="spitfire",
        kind="vehicle",
        world="ferro",
        emoji="✈️",
        title="Supermarine Spitfire",
        subtitle="caccia britannico · 1938",
        era="con",
        tags=("aereo", "caccia", "raf"),
        aliases=("spitfire", "mitchell"),
        summary=(
            "Caccia monoposto della RAF. Ali ellittiche riconoscibili, Battaglia d'Inghilterra, "
            "poi decine di varianti fino al 1945. Icona popolare quanto aeronautica."
        ),
        fields=(
            ("📅 Anno", "1938"),
            ("🌍 Paese", "Regno Unito"),
            ("🏭 Produttore", "Supermarine / Vickers-Armstrongs"),
        ),
        sections=(
            ("Storia",
             "Progettato da R.J. Mitchell. Combatte sul Canale, nel Mediterraneo, in Italia. "
             "Nei musei si conserva come oggetto di design e di memoria, non come «ricetta»."),
        ),
        related=("raf", "piloti", "ww2", "uk"),
    ),
    card(
        id="portaerei",
        kind="vehicle",
        world="ferro",
        emoji="🛳️",
        title="Portaerei",
        subtitle="un aeroporto che galleggia",
        era="con",
        tags=("navale", "aviazione"),
        aliases=("carrier", "akagi", "enterprise", "garibaldi"),
        summary=(
            "Nave il cui ponte è una pista. Nasce tra le due guerre, decide il Pacifico "
            "nel 1942, resta il simbolo delle marine d'alto mare."
        ),
        fields=(
            ("Nascita", "conversioni post-1918, poi classi dedicate"),
            ("Esempi storici", "Akagi, Enterprise, Ark Royal, Giuseppe Garibaldi"),
        ),
        sections=(
            ("Storia",
             "Taranto 1940 e Pearl Harbor mostrano cosa può un'aviazione imbarcata. "
             "Midway è la battaglia-tipo. Oggi poche marine ne possiedono: è un fatto politico "
             "e industriale, oltre che navale."),
        ),
        related=("midway", "marinai", "piloti"),
    ),
    card(
        id="u-boot",
        kind="vehicle",
        world="ferro",
        emoji="🌊",
        title="Sottomarini nella storia",
        subtitle="dal XIX secolo all'Atlantico",
        era="con",
        tags=("navale", "sott'acqua"),
        aliases=("u-boot", "sommergibile", "nazionale"),
        summary=(
            "Battelli subacquei usati in due guerre mondiali, soprattutto nell'Atlantico. "
            "Capitolo di blocco navale, convogli e guerra al traffico — raccontato dalle "
            "storie dei convogli, non da manuali di immersione."
        ),
        related=("ww1", "ww2", "navale", "logistica"),
    ),
    card(
        id="satcom",
        kind="vehicle",
        world="ferro",
        emoji="🛰️",
        title="Spazio militare",
        subtitle="satelliti, osservazione, comunicazioni",
        era="con",
        tags=("spazio", "guerra fredda"),
        aliases=("sputnik", "gps", "ricognizione satellitare"),
        summary=(
            "Dal 1957 lo spazio è anche un teatro di prestigio e di osservazione. "
            "Satelliti di comunicazione, meteo e rilevamento: programmi pubblici, trattati "
            "sulla militarizzazione, agenzie civili e militari."
        ),
        fields=(
            ("Programmi noti", "Sputnik, Corona (declassificato), GPS, Galileo"),
            ("Diritto", "Trattato sullo spazio extra-atmosferico, 1967"),
        ),
        sections=(
            ("Storia",
             "Corsa spaziale come capitolo della guerra fredda. Oggi molte funzioni sono "
             "duali (civili e di difesa). WARBOT parla di programmi dichiarati, non di "
             "architetture di targeting."),
        ),
        related=("cold", "sputnik", "usa"),
    ),
    card(
        id="sputnik",
        kind="vehicle",
        world="ferro",
        emoji="🛰️",
        title="Sputnik 1",
        subtitle="4 ottobre 1957",
        era="con",
        tags=("spazio", "urss"),
        aliases=("sputnik", "1957"),
        summary=(
            "Primo satellite artificiale. Non è un'arma: è un fatto tecnico che sposta "
            "la guerra fredda nello spazio e accelera la risposta statunitense (NASA, 1958)."
        ),
        related=("satcom", "cold"),
    ),
    card(
        id="maginot",
        kind="fort",
        world="ferro",
        emoji="🏰",
        title="Linea Maginot",
        subtitle="Francia · anni Trenta",
        era="con",
        tags=("linea", "calcestruzzo"),
        aliases=("maginot",),
        summary=(
            "Sistema fortificato francese sul confine tedesco. Capolavoro di genio e "
            "simbolo, dopo il 1940, dei limiti delle linee fisse."
        ),
        fields=(
            ("📅", "costruzione anni Trenta"),
            ("🌍", "Alsazia, Lorena, prolungamenti parziali"),
        ),
        sections=(
            ("Architettura e funzione",
             "Forti, casematte, gallerie, artiglierie in pozzo. Pensata per incanalare "
             "un attacco e dare tempo alla mobilitazione. Nel 1940 viene aggirata a nord "
             "attraverso le Ardenne: lezione storica, non un progetto da ripetere."),
        ),
        related=("ww2", "francia", "genio"),
    ),
    card(
        id="vallo",
        kind="fort",
        world="ferro",
        emoji="🌊",
        title="Vallo atlantico",
        subtitle="coste occidentali · 1942–44",
        era="con",
        tags=("bunker", "costa"),
        aliases=("atlantikwall", "omaha", "bunker"),
        summary=(
            "Catena di bunker, batterie e ostacoli voluta dalla Germania occupante dalle "
            "coste norvegesi a quelle francesi. Oggi è archeologia del litorale."
        ),
        sections=(
            ("Funzione storica",
             "Rallentare uno sbarco alleato. Overlord dimostra che una costa fortificata "
             "non basta senza riserve mobili e superiorità aerea. I resti si visitano."),
        ),
        related=("normandia", "ww2", "genio"),
    ),
    card(
        id="trincee",
        kind="fort",
        world="ferro",
        emoji="🌫️",
        title="Trincee",
        subtitle="il paesaggio del 1914–18",
        era="con",
        tags=("ww1", "terra"),
        aliases=("trincea", "no man's land"),
        summary=(
            "Rete di fossati, camminamenti, reticolati. Definiscono la Grande Guerra sul "
            "fronte occidentale e, in parte, su quello italiano."
        ),
        sections=(
            ("Architettura",
             "Linee parallele, spalti, posto di medicazione, filo. Il fango e l'acqua sono "
             "parte della storia. I sacrari e i musei di trincea (Dolomiti, Somme) sono "
             "il modo giusto di avvicinarle: memoria, non ricostruzione operativa."),
        ),
        related=("ww1", "somme", "genio", "elmetto"),
    ),
    card(
        id="castello",
        kind="fort",
        world="ferro",
        emoji="🏰",
        title="Castelli e mura",
        subtitle="la città che si chiude",
        era="med",
        tags=("medioevo", "assedio"),
        aliases=("rocca", "cinta", "mastio"),
        summary=(
            "Mastio, cortine, fossati, torri. Il castello è casa, tribunale e macchina "
            "d'assedio al contrario: deve durare più dei viveri di chi sta fuori."
        ),
        sections=(
            ("Funzione",
             "Controllo di un valico, di un fiume, di una città. L'artiglieria da bombarde "
             "in poi cambia i profili (bastioni, trace italienne). Visitare un castello è "
             "leggere secoli di adattamento, non imparare a fortificare."),
        ),
        related=("assedio", "alesia", "croci"),
    ),
)
