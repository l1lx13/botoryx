import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from sqlalchemy import text

from app.config import settings
from app.database.models import Base
from app.database.session import engine, close_database
from app.handlers import admin, user
from app.handlers import support

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="catalog", description="Каталог ботов"),
        BotCommand(command="popular", description="Популярные боты"),
        BotCommand(command="request", description="Оставить заявку"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="cancel", description="Отменить действие"),
    ])


async def main() -> None:
    session = AiohttpSession(proxy=settings.proxy_url or None)

    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dispatcher = Dispatcher()
    dispatcher.include_router(admin.router)
    dispatcher.include_router(user.router)
    dispatcher.include_router(support.router)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

            # Добавляем колонку в уже существующую БД, если её ещё нет.
            # CREATE TABLE IF NOT EXISTS сам по себе не меняет старые таблицы.
            await connection.execute(
                text(
                    """
                    ALTER TABLE bot_listings
                    ADD COLUMN IF NOT EXISTS digital_content TEXT
                    """
                )
            )

        await set_commands(bot)

        me = await bot.get_me()
        logger.info("Botoryx запущен: @%s", me.username)

        await bot.delete_webhook(drop_pending_updates=False)

        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )

    except Exception:
        logger.exception("Ошибка при запуске Botoryx")
        raise

    finally:
        await bot.session.close()
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())