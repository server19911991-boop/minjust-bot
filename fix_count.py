with open('bot.py', 'r') as f:
    content = f.read()

# Находим и исправляем handle_count_choice
import re

# Ищем вызов send_question и исправляем
content = re.sub(
    r'await send_question\(callback\.message,\s*state\)',
    'await send_question(callback.message, user_id, state)',
    content
)

with open('bot.py', 'w') as f:
    f.write(content)

print("✅ Исправлен вызов send_question")
