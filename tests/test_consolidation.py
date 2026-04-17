import numpy as np

from src.memory.consolidation import _compute_similarity


class TestComputeSimilarity:
    def test_identical_embeddings(self):
        emb = [1.0, 0.0, 0.0]
        assert _compute_similarity(emb, None, emb, None) == pytest.approx(1.0)

    def test_orthogonal_embeddings(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert _compute_similarity(a, None, b, None) == pytest.approx(0.0, abs=1e-6)

    def test_code_embeddings_used(self):
        code_a = [1.0, 0.0]
        code_b = [1.0, 0.0]
        assert _compute_similarity(None, code_a, None, code_b) == pytest.approx(1.0)

    def test_max_of_both(self):
        emb_a = [1.0, 0.0]
        emb_b = [0.0, 1.0]
        code_a = [1.0, 0.0]
        code_b = [1.0, 0.0]
        result = _compute_similarity(emb_a, code_a, emb_b, code_b)
        assert result == pytest.approx(1.0)

    def test_no_embeddings(self):
        assert _compute_similarity(None, None, None, None) == 0.0


import pytest
