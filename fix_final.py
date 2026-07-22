with open('bot.py', 'r') as f:
    content = f.read()

# Удаляем debug_callback полностью
import re
content = re.sub(r'# Универсальный обработчик для отладки всех callback\s+@dp\.callback_query\(\s+\)\s+async def debug_callback\(callback: CallbackQuery\):\s+logger\.info\(f"🔍 ВСЕ CALLBACK: \{callback\.data\}"\)\s+logger\.info\(f"🔍 USER: \{callback\.from_user\.id\}"\)\s+# Пропускаем дальше\s+await callback\.continue_propagation\(\)\s+', '', content, flags=re.DOTALL)

# Добавляем правильную отладку в select_category
content = content.replace(
    'async def select_category(callback: CallbackQuery, state: FSMContext):',
    '''async def select_category(callback: CallbackQuery, state: FSMContext):
    logger.info(f"🔍 ВЫБРАНА КАТЕГОРИЯ: {callback.data}")
    logger.info(f"🔍 USER ID: {callback.from_user.id}")
    category_id = callback.data.replace("category_", "")
    logger.info(f"🔍 CATEGORY ID: {category_id}")'''
)

# Добавляем правильную отладку в start_test
content = content.replace(
    'async def start_test(callback: CallbackQuery, state: FSMContext):',
    '''async def start_test(callback: CallbackQuery, state: FSMContext):
    logger.info(f"🔍 ЗАПУСК ТЕСТА: {callback.data}")
    logger.info(f"🔍 USER ID: {callback.from_user.id}")
    category_id = callback.data.replace("start_test_", "")
    logger.info(f"🔍 CATEGORY ID: {category_id}")'''
)

# Добавляем правильную отладку в handle_count_choice
content = content.replace(
    'async def handle_count_choice(callback: CallbackQuery, state: FSMContext):',
    '''async def handle_count_choice(callback: CallbackQuery, state: FSMContext):
    logger.info(f"🔍 ВЫБОР КОЛИЧЕСТВА: {callback.data}")
    logger.info(f"🔍 USER ID: {callback.from_user.id}")
    parts = callback.data.split("_")
    count = int(parts[1])
    category_id = parts[2] if len(parts) > 2 else "all"
    logger.info(f"🔍 COUNT: {count}, CATEGORY: {category_id}")'''
)

with open('bot.py', 'w') as f:
    f.write(content)

print("✅ Исправлено! debug_callback удален, отладка добавлена в обработчики")
