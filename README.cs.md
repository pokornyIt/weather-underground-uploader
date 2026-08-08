# Weather Underground Uploader

[English](README.md) | [Čeština](README.cs.md)

Weather Underground Uploader je malá konfigurovatelná služba v Pythonu, která
sbírá meteorologická měření z MQTT a odesílá aktuální pozorování do osobní
meteorologické stanice Weather Underground (PWS).

> [!NOTE]
> Běh MVP, kontejnerové balení bez oprávnění uživatele root a CI validace jsou
> implementované.

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

Služba umí:

- přijímat skalární a JSON měření z nakonfigurovaných MQTT témat,
- normalizovat teplotu, relativní vlhkost a atmosférický tlak,
- odmítat neplatné hodnoty a vyřazovat zastaralá měření,
- kombinovat aktuální hodnoty do dílčích pozorování,
- přeskakovat odeslání, pokud není k dispozici žádná aktuální hodnota,
- odesílat pozorování v konfigurovatelném intervalu,
- automaticky se znovu připojovat po ztrátě MQTT spojení.

Aplikace nezávisí na API Home Assistantu, konkrétním MQTT publisheru ani
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

Vytvořte lokální konfiguraci a soubor s přihlašovacími údaji z commitnutých
ukázek:

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

Oba soubory upravte pro cílovou instalaci a výslednou konfiguraci předejte CLI:

```bash
uv run --env-file .env weather-underground-uploader --config config.yaml
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

## Nasazení v Dockeru

Vytvořte lokální konfiguraci a soubor s přihlašovacími údaji z commitnutých
ukázek:

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

Oba soubory upravte pro cílovou instalaci. Skutečné přihlašovací údaje
uchovávejte pouze v `.env`; oba lokální soubory Git ignoruje.

Sestavte a spusťte službu:

```bash
docker compose up --build --detach
```

Sledujte strukturované logy služby nebo nasazení zastavte:

```bash
docker compose logs --follow
docker compose down
```

Kontejner běží jako neprivilegovaný uživatel s kořenovým souborovým systémem
pouze pro čtení. Compose připojuje `config.yaml` pouze pro čtení a restartuje
službu, pokud nebyla explicitně zastavena.

Změny kontejneru lokálně ověřte pomocí:

```bash
docker build .
docker compose config
```

## Hlavní soubory repozitáře

```text
.
├── .github/workflows/ci.yaml
├── .github/ISSUE_TEMPLATE/
├── .dockerignore
├── .env.example
├── compose.yaml
├── config.example.yaml
├── docs/cs/PROJECT.md
├── docs/en/PROJECT.md
├── src/wu_uploader/
├── tests/
├── .python-version
├── AGENTS.md
├── CONTRIBUTING.md
├── Dockerfile
├── LICENSE
├── README.cs.md
├── pyproject.toml
├── README.md
└── uv.lock
```

## Licence

Tento projekt je dostupný pod [licencí MIT](LICENSE).
