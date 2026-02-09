import logging
from typing import List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ValidationResult(BaseModel):
    """Result of medical response validation"""
    risk_level: str  # low, medium, high
    confidence_score: float
    requires_escalation: bool
    validation_message: str
    high_risk_keywords_detected: List[str] = []
    emergency_keywords_detected: List[str] = []


class MedicalValidationService:
    """Service to validate medical responses for safety and risk"""
    
    # Emergency keywords that always trigger escalation
    EMERGENCY_KEYWORDS = [
        "emergency", "urgent", "hospital", "ambulance", "cardiac", "heart attack",
        "stroke", "seizure", "unconscious", "bleeding", "severe bleeding",
        "poisoning", "overdose", "suicide", "self-harm", "death",
        "serious injury", "accident", "trauma"
    ]
    
    # High-risk keywords that may trigger escalation
    HIGH_RISK_KEYWORDS = [
        "pregnant", "pregnancy", "infant", "newborn", "baby",
        "cancer", "tumor", "malignant", "chemotherapy",
        "diabetes", "insulin", "kidney disease", "liver disease",
        "mental health", "depression", "anxiety", "psychosis",
        "addiction", "drug abuse", "alcohol abuse",
        "pain relief", "medication", "prescription",
        "high fever", "severe", "critical", "acute"
    ]
    
    # Medical conditions that need careful handling
    MEDICAL_CONDITIONS = [
        "asthma", "diabetes", "hypertension", "blood pressure",
        "cholesterol", "thyroid", "arthritis", "migraine",
        "eczema", "psoriasis", "allergies"
    ]
    
    @staticmethod
    def validate_response(
        user_query: str,
        bot_response: str,
        confidence_score: float = 0.5
    ) -> ValidationResult:
        """
        Validate a bot response against medical safety criteria
        
        Args:
            user_query: The original user query
            bot_response: The bot's response
            confidence_score: Confidence score of the response (0-1)
        
        Returns:
            ValidationResult with risk assessment
        """
        try:
            query_lower = user_query.lower() if user_query else ""
            response_lower = bot_response.lower() if bot_response else ""
            
            # Check for emergency keywords
            emergency_keywords = MedicalValidationService._find_keywords(
                query_lower + " " + response_lower,
                MedicalValidationService.EMERGENCY_KEYWORDS
            )
            
            # Check for high-risk keywords
            high_risk_keywords = MedicalValidationService._find_keywords(
                query_lower,
                MedicalValidationService.HIGH_RISK_KEYWORDS
            )
            
            # Check for medical conditions
            medical_conditions = MedicalValidationService._find_keywords(
                query_lower,
                MedicalValidationService.MEDICAL_CONDITIONS
            )
            
            # Determine risk level and escalation
            requires_escalation = False
            risk_level = "low"
            validation_message = "Response is appropriate"
            
            # Emergency keywords always trigger escalation
            if emergency_keywords:
                risk_level = "critical"
                requires_escalation = True
                validation_message = f"Emergency situation detected: {', '.join(emergency_keywords[:3])}"
            
            # High-risk keywords with low confidence trigger escalation
            elif high_risk_keywords and confidence_score < 0.7:
                risk_level = "high"
                requires_escalation = True
                validation_message = f"High-risk medical topic with low confidence: {', '.join(high_risk_keywords[:2])}"
            
            # Medical conditions require attention
            elif high_risk_keywords or medical_conditions:
                risk_level = "medium"
                if confidence_score < 0.5:
                    requires_escalation = True
                    validation_message = "Medical condition mentioned with low confidence"
                else:
                    validation_message = "Medical condition mentioned - response monitored"
            
            # Low confidence on any query
            elif confidence_score < 0.3:
                risk_level = "medium"
                requires_escalation = True
                validation_message = "Very low confidence - requires expert review"
            
            logger.info(
                f"[VALIDATION] Query: '{user_query[:50]}...' | "
                f"Risk: {risk_level} | Escalate: {requires_escalation} | "
                f"Confidence: {confidence_score}"
            )
            
            return ValidationResult(
                risk_level=risk_level,
                confidence_score=confidence_score,
                requires_escalation=requires_escalation,
                validation_message=validation_message,
                high_risk_keywords_detected=high_risk_keywords + medical_conditions,
                emergency_keywords_detected=emergency_keywords
            )
        
        except Exception as e:
            logger.error(f"Error validating response: {e}")
            return ValidationResult(
                risk_level="high",
                confidence_score=0.0,
                requires_escalation=True,
                validation_message=f"Validation error: {str(e)}",
                high_risk_keywords_detected=[],
                emergency_keywords_detected=[]
            )
    
    @staticmethod
    def _find_keywords(text: str, keyword_list: List[str]) -> List[str]:
        """Find keywords present in text"""
        found = []
        for keyword in keyword_list:
            if keyword in text:
                found.append(keyword)
        return found
