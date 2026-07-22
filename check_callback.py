with open('bot.py', 'r') as f:
    content = f.read()

# Добавляем принудительный вывод callback_data
content = content.replace(
    '''            InlineKeyboardButton(text="📝 20 вопросов", callback_data=f"count_20_{cat_id}"),''',
    '''            InlineKeyboardButton(text="📝 20 вопросов", callback_data=f"count_20_{cat_id}"),'''
)

# Добавляем отладку в handle_count_choice
content = content.replace(
    '''parts = callback.data.split("_")''',
    '''logger.info(f"🔍 ПОЛНЫЙ CALLBACK: {callback.data}")
    parts = callback.data.split("_")'''
)

with open('bot.py', 'w') as f:
    f.write(content)

print("✅ Добавлена отладка callback")
