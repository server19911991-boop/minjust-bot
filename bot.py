"""
ЮРИДИЧЕСКИЙ БОТ ДЛЯ ПОДГОТОВКИ К ЭКЗАМЕНУ МИНЮСТА
Версия 3.0 - ПОЛНОСТЬЮ РАБОЧАЯ
"""

import asyncio
import json
import logging
import os
import random
import secrets
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
)
from dotenv import load_dotenv

# ==================== КОНФИГУРАЦИЯ ====================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [551931619]  # Ваш ID

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== КАРТА КАТЕГОРИЙ ====================
CATEGORY_MAP = {
    'constitutional': 'constitutional',
    'civil': 'civil_law',
    'executive': 'executive_production',
    'criminal': 'criminal_tax_law',
    'admin': 'admin_law',
    'business': 'business_law',
    'bankrupt': 'bankruptcy',
    'concession': 'concession_investment',
    'control': 'control_legalization',
    'licensing': 'licensing_ethics',
    'ministry': 'ministry_exam',
    'labor': 'labor_law',
    'general': 'general'
}

# ==================== СОСТОЯНИЯ ====================
class ExamStates(StatesGroup):
    choosing_category = State()
    choosing_count = State()
    exam_in_progress = State()

# ==================== ДАТА-КЛАССЫ ====================
@dataclass
class Question:
    """Модель вопроса"""
    id: int
    question: str
    options: List[str]
    correct_options: List[int]
    article: str = ""
    category: str = "general"
    explanation: str = ""
    is_from_exam: bool = False

    def get_correct_texts(self) -> List[str]:
        return [self.options[i] for i in self.correct_options]

    def is_correct(self, selected: Set[int]) -> bool:
        return set(self.correct_options) == selected

    def get_correct_numbers(self) -> List[int]:
        return [i + 1 for i in sorted(self.correct_options)]


@dataclass
class Category:
    """Модель категории"""
    id: str
    name: str
    emoji: str
    description: str
    marker: str
    questions: List[int] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.questions)

    @property
    def display_name(self) -> str:
        return f"{self.emoji} {self.name} ({self.count})"


@dataclass
class UserSession:
    """Сессия пользователя"""
    user_id: int
    questions: List[Question] = field(default_factory=list)
    current_index: int = 0
    score: int = 0
    answers: List[dict] = field(default_factory=list)
    category_id: str = ""
    started_at: float = 0
    is_finished: bool = False
    total_attempts: int = 0
    question_count: int = 20
    seen_questions: List[int] = field(default_factory=list)
    all_questions_ids: List[int] = field(default_factory=list)

    def __post_init__(self):
        if not self.started_at:
            self.started_at = time.time()

    @property
    def total_questions(self) -> int:
        return len(self.questions)

    @property
    def progress(self) -> float:
        if not self.questions:
            return 0
        return (self.current_index / len(self.questions)) * 100

    @property
    def current_question(self) -> Optional[Question]:
        if 0 <= self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    @property
    def correct_percent(self) -> float:
        if not self.answers:
            return 0
        correct = sum(1 for a in self.answers if a.get('is_correct', False))
        return (correct / len(self.answers)) * 100


# ==================== УПРАВЛЕНИЕ ИНВАЙТАМИ ====================
class GuestInviteManager:
    def __init__(self):
        self.invites_file = "guest_invites.json"
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

    def create_invite(self, created_by: int, hours: int = 24) -> str:
        code = secrets.token_hex(8).upper()
        code = '-'.join([code[i:i+4] for i in range(0, len(code), 4)])
        expires = time.time() + hours * 3600
        self.invites[code] = {
            'created_by': created_by,
            'created_at': time.time(),
            'expires': expires,
            'hours': hours,
            'used_by': [],
            'active': True,
            'max_uses': 1
        }
        self.save_invites()
        return code


# ==================== КАТЕГОРИИ ВОПРОСОВ ====================
class QuestionCategory:
    CATEGORIES = {
        'constitutional': {
            'name': 'Конституционное право',
            'emoji': '⚖️',
            'description': 'Вопросы по Конституции Республики Беларусь',
            'marker': '(Блок Конституционное право)'
        },
        'civil_law': {
            'name': 'Гражданское законодательство',
            'emoji': '📘',
            'description': 'Вопросы по Гражданскому кодексу (ГК)',
            'marker': '(Блок Гражданское право)'
        },
        'labor_law': {
            'name': 'Трудовое законодательство',
            'emoji': '👔',
            'description': 'Вопросы по Трудовому кодексу (ТК)',
            'marker': '(Блок Трудовое право)'
        },
        'civil_procedure': {
            'name': 'Гражданское судопроизводство',
            'emoji': '⚖️',
            'description': 'Вопросы по Кодексу гражданского судопроизводства (КГС)',
            'marker': '(Блок Гражданское судопроизводство)'
        },
        'executive_production': {
            'name': 'Исполнительное производство',
            'emoji': '⚙️',
            'description': 'Вопросы по Закону об исполнительном производстве',
            'marker': '(Блок Исполнительное производство)'
        },
        'criminal_tax_law': {
            'name': 'Налоговое и уголовное законодательство',
            'emoji': '🔒',
            'description': 'Вопросы по УК и НК',
            'marker': '(Блок Налоговое и уголовное законодательство)'
        },
        'admin_law': {
            'name': 'Административное право',
            'emoji': '📋',
            'description': 'Вопросы по КоАП и ПИКоАП',
            'marker': '(Блок Административное право)'
        },
        'business_law': {
            'name': 'Закон о хозяйственных обществах',
            'emoji': '🏢',
            'description': 'Вопросы по Закону о хозяйственных обществах',
            'marker': '(Блок Закон о хозяйственных обществах)'
        },
        'bankruptcy': {
            'name': 'Банкротство',
            'emoji': '🏚️',
            'description': 'Вопросы по Закону о банкротстве',
            'marker': '(Блок Банкротство)'
        },
        'concession_investment': {
            'name': 'Концессия и инвестиции',
            'emoji': '💼',
            'description': 'Вопросы по Законам о концессиях и инвестициях',
            'marker': '(Блок Концессия и инвестиции)'
        },
        'control_legalization': {
            'name': 'Проверки и легализация',
            'emoji': '🔍',
            'description': 'Вопросы по Закону о легализации и Указу о проверках',
            'marker': '(Блок Проверки и легализация)'
        },
        'licensing_ethics': {
            'name': 'Лицензирование и этика',
            'emoji': '📜',
            'description': 'Вопросы по лицензированию, правилам и этике',
            'marker': '(Блок Лицензирование и этика)'
        },
        'ministry_exam': {
            'name': 'Вопросы с экзамена Минюста',
            'emoji': '📝',
            'description': 'Вопросы, которые были на реальных экзаменах в Министерстве юстиции',
            'marker': '(Блок Вопросы с экзамена Минюста)'
        }
    }

    @classmethod
    def categorize_question(cls, question: dict) -> str:
        article = question.get('article', '')
        for cat_id, data in cls.CATEGORIES.items():
            marker = data['marker']
            if marker.lower() in article.lower():
                return cat_id
        return 'general'


# ==================== ЗАГРУЗЧИК ВОПРОСОВ ====================
class QuestionLoader:
    def __init__(self):
        self.questions: List[Question] = []
        self.categories: Dict[str, Category] = {}
        self._load_questions()
        self._build_categories()

    def _load_questions(self):
        try:
            with open('questions.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    category = QuestionCategory.categorize_question(item)
                    question = Question(
                        id=item.get('id', 0),
                        question=item.get('question', ''),
                        options=item.get('options', []),
                        correct_options=item.get('correct_options', []),
                        article=item.get('article', ''),
                        category=category,
                        explanation=item.get('explanation', ''),
                        is_from_exam=item.get('is_from_exam', False)
                    )
                    self.questions.append(question)
            logger.info(f"✅ Загружено {len(self.questions)} вопросов")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки вопросов: {e}")
            self.questions = []

    def _build_categories(self):
        for cat_id, data in QuestionCategory.CATEGORIES.items():
            self.categories[cat_id] = Category(
                id=cat_id,
                name=data['name'],
                emoji=data['emoji'],
                description=data['description'],
                marker=data['marker'],
                questions=[]
            )
        for question in self.questions:
            if question.category in self.categories:
                self.categories[question.category].questions.append(question.id)
            else:
                if 'general' not in self.categories:
                    self.categories['general'] = Category(
                        id='general',
                        name='Общие вопросы',
                        emoji='📚',
                        description='Вопросы без четкой категории',
                        marker='',
                        questions=[]
                    )
                self.categories['general'].questions.append(question.id)
        logger.info("📊 Категории загружены")

    def get_questions_by_category(self, category_id: str, limit: int = 20) -> List[Question]:
        if category_id not in self.categories:
            return []
        question_ids = self.categories[category_id].questions
        if not question_ids:
            return []
        selected_ids = random.sample(question_ids, min(limit, len(question_ids)))
        return [q for q in self.questions if q.id in selected_ids]

    def get_all_questions(self, limit: int = 20) -> List[Question]:
        if not self.questions:
            return []
        return random.sample(self.questions, min(limit, len(self.questions)))

    def get_questions_for_category(self, category_id: str, seen_ids: List[int], limit: int = 20, allow_repeat: bool = False) -> List[Question]:
        if allow_repeat or category_id == "exam":
            return self.get_questions_by_category(category_id, limit)
        if category_id not in self.categories:
            return []
        all_ids = self.categories[category_id].questions
        unseen_ids = [q_id for q_id in all_ids if q_id not in seen_ids]
        if not unseen_ids:
            return self.get_questions_by_category(category_id, limit)
        selected_ids = random.sample(unseen_ids, min(limit, len(unseen_ids)))
        return [q for q in self.questions if q.id in selected_ids]


# ==================== ДАННЫЕ ПОЛЬЗОВАТЕЛЕЙ ====================
user_sessions: Dict[int, UserSession] = {}
guest_invite_manager = GuestInviteManager()

def get_user_session(user_id: int) -> UserSession:
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id=user_id)
    return user_sessions[user_id]


# ==================== ИНИЦИАЛИЗАЦИЯ ====================
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
question_loader = QuestionLoader()


# ==================== КЛАВИАТУРЫ ====================
def get_main_menu_keyboard(user_id: int = None) -> InlineKeyboardMarkup:
    buttons = []
    categories = []
    for cat_id, category in question_loader.categories.items():
        if category.count > 0 and cat_id != 'general':
            categories.append((cat_id, category))
    categories.sort(key=lambda x: x[1].count, reverse=True)

    for i in range(0, len(categories), 2):
        row = []
        cat_id, category = categories[i]
        row.append(InlineKeyboardButton(
            text=category.display_name,
            callback_data=f"category_{cat_id}"
        ))
        if i + 1 < len(categories):
            cat_id2, category2 = categories[i + 1]
            row.append(InlineKeyboardButton(
                text=category2.display_name,
                callback_data=f"category_{cat_id2}"
            ))
        buttons.append(row)

    if question_loader.questions:
        buttons.append([
            InlineKeyboardButton(
                text="📝 ЭКЗАМЕН (выбрать количество)",
                callback_data="exam_choose_count"
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats"),
        InlineKeyboardButton(text="🔄 Сбросить прогресс", callback_data="reset_progress"),
    ])
    buttons.append([
        InlineKeyboardButton(text="❓ Помощь", callback_data="help")
    ])

    if user_id and user_id in ADMIN_IDS:
        buttons.append([
            InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_panel")
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_count_choice_keyboard(category_id: str = None) -> InlineKeyboardMarkup:
    # Используем полный category_id без обрезания
    if category_id and category_id != "all":
        cat_id = category_id
    else:
        cat_id = "all"
    logger.info(f"🔍 KEYBOARD: category_id = {category_id}, cat_id = {cat_id}")
    buttons = [
        [
            InlineKeyboardButton(text="📝 20 вопросов", callback_data=f"count_20_{cat_id}"),
            InlineKeyboardButton(text="📝 50 вопросов", callback_data=f"count_50_{cat_id}")
        ],
        [
            InlineKeyboardButton(text="📝 100 вопросов", callback_data=f"count_100_{cat_id}")
        ],
        [
            InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_category_info_keyboard(category_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🚀 Начать тест", callback_data=f"start_test_{category_id}")],
        [InlineKeyboardButton(text="« Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_post_exam_keyboard(has_mistakes: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if has_mistakes:
        buttons.append([InlineKeyboardButton(text="📝 Работа над ошибками", callback_data="review_mistakes")])
    buttons.append([
        InlineKeyboardButton(text="🔄 Новый экзамен", callback_data="exam_choose_count"),
        InlineKeyboardButton(text="« В меню", callback_data="back_to_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def get_progress_bar(current: int, total: int, length: int = 10) -> str:
    if total == 0:
        return "░" * length
    filled = int((current / total) * length)
    return "▓" * filled + "░" * (length - filled)


def get_grade_emoji(percent: float) -> str:
    if percent >= 90:
        return "🏆"
    elif percent >= 75:
        return "🌟"
    elif percent >= 60:
        return "📘"
    else:
        return "📚"


def get_grade_text(percent: float) -> str:
    if percent >= 90:
        return "Отлично! Вы блестяще знаете материал!"
    elif percent >= 75:
        return "Хорошо! Есть небольшие пробелы, но в целом отлично!"
    elif percent >= 60:
        return "Удовлетворительно. Стоит повторить материал."
    else:
        return "Нужно повторить. Рекомендуем поработать над ошибками."


# ==================== ОБРАБОТЧИКИ КОМАНД ====================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    if user_id in user_sessions:
        session = user_sessions[user_id]
        session.is_finished = True
        session.questions = []
        session.current_index = 0
    welcome_text = (
        f"👋 **Добро пожаловать в бот для подготовки к экзамену Минюста!**\n\n"
        f"📚 **Всего вопросов в базе:** {len(question_loader.questions)}\n"
        f"📊 **Количество тем:** {len([c for c in question_loader.categories.values() if c.count > 0 and c.id != 'general'])}\n\n"
        f"Выберите тему для подготовки или начните экзамен:"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(user_id))
    await state.set_state(ExamStates.choosing_category)


@dp.message(Command("exam"))
async def cmd_exam(message: Message, state: FSMContext):
    if not question_loader.questions:
        await message.answer("❌ В базе данных нет вопросов. Обратитесь к администратору.")
        return
    await message.answer(
        "📝 **Выберите количество вопросов для экзамена:**",
        reply_markup=get_count_choice_keyboard()
    )
    await state.set_state(ExamStates.choosing_count)


@dp.message(Command("admin_panel"))
async def cmd_admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔑 Создать инвайт (24ч)", callback_data="invite_24"),
            InlineKeyboardButton(text="🔑 Создать инвайт (48ч)", callback_data="invite_48")
        ],
        [
            InlineKeyboardButton(text="🔑 Создать инвайт (72ч)", callback_data="invite_72"),
            InlineKeyboardButton(text="📋 Активные инвайты", callback_data="list_invites")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика бота", callback_data="bot_stats")
        ]
    ])
    await message.answer(
        "👑 **Админ-панель управления**\n\nВыберите действие:",
        reply_markup=keyboard
    )


# ==================== CALLBACK ОБРАБОТЧИКИ ====================
@dp.callback_query(F.data.startswith("category_"))
async def select_category(callback: CallbackQuery, state: FSMContext):
    logger.info(f"🔍 ВЫБРАНА КАТЕГОРИЯ: {callback.data}")
    category_id = callback.data.replace("category_", "")
    logger.info(f"🔍 CATEGORY ID: {category_id}")
    
    category = question_loader.categories.get(category_id)
    if not category:
        await callback.answer("❌ Категория не найдена", show_alert=True)
        return
    if category.count == 0:
        await callback.answer("❌ В этой категории пока нет вопросов", show_alert=True)
        return
    
    info_text = (
        f"{category.emoji} **{category.name}**\n\n"
        f"📝 **Описание:** {category.description}\n"
        f"📊 **Вопросов в категории:** {category.count}\n\n"
        f"🚀 Нажмите «Начать тест» для выбора количества вопросов."
    )
    await callback.message.edit_text(info_text, reply_markup=get_category_info_keyboard(category_id))
    await callback.answer()


@dp.callback_query(F.data.startswith("start_test_"))
async def start_test(callback: CallbackQuery, state: FSMContext):
    logger.info(f"🔍 ЗАПУСК ТЕСТА: {callback.data}")
    category_id = callback.data.replace("start_test_", "")
    logger.info(f"🔍 START_TEST: category_id = {category_id}")
    logger.info(f"🔍 CATEGORY ID: {category_id}")
    
    category = question_loader.categories.get(category_id)
    if not category or category.count == 0:
        await callback.answer("❌ В этой категории нет вопросов", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"{category.emoji} **{category.name}**\n\n"
        f"📊 В категории {category.count} вопросов.\n"
        f"Выберите количество вопросов для теста:",
        reply_markup=get_count_choice_keyboard(category_id)
    )
    await state.set_state(ExamStates.choosing_count)
    await callback.answer()


@dp.callback_query(F.data.startswith("count_"))
async def handle_count_choice(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    count = int(parts[1])
    category_id = parts[2] if len(parts) > 2 else "all"
    logger.info(f"🔍 ВЫБОР КОЛИЧЕСТВА: count={count}, category={category_id}")
    
    if category_id in CATEGORY_MAP:
        logger.info(f"🔍 KEYBOARD: преобразование {category_id} -> {CATEGORY_MAP[category_id]}")
        category_id = CATEGORY_MAP[category_id]
    logger.info(f"🔍 KEYBOARD: category_id после преобразования = {category_id}")
    
    session = get_user_session(user_id)
    
    if category_id == "all":
        questions = question_loader.get_all_questions(count)
        session.seen_questions = []
    else:
        session.category_id = category_id
        questions = question_loader.get_questions_for_category(category_id, session.seen_questions, count)
        for q in questions:
            if q.id not in session.seen_questions:
                session.seen_questions.append(q.id)
        if len(questions) < count:
            session.seen_questions = []
            questions = question_loader.get_questions_for_category(category_id, session.seen_questions, count)
            for q in questions:
                if q.id not in session.seen_questions:
                    session.seen_questions.append(q.id)
    
    if not questions:
        await callback.answer("❌ Недостаточно вопросов", show_alert=True)
        return
    
    session.questions = questions
    session.current_index = 0
    session.score = 0
    session.answers = []
    session.started_at = time.time()
    session.is_finished = False
    session.total_attempts += 1
    session.question_count = count
    
    await state.set_state(ExamStates.exam_in_progress)
    await callback.message.delete()
    await send_question(callback.message, user_id, state)
    await callback.answer(f"🚀 Начинаем экзамен из {count} вопросов!")


@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id in user_sessions:
        session = user_sessions[user_id]
        session.is_finished = True
    await state.set_state(ExamStates.choosing_category)
    try:
        await callback.message.edit_text(
            "📚 **Главное меню:**\n\nВыберите тему для подготовки:",
            reply_markup=get_main_menu_keyboard(user_id)
        )
    except Exception as e:
        if "message is not modified" in str(e):
            await callback.message.delete()
            await callback.message.answer(
                "📚 **Главное меню:**\n\nВыберите тему для подготовки:",
                reply_markup=get_main_menu_keyboard(user_id)
            )
    await callback.answer()


@dp.callback_query(F.data == "reset_progress")
async def reset_progress(callback: CallbackQuery):
    user_id = callback.from_user.id
    session = get_user_session(user_id)
    session.seen_questions = []
    await callback.answer("🔄 История просмотров сброшена!", show_alert=True)


@dp.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    help_text = (
        "❓ **Помощь**\n\n"
        "**📚 Как работает бот:**\n"
        "• Выберите тему из списка\n"
        "• Выберите количество вопросов (20, 50 или 100)\n"
        "• Отвечайте на вопросы, вводя номера через запятую\n"
        "• Например: `1,3,4`\n\n"
        "**📊 Результаты:**\n"
        "• После теста вы увидите статистику\n"
        "• Можно повторить ошибки\n\n"
        "**🎯 Категории:**\n"
        "1. ⚖️ Конституционное право\n"
        "2. 📘 Гражданское законодательство\n"
        "3. 👔 Трудовое законодательство\n"
        "4. ⚖️ Гражданское судопроизводство\n"
        "5. ⚙️ Исполнительное производство\n"
        "6. 🔒 Налоговое и уголовное право\n"
        "7. 📋 Административное право\n"
        "8. 🏢 Хозяйственные общества\n"
        "9. 🏚️ Банкротство\n"
        "10. 💼 Концессия и инвестиции\n"
        "11. 🔍 Проверки и легализация\n"
        "12. 📜 Лицензирование и этика\n"
        "13. 📝 Вопросы с экзамена Минюста"
    )
    await callback.message.answer(help_text)
    await callback.answer()


@dp.callback_query(F.data == "my_stats")
async def show_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    session = get_user_session(user_id)
    stats_text = f"📊 **Ваша статистика**\n\n"
    stats_text += f"📚 Всего тестов: {session.total_attempts}\n"
    if session.answers:
        total = len(session.answers)
        correct = sum(1 for a in session.answers if a.get('is_correct', False))
        stats_text += f"✅ Правильных ответов: {correct} из {total}\n"
        stats_text += f"🎯 Точность: {(correct/total*100):.1f}%\n"
    await callback.message.answer(stats_text)
    await callback.answer()


@dp.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    await cmd_admin_panel(callback.message)
    await callback.answer()


@dp.callback_query(F.data.startswith("invite_"))
async def create_invite_from_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    hours = int(callback.data.replace("invite_", ""))
    code = guest_invite_manager.create_invite(callback.from_user.id, hours)
    bot_username = (await bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start=guest_{code}"
    expires = datetime.fromtimestamp(guest_invite_manager.invites[code]['expires']).strftime('%d.%m.%Y %H:%M')
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Активные инвайты", callback_data="list_invites")],
        [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text(
        f"✅ **Гостевая ссылка создана!**\n\n"
        f"🔑 **Код:** `{code}`\n"
        f"⏱️ **Действует:** {hours} часов\n"
        f"⏰ **Истекает:** {expires}\n\n"
        f"📎 **Ссылка:**\n`{invite_link}`",
        reply_markup=keyboard
    )
    await callback.answer(f"✅ Инвайт на {hours} часов создан!")


@dp.callback_query(F.data == "list_invites")
async def list_active_invites(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    if not guest_invite_manager.invites:
        await callback.message.edit_text(
            "📭 **Нет активных инвайтов**",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="back_to_admin")]
            ])
        )
        return
    text = "📋 **Активные гостевые инвайты:**\n\n"
    buttons = []
    for code, invite in guest_invite_manager.invites.items():
        if not invite.get('active', True) or invite['expires'] < time.time():
            continue
        used = len(invite.get('used_by', []))
        max_uses = invite.get('max_uses', 1)
        hours = invite.get('hours', 24)
        expires = datetime.fromtimestamp(invite['expires']).strftime('%d.%m.%Y %H:%M')
        text += f"🔑 `{code}`\n"
        text += f"   ⏱️ {hours}ч, до {expires}\n"
        text += f"   👤 Использован: {used}/{max_uses}\n\n"
        buttons.append([
            InlineKeyboardButton(text=f"❌ Деактивировать {code}", callback_data=f"deactivate_{code}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад в админку", callback_data="back_to_admin")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    await cmd_admin_panel(callback.message)
    await callback.answer()


@dp.callback_query(F.data == "bot_stats")
async def show_bot_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    total_questions = len(question_loader.questions)
    total_categories = len([c for c in question_loader.categories.values() if c.count > 0])
    active_invites = sum(1 for inv in guest_invite_manager.invites.values() 
                        if inv.get('active', True) and inv['expires'] > time.time())
    text = (
        "📊 **Статистика бота**\n\n"
        f"📚 Всего вопросов: {total_questions}\n"
        f"📂 Категорий: {total_categories}\n"
        f"🔑 Активных инвайтов: {active_invites}\n"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data.startswith("deactivate_"))
async def deactivate_invite(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    code = callback.data.replace("deactivate_", "")
    if code not in guest_invite_manager.invites:
        await callback.answer("❌ Инвайт не найден", show_alert=True)
        await callback.answer("❌ Инвайт не найден", show_alert=True)
        return
    
    guest_invite_manager.invites[code]['active'] = False
    guest_invite_manager.save_invites()
    await callback.answer(f"✅ Инвайт `{code}` деактивирован", show_alert=True)
    await list_active_invites(callback)


@dp.callback_query(F.data == "review_mistakes")
async def review_mistakes(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    session = get_user_session(user_id)
    mistakes = [a for a in session.answers if not a.get('is_correct', False)]
    if not mistakes:
        await callback.answer("🎉 У вас нет ошибок в последнем тесте!", show_alert=True)
        return
    mistake_questions = []
    for mistake in mistakes:
        for q in question_loader.questions:
            if q.question == mistake.get('question', ''):
                mistake_questions.append(q)
                break
    if not mistake_questions:
        await callback.message.answer("❌ Не удалось найти вопросы для повторения")
        return
    session.questions = mistake_questions
    session.current_index = 0
    session.score = 0
    session.answers = []
    session.category_id = "mistakes"
    session.started_at = time.time()
    session.is_finished = False
    session.question_count = len(mistake_questions)
    await state.set_state(ExamStates.exam_in_progress)
    await callback.message.delete()
    await send_question(callback.message, user_id, state)
    await callback.answer(f"📝 Повторяем {len(mistake_questions)} ошибок")


@dp.message(Command("guest_invite"))
async def cmd_guest_invite(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    parts = message.text.split()
    hours = int(parts[1]) if len(parts) > 1 else 24
    if hours < 1 or hours > 72:
        await message.answer("❌ Укажите часы от 1 до 72")
        return
    code = guest_invite_manager.create_invite(message.from_user.id, hours)
    bot_username = (await bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start=guest_{code}"
    await message.answer(
        f"🔑 **Гостевая ссылка создана!**\n\n"
        f"📅 **Действует:** {hours} часов\n"
        f"📎 **Ссылка:**\n`{invite_link}`\n\n"
        f"📋 **Код:** `{code}`\n"
        f"⏱️ Истекает: {datetime.fromtimestamp(guest_invite_manager.invites[code]['expires']).strftime('%d.%m.%Y %H:%M')}"
    )


@dp.message(Command("guest_list"))
async def cmd_guest_list(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    if not guest_invite_manager.invites:
        await message.answer("📭 Нет активных гостевых инвайтов")
        return
    text = "📋 **Активные гостевые инвайты:**\n\n"
    for code, invite in guest_invite_manager.invites.items():
        if not invite.get('active', True) or invite['expires'] < time.time():
            continue
        used = len(invite.get('used_by', []))
        max_uses = invite.get('max_uses', 1)
        hours = invite.get('hours', 24)
        expires = datetime.fromtimestamp(invite['expires']).strftime('%d.%m.%Y %H:%M')
        text += f"🔑 `{code}` - {hours}ч, до {expires} ({used}/{max_uses})\n"
    await message.answer(text)


@dp.message(Command("guest_deactivate"))
async def cmd_guest_deactivate(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Использование: /guest_deactivate КОД")
        return
    code = parts[1]
    if code not in guest_invite_manager.invites:
        await message.answer("❌ Инвайт не найден")
        return
    guest_invite_manager.invites[code]['active'] = False
    guest_invite_manager.save_invites()
    await message.answer(f"✅ Инвайт `{code}` деактивирован")


# ==================== ОТПРАВКА ВОПРОСА ====================
async def send_question(message: Message, user_id: int, state: FSMContext):
    session = get_user_session(user_id)
    if session.is_finished or session.current_index >= len(session.questions):
        await finish_exam(message, user_id, state)
        return
    question = session.current_question
    if not question:
        await finish_exam(message, user_id, state)
        return
    progress = get_progress_bar(session.current_index, len(session.questions))
    options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(question.options)])
    category_name = "📝 Общий экзамен"
    if session.category_id in question_loader.categories:
        cat = question_loader.categories[session.category_id]
        category_name = f"{cat.emoji} {cat.name}"
    elif session.category_id == "mistakes":
        category_name = "📝 Работа над ошибками"
    text = (
        f"**{category_name}**\n"
        f"📊 Прогресс: `{progress}`\n"
        f"❓ **Вопрос {session.current_index + 1} из {len(session.questions)}**\n\n"
        f"**{question.question}**\n\n"
        f"{options_text}\n\n"
        f"📝 Введите номера правильных ответов через запятую (например: `1,3,4`):"
    )
    await message.answer(text, parse_mode="Markdown")


# ==================== ЗАВЕРШЕНИЕ ЭКЗАМЕНА ====================
async def finish_exam(message: Message, user_id: int, state: FSMContext):
    session = get_user_session(user_id)
    session.is_finished = True
    total = len(session.questions)
    score = session.score
    percent = (score / total) * 100 if total > 0 else 0
    mistakes = [a for a in session.answers if not a.get('is_correct', False)]
    grade_emoji = get_grade_emoji(percent)
    grade_text = get_grade_text(percent)
    duration = int(time.time() - session.started_at)
    minutes = duration // 60
    seconds = duration % 60
    text = (
        f"📊 **Экзамен завершен!** {grade_emoji}\n\n"
        f"✅ Правильных ответов: `{score}` из `{total}`\n"
        f"📈 Результат: `{percent:.1f}%`\n"
        f"⏱️ Время: {minutes} мин {seconds} сек\n\n"
        f"{grade_text}\n"
    )
    if mistakes:
        text += f"\n📝 Допущено ошибок: {len(mistakes)}"
    await message.answer(text, reply_markup=get_post_exam_keyboard(len(mistakes) > 0))
    await state.set_state(ExamStates.choosing_category)


# ==================== ОБРАБОТКА ОТВЕТОВ ====================
@dp.message(ExamStates.exam_in_progress)
async def process_answer(message: Message, state: FSMContext):
    user_id = message.from_user.id
    session = get_user_session(user_id)
    if session.is_finished or session.current_index >= len(session.questions):
        await message.answer("❌ Тест уже завершен. Начните новый экзамен командой /exam")
        await cmd_start(message, state)
        return
    question = session.current_question
    if not question:
        await message.answer("❌ Ошибка: вопрос не найден")
        await finish_exam(message, user_id, state)
        return
    try:
        numbers = [x.strip() for x in message.text.split(',') if x.strip()]
        selected = set()
        for num in numbers:
            try:
                n = int(num)
                if 1 <= n <= len(question.options):
                    selected.add(n - 1)
            except ValueError:
                pass
        if len(selected) == 0 or any(n < 0 or n >= len(question.options) for n in selected):
            await message.answer(
                f"⚠️ Нужно выбрать **{len(question.correct_options)}** ответ(а), а вы выбрали {len(selected)}.\n"
                f"Попробуйте снова (например: `{', '.join(question.get_correct_numbers())}`):"
            )
            return
    except Exception as e:
        await message.answer("❌ Ошибка ввода. Введите номера через запятую (например: `1,3,4`)")
        return
    is_correct = question.is_correct(selected)
    if is_correct:
        session.score += 1
        response = "✅ **Правильно!**\n\n"
    else:
        correct_texts = question.get_correct_texts()
        correct_nums = question.get_correct_numbers()
        response = (
            f"❌ **Неправильно.**\n\n"
            f"Правильные ответы: `{', '.join(map(str, correct_nums))}`\n"
            f"({', '.join(correct_texts)})\n\n"
        )
    if question.article:
        response += f"📚 Источник: {question.article}"
    await message.answer(response)
    session.answers.append({
        'question': question.question,
        'selected': list(selected),
        'correct': question.correct_options,
        'is_correct': is_correct
    })
    session.current_index += 1
    await send_question(message, user_id, state)


# ==================== ЗАПУСК ====================
async def main():
    print("=" * 60)
    print("🚀 ЮРИДИЧЕСКИЙ БОТ ЗАПУЩЕН")
    print("=" * 60)
    print(f"📚 Всего вопросов: {len(question_loader.questions)}")
    print("\n📊 Категории вопросов:")
    for cat_id, category in question_loader.categories.items():
        if category.count > 0 and cat_id != 'general':
            print(f"  {category.display_name}")
    if 'general' in question_loader.categories and question_loader.categories['general'].count > 0:
        print(f"  📚 Общие вопросы ({question_loader.categories['general'].count})")
    print("=" * 60)
    print("✅ Бот готов к работе!")
    print("=" * 60)
    logger.info("🚀 Запускаем polling...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске polling: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
