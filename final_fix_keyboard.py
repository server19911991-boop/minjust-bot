with open('bot.py', 'r') as f:
    content = f.read()

# Полностью переписываем get_count_choice_keyboard
content = content.replace(
    '''def get_count_choice_keyboard(category_id: str = None) -> InlineKeyboardMarkup:
    logger.info(f"🔍 KEYBOARD: category_id до преобразования = {category_id}")
    if category_id in CATEGORY_MAP:
        logger.info(f"🔍 KEYBOARD: преобразование {category_id} -> {CATEGORY_MAP[category_id]}")
        category_id = CATEGORY_MAP[category_id]
    logger.info(f"🔍 KEYBOARD: category_id после преобразования = {category_id}")
    cat_id = category_id if category_id and category_id != "all" else "all"
    buttons = [
        [
            InlineKeyboardButton(text="📝 20 вопросов", callback_data=f"count_20_{cat_id}"),
            InlineKeyboardButton(text="📝 50 вопросов", callback_data=f"count_50_{cat_id}")
        ],
        [
            InlineKeyboardButton(text="📝 100 вопросов", callback_data=f"count_100_{cat_id}")
        ],
        [
            InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)''',
    '''def get_count_choice_keyboard(category_id: str = None) -> InlineKeyboardMarkup:
    # Используем полный category_id без обрезания
    if category_id and category_id != "all":
        cat_id = category_id
    else:
        cat_id = "all"
    logger.info(f"🔍 KEYBOARD: category_id = {category_id}, cat_id = {cat_id}")
    buttons = [
        [
            InlineKeyboardButton(text="📝 20 вопросов", callback_data=f"count_20_{cat_id}"),
            InlineKeyboardButton(text="📝 50 вопросов", callback_data=f"count_50_{cat_id}")
        ],
        [
            InlineKeyboardButton(text="📝 100 вопросов", callback_data=f"count_100_{cat_id}")
        ],
        [
            InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)'''
)

with open('bot.py', 'w') as f:
    f.write(content)

print("✅ get_count_choice_keyboard полностью переписана без обрезания ID!")
