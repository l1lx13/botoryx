
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.config import settings
from app.database.models import SupportMessage, UserRequest
from app.database.session import async_session_factory


router = Router(name="support")

MENU_TEXTS = {
    "📚 Каталог ботов",
    "➕ Предложить бота",
    "💬 Поддержка",
    "🏠 Главное меню",
}


class SupportReplyState(StatesGroup):
    waiting_for_reply = State()


def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.admins


def ticket_keyboard(ticket_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✍️ Ответить",
        callback_data=f"support:reply:{ticket_id}",
    )
    builder.button(
        text="🔒 Закрыть заявку",
        callback_data=f"support:close:{ticket_id}",
    )
    builder.adjust(1)
    return builder.as_markup()


async def notify_new_request(
    bot: Bot,
    request_id: int,
    telegram_id: int,
    username: str | None,
    request_text: str,
) -> None:
    """Вызвать после сохранения новой заявки в базе."""
    name = f"@{escape(username)}" if username else "не указан"

    text = (
        f"📩 <b>Новая заявка #{request_id}</b>\n\n"
        f"👤 Пользователь: {name}\n"
        f"🆔 Telegram ID: <code>{telegram_id}</code>\n\n"
        f"💬 <b>Сообщение:</b>\n{escape(request_text)}"
    )

    for admin_id in settings.admins:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=ticket_keyboard(request_id),
            )
        except (TelegramForbiddenError, TelegramBadRequest):
            # Например, администратор ещё не запускал бота.
            continue


async def get_ticket(ticket_id: int) -> UserRequest | None:
    async with async_session_factory() as session:
        return await session.get(UserRequest, ticket_id)


@router.callback_query(F.data.startswith("support:reply:"))
async def begin_reply(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    ticket_id = int(callback.data.rsplit(":", 1)[1])
    ticket = await get_ticket(ticket_id)

    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    if ticket.status == "CLOSED":
        await callback.answer("Заявка уже закрыта.", show_alert=True)
        return

    await state.set_state(SupportReplyState.waiting_for_reply)
    await state.update_data(ticket_id=ticket_id)

    await callback.message.answer(
        f"✍️ Напиши ответ для заявки #{ticket_id}.\n\n"
        "Отправь текст следующим сообщением. Для отмены используй /cancel."
    )
    await callback.answer()


@router.message(SupportReplyState.waiting_for_reply, F.text)
async def send_admin_reply(
    message: Message,
    state: FSMContext,
    bot: Bot,
):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Ответ отменён.")
        return

    data = await state.get_data()
    ticket_id = data.get("ticket_id")

    if not ticket_id:
        await state.clear()
        await message.answer("Заявка не выбрана. Нажми «Ответить» ещё раз.")
        return

    async with async_session_factory() as session:
        ticket = await session.get(UserRequest, ticket_id)

        if ticket is None or ticket.status == "CLOSED":
            await state.clear()
            await message.answer("Заявка не найдена или уже закрыта.")
            return

        session.add(
            SupportMessage(
                request_id=ticket.id,
                sender_telegram_id=message.from_user.id,
                is_admin=True,
                text=message.text,
            )
        )
        ticket.status = "IN_PROGRESS"
        recipient_id = ticket.telegram_id
        await session.commit()

    try:
        await bot.send_message(
            chat_id=recipient_id,
            text=(
                f"💬 <b>Ответ поддержки Botoryx по заявке #{ticket_id}</b>\n\n"
                f"{escape(message.text)}\n\n"
                "Можешь ответить на это сообщение — я передам ответ поддержке."
            ),
        )
    except (TelegramForbiddenError, TelegramBadRequest):
        await message.answer(
            "⚠️ Ответ сохранён, но отправить его пользователю не удалось. "
            "Возможно, он заблокировал бота или ещё не запускал его."
        )
        await state.clear()
        return

    await state.clear()
    await message.answer(f"✅ Ответ отправлен пользователю по заявке #{ticket_id}.")


@router.callback_query(F.data.startswith("support:close:"))
async def close_ticket(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    ticket_id = int(callback.data.rsplit(":", 1)[1])

    async with async_session_factory() as session:
        ticket = await session.get(UserRequest, ticket_id)

        if ticket is None:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return

        ticket.status = "CLOSED"
        recipient_id = ticket.telegram_id
        await session.commit()

    try:
        await callback.bot.send_message(
            recipient_id,
            f"🔒 Заявка #{ticket_id} закрыта поддержкой Botoryx. "
            "Если понадобится помощь, отправь новую заявку через меню.",
        )
    except (TelegramForbiddenError, TelegramBadRequest):
        pass

    await callback.answer("Заявка закрыта.")
    if callback.message:
        await callback.message.answer(f"🔒 Заявка #{ticket_id} закрыта.")


@router.message(F.text)
async def receive_user_reply(message: Message, bot: Bot):
    """Принимает обычные текстовые ответы пользователей по открытым заявкам."""
    if message.from_user is None or is_admin(message.from_user.id):
        return

    if message.text.startswith("/") or message.text in MENU_TEXTS:
        return

    async with async_session_factory() as session:
        result = await session.execute(
            select(UserRequest)
            .where(
                UserRequest.telegram_id == message.from_user.id,
                UserRequest.status.in_(["NEW", "IN_PROGRESS"]),
            )
            .order_by(UserRequest.created_at.desc(), UserRequest.id.desc())
            .limit(1)
        )
        ticket = result.scalar_one_or_none()

        if ticket is None:
            return

        session.add(
            SupportMessage(
                request_id=ticket.id,
                sender_telegram_id=message.from_user.id,
                is_admin=False,
                text=message.text,
            )
        )
        ticket_id = ticket.id
        username = message.from_user.username
        await session.commit()

    name = f"@{escape(username)}" if username else "не указан"
    notification = (
        f"📨 <b>Ответ пользователя по заявке #{ticket_id}</b>\n\n"
        f"👤 {name}\n"
        f"🆔 <code>{message.from_user.id}</code>\n\n"
        f"💬 {escape(message.text)}"
    )

    for admin_id in settings.admins:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=notification,
                reply_markup=ticket_keyboard(ticket_id),
            )
        except (TelegramForbiddenError, TelegramBadRequest):
            continue

    await message.answer(
        "✅ Сообщение передано поддержке Botoryx. Можешь продолжать переписку."
    )
