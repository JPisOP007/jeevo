from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.database.models import User, Conversation, Reminder, LocalRiskLevel, HealthAlert, FamilyMember, VaccinationRecord, ResponseMetric
import logging

logger = logging.getLogger(__name__)

class UserRepository:

    @staticmethod
    async def create_user(db: AsyncSession, phone_number: str, **kwargs) -> User:

        user = User(phone_number=phone_number, **kwargs)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"Created user: {phone_number}")
        return user

    @staticmethod
    async def get_user_by_phone(db: AsyncSession, phone_number: str) -> Optional[User]:

        result = await db.execute(
            select(User).where(User.phone_number == phone_number)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_phone_number(db: AsyncSession, phone_number: str) -> Optional[User]:

        return await UserRepository.get_user_by_phone(db, phone_number)
    @staticmethod
    async def get_or_create_user(db: AsyncSession, phone_number: str, **kwargs) -> tuple[User, bool]:

        user = await UserRepository.get_user_by_phone(db, phone_number)
        if user:

            user.last_active = datetime.utcnow()
            await db.commit()
            return user, False
        else:
            user = await UserRepository.create_user(db, phone_number, **kwargs)
            return user, True

    @staticmethod
    async def update_user(db: AsyncSession, phone_number: str, **kwargs) -> Optional[User]:

        from app.database.models import LanguageEnum

        user = await UserRepository.get_user_by_phone(db, phone_number)
        if user:
            for key, value in kwargs.items():

                if key == "language" and isinstance(value, str):
                    try:
                        value = LanguageEnum(value)
                    except ValueError:
                        logger.warning(f"Invalid language code: {value}, defaulting to English")
                        value = LanguageEnum.ENGLISH
                setattr(user, key, value)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Updated user: {phone_number}")
        return user

    @staticmethod
    async def get_all_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:

        result = await db.execute(
            select(User).offset(skip).limit(limit)
        )
        return result.scalars().all()

class ConversationRepository:

    @staticmethod
    async def create_conversation(
        db: AsyncSession,
        user_id: int,
        message_id: str,
        **kwargs
    ) -> Conversation:

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

        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_recent_conversations(
        db: AsyncSession,
        user_id: int,
        limit: int = 10
    ) -> List[Conversation]:

        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.asc())
            .limit(limit)
        )
        conversations = result.scalars().all()
        return list(reversed(conversations))

    @staticmethod
    async def get_conversation_context(
        db: AsyncSession,
        user_id: int,
        limit: int = 10
    ) -> str:

        conversations = await ConversationRepository.get_recent_conversations(db, user_id, limit)
        
        context_lines = []
        for conv in conversations:
            if conv.user_message:
                context_lines.append(f"User: {conv.user_message}")
            if conv.bot_response:
                context_lines.append(f"Assistant: {conv.bot_response}")
        
        return "\n".join(context_lines)

class ReminderRepository:

    @staticmethod
    async def create_reminder(
        db: AsyncSession,
        user_id: int,
        **kwargs
    ) -> Reminder:

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

    @staticmethod
    async def get_risk_level(db: AsyncSession, pincode: str) -> Optional[LocalRiskLevel]:

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

    @staticmethod
    async def create_alert(db: AsyncSession, **kwargs) -> HealthAlert:

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

        now = datetime.utcnow()

        query = select(HealthAlert).where(
            HealthAlert.is_active == True,
            (HealthAlert.expires_at == None) | (HealthAlert.expires_at > now)
        )

        result = await db.execute(query.order_by(HealthAlert.priority.desc()))
        alerts = result.scalars().all()

        if pincode:
            filtered_alerts = []
            for alert in alerts:
                if alert.target_pincodes and pincode in alert.target_pincodes:
                    filtered_alerts.append(alert)
                elif not alert.target_pincodes:
                    filtered_alerts.append(alert)
            return filtered_alerts

        return alerts

class FamilyMemberRepository:

    @staticmethod
    async def create_family_member(
        db: AsyncSession,
        user_id: int,
        **kwargs
    ) -> FamilyMember:

        member = FamilyMember(user_id=user_id, **kwargs)
        db.add(member)
        await db.commit()
        await db.refresh(member)
        logger.info(f"Created family member {member.name} for user {user_id}")
        return member

    @staticmethod
    async def get_user_family_members(
        db: AsyncSession,
        user_id: int
    ) -> List[FamilyMember]:

        result = await db.execute(
            select(FamilyMember)
            .where(FamilyMember.user_id == user_id)
            .order_by(FamilyMember.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_family_member(
        db: AsyncSession,
        member_id: int
    ) -> Optional[FamilyMember]:

        result = await db.execute(
            select(FamilyMember).where(FamilyMember.id == member_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_family_member(
        db: AsyncSession,
        member_id: int,
        **kwargs
    ) -> Optional[FamilyMember]:

        member = await FamilyMemberRepository.get_family_member(db, member_id)
        if member:
            for key, value in kwargs.items():
                setattr(member, key, value)
            member.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(member)
        return member

    @staticmethod
    async def delete_family_member(
        db: AsyncSession,
        member_id: int
    ) -> bool:

        result = await db.execute(
            delete(FamilyMember).where(FamilyMember.id == member_id)
        )
        await db.commit()
        return result.rowcount > 0

class VaccinationRecordRepository:

    @staticmethod
    async def create_vaccination_record(
        db: AsyncSession,
        family_member_id: int,
        **kwargs
    ) -> VaccinationRecord:

        record = VaccinationRecord(family_member_id=family_member_id, **kwargs)
        db.add(record)
        await db.commit()
        await db.refresh(record)
        logger.info(f"Created vaccination record for family member {family_member_id}")
        return record

    @staticmethod
    async def get_member_vaccinations(
        db: AsyncSession,
        family_member_id: int,
        completed_only: bool = False
    ) -> List[VaccinationRecord]:

        query = select(VaccinationRecord).where(
            VaccinationRecord.family_member_id == family_member_id
        )

        if completed_only:
            query = query.where(VaccinationRecord.is_completed == True)

        result = await db.execute(query.order_by(VaccinationRecord.scheduled_date))
        return result.scalars().all()

    @staticmethod
    async def get_pending_vaccinations(
        db: AsyncSession,
        family_member_id: int
    ) -> List[VaccinationRecord]:

        result = await db.execute(
            select(VaccinationRecord).where(
                VaccinationRecord.family_member_id == family_member_id,
                VaccinationRecord.is_completed == False,
                VaccinationRecord.scheduled_date <= datetime.utcnow()
            ).order_by(VaccinationRecord.scheduled_date)
        )
        return result.scalars().all()

    @staticmethod
    async def mark_vaccination_complete(
        db: AsyncSession,
        record_id: int,
        actual_date: Optional[datetime] = None
    ) -> Optional[VaccinationRecord]:

        result = await db.execute(
            select(VaccinationRecord).where(VaccinationRecord.id == record_id)
        )
        record = result.scalar_one_or_none()

        if record:
            record.is_completed = True
            record.actual_date = actual_date or datetime.utcnow()
            await db.commit()
            await db.refresh(record)
            logger.info(f"Marked vaccination {record.vaccine_name} as complete")

        return record


class ResponseMetricRepository:

    @staticmethod
    async def create_metric(
        db: AsyncSession,
        user_id: int,
        message_id: str,
        response_type: str,
        **kwargs
    ) -> ResponseMetric:

        metric = ResponseMetric(
            user_id=user_id,
            message_id=message_id,
            response_type=response_type,
            **kwargs
        )
        db.add(metric)
        await db.commit()
        await db.refresh(metric)
        logger.info(f"Created response metric for user {user_id}")
        return metric

    @staticmethod
    async def get_user_metrics(
        db: AsyncSession,
        user_id: int,
        limit: int = 100
    ) -> List[ResponseMetric]:

        result = await db.execute(
            select(ResponseMetric)
            .where(ResponseMetric.user_id == user_id)
            .order_by(ResponseMetric.timestamp.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def mark_response_helpful(
        db: AsyncSession,
        metric_id: int,
        was_helpful: bool,
        feedback: str = None
    ) -> Optional[ResponseMetric]:

        result = await db.execute(
            select(ResponseMetric).where(ResponseMetric.id == metric_id)
        )
        metric = result.scalar_one_or_none()

        if metric:
            metric.was_helpful = was_helpful
            metric.feedback = feedback
            await db.commit()
            await db.refresh(metric)
            logger.info(f"Updated feedback for metric {metric_id}")

        return metric

    @staticmethod
    async def get_quality_stats(
        db: AsyncSession,
        user_id: int = None,
        days: int = 7
    ) -> Dict:

        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = select(ResponseMetric).where(
            ResponseMetric.timestamp >= cutoff_date
        )

        if user_id:
            query = query.where(ResponseMetric.user_id == user_id)

        result = await db.execute(query)
        metrics = result.scalars().all()

        total = len(metrics)
        helpful = len([m for m in metrics if m.was_helpful == True])
        not_helpful = len([m for m in metrics if m.was_helpful == False])

        helpful_rate = (helpful / total * 100) if total > 0 else 0

        return {
            "total_responses": total,
            "helpful": helpful,
            "not_helpful": not_helpful,
            "accuracy_rate": round(helpful_rate, 2),
            "period_days": days,
        }