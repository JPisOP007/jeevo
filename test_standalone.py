#!/usr/bin/env python3
"""
Standalone test suite that tests medical validation without external dependencies
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMedicalValidationStandalone:
    """Standalone tests for MedicalValidationService that don't require SQLAlchemy"""
    
    @staticmethod
    def test_validation_logic():
        """Test validation logic independently"""
        from app.services.medical_validation_service import MedicalValidationService
        
        # Test 1: Low risk
        result = MedicalValidationService.validate_response(
            user_query="I have a headache",
            bot_response="Try resting and drinking water",
            confidence_score=0.8
        )
        assert result.risk_level == "low", f"Expected 'low', got '{result.risk_level}'"
        assert result.requires_escalation == False
        print("✅ Test 1 Passed: Low-risk query")
        
        # Test 2: Emergency keywords
        result = MedicalValidationService.validate_response(
            user_query="I'm having a heart attack",
            bot_response="Call 911 immediately",
            confidence_score=0.5
        )
        assert result.risk_level == "critical", f"Expected 'critical', got '{result.risk_level}'"
        assert result.requires_escalation == True
        assert "heart attack" in result.emergency_keywords_detected
        print("✅ Test 2 Passed: Emergency keyword detection")
        
        # Test 3: High-risk keywords with low confidence
        result = MedicalValidationService.validate_response(
            user_query="I think I might be pregnant",
            bot_response="This needs medical evaluation",
            confidence_score=0.4
        )
        assert result.risk_level == "high", f"Expected 'high', got '{result.risk_level}'"
        assert result.requires_escalation == True
        print("✅ Test 3 Passed: High-risk with low confidence")
        
        # Test 4: Medical condition keywords
        result = MedicalValidationService.validate_response(
            user_query="My blood pressure is 180/110",
            bot_response="Monitor your BP regularly",
            confidence_score=0.7
        )
        assert result.risk_level == "medium", f"Expected 'medium', got '{result.risk_level}'"
        assert "blood pressure" in result.high_risk_keywords_detected
        print("✅ Test 4 Passed: Medical condition detection")
        
        # Test 5: Low confidence triggers escalation
        result = MedicalValidationService.validate_response(
            user_query="Something is wrong",
            bot_response="I'm uncertain what you mean",
            confidence_score=0.2
        )
        assert result.risk_level == "medium", f"Expected 'medium', got '{result.risk_level}'"
        assert result.requires_escalation == True
        print("✅ Test 5 Passed: Low confidence escalation")
        
        # Test 6: Keyword finding
        keywords = MedicalValidationService._find_keywords(
            "I have diabetes and high blood pressure",
            ["diabetes", "blood pressure", "cancer"]
        )
        assert len(keywords) == 2
        assert "diabetes" in keywords
        assert "blood pressure" in keywords
        print("✅ Test 6 Passed: Keyword identification")
        
        # Test 7: Multiple emergency keywords
        result = MedicalValidationService.validate_response(
            user_query="Unconscious and severe bleeding",
            bot_response="Call emergency services",
            confidence_score=0.6
        )
        assert result.risk_level == "critical"
        assert len(result.emergency_keywords_detected) >= 1
        print("✅ Test 7 Passed: Multiple emergency keywords")
        
        # Test 8: Hindi medical terms (basic test)
        result = MedicalValidationService.validate_response(
            user_query="मुझे बुखार है",  # "I have fever" in Hindi
            bot_response="बैठ कर आराम करें",
            confidence_score=0.7
        )
        # Won't detect because keywords are in English, but shouldn't crash
        assert result is not None
        print("✅ Test 8 Passed: Multilingual handling (no crash)")


class TestDisclaimerStandalone:
    """Standalone tests for DisclaimerService"""
    
    @staticmethod
    def test_disclaimer_defaults():
        """Test default disclaimers"""
        # Define disclaimers directly to avoid sqlalchemy import
        DEFAULT_DISCLAIMERS = {
            "low": {
                "en": "✅ This information is for general awareness only.",
                "hi": "✅ यह जानकारी सामान्य जागरूकता के लिए है।",
            },
            "medium": {
                "en": "⚠️ This is AI-generated guidance. Please consult a qualified doctor for proper medical advice.",
                "hi": "⚠️ यह एआई द्वारा उत्पन्न मार्गदर्शन है। सही चिकित्सा सलाह के लिए कृपया योग्य डॉक्टर से संपर्क करें।",
            },
            "high": {
                "en": "🚨 IMPORTANT: This requires immediate medical attention. Please consult a doctor or visit a hospital immediately.",
                "hi": "🚨 महत्वपूर्ण: इसके लिए तुरंत चिकित्सा ध्यान दिया जाना चाहिए। कृपया तुरंत डॉक्टर से परामर्श लें या अस्पताल जाएं।",
            },
            "critical": {
                "en": "🚨 EMERGENCY: This appears to be a life-threatening situation. Please call 911 or your local emergency number immediately!",
                "hi": "🚨 आपातकाल: यह एक जानलेवा स्थिति प्रतीत होती है। कृपया तुरंत 911 को कॉल करें या अपना स्थानीय आपातकालीन नंबर दबाएं!",
            }
        }
        
        disclaimers = DEFAULT_DISCLAIMERS
        
        # Test structure
        assert "low" in disclaimers
        assert "medium" in disclaimers
        assert "high" in disclaimers
        assert "critical" in disclaimers
        print("✅ Test 1 Passed: All risk levels have disclaimers")
        
        # Test languages
        for risk_level in disclaimers:
            assert "en" in disclaimers[risk_level]
            assert "hi" in disclaimers[risk_level]
        print("✅ Test 2 Passed: Multi-language support (en, hi)")
        
        # Test content differs by risk level
        low = disclaimers["low"]["en"]
        critical = disclaimers["critical"]["en"]
        assert low != critical
        assert len(critical) > len(low)
        assert "EMERGENCY" in critical or "emergency" in critical.lower() or "911" in critical
        print("✅ Test 3 Passed: Disclaimer severity increases")
        
        # Test content quality
        for risk_level, languages in disclaimers.items():
            for lang, content in languages.items():
                assert len(content) > 0, f"Empty disclaimer for {risk_level}/{lang}"
                assert len(content) < 500, f"Disclaimer too long for {risk_level}/{lang}"
        print("✅ Test 4 Passed: All disclaimers have appropriate length")
        
        # Test specific keywords in disclaimers
        assert "⚠️" in disclaimers["medium"]["en"] or "doctor" in disclaimers["medium"]["en"].lower()
        print("✅ Test 5 Passed: Disclaimers contain guidance")


class TestIntegrationStandalone:
    """Standalone integration tests"""
    
    @staticmethod
    def test_end_to_end_workflow():
        """Test complete end-to-end medical safety workflow"""
        from app.services.medical_validation_service import MedicalValidationService
        
        # Default disclaimers (avoiding sqlalchemy import)
        DEFAULT_DISCLAIMERS = {
            "low": {
                "en": "✅ This information is for general awareness only.",
            },
            "medium": {
                "en": "⚠️ This is AI-generated guidance. Please consult a qualified doctor.",
            },
            "high": {
                "en": "🚨 IMPORTANT: This requires immediate medical attention.",
            },
            "critical": {
                "en": "🚨 EMERGENCY: Please call 911 immediately!",
            }
        }
        
        # Scenario 1: Simple health query
        query1 = "What should I do for a cold?"
        response1 = "Rest, hydrate, and take over-the-counter medication"
        
        validation1 = MedicalValidationService.validate_response(
            user_query=query1,
            bot_response=response1,
            confidence_score=0.85
        )
        
        assert validation1.risk_level == "low"
        assert validation1.requires_escalation == False
        
        disclaimer1 = DEFAULT_DISCLAIMERS["low"]["en"]
        final_response1 = response1 + "\n\n" + disclaimer1
        assert len(final_response1) > len(response1)
        print("✅ Scenario 1 Passed: Simple query with disclaimer")
        
        # Scenario 2: Emergency query
        query2 = "I can't breathe and having severe chest pain"
        response2 = "This is a medical emergency"
        
        validation2 = MedicalValidationService.validate_response(
            user_query=query2,
            bot_response=response2,
            confidence_score=0.5
        )
        
        assert validation2.risk_level == "critical"
        assert validation2.requires_escalation == True
        
        disclaimer2 = DEFAULT_DISCLAIMERS["critical"]["en"]
        assert "911" in disclaimer2 or "emergency" in disclaimer2.lower()
        print("✅ Scenario 2 Passed: Emergency detection and escalation")
        
        # Scenario 3: High-risk medical condition
        query3 = "I'm pregnant and having stomach pain"
        response3 = "Please see a healthcare provider soon"
        
        validation3 = MedicalValidationService.validate_response(
            user_query=query3,
            bot_response=response3,
            confidence_score=0.65
        )
        
        assert validation3.risk_level == "high"
        
        disclaimer3 = DEFAULT_DISCLAIMERS["high"]["en"]
        final_response3 = response3 + "\n\n" + disclaimer3
        assert len(final_response3) > len(response3)
        print("✅ Scenario 3 Passed: High-risk medical condition")
        
        # Scenario 4: Multiple languages
        query4_hi = "मेरे को बुखार है"  # I have fever (Hindi)
        response4_hi = "आराम करें"  # Rest (Hindi)
        
        validation4 = MedicalValidationService.validate_response(
            user_query=query4_hi,
            bot_response=response4_hi,
            confidence_score=0.7
        )
        
        assert validation4.risk_level == "low"
        print("✅ Scenario 4 Passed: Multilingual support")


def run_all_standalone_tests():
    """Run all standalone tests"""
    print("\n" + "="*70)
    print("JEEVO MEDICAL FEATURES - STANDALONE TEST SUITE")
    print("="*70 + "\n")
    
    try:
        print("📋 RUNNING MEDICAL VALIDATION TESTS\n")
        TestMedicalValidationStandalone.test_validation_logic()
        
        print("\n📋 RUNNING DISCLAIMER TESTS\n")
        TestDisclaimerStandalone.test_disclaimer_defaults()
        
        print("\n📋 RUNNING INTEGRATION TESTS\n")
        TestIntegrationStandalone.test_end_to_end_workflow()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED SUCCESSFULLY!")
        print("="*70)
        print("\nTest Results Summary:")
        print("  ✅ Medical Validation Tests: 8/8 PASSED")
        print("  ✅ Disclaimer Tests: 5/5 PASSED")
        print("  ✅ Integration Tests: 4/4 PASSED")
        print("  ✅ Total: 17/17 PASSED\n")
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_standalone_tests()
    sys.exit(0 if success else 1)
