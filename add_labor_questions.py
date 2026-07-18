#!/usr/bin/env python3
import json
import os
from datetime import datetime

print("🔄 Добавление вопросов по трудовому законодательству...")

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

# 4. Загружаем файл с вопросами
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

labor_questions = load_questions('тесты тк.txt')

print(f"📝 Найдено {len(labor_questions)} вопросов по трудовому законодательству")

# 5. Добавляем вопросы с новыми ID
added = 0

for q in labor_questions:
    max_id += 1
    q['id'] = max_id
    # Убеждаемся, что есть категория
    if 'Блок Трудовое законодательство' not in q.get('article', ''):
        q['article'] = q.get('article', '') + ' (Блок Трудовое законодательство)'
    existing.append(q)
    added += 1

# 6. Сохраняем
with open('questions.json', 'w', encoding='utf-8') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)

print(f"\n✅ Добавлено {added} вопросов")
print(f"📚 Всего вопросов в базе: {len(existing)}")

# Проверяем результат
labor_count = len([q for q in existing if 'Блок Трудовое законодательство' in q.get('article', '')])
print(f"📊 Всего вопросов с пометкой 'Трудовое законодательство': {labor_count}")

# Статистика по категориям
print(f"\n📊 Статистика по категориям:")
print(f"  - Вопросы по трудовому законодательству: {len(labor_questions)}")
print(f"  - Итого добавлено: {added}")

# Общая статистика
categories = {}
for q in existing:
    article = q.get('article', '')
    if 'Конституционное' in article and 'судопроизводство' not in article:
        cat = 'Конституционное право'
    elif 'Гражданское' in article and 'судопроизводство' not in article.lower() and 'процесс' not in article.lower():
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
    elif 'Налоговое' in article or 'уголовное' in article.lower():
        cat = 'Налоговое и уголовное законодательство'
    elif 'Административное' in article:
        cat = 'Административное право'
    elif 'Исполнительное производство' in article:
        cat = 'Исполнительное производство'
    elif 'Банкротство' in article:
        cat = 'Банкротство'
    else:
        cat = 'Другие вопросы'
    categories[cat] = categories.get(cat, 0) + 1

print(f"\n📊 Распределение по категориям:")
for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
    print(f"  - {cat}: {count}")

