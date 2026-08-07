# Weather Underground Uploader

[English](README.md) | [Čeština](README.cs.md)

Weather Underground Uploader je malá konfigurovatelná služba v Pythonu, která
sbírá meteorologická měření z MQTT a odesílá aktuální pozorování do osobní
meteorologické stanice Weather Underground (PWS).

> [!NOTE]
> Repozitář je aktuálně ve fázi inicializace projektu. Služba ještě není
> implementovaná ani spustitelná.

## Plánovaný tok dat

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

MVP bude:

- přijímat skalární a JSON měření z nakonfigurovaných MQTT témat,
- normalizovat teplotu, relativní vlhkost a atmosférický tlak,
- odmítat neplatné hodnoty a vyřazovat zastaralá měření,
- kombinovat aktuální hodnoty do dílčích pozorování,
- přeskakovat odeslání, pokud není k dispozici žádná aktuální hodnota,
- odesílat pozorování v konfigurovatelném intervalu,
- automaticky se znovu připojovat po ztrátě MQTT spojení,
- běžet lokálně nebo v Docker kontejneru bez oprávnění uživatele root.

Aplikace nebude záviset na API Home Assistantu, konkrétním MQTT publisheru ani
konkrétním výrobci senzorů.

## Dokumentace

Autoritativní specifikace projektu a MVP je v souboru
[docs/cs/PROJECT.md](docs/cs/PROJECT.md).

Pokyny pro přispívání a automatizaci repozitáře jsou v souboru
[AGENTS.md](AGENTS.md).

## Požadavky pro vývoj

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- Docker pro práci související s kontejnery

Verze Pythonu je připnutá v `.python-version`. Závislosti projektu a konfigurace
nástrojů jsou v `pyproject.toml`; přesné verze závislostí jsou uzamčené v
`uv.lock`.

## Příprava vývojového prostředí

Vytvoření nebo aktualizace projektového virtuálního prostředí:

```bash
uv sync
```

Spuštění dostupných kontrol kvality:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

Testovací sada zůstane prázdná do implementace prvních komponent aplikace. V
tomto stavu pytest skončí s kódem 5, protože nenačte žádné testy.

Po přidání konfigurace pre-commit spusťte všechny nakonfigurované hooky pomocí:

```bash
uv run pre-commit run --all-files
```

## Plánovaná konfigurace

Služba načte YAML konfigurační soubor předaný pomocí:

```bash
weather-underground-uploader --config config.yaml
```

MQTT témata, pole payloadu, jednotky, limity aktuálnosti a intervaly odesílání
specifické pro instalaci budou uložené v tomto souboru. Finální ukázková
konfigurace bude po implementaci jejího načítání dostupná jako
`config.example.yaml`.

Přihlašovací údaje se budou načítat pouze z proměnných prostředí:

```text
MQTT_USERNAME
MQTT_PASSWORD
WU_STATION_ID
WU_STATION_KEY
```

Skutečné přihlašovací údaje necommitujte ani je neuvádějte v ukázkách
konfigurace, logovacích záznamech, hlášeních problémů nebo testovacích datech.

## Hlavní soubory repozitáře

```text
.
├── docs/cs/PROJECT.md
├── docs/en/PROJECT.md
├── .python-version
├── AGENTS.md
├── LICENSE
├── README.cs.md
├── pyproject.toml
├── README.md
└── uv.lock
```

Zdrojový balíček, testy, ukázková konfigurace, Docker soubory a vstupní bod pro
spuštění budou přidány během implementace.

## Licence

Tento projekt je dostupný pod [licencí MIT](LICENSE).
