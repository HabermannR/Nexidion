# **Design-Dokument: Nexidion V4 – The Collaborative Engine**

## **1. Vision & Strategische Neuausrichtung**

Nexidion V4 markiert den Übergang von einem persönlichen Wissens-Tresor zu einer kollaborativen, proaktiven Wissens-Engine. Während frühere Versionen die Kernfunktionalität validiert haben, erfordern die strategischen Ziele – insbesondere die **Multi-User-Fähigkeit** und die **Orchestrator Engine** – eine grundlegende Neuausrichtung der Frontend-Architektur.

Die V3-Architektur, die auf den Datenlade-Mechanismen von React Router basierte, war für eine Single-User-Anwendung konzipiert. Sie ist an ihre Grenzen gestoßen, da die Anforderungen des Projekts über einfache, navigationsgesteuerte Datenabfragen hinausgewachsen sind.

**Das Ziel von V4 ist es, ein technisches Fundament zu schaffen, das die strategische Vision von Nexidion nicht nur unterstützt, sondern aktiv ermöglicht. Wir bauen ein reaktives, robustes und skalierbares "Cockpit" für die Orchestrator Engine.**

## **2. Lehren aus V3: Die zu lösenden Kernprobleme**

Die V3-Architektur hat entscheidende Schwächen offenbart, die in V4 systematisch behoben werden müssen:

1.  **Enge Kopplung an die Navigation:** Das Laden von Daten war untrennbar mit dem Routing verbunden, was zu unerwünschten und unkontrollierbaren Neuladevorgängen bei reinen UI-Interaktionen führte.
2.  **Mangelnde Skalierbarkeit für Kollaboration:** Das System war "egozentrisch" und konnte nicht auf externe Änderungen (durch andere Benutzer oder serverseitige Prozesse) reagieren.
3.  **Unzureichende Cache-Kontrolle:** Es gab keine granulare Möglichkeit, Datensätze gezielt zu invalidieren, was oft zu "Over-Fetching" führte.
4.  **Hohe Komplexität & schlechte Developer Experience:** Die Logik zur Steuerung des Neuladens (`shouldRevalidate`) wurde zunehmend komplex und fehleranfällig.

## **3. Anforderungen an die V4-Architektur**

### Funktionale Anforderungen
*   **Entkopplung von Daten und Navigation:** Der Datenabruf muss vollständig unabhängig vom Routing-Zustand sein.
*   **Granulare Cache-Invalidierung:** Gezielte Definition, welche Daten nach einer Aktion veraltet sind.
*   **Unterstützung für externe Datenänderungen:** Die UI muss auf serverseitige Events reagieren können.
*   **Robustes Management von Server-Zuständen:** Klare und zuverlässige Verwaltung von Lade-, Fehler- und Erfolgszuständen.
*   **Intelligentes Caching:** Native Unterstützung für Strategien wie `stale-while-revalidate`.

### Nicht-funktionale (architektonische) Anforderungen
*   **Wartbarkeit & Skalierbarkeit:** Die Architektur muss logisch, vorhersehbar und erweiterbar sein.
*   **Hervorragende Developer Experience:** Werkzeuge müssen das Debugging erleichtern und die Entwicklungsgeschwindigkeit erhöhen.
*   **Klare Trennung der Zuständigkeiten (Separation of Concerns):** Eine saubere Trennung zwischen Server-Zustand, globalem UI-Zustand und Routing ist oberstes Gebot.

## **4. Die V4-Architektur: Das 3-Säulen-Modell**

Um die Anforderungen zu erfüllen, wird die V3-Architektur durch ein klares, Query-zentrisches 3-Säulen-Modell ersetzt.

### **Säule 1: React Router (Der Navigator)**
*   **Verantwortlichkeit:** Ausschließlich für das URL-basierte Routing und das Rendern der entsprechenden Komponenten-Layouts.
*   **Umsetzung:** Die `loader`- und `action`-Eigenschaften der Routen sind vollständig entfernt.

### **Säule 2: TanStack Query (Die Daten-Engine)**
*   **Verantwortlichkeit:** Die alleinige Quelle der Wahrheit (`Single Source of Truth`) für den gesamten **Server-Zustand**. Verwaltet den gesamten Lebenszyklus von Datenabfragen: Caching, Hintergrund-Aktualisierung, Invalidierung und Fehlerbehandlung.
*   **Umsetzung:**
    *   **`useQuery`:** Ersetzt alle `loader`. Jede Komponente deklariert ihre Datenabhängigkeiten direkt.
    *   **`useMutation`:** Ersetzt alle `action`-Funktionen für schreibende Operationen.
    *   **`QueryClient`:** Wird zentral genutzt, um nach Mutationen gezielt Queries zu invalidieren.
    *   **React Query Devtools:** Sind ein integraler Bestandteil des Entwicklungs-Workflows.

### **Säule 3: Zustand (Der UI-Controller)**
*   **Verantwortlichkeit:** Verwaltung des rein clientseitigen, globalen UI-Zustands, der keine Entsprechung auf dem Server hat (z.B. Benutzerauswahlen, geöffnete Panels).
*   **Umsetzung:** Der `workspaceStore` bleibt die zentrale Anlaufstelle für flüchtigen, globalen UI-Zustand.

## **5. Architektur-Muster, Regeln & Lessons Learned**

Um die Klarheit und Wartbarkeit der 3-Säulen-Architektur sicherzustellen, sind folgende Muster und Regeln verbindlich. Dieses Kapitel wurde um die entscheidenden **"Lessons Learned" aus der praktischen Implementierung** erweitert, um typische Fallstricke zu vermeiden.

### **5.1. Primäres Datenzugriffsmuster: Dedizierte Query-Hooks**

**Regel:** Für wiederkehrende Server-Datenabfragen ist **immer** ein dedizierter, wiederverwendbarer Custom Hook zu erstellen.

*   **Prinzip:** Eine `useQuery`-Definition wird in einem eigenen Hook gekapselt. Jede Komponente, die diese Daten benötigt, ruft diesen Hook auf, anstatt `useQuery` direkt zu verwenden.
*   **Beispiel (`useVaultTreeQuery`):**
    ```javascript
    // src/services/queries/useVaultTreeQuery.js
    export const useVaultTreeQuery = (vaultId) => {
      return useQuery({
        queryKey: ['vaultTree', vaultId],
        queryFn: () => apiClient.get(/* ... */),
        enabled: !!vaultId,
      });
    };
    ```
*   **Vorteile und Begründung ("Vertraue dem Cache, nicht dem Context"):**
    1.  **Effizienz:** TanStack Query's globaler Cache verhindert doppelte Netzwerkanfragen. Wenn zwei Komponenten `useVaultTreeQuery(vaultId)` aufrufen, wird die API nur einmal kontaktiert. Der Cache ist der Mechanismus zur gemeinsamen Datennutzung.
    2.  **Maximale Entkopplung:** Jede Komponente deklariert ihre Abhängigkeiten explizit und ist nicht von einem übergeordneten Provider abhängig.
    3.  **Code-Vereinfachung:** Dieses Muster vermeidet die Komplexität einer zusätzlichen `React.Context`-Schicht für Server-Daten.
    4.  **Zentralisierte Logik:** Query-Schlüssel, API-Funktionen und Caching-Optionen (`staleTime` etc.) sind an einem einzigen, wiederverwendbaren Ort definiert.

### **5.2. Verbot von Server-Daten in `zustand` (mit Klarstellung)**

**Regel:** Daten, die ihre "Source of Truth" auf dem Server haben (z.B. `treeData`, `versions`), dürfen **niemals** dauerhaft im `zustand`-Store dupliziert werden.

*   **Begründung:** Dies würde die V4-Architektur untergraben, indem es zu zwei konkurrierenden "Sources of Truth" führt und alle Vorteile von TanStack Query (automatisches Caching, Revalidierung, Ladezustände) zunichtemacht.
*   **Klarstellung & Ausnahme:** Der `zustand`-Store darf als **kurzlebiger Zwischenspeicher für UI-Zustände** verwendet werden, die sich aus Server-Daten ableiten (z.B. der aktuell ausgewählte Node, `diffSelection.base`). Dies ist akzeptabel, solange die Logik zum Befüllen und Zurücksetzen dieses Zustands robust und kontextbewusst ist (siehe Regel 5.5).

### **5.3. Selektives Rendering mit `zustand`**

**Regel:** Um unnötige Re-Renders zu vermeiden, muss **jeder Wert** aus dem `zustand`-Store mit einem eigenen, atomaren Hook-Aufruf selektiert werden.

*   **KORREKTES PATTERN:**
    ```javascript
    const valA = useStore(state => state.valA);
    const valB = useStore(state => state.valB);
    ```
*   **ANTI-PATTERN (verboten):**
    ```javascript
    // Führt zu Endlosschleifen, da bei jedem Render ein neues Objekt erstellt wird.
    const { valA, valB } = useStore(state => ({ valA: state.valA, valB: state.valB }));
    ```

### **5.4. Die Eiserne Regel von React: Unbedingte Hooks**

**Regel:** Hooks (jede Funktion, die mit `use...` beginnt) müssen **bei jedem einzelnen Render-Durchlauf einer Komponente in exakt derselben Reihenfolge aufgerufen werden**.

*   **Verbot:** Hooks dürfen **niemals** innerhalb von Bedingungen (`if/else`), Schleifen oder nach einem `return`-Statement aufgerufen werden. Die `enabled`-Option von `useQuery` ist eine Ausnahme, da sie den Hook nicht entfernt, sondern nur seine Ausführung pausiert.
*   **Begründung:** React verlässt sich auf die Aufrufreihenfolge, um den Zustand den richtigen Hooks zuzuordnen. Eine Änderung dieser Reihenfolge führt zu unvorhersehbaren Fehlern und Abstürzen (`Rendered more hooks than during the previous render`).
*   **KORREKTES PATTERN (Struktur einer Komponente):**
    ```javascript
    function MyComponent() {
        // PHASE 1: Alle `use...` Hooks ganz oben. Ausnahmslos.
        const { id } = useParams();
        const { data, isLoading, isError } = useMyQuery(id);
        const [uiState, setUiState] = useState(null);
        // ... alle weiteren Hooks ...

        // PHASE 2: Alle `useEffect`-Hooks.
        useEffect(() => { /* ... */ }, [data]);

        // PHASE 3: Alle Guard Clauses und bedingten "Early Returns".
        if (isLoading) return <Loading />;
        if (isError) return <Error />;
        if (!data) return <Empty />;

        // PHASE 4: Alle Berechnungen und Logik für das Rendering.
        const processedData = process(data);

        // PHASE 5: Das finale JSX-Return-Statement.
        return <div>{processedData}</div>;
    }
    ```

### **5.5. Das Gatekeeper-Muster & die Asynchronitäts-Falle**

Die größte Herausforderung der V4-Architektur ist das Management des Zusammenspiels von asynchronem Server-Zustand (`useQuery`) und synchron/asynchronem Client-Zustand (`zustand`).

**Problem:** Ein Kontextwechsel (z.B. Login, Vault-Wechsel, Node-Wechsel) löst zwei Dinge gleichzeitig aus:
1.  **Imperativer Reset (schnell):** Ein `useEffect` löscht den alten UI-Zustand aus dem `zustand`-Store (`resetContext()`).
2.  **Deklaratives Laden (langsam):** Ein `useQuery` startet eine neue Netzwerkanfrage für die Daten des neuen Kontexts.

**Die Lücke zwischen (1) und dem Abschluss von (2) ist die Quelle von "flackernden" UIs, "Kein Inhalt"-Meldungen und "hängenden" Ladebildschirmen.**

**Regel:** Jede Komponente, die Server-Daten anzeigt, muss ein **"Gatekeeper"** sein. Sie muss geduldig sein und darf ihren Inhalt erst rendern, wenn alle notwendigen Daten (sowohl vom Server als auch aus dem `zustand`-Store) garantiert vorhanden sind.

*   **Prinzip:** Eine Komponente muss ihren Lade- und Fehlerzustand aus **allen** ihren asynchronen Abhängigkeiten ableiten.
*   **ANTI-PATTERN (führt zu Deadlocks):**
    ```javascript
    // Falsch: Die Ladebedingung hängt vom Zustand-Store ab, der asynchron befüllt wird.
    // Wenn das Befüllen fehlschlägt, bleibt `!baseDataFromStore` für immer `true`.
    const isLoading = isQueryLoading || !baseDataFromStore; 
    if (isLoading) return <Loading />;
    ```
*   **KORREKTES GATEKEEPER-PATTERN:**
    ```javascript
    function NodeContent() {
        // 1. Hole alle Datenquellen.
        const { data: serverData, isLoading, isError } = useMyQuery(id);
        const { data: storeData } = useMyStore();

        // 2. Effekt, der den Store befüllt.
        useEffect(() => {
            if (serverData) setStoreData(serverData.someValue);
        }, [serverData]);

        // 3. GATEKEEPER: Prüfe zuerst den Ladezustand der *Server-Daten*.
        if (isLoading) return <Loading />;
        if (isError) return <Error />;

        // 4. GATEKEEPER: Prüfe erst DANACH den Zustand der *abgeleiteten Daten*.
        // `serverData` ist jetzt garantiert vorhanden.
        if (!serverData) return <Empty />; // z.B. API gab leeres Array zurück
        
        // Erst jetzt kann man sich auf den Store-Wert verlassen.
        if (!storeData) return <Loading />; // Für den kurzen Moment zwischen useEffect und Re-Render

        // 5. RENDERN: Jetzt sind alle Daten garantiert vorhanden.
        return <div>{storeData.name}</div>;
    }
    ```

### **5.6. Kontextbewusstes Aufräumen von Zustand**

**Regel:** Wenn eine Komponente einen Wert im globalen `zustand`-Store setzt, der vom URL-Kontext abhängt (z.B. die `nodeId`), muss sie auch dafür verantwortlich sein, diesen Zustand aufzuräumen, wenn sich der Kontext ändert.

*   **Problem:** Wenn man von Node A zu Node B navigiert, bleibt der Zustand von Node A im `zustand`-Store erhalten, was dazu führt, dass `NodeContent` die alten Daten anzeigt.
*   **Lösung:** Ein dedizierter `useEffect`, der nur auf die sich ändernde ID aus der URL reagiert und eine "Aufräum"-Aktion im Store aufruft.
*   **KORREKTES PATTERN:**
    ```javascript
    // In einer Komponente wie NodeContent.jsx
    const { nodeId } = useParams();
    const clearNodeSpecificState = useStore(state => state.clearNodeSpecificState);

    // Dieser Effekt feuert NUR, wenn sich die nodeId ändert.
    useEffect(() => {
        // Räume den alten Zustand auf, BEVOR neue Daten geladen werden.
        clearNodeSpecificState();
    }, [nodeId, clearNodeSpecificState]); 
    ```

### **5.7. Die Datenfluss-Strategie: Wer lädt was und wann?**

Eine der fundamentalsten Entscheidungen in der V4-Architektur ist, welche Komponente für das Laden welcher Daten verantwortlich ist. Ein falscher Ansatz hier führte zu den anfänglichen Problemen wie "Prop Drilling" (Daten durch viele Ebenen reichen) oder dem Bruch der Komponenten-Autonomie.

**Die finale, verbindliche Regel lautet: "Co-Location von Daten und Ansicht".**

**Regel:** Jede Komponente, die Server-Daten zur Darstellung benötigt, ist **selbst dafür verantwortlich, diese Daten mit dem entsprechenden `useQuery`-Hook abzurufen**.

*   **Prinzip:** Die Logik zum Laden von Daten befindet sich direkt bei der Komponente, die diese Daten anzeigt.
    *   `<ProjectTree />` braucht den Vault-Baum -> ruft `useVaultTreeQuery` auf.
    *   `<NodeContent />` braucht die Versionen eines Nodes -> ruft `useQuery(['versions', ...])` auf.
    *   `<NodeContent />` braucht AUCH den Vault-Baum für Breadcrumbs -> ruft ebenfalls `useVaultTreeQuery` auf.

**War die Ladereihenfolge nicht ein Problem?**

Ja, aber das Problem war nicht, *dass* mehrere Komponenten dieselben Daten angefragt haben. Das Problem war, dass sie die **Konsequenzen** dieser Anfragen (Lade- & Fehlerzustände) nicht korrekt behandelt haben.

**Warum dieser Ansatz der richtige ist (Dank TanStack Query):**

1.  **Automatische Deduplizierung:** Dies ist der magische Teil von TanStack Query. Wenn `<ProjectTree />` und `<NodeContent />` **exakt denselben `queryKey`** (`['vaultTree', vaultId]`) verwenden, wird die API-Anfrage **nur ein einziges Mal** an den Server gesendet. Die zweite Komponente, die den Hook aufruft, erhält die Daten sofort aus dem laufenden Request oder dem Cache. Es gibt keine doppelten Netzwerkanfragen.

2.  **Komponenten-Autonomie:** Jede Komponente ist eine in sich geschlossene, unabhängige Einheit. `<ProjectTree />` funktioniert auch dann, wenn `<NodeContent />` nicht auf der Seite ist und umgekehrt. Man muss nicht darüber nachdenken, ob ein übergeordnetes Layout die Daten schon geladen hat. Das vereinfacht das Refactoring und die Wiederverwendbarkeit enorm.

3.  **Kein "Prop Drilling":** Wir müssen die Baumdaten nicht vom `WorkspaceLayout` durch drei Ebenen nach unten an eine tief verschachtelte Komponente weiterreichen.

**Die Lösung des Problems liegt also nicht in der Zentralisierung des Datenabrufs, sondern in der konsequenten dezentralen Implementierung des Gatekeeper-Musters (Regel 5.5).**

**Zusammenfassendes Beispiel des korrekten Datenflusses beim Vault-Wechsel:**

1.  **URL wechselt** zu `/vaults/B/nodes/123`.
2.  **`<WorkspaceLayout />`** rendert. Es ist "dumm" und kümmert sich nur um die Anordnung der Panels.
3.  **`<ProjectTree />`** (im linken Panel) rendert:
    *   Ruft `useVaultTreeQuery('B')` auf.
    *   `isLoading` ist `true`.
    *   Der Gatekeeper in `<ProjectTree />` greift: `return <TreeLoader />`.
4.  **`<NodeContent />`** (im mittleren Panel) rendert:
    *   Ruft `useVaultTreeQuery('B')` auf. TanStack Query sieht denselben Key und hängt sich an den laufenden Request an. `isLoading` ist ebenfalls `true`.
    *   Ruft `useQuery(['versions', 'B', '123'])` auf. `isLoadingVersions` ist `true`.
    *   Der Gatekeeper in `<NodeContent />` greift: `return <ContentLoader />`.
5.  **Der Benutzer** sieht zwei Ladeanzeigen in den jeweiligen Panels. Die Anwendung ist stabil.
6.  **Die API-Anfragen** werden abgeschlossen.
7.  **TanStack Query** benachrichtigt alle Komponenten, die auf diese `queryKeys` lauschen.
8.  **`<ProjectTree />`** rendert neu: `isLoading` ist `false`. Der Gatekeeper lässt den Code passieren und der Baum wird gerendert.
9.  **`<NodeContent />`** rendert neu: Beide `isLoading`-Flags sind `false`. Der Gatekeeper lässt den Code passieren und der Node-Inhalt wird gerendert.

Dieser dezentrale, aber durch TanStack Query koordinierte Ansatz ist das Herzstück der V4-Datenarchitektur. Er bietet maximale Entkopplung und Wartbarkeit, erfordert aber von jeder datenabhängigen Komponente die Disziplin, das Gatekeeper-Muster zu implementieren.
---

## **6. Offene Punkte & Zukünftige Refactorings (TODO)**

*   **Settings-Architektur überarbeiten:** Die aktuelle Implementierung der `LlmSettings` ist ein Relikt und verstößt gegen Regel 5.2.
    *   **Ziel:** Die LLM-Modell-Auswahl und -Verwaltung sollte vollständig über das Backend gesteuert werden (eigene API-Endpunkte).
    *   **Umsetzung:** `chatModel` und `titleModel` aus dem `zustand`-Store entfernen. Die Einstellungsseite verwendet `useQuery` zum Lesen und `useMutation` zum Speichern der Einstellungen pro Benutzer (oder pro Vault, je nach finaler Entscheidung).

## **7. Der V4-Technology-Stack**

*   **Backend:** Python/Flask, SQLAlchemy, Celery & Redis
*   **Frontend:**
    *   Core: React 18+, Vite
    *   **Routing:** React Router v6
    *   **Server State Management:** **TanStack Query (React Query) v5**
    *   **Client State Management:** Zustand
    *   UI-Komponenten: Radix UI, Tailwind CSS

## **8. Erwartete Ergebnisse & Fazit**

Die V4-Architektur und die dazugehörigen, präzisierten Best Practices werden Nexidion auf ein neues Level heben. Die "Lessons Learned" sind kein Zeichen einer schwachen Architektur, sondern das Ergebnis eines rigorosen Prozesses, der theoretische Eleganz mit praktischer Robustheit in Einklang bringt. Die Anwendung ist nun nicht nur vorhersehbarer und performanter, sondern das Entwicklerteam hat ein tieferes, praxisnahes Verständnis für die Interaktion der Systemkomponenten gewonnen, was zukünftige Entwicklungen beschleunigen und Fehler minimieren wird.
