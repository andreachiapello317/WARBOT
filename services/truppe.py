"""Mondo TRUPPE: ruoli e gradi."""

from services.models import card

ITEMS = (
    card(
        id="fanteria",
        kind="role",
        world="truppe",
        emoji="🪖",
        title="Fanteria",
        subtitle="il grosso degli eserciti di terra",
        era="",
        tags=("ruolo", "terra"),
        aliases=("fante", "opliti", "legionario"),
        summary=(
            "Chi combatte e si muove a piedi. Dall'oplita al fante di linea, fino alle "
            "unità motorizzate contemporanee: è il ruolo più numeroso e il più raccontato."
        ),
        fields=(
            ("Ruolo", "presenza sul terreno, presidio, avanzata a contatto"),
            ("Periodo", "dall'antichità a oggi"),
            ("Formazione", "addestramento di corpo, disciplina di reparto, mestiere di squadra"),
        ),
        sections=(
            ("Organizzazione",
             "Si raggruppa in plotoni, compagnie, battaglioni. I nomi cambiano (centuria, "
             "coorte, regiment), l'idea resta: un'unità che tiene un tratto di terreno."),
            ("Uniforme ed equipaggiamento storico",
             "Scudo e lancia, poi moschetto e giubba, poi elmetto d'acciaio e combats. "
             "L'uniforme serve a riconoscersi e a nascondersi, a seconda dell'epoca."),
            ("Evoluzione",
             "Dalla falange al tiro a ripetizione, dalle trincee ai veicoli protetti. "
             "Il mestiere resta collettivo: pochi ruoli dipendono così tanto dal vicino."),
        ),
        related=("elmetto", "trincee", "ww1"),
    ),
    card(
        id="cavalleria",
        kind="role",
        world="truppe",
        emoji="🐎",
        title="Cavalleria",
        subtitle="dal cavallo al mezzo veloce",
        era="",
        tags=("ruolo", "mobilità"),
        aliases=("cavaliere", "ussaro", "dragoni"),
        summary=(
            "Truppe montate: ricognizione, urto, messaggi, inseguimento. Nel Novecento "
            "molte cavallerie diventano unità corazzate o aeree, tenendo nomi e tradizioni."
        ),
        fields=(
            ("Ruolo", "mobilità, contatto rapido, esplorazione"),
            ("Periodo", "antichità – XX secolo (poi eredità nei corazzati)"),
        ),
        sections=(
            ("Organizzazione",
             "Squadroni e reggimenti, spesso con forte identità di corpo. In molti eserciti "
             "resta un'arma con musei, bande e feste proprie."),
            ("Evoluzione",
             "Cavalleria pesante e leggera, dragoni a piedi, poi autoblindo e carristi. "
             "La transizione è culturale tanto quanto tecnica."),
        ),
        related=("carristi", "canne", "azincourt"),
    ),
    card(
        id="artiglieria",
        kind="role",
        world="truppe",
        emoji="💥",
        title="Artiglieria",
        subtitle="il fuoco da lontano, nella storia",
        era="",
        tags=("ruolo", "fuoco"),
        aliases=("cannone", "bombarde", "obice"),
        summary=(
            "Specialisti dei pezzi: bombarde, cannoni da campagna, batterie costiere, "
            "artiglieria contraerea. Nella Grande Guerra diventa l'arma che definisce il paesaggio."
        ),
        fields=(
            ("Ruolo", "fuoco di preparazione, interdizione, appoggio — in senso storico"),
            ("Periodo", "tardo medioevo – contemporaneità"),
        ),
        sections=(
            ("Organizzazione",
             "Batterie e gruppi, osservatori, traino animale poi motorizzato. Richiede "
             "calcolo, mappe e logistica delle munizioni più di molte altre armi."),
            ("Evoluzione",
             "Dalle mura abbattute dalle bombarde alle artiglierie industriali del 1914–18. "
             "Non pubblichiamo tavole di tiro né istruzioni d'impiego."),
        ),
        related=("ww1", "somme", "waterloo", "logistica"),
    ),
    card(
        id="genio",
        kind="role",
        world="truppe",
        emoji="🛠️",
        title="Genio",
        subtitle="ponti, trincee, mine, campi",
        era="",
        tags=("ruolo", "opere"),
        aliases=("guastatori", "zappatori", "ingegneri militari"),
        summary=(
            "Chi costruisce e disfa il terreno: strade, ponti, accampamenti, ostacoli, "
            "bonifiche. Il nome «genio» è napoleonico e italiano; altrove si dice engineers."
        ),
        fields=(
            ("Ruolo", "mobiliità dell'esercito e sopravvivenza delle opere"),
            ("Periodo", "sempre presente, istituzionalizzato in età moderna"),
        ),
        sections=(
            ("Ambiente",
             "Fiumi, montagne, città distrutte, campi minati storici. Il lavoro è spesso "
             "invisibile nelle pitture di battaglia, decisivo nei diari di campagna."),
            ("Evoluzione",
             "Zappatori d'assedio, ferrovieri militari, pontieri, EOD. Resta un mestiere "
             "tecnico: qui ne raccontiamo la storia, non i procedimenti."),
        ),
        related=("alesia", "trincee", "maginot", "assedio"),
    ),
    card(
        id="medic",
        kind="role",
        world="truppe",
        emoji="⚕️",
        title="Medici militari",
        subtitle="feriti, epidemie, Croce Rossa",
        era="",
        tags=("ruolo", "sanità"),
        aliases=("barelliere", "croce rossa", "sanità militare"),
        summary=(
            "Chirurghi da campo, infermieri, barellieri, servizi di evacuazione. "
            "La guerra moderna ha inventato catene di soccorso tanto quanto nuove armi."
        ),
        fields=(
            ("Ruolo", "cura, evacuazione, prevenzione epidemica"),
            ("Periodo", "antico (valetudinaria) – servizi sanitari contemporanei"),
        ),
        sections=(
            ("Organizzazione",
             "Poste di medicazione, ospedali da campo, treni sanitari, navi ospedale. "
             "La Convenzione di Ginevra protegge il personale sanitario come non combattente."),
            ("Evoluzione",
             "Dall'amputazione lampo napoleonica alla chirurgia di guerra del Novecento, "
             "fino alla medicina di evacuazione aerea. Florence Nightingale e la Croce Rossa "
             "segnano la svolta pubblica dell'Ottocento."),
        ),
        related=("ginevra", "nightingale", "ww1"),
    ),
    card(
        id="radio",
        kind="role",
        world="truppe",
        emoji="📡",
        title="Trasmettitori",
        subtitle="segnali, fili, radio",
        era="",
        tags=("ruolo", "comunicazioni"),
        aliases=("marconista", "trasmissioni", "signal"),
        summary=(
            "Chi fa arrivare gli ordini e i rapporti: staffette, telegrafo, telefono da "
            "campo, radio. Senza comunicazioni l'esercito è un insieme di isole."
        ),
        fields=(
            ("Ruolo", "collegamento tra comando e reparti"),
            ("Periodo", "sempre; professionale dalla telegrafia in poi"),
        ),
        sections=(
            ("Evoluzione",
             "Corrieri e trombe, telegrafo ottico, filo, radio, reti digitali. Ogni salto "
             "cambia la velocità del comando — tema storico, non un manuale di segnali."),
        ),
        related=("comando", "ricognizione", "satcom"),
    ),
    card(
        id="logi",
        kind="role",
        world="truppe",
        emoji="📦",
        title="Logistici",
        subtitle="pane, munizioni, pezzi di ricambio",
        era="",
        tags=("ruolo", "rifornimenti"),
        aliases=("sussistenza", "traino", "commissariato"),
        summary=(
            "Magazzinieri, autieri, trenieri, addetti ai carburanti e alle cucine. "
            "Napoleone e i generali del Novecento ripetono la stessa lezione: si marcia sul ventre."
        ),
        fields=(
            ("Ruolo", "far arrivare ciò che tiene in vita l'esercito"),
            ("Ambiente", "retrovie, stazioni, porti, depositi"),
        ),
        sections=(
            ("Evoluzione",
             "Carri a buoi, ferrovie militari, camion, ponti aerei. La campagna di Russia "
             "del 1812 e Stalingrado sono anche crisi di rifornimento, non solo di «genio tattica»."),
        ),
        related=("logistica", "stlg", "napo"),
    ),
    card(
        id="piloti",
        kind="role",
        world="truppe",
        emoji="✈️",
        title="Piloti",
        subtitle="un mestiere del Novecento",
        era="con",
        tags=("ruolo", "aria"),
        aliases=("aviatore", "caccia", "bomber"),
        summary=(
            "Dagli osservatori su biplano della Grande Guerra ai reparti da trasporto e "
            "caccia. Il pilota militare è figura pubblica, cinematografica e museale."
        ),
        fields=(
            ("Ruolo", "osservazione, caccia, bombardamento, trasporto — in senso storico"),
            ("Formazione", "scuole di volo, ore macchina, cultura di squadriglia"),
        ),
        sections=(
            ("Evoluzione",
             "1914: occhi dell'artiglieria. 1940: battaglia d'Inghilterra. Poi jet, elicotteri, "
             "droni da ricognizione. Raccontiamo tipi e storie, non manovre."),
        ),
        related=("spitfire", "midway", "raf"),
    ),
    card(
        id="marinai",
        kind="role",
        world="truppe",
        emoji="⚓",
        title="Marinai",
        subtitle="equipaggi di guerra e di sostegno",
        era="",
        tags=("ruolo", "mare"),
        aliases=("nostromo", "fuochista", "marina"),
        summary=(
            "Chi vive a bordo: coperta, macchina, artiglieria navale, cucina, sanità. "
            "La nave è una città verticale; il marinaio è mestiere collettivo."
        ),
        fields=(
            ("Ruolo", "condurre, rifornire, combattere e sopravvivere in mare"),
            ("Ambiente", "ponte, sottocoperta, arsenali, basi"),
        ),
        sections=(
            ("Evoluzione",
             "Galee, vascelli, corazzate, sottomarini, portaerei. Ogni scafo chiede saperi "
             "diversi. Le marine hanno lingue, gradi e santi patroni propri."),
        ),
        related=("lepanto", "portaerei", "itmarina"),
    ),
    card(
        id="carristi",
        kind="role",
        world="truppe",
        emoji="🛡️",
        title="Carristi",
        subtitle="equipaggi dei mezzi corazzati",
        era="con",
        tags=("ruolo", "corazzati"),
        aliases=("tankista", "carro", "blindati"),
        summary=(
            "Pilota, cannoniere, capocarro, marconista: un equipaggio chiuso in una scatola "
            "d'acciaio. Nascono nella Somme, si affermano nel secondo conflitto mondiale."
        ),
        fields=(
            ("Ruolo", "svolta della mobilità corazzata nel XX secolo"),
            ("Formazione", "scuole carristi, mestiere di equipaggio"),
        ),
        sections=(
            ("Evoluzione",
             "Dal Mark I britannico ai carri della seconda guerra e oltre. Tradizioni di "
             "reggimento molto forti (es. Ariete in Italia). Niente schede di impiego."),
        ),
        related=("t34", "somme", "cavalleria"),
    ),
    card(
        id="parà",
        kind="role",
        world="truppe",
        emoji="🪂",
        title="Paracadutisti",
        subtitle="entrare dal cielo",
        era="con",
        tags=("ruolo", "aviolancio"),
        aliases=("paracadutisti", "folgore", "airborne"),
        summary=(
            "Truppe aviotrasportate, nate tra le due guerre. Normandia, Creta, Arnhem "
            "sono i capitoli più noti. In Italia la Folgore è memoria di El Alamein."
        ),
        fields=(
            ("Ruolo", "arrivo rapido, presidio di nodi, operazioni aviotrasportate storiche"),
            ("Periodo", "anni Trenta – contemporaneità"),
        ),
        sections=(
            ("Evoluzione",
             "Da esperimento a specialità con berretto, brevetto e musei. Il racconto pubblico "
             "insiste su addestramento e spirito di corpo, non su tattiche d'assalto."),
        ),
        related=("normandia", "italia"),
    ),
    card(
        id="speciali",
        kind="role",
        world="truppe",
        emoji="🌑",
        title="Forze speciali",
        subtitle="unità piccole, storia recente",
        era="con",
        tags=("ruolo", "selezionate"),
        aliases=("raiders", "commando", "ranger"),
        summary=(
            "Unità selezionate nate soprattutto nel secondo conflitto e nella guerra fredda. "
            "Di loro si può raccontare l'origine, i nomi pubblici e il mito: non i procedimenti."
        ),
        fields=(
            ("Ruolo", "compiti particolari, fuori dal dispositivo di massa"),
            ("Periodo", "XX–XXI secolo"),
        ),
        sections=(
            ("Nota del museo",
             "WARBOT elenca l'esistenza storica di questi corpi e le missioni già di dominio "
             "pubblico. Non descrive addestramento, tecniche o obiettivi."),
        ),
        related=("ww2", "uk"),
    ),
    card(
        id="ufficiali",
        kind="role",
        world="truppe",
        emoji="⭐",
        title="Ufficiali",
        subtitle="comando, stato maggiore, responsabilità",
        era="",
        tags=("ruolo", "comando"),
        aliases=("tenente", "capitano", "generale", "stato maggiore"),
        summary=(
            "Chi detiene il comando formale: da plotone ad armata. La storia militare è anche "
            "storia di scuole di guerra, carte, ordini e errori documentati."
        ),
        fields=(
            ("Ruolo", "decidere, coordinare, rispondere dei reparti"),
            ("Formazione", "accademie, scuole di guerra, pratica di reparto"),
        ),
        sections=(
            ("Organizzazione",
             "Ufficiali inferiori, superiori, generali. In marina e in aeronautica i nomi "
             "cambiano (tenente di vascello, colonnello d'aviazione) ma la scala resta."),
            ("Evoluzione",
             "Dal nobile a cavallo al professionista uscito dall'accademia. Il Novecento "
             "aggiunge lo stato maggiore come cervello collettivo."),
        ),
        related=("tenente", "generale", "comando", "napoleone"),
    ),
    card(
        id="soldato",
        kind="rank",
        world="truppe",
        emoji="🪖",
        title="Soldato",
        subtitle="primo scalino",
        era="",
        tags=("grado",),
        aliases=("private", "soldat", "truppa"),
        summary="Grado di truppa: chi entra in servizio senza comando di reparto.",
        fields=(
            ("Italia", "Soldato / VFP"),
            ("Regno Unito", "Private"),
            ("Stati Uniti", "Private"),
            ("Francia", "Soldat"),
            ("Roma (analogia)", "Miles — non è un equivalente preciso"),
        ),
        sections=(
            ("Nota",
             "I gradi non si traducono uno a uno. Qui allineiamo il primo livello di truppa "
             "per leggere le tabelle, non per copiare gerarchie."),
        ),
        related=("caporale", "fanteria"),
    ),
    card(
        id="caporale",
        kind="rank",
        world="truppe",
        emoji="🎖️",
        title="Caporale",
        subtitle="primo comando minuto",
        era="",
        tags=("grado",),
        aliases=("corporal", "caporal"),
        summary="Primo grado di responsabilità su una squadra o un pezzo di servizio.",
        fields=(
            ("Italia", "Caporale / Caporale maggiore"),
            ("Regno Unito", "Corporal"),
            ("Stati Uniti", "Corporal"),
            ("Francia", "Caporal"),
        ),
        sections=(("Scala", "Soldato → Caporale → Sergente"),),
        related=("soldato", "sergente"),
    ),
    card(
        id="sergente",
        kind="rank",
        world="truppe",
        emoji="⭐",
        title="Sergente",
        subtitle="sottufficiale di squadra",
        era="",
        tags=("grado",),
        aliases=("sergeant", "sergent"),
        summary=(
            "Sottufficiale: mestiere, disciplina, addestramento quotidiano. In molte armate "
            "è il «sistema nervoso» del plotone."
        ),
        fields=(
            ("Italia", "Sergente / Sergente maggiore"),
            ("Regno Unito", "Sergeant"),
            ("Stati Uniti", "Sergeant"),
            ("Francia", "Sergent"),
        ),
        related=("caporale", "tenente"),
    ),
    card(
        id="tenente",
        kind="rank",
        world="truppe",
        emoji="🎖️",
        title="Tenente",
        subtitle="primo ufficiale",
        era="",
        tags=("grado",),
        aliases=("lieutenant", "sottotenente"),
        summary="Ufficiale inferiore, spesso al comando di un plotone o come ufficiale di bordo.",
        fields=(
            ("Italia", "Sottotenente / Tenente"),
            ("Regno Unito", "Second Lieutenant / Lieutenant"),
            ("Stati Uniti", "Second Lieutenant / First Lieutenant"),
            ("Francia", "Sous-lieutenant / Lieutenant"),
        ),
        related=("sergente", "capitano", "ufficiali"),
    ),
    card(
        id="capitano",
        kind="rank",
        world="truppe",
        emoji="⭐",
        title="Capitano",
        subtitle="la compagnia",
        era="",
        tags=("grado",),
        aliases=("captain", "capitaine"),
        summary="Ufficiale al comando di compagnia, batteria o squadriglia, a seconda dell'arma.",
        fields=(
            ("Italia", "Capitano"),
            ("Regno Unito", "Captain"),
            ("Stati Uniti", "Captain"),
            ("Francia", "Capitaine"),
            ("Marina", "in marina «capitano» è un'altra scala (capitano di corvetta, fregata, vascello)"),
        ),
        related=("tenente", "maggiore"),
    ),
    card(
        id="maggiore",
        kind="rank",
        world="truppe",
        emoji="⭐⭐",
        title="Maggiore",
        subtitle="ufficiale superiore",
        era="",
        tags=("grado",),
        aliases=("major", "commandant"),
        summary="Primo ufficiale superiore. In Francia il grado analogo di corpo è Commandant.",
        fields=(
            ("Italia", "Maggiore"),
            ("Regno Unito / USA", "Major"),
            ("Francia", "Commandant"),
        ),
        related=("capitano", "colonnello"),
    ),
    card(
        id="colonnello",
        kind="rank",
        world="truppe",
        emoji="⭐⭐⭐",
        title="Colonnello",
        subtitle="il reggimento",
        era="",
        tags=("grado",),
        aliases=("colonel",),
        summary="Tradizionalmente il comandante di reggimento. Oggi anche incarichi di stato maggiore.",
        fields=(
            ("Italia", "Colonnello"),
            ("Regno Unito / USA / Francia", "Colonel"),
        ),
        related=("maggiore", "generale"),
    ),
    card(
        id="generale",
        kind="rank",
        world="truppe",
        emoji="⭐⭐⭐⭐",
        title="Generale",
        subtitle="comando di grande unità",
        era="",
        tags=("grado",),
        aliases=("general", "général", "maresciallo"),
        summary=(
            "Famiglia di gradi apicali (brigadiere, maggiore generale, tenente generale, "
            "generale di corpo). I nomi e le stellette variano per nazione e periodo."
        ),
        fields=(
            ("Italia", "Generale di brigata → di corpo d'armata → Generale"),
            ("USA / UK", "Brigadier / Major General / Lieutenant General / General"),
            ("Francia", "Général de brigade → d'armée"),
        ),
        sections=(
            ("Nota",
             "«Maresciallo» in Italia è un sottufficiale; in Francia e URSS è un titolo "
             "apicale. Stessa parola, mondi diversi."),
        ),
        related=("colonnello", "comando", "ufficiali"),
    ),
)
