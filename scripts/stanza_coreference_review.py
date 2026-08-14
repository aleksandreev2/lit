#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _mention_payload(doc, mention) -> dict:
    is_zero = isinstance(mention.start_word, tuple) or isinstance(mention.end_word, tuple)
    if is_zero:
        text = "_"
    else:
        words = doc.sentences[mention.sentence].words[mention.start_word : mention.end_word]
        text = " ".join(word.text for word in words)
    return {
        "sentence": mention.sentence,
        "start_word": mention.start_word,
        "end_word": mention.end_word,
        "text": text,
        "is_zero": is_zero,
    }


def document_payload(doc) -> dict:
    dependencies: list[dict] = []
    for sentence_index, sentence in enumerate(doc.sentences):
        for word in sentence.words:
            dependencies.append(
                {
                    "sentence": sentence_index,
                    "id": word.id,
                    "text": word.text,
                    "lemma": word.lemma,
                    "upos": word.upos,
                    "feats": word.feats,
                    "head": word.head,
                    "deprel": word.deprel,
                }
            )

    chains = [
        {
            "index": chain.index,
            "representative_text": chain.representative_text,
            "representative_index": chain.representative_index,
            "mentions": [_mention_payload(doc, mention) for mention in chain.mentions],
        }
        for chain in doc.coref
    ]
    return {
        "status": "REVIEW",
        "engine": "stanza",
        "language": "ru",
        "dependencies": dependencies,
        "coreference_chains": chains,
        "automatic_rewrite_allowed": False,
        "note": (
            "Transformer-based semantic challenger output. It is evidence for editorial review, "
            "not a deterministic literary PASS and not an authority over canon. Zero mentions "
            "are preserved explicitly when Stanza emits them."
        ),
    }


def analyze_text(text: str, *, use_gpu: bool = False) -> dict:
    try:
        import stanza
    except ImportError as exc:
        raise RuntimeError(
            "Stanza is not installed. Install the optional tier with: python -m pip install '.[coref]'"
        ) from exc

    try:
        pipeline = stanza.Pipeline(
            "ru",
            processors="tokenize,pos,lemma,depparse,coref",
            download_method=None,
            use_gpu=use_gpu,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise RuntimeError(
            "Russian Stanza models are not available locally. Install them explicitly before "
            "review, for example with stanza.download('ru', "
            "processors='tokenize,pos,lemma,depparse,coref'). The review adapter never "
            "downloads models implicitly."
        ) from exc

    return document_payload(pipeline(text))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Optional Stanza dependency/coreference challenger for Russian prose."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--json", dest="json_output", action="store_true")
    args = parser.parse_args()

    try:
        payload = analyze_text(args.path.read_text(encoding="utf-8"), use_gpu=args.gpu)
    except RuntimeError as exc:
        print(f"STANZA_COREFERENCE_REVIEW: NOT_AVAILABLE: {exc}")
        return 2

    payload["file"] = str(args.path)
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            "STANZA_COREFERENCE_REVIEW: REVIEW "
            f"chains={len(payload['coreference_chains'])} "
            f"dependency_words={len(payload['dependencies'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
