import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_eval_report_contract_matches_generated_artifact(async_client: AsyncClient):
    response = await async_client.get("/api/v1/analytics/eval")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"].startswith("in-memory")
    assert payload["parameters"]["cases_evaluated"] == 15
    assert payload["total_cases"] == len(payload["details"])
    assert payload["methodology_version"] == "legacy-v1"
    assert payload["results_validated"] is False
