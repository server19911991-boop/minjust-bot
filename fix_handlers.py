with open('bot.py', 'r') as f:
    content = f.read()

# Удаляем debug_callback
import re
content = re.sub(r'# Универсальный обработчик для отладки всех callback\s+@dp\.callback_query\(\s+\)\s+async def debug_callback\(callback: CallbackQuery\):\s+logger\.info\(f"🔍 ВСЕ CALLBACK: \{callback\.data\}"\)\s+logger\.info\(f"🔍 USER: \{callback\.from_user\.id\}"\)\s+# Пропускаем дальше\s+await callback\.continue_propagation\(\)\s+', '', content, flags=re.DOTALL)

# Добавляем отладку в select_category
if 'async def select_category' in content:
    content = content.replace(
        'async def select_category(callback: CallbackQuery, state: FSMContext):',
        '''async def select_category(callback: CallbackQuery, state: FSMContext):
    logger.info(f"🔍 ВЫБРАНА КАТЕГОРИЯ: {callback.data}")
    logger.info(f"🔍 USER ID: {callback.from_user.id}")
    try:
        category_id = callback.data.replace("category_", "")
        logger.info(f"🔍 CATEGORY ID: {category_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка в select_category: {e}")
        await callback.answer("❌ Ошибка при выборе категории", show_alert=True)
        return'''
    )

# Добавляем отладку в start_test
if 'async def start_test' in content:
    content = content.replace(
        'async def start_test(callback: CallbackQuery, state: FSMContext):',
        '''async def start_test(callback: CallbackQuery, state: FSMContext):
    logger.info(f"🔍 ЗАПУСК ТЕСТА: {callback.data}")
    logger.info(f"🔍 USER ID: {callback.from_user.id}")
    try:
        category_id = callback.data.replace("start_test_", "")
        logger.info(f"🔍 CATEGORY ID: {category_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка в start_test: {e}")
        await callback.answer("❌ Ошибка при запуске теста", show_alert=True)
        return'''
    )

# Добавляем отладку в handle_count_choice
if 'async def handle_count_choice' in content:
    content = content.replace(
        'async def handle_count_choice(callback: CallbackQuery, state: FSMContext):',
        '''async def handle_count_choice(callback: CallbackQuery, state: FSMContext):
    logger.info(f"🔍 ВЫБОР КОЛИЧЕСТВА: {callback.data}")
    logger.info(f"🔍 USER ID: {callback.from_user.id}")
    try:
        parts = callback.data.split("_")
        count = int(parts[1])
        category_id = parts[2] if len(parts) > 2 else "all"
        logger.info(f"🔍 COUNT: {count}, CATEGORY: {category_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка в handle_count_choice: {e}")
        await callback.answer("❌ Ошибка при выборе количества", show_alert=True)
        return'''
    )

with open('bot.py', 'w') as f:
    f.write(content)

print("✅ Отладка добавлена в обработчики, debug_callback удален!")
