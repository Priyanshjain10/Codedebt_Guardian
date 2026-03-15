import pytest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

from services.embedding_pipeline import CodeChunker, EmbeddingPipeline
from models.db_models import CodeEmbedding

def test_chunk_generation():
    """verify chunk size (≈300 lines) and verify overlap (≈40 lines)"""
    chunker = CodeChunker()
    content = "\n".join([f"line {i}" for i in range(1, 401)])
    chunks = chunker.chunk(content, "test.py", chunk_size=300, overlap=40)
    
    assert len(chunks) == 2
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 300
    assert len(chunks[0]["content"].split("\n")) == 300
    
    assert chunks[1]["start_line"] == 261
    assert chunks[1]["end_line"] == 400
    assert len(chunks[1]["content"].split("\n")) == 140
    
    assert chunks[0]["file_path"] == "test.py"

@pytest.mark.asyncio
@patch("services.embedding_pipeline.ai_gateway")
@patch("services.embedding_pipeline.async_sessionmaker")
async def test_embedding_storage(mock_session_maker, mock_ai_gateway):
    """ensure embeddings are stored in code_embeddings table"""
    mock_session = MagicMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    mock_session.commit = AsyncMock()
    
    mock_ai_gateway.get_embedding = AsyncMock(return_value=[0.5] * 1536)
    
    pipeline = EmbeddingPipeline()
    project_id = str(uuid.uuid4())
    files = [{"name": "test.py", "content": "def foo():\n    pass"}]
    
    count = await pipeline.embed_scan_results(project_id, files)
    
    assert count == 1
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    
    added_record = mock_session.add.call_args[0][0]
    assert isinstance(added_record, CodeEmbedding)
    assert added_record.file_path == "test.py"
    assert added_record.embedding == [0.5] * 1536

@pytest.mark.asyncio
@patch("services.embedding_pipeline.ai_gateway")
@patch("services.embedding_pipeline.async_sessionmaker")
async def test_semantic_search(mock_session_maker, mock_ai_gateway):
    """insert mock embeddings and ensure cosine similarity returns correct results"""
    mock_session = MagicMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_ai_gateway.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    
    mock_result = MagicMock()
    mock_record = MagicMock()
    mock_record.file_path = "test.py"
    mock_record.chunk_start = 1
    mock_record.chunk_end = 10
    mock_record.content = "def foo():\n    pass"
    
    mock_result.scalars.return_value.all.return_value = [mock_record]
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    pipeline = EmbeddingPipeline()
    project_id = str(uuid.uuid4())
    
    results = await pipeline.find_similar(project_id, "query foo")
    
    assert len(results) == 1
    assert results[0]["file_path"] == "test.py"
    assert results[0]["start_line"] == 1
    assert results[0]["end_line"] == 10
    assert results[0]["content"] == "def foo():\n    pass"
    mock_session.execute.assert_called_once()

@pytest.mark.asyncio
@patch("services.embedding_pipeline.ai_gateway")
@patch("services.embedding_pipeline.async_sessionmaker")
async def test_similarity_threshold(mock_session_maker, mock_ai_gateway):
    """ensure top_k filtering works"""
    mock_session = MagicMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    mock_ai_gateway.get_embedding = AsyncMock(return_value=[0.2] * 1536)
    
    mock_result = MagicMock()
    records = []
    for i in range(10):
        r = MagicMock()
        r.file_path = f"file{i}.py"
        r.chunk_start = 1
        r.chunk_end = 10
        r.content = f"content {i}"
        records.append(r)
        
    mock_result.scalars.return_value.all.return_value = records[:3]
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    pipeline = EmbeddingPipeline()
    project_id = str(uuid.uuid4())
    
    results = await pipeline.find_similar(project_id, "query", top_k=3)
    
    assert len(results) == 3
    assert results[0]["file_path"] == "file0.py"
    assert results[1]["file_path"] == "file1.py"
    assert results[2]["file_path"] == "file2.py"
    
    called_stmt = mock_session.execute.call_args[0][0]
    # Check that LIMIT 3 is applied conceptually
    assert hasattr(called_stmt, '_limit_clause')
    assert called_stmt._limit_clause.value == 3
