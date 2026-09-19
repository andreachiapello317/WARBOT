"""Mondo BANDIERE: forze armate e paesi."""

from services.models import card

ITEMS = (
    card(
        id="italia",
        kind="army",
        world="bandiere",
        emoji="🇮🇹",
        title="Forze Armate Italiane",
        subtitle="Esercito, Marina, Aeronautica, Carabinieri",
        era="con",
        tags=("italia", "nato"),
        aliases=("esercito italiano", "marina militare", "aeronautica", "farnesina"),
        summary=(
            "Le Forze Armate della Repubblica: Esercito, Marina Militare, Aeronautica Militare "
            "e Arma dei Carabinieri. Discendenza risorgimentale, rifondazione repubblicana, "
            "appartenenza alla NATO e all'ONU."
        ),
        fields=(
            ("📜 Storia", "Regio Esercito 1861 · Repubblica 1946 · NATO 1949"),
            ("🎖️ Organizzazione", "Stato Maggiore della Difesa · quattro forze"),
            ("🌍 Missioni pubbliche", "ONU, NATO, UE: elenchi pubblici del Ministero della Difesa"),
        ),
        sections=(
            ("Esercito",
             "Arma di fanteria, cavalleria, artiglieria, genio, trasmissioni. Tradizioni di "
             "reggimento (Folgore, Taurinense, Sassari, Bersaglieri) con musei e feste."),
            ("Marina",
             "Flotta, fucilieri di marina (San Marco), sottomarini, pattugliatori. "
             "Arsenali di La Spezia, Taranto, Augusta."),
            ("Aeronautica",
             "Nata nel 1923 come Regia Aeronautica, rifondata in Repubblica. Frecce Tricolori "
             "come volto pubblico."),
            ("Tradizioni",
             "Giuramento, bandiera di guerra, Cappella dell'Esercito, sacrari. "
             "Il 4 novembre è Giorno dell'Unità Nazionale e delle Forze Armate."),
        ),
        related=("fanteria", "parà", "itmarina", "nato"),
    ),
    card(
        id="itmarina",
        kind="army",
        world="bandiere",
        emoji="⚓",
        title="Marina Militare",
        subtitle="Italia · forza navale",
        era="con",
        tags=("italia", "mare"),
        aliases=("regia marina", "marina italiana"),
        summary=(
            "Forza armata marittima italiana. Eredita la Regia Marina, le tradizioni "
            "sabaudo-borboniche e una geografia di penisola e isole."
        ),
        fields=(
            ("Periodo", "1861 – oggi"),
            ("Basi note", "La Spezia, Taranto, Ancona, Augusta"),
        ),
        sections=(
            ("Storia",
             "Lissa 1866, guerra italo-turca, due guerre mondiali, ricostruzione del secondo "
             "dopoguerra, missioni nel Mediterraneo. La storia è anche di navi-museo e di "
             "nomi (Dandolo, Cavour, Garibaldi)."),
        ),
        related=("italia", "marinai", "portaerei"),
    ),
    card(
        id="francia",
        kind="army",
        world="bandiere",
        emoji="🇫🇷",
        title="Forces armées françaises",
        subtitle="Terre, Marine, Air et Espace",
        era="con",
        tags=("francia", "nato"),
        aliases=("grande armée", "légion", "armée de terre"),
        summary=(
            "Forze armate della Repubblica francese. Eredità della levée en masse, della "
            "Grande Armée e dell'impero coloniale, oggi quadro NATO e UE, con deterrenza nucleare pubblica."
        ),
        fields=(
            ("Componenti", "Armée de Terre · Marine nationale · Armée de l'Air et de l'Espace · Gendarmerie"),
            ("Tradizioni", "Legione straniera, Saint-Cyr, École navale"),
        ),
        sections=(
            ("Storia",
             "Rivolta e rivoluzione, Napoleone, 1870, 1914–18, 1940 e Francia Libera, "
             "guerre di decolonizzazione, professionalizzazione contemporanea."),
        ),
        related=("napo", "100y", "nato"),
    ),
    card(
        id="uk",
        kind="army",
        world="bandiere",
        emoji="🇬🇧",
        title="British Armed Forces",
        subtitle="Royal Navy, British Army, RAF",
        era="con",
        tags=("regno unito", "nato"),
        aliases=("royal navy", "british army", "raf"),
        summary=(
            "Forze armate del Regno Unito. La Royal Navy è stata per secoli lo strumento "
            "di un impero marittimo; la RAF nasce nel 1918 come prima aeronautica indipendente."
        ),
        fields=(
            ("Componenti", "Royal Navy · British Army · Royal Air Force"),
            ("Alleanze", "NATO · Five Eyes · Commonwealth"),
        ),
        sections=(
            ("Storia",
             "Guerra dei Cent'anni, epoca velica, Waterloo, due guerre mondiali, ritiro "
             "da est di Suez. Tradizioni di reggimento molto visibili (Guardie, Royal Marines)."),
        ),
        related=("azincourt", "waterloo", "spitfire", "raf", "nato"),
    ),
    card(
        id="raf",
        kind="army",
        world="bandiere",
        emoji="✈️",
        title="Royal Air Force",
        subtitle="Regno Unito · 1918",
        era="con",
        tags=("aviazione", "uk"),
        aliases=("raf", "battle of britain"),
        summary=(
            "Aeronautica indipendente britannica, creata il 1º aprile 1918. La Battaglia "
            "d'Inghilterra (1940) è il capitolo più noto della sua memoria pubblica."
        ),
        related=("uk", "spitfire", "piloti", "ww2"),
    ),
    card(
        id="usa",
        kind="army",
        world="bandiere",
        emoji="🇺🇸",
        title="United States Armed Forces",
        subtitle="Army, Navy, Air Force, Marines, Space Force, Guardia Costiera",
        era="con",
        tags=("stati uniti", "nato"),
        aliases=("us army", "us navy", "marines", "pentagono"),
        summary=(
            "Forze armate degli Stati Uniti. Da esercito ottocentesco a dispositivo globale "
            "del Novecento, con una branca spaziale pubblica (U.S. Space Force, 2019)."
        ),
        fields=(
            ("Storia pubblica", "Indipendenza, guerra civile, 1917, 1941–45, guerra fredda"),
            ("Alleanze", "NATO e accordi bilaterali dichiarati"),
        ),
        sections=(
            ("Componenti",
             "Esercito, Marina, Aeronautica, Marine Corps, Space Force, Coast Guard. "
             "Ogni servizio ha accademie (West Point, Annapolis, Colorado Springs) e musei."),
            ("Nota",
             "WARBOT descrive strutture e storia pubblica, non dispiegamenti operativi correnti."),
        ),
        related=("midway", "normandia", "nato", "satcom"),
    ),
    card(
        id="nato",
        kind="army",
        world="bandiere",
        emoji="🟦",
        title="NATO",
        subtitle="Alleanza Atlantica · 1949",
        era="con",
        tags=("alleanza", "guerra fredda"),
        aliases=("atlantico", "articolo 5"),
        summary=(
            "Organizzazione del Trattato dell'Atlantico del Nord. Patto di difesa collettiva "
            "nato a Washington nel 1949. L'articolo 5 è la clausola più citata."
        ),
        fields=(
            ("Sede", "Bruxelles"),
            ("Nascita", "4 aprile 1949"),
        ),
        sections=(
            ("Storia",
             "Risposta al bipolarismo europeo. Allargamenti successivi sono fatti politici "
             "documentati. Non è un esercito unico: è un'alleanza di forze nazionali."),
        ),
        related=("cold", "usa", "italia", "onu"),
    ),
    card(
        id="roma",
        kind="army",
        world="bandiere",
        emoji="🐺",
        title="Esercito romano",
        subtitle="legioni, socii, flotta",
        era="ant",
        tags=("roma", "antichità"),
        aliases=("legione", "centuria", "coorte"),
        summary=(
            "Dispositivo militare di Roma monarchica, repubblicana e imperiale. La legione "
            "è l'unità celebre; accanto ci sono socii, ausiliari e flotta."
        ),
        fields=(
            ("Unità", "centuria · manipolo · coorte · legione"),
            ("Fonti", "Polibio, Livio, Vegezio — da leggere come testi d'epoca"),
        ),
        sections=(
            ("Organizzazione generale",
             "Cittadini-soldati in Repubblica, poi professionalizzazione augustea. "
             "Accampamento, marcia, assedio sono capitoli di storia, non un manuale da campo."),
        ),
        related=("punic", "gall", "canne", "cesare"),
    ),
)
