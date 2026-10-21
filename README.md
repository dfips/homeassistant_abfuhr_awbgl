# AWB Bergisch Gladbach Abfuhr

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dfips&repository=homeassistant_abfuhr_awbgl&category=integration)
[![GitHub release](https://img.shields.io/github/v/release/dfips/homeassistant_abfuhr_awbgl)](https://github.com/dfips/homeassistant_abfuhr_awbgl/releases)

Eine Home-Assistant-Integration für die Abfuhrtermine der **AWB Bergisch Gladbach**.
Die Daten kommen aus der öffentlichen JSON-API der AbfallApp von regio iT – ohne
API-Schlüssel und ohne Anmeldung.

> Dieses Projekt ist inoffiziell und steht in keiner Verbindung zur AWB
> Bergisch Gladbach oder zu regio iT.

## Funktionen

- Abfuhrkalender für eine Straße in Bergisch Gladbach
- Nächster Abfuhrtermin als Datumssensor
- Ein eigener Sensor pro ausgewählter Abfallart
- Kalender-Entität mit ganztägigen Terminen für Automatisierungen
- Restmüll-Varianten:
  - Standard (14-täglich)
  - 4-wöchentlich, rote Tonne
  - 4-wöchentlich, grüne Tonne
  - Alle Varianten gleichzeitig
- Weitere Abfallarten: Biomüll, Altpapier, Gelber Sack, Weihnachtsbaum
- Konfiguration über die Home-Assistant-Oberfläche
- Automatische Aktualisierung, standardmäßig alle 12 Stunden
- Deutsche und englische Übersetzungen

## Installation über HACS

1. HACS öffnen.
2. **Integrationen** auswählen.
3. Oben rechts auf **⋮ → Benutzerdefinierte Repositories** klicken.
4. Diese URL eintragen:

   ```text
   https://github.com/dfips/homeassistant_abfuhr_awbgl
   ```

5. Als Kategorie **Integration** auswählen und hinzufügen.
6. Nach **AWB Bergisch Gladbach Abfuhr** suchen und installieren.
7. Home Assistant neu starten.
8. **Einstellungen → Geräte & Dienste → Integration hinzufügen** öffnen und
   **AWB Bergisch Gladbach Abfuhr** auswählen.

Alternativ kann der Button oben verwendet werden, wenn My Home Assistant
eingerichtet ist.

### Manuelle Installation

Den Ordner `custom_components/abfuhr_awbgl` nach
`/config/custom_components/abfuhr_awbgl` kopieren und Home Assistant neu starten.

## Einrichtung

Bei der Einrichtung werden Straße und optional die PLZ abgefragt. Die
Integration lädt die Straßenliste der AWB und gleicht den Namen lokal ab.
Mehrere Treffer werden zur Auswahl angezeigt.

Danach werden die Abfuhr-Einstellungen gewählt:

| Einstellung | Bedeutung |
| --- | --- |
| Restmüll-Variante | Standard, 4-wöchentlich rot, 4-wöchentlich grün oder alle Varianten |
| Weitere Abfallarten | Biomüll, Altpapier, Gelber Sack, Weihnachtsbaum |
| Aktualisierungsintervall | Standard 12 Stunden, einstellbar von 1 bis 48 Stunden |

Bei „Alle Restmüll-Varianten“ werden die Termine aller drei Varianten
angezeigt. Pro Haushalt gilt davon nur eine Variante; die Option ist für die
Prüfung und für Haushalte gedacht, bei denen die Tonnengröße noch nicht klar
ist.

Über **Konfigurieren** an der Integration lassen sich Restmüll-Variante,
weitere Abfallarten und das Intervall später ändern. Die Straße selbst bleibt
beim Anlegen fest; für eine andere Straße wird ein zweiter Eintrag angelegt.

## Entitäten

Nach der Einrichtung entstehen je nach Auswahl:

- ein Sensor **Nächste Abfuhr** mit dem nächsten Termin
- ein Sensor pro Abfallart, z. B. **Restmüll**, **Biomüll**, **Altpapier**
- eine Kalender-Entität **Abfuhrtermine**

Der Sensor **Nächste Abfuhr** liefert als Zustand ein Datum im Format
`YYYY-MM-DD`. Wichtige Attribute:

| Attribut | Bedeutung |
| --- | --- |
| `days_until` | Tage bis zur nächsten Abfuhr (0 = heute) |
| `weekday` | Deutscher Wochentag |
| `fractions` | Abfallarten am nächsten Termin |
| `next_dates` | Die nächsten fünf Abfuhrtage mit Abfallarten |
| `street`, `plz`, `ortsteil` | Konfigurierte Straße |
| `last_import` | Datenstand der AWB |
| `restmuell_variante` | Gewählte Restmüll-Variante |

Die genauen Entity-IDs hängen vom Gerätenamen ab und können in Home Assistant
angepasst werden.

## Automatisierungen

### Erinnerung am Vortag

Die Kalender-Entität eignet sich für einen Kalender-Trigger. Ein ganztägiges
Event beginnt um Mitternacht; mit einem Offset von 12 Stunden wird die
Erinnerung am Vortag um 12:00 Uhr ausgelöst.

```yaml
automation:
  - alias: "Abfuhr-Erinnerung"
    triggers:
      - trigger: calendar
        event: start
        entity_id: calendar.strasse_abfuhrtermine
        offset: "-12:00:00"
    actions:
      - action: notify.notify
        data:
          title: "Müll rausstellen"
          message: "{{ trigger.calendar_event.summary }}"
```

Die Entity-ID `calendar.strasse_abfuhrtermine` muss durch die eigene
Kalender-Entität ersetzt werden.

### Erinnerung über den Sensor

```yaml
automation:
  - alias: "Abfuhr-Erinnerung am Abend"
    triggers:
      - trigger: time
        at: "18:00:00"
    conditions:
      - condition: template
        value_template: >-
          {{ state_attr('sensor.strasse_naechste_abfuhr', 'days_until') == 1 }}
    actions:
      - action: notify.notify
        data:
          title: "Morgen: Müll rausstellen"
          message: >-
            {{ state_attr('sensor.strasse_naechste_abfuhr', 'fractions') | join(', ') }}
```

## Datenquelle

Die Integration ruft folgende öffentliche Endpunkte auf:

```text
https://aw-bgl2-abfallapp.regioit.de/abfall-app-aw-bgl2/rest
```

Es werden ausschließlich öffentliche Stammdaten und Abfuhrtermine geladen. Die
API benötigt keinen Schlüssel. Es werden keine Zugangsdaten, Namen,
Hausnummern oder Koordinaten übertragen; die Abfrage erfolgt über die
Straßen-ID.

## Datenschutz

- Keine Telemetrie und keine externen Dienste außer der AWB-API.
- Die Konfiguration wird ausschließlich lokal in Home Assistant gespeichert.
- Der Diagnose-Export redigiert Straßenname, PLZ und Ortsteil.
- Es werden keine Zugangsdaten oder Schlüssel benötigt.
- Im Repository sind keine Secrets, lokalen Pfade oder persönlichen Daten
  enthalten.

## Einschränkungen

- Die API ist inoffiziell und kann sich ohne Ankündigung ändern.
- Die Daten werden straßenbezogen geliefert; eine Hausnummern-Auswahl gibt es
  in Bergisch Gladbach nicht.
- Meist ist nur das laufende Jahr verfügbar. Termine für das nächste Jahr
  erscheinen, sobald die AWB sie veröffentlicht.
- Bei „Alle Restmüll-Varianten“ können mehrere Restmüll-Termine an einem Tag
  erscheinen, obwohl pro Haushalt nur eine Variante gilt.
- Die Integration ist nicht mit der offiziellen AbfallApp verbunden.

## Fehlerbehebung

**Keine Straße gefunden**

Schreibweise prüfen und gegebenenfalls die PLZ angeben. Die Suche gleicht
Umlaute, `ß`/`ss` und `Straße`/`Str.` an.

**Keine Termine für das nächste Jahr**

Die AWB hat die Daten noch nicht veröffentlicht. Die Integration aktualisiert
sich automatisch, sobald die Termine verfügbar sind.

**Verbindungsfehler**

Die API ist eventuell vorübergehend nicht erreichbar. Die Integration
versucht es beim nächsten Update erneut. Debug-Logs lassen sich so aktivieren:

```yaml
logger:
  logs:
    custom_components.abfuhr_awbgl: debug
```

## Lizenz

MIT – siehe [LICENSE](LICENSE).
