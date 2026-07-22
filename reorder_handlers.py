with open('bot.py', 'r') as f:
    content = f.read()

# Находим блоки start_test и count_
import re

# Блок start_test
start_pattern = r'@dp\.callback_query\(F\.data\.startswith\("start_test_"\)\)\s+async def start_test.*?(?=@dp\.callback_query|async def|$)'
start_match = re.search(start_pattern, content, re.DOTALL)

# Блок count_
count_pattern = r'@dp\.callback_query\(F\.data\.startswith\("count_"\)\)\s+async def handle_count_choice.*?(?=@dp\.callback_query|async def|$)'
count_match = re.search(count_pattern, content, re.DOTALL)

if start_match and count_match:
    start_block = start_match.group(0)
    count_block = count_match.group(0)
    
    # Удаляем старые блоки
    content = content.replace(start_block, '')
    content = content.replace(count_block, '')
    
    # Находим первое @dp.callback_query (это category_)
    first_callback = re.search(r'@dp\.callback_query', content)
    if first_callback:
        pos = first_callback.start()
        # Вставляем start_test и count_ после category_
        category_end = content.find('\n', content.find('async def select_category') + 100)
        insert_pos = content.find('@dp.callback_query', category_end)
        if insert_pos == -1:
            insert_pos = pos + 100
        content = content[:insert_pos] + start_block + '\n\n' + count_block + '\n\n' + content[insert_pos:]
        print("✅ start_test и handle_count_choice перемещены после category_")
    else:
        print("❌ Не найден первый callback")
else:
    print("❌ start_test или count_ не найден")

with open('bot.py', 'w') as f:
    f.write(content)
