#!/usr/bin/env python3
import json
import os
from datetime import datetime

print("🔄 Начинаем добавление всех вопросов...")

# 1. Делаем резервную копию
backup_name = f"questions_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
if os.path.exists('questions.json'):
    os.rename('questions.json', backup_name)
    print(f"💾 Создана резервная копия: {backup_name}")

# 2. Загружаем существующие вопросы
existing = []
if os.path.exists(backup_name):
    with open(backup_name, 'r', encoding='utf-8') as f:
        existing = json.load(f)
    print(f"📊 Найдено {len(existing)} существующих вопросов")

# 3. Находим максимальный ID
max_id = max([q['id'] for q in existing]) if existing else 0
print(f"📌 Текущий максимальный ID: {max_id}")

# 4. Загружаем файлы с вопросами
def load_questions(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Файл {filename} не найден")
        return []
    except json.JSONDecodeError:
        print(f"❌ Ошибка в JSON файле {filename}")
        return []

legalization_questions = load_questions('Закон о мерах по противодействию.txt')
decree_questions = load_questions('Указ по проверкам.txt')

print(f"📝 Найдено {len(legalization_questions)} вопросов по легализации")
print(f"📝 Найдено {len(decree_questions)} вопросов по проверкам")

# 5. Добавляем вопросы с новыми ID
added = 0
for q in legalization_questions:
    max_id += 1
    q['id'] = max_id
    # Добавляем категорию если её нет
    if 'Блок Проверки и легализация' not in q.get('article', ''):
        q['article'] = q.get('article', '') + ' (Блок Проверки и легализация)'
    existing.append(q)
    added += 1

for q in decree_questions:
    max_id += 1
    q['id'] = max_id
    if 'Блок Проверки и легализация' not in q.get('article', ''):
        q['article'] = q.get('article', '') + ' (Блок Проверки и легализация)'
    existing.append(q)
    added += 1

# 6. Сохраняем
with open('questions.json', 'w', encoding='utf-8') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)

print(f"\n✅ Добавлено {added} вопросов")
print(f"📚 Всего вопросов в базе: {len(existing)}")

# Проверяем результат
legalization_count = len([q for q in existing if 'Проверки и легализация' in q.get('article', '')])
print(f"📊 Всего вопросов с пометкой 'Проверки и легализация': {legalization_count}")

# Дополнительно проверяем количество по каждому файлу
print(f"\n📊 Статистика по категориям:")
print(f"  - Вопросы по легализации: {len(legalization_questions)}")
print(f"  - Вопросы по проверкам: {len(decree_questions)}")
print(f"  - Итого добавлено: {added}")

# Проверяем общее количество вопросов с категориями
categories = {}
for q in existing:
    cat = 'Без категории'
    for marker in ['Конституционное', 'Гражданское', 'Трудовое', 'Лицензирование', 'Проверки', 'Минюста']:
        if marker in q.get('article', ''):
            cat = marker
            break
    categories[cat] = categories.get(cat, 0) + 1

print(f"\n📊 Распределение по категориям:")
for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
    print(f"  - {cat}: {count}")
