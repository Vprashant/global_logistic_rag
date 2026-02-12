"""
Hybrid Retriever combining BM25 (keyword) and semantic (vector) search.
Supports metadata filtering and RBAC.
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Hybrid retrieval engine combining BM25 and semantic search.
    """

    def __init__(
        self,
        vector_db_client,
        semantic_weight: float = 0.7,
        bm25_weight: float = 0.3,
        top_k: int = 5,
        enable_reranking: bool = True
    ):
        """
        Initialize hybrid retriever.

        Args:
            vector_db_client: Vector database client
            semantic_weight: Weight for semantic search (0-1)
            bm25_weight: Weight for BM25 search (0-1)
            top_k: Number of results to return
            enable_reranking: Whether to rerank results
        """
        self.vector_db = vector_db_client
        self.semantic_weight = semantic_weight
        self.bm25_weight = bm25_weight
        self.top_k = top_k
        self.enable_reranking = enable_reranking

        # Normalize weights
        total_weight = semantic_weight + bm25_weight
        self.semantic_weight = semantic_weight / total_weight
        self.bm25_weight = bm25_weight / total_weight

        logger.info(f"Hybrid retriever initialized: semantic={self.semantic_weight:.2f}, bm25={self.bm25_weight:.2f}")

    def search(
        self,
        query: str,
        user_role: Optional[str] = None,
        filters: Optional[Dict] = None,
        top_k: Optional[int] = None
    ) -> List[Dict]:
        """
        Perform hybrid search with RBAC filtering.

        Args:
            query: Search query
            user_role: User role for RBAC filtering
            filters: Additional metadata filters
            top_k: Number of results (overrides default)

        Returns:
            List of search results with scores
        """
        k = top_k or self.top_k

        # Apply RBAC filters
        if user_role:
            filters = filters or {}
            filters['security_clearance'] = self._get_clearance_levels(user_role)

        # Perform semantic search
        semantic_results = self._semantic_search(query, filters, k * 2)

        # Perform BM25 search
        bm25_results = self._bm25_search(query, filters, k * 2)

        # Combine results
        combined_results = self._combine_results(semantic_results, bm25_results)

        # Rerank if enabled
        if self.enable_reranking:
            combined_results = self._rerank(query, combined_results)

        # Return top k
        final_results = combined_results[:k]

        logger.info(f"Retrieved {len(final_results)} results for query: {query[:50]}...")
        return final_results

    def _semantic_search(
        self,
        query: str,
        filters: Optional[Dict],
        k: int
    ) -> List[Dict]:
        """
        Perform semantic vector search.

        Args:
            query: Search query
            filters: Metadata filters
            k: Number of results

        Returns:
            List of results with semantic scores
        """
        try:
            results = self.vector_db.semantic_search(
                query=query,
                filters=filters,
                top_k=k
            )

            # Normalize scores to 0-1 range
            results = self._normalize_scores(results)

            logger.debug(f"Semantic search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []

    def _bm25_search(
        self,
        query: str,
        filters: Optional[Dict],
        k: int
    ) -> List[Dict]:
        """
        Perform BM25 keyword search.

        Args:
            query: Search query
            filters: Metadata filters
            k: Number of results

        Returns:
            List of results with BM25 scores
        """
        try:
            results = self.vector_db.bm25_search(
                query=query,
                filters=filters,
                top_k=k
            )

            # Normalize scores to 0-1 range
            results = self._normalize_scores(results)

            logger.debug(f"BM25 search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"BM25 search error: {e}")
            return []

    def _combine_results(
        self,
        semantic_results: List[Dict],
        bm25_results: List[Dict]
    ) -> List[Dict]:
        """
        Combine semantic and BM25 results using weighted scores.

        Args:
            semantic_results: Results from semantic search
            bm25_results: Results from BM25 search

        Returns:
            Combined and ranked results
        """
        # Create a map of document_id -> combined_score
        score_map = {}
        doc_map = {}

        # Add semantic results
        for result in semantic_results:
            doc_id = result['document_id']
            score_map[doc_id] = result['score'] * self.semantic_weight
            doc_map[doc_id] = result

        # Add BM25 results
        for result in bm25_results:
            doc_id = result['document_id']
            if doc_id in score_map:
                score_map[doc_id] += result['score'] * self.bm25_weight
            else:
                score_map[doc_id] = result['score'] * self.bm25_weight
                doc_map[doc_id] = result

        # Sort by combined score
        sorted_docs = sorted(
            score_map.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Build final results
        combined = []
        for doc_id, combined_score in sorted_docs:
            result = doc_map[doc_id].copy()
            result['combined_score'] = combined_score
            combined.append(result)

        logger.debug(f"Combined {len(combined)} unique results")
        return combined

    def _rerank(
        self,
        query: str,
        results: List[Dict]
    ) -> List[Dict]:
        """
        Rerank results using cross-encoder model.

        Args:
            query: Original query
            results: Combined results

        Returns:
            Reranked results
        """
        try:
            from sentence_transformers import CrossEncoder

            # Initialize cross-encoder (cache it)
            if not hasattr(self, 'reranker'):
                self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

            # Prepare pairs for reranking
            pairs = [(query, result['content']) for result in results]

            # Get reranking scores
            rerank_scores = self.reranker.predict(pairs)

            # Update results with rerank scores
            for result, score in zip(results, rerank_scores):
                result['rerank_score'] = float(score)
                # Combine with original score
                result['final_score'] = (
                    0.7 * result['combined_score'] +
                    0.3 * result['rerank_score']
                )

            # Sort by final score
            results = sorted(results, key=lambda x: x['final_score'], reverse=True)

            logger.debug(f"Reranked {len(results)} results")
            return results

        except ImportError:
            logger.warning("sentence-transformers not available, skipping reranking")
            return results
        except Exception as e:
            logger.error(f"Reranking error: {e}")
            return results

    def _normalize_scores(self, results: List[Dict]) -> List[Dict]:
        """
        Normalize scores to 0-1 range.

        Args:
            results: Search results

        Returns:
            Results with normalized scores
        """
        if not results:
            return results

        scores = [r['score'] for r in results]
        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            # All scores are the same
            for result in results:
                result['score'] = 1.0
        else:
            # Min-max normalization
            for result in results:
                result['score'] = (result['score'] - min_score) / (max_score - min_score)

        return results

    def _get_clearance_levels(self, user_role: str) -> List[str]:
        """
        Get allowed security clearance levels for user role.

        Args:
            user_role: User role

        Returns:
            List of allowed clearance levels
        """
        # Define role-based access
        role_clearance = {
            'admin': ['public', 'internal', 'confidential', 'restricted'],
            'supply_chain_manager': ['public', 'internal', 'confidential'],
            'warehouse_operator': ['public', 'internal'],
            'viewer': ['public']
        }

        clearance = role_clearance.get(user_role, ['public'])
        logger.debug(f"Role {user_role} has clearance: {clearance}")
        return clearance

    def search_with_filters(
        self,
        query: str,
        source_types: Optional[List[str]] = None,
        date_range: Optional[Dict[str, str]] = None,
        regions: Optional[List[str]] = None,
        document_types: Optional[List[str]] = None,
        user_role: Optional[str] = None
    ) -> List[Dict]:
        """
        Search with multiple filter options.

        Args:
            query: Search query
            source_types: Filter by source types (e.g., ['s3', 'database'])
            date_range: Date range filter {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'}
            regions: Filter by regions (e.g., ['APAC', 'EMEA'])
            document_types: Filter by document types
            user_role: User role for RBAC

        Returns:
            Filtered search results
        """
        filters = {}

        if source_types:
            filters['source_type'] = source_types

        if document_types:
            filters['document_type'] = document_types

        if regions:
            filters['region'] = regions

        if date_range:
            filters['date_range'] = date_range

        return self.search(query, user_role=user_role, filters=filters)

    def get_similar_documents(
        self,
        document_id: str,
        top_k: int = 5
    ) -> List[Dict]:
        """
        Find documents similar to a given document.

        Args:
            document_id: ID of the reference document
            top_k: Number of similar documents to return

        Returns:
            List of similar documents
        """
        try:
            # Get the document's embedding
            doc = self.vector_db.get_document(document_id)
            if not doc:
                logger.warning(f"Document {document_id} not found")
                return []

            # Search using the document's embedding
            results = self.vector_db.vector_search(
                embedding=doc['embedding'],
                top_k=top_k + 1  # +1 to exclude the document itself
            )

            # Remove the original document
            results = [r for r in results if r['document_id'] != document_id]

            return results[:top_k]

        except Exception as e:
            logger.error(f"Error finding similar documents: {e}")
            return []


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # Mock vector DB for testing
    class MockVectorDB:
        def semantic_search(self, query, filters, top_k):
            return [
                {'document_id': 'doc1', 'content': 'Shipment delayed', 'score': 0.9},
                {'document_id': 'doc2', 'content': 'Port congestion', 'score': 0.8}
            ]

        def bm25_search(self, query, filters, top_k):
            return [
                {'document_id': 'doc2', 'content': 'Port congestion', 'score': 0.85},
                {'document_id': 'doc3', 'content': 'Weather delay', 'score': 0.75}
            ]

    vector_db = MockVectorDB()
    retriever = HybridRetriever(vector_db)

    # Test search
    results = retriever.search(
        query="What caused the shipment delays?",
        user_role="supply_chain_manager"
    )

    print(f"\nRetrieved {len(results)} results:")
    for result in results:
        print(f"  - {result['document_id']}: {result.get('combined_score', 0):.3f}")
