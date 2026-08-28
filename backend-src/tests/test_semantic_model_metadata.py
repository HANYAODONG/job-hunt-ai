from __future__ import annotations

import json

from app.services.semantic_ann_service import SemanticANNService


def test_load_index_model_name_from_metadata(tmp_path):
    index_path = tmp_path / "jobs_embeddings.npy"
    metadata_path = tmp_path / "model_metadata.json"
    metadata_path.write_text(
        json.dumps({"model_name": "char-ngram-hashing-768"}),
        encoding="utf-8",
    )

    service = SemanticANNService.__new__(SemanticANNService)
    service.nlp_service = type(
        "StubNLPService",
        (),
        {"active_embedding_model_name": "configured-model"},
    )()

    assert service._load_index_model_name(index_path) == "char-ngram-hashing-768"


def test_load_index_model_name_falls_back_to_active_model(tmp_path):
    service = SemanticANNService.__new__(SemanticANNService)
    service.nlp_service = type(
        "StubNLPService",
        (),
        {"active_embedding_model_name": "char-ngram-hashing-768"},
    )()

    assert service._load_index_model_name(tmp_path / "jobs_embeddings.npy") == "char-ngram-hashing-768"
