"""Mondo CAMPI: battaglie storiche."""

from services.models import card

ITEMS = (
    card(
        id="maratona",
        kind="battle",
        world="campi",
        emoji="🏃",
        title="Battaglia di Maratona",
        subtitle="490 a.C. · Attica",
        era="ant",
        tags=("grecia", "persia"),
        aliases=("marathon", "milziade"),
        summary=(
            "Sbarco persiano in Attica e scontro con l'esercito ateniese. "
            "È una delle battaglie più raccontate dell'antichità classica."
        ),
        fields=(
            ("📅 Data", "490 a.C."),
            ("📍 Luogo", "piana di Maratona, Attica"),
            ("👥 Forze", "opliti ateniesi e plateesi · corpo di sbarco achemenide"),
        ),
        sections=(
            ("Contesto",
             "Seconda spedizione voluta da Dario I dopo la rivolta ionica. L'obiettivo è "
             "punire Atene e Eretria e consolidare il controllo egeo."),
            ("Fasi",
             "1. Sbarco e schieramento sulla piana. 2. Attesa e scelta del momento da parte "
             "greca. 3. Carica oplitica e crollo delle ali persiane, secondo Erodoto. "
             "4. Rientro ateniese verso la città per prevenire un altro sbarco."),
            ("Conseguenze",
             "Atene resta indipendente. Il racconto alimenta l'identità civica. "
             "La corsa del messaggero è tradizione posteriore, non un resoconto militare."),
        ),
        related=("greco", "fanteria"),
    ),
    card(
        id="canne",
        kind="battle",
        world="campi",
        emoji="🛡️",
        title="Battaglia di Canne",
        subtitle="216 a.C. · Puglia",
        era="ant",
        tags=("annibale", "roma"),
        aliases=("cannae", "annibale", "varro"),
        summary=(
            "Sconfitta romana inflitta da Annibale. Resta il caso scolastico dell'accerchiamento "
            "in campo aperto, descritto da Polibio e Livio."
        ),
        fields=(
            ("📅 Data", "2 agosto 216 a.C. (tradizione)"),
            ("📍 Luogo", "Canne, presso l'Ofanto"),
            ("👥 Forze", "esercito consolare romano · armata cartaginese in Italia"),
        ),
        sections=(
            ("Contesto",
             "Seconda guerra punica. Roma cerca una battaglia risolutiva dopo il Ticino, "
             "la Trebbia e il Trasimeno."),
            ("Fasi",
             "1. Schieramento romano in profondità. 2. Centro cartaginese che cede in modo "
             "controllato. 3. Ali di cavalleria e fanteria che chiudono. 4. Accerchiamento "
             "e strage documentata dalle fonti. Non è un «trucco» da replicare: è un racconto "
             "di dispositivo e terreno, in un'epoca specifica."),
            ("Conseguenze",
             "Roma non tratta. Cambia leva e strategia, evita nuove battaglie campali in Italia "
             "e porta la guerra in Spagna e Africa."),
        ),
        related=("punic", "annibale", "cavalleria"),
    ),
    card(
        id="alesia",
        kind="battle",
        world="campi",
        emoji="🏰",
        title="Assedio di Alesia",
        subtitle="52 a.C. · Gallia",
        era="ant",
        tags=("cesare", "assedio"),
        aliases=("vercingetorige", "alesia"),
        summary=(
            "Doppio sistema di opere intorno all'oppidum di Alesia: Cesare tiene Vercingetorige "
            "dentro e respinge l'esercito di soccorso fuori. Fonte principale: i Commentarii."
        ),
        fields=(
            ("📅 Data", "52 a.C."),
            ("📍 Luogo", "Alise-Sainte-Reine, identificazione oggi prevalente"),
            ("👥 Forze", "legioni cesariane · Galli assediati e coalizione di soccorso"),
        ),
        sections=(
            ("Contesto",
             "Rivolta generale della Gallia dopo anni di campagne. Vercingetorige unisce molte genti."),
            ("Fasi",
             "1. Ritirata gallica nell'oppidum. 2. Linea di circonvallazione. 3. Linea di "
             "contrvallazione verso l'esterno. 4. Attacchi coordinati dall'interno e dall'esterno. "
             "5. Resa. Le opere sono archeologia e racconto, non un progetto da copiare."),
            ("Conseguenze",
             "Fine della rivolta su scala gallica. Vercingetorige prigioniero. Cesare rafforza "
             "la propria posizione a Roma."),
        ),
        related=("gall", "cesare", "assedio", "genio"),
    ),
    card(
        id="azincourt",
        kind="battle",
        world="campi",
        emoji="🏹",
        title="Battaglia di Azincourt",
        subtitle="25 ottobre 1415 · Artois",
        era="med",
        tags=("centanni", "arcieri"),
        aliases=("agincourt", "enrico v"),
        summary=(
            "Vittoria inglese di Enrico V su un esercito francese superiore di numero, "
            "in un campo stretto e fangoso. Gli arcieri a lungo raggio pesano nel racconto delle fonti."
        ),
        fields=(
            ("📅 Data", "25 ottobre 1415"),
            ("📍 Luogo", "Azincourt, nord della Francia"),
            ("👥 Forze", "sbarco inglese in ritirata · nobiltà e genti d'arme francesi"),
        ),
        sections=(
            ("Contesto",
             "Ripresa della Guerra dei Cent'anni. Enrico V ha preso Harfleur e tenta di raggiungere Calais."),
            ("Fasi",
             "1. Terreno ristretto tra boschi. 2. Paletti e palude che limitano la cavalleria. "
             "3. Pioggia di frecce e mischia. 4. Cattura di prigionieri nobili, poi uccisioni "
             "ordinate nel timore di un contrattacco — episodio discusso dagli storici."),
            ("Conseguenze",
             "Trattato di Troyes (1420) e pretesa inglese sulla corona francese, poi ribaltata "
             "nelle decadi successive."),
        ),
        related=("100y", "arcieri", "giovanna"),
    ),
    card(
        id="lepanto",
        kind="battle",
        world="campi",
        emoji="⛵",
        title="Battaglia di Lepanto",
        subtitle="7 ottobre 1571 · golfo di Patrasso",
        era="mod",
        tags=("navale", "ottomani", "venezia"),
        aliases=("legato santa", "don giovanni"),
        summary=(
            "Scontro navale tra la Lega Santa (Spagna, Venezia, Stato della Chiesa) e la flotta "
            "ottomana. È una delle battaglie di galee più documentate del Mediterraneo."
        ),
        fields=(
            ("📅 Data", "7 ottobre 1571"),
            ("📍 Luogo", "golfo di Patrasso, presso Lepanto"),
            ("👥 Forze", "Lega Santa · Impero ottomano"),
        ),
        sections=(
            ("Contesto",
             "Espansione ottomana in Mediterraneo e caduta di Cipro. La Lega è un'alleanza fragile, "
             "tenuta insieme da Pio V e da interessi veneziani e spagnoli."),
            ("Fasi",
             "Tre squadre cristiane allineate, scontro di spingarde e arrembaggio. La galeazza "
             "veneziana e il centro di Don Giovanni pesano nel racconto. Molte navi ottomane "
             "vengono catturate o affondate."),
            ("Conseguenze",
             "Non caccia gli Ottomani dal mare, ma ferma una stagione di iniziativa. Cipro resta "
             "ottomana. La memoria cristiana (dipinti, feste) supera l'effetto strategico immediato."),
        ),
        related=("navale", "venezia"),
    ),
    card(
        id="waterloo",
        kind="battle",
        world="campi",
        emoji="⚔️",
        title="Battaglia di Waterloo",
        subtitle="18 giugno 1815 · Belgio",
        era="mod",
        tags=("napoleone", "coalizione"),
        aliases=("waterloo", "wellington", "blucher", "mont saint jean"),
        summary=(
            "Ultima battaglia campale di Napoleone. Anglo-alleati di Wellington sul crinale, "
            "arrivo prussiano di Blücher, ritirata francese. Chiude i Cento giorni."
        ),
        fields=(
            ("📅 Data", "18 giugno 1815"),
            ("📍 Luogo", "Mont-Saint-Jean, a sud di Bruxelles"),
            ("👥 Forze", "Armata del Nord francese · anglo-alleati · prussiani"),
        ),
        sections=(
            ("Contesto",
             "Napoleone tornato dall'Elba. Vuole battere i coalizzati in Belgio prima che si uniscano. "
             "Ligny e Quatre Bras, due giorni prima, preparano il campo."),
            ("Fasi",
             "1. Mattina umida, artiglieria ritardata. 2. Attacchi a Hougoumont e al centro. "
             "3. Cariche di cavalleria. 4. Presa e perdita di La Haye Sainte. 5. Arrivo prussiano "
             "a Plancenoit. 6. Guardia in avanti, poi rotta. È una sequenza storica, non un copione tattico."),
            ("Conseguenze",
             "Seconda abdicazione, esilio a Sant'Elena, Congresso di Vienna confermato. "
             "«Waterloo» entra nel linguaggio comune come capolinea."),
        ),
        related=("napo", "napoleone", "vienna", "artiglieria"),
    ),
    card(
        id="somme",
        kind="battle",
        world="campi",
        emoji="🌫️",
        title="Battaglia della Somme",
        subtitle="1916 · Piccardia",
        era="con",
        tags=("ww1", "trincee"),
        aliases=("somme", "1 luglio 1916"),
        summary=(
            "Offensiva anglo-francese sul fronte occidentale. Il 1° luglio 1916 è tra i giorni "
            "più sanguinosi della storia militare britannica. Simbolo della guerra industriale."
        ),
        fields=(
            ("📅 Date", "1 luglio – 18 novembre 1916"),
            ("📍 Luogo", "fiume Somme, Francia"),
            ("👥 Forze", "British Expeditionary Force, francesi · esercito tedesco"),
        ),
        sections=(
            ("Contesto",
             "Alleggerire Verdun e logorare l'esercito tedesco. Artiglieria di preparazione "
             "per giorni, poi fanteria all'assalto."),
            ("Fasi",
             "Preparazione di fuoco, assalto del 1° luglio con perdite enormi britanniche, "
             "avanzate parziali, fango autunnale, carri in piccolo numero a Flers-Courcelette. "
             "Non descriviamo procedure d'assalto: restiamo al racconto storiografico."),
            ("Conseguenze",
             "Guadagni minimi per chilometri. Traumi demografici. La Somme diventa memoria "
             "nazionale britannica e laboratorio della guerra di materiali."),
        ),
        related=("ww1", "trincee", "carristi", "logistica"),
    ),
    card(
        id="stlg",
        kind="battle",
        world="campi",
        emoji="❄️",
        title="Battaglia di Stalingrado",
        subtitle="1942–1943 · Volga",
        era="con",
        tags=("ww2", "urss"),
        aliases=("stalingrado", "volgograd", "paulus", "zhukov", "ciukov"),
        summary=(
            "Scontro per la città sul Volga. Combattimento urbano, accerchiamento dell'Armata "
            "6ª tedesca, resa nel febbraio 1943. Svolta sul fronte orientale."
        ),
        fields=(
            ("📅 Date", "17 luglio 1942 – 2 febbraio 1943"),
            ("📍 Luogo", "Stalingrado (oggi Volgograd) e steppa del Don"),
            ("👥 Forze", "Wehrmacht e alleati dell'Asse · Armata Rossa"),
        ),
        sections=(
            ("Contesto",
             "Operazione Blu tedesca verso il Caucaso e il Volga. La città è nodo fluviale, "
             "industriale e simbolico."),
            ("Fasi",
             "1. Avvicinamento estivo. 2. Combattimento casa per casa. 3. Controffensiva sovietica "
             "Uranus sui fianchi. 4. Accerchiamento. 5. Fallimento del corridoio aereo e di "
             "Wintergewitter. 6. Resa di Paulus. Le fasi sono storia, non istruzioni urbane."),
            ("Conseguenze",
             "Perdita di un'armata intera. Iniziativa strategica all'Armata Rossa. Memoria "
             "cittadina e sovietica enorme; oggi Volgograd ne è il nome."),
        ),
        related=("ww2", "t34", "zukov", "logistica", "medic"),
    ),
    card(
        id="midway",
        kind="battle",
        world="campi",
        emoji="🛫",
        title="Battaglia delle Midway",
        subtitle="4–7 giugno 1942 · Pacifico",
        era="con",
        tags=("ww2", "portaerei", "usa", "giappone"),
        aliases=("midway", "nimitz", "nagumo"),
        summary=(
            "Scontro di portaerei nel Pacifico centrale. Gli Stati Uniti affondano quattro "
            "portaerei giapponesi. Svolta navale dopo Pearl Harbor."
        ),
        fields=(
            ("📅 Date", "4–7 giugno 1942"),
            ("📍 Luogo", "atollo di Midway"),
            ("👥 Forze", "Pacific Fleet USA · Kidō Butai giapponese"),
        ),
        sections=(
            ("Contesto",
             "Il Giappone vuole attirare le portaerei americane. Gli USA, grazie alla "
             "decrittazione, sanno dell'obiettivo. Non entriamo in dettagli di intelligence operativa."),
            ("Fasi",
             "Ricognizione, ondate aeree, colpi sulle ponti di volo giapponesi, affondamenti "
             "nel corso di ore. È guerra aeronavale di posizione e tempismo, raccontata dalle "
             "fonti postbelliche."),
            ("Conseguenze",
             "Il Giappone perde il nucleo delle portaerei d'attacco. L'iniziativa nel Pacifico "
             "passa gradualmente agli Stati Uniti."),
        ),
        related=("ww2", "portaerei", "piloti", "usa"),
    ),
    card(
        id="normandia",
        kind="battle",
        world="campi",
        emoji="🌊",
        title="Sbarco in Normandia",
        subtitle="6 giugno 1944 · Francia",
        era="con",
        tags=("ww2", "overlord"),
        aliases=("d-day", "overlord", "omaha", "utah", "gold", "juno", "sword"),
        summary=(
            "Apertura del fronte occidentale alleato in Francia. Operazione Overlord: "
            "sbarco anfibio, aviolanci, poi campagna di bocage fino alla liberazione di Parigi."
        ),
        fields=(
            ("📅 Data dello sbarco", "6 giugno 1944"),
            ("📍 Luogo", "coste calvadosine e della Manica"),
            ("👥 Forze", "USA, Regno Unito, Canada e altri alleati · occupazione tedesca"),
        ),
        sections=(
            ("Contesto",
             "Dopo l'Italia, gli Alleati aprono il fronte che Stalin chiede da anni. "
             "Inganno su Pas-de-Calais, accumulo in Gran Bretagna, scelta della luna e della marea."),
            ("Fasi",
             "Aviolanci notturni, bombardamenti, cinque spiagge, testa di ponte, battaglia "
             "di Caen e chiusura della sacca di Falaise. Descriviamo l'ordine degli eventi, "
             "non procedure da sbarco."),
            ("Conseguenze",
             "Liberazione della Francia settentrionale, crollo del fronte ovest tedesco. "
             "Memoria transnazionale del 6 giugno. Il Vallo atlantico resta archeologia militare."),
        ),
        related=("ww2", "parà", "vallo", "usa", "uk"),
    ),
)
