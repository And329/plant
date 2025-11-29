"""Entry point for automation worker V2."""

import asyncio
import logging

from app.workers.automation_worker_v2.worker import AutomationWorkerV2


async def main():
    """Worker entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    worker = AutomationWorkerV2()
    try:
        await worker.start()
    finally:
        if worker.redis is not None:
            await worker.redis.close()


if __name__ == "__main__":
    asyncio.run(main())
