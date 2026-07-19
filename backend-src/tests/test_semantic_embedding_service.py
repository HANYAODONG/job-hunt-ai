import unittest

from app.services.semantic_embedding_service import SemanticEmbeddingService


class SemanticEmbeddingServiceTests(unittest.TestCase):
    def test_fallback_embedding_and_rerank(self):
        service = SemanticEmbeddingService(model_name="dummy-model")
        texts = [
            "Python backend engineer",
            "Java distributed system developer",
            "Data scientist with machine learning",
        ]
        embeddings = service.encode_texts(texts)
        self.assertEqual(len(embeddings), 3)
        self.assertTrue(all(len(vec) > 0 for vec in embeddings))

        scores = service.rerank_candidates(
            query_text="Python backend developer",
            candidate_texts=[
                "Python backend engineer",
                "Java distributed system developer",
                "Data scientist with machine learning",
            ],
        )
        self.assertEqual(len(scores), 3)
        self.assertEqual(scores[0]["rank"], 1)
        self.assertGreater(scores[0]["score"], scores[1]["score"])


if __name__ == "__main__":
    unittest.main()
