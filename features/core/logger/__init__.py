"""Перехватчик Stdout логов behave"""
from .logger import StdoutLogger

__all__ = ['logger']

logger = StdoutLogger()
