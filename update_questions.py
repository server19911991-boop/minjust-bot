import json

# Читаем questions.json
with open('questions.json', 'r', encoding='utf-8') as f:
    questions = json.load(f)

# Меняем маркеры
count = 0
for q in questions:
    article = q.get('article', '')
    if '(Блок Гражданское судопроизводство)' in article:
        article = article.replace('(Блок Гражданское судопроизводство)', '(Блок Судебный процесс)')
        q['article'] = article
        count += 1

# Сохраняем
with open('questions.json', 'w', encoding='utf-8') as f:
    json.dump(questions, f, ensure_ascii=False, indent=2)

print(f"✅ Обновлено {count} вопросов: маркер изменен на '(Блок Судебный процесс)'")
