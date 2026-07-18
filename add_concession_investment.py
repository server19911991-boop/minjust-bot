#!/usr/bin/env python3
import json
import os
from datetime import datetime

print("🔄 Добавление вопросов по концессиям и инвестициям...")

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
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка в JSON файле {filename}: {e}")
        return []

concession_questions = load_questions('Закон о концессиях.txt')
investment_questions = load_questions('Закон об инвестициях.txt')

print(f"📝 Найдено {len(concession_questions)} вопросов по концессиям")
print(f"📝 Найдено {len(investment_questions)} вопросов по инвестициям")

# 5. Добавляем вопросы с новыми ID
added = 0

# Вопросы по концессиям
for q in concession_questions:
    max_id += 1
    q['id'] = max_id
    # Добавляем категорию если её нет
    if 'Блок Концессия и инвестиции' not in q.get('article', ''):
        q['article'] = q.get('article', '') + ' (Блок Концессия и инвестиции)'
    existing.append(q)
    added += 1

# Вопросы по инвестициям
for q in investment_questions:
    max_id += 1
    q['id'] = max_id
    if 'Блок Концессия и инвестиции' not in q.get('article', ''):
        q['article'] = q.get('article', '') + ' (Блок Концессия и инвестиции)'
    existing.append(q)
    added += 1

# 6. Сохраняем
with open('questions.json', 'w', encoding='utf-8') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)

print(f"\n✅ Добавлено {added} вопросов")
print(f"📚 Всего вопросов в базе: {len(existing)}")

# Проверяем результат
concession_count = len([q for q in existing if 'Концессия и инвестиции' in q.get('article', '')])
print(f"📊 Всего вопросов с пометкой 'Концессия и инвестиции': {concession_count}")

# Статистика по категориям
print(f"\n📊 Статистика по категориям:")
print(f"  - Вопросы по концессиям: {len(concession_questions)}")
print(f"  - Вопросы по инвестициям: {len(investment_questions)}")
print(f"  - Итого добавлено: {added}")

# Общая статистика
categories = {}
for q in existing:
    article = q.get('article', '')
    if 'Конституционное' in article:
        cat = 'Конституционное право'
    elif 'Гражданское' in article and 'судопроизводство' not in article.lower():
        cat = 'Гражданское законодательство'
    elif 'Трудовое' in article:
        cat = 'Трудовое законодательство'
    elif 'Лицензирование' in article:
        cat = 'Лицензирование и этика'
    elif 'Проверки' in article or 'легализация' in article:
        cat = 'Проверки и легализация'
    elif 'Минюста' in article:
        cat = 'Вопросы с экзамена Минюста'
    elif 'Гражданское судопроизводство' in article:
        cat = 'Гражданское судопроизводство'
    elif 'Концессия' in article or 'инвестици' in article.lower():
        cat = 'Концессия и инвестиции'
    else:
        cat = 'Другие вопросы'
    categories[cat] = categories.get(cat, 0) + 1

print(f"\n📊 Распределение по категориям:")
for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
    print(f"  - {cat}: {count}")

