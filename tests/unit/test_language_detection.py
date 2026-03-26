"""Tests for language detection"""

import pytest
from skills.language_detection import LanguageDetector, DetectionMethod


class TestLanguageDetector:
    """Test language detection"""
    
    @pytest.fixture
    def detector(self):
        return LanguageDetector()
    
    def test_detect_zulu(self, detector):
        result = detector.detect("Sawubona, unjani?")
        assert result.language == "zu"
        assert result.confidence > 0.5
    
    def test_detect_xhosa(self, detector):
        result = detector.detect("Molo, unjani?")
        assert result.language == "xh"
        assert result.confidence > 0.5
    
    def test_detect_afrikaans(self, detector):
        result = detector.detect("Hallo, hoe gaan dit?")
        assert result.language == "af"
        assert result.confidence > 0.5
    
    def test_detect_english(self, detector):
        result = detector.detect("Hello, how are you?")
        assert result.language == "en"
    
    def test_detect_all(self, detector):
        results = detector.detect_all("Sawubona")
        assert len(results) > 0
        assert results[0].language == "zu"
    
    def test_batch_detection(self, detector):
        texts = ["Sawubona", "Molo", "Hallo"]
        results = detector.detect_batch(texts)
        assert len(results) == 3
        assert results[0].language == "zu"
        assert results[1].language == "xh"
        assert results[2].language == "af"
    
    def test_get_language_name(self, detector):
        assert detector.get_language_name("zu") == "isiZulu"
        assert detector.get_language_name("xh") == "isiXhosa"
        assert detector.get_language_name("af") == "Afrikaans"


class TestDetectionMethods:
    """Test different detection methods"""
    
    def test_keyword_detection(self):
        detector = LanguageDetector(method=DetectionMethod.KEYWORD)
        result = detector.detect("Sawubona ngiyabonga")
        assert result.language == "zu"
        assert result.method == DetectionMethod.KEYWORD
    
    def test_statistical_detection(self):
        detector = LanguageDetector(method=DetectionMethod.STATISTICAL)
        result = detector.detect("Dumela, o kae?")
        assert result.method == DetectionMethod.STATISTICAL
    
    def test_hybrid_detection(self):
        detector = LanguageDetector(method=DetectionMethod.HYBRID)
        result = detector.detect("Yebo, ngiyaphila")
        assert result.method == DetectionMethod.HYBRID
