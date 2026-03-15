"""
CodeDebt Guardian — Code Embedding Pipeline
AST-aware chunking + vector embedding for semantic code search.
"""

import logging
from typing import Dict, List
import uuid
from database import async_sessionmaker
from models.db_models import CodeEmbedding
from services.ai_gateway import ai_gateway

logger = logging.getLogger(__name__)

class CodeChunker:
    """
    Deterministic code chunker.
    Splits code into fixed-size blocks (default 300 lines with 40 lines of overlap).
    """

    def chunk(
        self, content: str, file_path: str, chunk_size: int = 300, overlap: int = 40
    ) -> List[Dict]:
        """
        Chunk a source file deterministically.

        Returns:
            List of {"content": str, "start_line": int, "end_line": int, "file_path": str}
        """
        lines = content.split("\n")
        chunks = []
        step = chunk_size - overlap
        if step < 1:
            step = 1

        for i in range(0, len(lines), step):
            chunk_lines = lines[i : i + chunk_size]
            if not chunk_lines:
                break

            # Avoid emitting tiny tail chunks if they are empty
            if len("\n".join(chunk_lines).strip()) == 0:
                continue

            chunks.append(
                {
                    "content": "\n".join(chunk_lines),
                    "start_line": i + 1,
                    "end_line": min(i + chunk_size, len(lines)),
                    "file_path": file_path,
                }
            )

        return chunks


class EmbeddingPipeline:
    """
    Full embedding pipeline:
    1. Chunk code deterministically
    2. Embed via AI Gateway priority router
    3. Store in pgvector via async_sessionmaker
    """

    def __init__(self):
        self.chunker = CodeChunker()

    async def embed_scan_results(self, project_id: str, files: List[Dict]) -> int:
        """
        Embed code files from a scan into pgvector.

        Args:
            project_id: UUID of the project
            files: List of {"name": str, "content": str}

        Returns:
            Number of embeddings created
        """
        all_chunks = []
        for f in files:
            chunks = self.chunker.chunk(f.get("content", ""), f.get("name", ""))
            all_chunks.extend(chunks)

        if not all_chunks:
            return 0

        logger.info(f"Embedding {len(all_chunks)} code chunks for project {project_id}")

        count = 0
        proj_uuid = uuid.UUID(str(project_id))

        async with async_sessionmaker() as session:
            for chunk in all_chunks:
                try:
                    # AI gateway priority routing handles the embedding
                    vector = await ai_gateway.get_embedding(chunk["content"])

                    record = CodeEmbedding(
                        project_id=proj_uuid,
                        file_path=chunk["file_path"],
                        chunk_start=chunk["start_line"],
                        chunk_end=chunk["end_line"],
                        content=chunk["content"],
                        embedding=vector,
                    )
                    session.add(record)
                    count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to embed chunk in {chunk.get('file_path')}: {e}"
                    )

            await session.commit()

        return count

    async def find_similar(
        self, project_id: str, query: str, top_k: int = 5
    ) -> List[Dict]:
        """
        Find similar code chunks using vector search.
        """
        from sqlalchemy import select

        try:
            query_vector = await ai_gateway.get_embedding(query)
        except Exception as e:
            logger.error(f"Failed to get query embedding: {e}")
            return []

        proj_uuid = uuid.UUID(str(project_id))

        async with async_sessionmaker() as session:
            # Use cosine distance across the pgvector index
            stmt = (
                select(CodeEmbedding)
                .where(CodeEmbedding.project_id == proj_uuid)
                .order_by(CodeEmbedding.embedding.cosine_distance(query_vector))
                .limit(top_k)
            )

            results = await session.execute(stmt)
            records = results.scalars().all()

            return [
                {
                    "file_path": r.file_path,
                    "start_line": r.chunk_start,
                    "end_line": r.chunk_end,
                    "content": r.content,
                }
                for r in records
            ]


# Module-level singleton
embedding_pipeline = EmbeddingPipeline()
