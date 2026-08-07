# Weather Underground PWS – registrace vlastní stanice a získání API Key

Praktický návod pro uživatele, který chce poprvé založit vlastní Personal Weather Station (PWS), začít do
Weather Underground odesílat vlastní data a následně získat vlastní API Key. Postup byl prakticky ověřen v srpnu
2026.

> [!NOTE]
> Tento projekt potřebuje pouze Station ID a Station Key. API Key slouží ke čtení Weather API a pro provoz
> uploaderu není potřeba; příslušné části návodu jsou volitelné.

## 1. Co je cílem

Výsledkem tohoto postupu budou tři různé údaje:

```text
Station ID
Station Key
API Key
```

Je důležité je nezaměňovat.

- **Station ID** – identifikátor konkrétní PWS; používá se při uploadu i při čtení dat konkrétní stanice.
- **Station Key** – tajný klíč stanice pro upload. V PWS Upload Protocolu se posílá jako `PASSWORD`.
- **API Key** – samostatný klíč pro čtení Weather Underground / The Weather Company API.

## 2. Co potřebujete

Pro založení a aktivaci PWS není nutné mít komerční meteostanici. Weather Underground umožňuje při registraci
použít hardware typu `Other`. Prakticky bylo ověřeno, že stanici lze aktivovat i uploadem pouze části veličin,
například teploty a relativní vlhkosti.

Chybějící veličiny jako vítr, déšť, tlak nebo UV se jednoduše neposílají. **Nenahrazujte je umělou nulou.**

## 3. Vytvoření / přihlášení účtu

Otevřete Weather Underground:

[Weather Underground](https://www.wunderground.com/)

Přihlaste se nebo si vytvořte účet.

PWS síť je dostupná zde:

[Weather Underground PWS Network](https://www.wunderground.com/pws/overview)

Na stránce použijte `Register`, případně po přihlášení přejděte přes:

```text
My Profile
  └── My Devices
```

## 4. Registrace nové PWS

Nejprve vyberte skutečné umístění stanice na mapě.

Pro vlastní DIY/MQTT řešení doporučuji:

```text
Device Hardware: Other
```

### Name

Zvolte libovolný popisný název, například:

```text
Home Weather Station
```

nebo:

```text
MQTT Weather Station
```

### Elevation

Zadejte nadmořskou výšku místa stanice.

### Surface Type

Pokud žádná možnost rozumně neodpovídá skutečnému umístění, pole lze nechat prázdné, pokud není označeno jako
povinné.

### Height Above Ground

Také jde o volitelný údaj. U stanice sestavené z více fyzických senzorů v různých výškách nemusí existovat jedna
správná hodnota.

Pokud jej vyplňujete, WU používá stopy:

```text
2 m  ≈ 6.6 ft
10 m ≈ 32.8 ft
```

## 5. Po dokončení registrace

Weather Underground vytvoří zařízení a přidělí:

```text
Station ID
Station Key
```

Oba údaje bezpečně uložte, například pro budoucí aplikaci:

```env
WU_STATION_ID=...
WU_STATION_KEY=...
```

Credentials neukládejte do Git repozitáře.

Po registraci bude stanice typicky `Offline`. To je normální – aktivuje se až po prvním úspěšném uploadu.

## 6. PWS Upload Protocol

Kopie oficiální dokumentace je uložena v souboru
[PWS Upload Protocol](../pws-upload-Protocol.pdf). Aktuální online verze je dostupná na webu
[Weather.com](https://support.weather.com/s/article/PWS-Upload-Protocol?language=en_US).

Upload probíhá HTTP GET requestem na:

```text
https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php
```

Základní parametry:

```text
ID       = Station ID
PASSWORD = Station Key
dateutc  = čas měření
action   = updateraw
```

Pro jednoduchý test použijte:

```text
dateutc=now
```

## 7. Jednotky uploadu

Upload protokol používá převážně imperiální jednotky.

| Parametr         | Význam              | Jednotka |
| ---------------- | ------------------- | -------- |
| `tempf`          | teplota             | °F       |
| `humidity`       | relativní vlhkost   | %        |
| `baromin`        | tlak                | inHg     |
| `windspeedmph`   | rychlost větru      | mph      |
| `windgustmph`    | náraz větru         | mph      |
| `winddir`        | směr větru          | °        |
| `rainin`         | srážky              | inch     |
| `dailyrainin`    | denní srážky        | inch     |
| `solarradiation` | solární radiace     | W/m²     |
| `UV`             | UV index            | index    |

Například:

```text
20 °C = 68 °F
```

## 8. Nejjednodušší test uploadu

Pro první test stačí například teplota a vlhkost:

```text
ID=<Station ID>
PASSWORD=<Station Key>
dateutc=now
tempf=68.0
humidity=50
action=updateraw
```

## 9. Test pomocí Postman

Nastavte:

```text
Method: GET
URL: https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php
```

V Postman Environment vytvořte:

```text
WU_STATION_ID
WU_STATION_KEY
```

Query Params:

| Key        | Value                |
| ---------- | -------------------- |
| `ID`       | `{{WU_STATION_ID}}`  |
| `PASSWORD` | `{{WU_STATION_KEY}}` |
| `dateutc`  | `now`                |
| `tempf`    | `68.0`               |
| `humidity` | `50`                 |
| `action`   | `updateraw`          |

Při úspěchu vrátí Weather Underground:

```text
success
```

Tím je ověřeno, že Station ID, Station Key i upload endpoint fungují.

## 10. Test pomocí curl

```bash
export WU_STATION_ID='YOUR_STATION_ID'
read -s WU_STATION_KEY
export WU_STATION_KEY

curl -G \
  'https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php' \
  --data-urlencode "ID=${WU_STATION_ID}" \
  --data-urlencode "PASSWORD=${WU_STATION_KEY}" \
  --data-urlencode 'dateutc=now' \
  --data-urlencode 'tempf=68.0' \
  --data-urlencode 'humidity=50' \
  --data-urlencode 'action=updateraw'
```

Očekávaná odpověď:

```text
success
```

## 11. Co se stane po prvním uploadu

Po úspěšném uploadu se stanice přepne z:

```text
Offline
```

na:

```text
Online
```

Webové rozhraní může mít krátkou prodlevu.

Pokud jste odeslali pouze teplotu a vlhkost, ostatní veličiny mohou zůstat jako `--`. To je správně.

## 12. Získání API key

Samotná registrace PWS ještě nemusí zpřístupnit API key. Prakticky ověřený postup je:

```text
zaregistrovat PWS
        ↓
získat Station ID + Station Key
        ↓
odeslat validní observation
        ↓
stanice se stane Online
        ↓
sekce API Keys umožní vytvořit API Key
```

V účtu otevřete sekci:

```text
API Keys
```

Aktuální UI WU váže dostupnost PWS API na aktivní stanici a nedávné uploady. Pokud stanice dlouhodobě neposílá
data, přístup nemusí být považován za aktivní. V rozhraní je uváděna hranice 30 dnů od posledního uploadu.

Po vytvoření API key jej bezpečně uložte:

```env
WU_API_KEY=...
```

## 13. Ověření API key

Oficiální dokumentace je dostupná na stránce
[PWS Current Conditions API](https://developer.weather.com/docs/openapi/pws-observations-current-conditions-2-0).

Endpoint:

```text
https://api.weather.com/v2/pws/observations/current
```

Pro metrické jednotky použijte:

```text
units=m
```

### curl test

```bash
export WU_STATION_ID='YOUR_STATION_ID'
read -s WU_API_KEY
export WU_API_KEY

curl -G \
  'https://api.weather.com/v2/pws/observations/current' \
  --data-urlencode "stationId=${WU_STATION_ID}" \
  --data-urlencode 'format=json' \
  --data-urlencode 'units=m' \
  --data-urlencode 'numericPrecision=decimal' \
  --data-urlencode "apiKey=${WU_API_KEY}"
```

Při správném API key a aktivní stanici vrátí API JSON s aktuální observation.

## 14. Dvě různá rozhraní

```text
                        Weather Underground
                               │
           ┌───────────────────┴───────────────────┐
           │                                       │
           │ upload                                │ read
           ▼                                       ▼
 PWS Upload Protocol                       Weather API
           │                                       │
 Station ID + Station Key                  Station ID + API Key
```

### Upload

Používá:

```text
Station ID
Station Key
```

### Čtení API

Používá:

```text
Station ID
API Key
```

## 15. Nejčastější chyby

### Stanice zůstává Offline

Ověřte:

- správné Station ID,
- správný Station Key,
- `action=updateraw`,
- `dateutc=now` nebo validní UTC timestamp,
- odpověď upload endpointu.

Pokud endpoint vrátí `success`, upload byl přijat.

### Zaměněný Station Key a API Key

Upload:

```text
PASSWORD = Station Key
```

Čtení API:

```text
apiKey = API Key
```

### Posílání °C do `tempf`

`tempf` očekává Fahrenheit.

### Posílání hPa do `baromin`

`baromin` očekává inHg.

### Chybějící senzor se posílá jako nula

To je špatně. Pokud například nemáte anemometr, parametr `windspeedmph` vůbec neposílejte. `windspeedmph=0`
znamená skutečně naměřené bezvětří.

## 16. Doporučený minimální provoz

Pro udržování aktivní PWS není nutná kompletní komerční stanice. Lze pravidelně odesílat například:

```text
temperature
humidity
pressure
```

z vlastních MQTT senzorů.

Typická architektura:

```text
ESPHome ──────────┐
Zigbee2MQTT ──────┤
Z-Wave2MQTT ──────┤
MQTT device ──────┘
        │
        ▼
   MQTT broker
        │
        ▼
  PWS uploader
        │
        ▼
Weather Underground
```

Jedna WU observation může být sestavena z více fyzických senzorů.

## 17. Doporučení pro produkční uploader

- credentials ukládat mimo Git,
- používat pouze reálné naměřené hodnoty,
- chybějící nebo staré hodnoty neposílat,
- kontrolovat stáří MQTT dat,
- převody jednotek dělat až před WU uploadem,
- logovat odpověď WU,
- při dočasném výpadku WU nepoužívat agresivní retry loop.

Rozumný hobby upload interval může být například 60 sekund.

## 18. Užitečné odkazy

- [PWS Network](https://www.wunderground.com/pws/overview)
- [Buying Guide](https://www.wunderground.com/pws/buying-guide)
- [Installation Guide](https://www.wunderground.com/pws/installation-guide)
- [PWS Upload Protocol](https://support.weather.com/s/article/PWS-Upload-Protocol?language=en_US)
- [PWS Current Conditions API](https://developer.weather.com/docs/openapi/pws-observations-current-conditions-2-0)
- [PWS Historical API](https://developer.weather.com/docs/openapi/pws-historical-2-0/get-pws-history-all)

## 19. Rychlý checklist

```text
[ ] vytvořen / přihlášen Weather Underground účet
[ ] otevřena registrace PWS
[ ] vybrána poloha stanice
[ ] Device Hardware = Other (pro vlastní řešení)
[ ] PWS zaregistrována
[ ] bezpečně uložen Station ID
[ ] bezpečně uložen Station Key
[ ] proveden test uploadu
[ ] odpověď upload endpointu = success
[ ] PWS je Online
[ ] otevřena sekce API Keys
[ ] vytvořen a bezpečně uložen API Key
[ ] proveden test read API
[ ] API vrací JSON s daty stanice
```

Pokud všechny body projdou, máte funkční vlastní Weather Underground PWS i přístup k Weather Underground API.
