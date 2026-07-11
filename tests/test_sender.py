"""Tests for scheduler sender (Story 2.2)."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def set_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")


def _make_mock_bot():
    mock_bot = AsyncMock()
    mock_bot.__aenter__ = AsyncMock(return_value=mock_bot)
    mock_bot.__aexit__ = AsyncMock(return_value=False)
    return mock_bot


def test_send_telegram_message_calls_bot_with_correct_args():
    mock_bot = _make_mock_bot()
    with patch("homekeeper.scheduler.sender.Bot", return_value=mock_bot):
        from homekeeper.scheduler.sender import send_telegram_message
        send_telegram_message(12345, "test message")
    mock_bot.send_message.assert_awaited_once_with(
        chat_id=12345, text="test message", parse_mode="HTML", reply_markup=None
    )


def test_send_telegram_message_no_markup_by_default():
    mock_bot = _make_mock_bot()
    with patch("homekeeper.scheduler.sender.Bot", return_value=mock_bot):
        from homekeeper.scheduler.sender import send_telegram_message
        send_telegram_message(12345, "hello")
    _, kwargs = mock_bot.send_message.call_args
    assert kwargs.get("reply_markup") is None


def test_send_telegram_message_passes_reply_markup():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Test", callback_data="t:1")]])
    mock_bot = _make_mock_bot()
    with patch("homekeeper.scheduler.sender.Bot", return_value=mock_bot):
        from homekeeper.scheduler.sender import send_telegram_message
        send_telegram_message(12345, "hello", reply_markup=markup)
    mock_bot.send_message.assert_awaited_once_with(
        chat_id=12345, text="hello", parse_mode="HTML", reply_markup=markup
    )


def test_send_telegram_message_uses_token_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "my-secret-token")
    captured_tokens = []

    def mock_bot_factory(token):
        captured_tokens.append(token)
        return _make_mock_bot()

    with patch("homekeeper.scheduler.sender.Bot", side_effect=mock_bot_factory):
        from homekeeper.scheduler.sender import send_telegram_message
        send_telegram_message(99, "hello")

    assert captured_tokens == ["my-secret-token"]


def test_send_telegram_message_raises_on_api_error():
    mock_bot = _make_mock_bot()
    mock_bot.send_message.side_effect = Exception("Telegram API error")

    with patch("homekeeper.scheduler.sender.Bot", return_value=mock_bot):
        from homekeeper.scheduler.sender import send_telegram_message
        with pytest.raises(Exception, match="Telegram API error"):
            send_telegram_message(12345, "test")
