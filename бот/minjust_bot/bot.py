import asyncio
import json
import logging
import os
import random
import time
import secrets
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# === КЛАСС ЗАЩИТЫ ОТ КОПИРОВАНИЯ ===
class AntiCopyProtection:
    def __init__(self):
        self.screenshot_attempts = defaultdict(int)
        
    def add_watermark(self, text: str, user_id: int, session_id: str = None) -> str:
        """Добавляет водяной знак в сообщение"""
        serial = str(user_id)[-4:]
        session = session_id or secrets.token_hex(4)
        
        watermark = f"\n\n━━━━━━━━━━━━━━━━━━━\n`⚖️ Экзамен Минюста • Сессия: {session}`\n`👤 Пользователь: {serial}`"
        
        # Добавляем невидимые символы для отслеживания
        invisible = f"\u200B{user_id}\u200B{int(time.time())}\u200B{session}\u200B"
        
        return text + watermark + invisible
    
    def check_copied(self, text: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """Проверяет, есть ли водяной знак"""
        if '\u200B' not in text:
            return False, None, None
        
        try:
            parts = text.split('\u200B')
            if len(parts) >= 4:
                user_id = int(parts[1])
                session = parts[3]
                return True, user_id, session
        except:
            pass
        
        return True, None, None

# === КЛАСС УПРАВЛЕНИЯ ДОСТУПОМ ===
class AccessManager:
    def __init__(self):
        self.access_file = "access.json"
        self.pending_requests = {}  # request_id: (user_id, username, full_name, expires)
        self.guest_tokens = {}       # token: (user_id, expires, used)
        self.full_access_users = set()
        self.blocked_users = set()
        self.load_access()
    
    def load_access(self):
        try:
            with open(self.access_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.guest_tokens = {k: tuple(v) for k, v in data.get('guest_tokens', {}).items()}
                self.full_access_users = set(data.get('full_access', []))
                self.blocked_users = set(data.get('blocked', []))
        except FileNotFoundError:
            self.save_access()
    
    def save_access(self):
        guest_tokens_json = {k: list(v) for k, v in self.guest_tokens.items()}
        with open(self.access_file, 'w', encoding='utf-8') as f:
            json.dump({
                'guest_tokens': guest_tokens_json,
                'full_access': list(self.full_access_users),
                'blocked': list(self.blocked_users)
            }, f, ensure_ascii=False, indent=2)
    
    def create_request(self, user_id: int, username: str = None, full_name: str = None) -> str:
        """Создает запрос на гостевой доступ"""
        request_id = secrets.token_hex(4).upper()
        expires = time.time() + 3600  # 1 час
        self.pending_requests[request_id] = (user_id, username, full_name, expires)
        return request_id
    
    def approve_guest(self, request_id: str) -> Optional[str]:
        """Подтверждает гостевой доступ (1 тест)"""
        if request_id not in self.pending_requests:
            return None
        
        user_id, username, full_name, expires = self.pending_requests[request_id]
        
        if expires < time.time():
            del self.pending_requests[request_id]
            return None
        
        # Создаем гостевой токен на 1 тест
        token = secrets.token_hex(8).upper()
        token = '-'.join([token[i:i+4] for i in range(0, len(token), 4)])
        token_expires = time.time() + 7 * 24 * 3600  # 7 дней
        
        self.guest_tokens[token] = (user_id, token_expires, False)
        del self.pending_requests[request_id]
        self.save_access()
        
        return token
    
    def reject_request(self, request_id: str):
        """Отклоняет запрос"""
        if request_id in self.pending_requests:
            del self.pending_requests[request_id]
    
    def grant_full_access(self, user_id: int):
        """Выдает полный доступ"""
        self.full_access_users.add(user_id)
        # Удаляем гостевой токен если был
        tokens_to_remove = []
        for token, (uid, expires, used) in self.guest_tokens.items():
            if uid == user_id:
                tokens_to_remove.append(token)
        for token in tokens_to_remove:
            del self.guest_tokens[token]
        self.save_access()
    
    def check_access(self, user_id: int) -> Tuple[str, Optional[dict]]:
        """Проверяет доступ пользователя"""
        if user_id in ADMIN_IDS:
            return "admin", None
        
        if user_id in self.blocked_users:
            return "blocked", None
        
        if user_id in self.full_access_users:
            return "full", None
        
        for token, (uid, expires, used) in self.guest_tokens.items():
            if uid == user_id:
                if expires < time.time():
                    del self.guest_tokens[token]
                    self.save_access()
                    return "none", None
                
                if used:
                    return "used", None
                
                return "guest", {"token": token, "expires": expires}
        
        return "none", None
    
    def use_guest_token(self, user_id: int) -> bool:
        """Отмечает гостевой токен как использованный"""
        for token, (uid, expires, used) in self.guest_tokens.items():
            if uid == user_id and not used:
                self.guest_tokens[token] = (uid, expires, True)
                self.save_access()
                return True
        return False

# === КЛАСС УПРАВЛЕНИЯ ИНВАЙТАМИ ===
class InviteManager:
    def __init__(self):
        self.invites_file = "invites.json"
        self.invites = {}
        self.load_invites()
    
    def load_invites(self):
        try:
            with open(self.invites_file, 'r', encoding='utf-8') as f:
                self.invites = json.load(f)
        except FileNotFoundError:
            self.save_invites()
    
    def save_invites(self):
        with open(self.invites_file, 'w', encoding='utf-8') as f:
            json.dump(self.invites, f, ensure_ascii=False, indent=2)
    
    def create_invite(self, created_by: int, invite_type: str = "guest", max_uses: int = 1) -> str:
        """Создает инвайт"""
        code = secrets.token_hex(6).upper()
        expires = time.time() + 7 * 24 * 3600  # 7 дней
        
        self.invites[code] = {
            'created_by': created_by,
            'created_at': time.time(),
            'expires': expires,
            'type': invite_type,  # "guest" или "full"
            'max_uses': max_uses,
            'used_by': [],
            'active': True
        }
        
        self.save_invites()
        return code
    
    def use_invite(self, code: str, user_id: int, username: str = None) -> Tuple[bool, str]:
        """Использует инвайт"""
        if code not in self.invites:
            return False, "INVALID"
        
        invite = self.invites[code]
        
        if not invite.get('active', True):
            return False, "INACTIVE"
        
        if invite['expires'] < time.time():
            return False, "EXPIRED"
        
        if len(invite['used_by']) >= invite['max_uses']:
            return False, "LIMIT_REACHED"
        
        invite['used_by'].append({
            'user_id': user_id,
            'username': username,
            'time': time.time()
        })
        
        self.save_invites()
        return True, invite['type']

# === ЗАГРУЗКА ВОПРОСОВ ===
def load_questions():
    try:
        with open('questions.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("Файл questions.json не найден!")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка в JSON файле: {e}")
        return []

questions = load_questions()

# === ОБНОВЛЕННАЯ ФУНКЦИЯ КАТЕГОРИЗАЦИИ С ПРИОРИТЕТОМ ДЛЯ КОНСТИТУЦИИ ===
def categorize_question(question: dict) -> str:
    """
    Определяет блок для вопроса.
    Конституционное право имеет ВЫСШИЙ ПРИОРИТЕТ - все вопросы, связанные с Конституцией,
    попадают в отдельный блок, даже если они упоминают другие кодексы.
    """
    article = question.get('article', '').lower()
    question_text = question.get('question', '').lower()
    
    # === ПРОВЕРКА КОНСТИТУЦИОННОГО ПРАВА (ВЫСШИЙ ПРИОРИТЕТ) ===
    # Список ключевых слов для определения конституционных вопросов
    constitutional_keywords = [
        'конституция', 'конституционного строя', 'конституционный суд',
        'всебелорусское народное собрание', 'всебелорусское', 'референдум',
        'избирательная система', 'избирательное право', 'избирательный кодекс',
        'государственный суверенитет', 'разделение властей', 'президент республики беларусь',
        'президент рб', 'президента', 'гражданство', 'народное собрание',
        'основной закон', 'права и свободы', 'государственный строй',
        'законодательная власть', 'исполнительная власть', 'судебная власть',
        'парламент', 'национальное собрание', 'палата представителей', 'совет республики',
        'правительство', 'совет министров', 'местное управление', 'местное самоуправление',
        'государственный флаг', 'государственный герб', 'государственный гимн',
        'столица', 'государственный язык', 'белорусский язык', 'русский язык'
    ]
    
    # Проверяем статью и текст вопроса на наличие конституционных ключевых слов
    for keyword in constitutional_keywords:
        if keyword in article or keyword in question_text:
            return 'constitutional'
    
    # Если в статье явно указана Конституция
    if 'конституции' in article or 'конституция' in article:
        return 'constitutional'
    
    # === ОСТАЛЬНЫЕ КАТЕГОРИИ (проверяем после конституции) ===
    
    # Проверка по кодексам
    if 'пикоап' in article or 'пик°ап' in article or 'коАП' in article:
        return 'admin'
    
    if 'кгс' in article:
        return 'civil'
    
    if 'ук' in article or 'уголовный кодекс' in article:
        return 'criminal'
    
    if 'тк' in article or 'трудовой кодекс' in article:
        return 'labor'
    
    if 'гк' in article or 'гражданский кодекс' in article:
        return 'civil_law'
    
    # Специфичные законы
    if 'об урегулировании неплатежеспособности' in article or 'банкротство' in article:
        return 'bankrupt'
    
    if 'об исполнительном производстве' in article:
        return 'executive'
    
    # По умолчанию - общие вопросы
    return 'general'

# === ФУНКЦИЯ ДЛЯ СОЗДАНИЯ БЛОКОВ ===
def create_topics_from_questions(questions: List[dict]) -> dict:
    """
    Автоматически создает блоки на основе категоризации вопросов
    """
    if not questions:
        return {}
    
    # Словарь для хранения ID вопросов по категориям
    categorized = {
        'constitutional': [],  # Конституционное право - первый в списке
        'admin': [],
        'civil': [],
        'criminal': [],
        'bankrupt': [],
        'labor': [],
        'civil_law': [],
        'executive': [],
        'general': []
    }
    
    # Категоризируем каждый вопрос
    for q in questions:
        q_id = q.get('id')
        if q_id:
            category = categorize_question(q)
            categorized[category].append(q_id)
    
    # Сортируем ID в каждой категории
    for cat in categorized:
        categorized[cat].sort()
    
    # Создаем структуру блоков
    topics = {}
    
    # Названия блоков с эмодзи (конституционное право первым)
    block_names = {
        'constitutional': {'name': '⚖️ КОНСТИТУЦИОННОЕ ПРАВО', 'emoji': '⚖️'},
        'admin': {'name': '📋 Административное право', 'emoji': '📋'},
        'civil': {'name': '⚖️ Гражданский процесс', 'emoji': '⚖️'},
        'criminal': {'name': '🔒 Уголовное право', 'emoji': '🔒'},
        'bankrupt': {'name': '🏚️ Банкротство', 'emoji': '🏚️'},
        'labor': {'name': '👔 Трудовое право', 'emoji': '👔'},
        'civil_law': {'name': '📘 Гражданское право', 'emoji': '📘'},
        'executive': {'name': '⚙️ Исполнительное производство', 'emoji': '⚙️'},
        'general': {'name': '📚 Общие вопросы', 'emoji': '📚'}
    }
    
    # Для каждой категории определяем информацию
    for cat, ids in categorized.items():
        if ids:  # Если есть вопросы в категории
            topics[cat] = {
                'name': block_names[cat]['name'],
                'emoji': block_names[cat]['emoji'],
                'ids': ids,
                'start': min(ids),
                'end': max(ids),
                'count': len(ids)
            }
    
    # Добавляем режим экзамена (все вопросы)
    if questions:
        all_ids = [q.get('id') for q in questions if q.get('id')]
        topics['exam20'] = {
            'name': '📝 ЭКЗАМЕН (20 вопросов)',
            'emoji': '📝',
            'ids': all_ids,
            'start': min(all_ids) if all_ids else 1,
            'end': max(all_ids) if all_ids else 1,
            'count': len(all_ids)
        }
    
    return topics

# Загружаем вопросы и создаем блоки
questions = load_questions()
TOPICS = create_topics_from_questions(questions)

# Логируем результат для проверки
if TOPICS:
    logging.info("=" * 60)
    logging.info("РАСПРЕДЕЛЕНИЕ ПО БЛОКАМ:")
    logging.info("=" * 60)
    for key, topic in TOPICS.items():
        if key != 'exam20':
            logging.info(f"{topic['name']}: {topic['count']} вопросов (ID {topic['start']}-{topic['end']})")
    logging.info("=" * 60)

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ UI ===
def get_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Создает прогресс-бар"""
    filled = int((current / total) * length)
    return "▓" * filled + "░" * (length - filled)

def get_grade_emoji(percent: float) -> str:
    """Возвращает эмодзи в зависимости от результата"""
    if percent >= 90:
        return "🏆"
    elif percent >= 75:
        return "🌟"
    elif percent >= 60:
        return "📘"
    else:
        return "📚"

# === ФИЛЬТРАЦИЯ ВОПРОСОВ ===
def filter_questions_by_topic(topic_key: str) -> list:
    """Фильтрует вопросы по теме"""
    if topic_key not in TOPICS:
        return []
    
    # Для обычных тем используем список ID
    topic_ids = set(TOPICS[topic_key]['ids'])
    return [q for q in questions if q.get("id") in topic_ids]

def get_random_questions(question_list: list, count: int = 20) -> list:
    """Возвращает случайные вопросы"""
    if len(question_list) <= count:
        return question_list.copy()
    return random.sample(question_list, count)

# === ИНИЦИАЛИЗАЦИЯ ===
protector = AntiCopyProtection()
access_manager = AccessManager()
invite_manager = InviteManager()

# === КЛАВИАТУРЫ ===
def get_main_menu_keyboard(access_type: str) -> InlineKeyboardMarkup:
    """Главное меню в зависимости от типа доступа"""
    buttons = []
    
    if access_type in ["admin", "full"]:
        # Полный доступ - все темы в 2 колонки
        topics_list = [(k, v) for k, v in TOPICS.items() if k != 'exam20']
        
        # Фиксированный порядок блоков: конституционное право первым
        order = ['constitutional', 'admin', 'civil', 'criminal', 'bankrupt', 'labor', 'civil_law', 'executive', 'general']
        topics_list.sort(key=lambda x: order.index(x[0]) if x[0] in order else 999)
        
        for i in range(0, len(topics_list), 2):
            row = []
            # Первая кнопка в ряду
            key1, topic1 = topics_list[i]
            row.append(InlineKeyboardButton(
                text=f"{topic1['emoji']} {topic1['name']} ({topic1['count']})", 
                callback_data=f"topic_{key1}"
            ))
            # Вторая кнопка если есть
            if i + 1 < len(topics_list):
                key2, topic2 = topics_list[i + 1]
                row.append(InlineKeyboardButton(
                    text=f"{topic2['emoji']} {topic2['name']} ({topic2['count']})", 
                    callback_data=f"topic_{key2}"
                ))
            buttons.append(row)
        
        # Добавляем кнопку экзамена
        buttons.append([
            InlineKeyboardButton(text="📝 НАЧАТЬ ЭКЗАМЕН (20 вопросов)", callback_data="exam_general")
        ])
    else:
        # Гостевой доступ - только общий экзамен
        buttons.append([
            InlineKeyboardButton(text="📝 НАЧАТЬ ЭКЗАМЕН (20 вопросов)", callback_data="exam_general")
        ])
    
    # Общие кнопки
    if access_type in ["admin", "full", "guest"]:
        buttons.append([
            InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats"),
            InlineKeyboardButton(text="❓ Помощь", callback_data="help")
        ])
    
    # Для админов кнопка управления
    if access_type == "admin":
        buttons.append([
            InlineKeyboardButton(text="👑 Панель администратора", callback_data="admin_panel")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели"""
    buttons = [
        [
            InlineKeyboardButton(text="📨 Запросы доступа", callback_data="admin_requests"),
            InlineKeyboardButton(text="🔑 Создать инвайт", callback_data="admin_create_invite")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="🚫 Блокировка", callback_data="admin_block_menu")
        ],
        [
            InlineKeyboardButton(text="📝 Пройти экзамен", callback_data="exam_general"),
            InlineKeyboardButton(text="🔄 Перезапуск", callback_data="admin_restart")
        ],
        [
            InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_post_exam_keyboard(has_mistakes: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура после экзамена"""
    buttons = []
    
    if has_mistakes:
        buttons.append([InlineKeyboardButton(text="📝 Работа над ошибками", callback_data="review_mistakes")])
    
    buttons.append([
        InlineKeyboardButton(text="📝 Новый экзамен", callback_data="exam_general"),
        InlineKeyboardButton(text="« В меню", callback_data="back_to_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# === СОСТОЯНИЯ ===
class ExamStates(StatesGroup):
    choosing_topic = State()
    exam_in_progress = State()
    waiting_answer = State()

# === ДАННЫЕ ПОЛЬЗОВАТЕЛЕЙ ===
user_data: Dict[int, dict] = {}

def get_user_data(user_id: int):
    if user_id not in user_data:
        user_data[user_id] = {
            'questions': [],
            'current': 0,
            'score': 0,
            'answers': [],
            'last_answers': [],
            'topic': None,
            'access_type': None,
            'total_tests': 0,
            'session_id': secrets.token_hex(4),
            'last_message_id': None,
            'timer_task': None,
            'last_question_index': -1,
            'current_question': None
        }
    return user_data[user_id]

# === СТАРТ ===
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Очищаем состояние
    await state.clear()
    
    # Отменяем таймер если был
    data = get_user_data(user_id)
    if data.get('timer_task'):
        data['timer_task'].cancel()
        data['timer_task'] = None
    
    # Проверяем, не является ли это инвайт-ссылкой
    args = message.text.split()
    if len(args) > 1:
        invite_code = args[1]
        
        # Проверяем инвайт
        success, result = invite_manager.use_invite(invite_code, user_id, message.from_user.username)
        
        if success:
            if result == "full":
                access_manager.grant_full_access(user_id)
                await message.answer(
                    "🎉 **Инвайт активирован!**\n\n"
                    "Вам выдан **полный доступ** ко всем темам!\n"
                    "Нажмите /start чтобы начать."
                )
            else:  # guest
                # Создаем гостевой токен
                token = secrets.token_hex(8).upper()
                token = '-'.join([token[i:i+4] for i in range(0, len(token), 4)])
                token_expires = time.time() + 7 * 24 * 3600
                access_manager.guest_tokens[token] = (user_id, token_expires, False)
                access_manager.save_access()
                
                await message.answer(
                    "🎉 **Инвайт активирован!**\n\n"
                    "Вам предоставлена **одна попытка** для прохождения экзамена.\n"
                    "Нажмите /start чтобы начать."
                )
            return
        else:
            reasons = {
                "INVALID": "❌ Недействительный код приглашения",
                "EXPIRED": "⌛ Срок действия инвайта истек",
                "LIMIT_REACHED": "⚠️ Инвайт уже использован",
                "INACTIVE": "🚫 Инвайт деактивирован"
            }
            await message.answer(reasons.get(result, "❌ Ошибка активации инвайта"))
            return
    
    # Проверяем доступ
    access_type, access_data = access_manager.check_access(user_id)
    
    if access_type == "blocked":
        await message.answer(
            "🚫 **Доступ заблокирован**\n\nОбратитесь к администратору."
        )
        return
    
    if access_type == "none":
        # Создаем запрос на доступ
        request_id = access_manager.create_request(
            user_id,
            message.from_user.username,
            message.from_user.full_name
        )
        
        await message.answer(
            f"🔐 **Требуется подтверждение доступа**\n\n"
            f"Ваш запрос отправлен администратору.\n"
            f"После подтверждения вы сможете пройти **один** экзамен.\n\n"
            f"ID запроса: `{request_id}`"
        )
        
        # Уведомление админам
        for admin_id in ADMIN_IDS:
            try:
                text = (
                    f"👤 **Новый запрос на доступ**\n\n"
                    f"ID: `{user_id}`\n"
                    f"Username: @{message.from_user.username or 'нет'}\n"
                    f"Имя: {message.from_user.full_name}\n"
                    f"ID запроса: `{request_id}`"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Гостевой доступ", callback_data=f"approve_guest_{request_id}"),
                        InlineKeyboardButton(text="👑 Полный доступ", callback_data=f"grant_full_{user_id}")
                    ],
                    [
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{request_id}")
                    ]
                ])
                await bot.send_message(admin_id, text, reply_markup=keyboard)
            except:
                pass
        
        await state.set_state(ExamStates.choosing_topic)
        return
    
    if access_type == "used":
        await message.answer(
            "⚠️ **Ваша гостевая попытка уже использована**\n\n"
            "Запросите новый доступ у администратора."
        )
        return
    
    # Показываем главное меню
    constitutional_count = TOPICS.get('constitutional', {}).get('count', 0)
    welcome_text = (
        f"👋 **Добро пожаловать!**\n\n"
        f"📚 Всего вопросов в базе: {len(questions)}\n"
        f"⚖️ Вопросов по Конституции: {constitutional_count}\n"
    )
    
    if access_type == "admin":
        welcome_text += "👑 **Вы администратор**\n"
    elif access_type == "full":
        welcome_text += "🌟 **У вас полный доступ**\n"
    elif access_type == "guest":
        welcome_text += "🎯 **У вас гостевая попытка**\n"
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(access_type)
    )
    await state.set_state(ExamStates.choosing_topic)

# === ОБРАБОТКА ЗАПРОСОВ ===
@dp.callback_query(F.data.startswith("approve_guest_"))
async def approve_guest(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    
    request_id = callback.data.replace("approve_guest_", "")
    token = access_manager.approve_guest(request_id)
    
    if token:
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ **Гостевой доступ предоставлен!**"
        )
        await callback.answer("✅ Гость может пройти 1 тест")
    else:
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(F.data.startswith("grant_full_"))
async def grant_full_access(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    
    user_id = int(callback.data.replace("grant_full_", ""))
    access_manager.grant_full_access(user_id)
    
    await callback.message.edit_text(
        callback.message.text + "\n\n👑 **Пользователь получил полный доступ!**"
    )
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            user_id,
            "🌟 **Вам выдан полный доступ!**\n\n"
            "Теперь вам доступны все темы для подготовки.\n"
            "Нажмите /start чтобы начать."
        )
    except:
        pass
    
    await callback.answer("✅ Полный доступ выдан")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_request(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    
    request_id = callback.data.replace("reject_", "")
    access_manager.reject_request(request_id)
    
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ **Запрос отклонен**"
    )

# === АДМИН ПАНЕЛЬ ===
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👑 **Панель администратора**\n\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard()
    )

@dp.callback_query(F.data == "admin_requests")
async def admin_requests(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    
    if not access_manager.pending_requests:
        await callback.message.edit_text(
            "📨 **Нет активных запросов**",
            reply_markup=get_admin_keyboard()
        )
        return
    
    text = "📨 **Ожидающие запросы:**\n\n"
    for rid, (uid, uname, fname, exp) in access_manager.pending_requests.items():
        if exp > time.time():
            text += f"• `{rid}`: {fname} (@{uname})\n"
    
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard())

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    
    total_users = len(set([uid for uid, _ in user_data.items()]))
    total_guests = len(access_manager.guest_tokens)
    total_full = len(access_manager.full_access_users)
    
    text = (
        f"📊 **Статистика бота**\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🎫 Гостевых токенов: {total_guests}\n"
        f"🌟 Полный доступ: {total_full}\n"
        f"📚 Всего вопросов: {len(questions)}\n\n"
        f"📋 **Распределение по блокам:**\n"
    )
    
    for key, topic in TOPICS.items():
        if key != 'exam20':
            text += f"  {topic['emoji']} {topic['name']}: {topic['count']} вопросов\n"
    
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard())

@dp.callback_query(F.data == "admin_block_menu")
async def admin_block_menu(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🚫 **Блокировка пользователя**\n\n"
        "Используйте команду:\n"
        "`/block USER_ID` - заблокировать\n"
        "`/unblock USER_ID` - разблокировать",
        reply_markup=get_admin_keyboard()
    )

@dp.callback_query(F.data == "admin_restart")
async def admin_restart(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    
    await callback.message.edit_text("🔄 **Перезапуск бота...**\n\nБот будет перезапущен через 3 секунды.")
    await callback.answer()
    
    await asyncio.sleep(3)
    os.execl(sys.executable, sys.executable, *sys.argv)

@dp.callback_query(F.data == "admin_create_invite")
async def admin_create_invite(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎫 Гостевой доступ (1 тест)", callback_data="invite_guest"),
            InlineKeyboardButton(text="👑 Полный доступ", callback_data="invite_full")
        ],
        [InlineKeyboardButton(text="« Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(
        "🔑 **Создание инвайт-ссылки**\n\n"
        "Выберите тип доступа для нового пользователя:",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("invite_"))
async def process_invite_type(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    
    invite_type = callback.data.replace("invite_", "")
    code = invite_manager.create_invite(callback.from_user.id, invite_type)
    
    bot_username = (await bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start={code}"
    
    type_text = "🎫 Гостевой (1 тест)" if invite_type == "guest" else "👑 Полный доступ"
    
    await callback.message.edit_text(
        f"🔑 **Инвайт-ссылка создана**\n\n"
        f"📌 **Тип:** {type_text}\n"
        f"📎 **Ссылка:**\n`{invite_link}`\n\n"
        f"📋 **Код:** `{code}`\n"
        f"⏱️ Действителен: 7 дней\n\n"
        f"📤 Отправьте эту ссылку пользователю.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Пройти экзамен", callback_data="exam_general")],
            [InlineKeyboardButton(text="« Назад", callback_data="admin_panel")]
        ])
    )

# === КОМАНДЫ АДМИНА ===
@dp.message(Command("grant_full"))
async def grant_full_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        user_id = int(message.text.split()[1])
        access_manager.grant_full_access(user_id)
        await message.answer(f"✅ Полный доступ выдан пользователю {user_id}")
    except:
        await message.answer("❌ Использование: /grant_full USER_ID")

@dp.message(Command("block"))
async def block_user(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        user_id = int(message.text.split()[1])
        access_manager.blocked_users.add(user_id)
        access_manager.save_access()
        await message.answer(f"🚫 Пользователь {user_id} заблокирован")
    except:
        await message.answer("❌ Использование: /block USER_ID")

@dp.message(Command("unblock"))
async def unblock_user(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        user_id = int(message.text.split()[1])
        if user_id in access_manager.blocked_users:
            access_manager.blocked_users.remove(user_id)
            access_manager.save_access()
        await message.answer(f"✅ Пользователь {user_id} разблокирован")
    except:
        await message.answer("❌ Использование: /unblock USER_ID")

# === ВЫБОР ТЕМЫ ===
@dp.callback_query(F.data.startswith("topic_"))
async def process_topic(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    topic_key = callback.data.replace("topic_", "")
    
    # Проверяем доступ
    access_type, _ = access_manager.check_access(user_id)
    
    if access_type not in ["admin", "full"]:
        await callback.answer("У вас нет доступа к темам", show_alert=True)
        return
    
    # Фильтруем вопросы по теме
    topic_questions = filter_questions_by_topic(topic_key)
    
    if not topic_questions:
        await callback.answer("В этой теме пока нет вопросов", show_alert=True)
        return
    
    # Берем 20 случайных вопросов
    selected = get_random_questions(topic_questions, 20)
    random.shuffle(selected)
    
    data = get_user_data(user_id)
    data['questions'] = selected
    data['current'] = 0
    data['score'] = 0
    data['answers'] = []
    data['last_answers'] = []
    data['topic'] = TOPICS[topic_key]["name"]
    data['access_type'] = access_type
    data['session_id'] = secrets.token_hex(4)
    data['total_tests'] = data.get('total_tests', 0) + 1
    
    await state.set_state(ExamStates.exam_in_progress)
    await callback.message.delete()
    await send_question(callback.message, user_id, state)

# === ОБЩИЙ ЭКЗАМЕН ===
@dp.callback_query(F.data == "exam_general")
async def process_general_exam(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    # Проверяем доступ
    access_type, access_data = access_manager.check_access(user_id)
    
    if access_type == "guest":
        # Гость использует свою попытку
        if not access_manager.use_guest_token(user_id):
            await callback.answer("Ошибка при активации попытки", show_alert=True)
            return
    elif access_type not in ["admin", "full"]:
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    # Берем 20 случайных вопросов из всех
    selected = get_random_questions(questions, 20)
    random.shuffle(selected)
    
    data = get_user_data(user_id)
    data['questions'] = selected
    data['current'] = 0
    data['score'] = 0
    data['answers'] = []
    data['last_answers'] = []
    data['topic'] = "📝 Общий экзамен"
    data['access_type'] = access_type
    data['session_id'] = secrets.token_hex(4)
    data['total_tests'] = data.get('total_tests', 0) + 1
    
    await state.set_state(ExamStates.exam_in_progress)
    await callback.message.delete()
    await send_question(callback.message, user_id, state)

# === ОТПРАВКА ВОПРОСА ===
async def send_question(message: Message, user_id: int, state: FSMContext):
    data = get_user_data(user_id)
    q_index = data['current']
    questions_list = data['questions']
    
    if q_index >= len(questions_list):
        await finish_exam(message, user_id, state)
        return
    
    q = questions_list[q_index]
    correct_count = len(q.get('correct_options', [q.get('correct_option', 0)]))
    
    # Сохраняем данные текущего вопроса
    data['last_question_index'] = q_index
    data['current_question'] = {
        'text': q['question'],
        'correct_options': set(q.get('correct_options', [q.get('correct_option', 0)])),
        'options': q['options']
    }
    
    # Прогресс-бар
    progress = get_progress_bar(q_index, len(questions_list))
    
    # Форматируем варианты
    options_text = "\n".join([
        f"{i+1}. {opt}" 
        for i, opt in enumerate(q['options'])
    ])
    
    text = (
        f"📌 **{data['topic']}**\n"
        f"📊 Прогресс: `{progress}`\n"
        f"❓ **Вопрос {q_index + 1} из {len(questions_list)}**\n\n"
        f"**{q['question']}**\n\n"
        f"{options_text}\n\n"
        f"✨ *Нужно выбрать {correct_count} правильных ответов*\n"
        f"📝 Введите номера через запятую (например: `1,3,4`):"
    )
    
    sent_msg = await message.answer(
        text,
        parse_mode="Markdown"
    )
    
    data['last_message_id'] = sent_msg.message_id
    
    # Запускаем таймер
    task = asyncio.create_task(question_timer(user_id, message, state, 120))
    data['timer_task'] = task

# === ТАЙМЕР ===
async def question_timer(user_id: int, message: Message, state: FSMContext, seconds: int):
    await asyncio.sleep(seconds)
    
    data = get_user_data(user_id)
    current_state = await state.get_state()
    current_q = data['current']
    
    # Проверяем, что это тот же вопрос и состояние активно
    if (current_state == ExamStates.exam_in_progress and 
        current_q < len(data['questions']) and
        data.get('last_question_index') == current_q):
        
        q = data['questions'][current_q]
        correct_options = q.get('correct_options', [q.get('correct_option', 0)])
        correct_nums = [str(i+1) for i in sorted(correct_options)]
        
        await message.answer(
            f"⏰ **Время вышло!**\n\n"
            f"Правильные ответы: `{', '.join(correct_nums)}`"
        )
        
        data['answers'].append({
            'question': q['question'],
            'selected': [],
            'correct': list(correct_options),
            'is_correct': False
        })
        
        data['current'] += 1
        data['timer_task'] = None
        data['current_question'] = None
        await send_question(message, user_id, state)

# === ОБРАБОТКА ОТВЕТА ===
@dp.message(ExamStates.exam_in_progress)
async def process_answer(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = get_user_data(user_id)
    
    # Проверяем, что есть активный вопрос
    if data['current'] >= len(data['questions']):
        await message.answer("❌ Ошибка: тест уже завершен. Начните новый.")
        await cmd_start(message, state)
        return
    
    # Отменяем таймер
    if data.get('timer_task'):
        data['timer_task'].cancel()
        data['timer_task'] = None
    
    q_index = data['current']
    q = data['questions'][q_index]
    
    # Проверяем, что это тот же вопрос (защита от двойных ответов)
    if data.get('last_question_index') != q_index:
        await message.answer("⚠️ Похоже, вы уже ответили на этот вопрос. Переходим к следующему...")
        data['current'] += 1
        await send_question(message, user_id, state)
        return
    
    correct_options = set(q.get('correct_options', [q.get('correct_option', 0)]))
    article = q.get('article', '')
    
    # Парсим ответ
    try:
        # Разделяем по запятой и удаляем пробелы
        numbers = [x.strip() for x in message.text.split(',') if x.strip()]
        selected = set()
        
        for num in numbers:
            try:
                n = int(num)
                if 1 <= n <= len(q['options']):
                    selected.add(n-1)
            except ValueError:
                pass
        
        # Проверяем количество выбранных ответов
        if len(selected) != len(correct_options):
            await message.answer(
                f"⚠️ Нужно выбрать **{len(correct_options)}** ответ(а), а вы выбрали {len(selected)}.\n"
                f"Попробуйте снова (например: `{', '.join([str(i+1) for i in sorted(correct_options)][:3])}...`):"
            )
            # Возвращаем таймер
            task = asyncio.create_task(question_timer(user_id, message, state, 120))
            data['timer_task'] = task
            return
            
    except Exception as e:
        await message.answer("❌ Ошибка ввода. Введите номера через запятую (например: `1,3,4`)")
        task = asyncio.create_task(question_timer(user_id, message, state, 120))
        data['timer_task'] = task
        return
    
    # Проверка правильности
    is_correct = (selected == correct_options)
    
    if is_correct:
        data['score'] += 1
        response = "✅ **Правильно!**\n\n"
    else:
        correct_nums = [str(i+1) for i in sorted(correct_options)]
        correct_texts = [q['options'][i] for i in sorted(correct_options)]
        response = (
            f"❌ **Неправильно.**\n\n"
            f"Правильные ответы: `{', '.join(correct_nums)}`\n"
            f"({', '.join(correct_texts)})\n\n"
        )
    
    if article:
        response += f"📚 Статья: {article}"
    
    await message.answer(response)
    
    # Сохраняем ответ
    data['answers'].append({
        'question': q['question'],
        'selected': list(selected),
        'correct': list(correct_options),
        'is_correct': is_correct
    })
    
    # Переходим к следующему вопросу
    data['current'] += 1
    data['current_question'] = None
    await send_question(message, user_id, state)

# === ЗАВЕРШЕНИЕ ЭКЗАМЕНА ===
async def finish_exam(message: Message, user_id: int, state: FSMContext):
    data = get_user_data(user_id)
    total = len(data['questions'])
    score = data['score']
    percent = (score / total) * 100 if total > 0 else 0
    
    # Сохраняем для работы над ошибками
    data['last_answers'] = data['answers'].copy()
    
    # Проверяем наличие ошибок
    mistakes = [a for a in data['answers'] if not a['is_correct']]
    
    grade_emoji = get_grade_emoji(percent)
    
    text = (
        f"📊 **Экзамен завершен!** {grade_emoji}\n\n"
        f"✅ Правильных ответов: `{score}` из `{total}`\n"
        f"📈 Результат: `{percent:.1f}%`\n\n"
    )
    
    if percent >= 90:
        text += "🏆 **Отлично!** Вы отлично знаете материал!"
    elif percent >= 75:
        text += "🌟 **Хорошо!** Есть небольшие пробелы, но в целом хорошо!"
    elif percent >= 60:
        text += "📘 **Удовлетворительно.** Стоит повторить материал."
    else:
        text += "📚 **Нужно повторить.** Рекомендуем поработать над ошибками."
    
    if mistakes:
        text += f"\n\n📝 Допущено ошибок: {len(mistakes)}"
    
    await message.answer(text)
    
    # Возвращаем в меню
    access_type, _ = access_manager.check_access(user_id)
    await message.answer(
        "Выберите действие:",
        reply_markup=get_post_exam_keyboard(len(mistakes) > 0)
    )
    await state.set_state(ExamStates.choosing_topic)

# === РАБОТА НАД ОШИБКАМИ ===
@dp.callback_query(F.data == "review_mistakes")
async def review_mistakes(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = get_user_data(user_id)
    
    # Берем только неправильные ответы
    mistakes = [a for a in data.get('last_answers', []) if not a['is_correct']]
    
    if not mistakes:
        await callback.answer("🎉 У вас нет ошибок в последнем тесте!", show_alert=True)
        return
    
    # Находим полные вопросы
    mistake_questions = []
    for mistake in mistakes:
        for q in questions:
            if q['question'] == mistake['question']:
                mistake_questions.append(q)
                break
    
    if not mistake_questions:
        await callback.message.answer("❌ Не удалось найти вопросы для повторения")
        return
    
    data['questions'] = mistake_questions
    data['current'] = 0
    data['score'] = 0
    data['answers'] = []
    data['topic'] = "📝 Работа над ошибками"
    data['session_id'] = secrets.token_hex(4)
    
    await state.set_state(ExamStates.exam_in_progress)
    await callback.message.delete()
    await send_question(callback.message, user_id, state)
    await callback.answer(f"📝 Повторяем {len(mistake_questions)} ошибок")

# === СТАТИСТИКА ===
@dp.callback_query(F.data == "my_stats")
async def my_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = get_user_data(user_id)
    access_type, _ = access_manager.check_access(user_id)
    
    text = f"📊 **Ваша статистика**\n\n"
    text += f"📚 Всего тестов: {data.get('total_tests', 0)}\n"
    
    if data['answers']:
        total_answers = len(data['answers'])
        correct = sum(1 for a in data['answers'] if a['is_correct'])
        text += f"✅ Всего ответов: {total_answers}\n"
        text += f"🎯 Точность: {correct/total_answers*100:.1f}%\n"
    
    if access_type == "guest":
        # Показываем статус гостевой попытки
        for token, (uid, expires, used) in access_manager.guest_tokens.items():
            if uid == user_id:
                if used:
                    text += f"\n⚠️ Гостевая попытка: **использована**"
                else:
                    expires_date = datetime.fromtimestamp(expires).strftime('%d.%m.%Y')
                    text += f"\n🎯 Гостевая попытка: **активна** (до {expires_date})"
    
    await callback.message.answer(
        text,
        reply_markup=get_main_menu_keyboard(access_type)
    )

# === ПОМОЩЬ ===
@dp.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    text = (
        "❓ **Помощь**\n\n"
        "**🎯 Типы доступа:**\n"
        "• 🎫 **Гостевой** - 1 попытка общего экзамена\n"
        "• 🌟 **Полный** - все темы, неограниченно\n"
        "• 👑 **Админ** - управление доступом\n\n"
        "**📝 Как отвечать:**\n"
        "• Вводите номера через запятую\n"
        "• Например: `1,3,4`\n"
        "• Порядок не важен\n"
        "• Время на ответ: 120 секунд\n\n"
        "**📊 Функции:**\n"
        "• Прогресс-бар показывает ход теста\n"
        "• После теста можно повторить ошибки\n"
        "• Статистика сохраняется\n\n"
        "**👑 Команды для админов:**\n"
        "/grant_full - выдать полный доступ\n"
        "/block - заблокировать\n"
        "/unblock - разблокировать\n"
        "/restart - перезапустить бота"
    )
    
    await callback.message.answer(text)

# === ВОЗВРАТ В МЕНЮ ===
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    access_type, _ = access_manager.check_access(user_id)
    
    # Отменяем таймер если был
    data = get_user_data(user_id)
    if data.get('timer_task'):
        data['timer_task'].cancel()
        data['timer_task'] = None
    
    await state.set_state(ExamStates.choosing_topic)
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=get_main_menu_keyboard(access_type)
    )

# === КОМАНДА ПЕРЕЗАПУСКА ===
@dp.message(Command("restart"))
async def cmd_restart(message: Message):
    """Перезапускает бота (только для администраторов)"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    await message.answer("🔄 **Перезапуск бота...**\n\nБот будет недоступен несколько секунд.")
    
    await asyncio.sleep(2)
    os.execl(sys.executable, sys.executable, *sys.argv)

# === ОБРАБОТКА НЕИЗВЕСТНЫХ СООБЩЕНИЙ ===
@dp.message()
async def handle_unknown(message: Message, state: FSMContext):
    """Обрабатывает сообщения, которые не попали в другие обработчики"""
    current_state = await state.get_state()
    
    if current_state == ExamStates.exam_in_progress:
        await message.answer(
            "📝 Пожалуйста, введите номера ответов через запятую (например: 1,3,4)"
        )
    else:
        await cmd_start(message, state)

# === ЗАПУСК ===
async def main():
    print("=" * 60)
    print("🚀 ЮРИДИЧЕСКИЙ БОТ ЗАПУЩЕН")
    print("=" * 60)
    
    if not questions:
        print("❌ ОШИБКА: Нет вопросов! Бот не может работать.")
        print("Проверьте наличие файла questions.json")
        return
    
    print(f"👑 Администраторы: {ADMIN_IDS}")
    print(f"📚 Всего вопросов: {len(questions)}")
    print("\n📋 Доступные темы:")
    for key, topic in TOPICS.items():
        if key != 'exam20':
            print(f"  {topic['emoji']} {topic['name']}: {topic['count']} вопросов (ID {topic['start']}-{topic['end']})")
    print("=" * 60)
    print("✅ Система доступа: АКТИВНА")
    print("✅ Инвайт-ссылки: АКТИВНЫ")
    print("=" * 60)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())