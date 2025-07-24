"""
Queue management system for the Telegram to WhatsApp Sticker Converter Bot
"""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class QueueItem:
    user_id: int
    username: str
    chat_id: int
    message_id: int
    pack_input: Any  # Can be a string (short_name) or an InputStickerSet object
    timestamp: datetime
    status: str = "waiting"  # waiting, processing, completed, error

class QueueManager:
    def __init__(self):
        self.queue: List[QueueItem] = []
        self.processing: Optional[QueueItem] = None
        self.user_queues: Dict[int, QueueItem] = {}  # user_id -> QueueItem
        self._lock = asyncio.Lock()
    
    async def add_to_queue(self, user_id: int, username: str, chat_id: int, 
                          message_id: int, pack_input: Any) -> int:
        """Add user to queue and return position"""
        async with self._lock:
            if user_id in self.user_queues:
                existing_item = self.user_queues[user_id]
                if existing_item.status in ["waiting", "processing"]:
                    return self._get_position(user_id)
            
            queue_item = QueueItem(
                user_id=user_id,
                username=username,
                chat_id=chat_id,
                message_id=message_id,
                pack_input=pack_input,
                timestamp=datetime.now()
            )
            
            self.queue.append(queue_item)
            self.user_queues[user_id] = queue_item
            
            logger.info(f"Added user {username} (ID: {user_id}) to queue for pack: {pack_input}")
            return len(self.queue)
    
    async def get_next_item(self) -> Optional[QueueItem]:
        """Get next item to process"""
        async with self._lock:
            if self.processing is not None:
                return None
            
            if not self.queue:
                return None
            
            item = self.queue.pop(0)
            item.status = "processing"
            self.processing = item
            
            logger.info(f"Starting processing for user {item.username} (ID: {item.user_id})")
            return item
    
    async def complete_processing(self, user_id: int, success: bool = True):
        """Mark current processing as complete"""
        async with self._lock:
            if self.processing and self.processing.user_id == user_id:
                self.processing.status = "completed" if success else "error"
                
                if user_id in self.user_queues:
                    del self.user_queues[user_id]
                
                logger.info(f"Completed processing for user {self.processing.username} (ID: {user_id}), success: {success}")
                self.processing = None
    
    def get_queue_position(self, user_id: int) -> Optional[int]:
        """Get user's position in queue"""
        if user_id not in self.user_queues:
            return None
        
        return self._get_position(user_id)
    
    def _get_position(self, user_id: int) -> int:
        """Internal method to get position"""
        item = self.user_queues.get(user_id)
        if not item:
            return 0
        
        if item.status == "processing":
            return 1
        
        try:
            # Position is 1-based index in queue + 1 if someone is processing
            return self.queue.index(item) + 1 + (1 if self.processing else 0)
        except ValueError:
            return 0
    
    def get_queue_stats(self) -> dict:
        """Get queue statistics"""
        return {
            "total_waiting": len(self.queue),
            "currently_processing": self.processing is not None,
            "processing_user": self.processing.username if self.processing else None
        }
    
    def is_user_in_queue(self, user_id: int) -> bool:
        """Check if user is in queue"""
        return user_id in self.user_queues and self.user_queues[user_id].status in ["waiting", "processing"]

# Global queue manager instance
queue_manager = QueueManager()
