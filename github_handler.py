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
            return True
        except GithubException as e:
            print(f"Ошибка подключения к репозиторию: {e}")
            return False
    
    def create_note(self, message_text: str) -> tuple[bool, str]:
        """
        Создание заметки в GitHub репозитории
        
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
            
            # Формирование имени файла: YYYY-MM-DD_HHmmss.md
            filename = now.strftime("%Y-%m-%d_%H%M%S.md")
            
            # Формирование пути к файлу
            file_path = f"{config.INBOX_PATH}/{filename}"
            
            # Формирование YAML frontmatter
            date_formatted = now.strftime("%Y-%m-%d %H:%M")
            
            # Формирование содержимого файла
            content = f"""---
date: {date_formatted}
tags: [inbox, telegram]
---

{message_text}
"""
            
            # Создание файла в репозитории
            commit_message = f"Add note from Telegram: {filename}"
            self.repo.create_file(
                path=file_path,
                message=commit_message,
                content=content,
                branch="main"
            )
            
            return True, f"✅ Saved to {config.INBOX_PATH}"
            
        except GithubException as e:
            error_message = f"❌ Ошибка GitHub API: {e.status} - {e.data.get('message', 'Unknown error')}"
            print(error_message)
            return False, error_message
        except Exception as e:
            error_message = f"❌ Неизвестная ошибка: {str(e)}"
            print(error_message)
            return False, error_message
