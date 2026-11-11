"""Unit tests for app.pipeline.eligibility_checks — pure code, no LLM, no DB."""

from app.models.schemas import (
    ConsortiumPolicy,
    GoNoGoCriterionMatch,
    GoNoGoHumanOverride,
    PQChecklistItem,
)
from app.pipeline.eligibility_checks import (
    apply_turnover_year_check,
    detect_consortium_policy,
    sync_pq_checklist,
)

# The real C4i4 profile's shape: FY-range keys, rupee values.
TURNOVER = {"2022-23": 26622460, "2023-24": 19039637, "2024-25": 8079117}


def _turnover_match(criterion: str, required: str = "INR 100 Lakh", **kw) -> GoNoGoCriterionMatch:
    return GoNoGoCriterionMatch(
        criterion=criterion,
        required=required,
        company_value="Average approx INR 178 Lakh",
        status="pass",
        page_ref=25,
        **kw,
    )


# --- consortium policy -------------------------------------------------------------


def test_detects_an_allowed_consortium_with_its_page_and_quote() -> None:
    pages = [
        (10, "Bid validity is 180 days."),
        (34, "The tenderer reserves the right to reject any bid.  Consortium participation "
             "is allowed. Bidders may submit bids either individually or as a consortium."),
    ]

    policy = detect_consortium_policy(pages)

    assert policy.status == "allowed"
    assert policy.page_ref == 34
    assert policy.quote == "Consortium participation is allowed."


def test_not_allowed_wins_over_allowed() -> None:
    pages = [
        (2, "Joint Venture bids are permitted for civil works."),
        (5, "Consortium / JV shall not be allowed for this tender."),
    ]

    assert detect_consortium_policy(pages).status == "not_allowed"


def test_gem_form_style_no_answer_is_not_allowed() -> None:
    policy = detect_consortium_policy([(1, "Consortium/JV allowed: No\nMSE exemption: Yes")])

    assert policy.status == "not_allowed"


def test_a_consortium_mention_without_a_ruling_is_not_stated() -> None:
    pages = [(3, "In case of a consortium, the lead member shall sign the agreement.")]

    assert detect_consortium_policy(pages) == ConsortiumPolicy(status="not_stated")


# --- turnover years ---------------------------------------------------------------


def test_missing_named_year_becomes_insufficient_data() -> None:
    match = _turnover_match(
        "Average annual turnover of INR 100 Lakh during 2023-24, 2024-25 and 2025-26."
    )

    [corrected], correction = apply_turnover_year_check([match], TURNOVER)

    assert corrected.status == "insufficient_data"
    assert "FY 2025-26" in corrected.company_value
    assert "FY 2023-24 ₹1.90 Cr" in corrected.company_value
    assert correction == (corrected.status, corrected.company_value)


def test_recomputes_the_average_over_exactly_the_named_years() -> None:
    match = _turnover_match("Average turnover of INR 100 Lakh in FY 2022-23, 2023-24, 2024-25.")

    [corrected], _ = apply_turnover_year_check([match], TURNOVER)

    # (2.66 + 1.90 + 0.81) Cr / 3 = 1.79 Cr >= 1 Cr
    assert corrected.status == "pass"
    assert "₹1.79 Cr" in corrected.company_value


def test_fails_when_the_named_years_average_below_the_threshold() -> None:
    match = _turnover_match(
        "Average turnover in FY 2023-24 and 2024-25", required="Minimum INR 2 Crore"
    )

    [corrected], _ = apply_turnover_year_check([match], TURNOVER)

    assert corrected.status == "fail"


def test_leaves_criteria_without_named_years_untouched() -> None:
    match = _turnover_match("Average turnover of INR 100 Lakh over the last three years.")

    [corrected], correction = apply_turnover_year_check([match], TURNOVER)

    assert corrected == match
    assert correction is None


def test_never_overrides_a_human_review() -> None:
    match = _turnover_match(
        "Turnover of INR 100 Lakh in 2023-24, 2024-25, 2025-26",
        human_override=GoNoGoHumanOverride(
            status="pass", original_status="pass", reviewed_at="2026-10-26T00:00:00Z"
        ),
    )

    [corrected], _ = apply_turnover_year_check([match], TURNOVER)

    assert corrected.status == "pass"


def test_skips_when_profile_years_are_ambiguous() -> None:
    match = _turnover_match("Turnover of INR 100 Lakh in 2023-24, 2024-25, 2025-26")

    [corrected], _ = apply_turnover_year_check([match], {"2024": 720000000.0})

    assert corrected == match


# --- PQ checklist sync ------------------------------------------------------------


def test_syncs_turnover_and_consortium_rows() -> None:
    items = [
        PQChecklistItem(category="Average annual turnover", status="pass", company_value="1.78 Cr"),
        PQChecklistItem(category="Consortium / JV eligibility", status="not_applicable"),
        PQChecklistItem(category="PAN", status="pass"),
    ]
    policy = ConsortiumPolicy(
        status="allowed", quote="Consortium participation is allowed.", page_ref=34
    )

    turnover, consortium, pan = sync_pq_checklist(
        items, ("insufficient_data", "No FY 2025-26 figure."), policy
    )

    assert turnover.status == "insufficient_data"
    assert consortium.status == "pass"
    assert consortium.page_ref == 34
    assert consortium.tender_requirement == "Consortium participation is allowed."
    assert pan == items[2]


# --- turnover figures for the prompt -------------------------------------------------


def test_prompt_turnover_figures_do_the_arithmetic() -> None:
    from app.pipeline.eligibility_checks import turnover_facts_for_prompt

    text = turnover_facts_for_prompt(
        TURNOVER, ["Average annual turnover of INR 100 Lakh in 2023-24, 2024-25 and 2025-26"]
    )

    assert "Average of the latest 2 FYs on file: ₹1.36 Cr" in text
    assert "no figure on file for FY 2025-26" in text
    assert turnover_facts_for_prompt({}, []) == ""


# --- exemption claims ----------------------------------------------------------------

COEP_PAGES = [
    (11, "2. Submission of Earnest Money Deposit (EMD) shall not be mandatory for eligible "
         "Startups and Micro, Small and Medium Enterprises (MSMEs), subject to submission of "
         "valid documentary evidence."),
    (24, "3. Startups and MSMEs are also eligible to participate, subject to fulfillment of "
         "the eligibility criteria specified in the RFP."),
]


def test_drops_an_exemption_the_tender_never_grants() -> None:
    from app.pipeline.eligibility_checks import drop_unsupported_exemption_steps

    steps = [
        "Submit the Udyam MSME certificate to seek exemption from the 200 Lakh training "
        "project experience and turnover criteria.",
        "Submit the MSME certificate to claim the EMD exemption.",
        "Prepare a CA certificate for turnover.",
    ]

    assert drop_unsupported_exemption_steps(steps, COEP_PAGES) == steps[1:]


def test_a_gem_relaxation_answered_no_is_not_support() -> None:
    from app.pipeline.eligibility_checks import drop_unsupported_exemption_steps

    pages = [(0, "Startup Relaxation for Years of Experience and Turnover: No")]
    step = "Claim startup relaxation from the turnover criterion."

    assert drop_unsupported_exemption_steps([step], pages) == []


# --- duplicate criteria ----------------------------------------------------------------


def _criterion(text: str, page: int = 24, status: str = "pass") -> GoNoGoCriterionMatch:
    return GoNoGoCriterionMatch(
        criterion=text, required="-", company_value="-", status=status, page_ref=page
    )


def test_merges_the_same_criterion_stated_for_bidder_and_agency() -> None:
    from app.pipeline.eligibility_checks import dedupe_criteria

    matches = [
        _criterion("Bidder must hold valid statutory registrations such as PAN, GST, and other "
                   "regulatory registrations."),
        _criterion("The agency must possess valid statutory registrations such as PAN, GST, "
                   "and other applicable registrations."),
        _criterion("Bidder must be legally registered under applicable laws."),
        _criterion("The agency must be legally registered under applicable laws."),
    ]

    assert [m.criterion for m in dedupe_criteria(matches)] == [
        matches[0].criterion,
        matches[2].criterion,
    ]


def test_never_merges_criteria_with_different_numbers_pages_or_statuses() -> None:
    from app.pipeline.eligibility_checks import dedupe_criteria

    matches = [
        _criterion("Average annual turnover of INR 100 Lakh in the last 3 years"),
        _criterion("Average annual turnover of INR 200 Lakh in the last 3 years"),
        _criterion("Average annual turnover of INR 100 Lakh in the last 3 years", page=30),
        _criterion("Average annual turnover of INR 100 Lakh in the last 3 years", status="fail"),
    ]

    assert dedupe_criteria(matches) == matches
