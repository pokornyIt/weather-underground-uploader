# Weather Underground Uploader

[English](README.md) | [Čeština](README.cs.md)

Weather Underground Uploader je malá konfigurovatelná služba v Pythonu, která
sbírá meteorologická měření z MQTT a odesílá aktuální pozorování do osobní
meteorologické stanice Weather Underground (PWS).

> [!NOTE]
> Základní běh služby je implementovaný včetně striktní konfigurace, MQTT
> příjmu, stavu normalizovaných měření, plánovaného odesílání a korektního
> ukončení. Kontejnerové balení a CI zůstávají plánovanou prací.

## Tok dat

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

Služba:

- přijímat skalární a JSON měření z nakonfigurovaných MQTT témat,
- normalizovat teplotu, relativní vlhkost a atmosférický tlak,
- odmítat neplatné hodnoty a vyřazovat zastaralá měření,
- kombinovat aktuální hodnoty do dílčích pozorování,
- přeskakovat odeslání, pokud není k dispozici žádná aktuální hodnota,
- odesílat pozorování v konfigurovatelném intervalu,
- automaticky se znovu připojovat po ztrátě MQTT spojení.

Aplikace nebude záviset na API Home Assistantu, konkrétním MQTT publisheru ani
konkrétním výrobci senzorů.

## Dokumentace

Autoritativní specifikace projektu a MVP je v souboru
[docs/cs/PROJECT.md](docs/cs/PROJECT.md).

Pro registraci stanice a získání Station ID a Station Key použijte
[návod k nastavení Weather Underground PWS](docs/cs/weather-underground-pws-setup-guide.md). K dispozici je také
lokální kopie oficiálního dokumentu [PWS Upload Protocol](docs/pws-upload-Protocol.pdf).

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

Testovací sada pokrývá konfiguraci, spuštění CLI, zpracování měření, MQTT příjem,
plánování, ukončení služby a odesílání do Weather Underground bez požadavku na
živé služby.

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

Scheduler před prvním odesláním čeká jeden celý nakonfigurovaný interval.
Signály `SIGINT` a `SIGTERM` zastaví nová odesílání, odpojí MQTT a ukončí službu
bez tracebacku.

Přihlašovací údaje se načítají pouze z proměnných prostředí:

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

Nasazení v Docker kontejneru bez oprávnění uživatele root a CI budou přidány v
rámci zbývajícího implementačního issue.

## Licence

Tento projekt je dostupný pod [licencí MIT](LICENSE).
