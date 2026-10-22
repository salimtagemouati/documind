from unittest.mock import MagicMock, patch

import pytest

from app.services.ai_service import (
    analyze_sentiment,
    extract_entities,
    summarize_document,
)


@pytest.fixture
def mock_litellm_responses():
    """Mock LiteLLM responses for AI service tests."""
    with patch("litellm.acompletion") as mock_comp:
        mock_choice = MagicMock()
        mock_choice.message.content = (
            '{"persons": ["John Doe"], "locations": [], "dates": [], "technologies": [], '
            '"organizations": [], "monetary_values": [], "other": [], "label": "Positive", '
            '"score": 0.9, "confidence": 0.9, "tone": "formal", "explanation": "Good docs"}'
        )
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_comp.return_value = mock_resp

        yield mock_comp


@pytest.mark.asyncio
async def test_summarize_document(mock_litellm_responses):
    chunks = [{"content": "Chunk content"} for _ in range(3)]
    summary = await summarize_document(chunks, "test.pdf")
    assert isinstance(summary, str)
    assert len(summary) > 0


@pytest.mark.asyncio
async def test_map_reduce_summarize(mock_litellm_responses):
    chunks = [{"content": f"Chunk {i}"} for i in range(20)]
    summary = await summarize_document(chunks, "big.pdf")
    assert isinstance(summary, str)
    # Map-reduce triggers for >15 chunks, so multiple calls are made
    assert mock_litellm_responses.call_count > 1


@pytest.mark.asyncio
async def test_extract_entities(mock_litellm_responses):
    chunks = [{"content": "Chunk content"}]
    entities = await extract_entities(chunks)
    assert entities.persons == ["John Doe"]
    assert not entities.locations


@pytest.mark.asyncio
async def test_analyze_sentiment(mock_litellm_responses):
    chunks = [{"content": "Chunk content"}]
    sentiment = await analyze_sentiment(chunks, "test.pdf")
    assert sentiment.label == "Positive"
    assert sentiment.score == 0.9
