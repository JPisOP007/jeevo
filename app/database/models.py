from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database.base import Base

class LanguageEnum(str, enum.Enum):

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

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"

class ReminderType(str, enum.Enum):

    IMMUNIZATION = "immunization"
    CHECKUP = "checkup"
    MEDICATION = "medication"
    TEST = "test"
    FOLLOWUP = "followup"

class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(15), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    language = Column(SQLEnum(LanguageEnum), default=LanguageEnum.ENGLISH)

    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)

    voice_enabled = Column(Boolean, default=True)
    alerts_enabled = Column(Boolean, default=True)
    is_onboarded = Column(Boolean, default=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    family_members = relationship("FamilyMember", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.phone_number} - {self.name}>"

class Conversation(Base):

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    message_id = Column(String(100), unique=True, index=True)
    message_type = Column(String(20))
    user_message = Column(Text, nullable=True)
    bot_response = Column(Text, nullable=True)

    media_url = Column(String(500), nullable=True)
    media_id = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    response_time_ms = Column(Integer, nullable=True)
<<<<<<< HEAD
=======
    
    # Validation fields
    validation_id = Column(Integer, ForeignKey("response_validations.id"), nullable=True)
    validation_status = Column(String(50), nullable=True)  # low, medium, high, critical
    confidence_score = Column(Float, nullable=True)
    requires_escalation = Column(Boolean, default=False)
    escalation_id = Column(Integer, ForeignKey("escalated_cases.id"), nullable=True)
    high_risk_keywords = Column(JSON, nullable=True)
    medical_disclaimer_shown = Column(Boolean, default=False)
>>>>>>> origin/jp2

    user = relationship("User", back_populates="conversations")

    def __repr__(self):
        return f"<Conversation {self.id} - User {self.user_id}>"

class Reminder(Base):

    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    reminder_type = Column(SQLEnum(ReminderType), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    scheduled_time = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    is_sent = Column(Boolean, default=False)
    is_completed = Column(Boolean, default=False)

    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="reminders")

    def __repr__(self):
        return f"<Reminder {self.id} - {self.title}>"

class FamilyMember(Base):

    __tablename__ = "family_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    name = Column(String(100), nullable=False)
    relation = Column(String(50), nullable=True)
    age = Column(Integer, nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    gender = Column(String(10), nullable=True)

    phone_number = Column(String(15), nullable=True)
    blood_type = Column(String(5), nullable=True)
    allergies = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="family_members")
    vaccinations = relationship("VaccinationRecord", back_populates="family_member", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FamilyMember {self.id} - {self.name}>"

class VaccinationRecord(Base):

    __tablename__ = "vaccination_records"

    id = Column(Integer, primary_key=True, index=True)
    family_member_id = Column(Integer, ForeignKey("family_members.id"), nullable=False)

    vaccine_name = Column(String(100), nullable=False)
    vaccine_type = Column(String(50), nullable=True)

    scheduled_date = Column(DateTime, nullable=False)
    actual_date = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)

    location = Column(String(200), nullable=True)
    health_worker_name = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    family_member = relationship("FamilyMember", back_populates="vaccinations")

    def __repr__(self):
        return f"<VaccinationRecord {self.id} - {self.vaccine_name}>"

class LocalRiskLevel(Base):

    __tablename__ = "local_risk_levels"

    id = Column(Integer, primary_key=True, index=True)

    pincode = Column(String(10), index=True, nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)

    risk_level = Column(SQLEnum(RiskLevel), default=RiskLevel.GREEN)
    risk_factors = Column(JSON, nullable=True)

    active_diseases = Column(JSON, nullable=True)
    pollution_level = Column(String(20), nullable=True)
    weather_alerts = Column(JSON, nullable=True)

    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    data_source = Column(String(100), nullable=True)

    def __repr__(self):
        return f"<RiskLevel {self.pincode} - {self.risk_level}>"

class HealthAlert(Base):

    __tablename__ = "health_alerts"

    id = Column(Integer, primary_key=True, index=True)

    alert_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    target_pincodes = Column(JSON, nullable=True)
    target_cities = Column(JSON, nullable=True)
    target_states = Column(JSON, nullable=True)

    audio_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)

    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    sent_count = Column(Integer, default=0)

    def __repr__(self):
        return f"<HealthAlert {self.id} - {self.title}>"

class SessionData(Base):

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    phone_number = Column(String(15), index=True, nullable=False)

    context = Column(JSON, nullable=True)
    state = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<Session {self.session_id} - {self.phone_number}>"


class ResponseMetric(Base):

    __tablename__ = "response_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message_id = Column(String(255), nullable=False)
    response_type = Column(String(50), nullable=False)
    quality_rating = Column(String(50), default="unknown")
    response_content = Column(Text, nullable=True)
    response_time = Column(Float, nullable=True)
    was_helpful = Column(Boolean, nullable=True)
    feedback = Column(Text, nullable=True)
    message_type = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<ResponseMetric {self.id} - {self.quality_rating}>"
<<<<<<< HEAD
=======


class ResponseValidation(Base):
    """Store validation records for bot responses"""
    __tablename__ = "response_validations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    message_id = Column(String(255), nullable=True, index=True)
    
    # Request/Response content
    response_text = Column(Text, nullable=False)
    user_query = Column(Text, nullable=True)
    
    # Validation metrics
    confidence_score = Column(Float, nullable=True)
    risk_level = Column(String(50), nullable=True)  # low, medium, high
    
    # Keywords detected
    high_risk_keywords_detected = Column(JSON, nullable=True)
    emergency_keywords_detected = Column(JSON, nullable=True)
    
    # Escalation flags
    requires_escalation = Column(Boolean, default=False, index=True)
    escalation_reason = Column(Text, nullable=True)
    
    # Approval status
    approved_for_sending = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ResponseValidation {self.id} - {self.risk_level}>"


class Expert(Base):
    """Store expert/healthcare worker information"""
    __tablename__ = "experts"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(15), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    specialization = Column(String(100), nullable=True)
    expertise_area = Column(String(200), nullable=True)
    
    is_active = Column(Boolean, default=True, index=True)
    is_available = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    escalations = relationship("EscalatedCase", back_populates="assigned_expert")
    
    def __repr__(self):
        return f"<Expert {self.id} - {self.name}>"


class EscalatedCase(Base):
    """Store escalated cases for medical review"""
    __tablename__ = "escalated_cases"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    validation_id = Column(Integer, ForeignKey("response_validations.id"), nullable=True)
    assigned_expert_id = Column(Integer, ForeignKey("experts.id"), nullable=True, index=True)
    
    # Case details
    original_query = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=True)
    severity = Column(String(50), nullable=False)  # low, medium, high, critical
    escalation_reason = Column(Text, nullable=False)
    
    # Keywords that triggered escalation
    keywords_triggered = Column(JSON, nullable=True)
    
    # Status tracking
    status = Column(String(50), default="open", index=True)  # open, in_progress, resolved, closed
    resolution_notes = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    user = relationship("User")
    assigned_expert = relationship("Expert", back_populates="escalations")
    validation = relationship("ResponseValidation")
    
    def __repr__(self):
        return f"<EscalatedCase {self.id} - {self.severity}>"


class Disclaimer(Base):
    """Store medical disclaimers based on risk levels"""
    __tablename__ = "disclaimers"
    
    id = Column(Integer, primary_key=True, index=True)
    risk_level = Column(String(50), nullable=False, index=True)  # low, medium, high
    language = Column(SQLEnum(LanguageEnum), default=LanguageEnum.ENGLISH, index=True)
    
    title = Column(String(200), nullable=True)
    content = Column(Text, nullable=False)
    
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Disclaimer {self.id} - {self.risk_level}>"


class DisclaimerTracking(Base):
    """Track which users have seen which disclaimers"""
    __tablename__ = "disclaimer_tracking"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    disclaimer_id = Column(Integer, ForeignKey("disclaimers.id"), nullable=False)
    
    context = Column(JSON, nullable=True)
    message_id = Column(String(255), nullable=True)
    
    shown_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    user = relationship("User")
    disclaimer = relationship("Disclaimer")
    
    def __repr__(self):
        return f"<DisclaimerTracking {self.user_id} - {self.disclaimer_id}>"
>>>>>>> origin/jp2
