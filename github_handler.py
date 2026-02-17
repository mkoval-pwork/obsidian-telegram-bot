"""
Модуль для работы с GitHub API
"""
from datetime import datetime
from github import Github, GithubException
import config


class GitHubHandler:
    """Класс для работы с GitHub репозиторием"""
    
    def __init__(self):
        """Инициализация GitHub клиента"""
        self.github = Github(config.GITHUB_TOKEN)
        self.repo = None
        
    def connect_to_repo(self):
        """Подключение к репозиторию"""
        try:
            self.repo = self.github.get_repo(config.GITHUB_REPO)
            # Проверяем существование папки inbox
            self._ensure_inbox_exists()
            return True
        except GithubException as e:
            print(f"Ошибка подключения к репозиторию: {e}")
            return False
    
    def _ensure_inbox_exists(self):
        """Проверка и создание папки inbox если её нет"""
        try:
            # Пытаемся получить содержимое папки
            self.repo.get_contents(config.INBOX_PATH)
        except GithubException as e:
            if e.status == 404:
                # Папка не существует, создаём её через .gitkeep
                print(f"Папка {config.INBOX_PATH} не найдена, создаю...")
                try:
                    self.repo.create_file(
                        path=f"{config.INBOX_PATH}/.gitkeep",
                        message=f"Create {config.INBOX_PATH} folder",
                        content="",
                        branch="main"
                    )
                    print(f"✅ Папка {config.INBOX_PATH} создана")
                except Exception as create_error:
                    print(f"⚠️ Не удалось создать папку: {create_error}")
            else:
                # Другая ошибка, игнорируем
                pass
    
    def _format_processed_note(
        self,
        time_formatted: str,
        message_text: str,
        result,
        is_voice: bool = False,
        voice_metadata: dict = None
    ) -> str:
        """
        Форматирование обработанной заметки
        
        Args:
            time_formatted: Время в формате HH:MM
            message_text: Исходный текст
            result: ProcessingResult с данными обработки
            is_voice: Флаг голосового сообщения
            voice_metadata: Метаданные голосового (duration, language)
            
        Returns:
            Отформатированная заметка
        """
        # Заголовок с эмодзи для голосовых
        header = f"## {time_formatted} 🎤" if is_voice else f"## {time_formatted}"
        
        # Summary
        summary = f"**Summary:** {result.summary}"
        
        # Содержание
        content = f"""### Содержание

{message_text}"""
        
        # Задачи (если есть)
        tasks = ""
        if result.action_items:
            # Используем метод to_markdown() для форматирования с датами
            tasks_list = "\n".join(task.to_markdown() for task in result.action_items)
            tasks = f"""
### Задачи

{tasks_list}"""
        
        # Футер
        if is_voice and voice_metadata:
            duration = voice_metadata.get("duration", 0)
            language = voice_metadata.get("language", "unknown")
            footer = f"\n---\n*Источник: Telegram Voice Message • Длительность: {duration}с • Язык: {language} | Обработано: Smart Processing v{result.processing_version} ({result.model_used})*\n"
        else:
            footer = f"\n---\n*Источник: Telegram | Обработано: Smart Processing v{result.processing_version} ({result.model_used})*\n"
        
        return f"\n{header}\n\n{summary}\n\n{content}{tasks}{footer}"
    
    def create_note(
        self, 
        message_text: str,
        processed: bool = False,
        processing_result = None
    ) -> tuple[bool, str]:
        """
        Создание заметки в GitHub репозитории (добавление в дневной файл)
        
        Args:
            message_text: Текст сообщения из Telegram
            processed: Флаг обработки через LLM
            processing_result: Результат обработки (если processed=True)
            
        Returns:
            tuple: (успех, сообщение)
        """
        if not self.repo:
            if not self.connect_to_repo():
                return False, "❌ Ошибка подключения к GitHub репозиторию"
        
        try:
            # Получение текущего времени
            now = datetime.now()
            
            # Формирование имени файла: YYYY-MM-DD.md (один файл на день)
            filename = now.strftime("%Y-%m-%d.md")
            file_path = f"{config.INBOX_PATH}/{filename}"
            
            # Формирование заголовка с временем для новой заметки
            time_formatted = now.strftime("%H:%M")
            
            # Формирование заметки в зависимости от обработки
            if processed and processing_result:
                new_note = self._format_processed_note(
                    time_formatted=time_formatted,
                    message_text=message_text,
                    result=processing_result,
                    is_voice=False
                )
            else:
                new_note = f"\n## {time_formatted}\n\n{message_text}\n"
            
            # Проверка существования файла
            try:
                # Файл существует - получаем его содержимое
                file_content = self.repo.get_contents(file_path, ref="main")
                existing_content = file_content.decoded_content.decode('utf-8')
                
                # Добавляем новую заметку в конец файла
                updated_content = existing_content + new_note
                
                # Обновляем файл
                commit_message = f"Add note to {filename} at {time_formatted}"
                self.repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=updated_content,
                    sha=file_content.sha,
                    branch="main"
                )
                
                return True, f"✅ Added to {filename}"
                
            except GithubException as e:
                if e.status == 404:
                    # Файл не существует - создаём новый
                    date_formatted = now.strftime("%Y-%m-%d")
                    date_display = now.strftime("%d.%m.%Y")
                    
                    # Формирование frontmatter
                    if processed and processing_result:
                        tags = ['inbox', 'telegram'] + processing_result.tags
                        
                        # Добавление dates_mentioned если есть
                        dates_line = ""
                        if processing_result.dates_mentioned:
                            dates_str = ', '.join(processing_result.dates_mentioned)
                            dates_line = f"\ndates_mentioned: [{dates_str}]"
                        
                        frontmatter = f"""---
date: {date_formatted}
tags: [{', '.join(tags)}]
processed: true
processing_model: {processing_result.model_used}
processing_version: {processing_result.processing_version}{dates_line}
---"""
                        note_content = self._format_processed_note(
                            time_formatted=time_formatted,
                            message_text=message_text,
                            result=processing_result,
                            is_voice=False
                        ).lstrip('\n')
                    else:
                        frontmatter = f"""---
date: {date_formatted}
tags: [inbox, telegram, unprocessed]
processed: false
---"""
                        note_content = f"""## {time_formatted}

{message_text}"""
                    
                    content = f"""{frontmatter}

# Заметки за {date_display}

{note_content}
"""
                    
                    commit_message = f"Create daily note: {filename}"
                    self.repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=content,
                        branch="main"
                    )
                    
                    return True, f"✅ Created {filename}"
                else:
                    # Другая ошибка - пробрасываем дальше
                    raise
            
        except GithubException as e:
            error_message = f"❌ Ошибка GitHub API: {e.status} - {e.data.get('message', 'Unknown error')}"
            print(error_message)
            return False, error_message
        except Exception as e:
            error_message = f"❌ Неизвестная ошибка: {str(e)}"
            print(error_message)
            return False, error_message
    
    def create_voice_note(
        self,
        transcribed_text: str,
        duration: int,
        language: str = "ru",
        processed: bool = False,
        processing_result = None
    ) -> tuple[bool, str]:
        """
        Создание заметки из транскрибированного голосового сообщения (добавление в дневной файл)
        
        Args:
            transcribed_text: Транскрибированный текст
            duration: Длительность аудио в секундах
            language: Язык сообщения
            processed: Флаг обработки через LLM
            processing_result: Результат обработки (если processed=True)
            
        Returns:
            tuple: (успех, сообщение)
        """
        if not self.repo:
            if not self.connect_to_repo():
                return False, "❌ Ошибка подключения к GitHub репозиторию"
        
        try:
            # Получение текущего времени
            now = datetime.now()
            
            # Формирование имени файла: YYYY-MM-DD.md (один файл на день)
            filename = now.strftime("%Y-%m-%d.md")
            file_path = f"{config.INBOX_PATH}/{filename}"
            
            # Формирование заголовка с временем для новой голосовой заметки
            time_formatted = now.strftime("%H:%M")
            
            # Формирование заметки в зависимости от обработки
            if processed and processing_result:
                voice_metadata = {"duration": duration, "language": language}
                new_note = self._format_processed_note(
                    time_formatted=time_formatted,
                    message_text=transcribed_text,
                    result=processing_result,
                    is_voice=True,
                    voice_metadata=voice_metadata
                )
            else:
                new_note = f"\n## {time_formatted} 🎤\n\n{transcribed_text}\n\n---\n*Источник: Telegram Voice Message • Длительность: {duration}с • Язык: {language}*\n"
            
            # Проверка существования файла
            try:
                # Файл существует - получаем его содержимое
                file_content = self.repo.get_contents(file_path, ref="main")
                existing_content = file_content.decoded_content.decode('utf-8')
                
                # Добавляем новую заметку в конец файла
                updated_content = existing_content + new_note
                
                # Обновляем файл
                commit_message = f"Add voice note to {filename} at {time_formatted}"
                self.repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=updated_content,
                    sha=file_content.sha,
                    branch="main"
                )
                
                return True, f"✅ Added voice note to {filename}"
                
            except GithubException as e:
                if e.status == 404:
                    # Файл не существует - создаём новый
                    date_formatted = now.strftime("%Y-%m-%d")
                    date_display = now.strftime("%d.%m.%Y")
                    
                    # Формирование frontmatter
                    if processed and processing_result:
                        tags = ['inbox', 'telegram', 'voice'] + processing_result.tags
                        
                        # Добавление dates_mentioned если есть
                        dates_line = ""
                        if processing_result.dates_mentioned:
                            dates_str = ', '.join(processing_result.dates_mentioned)
                            dates_line = f"\ndates_mentioned: [{dates_str}]"
                        
                        frontmatter = f"""---
date: {date_formatted}
tags: [{', '.join(tags)}]
processed: true
processing_model: {processing_result.model_used}
processing_version: {processing_result.processing_version}{dates_line}
---"""
                        voice_metadata = {"duration": duration, "language": language}
                        note_content = self._format_processed_note(
                            time_formatted=time_formatted,
                            message_text=transcribed_text,
                            result=processing_result,
                            is_voice=True,
                            voice_metadata=voice_metadata
                        ).lstrip('\n')
                    else:
                        frontmatter = f"""---
date: {date_formatted}
tags: [inbox, telegram, voice, unprocessed]
processed: false
---"""
                        note_content = f"""## {time_formatted} 🎤

{transcribed_text}

---
*Источник: Telegram Voice Message • Длительность: {duration}с • Язык: {language}*"""
                    
                    content = f"""{frontmatter}

# Заметки за {date_display}

{note_content}
"""
                    
                    commit_message = f"Create daily note: {filename}"
                    self.repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=content,
                        branch="main"
                    )
                    
                    return True, f"✅ Created {filename} with voice note"
                else:
                    # Другая ошибка - пробрасываем дальше
                    raise
            
        except GithubException as e:
            error_message = f"❌ Ошибка GitHub API: {e.status} - {e.data.get('message', 'Unknown error')}"
            print(error_message)
            return False, error_message
        except Exception as e:
            error_message = f"❌ Неизвестная ошибка: {str(e)}"
            print(error_message)
            return False, error_message
