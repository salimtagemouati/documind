import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.ai_service import summarize_document, extract_entities, analyze_sentiment


@pytest.fixture
def mock_gemini_responses():
    """Mock Gemini model responses for AI service tests."""
    with patch("app.services.ai_service._chat_model") as mock_chat, \
         patch("app.services.ai_service._json_model") as mock_json:

        # Text response (for summarization)
        text_resp = MagicMock()
        text_resp.text = "Test Summary of the document."

        # JSON response (for entities and sentiment)
        json_resp = MagicMock()
        json_resp.text = '{"persons": ["John Doe"], "locations": [], "dates": [], "technologies": [], "organizations": [], "monetary_values": [], "other": [], "label": "Positive", "score": 0.9, "confidence": 0.9, "tone": "formal", "explanation": "Good docs"}'

        mock_chat.generate_content_async = AsyncMock(return_value=text_resp)
        mock_json.generate_content_async = AsyncMock(return_value=json_resp)

        yield {"chat": mock_chat, "json": mock_json}


@pytest.mark.asyncio
async def test_summarize_document(mock_gemini_responses):
    chunks = [{"content": "Chunk content"} for _ in range(3)]
    summary = await summarize_document(chunks, "test.pdf")
    assert isinstance(summary, str)
    assert len(summary) > 0


@pytest.mark.asyncio
async def test_map_reduce_summarize(mock_gemini_responses):
    chunks = [{"content": f"Chunk {i}"} for i in range(20)]
    summary = await summarize_document(chunks, "big.pdf")
    assert isinstance(summary, str)
    # Map-reduce triggers for >15 chunks, so multiple calls are made
    assert mock_gemini_responses["chat"].generate_content_async.call_count > 1


@pytest.mark.asyncio
async def test_extract_entities(mock_gemini_responses):
    chunks = [{"content": "Chunk content"}]
    entities = await extract_entities(chunks)
    assert entities.persons == ["John Doe"]
    assert not entities.locations


@pytest.mark.asyncio
async def test_analyze_sentiment(mock_gemini_responses):
    chunks = [{"content": "Chunk content"}]
    sentiment = await analyze_sentiment(chunks, "test.pdf")
    assert sentiment.label == "Positive"
    assert sentiment.score == 0.9
