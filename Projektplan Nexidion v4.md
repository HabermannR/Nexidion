 **Projektplan: Nexidion v4 – The Collaborative Engine (Aktualisiert)**

## **Phase 1 & 2: V4-Fundament & Feature-Parität**
*(Abgeschlossen, bilden die stabile Basis für die aktuellen Arbeiten)*

*   **Meilenstein 1 & 2:** ✅ **ABGESCHLOSSEN.** Die Anwendung läuft stabil auf der neuen V4-Architektur und die kritischen V2-Features (insb. interne Links) sind wiederhergestellt. Der Live-Betrieb ist etabliert. Epub export und Print preview fehlen noch und müssen nachgereicht werden.

---

## **Phase 3: Technologisches Fundament: Migration zu PostgreSQL `(AKTUELLER FOKUS)`**
*Fokus: Die Anwendung vollständig von der dateibasierten [[SQLite|63984dd5-dbef-4e2a-8098-6d7e87dc4901]]-Datenbank auf einen robusten, Multi-User-fähigen [[PostgreSQL|cd37cd63-4698-4a88-bbed-cd9bf8ba060e]]-Server umstellen. **Dies ist die zwingende Voraussetzung für jede Form der Kollaboration und hat höchste Priorität.** Es werden vor Abschluss dieser Phase **keine Änderungen am Datenbankmodell** vorgenommen.*

*   **[x] 3.1 (Infrastruktur): PostgreSQL-Server aufsetzen.** (Dev & Prod-Server)
*   **[x] 3.2 (Backend): App-Konfiguration anpassen.** (Dev & Prod-Server)
*   **[x] 3.3 (Migration): Initiales Schema erstellen.** (Dev & Prod-Server)
*   **[x] 3.4 (Datenmigration): Einmaliger Datentransfer.** (Dev & Prod-Server)
*   **[ ] 3.5 (Infrastruktur): Migration der "Arbeit"-Instanz abschließen.** Vollständige Umstellung der produktiven Testumgebung auf PostgreSQL. `(HÖCHSTE PRIORITÄT)`
*   **[ ] 3.6 (Workflow): Backup-Prozesse etablieren.** Einrichtung und Validierung von regelmäßigen `pg_dump`-Backups für alle Instanzen.
*   **[ ] 3.7 (Qualitätssicherung): Intensives Testen.** Überprüfen aller Kernfunktionen (Vault erstellen/wechseln, Node anlegen/editieren, Chat) auf den PostgreSQL-Instanzen, um die Stabilität sicherzustellen.

*   **Meilenstein 3:** Die Anwendung läuft auf allen Instanzen produktiv und stabil auf PostgreSQL. Der alte, riskante [[SQLite|63984dd5-dbef-4e2a-8098-6d7e87dc4901]]-Workflow ist vollständig abgelöst und die technologische Basis für Multi-User-Fähigkeit ist geschaffen.

---

## **Phase 4: Das Multi-User-Fundament & Initiales Onboarding**
*Fokus: Die Anwendung von einem Single-Owner-System auf ein kollaboratives System umstellen und den Import bestehender Wissensdatenbanken für den Test auf der Arbeit ermöglichen.*

*   **[ ] 4.1 (Backend): DB-Modelle für Multi-User anpassen.** Umsetzung der geplanten Änderungen in [[models.py|c3a5f9ca-a0fe-4efc-9ed8-bf7efe99cb56]] (User, Vault, Berechtigungen). Dies ist der erste Schritt nach Abschluss von Meilenstein 3.
*   **[ ] 4.2 (Backend): Service-Layer um Berechtigungen erweitern.** Sicherstellen, dass alle API-Aufrufe die Zugriffsrechte des anfragenden Benutzers prüfen (z.B. "Darf User A den Vault B sehen/editieren?").
*   **[ ] 4.3 (Frontend): Einfache UI für Zugriffsverwaltung.** Implementierung einer initialen Settings-Seite, auf der Vault-Besitzer anderen Benutzern Lese-/Schreibrechte erteilen können.
*   **[x] 4.4 (Feature): DokuWiki-Importer entwickeln.** Erstellung eines Skripts oder einer Admin-Funktion zum Import von Inhalten aus DokuWiki in einen Nexidion-Vault. Dies ist entscheidend für die Akzeptanz im Testbetrieb.

*   **Meilenstein 4:** Die Anwendung ist **Multi-User-fähig**. Benutzer können sich authentifizieren, auf geteilte Vaults zugreifen und bestehende Inhalte können importiert werden. Die Anwendung ist bereit für den Praxistest auf der Arbeit.

---

## **Phase 5: Stabilisierung & Architektur-Härtung**
*Fokus: Basierend auf dem Feedback aus dem Testbetrieb bekannte Bugs beheben und architektonische Schwachstellen systematisch beseitigen.*

*   **[ ] 5.1 (Bugfixing): Offene Bugs beheben.** Abarbeiten der Liste aus [[Bugs v4|a227db9b-67b0-44b3-8235-35a8b8d0d23b]].
    *   **[ ] 5.1.1 (Chat):** Unzuverlässiger Input / alter Chat bei Vault-Wechsel.
    *   **[ ] 5.1.2 (UI):** Save-Button Position, inkonsistente Chat-Breite.
    *   **[ ] 5.1.3 (Mobile):** Context Bar nicht sichtbar.
    *   **[ ] 5.1.4 (UX):** Burger-Menü schließt nicht nach Vault-Wahl.

*   **[ ] 5.2 (Architektur): Gatekeeper-Muster verfeinern.** Systematische Überprüfung aller datenabhängigen Komponenten, um die Robustheit bei schnellen Kontextwechseln (Vault, Node) weiter zu verbessern und "Flackern" oder Lade-Deadlocks zu eliminieren.

*   **[ ] 5.3 (Architektur): Settings-Architektur neu konzipieren & umsetzen.**
    *   **[ ] 5.3.1 (Theoretisches Modell):** Klärung des Problems: Globale Settings (z.B. "mein Account") müssen von kontextabhängigen Settings (z.B. "LLM-Einstellungen für Vault X") getrennt werden. Die URL-Struktur (`/settings` vs. `/vaults/:id/settings`) muss dies widerspiegeln. Der "last active vault"-Ansatz im Zustand-Store wird abgeschafft.
    *   **[ ] 5.3.2 (Backend):** Erstellung dedizierter API-Endpunkte für User-Settings und Vault-Settings.
    *   **[ ] 5.3.3 (Frontend):** Umbau der Settings-Seite(n) gemäß dem neuen Modell unter Verwendung von `useQuery` und `useMutation`.

*   **[ ] 5.4 (Code Quality): Gemeinsame Icon-Quelle.** Refactoring, um Icons für Frontend und Backend aus einer gemeinsamen Datei zu lesen und Duplizierung zu vermeiden.
*   **[ ] 5.5 (Feature): LLM-Management im Frontend.** UI zur Verwaltung von LLMs (hinzufügen, im Backend speichern) und deren Temperature-Settings.

*   **Meilenstein 5:** ✅ **PRODUKTREIFE ERREICHT.** Die Anwendung ist Multi-User-fähig, im Praxistest validiert, bekannte Bugs sind behoben und die Architektur ist robust und wartbar. Das Fundament für die Orchestrator-Engine ist grundsolide.

---


## **Phase 6: Die Orchestrator-Engine – Von der Theorie zur robusten Praxis**
*Fokus: Die Anwendung von einem reaktiven Werkzeug zu einer proaktiven, intelligenten Workflow-Plattform weiterentwickeln. Der Fokus liegt auf Stabilität, Skalierbarkeit und Transparenz von Anfang an.*

### **Paket 6.1: "Grundsätzliche Entscheidungen"**
*   **[ ] 6.1 (Fundamentale Entscheidung): Definitiver Task-Runner-Entscheid & Setup**
    *   **Anforderung:** Muss zuverlässig auf Linux (Prod) und Windows (Dev) laufen, robustes Fehlerhandling ermöglichen und skalierbar sein.
    *   **Evaluierung & Entscheidung:** Finale Entscheidung basierend auf deiner Empfehlung:
        *   **Option A (MVP-Fokus):** **Flask-APScheduler** mit PostgreSQL-Backend für maximale Einfachheit und Cross-Plattform-Kompatibilität.
        *   **Option B (Skalierungs-Fokus):** **Dramatiq** mit Redis-Backend als robusterer, Windows-kompatibler Celery-Ersatz.
    *   **Umsetzung:** Die gewählte Technologie wird definitiv entschieden, konfiguriert und fest in die Flask-App integriert.

---
### **Paket 6.2: "Minimaler, aber robuster Async Task"**
*Ziel: Den ersten asynchronen Workflow implementieren, dabei aber sofort die Grundlagen für Monitoring, Fehlerbehandlung und Sicherheit legen.*

*   **[ ] 6.2.1 (Backend): Erweitertes Orchestrator-Datenmodell.** Implementierung der SQLAlchemy-Models für `Workflow` und `Task`. Das `Task`-Modell wird von Anfang an robust gestaltet:
    ```python
    class Task(db.Model):
        # ...
        status = db.Column(db.Enum('pending', 'running', 'completed', 'failed', name='task_status_enum'), default='pending')
        priority = db.Column(db.Integer, default=0)  # 0=normal, 1=high, -1=low
        error_message = db.Column(db.Text, nullable=True)
        retry_count = db.Column(db.Integer, default=0)
    ```
*   **[ ] 6.2.2 (Backend): DB-Modell für `Node` erweitern.** Das `Node`-Modell wird um ein `summary`-Feld (Text) erweitert.
*   **[ ] 6.2.3 (Orchestrator): Erster Task nach Command Pattern.** Implementierung des `generate_summary`-Tasks. Das Design folgt dem **Command Pattern**, um Logik zu kapseln und Testbarkeit/Erweiterbarkeit zu gewährleisten:
    ```python
    # Bsp: a_tasks/commands.py
    class GenerateSummaryCommand:
        def __init__(self, node_id, max_retries=3): ...
        def execute(self): # Logik für Task-Ausführung
        def on_failure(self, exception): # Logik für Fehlerfall
    ```
*   **[ ] 6.2.4 (API): Sicherer Trigger-Endpunkt.** Der Node-Update-Endpunkt löst den Task aus und implementiert sofort **Rate Limiting** (`flask-limiter`), um Missbrauch und Kostenexplosionen zu verhindern.
*   **[ ] 6.2.5 (Architektur): Robustes Fehlerhandling & Graceful Degradation.** Implementierung der Logik, die den `status` im Task-Modell aktualisiert. Was passiert, wenn der LLM-Service ausfällt? Die Anwendung muss stabil bleiben, und der Fehler muss im Task-Objekt sauber protokolliert werden.

---
### **Paket 6.3: "AI as a Knowledge Weaver" (Vorgezogen)**
*Grund: Die Fähigkeit der KI, auf Wissen zu verweisen, ist eine grundlegendere Fähigkeit als die Aktualisierung von Inhalten und verbessert die Qualität aller nachfolgenden KI-Features.*

*   **[ ] 6.3.1 (Backend - MVP): "Context Stuffing"-Ansatz.** Der System-Prompt im Chat wird mit dem serialisierten Vault-Baum (Titel, UUIDs) angereichert.
*   **[ ] 6.3.2 (Frontend): Markdown-Renderer im Chat nutzen.** Sicherstellen, dass die von der AI generierten `[[...]]`-Links im Chat korrekt und klickbar dargestellt werden.
*   **[ ] 6.3.3 (Backend - Advanced): "Tool Use"-Ansatz.** Konzeption und Implementierung eines `find_node_by_title`-Tools für die AI als skalierbare Langzeitlösung, die Token-Limits umgeht.

---
### **Paket 6.4: "Dein Async Update"**
*Ziel: Den Kern-Use-Case "AI Propose Update" auf die neue, asynchrone und fehlertolerante Engine migrieren.*

*   **[ ] 6.4.1 (Backend): AI Update Task-Typ definieren.** Erstellung des asynchronen Tasks `propose_node_update` nach dem Command Pattern.
*   **[ ] 6.4.2 (API): Integration in das Workflow-System.** Die API erstellt einen `Workflow` und den `Task`, antwortet sofort mit einer `workflow_id` und überlässt die Ausführung dem Task-Runner.
*   **[ ] 6.4.3 (Frontend): UI auf asynchrone Antwort umstellen.** Die UI wartet nicht mehr, sondern zeigt einen "In Bearbeitung..."-Status an und bereitet sich auf den Empfang des Ergebnisses vor (siehe nächstes Paket).

---
### **Paket 6.5: "Das interaktive Cockpit"**
*Ziel: Volle Transparenz über die AI-Prozesse schaffen und eine exzellente User Experience für langlaufende Aktionen bieten.*

*   **[ ] 6.5.1 (Backend): Monitoring-API-Endpunkte.** Erstellung von `GET /workflows` und `GET /tasks`-Endpunkten.
*   **[ ] 6.5.2 (Backend): WebSocket-Integration.** Implementierung eines WebSocket-Servers (z.B. mit `Flask-SocketIO`), der Frontend-Clients über Status-Updates von Tasks in Echtzeit informiert (`task_started`, `task_completed`, `task_failed`).
*   **[ ] 6.5.3 (Frontend): Interaktive Monitoring-UI.** Eine UI, die sich per WebSocket verbindet und den Status der Tasks live anzeigt. Polling wird damit überflüssig, die UX ist deutlich besser.

---
### **Paket 6.6: "Bubble Up MVP"**
*Ziel: Den zweiten wichtigen Use Case, die Aktualisierung abhängiger Nodes, konzeptionell sauber und technisch beherrschbar umsetzen.*

*   **[ ] 6.6.1 (Backend): Konzeption & Risikobewertung.** Vor der Implementierung wird ein klares Konzept für das Dependency-System erarbeitet, das folgende Punkte adressiert:
    *   **Zykluserkennung:** Wie werden Endlosschleifen in Abhängigkeiten verhindert?
    *   **Performance:** Wie wird sichergestellt, dass die Analyse bei großen Vaults performant bleibt?
    *   **Benutzersteuerung:** Wie kann der Benutzer steuern, welche Änderungen propagiert werden sollen (z.B. Opt-in/Opt-out pro Node oder Link)?
*   **[ ] 6.6.2 (Backend): Dependency-Analyse implementieren.** Umsetzung der Logik zur Erkennung von Abhängigkeiten.
*   **[ ] 6.6.3 (Workflow): "Bubble-Up"-Workflow erstellen.** Implementierung des Workflows, der bei Änderungen die abhängigen Nodes identifiziert und Folge-Tasks (z.B. "review_dependency") erstellt.

*   **Meilenstein 6:** Nexidion hat sich zu einer robusten, transparenten und intelligenten Workflow-Plattform entwickelt.

---

## **Phase 7: Produktreife & Skalierung (Zukunft)**

*   **[ ] 7.1: Task-Type Bibliothek & weitere strategische Workflows.**
+   **[ ] 7.2 (UX-Erweiterung): Node-Visualisierung mit Infinite Canvas.**
+       *   **Evaluierung:** Prüfung von Standards wie `JSON Canvas` für die Implementierung.
+       *   **Ziel:** Eine alternative, räumliche Ansicht auf die Nodes eines Vaults bieten, um Zusammenhänge und Strukturen visuell zu erkunden. Potenziell auch zur Visualisierung von `Workflow`-Abhängigkeiten.
*   **[ ] 7.3: Globaler Admin-Bereich & System-Management.**
*   **[ ] 7.4: Sicherheit & Compliance härten.**
*   **[ ] 7.5: Dokumentation & finales Polishing.**

*   **Meilenstein 7:** Nexidion ist eine robuste, sichere und gut dokumentierte Plattform für intelligente Wissensarbeit.

---

## **Entwicklungsphilosophie: Kleine, funktionsfähige Pakete**

**Jeder Schritt endet in einem lauffähigen System** - das ist entscheidend für:
- **Motivation:** Konstanter, sichtbarer Fortschritt
- **Risikominimierung:** Kein "alles oder nichts", jederzeit pausierbar
- **Qualität:** Kleine Änderungen sind einfach zu debuggen
- **Flexibilität:** Richtungsänderungen sind jederzeit möglich

**Nach jedem Paket:** Vollständige Funktionsfähigkeit, Option zur Pause oder Richtungsänderung.
