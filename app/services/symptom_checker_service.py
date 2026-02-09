import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class SymptomChecker:

    SYMPTOM_WORKFLOWS = {
        "fever": {
            "name": "Fever Assessment",
            "questions": [
                "For how many days have you had fever?",
                "What is your temperature (if measured)?",
                "Do you have other symptoms like cough, body pain, or headache?",
                "Any recent travel or exposure to sick people?",
            ],
            "high_risk_indicators": ["temperature > 103", "difficulty breathing", "chest pain"],
            "red_flags": ["unconsciousness", "severe headache with stiff neck", "difficulty breathing"],
            "advice_if_severe": "This sounds serious. Please seek emergency care immediately (call 108) or visit the nearest hospital.",
        },
        "cough": {
            "name": "Cough Assessment",
            "questions": [
                "How long have you had the cough?",
                "Is it dry or with phlegm?",
                "Any fever, shortness of breath, or chest pain?",
                "Do you have asthma or respiratory conditions?",
            ],
            "high_risk_indicators": ["severe cough", "blood in phlegm", "difficulty breathing"],
            "red_flags": ["hemoptysis", "severe shortness of breath"],
            "advice_if_severe": "This needs medical attention. Visit a doctor or hospital soon.",
        },
        "headache": {
            "name": "Headache Assessment",
            "questions": [
                "How severe is your headache (1-10)?",
                "Is it throbbing, pressure, or sharp?",
                "Do you have fever, neck stiffness, or sensitivity to light?",
                "What triggered the headache?",
            ],
            "high_risk_indicators": ["sudden severe headache", "fever + stiff neck", "vision changes"],
            "red_flags": ["meningitis signs", "thunderclap headache"],
            "advice_if_severe": "Consult a doctor. If accompanied by fever and neck stiffness, seek emergency care.",
        },
        "bodyache": {
            "name": "Body Pain Assessment",
            "questions": [
                "Which parts of your body hurt?",
                "Is it constant or intermittent?",
                "Do you have fever or other symptoms?",
                "Did you recently exercise or have an injury?",
            ],
            "high_risk_indicators": ["severe pain", "inability to move", "numbness"],
            "red_flags": ["chest pain", "severe crushing pain"],
            "advice_if_severe": "Seek medical attention if pain is severe or accompanied by other concerning symptoms.",
        },
        "diarrhea": {
            "name": "Diarrhea Assessment",
            "questions": [
                "How many times per day?",
                "Is there blood or mucus?",
                "Do you have fever, vomiting, or abdominal pain?",
                "What did you eat in the last 24 hours?",
            ],
            "high_risk_indicators": ["bloody diarrhea", "severe dehydration", "high fever"],
            "red_flags": ["cholera symptoms", "severe electrolyte loss"],
            "advice_if_severe": "Stay hydrated with ORS. If severe or bloody, visit a doctor.",
        },
        "vomiting": {
            "name": "Vomiting Assessment",
            "questions": [
                "How many times have you vomited?",
                "Is there blood in vomit?",
                "Do you have abdominal pain or fever?",
                "When did the vomiting start?",
            ],
            "high_risk_indicators": ["projectile vomiting", "blood in vomit", "severe dehydration"],
            "red_flags": ["hematemesis", "signs of obstruction"],
            "advice_if_severe": "Drink small amounts of oral rehydration solution. See a doctor if persistent.",
        },
    }

    @staticmethod
    def detect_symptom(text: str) -> Optional[str]:
        text_lower = text.lower()

        for symptom in SymptomChecker.SYMPTOM_WORKFLOWS.keys():
            if symptom in text_lower:
                return symptom

        return None

    @staticmethod
    def get_assessment_flow(symptom: str) -> Optional[Dict]:
        return SymptomChecker.SYMPTOM_WORKFLOWS.get(symptom.lower())

    @staticmethod
    def get_next_question(symptom: str, current_step: int = 0) -> Optional[str]:
        workflow = SymptomChecker.get_assessment_flow(symptom)
        if not workflow:
            return None

        questions = workflow.get("questions", [])
        if current_step < len(questions):
            return questions[current_step]

        return None

    @staticmethod
    def check_red_flags(symptom: str, user_responses: List[str]) -> Dict:
        workflow = SymptomChecker.get_assessment_flow(symptom)
        if not workflow:
            return {"risk_level": "unknown", "message": ""}

        response_text = " ".join(user_responses).lower()
        red_flags = workflow.get("red_flags", [])
        high_risk = workflow.get("high_risk_indicators", [])

        has_red_flags = any(flag.lower() in response_text for flag in red_flags)
        has_high_risk = any(indicator.lower() in response_text for indicator in high_risk)

        if has_red_flags:
            return {
                "risk_level": "critical",
                "message": workflow.get("advice_if_severe", "Seek emergency care immediately."),
            }
        elif has_high_risk:
            return {
                "risk_level": "high",
                "message": workflow.get("advice_if_severe", "Please consult a doctor soon."),
            }
        else:
            return {
                "risk_level": "moderate",
                "message": "Continue monitoring your symptoms and consult if they worsen.",
            }

    @staticmethod
    def get_first_question(symptom: str) -> Optional[str]:
        return SymptomChecker.get_next_question(symptom, 0)

symptom_checker = SymptomChecker()
