"""Ascent data feeds — class-based data ingestion framework."""

from ascent.feeds.base import Feed
from ascent.feeds.decorator import Feed as FeedDecorator
from ascent.feeds.decorator import feed
from ascent.feeds.persist import Persist, persist
from ascent.feeds.schedule import Schedule

__all__ = ["Feed", "FeedDecorator", "Persist", "Schedule", "feed", "persist"]
