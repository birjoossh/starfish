"""Seed dim_stock with current Nifty 50 constituents.

Populates the master stock dimension table with the 50 current Nifty 50 stocks.
Run once during initial setup.

Usage:
    python -m ingestion.seed_stocks
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import pandas as pd
from sqlalchemy import text

from config.database import get_engine

logger = logging.getLogger(__name__)

# Current Nifty 50 constituents as of April 2026.
# Update when NSE announces reconstitution.
NIFTY50_SEED = [
    {"symbol": "ADANIENT", "company_name": "Adani Enterprises Ltd", "sector": "Metals & Mining", "industry": "Diversified", "isin": "INE423A01024", "face_value": 1.0},
    {"symbol": "ADANIPORTS", "company_name": "Adani Ports and Special Economic Zone Ltd", "sector": "Services", "industry": "Port & Port services", "isin": "INE742F01042", "face_value": 2.0},
    {"symbol": "APOLLOHOSP", "company_name": "Apollo Hospitals Enterprise Ltd", "sector": "Healthcare", "industry": "Hospital", "isin": "INE437A01024", "face_value": 5.0},
    {"symbol": "ASIANPAINT", "company_name": "Asian Paints Ltd", "sector": "Consumer Durables", "industry": "Paints", "isin": "INE021A01026", "face_value": 1.0},
    {"symbol": "AXISBANK", "company_name": "Axis Bank Ltd", "sector": "Financial Services", "industry": "Private Bank", "isin": "INE238A01034", "face_value": 2.0},
    {"symbol": "BAJAJ-AUTO", "company_name": "Bajaj Auto Ltd", "sector": "Automobile and Auto Components", "industry": "2/3 Wheelers", "isin": "INE917I01010", "face_value": 10.0},
    {"symbol": "BAJFINANCE", "company_name": "Bajaj Finance Ltd", "sector": "Financial Services", "industry": "Finance", "isin": "INE296A01024", "face_value": 2.0},
    {"symbol": "BAJAJFINSV", "company_name": "Bajaj Finserv Ltd", "sector": "Financial Services", "industry": "Finance", "isin": "INE918I01026", "face_value": 1.0},
    {"symbol": "BPCL", "company_name": "Bharat Petroleum Corporation Ltd", "sector": "Oil Gas & Consumable Fuels", "industry": "Refineries", "isin": "INE029A01011", "face_value": 10.0},
    {"symbol": "BHARTIARTL", "company_name": "Bharti Airtel Ltd", "sector": "Telecommunication", "industry": "Telecom Services", "isin": "INE397D01024", "face_value": 5.0},
    {"symbol": "BRITANNIA", "company_name": "Britannia Industries Ltd", "sector": "Fast Moving Consumer Goods", "industry": "Packaged Foods", "isin": "INE216A01030", "face_value": 1.0},
    {"symbol": "CIPLA", "company_name": "Cipla Ltd", "sector": "Healthcare", "industry": "Pharma", "isin": "INE059A01026", "face_value": 2.0},
    {"symbol": "COALINDIA", "company_name": "Coal India Ltd", "sector": "Oil Gas & Consumable Fuels", "industry": "Coal", "isin": "INE522F01014", "face_value": 10.0},
    {"symbol": "DRREDDY", "company_name": "Dr Reddy's Laboratories Ltd", "sector": "Healthcare", "industry": "Pharma", "isin": "INE089A01023", "face_value": 1.0},
    {"symbol": "EICHERMOT", "company_name": "Eicher Motors Ltd", "sector": "Automobile and Auto Components", "industry": "2/3 Wheelers", "isin": "INE066A01021", "face_value": 1.0},
    {"symbol": "GRASIM", "company_name": "Grasim Industries Ltd", "sector": "Construction Materials", "industry": "Cement & Cement Products", "isin": "INE047A01021", "face_value": 2.0},
    {"symbol": "HCLTECH", "company_name": "HCL Technologies Ltd", "sector": "Information Technology", "industry": "IT Services & Consulting", "isin": "INE860A01027", "face_value": 2.0},
    {"symbol": "HDFCBANK", "company_name": "HDFC Bank Ltd", "sector": "Financial Services", "industry": "Private Bank", "isin": "INE040A01034", "face_value": 1.0},
    {"symbol": "HDFCLIFE", "company_name": "HDFC Life Insurance Company Ltd", "sector": "Financial Services", "industry": "Insurance", "isin": "INE795G01014", "face_value": 10.0},
    {"symbol": "HEROMOTOCO", "company_name": "Hero MotoCorp Ltd", "sector": "Automobile and Auto Components", "industry": "2/3 Wheelers", "isin": "INE158A01026", "face_value": 2.0},
    {"symbol": "HINDALCO", "company_name": "Hindalco Industries Ltd", "sector": "Metals & Mining", "industry": "Aluminium", "isin": "INE039A01020", "face_value": 1.0},
    {"symbol": "HINDUNILVR", "company_name": "Hindustan Unilever Ltd", "sector": "Fast Moving Consumer Goods", "industry": "FMCG", "isin": "INE030A01027", "face_value": 1.0},
    {"symbol": "ICICIBANK", "company_name": "ICICI Bank Ltd", "sector": "Financial Services", "industry": "Private Bank", "isin": "INE090A01021", "face_value": 2.0},
    {"symbol": "INDUSINDBK", "company_name": "IndusInd Bank Ltd", "sector": "Financial Services", "industry": "Private Bank", "isin": "INE095A01012", "face_value": 10.0},
    {"symbol": "INFY", "company_name": "Infosys Ltd", "sector": "Information Technology", "industry": "IT Services & Consulting", "isin": "INE009A01021", "face_value": 5.0},
    {"symbol": "ITC", "company_name": "ITC Ltd", "sector": "Fast Moving Consumer Goods", "industry": "Cigarettes/Tobacco", "isin": "INE154A01025", "face_value": 1.0},
    {"symbol": "JSWSTEEL", "company_name": "JSW Steel Ltd", "sector": "Metals & Mining", "industry": "Steel", "isin": "INE019A01038", "face_value": 1.0},
    {"symbol": "KOTAKBANK", "company_name": "Kotak Mahindra Bank Ltd", "sector": "Financial Services", "industry": "Private Bank", "isin": "INE237A01028", "face_value": 5.0},
    {"symbol": "LT", "company_name": "Larsen & Toubro Ltd", "sector": "Construction", "industry": "Construction & Engineering", "isin": "INE018A01030", "face_value": 2.0},
    {"symbol": "LTIM", "company_name": "LTIMindtree Ltd", "sector": "Information Technology", "industry": "IT Services & Consulting", "isin": "INE214T01019", "face_value": 1.0},
    {"symbol": "M&M", "company_name": "Mahindra & Mahindra Ltd", "sector": "Automobile and Auto Components", "industry": "Passenger Cars & Utility Vehicles", "isin": "INE101A01026", "face_value": 5.0},
    {"symbol": "MARUTI", "company_name": "Maruti Suzuki India Ltd", "sector": "Automobile and Auto Components", "industry": "Passenger Cars & Utility Vehicles", "isin": "INE585B01010", "face_value": 5.0},
    {"symbol": "NESTLEIND", "company_name": "Nestle India Ltd", "sector": "Fast Moving Consumer Goods", "industry": "Packaged Foods", "isin": "INE239A01024", "face_value": 1.0},
    {"symbol": "NTPC", "company_name": "NTPC Ltd", "sector": "Power", "industry": "Power Generation", "isin": "INE733E01010", "face_value": 10.0},
    {"symbol": "ONGC", "company_name": "Oil and Natural Gas Corporation Ltd", "sector": "Oil Gas & Consumable Fuels", "industry": "Oil Exploration", "isin": "INE213A01029", "face_value": 5.0},
    {"symbol": "POWERGRID", "company_name": "Power Grid Corporation of India Ltd", "sector": "Power", "industry": "Power Transmission", "isin": "INE752E01010", "face_value": 10.0},
    {"symbol": "RELIANCE", "company_name": "Reliance Industries Ltd", "sector": "Oil Gas & Consumable Fuels", "industry": "Refineries", "isin": "INE002A01018", "face_value": 10.0},
    {"symbol": "SBILIFE", "company_name": "SBI Life Insurance Company Ltd", "sector": "Financial Services", "industry": "Insurance", "isin": "INE111W01024", "face_value": 10.0},
    {"symbol": "SBIN", "company_name": "State Bank of India", "sector": "Financial Services", "industry": "Public Bank", "isin": "INE062A01020", "face_value": 1.0},
    {"symbol": "SUNPHARMA", "company_name": "Sun Pharmaceutical Industries Ltd", "sector": "Healthcare", "industry": "Pharma", "isin": "INE044A01036", "face_value": 1.0},
    {"symbol": "TATACONSUM", "company_name": "Tata Consumer Products Ltd", "sector": "Fast Moving Consumer Goods", "industry": "Tea & Coffee", "isin": "INE192A01025", "face_value": 1.0},
    {"symbol": "TATAMOTORS", "company_name": "Tata Motors Ltd", "sector": "Automobile and Auto Components", "industry": "Passenger Cars & Utility Vehicles", "isin": "INE155A01022", "face_value": 2.0},
    {"symbol": "TATASTEEL", "company_name": "Tata Steel Ltd", "sector": "Metals & Mining", "industry": "Steel", "isin": "INE081A01020", "face_value": 1.0},
    {"symbol": "TCS", "company_name": "Tata Consultancy Services Ltd", "sector": "Information Technology", "industry": "IT Services & Consulting", "isin": "INE467B01029", "face_value": 1.0},
    {"symbol": "TECHM", "company_name": "Tech Mahindra Ltd", "sector": "Information Technology", "industry": "IT Services & Consulting", "isin": "INE669C01036", "face_value": 5.0},
    {"symbol": "TITAN", "company_name": "Titan Company Ltd", "sector": "Consumer Durables", "industry": "Gems & Jewellery", "isin": "INE280A01028", "face_value": 1.0},
    {"symbol": "ULTRACEMCO", "company_name": "UltraTech Cement Ltd", "sector": "Construction Materials", "industry": "Cement & Cement Products", "isin": "INE481G01011", "face_value": 10.0},
    {"symbol": "WIPRO", "company_name": "Wipro Ltd", "sector": "Information Technology", "industry": "IT Services & Consulting", "isin": "INE075A01022", "face_value": 2.0},
    {"symbol": "DIVISLAB", "company_name": "Divi's Laboratories Ltd", "sector": "Healthcare", "industry": "Pharma", "isin": "INE361B01024", "face_value": 2.0},
    {"symbol": "SHRIRAMFIN", "company_name": "Shriram Finance Ltd", "sector": "Financial Services", "industry": "Finance", "isin": "INE721A01013", "face_value": 10.0},
]


def seed_dim_stock() -> int:
    """Insert Nifty 50 constituents into dim_stock.

    Idempotent: uses ON CONFLICT DO UPDATE to refresh metadata.

    Returns:
        Number of rows upserted.
    """
    engine = get_engine()
    now = datetime.now()

    upsert_sql = text("""
        INSERT INTO dim_stock (
            symbol, company_name, sector, industry, nifty50_member,
            market_cap_cr, listing_date, face_value, isin, last_updated
        ) VALUES (
            :symbol, :company_name, :sector, :industry, TRUE,
            NULL, '2000-01-01', :face_value, :isin, :now
        )
        ON CONFLICT (symbol) DO UPDATE SET
            company_name = EXCLUDED.company_name,
            sector = EXCLUDED.sector,
            industry = EXCLUDED.industry,
            nifty50_member = TRUE,
            face_value = EXCLUDED.face_value,
            isin = EXCLUDED.isin,
            last_updated = :now
    """)

    count = 0
    with engine.connect() as conn:
        for stock in NIFTY50_SEED:
            stock["now"] = now
            conn.execute(upsert_sql, stock)
            count += 1
        conn.commit()

    logger.info(f"Seeded {count} stocks into dim_stock")
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_dim_stock()
    print("dim_stock seeded with 50 Nifty 50 constituents.")
