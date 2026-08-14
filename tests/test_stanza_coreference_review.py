from __future__ import annotations

from types import SimpleNamespace

from stanza_coreference_review import document_payload


def test_document_payload_serializes_dependency_and_coreference_evidence() -> None:
    words = [
        SimpleNamespace(
            id=1,
            text="Анна",
            lemma="Анна",
            upos="PROPN",
            feats="Case=Nom|Gender=Fem|Number=Sing",
            head=2,
            deprel="nsubj",
        ),
        SimpleNamespace(
            id=2,
            text="вошла",
            lemma="войти",
            upos="VERB",
            feats="Gender=Fem|Number=Sing|Tense=Past",
            head=0,
            deprel="root",
        ),
        SimpleNamespace(
            id=3,
            text="Она",
            lemma="она",
            upos="PRON",
            feats="Case=Nom|Gender=Fem|Number=Sing",
            head=4,
            deprel="nsubj",
        ),
        SimpleNamespace(
            id=4,
            text="села",
            lemma="сесть",
            upos="VERB",
            feats="Gender=Fem|Number=Sing|Tense=Past",
            head=0,
            deprel="root",
        ),
    ]
    sentence = SimpleNamespace(words=words)
    mention_a = SimpleNamespace(sentence=0, start_word=0, end_word=1)
    mention_b = SimpleNamespace(sentence=0, start_word=2, end_word=3)
    chain = SimpleNamespace(
        index=0,
        representative_text="Анна",
        representative_index=0,
        mentions=[mention_a, mention_b],
    )
    doc = SimpleNamespace(sentences=[sentence], coref=[chain])

    payload = document_payload(doc)

    assert payload["status"] == "REVIEW"
    assert payload["automatic_rewrite_allowed"] is False
    assert payload["dependencies"][0]["deprel"] == "nsubj"
    assert payload["coreference_chains"][0]["representative_text"] == "Анна"
    assert [item["text"] for item in payload["coreference_chains"][0]["mentions"]] == [
        "Анна",
        "Она",
    ]
    assert all(item["is_zero"] is False for item in payload["coreference_chains"][0]["mentions"])


def test_document_payload_preserves_zero_mentions() -> None:
    sentence = SimpleNamespace(
        words=[
            SimpleNamespace(
                id=1,
                text="Улыбнулась",
                lemma="улыбнуться",
                upos="VERB",
                feats="Gender=Fem|Number=Sing|Tense=Past",
                head=0,
                deprel="root",
            )
        ]
    )
    zero = SimpleNamespace(sentence=0, start_word=(0, 0), end_word=(0, 0))
    chain = SimpleNamespace(
        index=0,
        representative_text="Анна",
        representative_index=0,
        mentions=[zero],
    )
    doc = SimpleNamespace(sentences=[sentence], coref=[chain])

    payload = document_payload(doc)
    mention = payload["coreference_chains"][0]["mentions"][0]
    assert mention["text"] == "_"
    assert mention["is_zero"] is True
