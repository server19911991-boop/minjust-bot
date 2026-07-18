#!/usr/bin/env python3
import json
import os

MAIN_FILE = "questions.json"
EXAM_FILE = "Вопросы с экзамена с минюста.txt"
CATEGORY_MARKER = "(Блок Вопросы с экзамена Минюста)"

print("🚀 ДОБАВЛЕНИЕ ВОПРОСОВ С ЭКЗАМЕНА МИНЮСТА")
print("=" * 60)

# Проверяем наличие файлов
if not os.path.exists(MAIN_FILE):
    print(f"❌ Файл {MAIN_FILE} не найден!")
    exit()

if not os.path.exists(EXAM_FILE):
    print(f"❌ Файл {EXAM_FILE} не найден!")
    exit()

# Загружаем основной файл
print(f"📂 Загружаем основной файл: {MAIN_FILE}")
with open(MAIN_FILE, 'r', encoding='utf-8') as f:
    main_questions = json.load(f)

# Загружаем файл с вопросами экзамена
print(f"📂 Загружаем файл с вопросами экзамена: {EXAM_FILE}")
with open(EXAM_FILE, 'r', encoding='utf-8') as f:
    exam_questions = json.load(f)

print(f"\n📚 В основном файле: {len(main_questions)} вопросов")
print(f"📚 В файле экзамена: {len(exam_questions)} вопросов")

# Находим максимальный ID
max_id = max([q.get('id', 0) for q in main_questions]) if main_questions else 0
print(f"\n📌 Последний ID в основном файле: {max_id}")

# Перенумеровываем вопросы экзамена и добавляем маркер, если его нет
for q in exam_questions:
    max_id += 1
    q['id'] = max_id
    
    # Проверяем маркер
    if CATEGORY_MARKER not in q.get('article', ''):
        article = q.get('article', '')
        q['article'] = f"{article} {CATEGORY_MARKER}" if article else CATEGORY_MARKER
    
    # Убираем поле category, если оно есть
    if 'category' in q:
        del q['category']

# Объединяем
main_questions.extend(exam_questions)

# Сохраняем
print(f"\n💾 Сохраняем в {MAIN_FILE}...")
with open(MAIN_FILE, 'w', encoding='utf-8') as f:
    json.dump(main_questions, f, ensure_ascii=False, indent=4)

print("\n" + "=" * 60)
print("✅ ГОТОВО!")
print("=" * 60)
print(f"📚 Всего вопросов в базе: {len(main_questions)}")
print(f"➕ Добавлено вопросов с экзамена: {len(exam_questions)}")

# Подсчет вопросов с маркером
exam_count = sum(1 for q in main_questions if CATEGORY_MARKER in q.get('article', ''))
print(f"📝 Вопросов с маркером '{CATEGORY_MARKER}': {exam_count}")

print(f"\n🔄 Перезапустите бота: Ctrl+C, затем python3 bot.py")
