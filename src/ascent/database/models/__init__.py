# Import base first
# Import asset groups
from ascent.database.models.asset_groups import (
    ProviderAssetGroup,
    ProviderAssetGroupAttribute,
    ProviderAssetGroupMember,
    ProviderAssetGroupPeriodAttribute,
)

# Import asset metadata
from ascent.database.models.asset_metadata import AssetMetadata

# Import asset type metadata junction
from ascent.database.models.asset_type_metadata import AssetTypeMetadata

# Import assets
from ascent.database.models.assets import Asset
from ascent.database.models.base import Base

# Import descriptors (attributes, periods, metadata)
from ascent.database.models.descriptors import Attribute, Metadata, Period

# Import exchanges
from ascent.database.models.exchanges import Exchange

# Import feeds
from ascent.database.models.feeds import (
    Feed,
    FeedAssetScope,
    FeedDependency,
    FeedPartition,
    FeedRun,
    StrategyFeed,
)

# Import orders
from ascent.database.models.orders import Order, OrderStatus

# Import portfolio
from ascent.database.models.portfolio import Portfolio, PortfolioAssetHolding

# Import provider assets
from ascent.database.models.provider_assets import ProviderAssetMetadata

# Import provider content
from ascent.database.models.provider_content import (
    AssetContent,
    ProviderContent,
    ProviderContentAttribute,
    ProviderContentMetadata,
)

# Import provider metadata
from ascent.database.models.provider_metadata import ProviderMetadata

# Import provider type metadata junction
from ascent.database.models.provider_type_metadata import ProviderTypeMetadata

# Import providers
from ascent.database.models.providers import Provider

# Import strategy models
from ascent.database.models.strategy import Strategy, StrategyAssetScope, StrategyRun, StrategyState
from ascent.database.models.strategy_run_feeds import StrategyRunFeedRun

# Import trade analysis
from ascent.database.models.trade_analysis import (
    TradeCondition,
    TradeDataSeries,
    TradeSnapshot,
)

# Import trades
from ascent.database.models.trades import Trade, TradeLeg, TradeStatus

# Import transactions
from ascent.database.models.transactions import (
    Transaction,
    TransactionGroup,
    TransactionGroupMember,
    TransactionStatus,
)

# Import core types
from ascent.database.models.types import (
    AssetType,
    ContentType,
    ExchangeType,
    FeedType,
    OrderStatusType,
    OrderType,
    ProviderType,
    SentimentType,
    StrategyType,
    TradeStatusType,
    TransactionStatusType,
    TransactionType,
)

# Export all models for `from ascent.database.models import *`
__all__ = [
    # Base
    "Base",
    # Core Types
    "AssetType",
    "ExchangeType",
    "ProviderType",
    "ContentType",
    "SentimentType",
    "TransactionType",
    "TransactionStatusType",
    "StrategyType",
    "FeedType",
    "TradeStatusType",
    "OrderType",
    "OrderStatusType",
    # Asset Metadata
    "AssetMetadata",
    "AssetTypeMetadata",
    # Assets
    "Asset",
    # Exchanges
    "Exchange",
    # Providers
    "Provider",
    # Portfolio
    "Portfolio",
    "PortfolioAssetHolding",
    # Attribute System
    "Attribute",
    "Metadata",
    "Period",
    # Provider Metadata
    "ProviderMetadata",
    "ProviderTypeMetadata",
    # Provider Assets
    "ProviderAssetMetadata",
    # Provider Content
    "ProviderContent",
    "ProviderContentAttribute",
    "ProviderContentMetadata",
    "AssetContent",
    # Asset Groups
    "ProviderAssetGroup",
    "ProviderAssetGroupMember",
    "ProviderAssetGroupAttribute",
    "ProviderAssetGroupPeriodAttribute",
    # Orders
    "Order",
    "OrderStatus",
    # Transactions
    "Transaction",
    "TransactionGroup",
    "TransactionGroupMember",
    "TransactionStatus",
    # Feeds
    "Feed",
    "FeedAssetScope",
    "FeedDependency",
    "FeedPartition",
    "FeedRun",
    "StrategyFeed",
    # Strategies
    "Strategy",
    "StrategyAssetScope",
    "StrategyRun",
    "StrategyRunFeedRun",
    "StrategyState",
    # Trades
    "Trade",
    "TradeLeg",
    "TradeStatus",
    # Trade Analysis
    "TradeCondition",
    "TradeDataSeries",
    "TradeSnapshot",
]
