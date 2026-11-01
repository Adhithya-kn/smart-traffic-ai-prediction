"""
traffic_system/models/strategies/base.py - Abstract Prediction Strategy
Provides the contract for traffic congestion classification models (Strategy Pattern, OCP).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple

class IPredictionStrategy(ABC):
    """Abstract strategy for traffic classification inference."""

    @abstractmethod
    def predict(self, safe_features: Dict[str, Any]) -> Tuple[str, Dict[str, float]]:
        """
        Executes forward inference on a single feature dictionary.
        Returns (predicted_class_label, probability_distribution_dict).
        """
        pass

    @abstractmethod
    def predict_batch(self, batch_features: List[Dict[str, Any]]) -> List[Tuple[str, Dict[str, float]]]:
        """Vectorized forward batch prediction."""
        pass

    @abstractmethod
    def explain(self, safe_features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Returns top feature contribution drivers."""
        pass
