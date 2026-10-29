from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Каталог ботов")],
            [KeyboardButton(text="➕ Предложить бота")],
            [KeyboardButton(text="💬 Поддержка")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )


def back_to_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
    )


def categories_keyboard(categories) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=category.name,
                callback_data=f"category:{category.id}",
            )
        ]
        for category in categories
    ]

    rows.append(
        [
            InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="user:menu",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_keyboard(product) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🚀 Открыть бота",
                url=product.url,
            )
        ],
        [
            InlineKeyboardButton(
                text="🛒 Купить",
                callback_data=f"buy:{product.id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="📚 К категориям",
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

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить категорию",
                    callback_data="admin:add_category",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Добавить товар",
                    callback_data="admin:add_product",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📦 Управление товарами",
                    callback_data="admin:products",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧾 Заказы",
                    callback_data="admin:orders",
                )
            ],
        ]
    )


def products_keyboard(products) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=(
                    f"{product.name} — "
                    f"{'Опубликован' if product.is_published else 'Черновик'}"
                ),
                callback_data=f"admin:product:{product.id}",
            )
        ]
        for product in products
    ]

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ В админ-панель",
                callback_data="admin:menu",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_admin_actions_keyboard(
    product_id: int,
    is_published: bool,
) -> InlineKeyboardMarkup:
    action = "hide" if is_published else "publish"
    label = "Снять с публикации" if is_published else "Опубликовать"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"admin:{action}:{product_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ К товарам",
                    callback_data="admin:products",
                )
            ],
        ]
    )