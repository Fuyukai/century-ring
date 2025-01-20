import pytest

from century_ring import raise_for_cqe
from century_ring.aio.sidecar import start_uring_sidecar
from century_ring.enums import FileOpenMode

pytestmark = pytest.mark.anyio


async def test_waiting_for_completion_basic():
    async with start_uring_sidecar() as sidecar:
        ud = sidecar.ring.prep_openat(None, b"/dev/zero", FileOpenMode.READ_ONLY)
        result = await sidecar.wait_for_completion(ud)
        raise_for_cqe(result)

        assert result.result >= 0
        assert result.user_data == ud


async def test_waiting_with_failure():
    async with start_uring_sidecar() as sidecar:
        ud = sidecar.ring.prep_openat(None, b"/doesnt-exist", FileOpenMode.READ_ONLY)

        with pytest.raises(OSError):
            await sidecar.wait_for_completion(ud)
