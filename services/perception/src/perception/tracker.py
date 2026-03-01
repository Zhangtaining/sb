"""Tracker module — tracking is handled by Detector.track() via ultralytics.

This module re-exports TrackedDetection for backward compatibility.
"""
from perception.detector import TrackedDetection

__all__ = ["TrackedDetection"]
