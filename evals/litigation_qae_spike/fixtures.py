"""Rights-cleared synthetic FR/NL litigation fixtures and adversarial scripts."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from evals.litigation_qae_spike.contracts import (
    ContentReleaseGrant,
    EntityLinkProof,
    IndexedDocument,
    ModelCandidate,
    VisualBox,
)
from evals.litigation_qae_spike.engine import index_document_blocks


@dataclass(frozen=True, slots=True)
class SpikeCaseFixture:
    case_id: str
    description: str
    brief_text: str
    documents: dict[str, IndexedDocument]
    bordereau_entries: list[dict[str, Any]]
    bordereau_confirmed: bool
    entity_links: tuple[EntityLinkProof, ...]
    release: ContentReleaseGrant
    selected_blocks: tuple[tuple[str, str], ...]
    reference_tokens: set[str]
    expected_rule_codes: tuple[str, ...]
    clean_candidates: tuple[ModelCandidate, ...]


def _box(page: int, y0: float = 0.2) -> tuple[VisualBox, ...]:
    return (VisualBox(page=page, x0=0.1, y0=y0, x1=0.9, y1=y0 + 0.08),)


def build_case1_status_shift_reservation() -> SpikeCaseFixture:
    """Case 1: 'signé' in brief vs 'envoyé pour signature' + cross-block/page reservation."""
    brief_text = (
        "Selon la Pièce 1, PDF p. 1, le contrat cadre CTR-2026-01 a été signé le 12 mars 2026. "
        "L'accord lie donc irrévocablement les parties."
    )
    brief_doc = index_document_blocks(
        exhibit_id="brief",
        document_id="doc-brief-c1",
        version_id="v1",
        representation_id="rep-brief-c1",
        pages=[(1, [(brief_text, _box(1))], False)],
    )
    p1_doc = index_document_blocks(
        exhibit_id="piece-1",
        document_id="doc-p1-c1",
        version_id="v1",
        representation_id="rep-p1-c1",
        pages=[
            (
                1,
                [("Projet de contrat cadre CTR-2026-01 envoyé pour signature le 12 mars 2026.", _box(1))],
                False,
            ),
            (
                2,
                [
                    (
                        "Sous réserve de validation préalable par le conseil d'administration et sans préjudice des droits antérieurs.",
                        _box(2),
                    ),
                    (
                        "Annexe logistique sans incidence financière ni engagement.",
                        _box(2, y0=0.5),
                    ),
                ],
                False,
            ),
        ],
    )
    release = ContentReleaseGrant(
        release_id="rel-case1",
        matter_id="matter-synth-01",
        destination="eu-zero-retention-eval",
        retention_policy="no_prompt_retention_declared_unverified",
        max_total_chars=600,
        authorized=True,
    )
    candidates = (
        ModelCandidate(
            candidate_id="c1-brief-1",
            exhibit_id="brief",
            entity_id="CTR-2026-01",
            slot="contract_status",
            signal="contract_status_claim",
            raw_value="signed",
            quote="le contrat cadre CTR-2026-01 a été signé le 12 mars 2026",
            polarity="affirmative",
            provider="scripted",
            model="scripted-clean",
            prompt_version="spike-v1",
        ),
        ModelCandidate(
            candidate_id="c1-p1-1",
            exhibit_id="piece-1",
            entity_id="CTR-2026-01",
            slot="contract_status",
            signal="contract_status_source",
            raw_value="sent_for_signature",
            quote="envoyé pour signature le 12 mars 2026",
            polarity="affirmative",
            provider="scripted",
            model="scripted-clean",
            prompt_version="spike-v1",
        ),
    )
    return SpikeCaseFixture(
        case_id="case1_status_shift_reservation",
        description="Conclusion states signed while exhibit says sent_for_signature with page-2 reservation.",
        brief_text=brief_text,
        documents={"brief": brief_doc, "piece-1": p1_doc},
        bordereau_entries=[{"label": "piece", "number": "1", "source_version_id": "v1", "pages": []}],
        bordereau_confirmed=True,
        entity_links=(
            EntityLinkProof(
                entity_id="CTR-2026-01",
                source_exhibit_ids=("brief", "piece-1"),
                link_basis="explicit_reference_id",
                reference_token="CTR-2026-01",
            ),
        ),
        release=release,
        selected_blocks=(("brief", brief_doc.blocks[0].block_id), ("piece-1", p1_doc.blocks[0].block_id)),
        reference_tokens={"CTR-2026-01"},
        expected_rule_codes=("STATUS_SHIFT_CANDIDATE",),
        clean_candidates=candidates,
    )


def build_case2_fr_nl_multiscalar_trap() -> SpikeCaseFixture:
    """Case 2: Bilingual FR brief vs NL exhibit with two amounts in one sentence."""
    brief_text = (
        "Comme l'établit la Pièce 2, PDF p. 1, le défendeur a déjà payé 12 500 EUR "
        "sur la facture FAC-2025-019."
    )
    brief_doc = index_document_blocks(
        exhibit_id="brief",
        document_id="doc-brief-c2",
        version_id="v1",
        representation_id="rep-brief-c2",
        pages=[(1, [(brief_text, _box(1))], False)],
    )
    nl_text = (
        "Factuur FAC-2025-019 ten bedrage van 12.500,00 EUR, waarvan 2.500,00 EUR reeds "
        "betaald op 14 maart 2026, behoudens verificatie van de eindafrekening."
    )
    p2_doc = index_document_blocks(
        exhibit_id="piece-2",
        document_id="doc-p2-c2",
        version_id="v2",
        representation_id="rep-p2-c2",
        pages=[
            (1, [(nl_text, _box(1))], False),
            (2, [("Algemene leveringsvoorwaarden zonder bedragen.", _box(2))], False),
        ],
    )
    release = ContentReleaseGrant(
        release_id="rel-case2",
        matter_id="matter-synth-02",
        destination="eu-zero-retention-eval",
        retention_policy="no_prompt_retention_declared_unverified",
        max_total_chars=800,
        authorized=True,
    )
    candidates = (
        ModelCandidate(
            candidate_id="c2-brief-1",
            exhibit_id="brief",
            entity_id="FAC-2025-019",
            slot="amount_paid",
            signal="payment_claimed",
            raw_value="12 500 EUR",
            quote="le défendeur a déjà payé 12 500 EUR",
            polarity="affirmative",
            provider="scripted",
            model="scripted-clean",
            prompt_version="spike-v1",
        ),
        ModelCandidate(
            candidate_id="c2-p2-1",
            exhibit_id="piece-2",
            entity_id="FAC-2025-019",
            slot="amount_paid",
            signal="payment_source",
            raw_value="2.500,00 EUR",
            quote="waarvan 2.500,00 EUR reeds betaald op 14 maart 2026",
            polarity="affirmative",
            provider="scripted",
            model="scripted-clean",
            prompt_version="spike-v1",
        ),
    )
    return SpikeCaseFixture(
        case_id="case2_fr_nl_multiscalar_trap",
        description="FR brief claims 12 500 EUR paid while NL exhibit shows 12.500,00 invoiced / 2.500,00 paid.",
        brief_text=brief_text,
        documents={"brief": brief_doc, "piece-2": p2_doc},
        bordereau_entries=[{"label": "piece", "number": "2", "source_version_id": "v2", "pages": []}],
        bordereau_confirmed=True,
        entity_links=(
            EntityLinkProof(
                entity_id="FAC-2025-019",
                source_exhibit_ids=("brief", "piece-2"),
                link_basis="explicit_reference_id",
                reference_token="FAC-2025-019",
            ),
        ),
        release=release,
        selected_blocks=(("brief", brief_doc.blocks[0].block_id), ("piece-2", p2_doc.blocks[0].block_id)),
        reference_tokens={"FAC-2025-019"},
        expected_rule_codes=("BILINGUAL_SCALAR_DIFFERENCE_CANDIDATE",),
        clean_candidates=candidates,
    )


def build_case3_cross_exhibit_credit_note() -> SpikeCaseFixture:
    """Case 3: Uncited Pièce 7 credit note, multi-invoice Pièce 3, excluded Pièce 8, OCR Pièce 9."""
    brief_text = (
        "Selon la Pièce 3, PDF p. 1, la créance impayée sur la facture FAC-2025-042 s'élève à 12 500 EUR."
    )
    brief_doc = index_document_blocks(
        exhibit_id="brief",
        document_id="doc-brief-c3",
        version_id="v1",
        representation_id="rep-brief-c3",
        pages=[(1, [(brief_text, _box(1))], False)],
    )
    # Pièce 3 deliberately holds TWO distinct invoices so Bordereau confirmation alone != Entities.
    p3_doc = index_document_blocks(
        exhibit_id="piece-3",
        document_id="doc-p3-c3",
        version_id="v3",
        representation_id="rep-p3-c3",
        pages=[
            (1, [("Facture FAC-2025-042 : prestation IT pour un total de 12.500,00 EUR.", _box(1))], False),
            (2, [("Facture FAC-2025-099 : maintenance annuelle séparée de 3.000,00 EUR.", _box(2))], False),
        ],
    )
    # Uncited Pièce 7 credit note referencing FAC-2025-042.
    p7_doc = index_document_blocks(
        exhibit_id="piece-7",
        document_id="doc-p7-c3",
        version_id="v7",
        representation_id="rep-p7-c3",
        pages=[
            (1, [("Note de crédit / Creditnota relative à FAC-2025-042 pour un montant de 2.500,00 EUR.", _box(1))], False),
        ],
    )
    # Unrelated delivery slip (no token or counter-evidence cue -> excluded by preselection).
    p8_doc = index_document_blocks(
        exhibit_id="piece-8",
        document_id="doc-p8-c3",
        version_id="v8",
        representation_id="rep-p8-c3",
        pages=[(1, [("Bon de livraison matériel informatique du 4 février 2026.", _box(1))], False)],
    )
    # Scanned OCR-uncertain exhibit with empty visual boxes.
    p9_doc = index_document_blocks(
        exhibit_id="piece-9",
        document_id="doc-p9-c3",
        version_id="v9",
        representation_id="rep-p9-c3",
        pages=[(1, [("Scan illisible FAC-2025-042 reçu ?", ())], True)],
    )
    release = ContentReleaseGrant(
        release_id="rel-case3",
        matter_id="matter-synth-03",
        destination="eu-zero-retention-eval",
        retention_policy="no_prompt_retention_declared_unverified",
        max_total_chars=1200,
        authorized=True,
    )
    candidates = (
        ModelCandidate(
            candidate_id="c3-brief-1",
            exhibit_id="brief",
            entity_id="FAC-2025-042",
            slot="amount_claimed",
            signal="claim_amount",
            raw_value="12 500 EUR",
            quote="la créance impayée sur la facture FAC-2025-042 s'élève à 12 500 EUR",
            polarity="affirmative",
            provider="scripted",
            model="scripted-clean",
            prompt_version="spike-v1",
        ),
        ModelCandidate(
            candidate_id="c3-p7-1",
            exhibit_id="piece-7",
            entity_id="FAC-2025-042",
            slot="credit_note_amount",
            signal="credit_note",
            raw_value="2.500,00 EUR",
            quote="Note de crédit / Creditnota relative à FAC-2025-042 pour un montant de 2.500,00 EUR",
            polarity="affirmative",
            provider="scripted",
            model="scripted-clean",
            prompt_version="spike-v1",
        ),
    )
    return SpikeCaseFixture(
        case_id="case3_cross_exhibit_credit_note",
        description="Uncited Pièce 7 credit note contradicts claimed full amount on FAC-2025-042.",
        brief_text=brief_text,
        documents={
            "brief": brief_doc,
            "piece-3": p3_doc,
            "piece-7": p7_doc,
            "piece-8": p8_doc,
            "piece-9": p9_doc,
        },
        bordereau_entries=[
            {"label": "piece", "number": "3", "source_version_id": "v3", "pages": []},
            {"label": "piece", "number": "7", "source_version_id": "v7", "pages": []},
            {"label": "piece", "number": "8", "source_version_id": "v8", "pages": []},
            {"label": "piece", "number": "9", "source_version_id": "v9", "pages": []},
        ],
        bordereau_confirmed=True,
        entity_links=(
            EntityLinkProof(
                entity_id="FAC-2025-042",
                source_exhibit_ids=("brief", "piece-3", "piece-7"),
                link_basis="explicit_reference_id",
                reference_token="FAC-2025-042",
            ),
        ),
        release=release,
        selected_blocks=(("brief", brief_doc.blocks[0].block_id), ("piece-3", p3_doc.blocks[0].block_id)),
        reference_tokens={"FAC-2025-042"},
        expected_rule_codes=("CROSS_EXHIBIT_CONFLICT_CANDIDATE",),
        clean_candidates=candidates,
    )


def all_spike_fixtures() -> Sequence[SpikeCaseFixture]:
    return (
        build_case1_status_shift_reservation(),
        build_case2_fr_nl_multiscalar_trap(),
        build_case3_cross_exhibit_credit_note(),
    )
