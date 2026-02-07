from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime

from app.database.models import User, Conversation, Reminder, LocalRiskLevel, HealthAlert
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for User operations"""
    
    @staticmethod
    async def create_user(db: AsyncSession, phone_number: str, **kwargs) -> User:
        """Create a new user"""
        user = User(phone_number=phone_number, **kwargs)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"Created user: {phone_number}")
        return user
    
    @staticmethod
    async def get_user_by_phone(db: AsyncSession, phone_number: str) -> Optional[User]:
        """Get user by phone number"""
        result = await db.execute(
            select(User).where(User.phone_number == phone_number)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_or_create_user(db: AsyncSession, phone_number: str, **kwargs) -> tuple[User, bool]:
        """Get existing user or create new one"""
        user = await UserRepository.get_user_by_phone(db, phone_number)
        if user:
            # Update last_active
            user.last_active = datetime.utcnow()
            await db.commit()
            return user, False
        else:
            user = await UserRepository.create_user(db, phone_number, **kwargs)
            return user, True
    
    @staticmethod
    async def update_user(db: AsyncSession, phone_number: str, **kwargs) -> Optional[User]:
        """Update user information"""
        user = await UserRepository.get_user_by_phone(db, phone_number)
        if user:
            for key, value in kwargs.items():
                setattr(user, key, value)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Updated user: {phone_number}")
        return user
    
    @staticmethod
    async def get_all_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all users with pagination"""
        result = await db.execute(
            select(User).offset(skip).limit(limit)
        )
        return result.scalars().all()


class ConversationRepository:
    """Repository for Conversation operations"""
    
    @staticmethod
    async def create_conversation(
        db: AsyncSession,
        user_id: int,
        message_id: str,
        **kwargs
    ) -> Conversation:
        """Create a new conversation record"""
        conversation = Conversation(
            user_id=user_id,
            message_id=message_id,
            **kwargs
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation
    
    @staticmethod
    async def get_user_conversations(
        db: AsyncSession,
        user_id: int,
        limit: int = 50
    ) -> List[Conversation]:
        """Get recent conversations for a user"""
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


class ReminderRepository:
    """Repository for Reminder operations"""
    
    @staticmethod
    async def create_reminder(
        db: AsyncSession,
        user_id: int,
        **kwargs
    ) -> Reminder:
        """Create a new reminder"""
        reminder = Reminder(user_id=user_id, **kwargs)
        db.add(reminder)
        await db.commit()
        await db.refresh(reminder)
        logger.info(f"Created reminder for user {user_id}: {reminder.title}")
        return reminder
    
    @staticmethod
    async def get_user_reminders(
        db: AsyncSession,
        user_id: int,
        active_only: bool = True
    ) -> List[Reminder]:
        """Get reminders for a user"""
        query = select(Reminder).where(Reminder.user_id == user_id)
        
        if active_only:
            query = query.where(
                Reminder.is_sent == False,
                Reminder.is_completed == False
            )
        
        result = await db.execute(query.order_by(Reminder.scheduled_time))
        return result.scalars().all()
    
    @staticmethod
    async def get_pending_reminders(db: AsyncSession) -> List[Reminder]:
        """Get all pending reminders that need to be sent"""
        now = datetime.utcnow()
        result = await db.execute(
            select(Reminder)
            .where(
                Reminder.is_sent == False,
                Reminder.scheduled_time <= now
            )
            .order_by(Reminder.scheduled_time)
        )
        return result.scalars().all()
    
    @staticmethod
    async def mark_reminder_sent(db: AsyncSession, reminder_id: int) -> Optional[Reminder]:
        """Mark a reminder as sent"""
        result = await db.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        
        if reminder:
            reminder.is_sent = True
            reminder.sent_at = datetime.utcnow()
            await db.commit()
            await db.refresh(reminder)
        
        return reminder


class RiskLevelRepository:
    """Repository for LocalRiskLevel operations"""
    
    @staticmethod
    async def get_risk_level(db: AsyncSession, pincode: str) -> Optional[LocalRiskLevel]:
        """Get risk level for a pincode"""
        result = await db.execute(
            select(LocalRiskLevel).where(LocalRiskLevel.pincode == pincode)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_risk_level(
        db: AsyncSession,
        pincode: str,
        **kwargs
    ) -> LocalRiskLevel:
        """Update or create risk level for a pincode"""
        risk_level = await RiskLevelRepository.get_risk_level(db, pincode)
        
        if risk_level:
            for key, value in kwargs.items():
                setattr(risk_level, key, value)
            risk_level.last_updated = datetime.utcnow()
        else:
            risk_level = LocalRiskLevel(pincode=pincode, **kwargs)
            db.add(risk_level)
        
        await db.commit()
        await db.refresh(risk_level)
        return risk_level


class HealthAlertRepository:
    """Repository for HealthAlert operations"""
    
    @staticmethod
    async def create_alert(db: AsyncSession, **kwargs) -> HealthAlert:
        """Create a new health alert"""
        alert = HealthAlert(**kwargs)
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        logger.info(f"Created health alert: {alert.title}")
        return alert
    
    @staticmethod
    async def get_active_alerts(
        db: AsyncSession,
        pincode: Optional[str] = None
    ) -> List[HealthAlert]:
        """Get active health alerts, optionally filtered by pincode"""
        now = datetime.utcnow()
        
        query = select(HealthAlert).where(
            HealthAlert.is_active == True,
            (HealthAlert.expires_at == None) | (HealthAlert.expires_at > now)
        )
        
        result = await db.execute(query.order_by(HealthAlert.priority.desc()))
        alerts = result.scalars().all()
        
        # Filter by pincode if provided
        if pincode:
            filtered_alerts = []
            for alert in alerts:
                if alert.target_pincodes and pincode in alert.target_pincodes:
                    filtered_alerts.append(alert)
                elif not alert.target_pincodes:  # Global alert
                    filtered_alerts.append(alert)
            return filtered_alerts
        
        return alerts