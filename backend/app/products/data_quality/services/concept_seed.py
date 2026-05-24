"""Default dictionary seed (Phase 1 — completeness, validity, uniqueness).

These concepts are inserted on demand via POST /concepts/seed-defaults so a
new tenant gets a sensible starting dictionary on first use. The seed loader
is idempotent: ON CONFLICT DO NOTHING preserves any tenant edits to the
same (dimension, concept) key.

Editing the seed list here only affects *future* tenants and re-seeds for
tenants whose copies have been deleted. Existing tenant rows are not touched.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Shared regexes — anchored, conservative. Phase 2 may swap these for
# locale-specific variants (e.g. Saudi national ID, GCC phone).
# ---------------------------------------------------------------------------
_RE_EMAIL       = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
_RE_PHONE       = r"^\+?[0-9][0-9\s().\-]{6,19}$"
_RE_IBAN        = r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{1,30}$"
_RE_NATIONAL_ID = r"^[0-9]{9,15}$"
_RE_URL         = r"^https?://[\w.\-/:%?=&#]+$"
_RE_UUID        = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
_RE_ISO_DATE    = r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+\-]\d{2}:?\d{2})?)?$"
_RE_IPV4        = r"^([0-9]{1,3}\.){3}[0-9]{1,3}$"
_RE_POSTAL_CODE = r"^[A-Za-z0-9\s\-]{3,12}$"
_RE_CCY_ISO4217 = r"^[A-Z]{3}$"


# ---------------------------------------------------------------------------
# Validity (10) — does the value match a known shape?
# ---------------------------------------------------------------------------
VALIDITY: list[dict] = [
    {"concept": "email",
     "synonyms": ["email", "e_mail", "user_email", "contact_email", "email_addr", "email_address", "mail"],
     "rule_type": "format_regex", "parameter": {"pattern": _RE_EMAIL},
     "severity": "high", "applies_to_types": None,
     "notes": "Standard RFC-ish email shape."},

    {"concept": "phone",
     "synonyms": ["phone", "mobile", "tel", "telephone", "contact_number", "phone_number", "cell", "msisdn"],
     "rule_type": "format_regex", "parameter": {"pattern": _RE_PHONE},
     "severity": "medium", "applies_to_types": None,
     "notes": "Loose phone — digits with optional + and separators."},

    {"concept": "iban",
     "synonyms": ["iban", "bank_account", "account_iban"],
     "rule_type": "format_regex", "parameter": {"pattern": _RE_IBAN},
     "severity": "high", "applies_to_types": None,
     "notes": "ISO 13616 IBAN — country letters + check digits + alphanumerics."},

    {"concept": "national_id",
     "synonyms": ["national_id", "ssn", "citizen_id", "id_number", "government_id", "tax_id"],
     "rule_type": "format_regex", "parameter": {"pattern": _RE_NATIONAL_ID},
     "severity": "critical", "applies_to_types": None,
     "notes": "Generic 9–15 digit national identifier. Tighten per locale."},

    {"concept": "url",
     "synonyms": ["url", "website", "homepage", "link", "site"],
     "rule_type": "format_regex", "parameter": {"pattern": _RE_URL},
     "severity": "low", "applies_to_types": None,
     "notes": "http/https URL."},

    {"concept": "uuid",
     "synonyms": ["uuid", "guid"],
     "rule_type": "format_regex", "parameter": {"pattern": _RE_UUID},
     "severity": "medium", "applies_to_types": None,
     "notes": "UUID/GUID 8-4-4-4-12."},

    {"concept": "iso_date_string",
     "synonyms": ["date", "event_date", "transaction_date", "value_date"],
     "rule_type": "format_regex", "parameter": {"pattern": _RE_ISO_DATE},
     "severity": "medium", "applies_to_types": None,
     "notes": "Use only for columns stored as strings; native DATE/TIMESTAMP types are validated by the DB."},

    {"concept": "ipv4",
     "synonyms": ["ip", "ip_address", "ipv4", "client_ip", "remote_ip"],
     "rule_type": "format_regex", "parameter": {"pattern": _RE_IPV4},
     "severity": "low", "applies_to_types": None,
     "notes": "Dotted-quad IPv4."},

    {"concept": "postal_code",
     "synonyms": ["postal_code", "zip", "zip_code", "postcode"],
     "rule_type": "format_regex", "parameter": {"pattern": _RE_POSTAL_CODE},
     "severity": "low", "applies_to_types": None,
     "notes": "Loose postal-code shape; tighten per locale (e.g. Saudi 5-digit, US 5+4)."},

    {"concept": "currency_code",
     "synonyms": ["currency", "currency_code", "ccy", "iso_currency"],
     "rule_type": "format_regex", "parameter": {"pattern": _RE_CCY_ISO4217},
     "severity": "medium", "applies_to_types": None,
     "notes": "ISO 4217 — three uppercase letters."},
]


# ---------------------------------------------------------------------------
# Completeness (6) — should the column be filled?
# ---------------------------------------------------------------------------
COMPLETENESS: list[dict] = [
    {"concept": "primary_identifier_required",
     "synonyms": ["id", "uuid", "guid", "key", "primary_key", "pk"],
     "rule_type": "not_null", "parameter": {},
     "severity": "critical", "applies_to_types": None,
     "notes": "Primary identifier-shaped columns must be present on every row. Real PK columns are already enforced by the DB; this fires for *de-facto* identifier columns without a PK constraint."},

    {"concept": "creation_timestamp_required",
     "synonyms": ["created_at", "creation_date", "date_created", "inserted_at", "insert_ts", "created_on"],
     "rule_type": "not_null", "parameter": {},
     "severity": "high", "applies_to_types": None,
     "notes": "Every row should know when it was created."},

    {"concept": "email_required",
     "synonyms": ["email", "e_mail", "user_email", "contact_email", "email_addr", "email_address"],
     "rule_type": "max_null_rate", "parameter": {"threshold": 0.0},
     "severity": "high", "applies_to_types": ["master_data"],
     "notes": "Master-data records (customers, users) must carry an email."},

    {"concept": "foreign_key_required",
     "synonyms": ["customer_id", "account_id", "user_id", "owner_id", "parent_id", "tenant_id"],
     "rule_type": "max_null_rate", "parameter": {"threshold": 0.05},
     "severity": "medium", "applies_to_types": ["transaction", "event_log"],
     "notes": "Foreign-key-shaped columns on transactional/event tables shouldn't be missing for more than 5% of rows."},

    {"concept": "status_required",
     "synonyms": ["status", "state", "lifecycle_status", "stage"],
     "rule_type": "max_null_rate", "parameter": {"threshold": 0.01},
     "severity": "medium", "applies_to_types": None,
     "notes": "Lifecycle columns should be populated."},

    {"concept": "name_required",
     "synonyms": ["name", "full_name", "display_name", "title", "first_name", "last_name"],
     "rule_type": "max_null_rate", "parameter": {"threshold": 0.02},
     "severity": "medium", "applies_to_types": ["master_data"],
     "notes": "Identity columns on master-data records should rarely be missing."},
]


# ---------------------------------------------------------------------------
# Uniqueness (1) — should this column be unique?
#
# Migration 029 collapsed the previous three concepts (primary_identifier_
# unique / business_key_unique / natural_key_unique) into this single one.
# Reason: with entity_key_columns driving validator behaviour at the
# *table* level, the three concepts produced identical SQL — they were
# three knobs that all did the same thing.
#
# When the table's entity_key_columns is set, the validator groups by
# the entity key and checks per-entity uniqueness. When it's empty, the
# legacy "globally unique" SQL runs. Either way, the same concept fires.
# ---------------------------------------------------------------------------
UNIQUENESS: list[dict] = [
    {"concept": "column_must_be_unique",
     "synonyms": [
         # Surrogate / row-PK shapes
         "id", "uuid", "guid", "key", "primary_key", "pk",
         # Business identifiers
         "national_id", "national_no", "customer_id", "client_id",
         "customer_code", "account_number", "account_no", "external_id",
         "person_id", "subscriber_id",
         # Codes / SKUs
         "code", "sku", "isbn",
         # Natural keys
         "email", "username", "login", "handle",
     ],
     "rule_type": "unique", "parameter": {},
     "severity": "high", "applies_to_types": None,
     "notes": (
         "Column values must be unique. When the table has an entity key "
         "configured (Definition tab), uniqueness is checked across distinct "
         "entity keys — one client repeating the same mobile across many "
         "claims is fine; two clients sharing a mobile is a violation. When "
         "no entity key is set, the column must be globally unique."
     )},
]


def all_seed_concepts() -> list[tuple[str, dict]]:
    """Yield (dimension, concept_dict) tuples for the entire seed."""
    out: list[tuple[str, dict]] = []
    for c in VALIDITY:
        out.append(("validity", c))
    for c in COMPLETENESS:
        out.append(("completeness", c))
    for c in UNIQUENESS:
        out.append(("uniqueness", c))
    return out
