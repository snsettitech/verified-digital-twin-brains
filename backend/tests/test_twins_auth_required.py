import pytest
from fastapi import HTTPException

from routers import twins as twins_router


@pytest.mark.asyncio
async def test_list_twins_requires_authenticated_user():
    with pytest.raises(HTTPException) as exc:
        await twins_router.list_twins(user=None)
    assert exc.value.status_code == 401
    assert "Not authenticated" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_create_twin_requires_authenticated_user():
    request = twins_router.TwinCreateRequest(name="Test Twin")
    with pytest.raises(HTTPException) as exc:
        await twins_router.create_twin(request=request, user=None)
    assert exc.value.status_code == 401
    assert "Not authenticated" in str(exc.value.detail)

