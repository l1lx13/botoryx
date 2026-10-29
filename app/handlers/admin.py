import re
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database.models import BotListing, Category, Order
from app.database.session import async_session_factory
from app.keyboards.main import (
    admin_menu_keyboard,
    product_admin_actions_keyboard,
    products_keyboard,
)

router = Router()


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in settings.admins


async def deny_access(event: Message | CallbackQuery) -> None:
    text = "⛔ У тебя нет доступа к панели администратора."

    if isinstance(event, CallbackQuery):
        await event.answer("Нет доступа", show_alert=True)
    else:
        await event.answer(text)


class AddCategory(StatesGroup):
    name = State()


class AddProduct(StatesGroup):
    name = State()
    description = State()
    url = State()
    price = State()
    category = State()
    digital_content = State()


@router.message(F.text == "/admin")
async def admin_command(message: Message):
    if not is_admin(message.from_user.id if message.from_user else None):
        await deny_access(message)
        return

    await message.answer(
        "🛠 Панель администратора Botoryx\n\nВыбери действие:",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data == "admin:menu")
async def admin_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await deny_access(callback)
        return

    await state.clear()
    await callback.message.answer(
        "🛠 Панель администратора",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:add_category")
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await deny_access(callback)
        return

    await state.set_state(AddCategory.name)
    await callback.message.answer("Введи название новой категории.")
    await callback.answer()


@router.message(AddCategory.name)
async def add_category_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id if message.from_user else None):
        await state.clear()
        await deny_access(message)
        return

    name = (message.text or "").strip()

    if not name or len(name) > 100:
        await message.answer("Название должно быть от 1 до 100 символов.")
        return

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        slug = f"category-{message.from_user.id}"

    async with async_session_factory() as session:
        existing = await session.scalar(
            select(Category).where(Category.name == name)
        )

        if existing:
            await message.answer("Категория с таким названием уже существует.")
            return

        existing_slug = await session.scalar(
            select(Category).where(Category.slug == slug)
        )

        if existing_slug:
            slug = f"{slug}-{message.from_user.id}"

        session.add(Category(name=name, slug=slug))
        await session.commit()

    await state.clear()
    await message.answer(
        f"✅ Категория «{name}» создана.",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data == "admin:add_product")
async def add_product_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await deny_access(callback)
        return

    async with async_session_factory() as session:
        categories = (
            await session.scalars(select(Category).order_by(Category.name))
        ).all()

    if not categories:
        await callback.message.answer(
            "Сначала создай хотя бы одну категорию через «Добавить категорию»."
        )
        await callback.answer()
        return

    await state.clear()
    await state.set_state(AddProduct.name)
    await callback.message.answer("Шаг 1/6. Введи название товара.")
    await callback.answer()


@router.message(AddProduct.name)
async def product_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id if message.from_user else None):
        await state.clear()
        await deny_access(message)
        return

    name = (message.text or "").strip()

    if not name or len(name) > 150:
        await message.answer("Название должно быть от 1 до 150 символов.")
        return

    await state.update_data(name=name)
    await state.set_state(AddProduct.description)
    await message.answer("Шаг 2/6. Введи описание товара.")


@router.message(AddProduct.description)
async def product_description(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id if message.from_user else None):
        await state.clear()
        await deny_access(message)
        return

    description = (message.text or "").strip()

    if not description or len(description) > 4000:
        await message.answer("Описание должно быть от 1 до 4000 символов.")
        return

    await state.update_data(description=description)
    await state.set_state(AddProduct.url)
    await message.answer(
        "Шаг 3/6. Введи ссылку на Telegram в формате t.me/username.\n"
        "Например: t.me/your_bot (без http:// или https://)"
    )


@router.message(AddProduct.url)
async def product_url(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id if message.from_user else None):
        await state.clear()
        await deny_access(message)
        return

    url = (message.text or "").strip()
    
    # Удаляем http:// или https://, если пользователь их случайно ввёл
    if url.lower().startswith("http://"):
        url = url[7:]
    elif url.lower().startswith("https://"):
        url = url[8:]
        
    url = url.strip()
    
    # Проверяем, что ссылка начинается с t.me/
    if not url.startswith("t.me/"):
        await message.answer(
            "⚠️ Ссылка должна быть в формате t.me/username.\n"
            "Пожалуйста, введи корректную ссылку на Telegram (например, t.me/durov)."
        )
        return

    await state.update_data(url=url)
    await state.set_state(AddProduct.price)
    await message.answer("Шаг 4/6. Введи цену в рублях, например 299.00.")


@router.message(AddProduct.price)
async def product_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id if message.from_user else None):
        await state.clear()
        await deny_access(message)
        return

    raw_price = (message.text or "").strip().replace(",", ".")

    try:
        price = Decimal(raw_price)
        if not price.is_finite() or price <= 0 or price > Decimal("100000000"):
            raise InvalidOperation
        price = price.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        await message.answer("Введи положительную цену, например 299 или 299.50.")
        return

    await state.update_data(price=str(price))
    await state.set_state(AddProduct.category)

    async with async_session_factory() as session:
        categories = (
            await session.scalars(select(Category).order_by(Category.name))
        ).all()

    text = "Шаг 5/6. Введи ID категории из списка:\n\n"
    text += "\n".join(f"{category.id} — {category.name}" for category in categories)
    await message.answer(text)


@router.message(AddProduct.category)
async def product_category(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id if message.from_user else None):
        await state.clear()
        await deny_access(message)
        return

    try:
        category_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введи числовой ID категории.")
        return

    async with async_session_factory() as session:
        category = await session.get(Category, category_id)

    if not category:
        await message.answer("Такой категории нет. Выбери ID из списка.")
        return

    await state.update_data(category_id=category_id)
    await state.set_state(AddProduct.digital_content)
    await message.answer(
        "Шаг 6/6. Введи содержимое для выдачи после оплаты: "
        "ключ, инструкцию или ссылку доступа.\n\n"
        "Не вводи сюда пароль от личного аккаунта или другие секреты. "
        "Пока автоматическая оплата не подключена, товар не будет выдан покупателям."
    )


@router.message(AddProduct.digital_content)
async def product_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id if message.from_user else None):
        await state.clear()
        await deny_access(message)
        return

    content = (message.text or "").strip()

    if not content or len(content) > 10000:
        await message.answer("Содержимое должно быть от 1 до 10000 символов.")
        return

    data = await state.get_data()

    async with async_session_factory() as session:
        product = BotListing(
            name=data["name"],
            description=data["description"],
            url=data["url"],
            price=Decimal(data["price"]),
            currency="RUB",
            category_id=data["category_id"],
            digital_content=content,
            is_published=False,
        )

        session.add(product)
        await session.commit()
        await session.refresh(product)

        product_id = product.id
        product_name = product.name

    await state.clear()
    await message.answer(
        f"✅ Товар «{product_name}» сохранён как черновик.\n"
        f"ID товара: {product_id}\n\n"
        "Опубликуй его через управление товарами после проверки.",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data == "admin:products")
async def admin_products(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await deny_access(callback)
        return

    async with async_session_factory() as session:
        products = (
            await session.scalars(
                select(BotListing).order_by(BotListing.created_at.desc())
            )
        ).all()

    if not products:
        await callback.message.answer("Товаров пока нет.")
    else:
        await callback.message.answer(
            "📦 Товары — выбери карточку:",
            reply_markup=products_keyboard(products),
        )

    await callback.answer()


@router.callback_query(F.data.startswith("admin:product:"))
async def admin_product_details(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await deny_access(callback)
        return

    try:
        product_id = int(callback.data.rsplit(":", 1)[1])
    except (ValueError, AttributeError):
        await callback.answer("Некорректный ID", show_alert=True)
        return

    async with async_session_factory() as session:
        product = await session.get(BotListing, product_id)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    status = "Опубликован" if product.is_published else "Черновик"
    price = f"{product.price} {product.currency}" if product.price is not None else "Не указана"

    await callback.message.answer(
        f"📦 {product.name}\n\n"
        f"ID: {product.id}\n"
        f"Цена: {price}\n"
        f"Статус: {status}\n"
        f"Ссылка: {product.url}\n\n"
        f"{product.description}",
        reply_markup=product_admin_actions_keyboard(
            product.id,
            product.is_published,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:publish:"))
async def publish_product(callback: CallbackQuery):
    await set_product_publication(callback, publish=True)


@router.callback_query(F.data.startswith("admin:hide:"))
async def hide_product(callback: CallbackQuery):
    await set_product_publication(callback, publish=False)


async def set_product_publication(
    callback: CallbackQuery,
    publish: bool,
) -> None:
    if not is_admin(callback.from_user.id):
        await deny_access(callback)
        return

    try:
        product_id = int(callback.data.rsplit(":", 1)[1])
    except (ValueError, AttributeError):
        await callback.answer("Некорректный ID", show_alert=True)
        return

    async with async_session_factory() as session:
        product = await session.get(BotListing, product_id)

        if not product:
            await callback.answer("Товар не найден", show_alert=True)
            return

        product.is_published = publish
        await session.commit()
        name = product.name

    await callback.message.answer(
        f"{'✅ Товар опубликован' if publish else 'Скрытый товар снят с публикации'}: {name}"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:orders")
async def admin_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await deny_access(callback)
        return

    async with async_session_factory() as session:
        orders = (
            await session.scalars(
                select(Order)
                .options(selectinload(Order.product))
                .order_by(Order.created_at.desc())
                .limit(20)
            )
        ).all()

    if not orders:
        await callback.message.answer("Заказов пока нет.")
        await callback.answer()
        return

    lines = ["🧾 Последние заказы:"]
    for order in orders:
        lines.append(
            f"\n№{order.id} — {order.product.name}\n"
            f"Пользователь: {order.telegram_id}\n"
            f"Сумма: {order.amount} {order.currency}\n"
            f"Статус: {order.status}"
        )

    await callback.message.answer("\n".join(lines))
    await callback.answer()