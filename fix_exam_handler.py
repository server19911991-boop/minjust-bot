with open('bot.py', 'r') as f:
    content = f.read()

# Проверяем, есть ли обработчик для exam_choose_count
if 'async def choose_count_for_exam' not in content:
    print("❌ Обработчик для экзамена отсутствует! Добавляем...")
    
    exam_handler = '''
@dp.callback_query(F.data == "exam_choose_count")
async def choose_count_for_exam(callback: CallbackQuery, state: FSMContext):
    logger.info(f"🔍 ЭКЗАМЕН: вызов функции choose_count_for_exam")
    logger.info(f"🔍 ЭКЗАМЕН: callback.data = {callback.data}")
    await callback.message.edit_text(
        "📝 **Выберите количество вопросов для экзамена:**",
        reply_markup=get_count_choice_keyboard()
    )
    await state.set_state(ExamStates.choosing_count)
    await callback.answer()
'''
    
    # Вставляем перед другими обработчиками
    pos = content.find('@dp.callback_query(F.data == "back_to_main")')
    if pos != -1:
        content = content[:pos] + exam_handler + '\n' + content[pos:]
        print("✅ Обработчик добавлен перед back_to_main")
    else:
        content = content + exam_handler
        print("✅ Обработчик добавлен в конец")
    
    with open('bot.py', 'w') as f:
        f.write(content)
else:
    print("✅ Обработчик уже есть")
