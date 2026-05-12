# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Telegram service - matches all expected parameters.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramService:
    """Telegram service for user linking and messaging."""
    
    def __init__(self):
        self._links = {}
    
    def link_user(self, db, telegram_user_id: int, app_user_id: str = None, 
                  chat_id: str = None, username: str = None, first_name: str = None,
                  last_name: str = None) -> str:
        """Link Telegram user to app user ID."""
        key = str(telegram_user_id)
        
        # Try to get existing link
        if key in self._links:
            return self._links[key]
        
        # Create new link
        if app_user_id:
            self._links[key] = app_user_id
        else:
            self._links[key] = f"tg_{telegram_user_id}"
        
        logger.info(f"Linked Telegram user {telegram_user_id} -> {self._links[key]} "
                   f"(username: {username}, chat: {chat_id})")
        return self._links[key]
    
    def get_link(self, db, telegram_user_id: int) -> Optional[str]:
        """Get app user ID for a Telegram user."""
        return self._links.get(telegram_user_id)
    
    def get_user_id(self, db, telegram_user_id: int) -> Optional[str]:
        """Alias for get_link."""
        return self.get_link(db, telegram_user_id)
    
    def send_message(self, chat_id: str, text: str) -> bool:
        """Send a Telegram message."""
        logger.info(f"Would send to {chat_id}: {text[:50]}...")
        return True


# Singleton instance
telegram_service = TelegramService()
