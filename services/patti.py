"""Mondo PATTI: pace, documenti, personaggi, strategia storica."""

from services.models import card

ITEMS = (
    card(
        id="westfalia",
        kind="doc",
        world="patti",
        emoji="📜",
        title="Pace di Westfalia",
        subtitle="1648 · Münster e Osnabrück",
        era="mod",
        tags=("trattato", "europa"),
        aliases=("westfalia", "1648", "münster"),
        summary=(
            "Coppie di trattati che chiudono la Guerra dei Trent'anni. Punto di svolta "
            "della diplomazia europea: principi, confessioni, ambasciate."
        ),
        fields=(
            ("📅", "1648"),
            ("📍", "Münster e Osnabrück"),
            ("👥", "Impero, Francia, Svezia, Spagna, Province Unite, principi tedeschi"),
        ),
        sections=(
            ("Contenuto storico",
             "Riconoscimenti territoriali, diritti dei principi, chiusura — almeno formale — "
             "della stagione delle guerre di religione nell'Impero. Gli storici discutono "
             "quanto nasca davvero qui la «sovranità» moderna: il testo resta, il mito cresce."),
        ),
        related=("30y", "vienna"),
    ),
    card(
        id="vienna",
        kind="doc",
        world="patti",
        emoji="🏛️",
        title="Congresso di Vienna",
        subtitle="1814–1815",
        era="mod",
        tags=("diplomazia", "restaurazione"),
        aliases=("vienna", "metternich", "talleyrand"),
        summary=(
            "Conferenza che ridisegna l'Europa dopo Napoleone. Equilibrio delle potenze, "
            "restauri dinastici, nuove mappe italiane e tedesche."
        ),
        fields=(
            ("📅", "settembre 1814 – giugno 1815"),
            ("📍", "Vienna"),
            ("👥", "Austria, Russia, Prussia, Gran Bretagna, Francia"),
        ),
        sections=(
            ("Esito",
             "Santa Alleanza, confini, legittimità monarchica. In Italia: Lombardo-Veneto "
             "asburgico, Regno di Sardegna ingrandito. Il congresso coincide con i Cento giorni "
             "e con Waterloo."),
        ),
        related=("napo", "waterloo", "napoleone"),
    ),
    card(
        id="versailles",
        kind="doc",
        world="patti",
        emoji="🖋️",
        title="Trattato di Versailles",
        subtitle="28 giugno 1919",
        era="con",
        tags=("pace", "ww1"),
        aliases=("versailles", "1919", "wilson"),
        summary=(
            "Trattato di pace con la Germania dopo la Grande Guerra. Riparazioni, perdite "
            "coloniali, Società delle Nazioni. Conteso già dai contemporanei."
        ),
        fields=(
            ("📅", "28 giugno 1919"),
            ("📍", "Galleria degli Specchi, Versailles"),
            ("👥", "Germania · Francia, Regno Unito, Italia, USA e alleati"),
        ),
        sections=(
            ("Conseguenze",
             "Nuova mappa dell'Europa orientale, clausola di colpa, occupazione della "
             "Renania. In Italia il dibattito sulla «vittoria mutilata». Gli storici non "
             "attribuiscono il 1939 a un solo articolo: il trattato è un pezzo, non il destino."),
        ),
        related=("ww1", "onu", "ww2"),
    ),
    card(
        id="ginevra",
        kind="doc",
        world="patti",
        emoji="🔴",
        title="Convenzioni di Ginevra",
        subtitle="diritto internazionale umanitario",
        era="con",
        tags=("diritto", "croce rossa"),
        aliases=("ginevra", "croce rossa", "prigionieri"),
        summary=(
            "Trattati che proteggono feriti, prigionieri, civili, personale sanitario. "
            "La prima convenzione è del 1864; il corpus attuale è del 1949, con protocolli successivi."
        ),
        fields=(
            ("📅", "1864 · 1949 · protocolli 1977"),
            ("Sede simbolica", "Ginevra"),
        ),
        sections=(
            ("Perché sta in un museo di guerra",
             "Perché la guerra ha prodotto regole su cosa non si può fare ai non combattenti. "
             "Non è ingenuità: è diritto, violato e invocato. WARBOT lo mostra accanto alle battaglie."),
        ),
        related=("medic", "nightingale", "onu", "ww2"),
    ),
    card(
        id="onu",
        kind="peace",
        world="patti",
        emoji="🌐",
        title="Nazioni Unite",
        subtitle="1945 · San Francisco",
        era="con",
        tags=("pace", "internazionale"),
        aliases=("onu", "un", "caschi blu"),
        summary=(
            "Organizzazione nata per «salvare le future generazioni dal flagello della guerra». "
            "Consiglio di Sicurezza, Assemblea, caschi blu: strumenti politici, non magici."
        ),
        fields=(
            ("📅", "Carta firmata il 26 giugno 1945"),
            ("Sede", "New York"),
        ),
        sections=(
            ("Peacekeeping",
             "Missioni di mantenimento della pace con mandato, elmetto azzurro, regole "
             "d'ingaggio pubbliche. Storia di successi parziali e fallimenti noti (Ruanda, Srebrenica). "
             "È diplomazia armata di presenza, non un manuale di intervento."),
        ),
        related=("ww2", "ginevra", "nato", "versailles"),
    ),
    card(
        id="marshall",
        kind="peace",
        world="patti",
        emoji="🧱",
        title="Piano Marshall e ricostruzione",
        subtitle="dopoguerra europeo",
        era="con",
        tags=("ricostruzione", "economia"),
        aliases=("erp", "marshall", "ricostruzione"),
        summary=(
            "European Recovery Program (1948–52): aiuti statunitensi all'Europa occidentale. "
            "Capitolo di dopoguerra: macerie, sfollati, ponti ricostruiti, scelta di campo."
        ),
        related=("ww2", "cold", "usa", "italia"),
    ),
    card(
        id="pow",
        kind="peace",
        world="patti",
        emoji="🏕️",
        title="Prigionieri e sfollati",
        subtitle="la guerra dopo il fuoco",
        era="",
        tags=("civili", "diritto"),
        aliases=("prigionieri", "profughi", "dp", "lager"),
        summary=(
            "Campi di prigionia, rimpatri, displaced persons, deportazioni. Una parte enorme "
            "della storia militare non sta sul campo: sta nei treni, nei campi, nelle code del pane."
        ),
        sections=(
            ("Fonti",
             "Diari, Croce Rossa, commissioni d'inchiesta, memoriali. Ginevra parla dei "
             "prigionieri; i civili hanno una tutela più tarda e più fragile."),
        ),
        related=("ginevra", "ww2", "ww1"),
    ),
    card(
        id="napoleone",
        kind="person",
        world="patti",
        emoji="🦅",
        title="Napoleone Bonaparte",
        subtitle="1769–1821",
        era="mod",
        tags=("francia", "imperatore"),
        aliases=("napoleone", "bonaparte", "ajaccio"),
        summary=(
            "Ufficiale di artiglieria corso, generale della Rivoluzione, primo console, "
            "imperatore. Ridefinisce la guerra europea e il diritto civile. Muore a Sant'Elena."
        ),
        fields=(
            ("📅", "1769–1821"),
            ("🏛️ Ruolo", "generale, capo di Stato, legislatore"),
            ("⚔️ Conflitti", "guerre rivoluzionarie e napoleoniche"),
        ),
        sections=(
            ("Decisioni documentate",
             "Colpo di Stato del 18 brumaio, Code civil, blocchi continentali, divorzi "
             "politici, campagna di Russia, rientro dell'Elba. Ogni scelta ha un archivio."),
            ("Fonti",
             "Corrispondenza, bollettini, memoriali di Sant'Elena, storiografia immensa. "
             "Non è un eroe unico: è un nodo della storia europea."),
        ),
        related=("napo", "waterloo", "vienna", "artiglieria"),
    ),
    card(
        id="cesare",
        kind="person",
        world="patti",
        emoji="🐺",
        title="Gaio Giulio Cesare",
        subtitle="100–44 a.C.",
        era="ant",
        tags=("roma", "dittatore"),
        aliases=("cesare", "caesar", "giulio"),
        summary=(
            "Generale e scrittore. Conquista la Gallia, passa il Rubicone, vince la guerra "
            "civile, muore alle Idi di marzo. I Commentarii sono fonte e propaganda."
        ),
        fields=(
            ("📅", "100–44 a.C."),
            ("🏛️ Ruolo", "proconsole, dittatore, autore"),
        ),
        sections=(
            ("Conflitti", "Guerre galliche, guerra civile contro Pompeo."),
            ("Fonti", "Commentarii, Cicerone, Svetonio, Plutarco."),
        ),
        related=("gall", "alesia", "roma"),
    ),
    card(
        id="annibale",
        kind="person",
        world="patti",
        emoji="🐘",
        title="Annibale Barca",
        subtitle="247–183 a.C. circa",
        era="ant",
        tags=("cartagine",),
        aliases=("annibale", "hannibal"),
        summary=(
            "Generale cartaginese. Attraversa le Alpi, vince al Trasimeno e a Canne, "
            "non chiude Roma. Scipione lo batte a Zama. Figura di strategia e di memoria."
        ),
        related=("punic", "canne", "roma"),
    ),
    card(
        id="zukov",
        kind="person",
        world="patti",
        emoji="⭐",
        title="Georgij Žukov",
        subtitle="1896–1974",
        era="con",
        tags=("urss", "ww2"),
        aliases=("zhukov", "žukov", "giukov"),
        summary=(
            "Maresciallo dell'Unione Sovietica. Mosca, Stalingrado (come coordinatore dello "
            "Stavka), Kursk, Berlino. Biografia intrecciata al potere staliniano."
        ),
        fields=(
            ("📅", "1896–1974"),
            ("🏛️ Ruolo", "comandante di fronte, vicecomandante supremo"),
        ),
        related=("stlg", "ww2"),
    ),
    card(
        id="giovanna",
        kind="person",
        world="patti",
        emoji="⚜️",
        title="Giovanna d'Arco",
        subtitle="1412 circa – 1431",
        era="med",
        tags=("francia", "centanni"),
        aliases=("jeanne", "arc", "pulzella"),
        summary=(
            "Giovane lorenese che convince Carlo VII e partecipa alla ripresa di Orléans. "
            "Processata e arsa a Rouen. Santa e figura nazionale francese. Fonte: processi."
        ),
        related=("100y", "azincourt", "francia"),
    ),
    card(
        id="nightingale",
        kind="person",
        world="patti",
        emoji="🕯️",
        title="Florence Nightingale",
        subtitle="1820–1910",
        era="con",
        tags=("sanità", "crimea"),
        aliases=("nightingale", "lampada"),
        summary=(
            "Infermiera e riformatrice. Guerra di Crimea, statistiche sulla mortalità "
            "ospedaliera, nascita di una professione. Sta in un museo di guerra perché "
            "ha cambiato cosa significa «ferito»."
        ),
        related=("medic", "ginevra"),
    ),
    card(
        id="erodoto",
        kind="person",
        world="patti",
        emoji="📜",
        title="Erodoto",
        subtitle="V secolo a.C.",
        era="ant",
        tags=("fonte", "grecia"),
        aliases=("erodoto", "storie"),
        summary=(
            "Autore delle Storie. Senza di lui le guerre greco-persiane sarebbero un'altra "
            "ombra. Va letto come inchiesta, non come bollettino."
        ),
        related=("greco", "maratona"),
    ),
    card(
        id="logistica",
        kind="idea",
        world="patti",
        emoji="🧠",
        title="Logistica",
        subtitle="perché i rifornimenti decidono le campagne",
        era="",
        tags=("strategia", "storia"),
        aliases=("rifornimenti", "traino", "depots"),
        summary=(
            "Pane, foraggio, munizioni, pezzi, carburante. Le campagne falliscono più spesso "
            "per strade e magazzini che per «genio» da manifesto."
        ),
        sections=(
            ("Nella storia",
             "Annibale in Italia vive di quanto trova. Napoleone in Russia perde l'esercito "
             "anche per distanze e inverno. Stalingrado è, tra l'altro, un ponte aereo che "
             "non basta. La ferrovia del 1914 è un'arma tanto quanto il fucile."),
            ("Cosa non è",
             "Non è un corso di approvvigionamento contemporaneo. È la domanda: chi mangia, "
             "chi ripara, chi arriva in ritardo."),
        ),
        related=("logi", "stlg", "napo", "ww1"),
    ),
    card(
        id="assedio",
        kind="idea",
        world="patti",
        emoji="🧠",
        title="Assedio",
        subtitle="il tempo come arma",
        era="",
        tags=("strategia", "città"),
        aliases=("assedio", "cerchio", "blocco"),
        summary=(
            "Chiudere una piazza e aspettare. Funziona se i viveri finiscono prima del "
            "soccorso. Alesia, trecento assedi medievali, Leningrado: stessa domanda, epoche diverse."
        ),
        sections=(
            ("Architettura storica",
             "Circonvallazione, mine, artiglieria da breccia, negoziato. I trattati d'assedio "
             "d'ancien régime regolano rese «onorevoli». Non è un kit per chiudere una città."),
        ),
        related=("alesia", "castello", "genio"),
    ),
    card(
        id="comando",
        kind="idea",
        world="patti",
        emoji="🧠",
        title="Comando e morale",
        subtitle="chi decide, chi resiste",
        era="",
        tags=("strategia",),
        aliases=("stato maggiore", "morale", "disciplina"),
        summary=(
            "Il comando è carte, orari, personalità e paura. Il morale è fame, posta, "
            "voci, giustizia percepita. Le fonti (diari, fucilazioni, canti) lo mostrano meglio "
            "dei ritratti ufficiali."
        ),
        related=("ufficiali", "radio", "ww1"),
    ),
    card(
        id="ricognizione",
        kind="idea",
        world="patti",
        emoji="🧠",
        title="Ricognizione",
        subtitle="vedere prima",
        era="",
        tags=("strategia",),
        aliases=("esplorazione", "osservazione", "intelligence storica"),
        summary=(
            "Cavalieri, palloni, aerei da osservazione, satelliti. La storia della guerra "
            "è anche storia di chi arriva a sapere. Restiamo alle fonti pubbliche."
        ),
        related=("cavalleria", "piloti", "satcom"),
    ),
    card(
        id="navale",
        kind="idea",
        world="patti",
        emoji="🧠",
        title="Guerra navale nella storia",
        subtitle="rotte, blocchi, flotte",
        era="",
        tags=("strategia", "mare"),
        aliases=("blocco navale", "mare nostrum"),
        summary=(
            "Chi tiene le rotte tiene il grano e il carbone. Lepanto, Trafalgar, l'Atlantico "
            "del 1917 e del 1943: capitoli di geografia tanto quanto di navi."
        ),
        related=("lepanto", "portaerei", "u-boot", "marinai"),
    ),
)
