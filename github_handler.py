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
    
    def create_note(self, message_text: str) -> tuple[bool, str]:
        """
        Создание заметки в GitHub репозитории (добавление в дневной файл)
        
        Args:
            message_text: Текст сообщения из Telegram
            
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
                    
                    content = f"""---
date: {date_formatted}
tags: [inbox, telegram, daily]
---

# Заметки за {date_display}

## {time_formatted}

{message_text}
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
    
    def create_voice_note(self, transcribed_text: str, duration: int, language: str = "ru") -> tuple[bool, str]:
        """
        Создание заметки из транскрибированного голосового сообщения (добавление в дневной файл)
        
        Args:
            transcribed_text: Транскрибированный текст
            duration: Длительность аудио в секундах
            language: Язык сообщения
            
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
                    
                    content = f"""---
date: {date_formatted}
tags: [inbox, telegram, daily]
---

# Заметки за {date_display}

## {time_formatted} 🎤

{transcribed_text}

---
*Источник: Telegram Voice Message • Длительность: {duration}с • Язык: {language}*
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
