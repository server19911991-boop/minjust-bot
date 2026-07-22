with open('bot.py', 'r') as f:
    content = f.read()

# Меняем название категории в QuestionCategory.CATEGORIES
content = content.replace(
    "'civil_procedure': {\n            'name': 'Гражданское судопроизводство',",
    "'civil_procedure': {\n            'name': 'Судебный процесс',"
)

# Меняем описание
content = content.replace(
    "'description': 'Вопросы по Кодексу гражданского судопроизводства (КГС)',",
    "'description': 'Вопросы по гражданскому процессу (КГС)',"
)

# Меняем маркер для правильной категоризации
content = content.replace(
    "'marker': '(Блок Гражданское судопроизводство)'",
    "'marker': '(Блок Судебный процесс)'"
)

with open('bot.py', 'w') as f:
    f.write(content)

print("✅ Категория переименована: 'Гражданское судопроизводство' -> 'Судебный процесс'")
