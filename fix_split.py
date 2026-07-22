with open('bot.py', 'r') as f:
    content = f.read()

# Исправляем разбор category_id - берем все части после count_
content = content.replace(
    '''logger.info(f"🔍 ПОЛНЫЙ CALLBACK: {callback.data}")
    parts = callback.data.split("_")
    count = int(parts[1])
    category_id = parts[2] if len(parts) > 2 else "all"
    logger.info(f"🔍 ВЫБОР КОЛИЧЕСТВА: count={count}, category={category_id}")''',
    '''logger.info(f"🔍 ПОЛНЫЙ CALLBACK: {callback.data}")
    parts = callback.data.split("_")
    count = int(parts[1])
    # Берем ВСЕ части после count_ (начиная с индекса 2)
    if len(parts) > 2:
        category_id = "_".join(parts[2:])
    else:
        category_id = "all"
    logger.info(f"🔍 ВЫБОР КОЛИЧЕСТВА: count={count}, category={category_id}")'''
)

with open('bot.py', 'w') as f:
    f.write(content)

print("✅ Исправлен разбор category_id - теперь берется полный ID")
