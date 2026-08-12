# Příklady pro Home Assistant

Tyto volitelné příklady načítají pozorování z Weather Underground do Home Assistantu poté, co tento uploader odešle
měření do Personal Weather Station (PWS).

Home Assistant se nepřipojuje přímo k této službě. Aktuální pozorování čte z Weather.com PWS API.

## Přihlašovací údaje a identifikátory

Weather Underground používá tři různé hodnoty:

| Hodnota     | Účel                             | Používají ji příklady |
| ----------- | -------------------------------- | --------------------- |
| Station ID  | Identifikuje PWS                 | Ano                   |
| Station Key | Autorizuje upload z této služby  | Ne                    |
| API Key     | Autorizuje čtení Weather.com API | Ano                   |

Station Key nikdy nevkládejte do REST požadavku Home Assistantu. API Key je samostatný údaj pro čtení, který lze
získat po registraci a aktivaci PWS podle
[návodu k nastavení Weather Underground PWS](weather-underground-pws-setup-guide.md).

Station ID není autentizační tajemství, ale může prozradit přibližnou polohu. Příklady proto načítají Station ID i
API Key ze souboru `secrets.yaml`.

## Požadavky

- Home Assistant s přístupem k YAML konfiguraci
- aktivní Weather Underground PWS
- Weather.com API Key
- [HACS](https://www.hacs.xyz/) pro instalaci závislostí dashboardu
- [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) nainstalované pomocí HACS

Package soubory používají pouze vestavěné integrace Home Assistantu. Mushroom Cards vyžadují pouze dashboardy.

## Dostupné příklady

### Jedna stanice

Základní příklad načítá teplotu, relativní vlhkost a atmosférický tlak z jedné PWS. Jde o doporučený výchozí příklad,
který odpovídá veličinám podporovaným uploaderem.

Soubory:

- [`single-station/package.yaml`](../../examples/home-assistant/single-station/package.yaml)
- [`single-station/dashboard.yaml`](../../examples/home-assistant/single-station/dashboard.yaml)

Package vytvoří tyto hlavní entity:

```text
sensor.weather_underground_station
sensor.wu_temperature
sensor.wu_humidity
sensor.wu_pressure
```

### Oblastní agregace

Oblastní příklad načítá pět blízkých PWS. Počítá medián teploty, vlhkosti, tlaku, rosného bodu, UV indexu, slunečního
záření, rychlosti větru, nárazů větru, celkových srážek a intenzity srážek. Pro směr větru používá místo mediánu
kruhový průměr. Běžná agregovaná hodnota vznikne pouze tehdy, když dané měření poskytují alespoň tři platné stanice.

Soubory:

- [`area/package.yaml`](../../examples/home-assistant/area/package.yaml)
- [`area/dashboard.yaml`](../../examples/home-assistant/area/dashboard.yaml)

Zdrojová stanice je platná, pokud:

- její REST senzor je dostupný;
- Weather Underground vrátí `qcStatus: 1`;
- pozorování není starší než jedna hodina;
- vybraná hodnota je číselná a nachází se v nastaveném rozumném rozsahu.

Medián omezuje vliv jedné odlišné stanice. Maximální intenzita srážek a detekce deště vyžadují pouze jednu platnou
stanici, aby lokální přeháňku neskryly stanice beze srážek. Denní, týdenní, měsíční a roční
[utility metery](https://www.home-assistant.io/integrations/utility_meter/) akumulují agregovaný celkový úhrn.

Jde o příklad využití okolních veřejných pozorování, nikoliv o součást runtime uploaderu. Úhrny představují oblastní
odhad: změna množiny platných zdrojových stanic může posunout medián, a tím ovlivnit hodnoty utility meterů.

## Instalace Mushroom Cards

Nejprve nainstalujte HACS, pokud jej ještě nemáte. V HACS:

1. otevřete `Frontend`;
2. vyhledejte `Mushroom`;
3. stáhněte Mushroom Cards;
4. pokud to HACS vyžádá, obnovte prohlížeč.

Oba dashboardy používají `custom:mushroom-template-card`. Dokud nejsou Mushroom Cards načtené, zobrazí se chyba
chybějící karty.

## Zapnutí Home Assistant packages

Pokud ještě packages nepoužíváte, přidejte jejich načítání do hlavního souboru `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

V konfiguračním adresáři Home Assistantu vytvořte adresář `packages`.

Do něj zkopírujte jeden ukázkový package pod popisným názvem s příponou `.yaml`, například:

```text
/config/packages/weather_underground_station.yaml
```

nebo:

```text
/config/packages/weather_underground_area.yaml
```

Adresářové include v Home Assistantu rozpozná soubory `.yaml`, ale ignoruje soubory `.yml`.

## Nastavení secrets

Jako předlohu použijte [`secrets.example.yaml`](../../examples/home-assistant/secrets.example.yaml). Do souboru
`/config/secrets.yaml` v Home Assistantu zkopírujte pouze položky potřebné pro vybraný příklad a nahraďte všechny
placeholdery.

Pro jednu stanici:

```yaml
weather_com_api_key: "YOUR_WEATHER_COM_API_KEY"
wu_station_id: "YOUR_STATION_ID"
```

Pro oblastní agregaci:

```yaml
weather_com_api_key: "YOUR_WEATHER_COM_API_KEY"
wu_area_station_1_id: "YOUR_FIRST_STATION_ID"
wu_area_station_2_id: "YOUR_SECOND_STATION_ID"
wu_area_station_3_id: "YOUR_THIRD_STATION_ID"
wu_area_station_4_id: "YOUR_FOURTH_STATION_ID"
wu_area_station_5_id: "YOUR_FIFTH_STATION_ID"
```

Soubor `secrets.yaml` nekopírujte zpět do tohoto repozitáře.

## Načtení package

Před restartem zkontrolujte konfiguraci Home Assistantu. Opravte všechny chybějící secrets nebo duplicitní
identifikátory entit, které kontrola ohlásí. Po úspěšné kontrole Home Assistant restartujte.

REST senzory se dotazují Weather.com každých 20 minut. Template entity odmítnou pozorování starší než jednu hodinu,
hodnoty, které neprošly kontrolou kvality Weather Underground, a hodnoty mimo nastavené rozsahy.

## Přidání dashboardu

Ukázky dashboardů obsahují kompletní raw konfiguraci s kořenovým klíčem `views`.

1. vytvořte nový dashboard nebo otevřete prázdný dashboard spravovaný v YAML;
2. otevřete editor raw konfigurace;
3. vložte obsah odpovídajícího souboru `dashboard.yaml`;
4. dashboard uložte.

Entity ID v dashboardu předpokládají, že Home Assistant nemusel kvůli existující entitě přidat číselnou příponu.
Pokud se entity ID liší, upravte podle něj odkazy v dashboardu.

## Změna oblastních stanic

Pro nahrazení stanice stačí změnit její hodnotu v `secrets.yaml`.

Pro přidání stanice:

1. zkopírujte v oblastním package jeden celý REST blok;
2. nastavte novému senzoru nový název a `unique_id`;
3. přidejte secret s jeho Station ID;
4. přidejte entity ID do `group.wu_area_stations`;
5. volitelně přidejte stanici do seznamu zdrojů v dashboardu.

Počítadlo platných a nakonfigurovaných stanic se odvozuje ze skupiny a neobsahuje pevný celkový počet. Běžné template
pro měření nyní vyžadují tři platné hodnoty. Maximální intenzita srážek a detekce deště jsou záměrné výjimky, které
reagují už na jednu platnou stanici.

## Využití API

Každá nakonfigurovaná zdrojová stanice provede jeden požadavek za 20 minut. Základní příklad proto provede 72
požadavků denně a oblastní příklad s pěti stanicemi 360 požadavků denně. Před zkrácením `scan_interval` nebo přidáním
většího počtu stanic zkontrolujte aktuální podmínky a limity API.
