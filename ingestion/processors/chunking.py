"""
Advanced chunking strategies for RAG:
- Recursive character splitting
- Semantic chunking
- Parent-child indexing
- Context-aware chunking for documents
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import re

try:
    from langchain.text_splitter import (
        RecursiveCharacterTextSplitter,
        TokenTextSplitter
    )
except ImportError:
    RecursiveCharacterTextSplitter = None
    TokenTextSplitter = None

try:
    import tiktoken
except ImportError:
    tiktoken = None

logger = logging.getLogger(__name__)


class ChunkingStrategy:
    """Base class for chunking strategies."""

    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        """
        Chunk text into smaller pieces.

        Args:
            text: Text to chunk
            metadata: Metadata to attach to each chunk

        Returns:
            List of chunk dictionaries
        """
        raise NotImplementedError


class RecursiveChunker(ChunkingStrategy):
    """
    Recursive character text splitting that respects document structure.
    Tries to split on paragraphs, then sentences, then words.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None
    ):
        """
        Initialize recursive chunker.

        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
            separators: List of separators in order of preference
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        if separators is None:
            # Default separators: paragraph, line, sentence, word
            self.separators = ["\n\n", "\n", ". ", " ", ""]
        else:
            self.separators = separators

        if RecursiveCharacterTextSplitter:
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=self.separators,
                length_function=len
            )
        else:
            self.splitter = None

        logger.info(f"Recursive chunker initialized: size={chunk_size}, overlap={chunk_overlap}")

    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        """Chunk text recursively."""
        if self.splitter:
            chunks_text = self.splitter.split_text(text)
        else:
            # Fallback simple chunking
            chunks_text = self._simple_chunk(text)

        chunks = []
        for idx, chunk_text in enumerate(chunks_text):
            chunk = {
                'content': chunk_text,
                'chunk_index': idx,
                'total_chunks': len(chunks_text),
                'chunk_size': len(chunk_text),
                'chunking_method': 'recursive',
                'metadata': metadata or {}
            }
            chunks.append(chunk)

        logger.info(f"Created {len(chunks)} recursive chunks")
        return chunks

    def _simple_chunk(self, text: str) -> List[str]:
        """Simple fallback chunking."""
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunks.append(text[i:i + self.chunk_size])
        return chunks


class SemanticChunker(ChunkingStrategy):
    """
    Semantic chunking based on meaning similarity.
    Splits text where the semantic meaning changes significantly.
    """

    def __init__(
        self,
        embedding_model: Optional[str] = None,
        similarity_threshold: float = 0.7,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1500
    ):
        """
        Initialize semantic chunker.

        Args:
            embedding_model: Embedding model for similarity
            similarity_threshold: Threshold for splitting (0-1)
            min_chunk_size: Minimum chunk size
            max_chunk_size: Maximum chunk size
        """
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

        logger.info(f"Semantic chunker initialized: threshold={similarity_threshold}")

    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        """
        Chunk text semantically based on sentence similarity.

        Args:
            text: Text to chunk
            metadata: Metadata to attach

        Returns:
            List of semantic chunks
        """
        # Split into sentences
        sentences = self._split_sentences(text)

        if len(sentences) == 0:
            return []

        # For simplicity, use sentence count as proxy for semantic grouping
        # In production, use embeddings to calculate similarity between sentences
        chunks_text = self._group_sentences(sentences)

        chunks = []
        for idx, chunk_text in enumerate(chunks_text):
            chunk = {
                'content': chunk_text,
                'chunk_index': idx,
                'total_chunks': len(chunks_text),
                'chunk_size': len(chunk_text),
                'chunking_method': 'semantic',
                'metadata': metadata or {}
            }
            chunks.append(chunk)

        logger.info(f"Created {len(chunks)} semantic chunks")
        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting (can be improved with spaCy or NLTK)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _group_sentences(self, sentences: List[str]) -> List[str]:
        """
        Group sentences into chunks based on size constraints.

        Args:
            sentences: List of sentences

        Returns:
            List of grouped text chunks
        """
        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence_size = len(sentence)

            if current_size + sentence_size > self.max_chunk_size and current_chunk:
                # Finalize current chunk
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_size = sentence_size
            else:
                current_chunk.append(sentence)
                current_size += sentence_size

            # Also check minimum size
            if current_size >= self.min_chunk_size and len(current_chunk) >= 3:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_size = 0

        # Add remaining
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks


class ParentChildChunker(ChunkingStrategy):
    """
    Parent-child chunking strategy.
    Creates small chunks for retrieval but links them to larger parent chunks
    for context during generation.
    """

    def __init__(
        self,
        child_chunk_size: int = 400,
        parent_chunk_size: int = 2000,
        chunk_overlap: int = 50
    ):
        """
        Initialize parent-child chunker.

        Args:
            child_chunk_size: Size of child chunks (for retrieval)
            parent_chunk_size: Size of parent chunks (for context)
            chunk_overlap: Overlap between chunks
        """
        self.child_chunk_size = child_chunk_size
        self.parent_chunk_size = parent_chunk_size
        self.chunk_overlap = chunk_overlap

        # Create two splitters
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_chunk_size,
            chunk_overlap=chunk_overlap * 2
        ) if RecursiveCharacterTextSplitter else None

        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_size,
            chunk_overlap=chunk_overlap
        ) if RecursiveCharacterTextSplitter else None

        logger.info(f"Parent-child chunker initialized: parent={parent_chunk_size}, child={child_chunk_size}")

    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        """
        Create parent-child chunks.

        Args:
            text: Text to chunk
            metadata: Metadata to attach

        Returns:
            List of child chunks with parent references
        """
        if not self.parent_splitter or not self.child_splitter:
            # Fallback
            return self._fallback_chunk(text, metadata)

        # Create parent chunks
        parent_chunks = self.parent_splitter.split_text(text)

        all_child_chunks = []

        for parent_idx, parent_text in enumerate(parent_chunks):
            # Create child chunks from this parent
            child_texts = self.child_splitter.split_text(parent_text)

            for child_idx, child_text in enumerate(child_texts):
                chunk = {
                    'content': child_text,
                    'parent_content': parent_text,
                    'parent_index': parent_idx,
                    'child_index': child_idx,
                    'total_parents': len(parent_chunks),
                    'total_children': len(child_texts),
                    'chunk_size': len(child_text),
                    'parent_size': len(parent_text),
                    'chunking_method': 'parent_child',
                    'metadata': metadata or {}
                }
                all_child_chunks.append(chunk)

        logger.info(f"Created {len(all_child_chunks)} child chunks from {len(parent_chunks)} parents")
        return all_child_chunks

    def _fallback_chunk(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        """Fallback chunking without langchain."""
        chunks = []
        for i in range(0, len(text), self.child_chunk_size):
            chunk = {
                'content': text[i:i + self.child_chunk_size],
                'chunking_method': 'simple',
                'metadata': metadata or {}
            }
            chunks.append(chunk)
        return chunks


class ContextAwareChunker:
    """
    Context-aware chunking that preserves document structure.
    Respects sections, paragraphs, and logical boundaries.
    """

    def __init__(
        self,
        target_chunk_size: int = 1000,
        preserve_sections: bool = True,
        preserve_paragraphs: bool = True
    ):
        """
        Initialize context-aware chunker.

        Args:
            target_chunk_size: Target size for chunks
            preserve_sections: Whether to preserve section boundaries
            preserve_paragraphs: Whether to preserve paragraph boundaries
        """
        self.target_chunk_size = target_chunk_size
        self.preserve_sections = preserve_sections
        self.preserve_paragraphs = preserve_paragraphs

        logger.info("Context-aware chunker initialized")

    def chunk_document(
        self,
        text: str,
        metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Chunk document while preserving structure.

        Args:
            text: Document text
            metadata: Document metadata

        Returns:
            List of structurally-aware chunks
        """
        # Detect sections (headers)
        sections = self._detect_sections(text)

        chunks = []

        for section_idx, (section_title, section_text) in enumerate(sections):
            # Chunk this section
            if len(section_text) <= self.target_chunk_size:
                # Section fits in one chunk
                chunk = {
                    'content': section_text,
                    'section_title': section_title,
                    'section_index': section_idx,
                    'total_sections': len(sections),
                    'chunking_method': 'context_aware',
                    'metadata': metadata or {}
                }
                chunks.append(chunk)
            else:
                # Split section into multiple chunks
                section_chunks = self._chunk_section(section_text, section_title)
                for chunk_idx, chunk_text in enumerate(section_chunks):
                    chunk = {
                        'content': chunk_text,
                        'section_title': section_title,
                        'section_index': section_idx,
                        'section_chunk_index': chunk_idx,
                        'total_sections': len(sections),
                        'chunking_method': 'context_aware',
                        'metadata': metadata or {}
                    }
                    chunks.append(chunk)

        logger.info(f"Created {len(chunks)} context-aware chunks from {len(sections)} sections")
        return chunks

    def _detect_sections(self, text: str) -> List[Tuple[str, str]]:
        """
        Detect sections in document.

        Args:
            text: Document text

        Returns:
            List of (section_title, section_text) tuples
        """
        # Simple header detection (# Header or uppercase lines)
        sections = []
        current_title = "Introduction"
        current_text = []

        lines = text.split('\n')

        for line in lines:
            # Check if line is a header
            if line.strip().startswith('#'):
                # Save previous section
                if current_text:
                    sections.append((current_title, '\n'.join(current_text)))

                # Start new section
                current_title = line.strip('#').strip()
                current_text = []
            elif line.strip().isupper() and len(line.strip()) < 100:
                # Uppercase line as header
                if current_text:
                    sections.append((current_title, '\n'.join(current_text)))
                current_title = line.strip()
                current_text = []
            else:
                current_text.append(line)

        # Add last section
        if current_text:
            sections.append((current_title, '\n'.join(current_text)))

        # If no sections detected, treat as one section
        if not sections:
            sections = [("Document", text)]

        return sections

    def _chunk_section(self, section_text: str, section_title: str) -> List[str]:
        """
        Chunk a section into smaller pieces.

        Args:
            section_text: Text of the section
            section_title: Title of the section

        Returns:
            List of chunk texts
        """
        if self.preserve_paragraphs:
            # Split by paragraphs
            paragraphs = section_text.split('\n\n')
            chunks = []
            current_chunk = []
            current_size = 0

            for para in paragraphs:
                para_size = len(para)

                if current_size + para_size > self.target_chunk_size and current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = [para]
                    current_size = para_size
                else:
                    current_chunk.append(para)
                    current_size += para_size

            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))

            return chunks
        else:
            # Simple splitting
            chunks = []
            for i in range(0, len(section_text), self.target_chunk_size):
                chunks.append(section_text[i:i + self.target_chunk_size])
            return chunks


# Factory function
def get_chunker(
    strategy: str = "recursive",
    **kwargs
) -> ChunkingStrategy:
    """
    Factory function to get chunking strategy.

    Args:
        strategy: Chunking strategy name
        **kwargs: Strategy-specific parameters

    Returns:
        ChunkingStrategy instance
    """
    if strategy == "recursive":
        return RecursiveChunker(**kwargs)
    elif strategy == "semantic":
        return SemanticChunker(**kwargs)
    elif strategy == "parent_child":
        return ParentChildChunker(**kwargs)
    elif strategy == "context_aware":
        return ContextAwareChunker(**kwargs)
    else:
        raise ValueError(f"Unknown chunking strategy: {strategy}")


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    text = """
    # Shipment Delay Report

    This report covers the Q1 2024 shipment delays in the APAC region.

    ## Executive Summary

    During Q1 2024, we observed a 15% increase in shipment delays compared to Q4 2023.
    The primary causes were port congestion in Singapore and weather disruptions in the Pacific.

    ## Detailed Analysis

    Port congestion in Singapore affected 234 shipments, causing an average delay of 4.5 days.
    Weather disruptions affected 156 shipments, with an average delay of 2.8 days.

    ## Recommendations

    We recommend increasing buffer times for Singapore routes and implementing better weather monitoring.
    """

    # Test recursive chunking
    chunker = get_chunker("recursive", chunk_size=200, chunk_overlap=50)
    chunks = chunker.chunk(text)
    print(f"\nRecursive chunks: {len(chunks)}")

    # Test context-aware chunking
    ca_chunker = ContextAwareChunker(target_chunk_size=300)
    ca_chunks = ca_chunker.chunk_document(text)
    print(f"\nContext-aware chunks: {len(ca_chunks)}")

    for chunk in ca_chunks:
        print(f"\nSection: {chunk['section_title']}")
        print(f"Content: {chunk['content'][:100]}...")
