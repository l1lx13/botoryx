from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import func, select
from sqlalchemy import select

from app.handlers.support import notify_new_request
from app.database.models import BotListing, Category, Order, UserRequest
from app.database.session import async_session_factory
from app.keyboards.main import (
    back_to_menu_keyboard,
    categories_keyboard,
    main_menu_keyboard,
    product_keyboard,
)

router = Router()


class UserRequestForm(StatesGroup):
    message = State()


@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "👋 Добро пожаловать в Botoryx!\n\n"
        "Здесь собраны полезные Telegram-боты и цифровые сервисы "
        "для работы, бизнеса и повседневных задач.\n\n"
        "С чего начнём?",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
@router.message(F.text == "💬 Поддержка")
async def help_handler(message: Message):
    await message.answer(
        "ℹ️ Помощь по Botoryx\n\n"
        "📚 Каталог ботов — просмотр доступных сервисов.\n"
        "➕ Предложить бота — отправить предложение для каталога.\n"
        "💬 Поддержка — написать сообщение администрации.\n\n"
        "Выбери действие в меню ниже.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("catalog"))
@router.message(F.text == "📚 Каталог ботов")
async def catalog_handler(message: Message, state: FSMContext):
    await state.clear()

    async with async_session_factory() as session:
        categories = (
            await session.scalars(
                select(Category)
                .join(BotListing)
                .where(BotListing.is_published.is_(True))
                .distinct()
                .order_by(Category.name)
            )
        ).all()

    if not categories:
        await message.answer(
            "📚 Каталог Botoryx\n\n"
            "Пока здесь нет опубликованных ботов.\n"
            "Загляни немного позже!",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        "📚 Каталог Botoryx\n\n"
        "Выбери категорию:",
        reply_markup=categories_keyboard(categories),
    )


@router.callback_query(F.data == "user:catalog")
async def catalog_callback(callback: CallbackQuery):
    async with async_session_factory() as session:
        categories = (
            await session.scalars(
                select(Category)
                .join(BotListing)
                .where(BotListing.is_published.is_(True))
                .distinct()
                .order_by(Category.name)
            )
        ).all()

    if not categories:
        await callback.message.answer(
            "📚 Каталог пока пуст.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await callback.message.answer(
            "📚 Каталог Botoryx\n\nВыбери категорию:",
            reply_markup=categories_keyboard(categories),
        )

    await callback.answer()


@router.callback_query(F.data == "user:menu")
async def menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    await callback.message.answer(
        "🏠 Главное меню\n\nС чего начнём?",
        reply_markup=main_menu_keyboard(),
    )

    await callback.answer()


@router.message(F.text == "🏠 Главное меню")
async def main_menu_handler(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "🏠 Главное меню\n\nС чего начнём?",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("category:"))
async def category_handler(callback: CallbackQuery):
    try:
        category_id = int(callback.data.split(":", 1)[1])
    except (ValueError, AttributeError):
        await callback.answer("Не удалось определить категорию.", show_alert=True)
        return

    async with async_session_factory() as session:
        category = await session.get(Category, category_id)

        products = (
            await session.scalars(
                select(BotListing)
                .where(
                    BotListing.category_id == category_id,
                    BotListing.is_published.is_(True),
                )
                .order_by(BotListing.created_at.desc())
            )
        ).all()

    if category is None:
        await callback.answer("Категория не найдена.", show_alert=True)
        return

    if not products:
        await callback.message.answer(
            f"📚 {category.name}\n\n"
            "В этой категории пока нет опубликованных ботов.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⬅️ К категориям",
                            callback_data="user:catalog",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🏠 Главное меню",
                            callback_data="user:menu",
                        )
                    ],
                ]
            ),
        )
        await callback.answer()
        return

    await callback.message.answer(
        f"📚 Категория: {category.name}\n\n"
        "Вот что удалось найти:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"🤖 {product.name}",
                        callback_data=f"product:{product.id}",
                    )
                ]
                for product in products
            ]
            + [
                [
                    InlineKeyboardButton(
                        text="⬅️ К категориям",
                        callback_data="user:catalog",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="user:menu",
                    )
                ],
            ]
        ),
    )

    await callback.answer()


@router.callback_query(F.data.startswith("product:"))
async def product_handler(callback: CallbackQuery):
    try:
        product_id = int(callback.data.split(":", 1)[1])
    except (ValueError, AttributeError):
        await callback.answer("Не удалось определить товар.", show_alert=True)
        return

    async with async_session_factory() as session:
        product = await session.scalar(
            select(BotListing).where(
                BotListing.id == product_id,
                BotListing.is_published.is_(True),
            )
        )

        if product is None:
            await callback.answer("Этот товар больше недоступен.", show_alert=True)
            return

        name = product.name
        description = product.description
        price = product.price
        currency = product.currency
        url = product.url
        is_published = product.is_published
        saved_product_id = product.id

    price_text = (
        f"{price:.2f} {currency}"
        if price is not None
        else "Уточняется"
    )

    await callback.message.answer(
        f"🤖 {name}\n\n"
        f"{description}\n\n"
        f"💰 Цена: {price_text}\n\n"
        "Выбери, что сделать дальше:",
        reply_markup=product_keyboard(
            type(
                "ProductButtonData",
                (),
                {
                    "id": saved_product_id,
                    "url": url,
                    "is_published": is_published,
                },
            )()
        ),
    )

    await callback.answer()


@router.callback_query(F.data.startswith("buy:"))
async def create_order_handler(callback: CallbackQuery):
    if callback.from_user is None:
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return

    try:
        product_id = int(callback.data.split(":", 1)[1])
    except (ValueError, AttributeError):
        await callback.answer("Некорректный товар.", show_alert=True)
        return

    async with async_session_factory() as session:
        product = await session.scalar(
            select(BotListing).where(
                BotListing.id == product_id,
                BotListing.is_published.is_(True),
            )
        )

        if product is None:
            await callback.answer("Товар больше недоступен.", show_alert=True)
            return

        if product.price is None or product.price <= 0:
            await callback.answer(
                "У этого товара пока не настроена цена.",
                show_alert=True,
            )
            return

        order = Order(
            telegram_id=callback.from_user.id,
            product_id=product.id,
            amount=product.price,
            currency=product.currency,
            status="NEW",
        )

        session.add(order)
        await session.commit()
        await session.refresh(order)

        order_id = order.id
        product_name = product.name
        amount = order.amount
        currency = order.currency

    await callback.message.answer(
        f"🧾 Заказ №{order_id}\n\n"
        f"🤖 Товар: {product_name}\n"
        f"💰 Сумма: {amount:.2f} {currency}\n\n"
        "Заказ создан. Оплата ещё не завершена, поэтому товар пока не выдан.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📚 Вернуться в каталог",
                        callback_data="user:catalog",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="user:menu",
                    )
                ],
            ]
        ),
    )

    await callback.answer()


@router.message(Command("request"))
@router.message(F.text == "➕ Предложить бота")
async def request_start_handler(message: Message, state: FSMContext):
    await state.set_state(UserRequestForm.message)

    await message.answer(
        "➕ Предложить бота\n\n"
        "Расскажи, какого бота или сервис ты хочешь видеть в каталоге.\n"
        "Отправь предложение одним сообщением.",
        reply_markup=back_to_menu_keyboard(),
    )


@router.message(UserRequestForm.message)
async def request_save_handler(message: Message, state: FSMContext):
    if message.text == "🏠 Главное меню":
        await state.clear()
        await main_menu_handler(message, state)
        return

    text = (message.text or "").strip()

    if not text:
        await message.answer("Пожалуйста, отправь текстовое описание предложения.")
        return

    if len(text) > 4000:
        await message.answer("Сообщение слишком длинное. Максимум 4000 символов.")
        return


    async with async_session_factory() as session:
        request = UserRequest(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            message=text,
            status="NEW",
        )

        session.add(request)
        await session.commit()
        await session.refresh(request)

        request_id = request.id
        request_text = request.message

    await notify_new_request(
        bot=message.bot,
        request_id=request_id,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        request_text=request_text,
    )


    await state.clear()

    await message.answer(
        "✅ Спасибо! Твоё предложение сохранено.\n"
        "Администрация сможет рассмотреть его.",
        reply_markup=main_menu_keyboard(),
    )

@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("popular"))
async def popular_handler(message: Message):
    async with async_session_factory() as session:
        products = (
            await session.scalars(
                select(BotListing)
                .where(BotListing.is_published.is_(True))
                .order_by(BotListing.created_at.desc())
                .limit(10)
            )
        ).all()

    if not products:
        await message.answer(
            "🔥 Популярные боты\n\n"
            "Пока нет опубликованных ботов.",
            reply_markup=main_menu_keyboard(),
        )
        return

    buttons = [
        [
            InlineKeyboardButton(
                text=f"🤖 {product.name}",
                callback_data=f"product:{product.id}",
            )
        ]
        for product in products
    ]

    buttons.append([
        InlineKeyboardButton(
            text="📚 Весь каталог",
            callback_data="user:catalog",
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="user:menu",
        )
    ])

    await message.answer(
        "🔥 Популярные боты\n\n"
        "Подборка доступных ботов из каталога:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )