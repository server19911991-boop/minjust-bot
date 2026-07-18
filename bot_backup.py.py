import asyncio
import json
import logging
import os
from random import shuffle
from typing import Dict

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

def load_questions():
    with open('questions.json', 'r', encoding='utf-8') as f:
        return json.load(f)

class ExamStates(StatesGroup):
    waiting_for_start = State()
    in_progress = State()

user_data: Dict[int, dict] = {}

def get_user_quiz_data(user_id: int):
    if user_id not in user_data:
        user_data[user_id] = {
            'questions': [],
            'current_q_index': 0,
            'score': 0,
            'answers': []
        }
    return user_data[user_id]

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(ExamStates.waiting_for_start)
    await message.answer(
        "👋 Привет! Это бот для подготовки к экзамену Министерства юстиции.\n"
        "Я буду задавать тебе вопросы с вариантами ответов.\n\n"
        "Чтобы начать, отправь команду /exam"
    )

@dp.message(Command("exam"))
async def cmd_exam(message: Message, state: FSMContext):
    user_id = message.from_user.id
    quiz_data = get_user_quiz_data(user_id)
    
    all_questions = load_questions()
    shuffle(all_questions)
    quiz_data['questions'] = all_questions
    quiz_data['current_q_index'] = 0
    quiz_data['score'] = 0
    quiz_data['answers'] = []
    
    await state.set_state(ExamStates.in_progress)
    await send_question(message, user_id)

async def send_question(message: Message, user_id: int):
    quiz_data = get_user_quiz_data(user_id)
    q_index = quiz_data['current_q_index']
    questions = quiz_data['questions']
    
    if q_index >= len(questions):
        await finish_exam(message, user_id)
        return
    
    question_data = questions[q_index]
    
    buttons = []
    for i, option_text in enumerate(question_data['options']):
        buttons.append([InlineKeyboardButton(text=option_text, callback_data=f"answer_{i}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        f"Вопрос {q_index + 1} из {len(questions)}:\n\n{question_data['question']}",
        reply_markup=keyboard
    )

@dp.callback_query(ExamStates.in_progress, F.data.startswith("answer_"))
async def process_answer(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    quiz_data = get_user_quiz_data(user_id)
    q_index = quiz_data['current_q_index']
    question_data = quiz_data['questions'][q_index]
    
    selected_option_index = int(callback.data.split("_")[1])
    correct_index = question_data['correct_option']
    
    is_correct = (selected_option_index == correct_index)
    if is_correct:
        quiz_data['score'] += 1
        await callback.answer("✅ Правильно!", show_alert=False)
    else:
        correct_answer_text = question_data['options'][correct_index]
        await callback.answer(f"❌ Неправильно. Правильный ответ: {correct_answer_text}", show_alert=True)
    
    quiz_data['answers'].append({
        'question': question_data['question'],
        'selected': selected_option_index,
        'correct': correct_index,
        'is_correct': is_correct
    })
    
    await callback.message.delete()
    
    quiz_data['current_q_index'] += 1
    await send_question(callback.message, user_id)

async def finish_exam(message: Message, user_id: int):
    quiz_data = get_user_quiz_data(user_id)
    total_questions = len(quiz_data['questions'])
    score = quiz_data['score']
    percentage = (score / total_questions) * 100 if total_questions > 0 else 0
    
    await state.finish()
    
    await message.answer(
        f"📊 **Тест завершен!**\n\n"
        f"Правильных ответов: {score} из {total_questions}\n"
        f"Результат: {percentage:.1f}%\n\n"
        f"Чтобы попробовать снова, отправь /exam",
        parse_mode="Markdown"
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())