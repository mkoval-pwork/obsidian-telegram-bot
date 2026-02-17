"""
Unit тесты для github_handler.py

Требуется установка pytest и pytest-mock:
pip install pytest pytest-mock
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from github import GithubException
from github_handler import GitHubHandler


class TestGitHubHandler:
    """Базовые тесты для GitHubHandler"""
    
    @pytest.fixture
    def handler(self):
        """Fixture для создания GitHubHandler с мок конфигом"""
        with patch('github_handler.config') as mock_config:
            mock_config.GITHUB_TOKEN = "test_token"
            mock_config.GITHUB_REPO = "test/repo"
            mock_config.INBOX_PATH = "00_Inbox"
            
            handler = GitHubHandler()
            return handler
    
    @pytest.fixture
    def mock_repo(self):
        """Fixture для мок репозитория"""
        repo = Mock()
        repo.get_contents = Mock()
        repo.create_file = Mock()
        repo.update_file = Mock()
        return repo
    
    def test_init(self, handler):
        """Тест инициализации GitHubHandler"""
        assert handler.github is not None
        assert handler.repo is None
    
    def test_connect_to_repo_success(self, handler, mock_repo):
        """Тест успешного подключения к репозиторию"""
        with patch.object(handler.github, 'get_repo', return_value=mock_repo):
            result = handler.connect_to_repo()
            
            assert result is True
            assert handler.repo == mock_repo
            handler.github.get_repo.assert_called_once()
    
    def test_connect_to_repo_failure(self, handler):
        """Тест неудачного подключения к репозиторию"""
        with patch.object(handler.github, 'get_repo', side_effect=GithubException(404, "Not found")):
            result = handler.connect_to_repo()
            
            assert result is False
            assert handler.repo is None
    
    def test_format_processed_note_text(self, handler):
        """Тест форматирования обработанной текстовой заметки"""
        from llm_processor import ProcessingResult, ActionItem
        
        result = ProcessingResult(
            summary="Тестовое резюме",
            tags=["test", "example"],
            action_items=[
                ActionItem(text="Задача 1", date="2026-02-18", time="10:00", tags=["work"])
            ],
            success=True,
            model_used="gpt-4o-mini",
            processing_version="2.0"
        )
        
        formatted = handler._format_processed_note(
            time_formatted="14:30",
            message_text="Тестовый текст",
            result=result,
            is_voice=False
        )
        
        assert "## 14:30" in formatted
        assert "Тестовое резюме" in formatted
        assert "Тестовый текст" in formatted
        assert "Задача 1" in formatted
        assert "📅 2026-02-18" in formatted
        assert "⏰ 10:00" in formatted
    
    def test_format_processed_note_voice(self, handler):
        """Тест форматирования обработанной голосовой заметки"""
        from llm_processor import ProcessingResult, ActionItem
        
        result = ProcessingResult(
            summary="Голосовое резюме",
            tags=["voice", "test"],
            action_items=[],
            success=True,
            model_used="gpt-4o-mini",
            processing_version="2.0"
        )
        
        voice_metadata = {"duration": 45, "language": "ru"}
        
        formatted = handler._format_processed_note(
            time_formatted="15:00",
            message_text="Транскрибированный текст",
            result=result,
            is_voice=True,
            voice_metadata=voice_metadata
        )
        
        assert "## 15:00 🎤" in formatted
        assert "Голосовое резюме" in formatted
        assert "Транскрибированный текст" in formatted
        assert "45с" in formatted
        assert "ru" in formatted
        assert "Voice Message" in formatted
    
    def test_create_note_calls_create_or_append_note(self, handler):
        """Тест что create_note вызывает _create_or_append_note с правильными параметрами"""
        handler._create_or_append_note = Mock(return_value=(True, "Success"))
        
        result = handler.create_note("Test message", processed=False)
        
        handler._create_or_append_note.assert_called_once_with(
            message_text="Test message",
            is_voice=False,
            processed=False,
            processing_result=None
        )
        assert result == (True, "Success")
    
    def test_create_voice_note_calls_create_or_append_note(self, handler):
        """Тест что create_voice_note вызывает _create_or_append_note с правильными параметрами"""
        handler._create_or_append_note = Mock(return_value=(True, "Success"))
        
        result = handler.create_voice_note(
            transcribed_text="Voice text",
            duration=30,
            language="en",
            processed=False
        )
        
        handler._create_or_append_note.assert_called_once_with(
            message_text="Voice text",
            is_voice=True,
            voice_duration=30,
            voice_language="en",
            processed=False,
            processing_result=None
        )
        assert result == (True, "Success")


# Запуск тестов: pytest test_github_handler.py -v
