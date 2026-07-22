with open('bot.py', 'r') as f:
    content = f.read()

# Исправляем start_test - передаем полный category_id
content = content.replace(
    '''await callback.message.edit_text(
        f"{category.emoji} **{category.name}**\\n\\n"
        f"📊 В категории {category.count} вопросов.\\n"
        f"Выберите количество вопросов для теста:",
        reply_markup=get_count_choice_keyboard(category_id)
    )''',
    '''await callback.message.edit_text(
        f"{category.emoji} **{category.name}**\\n\\n"
        f"📊 В категории {category.count} вопросов.\\n"
        f"Выберите количество вопросов для теста:",
        reply_markup=get_count_choice_keyboard(category_id)
    )'''
)

# Добавляем отладку в start_test
content = content.replace(
    'category_id = callback.data.replace("start_test_", "")',
    '''category_id = callback.data.replace("start_test_", "")
    logger.info(f"🔍 START_TEST: category_id = {category_id}")'''
)

with open('bot.py', 'w') as f:
    f.write(content)

print("✅ Добавлена отладка в start_test")
