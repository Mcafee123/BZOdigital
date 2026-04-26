from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.parse import quote


DEFAULT_LAWS_PATH = Path(__file__).with_name("laws_combined.json")
MAX_TRAILING_LAW_TOKENS = 4
FEDERAL_LANGUAGE_PREFERENCE = ("fr", "de", "it", "en")


LawEntry = Dict[str, Any]
Citation = Dict[str, Any]


CITATION_MARKER_PATTERN = (
    r"§+|Art|art|Artikel|article|Article|articolo|Articolo|Paragraph|Par|par"
)
PROVISION_PATTERN = r"\d+(?:[a-zA-Z]\b)?"
CITATION_RANGE_PATTERN = rf"(?:\s*(?:-|–|—|bis|à|a)\s*{PROVISION_PATTERN})?"
CITATION_DETAIL_PATTERN = (
    CITATION_RANGE_PATTERN
    + rf"(?:\s*(?:Abs|Absatz|Al|al|Cpv|cpv)\.?\s*{PROVISION_PATTERN})?"
    + rf"(?:\s*(?:Ziff|Ziffer|Ch|ch|N|n)\.?\s*{PROVISION_PATTERN})?"
    + r"(?:\s*(?:Lit|lit|Buchstabe|Bchst|Let|let|Lett|lett)\.?\s*[A-Za-z])?"
    + r"(?:\s*f{1,2}\.)?"
)
COMBINATION_CONNECTOR_PATTERN = (
    r"(?:,|;|/|&|\b(?:und|sowie|oder|beziehungsweise|respektive|wie\s+auch|et|ou|"
    r"ainsi\s+que|de\s+même\s+que|soit|voire|e|ed|o|od|oppure|nonché|nonche|"
    r"rispettivamente|ossia|ovvero)\b|\b(?:bzw|resp)\.|\bi\.?\s*V\.?\s*m\.?)"
)
COMBINATION_SEPARATOR_PATTERN = rf"\s*{COMBINATION_CONNECTOR_PATTERN}\s*"


REGEX_CITATION_START = re.compile(
    rf"(?<![\w])(?P<citation>(?P<marker>{CITATION_MARKER_PATTERN})\.?\s*"
    rf"(?P<provision>{PROVISION_PATTERN}){CITATION_DETAIL_PATTERN})",
    re.UNICODE,
)
REGEX_CONNECTED_CITATION_CHUNK = re.compile(
    rf"(?P<separator>{COMBINATION_SEPARATOR_PATTERN})"
    rf"(?P<citation>(?:(?P<marker>{CITATION_MARKER_PATTERN})\.?\s*)?"
    rf"(?P<provision>{PROVISION_PATTERN}){CITATION_DETAIL_PATTERN})",
    re.IGNORECASE | re.UNICODE,
)
REGEX_TRAILING_BLOCKED_UNIT = re.compile(
    r"^\s*(?:%|prozent|percent|pourcent|per\s+cento|promille|franken|chf|euro|eur|"
    r"jahre|jahr|monate|monat|tage|tag|stunden|stunde|personen|person|einwohner|"
    r"einwohnerinnen|habitants|persone)\b",
    re.IGNORECASE | re.UNICODE,
)
REGEX_BGE = re.compile(
    r"(?:(?:(BGE|ATF|DTF)\.?\s*)?(\d+(?:\w\b)?)\s*M{0,4}"
    r"(IV|V|I{1,3}[ab]?)+\s*(\d+(?:\w\b)?))",
    re.IGNORECASE | re.UNICODE,
)
REGEX_BGER = re.compile(r"(\d+)([A-Z])_(\d+/\d+)")


def load_combined_laws(path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Load the combined Zurich/federal law JSON."""
    law_path = Path(path) if path is not None else DEFAULT_LAWS_PATH
    with law_path.open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=4)
def load_official_laws_by_abbreviation(path: str = str(DEFAULT_LAWS_PATH)) -> Dict[str, LawEntry]:
    """Load and index law abbreviations from a JSON file path."""
    return build_official_laws_by_abbreviation(load_combined_laws(path))


def build_official_laws_by_abbreviation(law_data: Mapping[str, Any]) -> Dict[str, LawEntry]:
    laws_by_abbreviation: Dict[str, LawEntry] = {}

    add_zurich_laws(laws_by_abbreviation, law_data.get("zh") or [])
    add_federal_laws(laws_by_abbreviation, law_data.get("ch") or [])

    return laws_by_abbreviation


def add_zurich_laws(
    laws_by_abbreviation: Dict[str, LawEntry],
    laws: Iterable[Mapping[str, Any]],
) -> None:
    for law in laws:
        abbreviation = normalize_law_abbreviation(law.get("law_title_abbreviation"))

        if not abbreviation or not law.get("in_force") or not law.get("dynamic_prod_url"):
            continue

        laws_by_abbreviation[abbreviation] = {
            "abbreviation": abbreviation,
            "dynamic_prod_url": law.get("dynamic_prod_url"),
            "dynamic_source_url": law.get("dynamic_source_url"),
            "language": None,
            "law": dict(law),
            "scope": "zh",
        }


def add_federal_laws(
    laws_by_abbreviation: Dict[str, LawEntry],
    laws: Iterable[Mapping[str, Any]],
) -> None:
    for law in laws:
        if (
            not law.get("in_force")
            or not law.get("law_title_abbreviation")
            or not law.get("dynamic_prod_url")
        ):
            continue

        for law_entry in get_federal_law_entries(law):
            for abbreviation in get_law_abbreviation_aliases(law_entry["abbreviation"]):
                laws_by_abbreviation.setdefault(abbreviation, law_entry)


def get_federal_law_entries(law: Mapping[str, Any]) -> List[LawEntry]:
    entries_by_abbreviation: Dict[str, LawEntry] = {}
    abbreviations = law.get("law_title_abbreviation") or {}
    prod_urls = law.get("dynamic_prod_url") or {}
    source_urls = law.get("dynamic_source_url") or {}

    for language in FEDERAL_LANGUAGE_PREFERENCE:
        abbreviation = normalize_law_abbreviation(abbreviations.get(language))
        dynamic_prod_url = prod_urls.get(language)
        dynamic_source_url = source_urls.get(language)

        if not abbreviation or not dynamic_prod_url or not dynamic_source_url:
            continue

        entries_by_abbreviation.setdefault(
            abbreviation,
            {
                "abbreviation": abbreviation,
                "dynamic_prod_url": dynamic_prod_url,
                "dynamic_source_url": dynamic_source_url,
                "language": language,
                "law": dict(law),
                "scope": "ch",
            },
        )

    return list(entries_by_abbreviation.values())


def get_law_abbreviation_aliases(abbreviation: str) -> List[str]:
    aliases = [abbreviation]
    without_trailing_dots = re.sub(r"\.+$", "", abbreviation)

    if without_trailing_dots and without_trailing_dots != abbreviation:
        aliases.append(without_trailing_dots)

    return aliases


def add_custom_laws(
    laws_by_abbreviation: Dict[str, LawEntry],
    custom_laws: Optional[Any],
) -> None:
    """Add call-time laws, overriding built-in abbreviations when they collide."""
    for custom_law in iter_custom_laws(custom_laws):
        law_entry = build_custom_law_entry(custom_law)

        if not law_entry:
            continue

        for abbreviation in get_law_abbreviation_aliases(law_entry["abbreviation"]):
            laws_by_abbreviation[abbreviation] = law_entry


def iter_custom_laws(custom_laws: Optional[Any]) -> Iterable[Mapping[str, Any]]:
    if custom_laws is None:
        return []

    if isinstance(custom_laws, Mapping):
        nested_laws = custom_laws.get("custom-laws", custom_laws.get("custom_laws"))

        if nested_laws is not None:
            return iter_custom_laws(nested_laws)

        return [custom_laws]

    return [custom_law for custom_law in custom_laws if isinstance(custom_law, Mapping)]


def build_custom_law_entry(custom_law: Mapping[str, Any]) -> Optional[LawEntry]:
    abbreviation = normalize_law_abbreviation(
        custom_law.get("abbreviation", custom_law.get("abbrevation"))
    )
    link_template = str(
        custom_law.get("link_template", custom_law.get("url_template", custom_law.get("link", "")))
        or ""
    ).strip()

    if not abbreviation or not link_template:
        return None

    law = {
        "custom": True,
        "law_title_abbreviation": abbreviation,
        "law_title_full": custom_law.get("title", custom_law.get("name", abbreviation)),
        "law_title_short": custom_law.get("short_title", ""),
        "refno_law": custom_law.get("refno", custom_law.get("refno_law")),
    }

    return {
        "abbreviation": abbreviation,
        "dynamic_prod_url": custom_law.get("base_url"),
        "dynamic_source_url": custom_law.get("source_url"),
        "language": custom_law.get("language"),
        "law": law,
        "link_template": link_template,
        "scope": "custom",
    }

def set_ancors(markdown: str) -> str:
    # If the markdown contains a heading with a law reference without abbreviation, we add an anchor to the heading to make sure the link works
    def add_anchor(match: re.Match[str]) -> str:
        heading = match.group(1)
        reference = match.group(2)
        anchor = re.sub(r"\s+", "-", reference.strip()).lower()
        return f"{heading} <a name=\"{anchor}\"></a>{reference}"

def enrich_markdown(
    text: str,
    default_law: Optional[str | LawEntry] = None,
    custom_laws: Optional[Any] = None,
    laws_by_abbreviation: Optional[Mapping[str, LawEntry]] = None,
    laws_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Return enriched Markdown plus rule-based citation metadata.

    Custom laws can be supplied as a list or as {"custom-laws": [...]}.
    Each entry needs an "abbrevation" or "abbreviation" and a templated
    "link", "link_template", or "url_template" value.
    """
    laws = get_laws_by_abbreviation(laws_by_abbreviation, laws_path, custom_laws)
    default_law_entry = resolve_default_law(default_law, laws)
    law_result = enrich_law_references(text, default_law_entry, laws)
    court_citations = collect_court_citations(text)
    markdown = law_result["markdown"]
    markdown = set_ancors(markdown)

    markdown = REGEX_BGER.sub(
        lambda match: build_markdown_link(match.group(0), build_bger_url(match.group(0))),
        markdown,
    )
    markdown = REGEX_BGE.sub(
        lambda match: build_markdown_link(
            match.group(0),
            build_bge_url(
                {
                    "division": match.group(3),
                    "language": get_bge_reporter_language(match.group(1)),
                    "page": match.group(4),
                    "volume": match.group(2),
                }
            ),
        ),
        markdown,
    )

    citations = sorted(
        [*law_result["citations"], *court_citations],
        key=lambda citation: (citation["start_index"], citation["end_index"]),
    )

    return {
        "citations": citations,
        "markdown": markdown,
    }


def get_laws_by_abbreviation(
    laws_by_abbreviation: Optional[Mapping[str, LawEntry]],
    laws_path: Optional[Path | str],
    custom_laws: Optional[Any] = None,
) -> Mapping[str, LawEntry]:
    if laws_by_abbreviation is not None:
        laws = dict(laws_by_abbreviation)
    else:
        path = str(Path(laws_path)) if laws_path is not None else str(DEFAULT_LAWS_PATH)
        laws = dict(load_official_laws_by_abbreviation(path))

    add_custom_laws(laws, custom_laws)
    return laws


def resolve_default_law(
    default_law: Optional[str | LawEntry],
    laws_by_abbreviation: Mapping[str, LawEntry],
) -> Optional[LawEntry]:
    if default_law is None or isinstance(default_law, dict):
        return default_law

    return laws_by_abbreviation.get(normalize_law_abbreviation(default_law))


def enrich_law_references(
    text: str,
    default_law: Optional[LawEntry],
    laws_by_abbreviation: Mapping[str, LawEntry],
) -> Dict[str, Any]:
    citations: List[Citation] = []
    markdown_parts: List[str] = []
    cursor = 0

    for match in REGEX_CITATION_START.finditer(text):
        if match.start() < cursor:
            continue

        reference = parse_law_reference(text, match, default_law, laws_by_abbreviation)

        if not reference:
            continue

        markdown_parts.append(text[cursor : match.start()])
        markdown_parts.append(render_law_reference(reference, text))
        citations.extend(build_law_citation_records(reference, text))
        cursor = reference["end_index"]

    markdown_parts.append(text[cursor:])

    return {
        "citations": citations,
        "markdown": "".join(markdown_parts),
    }


def parse_law_reference(
    text: str,
    start_match: re.Match[str],
    default_law: Optional[LawEntry],
    laws_by_abbreviation: Mapping[str, LawEntry],
) -> Optional[Dict[str, Any]]:
    first_chunk = {
        "end_index": start_match.end(),
        "label": start_match.group("citation"),
        "marker": start_match.group("marker"),
        "provision": start_match.group("provision"),
        "start_index": start_match.start(),
    }
    chunks = [first_chunk]
    end_index = first_chunk["end_index"]

    while True:
        chunk_match = REGEX_CONNECTED_CITATION_CHUNK.match(text, end_index)

        if not chunk_match:
            break

        chunk_start_index = chunk_match.start() + len(chunk_match.group("separator"))
        chunks.append(
            {
                "end_index": chunk_match.end(),
                "label": chunk_match.group("citation"),
                "marker": chunk_match.group("marker") or chunks[0]["marker"],
                "provision": chunk_match.group("provision"),
                "start_index": chunk_start_index,
            }
        )
        end_index = chunk_match.end()

    trailing_law = find_trailing_law(text, end_index, laws_by_abbreviation)

    if trailing_law and trailing_law.get("law"):
        return {
            "chunks": chunks,
            "end_index": trailing_law["end_index"],
            "law": trailing_law["law"],
            "law_abbreviation": trailing_law["abbreviation"],
            "law_match_source": "explicit",
        }

    if trailing_law and trailing_law.get("unknown_abbreviation"):
        return {
            "chunks": chunks,
            "end_index": trailing_law["end_index"],
            "law": None,
            "markdown": text[start_match.start() : trailing_law["end_index"]],
            "unknown_law_abbreviation": trailing_law["unknown_abbreviation"],
        }

    if not default_law or has_unsafe_trailing_unit(text, end_index):
        return None

    return {
        "chunks": chunks,
        "end_index": end_index,
        "law": default_law,
        "law_abbreviation": default_law["abbreviation"],
        "law_match_source": "default-law",
    }


def find_trailing_law(
    text: str,
    index: int,
    laws_by_abbreviation: Mapping[str, LawEntry],
) -> Optional[Dict[str, Any]]:
    whitespace_match = re.match(r"\s+", text[index:])

    if not whitespace_match:
        return None

    first_token_index = index + whitespace_match.end()
    candidates: List[Dict[str, Any]] = []
    token_start_index = first_token_index

    for _ in range(MAX_TRAILING_LAW_TOKENS):
        token = read_law_abbreviation_token(text, token_start_index)

        if not token:
            break

        token_end_index = token_start_index + len(token)
        candidates.append(
            {
                "abbreviation": text[first_token_index:token_end_index],
                "end_index": token_end_index,
            }
        )

        next_whitespace_match = re.match(r"\s+", text[token_end_index:])

        if not next_whitespace_match:
            break

        token_start_index = token_end_index + next_whitespace_match.end()

    if not candidates:
        return None

    for candidate in reversed(candidates):
        law = laws_by_abbreviation.get(normalize_law_abbreviation(candidate["abbreviation"]))

        if law:
            return {
                "abbreviation": candidate["abbreviation"],
                "end_index": candidate["end_index"],
                "law": law,
            }

    return {
        "end_index": candidates[0]["end_index"],
        "unknown_abbreviation": candidates[0]["abbreviation"],
    }


def read_law_abbreviation_token(text: str, index: int) -> Optional[str]:
    if index >= len(text) or not is_law_token_start(text[index]):
        return None

    end_index = index

    while end_index < len(text) and is_law_token_character(text[end_index]):
        end_index += 1

    while end_index > index and not is_law_token_final_character(text[end_index - 1]):
        end_index -= 1

    if end_index <= index:
        return None

    token = text[index:end_index]

    if token[0].islower() and not any(character.isupper() or character.isdigit() for character in token[1:]):
        return None

    return token


def is_law_token_start(character: str) -> bool:
    return character == "(" or character.isupper() or character.isdigit()


def is_law_token_character(character: str) -> bool:
    return character.isalnum() or character in "/+–().-"


def is_law_token_final_character(character: str) -> bool:
    return character.isalnum() or character in ")/+–-"


def has_unsafe_trailing_unit(text: str, index: int) -> bool:
    return bool(REGEX_TRAILING_BLOCKED_UNIT.match(text[index:]))


def render_law_reference(reference: Mapping[str, Any], source_text: str) -> str:
    if reference.get("markdown") is not None:
        return str(reference["markdown"])

    markdown_parts: List[str] = []
    cursor = reference["chunks"][0]["start_index"]

    for chunk in reference["chunks"]:
        markdown_parts.append(source_text[cursor : chunk["start_index"]])
        markdown_parts.append(
            build_markdown_link(
                chunk["label"],
                build_provision_url(reference["law"], chunk["provision"]),
            )
        )
        cursor = chunk["end_index"]

    markdown_parts.append(source_text[cursor : reference["end_index"]])
    return "".join(markdown_parts)


def build_law_citation_records(reference: Mapping[str, Any], source_text: str) -> List[Citation]:
    chunks = reference["chunks"]
    group_text = source_text[chunks[0]["start_index"] : reference["end_index"]]
    citations = []

    for index, chunk in enumerate(chunks):
        provision_details = parse_provision_details(chunk["label"], chunk["provision"])
        url = build_provision_url(reference["law"], chunk["provision"]) if reference.get("law") else None
        citation = {
            "confidence": 0.95 if reference.get("law") else 0.55,
            "end_index": chunk["end_index"],
            "extraction_method": "regex-law-reference",
            "full_text": group_text,
            "group_end_index": reference["end_index"],
            "group_index": index,
            "group_start_index": chunks[0]["start_index"],
            "is_resolved": bool(reference.get("law")),
            "label": chunk["label"],
            "law_abbreviation": reference.get("law_abbreviation")
            or reference.get("unknown_law_abbreviation"),
            "law_match_source": reference.get("law_match_source")
            or ("explicit" if reference.get("unknown_law_abbreviation") else None),
            "marker": chunk.get("marker"),
            "provision": chunk["provision"],
            "start_index": chunk["start_index"],
            "text": source_text[chunk["start_index"] : chunk["end_index"]],
            "type": "law",
            "url": url,
        }
        citation.update(provision_details)
        citation.update(build_law_metadata(reference.get("law")))
        citations.append(citation)

    return citations


def parse_provision_details(label: str, provision: str) -> Dict[str, Optional[str]]:
    details: Dict[str, Optional[str]] = {
        "following": None,
        "letter": None,
        "letter_label": None,
        "number": None,
        "number_label": None,
        "paragraph": None,
        "paragraph_label": None,
        "provision_end": None,
        "range_connector": None,
    }
    provision_match = re.search(re.escape(provision), label)

    if not provision_match:
        return details

    tail = label[provision_match.end() :]
    range_match = re.match(rf"\s*(?P<connector>-|–|—|bis|à|a)\s*(?P<value>{PROVISION_PATTERN})", tail, re.IGNORECASE)
    paragraph_match = re.search(rf"(?P<label>Abs|Absatz|Al|al|Cpv|cpv)\.?\s*(?P<value>{PROVISION_PATTERN})", tail, re.IGNORECASE)
    number_match = re.search(rf"(?P<label>Ziff|Ziffer|Ch|ch|N|n)\.?\s*(?P<value>{PROVISION_PATTERN})", tail, re.IGNORECASE)
    letter_match = re.search(r"(?P<label>Lit|lit|Buchstabe|Bchst|Let|let|Lett|lett)\.?\s*(?P<value>[A-Za-z])", tail)
    following_match = re.search(r"\b(?P<value>f{1,2}\.)\s*$", tail, re.IGNORECASE)

    if range_match:
        details["provision_end"] = range_match.group("value")
        details["range_connector"] = range_match.group("connector")

    if paragraph_match:
        details["paragraph"] = paragraph_match.group("value")
        details["paragraph_label"] = paragraph_match.group("label")

    if number_match:
        details["number"] = number_match.group("value")
        details["number_label"] = number_match.group("label")

    if letter_match:
        details["letter"] = letter_match.group("value")
        details["letter_label"] = letter_match.group("label")

    if following_match:
        details["following"] = following_match.group("value")

    return details


def build_law_metadata(law_entry: Optional[LawEntry]) -> Dict[str, Any]:
    if not law_entry:
        return {
            "law_dynamic_prod_url": None,
            "law_dynamic_source_url": None,
            "law_language": None,
            "law_link_template": None,
            "law_refno": None,
            "law_scope": None,
            "law_title_abbreviation": None,
            "law_title_full": None,
            "law_title_short": None,
        }

    law = law_entry["law"]
    return {
        "law_dynamic_prod_url": law_entry.get("dynamic_prod_url"),
        "law_dynamic_source_url": law_entry.get("dynamic_source_url"),
        "law_language": law_entry.get("language"),
        "law_link_template": law_entry.get("link_template"),
        "law_refno": law.get("refno_law"),
        "law_scope": law_entry.get("scope"),
        "law_title_abbreviation": law_entry.get("abbreviation"),
        "law_title_full": get_localized_law_value(law.get("law_title_full"), law_entry.get("language")),
        "law_title_short": get_localized_law_value(law.get("law_title_short"), law_entry.get("language")),
    }


def get_localized_law_value(value: Any, preferred_language: Optional[str]) -> str:
    if not isinstance(value, Mapping):
        return value or ""

    if preferred_language and value.get(preferred_language):
        return value[preferred_language]

    for language in FEDERAL_LANGUAGE_PREFERENCE:
        if value.get(language):
            return value[language]

    return ""


def build_provision_url(law: LawEntry, provision: str) -> str:
    if law["scope"] == "custom":
        return build_custom_provision_url(law, provision)

    if law["scope"] == "ch":
        return build_fedlex_provision_url(law, provision)

    return build_odat_provision_url(law, provision)


def build_odat_provision_url(law: LawEntry, provision: str) -> str:
    return f"{law['dynamic_prod_url']}-latest.html#seq-0-prov-{quote(provision.lower(), safe='')}"


def build_fedlex_provision_url(law: LawEntry, provision: str) -> str:
    return f"{law['dynamic_source_url']}#art_{quote(provision.lower(), safe='')}"


def build_custom_provision_url(law: LawEntry, provision: str) -> str:
    return render_link_template(law["link_template"], law, provision)


def render_link_template(template: str, law: LawEntry, provision: str) -> str:
    context = build_link_template_context(law, provision)

    try:
        return template.format_map(DefaultFormatContext(context))
    except (KeyError, ValueError):
        return template


def build_link_template_context(law: LawEntry, provision: str) -> Dict[str, Any]:
    abbreviation = law.get("abbreviation", "")
    refno = law.get("law", {}).get("refno_law") or ""
    provision_lower = provision.lower()

    return {
        "abbreviation": abbreviation,
        "abbrevation": abbreviation,
        "article": provision,
        "article_lower": provision_lower,
        "article_urlencoded": quote(provision, safe=""),
        "law_abbreviation": abbreviation,
        "law_refno": refno,
        "provision": provision,
        "provision_lower": provision_lower,
        "provision_urlencoded": quote(provision, safe=""),
        "refno": refno,
    }


class DefaultFormatContext(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def collect_court_citations(text: str) -> List[Citation]:
    return [*collect_bger_citations(text), *collect_bge_citations(text)]


def collect_bger_citations(text: str) -> List[Citation]:
    citations = []

    for match in REGEX_BGER.finditer(text):
        citations.append(
            {
                "chamber_number": match.group(1),
                "confidence": 0.9,
                "court": "swiss_federal_supreme_court",
                "docket_number": match.group(0),
                "end_index": match.end(),
                "extraction_method": "regex-bger-docket",
                "is_resolved": True,
                "start_index": match.start(),
                "text": match.group(0),
                "type": "case_law",
                "url": build_bger_url(match.group(0)),
            }
        )

    return citations


def collect_bge_citations(text: str) -> List[Citation]:
    citations = []

    for match in REGEX_BGE.finditer(text):
        reporter = match.group(1) or "BGE"
        language = get_bge_reporter_language(reporter)
        citations.append(
            {
                "confidence": 0.9,
                "court": "swiss_federal_supreme_court",
                "division": match.group(3),
                "end_index": match.end(),
                "extraction_method": "regex-bge-official-report",
                "is_resolved": True,
                "language": language,
                "page": match.group(4),
                "reporter": reporter,
                "start_index": match.start(),
                "text": match.group(0),
                "type": "case_law",
                "url": build_bge_url(
                    {
                        "division": match.group(3),
                        "language": language,
                        "page": match.group(4),
                        "volume": match.group(2),
                    }
                ),
                "volume": match.group(2),
            }
        )

    return citations


def build_bger_url(reference: str) -> str:
    return f"https://links.weblaw.ch/{quote(reference, safe='')}"


def get_bge_reporter_language(reporter: Optional[str]) -> str:
    if reporter == "ATF":
        return "fr"

    if reporter == "DTF":
        return "it"

    return "de"


def build_bge_url(citation: Mapping[str, str]) -> str:
    language = citation["language"]
    return (
        f"https://www.bger.ch/ext/eurospider/live/{language}/php/aza/http/index.php"
        f"?lang={language}&type=show_document&page=1&from_date=&to_date=&sort=relevance"
        f"&insertion_date=&top_subcollection_aza=all&query_words=&rank=0&azaclir=aza"
        f"&highlight_docid=atf%3A%2F%2F{citation['volume']}-{citation['division']}-{citation['page']}%3A{language}"
        f"&number_of_ranks=0#page{citation['page']}"
    )


def normalize_law_abbreviation(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def build_markdown_link(label: str, url: str) -> str:
    return f"[{escape_markdown_link_label(label)}]({encode_markdown_link_destination(url)})"


def escape_markdown_link_label(value: str) -> str:
    return re.sub(r"([\\\[\]])", r"\\\1", str(value))


def encode_markdown_link_destination(value: str) -> str:
    return str(value).replace(" ", "%20").replace("(", "%28").replace(")", "%29")
