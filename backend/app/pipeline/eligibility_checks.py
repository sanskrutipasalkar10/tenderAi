"""Rule-based corrections layered on top of the go_no_go model output (CLAUDE.md hard
rule 3 — arithmetic and literal-text checks are code, not prompt instructions;
docs/DECISIONS.md #93).

- Consortium policy: whether the tender lets a consortium/JV bid, read straight from
  the tender's own sentences and page-cited. A failed eligibility criterion is only
  coverable by a partner when this says "allowed" — the frontend uses it to say so
  plainly instead of leaving "Partner Required" as a score-band coincidence.
- Turnover years: the tender names exact financial years ("2023-24, 2024-25 and
  2025-26"); the model was found averaging the profile's three most recent years
  instead (2022-23..2024-25) and passing a criterion the company can't yet evidence.
  Recomputed here from exactly the named years; a missing year is insufficient_data.
"""

import re
from collections.abc import Sequence
from typing import Literal

from app.core.logging import get_logger
from app.models.schemas import ConsortiumPolicy, GoNoGoCriterionMatch, PQChecklistItem

logger = get_logger(__name__)

# --- consortium policy -----------------------------------------------------------

_CONSORTIUM = re.compile(r"\b(consortium|consortia|joint[\s-]+venture|JV)\b", re.IGNORECASE)
_NOT_ALLOWED = re.compile(
    r"\b(not\s+(be\s+)?(allowed|permitted|accepted|eligible|entertained|considered)"
    r"|shall\s+not\s+(be\s+)?(allowed|permitted|accepted)|no\s+consortium|prohibited"
    r"|disallowed|cannot\s+(bid|participate|submit))\b"
    # GeM bid-form style: "Consortium/JV allowed: No"
    r"|\b(allowed|permitted)\s*[:\-]?\s*no\b",
    re.IGNORECASE,
)
_ALLOWED = re.compile(
    r"\b(is|are|shall\s+be)\s+(allowed|permitted|acceptable|accepted)\b"
    r"|\bmay\s+(bid|submit|participate|apply|form)\b"
    r"|\bcan\s+(bid|submit|participate|apply)\b"
    r"|\b(allowed|permitted)\s*[:\-]?\s*yes\b"
    r"|\bparticipation\s+is\s+(allowed|permitted)\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.;!?])\s+")
_MAX_QUOTE_CHARS = 240


def detect_consortium_policy(pages: Sequence[tuple[int, str]]) -> ConsortiumPolicy:
    """First explicit "not allowed" statement wins over any "allowed" one — if a tender
    says both (e.g. a GeM form field vs. a buyer clause), assuming a partner can help
    when it can't is the costlier mistake; the quote is shown so a human can check.
    """
    allowed: ConsortiumPolicy | None = None
    for page_number, text in pages:
        for sentence in _SENTENCE_SPLIT.split(re.sub(r"\s+", " ", text)):
            if not _CONSORTIUM.search(sentence):
                continue
            # Leading list bullets (PDF private-use glyphs like , "●", "-") aren't
            # part of what the tender said.
            quote = re.sub(r"^[^\w(\"']+", "", sentence.strip())[:_MAX_QUOTE_CHARS]
            if _NOT_ALLOWED.search(sentence):
                return ConsortiumPolicy(status="not_allowed", quote=quote, page_ref=page_number)
            if allowed is None and _ALLOWED.search(sentence):
                allowed = ConsortiumPolicy(status="allowed", quote=quote, page_ref=page_number)
    return allowed or ConsortiumPolicy(status="not_stated")


# --- turnover years ---------------------------------------------------------------

_FY = re.compile(r"\b(?:FY\s*)?(20\d{2})\s*[-–/]\s*(20\d{2}|\d{2})\b", re.IGNORECASE)
_AMOUNT = re.compile(
    r"(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)\s*(crores?|cr\b|lakhs?|lacs?|lakh)?",
    re.IGNORECASE,
)
_UNIT = {"crore": 10_000_000, "cr": 10_000_000, "lakh": 100_000, "lac": 100_000}
# A bare number below this can't be a rupee turnover threshold (it's a year count, a
# percentage, a clause number...) — only trusted when it carries a lakh/crore unit.
_MIN_PLAIN_RUPEE_AMOUNT = 100_000


def _financial_years(text: str) -> list[int]:
    """Start years of every "YYYY-YY"/"YYYY-YYYY" financial year named in `text`."""
    years = set()
    for start, end in _FY.findall(text):
        start_year = int(start)
        end_year = int(end) if len(end) == 4 else int(str(start_year)[:2] + end)
        if end_year == start_year + 1:
            years.add(start_year)
    return sorted(years)


def _fy_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _rupees(value: float) -> str:
    if value >= 10_000_000:
        return f"₹{value / 10_000_000:.2f} Cr"
    return f"₹{value / 100_000:.2f} Lakh"


def _threshold_rupees(text: str) -> float | None:
    """The turnover threshold in rupees, from text like "INR 100 Lakh" / "₹5 Crore" /
    "Rs. 1,00,00,000" — or None when it can't be read unambiguously."""
    for number, unit in _AMOUNT.findall(text):
        try:
            value = float(number.replace(",", ""))
        except ValueError:
            continue
        unit = unit.lower().rstrip("s")
        if unit:
            key = "cr" if unit.startswith("cr") else ("lac" if unit.startswith("lac") else unit)
            return value * _UNIT[key]
        if value >= _MIN_PLAIN_RUPEE_AMOUNT and not 2000 <= value <= 2100:
            return value
    return None


def _profile_turnover_by_year(annual_turnover: object) -> dict[int, float]:
    if not isinstance(annual_turnover, dict):
        return {}
    by_year: dict[int, float] = {}
    for key, value in annual_turnover.items():
        years = _financial_years(str(key))
        if len(years) == 1 and isinstance(value, int | float):
            by_year[years[0]] = float(value)
    return by_year


TurnoverStatus = Literal["pass", "fail", "insufficient_data"]


def _check_turnover(
    match: GoNoGoCriterionMatch, turnover_by_year: dict[int, float]
) -> tuple[TurnoverStatus, str] | None:
    text = f"{match.criterion} {match.required}"
    if "turnover" not in text.lower():
        return None
    named = _financial_years(text)
    if len(named) < 2:
        return None

    labels = ", ".join(_fy_label(y) for y in named)
    known = ", ".join(
        f"FY {_fy_label(y)} {_rupees(turnover_by_year[y])}" for y in named if y in turnover_by_year
    )
    missing = [y for y in named if y not in turnover_by_year]
    if missing:
        missing_labels = ", ".join(_fy_label(y) for y in missing)
        value = (
            f"Tender averages FY {labels}; the company profile has no turnover for FY "
            f"{missing_labels}." + (f" Known: {known}." if known else "")
        )
        return "insufficient_data", value

    average = sum(turnover_by_year[y] for y in named) / len(named)
    value = f"Average over FY {labels} = {_rupees(average)} ({known})."
    threshold = _threshold_rupees(match.required) or _threshold_rupees(match.criterion)
    if threshold is None:
        return None
    return ("pass" if average >= threshold else "fail"), value


def apply_turnover_year_check(
    matches: list[GoNoGoCriterionMatch], annual_turnover: object
) -> tuple[list[GoNoGoCriterionMatch], tuple[TurnoverStatus, str] | None]:
    """Returns the corrected matches, plus the (status, company_value) correction made
    to a turnover criterion (None if nothing was corrected) so the PQ checklist's own
    turnover row can be brought in line with it.

    Never touches a criterion a human already reviewed. Skipped entirely when no
    profile turnover key is a recognisable financial year (e.g. bare "2024" keys —
    which year that means is ambiguous, and guessing would mislabel real data).
    """
    turnover_by_year = _profile_turnover_by_year(annual_turnover)
    if not turnover_by_year:
        return matches, None

    corrected: list[GoNoGoCriterionMatch] = []
    correction: tuple[TurnoverStatus, str] | None = None
    for match in matches:
        check = (
            _check_turnover(match, turnover_by_year)
            if match.criterion_type == "eligibility" and match.human_override is None
            else None
        )
        if check is None:
            corrected.append(match)
            continue
        status, value = check
        correction = correction or check
        corrected.append(match.model_copy(update={"status": status, "company_value": value}))
    return corrected, correction


# --- PQ checklist rows ------------------------------------------------------------

_TURNOVER_ROW = "Average annual turnover"
_CONSORTIUM_ROW = "Consortium / JV eligibility"


def sync_pq_checklist(
    items: list[PQChecklistItem] | None,
    turnover_correction: tuple[TurnoverStatus, str] | None,
    consortium: ConsortiumPolicy,
) -> list[PQChecklistItem] | None:
    """The PQ checklist is a separate model call that can disagree with the corrected
    criteria above — keep its turnover and consortium rows consistent with them."""
    if items is None:
        return None
    synced = []
    for item in items:
        if item.category == _TURNOVER_ROW and turnover_correction is not None:
            status, value = turnover_correction
            item = item.model_copy(update={"status": status, "company_value": value})
        elif item.category == _CONSORTIUM_ROW and consortium.status != "not_stated":
            item = item.model_copy(
                update={
                    "tender_requirement": consortium.quote,
                    "page_ref": consortium.page_ref,
                    "status": "pass" if consortium.status == "allowed" else "not_applicable",
                    "company_value": (
                        "Allowed — the company may bid alone or with a consortium/JV partner."
                        if consortium.status == "allowed"
                        else "Not allowed — the company must meet every criterion on its own."
                    ),
                }
            )
        synced.append(item)
    return synced


# --- exact turnover figures for the prompt ----------------------------------------


def turnover_facts_for_prompt(annual_turnover: object, criteria_texts: Sequence[str]) -> str:
    """Code-computed turnover figures handed to the go_no_go model, so its Financial
    Capability score/reason is never built on its own arithmetic (found on a real run:
    "₹1.9 Cr and ₹0.8 Cr average below 100 Lakh" — the average is ₹1.35 Cr). Empty
    string when the profile has no recognisable FY turnover.
    """
    by_year = _profile_turnover_by_year(annual_turnover)
    if not by_year:
        return ""
    years = sorted(by_year)
    lines = [
        "COMPUTED TURNOVER FIGURES (exact, computed in code — use these, never recompute):",
        "- " + "; ".join(f"FY {_fy_label(y)} {_rupees(by_year[y])}" for y in years),
    ]
    for n in (2, 3):
        if len(years) >= n:
            latest = years[-n:]
            average = sum(by_year[y] for y in latest) / n
            lines.append(f"- Average of the latest {n} FYs on file: {_rupees(average)}")
    for text in criteria_texts:
        named = _financial_years(text)
        if "turnover" not in text.lower() or len(named) < 2:
            continue
        missing = [y for y in named if y not in by_year]
        labels = ", ".join(_fy_label(y) for y in named)
        if missing:
            lines.append(
                f"- Tender names FY {labels}: no figure on file for FY "
                f"{', '.join(_fy_label(y) for y in missing)} (insufficient data, not a fail)"
            )
        else:
            average = sum(by_year[y] for y in named) / len(named)
            lines.append(f"- Tender names FY {labels}: average {_rupees(average)}")
    return "\n".join(lines)


# --- exemption claims in next steps -------------------------------------------------

_EXEMPTION_CLAIM = re.compile(r"\b(exempt\w*|relax\w*|waive\w*|waiver)\b", re.IGNORECASE)
_EXEMPTION_STATED = re.compile(
    r"\b(exempt\w*|relax\w*|waive\w*|waiver|(shall\s+)?not\s+(be\s+)?(mandatory|required))\b",
    re.IGNORECASE,
)
# A GeM form field answered "No" ("Startup Relaxation for Years of Experience and
# Turnover: No") states that there is NO relaxation — it mustn't count as support.
_EXEMPTION_DENIED = re.compile(r"(relaxation|exemption)[^.]{0,120}:\s*no\b", re.IGNORECASE)
_EXEMPTION_TOPICS: dict[str, re.Pattern[str]] = {
    name: re.compile(pattern, re.IGNORECASE)
    for name, pattern in {
        "turnover": r"turnover",
        "experience": (
            r"experience|similar\s+(project|work|assignment)|project\s+value|work\s+order"
        ),
        "emd": r"\bEMD\b|earnest\s+money|bid\s+security",
        "tender fee": r"tender\s+fee|document\s+fee",
        "performance security": r"performance\s+(security|bank\s+guarantee)|\bPBG\b",
        "net worth": r"net\s*-?\s*worth",
    }.items()
}


def drop_unsupported_exemption_steps(
    next_steps: Sequence[str], pages: Sequence[tuple[int, str]]
) -> list[str]:
    """Drops a next step that tells the bid team to claim an exemption/relaxation the
    tender never grants for that requirement. Found on a real run: "submit the MSME
    certificate to seek exemption from the 200 Lakh experience and turnover criteria"
    — the tender exempts MSMEs from the EMD only, and requires them to meet every
    eligibility criterion. Following that step would mean a non-qualifying bid.
    A step is kept when every requirement it names appears in some tender sentence
    that grants an exemption (or when it names no recognisable requirement at all).
    """
    granting = [
        sentence
        for _, text in pages
        for sentence in _SENTENCE_SPLIT.split(re.sub(r"\s+", " ", text))
        if _EXEMPTION_STATED.search(sentence) and not _EXEMPTION_DENIED.search(sentence)
    ]
    kept = []
    for step in next_steps:
        if _EXEMPTION_CLAIM.search(step):
            topics = [p for p in _EXEMPTION_TOPICS.values() if p.search(step)]
            if topics and not all(any(t.search(s) for s in granting) for t in topics):
                logger.warning("eligibility_checks.dropped_unsupported_exemption_step", step=step)
                continue
        kept.append(step)
    return kept


# --- duplicate criteria ---------------------------------------------------------------

_SUBJECT = re.compile(
    r"^\s*(the\s+)?(bidders?|agency|agencies|institute/agency|institute|firm|tenderer|"
    r"applicant|contractor|vendor|seller)\b",
    re.IGNORECASE,
)
_STOPWORDS = {
    "a", "an", "and", "any", "as", "at", "be", "by", "for", "from", "have", "has", "in",
    "is", "least", "minimum", "must", "of", "or", "other", "shall", "should", "such",
    "the", "to", "with", "within", "valid", "relevant", "applicable",
}
_DUPLICATE_SIMILARITY = 0.5


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", _SUBJECT.sub("", text).lower())
    return {w for w in words if w not in _STOPWORDS}


def dedupe_criteria(matches: list[GoNoGoCriterionMatch]) -> list[GoNoGoCriterionMatch]:
    """Tenders often state the same eligibility list twice (e.g. "The agency must…"
    and again "Bidders must…" on the same page), and the model reports both. Merges a
    criterion into an earlier one when they share a page, type and status, name the
    same numbers, and mostly the same words — keeping the first. Conservative: two
    criteria that differ in any number (₹100 Lakh vs ₹200 Lakh) are never merged.
    """
    kept: list[GoNoGoCriterionMatch] = []
    for match in matches:
        words = _content_words(match.criterion)
        numbers = set(re.findall(r"\d+", match.criterion))
        duplicate = any(
            other.page_ref == match.page_ref
            and other.criterion_type == match.criterion_type
            and other.status == match.status
            and set(re.findall(r"\d+", other.criterion)) == numbers
            and words
            and len(words & _content_words(other.criterion))
            / len(words | _content_words(other.criterion))
            >= _DUPLICATE_SIMILARITY
            for other in kept
        )
        if not duplicate:
            kept.append(match)
    return kept
