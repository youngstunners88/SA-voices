"""Language detection for South African languages"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np


class DetectionMethod(Enum):
    KEYWORD = "keyword"
    STATISTICAL = "statistical"
    NEURAL = "neural"
    HYBRID = "hybrid"


@dataclass
class DetectionResult:
    """Language detection result"""
    language: str
    confidence: float
    method: DetectionMethod
    all_scores: Dict[str, float]
    is_reliable: bool
    processing_time: float


class LanguageDetector:
    """Detect South African languages in text"""
    
    # All 11 official SA languages
    SA_LANGUAGES = ["af", "en", "nr", "nso", "st", "ss", "tn", "ts", "ve", "xh", "zu"]
    
    # Characteristic keywords for each language
    KEYWORDS = {
        "zu": {
            "sawubona", "unjani", "ngiyaphila", "yebo", "cha", "ngiyabonga",
            "siza", "lala", "kahle", "hamba", "ikhaya", "umama", "ubaba",
            "uthando", "ukudla", "amanzi", "inja", "inkomo"
        },
        "xh": {
            "molo", "unjani", "ndiphilile", "ewe", "hayi", "enkosi",
            "ndiyabulela", "uxolo", "chommie", "bhuti", "sisi", "tata",
            "umama", "utyebile", "ndiyafuna", "ndiyaqonda", "hayibo"
        },
        "af": {
            "hallo", "hoe gaan", "goed", "ja", "nee", "dankie", "baie",
            "lekker", "braai", "boerewors", "tjops", "kak", "nogal",
            "shame", "now now", "just now", "robot", "bakkie"
        },
        "nso": {
            "dumela", "o kae", "ke gona", "ee", "aa", "ke a leboga",
            "thobela", "boroko", "tshwarelo", "ke rata", "ntate", "mme",
            "ngwana", "lenaka", "setswana", "sepedi", "mosadi"
        },
        "st": {
            "lumela", "o phela", "ke teng", "e", "tjhe", "kea leboha",
            "thobela", "robala", "hamba", "ntate", "mme", "ngoanana",
            "lerato", "diphoofolo", "metsi", "leleme", "ntlo"
        },
        "tn": {
            "dumela", "o tsogile", "ke teng", "ee", "nyaa", "ke a leboga",
            "simolola", "robala", "sala", "ntate", "mme", "ngwana",
            "lerato", "dikgomo", "metsi", "motse", "dumelang"
        },
        "ts": {
            "avuxeni", "ku njhani", "ndza kona", "ina", "eh", "ndza nkhensa",
            "handlekile", "mi hi", "vuya", "tata", "mhani", "nwana",
            "rihandzu", "timbya", "mati", "xikolo", "vuhlanganisi"
        },
        "ss": {
            "sawubona", "unjani", "ngiyaphila", "yebo", "cha", "ngiyabonga",
            "kulungile", "hamba", "lala", "babe", "make", "umntfwana",
            "tsandza", "kudla", "emanti", "liphoofolo", "sikolo"
        },
        "ve": {
            "ndaa", "vho", "vhufhee", "ee", "hai", "ndi khou tou thusa",
            "vho dovhada", "madekwana", "khou humbela", "khotsi", "mme",
            "nwana", "lufuno", "zwili", "vhasiki", "vhutshilo"
        },
        "nr": {
            "lotjhani", "unjani", "siyaphila", "yebo", "cha", "siyabonga",
            "buya", "hamba", "ubaba", "umama", "umntwana", "uthando",
            "ukudla", "amanzi", "inkomo", "inja", "isikole"
        },
        "en": {
            "hello", "how are", "fine", "thank", "yes", "no", "please",
            "sorry", "goodbye", "morning", "afternoon", "evening",
            "love", "food", "water", "house", "family", "friend"
        }
    }
    
    # Character patterns for each language
    CHARACTER_PATTERNS = {
        "zu": r'[cs]h|ng|ny|[^aeiou]y',
        "xh": r'[cs]h|rh|dl|ty|dy|[^aeiou]y',
        "af": r'aa|ee|oo|oe|ui|ij',
        "nso": r'sw|kg|th|ph|hl|tlh',
        "st": r'hl|kg|ph|tl|ts|tj',
        "tn": r'kg|th|ph|tlh|dl|tl',
        "ts": r'ny|by|vy|ty|dy|x[^h]',
        "ss": r'gc|qw|nc|ngc|nj|dl',
        "ve": r'vh|ph|th|zw|sw|dz',
        "nr": r'rh|th|ph|bh|kl|dl',
    }
    
    def __init__(
        self,
        method: DetectionMethod = DetectionMethod.HYBRID,
        confidence_threshold: float = 0.7,
        fallback_language: str = "en"
    ):
        self.method = method
        self.confidence_threshold = confidence_threshold
        self.fallback_language = fallback_language
        self._ngram_models = {}
        self._neural_model = None
    
    def detect(self, text: str) -> DetectionResult:
        """Detect language of text"""
        import time
        start_time = time.time()
        
        if self.method == DetectionMethod.KEYWORD:
            scores = self._keyword_detection(text)
        elif self.method == DetectionMethod.STATISTICAL:
            scores = self._statistical_detection(text)
        elif self.method == DetectionMethod.NEURAL:
            scores = self._neural_detection(text)
        else:  # HYBRID
            scores = self._hybrid_detection(text)
        
        # Get best language
        if not scores:
            best_lang = self.fallback_language
            confidence = 0.0
        else:
            best_lang = max(scores, key=scores.get)
            confidence = scores[best_lang]
        
        processing_time = time.time() - start_time
        
        return DetectionResult(
            language=best_lang,
            confidence=confidence,
            method=self.method,
            all_scores=scores,
            is_reliable=confidence >= self.confidence_threshold,
            processing_time=processing_time
        )
    
    def detect_all(self, text: str) -> List[DetectionResult]:
        """Detect with scores for all languages"""
        result = self.detect(text)
        
        # Sort by confidence
        sorted_scores = sorted(
            result.all_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            DetectionResult(
                language=lang,
                confidence=score,
                method=self.method,
                all_scores=result.all_scores,
                is_reliable=score >= self.confidence_threshold,
                processing_time=result.processing_time
            )
            for lang, score in sorted_scores
        ]
    
    def detect_batch(self, texts: List[str]) -> List[DetectionResult]:
        """Detect languages for multiple texts"""
        return [self.detect(text) for text in texts]
    
    def _keyword_detection(self, text: str) -> Dict[str, float]:
        """Keyword-based detection"""
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        
        scores = {}
        for lang, keywords in self.KEYWORDS.items():
            matches = words & keywords
            if matches:
                # Score based on number and proportion of matches
                score = len(matches) / max(len(words), len(keywords)) * 100
                scores[lang] = min(1.0, score)
        
        return scores
    
    def _statistical_detection(self, text: str) -> Dict[str, float]:
        """Statistical n-gram detection"""
        text_lower = text.lower()
        scores = {}
        
        # Character pattern matching
        for lang, pattern in self.CHARACTER_PATTERNS.items():
            matches = len(re.findall(pattern, text_lower))
            if matches > 0:
                # Normalize by text length
                scores[lang] = matches / len(text_lower) * 10
        
        # N-gram analysis
        trigrams = self._extract_ngrams(text_lower, 3)
        
        for lang in self.SA_LANGUAGES:
            if lang not in self._ngram_models:
                # Build n-gram model from keywords
                self._ngram_models[lang] = self._extract_ngrams(
                    ' '.join(self.KEYWORDS[lang]), 3
                )
            
            model_trigrams = self._ngram_models[lang]
            if model_trigrams:
                overlap = len(trigrams & model_trigrams)
                scores[lang] = scores.get(lang, 0) + overlap / len(model_trigrams)
        
        # Normalize
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                scores = {k: min(1.0, v / max_score) for k, v in scores.items()}
        
        return scores
    
    def _neural_detection(self, text: str) -> Dict[str, float]:
        """Neural model-based detection"""
        # Placeholder for neural model
        # In production, would use fastText, langdetect, or custom transformer
        
        if self._neural_model is None:
            try:
                from langdetect import detect_langs
                self._neural_model = detect_langs
            except ImportError:
                # Fallback to statistical
                return self._statistical_detection(text)
        
        try:
            predictions = self._neural_model(text)
            scores = {}
            for pred in predictions:
                lang = pred.lang
                if lang in self.SA_LANGUAGES:
                    scores[lang] = pred.prob
            return scores
        except:
            return {}
    
    def _hybrid_detection(self, text: str) -> Dict[str, float]:
        """Combine all detection methods"""
        # Get scores from each method
        keyword_scores = self._keyword_detection(text)
        stat_scores = self._statistical_detection(text)
        neural_scores = self._neural_detection(text)
        
        # Weighted combination
        combined = {}
        all_langs = set(keyword_scores) | set(stat_scores) | set(neural_scores)
        
        for lang in all_langs:
            score = (
                keyword_scores.get(lang, 0) * 0.4 +
                stat_scores.get(lang, 0) * 0.3 +
                neural_scores.get(lang, 0) * 0.3
            )
            if score > 0.1:  # Filter very low scores
                combined[lang] = min(1.0, score)
        
        return combined
    
    def _extract_ngrams(self, text: str, n: int) -> set:
        """Extract n-grams from text"""
        ngrams = set()
        text = re.sub(r'\s+', ' ', text.lower())
        for i in range(len(text) - n + 1):
            ngrams.add(text[i:i + n])
        return ngrams
    
    def detect_code_switching(self, text: str) -> List[Tuple[str, str, float]]:
        """Detect code switching (multiple languages in text)"""
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        
        results = []
        for sent in sentences:
            sent = sent.strip()
            if sent:
                result = self.detect(sent)
                results.append((sent, result.language, result.confidence))
        
        return results
    
    def get_language_name(self, code: str) -> str:
        """Get language name from code"""
        names = {
            "af": "Afrikaans",
            "en": "English",
            "nr": "isiNdebele",
            "nso": "Sepedi",
            "st": "Sesotho",
            "ss": "siSwati",
            "tn": "Setswana",
            "ts": "Xitsonga",
            "ve": "Tshivenda",
            "xh": "isiXhosa",
            "zu": "isiZulu",
        }
        return names.get(code, code)
