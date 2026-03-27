"""Ascent data feeds — decorator-based data ingestion framework."""

from ascent.feeds.decorator import Feed, feed
from ascent.feeds.persist import Persist, persist
from ascent.feeds.schedule import Schedule

__all__ = ["Feed", "Persist", "Schedule", "feed", "persist"]
