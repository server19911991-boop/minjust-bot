with open('bot.py', 'r') as f:
    content = f.read()

# Находим функции send_question и finish_exam
import re

# Ищем блок send_question
send_pattern = r'# ==================== ОТПРАВКА ВОПРОСА ====================\s+async def send_question.*?(?=# ====================|async def|$)'
send_match = re.search(send_pattern, content, re.DOTALL)

# Ищем блок finish_exam
finish_pattern = r'# ==================== ЗАВЕРШЕНИЕ ЭКЗАМЕНА ====================\s+async def finish_exam.*?(?=# ====================|async def|$)'
finish_match = re.search(finish_pattern, content, re.DOTALL)

if send_match and finish_match:
    send_block = send_match.group(0)
    finish_block = finish_match.group(0)
    
    # Удаляем старые блоки
    content = content.replace(send_block, '')
    content = content.replace(finish_block, '')
    
    # Находим место перед handle_count_choice
    pos = content.find('async def handle_count_choice')
    if pos != -1:
        # Вставляем функции перед handle_count_choice
        content = content[:pos] + send_block + '\n\n' + finish_block + '\n\n' + content[pos:]
        print("✅ send_question и finish_exam перемещены перед handle_count_choice")
    else:
        print("❌ handle_count_choice не найден")
else:
    print("❌ send_question или finish_exam не найдены")

with open('bot.py', 'w') as f:
    f.write(content)
