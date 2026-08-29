from __future__ import annotations

import calendar
import hashlib
import random
import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

FIRST_NAMES = [
    "Anna", "Julia", "Laura", "Sophie", "Marie", "Katharina", "Lea", "Lena",
    "Elena", "Natalia", "Maximilian", "Alexander", "Daniel", "Thomas",
    "Michael", "Johannes", "Lukas", "Felix", "David", "Martin", "Arthur",
]
LAST_NAMES = [
    "Schmidt", "Müller", "Schneider", "Fischer", "Weber", "Meyer", "Wagner",
    "Becker", "Hoffmann", "Schulz", "Koch", "Richter", "Klein", "Wolf",
    "Neumann", "Schwarz", "Zimmermann", "Braun", "Krüger", "Hartmann",
]

COMPANY_PREFIXES = [
    "Nord", "Süd", "West", "Ost", "Rhein", "Elbe", "Main", "Hanse",
    "Alpen", "Spree", "Neckar", "Donau", "Mosel", "Ruhr", "Taunus",
    "Kronen", "Linden", "Hafen", "Berg", "Tal", "Brücke", "Stern",
    "Nova", "Vertex", "Atlas", "Aurum", "Vektor", "Forum", "Union",
    "Kontor", "Metropol", "Europa", "Germania", "Pioneer", "Central",
]
COMPANY_CORES = [
    "Digital", "Industrie", "Werk", "Handel", "Logistik", "Technik",
    "Systeme", "Solutions", "Services", "Consulting", "Produktion",
    "Energie", "Immobilien", "Medien", "Gesundheit", "Bildung",
    "Automotive", "Maritim", "Bau", "Projekt", "Holding", "Partner",
    "Netzwerk", "Management", "Versorgung", "Innovation", "Engineering",
    "Commerce", "Manufacturing", "Development", "Operations", "Group",
]
COMPANY_QUALIFIERS = [
    "Berlin", "Hanse", "Mitte", "Süd", "Nord", "West", "Ost", "Rheinland",
    "Bavaria", "Saxonia", "Europa", "Deutschland", "Regional", "International",
    "Prime", "Pro", "Plus", "Direkt", "Kompetenz", "Zentrum",
]

LEGAL_NAME_SUFFIXES = {
    "EU": "",
    "EK": "e.K.",
    "GBR": "GbR",
    "OHG": "OHG",
    "KG": "KG",
    "GMBH": "GmbH",
    "UG": "UG (haftungsbeschränkt)",
    "GMBHCO": "GmbH & Co. KG",
    "AG": "AG",
    "KGaA": "KGaA",
    "SE": "SE",
    "EG": "eG",
    "EV": "e.V.",
    "STIFT": "Stiftung",
}


def money(value) -> str:
    return str(
        Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    )


def d(value: date | None) -> str:
    return value.isoformat() if value else ""


def dt(value: datetime | None) -> str:
    return value.isoformat(timespec="seconds") if value else ""


def month_starts(start: date, months: int) -> list[date]:
    result = []
    year, month = start.year, start.month
    for _ in range(months):
        result.append(date(year, month, 1))
        month += 1
        if month == 13:
            month = 1
            year += 1
    return result


def month_end(value: date) -> date:
    return date(
        value.year,
        value.month,
        calendar.monthrange(value.year, value.month)[1],
    )


def random_date(
    rng: random.Random,
    start: date,
    end: date,
) -> date:
    if end <= start:
        return start
    return start + timedelta(days=rng.randint(0, (end - start).days))


def random_datetime(
    rng: random.Random,
    day: date,
) -> datetime:
    return datetime(
        day.year,
        day.month,
        day.day,
        rng.randint(8, 18),
        rng.randint(0, 59),
        rng.randint(0, 59),
    )


def weighted_choice(
    rng: random.Random,
    weights: dict[str, float],
) -> str:
    keys = list(weights)
    return rng.choices(
        keys,
        weights=[weights[key] for key in keys],
        k=1,
    )[0]


def synthetic_vat_id(seed_text: str) -> str:
    number = (
        int(hashlib.sha256(seed_text.encode()).hexdigest()[:10], 16)
        % 1_000_000_000
    )
    return f"DE{number:09d}"


def synthetic_iban(seed_text: str) -> str:
    digest = hashlib.sha256(seed_text.encode()).hexdigest()
    bank = int(digest[:8], 16) % 100_000_000
    account = int(digest[8:20], 16) % 10_000_000_000
    return f"DE00{bank:08d}{account:010d}"


def person_name(rng: random.Random) -> tuple[str, str]:
    return rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)


def legal_name_suffix(legal_form_code: str) -> str:
    return LEGAL_NAME_SUFFIXES[legal_form_code]


def company_name(
    rng: random.Random,
    legal_form_code: str,
    distinguishing_token: str | None = None,
) -> str:
    parts = [
        rng.choice(COMPANY_PREFIXES),
        rng.choice(COMPANY_CORES),
    ]
    if rng.random() < 0.58:
        parts.append(rng.choice(COMPANY_QUALIFIERS))
    if distinguishing_token:
        parts.append(distinguishing_token)
    suffix = legal_name_suffix(legal_form_code)
    if suffix:
        parts.append(suffix)
    return " ".join(parts)


def ascii_email_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    token = re.sub(r"[^a-zA-Z0-9]+", ".", ascii_text).strip(".").lower()
    return token or "user"


class IdFactory:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def next(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}{self.counters[prefix]:09d}"
