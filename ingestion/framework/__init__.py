"""Ingestion framework — parallel pipeline infrastructure.

Provides a uniform fetch → parse → upsert → log contract over all 9
Section 3 data sources. Existing ``daily_run.py`` is untouched.

Quick-start::

    from ingestion.framework import Pipeline, HybridFetcher, NseHttpFetcher
    from ingestion.framework import SourceType, LocalFetcher, EodPriceLoader
    from config.settings import settings

    pipeline = Pipeline(
        fetcher=HybridFetcher(
            http=NseHttpFetcher(SourceType.BHAVCOPY),
            local=LocalFetcher(settings.project_root / "data/raw/bhavcopy"),
        ),
        loader=EodPriceLoader(),
        source_name="bhavcopy",
        table_name="fact_eod_price",
    )
    pipeline.run(date.today())
"""
from ingestion.framework.fetchers import (
    BaseFetcher, FetchError, NseHttpFetcher, SourceType, LocalFetcher, HybridFetcher
)
from ingestion.framework.loaders import (
    BaseLoader,
    EodPriceLoader,
    Wk52Loader,
    ConstituentsLoader,
    ReconstitutionLoader,
    CorporateActionsFrameworkLoader,
    EventCalendarLoader,
    AnnouncementsLoader,
    IntradayLoader,
    IndexPriceLoader
)
from ingestion.framework.log import IngestionLogger
from ingestion.framework.pipeline import Pipeline

__all__ = [
    "BaseFetcher", "FetchError",
    "NseHttpFetcher", "SourceType",
    "LocalFetcher", "HybridFetcher",
    "BaseLoader",
    "EodPriceLoader",
    "Wk52Loader",
    "ConstituentsLoader",
    "ReconstitutionLoader",
    "IndexPriceLoader",
    "CorporateActionsFrameworkLoader",
    "EventCalendarLoader",
    "AnnouncementsLoader",
    "IntradayLoader",
    "IngestionLogger",
    "Pipeline",
]
