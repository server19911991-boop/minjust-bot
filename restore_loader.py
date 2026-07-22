with open('bot.py', 'r') as f:
    content = f.read()

# Проверяем, есть ли класс QuestionLoader
if 'class QuestionLoader:' not in content:
    print("❌ Класс QuestionLoader отсутствует! Восстанавливаем...")
    
    # Находим место для вставки (после класса QuestionCategory)
    pos = content.find('class QuestionCategory:')
    if pos == -1:
        pos = content.find('class UserSession:')
    
    # Создаем класс QuestionLoader
    loader_class = '''
# ==================== ЗАГРУЗКА ДАННЫХ ====================
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
        except FileNotFoundError:
            logger.error("❌ Файл questions.json не найден!")
            self.questions = []
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка в JSON файле: {e}")
            self.questions = []
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
    
    def get_unseen_questions(self, category_id: str, seen_ids: List[int], limit: int = 20) -> List[Question]:
        if category_id not in self.categories:
            return []
        all_ids = self.categories[category_id].questions
        unseen_ids = [q_id for q_id in all_ids if q_id not in seen_ids]
        if not unseen_ids:
            return []
        selected_ids = random.sample(unseen_ids, min(limit, len(unseen_ids)))
        return [q for q in self.questions if q.id in selected_ids]
    
    def get_questions_for_category(self, category_id: str, seen_ids: List[int], limit: int = 20, allow_repeat: bool = False) -> List[Question]:
        if allow_repeat or category_id == "exam":
            return self.get_questions_by_category(category_id, limit)
        unseen = self.get_unseen_questions(category_id, seen_ids, limit)
        if len(unseen) >= limit:
            return unseen
        all_ids = self.categories[category_id].questions if category_id in self.categories else []
        remaining = limit - len(unseen)
        available = [q_id for q_id in all_ids if q_id not in [q.id for q in unseen]]
        if available:
            extra = random.sample(available, min(remaining, len(available)))
            return unseen + [q for q in self.questions if q.id in extra]
        return unseen
    
    def get_question_by_id(self, q_id: int) -> Optional[Question]:
        for q in self.questions:
            if q.id == q_id:
                return q
        return None
'''
    
    # Вставляем перед UserSession
    user_session_pos = content.find('class UserSession:')
    content = content[:user_session_pos] + loader_class + '\n\n' + content[user_session_pos:]
    
    print("✅ Класс QuestionLoader восстановлен!")
else:
    print("✅ Класс QuestionLoader уже есть")

with open('bot.py', 'w') as f:
    f.write(content)
