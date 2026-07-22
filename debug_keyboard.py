with open('bot.py', 'r') as f:
    content = f.read()

# Добавляем отладку в get_count_choice_keyboard
content = content.replace(
    'def get_count_choice_keyboard(category_id: str = None) -> InlineKeyboardMarkup:',
    '''def get_count_choice_keyboard(category_id: str = None) -> InlineKeyboardMarkup:
    logger.info(f"🔍 KEYBOARD: category_id до преобразования = {category_id}")'''
)

# Добавляем отладку после преобразования
content = content.replace(
    'if category_id in CATEGORY_MAP:\n        category_id = CATEGORY_MAP[category_id]',
    '''if category_id in CATEGORY_MAP:
        logger.info(f"🔍 KEYBOARD: преобразование {category_id} -> {CATEGORY_MAP[category_id]}")
        category_id = CATEGORY_MAP[category_id]
    logger.info(f"🔍 KEYBOARD: category_id после преобразования = {category_id}")'''
)

with open('bot.py', 'w') as f:
    f.write(content)

print("✅ Отладка добавлена в get_count_choice_keyboard!")
