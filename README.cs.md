# Weather Underground Uploader

[English](README.md) | [Čeština](README.cs.md)

Weather Underground Uploader je malá konfigurovatelná služba v Pythonu, která
sbírá meteorologická měření z MQTT a odesílá aktuální pozorování do osobní
meteorologické stanice Weather Underground (PWS).

> [!NOTE]
> Striktní načítání konfigurace a vstupní bod CLI jsou implementované. MQTT
> příjem a odesílání do Weather Underground zatím implementované nejsou.

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

Pokyny pro přispívání jsou v souboru
[CONTRIBUTING.md](CONTRIBUTING.md).
Pokyny pro automatizaci repozitáře jsou v souboru [AGENTS.md](AGENTS.md).

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

Testovací sada pokrývá implementované chování konfigurace a CLI.

Všechny nakonfigurované pre-commit hooky spusťte pomocí:

```bash
uv run pre-commit run --all-files
```

Manuální pytest hook spusťte pomocí:

```bash
uv run pre-commit run pytest --hook-stage manual --all-files
```

## Konfigurace

Zkopírujte `config.example.yaml`, upravte hodnoty specifické pro instalaci a
výsledný soubor předejte CLI:

```bash
uv run weather-underground-uploader --config config.yaml
```

CLI před spuštěním striktně ověří celou konfiguraci. Neznámé klíče,
nepodporované kombinace, duplicitní cíle a chybějící povinné hodnoty způsobí
srozumitelnou chybu.

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
├── .github/ISSUE_TEMPLATE/
├── config.example.yaml
├── docs/cs/PROJECT.md
├── docs/en/PROJECT.md
├── src/wu_uploader/
├── tests/
├── .python-version
├── AGENTS.md
├── CONTRIBUTING.md
├── LICENSE
├── README.cs.md
├── pyproject.toml
├── README.md
└── uv.lock
```

MQTT příjem, odesílání do Weather Underground, plánování a Docker nasazení budou
přidány v rámci zbývajících implementačních issue.

## Licence

Tento projekt je dostupný pod [licencí MIT](LICENSE).
