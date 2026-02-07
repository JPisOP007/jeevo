from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database.base import Base


class LanguageEnum(str, enum.Enum):
    """Supported languages"""
    ENGLISH = "en"
    HINDI = "hi"
    MARATHI = "mr"
    GUJARATI = "gu"
    BENGALI = "bn"
    TAMIL = "ta"
    TELUGU = "te"
    KANNADA = "kn"
    MALAYALAM = "ml"
    PUNJABI = "pa"


class RiskLevel(str, enum.Enum):
    """Risk level indicators"""
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ReminderType(str, enum.Enum):
    """Types of medical reminders"""
    IMMUNIZATION = "immunization"
    CHECKUP = "checkup"
    MEDICATION = "medication"
    TEST = "test"
    FOLLOWUP = "followup"


class User(Base):
    """User table for storing WhatsApp user information"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(15), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    language = Column(SQLEnum(LanguageEnum), default=LanguageEnum.ENGLISH)
    
    # Location information
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)
    
    # User preferences
    voice_enabled = Column(Boolean, default=True)
    alerts_enabled = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.phone_number} - {self.name}>"


class Conversation(Base):
    """Store conversation history"""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Message details
    message_id = Column(String(100), unique=True, index=True)
    message_type = Column(String(20))  # text, audio, image, video, document
    user_message = Column(Text, nullable=True)
    bot_response = Column(Text, nullable=True)
    
    # Media information
    media_url = Column(String(500), nullable=True)
    media_id = Column(String(100), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    response_time_ms = Column(Integer, nullable=True)  # Response time in milliseconds
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    
    def __repr__(self):
        return f"<Conversation {self.id} - User {self.user_id}>"


class Reminder(Base):
    """Medical reminders table"""
    __tablename__ = "reminders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Reminder details
    reminder_type = Column(SQLEnum(ReminderType), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Scheduling
    scheduled_time = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    is_sent = Column(Boolean, default=False)
    is_completed = Column(Boolean, default=False)
    
    # Recurrence (for future implementation)
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(50), nullable=True)  # daily, weekly, monthly
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="reminders")
    
    def __repr__(self):
        return f"<Reminder {self.id} - {self.title}>"


class LocalRiskLevel(Base):
    """Store local health risk levels"""
    __tablename__ = "local_risk_levels"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Location
    pincode = Column(String(10), index=True, nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    
    # Risk information
    risk_level = Column(SQLEnum(RiskLevel), default=RiskLevel.GREEN)
    risk_factors = Column(JSON, nullable=True)  # List of active risk factors
    
    # Health alerts
    active_diseases = Column(JSON, nullable=True)  # List of active disease outbreaks
    pollution_level = Column(String(20), nullable=True)  # AQI level
    weather_alerts = Column(JSON, nullable=True)  # Weather-related alerts
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    data_source = Column(String(100), nullable=True)  # Source of the data
    
    def __repr__(self):
        return f"<RiskLevel {self.pincode} - {self.risk_level}>"


class HealthAlert(Base):
    """Store health alerts and announcements"""
    __tablename__ = "health_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Alert details
    alert_type = Column(String(50), nullable=False)  # outbreak, immunization, weather, safety
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    
    # Targeting
    target_pincodes = Column(JSON, nullable=True)  # List of pincodes
    target_cities = Column(JSON, nullable=True)  # List of cities
    target_states = Column(JSON, nullable=True)  # List of states
    
    # Delivery
    audio_url = Column(String(500), nullable=True)  # URL for voice announcement
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)  # 1=low, 2=medium, 3=high
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    sent_count = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<HealthAlert {self.id} - {self.title}>"


class SessionData(Base):
    """Store user session data"""
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    phone_number = Column(String(15), index=True, nullable=False)
    
    # Session data
    context = Column(JSON, nullable=True)  # Conversation context
    state = Column(String(50), nullable=True)  # Current conversation state
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    def __repr__(self):
        return f"<Session {self.session_id} - {self.phone_number}>"