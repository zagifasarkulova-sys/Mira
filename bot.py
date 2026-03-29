import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from database import init_db
from handlers import router
from scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_HOST = os.environ.get("RENDER_EXTERNAL_URL", "")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = int(os.environ.get("PORT", 8080))


async def health_handler(request):
    return web.Response(text="OK")


async def main():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    await init_db()
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook: {WEBHOOK_URL}")

    scheduler = setup_scheduler(bot)
    scheduler.start()

    app = web.Application()
    app.router.add_get("/health", health_handler)

    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Server on port {PORT}")

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()
        await bot.delete_webhook()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
