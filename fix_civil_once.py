with open('bot.py', 'r') as f:
    content = f.read()

# Исправляем handle_count_choice - преобразуем только если ID равен "civil"
content = content.replace(
    '''    if category_id in CATEGORY_MAP:
        logger.info(f"🔍 KEYBOARD: преобразование {category_id} -> {CATEGORY_MAP[category_id]}")
        category_id = CATEGORY_MAP[category_id]''',
    '''    # Преобразуем только если ID равен "civil" (для экзамена)
    if category_id in CATEGORY_MAP and category_id == "civil":
        logger.info(f"🔍 KEYBOARD: преобразование {category_id} -> {CATEGORY_MAP[category_id]}")
        category_id = CATEGORY_MAP[category_id]
    elif category_id in CATEGORY_MAP:
        # Для всех остальных ID оставляем как есть
        logger.info(f"🔍 KEYBOARD: ID {category_id} не преобразуется")'''
)

with open('bot.py', 'w') as f:
    f.write(content)

print("✅ Исправлено! Теперь только 'civil' преобразуется в 'civil_law'")
