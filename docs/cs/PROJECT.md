# Weather Underground Uploader

## 1. Účel

Weather Underground Uploader je malá samostatná služba, která:

1. odebírá meteorologická měření publikovaná přes MQTT,
2. získává a normalizuje nakonfigurované hodnoty,
3. uchovává poslední platnou hodnotu pro každé podporované meteorologické pole,
4. pravidelně odesílá neprázdné pozorování do osobní meteorologické stanice
   Weather Underground (PWS).

Aplikace nesmí záviset na API Home Assistantu, konkrétním MQTT publisheru ani
konkrétním výrobci hardwaru.

```text
MQTT publishers
      │
      ▼
 MQTT broker
      │
      ▼
Weather Underground Uploader
      │
      ▼
Weather Underground PWS
```

Implementace má zůstat malá a srozumitelná. MQTT témata, pole payloadu,
jednotky, přihlašovací údaje a intervaly specifické pro konkrétní instalaci musí
být dodány externě.

---

## 2. Rozsah MVP

MVP musí podporovat:

- konfiguraci ve formátu YAML,
- jeden MQTT broker,
- více MQTT témat a zdrojů,
- skalární a JSON MQTT payloady,
- získání jedné hodnoty z každého nakonfigurovaného zdroje,
- teplotu, relativní vlhkost a atmosférický tlak,
- převod podporovaných vstupních jednotek,
- kontrolu aktuálnosti pro každý zdroj,
- pravidelná dílčí pozorování,
- odesílání do Weather Underground PWS,
- automatické opětovné připojení k MQTT,
- validaci vstupu a konfigurace,
- strukturované textové logování na standardní výstup,
- korektní ukončení procesu,
- Docker image a konfiguraci Docker Compose,
- přihlašovací údaje dodané pomocí proměnných prostředí.

Mimo rozsah MVP jsou:

- integrace s API Home Assistantu,
- databáze nebo ukládání historie,
- webové uživatelské rozhraní,
- endpointy pro metriky,
- opětovné načtení konfigurace bez restartu procesu,
- vnořené JSON cesty,
- šablony, výrazy, kalibrace nebo libovolné transformace,
- více záložních nebo prioritních zdrojů pro jedno meteorologické pole,
- odvozené hodnoty,
- déšť, vítr, UV, sluneční záření a rosný bod,
- jiné výstupy než Weather Underground.

Architektura má v budoucnu umožnit přidání dalších polí a výstupních adaptérů,
MVP ale nesmí implementovat nepoužívané frameworky pro rozšíření.

---

## 3. Požadavky na běh a projekt

Použijte:

- Python 3.14,
- `uv` s projektovým prostředím `.venv`,
- `pyproject.toml` a commitovaný `uv.lock`,
- pytest,
- pyright,
- Ruff,
- pre-commit,
- Docker.

Zdrojový kód, identifikátory, komentáře, testy, dokumentace konfigurace, logovací
zprávy a chybové zprávy musí být v angličtině.

Trvalá databáze není potřeba.

---

## 4. Konfigurace

Aplikace musí při startu načíst jeden YAML konfigurační soubor. Jeho cesta musí
být předána jako `--config PATH`. Opětovné načtení konfigurace za běhu není
vyžadováno.

Neznámé klíče, nepodporované hodnoty, konfliktní zdroje a chybějící povinné
hodnoty musí způsobit ukončení startu s jasnou chybou. Chyba má určit příslušnou
cestu v konfiguraci a nesmí odhalit přihlašovací údaje.

### 4.1 Konfigurační model

```yaml
mqtt:
  host: mqtt.example.local
  port: 1883
  client_id: weather-underground-uploader
  keepalive: 60s
  tls: false

upload:
  interval: 60s
  timeout: 10s

sources:
  outdoor_temperature:
    topic: zigbee2mqtt/outdoor
    payload: json
    value: temperature
    unit: celsius
    max_age: 180s
    accept_retained: false
    target: temperature

  outdoor_humidity:
    topic: zigbee2mqtt/outdoor
    payload: json
    value: humidity
    unit: percent
    max_age: 180s
    accept_retained: false
    target: humidity

  pressure:
    topic: sensors/pressure
    payload: scalar
    unit: hpa
    max_age: 300s
    accept_retained: false
    target: pressure

outputs:
  weather_underground:
    enabled: true
```

Tato struktura je povinným konfiguračním modelem MVP. Přesné validační typy a
výchozí hodnoty musí být zdokumentovány v `config.example.yaml`.

### 4.2 Povinná pole

Povinné jsou `mqtt.host`, `mqtt.port`, `upload.interval` a alespoň jeden zdroj.

Každý zdroj vyžaduje:

- `topic`,
- `payload`,
- `unit`,
- `max_age`,
- `target`.

`value` je povinné pro JSON payload a zakázané pro skalární payload.

### 4.3 Výchozí hodnoty a formáty hodnot

Platí následující výchozí hodnoty:

- `mqtt.client_id`: `weather-underground-uploader`,
- `mqtt.keepalive`: `60s`,
- `mqtt.tls`: `false`,
- `upload.timeout`: `10s`,
- `accept_retained`: `false`,
- `outputs.weather_underground.enabled`: `true`.

Doby trvání musí být kladná celá čísla následovaná `s`, `m` nebo `h`.

MQTT TLS musí používat standardní ověření certifikátu a úložiště důvěryhodných
certifikátů operačního systému. Vypnutí ověřování certifikátu není podporováno.

### 4.4 Podporované cíle a jednotky

| Cíl | Podporované vstupní jednotky | Interní jednotka |
| --- | --- | --- |
| `temperature` | `celsius`, `fahrenheit` | °C |
| `humidity` | `percent` | % |
| `pressure` | `hpa`, `pa`, `inhg` | hPa |

Názvy cílů a jednotek rozlišují velikost písmen.

V MVP smí být pro každý cíl nakonfigurován pouze jeden zdroj. Konfigurace dvou
zdrojů se stejným cílem musí způsobit chybu při startu.

### 4.5 Přihlašovací údaje

Přihlašovací údaje nesmí být uvedeny v YAML konfiguraci.

Aplikace načítá:

```text
MQTT_USERNAME
MQTT_PASSWORD
WU_STATION_ID
WU_STATION_KEY
```

Přihlašovací údaje MQTT jsou nepovinné. Pokud je nastavena pouze jedna z
proměnných `MQTT_USERNAME` a `MQTT_PASSWORD`, start musí selhat.

Pokud je výstup Weather Underground povolen, jsou `WU_STATION_ID` a
`WU_STATION_KEY` povinné.

---

## 5. Vstupní kontrakt MQTT

Aplikace data z MQTT pouze přijímá a nikdy je do MQTT nepublikuje.

MVP používá MQTT 3.1.1 s čistou relací.

Aplikace musí:

- odebírat každé jedinečné nakonfigurované téma,
- zabránit duplicitnímu odběru, pokud více zdrojů používá stejné téma,
- požadovat QoS 1 pro odběry,
- zpracovávat zprávy nezávisle, aby jedna neplatná hodnota neovlivnila ostatní
  zdroje,
- po ztrátě spojení se automaticky znovu připojit, začít po 1 sekundě a
  zdvojnásobovat prodlevu nejvýše do 60 sekund,
- po opětovném připojení obnovit odběry.

MQTT témata se zástupnými znaky nejsou v MVP podporována.

### 5.1 Skalární payload

Skalární payload se dekóduje jako UTF-8, odstraní se okolní mezery a výsledek se
převede na konečné desetinné číslo.

```text
1007.4
```

Prázdné payloady, payloady, které nelze dekódovat jako UTF-8, nečíselné hodnoty,
`NaN` a nekonečné hodnoty jsou neplatné.

### 5.2 JSON payload

JSON payload musí být JSON objekt kódovaný v UTF-8. Vlastnost zdroje `value`
určuje jeden klíč objektu na nejvyšší úrovni.

```json
{
  "temperature": 18.7,
  "humidity": 63.2
}
```

Získaná hodnota musí být JSON číslo. Chybějící klíče, `null`, booleovské hodnoty,
řetězce, vnořené cesty, `NaN` a nekonečné hodnoty jsou neplatné.

### 5.3 Budoucí získávání hodnot pomocí šablon

Přímé získání hodnoty z nejvyšší úrovně JSON popsané výše je pro MVP záměrně
dostačující. Budoucí verze může přidat vzájemně se vylučující volbu
`value_template` používající sandboxovanou syntaxi Jinja, která má podobný účel
jako [`value_template`](https://www.home-assistant.io/integrations/sensor.mqtt/)
MQTT senzoru Home Assistantu.

Možná budoucí konfigurace, která není v MVP platná, je:

```yaml
value_template: "{{ value_json.environment.temperature }}"
```

Kontext šablony má být omezen na dekódovaný payload jako `value` a v případě
platného JSON také jako `value_json`. Nesmí zpřístupňovat stav Home Assistantu,
proměnné prostředí, soubory, síťový přístup ani libovolné Python objekty. Její
vykreslený výsledek musí běžný validační řetězec převést a ověřit jako jedno
konečné číslo.

Před implementací podpory šablon musí být specifikovány povolené filtry, funkce,
limity běhu, chování při chybách a bezpečnostní testy. MVP nesmí přidávat Jinja
jako závislost.

### 5.4 Retained zprávy

Retained zprávy musí být ignorovány, pokud odpovídající zdroj nemá
`accept_retained: true`.

MVP nezískává čas měření z payloadu. Přijatá retained zpráva se proto považuje za
aktualizovanou v okamžiku přijetí, nikoliv původního publikování. Toto omezení
musí být uvedeno v ukázkové konfiguraci.

---

## 6. Normalizovaný stav měření

Zpracování MQTT nesmí přímo volat adaptér Weather Underground. Každá platná MQTT
hodnota se nejprve převede do interní jednotky a uloží do cache měření.

Každé měření v cache obsahuje:

```text
target
value
unit
received_at
source
```

`received_at` vychází z monotónních hodin a používá se pouze pro výpočet stáří.
Systémový čas nesmí ovlivnit rozhodování o aktuálnosti.

Aktualizace cache a čtení plánovačem musí být bezpečné při souběžném provádění.
Cache je pouze v paměti a po každém restartu procesu začíná prázdná.

---

## 7. Validace a převod jednotek

Validace probíhá v tomto pořadí:

1. dekódování a parsování payloadu,
2. získání nakonfigurované hodnoty,
3. převod do interní jednotky,
4. validace normalizované hodnoty,
5. aktualizace cache.

Validační pravidla MVP jsou:

- každá hodnota musí být konečné číslo,
- teplota musí být včetně mezních hodnot mezi -100 a 100 °C,
- vlhkost musí být včetně mezních hodnot mezi 0 a 100 procenty,
- tlak musí být včetně mezních hodnot mezi 300 a 1200 hPa.

Neplatné hodnoty:

- nesmí aktualizovat hodnotu v cache,
- musí vytvořit varování obsahující identifikátor zdroje a důvod,
- nesmí ukončit službu ani ovlivnit ostatní zdroje.

Převod jednotek je součástí normalizační vrstvy. Převod do jednotek protokolu
Weather Underground patří pouze do jeho výstupního adaptéru.

---

## 8. Aktuálnost a sestavení pozorování

V každém nakonfigurovaném intervalu odesílání pořídí plánovač konzistentní snímek
cache.

Měření je zastaralé, pokud:

```text
current_time - received_at > max_age
```

Zastaralá měření jsou vyřazena a zaznamenána na úrovni warning. Ostatní aktuální
hodnoty mohou být odeslány.

Dílčí pozorování jsou platná. Chybějící nebo zastaralé hodnoty musí být vynechány
a nikdy nesmí být vymyšleny. Chybějící měření zejména nesmí být nahrazeno nulou.

Pokud snímek neobsahuje žádná aktuální platná měření, odeslání musí být
přeskočeno a důvod zaznamenán. Plánovač před prvním pokusem o odeslání počká po
startu na uplynutí celého intervalu.

MQTT zpráva nikdy nevyvolá okamžité odeslání.

---

## 9. Výstup Weather Underground

Weather Underground je jediným výstupem MVP.

Adaptér smí být zavolán pouze tehdy, když pozorování obsahuje alespoň jedno
aktuální platné měření podle kapitoly 8. Pokud takové měření neexistuje, nesmí být
proveden žádný HTTP požadavek na Weather Underground. Pokud je alespoň jedno
měření aktuální, odešle se a všechna chybějící, neplatná nebo zastaralá pole se
vynechají.

Adaptér musí implementovat oficiální PWS Upload Protocol:

https://support.weather.com/s/article/PWS-Upload-Protocol?language=en_US

Oficiální dokumentace protokolu je autoritativním zdrojem pro endpoint, povinné
parametry požadavku, jednotky protokolu a formát odpovědi.

MVP mapuje:

| Interní pole | Pole Weather Underground |
| --- | --- |
| temperature | venkovní teplota |
| humidity | venkovní relativní vlhkost |
| pressure | atmosférický tlak |

Adaptér musí:

- používat HTTPS,
- dodat Station ID a Station Key,
- identifikovat uploader pomocí parametru software type daného protokolem,
- použít aktuální čas odeslání podle požadavků protokolu,
- zahrnout pouze pole přítomná v pozorování,
- převést interní jednotky do jednotek protokolu,
- použít nakonfigurovaný HTTP timeout,
- považovat za úspěch pouze zdokumentovanou úspěšnou odpověď protokolu,
- odstranit přihlašovací údaje z URL, výjimek a logů.

Neúspěšná pozorování se trvale neukládají ani nezařazují do fronty. Dočasná chyba
se zaznamená a při dalším naplánovaném intervalu se odešle nejnovější aktuální
pozorování. Aplikace nesmí provádět agresivní smyčku okamžitých opakování.

Chyba autentizace nebo konfigurace musí být jasně zaznamenána bez odhalení
přihlašovacích údajů. Nesmí ukončit smyčku zpracování MQTT.

Přístup k read API Weather Underground ani jeho API key se v MVP nepoužívají.

---

## 10. Zpracování chyb a životní cyklus procesu

### Neplatná konfigurace

Proces musí skončit před připojením k MQTT nebo Weather Underground.

### MQTT není dostupné

Proces pokračuje v běhu a automaticky se znovu připojuje. Měření během odpojení
standardně zastarávají.

### Neplatný MQTT payload

Zaznamenejte varování, ignorujte dotčenou aktualizaci a pokračujte.

### Weather Underground není dostupný

Zaznamenejte chybu a počkejte do dalšího naplánovaného intervalu.

### Ukončení

Při `SIGINT` nebo `SIGTERM` přestaňte plánovat nová odeslání, odpojte se od MQTT,
dokončete nebo zrušte probíhající práci v rámci nakonfigurovaného HTTP timeoutu a
ukončete proces bez tracebacku.

---

## 11. Logování a ochrana přihlašovacích údajů

Logy musí být zapisovány na standardní výstup a přirozeně fungovat s:

```bash
docker compose logs -f
```

Logy musí používat konzistentní strukturovaná pole klíč-hodnota v textu čitelném
pro člověka.

```text
INFO event=mqtt_connected host=mqtt.example.local
INFO event=measurement_updated source=outdoor_temperature target=temperature value=18.4 unit=celsius
WARN event=measurement_stale source=pressure age_seconds=421 max_age_seconds=300
WARN event=invalid_measurement source=outdoor_humidity reason=out_of_range
INFO event=wu_upload_succeeded fields=temperature,humidity
ERROR event=wu_upload_failed reason=http_error status=500
```

Logy nikdy nesmí obsahovat:

- MQTT hesla,
- Weather Underground Station Keys,
- celé URL požadavků obsahující přihlašovací údaje,
- nezpracovaný obsah proměnných prostředí.

---

## 12. Nasazení v Dockeru

Repozitář musí poskytovat:

- `Dockerfile`,
- `compose.yaml`,
- `.env.example` obsahující pouze zástupné hodnoty,
- `config.example.yaml`,
- připojení konfiguračního souboru pouze pro čtení.

Kontejner musí běžet pod uživatelem bez oprávnění root a používat:

```yaml
restart: unless-stopped
```

Trvalý volume není potřeba.

---

## 13. Doporučené hranice modulů

Jednoduché úvodní rozdělení je:

```text
config
mqtt
measurements
normalization
models
scheduler
outputs/weather_underground
```

Jde o doporučení, nikoliv povinnou strukturu souborů. Upřednostňujte přímý a
testovatelný kód před zbytečnými abstrakcemi.

---

## 14. Minimální akceptační kritéria

MVP je dokončené, když:

- platné skalární a JSON MQTT zprávy vytvoří očekávané normalizované hodnoty v
  cache,
- neplatná a zastaralá měření ani retained zprávy, jejichž zpracování není
  povoleno, nejsou odeslány,
- naplánované neprázdné dílčí pozorování je namapováno a předáno adaptéru Weather
  Underground,
- služba se po odpojení od MQTT znovu připojí a korektně skončí při `SIGTERM`,
- automatické testy a kontroly Ruff projdou, Docker image se sestaví a
  konfigurace Docker Compose se úspěšně ověří.

Automatická testovací sada nesmí vyžadovat skutečné přihlašovací údaje Weather
Underground. Síťové interakce musí být nahraditelné testovacími doubles.
