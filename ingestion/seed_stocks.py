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
    {"symbol": "20MICRONS", "company_name": "20 Microns Ltd", "sector": "Materials", "industry": "Mining & Metals", "isin": "INE144J01027", "face_value": 5.0},
      {"symbol": "BEL", "company_name": "Bharat Electronics Ltd", "sector": "Aerospace & Defence", "industry": "Defence", "isin": "INE263A01024", "face_value": 1.0},
  {"symbol": "ETERNAL", "company_name": "Eternal Ltd", "sector": "Technology", "industry": "e-Commerce", "isin": "INE758T01015", "face_value": 1.0},
  {"symbol": "INDIGO", "company_name": "InterGlobe Aviation Ltd", "sector": "Services", "industry": "Airlines", "isin": "INE646L01027", "face_value": 10.0},
  {"symbol": "JIOFIN", "company_name": "Jio Financial Services Ltd", "sector": "Financial Services", "industry": "Investment Company", "isin": "INE758E01017", "face_value": 10.0},
  {"symbol": "MAXHEALTH", "company_name": "Max Healthcare Institute Ltd", "sector": "Healthcare", "industry": "Hospitals & Diagnostic Centres", "isin": "INE027H01010", "face_value": 10.0},
  {"symbol": "TMPV", "company_name": "Tata Motors Passenger Vehicles Ltd", "sector": "Automobile", "industry": "Passenger Cars & Utility Vehicles", "isin": "INE155A01022", "face_value": 2.0},
  {"symbol": "TRENT", "company_name": "Trent Ltd", "sector": "Consumer Discretionary", "industry": "Retail - Apparel & Accessories", "isin": "INE848E01016", "face_value": 1.0},
  {
  "symbol": "011NSETEST",
  "company_name": "011NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN005",
  "face_value": 1000.0
 },
 {
  "symbol": "021NSETEST",
  "company_name": "021NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN006",
  "face_value": 1000.0
 },
 {
  "symbol": "031NSETEST",
  "company_name": "031NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN007",
  "face_value": 1000.0
 },
 {
  "symbol": "041NSETEST",
  "company_name": "041NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN008",
  "face_value": 1000.0
 },
 {
  "symbol": "051NSETEST",
  "company_name": "051NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN009",
  "face_value": 1000.0
 },
 {
  "symbol": "061NSETEST",
  "company_name": "061NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN010",
  "face_value": 1000.0
 },
 {
  "symbol": "071NSETEST",
  "company_name": "071NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN011",
  "face_value": 1000.0
 },
 {
  "symbol": "081NSETEST",
  "company_name": "081NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN012",
  "face_value": 1000.0
 },
 {
  "symbol": "091NSETEST",
  "company_name": "091NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN013",
  "face_value": 1000.0
 },
 {
  "symbol": "101NSETEST",
  "company_name": "101NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN014",
  "face_value": 1000.0
 },
 {
  "symbol": "111NSETEST",
  "company_name": "111NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN015",
  "face_value": 1000.0
 },
 {
  "symbol": "11NSETEST",
  "company_name": "11NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN001",
  "face_value": 1000.0
 },
 {
  "symbol": "121NSETEST",
  "company_name": "121NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN016",
  "face_value": 1000.0
 },
 {
  "symbol": "131NSETEST",
  "company_name": "131NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN017",
  "face_value": 1000.0
 },
 {
  "symbol": "141NSETEST",
  "company_name": "141NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN018",
  "face_value": 1000.0
 },
 {
  "symbol": "151NSETEST",
  "company_name": "151NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN019",
  "face_value": 1000.0
 },
 {
  "symbol": "161NSETEST",
  "company_name": "161NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN020",
  "face_value": 1000.0
 },
 {
  "symbol": "171NSETEST",
  "company_name": "171NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN021",
  "face_value": 1000.0
 },
 {
  "symbol": "181NSETEST",
  "company_name": "181NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN022",
  "face_value": 1000.0
 },
 {
  "symbol": "20MICRONS",
  "company_name": "20 MICRONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE144J01027",
  "face_value": 500.0
 },
 {
  "symbol": "21STCENMGM",
  "company_name": "21ST CENTURY MGMT SERVICE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE253B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "360ONE",
  "company_name": "360 ONE WAM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE466L01038",
  "face_value": 100.0
 },
 {
  "symbol": "3BBLACKBIO",
  "company_name": "3B BLACKBIO DX LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE994E01018",
  "face_value": 1000.0
 },
 {
  "symbol": "3IINFO-RE",
  "company_name": "3I INFOTECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE748C20012",
  "face_value": 1000.0
 },
 {
  "symbol": "3IINFOLTD",
  "company_name": "3I INFOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE748C01038",
  "face_value": 1000.0
 },
 {
  "symbol": "3IINFOTECH",
  "company_name": "3I INFOTECH LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE748C01020",
  "face_value": 1000.0
 },
 {
  "symbol": "3MINDIA",
  "company_name": "3M INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE470A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "3PLAND",
  "company_name": "3P LAND HOLDINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE105C01023",
  "face_value": 200.0
 },
 {
  "symbol": "5PAISA",
  "company_name": "5PAISA CAPITAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE618L01018",
  "face_value": 1000.0
 },
 {
  "symbol": "5PAISA-RE",
  "company_name": "5PAISA CAPITAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE618L20018",
  "face_value": 1000.0
 },
 {
  "symbol": "63MOONS",
  "company_name": "63 MOONS TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE111B01023",
  "face_value": 200.0
 },
 {
  "symbol": "A2ZINFRA",
  "company_name": "A2Z INFRA ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE619I01012",
  "face_value": 1000.0
 },
 {
  "symbol": "AAATECH",
  "company_name": "AAA TECHNOLOGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0D0U01013",
  "face_value": 1000.0
 },
 {
  "symbol": "AADHARHFC",
  "company_name": "AADHAR HOUSING FINANCE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE883F01010",
  "face_value": 1000.0
 },
 {
  "symbol": "AAKASH",
  "company_name": "AAKASH EXPLORATION SER L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE087Z01024",
  "face_value": 100.0
 },
 {
  "symbol": "AAREYDRUGS",
  "company_name": "AAREY DRUGS & PHARM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE198H01019",
  "face_value": 1000.0
 },
 {
  "symbol": "AARNAV",
  "company_name": "AARNAV FASHIONS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE750R01016",
  "face_value": 1000.0
 },
 {
  "symbol": "AARON",
  "company_name": "AARON INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE721Z01010",
  "face_value": 1000.0
 },
 {
  "symbol": "AARTECH",
  "company_name": "AARTECH SOLONICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01C001026",
  "face_value": 500.0
 },
 {
  "symbol": "AARTI-RE",
  "company_name": "AARTI SURFACTANTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE09EO20013",
  "face_value": 1000.0
 },
 {
  "symbol": "AARTIDRUGS",
  "company_name": "AARTI DRUGS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE767A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "AARTIIND",
  "company_name": "AARTI INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE769A01020",
  "face_value": 500.0
 },
 {
  "symbol": "AARTIPHARM",
  "company_name": "AARTI PHARMALABS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0LRU01027",
  "face_value": 500.0
 },
 {
  "symbol": "AARTISURF",
  "company_name": "AARTI SURFACTANTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE09EO01013",
  "face_value": 1000.0
 },
 {
  "symbol": "AARVI",
  "company_name": "AARVI ENCON LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE754X01016",
  "face_value": 1000.0
 },
 {
  "symbol": "AAVAS",
  "company_name": "AAVAS FINANCIERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE216P01012",
  "face_value": 1000.0
 },
 {
  "symbol": "AB10BKINAV",
  "company_name": "BIRLASLAMC - AB10BKINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000339",
  "face_value": 1000.0
 },
 {
  "symbol": "ABAN",
  "company_name": "ABAN OFFSHORE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE421A01028",
  "face_value": 200.0
 },
 {
  "symbol": "ABANSENT",
  "company_name": "ABANS ENTERPRISES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE365O01028",
  "face_value": 200.0
 },
 {
  "symbol": "ABB",
  "company_name": "ABB INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE117A01022",
  "face_value": 200.0
 },
 {
  "symbol": "ABBOTINDIA",
  "company_name": "ABBOTT INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE358A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "ABCAPITAL",
  "company_name": "ADITYA BIRLA CAPITAL LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE674K01013",
  "face_value": 1000.0
 },
 {
  "symbol": "ABCOTS",
  "company_name": "A B COTSPIN INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE08PH01015",
  "face_value": 1000.0
 },
 {
  "symbol": "ABDL",
  "company_name": "ALLIED BLEND N DISTILS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE552Z01027",
  "face_value": 200.0
 },
 {
  "symbol": "ABFRL",
  "company_name": "ADITYA BIRLA FASHION & RT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE647O01011",
  "face_value": 1000.0
 },
 {
  "symbol": "ABFRL-RE",
  "company_name": "ADITYA BIRLA FASHION RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE647O20011",
  "face_value": 1000.0
 },
 {
  "symbol": "ABGSEC",
  "company_name": "BIRLASLAMC - ABGSEC",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KC1134",
  "face_value": 10000.0
 },
 {
  "symbol": "ABGSECINAV",
  "company_name": "BIRLASLAMC - ABGSECINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000231",
  "face_value": 10000.0
 },
 {
  "symbol": "ABHISHEK",
  "company_name": "ABHISHEK CORPORATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE004I01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ABIN-RE1",
  "company_name": "A B INFRABUILD LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00YB20025",
  "face_value": 1000.0
 },
 {
  "symbol": "ABINFRA",
  "company_name": "A B INFRABUILD LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00YB01025",
  "face_value": 100.0
 },
 {
  "symbol": "ABLBL",
  "company_name": "ADITYA BIRLA LIFES BRAN L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE14LE01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ABMINTLLTD",
  "company_name": "ABM INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE251C01025",
  "face_value": 1000.0
 },
 {
  "symbol": "ABMINTLTD",
  "company_name": "ABM INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE251C01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ABMKNO",
  "company_name": "A B M KNOWLEDGEWARE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE850B01026",
  "face_value": 500.0
 },
 {
  "symbol": "ABREL",
  "company_name": "ADITYA BIRLA REAL EST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE055A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "ABSL10BANK",
  "company_name": "BIRLASLAMC - ABSL10BANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KC1670",
  "face_value": 1000.0
 },
 {
  "symbol": "ABSLAMC",
  "company_name": "ADIT BIRL SUN LIF AMC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE404A01024",
  "face_value": 500.0
 },
 {
  "symbol": "ABSLBAINAV",
  "company_name": "ABSLBANETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000049",
  "face_value": 100.0
 },
 {
  "symbol": "ABSLBANETF",
  "company_name": "BIRLASLAMC - ABSLBANETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KB17D5",
  "face_value": 100.0
 },
 {
  "symbol": "ABSLLIQUID",
  "company_name": "BIRLASLAMC - ABSLLIQUID",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KB18T9",
  "face_value": 100000.0
 },
 {
  "symbol": "ABSLLQINAV",
  "company_name": "BIRLASLAMC - ABSLLQINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000180",
  "face_value": 100000.0
 },
 {
  "symbol": "ABSLMSCIN",
  "company_name": "BIRLASLAMC - ABSLMSCIN",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KC1662",
  "face_value": 1000.0
 },
 {
  "symbol": "ABSLNN50ET",
  "company_name": "BIRLASLAMC - ABSLNN50ET",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KB16D7",
  "face_value": 100.0
 },
 {
  "symbol": "ABSLNNINAV",
  "company_name": "ABSLNN50ET INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000053",
  "face_value": 100.0
 },
 {
  "symbol": "ABSLPSE",
  "company_name": "BIRLASLAMC-ABSLPSE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KB19Z4",
  "face_value": 100.0
 },
 {
  "symbol": "ABSMSCINAV",
  "company_name": "BIRLASLAMC - ABSMSCINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000337",
  "face_value": 1000.0
 },
 {
  "symbol": "ABSPSEINAV",
  "company_name": "BIRLASLAMC-ABSPSEINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000223",
  "face_value": 100.0
 },
 {
  "symbol": "ACC",
  "company_name": "ACC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE012A01025",
  "face_value": 1000.0
 },
 {
  "symbol": "ACCELYA",
  "company_name": "ACCELYA SOLN INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE793A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "ACCURACY",
  "company_name": "ACCURACY SHIPPING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE648Z01023",
  "face_value": 100.0
 },
 {
  "symbol": "ACE",
  "company_name": "ACTION CONST EQUIP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE731H01025",
  "face_value": 200.0
 },
 {
  "symbol": "ACEINTEG",
  "company_name": "ACE INTEGRATED SOLU. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE543V01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ACELAB",
  "company_name": "A C E LABORATORIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE522901011",
  "face_value": 1000.0
 },
 {
  "symbol": "ACI",
  "company_name": "ARCHEAN CHEMICAL IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE128X01021",
  "face_value": 200.0
 },
 {
  "symbol": "ACL",
  "company_name": "ANDHRA CEMENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE666E01020",
  "face_value": 1000.0
 },
 {
  "symbol": "ACLGATI",
  "company_name": "ALLCARGO GATI LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE152B01027",
  "face_value": 200.0
 },
 {
  "symbol": "ACMESOLAR",
  "company_name": "ACME SOLAR HOLDINGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE622W01025",
  "face_value": 200.0
 },
 {
  "symbol": "ACSTECH",
  "company_name": "A C S TECHNOLOGIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE366C01021",
  "face_value": 1000.0
 },
 {
  "symbol": "ACUTAAS",
  "company_name": "ACUTAAS CHEMICALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00FF01025",
  "face_value": 500.0
 },
 {
  "symbol": "ADANI-RE",
  "company_name": "ADANI ENTERPRISES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE423A20016",
  "face_value": 100.0
 },
 {
  "symbol": "ADANIENSOL",
  "company_name": "ADANI ENERGY SOLUTION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE931S01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ADANIENT",
  "company_name": "ADANI ENTERPRISES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE423A01024",
  "face_value": 100.0
 },
 {
  "symbol": "ADANIGREEN",
  "company_name": "ADANI GREEN ENERGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE364U01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ADANIPORTS",
  "company_name": "ADANI PORT & SEZ LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE742F01042",
  "face_value": 200.0
 },
 {
  "symbol": "ADANIPOWER",
  "company_name": "ADANI POWER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE814H01029",
  "face_value": 200.0
 },
 {
  "symbol": "ADARSHCHEM",
  "company_name": "ADARSH CHEMICALS & FERT.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE442501016",
  "face_value": 1000.0
 },
 {
  "symbol": "ADFFOODS",
  "company_name": "ADF FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE982B01027",
  "face_value": 200.0
 },
 {
  "symbol": "ADHUNIK",
  "company_name": "ADHUNIK METALIKS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE400H01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ADITYASPIN",
  "company_name": "ADITYA SPINNERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE442601014",
  "face_value": 1000.0
 },
 {
  "symbol": "ADL",
  "company_name": "ARCHIDPLY DECOR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0CHO01012",
  "face_value": 1000.0
 },
 {
  "symbol": "ADOR",
  "company_name": "ADOR WELDING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE045A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ADRO-RE",
  "company_name": "ADROIT INFOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE737B20017",
  "face_value": 1000.0
 },
 {
  "symbol": "ADROITINFO",
  "company_name": "ADROIT INFOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE737B01033",
  "face_value": 1000.0
 },
 {
  "symbol": "ADSL",
  "company_name": "ALLIED DIGITAL SERV. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE102I01027",
  "face_value": 500.0
 },
 {
  "symbol": "ADVAIT",
  "company_name": "ADVAIT ENRGY TRANSITION L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0ALI01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ADVANCE",
  "company_name": "ADVANCE AGROLIFE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1B0W01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ADVANIHOTR",
  "company_name": "ADVANI HOT.& RES.(I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE199C01026",
  "face_value": 200.0
 },
 {
  "symbol": "ADVENTHTL",
  "company_name": "ADVENT HOTELS INTERNATI L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE28GN01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ADVENZYMES",
  "company_name": "ADVANCED ENZYME TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE837H01020",
  "face_value": 200.0
 },
 {
  "symbol": "AEC",
  "company_name": "AEC (I) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE441901019",
  "face_value": 1000.0
 },
 {
  "symbol": "AEGISLOG",
  "company_name": "AEGIS LOGISTICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE208C01025",
  "face_value": 100.0
 },
 {
  "symbol": "AEGISVOPAK",
  "company_name": "AEGIS VOPAK TERMINALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0INX01018",
  "face_value": 1000.0
 },
 {
  "symbol": "AEPL",
  "company_name": "ARTEMIS ELECTRICALS & P L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE757T01025",
  "face_value": 100.0
 },
 {
  "symbol": "AEQUS",
  "company_name": "AEQUS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE947N01017",
  "face_value": 1000.0
 },
 {
  "symbol": "AEROENTER",
  "company_name": "AEROFLEX ENTERPRISES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE065D01027",
  "face_value": 200.0
 },
 {
  "symbol": "AEROFLEX",
  "company_name": "AEROFLEX INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE024001021",
  "face_value": 200.0
 },
 {
  "symbol": "AERONEU",
  "company_name": "AEROFLEX NEU LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE035801013",
  "face_value": 1000.0
 },
 {
  "symbol": "AETHER",
  "company_name": "AETHER INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0BWX01014",
  "face_value": 1000.0
 },
 {
  "symbol": "AFCONS",
  "company_name": "AFCONS INFRASTRUCTURE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE101I01011",
  "face_value": 1000.0
 },
 {
  "symbol": "AFFLE",
  "company_name": "AFFLE 3I LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00WC01027",
  "face_value": 200.0
 },
 {
  "symbol": "AFFORDABLE",
  "company_name": "AFFORD ROBO & AUTO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE692Z01013",
  "face_value": 1000.0
 },
 {
  "symbol": "AFIL",
  "company_name": "AKME FINTRADE (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE916Y01027",
  "face_value": 100.0
 },
 {
  "symbol": "AFL-RE",
  "company_name": "ARVIND FASHIONS LTD-RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE955V20021",
  "face_value": 400.0
 },
 {
  "symbol": "AFSL",
  "company_name": "ABANS FINANCIAL SRVCS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00ZE01026",
  "face_value": 200.0
 },
 {
  "symbol": "AGARIND",
  "company_name": "AGARWAL INDS CORP LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE204E01012",
  "face_value": 1000.0
 },
 {
  "symbol": "AGARWALEYE",
  "company_name": "DR AGARWALS HEALTH CARE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE943P01029",
  "face_value": 100.0
 },
 {
  "symbol": "AGI",
  "company_name": "AGI GREENPAC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE415A01038",
  "face_value": 200.0
 },
 {
  "symbol": "AGIIL",
  "company_name": "AGI INFRA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE976R01033",
  "face_value": 100.0
 },
 {
  "symbol": "AGRIHATCH",
  "company_name": "AGRITECH HATCHERIED AND F",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE442901018",
  "face_value": 1000.0
 },
 {
  "symbol": "AGRITECH",
  "company_name": "AGRI-TECH (INDIA) LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE449G01018",
  "face_value": 1000.0
 },
 {
  "symbol": "AGROPHOS",
  "company_name": "AGRO PHOS INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE740V01019",
  "face_value": 1000.0
 },
 {
  "symbol": "AGSTRA",
  "company_name": "AGS TRANSACT TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE583L01014",
  "face_value": 1000.0
 },
 {
  "symbol": "AHCL",
  "company_name": "ANLON HEALTHCARE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0Y8W01025",
  "face_value": 200.0
 },
 {
  "symbol": "AHLADA",
  "company_name": "AHLADA ENGINEERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00PV01013",
  "face_value": 1000.0
 },
 {
  "symbol": "AHLEAST",
  "company_name": "ASIAN HOTELS (EAST) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE926K01017",
  "face_value": 1000.0
 },
 {
  "symbol": "AHLUCONT",
  "company_name": "AHLUWALIA CONT IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE758C01029",
  "face_value": 200.0
 },
 {
  "symbol": "AHLWEST",
  "company_name": "ASIAN HOTELS (WEST) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE915K01010",
  "face_value": 1000.0
 },
 {
  "symbol": "AIAENG",
  "company_name": "AIA ENGINEERING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE212H01026",
  "face_value": 200.0
 },
 {
  "symbol": "AIFL",
  "company_name": "ASHAPURA INTI FASHION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE428O01016",
  "face_value": 1000.0
 },
 {
  "symbol": "AIIL",
  "company_name": "AUTHUM INVEST & INFRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE206F01022",
  "face_value": 100.0
 },
 {
  "symbol": "AIMCOPEST",
  "company_name": "AIMCO PESTICIDES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE008B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "AIRAN",
  "company_name": "AIRAN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE645W01026",
  "face_value": 200.0
 },
 {
  "symbol": "AIROLAM",
  "company_name": "AIRO LAM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE801L01010",
  "face_value": 1000.0
 },
 {
  "symbol": "AIRTEL-RE",
  "company_name": "BHARTI AIRTEL LIMITED-RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE397D20024",
  "face_value": 500.0
 },
 {
  "symbol": "AJANTPHARM",
  "company_name": "AJANTA PHARMA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE031B01049",
  "face_value": 200.0
 },
 {
  "symbol": "AJAXENGG",
  "company_name": "AJAX ENGINEERING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE274Y01021",
  "face_value": 100.0
 },
 {
  "symbol": "AJMERA",
  "company_name": "AJMERA REALTY & INF I LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE298G01035",
  "face_value": 200.0
 },
 {
  "symbol": "AJOONI",
  "company_name": "AJOONI BIOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE820Y01021",
  "face_value": 200.0
 },
 {
  "symbol": "AJOONI-RE",
  "company_name": "AJOONI BIOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE820Y20013",
  "face_value": 200.0
 },
 {
  "symbol": "AJOONI-RE1",
  "company_name": "AJOONI BIOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE820Y20021",
  "face_value": 200.0
 },
 {
  "symbol": "AJRINFRA",
  "company_name": "AJR INFRA & TOLLING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE181G01025",
  "face_value": 200.0
 },
 {
  "symbol": "AKAIMPEX",
  "company_name": "AKAI IMPEX LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE443401018",
  "face_value": 1000.0
 },
 {
  "symbol": "AKARLAMIN",
  "company_name": "AKAR LAMINATORS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE984C01013",
  "face_value": 1000.0
 },
 {
  "symbol": "AKASH",
  "company_name": "AKASH INFRA-PROJECTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE737W01013",
  "face_value": 1000.0
 },
 {
  "symbol": "AKCAPIT",
  "company_name": "A K CAPITAL SERVICES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE701G01012",
  "face_value": 1000.0
 },
 {
  "symbol": "AKG",
  "company_name": "AKG EXIM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00Y801016",
  "face_value": 1000.0
 },
 {
  "symbol": "AKG-RE",
  "company_name": "AKG EXIM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00Y820016",
  "face_value": 1000.0
 },
 {
  "symbol": "AKGACOUST",
  "company_name": "AKG ACOUSTICS (I) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE442001017",
  "face_value": 1000.0
 },
 {
  "symbol": "AKI",
  "company_name": "AKI INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE642Z01026",
  "face_value": 200.0
 },
 {
  "symbol": "AKSH-RE",
  "company_name": "AKSHAR SPINTEX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE256Z20017",
  "face_value": 100.0
 },
 {
  "symbol": "AKSHAR",
  "company_name": "AKSHAR SPINTEX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE256Z01025",
  "face_value": 100.0
 },
 {
  "symbol": "AKSHARCHEM",
  "company_name": "AKSHARCHEM INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE542B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "AKSHOPTFBR",
  "company_name": "AKSH OPTIFIBRE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE523B01011",
  "face_value": 500.0
 },
 {
  "symbol": "AKUMS",
  "company_name": "AKUMS DRUGS AND PHARMA L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE09XN01023",
  "face_value": 200.0
 },
 {
  "symbol": "ALANKIT",
  "company_name": "ALANKIT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE914E01040",
  "face_value": 100.0
 },
 {
  "symbol": "ALBERTDAVD",
  "company_name": "ALBERT DAVID LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE155C01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ALBRMORARJ",
  "company_name": "ALBRIGHT & WILSON CHE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE255B01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ALCHEM",
  "company_name": "ALCHEMIST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE964B01033",
  "face_value": 1000.0
 },
 {
  "symbol": "ALEMBICLTD",
  "company_name": "ALEMBIC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE426A01027",
  "face_value": 200.0
 },
 {
  "symbol": "ALFREDHERB",
  "company_name": "ALFRED HERBERT (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE528801017",
  "face_value": 1000.0
 },
 {
  "symbol": "ALGOQUANT",
  "company_name": "ALGOQUANT FINTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE598D01035",
  "face_value": 100.0
 },
 {
  "symbol": "ALIANCREDT",
  "company_name": "ALLIANCE CREDIT & INVEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE529101011",
  "face_value": 1000.0
 },
 {
  "symbol": "ALICON",
  "company_name": "ALICON CASTALLOY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE062D01024",
  "face_value": 500.0
 },
 {
  "symbol": "ALIVUS",
  "company_name": "ALIVUS LIFE SCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE03Q201024",
  "face_value": 200.0
 },
 {
  "symbol": "ALKALI",
  "company_name": "ALKALI METALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE773I01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ALKEM",
  "company_name": "ALKEM LABORATORIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE540L01014",
  "face_value": 200.0
 },
 {
  "symbol": "ALKYLAMINE",
  "company_name": "ALKYL AMINES CHEM. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE150B01039",
  "face_value": 200.0
 },
 {
  "symbol": "ALLCARGO",
  "company_name": "ALLCARGO LOGISTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE418H01029",
  "face_value": 200.0
 },
 {
  "symbol": "ALLDIGI",
  "company_name": "ALLDIGI TECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE835G01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ALLTIME",
  "company_name": "ALL TIME PLASTICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0GV601021",
  "face_value": 200.0
 },
 {
  "symbol": "ALMONDZ",
  "company_name": "ALMONDZ GLOBAL SEC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE326B01035",
  "face_value": 100.0
 },
 {
  "symbol": "ALOKINDS",
  "company_name": "ALOK INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE270A01029",
  "face_value": 100.0
 },
 {
  "symbol": "ALOKTEXT",
  "company_name": "ALOK INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE270A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "ALPA",
  "company_name": "ALPA LABORATORIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE385I01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ALPHA",
  "company_name": "KOTAKMAMC - KOTAKALPHA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1IA5",
  "face_value": 1000.0
 },
 {
  "symbol": "ALPHADRUG",
  "company_name": "ALPHA DRUG (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE444101013",
  "face_value": 1000.0
 },
 {
  "symbol": "ALPHAETF",
  "company_name": "MIRAEAMC - ALPHAETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01KU7",
  "face_value": 1000.0
 },
 {
  "symbol": "ALPHAGEO",
  "company_name": "ALPHAGEO (INDIA) LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE137C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ALPHAINAV",
  "company_name": "MIRAEAMC - ALPHAINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000202",
  "face_value": 1000.0
 },
 {
  "symbol": "ALPINEIND",
  "company_name": "ALPINE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE444301019",
  "face_value": 1000.0
 },
 {
  "symbol": "ALPL30IETF",
  "company_name": "ICICIPRAMC - ICICIALPLV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC17V7",
  "face_value": 100.0
 },
 {
  "symbol": "ALPSINDUS",
  "company_name": "ALPS INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE093B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "ALSAMARINE",
  "company_name": "ALSA MARINE AND HARVESTS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE444501014",
  "face_value": 1000.0
 },
 {
  "symbol": "ALTOS",
  "company_name": "ALTOS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE490401010",
  "face_value": 1000.0
 },
 {
  "symbol": "AMAGI",
  "company_name": "AMAGI MEDIA LABS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE121R01077",
  "face_value": 500.0
 },
 {
  "symbol": "AMANTA",
  "company_name": "AMANTA HEALTHCARE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE084K01015",
  "face_value": 1000.0
 },
 {
  "symbol": "AMARDYCHEM",
  "company_name": "AMAR DYECHEM LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE444701010",
  "face_value": 10000.0
 },
 {
  "symbol": "AMBALALSA",
  "company_name": "AMBALAL SARABHAI ENT L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE432A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "AMBASARABH",
  "company_name": "AMBALAL SARABHAI ENTERP.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYY000004",
  "face_value": 1000.0
 },
 {
  "symbol": "AMBER",
  "company_name": "AMBER ENTERPRISES (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE371P01015",
  "face_value": 1000.0
 },
 {
  "symbol": "AMBICAAGAR",
  "company_name": "AMBICA AGAR & AROMAINDLTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE792B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "AMBIKCO",
  "company_name": "AMBIKA COTTON MILL LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE540G01014",
  "face_value": 1000.0
 },
 {
  "symbol": "AMBUJACEM",
  "company_name": "AMBUJA CEMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE079A01024",
  "face_value": 200.0
 },
 {
  "symbol": "AMBUJELCST",
  "company_name": "AMBUJA ELECTROCASTING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE445001014",
  "face_value": 1000.0
 },
 {
  "symbol": "AMDIND",
  "company_name": "AMD INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE005I01014",
  "face_value": 1000.0
 },
 {
  "symbol": "AMFORGEIND",
  "company_name": "AMFORGE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE991A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "AMIRCHAND",
  "company_name": "AMIR CHAND JAG KUM (E) L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE05TO01019",
  "face_value": 1000.0
 },
 {
  "symbol": "AMJLAND",
  "company_name": "AMJ LAND HOLDINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE606A01024",
  "face_value": 200.0
 },
 {
  "symbol": "AMNPLST",
  "company_name": "AMINES & PLASTICIZERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE275D01022",
  "face_value": 200.0
 },
 {
  "symbol": "AMRUTANJAN",
  "company_name": "AMRUTAJAN HEALTH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE098F01031",
  "face_value": 100.0
 },
 {
  "symbol": "AMRUTIND",
  "company_name": "AMRUT INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE389801015",
  "face_value": 1000.0
 },
 {
  "symbol": "AMTEKAUTO",
  "company_name": "AMTEK AUTO LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE130C01021",
  "face_value": 200.0
 },
 {
  "symbol": "ANANDRATHI",
  "company_name": "ANAND RATHI WEALTH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE463V01026",
  "face_value": 500.0
 },
 {
  "symbol": "ANANTRAJ",
  "company_name": "ANANT RAJ LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE242C01024",
  "face_value": 200.0
 },
 {
  "symbol": "ANDHRACEMT",
  "company_name": "ANDHRA CEMENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE666E01012",
  "face_value": 1000.0
 },
 {
  "symbol": "ANDHRAPAP",
  "company_name": "ANDHRA PAPER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE435A01051",
  "face_value": 200.0
 },
 {
  "symbol": "ANDHRAPET",
  "company_name": "ANDHRA PETROCHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE714B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "ANDHRSUGAR",
  "company_name": "ANDHRA SUGARS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE715B01021",
  "face_value": 200.0
 },
 {
  "symbol": "ANDREWYU",
  "company_name": "ANDREW YULE & CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE449C01025",
  "face_value": 200.0
 },
 {
  "symbol": "ANDREWYULE",
  "company_name": "ANDREW YULE & CO. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE001501019",
  "face_value": 1000.0
 },
 {
  "symbol": "ANGELONE",
  "company_name": "ANGEL ONE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE732I01021",
  "face_value": 100.0
 },
 {
  "symbol": "ANIKINDS",
  "company_name": "ANIK INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE087B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ANKITMETAL",
  "company_name": "ANKIT MET & POW LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE106I01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ANMOL",
  "company_name": "ANMOL INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02AR01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ANSALAPI",
  "company_name": "ANSAL PROP & INFRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE436A01026",
  "face_value": 500.0
 },
 {
  "symbol": "ANSALHSG",
  "company_name": "ANSAL HOUSING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE880B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "ANTELOPUS",
  "company_name": "ANTELOPUS SELAN ENRGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE818A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ANTFRIBEAR",
  "company_name": "ANTIFRICTION BEARING CORP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE779A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "ANTGRAPHIC",
  "company_name": "ANTARCTICA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE414B01021",
  "face_value": 100.0
 },
 {
  "symbol": "ANTHEM",
  "company_name": "ANTHEM BIOSCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0CZ201020",
  "face_value": 200.0
 },
 {
  "symbol": "ANUHPHR",
  "company_name": "ANUH PHARMA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE489G01022",
  "face_value": 500.0
 },
 {
  "symbol": "ANUP",
  "company_name": "THE ANUP ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE294Z01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ANURAS",
  "company_name": "ANUPAM RASAYAN INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE930P01018",
  "face_value": 1000.0
 },
 {
  "symbol": "AOGOLDINAV",
  "company_name": "AONEAMC - AOGOLDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000299",
  "face_value": 1000.0
 },
 {
  "symbol": "AONE50INAV",
  "company_name": "AONEAMC - AONE50INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000316",
  "face_value": 1000.0
 },
 {
  "symbol": "AONEGOLD",
  "company_name": "AONEAMC - AONEGOLD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF1J2R01114",
  "face_value": 1000.0
 },
 {
  "symbol": "AONELIINAV",
  "company_name": "AONEAMC - AONELIINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000270",
  "face_value": 100000.0
 },
 {
  "symbol": "AONELIQUID",
  "company_name": "AONEAMC - AONELIQUID",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF1J2R01056",
  "face_value": 100000.0
 },
 {
  "symbol": "AONENFINAV",
  "company_name": "AONEAMC - AONENFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000279",
  "face_value": 1000.0
 },
 {
  "symbol": "AONENIFTY",
  "company_name": "AONEAMC - AONENIFTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF1J2R01064",
  "face_value": 1000.0
 },
 {
  "symbol": "AONESIINAV",
  "company_name": "AONEAMC - AONESIINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000338",
  "face_value": 1000.0
 },
 {
  "symbol": "AONESILVER",
  "company_name": "AONEAMC - AONESILVER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF1J2R01171",
  "face_value": 1000.0
 },
 {
  "symbol": "AONETMMQ50",
  "company_name": "AONEAMC - AONETMMQ50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF1J2R01148",
  "face_value": 1000.0
 },
 {
  "symbol": "AONETOINAV",
  "company_name": "AONEAMC - AONETOINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000260",
  "face_value": 1000.0
 },
 {
  "symbol": "AONETOTAL",
  "company_name": "AONEAMC - AONETOTAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF1J2R01015",
  "face_value": 1000.0
 },
 {
  "symbol": "APARINDS",
  "company_name": "APAR INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE372A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "APCL",
  "company_name": "ANJANI PORTLAND CEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE071F01012",
  "face_value": 1000.0
 },
 {
  "symbol": "APCL-RE",
  "company_name": "ANJANI PORTLAND CEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE071F20012",
  "face_value": 1000.0
 },
 {
  "symbol": "APCOTEXIND",
  "company_name": "APCOTEX INDUSTRIES LIMITE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE116A01032",
  "face_value": 200.0
 },
 {
  "symbol": "APEX",
  "company_name": "APEX FROZEN FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE346W01013",
  "face_value": 1000.0
 },
 {
  "symbol": "APLAPOLLO",
  "company_name": "APL APOLLO TUBES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE702C01027",
  "face_value": 200.0
 },
 {
  "symbol": "APLLTD",
  "company_name": "ALEMBIC PHARMA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE901L01018",
  "face_value": 200.0
 },
 {
  "symbol": "APOLLO",
  "company_name": "APOLLO MICRO SYSTEMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE713T01028",
  "face_value": 100.0
 },
 {
  "symbol": "APOLLOHOSP",
  "company_name": "APOLLO HOSPITALS ENTER. L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE437A01024",
  "face_value": 500.0
 },
 {
  "symbol": "APOLLOPIPE",
  "company_name": "APOLLO PIPES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE126J01016",
  "face_value": 1000.0
 },
 {
  "symbol": "APOLLOTUBE",
  "company_name": "APOLLO TUBES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE004301011",
  "face_value": 1000.0
 },
 {
  "symbol": "APOLLOTYRE",
  "company_name": "APOLLO TYRES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE438A01022",
  "face_value": 100.0
 },
 {
  "symbol": "APOLSINHOT",
  "company_name": "APOLLO SINDOORI HOTEL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE451F01024",
  "face_value": 500.0
 },
 {
  "symbol": "APPLECREDT",
  "company_name": "APPLE CREDIT CORPORATION",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE212A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "APPLEIND",
  "company_name": "APPLE FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE096A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "APTECHT",
  "company_name": "APTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE266F01018",
  "face_value": 1000.0
 },
 {
  "symbol": "APTUS",
  "company_name": "APTUS VALUE HSG FIN I LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE852O01025",
  "face_value": 200.0
 },
 {
  "symbol": "AQYLON",
  "company_name": "AQYLON NEXUS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE416A01051",
  "face_value": 100.0
 },
 {
  "symbol": "ARAVALISEC",
  "company_name": "ARAVALI SECURITIES AND FI",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE445901015",
  "face_value": 1000.0
 },
 {
  "symbol": "ARCHIDPLY",
  "company_name": "ARCHIDPLY IND. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE877I01016",
  "face_value": 1000.0
 },
 {
  "symbol": "ARCHIES",
  "company_name": "ARCHIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE731A01020",
  "face_value": 200.0
 },
 {
  "symbol": "ARCOTECH",
  "company_name": "ARCOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE574I01035",
  "face_value": 200.0
 },
 {
  "symbol": "ARE&M",
  "company_name": "AMARA RAJA ENERGY MOB LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE885A01032",
  "face_value": 100.0
 },
 {
  "symbol": "ARENTERP",
  "company_name": "RAJDARSHAN INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE610C01014",
  "face_value": 1000.0
 },
 {
  "symbol": "ARFIN",
  "company_name": "ARFIN INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE784R01023",
  "face_value": 100.0
 },
 {
  "symbol": "ARIES",
  "company_name": "ARIES AGRO LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE298I01015",
  "face_value": 1000.0
 },
 {
  "symbol": "ARIHANT",
  "company_name": "ARIHANT FOUN & HOU LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE413D01011",
  "face_value": 1000.0
 },
 {
  "symbol": "ARIHANTCAP",
  "company_name": "ARIHANT CAPITAL MKTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE420B01036",
  "face_value": 100.0
 },
 {
  "symbol": "ARIHANTSUP",
  "company_name": "ARIHANT SUPERSTRUCT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE643K01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ARIS",
  "company_name": "ARISINFRA SOLUTIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0H9P01028",
  "face_value": 200.0
 },
 {
  "symbol": "ARKADE",
  "company_name": "ARKADE DEVELOPERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0QRL01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ARMANFIN",
  "company_name": "ARMAN FIN SERV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE109C01017",
  "face_value": 1000.0
 },
 {
  "symbol": "AROGRANITE",
  "company_name": "ARO GRANITE IND. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE210C01013",
  "face_value": 1000.0
 },
 {
  "symbol": "ARROWGREEN",
  "company_name": "ARROW GREENTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE570D01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ARSHIYA",
  "company_name": "ARSHIYA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE968D01022",
  "face_value": 200.0
 },
 {
  "symbol": "ARSSBL",
  "company_name": "ANAND RATHI SH N STK BR L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE549H01021",
  "face_value": 500.0
 },
 {
  "symbol": "ARSSINFRA",
  "company_name": "ARSS INFRA PROJ. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE267I01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ARTEMISMED",
  "company_name": "ARTEMIS MED SERVICE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE025R01021",
  "face_value": 100.0
 },
 {
  "symbol": "ARTNIRMAN",
  "company_name": "ART NIRMAN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE738V01013",
  "face_value": 1000.0
 },
 {
  "symbol": "ARTSONENGG",
  "company_name": "ARTSON ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE533801010",
  "face_value": 1000.0
 },
 {
  "symbol": "ARUNASUGAR",
  "company_name": "ARUNA SUGARS AND ENTERP.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE008101011",
  "face_value": 1000.0
 },
 {
  "symbol": "ARVEE",
  "company_name": "ARVEE LABORATORIES I LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE006Z01016",
  "face_value": 1000.0
 },
 {
  "symbol": "ARVIND",
  "company_name": "ARVIND LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE034A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "ARVINDF-RE",
  "company_name": "ARVIND FASHIONS RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE955V20013",
  "face_value": 400.0
 },
 {
  "symbol": "ARVINDFASN",
  "company_name": "ARVIND FASHIONS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE955V01021",
  "face_value": 400.0
 },
 {
  "symbol": "ARVSMART",
  "company_name": "ARVIND SMARTSPACES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE034S01021",
  "face_value": 1000.0
 },
 {
  "symbol": "ARYAFINFAB",
  "company_name": "ARYAN FINEFAB LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE008901014",
  "face_value": 1000.0
 },
 {
  "symbol": "ASAHIINDIA",
  "company_name": "ASAHI INDIA GLASS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE439A01020",
  "face_value": 100.0
 },
 {
  "symbol": "ASAHISONG",
  "company_name": "ASAHI SONGWON COLOR LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE228I01012",
  "face_value": 1000.0
 },
 {
  "symbol": "ASAL",
  "company_name": "AUTOMOTIVE STAMPINGS & AS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE900C01027",
  "face_value": 1000.0
 },
 {
  "symbol": "ASALCBR",
  "company_name": "ASSO ALCOHOLS & BREW LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE073G01016",
  "face_value": 1000.0
 },
 {
  "symbol": "ASHAPURMIN",
  "company_name": "ASHAPURA MINECHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE348A01023",
  "face_value": 200.0
 },
 {
  "symbol": "ASHIANA",
  "company_name": "ASHIANA HOUSING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE365D01021",
  "face_value": 200.0
 },
 {
  "symbol": "ASHIKA",
  "company_name": "ASHIKA CREDIT CAPITAL L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE094B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "ASHIMASYN",
  "company_name": "ASHIMA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE440A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ASHOKA",
  "company_name": "ASHOKA BUILDCON LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE442H01029",
  "face_value": 500.0
 },
 {
  "symbol": "ASHOKALCO",
  "company_name": "ASHOK ALCO-CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE010401011",
  "face_value": 1000.0
 },
 {
  "symbol": "ASHOKAMET",
  "company_name": "ASHOKA METCAST LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE760Y01011",
  "face_value": 1000.0
 },
 {
  "symbol": "ASHOKLEY",
  "company_name": "ASHOK LEYLAND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE208A01029",
  "face_value": 100.0
 },
 {
  "symbol": "ASHOKORG",
  "company_name": "ASHOK ORGANIC INDUS. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE010901010",
  "face_value": 1000.0
 },
 {
  "symbol": "ASIAN-RE",
  "company_name": "ASIAN GRANITO INDIA-RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE022I20019",
  "face_value": 1000.0
 },
 {
  "symbol": "ASIAN-RE1",
  "company_name": "ASIAN GRANITO INDIA LIMIT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE022I20027",
  "face_value": 1000.0
 },
 {
  "symbol": "ASIANALLOY",
  "company_name": "ASIAN ALLOYS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE011301012",
  "face_value": 1000.0
 },
 {
  "symbol": "ASIANCONSO",
  "company_name": "ASIAN CONSOLIDATED INDUST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE011901019",
  "face_value": 1000.0
 },
 {
  "symbol": "ASIANENE",
  "company_name": "ASIAN ENERGY SERVICES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE276G01015",
  "face_value": 1000.0
 },
 {
  "symbol": "ASIANHOTNR",
  "company_name": "ASIAN HOTELS (NORTH) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE363A01022",
  "face_value": 1000.0
 },
 {
  "symbol": "ASIANPAINT",
  "company_name": "ASIAN PAINTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE021A01026",
  "face_value": 100.0
 },
 {
  "symbol": "ASIANTILES",
  "company_name": "ASIAN GRANITO IND. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE022I01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ASIL",
  "company_name": "AMIT SPINNING IND. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE988A01026",
  "face_value": 500.0
 },
 {
  "symbol": "ASILIND",
  "company_name": "ASIL INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE012901018",
  "face_value": 1000.0
 },
 {
  "symbol": "ASKAUTOLTD",
  "company_name": "ASK AUTOMOTIVE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE491J01022",
  "face_value": 200.0
 },
 {
  "symbol": "ASMS",
  "company_name": "BARTRONICS INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE855F01042",
  "face_value": 100.0
 },
 {
  "symbol": "ASOCALCHOL",
  "company_name": "ASSOCIATED ALCOHOL & BREW",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE013401018",
  "face_value": 1000.0
 },
 {
  "symbol": "ASPINWALL",
  "company_name": "ASPINWALL & CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE991I01015",
  "face_value": 1000.0
 },
 {
  "symbol": "ASSAMFRONT",
  "company_name": "AFT INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE417A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ASTAR",
  "company_name": "ASIAN STAR CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE194D01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ASTEC",
  "company_name": "ASTEC LIFESCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE563J01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ASTEC-RE",
  "company_name": "ASTEC LIFESCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE563J20010",
  "face_value": 1000.0
 },
 {
  "symbol": "ASTERDM",
  "company_name": "ASTER DM HEALTHCARE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE914M01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ASTRAL",
  "company_name": "ASTRAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE006I01046",
  "face_value": 100.0
 },
 {
  "symbol": "ASTRAMICRO",
  "company_name": "ASTRA MICROWAVE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE386C01029",
  "face_value": 200.0
 },
 {
  "symbol": "ASTRAZEN",
  "company_name": "ASTRAZENECA PHARMA IND LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE203A01020",
  "face_value": 200.0
 },
 {
  "symbol": "ASTRON",
  "company_name": "ASTRON PAPER BORD MIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE646X01014",
  "face_value": 1000.0
 },
 {
  "symbol": "ATAL-RE",
  "company_name": "ATAL REALTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0ALR20011",
  "face_value": 200.0
 },
 {
  "symbol": "ATALREAL",
  "company_name": "ATAL REALTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0ALR01029",
  "face_value": 200.0
 },
 {
  "symbol": "ATAM",
  "company_name": "ATAM VALVES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE09KD01013",
  "face_value": 1000.0
 },
 {
  "symbol": "ATASHIND",
  "company_name": "ATASH INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE014001015",
  "face_value": 1000.0
 },
 {
  "symbol": "ATCOM",
  "company_name": "ATCOM TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE834A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "ATGL",
  "company_name": "ADANI TOTAL GAS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE399L01023",
  "face_value": 100.0
 },
 {
  "symbol": "ATHERENERG",
  "company_name": "ATHER ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0LEZ01016",
  "face_value": 100.0
 },
 {
  "symbol": "ATL",
  "company_name": "ALLCARGO TERMINALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0NN701020",
  "face_value": 200.0
 },
 {
  "symbol": "ATL-RE",
  "company_name": "ALLCARGO TERMINALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0NN720012",
  "face_value": 200.0
 },
 {
  "symbol": "ATLANTAA",
  "company_name": "ATLANTAA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE285H01022",
  "face_value": 200.0
 },
 {
  "symbol": "ATLANTAELE",
  "company_name": "ATLANTA ELECTRICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0Z4F01028",
  "face_value": 200.0
 },
 {
  "symbol": "ATLANTSPG",
  "company_name": "ATLANTIC SPG & WVG MILLS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE014401017",
  "face_value": 1000.0
 },
 {
  "symbol": "ATLASCOPCO",
  "company_name": "ATLAS COPCO INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE445A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ATLASCYCLE",
  "company_name": "ATLAS CYCLE (HARYANA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE446A01025",
  "face_value": 500.0
 },
 {
  "symbol": "ATNINTER",
  "company_name": "ATN INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE803A01027",
  "face_value": 400.0
 },
 {
  "symbol": "ATUL",
  "company_name": "ATUL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE100A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ATULAUTO",
  "company_name": "ATUL AUTO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE951D01028",
  "face_value": 500.0
 },
 {
  "symbol": "ATVPETRO",
  "company_name": "SVC SUPERCHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE038B01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ATVPROJ",
  "company_name": "ATV PROJECTS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE015201010",
  "face_value": 1000.0
 },
 {
  "symbol": "AUBANK",
  "company_name": "AU SMALL FINANCE BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE949L01017",
  "face_value": 1000.0
 },
 {
  "symbol": "AURANPAPER",
  "company_name": "AURANGABAD PAPER MILLS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE015401016",
  "face_value": 1000.0
 },
 {
  "symbol": "AURIGROW",
  "company_name": "AURI GROW INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE925Y01036",
  "face_value": 100.0
 },
 {
  "symbol": "AURIONPRO",
  "company_name": "AURIONPRO SOLN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE132H01018",
  "face_value": 1000.0
 },
 {
  "symbol": "AUROPHARMA",
  "company_name": "AUROBINDO PHARMA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE406A01037",
  "face_value": 100.0
 },
 {
  "symbol": "AURUM",
  "company_name": "AURUM PROPTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE898S01029",
  "face_value": 500.0
 },
 {
  "symbol": "AURUM-RE",
  "company_name": "AURUM PROPTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE898S20011",
  "face_value": 500.0
 },
 {
  "symbol": "AUSOMENT",
  "company_name": "AUSOM ENTERPRISE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE218C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "AUSTRAL",
  "company_name": "AUSTRAL COKE & PRO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE455J01027",
  "face_value": 100.0
 },
 {
  "symbol": "AUTOAXLES",
  "company_name": "AUTOMOTIVE AXLES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE449A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "AUTOBEES",
  "company_name": "NIPPONAMC - NETFAUTO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KC1337",
  "face_value": 1000.0
 },
 {
  "symbol": "AUTOBEINAV",
  "company_name": "AUTOBEES INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000132",
  "face_value": 100.0
 },
 {
  "symbol": "AUTOCORP",
  "company_name": "AUTOMOBILE CORP OF GOA LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE016201019",
  "face_value": 1000.0
 },
 {
  "symbol": "AUTOIETF",
  "company_name": "ICICIPRAMC - ICICIAUTO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC10V2",
  "face_value": 100.0
 },
 {
  "symbol": "AUTOIND",
  "company_name": "AUTOLINE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE718H01014",
  "face_value": 1000.0
 },
 {
  "symbol": "AUTOLEC",
  "company_name": "AUTOLEC INDUSTRIES  LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE134C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "AUTOLITIND",
  "company_name": "AUTOLITE (INDIA) LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE448A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "AUTOPALIND",
  "company_name": "AUTOPAL INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE016401015",
  "face_value": 1000.0
 },
 {
  "symbol": "AUTORIDFIN",
  "company_name": "AUTORIDERS FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE450A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "AVADHSUGAR",
  "company_name": "AVADH SUG & ENERGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE349W01017",
  "face_value": 1000.0
 },
 {
  "symbol": "AVAILFC",
  "company_name": "AVAILABLE FINANCE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE325G01010",
  "face_value": 1000.0
 },
 {
  "symbol": "AVALON",
  "company_name": "AVALON TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0LCL01028",
  "face_value": 200.0
 },
 {
  "symbol": "AVANTEL",
  "company_name": "AVANTEL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE005B01027",
  "face_value": 200.0
 },
 {
  "symbol": "AVANTEL-RE",
  "company_name": "AVANTEL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE005B20019",
  "face_value": 200.0
 },
 {
  "symbol": "AVANTIFEED",
  "company_name": "AVANTI FEEDS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE871C01038",
  "face_value": 100.0
 },
 {
  "symbol": "AVERY",
  "company_name": "AVERY  (I)  LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE906A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "AVG",
  "company_name": "AVG LOGISTICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE680Z01018",
  "face_value": 1000.0
 },
 {
  "symbol": "AVL",
  "company_name": "ADITYA VISION LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE679V01027",
  "face_value": 100.0
 },
 {
  "symbol": "AVON-RE",
  "company_name": "AVONMORE CAPITAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE323B20016",
  "face_value": 100.0
 },
 {
  "symbol": "AVONIND",
  "company_name": "AVON INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE446301017",
  "face_value": 1000.0
 },
 {
  "symbol": "AVONMORE",
  "company_name": "AVONMORE CAP&MGT SERV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE323B01024",
  "face_value": 100.0
 },
 {
  "symbol": "AVROIND",
  "company_name": "AVRO INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE652Z01017",
  "face_value": 1000.0
 },
 {
  "symbol": "AVTNPL",
  "company_name": "AVT NATURAL PRODUCTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE488D01021",
  "face_value": 100.0
 },
 {
  "symbol": "AWFIS",
  "company_name": "AWFIS SPACE SOLUTIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE108V01019",
  "face_value": 1000.0
 },
 {
  "symbol": "AWHCL",
  "company_name": "ANTONY WASTE HDG CELL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01BK01022",
  "face_value": 500.0
 },
 {
  "symbol": "AWL",
  "company_name": "AWL AGRI BUSINESS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE699H01024",
  "face_value": 100.0
 },
 {
  "symbol": "AXISBANK",
  "company_name": "AXIS BANK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE238A01034",
  "face_value": 200.0
 },
 {
  "symbol": "AXISBNINAV",
  "company_name": "AXISBNKETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000056",
  "face_value": 100.0
 },
 {
  "symbol": "AXISBNKETF",
  "company_name": "AXISAMC - AXISBNKETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF846K01X63",
  "face_value": 10000.0
 },
 {
  "symbol": "AXISBPINAV",
  "company_name": "AXISBPSETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000055",
  "face_value": 100.0
 },
 {
  "symbol": "AXISBPSETF",
  "company_name": "AXISAMC - AXISBPSETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF846K01Z04",
  "face_value": 100.0
 },
 {
  "symbol": "AXISCADES",
  "company_name": "AXISCADES TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE555B01013",
  "face_value": 500.0
 },
 {
  "symbol": "AXISCEINAV",
  "company_name": "AXISCETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000057",
  "face_value": 100.0
 },
 {
  "symbol": "AXISCETF",
  "company_name": "AXISAMC - AXISCETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF846K016C7",
  "face_value": 1000.0
 },
 {
  "symbol": "AXISGOINAV",
  "company_name": "AXISGOLD NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000034",
  "face_value": 100.0
 },
 {
  "symbol": "AXISGOLD",
  "company_name": "AXIS MF - AXIS GOLD ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF846K01W80",
  "face_value": 100.0
 },
 {
  "symbol": "AXISHCETF",
  "company_name": "AXISAMC - AXISHCETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF846K01Z12",
  "face_value": 1000.0
 },
 {
  "symbol": "AXISHCINAV",
  "company_name": "AXISHCETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000054",
  "face_value": 100.0
 },
 {
  "symbol": "AXISILINAV",
  "company_name": "AXISAMC - AXISILINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000161",
  "face_value": 1000.0
 },
 {
  "symbol": "AXISILVER",
  "company_name": "AXISAMC - AXISILVER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF846K011K1",
  "face_value": 1000.0
 },
 {
  "symbol": "AXISNIFTY",
  "company_name": "AXISAMC - AXISNIFTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF846K01W98",
  "face_value": 1000.0
 },
 {
  "symbol": "AXISNIINAV",
  "company_name": "AXISNIFTY INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000058",
  "face_value": 100.0
 },
 {
  "symbol": "AXISTECETF",
  "company_name": "AXISAMC - AXISTECETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF846K01Y96",
  "face_value": 10000.0
 },
 {
  "symbol": "AXISTEINAV",
  "company_name": "AXISTECETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000059",
  "face_value": 100.0
 },
 {
  "symbol": "AXISVAINAV",
  "company_name": "AXISAMC - AXISVAINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000266",
  "face_value": 1000.0
 },
 {
  "symbol": "AXISVALUE",
  "company_name": "AXISAMC - AXISVALUE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF846KA1119",
  "face_value": 1000.0
 },
 {
  "symbol": "AXITA",
  "company_name": "AXITA COTTON LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02EZ01022",
  "face_value": 100.0
 },
 {
  "symbol": "AXSENSEX",
  "company_name": "AXISAMC - AXSENSEX",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF846K010Q0",
  "face_value": 1000.0
 },
 {
  "symbol": "AXSNSXINAV",
  "company_name": "AXISAMC - AXSNSXINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000182",
  "face_value": 1000.0
 },
 {
  "symbol": "AYE",
  "company_name": "AYE FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE501X01029",
  "face_value": 200.0
 },
 {
  "symbol": "AYMSYNTEX",
  "company_name": "AYM SYNTEX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE193B01039",
  "face_value": 1000.0
 },
 {
  "symbol": "AZAD",
  "company_name": "AZAD ENGINEERING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02IJ01035",
  "face_value": 200.0
 },
 {
  "symbol": "BAFNAPH",
  "company_name": "BAFNA PHARMACEUTICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE878I01022",
  "face_value": 1000.0
 },
 {
  "symbol": "BAFNAPHARM",
  "company_name": "BAFNA PHARMACEUTICALS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE878I01014",
  "face_value": 1000.0
 },
 {
  "symbol": "BAGFILMS",
  "company_name": "B.A.G FILMS AND MEDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE116D01028",
  "face_value": 200.0
 },
 {
  "symbol": "BAGWATIGAS",
  "company_name": "BHAGWATI GASES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE447201018",
  "face_value": 1000.0
 },
 {
  "symbol": "BAIDFIN",
  "company_name": "BAID FINSERV LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE020D01022",
  "face_value": 200.0
 },
 {
  "symbol": "BAIDFIN-RE",
  "company_name": "BAID FINSERV LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE020D20014",
  "face_value": 200.0
 },
 {
  "symbol": "BAJAJ-AUTO",
  "company_name": "BAJAJ AUTO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE917I01010",
  "face_value": 1000.0
 },
 {
  "symbol": "BAJAJCON",
  "company_name": "BAJAJ CONSUMER CARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE933K01021",
  "face_value": 100.0
 },
 {
  "symbol": "BAJAJELEC",
  "company_name": "BAJAJ ELECT.LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE193E01025",
  "face_value": 200.0
 },
 {
  "symbol": "BAJAJFINSV",
  "company_name": "BAJAJ FINSERV LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE918I01026",
  "face_value": 100.0
 },
 {
  "symbol": "BAJAJHCARE",
  "company_name": "BAJAJ HEALTHCARE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE411U01027",
  "face_value": 500.0
 },
 {
  "symbol": "BAJAJHFL",
  "company_name": "BAJAJ HOUSING FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE377Y01014",
  "face_value": 1000.0
 },
 {
  "symbol": "BAJAJHIND",
  "company_name": "BAJAJ HINDUSTHAN SUGAR LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE306A01021",
  "face_value": 100.0
 },
 {
  "symbol": "BAJAJHLDNG",
  "company_name": "BAJAJ HOLDINGS & INVS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE118A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "BAJAJINDEF",
  "company_name": "INDEF MANUFACTURING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0O9T01021",
  "face_value": 100.0
 },
 {
  "symbol": "BAJAJST",
  "company_name": "BAJAJ STEEL INDS. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE704G01024",
  "face_value": 500.0
 },
 {
  "symbol": "BAJEL",
  "company_name": "BAJEL PROJECTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0KQN01018",
  "face_value": 200.0
 },
 {
  "symbol": "BAJFINANCE",
  "company_name": "BAJAJ FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE296A01032",
  "face_value": 100.0
 },
 {
  "symbol": "BAKELHYLAM",
  "company_name": "BAKELITE HYLAM LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE019301014",
  "face_value": 1000.0
 },
 {
  "symbol": "BALAJEE",
  "company_name": "SHREE TIRUPATI BALAJEE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0S2G01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BALAJHOTEL",
  "company_name": "BALAJI HOTELS & ENTER. LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE454A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BALAJIDIST",
  "company_name": "BALAJI DISTILLERIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE453A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "BALAJIIND",
  "company_name": "BALAJI INDUSTRIAL CORP. L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE455A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "BALAJITELE",
  "company_name": "BALAJI TELEFILMS LIMITED.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE794B01026",
  "face_value": 200.0
 },
 {
  "symbol": "BALAMINES",
  "company_name": "BALAJI AMINES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE050E01027",
  "face_value": 200.0
 },
 {
  "symbol": "BALAXI",
  "company_name": "BALAXI PHARMA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE618N01022",
  "face_value": 200.0
 },
 {
  "symbol": "BALKRI-RE",
  "company_name": "BALKRSHNA PAPER MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE875R20011",
  "face_value": 1000.0
 },
 {
  "symbol": "BALKRISHNA",
  "company_name": "BALKRISHNA PAPER MILLS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE875R01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BALKRISIND",
  "company_name": "BALKRISHNA IND. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE787D01026",
  "face_value": 200.0
 },
 {
  "symbol": "BALLARPUR",
  "company_name": "BALLARPUR INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE294A01037",
  "face_value": 200.0
 },
 {
  "symbol": "BALMLAWRIE",
  "company_name": "BALMER LAWRIE & CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE164A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "BALPHARMA",
  "company_name": "BAL PHARMA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE083D01012",
  "face_value": 1000.0
 },
 {
  "symbol": "BALRAMCHIN",
  "company_name": "BALRAMPUR CHINI MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE119A01028",
  "face_value": 100.0
 },
 {
  "symbol": "BALUFORGE",
  "company_name": "BALU FORGE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE011E01029",
  "face_value": 1000.0
 },
 {
  "symbol": "BALURTRANS",
  "company_name": "BALURGHAT TECHNOLOGIES LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE447101010",
  "face_value": 1000.0
 },
 {
  "symbol": "BANARBEADS",
  "company_name": "BANARAS BEADS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE655B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BANARISUG",
  "company_name": "BANNARI AMMAN SUGARS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE459A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "BANCOINDIA",
  "company_name": "BANCO PRODUCTS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE213C01025",
  "face_value": 200.0
 },
 {
  "symbol": "BANCOPROD",
  "company_name": "BANCO PRODUCTS (I) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE213C01017",
  "face_value": 1000.0
 },
 {
  "symbol": "BANDHANBNK",
  "company_name": "BANDHAN BANK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE545U01014",
  "face_value": 1000.0
 },
 {
  "symbol": "BANG",
  "company_name": "BANG OVERSEAS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE863I01016",
  "face_value": 1000.0
 },
 {
  "symbol": "BANK10ADD",
  "company_name": "DSPAMC - BANK10ADD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1YH2",
  "face_value": 1000.0
 },
 {
  "symbol": "BANKA",
  "company_name": "BANKA BIOLOO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE862Y01015",
  "face_value": 1000.0
 },
 {
  "symbol": "BANKADD",
  "company_name": "DSPAMC - DSPBANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1RX3",
  "face_value": 1000.0
 },
 {
  "symbol": "BANKBARODA",
  "company_name": "BANK OF BARODA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE028A01039",
  "face_value": 200.0
 },
 {
  "symbol": "BANKBEES",
  "company_name": "NIP IND ETF BANK BEES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KB15I9",
  "face_value": 100.0
 },
 {
  "symbol": "BANKBENAV",
  "company_name": "BANK BEES NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000018",
  "face_value": 1000.0
 },
 {
  "symbol": "BANKBETA",
  "company_name": "UTIAMC-BANKBETA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF789F1AUV1",
  "face_value": 100.0
 },
 {
  "symbol": "BANKBETF",
  "company_name": "BFAM - BANKBETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF0QA701714",
  "face_value": 1000.0
 },
 {
  "symbol": "BANKBINAV",
  "company_name": "BFAM - BANKBETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000210",
  "face_value": 1000.0
 },
 {
  "symbol": "BANKETF",
  "company_name": "MIRAEAMC - BANKETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01KR3",
  "face_value": 40000.0
 },
 {
  "symbol": "BANKIETF",
  "company_name": "ICICIPRAMC - IPRU5008",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC15I8",
  "face_value": 100.0
 },
 {
  "symbol": "BANKINDIA",
  "company_name": "BANK OF INDIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE084A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "BANKNIFTY1",
  "company_name": "KOTAKMAMC-KOTAKBKETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1ZB7",
  "face_value": 100.0
 },
 {
  "symbol": "BANKPSU",
  "company_name": "MIRAEAMC - BANKPSU",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01LZ4",
  "face_value": 1000.0
 },
 {
  "symbol": "BANSALWIRE",
  "company_name": "BANSAL WIRE INDUSTRIES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0B9K01025",
  "face_value": 500.0
 },
 {
  "symbol": "BANSWRAS",
  "company_name": "BANSWARA SYNTEX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE629D01020",
  "face_value": 500.0
 },
 {
  "symbol": "BARODARAYN",
  "company_name": "BARODA RAYON CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE022701010",
  "face_value": 1000.0
 },
 {
  "symbol": "BARTRONICS",
  "company_name": "BARTRONICS INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE855F01034",
  "face_value": 1000.0
 },
 {
  "symbol": "BASF",
  "company_name": "BASF INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE373A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "BASML",
  "company_name": "BANNARI AM SPIN MILL LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE186H01022",
  "face_value": 500.0
 },
 {
  "symbol": "BASML-RE",
  "company_name": "BANNARI AMMAN SPINNING RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE186H20014",
  "face_value": 500.0
 },
 {
  "symbol": "BASML-RE1",
  "company_name": "BANNARI AMMAN SPINNING",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE186H20022",
  "face_value": 500.0
 },
 {
  "symbol": "BATAINDIA",
  "company_name": "BATA INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE176A01028",
  "face_value": 500.0
 },
 {
  "symbol": "BATLIBOI",
  "company_name": "BATLIBOI LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE177C01022",
  "face_value": 500.0
 },
 {
  "symbol": "BAUSCHLOMB",
  "company_name": "RAYBAN SUN OPTICS IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE854A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "BAYERCROP",
  "company_name": "BAYER CROPSCIENCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE462A01022",
  "face_value": 1000.0
 },
 {
  "symbol": "BBETF0432",
  "company_name": "EDELAMC - BBETF0432",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01OB1",
  "face_value": 100000.0
 },
 {
  "symbol": "BBETF0INAV",
  "company_name": "BBETF0432 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000069",
  "face_value": 100.0
 },
 {
  "symbol": "BBL",
  "company_name": "BHARAT BIJLEE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE464A01036",
  "face_value": 500.0
 },
 {
  "symbol": "BBNPNBETF",
  "company_name": "BARODABNP - BBNPNBETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF251K01TL6",
  "face_value": 1000.0
 },
 {
  "symbol": "BBNPNBINAV",
  "company_name": "BARODABNP - BBNPNBINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000228",
  "face_value": 1000.0
 },
 {
  "symbol": "BBNPPGOLD",
  "company_name": "BARODABNP - BBNPPGOLD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF251K01SU9",
  "face_value": 1000.0
 },
 {
  "symbol": "BBOX",
  "company_name": "BLACK BOX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE676A01027",
  "face_value": 200.0
 },
 {
  "symbol": "BBTC",
  "company_name": "BOMBAY BURMAH TRADING COR",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE050A01025",
  "face_value": 200.0
 },
 {
  "symbol": "BBTCL",
  "company_name": "B&B TRIPLEWALL CONT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01EE01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BCG",
  "company_name": "BRIGHTCOM GROUP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE425B01027",
  "face_value": 200.0
 },
 {
  "symbol": "BCIL-RE",
  "company_name": "BHAGIRADHA CHEM & IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE414D20019",
  "face_value": 1000.0
 },
 {
  "symbol": "BCLIND",
  "company_name": "BCL INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE412G01024",
  "face_value": 100.0
 },
 {
  "symbol": "BCONCEPTS",
  "company_name": "BRAND CONCEPTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE977Y01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BCP",
  "company_name": "B.C. POWER CONTROLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE905P01028",
  "face_value": 200.0
 },
 {
  "symbol": "BCPL",
  "company_name": "BCPL RAILWAY INFRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00SW01015",
  "face_value": 1000.0
 },
 {
  "symbol": "BDL",
  "company_name": "BHARAT DYNAMICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE171Z01026",
  "face_value": 500.0
 },
 {
  "symbol": "BEARD-RE",
  "company_name": "BEARDSELL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE520H20014",
  "face_value": 200.0
 },
 {
  "symbol": "BEARDSELL",
  "company_name": "BEARDSELL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE520H01022",
  "face_value": 200.0
 },
 {
  "symbol": "BECREL",
  "company_name": "BEST & CROMPTON ENGG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE287A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "BECTORFOOD",
  "company_name": "MRS BECTORS FOOD SPE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE495P01020",
  "face_value": 200.0
 },
 {
  "symbol": "BEDMUTHA",
  "company_name": "BEDMUTHA INDUST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE844K01012",
  "face_value": 1000.0
 },
 {
  "symbol": "BEEKAY",
  "company_name": "BEEKAY STEEL INDS. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE213D01015",
  "face_value": 1000.0
 },
 {
  "symbol": "BEL",
  "company_name": "BHARAT ELECTRONICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE263A01024",
  "face_value": 100.0
 },
 {
  "symbol": "BELCONTROL",
  "company_name": "BELLS CONTROLS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE025C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "BELLACASA",
  "company_name": "BELLA CASA FASH AND RET L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE344T01014",
  "face_value": 1000.0
 },
 {
  "symbol": "BELLARYSTL",
  "company_name": "BELLARY STEELS AND ALLOYS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE166C01017",
  "face_value": 1000.0
 },
 {
  "symbol": "BELRISE",
  "company_name": "BELRISE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE894V01022",
  "face_value": 500.0
 },
 {
  "symbol": "BEML",
  "company_name": "BEML LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE258A01024",
  "face_value": 500.0
 },
 {
  "symbol": "BENGALASM",
  "company_name": "BENGAL & ASSAM CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE083K01017",
  "face_value": 1000.0
 },
 {
  "symbol": "BEPL",
  "company_name": "BHANSALI ENG. POLYMERS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE922A01025",
  "face_value": 100.0
 },
 {
  "symbol": "BERGEPAINT",
  "company_name": "BERGER PAINTS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE463A01038",
  "face_value": 100.0
 },
 {
  "symbol": "BESTAGRO",
  "company_name": "BEST AGROLIFE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE052T01021",
  "face_value": 100.0
 },
 {
  "symbol": "BESTAVISON",
  "company_name": "BESTA VISION ELECTRONICS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE025201018",
  "face_value": 1000.0
 },
 {
  "symbol": "BESTCROMP",
  "company_name": "BEST & CROMPTON LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE287A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "BETA",
  "company_name": "BETA DRUGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE351Y01019",
  "face_value": 1000.0
 },
 {
  "symbol": "BETANAPTOL",
  "company_name": "BETA NAPHTHOL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE025301016",
  "face_value": 1000.0
 },
 {
  "symbol": "BFINVEST",
  "company_name": "BF INVESTMENT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE878K01010",
  "face_value": 500.0
 },
 {
  "symbol": "BFSI",
  "company_name": "MIRAEAMC - MAFSETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01HI8",
  "face_value": 1000.0
 },
 {
  "symbol": "BFUTILITIE",
  "company_name": "BF UTILITIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE243D01012",
  "face_value": 500.0
 },
 {
  "symbol": "BGEAR-RE",
  "company_name": "BHARAT GEARS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE561C20019",
  "face_value": 1000.0
 },
 {
  "symbol": "BGLOBAL",
  "company_name": "BHARATIYA GLOBAL INFO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE224M01013",
  "face_value": 1000.0
 },
 {
  "symbol": "BGRENERGY",
  "company_name": "BGR ENERGY SYSTEMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE661I01014",
  "face_value": 1000.0
 },
 {
  "symbol": "BHAGCHEM",
  "company_name": "BHAGIRADHA CHEM & INDS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE414D01027",
  "face_value": 100.0
 },
 {
  "symbol": "BHAGERIA",
  "company_name": "BHAGERIA INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE354C01027",
  "face_value": 500.0
 },
 {
  "symbol": "BHAGYANGR",
  "company_name": "BHAGYANAGAR INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE458B01036",
  "face_value": 200.0
 },
 {
  "symbol": "BHAGYAPROP",
  "company_name": "BHAGYANAGAR PRO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE363W01018",
  "face_value": 200.0
 },
 {
  "symbol": "BHANDA-RE",
  "company_name": "BHANDARI HOSIERY EXP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE474E20011",
  "face_value": 100.0
 },
 {
  "symbol": "BHANDA-RE1",
  "company_name": "BHANDARI HOSIERY EXP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE474E20029",
  "face_value": 100.0
 },
 {
  "symbol": "BHANDA-RE2",
  "company_name": "BHANDARI HOSIERY EXP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE474E20037",
  "face_value": 100.0
 },
 {
  "symbol": "BHANDARI",
  "company_name": "BHANDARI HOSIERY EXP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE474E01029",
  "face_value": 100.0
 },
 {
  "symbol": "BHARATCOAL",
  "company_name": "BHARAT COKING COAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE05XR01022",
  "face_value": 1000.0
 },
 {
  "symbol": "BHARATFORG",
  "company_name": "BHARAT FORGE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE465A01025",
  "face_value": 200.0
 },
 {
  "symbol": "BHARATGEAR",
  "company_name": "BHARAT GEARS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE561C01019",
  "face_value": 1000.0
 },
 {
  "symbol": "BHARATHOT",
  "company_name": "BHARAT HOTELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE466A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "BHARATIDIL",
  "company_name": "BHARATI DEF & INFRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE673G01013",
  "face_value": 1000.0
 },
 {
  "symbol": "BHARATRAS",
  "company_name": "BHARAT RASAYAN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE838B01021",
  "face_value": 500.0
 },
 {
  "symbol": "BHARATSE",
  "company_name": "BHARAT SEATS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE415D01024",
  "face_value": 200.0
 },
 {
  "symbol": "BHARATWIRE",
  "company_name": "BHARAT WIRE ROPES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE316L01019",
  "face_value": 1000.0
 },
 {
  "symbol": "BHARTIARTL",
  "company_name": "BHARTI AIRTEL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE397D01024",
  "face_value": 500.0
 },
 {
  "symbol": "BHARTIHEXA",
  "company_name": "BHARTI HEXACOM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE343G01021",
  "face_value": 500.0
 },
 {
  "symbol": "BHEL",
  "company_name": "BHEL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE257A01026",
  "face_value": 200.0
 },
 {
  "symbol": "BHUPENCAP",
  "company_name": "BHUPENDRA CAP & FINANCE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE030601012",
  "face_value": 1000.0
 },
 {
  "symbol": "BI",
  "company_name": "BILCARE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE986A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "BIGBLOC",
  "company_name": "BIGBLOC CONSTRUCTION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE412U01025",
  "face_value": 200.0
 },
 {
  "symbol": "BIHARALLOY",
  "company_name": "UMI SPECIAL STEEL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE447501011",
  "face_value": 1000.0
 },
 {
  "symbol": "BIHARCAUST",
  "company_name": "BIHAR CAUSTICS AND CHEM.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE605B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "BIHARSPONG",
  "company_name": "BIHAR SPONGE IRON LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE031301018",
  "face_value": 1000.0
 },
 {
  "symbol": "BIKAJI",
  "company_name": "BIKAJI FOODS INTERN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00E101023",
  "face_value": 100.0
 },
 {
  "symbol": "BIL",
  "company_name": "BHARTIYA INTERNATIONAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE828A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "BILENERGY",
  "company_name": "BIL ENERGY SYSTEMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE607L01029",
  "face_value": 100.0
 },
 {
  "symbol": "BILPOWER",
  "company_name": "BILPOWER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE952D01018",
  "face_value": 1000.0
 },
 {
  "symbol": "BILVYAPAR",
  "company_name": "BIL VYAPAR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE071A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "BIMETAL",
  "company_name": "BIMETAL BEARINGS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE469A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "BIMETBRG",
  "company_name": "BIMETAL BEARINGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYY000005",
  "face_value": 1000.0
 },
 {
  "symbol": "BIOCON",
  "company_name": "BIOCON LIMITED.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE376G01013",
  "face_value": 500.0
 },
 {
  "symbol": "BIOFILCHEM",
  "company_name": "BIOFIL CHEM & PHARMA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE829A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "BIRLACABLE",
  "company_name": "BIRLA CABLE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE800A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "BIRLACORPN",
  "company_name": "BIRLA CORPORATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE340A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "BIRLAMONEY",
  "company_name": "ADITYA BIRLA MONEY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE865C01022",
  "face_value": 100.0
 },
 {
  "symbol": "BIRLANU",
  "company_name": "BIRLANU LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE557A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BIRLAPREC",
  "company_name": "BIRLA PRECISION TECH L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE372E01025",
  "face_value": 200.0
 },
 {
  "symbol": "BIRLATYRE",
  "company_name": "BIRLA TYRES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0AEJ01013",
  "face_value": 1000.0
 },
 {
  "symbol": "BIRLAYAMAH",
  "company_name": "BIRLA YAMAHA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE224B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "BKMINDST",
  "company_name": "BKM INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE831Q01016",
  "face_value": 100.0
 },
 {
  "symbol": "BLACKBUCK",
  "company_name": "BLACKBUCK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0UIZ01018",
  "face_value": 100.0
 },
 {
  "symbol": "BLACKROSE",
  "company_name": "BLACK ROSE INDS. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE761G01016",
  "face_value": 100.0
 },
 {
  "symbol": "BLAL",
  "company_name": "BEML LAND ASSETS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0N7W01012",
  "face_value": 1000.0
 },
 {
  "symbol": "BLBLIMITED",
  "company_name": "BLB LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE791A01024",
  "face_value": 100.0
 },
 {
  "symbol": "BLIL",
  "company_name": "BALMER LAWRIE INVSTS. L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE525F01025",
  "face_value": 100.0
 },
 {
  "symbol": "BLISSGVS",
  "company_name": "BLISS GVS PHARMA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE416D01022",
  "face_value": 100.0
 },
 {
  "symbol": "BLKASHYAP",
  "company_name": "B.L.KASHYAP & SON LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE350H01032",
  "face_value": 100.0
 },
 {
  "symbol": "BLS",
  "company_name": "BLS INTL SERVS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE153T01027",
  "face_value": 100.0
 },
 {
  "symbol": "BLSE",
  "company_name": "BLS E-SERVICES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0NLT01010",
  "face_value": 1000.0
 },
 {
  "symbol": "BLUEBLENDS",
  "company_name": "BLUE BLENDS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE113O01014",
  "face_value": 1000.0
 },
 {
  "symbol": "BLUECHIP",
  "company_name": "BLUE CHIP INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE657B01025",
  "face_value": 200.0
 },
 {
  "symbol": "BLUECOAST",
  "company_name": "BLUE COAST HOTELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE472B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BLUEDART",
  "company_name": "BLUE DART EXPRESS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE233B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "BLUEJET",
  "company_name": "BLUE JET HEALTHCARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0KBH01020",
  "face_value": 200.0
 },
 {
  "symbol": "BLUESTARCO",
  "company_name": "BLUE STAR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE472A01039",
  "face_value": 200.0
 },
 {
  "symbol": "BLUESTONE",
  "company_name": "BLUESTONE JEWEL LFSTL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE304W01038",
  "face_value": 100.0
 },
 {
  "symbol": "BLUSPRING",
  "company_name": "BLUSPRING ENTERPRISES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0U4101014",
  "face_value": 1000.0
 },
 {
  "symbol": "BMWVENTLTD",
  "company_name": "BMW VENTURES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE965W01036",
  "face_value": 1000.0
 },
 {
  "symbol": "BNAGROCHEM",
  "company_name": "BN AGROCHEM LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00HZ01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BNALTD",
  "company_name": "B & A LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE489D01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BNGOLDINAV",
  "company_name": "BARODABNP - BNGOLDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000206",
  "face_value": 1000.0
 },
 {
  "symbol": "BNK10DINAV",
  "company_name": "DSPAMC - BNK10DINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000342",
  "face_value": 1000.0
 },
 {
  "symbol": "BNKETFINAV",
  "company_name": "MIRAEAMC - BNKETFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000190",
  "face_value": 40000.0
 },
 {
  "symbol": "BNKPSUINAV",
  "company_name": "MIRAEAMC - BNKPSUINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000244",
  "face_value": 1000.0
 },
 {
  "symbol": "BODALCHEM",
  "company_name": "BODAL CHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE338D01028",
  "face_value": 200.0
 },
 {
  "symbol": "BOHRAIND",
  "company_name": "BOHRA INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE802W01023",
  "face_value": 1000.0
 },
 {
  "symbol": "BOMDYEING",
  "company_name": "BOMBAY DYEING & MFG. CO L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE032A01023",
  "face_value": 200.0
 },
 {
  "symbol": "BONLON",
  "company_name": "BONLON INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0B9A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "BORANA",
  "company_name": "BORANA WEAVES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE16SF01016",
  "face_value": 1000.0
 },
 {
  "symbol": "BOROGLASS",
  "company_name": "BOROSIL GLASS WORKS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE036101017",
  "face_value": 1000.0
 },
 {
  "symbol": "BOROLTD",
  "company_name": "BOROSIL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02PY01013",
  "face_value": 100.0
 },
 {
  "symbol": "BORORENEW",
  "company_name": "BOROSIL RENEWABLES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE666D01022",
  "face_value": 100.0
 },
 {
  "symbol": "BOROSCI",
  "company_name": "BOROSIL SCIENTIFIC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02L001032",
  "face_value": 100.0
 },
 {
  "symbol": "BOSCH-HCIL",
  "company_name": "BOSCH HOME COMFRT IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE782A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "BOSCHLTD",
  "company_name": "BOSCH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE323A01026",
  "face_value": 1000.0
 },
 {
  "symbol": "BPCL",
  "company_name": "BHARAT PETROLEUM CORP  LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE029A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BPL",
  "company_name": "BPL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE110A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "BRFL",
  "company_name": "BOMBAY RAYON FASHIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE589G01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BRIGADE",
  "company_name": "BRIGADE ENTER. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE791I01019",
  "face_value": 1000.0
 },
 {
  "symbol": "BRIGHOTEL",
  "company_name": "BRIGADE HOTEL VENTURE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE03NU01014",
  "face_value": 1000.0
 },
 {
  "symbol": "BRIGHTBROS",
  "company_name": "BRIGHT BROTHERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE538901013",
  "face_value": 1000.0
 },
 {
  "symbol": "BRITANNIA",
  "company_name": "BRITANNIA INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE216A01030",
  "face_value": 100.0
 },
 {
  "symbol": "BRITEAUTO",
  "company_name": "BRITE AUTOMOTIVE & PLAST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE037101016",
  "face_value": 1000.0
 },
 {
  "symbol": "BRNL",
  "company_name": "BHARAT ROAD NETWORK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE727S01012",
  "face_value": 1000.0
 },
 {
  "symbol": "BROOKS",
  "company_name": "BROOKS LAB LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE650L01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BROOKS-RE",
  "company_name": "BROOKS LAB LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE650L20011",
  "face_value": 1000.0
 },
 {
  "symbol": "BSE",
  "company_name": "BSE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE118H01025",
  "face_value": 200.0
 },
 {
  "symbol": "BSE500IETF",
  "company_name": "ICICIPRAMC - ICICI500",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC1V59",
  "face_value": 100.0
 },
 {
  "symbol": "BSELINFRA",
  "company_name": "BSEL INFRASTRUCTURE REALT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE395A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "BSHSL",
  "company_name": "BOMBAY SUPER HYBRID SEEDS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE032Z01020",
  "face_value": 100.0
 },
 {
  "symbol": "BSI",
  "company_name": "BSI LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE446901014",
  "face_value": 1000.0
 },
 {
  "symbol": "BSL",
  "company_name": "BSL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE594B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "BSLGOLDETF",
  "company_name": "ADITYBIRLA SL GOLD ETF-GR",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KB18D3",
  "face_value": 10.0
 },
 {
  "symbol": "BSLGOLINAV",
  "company_name": "BSLGOLDETF NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000035",
  "face_value": 10.0
 },
 {
  "symbol": "BSLIMITED",
  "company_name": "BS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE043K01029",
  "face_value": 100.0
 },
 {
  "symbol": "BSLNIFINAV",
  "company_name": "BSLNIFTY INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000052",
  "face_value": 100.0
 },
 {
  "symbol": "BSLNIFTY",
  "company_name": "ADITYBIRLA SL NIF ETF-GR",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KB19D1",
  "face_value": 100.0
 },
 {
  "symbol": "BSLSENETFG",
  "company_name": "BIRLASLAMC - BSLSENETFG",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KB10E8",
  "face_value": 100.0
 },
 {
  "symbol": "BSLSENINAV",
  "company_name": "BSLSENETFG INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000051",
  "face_value": 100.0
 },
 {
  "symbol": "BSOFT",
  "company_name": "BIRLASOFT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE836A01035",
  "face_value": 200.0
 },
 {
  "symbol": "BTML",
  "company_name": "BODHI TREE MULTIMEDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0EEJ01023",
  "face_value": 100.0
 },
 {
  "symbol": "BTML-RE1",
  "company_name": "BODHI TREE MULTIMEDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0EEJ20023",
  "face_value": 100.0
 },
 {
  "symbol": "BTTL",
  "company_name": "BHILWARA TECHNICAL TEXT L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE274K01012",
  "face_value": 100.0
 },
 {
  "symbol": "BTWIND",
  "company_name": "BTW INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE037601015",
  "face_value": 1000.0
 },
 {
  "symbol": "BUILDPRO",
  "company_name": "SHANKARA BUILDPRO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE24OJ01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BURNPUR",
  "company_name": "BURNPUR CEMENT LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE817H01022",
  "face_value": 1000.0
 },
 {
  "symbol": "BURRBROWN",
  "company_name": "BURR BROWN (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE038101015",
  "face_value": 1000.0
 },
 {
  "symbol": "BURRWELCOM",
  "company_name": "BURROUGHS WELLCOME (INDIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE157A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "BUTTERFLY",
  "company_name": "BTRFLY GANDHI APPL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE295F01017",
  "face_value": 1000.0
 },
 {
  "symbol": "BUWALKASTL",
  "company_name": "BHUWALKA STEEL INDUS. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE031001014",
  "face_value": 1000.0
 },
 {
  "symbol": "BVCL",
  "company_name": "BARAK VALLEY CEM. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE139I01011",
  "face_value": 1000.0
 },
 {
  "symbol": "BYKE",
  "company_name": "THE BYKE HOSPITALITY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE319B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "CABOTINDIA",
  "company_name": "CABOT INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE144B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "CADBURY",
  "company_name": "CADBURY INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE184A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "CALSOFT",
  "company_name": "CALIFORNIA SOFTWARE CO LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE526B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "CALSOFT-RE",
  "company_name": "CALIFORNIA SOFT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE526B20014",
  "face_value": 1000.0
 },
 {
  "symbol": "CAMLIN-RE",
  "company_name": "CAMLIN FINE SCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE052I20016",
  "face_value": 100.0
 },
 {
  "symbol": "CAMLINFINE",
  "company_name": "CAMLIN FINE SCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE052I01032",
  "face_value": 100.0
 },
 {
  "symbol": "CAMPALLIED",
  "company_name": "CAMPHOR AND ALLIED PRODUC",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE039601013",
  "face_value": 1000.0
 },
 {
  "symbol": "CAMPUS",
  "company_name": "CAMPUS ACTIVEWEAR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE278Y01022",
  "face_value": 500.0
 },
 {
  "symbol": "CAMS",
  "company_name": "COMPUTER AGE MNGT SER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE596I01020",
  "face_value": 200.0
 },
 {
  "symbol": "CANBK",
  "company_name": "CANARA BANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE476A01022",
  "face_value": 200.0
 },
 {
  "symbol": "CANDC",
  "company_name": "C&C CONST. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE874H01015",
  "face_value": 1000.0
 },
 {
  "symbol": "CANFINHOME",
  "company_name": "CAN FIN HOMES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE477A01020",
  "face_value": 200.0
 },
 {
  "symbol": "CANHLIFE",
  "company_name": "CANARA HSBC LIFE INS CO L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01TY01017",
  "face_value": 1000.0
 },
 {
  "symbol": "CANTABIL",
  "company_name": "CANTABIL RETAIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE068L01024",
  "face_value": 200.0
 },
 {
  "symbol": "CAPACITE",
  "company_name": "CAPACITE INFRAPROJECT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE264T01014",
  "face_value": 1000.0
 },
 {
  "symbol": "CAPILLARY",
  "company_name": "CAPILLARY TECHNO INDIA L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0ILV01024",
  "face_value": 200.0
 },
 {
  "symbol": "CAPITALSFB",
  "company_name": "CAPITAL SMALL FIN BANK L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE646H01017",
  "face_value": 1000.0
 },
 {
  "symbol": "CAPLIPOINT",
  "company_name": "CAPLIN POINT LAB LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE475E01026",
  "face_value": 200.0
 },
 {
  "symbol": "CAPRIHANS",
  "company_name": "CAPRIHANS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE479A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "CAPTRU-RE",
  "company_name": "CAPITAL TRUST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE707C20018",
  "face_value": 1000.0
 },
 {
  "symbol": "CAPTRU-RE1",
  "company_name": "CAPITAL TRUST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE707C20026",
  "face_value": 1000.0
 },
 {
  "symbol": "CAPTRUST",
  "company_name": "CAPITAL TRUST LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE707C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "CARBORUNIV",
  "company_name": "CARBORUNDUM UNIVERSAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE120A01034",
  "face_value": 100.0
 },
 {
  "symbol": "CARERATING",
  "company_name": "CARE RATINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE752H01013",
  "face_value": 1000.0
 },
 {
  "symbol": "CARRARO",
  "company_name": "CARRARO INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0V7W01012",
  "face_value": 1000.0
 },
 {
  "symbol": "CARRIERAIR",
  "company_name": "CARRIER AIRCON LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE480A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "CARTRADE",
  "company_name": "CARTRADE TECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE290S01011",
  "face_value": 1000.0
 },
 {
  "symbol": "CARYSIL",
  "company_name": "CARYSIL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE482D01024",
  "face_value": 200.0
 },
 {
  "symbol": "CASHIEINAV",
  "company_name": "ICICIPRAMC - CASHIEINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000265",
  "face_value": 100000.0
 },
 {
  "symbol": "CASHIETF",
  "company_name": "ICICIPRAMC - CASHIETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109K1A021",
  "face_value": 100000.0
 },
 {
  "symbol": "CASTEXTECH",
  "company_name": "CASTEX TECHNOLOGIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE068D01021",
  "face_value": 200.0
 },
 {
  "symbol": "CASTROLIND",
  "company_name": "CASTROL INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE172A01027",
  "face_value": 500.0
 },
 {
  "symbol": "CCAVENUE",
  "company_name": "AVENUESAI LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE483S01020",
  "face_value": 100.0
 },
 {
  "symbol": "CCCL",
  "company_name": "CONS. CONST. CONSORT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE429I01024",
  "face_value": 200.0
 },
 {
  "symbol": "CCHHL",
  "company_name": "COUNTRY CLUB HOSP HOL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE652F01027",
  "face_value": 200.0
 },
 {
  "symbol": "CCI",
  "company_name": "CABLE CORPN. OF INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE475A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "CCL",
  "company_name": "CCL PRODUCTS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE421D01022",
  "face_value": 200.0
 },
 {
  "symbol": "CDSL",
  "company_name": "CENTRAL DEPO SER (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE736A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "CEATLTD",
  "company_name": "CEAT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE482A01020",
  "face_value": 1000.0
 },
 {
  "symbol": "CEENIKEXPO",
  "company_name": "CEENIK EXPORTS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE539101013",
  "face_value": 1000.0
 },
 {
  "symbol": "CEIGALL",
  "company_name": "CEIGALL INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0AG901020",
  "face_value": 500.0
 },
 {
  "symbol": "CEINSYS",
  "company_name": "CEINSYS TECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE016Q01014",
  "face_value": 1000.0
 },
 {
  "symbol": "CELEBRITY",
  "company_name": "CELEBRITY FASHIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE185H01016",
  "face_value": 1000.0
 },
 {
  "symbol": "CELESTE",
  "company_name": "CELESTE INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE042801014",
  "face_value": 1000.0
 },
 {
  "symbol": "CELESTIAL",
  "company_name": "CELESTIAL BIOLABS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE221I01017",
  "face_value": 1000.0
 },
 {
  "symbol": "CELLO",
  "company_name": "CELLO WORLD LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0LMW01024",
  "face_value": 500.0
 },
 {
  "symbol": "CEMPRO",
  "company_name": "CEMINDIA PROJECTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE686A01026",
  "face_value": 100.0
 },
 {
  "symbol": "CENTAKCHEM",
  "company_name": "CENTAK CHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE942A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "CENTENKA",
  "company_name": "CENTURY ENKA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE485A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "CENTEXT",
  "company_name": "CENTURY EXTRUSIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE281A01026",
  "face_value": 100.0
 },
 {
  "symbol": "CENTRALBK",
  "company_name": "CENTRAL BANK OF INDIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE483A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "CENTRLROAD",
  "company_name": "CENTRAL  ROADLINES CORPN",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE043601017",
  "face_value": 1000.0
 },
 {
  "symbol": "CENTRUM",
  "company_name": "CENTRUM CAPITAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE660C01027",
  "face_value": 100.0
 },
 {
  "symbol": "CENTUM",
  "company_name": "CENTUM ELECTRONICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE320B01020",
  "face_value": 1000.0
 },
 {
  "symbol": "CENTURYPLY",
  "company_name": "CENTURY PLYBOARDS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE348B01021",
  "face_value": 100.0
 },
 {
  "symbol": "CERA",
  "company_name": "CERA SANITARYWARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE739E01017",
  "face_value": 500.0
 },
 {
  "symbol": "CEREBRAINT",
  "company_name": "CEREBRA INT TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE345B01019",
  "face_value": 1000.0
 },
 {
  "symbol": "CESC",
  "company_name": "CESC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE486A01021",
  "face_value": 100.0
 },
 {
  "symbol": "CEWATER",
  "company_name": "CONCORD ENVIRO SYSTEMS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE037Z01029",
  "face_value": 500.0
 },
 {
  "symbol": "CGCL",
  "company_name": "CAPRI GLOBAL CAPITAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE180C01042",
  "face_value": 100.0
 },
 {
  "symbol": "CGCL-RE",
  "company_name": "CAPRI GLOBAL CAP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE180C20018",
  "face_value": 200.0
 },
 {
  "symbol": "CGGLASS",
  "company_name": "CG GLASS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE045001018",
  "face_value": 1000.0
 },
 {
  "symbol": "CGPOWER",
  "company_name": "CG POWER AND IND SOL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE067A01029",
  "face_value": 200.0
 },
 {
  "symbol": "CHALET",
  "company_name": "CHALET HOTELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE427F01016",
  "face_value": 1000.0
 },
 {
  "symbol": "CHAMBLFERT",
  "company_name": "CHAMBAL FERTILIZERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE085A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "CHEMBOND",
  "company_name": "CHEMBOND MATERIALTECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE995D01025",
  "face_value": 500.0
 },
 {
  "symbol": "CHEMBONDCH",
  "company_name": "CHEMBOND CHEMICAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0TGX01019",
  "face_value": 500.0
 },
 {
  "symbol": "CHEMCON",
  "company_name": "CHEMCON SPECIAL CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE03YM01018",
  "face_value": 1000.0
 },
 {
  "symbol": "CHEMFAB",
  "company_name": "CHEMFAB ALKALIS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE783X01023",
  "face_value": 1000.0
 },
 {
  "symbol": "CHEMICAL",
  "company_name": "KOTAKMAMC - CHEMICAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1XV0",
  "face_value": 1000.0
 },
 {
  "symbol": "CHEMINAV",
  "company_name": "KOTAKMAMC - CHEMINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000314",
  "face_value": 1000.0
 },
 {
  "symbol": "CHEMOXSEC",
  "company_name": "CHEMOX SECURITIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE047001016",
  "face_value": 1000.0
 },
 {
  "symbol": "CHEMPLASTS",
  "company_name": "CHEMPLAST SANMAR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE488A01050",
  "face_value": 500.0
 },
 {
  "symbol": "CHENNPETRO",
  "company_name": "CHENNAI PETROLEUM CORP LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE178A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "CHETNADCEM",
  "company_name": "CHETTINAD CEMENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE132B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "CHEVIOT",
  "company_name": "CHEVIOT COMPANY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE974B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "CHGOLDINAV",
  "company_name": "CHOICEAMC - CHGOLDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000309",
  "face_value": 10000.0
 },
 {
  "symbol": "CHOICEGOLD",
  "company_name": "CHOICEAMC - CHOICEGOLD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF2KCX01012",
  "face_value": 10000.0
 },
 {
  "symbol": "CHOICEIN",
  "company_name": "CHOICE INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE102B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "CHOKAINTL",
  "company_name": "CHOKHANI INTERNATIONAL LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE448401013",
  "face_value": 1000.0
 },
 {
  "symbol": "CHOKSITUBE",
  "company_name": "CHOKSI TUBE CO. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE048501014",
  "face_value": 1000.0
 },
 {
  "symbol": "CHOLAFIN",
  "company_name": "CHOLAMANDALAM IN & FIN CO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE121A01024",
  "face_value": 200.0
 },
 {
  "symbol": "CHOLAHLDNG",
  "company_name": "CHOLAMANDALAM FIN HOL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE149A01033",
  "face_value": 100.0
 },
 {
  "symbol": "CHOWGULSTM",
  "company_name": "CHOWGULE STEAMSHIPS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE490A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "CHROMATIC",
  "company_name": "CHROMATIC INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE662C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "CIBASPEC",
  "company_name": "CIBA SPECIALITY CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE908A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "CIEINDIA",
  "company_name": "CIE AUTOMOTIVE INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE536H01010",
  "face_value": 1000.0
 },
 {
  "symbol": "CIFL",
  "company_name": "CAPITAL INDIA FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE345H01024",
  "face_value": 200.0
 },
 {
  "symbol": "CIGNITITEC",
  "company_name": "CIGNITI TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE675C01017",
  "face_value": 1000.0
 },
 {
  "symbol": "CIMCOBIRLA",
  "company_name": "CIMMCO BIRLA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE184C01010",
  "face_value": 1000.0
 },
 {
  "symbol": "CIMMCO",
  "company_name": "CIMMCO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE184C01028",
  "face_value": 1000.0
 },
 {
  "symbol": "CINELINE",
  "company_name": "CINELINE INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE704H01022",
  "face_value": 500.0
 },
 {
  "symbol": "CINEVISTA",
  "company_name": "CINEVISTA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE039B01026",
  "face_value": 200.0
 },
 {
  "symbol": "CIPLA",
  "company_name": "CIPLA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE059A01026",
  "face_value": 200.0
 },
 {
  "symbol": "CITURGIBIO",
  "company_name": "CITURGIA BIOCHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE795B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "CKFSL",
  "company_name": "COX & KINGS FIN SERV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE391Z01012",
  "face_value": 1000.0
 },
 {
  "symbol": "CLCIND",
  "company_name": "CLC INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE376C01038",
  "face_value": 1000.0
 },
 {
  "symbol": "CLEAN",
  "company_name": "CLEAN SCIENCE & TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE227W01023",
  "face_value": 100.0
 },
 {
  "symbol": "CLEANMAX",
  "company_name": "CLEAN MAX ENVIRO EN SOL L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE647U01026",
  "face_value": 100.0
 },
 {
  "symbol": "CLEDUCATE",
  "company_name": "CL EDUCATE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE201M01029",
  "face_value": 500.0
 },
 {
  "symbol": "CLIFCO",
  "company_name": "COIMBATORE LAKSHMI INVEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE051901010",
  "face_value": 1000.0
 },
 {
  "symbol": "CLSEL",
  "company_name": "CHAMAN LAL SETIA EXP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE419D01026",
  "face_value": 200.0
 },
 {
  "symbol": "CMICABLES",
  "company_name": "CMI LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE981B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "CMPDI",
  "company_name": "CENTRAL MINE P N D INST L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE05HV01027",
  "face_value": 200.0
 },
 {
  "symbol": "CMSINFO",
  "company_name": "CMS INFO SYSTEMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE925R01014",
  "face_value": 1000.0
 },
 {
  "symbol": "CNL",
  "company_name": "CREATIVE NEWTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE985W01018",
  "face_value": 1000.0
 },
 {
  "symbol": "CNOVAPETRO",
  "company_name": "CIL NOVA PETROCHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE672K01025",
  "face_value": 1000.0
 },
 {
  "symbol": "COALINDIA",
  "company_name": "COAL INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE522F01014",
  "face_value": 1000.0
 },
 {
  "symbol": "COAST-RE",
  "company_name": "COASTAL CORP LIMITED-RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE377E20016",
  "face_value": 1000.0
 },
 {
  "symbol": "COASTCORP",
  "company_name": "COASTAL CORPORATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE377E01024",
  "face_value": 200.0
 },
 {
  "symbol": "COCHINSHIP",
  "company_name": "COCHIN SHIPYARD LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE704P01025",
  "face_value": 500.0
 },
 {
  "symbol": "COCKERILL",
  "company_name": "JOHN COCKERILL INDIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE515A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "COFFEEDAY",
  "company_name": "COFFEE DAY ENTERPRISE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE335K01011",
  "face_value": 1000.0
 },
 {
  "symbol": "COFORGE",
  "company_name": "COFORGE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE591G01025",
  "face_value": 200.0
 },
 {
  "symbol": "COHANCE",
  "company_name": "COHANCE LIFESCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE03QK01018",
  "face_value": 100.0
 },
 {
  "symbol": "COLPAL",
  "company_name": "COLGATE PALMOLIVE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE259A01022",
  "face_value": 100.0
 },
 {
  "symbol": "COMFINTE",
  "company_name": "COMFORT INTECH LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE819A01049",
  "face_value": 100.0
 },
 {
  "symbol": "COMMOIETF",
  "company_name": "ICICIPRAMC - ICICICOMMO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC19O8",
  "face_value": 1000.0
 },
 {
  "symbol": "COMP-RE",
  "company_name": "COMPUAGE INFOCOM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE070C20011",
  "face_value": 200.0
 },
 {
  "symbol": "COMPACDISC",
  "company_name": "COMPACT DISC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE052701013",
  "face_value": 1000.0
 },
 {
  "symbol": "COMPINFO",
  "company_name": "COMPUAGE INFOCOM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE070C01037",
  "face_value": 200.0
 },
 {
  "symbol": "COMPUSOFT",
  "company_name": "COMPUCOM SOFTWARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE453B01029",
  "face_value": 200.0
 },
 {
  "symbol": "COMSYN",
  "company_name": "COMMERCIAL SYN BAGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE073V01015",
  "face_value": 1000.0
 },
 {
  "symbol": "CONCOR",
  "company_name": "CONTAINER CORP OF IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE111A01025",
  "face_value": 500.0
 },
 {
  "symbol": "CONCORDBIO",
  "company_name": "CONCORD BIOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE338H01029",
  "face_value": 100.0
 },
 {
  "symbol": "CONFIPET",
  "company_name": "CONFIDENCE PETRO IND LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE552D01024",
  "face_value": 100.0
 },
 {
  "symbol": "CONS",
  "company_name": "KOTAKMAMC - KOTAKCONS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1ZF8",
  "face_value": 100.0
 },
 {
  "symbol": "CONSOFINVT",
  "company_name": "CONSO. FIN. & HOLD. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE025A01027",
  "face_value": 1000.0
 },
 {
  "symbol": "CONSUMBEES",
  "company_name": "NIP IND ETF CONSUMPTION",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KA1LD7",
  "face_value": 1000.0
 },
 {
  "symbol": "CONSUMER",
  "company_name": "MIRAEAMC - CONSUMER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01NS5",
  "face_value": 1000.0
 },
 {
  "symbol": "CONSUMIETF",
  "company_name": "ICICIPRAMC - ICICICONSU",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC1V42",
  "face_value": 1000.0
 },
 {
  "symbol": "CONSUMINAV",
  "company_name": "MIRAEAMC - CONSUMINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000252",
  "face_value": 1000.0
 },
 {
  "symbol": "CONTNLCONS",
  "company_name": "CONTINENTAL CONSTRUCTIONS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE970B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "CONTROLPR",
  "company_name": "CONTROL PRINT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE663B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "CORALFINAC",
  "company_name": "CORAL INDIA FIN & HOUS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE558D01021",
  "face_value": 200.0
 },
 {
  "symbol": "CORDSCABLE",
  "company_name": "CORDS CABLE INDUS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE792I01017",
  "face_value": 1000.0
 },
 {
  "symbol": "COROMANDEL",
  "company_name": "COROMANDEL INTERNTL. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE169A01031",
  "face_value": 100.0
 },
 {
  "symbol": "CORONA",
  "company_name": "CORONA REMEDIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02ZQ01018",
  "face_value": 1000.0
 },
 {
  "symbol": "COSMOFIRST",
  "company_name": "COSMO FIRST LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE757A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "COUNCODOS",
  "company_name": "COUNTRY CONDO S LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE695B01025",
  "face_value": 100.0
 },
 {
  "symbol": "COX&KINGS",
  "company_name": "COX & KINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE008I01026",
  "face_value": 500.0
 },
 {
  "symbol": "CPCAP",
  "company_name": "CP CAPITAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE521J01018",
  "face_value": 1000.0
 },
 {
  "symbol": "CPEDU",
  "company_name": "CAREER POINT EDUTECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0P6P01016",
  "face_value": 1000.0
 },
 {
  "symbol": "CPPLUS",
  "company_name": "ADITYA INFOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE819V01029",
  "face_value": 100.0
 },
 {
  "symbol": "CPSEETF",
  "company_name": "CPSE ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF457M01133",
  "face_value": 1000.0
 },
 {
  "symbol": "CPSEETFNAV",
  "company_name": "CPSE ETF NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000019",
  "face_value": 1000.0
 },
 {
  "symbol": "CRAFTSMAN",
  "company_name": "CRAFTSMAN AUTOMATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00LO01017",
  "face_value": 500.0
 },
 {
  "symbol": "CRAMC",
  "company_name": "CANARA ROBECO AMC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE218I01013",
  "face_value": 1000.0
 },
 {
  "symbol": "CREATIVEYE",
  "company_name": "CREATIVE EYE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE230B01021",
  "face_value": 500.0
 },
 {
  "symbol": "CREDITACC",
  "company_name": "CREDITACCESS GRAMEEN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE741K01010",
  "face_value": 1000.0
 },
 {
  "symbol": "CREST",
  "company_name": "CREST VENTURES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE559D01011",
  "face_value": 1000.0
 },
 {
  "symbol": "CRISIL",
  "company_name": "CRISIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE007A01025",
  "face_value": 100.0
 },
 {
  "symbol": "CRIZAC",
  "company_name": "CRIZAC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0S4R01014",
  "face_value": 200.0
 },
 {
  "symbol": "CROMPTON",
  "company_name": "CROMPT GREA CON ELEC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE299U01018",
  "face_value": 200.0
 },
 {
  "symbol": "CROWN",
  "company_name": "CROWN LIFTERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE491V01019",
  "face_value": 1000.0
 },
 {
  "symbol": "CSBBANK",
  "company_name": "CSB BANK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE679A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "CSLFINANCE",
  "company_name": "CSL FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE718F01018",
  "face_value": 1000.0
 },
 {
  "symbol": "CTCOTTON",
  "company_name": "CT COTTON YARN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE038601014",
  "face_value": 1000.0
 },
 {
  "symbol": "CTE",
  "company_name": "CAMBRIDGE TECH ENTER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE627H01017",
  "face_value": 1000.0
 },
 {
  "symbol": "CUB",
  "company_name": "CITY UNION BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE491A01021",
  "face_value": 100.0
 },
 {
  "symbol": "CUBEXTUB",
  "company_name": "CUBEX TUBINGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE144D01012",
  "face_value": 1000.0
 },
 {
  "symbol": "CUMMINSIND",
  "company_name": "CUMMINS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE298A01020",
  "face_value": 200.0
 },
 {
  "symbol": "CUPID",
  "company_name": "CUPID LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE509F01029",
  "face_value": 100.0
 },
 {
  "symbol": "CURAA",
  "company_name": "CURA TECHNOLOGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE117B01020",
  "face_value": 1000.0
 },
 {
  "symbol": "CURATECH",
  "company_name": "CURA TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE117B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "CYBER-RE",
  "company_name": "CYBER MEDIA (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE278G20011",
  "face_value": 1000.0
 },
 {
  "symbol": "CYBERMEDIA",
  "company_name": "CYBER MEDIA (INDIA) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE278G01037",
  "face_value": 1000.0
 },
 {
  "symbol": "CYBERTECH",
  "company_name": "CYBERTECH SYSTEMS & SOFTW",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE214A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "CYIENT",
  "company_name": "CYIENT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE136B01020",
  "face_value": 500.0
 },
 {
  "symbol": "CYIENTDLM",
  "company_name": "CYIENT DLM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE055S01018",
  "face_value": 1000.0
 },
 {
  "symbol": "DABUR",
  "company_name": "DABUR INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE016A01026",
  "face_value": 100.0
 },
 {
  "symbol": "DAGERFORST",
  "company_name": "DAGGER-FORST TOOLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE542201012",
  "face_value": 1000.0
 },
 {
  "symbol": "DAICHI",
  "company_name": "DAI-ICHI KARKARIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE928C01010",
  "face_value": 1000.0
 },
 {
  "symbol": "DAICHIKARK",
  "company_name": "DAI ICHI KARKARIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE059401013",
  "face_value": 1000.0
 },
 {
  "symbol": "DALBHARAT",
  "company_name": "DALMIA BHARAT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00R701025",
  "face_value": 200.0
 },
 {
  "symbol": "DALMIASUG",
  "company_name": "DALMIA BHARAT SUG IN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE495A01022",
  "face_value": 200.0
 },
 {
  "symbol": "DAMANIAAIR",
  "company_name": "SKYLINE NEPC LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE059701016",
  "face_value": 1000.0
 },
 {
  "symbol": "DAMCAPITAL",
  "company_name": "DAM CAPITAL ADVISORS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE284H01025",
  "face_value": 200.0
 },
 {
  "symbol": "DAMODARIND",
  "company_name": "DAMODAR INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE497D01022",
  "face_value": 500.0
 },
 {
  "symbol": "DANGEE",
  "company_name": "DANGEE DUMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE688Y01022",
  "face_value": 100.0
 },
 {
  "symbol": "DATAMATICS",
  "company_name": "DATAMATICS GLOBAL SER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE365B01017",
  "face_value": 500.0
 },
 {
  "symbol": "DATAPATTNS",
  "company_name": "DATA PATTERNS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0IX101010",
  "face_value": 200.0
 },
 {
  "symbol": "DATAPROINF",
  "company_name": "DATAPRO INFORMATION TECHN",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE060301012",
  "face_value": 1000.0
 },
 {
  "symbol": "DATARSWICH",
  "company_name": "DATAR SWITCHGEAR LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE060401010",
  "face_value": 1000.0
 },
 {
  "symbol": "DAURALAORG",
  "company_name": "DAURALA ORGANICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE060701013",
  "face_value": 1000.0
 },
 {
  "symbol": "DAVAN-RE1",
  "company_name": "DAVANGERE SUGAR COMPANY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE179G20029",
  "face_value": 100.0
 },
 {
  "symbol": "DAVANGERE",
  "company_name": "DAVANGERE SUGAR COMPANY L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE179G01029",
  "face_value": 100.0
 },
 {
  "symbol": "DBCORP",
  "company_name": "D.B.CORP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE950I01011",
  "face_value": 1000.0
 },
 {
  "symbol": "DBEIL",
  "company_name": "DEEPAK BUILDERS & ENG I L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0OPA01019",
  "face_value": 1000.0
 },
 {
  "symbol": "DBL",
  "company_name": "DILIP BUILDCON LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE917M01012",
  "face_value": 1000.0
 },
 {
  "symbol": "DBOL",
  "company_name": "DHAMPUR BIO ORGANICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0I3401014",
  "face_value": 1000.0
 },
 {
  "symbol": "DBREALTY",
  "company_name": "VALOR ESTATE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE879I01012",
  "face_value": 1000.0
 },
 {
  "symbol": "DBSTOCKBRO",
  "company_name": "DB (INT) STOCK BROKERS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE921B01025",
  "face_value": 200.0
 },
 {
  "symbol": "DCAL",
  "company_name": "DISHMAN CARBO AMCIS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE385W01011",
  "face_value": 200.0
 },
 {
  "symbol": "DCBBANK",
  "company_name": "DCB BANK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE503A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "DCI",
  "company_name": "DC INFOTECH AND COMUN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0A1101019",
  "face_value": 1000.0
 },
 {
  "symbol": "DCM",
  "company_name": "DCM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE498A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "DCMDAEWOO",
  "company_name": "DCM DAEWOO MOTORS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE497A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "DCMFINSERV",
  "company_name": "DCM FINANCIAL SERVICES LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE891B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "DCMNVL",
  "company_name": "DCM NOUVELLE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE08KP01019",
  "face_value": 1000.0
 },
 {
  "symbol": "DCMSHRIRAM",
  "company_name": "DCM SHRIRAM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE499A01024",
  "face_value": 200.0
 },
 {
  "symbol": "DCMSIL",
  "company_name": "DCM SHRIRAM INTERNATNL L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0OU201013",
  "face_value": 200.0
 },
 {
  "symbol": "DCMSRIND",
  "company_name": "DCM SHRIRAM IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE843D01027",
  "face_value": 200.0
 },
 {
  "symbol": "DCMSRMIND",
  "company_name": "DCM SHRIRAM INDUSTRIES LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE061501016",
  "face_value": 1000.0
 },
 {
  "symbol": "DCW",
  "company_name": "DCW LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE500A01029",
  "face_value": 200.0
 },
 {
  "symbol": "DCXINDIA",
  "company_name": "DCX SYSTEMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0KL801015",
  "face_value": 200.0
 },
 {
  "symbol": "DDEVPLSTIK",
  "company_name": "DDEV PLASTIKS IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0HR601026",
  "face_value": 100.0
 },
 {
  "symbol": "DECANGRAN",
  "company_name": "DECCAN GRANITES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE061701012",
  "face_value": 1000.0
 },
 {
  "symbol": "DECCANCE",
  "company_name": "DECCAN CEMENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE583C01021",
  "face_value": 500.0
 },
 {
  "symbol": "DECNGOLD",
  "company_name": "DECCAN GOLD MINES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE945F01025",
  "face_value": 100.0
 },
 {
  "symbol": "DEEDEV",
  "company_name": "DEE DEVELOPMENT ENG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE841L01016",
  "face_value": 1000.0
 },
 {
  "symbol": "DEEPAK-RE",
  "company_name": "DEEPAK FERTILIZERS RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE501A20019",
  "face_value": 1000.0
 },
 {
  "symbol": "DEEPAKFERT",
  "company_name": "DEEPAK FERTILIZERS & PETR",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE501A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "DEEPAKNITR",
  "company_name": "DEEPAK NITRITE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE288B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "DEEPAKNTR",
  "company_name": "DEEPAK NITRITE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE288B01029",
  "face_value": 200.0
 },
 {
  "symbol": "DEEPAKSPIN",
  "company_name": "DEEPAK SPINNERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE062401018",
  "face_value": 1000.0
 },
 {
  "symbol": "DEEPENR",
  "company_name": "DEEP ENE RESOURCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE677H01012",
  "face_value": 1000.0
 },
 {
  "symbol": "DEEPHARMA",
  "company_name": "DEE-PHARMA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE062501015",
  "face_value": 1000.0
 },
 {
  "symbol": "DEEPINDS",
  "company_name": "DEEP INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0FHS01024",
  "face_value": 500.0
 },
 {
  "symbol": "DEFENCE",
  "company_name": "MIRAEAMC - DEFENCE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01QC2",
  "face_value": 1000.0
 },
 {
  "symbol": "DEFENCINAV",
  "company_name": "MIRAEAMC - DEFENCINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000336",
  "face_value": 1000.0
 },
 {
  "symbol": "DELHIVERY",
  "company_name": "DELHIVERY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE148O01028",
  "face_value": 100.0
 },
 {
  "symbol": "DELPH-RE",
  "company_name": "ELPHI WORLD MONEY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE726L20019",
  "face_value": 1000.0
 },
 {
  "symbol": "DELPHIFX",
  "company_name": "DELPHI WORLD MONEY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE726L01027",
  "face_value": 200.0
 },
 {
  "symbol": "DELTACORP",
  "company_name": "DELTA CORP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE124G01033",
  "face_value": 100.0
 },
 {
  "symbol": "DELTAMAGNT",
  "company_name": "DELTA MANUFACTURING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE393A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "DEN",
  "company_name": "DEN NETWORKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE947J01015",
  "face_value": 1000.0
 },
 {
  "symbol": "DENMURFAX",
  "company_name": "DENMUR FAX ROLL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE063301019",
  "face_value": 1000.0
 },
 {
  "symbol": "DENORA",
  "company_name": "DE NORA INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE244A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "DENTA",
  "company_name": "DENTA WATER N INFRA SOL L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0R4L01018",
  "face_value": 1000.0
 },
 {
  "symbol": "DEVIT",
  "company_name": "DEV INFO TECHNOLOGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE060X01034",
  "face_value": 200.0
 },
 {
  "symbol": "DEVX",
  "company_name": "DEV ACCELERATOR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0VOV01021",
  "face_value": 200.0
 },
 {
  "symbol": "DEVYANI",
  "company_name": "DEVYANI INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE872J01023",
  "face_value": 100.0
 },
 {
  "symbol": "DEWANRUB",
  "company_name": "DEWAN RUBBER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE064201010",
  "face_value": 1000.0
 },
 {
  "symbol": "DEWANSTEEL",
  "company_name": "DEWAN STEELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE064301018",
  "face_value": 1000.0
 },
 {
  "symbol": "DEWANTYRE",
  "company_name": "DEWAN TYRE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE064501013",
  "face_value": 1000.0
 },
 {
  "symbol": "DFMFOODS",
  "company_name": "DFM FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE456C01020",
  "face_value": 200.0
 },
 {
  "symbol": "DGCONTENT",
  "company_name": "DIGICONTENT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE03JI01017",
  "face_value": 200.0
 },
 {
  "symbol": "DHAMPURSUG",
  "company_name": "DHAMPUR SUGAR MILLS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE041A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "DHAN-RE",
  "company_name": "DHANLAXMI BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE680A20011",
  "face_value": 1000.0
 },
 {
  "symbol": "DHANBANK",
  "company_name": "DHANLAXMI BANK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE680A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "DHANI",
  "company_name": "DHANI SERVICES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE274G01010",
  "face_value": 200.0
 },
 {
  "symbol": "DHANUKA",
  "company_name": "DHANUKA AGRITECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE435G01025",
  "face_value": 200.0
 },
 {
  "symbol": "DHARAMORAR",
  "company_name": "DHARAMSI MORARJI CHEMICAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE505A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "DHARAN",
  "company_name": "DHARAN INFRA-EPC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE278R01034",
  "face_value": 100.0
 },
 {
  "symbol": "DHARMAJ",
  "company_name": "DHARMAJ CROP GUARD LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00OQ01016",
  "face_value": 1000.0
 },
 {
  "symbol": "DHARNENIND",
  "company_name": "DHARNENDRA INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE449301014",
  "face_value": 1000.0
 },
 {
  "symbol": "DHARSUGAR",
  "company_name": "DHARANI SUGARS & CHEMICAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE988C01014",
  "face_value": 1000.0
 },
 {
  "symbol": "DHFL",
  "company_name": "DEWAN HOUSING FIN CORP LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE202B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "DHRUV",
  "company_name": "DHRUV CONSULTANCY SER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE506Z01015",
  "face_value": 1000.0
 },
 {
  "symbol": "DHUNINV",
  "company_name": "DHUNSERI INVESTMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE320L01011",
  "face_value": 1000.0
 },
 {
  "symbol": "DIACABS",
  "company_name": "DIAMOND POWER INFRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE989C01038",
  "face_value": 100.0
 },
 {
  "symbol": "DIAMINESQ",
  "company_name": "DIAMINES & CHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE591D01014",
  "face_value": 1000.0
 },
 {
  "symbol": "DIAMONDYD",
  "company_name": "PRATAAP SNACKS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE393P01035",
  "face_value": 500.0
 },
 {
  "symbol": "DIAPOWER",
  "company_name": "DIAMOND POWER INFRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE989C01012",
  "face_value": 1000.0
 },
 {
  "symbol": "DICIND",
  "company_name": "DIC INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE303A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "DIFFNKG",
  "company_name": "DIFFUSION ENGINEERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE184O01015",
  "face_value": 1000.0
 },
 {
  "symbol": "DIGIDRIVE",
  "company_name": "DIGIDRIVE DISTRIBUTORS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0PSC01024",
  "face_value": 1000.0
 },
 {
  "symbol": "DIGISPICE",
  "company_name": "DIGISPICE TECHNOLOGIES LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE927C01020",
  "face_value": 300.0
 },
 {
  "symbol": "DIGITIDE",
  "company_name": "DIGITIDE SOLUTIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0U4701011",
  "face_value": 1000.0
 },
 {
  "symbol": "DIGJAMLMTD",
  "company_name": "DIGJAM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE731U01028",
  "face_value": 1000.0
 },
 {
  "symbol": "DIGJAMLTD",
  "company_name": "DIGJAM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE731U01010",
  "face_value": 1000.0
 },
 {
  "symbol": "DIL",
  "company_name": "DEBOCK INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE411Y01011",
  "face_value": 1000.0
 },
 {
  "symbol": "DIL-RE",
  "company_name": "DEBOCK INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE411Y20011",
  "face_value": 1000.0
 },
 {
  "symbol": "DISAQ",
  "company_name": "DISA INDIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE131C01011",
  "face_value": 1000.0
 },
 {
  "symbol": "DISHTV",
  "company_name": "DISH TV INDIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE836F01026",
  "face_value": 100.0
 },
 {
  "symbol": "DIVGIITTS",
  "company_name": "DIVGI TORQTRANSFER SYST L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE753U01022",
  "face_value": 500.0
 },
 {
  "symbol": "DIVIDEINAV",
  "company_name": "MIRAEAMC - DIVIDEINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000326",
  "face_value": 1000.0
 },
 {
  "symbol": "DIVIDEND",
  "company_name": "MIRAEAMC - DIVIDEND",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01PY8",
  "face_value": 1000.0
 },
 {
  "symbol": "DIVISLAB",
  "company_name": "DIVI S LABORATORIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE361B01024",
  "face_value": 200.0
 },
 {
  "symbol": "DIVOPPBEES",
  "company_name": "NIP IND ETF DIV OPP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KA1MS3",
  "face_value": 1000.0
 },
 {
  "symbol": "DIXON",
  "company_name": "DIXON TECHNO (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE935N01020",
  "face_value": 200.0
 },
 {
  "symbol": "DJML",
  "company_name": "DJ MEDIAPRINT & LOG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0B1K01014",
  "face_value": 1000.0
 },
 {
  "symbol": "DLF",
  "company_name": "DLF LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE271C01023",
  "face_value": 200.0
 },
 {
  "symbol": "DLINKINDIA",
  "company_name": "D-LINK INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE250K01012",
  "face_value": 200.0
 },
 {
  "symbol": "DMART",
  "company_name": "AVENUE SUPERMARTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE192R01011",
  "face_value": 1000.0
 },
 {
  "symbol": "DMCC",
  "company_name": "DMCC SPECIALITY CHEMICALS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE505A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "DNAMEDIA",
  "company_name": "DILIGENT MEDIA CORP LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE016M01021",
  "face_value": 100.0
 },
 {
  "symbol": "DODLA",
  "company_name": "DODLA DAIRY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE021O01019",
  "face_value": 1000.0
 },
 {
  "symbol": "DOLATALGO",
  "company_name": "DOLAT ALGOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE966A01022",
  "face_value": 100.0
 },
 {
  "symbol": "DOLLAR",
  "company_name": "DOLLAR INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE325C01035",
  "face_value": 200.0
 },
 {
  "symbol": "DOLPHIN",
  "company_name": "DOLPHIN OFF ENT (IND) L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE920A01037",
  "face_value": 100.0
 },
 {
  "symbol": "DOLPHINOFF",
  "company_name": "DOLPHIN OFF. ENT IND LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE920A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "DOMS",
  "company_name": "DOMS INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE321T01012",
  "face_value": 1000.0
 },
 {
  "symbol": "DONEAR",
  "company_name": "DONEAR IND. LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE668D01028",
  "face_value": 200.0
 },
 {
  "symbol": "DOONVALLEY",
  "company_name": "DOON VALLEY RICE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY9099",
  "face_value": 1000.0
 },
 {
  "symbol": "DPABHUSHAN",
  "company_name": "D. P. ABHUSHAN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE266Y01019",
  "face_value": 1000.0
 },
 {
  "symbol": "DPSCLTD",
  "company_name": "DPSC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE360C01024",
  "face_value": 100.0
 },
 {
  "symbol": "DPWIRES",
  "company_name": "D P WIRES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE864X01013",
  "face_value": 1000.0
 },
 {
  "symbol": "DQE",
  "company_name": "DQ ENTERTAINMENT INT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE656K01010",
  "face_value": 1000.0
 },
 {
  "symbol": "DRAGARWQ",
  "company_name": "DR. AGARWAL'S EYE HOSP L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE934C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "DRBECK",
  "company_name": "SCHENECTADY-BECK INDIA LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYY000003",
  "face_value": 1000.0
 },
 {
  "symbol": "DRCSYSTEMS",
  "company_name": "DRC SYSTEMS INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE03RS01027",
  "face_value": 100.0
 },
 {
  "symbol": "DREAMFOLKS",
  "company_name": "DREAMFOLKS SERVICES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0JS101016",
  "face_value": 200.0
 },
 {
  "symbol": "DREDGECORP",
  "company_name": "DREDGING CORP OF INDIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE506A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "DRREDDY",
  "company_name": "DR. REDDY S LABORATORIES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE089A01031",
  "face_value": 100.0
 },
 {
  "symbol": "DSFCL",
  "company_name": "DCM SHRIRAM FINE CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0OFM01015",
  "face_value": 200.0
 },
 {
  "symbol": "DSKULKARNI",
  "company_name": "D S KULKARNI DEVELOPERS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE891A01022",
  "face_value": 1000.0
 },
 {
  "symbol": "DSPBNKINAV",
  "company_name": "DSPAMC - DSPBNKINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000174",
  "face_value": 1000.0
 },
 {
  "symbol": "DSPGOINAV",
  "company_name": "DSPAMC - DSPGOLDETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000186",
  "face_value": 1000.0
 },
 {
  "symbol": "DSPN50INAV",
  "company_name": "DSPN50ETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000061",
  "face_value": 100.0
 },
 {
  "symbol": "DSPNEWINAV",
  "company_name": "DSPNEWETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000060",
  "face_value": 100.0
 },
 {
  "symbol": "DSPNITINAV",
  "company_name": "DSPAMC - DSPNITINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000189",
  "face_value": 1000.0
 },
 {
  "symbol": "DSPPSBINAV",
  "company_name": "DSPAMC - DSPPSBINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000193",
  "face_value": 1000.0
 },
 {
  "symbol": "DSPPVBINAV",
  "company_name": "DSPAMC - DSPPVBINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000192",
  "face_value": 1000.0
 },
 {
  "symbol": "DSPQ50INAV",
  "company_name": "DSPQ50ETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000062",
  "face_value": 100.0
 },
 {
  "symbol": "DSPSENINAV",
  "company_name": "DSPAMC - DSPSENINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000194",
  "face_value": 1000.0
 },
 {
  "symbol": "DSPSILINAV",
  "company_name": "DSPAMC - DSPSILINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000159",
  "face_value": 1000.0
 },
 {
  "symbol": "DSSL",
  "company_name": "DYNACONS SYS & SOLN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE417B01040",
  "face_value": 1000.0
 },
 {
  "symbol": "DTIL",
  "company_name": "DHUNSERI TEA & IND. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE341R01014",
  "face_value": 1000.0
 },
 {
  "symbol": "DUCON",
  "company_name": "DUCON INFRATECHNOLOGIES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE741L01018",
  "face_value": 100.0
 },
 {
  "symbol": "DUCON-RE",
  "company_name": "DUCON INFRATECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE741L20018",
  "face_value": 100.0
 },
 {
  "symbol": "DUNCANSIND",
  "company_name": "DUNCANS INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE508A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "DUNLOP",
  "company_name": "DUNLOP (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE070201012",
  "face_value": 1000.0
 },
 {
  "symbol": "DVL",
  "company_name": "DHUNSERI VENTURES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE477B01010",
  "face_value": 1000.0
 },
 {
  "symbol": "DWARKESH",
  "company_name": "DWARIKESH SUGAR IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE366A01041",
  "face_value": 100.0
 },
 {
  "symbol": "DYCL",
  "company_name": "DYNAMIC CABLES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE600Y01019",
  "face_value": 1000.0
 },
 {
  "symbol": "DYNAMATECH",
  "company_name": "DYNAMATIC TECHNOLOGIES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE221B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "DYNAPHARMA",
  "company_name": "DYNACHEM PHARMA (EXPORTS)",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE070801019",
  "face_value": 1000.0
 },
 {
  "symbol": "DYNPRO",
  "company_name": "DYNEMIC PRODUCTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE256H01015",
  "face_value": 1000.0
 },
 {
  "symbol": "DYNPRO-RE",
  "company_name": "DYNEMIC PRODUCTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE256H20015",
  "face_value": 1000.0
 },
 {
  "symbol": "E2E",
  "company_name": "E2E NETWORKS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE255Z01019",
  "face_value": 1000.0
 },
 {
  "symbol": "EARNHEALTH",
  "company_name": "EARNEST HEALTHCARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE071901016",
  "face_value": 1000.0
 },
 {
  "symbol": "EASEMYTRIP",
  "company_name": "EASY TRIP PLANNERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE07O001026",
  "face_value": 100.0
 },
 {
  "symbol": "EASTMINING",
  "company_name": "EASTERN MINING & ALL. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE072701019",
  "face_value": 1000.0
 },
 {
  "symbol": "EASTOVERSE",
  "company_name": "EASTERN OVERSEAS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE072801017",
  "face_value": 1000.0
 },
 {
  "symbol": "EASTSILK",
  "company_name": "EASTERN SILK INDUSTRIES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE962C01035",
  "face_value": 200.0
 },
 {
  "symbol": "EASUNREYRL",
  "company_name": "EASUN REYROLLE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE268C01029",
  "face_value": 200.0
 },
 {
  "symbol": "EBANK",
  "company_name": "EDELWEISS ETF-NIFTY BANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01EL1",
  "face_value": 1000.0
 },
 {
  "symbol": "EBANKINAV",
  "company_name": "EBANK INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000064",
  "face_value": 100.0
 },
 {
  "symbol": "EBANKNIFTY",
  "company_name": "EDELAMC - EBANKNIFTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01TE4",
  "face_value": 1000.0
 },
 {
  "symbol": "EBB433INAV",
  "company_name": "EDELAMC - EBB433INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000171",
  "face_value": 100000.0
 },
 {
  "symbol": "EBBE23INAV",
  "company_name": "EBBETF0423 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000065",
  "face_value": 100.0
 },
 {
  "symbol": "EBBE30INAV",
  "company_name": "EBBETF0430 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000066",
  "face_value": 100.0
 },
 {
  "symbol": "EBBE31INAV",
  "company_name": "EBBETF0425 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000067",
  "face_value": 100.0
 },
 {
  "symbol": "EBBE32INAV",
  "company_name": "EBBETF0431 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000068",
  "face_value": 100.0
 },
 {
  "symbol": "EBBETF0423",
  "company_name": "EDELAMC - EBBETF0423",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01KN4",
  "face_value": 100000.0
 },
 {
  "symbol": "EBBETF0425",
  "company_name": "EDELAMC - EBBETF0425",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01LD3",
  "face_value": 100000.0
 },
 {
  "symbol": "EBBETF0430",
  "company_name": "EDELAMC - EBBETF0430",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01KO2",
  "face_value": 100000.0
 },
 {
  "symbol": "EBBETF0431",
  "company_name": "EDELAMC - EBBETF0431",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01LE1",
  "face_value": 100000.0
 },
 {
  "symbol": "EBBETF0433",
  "company_name": "EDELAMC - EBBETF0433",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01QX0",
  "face_value": 100000.0
 },
 {
  "symbol": "EBGNG",
  "company_name": "GNG ELECTRONICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE18JU01028",
  "face_value": 200.0
 },
 {
  "symbol": "EBNKNFINAV",
  "company_name": "EDELAMC - EBNKNFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000241",
  "face_value": 1000.0
 },
 {
  "symbol": "ECAPININAV",
  "company_name": "EDELAMC - ECAPININAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000253",
  "face_value": 1000.0
 },
 {
  "symbol": "ECAPINSURE",
  "company_name": "EDELAMC - ECAPINSURE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01TX4",
  "face_value": 1000.0
 },
 {
  "symbol": "ECLERX",
  "company_name": "ECLERX SERVICES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE738I01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ECOSMOBLTY",
  "company_name": "ECOS (INDIA) MOB & HOSP L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE06HJ01020",
  "face_value": 200.0
 },
 {
  "symbol": "EDELWEISS",
  "company_name": "EDELWEISS FIN SERV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE532F01054",
  "face_value": 100.0
 },
 {
  "symbol": "EDL",
  "company_name": "EMPEE DISTI. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE180G01019",
  "face_value": 1000.0
 },
 {
  "symbol": "EDUCOMP",
  "company_name": "EDUCOMP SOLUTIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE216H01027",
  "face_value": 200.0
 },
 {
  "symbol": "EFCIL",
  "company_name": "EFC (I) LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE886D01026",
  "face_value": 200.0
 },
 {
  "symbol": "EGOLD",
  "company_name": "EDELAMC - EGOLD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01SE6",
  "face_value": 1000.0
 },
 {
  "symbol": "EGOLDINAV",
  "company_name": "EDELAMC - EGOLDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000204",
  "face_value": 1000.0
 },
 {
  "symbol": "EICHERMOT",
  "company_name": "EICHER MOTORS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE066A01021",
  "face_value": 100.0
 },
 {
  "symbol": "EIDPARRY",
  "company_name": "EID PARRY INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE126A01031",
  "face_value": 100.0
 },
 {
  "symbol": "EIEL",
  "company_name": "ENVIRO INFRA ENGINEERS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0LLY01014",
  "face_value": 1000.0
 },
 {
  "symbol": "EIFFL",
  "company_name": "EURO (I) FRESH FOODS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE546V01010",
  "face_value": 1000.0
 },
 {
  "symbol": "EIH-RE",
  "company_name": "EIH LIMITED RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE230A20015",
  "face_value": 200.0
 },
 {
  "symbol": "EIHAHOTELS",
  "company_name": "EIH ASSOCIATED HOTELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE276C01014",
  "face_value": 1000.0
 },
 {
  "symbol": "EIHOTEL",
  "company_name": "EIH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE230A01023",
  "face_value": 200.0
 },
 {
  "symbol": "EIMCOELECO",
  "company_name": "EIMCO ELECON (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE158B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "EKC",
  "company_name": "EVEREST KANTO CYLINDERLTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE184H01027",
  "face_value": 200.0
 },
 {
  "symbol": "ELANTAS",
  "company_name": "ELANTAS BECK INDIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE280B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ELBEE",
  "company_name": "ELBEE SERVICES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE030B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ELCIDIN",
  "company_name": "ELCID INVESTMENTS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE927X01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ELDEHSG",
  "company_name": "ELDECO HSG & IND LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE668G01021",
  "face_value": 200.0
 },
 {
  "symbol": "ELECON",
  "company_name": "ELECON ENG. CO. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE205B01031",
  "face_value": 100.0
 },
 {
  "symbol": "ELECONENGG",
  "company_name": "ELECON ENGINEERING CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE205B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "ELECTCAST",
  "company_name": "ELECTROSTEEL CASTINGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE086A01029",
  "face_value": 100.0
 },
 {
  "symbol": "ELECTHERM",
  "company_name": "ELECTROTHERM (I) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE822G01016",
  "face_value": 1000.0
 },
 {
  "symbol": "ELECTRA",
  "company_name": "ELECTRA (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE075101019",
  "face_value": 1000.0
 },
 {
  "symbol": "ELECTRX",
  "company_name": "ELECTREX (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE075301015",
  "face_value": 1000.0
 },
 {
  "symbol": "ELGIEQUIP",
  "company_name": "ELGI EQUIPMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE285A01027",
  "face_value": 100.0
 },
 {
  "symbol": "ELGIRUBCO",
  "company_name": "ELGI RUBBER CO. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE819L01012",
  "face_value": 100.0
 },
 {
  "symbol": "ELIN",
  "company_name": "ELIN ELECTRONICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE050401020",
  "face_value": 500.0
 },
 {
  "symbol": "ELIQUID",
  "company_name": "EDELAMC - ELIQUID",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01VW2",
  "face_value": 100000.0
 },
 {
  "symbol": "ELIQUIINAV",
  "company_name": "EDELAMC - ELIQUIINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000302",
  "face_value": 100000.0
 },
 {
  "symbol": "ELITECON",
  "company_name": "ELITECON INTERNATIONAL L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE669R01026",
  "face_value": 100.0
 },
 {
  "symbol": "ELLEN",
  "company_name": "ELLENBARRIE INDUS GASES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE236E01022",
  "face_value": 200.0
 },
 {
  "symbol": "ELM250",
  "company_name": "EDELAMC - ELM250",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01VV4",
  "face_value": 1000.0
 },
 {
  "symbol": "ELM250INAV",
  "company_name": "EDELAMC - ELM250INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000298",
  "face_value": 1000.0
 },
 {
  "symbol": "ELNET",
  "company_name": "ELNET TECH. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE033C01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ELPROINTL",
  "company_name": "ELPRO INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE579B01039",
  "face_value": 100.0
 },
 {
  "symbol": "EMAMILTD",
  "company_name": "EMAMI LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE548C01032",
  "face_value": 100.0
 },
 {
  "symbol": "EMAMIPAP",
  "company_name": "EMAMI PAPER MILLS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE830C01026",
  "face_value": 200.0
 },
 {
  "symbol": "EMAMIREAL",
  "company_name": "EMAMI REALTY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE778K01012",
  "face_value": 200.0
 },
 {
  "symbol": "EMBDL",
  "company_name": "EMBASSY DEVELOPMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE069I01010",
  "face_value": 200.0
 },
 {
  "symbol": "EMCO",
  "company_name": "EMCO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE078A01026",
  "face_value": 200.0
 },
 {
  "symbol": "EMCOTRANS",
  "company_name": "EMCO LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE078A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "EMCURE",
  "company_name": "EMCURE PHARMACEUTICALS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE168P01015",
  "face_value": 1000.0
 },
 {
  "symbol": "EMIL",
  "company_name": "ELECTRONICS MART IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02YR01019",
  "face_value": 1000.0
 },
 {
  "symbol": "EMKAY",
  "company_name": "EMKAY GLOBAL FIN SERV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE296H01011",
  "face_value": 1000.0
 },
 {
  "symbol": "EMLTMQINAV",
  "company_name": "EDELAMC - EMLTMQINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000250",
  "face_value": 1000.0
 },
 {
  "symbol": "EMMBI",
  "company_name": "EMMBI INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE753K01015",
  "face_value": 1000.0
 },
 {
  "symbol": "EMMVEE",
  "company_name": "EMMVEE PHOTOVOLTAIC PWR L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1C6T01020",
  "face_value": 200.0
 },
 {
  "symbol": "EMPEESUG",
  "company_name": "EMPEE SUGAR AND CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE928B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "EMPEESUGAR",
  "company_name": "EMPEE SUGARS AND CHEMICAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE077601016",
  "face_value": 1000.0
 },
 {
  "symbol": "EMPOWER",
  "company_name": "EMPOWER INDIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE507F01023",
  "face_value": 100.0
 },
 {
  "symbol": "EMSLIMITED",
  "company_name": "EMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0OV601013",
  "face_value": 1000.0
 },
 {
  "symbol": "EMUDHRA",
  "company_name": "EMUDHRA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01QM01018",
  "face_value": 500.0
 },
 {
  "symbol": "EMULTIMQ",
  "company_name": "EDELAMC - EMULTIMQ",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01TF1",
  "face_value": 1000.0
 },
 {
  "symbol": "ENARAIFIN",
  "company_name": "ENARAI FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE078001018",
  "face_value": 1000.0
 },
 {
  "symbol": "ENDURANCE",
  "company_name": "ENDURANCE TECHNO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE913H01037",
  "face_value": 1000.0
 },
 {
  "symbol": "ENERGY",
  "company_name": "MIRAEAMC - ENERGY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01PR2",
  "face_value": 1000.0
 },
 {
  "symbol": "ENERGYDEV",
  "company_name": "ENERGY DEVE. CO.LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE306C01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ENERGYINAV",
  "company_name": "MIRAEAMC - ENERGYINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000310",
  "face_value": 1000.0
 },
 {
  "symbol": "ENGINERSIN",
  "company_name": "ENGINEERS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE510A01028",
  "face_value": 500.0
 },
 {
  "symbol": "ENIFTY",
  "company_name": "EDELAMC - ENIFTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01VX0",
  "face_value": 1000.0
 },
 {
  "symbol": "ENIFTYINAV",
  "company_name": "EDELAMC - ENIFTYINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000318",
  "face_value": 1000.0
 },
 {
  "symbol": "ENIL",
  "company_name": "ENTERTAIN NET. IND. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE265F01028",
  "face_value": 1000.0
 },
 {
  "symbol": "ENOREFONRY",
  "company_name": "ENNORE FOUNDRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE078601015",
  "face_value": 1000.0
 },
 {
  "symbol": "ENRIN",
  "company_name": "SIEMENS ENERGY INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1NPP01017",
  "face_value": 200.0
 },
 {
  "symbol": "ENTERO",
  "company_name": "ENTERO HEALTHCARE SOLU L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE010601016",
  "face_value": 1000.0
 },
 {
  "symbol": "EON",
  "company_name": "EON ELECTRIC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE076H01025",
  "face_value": 500.0
 },
 {
  "symbol": "EPACK",
  "company_name": "EPACK DURABLE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0G5901015",
  "face_value": 1000.0
 },
 {
  "symbol": "EPACKPEB",
  "company_name": "EPACK PREFAB TECHN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0MLS01022",
  "face_value": 200.0
 },
 {
  "symbol": "EPIGRAL",
  "company_name": "EPIGRAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE071N01016",
  "face_value": 1000.0
 },
 {
  "symbol": "EPL",
  "company_name": "EPL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE255A01020",
  "face_value": 200.0
 },
 {
  "symbol": "EQ30",
  "company_name": "EDEL ETF NIFTY 100 QUAL30",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01EM9",
  "face_value": 1000.0
 },
 {
  "symbol": "EQU200INAV",
  "company_name": "MIRAEAMC - EQU200INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000264",
  "face_value": 1000.0
 },
 {
  "symbol": "EQUA50INAV",
  "company_name": "MIRAEAMC - EQUA50INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000276",
  "face_value": 1000.0
 },
 {
  "symbol": "EQUAL200",
  "company_name": "MIRAEAMC - EQUAL200",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01OA1",
  "face_value": 1000.0
 },
 {
  "symbol": "EQUAL50",
  "company_name": "MIRAEAMC - EQUAL50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01OO2",
  "face_value": 1000.0
 },
 {
  "symbol": "EQUAL50ADD",
  "company_name": "DSPAMC - DSPNEWETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1QK2",
  "face_value": 1000.0
 },
 {
  "symbol": "EQUIPPP",
  "company_name": "EQUIPPP SOC IMP TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE217G01035",
  "face_value": 100.0
 },
 {
  "symbol": "EQUITAS",
  "company_name": "EQUITAS HOLDINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE988K01017",
  "face_value": 1000.0
 },
 {
  "symbol": "EQUITASBNK",
  "company_name": "EQUITAS SMALL FIN BNK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE063P01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ERIS",
  "company_name": "ERIS LIFESCIENCES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE406M01024",
  "face_value": 100.0
 },
 {
  "symbol": "EROSMEDIA",
  "company_name": "EROS INTL MEDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE416L01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ESABINDIA",
  "company_name": "ESAB INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE284A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "ESAFSFB",
  "company_name": "ESAF SMALL FINANCE BANK L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE818W01011",
  "face_value": 1000.0
 },
 {
  "symbol": "ESCORTS",
  "company_name": "ESCORTS KUBOTA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE042A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "ESCORTSFIN",
  "company_name": "ESCORTS FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE359A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "ESENSEINAV",
  "company_name": "EDELAMC - ESENSEINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000317",
  "face_value": 1000.0
 },
 {
  "symbol": "ESENSEX",
  "company_name": "EDELAMC - ESENSEX",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01VY8",
  "face_value": 1000.0
 },
 {
  "symbol": "ESG",
  "company_name": "MIRAEAMC - MAESGETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01GS9",
  "face_value": 1750.0
 },
 {
  "symbol": "ESILINAV",
  "company_name": "EDELAMC - ESILVER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000205",
  "face_value": 1000.0
 },
 {
  "symbol": "ESILVER",
  "company_name": "EDELAMC - ESILVER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01SF3",
  "face_value": 1000.0
 },
 {
  "symbol": "ESL",
  "company_name": "ELECTROSTEEL STEELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE481K01013",
  "face_value": 1000.0
 },
 {
  "symbol": "ESSARPORTS",
  "company_name": "ESSAR PORTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE282A01024",
  "face_value": 1000.0
 },
 {
  "symbol": "ESSARSHPNG",
  "company_name": "ESSAR SHIPPING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE122M01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ESSDEE",
  "company_name": "ESS DEE ALUM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE825H01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ESSEN-RE",
  "company_name": "INTEGRA ESSENTIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE418N20019",
  "face_value": 100.0
 },
 {
  "symbol": "ESSEN-RE1",
  "company_name": "INTEGRA ESSENTIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE418N20027",
  "face_value": 100.0
 },
 {
  "symbol": "ESSEN-RE2",
  "company_name": "INTEGRA ESSENTIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE418N20035",
  "face_value": 100.0
 },
 {
  "symbol": "ESSENTIA",
  "company_name": "INTEGRA ESSENTIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE418N01035",
  "face_value": 100.0
 },
 {
  "symbol": "ESTCSTSTEL",
  "company_name": "EAST COAST STEEL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE072001014",
  "face_value": 1000.0
 },
 {
  "symbol": "ESTER",
  "company_name": "ESTER INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE778B01029",
  "face_value": 500.0
 },
 {
  "symbol": "ESTERIND",
  "company_name": "ESTER INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE080101012",
  "face_value": 1000.0
 },
 {
  "symbol": "ESTWSTRAV",
  "company_name": "EAST WEST TRAVEL & TRADE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE072401016",
  "face_value": 1000.0
 },
 {
  "symbol": "ETERNAL",
  "company_name": "ETERNAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE758T01015",
  "face_value": 100.0
 },
 {
  "symbol": "ETHOS-RE",
  "company_name": "ETHOS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE04TZ20018",
  "face_value": 1000.0
 },
 {
  "symbol": "ETHOSLTD",
  "company_name": "ETHOS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE04TZ01018",
  "face_value": 1000.0
 },
 {
  "symbol": "EUPHARMLAB",
  "company_name": "EUPHARMA LABS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE909A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "EUREKAFORB",
  "company_name": "EUREKA FORBES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0KCE01017",
  "face_value": 1000.0
 },
 {
  "symbol": "EUROBOND",
  "company_name": "EURO PANEL PRODUCTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE505V01016",
  "face_value": 1000.0
 },
 {
  "symbol": "EUROCERA",
  "company_name": "EURO CERAMICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE649H01011",
  "face_value": 1000.0
 },
 {
  "symbol": "EUROMULTI",
  "company_name": "EURO MULTIVISION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE063J01011",
  "face_value": 1000.0
 },
 {
  "symbol": "EUROPRATIK",
  "company_name": "EURO PRATIK SALES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE198501012",
  "face_value": 100.0
 },
 {
  "symbol": "EUROTEXIND",
  "company_name": "EUROTEX INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE022C01012",
  "face_value": 1000.0
 },
 {
  "symbol": "EVEREADY",
  "company_name": "EVEREADY INDS. IND.  LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE128A01029",
  "face_value": 500.0
 },
 {
  "symbol": "EVERESTIND",
  "company_name": "EVEREST INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE295A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "EVIETF",
  "company_name": "ICICIPRAMC - EVIETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109K1A153",
  "face_value": 1000.0
 },
 {
  "symbol": "EVIETFINAV",
  "company_name": "ICICIPRAMC - EVIETFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000272",
  "face_value": 1000.0
 },
 {
  "symbol": "EVINDIA",
  "company_name": "MIRAEAMC - EVINDIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01LQ3",
  "face_value": 1000.0
 },
 {
  "symbol": "EVINDINAV",
  "company_name": "MIRAEAMC - EVINDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000232",
  "face_value": 1000.0
 },
 {
  "symbol": "EXCELINDUS",
  "company_name": "EXCEL INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE369A01029",
  "face_value": 500.0
 },
 {
  "symbol": "EXCELSOFT",
  "company_name": "EXCELSOFT TECHNOLOGIES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE606N01019",
  "face_value": 1000.0
 },
 {
  "symbol": "EXICOM",
  "company_name": "EXICOM TELE SYSTEMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE777F01014",
  "face_value": 1000.0
 },
 {
  "symbol": "EXICOM-RE",
  "company_name": "EXICOM TELE-SYSTEMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE777F20014",
  "face_value": 1000.0
 },
 {
  "symbol": "EXIDEIND",
  "company_name": "EXIDE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE302A01020",
  "face_value": 100.0
 },
 {
  "symbol": "EXPLEOSOL",
  "company_name": "EXPLEO SOLUTIONS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE201K01015",
  "face_value": 1000.0
 },
 {
  "symbol": "EXXARO",
  "company_name": "EXXARO TILES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0GFE01026",
  "face_value": 100.0
 },
 {
  "symbol": "FABTECH",
  "company_name": "FABTECH TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0HF201011",
  "face_value": 1000.0
 },
 {
  "symbol": "FACT",
  "company_name": "FACT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE188A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "FAIRCHEMOR",
  "company_name": "FAIRCHEM ORGANICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0DNW01011",
  "face_value": 1000.0
 },
 {
  "symbol": "FALCONTYRE",
  "company_name": "FALCON TYRES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE511B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "FASTCAP",
  "company_name": "FAST CAPITAL GROWTH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE547101019",
  "face_value": 1000.0
 },
 {
  "symbol": "FAZE3Q",
  "company_name": "FAZE THREE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE963C01033",
  "face_value": 1000.0
 },
 {
  "symbol": "FAZETHREE",
  "company_name": "FAZE THREE EXPORTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE450401018",
  "face_value": 1000.0
 },
 {
  "symbol": "FCL",
  "company_name": "FINEOTEX CHEMICAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE045J01034",
  "face_value": 100.0
 },
 {
  "symbol": "FCONSUMER",
  "company_name": "FUTURE CONSUMER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE220J01025",
  "face_value": 600.0
 },
 {
  "symbol": "FCSSOFT",
  "company_name": "FCS SOFTWARE SOLN. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE512B01022",
  "face_value": 100.0
 },
 {
  "symbol": "FDC",
  "company_name": "FDC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE258B01022",
  "face_value": 100.0
 },
 {
  "symbol": "FEDDERELEC",
  "company_name": "FEDDERS ELECTRIC & ENG LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE249C01011",
  "face_value": 1000.0
 },
 {
  "symbol": "FEDDERSHOL",
  "company_name": "FEDDERS HOLDING LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE417D01020",
  "face_value": 100.0
 },
 {
  "symbol": "FEDERALBNK",
  "company_name": "FEDERAL BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE171A01029",
  "face_value": 200.0
 },
 {
  "symbol": "FEDFINA",
  "company_name": "FEDBANK FINANCIAL SER L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE007N01010",
  "face_value": 1000.0
 },
 {
  "symbol": "FEL",
  "company_name": "FUTURE ENTERPRISES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE623B01027",
  "face_value": 200.0
 },
 {
  "symbol": "FELDVR",
  "company_name": "FUTURE ENTERPRISES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "IN9623B01058",
  "face_value": 200.0
 },
 {
  "symbol": "FEMNORMIN",
  "company_name": "FEMNOR MINERAL (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE082201018",
  "face_value": 1000.0
 },
 {
  "symbol": "FERMENTA",
  "company_name": "FERMENTA BIOTECH LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE225B01021",
  "face_value": 500.0
 },
 {
  "symbol": "FERROALLOY",
  "company_name": "FERRO ALLOYS CORPORATION",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE082401014",
  "face_value": 1000.0
 },
 {
  "symbol": "FGPIND",
  "company_name": "FGP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE456101018",
  "face_value": 1000.0
 },
 {
  "symbol": "FIBERWEB",
  "company_name": "FIBERWEB INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE296C01020",
  "face_value": 1000.0
 },
 {
  "symbol": "FICOMORGAN",
  "company_name": "FICOM ORGANICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE082701017",
  "face_value": 1000.0
 },
 {
  "symbol": "FIEMIND",
  "company_name": "FIEM INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE737H01014",
  "face_value": 1000.0
 },
 {
  "symbol": "FILATEX",
  "company_name": "FILATEX INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE816B01035",
  "face_value": 100.0
 },
 {
  "symbol": "FILATFASH",
  "company_name": "FILATEX FASHIONS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE185E01021",
  "face_value": 100.0
 },
 {
  "symbol": "FINCABLES",
  "company_name": "FINOLEX CABLES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE235A01022",
  "face_value": 200.0
 },
 {
  "symbol": "FINEORG",
  "company_name": "FINE ORGANIC IND. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE686Y01026",
  "face_value": 500.0
 },
 {
  "symbol": "FINIETF",
  "company_name": "ICICIPRAMC-ICICIFIN",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC17L8",
  "face_value": 1000.0
 },
 {
  "symbol": "FINKURVE",
  "company_name": "FINKURVE FINANCIAL SERV L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE734I01027",
  "face_value": 100.0
 },
 {
  "symbol": "FINOPB",
  "company_name": "FINO PAYMENTS BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02NC01014",
  "face_value": 1000.0
 },
 {
  "symbol": "FINPIPE",
  "company_name": "FINOLEX INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE183A01024",
  "face_value": 200.0
 },
 {
  "symbol": "FIRSTCRY",
  "company_name": "BRAINBEES SOLUTIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02RE01045",
  "face_value": 200.0
 },
 {
  "symbol": "FISCHER",
  "company_name": "FISCHER MEDICAL VENTURE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE771F01041",
  "face_value": 100.0
 },
 {
  "symbol": "FISHFALCON",
  "company_name": "FISHING FALCONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE084301014",
  "face_value": 1000.0
 },
 {
  "symbol": "FIVESTAR",
  "company_name": "FIVE-STAR BUS FIN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE128S01021",
  "face_value": 100.0
 },
 {
  "symbol": "FLAIR",
  "company_name": "FLAIR WRITING INDUST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00Y201027",
  "face_value": 500.0
 },
 {
  "symbol": "FLATPROD",
  "company_name": "FLAT PRODUCTS EQUIPMENT (",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYY000006",
  "face_value": 1000.0
 },
 {
  "symbol": "FLEXIADD",
  "company_name": "DSPAMC - FLEXIADD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1WU9",
  "face_value": 1000.0
 },
 {
  "symbol": "FLEXIAINAV",
  "company_name": "DSPAMC - FLEXIAINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000303",
  "face_value": 1000.0
 },
 {
  "symbol": "FLEXITUFF",
  "company_name": "FLEXITUFF VENTURES INT L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE060J01017",
  "face_value": 1000.0
 },
 {
  "symbol": "FLFL",
  "company_name": "FUT LIFESTYLE FASH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE452O01016",
  "face_value": 200.0
 },
 {
  "symbol": "FLUOROCHEM",
  "company_name": "GUJARAT FLUOROCHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE09N301011",
  "face_value": 100.0
 },
 {
  "symbol": "FMCGIETF",
  "company_name": "ICICIPRAMC - ICICIFMCG",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC19V3",
  "face_value": 100.0
 },
 {
  "symbol": "FMGOETZE",
  "company_name": "FEDERAL-MOGUL GOETZE (IND",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE529A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "FMNL",
  "company_name": "FUTURE MKT NETWORKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE360L01017",
  "face_value": 1000.0
 },
 {
  "symbol": "FOCUS",
  "company_name": "FOCUS LIGHTG & FIXTRS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE593W01028",
  "face_value": 200.0
 },
 {
  "symbol": "FOODSIN",
  "company_name": "FOODS & INNS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE976E01023",
  "face_value": 100.0
 },
 {
  "symbol": "FORBESGOK",
  "company_name": "FORBES GOKAK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE518A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "FORCEMOT",
  "company_name": "FORCE MOTORS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE451A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "FORTIS",
  "company_name": "FORTIS HEALTHCARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE061F01013",
  "face_value": 1000.0
 },
 {
  "symbol": "FORTISFIN",
  "company_name": "FORTIS FINANCIAL SERVICES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE991C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "FOSECOIND",
  "company_name": "FOSECO INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE519A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "FRACTAL",
  "company_name": "FRACTAL ANALYTICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE212S01015",
  "face_value": 100.0
 },
 {
  "symbol": "FRETAIL",
  "company_name": "FUTURE RETAIL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE752P01024",
  "face_value": 200.0
 },
 {
  "symbol": "FRONTSP",
  "company_name": "FRONTIER SPRINGS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE572D01014",
  "face_value": 1000.0
 },
 {
  "symbol": "FSC",
  "company_name": "FUTURE SUPP CHAIN SOL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE935Q01015",
  "face_value": 1000.0
 },
 {
  "symbol": "FSL",
  "company_name": "FIRSTSOURCE SOLU. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE684F01012",
  "face_value": 1000.0
 },
 {
  "symbol": "FULFORD",
  "company_name": "FULFORD (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE521A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "FUSI-RE",
  "company_name": "FUSION FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE139R20012",
  "face_value": 1000.0
 },
 {
  "symbol": "FUSION",
  "company_name": "FUSION FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE139R01012",
  "face_value": 1000.0
 },
 {
  "symbol": "G1NSETEST",
  "company_name": "G1NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN002",
  "face_value": 1000.0
 },
 {
  "symbol": "GABRIEL",
  "company_name": "GABRIEL INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE524A01029",
  "face_value": 100.0
 },
 {
  "symbol": "GACMDVR-RE",
  "company_name": "GACM TECHNOLOGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE224E20028",
  "face_value": 100.0
 },
 {
  "symbol": "GAEL",
  "company_name": "GUJARAT AMBUJA EXPORTS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE036B01030",
  "face_value": 100.0
 },
 {
  "symbol": "GAIL",
  "company_name": "GAIL (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE129A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "GAL-RE",
  "company_name": "GYSCOAL ALLOYS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE482J20013",
  "face_value": 100.0
 },
 {
  "symbol": "GALAPREC",
  "company_name": "GALA PRECISION ENG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0RE001014",
  "face_value": 1000.0
 },
 {
  "symbol": "GALAXYSURF",
  "company_name": "GALAXY SURFACTANTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE600K01018",
  "face_value": 1000.0
 },
 {
  "symbol": "GALLANTT",
  "company_name": "GALLANTT ISPAT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE297H01019",
  "face_value": 1000.0
 },
 {
  "symbol": "GALLISPAT",
  "company_name": "GALLANTT ISPAT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE528K01029",
  "face_value": 100.0
 },
 {
  "symbol": "GALPOWTEL",
  "company_name": "GALADA POWER & TELECOM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE255C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "GAMMONIND",
  "company_name": "GAMMON INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE259B01020",
  "face_value": 200.0
 },
 {
  "symbol": "GANDHAR",
  "company_name": "GANDHAR OIL REFINE IND L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE717W01049",
  "face_value": 200.0
 },
 {
  "symbol": "GANDHITUBE",
  "company_name": "GANDHI SPL. TUBES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE524B01027",
  "face_value": 500.0
 },
 {
  "symbol": "GANECOS",
  "company_name": "GANESHA ECOSPHERE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE845D01014",
  "face_value": 1000.0
 },
 {
  "symbol": "GANESHANHY",
  "company_name": "GANESH ANYHDRIDE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE418A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "GANESHBE",
  "company_name": "GANESH BENZOPLAST LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE388A01029",
  "face_value": 100.0
 },
 {
  "symbol": "GANESHBENZ",
  "company_name": "GANESH BENZOPLAST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE388A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "GANESHCP",
  "company_name": "GANESH CONSUMER PRODUCT L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE652V01016",
  "face_value": 1000.0
 },
 {
  "symbol": "GANESHHOU",
  "company_name": "GANESH HOUSING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE460C01014",
  "face_value": 1000.0
 },
 {
  "symbol": "GANGAFORGE",
  "company_name": "GANGA FORGING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE691Z01023",
  "face_value": 100.0
 },
 {
  "symbol": "GANGESSECU",
  "company_name": "GANGES SECURITIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE335W01016",
  "face_value": 1000.0
 },
 {
  "symbol": "GANGOTEX",
  "company_name": "GANGOTRI TEXTILES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE548101018",
  "face_value": 1000.0
 },
 {
  "symbol": "GANGOTRI",
  "company_name": "GANGOTRI TEXTILES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE670B01028",
  "face_value": 500.0
 },
 {
  "symbol": "GANHSGFIN",
  "company_name": "GANESH HOUSING FIN CORP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE460C01014",
  "face_value": 1000.0
 },
 {
  "symbol": "GARDENSILK",
  "company_name": "GARDEN SILK MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE526A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "GARFIBRES",
  "company_name": "GARWARE TECH FIBRES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE276A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "GARUDA",
  "company_name": "GARUDA CONSTRUCT N ENG L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0JVO01026",
  "face_value": 500.0
 },
 {
  "symbol": "GARWARPOLY",
  "company_name": "GARWARE POLYESTER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE291A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "GARWARSHIP",
  "company_name": "GARWARE SHIPPING CORP. LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE091701016",
  "face_value": 1000.0
 },
 {
  "symbol": "GATDVR-RE",
  "company_name": "GACM TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE224E20044",
  "face_value": 100.0
 },
 {
  "symbol": "GATECH",
  "company_name": "GACM TECHNOLOGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE224E01028",
  "face_value": 100.0
 },
 {
  "symbol": "GATECH-RE",
  "company_name": "GACM TECHNOLOGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE224E20010",
  "face_value": 100.0
 },
 {
  "symbol": "GATECH-RE1",
  "company_name": "GACM TECHNO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE224E20036",
  "face_value": 100.0
 },
 {
  "symbol": "GATECHDVR",
  "company_name": "GACM TECHNOLOGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE224E01036",
  "face_value": 100.0
 },
 {
  "symbol": "GATEWAY",
  "company_name": "GATEWAY DISTRIPARKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE079J01017",
  "face_value": 1000.0
 },
 {
  "symbol": "GAUDIUMIVF",
  "company_name": "GAUDIUM IVF N WOMEN H L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0P8B01020",
  "face_value": 500.0
 },
 {
  "symbol": "GAYAHWS",
  "company_name": "GAYATRI HIGHWAYS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE287Z01012",
  "face_value": 200.0
 },
 {
  "symbol": "GAYAPROJ",
  "company_name": "GAYATRI PROJECTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE336H01023",
  "face_value": 200.0
 },
 {
  "symbol": "GBGLOBAL",
  "company_name": "GB GLOBAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE087J01028",
  "face_value": 1000.0
 },
 {
  "symbol": "GCSL",
  "company_name": "GRETEX CORPORATE SERVICES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE199P01028",
  "face_value": 1000.0
 },
 {
  "symbol": "GDL",
  "company_name": "GATEWAY DISTRIPARKS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE852F01015",
  "face_value": 1000.0
 },
 {
  "symbol": "GDL-RE",
  "company_name": "GATEWAY DISTRIPARKS RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE852F20015",
  "face_value": 1000.0
 },
 {
  "symbol": "GECALSTHOM",
  "company_name": "ALSTOM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE200A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "GEECEE",
  "company_name": "GEECEE VENTURES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE916G01016",
  "face_value": 1000.0
 },
 {
  "symbol": "GEEKAYEXIM",
  "company_name": "GEEKAY EXIM (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE451601012",
  "face_value": 1000.0
 },
 {
  "symbol": "GEEKAYWIRE",
  "company_name": "GEEKAY WIRES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE669X01032",
  "face_value": 100.0
 },
 {
  "symbol": "GEMAROMA",
  "company_name": "GEM AROMATICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE06XZ01023",
  "face_value": 200.0
 },
 {
  "symbol": "GEMSPIN",
  "company_name": "GEM SPINNERS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE092501019",
  "face_value": 1000.0
 },
 {
  "symbol": "GENCON",
  "company_name": "GENERIC ENG CONS PROJ LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE854S01022",
  "face_value": 500.0
 },
 {
  "symbol": "GENESYS",
  "company_name": "GENESYS INTL CORPN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE727B01026",
  "face_value": 500.0
 },
 {
  "symbol": "GENSOL",
  "company_name": "GENSOL ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE06H201014",
  "face_value": 1000.0
 },
 {
  "symbol": "GENUSPAPER",
  "company_name": "GENUS P&B LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE949P01018",
  "face_value": 100.0
 },
 {
  "symbol": "GENUSPOWER",
  "company_name": "GENUS POWER INFRASTRU LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE955D01029",
  "face_value": 100.0
 },
 {
  "symbol": "GEOJIT-RE",
  "company_name": "GEOJIT FIN SERV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE007B20015",
  "face_value": 100.0
 },
 {
  "symbol": "GEOJITFSL",
  "company_name": "GEOJIT FINANCIAL SER L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE007B01023",
  "face_value": 100.0
 },
 {
  "symbol": "GEORGFISCH",
  "company_name": "GEORG FISCHER DISA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYY000001",
  "face_value": 1000.0
 },
 {
  "symbol": "GESHIP",
  "company_name": "THE GE SHPG.LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE017A01032",
  "face_value": 1000.0
 },
 {
  "symbol": "GESTETNER",
  "company_name": "GESTETNER (INDIAI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE223C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "GFLLIMITED",
  "company_name": "GFL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE538A01037",
  "face_value": 100.0
 },
 {
  "symbol": "GFSTEELS",
  "company_name": "GRAND FOUNDRY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE534A01028",
  "face_value": 400.0
 },
 {
  "symbol": "GHCL",
  "company_name": "GHCL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE539A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "GHCLTEXTIL",
  "company_name": "GHCL TEXTILES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0PA801013",
  "face_value": 200.0
 },
 {
  "symbol": "GHOSPIINAV",
  "company_name": "GROWWAMC - GHOSPIINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000340",
  "face_value": 1000.0
 },
 {
  "symbol": "GICBAL",
  "company_name": "GIC BALANCED FUND",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE451001015",
  "face_value": 1000.0
 },
 {
  "symbol": "GICHSGFIN",
  "company_name": "GIC HOUSING FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE289B01019",
  "face_value": 1000.0
 },
 {
  "symbol": "GICL",
  "company_name": "GLOBE INTL CARRIERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE947T01022",
  "face_value": 500.0
 },
 {
  "symbol": "GICRE",
  "company_name": "GENERAL INS CORP OF INDIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE481Y01014",
  "face_value": 500.0
 },
 {
  "symbol": "GILLANDERS",
  "company_name": "GILLANDERS ARBUTHNOT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE047B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "GILLETTE",
  "company_name": "GILLETTE INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE322A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "GILT10BETA",
  "company_name": "UTIAMC-GILT10BETA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF789F1AZF3",
  "face_value": 1000.0
 },
 {
  "symbol": "GILT5BETA",
  "company_name": "UTIAMC-GILT5BETA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF789F1AZE6",
  "face_value": 1000.0
 },
 {
  "symbol": "GILT5YBEES",
  "company_name": "RELCAPAMC - NETFGILT5Y",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KC1030",
  "face_value": 1000.0
 },
 {
  "symbol": "GILT5YINAV",
  "company_name": "GILT5YBEES INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000130",
  "face_value": 100.0
 },
 {
  "symbol": "GINNIFILA",
  "company_name": "GINNI FILAMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE424C01010",
  "face_value": 1000.0
 },
 {
  "symbol": "GIPCL",
  "company_name": "GUJ IND POW CO. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE162A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "GISO-RE",
  "company_name": "GI ENGINEERING SOLUTIONS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE065J20016",
  "face_value": 1000.0
 },
 {
  "symbol": "GITANJALI",
  "company_name": "GITANJALI GEMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE346H01014",
  "face_value": 1000.0
 },
 {
  "symbol": "GKENERGY",
  "company_name": "GK ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1AG301022",
  "face_value": 200.0
 },
 {
  "symbol": "GKSL",
  "company_name": "GUJARAT KIDNEY N SUP SP L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0V0W01025",
  "face_value": 200.0
 },
 {
  "symbol": "GKWLIMITED",
  "company_name": "GKW LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE528A01020",
  "face_value": 1000.0
 },
 {
  "symbol": "GLAND",
  "company_name": "GLAND PHARMA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE068V01023",
  "face_value": 100.0
 },
 {
  "symbol": "GLAXO",
  "company_name": "GLAXOSMITHKLINE PHARMA LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE159A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "GLD360INAV",
  "company_name": "360ONEAMC - GLD360INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000262",
  "face_value": 1000.0
 },
 {
  "symbol": "GLDCASINAV",
  "company_name": "ZERODHAAMC - GLDCASINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000219",
  "face_value": 1000.0
 },
 {
  "symbol": "GLENMARK",
  "company_name": "GLENMARK PHARMACEUTICALS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE935A01035",
  "face_value": 100.0
 },
 {
  "symbol": "GLFL",
  "company_name": "GUJARAT LEASE FINANCING L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE540A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "GLOBABOARD",
  "company_name": "GLOBAL BOARDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE085D01017",
  "face_value": 1000.0
 },
 {
  "symbol": "GLOBAL",
  "company_name": "GLOBAL EDUCATION LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE291W01037",
  "face_value": 200.0
 },
 {
  "symbol": "GLOBALE",
  "company_name": "GLOBALE TESSILE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0URU01010",
  "face_value": 1000.0
 },
 {
  "symbol": "GLOBALVECT",
  "company_name": "GLOBAL VEC HELICORP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE792H01019",
  "face_value": 1000.0
 },
 {
  "symbol": "GLOBE",
  "company_name": "GLOBE ENTERPRISE (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE581X01021",
  "face_value": 200.0
 },
 {
  "symbol": "GLOBE-RE",
  "company_name": "GLOBE TEXTILES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE581X20013",
  "face_value": 200.0
 },
 {
  "symbol": "GLOBE-RE1",
  "company_name": "GLOBE TEXTILES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE581X20021",
  "face_value": 200.0
 },
 {
  "symbol": "GLOBECIVIL",
  "company_name": "GLOBE CIVIL PROJECTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0V3U01015",
  "face_value": 1000.0
 },
 {
  "symbol": "GLOBOFFS",
  "company_name": "GLOBAL OFFSHORE SERV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE446C01013",
  "face_value": 1000.0
 },
 {
  "symbol": "GLOBUSSPR",
  "company_name": "GLOBUS SPIRITS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE615I01010",
  "face_value": 1000.0
 },
 {
  "symbol": "GLOSTERLTD",
  "company_name": "GLOSTER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE350Z01018",
  "face_value": 1000.0
 },
 {
  "symbol": "GLOTTIS",
  "company_name": "GLOTTIS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0TQE01026",
  "face_value": 200.0
 },
 {
  "symbol": "GMBREW",
  "company_name": "G M BREWERIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE075D01018",
  "face_value": 1000.0
 },
 {
  "symbol": "GMDCLTD",
  "company_name": "GUJARAT MINERAL DEV CORP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE131A01031",
  "face_value": 200.0
 },
 {
  "symbol": "GMMPFAUDLR",
  "company_name": "GMM PFAUDLER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE541A01023",
  "face_value": 200.0
 },
 {
  "symbol": "GMRAIRPORT",
  "company_name": "GMR AIRPORTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE776C01039",
  "face_value": 100.0
 },
 {
  "symbol": "GMRP&UI",
  "company_name": "GMR POW AND URBAN INFRA L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0CU601026",
  "face_value": 500.0
 },
 {
  "symbol": "GMRVASAVI",
  "company_name": "GMR TECHNOLOGIES & INDUST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE353B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "GMSIND",
  "company_name": "G M S INDUSTRIES (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE549201015",
  "face_value": 1000.0
 },
 {
  "symbol": "GNA",
  "company_name": "GNA AXLES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE934S01014",
  "face_value": 1000.0
 },
 {
  "symbol": "GNFC",
  "company_name": "GUJ NAR VAL FER & CHEM L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE113A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "GNRL",
  "company_name": "GUJARAT NATURAL RES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE207H01018",
  "face_value": 1000.0
 },
 {
  "symbol": "GOACARBON",
  "company_name": "GOA CARBON LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE426D01013",
  "face_value": 1000.0
 },
 {
  "symbol": "GOCLCORP",
  "company_name": "GOCL CORPORATION LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE077F01035",
  "face_value": 200.0
 },
 {
  "symbol": "GOCOLORS",
  "company_name": "GO FASHION INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0BJS01011",
  "face_value": 1000.0
 },
 {
  "symbol": "GODAVARIB",
  "company_name": "GODAVARI BIOREFINERIES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE497S01012",
  "face_value": 1000.0
 },
 {
  "symbol": "GODFRYPHLP",
  "company_name": "GODFREY PHILLIPS INDIA LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE260B01028",
  "face_value": 200.0
 },
 {
  "symbol": "GODHA-RE",
  "company_name": "GODHA CABCON INSULAT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE925Y20010",
  "face_value": 100.0
 },
 {
  "symbol": "GODIGIT",
  "company_name": "GO DIGIT GENERAL INS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE03JT01014",
  "face_value": 1000.0
 },
 {
  "symbol": "GODREJAGRO",
  "company_name": "GODREJ AGROVET LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE850D01014",
  "face_value": 1000.0
 },
 {
  "symbol": "GODREJCP",
  "company_name": "GODREJ CONSUMER PRODUCTS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE102D01028",
  "face_value": 100.0
 },
 {
  "symbol": "GODREJIND",
  "company_name": "GODREJ INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE233A01035",
  "face_value": 100.0
 },
 {
  "symbol": "GODREJPROP",
  "company_name": "GODREJ PROPERTIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE484J01027",
  "face_value": 500.0
 },
 {
  "symbol": "GOENKA",
  "company_name": "GOENKA DIAMOND&JEWELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE516K01024",
  "face_value": 100.0
 },
 {
  "symbol": "GOKEX",
  "company_name": "GOKALDAS EXPORTS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE887G01027",
  "face_value": 500.0
 },
 {
  "symbol": "GOKUL",
  "company_name": "GOKUL REFOILS & SOLV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE020J01029",
  "face_value": 200.0
 },
 {
  "symbol": "GOKUL-RE",
  "company_name": "GOKUL AGRO RESOURCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE314T20017",
  "face_value": 200.0
 },
 {
  "symbol": "GOKULAGRO",
  "company_name": "GOKUL AGRO RESOURCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE314T01033",
  "face_value": 100.0
 },
 {
  "symbol": "GOLCRESFIN",
  "company_name": "GOLDCREST FINANCE (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE096401018",
  "face_value": 1000.0
 },
 {
  "symbol": "GOLD1",
  "company_name": "KOTAK GOLD ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1HJ8",
  "face_value": 100.0
 },
 {
  "symbol": "GOLD360",
  "company_name": "360ONEAMC - GOLD360",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF579M01BB5",
  "face_value": 1000.0
 },
 {
  "symbol": "GOLDADD",
  "company_name": "DSPAMC - DSPGOLD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1SW3",
  "face_value": 1000.0
 },
 {
  "symbol": "GOLDBDINAV",
  "company_name": "BANDHANAMC - GOLDBDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000323",
  "face_value": 1000.0
 },
 {
  "symbol": "GOLDBEES",
  "company_name": "NIP IND ETF GOLD BEES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KB17I5",
  "face_value": 100.0
 },
 {
  "symbol": "GOLDBEINAV",
  "company_name": "GOLDBEES NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000036",
  "face_value": 100.0
 },
 {
  "symbol": "GOLDBENAV",
  "company_name": "GOLD BEES NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000020",
  "face_value": 1000.0
 },
 {
  "symbol": "GOLDBETA",
  "company_name": "UTIAMC-UTIGOLDBETA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF789F1AUX7",
  "face_value": 100.0
 },
 {
  "symbol": "GOLDBND",
  "company_name": "BANDHANAMC - GOLDBND",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF194KB1KJ7",
  "face_value": 1000.0
 },
 {
  "symbol": "GOLDCASE",
  "company_name": "ZERODHAAMC - GOLDCASE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF0R8F01042",
  "face_value": 1000.0
 },
 {
  "symbol": "GOLDENTOBC",
  "company_name": "GOLDEN TOBACCO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE973A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "GOLDETF",
  "company_name": "MIRAEAMC - MAGOLDETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01JP9",
  "face_value": 1000.0
 },
 {
  "symbol": "GOLDIAM",
  "company_name": "GOLDIAM INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE025B01025",
  "face_value": 200.0
 },
 {
  "symbol": "GOLDIETF",
  "company_name": "ICICI PRUDENTIAL GOLD ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC1NT3",
  "face_value": 100.0
 },
 {
  "symbol": "GOLDSHINAV",
  "company_name": "GOLDSHARE NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000037",
  "face_value": 100.0
 },
 {
  "symbol": "GOLDTECH",
  "company_name": "AION-TECH SOLUTIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE805A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "GONTERPEIP",
  "company_name": "GONTERMANN PEIPERS (I) LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE530A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "GOODLUCK",
  "company_name": "GOODLUCK INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE127I01024",
  "face_value": 200.0
 },
 {
  "symbol": "GOODRICKE",
  "company_name": "GOODRICKE GROUP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE300A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "GOODVALUE",
  "company_name": "GOOD VALUE MARKETING CO.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE097901016",
  "face_value": 1000.0
 },
 {
  "symbol": "GOODYEAR",
  "company_name": "GOODYEAR INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE533A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "GOPAL",
  "company_name": "GOPAL SNACKS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0L9R01028",
  "face_value": 100.0
 },
 {
  "symbol": "GORDONHERB",
  "company_name": "GORDON HERBERT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE098401016",
  "face_value": 1000.0
 },
 {
  "symbol": "GOVINRUBER",
  "company_name": "GOVIND RUBBER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE011C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "GOYALALUM",
  "company_name": "GOYAL ALUMINIUMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE705X01026",
  "face_value": 100.0
 },
 {
  "symbol": "GPIL",
  "company_name": "GODAWARI POW & ISP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE177H01039",
  "face_value": 100.0
 },
 {
  "symbol": "GPPL",
  "company_name": "GUJARAT PIPAVAV PORT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE517F01014",
  "face_value": 1000.0
 },
 {
  "symbol": "GPTHEALTH",
  "company_name": "GPT HEALTHCARE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE486R01017",
  "face_value": 1000.0
 },
 {
  "symbol": "GPTINFRA",
  "company_name": "GPT INFRAPROJECTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE390G01014",
  "face_value": 1000.0
 },
 {
  "symbol": "GRANDFONRY",
  "company_name": "GRAND FOUNDRY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE534A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "GRANDOAK",
  "company_name": "GRAND OAK CANYONS DIST L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE926B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "GRANULES",
  "company_name": "GRANULES INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE101D01020",
  "face_value": 100.0
 },
 {
  "symbol": "GRAPCOMIN",
  "company_name": "GRAPCO MINING AND CO. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE099401015",
  "face_value": 1000.0
 },
 {
  "symbol": "GRAPHITE",
  "company_name": "GRAPHITE INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE371A01025",
  "face_value": 200.0
 },
 {
  "symbol": "GRASIM",
  "company_name": "GRASIM INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE047A01021",
  "face_value": 200.0
 },
 {
  "symbol": "GRASIM-RE",
  "company_name": "GRASIM IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE047A20013",
  "face_value": 200.0
 },
 {
  "symbol": "GRAUWEIL",
  "company_name": "GRAUER & WEIL IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE266D01021",
  "face_value": 100.0
 },
 {
  "symbol": "GRAVISSHO",
  "company_name": "GRAVISS HOSPITALITY LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE214F01026",
  "face_value": 200.0
 },
 {
  "symbol": "GRAVITA",
  "company_name": "GRAVITA INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE024L01027",
  "face_value": 200.0
 },
 {
  "symbol": "GRCAPMINAV",
  "company_name": "GROWWAMC - GRCAPMINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000322",
  "face_value": 1000.0
 },
 {
  "symbol": "GREAVESCOT",
  "company_name": "GREAVES COTTON LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE224A01026",
  "face_value": 200.0
 },
 {
  "symbol": "GREEN-RE",
  "company_name": "ORIENT GREEN POWER CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE999K20014",
  "face_value": 1000.0
 },
 {
  "symbol": "GREEN-RE1",
  "company_name": "ORIENT GREEN POWER CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE999K20022",
  "face_value": 1000.0
 },
 {
  "symbol": "GREENLAM",
  "company_name": "GREENLAM INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE544R01021",
  "face_value": 100.0
 },
 {
  "symbol": "GREENPANEL",
  "company_name": "GREENPANEL INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE08ZM01014",
  "face_value": 100.0
 },
 {
  "symbol": "GREENPLY",
  "company_name": "GREENPLY INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE461C01038",
  "face_value": 100.0
 },
 {
  "symbol": "GREENPOWER",
  "company_name": "ORIENT GREEN POWER CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE999K01014",
  "face_value": 1000.0
 },
 {
  "symbol": "GRINDWELL",
  "company_name": "GRINDWELL NORTON LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE536A01023",
  "face_value": 500.0
 },
 {
  "symbol": "GRINFRA",
  "company_name": "G R INFRAPROJECTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE201P01022",
  "face_value": 500.0
 },
 {
  "symbol": "GRINWELNOR",
  "company_name": "GRINDWELL NORTON LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE536A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "GRMOVER",
  "company_name": "GRM OVERSEAS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE192H01020",
  "face_value": 200.0
 },
 {
  "symbol": "GRN200INAV",
  "company_name": "GROWWAMC - GRN200INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000258",
  "face_value": 1000.0
 },
 {
  "symbol": "GRO250INAV",
  "company_name": "GROWWAMC - GRO250INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000308",
  "face_value": 1000.0
 },
 {
  "symbol": "GROBTEA",
  "company_name": "THE GROB TEA COMPANY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE646C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "GROLIQINAV",
  "company_name": "GROWWAMC - GROLIQINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000242",
  "face_value": 10000.0
 },
 {
  "symbol": "GRONIFINAV",
  "company_name": "GROWWAMC - GRONIFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000291",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWEVINAV",
  "company_name": "GROWWAMC - GROWEVINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000235",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWLOINAV",
  "company_name": "GROWWAMC - GROWLOINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000284",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWMOINAV",
  "company_name": "GROWWAMC - GROWMOINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000273",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWSLINAV",
  "company_name": "GROWWAMC - GROWSLINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000278",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWW",
  "company_name": "BILLIONBRAINS GARAGE VN L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0HOQ01053",
  "face_value": 200.0
 },
 {
  "symbol": "GROWWCAPM",
  "company_name": "GROWWAMC - GROWWCAPM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01MM4",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWCHEM",
  "company_name": "GROWWAMC - GROWWCHEM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01NP5",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWDEFNC",
  "company_name": "GROWWAMC - GROWWDEFNC",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01IO8",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWEINAV",
  "company_name": "GROWWAMC - GROWWEINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000333",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWEV",
  "company_name": "GROWWAMC - GROWWEV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01IH2",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWGINAV",
  "company_name": "GROWWAMC - GROWWGINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000249",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWGOLD",
  "company_name": "GROWWAMC - GROWWGOLD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01OE7",
  "face_value": 100.0
 },
 {
  "symbol": "GROWWHOSPI",
  "company_name": "GROWWAMC - GROWWHOSPI",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01OD9",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWLIQID",
  "company_name": "GROWWAMC - GROWWLIQID",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01IP5",
  "face_value": 10000.0
 },
 {
  "symbol": "GROWWLOVOL",
  "company_name": "GROWWAMC - GROWWLOVOL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01LB9",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWMC150",
  "company_name": "GROWWAMC - GROWWMC150",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01MV5",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWMETAL",
  "company_name": "GROWWAMC - GROWWMETAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01NI0",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWMOM50",
  "company_name": "GROWWAMC - GROWWMOM50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01KJ4",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWN200",
  "company_name": "GROWWAMC - GROWWN200",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01JV1",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWNET",
  "company_name": "GROWWAMC - GROWWNET",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01LI4",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWNIFTY",
  "company_name": "GROWWAMC - GROWWNIFTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01LL8",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWNINAV",
  "company_name": "GROWWAMC - GROWWNINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000287",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWNXT50",
  "company_name": "GROWWAMC - GROWWNXT50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01LZ8",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWPINAV",
  "company_name": "GROWWAMC - GROWWPINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000292",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWPOWER",
  "company_name": "GROWWAMC - GROWWPOWER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01LM6",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWPSE",
  "company_name": "GROWWAMC - GROWWPSE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01NQ3",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWPSUBK",
  "company_name": "GROWWAMC - GROWWPSUBK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01OG2",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWRAIL",
  "company_name": "GROWWAMC - GROWWRAIL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01JJ6",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWRINAV",
  "company_name": "GROWWAMC - GROWWRINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000301",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWRLTY",
  "company_name": "GROWWAMC - GROWWRLTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01MN2",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWSC250",
  "company_name": "GROWWAMC - GROWWSC250",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01MO0",
  "face_value": 1000.0
 },
 {
  "symbol": "GROWWSLVR",
  "company_name": "GROWWAMC - GROWWSLVR",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01OF4",
  "face_value": 100.0
 },
 {
  "symbol": "GRPLTD",
  "company_name": "GRP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE137I01015",
  "face_value": 1000.0
 },
 {
  "symbol": "GRRAILINAV",
  "company_name": "GROWWAMC - GRRAILINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000255",
  "face_value": 1000.0
 },
 {
  "symbol": "GRSE",
  "company_name": "GARDEN REACH SHIP&ENG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE382Z01011",
  "face_value": 1000.0
 },
 {
  "symbol": "GRW150INAV",
  "company_name": "GROWWAMC - GRW150INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000313",
  "face_value": 1000.0
 },
 {
  "symbol": "GRWCHEINAV",
  "company_name": "GROWWAMC - GRWCHEINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000332",
  "face_value": 1000.0
 },
 {
  "symbol": "GRWMTLINAV",
  "company_name": "GROWWAMC - GRWMTLINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000328",
  "face_value": 1000.0
 },
 {
  "symbol": "GRWN50INAV",
  "company_name": "GROWWAMC - GRWN50INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000296",
  "face_value": 1000.0
 },
 {
  "symbol": "GRWPSUINAV",
  "company_name": "GROWWAMC - GRWPSUINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000344",
  "face_value": 1000.0
 },
 {
  "symbol": "GRWRHITECH",
  "company_name": "GARWARE HI-TECH FILMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE291A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "GRWWDFINAV",
  "company_name": "GROWWAMC - GRWWDFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000247",
  "face_value": 1000.0
 },
 {
  "symbol": "GSCLCEMENT",
  "company_name": "GUJARAT SIDHEE CEM. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE542A01039",
  "face_value": 1000.0
 },
 {
  "symbol": "GSEC10ABSL",
  "company_name": "BIRLASLAMC - GSEC10ABSL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KC1142",
  "face_value": 10000.0
 },
 {
  "symbol": "GSEC10IETF",
  "company_name": "ICICIPRAMC - ICICI10GS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC18O0",
  "face_value": 1000.0
 },
 {
  "symbol": "GSEC10INAV",
  "company_name": "BIRLASLAMC - GSEC10INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000236",
  "face_value": 10000.0
 },
 {
  "symbol": "GSEC10YEAR",
  "company_name": "MIRAEAMC - MAGS813ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01KF8",
  "face_value": 1000.0
 },
 {
  "symbol": "GSEC5IETF",
  "company_name": "ICICIPRAMC - ICICI5GSEC",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC14A8",
  "face_value": 1000.0
 },
 {
  "symbol": "GSFC",
  "company_name": "GUJ STATE FERT & CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE026A01025",
  "face_value": 200.0
 },
 {
  "symbol": "GSL",
  "company_name": "GSL (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE184901010",
  "face_value": 1000.0
 },
 {
  "symbol": "GSLSU",
  "company_name": "GLOBAL SURFACES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0JSX01015",
  "face_value": 1000.0
 },
 {
  "symbol": "GSPCROP",
  "company_name": "GSP CROP SCIENCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE713R01022",
  "face_value": 1000.0
 },
 {
  "symbol": "GSPL",
  "company_name": "GUJARAT STATE PETRO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE246F01010",
  "face_value": 1000.0
 },
 {
  "symbol": "GSS",
  "company_name": "GSS INFOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE871H01011",
  "face_value": 1000.0
 },
 {
  "symbol": "GTECJAINX",
  "company_name": "G-TEC JAINX EDUCATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE586X01012",
  "face_value": 1000.0
 },
 {
  "symbol": "GTL",
  "company_name": "GTL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE043A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "GTLINFRA",
  "company_name": "GTL INFRA.LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE221H01019",
  "face_value": 1000.0
 },
 {
  "symbol": "GTNIND",
  "company_name": "GTN INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE537A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "GTNTEX",
  "company_name": "GTN TEXTILES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE302H01017",
  "face_value": 1000.0
 },
 {
  "symbol": "GTPL",
  "company_name": "GTPL HATHWAY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE869I01013",
  "face_value": 1000.0
 },
 {
  "symbol": "GUFICBIO",
  "company_name": "GUFIC BIOSCIENCES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE742B01025",
  "face_value": 100.0
 },
 {
  "symbol": "GUJALKALI",
  "company_name": "GUJARAT ALKALIES & CHEM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE186A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "GUJAPOLLO",
  "company_name": "GUJ. APOLLO IND. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE826C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "GUJBOROSIL",
  "company_name": "GUJARAT BOROSIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE059C01014",
  "face_value": 1000.0
 },
 {
  "symbol": "GUJCOTEX",
  "company_name": "GUJARAT COTEX LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE452201010",
  "face_value": 1000.0
 },
 {
  "symbol": "GUJGASLTD",
  "company_name": "GUJARAT GAS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE844O01030",
  "face_value": 200.0
 },
 {
  "symbol": "GUJNRECOKE",
  "company_name": "GUJARAT N R E COKE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE110D01013",
  "face_value": 1000.0
 },
 {
  "symbol": "GUJNREDVR",
  "company_name": "GUJ NRE DVR  B  CLASS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "IN9110D01011",
  "face_value": 1000.0
 },
 {
  "symbol": "GUJOPTICAL",
  "company_name": "GUJARAT OPTICAL COMM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE452401016",
  "face_value": 1000.0
 },
 {
  "symbol": "GUJRAFFIA",
  "company_name": "GUJARAT RAFFIA INDUST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE610B01024",
  "face_value": 1000.0
 },
 {
  "symbol": "GUJRATTELE",
  "company_name": "GUJARAT TELEPHONE CABLES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE261B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "GUJTHEM",
  "company_name": "GUJARAT THEMIS BIOSYN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE942C01045",
  "face_value": 100.0
 },
 {
  "symbol": "GUJTHEMIS",
  "company_name": "GUJARAT THEMIS BIOSYN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE183701015",
  "face_value": 1000.0
 },
 {
  "symbol": "GULFOILLUB",
  "company_name": "GULF OIL LUB. IND. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE635Q01029",
  "face_value": 200.0
 },
 {
  "symbol": "GULFPETRO",
  "company_name": "GP PETROLEUMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE586G01017",
  "face_value": 500.0
 },
 {
  "symbol": "GULPOLY",
  "company_name": "GULSHAN POLYOLS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE255D01024",
  "face_value": 100.0
 },
 {
  "symbol": "GVKPIL",
  "company_name": "GVK POW. & INFRA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE251H01024",
  "face_value": 100.0
 },
 {
  "symbol": "GVPIL",
  "company_name": "GE POWER INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE878A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "GVPTECH",
  "company_name": "GVP INFOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE382T01030",
  "face_value": 200.0
 },
 {
  "symbol": "GVPTECH-RE",
  "company_name": "GVP INFOTECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE382T20014",
  "face_value": 200.0
 },
 {
  "symbol": "GVT&D",
  "company_name": "GE VERNOVA T&D INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE200A01026",
  "face_value": 200.0
 },
 {
  "symbol": "HAL",
  "company_name": "HINDUSTAN AERONAUTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE066F01020",
  "face_value": 500.0
 },
 {
  "symbol": "HALDER",
  "company_name": "HALDER VENTURE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE115S01010",
  "face_value": 1000.0
 },
 {
  "symbol": "HALDYNGL",
  "company_name": "HALDYN GLASS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE506D01020",
  "face_value": 100.0
 },
 {
  "symbol": "HALEOSLABS",
  "company_name": "HALEOS LABS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE320X01016",
  "face_value": 1000.0
 },
 {
  "symbol": "HAPPSTMNDS",
  "company_name": "HAPPIEST MINDS TECHNO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE419U01012",
  "face_value": 200.0
 },
 {
  "symbol": "HAPPYFORGE",
  "company_name": "HAPPY FORGINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE330T01021",
  "face_value": 200.0
 },
 {
  "symbol": "HARDWYN",
  "company_name": "HARDWYN INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE626Z01029",
  "face_value": 100.0
 },
 {
  "symbol": "HARIAEXPO",
  "company_name": "HARIA EXPORTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE772B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "HARIGCRANK",
  "company_name": "HARIG CRANKSHAFTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE180501012",
  "face_value": 1000.0
 },
 {
  "symbol": "HARIOMPIPE",
  "company_name": "HARIOM PIPE INDUSTRIES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00EV01017",
  "face_value": 1000.0
 },
 {
  "symbol": "HARITASEAT",
  "company_name": "HARITA SEATING SYS. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE939D01015",
  "face_value": 1000.0
 },
 {
  "symbol": "HARRMALAYA",
  "company_name": "HARRISON MALAYALAM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE544A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "HARSHA",
  "company_name": "HARSHA ENGINEERS INT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0JUS01029",
  "face_value": 1000.0
 },
 {
  "symbol": "HARYANPETR",
  "company_name": "HARYANA PETROCHEMICALS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE174901012",
  "face_value": 1000.0
 },
 {
  "symbol": "HATHWAY",
  "company_name": "HATHWAY CABLE & DATACOM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE982F01036",
  "face_value": 200.0
 },
 {
  "symbol": "HATSUN",
  "company_name": "HATSUN AGRO PRODUCT LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE473B01035",
  "face_value": 100.0
 },
 {
  "symbol": "HATSUN-RE",
  "company_name": "HATSUN AGRO PROD LTD-RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE473B20019",
  "face_value": 100.0
 },
 {
  "symbol": "HAVELLS",
  "company_name": "HAVELLS INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE176B01034",
  "face_value": 100.0
 },
 {
  "symbol": "HAVISHA",
  "company_name": "SRI HAVISHA HOSP & INFR L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE293B01029",
  "face_value": 200.0
 },
 {
  "symbol": "HAWKINCOOK",
  "company_name": "HAWKINS COOKERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE979B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "HBANKEINAV",
  "company_name": "HBANKETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000070",
  "face_value": 100.0
 },
 {
  "symbol": "HBESD",
  "company_name": "H B ESTATE DEVELOPERS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE640B01021",
  "face_value": 1000.0
 },
 {
  "symbol": "HBLENGINE",
  "company_name": "HBL ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE292B01021",
  "face_value": 100.0
 },
 {
  "symbol": "HBS500INAV",
  "company_name": "HDFCAMC - HBS500INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000176",
  "face_value": 2386.0
 },
 {
  "symbol": "HBSL",
  "company_name": "HB STOCKHOLDINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE550B01022",
  "face_value": 1000.0
 },
 {
  "symbol": "HCC",
  "company_name": "HINDUSTAN CONSTRUCTION CO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE549A01026",
  "face_value": 100.0
 },
 {
  "symbol": "HCC-RE",
  "company_name": "HINDUSTAN CONSTRUCTION CO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE549A20018",
  "face_value": 100.0
 },
 {
  "symbol": "HCC-RE1",
  "company_name": "HINDUSTAN CONSTRUCTION CO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE549A20026",
  "face_value": 100.0
 },
 {
  "symbol": "HCG",
  "company_name": "HEALTHCARE GLOB. ENT. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE075I01017",
  "face_value": 1000.0
 },
 {
  "symbol": "HCG-RE",
  "company_name": "HEALTHCARE GLOBAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE075I20017",
  "face_value": 1000.0
 },
 {
  "symbol": "HCL-INSYS",
  "company_name": "HCL INFOSYSTEMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE236A01020",
  "face_value": 200.0
 },
 {
  "symbol": "HCLTECH",
  "company_name": "HCL TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE860A01027",
  "face_value": 200.0
 },
 {
  "symbol": "HDBFS",
  "company_name": "HDB FINANCIAL SERVICES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE756I01012",
  "face_value": 1000.0
 },
 {
  "symbol": "HDF100INAV",
  "company_name": "HDFCNIF100 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000150",
  "face_value": 100.0
 },
 {
  "symbol": "HDFC",
  "company_name": "HDFC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE001A01036",
  "face_value": 200.0
 },
 {
  "symbol": "HDFC50INAV",
  "company_name": "HDFCNEXT50 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000151",
  "face_value": 100.0
 },
 {
  "symbol": "HDFCAMC",
  "company_name": "HDFC AMC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE127D01025",
  "face_value": 500.0
 },
 {
  "symbol": "HDFCBANK",
  "company_name": "HDFC BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE040A01034",
  "face_value": 100.0
 },
 {
  "symbol": "HDFCBSE500",
  "company_name": "HDFCAMC - HDFCBSE500",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1EZ4",
  "face_value": 2386.0
 },
 {
  "symbol": "HDFCGOLD",
  "company_name": "HDFC GOLD ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1981",
  "face_value": 100.0
 },
 {
  "symbol": "HDFCGRINAV",
  "company_name": "HDFCAMC - HDFCGRINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000162",
  "face_value": 8907.0
 },
 {
  "symbol": "HDFCGROWTH",
  "company_name": "HDFCAMC - HDFCGROWTH",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1DJ0",
  "face_value": 8907.0
 },
 {
  "symbol": "HDFCLIFE",
  "company_name": "HDFC LIFE INS CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE795G01014",
  "face_value": 1000.0
 },
 {
  "symbol": "HDFCLIQUID",
  "company_name": "HDFCAMC - HDFCLIQUID",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1JG3",
  "face_value": 100000.0
 },
 {
  "symbol": "HDFCLOWVOL",
  "company_name": "HDFCAMC - HDFCLOWVOL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1HU8",
  "face_value": 1261.0
 },
 {
  "symbol": "HDFCLVINAV",
  "company_name": "HDFCAMC - HDFCLOWVOL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000166",
  "face_value": 12618.0
 },
 {
  "symbol": "HDFCMFINAV",
  "company_name": "HDFCMFGETF NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000038",
  "face_value": 100.0
 },
 {
  "symbol": "HDFCMID150",
  "company_name": "HDFCAMC - HDFCMID150",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1HT0",
  "face_value": 1159.0
 },
 {
  "symbol": "HDFCMOINAV",
  "company_name": "HDFCAMC - HDFCMOMENT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000165",
  "face_value": 19061.0
 },
 {
  "symbol": "HDFCMOMENT",
  "company_name": "HDFCAMC - HDFCMOMENT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1HV6",
  "face_value": 1906.0
 },
 {
  "symbol": "HDFCNEXT50",
  "company_name": "HDFCAMC - HDFCNEXT50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1HS2",
  "face_value": 4181.0
 },
 {
  "symbol": "HDFCNFINAV",
  "company_name": "HDFCNIFETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000071",
  "face_value": 100.0
 },
 {
  "symbol": "HDFCNIF100",
  "company_name": "HDFCAMC - HDFCNIF100",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1HR4",
  "face_value": 1772.0
 },
 {
  "symbol": "HDFCNIFBAN",
  "company_name": "HDFCAMC - HDFCNIFBAN",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1HY0",
  "face_value": 2233.0
 },
 {
  "symbol": "HDFCNIFIT",
  "company_name": "HDFCAMC - HDFCNIFIT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1IA8",
  "face_value": 2999.0
 },
 {
  "symbol": "HDFCNIFTY",
  "company_name": "HDFCAMC - HDFCNIFTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1965",
  "face_value": 7612.0
 },
 {
  "symbol": "HDFCNIINAV",
  "company_name": "HDFCAMC - HDFCNIINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000188",
  "face_value": 29992.0
 },
 {
  "symbol": "HDFCPBINAV",
  "company_name": "HDFCAMC - HDFCPBINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000168",
  "face_value": 21675.0
 },
 {
  "symbol": "HDFCPSUBK",
  "company_name": "HDFCAMC HDFCPSUBK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1HW4",
  "face_value": 6278.0
 },
 {
  "symbol": "HDFCPVTBAN",
  "company_name": "HDFCAMC - HDFCPVTBAN",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1HZ7",
  "face_value": 2167.0
 },
 {
  "symbol": "HDFCQUAL",
  "company_name": "HDFCAMC - HDFCQUAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1DL6",
  "face_value": 3859.0
 },
 {
  "symbol": "HDFCQUINAV",
  "company_name": "HDFCAMC - HDFCQUINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000163",
  "face_value": 3859.0
 },
 {
  "symbol": "HDFCSEINAV",
  "company_name": "HDFCSENETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000072",
  "face_value": 100.0
 },
 {
  "symbol": "HDFCSENSEX",
  "company_name": "HDFCAMC - HDFCSENSEX",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1HX2",
  "face_value": 2503.0
 },
 {
  "symbol": "HDFCSIINAV",
  "company_name": "HDFCAMC - HDFCSIINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000160",
  "face_value": 5252.0
 },
 {
  "symbol": "HDFCSILVER",
  "company_name": "HDFCAMC - HDFCSILVER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1DI2",
  "face_value": 5252.0
 },
 {
  "symbol": "HDFCSML250",
  "company_name": "HDFCAMC - HDFCSML250",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1FB2",
  "face_value": 9131.0
 },
 {
  "symbol": "HDFCVALUE",
  "company_name": "HDFCAMC - HDFCVALUE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF179KC1DK8",
  "face_value": 8607.0
 },
 {
  "symbol": "HDFCVLINAV",
  "company_name": "HDFCAMC - HDFCVLINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000164",
  "face_value": 8607.0
 },
 {
  "symbol": "HDFLIQINAV",
  "company_name": "HDFCAMC - HDFLIQINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000196",
  "face_value": 100000.0
 },
 {
  "symbol": "HDFPBKINAV",
  "company_name": "HDFCAMC HDFPBKINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000216",
  "face_value": 6278.0
 },
 {
  "symbol": "HDIL",
  "company_name": "HOUSING DEV & INFRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE191I01012",
  "face_value": 1000.0
 },
 {
  "symbol": "HEADSUP",
  "company_name": "HEADS UP VENTURES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE759V01019",
  "face_value": 1000.0
 },
 {
  "symbol": "HEALADINAV",
  "company_name": "DSPAMC - HEALADINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000215",
  "face_value": 1000.0
 },
 {
  "symbol": "HEALTHADD",
  "company_name": "DSPAMC - HEALTHADD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1UF4",
  "face_value": 1000.0
 },
 {
  "symbol": "HEALTHCARE",
  "company_name": "MIRAEAMC - HEALTHCARE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01QA6",
  "face_value": 1000.0
 },
 {
  "symbol": "HEALTHIETF",
  "company_name": "ICICIPRAMC - ICICIPHARM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC1Q72",
  "face_value": 1000.0
 },
 {
  "symbol": "HEALTHINAV",
  "company_name": "HEALTHY INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000048",
  "face_value": 100.0
 },
 {
  "symbol": "HEALTHY",
  "company_name": "BIRLASLAMC - HEALTHY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KB10C2",
  "face_value": 100.0
 },
 {
  "symbol": "HECPROJECT",
  "company_name": "HEC INFRA PROJECTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE558R01013",
  "face_value": 1000.0
 },
 {
  "symbol": "HEG",
  "company_name": "HEG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE545A01024",
  "face_value": 200.0
 },
 {
  "symbol": "HEIDELBERG",
  "company_name": "HEIDELBERGCEMENT (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE578A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "HEMIPROP",
  "company_name": "HEMISPHERE PROP IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0AJG01018",
  "face_value": 1000.0
 },
 {
  "symbol": "HERANBA",
  "company_name": "HERANBA INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE694N01015",
  "face_value": 1000.0
 },
 {
  "symbol": "HERBETSON",
  "company_name": "HERBERTSONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE176301013",
  "face_value": 1000.0
 },
 {
  "symbol": "HERCULES",
  "company_name": "HERCULES INVESTMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE688E01024",
  "face_value": 100.0
 },
 {
  "symbol": "HERDIOXIDE",
  "company_name": "HERDILLIA OXIDES & ELECTR",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE176501018",
  "face_value": 1000.0
 },
 {
  "symbol": "HERIT-RE",
  "company_name": "HERITAGE FOODS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE978A20019",
  "face_value": 500.0
 },
 {
  "symbol": "HERITGFOOD",
  "company_name": "HERITAGE FOODS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE978A01027",
  "face_value": 500.0
 },
 {
  "symbol": "HEROMOTOCO",
  "company_name": "HERO MOTOCORP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE158A01026",
  "face_value": 200.0
 },
 {
  "symbol": "HESTERBIO",
  "company_name": "HESTER BIOSCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE782E01017",
  "face_value": 1000.0
 },
 {
  "symbol": "HEXATRADEX",
  "company_name": "HEXA TRADEX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE750M01017",
  "face_value": 200.0
 },
 {
  "symbol": "HEXAWARE",
  "company_name": "HEXAWARE TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE093A01033",
  "face_value": 200.0
 },
 {
  "symbol": "HEXT",
  "company_name": "HEXAWARE TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE093A01041",
  "face_value": 100.0
 },
 {
  "symbol": "HFCL",
  "company_name": "HFCL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE548A01028",
  "face_value": 100.0
 },
 {
  "symbol": "HGINFRA",
  "company_name": "H.G.INFRA ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE926X01010",
  "face_value": 1000.0
 },
 {
  "symbol": "HGM",
  "company_name": "HANDSON GBL MNGMNT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE596H01014",
  "face_value": 1000.0
 },
 {
  "symbol": "HGS",
  "company_name": "HINDUJA GLOBAL SOLS. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE170I01016",
  "face_value": 1000.0
 },
 {
  "symbol": "HIGHGROUND",
  "company_name": "HIGH GROUND ENTP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE361M01021",
  "face_value": 100.0
 },
 {
  "symbol": "HIKAL",
  "company_name": "HIKAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE475B01022",
  "face_value": 200.0
 },
 {
  "symbol": "HILINFRA",
  "company_name": "HIGHWAY INFRASTRUCTURE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00RL01028",
  "face_value": 500.0
 },
 {
  "symbol": "HILTON",
  "company_name": "HILTON METAL FORGING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE788H01017",
  "face_value": 1000.0
 },
 {
  "symbol": "HILTON-RE",
  "company_name": "HILTON METAL FORGING LIMI",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE788H20017",
  "face_value": 1000.0
 },
 {
  "symbol": "HILTON-RE1",
  "company_name": "HILTON METAL FORGING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE788H20025",
  "face_value": 1000.0
 },
 {
  "symbol": "HILTON-RE2",
  "company_name": "HILTON METAL FORGING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE788H20033",
  "face_value": 1000.0
 },
 {
  "symbol": "HIMADCHEM",
  "company_name": "HIMADRI CHEMICALS AND IND",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE019C01026",
  "face_value": 1000.0
 },
 {
  "symbol": "HIMATSEIDE",
  "company_name": "HIMATSINGKA SEIDE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE049A01027",
  "face_value": 500.0
 },
 {
  "symbol": "HIMGRANITE",
  "company_name": "HIMALAYA GRANITES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY9383",
  "face_value": 1000.0
 },
 {
  "symbol": "HINDALCO",
  "company_name": "HINDALCO  INDUSTRIES  LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE038A01020",
  "face_value": 100.0
 },
 {
  "symbol": "HINDCOMPOS",
  "company_name": "HINDUSTAN COMPOSITES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE310C01029",
  "face_value": 500.0
 },
 {
  "symbol": "HINDCON",
  "company_name": "HINDCON CHEMICALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE642Y01029",
  "face_value": 200.0
 },
 {
  "symbol": "HINDCOPPER",
  "company_name": "HINDUSTAN COPPER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE531E01026",
  "face_value": 500.0
 },
 {
  "symbol": "HINDIND",
  "company_name": "HIND INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE173501011",
  "face_value": 1000.0
 },
 {
  "symbol": "HINDINDCHM",
  "company_name": "HINDUSTAN INDUSTRIAL CHEM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE169201014",
  "face_value": 1000.0
 },
 {
  "symbol": "HINDMOTORS",
  "company_name": "HINDUSTAN MOTORS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE253A01025",
  "face_value": 500.0
 },
 {
  "symbol": "HINDNATGLS",
  "company_name": "HIND NATL GLASS & IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE952A01022",
  "face_value": 200.0
 },
 {
  "symbol": "HINDNITRO",
  "company_name": "HINDUSTAN NITROPROD GUJRA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE169501017",
  "face_value": 1000.0
 },
 {
  "symbol": "HINDOILEXP",
  "company_name": "HINDUSTAN OIL EXPLORATION",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE345A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "HINDPETRO",
  "company_name": "HINDUSTAN PETROLEUM CORP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE094A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "HINDPHOTO",
  "company_name": "HINDUSTAN PHOTO FILMS MFG",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE453901014",
  "face_value": 1000.0
 },
 {
  "symbol": "HINDRECT",
  "company_name": "HIND RECTIFIERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE553701017",
  "face_value": 1000.0
 },
 {
  "symbol": "HINDSYNTEX",
  "company_name": "HIND SYNTEX LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE155B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "HINDTINWRK",
  "company_name": "HINDUSTAN TIN WORKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE554501010",
  "face_value": 1000.0
 },
 {
  "symbol": "HINDUNILVR",
  "company_name": "HINDUSTAN UNILEVER LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE030A01027",
  "face_value": 100.0
 },
 {
  "symbol": "HINDWAR-RE",
  "company_name": "HINDWARE HME INOVATON LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE05AN20011",
  "face_value": 200.0
 },
 {
  "symbol": "HINDWAREAP",
  "company_name": "HINDWARE HME INOVATON LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE05AN01011",
  "face_value": 200.0
 },
 {
  "symbol": "HINDZINC",
  "company_name": "HINDUSTAN ZINC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE267A01025",
  "face_value": 200.0
 },
 {
  "symbol": "HINPOWPLUS",
  "company_name": "HINDUSTAN POWERPLUS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE554A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "HIRECT",
  "company_name": "HIND RECTIFIER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE835D01023",
  "face_value": 200.0
 },
 {
  "symbol": "HISARMETAL",
  "company_name": "HISAR METAL IND. LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE598C01011",
  "face_value": 1000.0
 },
 {
  "symbol": "HITECH",
  "company_name": "HI-TECH PIPES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE106T01025",
  "face_value": 100.0
 },
 {
  "symbol": "HITECHCORP",
  "company_name": "HITECH CORPORATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE120D01012",
  "face_value": 1000.0
 },
 {
  "symbol": "HITECHGEAR",
  "company_name": "THE HI-TECH GEARS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE127B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "HLEGLAS",
  "company_name": "HLE GLASCOAT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE461D01028",
  "face_value": 200.0
 },
 {
  "symbol": "HLTCREINAV",
  "company_name": "MIRAEAMC - HLTCREINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000334",
  "face_value": 1000.0
 },
 {
  "symbol": "HLVLTD",
  "company_name": "HLV LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE102A01024",
  "face_value": 200.0
 },
 {
  "symbol": "HMAAGRO",
  "company_name": "HMA AGRO INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0ECP01024",
  "face_value": 100.0
 },
 {
  "symbol": "HMI150INAV",
  "company_name": "HDFCAMC - HMI150INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000177",
  "face_value": 11595.0
 },
 {
  "symbol": "HMT",
  "company_name": "HINDUSTAN MACHINE TOOLS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE262A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "HMVL",
  "company_name": "HINDUSTAN MEDIA VENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE871K01015",
  "face_value": 1000.0
 },
 {
  "symbol": "HNDFDS",
  "company_name": "HINDUSTAN FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE254N01026",
  "face_value": 200.0
 },
 {
  "symbol": "HNGSNBENAV",
  "company_name": "HANGSENG BEES NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000021",
  "face_value": 1000.0
 },
 {
  "symbol": "HNGSNGBEES",
  "company_name": "NIP IND ETF HANGSENG BEES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KB19I1",
  "face_value": 100.0
 },
 {
  "symbol": "HOGANAS",
  "company_name": "HOGANAS INDIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE132A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "HOMEFIRST",
  "company_name": "HOME FIRST FIN CO IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE481N01025",
  "face_value": 200.0
 },
 {
  "symbol": "HONASA",
  "company_name": "HONASA CONSUMER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0J5401028",
  "face_value": 1000.0
 },
 {
  "symbol": "HONAUT",
  "company_name": "HONEYWELL AUTOMATION IND",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE671A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "HONDAPOWER",
  "company_name": "HONDA I POWER PRODUCT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE634A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "HOTLINGLAS",
  "company_name": "HOTLINE GLASS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE676B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "HPAL",
  "company_name": "HP ADHESIVES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0GSL01024",
  "face_value": 200.0
 },
 {
  "symbol": "HPIL",
  "company_name": "HINDPRAKASH INDUSTRY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE05X901010",
  "face_value": 1000.0
 },
 {
  "symbol": "HPL",
  "company_name": "HPL ELECTRIC & POWER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE495S01016",
  "face_value": 1000.0
 },
 {
  "symbol": "HSBCGDINAV",
  "company_name": "HSBCAMC - HSBCGDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000343",
  "face_value": 1000.0
 },
 {
  "symbol": "HSBCGOLD",
  "company_name": "HSBCAMC - HSBCGOLD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF336L01RX2",
  "face_value": 1000.0
 },
 {
  "symbol": "HSCL",
  "company_name": "HIMADRI SPECIALITY CHEM L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE019C01026",
  "face_value": 100.0
 },
 {
  "symbol": "HSM250INAV",
  "company_name": "HDFCAMC - HSM250INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000178",
  "face_value": 9131.0
 },
 {
  "symbol": "HTMEDIA",
  "company_name": "HT MEDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE501G01024",
  "face_value": 200.0
 },
 {
  "symbol": "HUBTOWN",
  "company_name": "HUBTOWN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE703H01016",
  "face_value": 1000.0
 },
 {
  "symbol": "HUDCO",
  "company_name": "HSG & URBAN DEV CORPN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE031A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "HUHTAMAKI",
  "company_name": "HUHTAMAKI INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE275B01026",
  "face_value": 200.0
 },
 {
  "symbol": "HYBRIDFIN",
  "company_name": "HYBRID FINANCIAL SERVICE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE965B01022",
  "face_value": 500.0
 },
 {
  "symbol": "HYTSNMAGNT",
  "company_name": "HYTAISUN MAGNETICS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE165301016",
  "face_value": 1000.0
 },
 {
  "symbol": "HYUNDAI",
  "company_name": "HYUNDAI MOTOR INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0V6F01027",
  "face_value": 1000.0
 },
 {
  "symbol": "IBMFNIFTY",
  "company_name": "IBULLSAMC - IBMFNIFTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF666M01FS5",
  "face_value": 1000.0
 },
 {
  "symbol": "IBMFNIINAV",
  "company_name": "IBMFNIFTY INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000094",
  "face_value": 100.0
 },
 {
  "symbol": "IBUL-RE",
  "company_name": "INDIABULLS HSG FIN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE148I20012",
  "face_value": 200.0
 },
 {
  "symbol": "IBULLSLTD",
  "company_name": "INDIABULLS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE126M01010",
  "face_value": 200.0
 },
 {
  "symbol": "IC10GSINAV",
  "company_name": "ICICIPRAMC - IC10GSINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000172",
  "face_value": 1000.0
 },
 {
  "symbol": "ICDSLTD",
  "company_name": "ICDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE613B01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ICEMAKE",
  "company_name": "ICE MAKE REFRIGERAT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE520Y01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ICICI1INAV",
  "company_name": "ICICINF100 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000087",
  "face_value": 100.0
 },
 {
  "symbol": "ICICI2INAV",
  "company_name": "ICICIB22 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000075",
  "face_value": 100.0
 },
 {
  "symbol": "ICICI5INAV",
  "company_name": "ICICI500 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000085",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIAINAV",
  "company_name": "ICICIALPLV INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000086",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIAMC",
  "company_name": "ICICI PRUDENTIAL AMC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE346A01027",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIB22",
  "company_name": "ICICIPRAMC - BHARATIWIN",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KB15Y7",
  "face_value": 1000.0
 },
 {
  "symbol": "ICICIBANK",
  "company_name": "ICICI BANK LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE090A01021",
  "face_value": 200.0
 },
 {
  "symbol": "ICICIBINAV",
  "company_name": "ICICIBANKP INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000091",
  "face_value": 100.0
 },
 {
  "symbol": "ICICICINAV",
  "company_name": "ICICICONSU INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000078",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIFINAV",
  "company_name": "ICICIFMCG INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000079",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIGI",
  "company_name": "ICICI LOMBARD GIC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE765G01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ICICIGINAV",
  "company_name": "ICICIGOLD NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000039",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIKINAV",
  "company_name": "ICICIBANKN INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000073",
  "face_value": 100.0
 },
 {
  "symbol": "ICICILINAV",
  "company_name": "ICICILOVOL INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000089",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIMINAV",
  "company_name": "ICICIM150 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000083",
  "face_value": 100.0
 },
 {
  "symbol": "ICICININAV",
  "company_name": "ICICINV20 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000090",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIOINAV",
  "company_name": "ICICIAUTO INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000076",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIPINAV",
  "company_name": "ICICIMCAP INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000074",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIPRULI",
  "company_name": "ICICI PRU LIFE INS CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE726G01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ICICIQINAV",
  "company_name": "ICICILIQ INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000082",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIRINAV",
  "company_name": "ICICIPHARM INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000080",
  "face_value": 100.0
 },
 {
  "symbol": "ICICISINAV",
  "company_name": "ICICISILVE NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000040",
  "face_value": 1000.0
 },
 {
  "symbol": "ICICITINAV",
  "company_name": "ICICITECH INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000081",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIXINAV",
  "company_name": "ICICINXT50 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000084",
  "face_value": 100.0
 },
 {
  "symbol": "ICICIYINAV",
  "company_name": "ICICINIFTY INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000088",
  "face_value": 100.0
 },
 {
  "symbol": "ICICMOINAV",
  "company_name": "ICICIPRAMC - ICICMOINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000154",
  "face_value": 1000.0
 },
 {
  "symbol": "ICICOMINAV",
  "company_name": "ICICIPRAMC - ICICOMINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000173",
  "face_value": 1000.0
 },
 {
  "symbol": "ICIFININAV",
  "company_name": "ICICIPRAMC-ICIFININAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000169",
  "face_value": 1000.0
 },
 {
  "symbol": "ICIL",
  "company_name": "INDO COUNT INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE483B01026",
  "face_value": 200.0
 },
 {
  "symbol": "ICINFRINAV",
  "company_name": "ICICIPRAMC - ICINFRINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000158",
  "face_value": 1000.0
 },
 {
  "symbol": "ICIQ30INAV",
  "company_name": "ICICIPRAMC - ICIQ30INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000195",
  "face_value": 1000.0
 },
 {
  "symbol": "ICISECINAV",
  "company_name": "ICICI5GSEC INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000077",
  "face_value": 100.0
 },
 {
  "symbol": "ICISENINAV",
  "company_name": "ICICISENSX INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000092",
  "face_value": 100.0
 },
 {
  "symbol": "ICRA",
  "company_name": "ICRA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE725G01011",
  "face_value": 1000.0
 },
 {
  "symbol": "ICSA",
  "company_name": "ICSA (INDIA) LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE306B01029",
  "face_value": 200.0
 },
 {
  "symbol": "IDBI",
  "company_name": "IDBI BANK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE008A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "IDBIGOINAV",
  "company_name": "IDBIGOLD NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000041",
  "face_value": 10000.0
 },
 {
  "symbol": "IDEA",
  "company_name": "VODAFONE IDEA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE669E01016",
  "face_value": 1000.0
 },
 {
  "symbol": "IDEAFORGE",
  "company_name": "IDEAFORGE TECHNO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE349Y01013",
  "face_value": 1000.0
 },
 {
  "symbol": "IDFC",
  "company_name": "IDFC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE043D01016",
  "face_value": 1000.0
 },
 {
  "symbol": "IDFCFIRSTB",
  "company_name": "IDFC FIRST BANK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE092T01019",
  "face_value": 1000.0
 },
 {
  "symbol": "IDFNIFINAV",
  "company_name": "IDFNIFTYET INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000093",
  "face_value": 100.0
 },
 {
  "symbol": "IDFNIFTYET",
  "company_name": "BANDHANAMC - IDFNIFTYET",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF194KA1U07",
  "face_value": 1000.0
 },
 {
  "symbol": "IDLCHEM",
  "company_name": "IDL INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE077F01027",
  "face_value": 1000.0
 },
 {
  "symbol": "IEL",
  "company_name": "INDIABULLS ENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE059901020",
  "face_value": 200.0
 },
 {
  "symbol": "IEX",
  "company_name": "INDIAN ENERGY EXC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE022Q01020",
  "face_value": 100.0
 },
 {
  "symbol": "IFBAGRO",
  "company_name": "IFB AGRO INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE076C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "IFBIND",
  "company_name": "IFB INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE559A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "IFBVENTUR",
  "company_name": "IFB VENTURE CAPITAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE455201017",
  "face_value": 1000.0
 },
 {
  "symbol": "IFCI",
  "company_name": "IFCI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE039A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "IFGLEXPOR",
  "company_name": "IFGL REFRACTORIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE133Y01011",
  "face_value": 1000.0
 },
 {
  "symbol": "IGARASHI",
  "company_name": "IGARASHI MOTORS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE188B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "IGCL",
  "company_name": "INDOGULF CROPSCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE05J901018",
  "face_value": 1000.0
 },
 {
  "symbol": "IGGIRESORT",
  "company_name": "IGGI RESORTS INTL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE166601018",
  "face_value": 1000.0
 },
 {
  "symbol": "IGIL",
  "company_name": "INTERNATIO GEMM INS (I) L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0Q9301021",
  "face_value": 200.0
 },
 {
  "symbol": "IGL",
  "company_name": "INDRAPRASTHA GAS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE203G01027",
  "face_value": 200.0
 },
 {
  "symbol": "IGPL",
  "company_name": "I G PETROCHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE204A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "IHCL-RE",
  "company_name": "INDIAN HOTELS CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE053A20011",
  "face_value": 100.0
 },
 {
  "symbol": "IIFL",
  "company_name": "IIFL FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE530B01024",
  "face_value": 200.0
 },
 {
  "symbol": "IIFL-RE",
  "company_name": "IIFL FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE530B20016",
  "face_value": 200.0
 },
 {
  "symbol": "IIFLCAPS",
  "company_name": "IIFL CAPITAL SERVICES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE489L01022",
  "face_value": 200.0
 },
 {
  "symbol": "IITL",
  "company_name": "INDUSTRIAL INV TRUST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE886A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "IKIO",
  "company_name": "IKIO TECHNOLOGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0LOJ01019",
  "face_value": 1000.0
 },
 {
  "symbol": "IKS",
  "company_name": "INVENTURUS KNOWLEDGE SO L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE115Q01022",
  "face_value": 100.0
 },
 {
  "symbol": "IL&FSENGG",
  "company_name": "IL&FS ENG AND CONS CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE369I01014",
  "face_value": 1000.0
 },
 {
  "symbol": "IL&FSTRANS",
  "company_name": "IL&FS TRANS NET LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE975G01012",
  "face_value": 1000.0
 },
 {
  "symbol": "IMAGICAA",
  "company_name": "IMAGICAAWORLD ENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE172N01012",
  "face_value": 1000.0
 },
 {
  "symbol": "IMFA",
  "company_name": "INDIAN METALS & FERRO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE919H01018",
  "face_value": 1000.0
 },
 {
  "symbol": "IMPAL",
  "company_name": "IND MOTOR PART & ACC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE547E01014",
  "face_value": 1000.0
 },
 {
  "symbol": "IMPEXFERRO",
  "company_name": "IMPEX FERRO TECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE691G01015",
  "face_value": 1000.0
 },
 {
  "symbol": "INA",
  "company_name": "INSOLATION ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0LGX01024",
  "face_value": 100.0
 },
 {
  "symbol": "INCREDIBLE",
  "company_name": "INCREDIBLE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE452L01012",
  "face_value": 1000.0
 },
 {
  "symbol": "INDAIRYSPE",
  "company_name": "INDIANA DAIRY SPEC. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE158101019",
  "face_value": 1000.0
 },
 {
  "symbol": "INDAL",
  "company_name": "INDIAN ALUMINIUM CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE249A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "INDBANK",
  "company_name": "INDBANK MERCH BANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE841B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "INDBIOFOOD",
  "company_name": "INDO BIOTECH FOODS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE159001010",
  "face_value": 1000.0
 },
 {
  "symbol": "INDGN",
  "company_name": "INDEGENE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE065X01017",
  "face_value": 200.0
 },
 {
  "symbol": "INDHOTEL",
  "company_name": "THE INDIAN HOTELS CO. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE053A01029",
  "face_value": 100.0
 },
 {
  "symbol": "INDIACEM",
  "company_name": "THE INDIA CEMENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE383A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "INDIAGLYCO",
  "company_name": "INDIA GLYCOLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE560A01023",
  "face_value": 500.0
 },
 {
  "symbol": "INDIALEASE",
  "company_name": "INDIA LEASE DEVELOPMENT L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE162101013",
  "face_value": 1000.0
 },
 {
  "symbol": "INDIAMART",
  "company_name": "INDIAMART INTERMESH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE933S01016",
  "face_value": 1000.0
 },
 {
  "symbol": "INDIANACRY",
  "company_name": "INDIAN ACRYLICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE862B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "INDIANB",
  "company_name": "INDIAN BANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE562A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "INDIANCARD",
  "company_name": "INDIAN CARD CLOTHING CO.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE061A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "INDIANHUME",
  "company_name": "INDIAN HUME PIPE CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE323C01030",
  "face_value": 200.0
 },
 {
  "symbol": "INDIANORG",
  "company_name": "INDIAN ORGANIC CHEMICAL L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE564A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "INDIAPHOTO",
  "company_name": "KODAK INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE377A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "INDIASEC",
  "company_name": "INDIA SECURITIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE134A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "INDIASHLTR",
  "company_name": "INDIA SHELTER FIN CORP L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE922K01024",
  "face_value": 500.0
 },
 {
  "symbol": "INDIGO",
  "company_name": "INTERGLOBE AVIATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE646L01027",
  "face_value": 1000.0
 },
 {
  "symbol": "INDIGOPNTS",
  "company_name": "INDIGO PAINTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE09VQ01012",
  "face_value": 1000.0
 },
 {
  "symbol": "INDIQUBE",
  "company_name": "INDIQUBE SPACES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE06ST01018",
  "face_value": 100.0
 },
 {
  "symbol": "INDLMETER",
  "company_name": "IMP POWERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE065B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "INDNIPPON",
  "company_name": "INDIA NIPPON ELECT  LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE092B01025",
  "face_value": 500.0
 },
 {
  "symbol": "INDO-RE",
  "company_name": "INDOWIND ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE227G20018",
  "face_value": 1000.0
 },
 {
  "symbol": "INDO-RE1",
  "company_name": "INDOWIND ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE227G20026",
  "face_value": 1000.0
 },
 {
  "symbol": "INDO-RE2",
  "company_name": "INDOWIND ENERGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE227G20034",
  "face_value": 1000.0
 },
 {
  "symbol": "INDOAMIN",
  "company_name": "INDO AMINES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE760F01028",
  "face_value": 500.0
 },
 {
  "symbol": "INDOASAHI",
  "company_name": "INDO ASAHI GLASS CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE158701016",
  "face_value": 1000.0
 },
 {
  "symbol": "INDOBORAX",
  "company_name": "INDO BORAX & CHEMICAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE803D01021",
  "face_value": 100.0
 },
 {
  "symbol": "INDOCO",
  "company_name": "INDOCO REMEDIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE873D01024",
  "face_value": 200.0
 },
 {
  "symbol": "INDOCOUNT",
  "company_name": "INDO COUNT IND. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE483B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "INDOFARM",
  "company_name": "INDO FARM EQUIPMENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE622H01018",
  "face_value": 1000.0
 },
 {
  "symbol": "INDOFREBIO",
  "company_name": "INDO-FRENCH BIOTECH ENTER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE159701015",
  "face_value": 1000.0
 },
 {
  "symbol": "INDOMATAPP",
  "company_name": "INDO MATSUSHITA APP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE160401019",
  "face_value": 1000.0
 },
 {
  "symbol": "INDORAMA",
  "company_name": "INDO RAMA SYNTHETICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE156A01020",
  "face_value": 1000.0
 },
 {
  "symbol": "INDORAMSYN",
  "company_name": "INDO RAMA SYNTHETICS (I)",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE156A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "INDOSTAR",
  "company_name": "INDOSTAR CAPITAL FIN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE896L01010",
  "face_value": 1000.0
 },
 {
  "symbol": "INDOTECH",
  "company_name": "INDO TECH TRANSFORM LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE332H01014",
  "face_value": 1000.0
 },
 {
  "symbol": "INDOTHAI",
  "company_name": "INDO THAI SEC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE337M01021",
  "face_value": 100.0
 },
 {
  "symbol": "INDOUS",
  "company_name": "INDO US BIOTECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE250Z01010",
  "face_value": 1000.0
 },
 {
  "symbol": "INDOWIND",
  "company_name": "INDOWIND ENERGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE227G01018",
  "face_value": 1000.0
 },
 {
  "symbol": "INDOZINC",
  "company_name": "INDO ZINC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE160901018",
  "face_value": 1000.0
 },
 {
  "symbol": "INDPRUD",
  "company_name": "INDUSTRIAL & PRU INV CO L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE620D01011",
  "face_value": 1000.0
 },
 {
  "symbol": "INDRAMEDCO",
  "company_name": "INDRAPRASTHA MEDICAL CORP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE681B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "INDRATNA",
  "company_name": "IND RATNA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE457501018",
  "face_value": 1000.0
 },
 {
  "symbol": "INDSEAMFIN",
  "company_name": "INDIAN SEAMLESS FIN SERV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE164101011",
  "face_value": 1000.0
 },
 {
  "symbol": "INDSTMSHIP",
  "company_name": "INDIA STEAMSHIP CO LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE162601012",
  "face_value": 1000.0
 },
 {
  "symbol": "INDSWFTLAB",
  "company_name": "IND SWIFT LABORATORIES LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE915B01019",
  "face_value": 1000.0
 },
 {
  "symbol": "INDSWFTLTD",
  "company_name": "IND-SWIFT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE788B01028",
  "face_value": 200.0
 },
 {
  "symbol": "INDTERRAIN",
  "company_name": "IND TERRAIN FASHIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE611L01021",
  "face_value": 200.0
 },
 {
  "symbol": "INDTRADECO",
  "company_name": "IND TRA DECO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE455501010",
  "face_value": 1000.0
 },
 {
  "symbol": "INDUNISSAN",
  "company_name": "INDU NISSAN OXO CHEM IND.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE155401016",
  "face_value": 1000.0
 },
 {
  "symbol": "INDUSFILA",
  "company_name": "INDUSFILALIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE025I01012",
  "face_value": 1000.0
 },
 {
  "symbol": "INDUSINDBK",
  "company_name": "INDUSIND BANK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE095A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "INDUSTOWER",
  "company_name": "INDUS TOWERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE121J01017",
  "face_value": 1000.0
 },
 {
  "symbol": "INDYESTUF",
  "company_name": "IDI LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE888A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "INERTIAIND",
  "company_name": "INERTIA INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE155901015",
  "face_value": 1000.0
 },
 {
  "symbol": "INFARINDIA",
  "company_name": "INFAR (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE568A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "INFIBE-RE",
  "company_name": "INFIBEAM AVENUES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE483S20012",
  "face_value": 100.0
 },
 {
  "symbol": "INFOBEAN",
  "company_name": "INFOBEANS TECHNO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE344S01016",
  "face_value": 1000.0
 },
 {
  "symbol": "INFOMEDIA",
  "company_name": "INFOMEDIA PRESS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE669A01022",
  "face_value": 1000.0
 },
 {
  "symbol": "INFRA",
  "company_name": "MIRAEAMC - INFRA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01QB4",
  "face_value": 1000.0
 },
 {
  "symbol": "INFRABEES",
  "company_name": "NIP IND ETF INFRA BEES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF732E01268",
  "face_value": 1000.0
 },
 {
  "symbol": "INFRABENAV",
  "company_name": "INFRA BEES NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000022",
  "face_value": 1000.0
 },
 {
  "symbol": "INFRAIETF",
  "company_name": "ICICIPRAMC - ICICIINFRA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC16E5",
  "face_value": 1000.0
 },
 {
  "symbol": "INFRAINAV",
  "company_name": "MIRAEAMC - INFRAINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000335",
  "face_value": 1000.0
 },
 {
  "symbol": "INFY",
  "company_name": "INFOSYS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE009A01021",
  "face_value": 500.0
 },
 {
  "symbol": "INGERRAND",
  "company_name": "INGERSOLL-RAND INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE177A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "INNOVACAP",
  "company_name": "INNOVA CAPTAB LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0DUT01020",
  "face_value": 1000.0
 },
 {
  "symbol": "INNOVANA",
  "company_name": "INNOVANA THINKLABS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE403Y01018",
  "face_value": 1000.0
 },
 {
  "symbol": "INNOVISION",
  "company_name": "INNOVISION LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0ADB01012",
  "face_value": 1000.0
 },
 {
  "symbol": "INOVATMARN",
  "company_name": "INNOVATIVE MARINE FOODS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE156701018",
  "face_value": 1000.0
 },
 {
  "symbol": "INOXGREEN",
  "company_name": "INOX GREEN ENERGY SER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE510W01014",
  "face_value": 1000.0
 },
 {
  "symbol": "INOXINDIA",
  "company_name": "INOX INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE616N01034",
  "face_value": 200.0
 },
 {
  "symbol": "INOXLEISUR",
  "company_name": "INOX LEISURE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE312H01016",
  "face_value": 1000.0
 },
 {
  "symbol": "INOXWI-RE",
  "company_name": "INOX WIND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE066P20011",
  "face_value": 1000.0
 },
 {
  "symbol": "INOXWIND",
  "company_name": "INOX WIND LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE066P01011",
  "face_value": 1000.0
 },
 {
  "symbol": "INSECTICID",
  "company_name": "INSECTICIDES (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE070I01018",
  "face_value": 1000.0
 },
 {
  "symbol": "INSILCO",
  "company_name": "INSILCO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE901A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "INSPIRISYS",
  "company_name": "INSPIRISYS SOLUTIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE020G01017",
  "face_value": 1000.0
 },
 {
  "symbol": "INTCOMTECH",
  "company_name": "ICES SOFTWARE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE152901018",
  "face_value": 1000.0
 },
 {
  "symbol": "INTEGRFIN",
  "company_name": "INTEGRATED FINANCE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE157801015",
  "face_value": 1000.0
 },
 {
  "symbol": "INTELLECT",
  "company_name": "INTELLECT DESIGN ARENA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE306R01017",
  "face_value": 500.0
 },
 {
  "symbol": "INTENTECH",
  "company_name": "INTENSE TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE781A01025",
  "face_value": 200.0
 },
 {
  "symbol": "INTERARCH",
  "company_name": "INTERARCH BLDNG SOLTN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00M901018",
  "face_value": 1000.0
 },
 {
  "symbol": "INTERNET",
  "company_name": "MIRAEAMC - INTERNET",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01PB6",
  "face_value": 1000.0
 },
 {
  "symbol": "INTERNINAV",
  "company_name": "MIRAEAMC - INTERNINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000288",
  "face_value": 1000.0
 },
 {
  "symbol": "INTLCONV",
  "company_name": "INTL CONVEYORS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE575C01027",
  "face_value": 100.0
 },
 {
  "symbol": "INTLTRAVHS",
  "company_name": "INTERNATIONAL TRAVEL HOUS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE262B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "INVELTRANS",
  "company_name": "GKN DRIVESHAFTS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE527A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "INVENT-RE",
  "company_name": "INVENTURE GRO & SEC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE878H20016",
  "face_value": 100.0
 },
 {
  "symbol": "INVENTURE",
  "company_name": "INVENTURE GRO & SEC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE878H01024",
  "face_value": 100.0
 },
 {
  "symbol": "INVPRECQ",
  "company_name": "INVESTMENT & PREC CAST L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE155E01016",
  "face_value": 1000.0
 },
 {
  "symbol": "IOB",
  "company_name": "INDIAN OVERSEAS BANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE565A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "IOC",
  "company_name": "INDIAN OIL CORP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE242A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "IOLCP",
  "company_name": "IOL CHEM AND PHARMA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE485C01029",
  "face_value": 200.0
 },
 {
  "symbol": "IONEXCHANG",
  "company_name": "ION EXCHANGE (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE570A01022",
  "face_value": 100.0
 },
 {
  "symbol": "IPCALAB",
  "company_name": "IPCA LABORATORIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE571A01038",
  "face_value": 100.0
 },
 {
  "symbol": "IPL",
  "company_name": "INDIA PESTICIDES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0D6701023",
  "face_value": 100.0
 },
 {
  "symbol": "IPRINGS",
  "company_name": "I P RINGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE558A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "IRB",
  "company_name": "IRB INFRA DEV LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE821I01022",
  "face_value": 100.0
 },
 {
  "symbol": "IRCON",
  "company_name": "IRCON INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE962Y01021",
  "face_value": 200.0
 },
 {
  "symbol": "IRCTC",
  "company_name": "INDIAN RAIL TOUR CORP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE335Y01020",
  "face_value": 200.0
 },
 {
  "symbol": "IREDA",
  "company_name": "INDIAN RENEWABLE ENERGY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE202E01016",
  "face_value": 1000.0
 },
 {
  "symbol": "IRFC",
  "company_name": "INDIAN RAILWAY FIN CORP L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE053F01010",
  "face_value": 1000.0
 },
 {
  "symbol": "IRIS",
  "company_name": "IRIS REGTECH SOLUTION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE864K01010",
  "face_value": 1000.0
 },
 {
  "symbol": "IRIS-RE",
  "company_name": "IRIS CLOTHINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01GN20017",
  "face_value": 200.0
 },
 {
  "symbol": "IRISDOREME",
  "company_name": "IRIS CLOTHINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01GN01025",
  "face_value": 200.0
 },
 {
  "symbol": "IRMENERGY",
  "company_name": "IRM ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE07U701015",
  "face_value": 1000.0
 },
 {
  "symbol": "ISEC",
  "company_name": "ICICI SECURITIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE763G01038",
  "face_value": 500.0
 },
 {
  "symbol": "ISFT",
  "company_name": "INTRASOFT TECH. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE566K01011",
  "face_value": 1000.0
 },
 {
  "symbol": "ISGEC",
  "company_name": "ISGEC HEAVY ENG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE858B01029",
  "face_value": 100.0
 },
 {
  "symbol": "ISHANCH",
  "company_name": "ISHAN DYES N CHEMICALS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE561M01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ISIBARS",
  "company_name": "ISIBARS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE072A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "ISMTLTD",
  "company_name": "ISMT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE732F01019",
  "face_value": 500.0
 },
 {
  "symbol": "ISPATALLOY",
  "company_name": "ISPAT ALLOYS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE458501017",
  "face_value": 1000.0
 },
 {
  "symbol": "ISSAL",
  "company_name": "INDIAN SEAMLESS STEELS &",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE879C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "ISWARMEDIC",
  "company_name": "ISHWAR MEDICAL SERVICES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE458401010",
  "face_value": 1000.0
 },
 {
  "symbol": "IT",
  "company_name": "KOTAKMAMC - KOTAKIT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1GC5",
  "face_value": 1000.0
 },
 {
  "symbol": "ITADD",
  "company_name": "DSPAMC - DSPIT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1SX1",
  "face_value": 1000.0
 },
 {
  "symbol": "ITBEES",
  "company_name": "NIP IND ETF IT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KB15V2",
  "face_value": 1000.0
 },
 {
  "symbol": "ITBEESINAV",
  "company_name": "ITBEES INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000127",
  "face_value": 100.0
 },
 {
  "symbol": "ITBETA",
  "company_name": "UTIAMC-ITBETA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF789F1AZD8",
  "face_value": 1000.0
 },
 {
  "symbol": "ITC",
  "company_name": "ITC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE154A01025",
  "face_value": 100.0
 },
 {
  "symbol": "ITCHOTELS",
  "company_name": "ITC HOTELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE379A01028",
  "face_value": 100.0
 },
 {
  "symbol": "ITDC",
  "company_name": "INDIA TOUR. DEV. CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE353K01014",
  "face_value": 1000.0
 },
 {
  "symbol": "ITETF",
  "company_name": "MIRAEAMC - ITETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01KV5",
  "face_value": 1000.0
 },
 {
  "symbol": "ITETFINAV",
  "company_name": "MIRAEAMC - ITETFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000201",
  "face_value": 1000.0
 },
 {
  "symbol": "ITI",
  "company_name": "ITI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE248A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ITIETF",
  "company_name": "ICICIPRAMC - ICICITECH",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC16I6",
  "face_value": 100.0
 },
 {
  "symbol": "ITWSIGNODE",
  "company_name": "ITW SIGNODE INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE240A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "IVALUE",
  "company_name": "IVALUE INFOSOLUTIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE056801025",
  "face_value": 200.0
 },
 {
  "symbol": "IVC",
  "company_name": "IL&FS INVESTMENT MANAGERS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE050B01023",
  "face_value": 200.0
 },
 {
  "symbol": "IVP",
  "company_name": "IVP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE043C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "IVRCLINFRA",
  "company_name": "IVRCL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE875A01025",
  "face_value": 200.0
 },
 {
  "symbol": "IVZINGINAV",
  "company_name": "IVZINGOLD NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000042",
  "face_value": 10000.0
 },
 {
  "symbol": "IVZINGOLD",
  "company_name": "INVESCO INDIA GOLD ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF205K01361",
  "face_value": 10000.0
 },
 {
  "symbol": "IVZINNIFTY",
  "company_name": "INVESCO INDIA NIFTY ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF205K01DA9",
  "face_value": 1000.0
 },
 {
  "symbol": "IVZINNINAV",
  "company_name": "IVZINNIFTY INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000095",
  "face_value": 100.0
 },
 {
  "symbol": "IWEL",
  "company_name": "INOX WIND ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0FLR01028",
  "face_value": 1000.0
 },
 {
  "symbol": "IWP",
  "company_name": "INDIAN WOOD PRODUCTS CO L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE586E01020",
  "face_value": 200.0
 },
 {
  "symbol": "IXIGO",
  "company_name": "LE TRAVENUES TECHNOLOGY L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0HV901016",
  "face_value": 100.0
 },
 {
  "symbol": "IZMO",
  "company_name": "IZMO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE848A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "J&KBANK",
  "company_name": "J & K BANK LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE168A01041",
  "face_value": 100.0
 },
 {
  "symbol": "JAGAJITIND",
  "company_name": "JAGATJIT INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE574A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "JAGRAN",
  "company_name": "JAGRAN PRAKASHAN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE199G01027",
  "face_value": 200.0
 },
 {
  "symbol": "JAGSNPHARM",
  "company_name": "JAGSONPAL PHARMACEUTICALS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE048B01035",
  "face_value": 200.0
 },
 {
  "symbol": "JAIBALAJI",
  "company_name": "JAI BALAJI INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE091G01026",
  "face_value": 200.0
 },
 {
  "symbol": "JAICORPLTD",
  "company_name": "JAI CORP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE070D01027",
  "face_value": 100.0
 },
 {
  "symbol": "JAIHINDPRO",
  "company_name": "JAIHIND PROJECTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE343D01010",
  "face_value": 1000.0
 },
 {
  "symbol": "JAINPLAST",
  "company_name": "JAIN PLASTICS & CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE145901018",
  "face_value": 1000.0
 },
 {
  "symbol": "JAINREC",
  "company_name": "JAIN RESOURCE RECYCLING L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0YD401026",
  "face_value": 200.0
 },
 {
  "symbol": "JAINSTUDIO",
  "company_name": "JAIN STUDIOS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE486B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "JAIPARBOLI",
  "company_name": "JAI PARABOLIC SPRINGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE686B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "JAIPURKURT",
  "company_name": "NANDANI CREATION LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE696V01013",
  "face_value": 1000.0
 },
 {
  "symbol": "JALANFORG",
  "company_name": "JALAN FORGINGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE146501015",
  "face_value": 1000.0
 },
 {
  "symbol": "JAMNAAUTO",
  "company_name": "JAMNA AUTO IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE039C01032",
  "face_value": 100.0
 },
 {
  "symbol": "JAMNAUTO",
  "company_name": "JAMNA AUTO IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE147001015",
  "face_value": 1000.0
 },
 {
  "symbol": "JARO",
  "company_name": "JARO INS OF TEC MG N RE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00YJ01010",
  "face_value": 1000.0
 },
 {
  "symbol": "JASCHIND",
  "company_name": "JASCH INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE147601012",
  "face_value": 1000.0
 },
 {
  "symbol": "JASH",
  "company_name": "JASH ENGINEERING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE039O01029",
  "face_value": 200.0
 },
 {
  "symbol": "JASWALGRAN",
  "company_name": "JASWAL GRANITES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE147801018",
  "face_value": 1000.0
 },
 {
  "symbol": "JAYAGROGN",
  "company_name": "JAYANT AGRO ORGANICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE785A01026",
  "face_value": 500.0
 },
 {
  "symbol": "JAYBARMARU",
  "company_name": "JAY BHARAT MARUTI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE571B01036",
  "face_value": 200.0
 },
 {
  "symbol": "JAYBUSMAC",
  "company_name": "JAYANTI BUSINESS MACHINES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE142501019",
  "face_value": 1000.0
 },
 {
  "symbol": "JAYDYSTUF",
  "company_name": "JAYSYNTH DYESTUFF (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE142901011",
  "face_value": 1000.0
 },
 {
  "symbol": "JAYKAY",
  "company_name": "JAYKAY ENTERPRISES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE903A01025",
  "face_value": 100.0
 },
 {
  "symbol": "JAYNECOIND",
  "company_name": "JAYASWAL NECO INDUSTR LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE854B01010",
  "face_value": 1000.0
 },
 {
  "symbol": "JAYSREETEA",
  "company_name": "JAYSHREE TEA & INDUSTRIES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE364A01020",
  "face_value": 500.0
 },
 {
  "symbol": "JBCHEPHARM",
  "company_name": "J B CHEMICALS AND PHARMA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE572A01036",
  "face_value": 100.0
 },
 {
  "symbol": "JBFIND",
  "company_name": "JBF INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE187A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "JBMA",
  "company_name": "JBM AUTO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE927D01051",
  "face_value": 100.0
 },
 {
  "symbol": "JCT",
  "company_name": "JCT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE945A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "JERSY",
  "company_name": "JERSY INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE143501018",
  "face_value": 1000.0
 },
 {
  "symbol": "JETAIRWAYS",
  "company_name": "JET AIRWAYS (INDIA) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE802G01018",
  "face_value": 1000.0
 },
 {
  "symbol": "JETFRE-RE",
  "company_name": "JET FREIGHT LOGISTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE982V20017",
  "face_value": 500.0
 },
 {
  "symbol": "JETFREIGHT",
  "company_name": "JET FREIGHT LOGISTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE982V01025",
  "face_value": 500.0
 },
 {
  "symbol": "JFLABS",
  "company_name": "JF LABORATORIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE226C01019",
  "face_value": 1000.0
 },
 {
  "symbol": "JGCHEM",
  "company_name": "J.G.CHEMICALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0MB501011",
  "face_value": 1000.0
 },
 {
  "symbol": "JHS",
  "company_name": "JHS SVEND. LAB. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE544H01014",
  "face_value": 1000.0
 },
 {
  "symbol": "JIKIND",
  "company_name": "JIK INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE026B01049",
  "face_value": 1000.0
 },
 {
  "symbol": "JINDALDRUG",
  "company_name": "JINDAL DRUGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE459101015",
  "face_value": 1000.0
 },
 {
  "symbol": "JINDALPHOT",
  "company_name": "JINDAL PHOTO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE796G01012",
  "face_value": 1000.0
 },
 {
  "symbol": "JINDALPOLY",
  "company_name": "JINDAL POLY FILMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE197D01010",
  "face_value": 1000.0
 },
 {
  "symbol": "JINDALSAW",
  "company_name": "JINDAL SAW LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE324A01032",
  "face_value": 100.0
 },
 {
  "symbol": "JINDALSTEL",
  "company_name": "JINDAL STEEL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE749A01030",
  "face_value": 100.0
 },
 {
  "symbol": "JINDCOT",
  "company_name": "JINDAL COTEX LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE904J01016",
  "face_value": 1000.0
 },
 {
  "symbol": "JINDRILL",
  "company_name": "JINDAL DRILLING IND. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE742C01031",
  "face_value": 500.0
 },
 {
  "symbol": "JINDWORLD",
  "company_name": "JINDAL WORLDWIDE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE247D01039",
  "face_value": 100.0
 },
 {
  "symbol": "JIOFIN",
  "company_name": "JIO FIN SERVICES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE758E01017",
  "face_value": 1000.0
 },
 {
  "symbol": "JISLDVREQS",
  "company_name": "JAIN DVR EQUITY SHARES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "IN9175A01010",
  "face_value": 200.0
 },
 {
  "symbol": "JISLJALEQS",
  "company_name": "JAIN IRRIGATION SYSTEMS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE175A01038",
  "face_value": 200.0
 },
 {
  "symbol": "JITFINFRA",
  "company_name": "JITF INFRALOGISTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE863T01013",
  "face_value": 200.0
 },
 {
  "symbol": "JIYAECO",
  "company_name": "JIYA ECO-PRODUCTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE023S01016",
  "face_value": 1000.0
 },
 {
  "symbol": "JKCEMENT",
  "company_name": "JK CEMENT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE823G01014",
  "face_value": 1000.0
 },
 {
  "symbol": "JKCORP",
  "company_name": "JK CORP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE786A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "JKDAIRY",
  "company_name": "JK DAIRY AND FOODS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE458701013",
  "face_value": 1000.0
 },
 {
  "symbol": "JKIL",
  "company_name": "JKUMAR INFR.LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE576I01022",
  "face_value": 500.0
 },
 {
  "symbol": "JKIND",
  "company_name": "JK INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE573A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "JKIPL",
  "company_name": "JINKUSHAL INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1FF001016",
  "face_value": 1000.0
 },
 {
  "symbol": "JKLAKSHMI",
  "company_name": "JK LAKSHMI CEMENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE786A01032",
  "face_value": 500.0
 },
 {
  "symbol": "JKPAPER",
  "company_name": "JK PAPER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE789E01012",
  "face_value": 1000.0
 },
 {
  "symbol": "JKPHARMA",
  "company_name": "J K PHARMACHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE335C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "JKSYNTHETC",
  "company_name": "JK SYNTHETICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE150501018",
  "face_value": 1000.0
 },
 {
  "symbol": "JKTYRE",
  "company_name": "JK TYRE & INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE573A01042",
  "face_value": 200.0
 },
 {
  "symbol": "JKUDYOG",
  "company_name": "JK UDAIPUR UDYOG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE225C01011",
  "face_value": 1000.0
 },
 {
  "symbol": "JLHL",
  "company_name": "JUPITER LIFE LINE HOSP L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE682M01012",
  "face_value": 1000.0
 },
 {
  "symbol": "JMA",
  "company_name": "JULLUNDUR MOT AGENCY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE412C01023",
  "face_value": 200.0
 },
 {
  "symbol": "JMCPROJECT",
  "company_name": "JMC PROJECTS (I) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE890A01024",
  "face_value": 200.0
 },
 {
  "symbol": "JMFINANCIL",
  "company_name": "JM FINANCIAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE780C01023",
  "face_value": 100.0
 },
 {
  "symbol": "JMSHARE",
  "company_name": "J M SHARE AND STOCK BROKE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE150801012",
  "face_value": 1000.0
 },
 {
  "symbol": "JMTAUTOLTD",
  "company_name": "JMT AUTO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE988E01036",
  "face_value": 100.0
 },
 {
  "symbol": "JNKINDIA",
  "company_name": "JNK INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0OAF01028",
  "face_value": 200.0
 },
 {
  "symbol": "JOCIL",
  "company_name": "JOCIL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE839G01010",
  "face_value": 1000.0
 },
 {
  "symbol": "JORDENGG",
  "company_name": "JORD ENGINEERS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE138601013",
  "face_value": 1000.0
 },
 {
  "symbol": "JPASSOCIAT",
  "company_name": "JAIPRAKASH ASSOCIATES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE455F01025",
  "face_value": 200.0
 },
 {
  "symbol": "JPINFRATEC",
  "company_name": "JAYPEE INFRATECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE099J01015",
  "face_value": 1000.0
 },
 {
  "symbol": "JPOLYINVST",
  "company_name": "JIND POL INV & FIN CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE147P01019",
  "face_value": 1000.0
 },
 {
  "symbol": "JPPOWER",
  "company_name": "JAIPRAKASH POWER VEN. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE351F01018",
  "face_value": 1000.0
 },
 {
  "symbol": "JSFB",
  "company_name": "JANA SMALL FIN BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE953L01027",
  "face_value": 1000.0
 },
 {
  "symbol": "JSL",
  "company_name": "JINDAL STAINLESS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE220G01021",
  "face_value": 200.0
 },
 {
  "symbol": "JSLHISAR",
  "company_name": "JINDAL STAINLESS (H) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE455T01018",
  "face_value": 200.0
 },
 {
  "symbol": "JSLL",
  "company_name": "JEENA SIKHO LIFECARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0J5801029",
  "face_value": 200.0
 },
 {
  "symbol": "JSWCEMENT",
  "company_name": "JSW CEMENT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE718I01012",
  "face_value": 1000.0
 },
 {
  "symbol": "JSWDULUX",
  "company_name": "JSW DULUX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE133A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "JSWENERGY",
  "company_name": "JSW ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE121E01018",
  "face_value": 1000.0
 },
 {
  "symbol": "JSWHL",
  "company_name": "JSW HOLDINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE824G01012",
  "face_value": 1000.0
 },
 {
  "symbol": "JSWINFRA",
  "company_name": "JSW INFRASTRUCTURE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE880J01026",
  "face_value": 200.0
 },
 {
  "symbol": "JSWISPL",
  "company_name": "JSW ISPAT SPE PRO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE743C01021",
  "face_value": 1000.0
 },
 {
  "symbol": "JSWSTEEL",
  "company_name": "JSW STEEL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE019A01038",
  "face_value": 100.0
 },
 {
  "symbol": "JTEKT-RE",
  "company_name": "JTEKT INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE643A20019",
  "face_value": 100.0
 },
 {
  "symbol": "JTEKTINDIA",
  "company_name": "JTEKT INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE643A01035",
  "face_value": 100.0
 },
 {
  "symbol": "JTLIND",
  "company_name": "JTL INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE391J01032",
  "face_value": 100.0
 },
 {
  "symbol": "JUBLCPL",
  "company_name": "JUBILANT AGRI N CON PRO L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE03CC01015",
  "face_value": 1000.0
 },
 {
  "symbol": "JUBLFOOD",
  "company_name": "JUBILANT FOODWORKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE797F01020",
  "face_value": 200.0
 },
 {
  "symbol": "JUBLINDS",
  "company_name": "JUBILANT INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE645L01011",
  "face_value": 1000.0
 },
 {
  "symbol": "JUBLINGREA",
  "company_name": "JUBILANT INGREVIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0BY001018",
  "face_value": 100.0
 },
 {
  "symbol": "JUBLPHARMA",
  "company_name": "JUBILANT PHARMOVA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE700A01033",
  "face_value": 100.0
 },
 {
  "symbol": "JUNIORBEES",
  "company_name": "NIP IND ETF JUNIOR BEES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF732E01045",
  "face_value": 125.0
 },
 {
  "symbol": "JUNIPER",
  "company_name": "JUNIPER HOTELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE696F01016",
  "face_value": 1000.0
 },
 {
  "symbol": "JUNORBENAV",
  "company_name": "JUNIOR BEES NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000023",
  "face_value": 1000.0
 },
 {
  "symbol": "JUPITER",
  "company_name": "JUPITER BIOSCIENCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE918B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "JUSTDIAL",
  "company_name": "JUSTDIAL LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE599M01018",
  "face_value": 1000.0
 },
 {
  "symbol": "JVLAGRO",
  "company_name": "JVL AGRO INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE430G01026",
  "face_value": 100.0
 },
 {
  "symbol": "JWL",
  "company_name": "JUPITER WAGONS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE209L01016",
  "face_value": 1000.0
 },
 {
  "symbol": "JYOTHYLAB",
  "company_name": "JYOTHY LABS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE668F01031",
  "face_value": 100.0
 },
 {
  "symbol": "JYOTI-RE",
  "company_name": "JYOTI STRUCTURES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE197A20016",
  "face_value": 200.0
 },
 {
  "symbol": "JYOTI-RE1",
  "company_name": "JYOTI STRUCTURES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE197A20024",
  "face_value": 200.0
 },
 {
  "symbol": "JYOTICNC",
  "company_name": "JYOTI CNC AUTOMATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE980O01024",
  "face_value": 200.0
 },
 {
  "symbol": "JYOTISTRUC",
  "company_name": "JYOTI STRUCTURES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE197A01024",
  "face_value": 200.0
 },
 {
  "symbol": "KABRAEXTRU",
  "company_name": "KABRA EXTRUSION TECHNIK L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE900B01029",
  "face_value": 500.0
 },
 {
  "symbol": "KAJARIACER",
  "company_name": "KAJARIA CERAMICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE217B01036",
  "face_value": 100.0
 },
 {
  "symbol": "KAKATCEM",
  "company_name": "KAKATIYA CEM SUGAR &IND L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE437B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "KALAMANDIR",
  "company_name": "SAI SILKS (KALAMANDIR) L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE438K01021",
  "face_value": 200.0
 },
 {
  "symbol": "KALPATARU",
  "company_name": "KALPATARU LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE227J01012",
  "face_value": 1000.0
 },
 {
  "symbol": "KALYANI",
  "company_name": "KALYANI COMMERCIALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE610E01010",
  "face_value": 1000.0
 },
 {
  "symbol": "KALYANIFRG",
  "company_name": "KALYANI FORGE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE314G01014",
  "face_value": 1000.0
 },
 {
  "symbol": "KALYANISHP",
  "company_name": "KALYANI SHARP INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE207B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "KALYANISTL",
  "company_name": "KALYANI STEELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE907A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "KALYANKJIL",
  "company_name": "KALYAN JEWELLERS IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE303R01014",
  "face_value": 1000.0
 },
 {
  "symbol": "KAMAHOLD",
  "company_name": "KAMA HOLDINGS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE411F01010",
  "face_value": 1000.0
 },
 {
  "symbol": "KAMATHOTEL",
  "company_name": "KAMAT HOTELS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE967C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "KAMDHENU",
  "company_name": "KAMDHENU LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE390H01020",
  "face_value": 100.0
 },
 {
  "symbol": "KAMOPAINTS",
  "company_name": "KAMDHENU VENTURES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0BTI01037",
  "face_value": 100.0
 },
 {
  "symbol": "KANAKSTEEL",
  "company_name": "KANAKDHARA STEEL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE137801010",
  "face_value": 1000.0
 },
 {
  "symbol": "KANANIIND",
  "company_name": "KANANI INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE879E01037",
  "face_value": 100.0
 },
 {
  "symbol": "KANCHI",
  "company_name": "KANCHI KARPOORAM LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE081G01019",
  "face_value": 1000.0
 },
 {
  "symbol": "KANELOIL",
  "company_name": "KANEL OILS & EXPO. INDS.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE138101014",
  "face_value": 1000.0
 },
 {
  "symbol": "KANORICHEM",
  "company_name": "KANORIA CHEMICALS & INDUS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE138C01024",
  "face_value": 500.0
 },
 {
  "symbol": "KANPRPLA",
  "company_name": "KANPUR PLASTIPACK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE694E01014",
  "face_value": 1000.0
 },
 {
  "symbol": "KANSAINER",
  "company_name": "KANSAI NEROLAC PAINTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE531A01024",
  "face_value": 100.0
 },
 {
  "symbol": "KAPSTON",
  "company_name": "KAPSTON SERVICES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE542Z01028",
  "face_value": 500.0
 },
 {
  "symbol": "KARMAENG",
  "company_name": "KARMA ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE725L01011",
  "face_value": 1000.0
 },
 {
  "symbol": "KARURVYSYA",
  "company_name": "KARUR VYSYA BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE036D01028",
  "face_value": 200.0
 },
 {
  "symbol": "KAUSHALYA",
  "company_name": "KAUSHALYA INFRA DEV LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE234I01028",
  "face_value": 100000.0
 },
 {
  "symbol": "KAVDEFENCE",
  "company_name": "KAVVERI DFS & WIR TEC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE641C01019",
  "face_value": 1000.0
 },
 {
  "symbol": "KAYA",
  "company_name": "KAYA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE587G01015",
  "face_value": 1000.0
 },
 {
  "symbol": "KAYNES",
  "company_name": "KAYNES TECHNOLOGY IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE918Z01012",
  "face_value": 1000.0
 },
 {
  "symbol": "KCP",
  "company_name": "KCP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE805C01028",
  "face_value": 100.0
 },
 {
  "symbol": "KCPSUGIND",
  "company_name": "KCP SUGAR IND CORP LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE790B01024",
  "face_value": 100.0
 },
 {
  "symbol": "KDDL",
  "company_name": "KDDL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE291D01011",
  "face_value": 1000.0
 },
 {
  "symbol": "KDDL-RE",
  "company_name": "KDDL RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE291D20011",
  "face_value": 1000.0
 },
 {
  "symbol": "KEC",
  "company_name": "KEC INTL. LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE389H01022",
  "face_value": 200.0
 },
 {
  "symbol": "KECL",
  "company_name": "KIRLOSKAR ELECTRIC CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE134B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "KEEPLEARN",
  "company_name": "DSJ KEEP LEARNING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE055C01020",
  "face_value": 100.0
 },
 {
  "symbol": "KEEPLN-RE",
  "company_name": "DSJ KEEP LEARNING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE055C20012",
  "face_value": 100.0
 },
 {
  "symbol": "KEI",
  "company_name": "KEI INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE878B01027",
  "face_value": 200.0
 },
 {
  "symbol": "KELLTONTEC",
  "company_name": "KELLTON TECH SOL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE164B01030",
  "face_value": 100.0
 },
 {
  "symbol": "KENNAMET",
  "company_name": "KENNAMETAL INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE717A01029",
  "face_value": 1000.0
 },
 {
  "symbol": "KERALACHEM",
  "company_name": "KERALA CHEMICALS AND PROT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYY000002",
  "face_value": 1000.0
 },
 {
  "symbol": "KERNEX",
  "company_name": "KERNEX MICROSYS(I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE202H01019",
  "face_value": 1000.0
 },
 {
  "symbol": "KESORAMIND",
  "company_name": "KESORAM INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE087A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "KESWANISYN",
  "company_name": "KESWANI SYNTHETIC IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE130801017",
  "face_value": 1000.0
 },
 {
  "symbol": "KEYFINSERV",
  "company_name": "KEYNOTE FIN SERV LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE681C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "KFINTECH",
  "company_name": "KFIN TECHNOLOGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE138Y01010",
  "face_value": 1000.0
 },
 {
  "symbol": "KGDENIM",
  "company_name": "K G DENIM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE104A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "KGKHOSLA",
  "company_name": "KG KHOSLA COMPRESSORS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE811A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "KGL",
  "company_name": "KARUTURI GLOBAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE299C01024",
  "face_value": 100.0
 },
 {
  "symbol": "KHADIM",
  "company_name": "KHADIM INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE834I01025",
  "face_value": 1000.0
 },
 {
  "symbol": "KHAICHEM",
  "company_name": "KHAITAN CHEM & FERT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE745B01028",
  "face_value": 100.0
 },
 {
  "symbol": "KHAITANELE",
  "company_name": "KHAITAN ELECTRICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE761A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "KHAITANLTD",
  "company_name": "KHAITAN (INDIA)LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE731C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "KHANDSE",
  "company_name": "KHANDWALA SECURITIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE060B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "KHATJUNKER",
  "company_name": "INDOKEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE131901014",
  "face_value": 1000.0
 },
 {
  "symbol": "KICL",
  "company_name": "KALYANI INVEST CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE029L01018",
  "face_value": 1000.0
 },
 {
  "symbol": "KIL-RE",
  "company_name": "KESORAM INDUSTRIES LTD-RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE087A20019",
  "face_value": 1000.0
 },
 {
  "symbol": "KILBUNENGG",
  "company_name": "KILBURN ENGG. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE126501019",
  "face_value": 1000.0
 },
 {
  "symbol": "KILITC-RE",
  "company_name": "KILITCH DRUGS (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE729D20010",
  "face_value": 1000.0
 },
 {
  "symbol": "KILITCH",
  "company_name": "KILITCH DRUGS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE729D01010",
  "face_value": 1000.0
 },
 {
  "symbol": "KIMS",
  "company_name": "KRISHNA INST OF MED SCI L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE967H01025",
  "face_value": 200.0
 },
 {
  "symbol": "KINETICENG",
  "company_name": "KINETIC ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE266B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "KINGFA",
  "company_name": "KINGFA SCI & TEC IND LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE473D01015",
  "face_value": 1000.0
 },
 {
  "symbol": "KINGSINTL",
  "company_name": "KINGS INTERNATIONAL AQUA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE127201015",
  "face_value": 1000.0
 },
 {
  "symbol": "KIOCL",
  "company_name": "KIOCL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE880L01014",
  "face_value": 1000.0
 },
 {
  "symbol": "KIRANOVER",
  "company_name": "KIRAN OVERSEAS EXPORTS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE127401011",
  "face_value": 1000.0
 },
 {
  "symbol": "KIRANVYPAR",
  "company_name": "KIRAN VYAPAR LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE555P01013",
  "face_value": 1000.0
 },
 {
  "symbol": "KIRIINDUS",
  "company_name": "KIRI INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE415I01015",
  "face_value": 1000.0
 },
 {
  "symbol": "KIRLFER",
  "company_name": "KIRLOSKAR FERROUS IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE884B01025",
  "face_value": 500.0
 },
 {
  "symbol": "KIRLOSBROS",
  "company_name": "KIRLOSKAR BROTHERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE732A01036",
  "face_value": 200.0
 },
 {
  "symbol": "KIRLOSELEC",
  "company_name": "KIRLOSKAR ELECTRODYNE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE459501016",
  "face_value": 1000.0
 },
 {
  "symbol": "KIRLOSENG",
  "company_name": "KIRLOSKAR OIL ENG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE146L01010",
  "face_value": 200.0
 },
 {
  "symbol": "KIRLOSFERR",
  "company_name": "KIRLOSKAR FERROUS INDUSTR",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE884B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "KIRLOSIND",
  "company_name": "KIRLOSKAR INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE250A01039",
  "face_value": 1000.0
 },
 {
  "symbol": "KIRLOSINV",
  "company_name": "KIRLOSKAR INV. & FIN. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE195B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "KIRLOSPNEU",
  "company_name": "KIRLOSKAR PNEUMATIC CO. L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE328A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "KIRLPNU",
  "company_name": "KIRLOSKAR PNEUMATIC COM L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE811A01020",
  "face_value": 200.0
 },
 {
  "symbol": "KITEX",
  "company_name": "KITEX GARMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE602G01020",
  "face_value": 100.0
 },
 {
  "symbol": "KITSTEEL",
  "company_name": "KITTI STEELS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE128601015",
  "face_value": 1000.0
 },
 {
  "symbol": "KJINTL",
  "company_name": "KJ INTL. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE459201013",
  "face_value": 1000.0
 },
 {
  "symbol": "KKCL",
  "company_name": "KEWAL KIRAN CLOTHING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE401H01017",
  "face_value": 1000.0
 },
 {
  "symbol": "KLBRENG-B",
  "company_name": "KILBURN ENGINEERING LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE338F01015",
  "face_value": 1000.0
 },
 {
  "symbol": "KMEW",
  "company_name": "KNOWLEDGE MARINE & EN W L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0CJD01029",
  "face_value": 500.0
 },
 {
  "symbol": "KMSUGAR",
  "company_name": "K M SUGAR MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE157H01023",
  "face_value": 200.0
 },
 {
  "symbol": "KNAGRI",
  "company_name": "KN AGRI RESOURCES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0KNW01016",
  "face_value": 1000.0
 },
 {
  "symbol": "KNRCON",
  "company_name": "KNR CONSTRU LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE634I01029",
  "face_value": 200.0
 },
 {
  "symbol": "KOCONSINAV",
  "company_name": "KOTAKMAMC - KOCONSINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000152",
  "face_value": 1000.0
 },
 {
  "symbol": "KOHINOOR",
  "company_name": "KOHINOOR FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE080B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "KOKMNCINAV",
  "company_name": "KOTAKMAMC - KOTAKMNCINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000155",
  "face_value": 1000.0
 },
 {
  "symbol": "KOKUYOCMLN",
  "company_name": "KOKUYO CAMLIN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE760A01029",
  "face_value": 100.0
 },
 {
  "symbol": "KOLTEPATIL",
  "company_name": "KOLTE PATIL DEV. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE094I01018",
  "face_value": 1000.0
 },
 {
  "symbol": "KOPRAN",
  "company_name": "KOPRAN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE082A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "KOTAKAINAV",
  "company_name": "KOTAKALPHA INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000101",
  "face_value": 100.0
 },
 {
  "symbol": "KOTAKBANK",
  "company_name": "KOTAK MAHINDRA BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE237A01036",
  "face_value": 100.0
 },
 {
  "symbol": "KOTAKBINAV",
  "company_name": "KOTAKBKETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000096",
  "face_value": 100.0
 },
 {
  "symbol": "KOTAKGINAV",
  "company_name": "KOTAKGOLD NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000043",
  "face_value": 100.0
 },
 {
  "symbol": "KOTAKIINAV",
  "company_name": "KOTAKIT INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000099",
  "face_value": 100.0
 },
 {
  "symbol": "KOTAKLINAV",
  "company_name": "KOTAKLOVOL INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000103",
  "face_value": 100.0
 },
 {
  "symbol": "KOTAKMINAV",
  "company_name": "KOTAKMID50 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000100",
  "face_value": 100.0
 },
 {
  "symbol": "KOTAKNINAV",
  "company_name": "KOTAKNIFTY INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000102",
  "face_value": 100.0
 },
 {
  "symbol": "KOTAKPINAV",
  "company_name": "KOTAKPSUBK INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000098",
  "face_value": 100.0
 },
 {
  "symbol": "KOTAKSINAV",
  "company_name": "KOTAKMAMC - KOTAKSINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000170",
  "face_value": 1000.0
 },
 {
  "symbol": "KOTAKVINAV",
  "company_name": "KOTAKNV20 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000097",
  "face_value": 100.0
 },
 {
  "symbol": "KOTARISUG",
  "company_name": "KOTHARI SUG & CHEM LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE419A01022",
  "face_value": 1000.0
 },
 {
  "symbol": "KOTHARINDL",
  "company_name": "KOTHARI INDUSTRIAL CORPOR",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE972A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "KOTHARIPET",
  "company_name": "KOTHARI PETROCHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE720A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "KOTHARIPRO",
  "company_name": "KOTHARI PRODUCTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE823A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "KOTIC",
  "company_name": "KOTHARI INDUSTRIAL CORP L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE972A01020",
  "face_value": 500.0
 },
 {
  "symbol": "KOTLIQINAV",
  "company_name": "KOTAKMAMC - KOTLIQINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000175",
  "face_value": 100000.0
 },
 {
  "symbol": "KOTYARK",
  "company_name": "KOTYARK INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0J0B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "KOVAI",
  "company_name": "KOVAI MEDICAL CENTER & HO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE177F01017",
  "face_value": 1000.0
 },
 {
  "symbol": "KPEL",
  "company_name": "K.P. ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE127T01021",
  "face_value": 500.0
 },
 {
  "symbol": "KPIGREEN",
  "company_name": "KPI GREEN ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE542W01025",
  "face_value": 500.0
 },
 {
  "symbol": "KPIL",
  "company_name": "KALPATARU PROJECT INT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE220B01022",
  "face_value": 200.0
 },
 {
  "symbol": "KPITTECH",
  "company_name": "KPIT TECHNOLOGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE04I401011",
  "face_value": 1000.0
 },
 {
  "symbol": "KPL",
  "company_name": "KWALITY PHARMACEUTICALS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE552U01010",
  "face_value": 1000.0
 },
 {
  "symbol": "KPRMILL",
  "company_name": "KPR MILL LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE930H01031",
  "face_value": 100.0
 },
 {
  "symbol": "KRBL",
  "company_name": "KRBL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE001B01026",
  "face_value": 100.0
 },
 {
  "symbol": "KREBSBIO",
  "company_name": "KREBS BIOCHEMICALS & IND",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE268B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "KRIDHANINF",
  "company_name": "KRIDHAN INFRA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE524L01026",
  "face_value": 200.0
 },
 {
  "symbol": "KRISHANA",
  "company_name": "KRISHANA PHOSCHEM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE506W01012",
  "face_value": 1000.0
 },
 {
  "symbol": "KRISHFL-RE",
  "company_name": "KRISHIVAL FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0GGO20015",
  "face_value": 1000.0
 },
 {
  "symbol": "KRISHIVAL",
  "company_name": "KRISHIVAL FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0GGO01015",
  "face_value": 1000.0
 },
 {
  "symbol": "KRISHNADEF",
  "company_name": "KRISHNA DEF AND ALD IND L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0J5601015",
  "face_value": 1000.0
 },
 {
  "symbol": "KRISNAFILA",
  "company_name": "KRISHNA FILAMENTS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE073A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "KRITI",
  "company_name": "KRITI INDUSTRIES IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE479D01038",
  "face_value": 100.0
 },
 {
  "symbol": "KRITIKA",
  "company_name": "KRITIKA WIRES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00Z501029",
  "face_value": 200.0
 },
 {
  "symbol": "KRITINUT",
  "company_name": "KRITI NUTRIENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE798K01010",
  "face_value": 100.0
 },
 {
  "symbol": "KRN",
  "company_name": "KRN HEAT EXCHANGE N REF L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0Q3J01015",
  "face_value": 1000.0
 },
 {
  "symbol": "KRONECOMM",
  "company_name": "KRONE COMMUNICATIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE833A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "KRONOX",
  "company_name": "KRONOX LAB SCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0ATZ01017",
  "face_value": 1000.0
 },
 {
  "symbol": "KROSS",
  "company_name": "KROSS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0O6601022",
  "face_value": 500.0
 },
 {
  "symbol": "KRSNAA",
  "company_name": "KRSNAA DIAGNOSTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE08LI01020",
  "face_value": 500.0
 },
 {
  "symbol": "KRYSTAL",
  "company_name": "KRYSTAL INTEGRATED SER L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0QN801017",
  "face_value": 1000.0
 },
 {
  "symbol": "KSB",
  "company_name": "KSB LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE999A01023",
  "face_value": 200.0
 },
 {
  "symbol": "KSCL",
  "company_name": "KAVERI SEED CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE455I01029",
  "face_value": 200.0
 },
 {
  "symbol": "KSERASERA",
  "company_name": "KSS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE216D01026",
  "face_value": 100.0
 },
 {
  "symbol": "KSHINTL",
  "company_name": "KSH INTERNATIONAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE987S01020",
  "face_value": 500.0
 },
 {
  "symbol": "KSHITI-RE",
  "company_name": "KSHITIJ POLYLINE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE013820019",
  "face_value": 200.0
 },
 {
  "symbol": "KSHITIJPOL",
  "company_name": "KSHITIJ POLYLINE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE013801027",
  "face_value": 200.0
 },
 {
  "symbol": "KSK",
  "company_name": "KSK ENERGY VENTURES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE143H01015",
  "face_value": 1000.0
 },
 {
  "symbol": "KSL",
  "company_name": "KALYANI STEELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE907A01026",
  "face_value": 500.0
 },
 {
  "symbol": "KSOLVES",
  "company_name": "KSOLVES INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0D6I01023",
  "face_value": 500.0
 },
 {
  "symbol": "KSR",
  "company_name": "KSR FOOTWEAR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1SPP01016",
  "face_value": 1000.0
 },
 {
  "symbol": "KTKBANK",
  "company_name": "KARNATAKA BANK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE614B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "KUANTUM",
  "company_name": "KUANTUM PAPERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE529I01021",
  "face_value": 100.0
 },
 {
  "symbol": "KUNDANMM",
  "company_name": "KUNDAN MIN AND METALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE889B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "KUSUMINGOT",
  "company_name": "KUSUM INGOTS & ALLOYS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE121501014",
  "face_value": 1000.0
 },
 {
  "symbol": "KWALITY",
  "company_name": "KWALITY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE775B01025",
  "face_value": 100.0
 },
 {
  "symbol": "KWIL",
  "company_name": "KWALITY WALL'S (INDIA) L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE2KCE01013",
  "face_value": 100.0
 },
 {
  "symbol": "L&TFH-RE",
  "company_name": "L&T FIN HOLDINGS LTD RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE498L20015",
  "face_value": 1000.0
 },
 {
  "symbol": "LABHCONST",
  "company_name": "LABH CONSTRUCTION LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE116101010",
  "face_value": 1000.0
 },
 {
  "symbol": "LAGNAM",
  "company_name": "LAGNAM SPINTEX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE548Z01017",
  "face_value": 1000.0
 },
 {
  "symbol": "LAHOTIOV",
  "company_name": "LAHOTI OVERSEAS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE515C01023",
  "face_value": 200.0
 },
 {
  "symbol": "LAKHNNATNL",
  "company_name": "LAKHANPAL NATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE795A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "LAKPRE",
  "company_name": "LAKSHMI PRE SCRE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE651C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "LAKSELECON",
  "company_name": "LAKSHMI ELECT CONTROL SYS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE117401013",
  "face_value": 1000.0
 },
 {
  "symbol": "LAKSHMIEFL",
  "company_name": "LAKSHMI ENG. & FOODS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE992B01026",
  "face_value": 200.0
 },
 {
  "symbol": "LAKSHMILL",
  "company_name": "LAKSHMI MILLS CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE938C01019",
  "face_value": 10000.0
 },
 {
  "symbol": "LAKSHVILAS",
  "company_name": "LAKSHMI VILAS BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE694C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "LAL",
  "company_name": "LORENZINI APPARELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE740X01023",
  "face_value": 100.0
 },
 {
  "symbol": "LALPATHLAB",
  "company_name": "DR. LAL PATH LABS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE600L01024",
  "face_value": 1000.0
 },
 {
  "symbol": "LAMBODHARA",
  "company_name": "LAMBODHARA TEXTILES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE112F01022",
  "face_value": 500.0
 },
 {
  "symbol": "LANCER",
  "company_name": "LANCER CONTAINER LINE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE359U01028",
  "face_value": 500.0
 },
 {
  "symbol": "LANCOIND",
  "company_name": "LANCO INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE943C01019",
  "face_value": 1000.0
 },
 {
  "symbol": "LANCORHOL",
  "company_name": "LANCOR HOLDINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE572G01025",
  "face_value": 200.0
 },
 {
  "symbol": "LANDMARK",
  "company_name": "LANDMARK CARS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE559R01029",
  "face_value": 500.0
 },
 {
  "symbol": "LANDSMILL",
  "company_name": "LANDSMILL GREEN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE688J01023",
  "face_value": 100.0
 },
 {
  "symbol": "LAOPALA",
  "company_name": "LA OPALA RG LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE059D01020",
  "face_value": 200.0
 },
 {
  "symbol": "LASA",
  "company_name": "LASA SUPERGENERICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE670X01014",
  "face_value": 1000.0
 },
 {
  "symbol": "LATENTVIEW",
  "company_name": "LATENT VIEW ANALYTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0I7C01011",
  "face_value": 100.0
 },
 {
  "symbol": "LATTEYS",
  "company_name": "LATTEYS INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE262Z01023",
  "face_value": 200.0
 },
 {
  "symbol": "LAURUSLABS",
  "company_name": "LAURUS LABS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE947Q01028",
  "face_value": 200.0
 },
 {
  "symbol": "LAXMICOT",
  "company_name": "LAXMI COTSPIN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE801V01019",
  "face_value": 1000.0
 },
 {
  "symbol": "LAXMIDENTL",
  "company_name": "LAXMI DENTAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0WO601020",
  "face_value": 200.0
 },
 {
  "symbol": "LAXMIINDIA",
  "company_name": "LAXMI INDIA FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE06WU01026",
  "face_value": 500.0
 },
 {
  "symbol": "LCCINFOTEC",
  "company_name": "LCC INFOTECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE938A01021",
  "face_value": 200.0
 },
 {
  "symbol": "LDTEXT",
  "company_name": "LD TEXTILES IND. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE122001014",
  "face_value": 1000.0
 },
 {
  "symbol": "LEEL",
  "company_name": "LEEL ELECTRICALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE245C01019",
  "face_value": 1000.0
 },
 {
  "symbol": "LEENATEX",
  "company_name": "LEENA TEXTILES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE113401017",
  "face_value": 1000.0
 },
 {
  "symbol": "LEMERITE",
  "company_name": "LE MERITE EXPORTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0G1L01017",
  "face_value": 1000.0
 },
 {
  "symbol": "LEMONTREE",
  "company_name": "LEMON TREE HOTELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE970X01018",
  "face_value": 1000.0
 },
 {
  "symbol": "LENSKART",
  "company_name": "LENSKART SOLUTIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE956O01016",
  "face_value": 200.0
 },
 {
  "symbol": "LEXUS",
  "company_name": "LEXUS GRANITO (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE500X01013",
  "face_value": 1000.0
 },
 {
  "symbol": "LFIC",
  "company_name": "LAKSHMI FIN IND CORP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE850E01012",
  "face_value": 1000.0
 },
 {
  "symbol": "LGBBROSLTD",
  "company_name": "LG BALAKRISHNAN & BROS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE337A01034",
  "face_value": 1000.0
 },
 {
  "symbol": "LGBFORGE",
  "company_name": "LGB FORGE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE201J01017",
  "face_value": 100.0
 },
 {
  "symbol": "LGEINDIA",
  "company_name": "LG ELECTRONICS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE324D01010",
  "face_value": 1000.0
 },
 {
  "symbol": "LGHL",
  "company_name": "LAXMI GOLDORNA HOUSE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE258Y01016",
  "face_value": 1000.0
 },
 {
  "symbol": "LIBAS",
  "company_name": "LIBAS CONSU PRODUCTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE908V01012",
  "face_value": 1000.0
 },
 {
  "symbol": "LIBAS-RE",
  "company_name": "LIBAS CON PRODUCT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE908V20012",
  "face_value": 1000.0
 },
 {
  "symbol": "LIBERTSHOE",
  "company_name": "LIBERTY SHOES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE557B01019",
  "face_value": 1000.0
 },
 {
  "symbol": "LICHSGFIN",
  "company_name": "LIC HOUSING FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE115A01026",
  "face_value": 200.0
 },
 {
  "symbol": "LICI",
  "company_name": "LIFE INSURA CORP OF INDIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0J1Y01017",
  "face_value": 1000.0
 },
 {
  "symbol": "LICMFGOLD",
  "company_name": "LIC MF - LIC GOLD ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF767K01SM1",
  "face_value": 100.0
 },
 {
  "symbol": "LICN50INAV",
  "company_name": "LICNETFN50 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000105",
  "face_value": 100.0
 },
 {
  "symbol": "LICNETFGSC",
  "company_name": "LICNAMC - LICNMFET",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF767K01MV5",
  "face_value": 1000.0
 },
 {
  "symbol": "LICNETFN50",
  "company_name": "LICNAMC - LICNFENGP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF767K01OS7",
  "face_value": 1000.0
 },
 {
  "symbol": "LICNETFSEN",
  "company_name": "LICNAMC - LICNFESGP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF767K01OT5",
  "face_value": 1000.0
 },
 {
  "symbol": "LICNETINAV",
  "company_name": "LICNETFSEN INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000107",
  "face_value": 100.0
 },
 {
  "symbol": "LICNFNHGP",
  "company_name": "LICNAMC - LICNFNHGP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF767K01PC8",
  "face_value": 1000.0
 },
 {
  "symbol": "LICNFNINAV",
  "company_name": "LICNFNHGP INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000104",
  "face_value": 100.0
 },
 {
  "symbol": "LICNGSINAV",
  "company_name": "LICNETFGSC INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000106",
  "face_value": 100.0
 },
 {
  "symbol": "LICNMDINAV",
  "company_name": "LICNAMC - LICNMDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000217",
  "face_value": 1000.0
 },
 {
  "symbol": "LICNMID100",
  "company_name": "LICNAMC - LICNMID100",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF767K01RN1",
  "face_value": 1000.0
 },
 {
  "symbol": "LIKHITHA",
  "company_name": "LIKHITHA INFRASTRUC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE060901027",
  "face_value": 500.0
 },
 {
  "symbol": "LINC",
  "company_name": "LINC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE802B01027",
  "face_value": 500.0
 },
 {
  "symbol": "LINCOLN",
  "company_name": "LINCOLN PHARMA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE405C01035",
  "face_value": 1000.0
 },
 {
  "symbol": "LINDEINDIA",
  "company_name": "LINDE INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE473A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "LIQADDINAV",
  "company_name": "DSPAMC - LIQADDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000222",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQCASINAV",
  "company_name": "ZERODHAAMC - LIQCASINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000209",
  "face_value": 10000.0
 },
 {
  "symbol": "LIQETFINAV",
  "company_name": "BFAM - LIQETFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000225",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQGRBINAV",
  "company_name": "NIPPONAMC - LIQGRBINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000292",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQGRWBEES",
  "company_name": "NIPPONAMC - LIQGRWBEES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KC1FU1",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQIDINAV",
  "company_name": "MIRAEAMC - LIQIDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000191",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQPLSINAV",
  "company_name": "MIRAEAMC - LIQPLSINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000251",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQSBIINAV",
  "company_name": "SBIAMC - LIQSBIINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000203",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQSHRINAV",
  "company_name": "SHRIRAM - LIQSHRINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000230",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQUID",
  "company_name": "MIRAEAMC - LIQUID",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01KS1",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQUID1",
  "company_name": "KOTAKMAMC - KOTAKLIQ",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1LV5",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQUIDADD",
  "company_name": "DSPAMC - LIQUIDADD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1UM0",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQUIDBEES",
  "company_name": "NIP IND ETF LIQUID BEES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF732E01037",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQUIDBETF",
  "company_name": "BFAM - LIQUIDBETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF0QA701854",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQUIDCASE",
  "company_name": "ZERODHAAMC - LIQUIDCASE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF0R8F01034",
  "face_value": 10000.0
 },
 {
  "symbol": "LIQUIDETF",
  "company_name": "DSP LIQUID ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1EU7",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQUIDIETF",
  "company_name": "ICICIPRAMC - ICICILIQ",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC1KT9",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQUIDINAV",
  "company_name": "LIQUIDBEES INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000124",
  "face_value": 100.0
 },
 {
  "symbol": "LIQUIDPLUS",
  "company_name": "MIRAEAMC - LIQUIDPLUS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01MY5",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQUIDSBI",
  "company_name": "SBIAMC - LIQUIDSBI",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KA13Z8",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQUIDSHRI",
  "company_name": "SHRIRAM - LIQUIDSHRI",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF680P01422",
  "face_value": 100000.0
 },
 {
  "symbol": "LIQUIEINAV",
  "company_name": "LIQUIDETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000063",
  "face_value": 100.0
 },
 {
  "symbol": "LKPMERFIN",
  "company_name": "LKP MERCHANT FINANCING LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE115201019",
  "face_value": 1000.0
 },
 {
  "symbol": "LLOYDMETAL",
  "company_name": "LLOYD METALS & ENGG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE115301017",
  "face_value": 1000.0
 },
 {
  "symbol": "LLOYDS-RE",
  "company_name": "LLOYDS ENGG WORK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE093R20011",
  "face_value": 100.0
 },
 {
  "symbol": "LLOYDS-RE1",
  "company_name": "LLOYDS ENG WORKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE093R20029",
  "face_value": 100.0
 },
 {
  "symbol": "LLOYDSE-RE",
  "company_name": "LLOYDS ENTERPRISES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE080I20017",
  "face_value": 100.0
 },
 {
  "symbol": "LLOYDSENGG",
  "company_name": "LLOYDS ENGG WORK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE093R01011",
  "face_value": 100.0
 },
 {
  "symbol": "LLOYDSENT",
  "company_name": "LLOYDS ENTERPRISES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE080I01025",
  "face_value": 100.0
 },
 {
  "symbol": "LLOYDSME",
  "company_name": "LLOYDS METALS N ENERGY L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE281B01032",
  "face_value": 100.0
 },
 {
  "symbol": "LMW",
  "company_name": "LMW LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE269B01029",
  "face_value": 1000.0
 },
 {
  "symbol": "LODHA",
  "company_name": "LODHA DEVELOPERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE670K01029",
  "face_value": 1000.0
 },
 {
  "symbol": "LOKESHMACH",
  "company_name": "LOKESH MACHINES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE397H01017",
  "face_value": 1000.0
 },
 {
  "symbol": "LOKHSG",
  "company_name": "LOK HOUSING & CONSTRUCTIO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE115701018",
  "face_value": 1000.0
 },
 {
  "symbol": "LORDSCHLO",
  "company_name": "LORDS CHLORO ALKALI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE846D01012",
  "face_value": 1000.0
 },
 {
  "symbol": "LOTUSDEV",
  "company_name": "SRI LOTUS DEVLPRS N RTY L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0V9Q01010",
  "face_value": 100.0
 },
 {
  "symbol": "LOTUSEYE",
  "company_name": "LOTUS EYE HOSP & INST L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE947I01017",
  "face_value": 1000.0
 },
 {
  "symbol": "LOVABLE",
  "company_name": "LOVABLE LINGERIE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE597L01014",
  "face_value": 1000.0
 },
 {
  "symbol": "LOWVOL",
  "company_name": "MIRAEAMC - MANV30F",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01JU9",
  "face_value": 10000.0
 },
 {
  "symbol": "LOWVOL1",
  "company_name": "KOTAKMAMC - KOTAKLOVOL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1IY5",
  "face_value": 1000.0
 },
 {
  "symbol": "LOWVOLIETF",
  "company_name": "ICICI PR NIF LW VL 30 ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC19U5",
  "face_value": 100.0
 },
 {
  "symbol": "LOYALTEX",
  "company_name": "LOYAL TEXTILE MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE970D01010",
  "face_value": 1000.0
 },
 {
  "symbol": "LPDC",
  "company_name": "LANDMARK PR.DEV.CO.LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE197J01017",
  "face_value": 100.0
 },
 {
  "symbol": "LT",
  "company_name": "LARSEN & TOUBRO LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE018A01030",
  "face_value": 200.0
 },
 {
  "symbol": "LTCASEINAV",
  "company_name": "ZERODHAAMC - LTCASEINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000295",
  "face_value": 1000.0
 },
 {
  "symbol": "LTF",
  "company_name": "L&T FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE498L01015",
  "face_value": 1000.0
 },
 {
  "symbol": "LTFOODS",
  "company_name": "LT FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE818H01020",
  "face_value": 100.0
 },
 {
  "symbol": "LTGILTBEES",
  "company_name": "NIP IND ETF LONGTERM GILT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KB1882",
  "face_value": 1000.0
 },
 {
  "symbol": "LTGILTCASE",
  "company_name": "ZERODHAAMC - LTGILTCASE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF0R8F01133",
  "face_value": 1000.0
 },
 {
  "symbol": "LTGILTINAV",
  "company_name": "LTGILTBEES INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000125",
  "face_value": 100.0
 },
 {
  "symbol": "LTM",
  "company_name": "LTM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE214T01019",
  "face_value": 100.0
 },
 {
  "symbol": "LTTS",
  "company_name": "L&T TECHNOLOGY SER. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE010V01017",
  "face_value": 200.0
 },
 {
  "symbol": "LUMAXIND",
  "company_name": "LUMAX INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE162B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "LUMAXTECH",
  "company_name": "LUMAX AUTO TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE872H01027",
  "face_value": 200.0
 },
 {
  "symbol": "LUNARDIAM",
  "company_name": "LUNAR DIAMONDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE109601018",
  "face_value": 1000.0
 },
 {
  "symbol": "LUPIN",
  "company_name": "LUPIN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE326A01037",
  "face_value": 200.0
 },
 {
  "symbol": "LUXIND",
  "company_name": "LUX INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE150G01020",
  "face_value": 200.0
 },
 {
  "symbol": "LXCHEM",
  "company_name": "LAXMI ORGANIC INDUS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE576O01020",
  "face_value": 200.0
 },
 {
  "symbol": "LYKALABS",
  "company_name": "LYKA LABS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE933A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "LYPSAGEMS",
  "company_name": "LYPSA GEMS & JEWEL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE142K01011",
  "face_value": 1000.0
 },
 {
  "symbol": "M&M",
  "company_name": "MAHINDRA & MAHINDRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE101A01026",
  "face_value": 500.0
 },
 {
  "symbol": "M&MFIN",
  "company_name": "M&M FIN. SERVICES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE774D01024",
  "face_value": 200.0
 },
 {
  "symbol": "M&MFIN-RE",
  "company_name": "MAHINDRA & MAHINDRA RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE774D20016",
  "face_value": 200.0
 },
 {
  "symbol": "M&MFIN-RE1",
  "company_name": "MAHINDRA & MAHINDRA RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE774D20024",
  "face_value": 200.0
 },
 {
  "symbol": "MAANALU",
  "company_name": "MAAN ALUMINIUM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE215I01027",
  "face_value": 500.0
 },
 {
  "symbol": "MACPOWER",
  "company_name": "MACPOWER CNC MACHINES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE155Z01011",
  "face_value": 1000.0
 },
 {
  "symbol": "MADHAV",
  "company_name": "MADHAV MARBLE & GRANITE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE925C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "MADHAVIPL",
  "company_name": "MADHAV INFRA PROJECTS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE631R01026",
  "face_value": 100.0
 },
 {
  "symbol": "MADHUCON",
  "company_name": "MADHUCON PROJECTS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE378D01032",
  "face_value": 100.0
 },
 {
  "symbol": "MADHURFOOD",
  "company_name": "MADHUR FOOD PRODUCTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE112401018",
  "face_value": 1000.0
 },
 {
  "symbol": "MADHUSYNTX",
  "company_name": "MADHUMILAN SYNTEX LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE112301010",
  "face_value": 1000.0
 },
 {
  "symbol": "MADRASALMN",
  "company_name": "MADRAS ALUMINIUM CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE223B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "MADRASFERT",
  "company_name": "MADRAS FERTILISERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE414A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "MADRASMFIN",
  "company_name": "MADRAS MOTOR FIN. & GUAR.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE106801017",
  "face_value": 1000.0
 },
 {
  "symbol": "MADSUDIND",
  "company_name": "MADHUSUDAN IND. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE112501015",
  "face_value": 1000.0
 },
 {
  "symbol": "MADURACOAT",
  "company_name": "MADURA COATS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE122A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MAESGEINAV",
  "company_name": "MAESGETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000116",
  "face_value": 100.0
 },
 {
  "symbol": "MAFANG",
  "company_name": "MIRAEAMC - MAFANG",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01HF4",
  "face_value": 4000.0
 },
 {
  "symbol": "MAFANGINAV",
  "company_name": "MAFANG INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000114",
  "face_value": 100.0
 },
 {
  "symbol": "MAFATIND",
  "company_name": "MAFATLAL INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE270B01035",
  "face_value": 200.0
 },
 {
  "symbol": "MAFATLAFIN",
  "company_name": "MAFATLAL FINANCE COMPANY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE965B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MAFATLAIND",
  "company_name": "MAFATLAL INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE270B01019",
  "face_value": 10000.0
 },
 {
  "symbol": "MAFSETINAV",
  "company_name": "MAFSETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000110",
  "face_value": 100.0
 },
 {
  "symbol": "MAG813INAV",
  "company_name": "MIRAEAMC - MAG813INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000184",
  "face_value": 1000.0
 },
 {
  "symbol": "MAGADSUGAR",
  "company_name": "MAGADH SUGAR & ENERGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE347W01011",
  "face_value": 1000.0
 },
 {
  "symbol": "MAGNUM",
  "company_name": "MAGNUM VENTURES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE387I01016",
  "face_value": 1000.0
 },
 {
  "symbol": "MAGNUM-RE",
  "company_name": "MAGNUM VENTURES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE387I20016",
  "face_value": 1000.0
 },
 {
  "symbol": "MAGOLDINAV",
  "company_name": "MIRAEAMC - MAGOLDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000179",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHABANK",
  "company_name": "BANK OF MAHARASHTRA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE457A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHAGRO",
  "company_name": "MAHADEV INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE460801017",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHALEAS",
  "company_name": "MAHADEV CORP (I) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY9181",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHAPE-RE",
  "company_name": "MAHA RASHTRA APEX CORPOR",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE843B20013",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHAPEXLTD",
  "company_name": "MAHA RASHTRA APEX COPR. L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE843B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHASTEEL",
  "company_name": "MAHAMAYA STEEL INDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE451L01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHENDSUIT",
  "company_name": "MAHENDRA PETROCHEMICALS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "IN8452H01019",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHEPC",
  "company_name": "MAHINDRA EPC IRRIG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE215D01010",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHESHWARI",
  "company_name": "MAHESHWARI LOGISTICS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE263W01010",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHKTECH",
  "company_name": "MIRAEAMC - MAHKTECH",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01HS7",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHKTEINAV",
  "company_name": "MAHKTECH INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000108",
  "face_value": 100.0
 },
 {
  "symbol": "MAHLIFE",
  "company_name": "MAHINDRA LIFESPACE DEVLTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE813A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHLIFE-RE",
  "company_name": "MAHINDRA LIFESPACE RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE813A20018",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHLOG",
  "company_name": "MAHINDRA LOGISTIC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE766P01016",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHLOG-RE",
  "company_name": "MAHINDRA LOGISTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE766P20016",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHSCOOTER",
  "company_name": "MAHARASHTRA SCOOTERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE288A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "MAHSEAMLES",
  "company_name": "MAHARASHTRA SEAMLESS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE271B01025",
  "face_value": 500.0
 },
 {
  "symbol": "MAIKALFIBR",
  "company_name": "MAIKAAL FIBRES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE104601013",
  "face_value": 1000.0
 },
 {
  "symbol": "MAITHANALL",
  "company_name": "MAITHAN ALLOYS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE683C01011",
  "face_value": 1000.0
 },
 {
  "symbol": "MAJESAUT",
  "company_name": "MAJESTIC AUTO LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE201B01022",
  "face_value": 1000.0
 },
 {
  "symbol": "MAJESAUTO",
  "company_name": "MAJESTIC AUTO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE201B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MAJESTIND",
  "company_name": "MAJESTIC INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE104801019",
  "face_value": 1000.0
 },
 {
  "symbol": "MAKEINDIA",
  "company_name": "MIRAEAMC - MAMFGETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01IB1",
  "face_value": 5000.0
 },
 {
  "symbol": "MALLCOM",
  "company_name": "MALLCOM (INDIA) LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE389C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "MALUPAPER",
  "company_name": "MALU PAPER MILLS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE383H01017",
  "face_value": 1000.0
 },
 {
  "symbol": "MAM150INAV",
  "company_name": "MAM150ETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000112",
  "face_value": 100.0
 },
 {
  "symbol": "MAMATA",
  "company_name": "MAMATA MACHINERY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0TO701015",
  "face_value": 1000.0
 },
 {
  "symbol": "MAMFGEINAV",
  "company_name": "MAMFGETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000111",
  "face_value": 100.0
 },
 {
  "symbol": "MAN50EINAV",
  "company_name": "MAN50ETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000109",
  "face_value": 100.0
 },
 {
  "symbol": "MANAKALUCO",
  "company_name": "MANAK ALUMINIUM CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE859Q01017",
  "face_value": 100.0
 },
 {
  "symbol": "MANAKCOAT",
  "company_name": "MAN COAT METAL & IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE830Q01018",
  "face_value": 100.0
 },
 {
  "symbol": "MANAKSIA",
  "company_name": "MANAKSIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE015D01022",
  "face_value": 200.0
 },
 {
  "symbol": "MANAKSTEEL",
  "company_name": "MANAKSIA STEELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE824Q01011",
  "face_value": 100.0
 },
 {
  "symbol": "MANALIPETC",
  "company_name": "MANALI PETROCHEMICALS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE201A01024",
  "face_value": 500.0
 },
 {
  "symbol": "MANALUMN",
  "company_name": "MAN INDUSTRIES (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE993A01026",
  "face_value": 1000.0
 },
 {
  "symbol": "MANAPPURAM",
  "company_name": "MANAPPURAM FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE522D01027",
  "face_value": 200.0
 },
 {
  "symbol": "MANBA",
  "company_name": "MANBA FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE939X01013",
  "face_value": 1000.0
 },
 {
  "symbol": "MANCREDIT",
  "company_name": "MANGAL CREDIT N FINCORP L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE545L01039",
  "face_value": 1000.0
 },
 {
  "symbol": "MANDHANA",
  "company_name": "MANDHANA INDUS. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE087J01010",
  "face_value": 1000.0
 },
 {
  "symbol": "MANGALAM",
  "company_name": "MANGALAM DRUG & CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE584F01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MANGCHEFER",
  "company_name": "MANG.CHEM.FERT.LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE558B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "MANGLMCEM",
  "company_name": "MANGALAM CEMENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE347A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "MANGTIMBER",
  "company_name": "MANGALAM TIMBER PRODUCTS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE805B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "MANINDS",
  "company_name": "MAN INDUSTRIES (I) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE993A01026",
  "face_value": 500.0
 },
 {
  "symbol": "MANINFRA",
  "company_name": "MAN INFRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE949H01023",
  "face_value": 200.0
 },
 {
  "symbol": "MANKIND",
  "company_name": "MANKIND PHARMA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE634S01028",
  "face_value": 100.0
 },
 {
  "symbol": "MANOMAY",
  "company_name": "MANOMAY TEX INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE784W01015",
  "face_value": 1000.0
 },
 {
  "symbol": "MANORAMA",
  "company_name": "MANORAMA INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00VM01036",
  "face_value": 200.0
 },
 {
  "symbol": "MANORG",
  "company_name": "MANGALAM ORGANICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE370D01013",
  "face_value": 1000.0
 },
 {
  "symbol": "MANPASAND",
  "company_name": "MANPASAND BEVERAGES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE122R01018",
  "face_value": 1000.0
 },
 {
  "symbol": "MANTRIHSG",
  "company_name": "MANTRI HSG & CONST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE102101016",
  "face_value": 1000.0
 },
 {
  "symbol": "MANUFGBEES",
  "company_name": "NIPPONAMC - MANUFGBEES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KC1GH6",
  "face_value": 1000.0
 },
 {
  "symbol": "MANUGRAIND",
  "company_name": "MANUGRAPH INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE562701016",
  "face_value": 1000.0
 },
 {
  "symbol": "MANUGRAPH",
  "company_name": "MANUGRAPH INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE867A01022",
  "face_value": 200.0
 },
 {
  "symbol": "MANXT5INAV",
  "company_name": "MANXT50 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000113",
  "face_value": 100.0
 },
 {
  "symbol": "MANYAVAR",
  "company_name": "VEDANT FASHIONS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE825V01034",
  "face_value": 100.0
 },
 {
  "symbol": "MAPMYINDIA",
  "company_name": "C.E. INFO SYSTEMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0BV301023",
  "face_value": 200.0
 },
 {
  "symbol": "MARALOVER",
  "company_name": "MARAL OVERSEAS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE882A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "MARATHON",
  "company_name": "MARATHON NXTGEN REALT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE182D01020",
  "face_value": 500.0
 },
 {
  "symbol": "MARICO",
  "company_name": "MARICO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE196A01026",
  "face_value": 100.0
 },
 {
  "symbol": "MARINE",
  "company_name": "MARINE ELECTRICAL (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01JE01028",
  "face_value": 200.0
 },
 {
  "symbol": "MARKOLINES",
  "company_name": "MARKOLINES PAVEMENT TEC L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0FW001016",
  "face_value": 1000.0
 },
 {
  "symbol": "MARKSANS",
  "company_name": "MARKSANS PHARMA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE750C01026",
  "face_value": 100.0
 },
 {
  "symbol": "MARNITPOLY",
  "company_name": "MPL CORPORATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE187601013",
  "face_value": 1000.0
 },
 {
  "symbol": "MARSHAL-RE",
  "company_name": "MARSHALL MACHINES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00SZ20018",
  "face_value": 1000.0
 },
 {
  "symbol": "MARSHALL",
  "company_name": "MARSHALL MACHINES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00SZ01018",
  "face_value": 1000.0
 },
 {
  "symbol": "MARSONS",
  "company_name": "MARSONS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE415B01044",
  "face_value": 100.0
 },
 {
  "symbol": "MARUTI",
  "company_name": "MARUTI SUZUKI INDIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE585B01010",
  "face_value": 500.0
 },
 {
  "symbol": "MASFIN",
  "company_name": "MAS FINANCIAL SERV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE348L01012",
  "face_value": 1000.0
 },
 {
  "symbol": "MASILINAV",
  "company_name": "MIRAEAMC - MASILINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000187",
  "face_value": 1000.0
 },
 {
  "symbol": "MASKINVEST",
  "company_name": "MASK INVESTMENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE885F01015",
  "face_value": 1000.0
 },
 {
  "symbol": "MASPTOINAV",
  "company_name": "MASPTOP50 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000115",
  "face_value": 100.0
 },
 {
  "symbol": "MASPTOP50",
  "company_name": "MIRAEAMC - MASPTOP50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01HP3",
  "face_value": 2000.0
 },
 {
  "symbol": "MASTEK",
  "company_name": "MASTEK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE759A01021",
  "face_value": 500.0
 },
 {
  "symbol": "MASTERTR",
  "company_name": "MASTER TRUST LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE677D01037",
  "face_value": 100.0
 },
 {
  "symbol": "MATHPLATT",
  "company_name": "MATHER & PLATT (I) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE844C01019",
  "face_value": 1000.0
 },
 {
  "symbol": "MATRIMONY",
  "company_name": "MATRIMONY.COM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE866R01028",
  "face_value": 500.0
 },
 {
  "symbol": "MAWANASUG",
  "company_name": "MAWANA SUGARS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE636A01039",
  "face_value": 1000.0
 },
 {
  "symbol": "MAXESTATES",
  "company_name": "MAX ESTATES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE03EI01018",
  "face_value": 1000.0
 },
 {
  "symbol": "MAXHEALTH",
  "company_name": "MAX HEALTHCARE INS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE027H01010",
  "face_value": 1000.0
 },
 {
  "symbol": "MAXIND",
  "company_name": "MAX INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0CG601016",
  "face_value": 1000.0
 },
 {
  "symbol": "MAXIND-RE",
  "company_name": "MAX INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0CG620016",
  "face_value": 1000.0
 },
 {
  "symbol": "MAXORCHARD",
  "company_name": "MAXWORTH ORCHARDS INDIA L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE189201010",
  "face_value": 1000.0
 },
 {
  "symbol": "MAXVIL",
  "company_name": "MAX VENTURES AND INDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE154U01015",
  "face_value": 1000.0
 },
 {
  "symbol": "MAYURUNIQ",
  "company_name": "MAYUR UNIQUOTERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE040D01038",
  "face_value": 500.0
 },
 {
  "symbol": "MAZDA",
  "company_name": "MAZDA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE885E01042",
  "face_value": 200.0
 },
 {
  "symbol": "MAZDALEASE",
  "company_name": "MAZDA IND. & LEASING LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE461201019",
  "face_value": 1000.0
 },
 {
  "symbol": "MAZDOCK",
  "company_name": "MAZAGON DOCK SHIPBUIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE249Z01020",
  "face_value": 500.0
 },
 {
  "symbol": "MBAPL",
  "company_name": "MADHYA BHARAT AGRO P. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE900L01010",
  "face_value": 1000.0
 },
 {
  "symbol": "MBECL",
  "company_name": "MCNALLY BH. ENG. CO.LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE748A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "MBEL",
  "company_name": "M AND B ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE08N601015",
  "face_value": 1000.0
 },
 {
  "symbol": "MBLINFRA",
  "company_name": "MBL INFRASTRUCTURE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE912H01013",
  "face_value": 1000.0
 },
 {
  "symbol": "MCCHRLS-B",
  "company_name": "MAC CHARLES (INDIA) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE435D01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MCDHOLDING",
  "company_name": "MCDOWELL HOLDINGS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE836H01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MCL",
  "company_name": "MADHAV COPPER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE813V01022",
  "face_value": 500.0
 },
 {
  "symbol": "MCLEODRUSS",
  "company_name": "MCLEOD RUSSEL INDIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE942G01012",
  "face_value": 500.0
 },
 {
  "symbol": "MCLOUD",
  "company_name": "MAGELLANIC CLOUD LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE613C01026",
  "face_value": 200.0
 },
 {
  "symbol": "MCX",
  "company_name": "MULTI COMMODITY EXCHANGE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE745G01043",
  "face_value": 200.0
 },
 {
  "symbol": "MD150CINAV",
  "company_name": "ZERODHAAMC - MD150CINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000227",
  "face_value": 1000.0
 },
 {
  "symbol": "MEDANTA",
  "company_name": "GLOBAL HEALTH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE474Q01031",
  "face_value": 200.0
 },
 {
  "symbol": "MEDIASSIST",
  "company_name": "MEDI ASSIST HEALTH SER L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE456Z01021",
  "face_value": 500.0
 },
 {
  "symbol": "MEDICAMEQ",
  "company_name": "MEDICAMEN BIOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE646B01010",
  "face_value": 1000.0
 },
 {
  "symbol": "MEDICAPS",
  "company_name": "MEDI CAPS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE190701016",
  "face_value": 1000.0
 },
 {
  "symbol": "MEDICO",
  "company_name": "MEDICO REMEDIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE630Y01024",
  "face_value": 200.0
 },
 {
  "symbol": "MEDPLUS",
  "company_name": "MEDPLUS HEALTH SERV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE804L01022",
  "face_value": 200.0
 },
 {
  "symbol": "MEESHO",
  "company_name": "MEESHO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0VDM01015",
  "face_value": 100.0
 },
 {
  "symbol": "MEGA-RE",
  "company_name": "MEGASOFT LIMITED - RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE933B20012",
  "face_value": 1000.0
 },
 {
  "symbol": "MEGASTAR",
  "company_name": "MEGASTAR FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00EM01016",
  "face_value": 1000.0
 },
 {
  "symbol": "MEGH",
  "company_name": "MEGHMANI ORGANICS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE974H01013",
  "face_value": 100.0
 },
 {
  "symbol": "MEIL",
  "company_name": "MANGAL ELECTRICAL IND L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0PKD01011",
  "face_value": 1000.0
 },
 {
  "symbol": "MELSTAR",
  "company_name": "MELSTAR INFORMATION TECH",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE817A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "MENNPIS",
  "company_name": "MENON PISTONS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE650G01029",
  "face_value": 100.0
 },
 {
  "symbol": "MENONBE",
  "company_name": "MENON BEARINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE071D01033",
  "face_value": 100.0
 },
 {
  "symbol": "MEP",
  "company_name": "MEP INFRA. DEVELOPERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE776I01010",
  "face_value": 1000.0
 },
 {
  "symbol": "MERCANTILE",
  "company_name": "MERCANTILE VENTURES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE689O01013",
  "face_value": 1000.0
 },
 {
  "symbol": "MERCATOR",
  "company_name": "MERCATOR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE934B01028",
  "face_value": 100.0
 },
 {
  "symbol": "MERIND",
  "company_name": "MERIND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE215A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "MESCOPHARM",
  "company_name": "MESCO PHARMA. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE192601016",
  "face_value": 1000.0
 },
 {
  "symbol": "METAL",
  "company_name": "MIRAEAMC - METAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01LY7",
  "face_value": 1000.0
 },
 {
  "symbol": "METALFORGE",
  "company_name": "METALYST FORGINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE425A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "METALIETF",
  "company_name": "ICICIPRAMC - METALIETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC19W1",
  "face_value": 1000.0
 },
 {
  "symbol": "METALIINAV",
  "company_name": "ICICIPRAMC - METALIINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000237",
  "face_value": 1000.0
 },
 {
  "symbol": "METALINAV",
  "company_name": "MIRAEAMC - METALINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000246",
  "face_value": 1000.0
 },
 {
  "symbol": "METALPIPE",
  "company_name": "METALMAN INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE192801012",
  "face_value": 1000.0
 },
 {
  "symbol": "METAZINC",
  "company_name": "MTZ (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE865A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "METKORE",
  "company_name": "METKORE ALLOYS & IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE592I01029",
  "face_value": 200.0
 },
 {
  "symbol": "METROBRAND",
  "company_name": "METRO BRANDS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE317I01021",
  "face_value": 500.0
 },
 {
  "symbol": "METROCHEM",
  "company_name": "METROCHEM INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE732B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "METROGLOBL",
  "company_name": "METROGLOBAL LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE085D01033",
  "face_value": 1000.0
 },
 {
  "symbol": "METROPOLIS",
  "company_name": "METROPOLIS HEALTHCARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE112L01020",
  "face_value": 200.0
 },
 {
  "symbol": "MFML",
  "company_name": "MAHALAXMI FABRIC MILLS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0US801024",
  "face_value": 1000.0
 },
 {
  "symbol": "MFSL",
  "company_name": "MAX FINANCIAL SERV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE180A01020",
  "face_value": 200.0
 },
 {
  "symbol": "MGBEESINAV",
  "company_name": "NIPPONAMC - MGBEESINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000297",
  "face_value": 1000.0
 },
 {
  "symbol": "MGEL",
  "company_name": "MANGALAM GLOBAL ENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0APB01032",
  "face_value": 100.0
 },
 {
  "symbol": "MGEL-RE",
  "company_name": "MANGALAM GLOBAL ENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0APB20016",
  "face_value": 200.0
 },
 {
  "symbol": "MGL",
  "company_name": "MAHANAGAR GAS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE002S01010",
  "face_value": 1000.0
 },
 {
  "symbol": "MHLXMIRU",
  "company_name": "MAHALAXMI RUBTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE112D01035",
  "face_value": 1000.0
 },
 {
  "symbol": "MHRIL",
  "company_name": "MAHINDRA HOLIDAYS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE998I01010",
  "face_value": 1000.0
 },
 {
  "symbol": "MIC",
  "company_name": "MIC ELECTRONICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE287C01029",
  "face_value": 200.0
 },
 {
  "symbol": "MICEL",
  "company_name": "MIC ELECTRONICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE287C01037",
  "face_value": 200.0
 },
 {
  "symbol": "MICROPLANT",
  "company_name": "MICRO PLANTAE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE193901019",
  "face_value": 1000.0
 },
 {
  "symbol": "MID150",
  "company_name": "KOTAKMAMC - MID150",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1VW2",
  "face_value": 1000.0
 },
 {
  "symbol": "MID150BEES",
  "company_name": "NIP IND ETF MIDCAP 150",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KB1V68",
  "face_value": 1000.0
 },
 {
  "symbol": "MID150CASE",
  "company_name": "ZERODHAAMC - MID150CASE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF0R8F01059",
  "face_value": 1000.0
 },
 {
  "symbol": "MID150INAV",
  "company_name": "MID150BEES INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000126",
  "face_value": 100.0
 },
 {
  "symbol": "MID15INAV",
  "company_name": "KOTAKMAMC - MID15INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000269",
  "face_value": 1000.0
 },
 {
  "symbol": "MIDADDINAV",
  "company_name": "DSPAMC - MIDADDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000324",
  "face_value": 1000.0
 },
 {
  "symbol": "MIDCAP",
  "company_name": "KOTAKMAMC - KOTAKMID50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1ZC5",
  "face_value": 100.0
 },
 {
  "symbol": "MIDCAPADD",
  "company_name": "DSPAMC - MIDCAPADD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1WW5",
  "face_value": 1000.0
 },
 {
  "symbol": "MIDCAPBETA",
  "company_name": "UTIAMC-MIDCAPBETA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF789F1AYX9",
  "face_value": 1000.0
 },
 {
  "symbol": "MIDCAPETF",
  "company_name": "MIRAEAMC - MAM150ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01IC9",
  "face_value": 500.0
 },
 {
  "symbol": "MIDCAPIETF",
  "company_name": "ICICIPRAMC - ICICIM150",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC11W8",
  "face_value": 100.0
 },
 {
  "symbol": "MIDEASTI",
  "company_name": "MIDEAST INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE194401019",
  "face_value": 1000.0
 },
 {
  "symbol": "MIDEASTSTL",
  "company_name": "MIDEAST INTEGRATED STEEL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE194501016",
  "face_value": 1000.0
 },
 {
  "symbol": "MIDHANI",
  "company_name": "MISHRA DHATU NIGAM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE099Z01011",
  "face_value": 1000.0
 },
 {
  "symbol": "MIDINDIA",
  "company_name": "MID INDIA INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE563601017",
  "face_value": 1000.0
 },
 {
  "symbol": "MIDQ50ADD",
  "company_name": "DSPAMC - DSPQ50ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1QL0",
  "face_value": 1000.0
 },
 {
  "symbol": "MIDSELIETF",
  "company_name": "ICICI PRUD MIDCAP SEL ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC10W0",
  "face_value": 100.0
 },
 {
  "symbol": "MIDSMAINAV",
  "company_name": "MIRAEAMC - MIDSMAINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000224",
  "face_value": 1000.0
 },
 {
  "symbol": "MIDSMALL",
  "company_name": "MIRAEAMC - MIDSMALL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01LJ8",
  "face_value": 1000.0
 },
 {
  "symbol": "MIDWESTIRN",
  "company_name": "MIDWEST IRON & STEEL CO L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE195001016",
  "face_value": 1000.0
 },
 {
  "symbol": "MIDWESTLTD",
  "company_name": "MIDWEST LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0XAD01024",
  "face_value": 500.0
 },
 {
  "symbol": "MILTONPLAS",
  "company_name": "MILTON PLASTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE343A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "MINDA-RE",
  "company_name": "MINDA INDUSTRIES RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE405E20015",
  "face_value": 200.0
 },
 {
  "symbol": "MINDACORP",
  "company_name": "MINDA CORPORATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE842C01021",
  "face_value": 200.0
 },
 {
  "symbol": "MINDTECK",
  "company_name": "MINDTECK (INDIA) LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE110B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "MINDTREE",
  "company_name": "MINDTREE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE018I01017",
  "face_value": 1000.0
 },
 {
  "symbol": "MINFRAINAV",
  "company_name": "MOTILALAMC - MINFRAINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000277",
  "face_value": 1000.0
 },
 {
  "symbol": "MIRC-RE",
  "company_name": "MIRC ELECTRONICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE831A20010",
  "face_value": 100.0
 },
 {
  "symbol": "MIRCELECTR",
  "company_name": "MIRC ELECTRONICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE831A01028",
  "face_value": 100.0
 },
 {
  "symbol": "MIRZAINT",
  "company_name": "MIRZA INTERNATIONAL LIMIT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE771A01026",
  "face_value": 200.0
 },
 {
  "symbol": "MITCON",
  "company_name": "MITCON CON & ENG SER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE828O01033",
  "face_value": 1000.0
 },
 {
  "symbol": "MITCON-RE",
  "company_name": "MITCON CON",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE828O20017",
  "face_value": 1000.0
 },
 {
  "symbol": "MITTAL",
  "company_name": "MITTAL LIFE STYLE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE997Y01027",
  "face_value": 100.0
 },
 {
  "symbol": "MITTAL-RE",
  "company_name": "MITTAL LIFE STYLE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE997Y20019",
  "face_value": 1000.0
 },
 {
  "symbol": "MITTAL-RE1",
  "company_name": "MITTAL LIFE STYLE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE997Y20027",
  "face_value": 100.0
 },
 {
  "symbol": "MKPL",
  "company_name": "M K PROTEINS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE964W01021",
  "face_value": 100.0
 },
 {
  "symbol": "MMFL",
  "company_name": "MM FORGINGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE227C01017",
  "face_value": 1000.0
 },
 {
  "symbol": "MMP",
  "company_name": "MMP INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE511Y01018",
  "face_value": 1000.0
 },
 {
  "symbol": "MMTC",
  "company_name": "MMTC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE123F01029",
  "face_value": 100.0
 },
 {
  "symbol": "MMWL",
  "company_name": "MEDIA MATRIX WORLDWIDE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE200D01020",
  "face_value": 100.0
 },
 {
  "symbol": "MNC",
  "company_name": "KOTAKMAMC - KOTAKMNC",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1JF2",
  "face_value": 1000.0
 },
 {
  "symbol": "MNV30FINAV",
  "company_name": "MIRAEAMC - MNV30FINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000183",
  "face_value": 10000.0
 },
 {
  "symbol": "MOALPHA50",
  "company_name": "MOTILALAMC - MOALPHA50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01FR8",
  "face_value": 1000.0
 },
 {
  "symbol": "MOALPHINAV",
  "company_name": "MOTILALAMC - MOALPHINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000289",
  "face_value": 1000.0
 },
 {
  "symbol": "MOBANK10",
  "company_name": "MOTILALAMC - MOBANK10",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01GV8",
  "face_value": 1000.0
 },
 {
  "symbol": "MOBIKWIK",
  "company_name": "ONE MOBIKWIK SYSTEMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0HLU01028",
  "face_value": 200.0
 },
 {
  "symbol": "MOBK10INAV",
  "company_name": "MOTILALAMC - MOBK10INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000347",
  "face_value": 1000.0
 },
 {
  "symbol": "MOCAPIINAV",
  "company_name": "MOTILALAMC - MOCAPIINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000261",
  "face_value": 1000.0
 },
 {
  "symbol": "MOCAPITAL",
  "company_name": "MOTILALAMC - MOCAPITAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01EV3",
  "face_value": 1000.0
 },
 {
  "symbol": "MODEFENCE",
  "company_name": "MOTILALAMC - MODEFENCE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01DJ0",
  "face_value": 1000.0
 },
 {
  "symbol": "MODEFINAV",
  "company_name": "MOTILALAMC - MODEFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000238",
  "face_value": 1000.0
 },
 {
  "symbol": "MODERNDENM",
  "company_name": "MODERN DENIM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE197201010",
  "face_value": 1000.0
 },
 {
  "symbol": "MODERNMAL",
  "company_name": "MODERN MALLEABLE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE197401016",
  "face_value": 1000.0
 },
 {
  "symbol": "MODERNWOOL",
  "company_name": "MODERN TERRY TOWELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE198001013",
  "face_value": 1000.0
 },
 {
  "symbol": "MODIALKALI",
  "company_name": "MODI ALKALIES & CHEM LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE198101011",
  "face_value": 1000.0
 },
 {
  "symbol": "MODINATUR",
  "company_name": "MODI NATURALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE537F01012",
  "face_value": 1000.0
 },
 {
  "symbol": "MODINSULAT",
  "company_name": "MODERN INSULATORS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE197301018",
  "face_value": 1000.0
 },
 {
  "symbol": "MODIOLIVET",
  "company_name": "MODI OLIVETTI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE198801016",
  "face_value": 1000.0
 },
 {
  "symbol": "MODIPON",
  "company_name": "MODIPON LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE199401014",
  "face_value": 1000.0
 },
 {
  "symbol": "MODIRUBBER",
  "company_name": "MODI RUBBER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE832A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "MODIS",
  "company_name": "MODIS NAVNIRMAN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0L0L01012",
  "face_value": 1000.0
 },
 {
  "symbol": "MODISONLTD",
  "company_name": "MODISON LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE737D01021",
  "face_value": 100.0
 },
 {
  "symbol": "MODITHREAD",
  "company_name": "MODI TELEFIBERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE199201018",
  "face_value": 1000.0
 },
 {
  "symbol": "MODRNSYNTX",
  "company_name": "MODERN SYNTEX (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE197801017",
  "face_value": 1000.0
 },
 {
  "symbol": "MODTHREAD",
  "company_name": "MODERN THREADS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE794W01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MOENERGY",
  "company_name": "MOTILALAMC - MOENERGY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01GH7",
  "face_value": 1000.0
 },
 {
  "symbol": "MOENERINAV",
  "company_name": "MOTILALAMC - MOENERINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000305",
  "face_value": 1000.0
 },
 {
  "symbol": "MOGOLD",
  "company_name": "MOTILALAMC - MOGOLD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01FY4",
  "face_value": 1000.0
 },
 {
  "symbol": "MOGOLDINAV",
  "company_name": "MOTILALAMC - MOGOLDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000293",
  "face_value": 1000.0
 },
 {
  "symbol": "MOGSEC",
  "company_name": "MOTILALAMC - G5",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01AK4",
  "face_value": 1000.0
 },
 {
  "symbol": "MOGSECINAV",
  "company_name": "MOGSEC INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000117",
  "face_value": 100.0
 },
 {
  "symbol": "MOHEALTH",
  "company_name": "MOTILALAMC - MOHEALTH",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01BB1",
  "face_value": 1000.0
 },
 {
  "symbol": "MOHITIND",
  "company_name": "MOHIT INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE954E01012",
  "face_value": 1000.0
 },
 {
  "symbol": "MOHLTHINAV",
  "company_name": "MOTILALAMC - MOHLTHINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000153",
  "face_value": 1000.0
 },
 {
  "symbol": "MOHOTAIND",
  "company_name": "MOHOTA INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE313D01013",
  "face_value": 1000.0
 },
 {
  "symbol": "MOIL",
  "company_name": "MOIL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE490G01020",
  "face_value": 1000.0
 },
 {
  "symbol": "MOINFRA",
  "company_name": "MOTILALAMC - MOINFRA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01FL1",
  "face_value": 1000.0
 },
 {
  "symbol": "MOIPO",
  "company_name": "MOTILALAMC - MOIPO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01GI5",
  "face_value": 1000.0
 },
 {
  "symbol": "MOIPOINAV",
  "company_name": "MOTILALAMC - MOIPOINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000315",
  "face_value": 1000.0
 },
 {
  "symbol": "MOKSH",
  "company_name": "MOKSH ORNAMENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE514Y01020",
  "face_value": 200.0
 },
 {
  "symbol": "MOKSH-RE",
  "company_name": "MOKSH ORNAMENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE514Y20012",
  "face_value": 200.0
 },
 {
  "symbol": "MOL",
  "company_name": "MEGHMANI ORGANICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0CT101020",
  "face_value": 100.0
 },
 {
  "symbol": "MOLDPLAST",
  "company_name": "MOLD-TEK PLASTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE200001019",
  "face_value": 1000.0
 },
 {
  "symbol": "MOLDTECH",
  "company_name": "MOLD-TEK TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE835B01035",
  "face_value": 200.0
 },
 {
  "symbol": "MOLDTEK-RE",
  "company_name": "MOLD-TEK PACKAGING RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE893J20011",
  "face_value": 500.0
 },
 {
  "symbol": "MOLDTKPAC",
  "company_name": "MOLD-TEK PACKAGING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE893J01029",
  "face_value": 500.0
 },
 {
  "symbol": "MOLOWVINAV",
  "company_name": "MOLOWVOL INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000123",
  "face_value": 100.0
 },
 {
  "symbol": "MOLOWVOL",
  "company_name": "MOTILALAMC - MOLOWVOL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01BL0",
  "face_value": 200.0
 },
 {
  "symbol": "MOM100",
  "company_name": "MOTILAL OS MIDCAP100 ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01023",
  "face_value": 1000.0
 },
 {
  "symbol": "MOM100INAV",
  "company_name": "MOM100 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000118",
  "face_value": 100.0
 },
 {
  "symbol": "MOM30IETF",
  "company_name": "ICICIPRAMC - ICICIMOM30",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC17C7",
  "face_value": 1000.0
 },
 {
  "symbol": "MOM50",
  "company_name": "MOTILAL OSWAL M50 ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01536",
  "face_value": 700.0
 },
 {
  "symbol": "MOM50INAV",
  "company_name": "MOM50 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000119",
  "face_value": 100.0
 },
 {
  "symbol": "MOME30INAV",
  "company_name": "KOTAKMAMC - MOME30INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000306",
  "face_value": 1000.0
 },
 {
  "symbol": "MOME50INAV",
  "company_name": "MOTILALAMC - MOME50INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000243",
  "face_value": 1000.0
 },
 {
  "symbol": "MOMENTUM",
  "company_name": "BIRLASLAMC - MOMENTUM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KB14K7",
  "face_value": 100.0
 },
 {
  "symbol": "MOMENTUM30",
  "company_name": "KOTAKMAMC - MOMENTUM30",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1XS6",
  "face_value": 1000.0
 },
 {
  "symbol": "MOMENTUM50",
  "company_name": "MOTILALAMC - MOMENTUM50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01DK8",
  "face_value": 1000.0
 },
 {
  "symbol": "MOMGF",
  "company_name": "MOTILALAMC - MOMGF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01FK3",
  "face_value": 1000.0
 },
 {
  "symbol": "MOMGFINAV",
  "company_name": "MOTILALAMC - MOMGFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000280",
  "face_value": 1000.0
 },
 {
  "symbol": "MOMIDMINAV",
  "company_name": "MOTILALAMC - MOMIDMINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000286",
  "face_value": 1000.0
 },
 {
  "symbol": "MOMIDMTM",
  "company_name": "MOTILALAMC - MOMIDMTM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01FQ0",
  "face_value": 1000.0
 },
 {
  "symbol": "MOMNC",
  "company_name": "MOTILALAMC - MOMNC",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01GK1",
  "face_value": 1000.0
 },
 {
  "symbol": "MOMNCINAV",
  "company_name": "MOTILALAMC - MOMNCINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000321",
  "face_value": 1000.0
 },
 {
  "symbol": "MOMNTMINAV",
  "company_name": "BIRLASLAMC - MOMNTMINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000156",
  "face_value": 100.0
 },
 {
  "symbol": "MOMOMEINAV",
  "company_name": "MOMOMENTUM INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000121",
  "face_value": 100.0
 },
 {
  "symbol": "MOMOMENTUM",
  "company_name": "MOTILALAMC - MOMOMENTUM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01BK2",
  "face_value": 200.0
 },
 {
  "symbol": "MON100",
  "company_name": "MOTILAL OS NASDAQ100 ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01AP3",
  "face_value": 100.0
 },
 {
  "symbol": "MON100INAV",
  "company_name": "MON100 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000122",
  "face_value": 100.0
 },
 {
  "symbol": "MON500INAV",
  "company_name": "MOTILALAMC - MON500INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000200",
  "face_value": 1000.0
 },
 {
  "symbol": "MON50EINAV",
  "company_name": "MOTILALAMC - MON50EINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000274",
  "face_value": 1000.0
 },
 {
  "symbol": "MON50EQUAL",
  "company_name": "MOTILALAMC - MON50EQUAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01FC0",
  "face_value": 1000.0
 },
 {
  "symbol": "MONARCH",
  "company_name": "MONARCH NETWORTH CAP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE903D01011",
  "face_value": 1000.0
 },
 {
  "symbol": "MONEXT50",
  "company_name": "MOTILALAMC - MONEXT50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01FD8",
  "face_value": 1000.0
 },
 {
  "symbol": "MONEYBOXX",
  "company_name": "MONEYBOXX FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE296Q01012",
  "face_value": 1000.0
 },
 {
  "symbol": "MONICAELEC",
  "company_name": "MONICA ELECTRONICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE200501018",
  "face_value": 1000.0
 },
 {
  "symbol": "MONIFTY100",
  "company_name": "MOTILALAMC - MONIFTY100",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01GG9",
  "face_value": 1000.0
 },
 {
  "symbol": "MONIFTY500",
  "company_name": "MOTILALAMC - MONIFTY500",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01BU1",
  "face_value": 1000.0
 },
 {
  "symbol": "MONNETISPA",
  "company_name": "MONNET ISPAT & ENERGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE743C01013",
  "face_value": 1000.0
 },
 {
  "symbol": "MONQ50",
  "company_name": "MOTILALAMC - MONQ50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01AU3",
  "face_value": 1000.0
 },
 {
  "symbol": "MONQ50INAV",
  "company_name": "MONQ50 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000120",
  "face_value": 100.0
 },
 {
  "symbol": "MONT50INAV",
  "company_name": "MOTILALAMC - MONT50INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000275",
  "face_value": 1000.0
 },
 {
  "symbol": "MONTARIND",
  "company_name": "MONTARI INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE201201014",
  "face_value": 1000.0
 },
 {
  "symbol": "MONTECARLO",
  "company_name": "MONTE CARLO FASHIONS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE950M01013",
  "face_value": 1000.0
 },
 {
  "symbol": "MOPSE",
  "company_name": "MOTILALAMC - MOPSE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01FO5",
  "face_value": 1000.0
 },
 {
  "symbol": "MOPSEINAV",
  "company_name": "MOTILALAMC - MOPSE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000281",
  "face_value": 1000.0
 },
 {
  "symbol": "MOQLTYINAV",
  "company_name": "MOTILALAMC - MOQLTYINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01BH8",
  "face_value": 1000.0
 },
 {
  "symbol": "MOQUALITY",
  "company_name": "MOTILALAMC - MOQUALITY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01BH8",
  "face_value": 1000.0
 },
 {
  "symbol": "MORARJEE",
  "company_name": "MORARJEE TEXTILES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE161G01027",
  "face_value": 700.0
 },
 {
  "symbol": "MOREALINAV",
  "company_name": "MOTILALAMC - MOREALINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000220",
  "face_value": 1000.0
 },
 {
  "symbol": "MOREALTY",
  "company_name": "MOTILALAMC - MOREALTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01CI4",
  "face_value": 1000.0
 },
 {
  "symbol": "MOREPENLAB",
  "company_name": "MOREPEN LAB. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE083A01026",
  "face_value": 200.0
 },
 {
  "symbol": "MOS250INAV",
  "company_name": "MOTILALAMC - MOS250INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000221",
  "face_value": 1000.0
 },
 {
  "symbol": "MOSCHIP",
  "company_name": "MOSCHIP TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE935B01025",
  "face_value": 200.0
 },
 {
  "symbol": "MOSERVICE",
  "company_name": "MOTILALAMC - MOSERVICE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01GJ3",
  "face_value": 1000.0
 },
 {
  "symbol": "MOSERVINAV",
  "company_name": "MOTILALAMC - MOSERVINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000319",
  "face_value": 1000.0
 },
 {
  "symbol": "MOSILVER",
  "company_name": "MOTILALAMC - MOSILVER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01FZ1",
  "face_value": 1000.0
 },
 {
  "symbol": "MOSILVINAV",
  "company_name": "MOTILALAMC - MOSILVINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000294",
  "face_value": 1000.0
 },
 {
  "symbol": "MOSMALL250",
  "company_name": "MOTILALAMC - MOSMALL250",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01CH6",
  "face_value": 1000.0
 },
 {
  "symbol": "MOTHERSON",
  "company_name": "SAMVRDHNA MTHRSN INTL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE775A01035",
  "face_value": 100.0
 },
 {
  "symbol": "MOTILALOFS",
  "company_name": "MOTILAL OSWAL FIN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE338I01027",
  "face_value": 100.0
 },
 {
  "symbol": "MOTISONS",
  "company_name": "MOTISONS JEWELLERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0FRK01020",
  "face_value": 100.0
 },
 {
  "symbol": "MOTOGENFIN",
  "company_name": "MOTOR & GENERAL FINANCE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE861B01023",
  "face_value": 500.0
 },
 {
  "symbol": "MOTOUR",
  "company_name": "MOTILALAMC - MOTOUR",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01FP2",
  "face_value": 1000.0
 },
 {
  "symbol": "MOTOURINAV",
  "company_name": "MOTILALAMC - MOTOURINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000282",
  "face_value": 1000.0
 },
 {
  "symbol": "MOVALUE",
  "company_name": "MOTILALAMC - MOVALUE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01BE5",
  "face_value": 1000.0
 },
 {
  "symbol": "MOVALUINAV",
  "company_name": "MOTILALAMC - MOVALUINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF247L01BE5",
  "face_value": 1000.0
 },
 {
  "symbol": "MOY100INAV",
  "company_name": "MOTILALAMC - MOY100INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000304",
  "face_value": 1000.0
 },
 {
  "symbol": "MPAGROFERT",
  "company_name": "M P AGRO FERTILISERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY9408",
  "face_value": 1000.0
 },
 {
  "symbol": "MPHASIS",
  "company_name": "MPHASIS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE356A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "MPSLTD",
  "company_name": "MPS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE943D01017",
  "face_value": 1000.0
 },
 {
  "symbol": "MRF",
  "company_name": "MRF LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE883A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "MRPL",
  "company_name": "MRPL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE103A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MSCIADD",
  "company_name": "DSPAMC - MSCIADD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1WV7",
  "face_value": 1000.0
 },
 {
  "symbol": "MSCIADINAV",
  "company_name": "DSPAMC - MSCIADINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000320",
  "face_value": 1000.0
 },
 {
  "symbol": "MSCIINDIA",
  "company_name": "KOTAKMAMC - MSCIINDIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1VD2",
  "face_value": 1000.0
 },
 {
  "symbol": "MSCIININAV",
  "company_name": "MSCIINDIA - MSCIININAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000257",
  "face_value": 1000.0
 },
 {
  "symbol": "MSLIND",
  "company_name": "MSL INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE203501015",
  "face_value": 1000.0
 },
 {
  "symbol": "MSPL",
  "company_name": "MSP STEEL & POWER LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE752G01015",
  "face_value": 1000.0
 },
 {
  "symbol": "MSSHOES",
  "company_name": "M S SHOES EAST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE501201011",
  "face_value": 1000.0
 },
 {
  "symbol": "MSTCLTD",
  "company_name": "MSTC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE255X01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MSUMI",
  "company_name": "MOTHERSON SUMI WRNG IND L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0FS801015",
  "face_value": 100.0
 },
 {
  "symbol": "MTARTECH",
  "company_name": "MTAR TECHNOLOGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE864I01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MTEDUCARE",
  "company_name": "MT EDUCARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE472M01018",
  "face_value": 1000.0
 },
 {
  "symbol": "MTNL",
  "company_name": "MAHANAGAR TELEPHONE NIGAM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE153A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "MUFIN",
  "company_name": "MUFIN GREEN FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE08KJ01020",
  "face_value": 100.0
 },
 {
  "symbol": "MUFTI",
  "company_name": "CREDO BRANDS MARKETING L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE220Q01020",
  "face_value": 200.0
 },
 {
  "symbol": "MUKANDENGG",
  "company_name": "MUKAND ENGINEERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE022B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MUKANDLTD",
  "company_name": "MUKAND LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE304A01026",
  "face_value": 1000.0
 },
 {
  "symbol": "MUKATPIPE",
  "company_name": "MUKAT PIPES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE203601013",
  "face_value": 1000.0
 },
 {
  "symbol": "MUKERPAPER",
  "company_name": "MUKERIAN PAPER LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE203801019",
  "face_value": 1000.0
 },
 {
  "symbol": "MUKKA",
  "company_name": "MUKKA PROTEINS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0CG401037",
  "face_value": 100.0
 },
 {
  "symbol": "MUKTAARTS",
  "company_name": "MUKTA ARTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE374B01019",
  "face_value": 500.0
 },
 {
  "symbol": "MULCAPINAV",
  "company_name": "MIRAEAMC - MULCAPINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000239",
  "face_value": 1000.0
 },
 {
  "symbol": "MULTIARC",
  "company_name": "MULTI-ARC INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE204301019",
  "face_value": 1000.0
 },
 {
  "symbol": "MULTICAP",
  "company_name": "MIRAEAMC - MULTICAP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01LX9",
  "face_value": 1000.0
 },
 {
  "symbol": "MUNJALAU",
  "company_name": "MUNJAL AUTO IND. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE672B01032",
  "face_value": 200.0
 },
 {
  "symbol": "MUNJALSHOW",
  "company_name": "MUNJAL SHOWA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE577A01027",
  "face_value": 200.0
 },
 {
  "symbol": "MURABLACK",
  "company_name": "MURABLACK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE461501012",
  "face_value": 1000.0
 },
 {
  "symbol": "MURUDCERA",
  "company_name": "MURUDESHWAR CERAMICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE692B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "MUTHOOTCAP",
  "company_name": "MUTHOOT CAP SERV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE296G01013",
  "face_value": 1000.0
 },
 {
  "symbol": "MUTHOOTFIN",
  "company_name": "MUTHOOT FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE414G01012",
  "face_value": 1000.0
 },
 {
  "symbol": "MUTHOOTMF",
  "company_name": "MUTHOOT MICROFIN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE046W01019",
  "face_value": 1000.0
 },
 {
  "symbol": "MVGJL",
  "company_name": "MANOJ VAIBHAV GEM N JEW L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0KNT01012",
  "face_value": 1000.0
 },
 {
  "symbol": "MVL",
  "company_name": "MVL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE744I01034",
  "face_value": 100.0
 },
 {
  "symbol": "MWL",
  "company_name": "MANGALAM WORLDWIDE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0JYY01011",
  "face_value": 1000.0
 },
 {
  "symbol": "MYSOREBANK",
  "company_name": "STATE BANK OF MYSORE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE651A01020",
  "face_value": 1000.0
 },
 {
  "symbol": "MYSORPETRO",
  "company_name": "MYSORE PETROCHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE741A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "N1NSETEST",
  "company_name": "N1NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN003",
  "face_value": 1000.0
 },
 {
  "symbol": "NACL-RE",
  "company_name": "NACL INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE295D20012",
  "face_value": 100.0
 },
 {
  "symbol": "NACLIND",
  "company_name": "NACL INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE295D01020",
  "face_value": 100.0
 },
 {
  "symbol": "NAGAFERT",
  "company_name": "NAGARJUN FERT AND CHE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE454M01024",
  "face_value": 100.0
 },
 {
  "symbol": "NAGARJUFIN",
  "company_name": "NAGARJUNA FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE207401014",
  "face_value": 1000.0
 },
 {
  "symbol": "NAGAROIL",
  "company_name": "NAGARJUNA OIL REFINERY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE453M01018",
  "face_value": 100.0
 },
 {
  "symbol": "NAGREE-RE",
  "company_name": "NAGREEKA EXPORTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE123B20010",
  "face_value": 500.0
 },
 {
  "symbol": "NAGREEKCAP",
  "company_name": "NAGREEKA CAP & INFR.LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE245I01016",
  "face_value": 500.0
 },
 {
  "symbol": "NAGREEKEXP",
  "company_name": "NAGREEKA EXPORTS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE123B01028",
  "face_value": 500.0
 },
 {
  "symbol": "NAHARCAP",
  "company_name": "NAHAR CAP & FIN.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE049I01012",
  "face_value": 500.0
 },
 {
  "symbol": "NAHARINDUS",
  "company_name": "NAHAR INDS ENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE289A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "NAHARPOLY",
  "company_name": "NAHAR POLY FILMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE308A01027",
  "face_value": 500.0
 },
 {
  "symbol": "NAHARSPING",
  "company_name": "NAHAR SPINNING MILLS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE290A01027",
  "face_value": 500.0
 },
 {
  "symbol": "NAHARSUGAR",
  "company_name": "NAHAR SUGARS & ALLIED IND",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE208101019",
  "face_value": 1000.0
 },
 {
  "symbol": "NAKODA",
  "company_name": "NAKODA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE559B01023",
  "face_value": 500.0
 },
 {
  "symbol": "NAKODATEX",
  "company_name": "NAKODA TEXTILE INDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE208301015",
  "face_value": 1000.0
 },
 {
  "symbol": "NALCOCHEM",
  "company_name": "NALCO CHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE582A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "NAM-INDIA",
  "company_name": "NIPPON L I A M LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE298J01013",
  "face_value": 1000.0
 },
 {
  "symbol": "NAMTECHELE",
  "company_name": "NAMTECH ELETRONIC DEVICES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE607C01010",
  "face_value": 1000.0
 },
 {
  "symbol": "NANDANI-RE",
  "company_name": "NANDANI CREATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE696V20013",
  "face_value": 1000.0
 },
 {
  "symbol": "NARMA-RE",
  "company_name": "NARMADA AGROBASE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE117Z20011",
  "face_value": 1000.0
 },
 {
  "symbol": "NARMADA",
  "company_name": "NARMADA AGROBASE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE117Z01011",
  "face_value": 1000.0
 },
 {
  "symbol": "NARMADASUG",
  "company_name": "GIRDHARILAL SUGAR & ALLIE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE209601017",
  "face_value": 1000.0
 },
 {
  "symbol": "NATCAPSUQ",
  "company_name": "NATURAL CAPSULES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE936B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "NATCOPHARM",
  "company_name": "NATCO PHARMA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE987B01026",
  "face_value": 200.0
 },
 {
  "symbol": "NATHBIOGEN",
  "company_name": "NATH BIO-GENES (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE448G01010",
  "face_value": 1000.0
 },
 {
  "symbol": "NATHPULP",
  "company_name": "NATH PULP & PAPER MILLS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE776A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "NATIONALUM",
  "company_name": "NATIONAL ALUMINIUM CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE139A01034",
  "face_value": 500.0
 },
 {
  "symbol": "NATIONSTD",
  "company_name": "NATIONAL STAND (INDIA) L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE166R01015",
  "face_value": 1000.0
 },
 {
  "symbol": "NATNLSTEEL",
  "company_name": "NATIONAL STEEL & AGRO IND",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE088B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "NATPEROXID",
  "company_name": "NATIONAL PEROXIDE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY9466",
  "face_value": 10000.0
 },
 {
  "symbol": "NAUKRI",
  "company_name": "INFO EDGE (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE663F01032",
  "face_value": 200.0
 },
 {
  "symbol": "NAVA",
  "company_name": "NAVA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE725A01030",
  "face_value": 100.0
 },
 {
  "symbol": "NAVBHARENT",
  "company_name": "NAVBHARAT ENTERPRISES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE211901017",
  "face_value": 1000.0
 },
 {
  "symbol": "NAVINFLUOR",
  "company_name": "NAVIN FLUORINE INT. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE048G01026",
  "face_value": 200.0
 },
 {
  "symbol": "NAVINIFTY",
  "company_name": "NAVIAMC - NAVINIFTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF959L01HI3",
  "face_value": 1000.0
 },
 {
  "symbol": "NAVKARCORP",
  "company_name": "NAVKAR CORPORATION LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE278M01019",
  "face_value": 1000.0
 },
 {
  "symbol": "NAVKARURB",
  "company_name": "NAVKAR URBANSTRUCTURE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE268H01044",
  "face_value": 100.0
 },
 {
  "symbol": "NAVNETEDUL",
  "company_name": "NAVNEET EDUCATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE060A01024",
  "face_value": 200.0
 },
 {
  "symbol": "NAVNIFINAV",
  "company_name": "NAVIAMC - NAVNIFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000198",
  "face_value": 1000.0
 },
 {
  "symbol": "NAZARA",
  "company_name": "NAZARA TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE418L01047",
  "face_value": 200.0
 },
 {
  "symbol": "NBCC",
  "company_name": "NBCC (INDIA) LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE095N01031",
  "face_value": 100.0
 },
 {
  "symbol": "NBIFIN",
  "company_name": "N.B.I. IND. FIN. CO. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE365I01020",
  "face_value": 500.0
 },
 {
  "symbol": "NCC",
  "company_name": "NCC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE868B01028",
  "face_value": 200.0
 },
 {
  "symbol": "NCLIND",
  "company_name": "NCL INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE732C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "NDGL",
  "company_name": "NAGA DHUNSERI GROUP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE756C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "NDL",
  "company_name": "NANDAN DENIM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE875G01048",
  "face_value": 100.0
 },
 {
  "symbol": "NDLVENTURE",
  "company_name": "NDL VENTURES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE353A01023",
  "face_value": 1000.0
 },
 {
  "symbol": "NDRAUTO",
  "company_name": "NDR AUTO COMPONENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE07OG01012",
  "face_value": 1000.0
 },
 {
  "symbol": "NDTV",
  "company_name": "NDTV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE155G01029",
  "face_value": 400.0
 },
 {
  "symbol": "NDTV-RE",
  "company_name": "NEW DELHI TELEVISION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE155G20011",
  "face_value": 400.0
 },
 {
  "symbol": "NEAGI",
  "company_name": "NEELAMALAI AGRO INDS. L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE605D01012",
  "face_value": 1000.0
 },
 {
  "symbol": "NECCLTD",
  "company_name": "NORTH EAST CARRY CORP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE553C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "NECLIFE",
  "company_name": "NECTAR LIFESCIENCES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE023H01027",
  "face_value": 100.0
 },
 {
  "symbol": "NECLTD-RE",
  "company_name": "NORTH EAST CARRY CORP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE553C20016",
  "face_value": 1000.0
 },
 {
  "symbol": "NEDUNGBANK",
  "company_name": "NEDUNGADI BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE586A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "NELCAST",
  "company_name": "NELCAST LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE189I01024",
  "face_value": 200.0
 },
 {
  "symbol": "NELCO",
  "company_name": "NELCO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE045B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "NEOGEN",
  "company_name": "NEOGEN CHEMICALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE136S01016",
  "face_value": 1000.0
 },
 {
  "symbol": "NEOSACK",
  "company_name": "NEO SACK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE214101011",
  "face_value": 1000.0
 },
 {
  "symbol": "NEPCPAPER",
  "company_name": "NEPC PAPER & BOARD LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE471B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "NEPHROPLUS",
  "company_name": "NEPHROCARE HEALTH SERV L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE428V01029",
  "face_value": 200.0
 },
 {
  "symbol": "NESCO",
  "company_name": "NESCO LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE317F01035",
  "face_value": 200.0
 },
 {
  "symbol": "NESTLEIND",
  "company_name": "NESTLE INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE239A01024",
  "face_value": 100.0
 },
 {
  "symbol": "NETF",
  "company_name": "TATAAML - NETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF277K015R5",
  "face_value": 1000.0
 },
 {
  "symbol": "NETFINAV",
  "company_name": "NETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000142",
  "face_value": 100.0
 },
 {
  "symbol": "NETFSIINAV",
  "company_name": "NETFSILVER NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000044",
  "face_value": 1000.0
 },
 {
  "symbol": "NETWEB",
  "company_name": "NETWEB TECH INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0NT901020",
  "face_value": 200.0
 },
 {
  "symbol": "NETWORK",
  "company_name": "NETWORK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE214801016",
  "face_value": 1000.0
 },
 {
  "symbol": "NETWORK18",
  "company_name": "NETWORK18 MEDIA & INV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE870H01013",
  "face_value": 500.0
 },
 {
  "symbol": "NEUEON",
  "company_name": "NEUEON CORPORATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE333I01044",
  "face_value": 100.0
 },
 {
  "symbol": "NEULANDLAB",
  "company_name": "NEULAND LAB LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE794A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "NEWGEN",
  "company_name": "NEWGEN SOFTWARE TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE619B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "NEXT30ADD",
  "company_name": "DSPAMC - NEXT30ADD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1VE5",
  "face_value": 1000.0
 },
 {
  "symbol": "NEXT50",
  "company_name": "MIRAEAMC - MANXT50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01FN2",
  "face_value": 27500.0
 },
 {
  "symbol": "NEXT50ADD",
  "company_name": "DSPAMC - NEXT50ADD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1XU7",
  "face_value": 1000.0
 },
 {
  "symbol": "NEXT50BETA",
  "company_name": "UTIAMC-NEXT50BETA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF789F1AUW9",
  "face_value": 100.0
 },
 {
  "symbol": "NEXT50ETF",
  "company_name": "KOTAKMAMC - NEXT50ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1YO3",
  "face_value": 1000.0
 },
 {
  "symbol": "NEXT50IETF",
  "company_name": "ICICIPRAMC - ICICINXT50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC1NS5",
  "face_value": 100.0
 },
 {
  "symbol": "NEXT50INAV",
  "company_name": "DSPAMC - NEXT50INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000330",
  "face_value": 1000.0
 },
 {
  "symbol": "NEXT5EINAV",
  "company_name": "KOTAKMAMC - NEXT5EINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000331",
  "face_value": 1000.0
 },
 {
  "symbol": "NEXTMEDIA",
  "company_name": "NEXT MEDIAWORKS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE747B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "NFL",
  "company_name": "NATIONAL FERT. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE870D01012",
  "face_value": 1000.0
 },
 {
  "symbol": "NFQLTYINAV",
  "company_name": "BIRLASLAMC - NFQLTYINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000157",
  "face_value": 100.0
 },
 {
  "symbol": "NGIL",
  "company_name": "NAKODA GROUP OF IND. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE236Y01012",
  "face_value": 1000.0
 },
 {
  "symbol": "NGIL-RE",
  "company_name": "NAKODA GRP OF IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE236Y20012",
  "face_value": 1000.0
 },
 {
  "symbol": "NGIL-RE1",
  "company_name": "NAKODA GRP OF IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE236Y20020",
  "face_value": 1000.0
 },
 {
  "symbol": "NGIL-RE2",
  "company_name": "NAKODA GROUP OF IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE236Y20038",
  "face_value": 1000.0
 },
 {
  "symbol": "NGLFINE",
  "company_name": "NGL FINE CHEM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE887E01022",
  "face_value": 500.0
 },
 {
  "symbol": "NH",
  "company_name": "NARAYANA HRUDAYALAYA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE410P01011",
  "face_value": 1000.0
 },
 {
  "symbol": "NHPC",
  "company_name": "NHPC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE848E01016",
  "face_value": 1000.0
 },
 {
  "symbol": "NIACL",
  "company_name": "THE NEW INDIA ASSU CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE470Y01017",
  "face_value": 500.0
 },
 {
  "symbol": "NIBE",
  "company_name": "NIBE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE149O01018",
  "face_value": 1000.0
 },
 {
  "symbol": "NIBL",
  "company_name": "NRB INDUS. BEARINGS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE047O01014",
  "face_value": 200.0
 },
 {
  "symbol": "NIF100BEES",
  "company_name": "NIP IND ETF NIFTY 100",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204K014N5",
  "face_value": 1000.0
 },
 {
  "symbol": "NIF100IETF",
  "company_name": "ICICI PRUD NIFTY 100 ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC16V9",
  "face_value": 100.0
 },
 {
  "symbol": "NIF100INAV",
  "company_name": "KOTAKMAMC - NIF100INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000259",
  "face_value": 1000.0
 },
 {
  "symbol": "NIF10GINAV",
  "company_name": "UTIAMC - NIF10GINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000214",
  "face_value": 1000.0
 },
 {
  "symbol": "NIF5GINAV",
  "company_name": "UTIAMC - NIF5GINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000213",
  "face_value": 1000.0
 },
 {
  "symbol": "NIFITEINAV",
  "company_name": "UTIAMC - NIFITEINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000212",
  "face_value": 1000.0
 },
 {
  "symbol": "NIFTY1",
  "company_name": "KOTAK NIFTY ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174K014P6",
  "face_value": 100.0
 },
 {
  "symbol": "NIFTY100EW",
  "company_name": "KOTAKMAMC - NIFTY100EW",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1UW4",
  "face_value": 1000.0
 },
 {
  "symbol": "NIFTYADD",
  "company_name": "DSPAMC - DSPNIFTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1CL0",
  "face_value": 1000.0
 },
 {
  "symbol": "NIFTYBEES",
  "company_name": "NIP IND ETF NIFTY BEES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KB14I2",
  "face_value": 100.0
 },
 {
  "symbol": "NIFTYBENAV",
  "company_name": "NIFTY BEES NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000024",
  "face_value": 1000.0
 },
 {
  "symbol": "NIFTYBETA",
  "company_name": "UTIAMC-NIFTYBETA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF789F1AZC0",
  "face_value": 100.0
 },
 {
  "symbol": "NIFTYBETF",
  "company_name": "BFAM - NIFTYBETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF0QA701722",
  "face_value": 1000.0
 },
 {
  "symbol": "NIFTYBINAV",
  "company_name": "BFAM - NIFTYBETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000211",
  "face_value": 1000.0
 },
 {
  "symbol": "NIFTYCASE",
  "company_name": "ZERODHAAMC - NIFTYCASE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF0R8F01166",
  "face_value": 1000.0
 },
 {
  "symbol": "NIFTYCINAV",
  "company_name": "ZERODHAAMC - NIFTYCINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000307",
  "face_value": 1000.0
 },
 {
  "symbol": "NIFTYEES",
  "company_name": "EDELWEISS ETF - NIFTY 50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF754K01EK3",
  "face_value": 1000.0
 },
 {
  "symbol": "NIFTYETF",
  "company_name": "MIRAEAMC - MAN50ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01EG9",
  "face_value": 10000.0
 },
 {
  "symbol": "NIFTYIETF",
  "company_name": "ICICI PRUD NIFTY ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109K012R6",
  "face_value": 1000.0
 },
 {
  "symbol": "NIFTYQLITY",
  "company_name": "BIRLASLAMC - NIFTYQLITY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KB15K4",
  "face_value": 100.0
 },
 {
  "symbol": "NIHONIRMAN",
  "company_name": "NIHON NIRMAAN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE216801014",
  "face_value": 1000.0
 },
 {
  "symbol": "NIITLTD",
  "company_name": "NIIT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE161A01038",
  "face_value": 200.0
 },
 {
  "symbol": "NIITMTS",
  "company_name": "NIIT LEARNING SYSTEMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE342G01023",
  "face_value": 200.0
 },
 {
  "symbol": "NILAINFRA",
  "company_name": "NILA INFRASTRUCTURES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE937C01029",
  "face_value": 100.0
 },
 {
  "symbol": "NILASPACES",
  "company_name": "NILA SPACES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00S901012",
  "face_value": 100.0
 },
 {
  "symbol": "NILE",
  "company_name": "NILE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE445D01013",
  "face_value": 1000.0
 },
 {
  "symbol": "NILKAMAL",
  "company_name": "NILKAMAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE310A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "NIM150INAV",
  "company_name": "UTIAMC - NIM150INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000197",
  "face_value": 1000.0
 },
 {
  "symbol": "NIMBSPROJ",
  "company_name": "NIMBUS PROJECTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE875B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "NINSYS",
  "company_name": "NINTEC SYSTEMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE395U01014",
  "face_value": 1000.0
 },
 {
  "symbol": "NIPPOBATRY",
  "company_name": "INDO-NATIONAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE567A01028",
  "face_value": 500.0
 },
 {
  "symbol": "NIPPONDENS",
  "company_name": "DENSO INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE502A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "NIRAJ",
  "company_name": "NIRAJ CEMENT STRUC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE368I01016",
  "face_value": 1000.0
 },
 {
  "symbol": "NIRAJISPAT",
  "company_name": "NIRAJ ISPAT IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE326T01011",
  "face_value": 1000.0
 },
 {
  "symbol": "NIRAJPETRO",
  "company_name": "NIRAJ PETRO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE217601017",
  "face_value": 1000.0
 },
 {
  "symbol": "NIRLON",
  "company_name": "NIRLON LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE910A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "NITCO",
  "company_name": "NITCO LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE858F01012",
  "face_value": 1000.0
 },
 {
  "symbol": "NITINFIRE",
  "company_name": "NITIN FIRE PROT IND. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE489H01020",
  "face_value": 200.0
 },
 {
  "symbol": "NITINSPIN",
  "company_name": "NITIN SPINNERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE229H01012",
  "face_value": 1000.0
 },
 {
  "symbol": "NITIRAJ",
  "company_name": "NITIRAJ ENGINEERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE439T01012",
  "face_value": 1000.0
 },
 {
  "symbol": "NITTAGELA",
  "company_name": "NITTA GELATIN INDIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE265B01019",
  "face_value": 1000.0
 },
 {
  "symbol": "NIVABUPA",
  "company_name": "NIVA BUPA HEALTH INS CO L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE995S01015",
  "face_value": 1000.0
 },
 {
  "symbol": "NIYATILEAS",
  "company_name": "NIYATI INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY9410",
  "face_value": 1000.0
 },
 {
  "symbol": "NKIND",
  "company_name": "NK INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE542C01019",
  "face_value": 1000.0
 },
 {
  "symbol": "NLCINDIA",
  "company_name": "NLC INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE589A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "NMDC",
  "company_name": "NMDC LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE584A01023",
  "face_value": 100.0
 },
 {
  "symbol": "NOCIL",
  "company_name": "NOCIL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE163A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "NOESISIND",
  "company_name": "NOESIS INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE141B01020",
  "face_value": 1000.0
 },
 {
  "symbol": "NOIDATOLL",
  "company_name": "NOIDA TOLL BRIDGE CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE781B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "NORBTEAEXP",
  "company_name": "NORBEN TEA & EXPORTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE369C01017",
  "face_value": 1000.0
 },
 {
  "symbol": "NORTHARC",
  "company_name": "NORTHERN ARC CAPITAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE850M01015",
  "face_value": 1000.0
 },
 {
  "symbol": "NORTHSUG",
  "company_name": "NORTHLAND SUGAR COM. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE219501017",
  "face_value": 1000.0
 },
 {
  "symbol": "NOVAAGRI",
  "company_name": "NOVA AGRITECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02H701025",
  "face_value": 200.0
 },
 {
  "symbol": "NOVARTIND",
  "company_name": "NOVARTIS INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE234A01025",
  "face_value": 500.0
 },
 {
  "symbol": "NPBET",
  "company_name": "TATAAML - NPBET",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF277K010X4",
  "face_value": 1000.0
 },
 {
  "symbol": "NPBETINAV",
  "company_name": "NPBET INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000144",
  "face_value": 100.0
 },
 {
  "symbol": "NPST",
  "company_name": "NETWORK PEOPLE SRV TECH L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0FFK01017",
  "face_value": 1000.0
 },
 {
  "symbol": "NRAIL",
  "company_name": "N R AGARWAL INDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE740D01017",
  "face_value": 1000.0
 },
 {
  "symbol": "NRBBEARING",
  "company_name": "NRB BEARING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE349A01021",
  "face_value": 200.0
 },
 {
  "symbol": "NRL",
  "company_name": "NUPUR RECYCLERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0JM501013",
  "face_value": 1000.0
 },
 {
  "symbol": "NSDL",
  "company_name": "NATIONAL SECURITIES DEP L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000312",
  "face_value": 200.0
 },
 {
  "symbol": "NSIL",
  "company_name": "NALWA SONS INVESTMENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE023A01030",
  "face_value": 1000.0
 },
 {
  "symbol": "NSLNISP",
  "company_name": "NMDC STEEL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0NNS01018",
  "face_value": 1000.0
 },
 {
  "symbol": "NTPC",
  "company_name": "NTPC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE733E01010",
  "face_value": 1000.0
 },
 {
  "symbol": "NTPCGREEN",
  "company_name": "NTPC GREEN ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0ONG01011",
  "face_value": 1000.0
 },
 {
  "symbol": "NUCLEUS",
  "company_name": "NUCLEUS SOFTWARE EXPORTS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE096B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "NURECA",
  "company_name": "NURECA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0DSF01015",
  "face_value": 1000.0
 },
 {
  "symbol": "NUTEK",
  "company_name": "NU TEK INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE318J01027",
  "face_value": 500.0
 },
 {
  "symbol": "NUVAMA",
  "company_name": "NUVAMA WEALTH MANAGE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE531F01023",
  "face_value": 200.0
 },
 {
  "symbol": "NUVOCO",
  "company_name": "NUVOCO VISTAS CORP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE118D01016",
  "face_value": 1000.0
 },
 {
  "symbol": "NV20",
  "company_name": "KOTAKMAMC - KTKNV20ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1ZE1",
  "face_value": 100.0
 },
 {
  "symbol": "NV20BEES",
  "company_name": "NIP IND ETF ETF NV20",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KB18I3",
  "face_value": 100.0
 },
 {
  "symbol": "NV20IETF",
  "company_name": "ICICI PRUDENTIAL NV20 ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC11V0",
  "face_value": 100.0
 },
 {
  "symbol": "NX30ADINAV",
  "company_name": "DSPAMC - NX30ADINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000254",
  "face_value": 1000.0
 },
 {
  "symbol": "NXTDIG-RE",
  "company_name": "NXTDIGITAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE353A20015",
  "face_value": 1000.0
 },
 {
  "symbol": "NYKAA",
  "company_name": "FSN E COMMERCE VENTURES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE388Y01029",
  "face_value": 100.0
 },
 {
  "symbol": "OAL",
  "company_name": "ORIENTAL AROMATICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE959C01023",
  "face_value": 500.0
 },
 {
  "symbol": "OBCL",
  "company_name": "ORISSA BENGAL CARRIER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE426Z01016",
  "face_value": 1000.0
 },
 {
  "symbol": "OBEROIRLTY",
  "company_name": "OBEROI REALTY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE093I01010",
  "face_value": 1000.0
 },
 {
  "symbol": "OCCL",
  "company_name": "ORIENTAL CARBN & CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE321D01016",
  "face_value": 1000.0
 },
 {
  "symbol": "OCCLLTD",
  "company_name": "OCCL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0PK601023",
  "face_value": 200.0
 },
 {
  "symbol": "ODIGMA",
  "company_name": "ODIGMA CONSULTANCY SOL L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE054301028",
  "face_value": 100.0
 },
 {
  "symbol": "OFSS",
  "company_name": "ORACLE FIN SERV SOFT LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE881D01027",
  "face_value": 500.0
 },
 {
  "symbol": "OIL",
  "company_name": "OIL INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE274J01014",
  "face_value": 1000.0
 },
 {
  "symbol": "OILCOUNTUB",
  "company_name": "OIL COUNTRY TUBULAR LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE591A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "OILETFINAV",
  "company_name": "ICICIPRAMC - OILETFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000234",
  "face_value": 1000.0
 },
 {
  "symbol": "OILIETF",
  "company_name": "ICICIPRAMC - OILIETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC18W3",
  "face_value": 1000.0
 },
 {
  "symbol": "OISL",
  "company_name": "OCL IRON AND STEEL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE196J01019",
  "face_value": 100.0
 },
 {
  "symbol": "OLAELEC",
  "company_name": "OLA ELECTRIC MOBILITY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0LXG01040",
  "face_value": 1000.0
 },
 {
  "symbol": "OLECTRA",
  "company_name": "OLECTRA GREENTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE260D01016",
  "face_value": 400.0
 },
 {
  "symbol": "OMAXAUTO",
  "company_name": "OMAX AUTOS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE090B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "OMAXE",
  "company_name": "OMAXE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE800H01010",
  "face_value": 1000.0
 },
 {
  "symbol": "OMFREIGHT",
  "company_name": "OM FREIGHT FORWARDERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1BZC01019",
  "face_value": 1000.0
 },
 {
  "symbol": "OMINFRAL",
  "company_name": "OM INFRA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE239D01028",
  "face_value": 100.0
 },
 {
  "symbol": "OMKARCHEM",
  "company_name": "OMKAR SPL CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE474L01016",
  "face_value": 1000.0
 },
 {
  "symbol": "OMNI",
  "company_name": "OMNITECH ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0UH301010",
  "face_value": 500.0
 },
 {
  "symbol": "OMPOWER",
  "company_name": "OM POWER TRANSMISSION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE25E901019",
  "face_value": 1000.0
 },
 {
  "symbol": "ONECAP-RE",
  "company_name": "ONELIFE ADVISORS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE912L20015",
  "face_value": 1000.0
 },
 {
  "symbol": "ONELIFECAP",
  "company_name": "ONELIFE CAP ADVISORS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE912L01015",
  "face_value": 1000.0
 },
 {
  "symbol": "ONEPOINT",
  "company_name": "ONE POINT ONE SOL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE840Y01029",
  "face_value": 200.0
 },
 {
  "symbol": "ONESOURCE",
  "company_name": "ONESOURCE SPECL PHARMA L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE013P01021",
  "face_value": 100.0
 },
 {
  "symbol": "ONGC",
  "company_name": "OIL AND NATURAL GAS CORP.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE213A01029",
  "face_value": 500.0
 },
 {
  "symbol": "ONIDASAVAK",
  "company_name": "ONIDA SAVAK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE224101019",
  "face_value": 1000.0
 },
 {
  "symbol": "ONMOBILE",
  "company_name": "ONMOBILE GLOBAL LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE809I01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ONWARDTEC",
  "company_name": "ONWARD TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE229A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "OPTELCOMM",
  "company_name": "OPTEL TELECOM. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE567701011",
  "face_value": 1000.0
 },
 {
  "symbol": "OPTIEMUS",
  "company_name": "OPTIEMUS INFRACOM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE350C01017",
  "face_value": 1000.0
 },
 {
  "symbol": "OPTOCIRCUI",
  "company_name": "OPTO CIRCUITS (I) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE808B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "ORBTEXP",
  "company_name": "ORBIT EXPORTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE231G01010",
  "face_value": 1000.0
 },
 {
  "symbol": "ORCHASP",
  "company_name": "ORCHASP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE215B01022",
  "face_value": 200.0
 },
 {
  "symbol": "ORCHIDPHAR",
  "company_name": "ORCHID PHARMA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE191A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ORCHPHARMA",
  "company_name": "ORCHID PHARMA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE191A01027",
  "face_value": 1000.0
 },
 {
  "symbol": "ORICONENT",
  "company_name": "ORICON ENTERPRISES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE730A01022",
  "face_value": 200.0
 },
 {
  "symbol": "ORIENT-RE",
  "company_name": "ORIENTAL TRIMEX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE998H20012",
  "face_value": 1000.0
 },
 {
  "symbol": "ORIENTALTL",
  "company_name": "ORIENTAL TRIMEX LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE998H01012",
  "face_value": 1000.0
 },
 {
  "symbol": "ORIENTBELL",
  "company_name": "ORIENT BELL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE607D01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ORIENTCARB",
  "company_name": "ORIENTAL CARBON & CHEM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE225301014",
  "face_value": 1000.0
 },
 {
  "symbol": "ORIENTCEM",
  "company_name": "ORIENT CEMENT LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE876N01018",
  "face_value": 100.0
 },
 {
  "symbol": "ORIENTCER",
  "company_name": "ORIENT CERATECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE569C01020",
  "face_value": 100.0
 },
 {
  "symbol": "ORIENTCONT",
  "company_name": "ORIENTAL CONTAINERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE730A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "ORIENTELEC",
  "company_name": "ORIENT ELECTRIC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE142Z01019",
  "face_value": 100.0
 },
 {
  "symbol": "ORIENTHOT",
  "company_name": "ORIENT HOTELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE750A01020",
  "face_value": 100.0
 },
 {
  "symbol": "ORIENTLTD",
  "company_name": "ORIENT PRESS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE609C01024",
  "face_value": 1000.0
 },
 {
  "symbol": "ORIENTPPR",
  "company_name": "ORIENT PAPER AND INDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE592A01026",
  "face_value": 100.0
 },
 {
  "symbol": "ORIENTTECH",
  "company_name": "ORIENT TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0PPK01015",
  "face_value": 1000.0
 },
 {
  "symbol": "ORISSAMINE",
  "company_name": "ORISSA MIN DEV CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE725E01024",
  "face_value": 100.0
 },
 {
  "symbol": "ORKAY",
  "company_name": "ORKAY INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE226801012",
  "face_value": 1000.0
 },
 {
  "symbol": "ORKLAINDIA",
  "company_name": "ORKLA INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE16NZ01023",
  "face_value": 100.0
 },
 {
  "symbol": "ORTEL",
  "company_name": "ORTEL COMMUNICATIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE849L01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ORTINGLOBE",
  "company_name": "ORTIN GLOBAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE749B01020",
  "face_value": 1000.0
 },
 {
  "symbol": "ORTINLABSS",
  "company_name": "ORTIN LABORATORIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE749B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "ORTONSYNTH",
  "company_name": "ORTON SYNTHETICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE462101010",
  "face_value": 1000.0
 },
 {
  "symbol": "OSIAHYPER",
  "company_name": "OSIA HYPER RETAIL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE06IR01021",
  "face_value": 100.0
 },
 {
  "symbol": "OSWALAGFUR",
  "company_name": "OSWAL AGRO FURANE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE227301012",
  "face_value": 1000.0
 },
 {
  "symbol": "OSWALAGRO",
  "company_name": "OSWAL AGRO MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE142A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "OSWALGREEN",
  "company_name": "OSWAL GREENTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE143A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "OSWALPUMPS",
  "company_name": "OSWAL PUMPS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0BYP01024",
  "face_value": 100.0
 },
 {
  "symbol": "OSWALSEEDS",
  "company_name": "SHREEOSWAL S AND CHE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00IK01029",
  "face_value": 200.0
 },
 {
  "symbol": "OSWALSPG",
  "company_name": "OSWAL SPG & WEAVING MILLS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE227701013",
  "face_value": 1000.0
 },
 {
  "symbol": "OSWALSUG",
  "company_name": "OSWAL SUGARS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE227801011",
  "face_value": 1000.0
 },
 {
  "symbol": "OTIS",
  "company_name": "OTIS ELEVATOR COMPANY (I)",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE099A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "OTOKLIN",
  "company_name": "OTOKLIN PLANTS & EQUIP. L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE228201013",
  "face_value": 1000.0
 },
 {
  "symbol": "PAAMDRUG",
  "company_name": "PAAM DRUGS & PHARMA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE229401018",
  "face_value": 1000.0
 },
 {
  "symbol": "PAAMPHARMA",
  "company_name": "PAAM PHARMACEUTICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE229501015",
  "face_value": 1000.0
 },
 {
  "symbol": "PACEDIGITK",
  "company_name": "PACE DIGITEK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0S3G01027",
  "face_value": 200.0
 },
 {
  "symbol": "PACIFICIND",
  "company_name": "PACIFIC INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE229701011",
  "face_value": 1000.0
 },
 {
  "symbol": "PADMINPOLY",
  "company_name": "PADMINI TECHNOLOGIES  LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE114B01019",
  "face_value": 1000.0
 },
 {
  "symbol": "PAEL",
  "company_name": "PAE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE766A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PAGEIND",
  "company_name": "PAGE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE761H01022",
  "face_value": 1000.0
 },
 {
  "symbol": "PAISALO",
  "company_name": "PAISALO DIGITAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE420C01059",
  "face_value": 100.0
 },
 {
  "symbol": "PAKKA",
  "company_name": "PAKKA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE551D01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PALASHSECU",
  "company_name": "PALASH SECURITIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE471W01019",
  "face_value": 1000.0
 },
 {
  "symbol": "PALCREDIT",
  "company_name": "PAL CREDIT & CAPITAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE230201019",
  "face_value": 1000.0
 },
 {
  "symbol": "PALREDTEC",
  "company_name": "PALRED TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE218G01033",
  "face_value": 1000.0
 },
 {
  "symbol": "PANACEABIO",
  "company_name": "PANACEA BIOTEC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE922B01023",
  "face_value": 100.0
 },
 {
  "symbol": "PANACHE",
  "company_name": "PANACHE DIGILIFE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE895W01019",
  "face_value": 1000.0
 },
 {
  "symbol": "PANAMAPET",
  "company_name": "PANAMA PETROCHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE305C01029",
  "face_value": 200.0
 },
 {
  "symbol": "PANASIGLOB",
  "company_name": "PAN ASIA GLOBAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE568001015",
  "face_value": 1000.0
 },
 {
  "symbol": "PANCARBON",
  "company_name": "PANA CARBON IND CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE013E01017",
  "face_value": 1000.0
 },
 {
  "symbol": "PANCHMSTEL",
  "company_name": "PANCHMAHAL STEEL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE231301016",
  "face_value": 1000.0
 },
 {
  "symbol": "PANDGRAPH",
  "company_name": "PANDIAN GRAPHITES (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE231401014",
  "face_value": 1000.0
 },
 {
  "symbol": "PANSARI",
  "company_name": "PANSARI DEVELOPERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE697V01011",
  "face_value": 1000.0
 },
 {
  "symbol": "PANYAMCEM",
  "company_name": "PANYAM CEMENT MINING INDS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE232101019",
  "face_value": 10000.0
 },
 {
  "symbol": "PAR",
  "company_name": "PAR DRUGS AND CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE04LG01015",
  "face_value": 1000.0
 },
 {
  "symbol": "PARABDRUGS",
  "company_name": "PARABOLIC DRUGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE618H01016",
  "face_value": 1000.0
 },
 {
  "symbol": "PARACABLES",
  "company_name": "PARAMOUNT COMM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE074B01023",
  "face_value": 200.0
 },
 {
  "symbol": "PARADEEP",
  "company_name": "PARADEEP PHOSPHATES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE088F01024",
  "face_value": 1000.0
 },
 {
  "symbol": "PARAGMILK",
  "company_name": "PARAG MILK FOODS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE883N01014",
  "face_value": 1000.0
 },
 {
  "symbol": "PARAS",
  "company_name": "PARAS DEF AND SPCE TECH L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE045601023",
  "face_value": 500.0
 },
 {
  "symbol": "PARASIND",
  "company_name": "PARASRAMPURIA INDUSTRIES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE462601019",
  "face_value": 1000.0
 },
 {
  "symbol": "PARASPETRO",
  "company_name": "PARAS PETROFILS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE162C01024",
  "face_value": 100.0
 },
 {
  "symbol": "PARKHOSPS",
  "company_name": "PARK MEDI WORLD LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE119201023",
  "face_value": 200.0
 },
 {
  "symbol": "PARKHOTELS",
  "company_name": "PARKHOTELS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE988S01028",
  "face_value": 100.0
 },
 {
  "symbol": "PARRYAGRO",
  "company_name": "PARRY AGRO INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE187C01013",
  "face_value": 1000.0
 },
 {
  "symbol": "PARSSYNTH",
  "company_name": "PARASRAMPURIA SYNTHETICS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE232501010",
  "face_value": 1000.0
 },
 {
  "symbol": "PARSVNATH",
  "company_name": "PARSVNATH DEVELOPER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE561H01026",
  "face_value": 500.0
 },
 {
  "symbol": "PASHUPATI",
  "company_name": "PASHUPATI COTSPIN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE124Y01028",
  "face_value": 100.0
 },
 {
  "symbol": "PASUPATSPG",
  "company_name": "PASHUPATI SPG & WVG MILLS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE234301013",
  "face_value": 1000.0
 },
 {
  "symbol": "PASUPTAC",
  "company_name": "PASUPATI ACRYLON LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE818B01023",
  "face_value": 1000.0
 },
 {
  "symbol": "PASUPTACRY",
  "company_name": "PASUPATI ACRYLON LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE234101017",
  "face_value": 1000.0
 },
 {
  "symbol": "PATANJALI",
  "company_name": "PATANJALI FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE619A01035",
  "face_value": 200.0
 },
 {
  "symbol": "PATEL-RE",
  "company_name": "PATEL ENGINEERING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE244B20014",
  "face_value": 100.0
 },
 {
  "symbol": "PATELEG-RE",
  "company_name": "PATEL ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE244B20022",
  "face_value": 100.0
 },
 {
  "symbol": "PATELENG",
  "company_name": "PATEL ENGINEERING LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE244B01030",
  "face_value": 100.0
 },
 {
  "symbol": "PATELRMART",
  "company_name": "PATEL RETAIL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0R8B01010",
  "face_value": 1000.0
 },
 {
  "symbol": "PATINT-RE",
  "company_name": "PATEL INTEGRATED RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE529D20014",
  "face_value": 1000.0
 },
 {
  "symbol": "PATINT-RE1",
  "company_name": "PATEL INTEGRATED LOGISTIC",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE529D20022",
  "face_value": 1000.0
 },
 {
  "symbol": "PATINT-RE2",
  "company_name": "PATEL INTEGRATED LOGISTIC",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE529D20030",
  "face_value": 1000.0
 },
 {
  "symbol": "PATINTLOG",
  "company_name": "PATEL INT. LOG. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE529D01014",
  "face_value": 1000.0
 },
 {
  "symbol": "PATSPINLTD",
  "company_name": "PATSPIN INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE790C01014",
  "face_value": 1000.0
 },
 {
  "symbol": "PAUSHAKLTD",
  "company_name": "PAUSHAK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE111F01024",
  "face_value": 500.0
 },
 {
  "symbol": "PAVNAIND",
  "company_name": "PAVNA INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE07S101038",
  "face_value": 100.0
 },
 {
  "symbol": "PAYTM",
  "company_name": "ONE 97 COMMUNICATIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE982J01020",
  "face_value": 100.0
 },
 {
  "symbol": "PBAINFRA",
  "company_name": "PBA INFRASTRUCTURE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE160H01019",
  "face_value": 1000.0
 },
 {
  "symbol": "PCBL",
  "company_name": "PCBL CHEMICAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE602A01031",
  "face_value": 100.0
 },
 {
  "symbol": "PCJEWELLER",
  "company_name": "PC JEWELLER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE785M01021",
  "face_value": 100.0
 },
 {
  "symbol": "PCL",
  "company_name": "PERTECH COMPUTERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE238701010",
  "face_value": 1000.0
 },
 {
  "symbol": "PDMJEPAPER",
  "company_name": "PUDUMJEE PAPER PRO. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE865T01018",
  "face_value": 100.0
 },
 {
  "symbol": "PDPL",
  "company_name": "PARENTERAL DRUGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE904D01019",
  "face_value": 1000.0
 },
 {
  "symbol": "PDSL",
  "company_name": "PDS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE111Q01021",
  "face_value": 200.0
 },
 {
  "symbol": "PEARLPOLY",
  "company_name": "PEARL POLYMERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE844A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "PEERABASAN",
  "company_name": "PEERLESS ABASAN FINANCE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE236501016",
  "face_value": 1000.0
 },
 {
  "symbol": "PEL",
  "company_name": "PIRAMAL ENTERPRISES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE140A01024",
  "face_value": 200.0
 },
 {
  "symbol": "PENAPATSEC",
  "company_name": "PENNAR PATERSON LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE237201012",
  "face_value": 1000.0
 },
 {
  "symbol": "PENARSTEEL",
  "company_name": "PENNAR INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE932A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "PENIND",
  "company_name": "PENNAR INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE932A01024",
  "face_value": 500.0
 },
 {
  "symbol": "PENINLAND",
  "company_name": "PENINSULA LAND LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE138A01028",
  "face_value": 200.0
 },
 {
  "symbol": "PENNARALUM",
  "company_name": "PENNAR ALUMINIUM CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE057C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PENTFRPROD",
  "company_name": "PENTAFOUR PRODUCTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE237501015",
  "face_value": 1000.0
 },
 {
  "symbol": "PENTFRSOLC",
  "company_name": "PENTAFOUR SOLEC TECHNOLOG",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE237701011",
  "face_value": 1000.0
 },
 {
  "symbol": "PERMAGNET",
  "company_name": "PERMANENT MAGNETS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE462801015",
  "face_value": 1000.0
 },
 {
  "symbol": "PERSISTENT",
  "company_name": "PERSISTENT SYSTEMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE262H01021",
  "face_value": 500.0
 },
 {
  "symbol": "PETRONENGG",
  "company_name": "PETRON ENGG CONSTRUCT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE742A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "PETRONET",
  "company_name": "PETRONET LNG LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE347G01014",
  "face_value": 1000.0
 },
 {
  "symbol": "PFC",
  "company_name": "POWER FIN CORP LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE134E01011",
  "face_value": 1000.0
 },
 {
  "symbol": "PFIMXPHARM",
  "company_name": "PFIMEX PHARMACEUTICALS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE239101012",
  "face_value": 1000.0
 },
 {
  "symbol": "PFIZER",
  "company_name": "PFIZER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE182A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PFOCUS",
  "company_name": "PRIME FOCUS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE367G01038",
  "face_value": 100.0
 },
 {
  "symbol": "PFS",
  "company_name": "PTC INDIA FIN SERV LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE560K01014",
  "face_value": 1000.0
 },
 {
  "symbol": "PGEL",
  "company_name": "PG ELECTROPLAST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE457L01029",
  "face_value": 100.0
 },
 {
  "symbol": "PGHH",
  "company_name": "P&G HYGIENE & HEALTH CARE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE179A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "PGHL",
  "company_name": "PROCTER & GAMBLE HEALTH L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE199A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "PGIL",
  "company_name": "PEARL GLOBAL IND LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE940H01022",
  "face_value": 500.0
 },
 {
  "symbol": "PHARMABEES",
  "company_name": "NIPPONAMC - NETFPHARMA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KC1089",
  "face_value": 1000.0
 },
 {
  "symbol": "PHARMAINAV",
  "company_name": "PHARMABEES INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000131",
  "face_value": 100.0
 },
 {
  "symbol": "PHILIPS",
  "company_name": "PHILIPS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE319A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "PHOENIXLTD",
  "company_name": "THE PHOENIX MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE211B01039",
  "face_value": 200.0
 },
 {
  "symbol": "PHOENXINTL",
  "company_name": "PHOENIX INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE245B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "PICCADIL",
  "company_name": "PICCADILY AGRO INDUSTRI L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE546C01010",
  "face_value": 1000.0
 },
 {
  "symbol": "PICCADSUG",
  "company_name": "PICCADILLY SUGAR & ALLIED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE240601018",
  "face_value": 1000.0
 },
 {
  "symbol": "PIDILITIND",
  "company_name": "PIDILITE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE318A01026",
  "face_value": 100.0
 },
 {
  "symbol": "PIGL",
  "company_name": "POWER INSTRUMENT (G) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE557Z01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PIIND",
  "company_name": "PI INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE603J01030",
  "face_value": 100.0
 },
 {
  "symbol": "PILANIINVS",
  "company_name": "PILANI INV & IND COR LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE417C01014",
  "face_value": 1000.0
 },
 {
  "symbol": "PILITA",
  "company_name": "PIL ITALICA LIFESTYLE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE600A01035",
  "face_value": 100.0
 },
 {
  "symbol": "PINCON",
  "company_name": "PINCON SPIRIT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE675G01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PINDLTD",
  "company_name": "P I INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY9416",
  "face_value": 1000.0
 },
 {
  "symbol": "PINELABS",
  "company_name": "PINE LABS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE15B701018",
  "face_value": 100.0
 },
 {
  "symbol": "PIONDIST",
  "company_name": "PIONEER DIST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE889E01010",
  "face_value": 1000.0
 },
 {
  "symbol": "PIONEEREMB",
  "company_name": "PIONEER EMBROIDERIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE156C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PIONRINV",
  "company_name": "PIONEER INVESTCORP LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE746D01014",
  "face_value": 1000.0
 },
 {
  "symbol": "PIRAMALFIN",
  "company_name": "PIRAMAL FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE202B01038",
  "face_value": 200.0
 },
 {
  "symbol": "PITTIECEM",
  "company_name": "PITTIE CEMENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE242101017",
  "face_value": 1000.0
 },
 {
  "symbol": "PITTIEFIN",
  "company_name": "PITTIE FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE242201015",
  "face_value": 1000.0
 },
 {
  "symbol": "PITTIENG",
  "company_name": "PITTI ENGINEERING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE450D01021",
  "face_value": 500.0
 },
 {
  "symbol": "PIXTRANS",
  "company_name": "PIX TRANSMISSIONS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE751B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PKTEA",
  "company_name": "THE P K TEA PROD CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE431F01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PLASTIBLEN",
  "company_name": "PLASTIBLENDS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE083C01022",
  "face_value": 500.0
 },
 {
  "symbol": "PLATIND",
  "company_name": "PLATINUM INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0PT501018",
  "face_value": 1000.0
 },
 {
  "symbol": "PLAZACABLE",
  "company_name": "PLAZA WIRES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0INJ01017",
  "face_value": 1000.0
 },
 {
  "symbol": "PLPHAR-RE",
  "company_name": "PIRAMAL PHARMA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0DK520011",
  "face_value": 1000.0
 },
 {
  "symbol": "PML",
  "company_name": "PAUL MERCHANTS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE291E01019",
  "face_value": 1000.0
 },
 {
  "symbol": "PNB",
  "company_name": "PUNJAB NATIONAL BANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE160A01022",
  "face_value": 200.0
 },
 {
  "symbol": "PNB-RE",
  "company_name": "PNB HOUSING FIN LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE572E20012",
  "face_value": 1000.0
 },
 {
  "symbol": "PNBGILTS",
  "company_name": "PNB GILTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE859A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "PNBHOUSING",
  "company_name": "PNB HOUSING FIN LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE572E01012",
  "face_value": 1000.0
 },
 {
  "symbol": "PNC",
  "company_name": "PRITISH NANDY COMMUNICATI",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE392B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "PNCINFRA",
  "company_name": "PNC INFRATECH LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE195J01029",
  "face_value": 200.0
 },
 {
  "symbol": "PNGJL",
  "company_name": "P N GADGIL JEWELLERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE953R01016",
  "face_value": 1000.0
 },
 {
  "symbol": "PNGSREVA",
  "company_name": "PNGS REVA DIAMOND JEWEL L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1RDG01013",
  "face_value": 1000.0
 },
 {
  "symbol": "POCHIRAJU",
  "company_name": "POCHIRAJU IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE332G01032",
  "face_value": 1000.0
 },
 {
  "symbol": "POCL",
  "company_name": "PONDY OXIDES & CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE063E01053",
  "face_value": 500.0
 },
 {
  "symbol": "PODARPIGMT",
  "company_name": "PODDAR PIGMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE243001018",
  "face_value": 1000.0
 },
 {
  "symbol": "PODDARHOUS",
  "company_name": "PODDAR HOUSE & DVPT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE888B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PODDARMENT",
  "company_name": "PODDAR PIGMENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE371C01013",
  "face_value": 1000.0
 },
 {
  "symbol": "POKARNA",
  "company_name": "POKARNA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE637C01025",
  "face_value": 200.0
 },
 {
  "symbol": "POLICYBZR",
  "company_name": "PB FINTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE417T01026",
  "face_value": 200.0
 },
 {
  "symbol": "POLYCAB",
  "company_name": "POLYCAB INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE455K01017",
  "face_value": 1000.0
 },
 {
  "symbol": "POLYMED",
  "company_name": "POLY MEDICURE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE205C01021",
  "face_value": 500.0
 },
 {
  "symbol": "POLYPLEX",
  "company_name": "POLYPLEX CORPORATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE633B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PONDYOXIDE",
  "company_name": "PONDY OXIDE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE063E01038",
  "face_value": 1000.0
 },
 {
  "symbol": "PONNIERODE",
  "company_name": "PONNIE SUGARS (ERODE) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE838E01017",
  "face_value": 1000.0
 },
 {
  "symbol": "POONAWALLA",
  "company_name": "POONAWALLA FINCORP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE511C01022",
  "face_value": 200.0
 },
 {
  "symbol": "PORRITSPEN",
  "company_name": "PORRITTS & SPENCER (ASIA)",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE285C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "POWERGRID",
  "company_name": "POWER GRID CORP. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE752E01010",
  "face_value": 1000.0
 },
 {
  "symbol": "POWERICA",
  "company_name": "POWERICA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE921L01032",
  "face_value": 500.0
 },
 {
  "symbol": "POWERINDIA",
  "company_name": "HITACHI ENERGY INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE07Y701011",
  "face_value": 200.0
 },
 {
  "symbol": "POWERMECH",
  "company_name": "POWER MECH PROJECTS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE211R01019",
  "face_value": 1000.0
 },
 {
  "symbol": "PPAP",
  "company_name": "PPAP AUTOMOTIVE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE095I01015",
  "face_value": 1000.0
 },
 {
  "symbol": "PPIL",
  "company_name": "PHARMACEUTICALS PRODUCTS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE239401016",
  "face_value": 1000.0
 },
 {
  "symbol": "PPL",
  "company_name": "PRAKASH PIPES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE050001010",
  "face_value": 1000.0
 },
 {
  "symbol": "PPLPHARMA",
  "company_name": "PIRAMAL PHARMA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0DK501011",
  "face_value": 1000.0
 },
 {
  "symbol": "PRABHA",
  "company_name": "PRABHA ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0I0M01023",
  "face_value": 100.0
 },
 {
  "symbol": "PRABHA-RE",
  "company_name": "PRABHA ENERGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0I0M20015",
  "face_value": 100.0
 },
 {
  "symbol": "PRABHAT",
  "company_name": "PRABHAT DAIRY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE302M01033",
  "face_value": 1000.0
 },
 {
  "symbol": "PRADIP",
  "company_name": "PRADIP OVERSEAS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE495J01015",
  "face_value": 1000.0
 },
 {
  "symbol": "PRADPME",
  "company_name": "PRADEEP METALS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE770A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "PRAENG",
  "company_name": "PRAJAY ENG. SYN. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE505C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "PRAGBOSIMI",
  "company_name": "PRAG BOSIMI SYNTHETICS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE463101019",
  "face_value": 1000.0
 },
 {
  "symbol": "PRAJIND",
  "company_name": "PRAJ INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE074A01025",
  "face_value": 200.0
 },
 {
  "symbol": "PRAKASH",
  "company_name": "PRAKASH INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE603A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "PRAKASHSTL",
  "company_name": "PRAKASH STEELAGE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE696K01024",
  "face_value": 100.0
 },
 {
  "symbol": "PRATIBHA",
  "company_name": "PRATIBHA INDS. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE308H01022",
  "face_value": 200.0
 },
 {
  "symbol": "PRAVEG",
  "company_name": "PRAVEG LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE722B01019",
  "face_value": 1000.0
 },
 {
  "symbol": "PRAXIS",
  "company_name": "PRAXIS HOME RETAIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE546Y01022",
  "face_value": 500.0
 },
 {
  "symbol": "PRAXIS-RE",
  "company_name": "PRAXIS HOME RETAIL LTD-RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE546Y20014",
  "face_value": 500.0
 },
 {
  "symbol": "PRAXIS-RE1",
  "company_name": "PRAXIS HOME RETAIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE546Y20022",
  "face_value": 500.0
 },
 {
  "symbol": "PRAXIS-RE2",
  "company_name": "PRAXIS HOME RETAIL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE546Y20030",
  "face_value": 500.0
 },
 {
  "symbol": "PRECAM",
  "company_name": "PRECISION CAMSHAFTS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE484I01029",
  "face_value": 1000.0
 },
 {
  "symbol": "PRECIMDIAM",
  "company_name": "PRECIMET DIAMONDS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE440B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PRECOT",
  "company_name": "PRECOT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE283A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "PRECSNFAST",
  "company_name": "PRECISION FASTENERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE502401016",
  "face_value": 1000.0
 },
 {
  "symbol": "PRECWIRE",
  "company_name": "PRECISION WIRES INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE372C01037",
  "face_value": 100.0
 },
 {
  "symbol": "PREMCO",
  "company_name": "PREMCO GLOBAL LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE001E01012",
  "face_value": 1000.0
 },
 {
  "symbol": "PREMEXPLN",
  "company_name": "PREMIER EXPLOSIVES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE863B01029",
  "face_value": 200.0
 },
 {
  "symbol": "PREMIER",
  "company_name": "PREMIER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE342A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PREMIERENE",
  "company_name": "PREMIER ENERGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0BS701011",
  "face_value": 100.0
 },
 {
  "symbol": "PREMIERPOL",
  "company_name": "PREMIER POLYFILM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE309M01020",
  "face_value": 100.0
 },
 {
  "symbol": "PREMVINYL",
  "company_name": "PREMIER VINYL FLOORING LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE247701019",
  "face_value": 1000.0
 },
 {
  "symbol": "PRESSMN",
  "company_name": "PRESSMAN ADVERTISING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE980A01023",
  "face_value": 200.0
 },
 {
  "symbol": "PRESTIGE",
  "company_name": "PRESTIGE ESTATE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE811K01011",
  "face_value": 1000.0
 },
 {
  "symbol": "PRICOL-RE",
  "company_name": "PRICOL RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE726V20018",
  "face_value": 100.0
 },
 {
  "symbol": "PRICOLLTD",
  "company_name": "PRICOL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE726V01018",
  "face_value": 100.0
 },
 {
  "symbol": "PRIMESECU",
  "company_name": "PRIME SECURITIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE032B01021",
  "face_value": 500.0
 },
 {
  "symbol": "PRIMO",
  "company_name": "PRIMO CHEMICALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE607A01022",
  "face_value": 200.0
 },
 {
  "symbol": "PRINCEPIPE",
  "company_name": "PRINCE PIPES FITTINGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE689W01016",
  "face_value": 1000.0
 },
 {
  "symbol": "PRITI",
  "company_name": "PRITI INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE974Z01015",
  "face_value": 1000.0
 },
 {
  "symbol": "PRITIKAUTO",
  "company_name": "PRITIKA AUTO INDUS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE583R01029",
  "face_value": 200.0
 },
 {
  "symbol": "PRIVISCL",
  "company_name": "PRIVI SPECIALITY CHE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE959A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "PRIYADCEM",
  "company_name": "PRIYADARSHINI CEMENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE855B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "PRIYADYES",
  "company_name": "PRIYA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE249301016",
  "face_value": 1000.0
 },
 {
  "symbol": "PROSEED",
  "company_name": "PROSEED INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE217G01027",
  "face_value": 100.0
 },
 {
  "symbol": "PROSTARM",
  "company_name": "PROSTARM INFO SYSTEMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0BX301013",
  "face_value": 1000.0
 },
 {
  "symbol": "PROTEAN",
  "company_name": "PROTEAN EGOV TECHNO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE004A01022",
  "face_value": 1000.0
 },
 {
  "symbol": "PROVOGE",
  "company_name": "PROVOGUE (INDIA) LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE968G01033",
  "face_value": 100.0
 },
 {
  "symbol": "PROZONER",
  "company_name": "PROZONE REALTY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE195N01013",
  "face_value": 200.0
 },
 {
  "symbol": "PRSMJOHNSN",
  "company_name": "PRISM JOHNSON LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE010A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "PRUDENT",
  "company_name": "PRUDENT CORP ADV SER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00F201020",
  "face_value": 500.0
 },
 {
  "symbol": "PRUDMOULI",
  "company_name": "PRUDENTIAL SUGAR CORPORAT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE024D01016",
  "face_value": 1000.0
 },
 {
  "symbol": "PSB",
  "company_name": "PUNJAB & SIND BANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE608A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "PSBKICINAV",
  "company_name": "ICICIPRAMC - PSBKICINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000181",
  "face_value": 1000.0
 },
 {
  "symbol": "PSIDATASYS",
  "company_name": "PSI DATA SYSTEMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE299A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "PSL",
  "company_name": "PSL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE474B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "PSMSPGMILL",
  "company_name": "PSM SPINNING MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE503001013",
  "face_value": 1000.0
 },
 {
  "symbol": "PSPPROJECT",
  "company_name": "PSP PROJECTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE488V01015",
  "face_value": 1000.0
 },
 {
  "symbol": "PSUBANK",
  "company_name": "KOTAK PSU BANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF373I01023",
  "face_value": 1000.0
 },
 {
  "symbol": "PSUBANKADD",
  "company_name": "DSPAMC - DSPPSBKETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1SY9",
  "face_value": 1000.0
 },
 {
  "symbol": "PSUBKBENAV",
  "company_name": "PSU BANK BEES NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000025",
  "face_value": 1000.0
 },
 {
  "symbol": "PSUBNKBEES",
  "company_name": "NIP IND ETF PSU BANK BEES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KB16I7",
  "face_value": 100.0
 },
 {
  "symbol": "PSUBNKIETF",
  "company_name": "ICICIPRAMC - PSUBANKICI",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC10S8",
  "face_value": 1000.0
 },
 {
  "symbol": "PTC",
  "company_name": "PTC INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE877F01012",
  "face_value": 1000.0
 },
 {
  "symbol": "PTCIL",
  "company_name": "PTC INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE596F01018",
  "face_value": 1000.0
 },
 {
  "symbol": "PTL",
  "company_name": "PTL ENTERPRISES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE034D01049",
  "face_value": 100.0
 },
 {
  "symbol": "PUNALKALI",
  "company_name": "PUNJAB ALKALIES & CHEMICA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE607A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "PUNANDLAMP",
  "company_name": "PUNJAB ANAND LAMPS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE276B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "PUNJABCHEM",
  "company_name": "PUNJAB CHEM & CROP PROT L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE277B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "PUNJABWIRE",
  "company_name": "PUNJAB WIRELESS SYSTEMS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE252201012",
  "face_value": 1000.0
 },
 {
  "symbol": "PUNJABWOOL",
  "company_name": "PUNJAB WOOLCOMBERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE252301010",
  "face_value": 1000.0
 },
 {
  "symbol": "PUNJCOMMU",
  "company_name": "PUNJAB COMMUNICATIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE609A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "PUNJLLOYD",
  "company_name": "PUNJ LLOYD LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE701B01021",
  "face_value": 200.0
 },
 {
  "symbol": "PUNSUMI",
  "company_name": "PUNSUMI (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE252401018",
  "face_value": 1000.0
 },
 {
  "symbol": "PURVA",
  "company_name": "PURAVANKARA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE323I01011",
  "face_value": 500.0
 },
 {
  "symbol": "PVP",
  "company_name": "PVP VENTURES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE362A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "PVR-RE",
  "company_name": "PVR LIMITED RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE191H20014",
  "face_value": 1000.0
 },
 {
  "symbol": "PVRINOX",
  "company_name": "PVR INOX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE191H01014",
  "face_value": 1000.0
 },
 {
  "symbol": "PVSL",
  "company_name": "POPULAR VEHICLES N SER L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE772T01024",
  "face_value": 200.0
 },
 {
  "symbol": "PVTBANIETF",
  "company_name": "ICICIPRAMC - ICICIBANKP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC18U7",
  "face_value": 100.0
 },
 {
  "symbol": "PVTBANKADD",
  "company_name": "DSPAMC - DSPPVBKETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1TA7",
  "face_value": 1000.0
 },
 {
  "symbol": "PWL",
  "company_name": "PHYSICSWALLAH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0LP301011",
  "face_value": 100.0
 },
 {
  "symbol": "PYRAMID",
  "company_name": "PYRAMID TECHNOPLAST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0MIS01010",
  "face_value": 1000.0
 },
 {
  "symbol": "QGOLDHALF",
  "company_name": "QUANTUM GOLD FUND",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF082J01408",
  "face_value": 200.0
 },
 {
  "symbol": "QGOLDHINAV",
  "company_name": "QGOLDHALF NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000045",
  "face_value": 200.0
 },
 {
  "symbol": "QNIFTY",
  "company_name": "QUANTUM NIFTY 50 ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF082J01499",
  "face_value": 100.0
 },
 {
  "symbol": "QNIFTYINAV",
  "company_name": "QNIFTY INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000133",
  "face_value": 100.0
 },
 {
  "symbol": "QPOWER",
  "company_name": "QUALITY POWER ELEC EQUP L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0SII01026",
  "face_value": 1000.0
 },
 {
  "symbol": "QUADFUTURE",
  "company_name": "QUADRANT FUTURE TEK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0LRY01011",
  "face_value": 1000.0
 },
 {
  "symbol": "QUAL30IETF",
  "company_name": "ICICIPRAMC - ICICIQTY30",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC18V5",
  "face_value": 100.0
 },
 {
  "symbol": "QUALITINAV",
  "company_name": "KOTAKMAMC - QUALITINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000290",
  "face_value": 1000.0
 },
 {
  "symbol": "QUALITY30",
  "company_name": "KOTAKMAMC - QUALITY30",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1WT6",
  "face_value": 1000.0
 },
 {
  "symbol": "QUESS",
  "company_name": "QUESS CORP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE615P01015",
  "face_value": 1000.0
 },
 {
  "symbol": "QUICKHEAL",
  "company_name": "QUICK HEAL TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE306L01010",
  "face_value": 1000.0
 },
 {
  "symbol": "QUINT",
  "company_name": "QUINT DIGITAL LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE641R01017",
  "face_value": 1000.0
 },
 {
  "symbol": "QUINTEGRA",
  "company_name": "QUINTEGRA SOLUTIONS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE033B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "RACE",
  "company_name": "RACE ECO CHAIN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE084Q01012",
  "face_value": 1000.0
 },
 {
  "symbol": "RACLGEAR",
  "company_name": "RACL GEARTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE704B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "RADAAN",
  "company_name": "RADAAN MEDIAWORKS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE874F01027",
  "face_value": 200.0
 },
 {
  "symbol": "RADHIKAJWE",
  "company_name": "RADHIKA JEWELTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE583V01021",
  "face_value": 200.0
 },
 {
  "symbol": "RADIANTCMS",
  "company_name": "RADIANT CASH MGMT SER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE855R01021",
  "face_value": 100.0
 },
 {
  "symbol": "RADICO",
  "company_name": "RADICO KHAITAN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE944F01028",
  "face_value": 200.0
 },
 {
  "symbol": "RADICOKHAI",
  "company_name": "RADICO KHAITAN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE381B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "RADIOCITY",
  "company_name": "MUSIC BROADCAST LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE919I01024",
  "face_value": 200.0
 },
 {
  "symbol": "RAILTEL",
  "company_name": "RAILTEL CORP OF IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0DD101019",
  "face_value": 1000.0
 },
 {
  "symbol": "RAIN",
  "company_name": "RAIN INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE855B01025",
  "face_value": 200.0
 },
 {
  "symbol": "RAINBOW",
  "company_name": "RAINBOW CHILDRENS MED LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE961O01016",
  "face_value": 1000.0
 },
 {
  "symbol": "RAINBOWPAP",
  "company_name": "RAINBOW PAPERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE028D01025",
  "face_value": 200.0
 },
 {
  "symbol": "RAINBOWPPR",
  "company_name": "RAINBOW PAPERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE256201018",
  "face_value": 1000.0
 },
 {
  "symbol": "RAJASBREW",
  "company_name": "RAJASTHAN BREWERIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE257201017",
  "face_value": 1000.0
 },
 {
  "symbol": "RAJESHEXPO",
  "company_name": "RAJESH EXPORTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE343B01030",
  "face_value": 100.0
 },
 {
  "symbol": "RAJMET",
  "company_name": "RAJNANDINI METAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00KV01022",
  "face_value": 100.0
 },
 {
  "symbol": "RAJOIL",
  "company_name": "RAJ OIL MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE294G01018",
  "face_value": 1000.0
 },
 {
  "symbol": "RAJOOENG",
  "company_name": "RAJOO ENGINEERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE535F01024",
  "face_value": 100.0
 },
 {
  "symbol": "RAJPALAYAM",
  "company_name": "RAJAPALAYAM MILLS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE296E01026",
  "face_value": 1000.0
 },
 {
  "symbol": "RAJRATAN",
  "company_name": "RAJRATAN GLOBAL WIRE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE451D01029",
  "face_value": 200.0
 },
 {
  "symbol": "RAJRAYON",
  "company_name": "RAJ RAYON INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE533D01024",
  "face_value": 100.0
 },
 {
  "symbol": "RAJRILTD",
  "company_name": "RAJ RAYON INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE533D01032",
  "face_value": 100.0
 },
 {
  "symbol": "RAJSREESUG",
  "company_name": "RAJSHREE SUGAR & CHEMICAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE562B01019",
  "face_value": 1000.0
 },
 {
  "symbol": "RAJTV",
  "company_name": "RAJ TV NETWORK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE952H01027",
  "face_value": 500.0
 },
 {
  "symbol": "RAJVIR",
  "company_name": "RAJVIR INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE011H01014",
  "face_value": 1000.0
 },
 {
  "symbol": "RALLIS",
  "company_name": "RALLIS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE613A01020",
  "face_value": 100.0
 },
 {
  "symbol": "RAMADHOTEL",
  "company_name": "ADVANI HOTELS & RESORTS I",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE199C01026",
  "face_value": 1000.0
 },
 {
  "symbol": "RAMANEWS",
  "company_name": "SHREE RAMA NEWSPRINT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE278B01020",
  "face_value": 1000.0
 },
 {
  "symbol": "RAMAPETRO",
  "company_name": "RAMA PETROCHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE783A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "RAMAPHO",
  "company_name": "RAMA PHOSPHATES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE809A01032",
  "face_value": 500.0
 },
 {
  "symbol": "RAMAPHOSP",
  "company_name": "RAMA PHOSPHATES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE463501010",
  "face_value": 1000.0
 },
 {
  "symbol": "RAMASTEEL",
  "company_name": "RAMA STEEL TUBES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE230R01035",
  "face_value": 100.0
 },
 {
  "symbol": "RAMAVISION",
  "company_name": "RAMA VISION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE763B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "RAMCOCEM",
  "company_name": "THE RAMCO CEMENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE331A01037",
  "face_value": 100.0
 },
 {
  "symbol": "RAMCOIND",
  "company_name": "RAMCO INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE614A01028",
  "face_value": 100.0
 },
 {
  "symbol": "RAMCOSYS",
  "company_name": "RAMCO SYSTEMS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE246B01019",
  "face_value": 1000.0
 },
 {
  "symbol": "RAMGOPOLY",
  "company_name": "RAMGOPAL POLYTEX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE410D01017",
  "face_value": 1000.0
 },
 {
  "symbol": "RAMKY",
  "company_name": "RAMKY INFRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE874I01013",
  "face_value": 1000.0
 },
 {
  "symbol": "RAMRAT",
  "company_name": "RAM RATNA WIRES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE207E01023",
  "face_value": 500.0
 },
 {
  "symbol": "RAMSARUP",
  "company_name": "RAMSARUP INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE005D01015",
  "face_value": 1000.0
 },
 {
  "symbol": "RANASUG",
  "company_name": "RANA SUGARS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE625B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "RANEENGINE",
  "company_name": "RANE ENG VALVE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE222J01013",
  "face_value": 1000.0
 },
 {
  "symbol": "RANEHOLDIN",
  "company_name": "RANE HOLDINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE384A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "RANKAQUA",
  "company_name": "RANK INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY10887",
  "face_value": 1000.0
 },
 {
  "symbol": "RASLAMIPAK",
  "company_name": "RAS PROPACK LAMIPACK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE279B01010",
  "face_value": 1000.0
 },
 {
  "symbol": "RATEGAIN",
  "company_name": "RATEGAIN TRAVEL TECHN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0CLI01024",
  "face_value": 100.0
 },
 {
  "symbol": "RATHIALLOY",
  "company_name": "RATHI ALLOYS AND STEELS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE263601010",
  "face_value": 1000.0
 },
 {
  "symbol": "RATNAMANI",
  "company_name": "RATNAMANI MET & TUB LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE703B01027",
  "face_value": 200.0
 },
 {
  "symbol": "RATNAVEER",
  "company_name": "RATNAVEER PRECISION ENG L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE05CZ01011",
  "face_value": 1000.0
 },
 {
  "symbol": "RAVALSUGAR",
  "company_name": "RAVALGAON SUGAR FARM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE615A01017",
  "face_value": 5000.0
 },
 {
  "symbol": "RAYMOND",
  "company_name": "RAYMOND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE301A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "RAYMONDLSL",
  "company_name": "RAYMOND LIFESTYLE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02ID01020",
  "face_value": 200.0
 },
 {
  "symbol": "RAYMONDREL",
  "company_name": "RAYMOND REALTY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1SY401010",
  "face_value": 1000.0
 },
 {
  "symbol": "RAYMONDSYN",
  "company_name": "RECRON SYNTHETICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE616A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "RBA",
  "company_name": "RESTAURANT BRAND ASIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE07T201019",
  "face_value": 1000.0
 },
 {
  "symbol": "RBL",
  "company_name": "RANE BRAKE LINING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE244J01017",
  "face_value": 1000.0
 },
 {
  "symbol": "RBLBANK",
  "company_name": "RBL BANK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE976G01028",
  "face_value": 1000.0
 },
 {
  "symbol": "RBZJEWEL",
  "company_name": "RBZ JEWELLERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0PEQ01016",
  "face_value": 1000.0
 },
 {
  "symbol": "RCF",
  "company_name": "RASHTRIYA CHEMICALS & FER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE027A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "RCOM",
  "company_name": "RELIANCE COMMUNICATIONS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE330H01018",
  "face_value": 500.0
 },
 {
  "symbol": "READYFOOD",
  "company_name": "READY FOODS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE265801014",
  "face_value": 1000.0
 },
 {
  "symbol": "RECKCOLMAN",
  "company_name": "RECKITT BENCKISER (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE274A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "RECLTD",
  "company_name": "REC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE020B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "REDINGTON",
  "company_name": "REDINGTON LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE891D01026",
  "face_value": 200.0
 },
 {
  "symbol": "REDTAPE",
  "company_name": "REDTAPE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0LXT01019",
  "face_value": 200.0
 },
 {
  "symbol": "REFEX",
  "company_name": "REFEX INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE056I01025",
  "face_value": 200.0
 },
 {
  "symbol": "REFEX-RE",
  "company_name": "REFEX INDUSTRIES RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE056I20017",
  "face_value": 1000.0
 },
 {
  "symbol": "REGAAL",
  "company_name": "REGAAL RESOURCES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0MHO01029",
  "face_value": 500.0
 },
 {
  "symbol": "REGENCERAM",
  "company_name": "REGENCY CERAMICS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE277C01012",
  "face_value": 1000.0
 },
 {
  "symbol": "REILPROD",
  "company_name": "REIL PRODUCTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE267201015",
  "face_value": 1000.0
 },
 {
  "symbol": "REL100NAV",
  "company_name": "RELCAPAMC - RELCNX100",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000026",
  "face_value": 1000.0
 },
 {
  "symbol": "RELAXO",
  "company_name": "RELAXO FOOT LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE131B01039",
  "face_value": 100.0
 },
 {
  "symbol": "RELAXOFOOT",
  "company_name": "RELAXO FOOTWEAR LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE573001018",
  "face_value": 1000.0
 },
 {
  "symbol": "RELBANKNAV",
  "company_name": "R SHARES BANKING ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000027",
  "face_value": 1000.0
 },
 {
  "symbol": "RELCAPITAL",
  "company_name": "RELIANCE CAPITAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE013A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "RELCHEMQ",
  "company_name": "RELIANCE CHEMOTEX IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE750D01016",
  "face_value": 1000.0
 },
 {
  "symbol": "RELCONSNAV",
  "company_name": "RELCAPAMC - RELCONS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000028",
  "face_value": 1000.0
 },
 {
  "symbol": "RELDIVNAV",
  "company_name": "RELCAPAMC - RELDIVOPP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000029",
  "face_value": 1000.0
 },
 {
  "symbol": "RELGOLDNAV",
  "company_name": "R SHARES GOLD ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000030",
  "face_value": 10000.0
 },
 {
  "symbol": "RELIABLE",
  "company_name": "RELIABLE DATA SERVICE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE375Y01018",
  "face_value": 1000.0
 },
 {
  "symbol": "RELIANCE",
  "company_name": "RELIANCE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE002A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "RELIGARE",
  "company_name": "RELIGARE ENTER. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE621H01010",
  "face_value": 1000.0
 },
 {
  "symbol": "RELINFRA",
  "company_name": "RELIANCE INFRASTRUCTU LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE036A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "RELNV20NAV",
  "company_name": "RELCAPAMC - RELNV20",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000031",
  "face_value": 1000.0
 },
 {
  "symbol": "RELTD",
  "company_name": "RAVINDRA ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE206N01018",
  "face_value": 1000.0
 },
 {
  "symbol": "REMIMETAL",
  "company_name": "REMI METALS GUJARAT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE268401010",
  "face_value": 1000.0
 },
 {
  "symbol": "REMSONSIND",
  "company_name": "REMSONS INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE474C01023",
  "face_value": 200.0
 },
 {
  "symbol": "RENCOGEAR",
  "company_name": "RENCO GEARS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE268701013",
  "face_value": 1000.0
 },
 {
  "symbol": "RENIFTYNAV",
  "company_name": "RELCAPAMC - RELNIFTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000032",
  "face_value": 1000.0
 },
 {
  "symbol": "RENUKA",
  "company_name": "SHREE RENUKA SUGARS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE087H01022",
  "face_value": 100.0
 },
 {
  "symbol": "REPCOHOME",
  "company_name": "REPCO HOME FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE612J01015",
  "face_value": 1000.0
 },
 {
  "symbol": "REPL",
  "company_name": "RUDRABHISHEK ENTERP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE364Z01019",
  "face_value": 1000.0
 },
 {
  "symbol": "REPLENGINE",
  "company_name": "REPL ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE268801011",
  "face_value": 1000.0
 },
 {
  "symbol": "REPRO",
  "company_name": "REPRO INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE461B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "RESPONIND",
  "company_name": "RESPONSIVE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE688D01026",
  "face_value": 100.0
 },
 {
  "symbol": "RETAIL",
  "company_name": "JHS SVENDGAARD RETAIL V L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE03DD01011",
  "face_value": 1000.0
 },
 {
  "symbol": "RGL",
  "company_name": "RENAISSANCE GLOBAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE722H01024",
  "face_value": 200.0
 },
 {
  "symbol": "RHETAN",
  "company_name": "RHETAN TMT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0KKN01029",
  "face_value": 100.0
 },
 {
  "symbol": "RHFL",
  "company_name": "RELIANCE HOME FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE217K01011",
  "face_value": 1000.0
 },
 {
  "symbol": "RHIM",
  "company_name": "RHI MAGNESITA INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE743M01012",
  "face_value": 100.0
 },
 {
  "symbol": "RHL",
  "company_name": "ROBUST HOTELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE508K01013",
  "face_value": 1000.0
 },
 {
  "symbol": "RICHSILK",
  "company_name": "RICHIMEN SILK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE269401019",
  "face_value": 1000.0
 },
 {
  "symbol": "RICOAUTO",
  "company_name": "RICO AUTO INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE209B01025",
  "face_value": 100.0
 },
 {
  "symbol": "RIIL",
  "company_name": "RELIANCE INDUSTRIAL INFRA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE046A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "RIL-RE",
  "company_name": "RELIANCE INDUSTRIES RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE002A20018",
  "face_value": 1000.0
 },
 {
  "symbol": "RISHABH",
  "company_name": "RISHABH INSTRUMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0N2P01017",
  "face_value": 1000.0
 },
 {
  "symbol": "RISHIPACK",
  "company_name": "RISHI PACKERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE271301017",
  "face_value": 1000.0
 },
 {
  "symbol": "RITCO",
  "company_name": "RITCO LOGISTICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01EG01016",
  "face_value": 1000.0
 },
 {
  "symbol": "RITES",
  "company_name": "RITES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE320J01015",
  "face_value": 1000.0
 },
 {
  "symbol": "RKDL",
  "company_name": "RAVI KUMAR DIST. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE722J01012",
  "face_value": 1000.0
 },
 {
  "symbol": "RKEC",
  "company_name": "RKEC PROJECTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE786W01010",
  "face_value": 1000.0
 },
 {
  "symbol": "RKFORGE",
  "company_name": "RAMKRISHNA FORGINGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE399G01023",
  "face_value": 200.0
 },
 {
  "symbol": "RKSWAMY",
  "company_name": "R K SWAMY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0NQ801033",
  "face_value": 500.0
 },
 {
  "symbol": "RMC",
  "company_name": "RMC SWITCHGEARS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE655V01019",
  "face_value": 1000.0
 },
 {
  "symbol": "RMCL",
  "company_name": "RADHA MADHAV CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE172H01014",
  "face_value": 1000.0
 },
 {
  "symbol": "RMDRIP",
  "company_name": "R M DRIP & SPRINK SYS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE219Y01026",
  "face_value": 100.0
 },
 {
  "symbol": "RML",
  "company_name": "RANE (MADRAS) LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE050H01012",
  "face_value": 1000.0
 },
 {
  "symbol": "RMMIL",
  "company_name": "RESURGERE MINES & MINERAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE774I01031",
  "face_value": 1000.0
 },
 {
  "symbol": "RNAVAL",
  "company_name": "RELIANCE NAVAL & ENGG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE542F01012",
  "face_value": 1000.0
 },
 {
  "symbol": "RNBDENIMS",
  "company_name": "R&B DENIMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE012Q01039",
  "face_value": 100.0
 },
 {
  "symbol": "ROHITFERRO",
  "company_name": "ROHIT FERRO-TECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE248H01012",
  "face_value": 1000.0
 },
 {
  "symbol": "ROHLTD",
  "company_name": "ROYAL ORCHID HOTELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE283H01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ROLATAN",
  "company_name": "ROLLATAINERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE273101019",
  "face_value": 1000.0
 },
 {
  "symbol": "ROLEXRINGS",
  "company_name": "ROLEX RINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE645S01024",
  "face_value": 100.0
 },
 {
  "symbol": "ROLLT",
  "company_name": "ROLLATAINERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE927A01040",
  "face_value": 100.0
 },
 {
  "symbol": "ROLTA",
  "company_name": "ROLTA INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE293A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "ROMIND",
  "company_name": "ROM INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE573501017",
  "face_value": 1000.0
 },
 {
  "symbol": "ROML",
  "company_name": "RAJ OIL MILLS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE294G01026",
  "face_value": 1000.0
 },
 {
  "symbol": "ROML-RE",
  "company_name": "RAJ OIL MILLS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE294G20018",
  "face_value": 1000.0
 },
 {
  "symbol": "ROSSARI",
  "company_name": "ROSSARI BIOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02A801020",
  "face_value": 200.0
 },
 {
  "symbol": "ROSSELL",
  "company_name": "ROSSELL INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE166D01015",
  "face_value": 1000.0
 },
 {
  "symbol": "ROSSELLIND",
  "company_name": "ROSSELL INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE847C01020",
  "face_value": 200.0
 },
 {
  "symbol": "ROSSTECH",
  "company_name": "ROSSELL TECHSYS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0OJW01016",
  "face_value": 200.0
 },
 {
  "symbol": "ROTO",
  "company_name": "ROTO PUMPS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE535D01037",
  "face_value": 100.0
 },
 {
  "symbol": "ROUTE",
  "company_name": "ROUTE MOBILE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE450U01017",
  "face_value": 1000.0
 },
 {
  "symbol": "ROYALCUSHN",
  "company_name": "ROYAL CUSHION VINYL PRODU",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE464001010",
  "face_value": 1000.0
 },
 {
  "symbol": "RPEL",
  "company_name": "RAGHAV PRODUCTIVITY ENH L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE912T01018",
  "face_value": 1000.0
 },
 {
  "symbol": "RPGLIFE",
  "company_name": "RPG LIFE SCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE105J01010",
  "face_value": 800.0
 },
 {
  "symbol": "RPOWER",
  "company_name": "RELIANCE POWER LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE614G01033",
  "face_value": 1000.0
 },
 {
  "symbol": "RPP-RE",
  "company_name": "R.P.P. INFRA PROJECTS-RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE324L20013",
  "face_value": 1000.0
 },
 {
  "symbol": "RPPINFRA",
  "company_name": "R.P.P INFRA PROJECTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE324L01013",
  "face_value": 1000.0
 },
 {
  "symbol": "RPPL",
  "company_name": "RAJSHREE POLYPACK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE760W01023",
  "face_value": 500.0
 },
 {
  "symbol": "RPSGVENT",
  "company_name": "RPSG VENTURES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE425Y01011",
  "face_value": 1000.0
 },
 {
  "symbol": "RPTECH",
  "company_name": "RASHI PERIPHERALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0J1F01024",
  "face_value": 500.0
 },
 {
  "symbol": "RRIL",
  "company_name": "R R I L LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE951M01037",
  "face_value": 500.0
 },
 {
  "symbol": "RRKABEL",
  "company_name": "R R KABEL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE777K01022",
  "face_value": 500.0
 },
 {
  "symbol": "RSDFIN",
  "company_name": "R S D FINANCE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE616F01022",
  "face_value": 500.0
 },
 {
  "symbol": "RSL",
  "company_name": "RAJPUTANA STAINLESS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE313L01016",
  "face_value": 1000.0
 },
 {
  "symbol": "RSSOFTWARE",
  "company_name": "R. S. SOFTWARE (INDIA) LI",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE165B01029",
  "face_value": 500.0
 },
 {
  "symbol": "RSWM",
  "company_name": "RSWM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE611A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "RSWM-RE",
  "company_name": "RSWM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE611A20016",
  "face_value": 1000.0
 },
 {
  "symbol": "RSYSTEMS",
  "company_name": "R SYS INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE411H01032",
  "face_value": 100.0
 },
 {
  "symbol": "RTNINDIA",
  "company_name": "RATTANINDIA ENT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE834M01019",
  "face_value": 200.0
 },
 {
  "symbol": "RTNPOWER",
  "company_name": "RATTANINDIA POWER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE399K01017",
  "face_value": 1000.0
 },
 {
  "symbol": "RUBFILA",
  "company_name": "RUBFILA INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE642C01025",
  "face_value": 500.0
 },
 {
  "symbol": "RUBFILINTL",
  "company_name": "RUBFILA INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE642C01017",
  "face_value": 1000.0
 },
 {
  "symbol": "RUBICON",
  "company_name": "RUBICON RESEARCH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE506V01022",
  "face_value": 100.0
 },
 {
  "symbol": "RUBYMILLS",
  "company_name": "THE RUBY MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE301D01026",
  "face_value": 500.0
 },
 {
  "symbol": "RUCHINFRA",
  "company_name": "RUCHI INFRASTRUCTURE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE413B01023",
  "face_value": 100.0
 },
 {
  "symbol": "RUCHIRA",
  "company_name": "RUCHIRA PAPERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE803H01014",
  "face_value": 1000.0
 },
 {
  "symbol": "RUCHISOYA",
  "company_name": "RUCHI SOYA INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE619A01027",
  "face_value": 200.0
 },
 {
  "symbol": "RUCHISTRIP",
  "company_name": "RUCHI STRIPS AND ALLOYS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE275101017",
  "face_value": 1000.0
 },
 {
  "symbol": "RUDRA",
  "company_name": "RUDRA GLOBAL INFRA PROD L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE027T01023",
  "face_value": 500.0
 },
 {
  "symbol": "RUPA",
  "company_name": "RUPA & COMPANY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE895B01021",
  "face_value": 100.0
 },
 {
  "symbol": "RUSHI-RE1",
  "company_name": "RUSHIL DECOR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE573K20025",
  "face_value": 1000.0
 },
 {
  "symbol": "RUSHIL",
  "company_name": "RUSHIL DECOR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE573K01025",
  "face_value": 100.0
 },
 {
  "symbol": "RUSHIL-RE",
  "company_name": "RUSHIL DECOR RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE573K20017",
  "face_value": 1000.0
 },
 {
  "symbol": "RUSTOMJEE",
  "company_name": "KEYSTONE REALTORS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE263M01029",
  "face_value": 1000.0
 },
 {
  "symbol": "RVHL",
  "company_name": "RAVINDER HEIGHTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE09E501017",
  "face_value": 100.0
 },
 {
  "symbol": "RVNL",
  "company_name": "RAIL VIKAS NIGAM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE415G01027",
  "face_value": 1000.0
 },
 {
  "symbol": "RVTH",
  "company_name": "REVATHI EQUIPMENT INDIA L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0DAB01012",
  "face_value": 1000.0
 },
 {
  "symbol": "S&SIND",
  "company_name": "S&S INDUSTRIES & ENTERPRI",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE464301014",
  "face_value": 1000.0
 },
 {
  "symbol": "S&SPOWER",
  "company_name": "S&S POWER SWITCHGEARS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE902B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SAATVIKGL",
  "company_name": "SAATVIK GREEN ENERGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE13B501022",
  "face_value": 200.0
 },
 {
  "symbol": "SABEVENTS",
  "company_name": "SAB EVENTS & GOVERNANCE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE860T01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SABTN",
  "company_name": "SRI ADHIKARI BROS.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE416A01036",
  "face_value": 1000.0
 },
 {
  "symbol": "SADBHAV",
  "company_name": "SADBHAV ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE226H01026",
  "face_value": 100.0
 },
 {
  "symbol": "SADBHIN",
  "company_name": "SADBHAV INFRA PROJ LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE764L01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SADHNA-RE",
  "company_name": "SADHANA NITROCHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE888C20024",
  "face_value": 100.0
 },
 {
  "symbol": "SADHNAN-RE",
  "company_name": "SADHANA NITROCHEM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE888C20016",
  "face_value": 100.0
 },
 {
  "symbol": "SADHNANIQ",
  "company_name": "SADHANA NITROCHEM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE888C01040",
  "face_value": 100.0
 },
 {
  "symbol": "SAFARI",
  "company_name": "SAFARI IND (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE429E01023",
  "face_value": 200.0
 },
 {
  "symbol": "SAGARCEM",
  "company_name": "SAGAR CEMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE229C01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SAGARDEEP",
  "company_name": "SAGARDEEP ALLOYS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE976T01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SAGCEM",
  "company_name": "SAGAR CEMENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE229C01021",
  "face_value": 200.0
 },
 {
  "symbol": "SAGILITY",
  "company_name": "SAGILITY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0W2G01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SAHLIBHFI",
  "company_name": "SHALIBHADRA FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE861D01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SAHYADRI",
  "company_name": "SAHYADRI INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE280H01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SAIL",
  "company_name": "STEEL AUTHORITY OF INDIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE114A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SAILIFE",
  "company_name": "SAI LIFE SCIENCES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE570L01029",
  "face_value": 100.0
 },
 {
  "symbol": "SAIPARENT",
  "company_name": "SAI PARENTERALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0H9F01037",
  "face_value": 500.0
 },
 {
  "symbol": "SAISERVICE",
  "company_name": "SAI SERVICES STATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE278801019",
  "face_value": 1000.0
 },
 {
  "symbol": "SAKAR",
  "company_name": "SAKAR HEALTHCARE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE732S01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SAKHTISUG",
  "company_name": "SAKTHI SUGARS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE623A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SAKSOFT",
  "company_name": "SAKSOFT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE667G01023",
  "face_value": 100.0
 },
 {
  "symbol": "SAKTHIFIN",
  "company_name": "SAKTHI FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE302E01014",
  "face_value": 1000.0
 },
 {
  "symbol": "SAKUMA",
  "company_name": "SAKUMA EXPORTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE190H01024",
  "face_value": 100.0
 },
 {
  "symbol": "SAKUMA-RE",
  "company_name": "SAKUMA EXPORTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE190H20016",
  "face_value": 100.0
 },
 {
  "symbol": "SALASAR",
  "company_name": "SALASAR TECHNO ENGG. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE170V01027",
  "face_value": 100.0
 },
 {
  "symbol": "SALONA",
  "company_name": "SALONA COTSPIN LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE498E01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SALSTEEL",
  "company_name": "S.A.L. STEEL LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE658G01014",
  "face_value": 1000.0
 },
 {
  "symbol": "SALZERELEC",
  "company_name": "SALZER ELECTRONICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE457F01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SAMBHAAV",
  "company_name": "SAMBHAAV MEDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE699B01027",
  "face_value": 100.0
 },
 {
  "symbol": "SAMBHV",
  "company_name": "SAMBHV STEEL TUBES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE12NJ01018",
  "face_value": 1000.0
 },
 {
  "symbol": "SAMHI",
  "company_name": "SAMHI HOTELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE08U801020",
  "face_value": 100.0
 },
 {
  "symbol": "SAMMAANCAP",
  "company_name": "SAMMAAN CAPITAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE148I01020",
  "face_value": 200.0
 },
 {
  "symbol": "SAMPANN",
  "company_name": "SAMPANN UTPADAN INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE735M01018",
  "face_value": 1000.0
 },
 {
  "symbol": "SAMTELTD",
  "company_name": "SAMTEL (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE280901013",
  "face_value": 1000.0
 },
 {
  "symbol": "SANATHAN",
  "company_name": "SANATHAN TEXTILES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0JPD01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SANCO",
  "company_name": "SANCO INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE782L01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SANDESH",
  "company_name": "SANDESH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE583B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SANDHAR",
  "company_name": "SANDHAR TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE278H01035",
  "face_value": 1000.0
 },
 {
  "symbol": "SANDUMA",
  "company_name": "SANDUR MANG & IRON ORES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE149K01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SANDVIKAS",
  "company_name": "SANDVIK ASIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE624A01019",
  "face_value": 10000.0
 },
 {
  "symbol": "SANG-RE",
  "company_name": "SANGINITA CHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE753W20010",
  "face_value": 1000.0
 },
 {
  "symbol": "SANGAMIND",
  "company_name": "SANGAM (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE495C01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SANGHIIND",
  "company_name": "SANGHI INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE999B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SANGHVIFOR",
  "company_name": "SANGHVI FOR & ENG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE263L01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SANGHVIMOV",
  "company_name": "SANGHVI MOVERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE989A01032",
  "face_value": 100.0
 },
 {
  "symbol": "SANGINITA",
  "company_name": "SANGINITA CHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE753W01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SANOFI",
  "company_name": "SANOFI INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE058A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SANOFICONR",
  "company_name": "SANOFI CONS HEALTHC IND L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0UOS01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SANSERA",
  "company_name": "SANSERA ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE953O01021",
  "face_value": 200.0
 },
 {
  "symbol": "SANSTAR",
  "company_name": "SANSTAR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE08NE01025",
  "face_value": 200.0
 },
 {
  "symbol": "SANWARIA",
  "company_name": "SANWARIA CONSUMER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE890C01046",
  "face_value": 100.0
 },
 {
  "symbol": "SAPPHIRE",
  "company_name": "SAPPHIRE FOODS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE806T01020",
  "face_value": 200.0
 },
 {
  "symbol": "SAPPL",
  "company_name": "SHREE AJIT PULP & PAPER L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE185C01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SARASIND",
  "company_name": "SARASWATI INDL SYNDICATE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE858B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SARDAEN",
  "company_name": "SARDA ENERGY & MIN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE385C01021",
  "face_value": 100.0
 },
 {
  "symbol": "SAREGAMA",
  "company_name": "SAREGAMA INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE979A01025",
  "face_value": 100.0
 },
 {
  "symbol": "SARLAPOLY",
  "company_name": "SARLA PERF. FIBERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE453D01025",
  "face_value": 100.0
 },
 {
  "symbol": "SARVES-RE",
  "company_name": "SARVESHWAR FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE324X20018",
  "face_value": 100.0
 },
 {
  "symbol": "SARVESHWAR",
  "company_name": "SARVESHWAR FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE324X01026",
  "face_value": 100.0
 },
 {
  "symbol": "SASKEN",
  "company_name": "SASKEN TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE231F01020",
  "face_value": 1000.0
 },
 {
  "symbol": "SASTASUNDR",
  "company_name": "SASTASUNDAR VENTURES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE019J01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SATHAISPAT",
  "company_name": "SATHAVAHANA ISPAT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE176C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SATHVANISP",
  "company_name": "SATHAVAHANA ISPAT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE176C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SATIA",
  "company_name": "SATIA INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE170E01023",
  "face_value": 100.0
 },
 {
  "symbol": "SATIN",
  "company_name": "SATIN CREDIT NET LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE836B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SATIN-RE",
  "company_name": "SATIN CREDITCARE RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE836B20017",
  "face_value": 1000.0
 },
 {
  "symbol": "SATYAMCEM",
  "company_name": "SATYAM CEMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE285201013",
  "face_value": 1000.0
 },
 {
  "symbol": "SAURASHCEM",
  "company_name": "SAURASHTRA CEMENT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE626A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "SAURASTPPR",
  "company_name": "SAURASHTRA PAPER & BOARD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE285601014",
  "face_value": 1000.0
 },
 {
  "symbol": "SAYAJHOTEL",
  "company_name": "SAYAJI HOTELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE286301010",
  "face_value": 1000.0
 },
 {
  "symbol": "SAYAJIHOTL",
  "company_name": "SAYAJI HOTELS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE318C01014",
  "face_value": 1000.0
 },
 {
  "symbol": "SBBJ",
  "company_name": "STATE BANK OF BIKANER & J",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE648A01026",
  "face_value": 1000.0
 },
 {
  "symbol": "SBC",
  "company_name": "SBC EXPORTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE04AK01028",
  "face_value": 100.0
 },
 {
  "symbol": "SBCL",
  "company_name": "SHIVALIK BIMETAL CON. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE386D01027",
  "face_value": 200.0
 },
 {
  "symbol": "SBFC",
  "company_name": "SBFC FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE423Y01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SBGLP",
  "company_name": "SURATWWALA BUS GROUP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE05ST01028",
  "face_value": 100.0
 },
 {
  "symbol": "SBI150INAV",
  "company_name": "SBIAMC - SBI150INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000346",
  "face_value": 1000.0
 },
 {
  "symbol": "SBIBPB",
  "company_name": "SBIAMC - SBIBPB",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KB1712",
  "face_value": 1000.0
 },
 {
  "symbol": "SBIBPBINAV",
  "company_name": "SBIAMC - SBIBPBINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000268",
  "face_value": 1000.0
 },
 {
  "symbol": "SBICARD",
  "company_name": "SBI CARDS & PAY SER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE018E01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SBICONINAV",
  "company_name": "SBIETFCON INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000135",
  "face_value": 100.0
 },
 {
  "symbol": "SBIETFCON",
  "company_name": "SBIAMC - SBIETFCON",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KA1X17",
  "face_value": 1000.0
 },
 {
  "symbol": "SBIETFINAV",
  "company_name": "SBIETFIT INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000138",
  "face_value": 100.0
 },
 {
  "symbol": "SBIETFIT",
  "company_name": "SBIAMC - SBIETFIT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KA1S14",
  "face_value": 1000.0
 },
 {
  "symbol": "SBIETFPB",
  "company_name": "SBIAMC - SBIETFPB",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KA1S22",
  "face_value": 1000.0
 },
 {
  "symbol": "SBIETFQLTY",
  "company_name": "SBIAMC - SBIETFQLTY",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KA1WX6",
  "face_value": 1000.0
 },
 {
  "symbol": "SBIFPBINAV",
  "company_name": "SBIETFPB INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000136",
  "face_value": 100.0
 },
 {
  "symbol": "SBIHOMEFIN",
  "company_name": "SBI HOME FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE627A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SBILIFE",
  "company_name": "SBI LIFE INSURANCE CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE123W01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SBILIQETF",
  "company_name": "SBIAMC - SBILIQETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KB1969",
  "face_value": 100000.0
 },
 {
  "symbol": "SBILIQINAV",
  "company_name": "SBIAMC - SBILIQINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000293",
  "face_value": 100000.0
 },
 {
  "symbol": "SBILTYINAV",
  "company_name": "SBIETFQLTY INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000134",
  "face_value": 100.0
 },
 {
  "symbol": "SBIMIDMOM",
  "company_name": "SBIAMC - SBIMIDMOM",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KB1AJ0",
  "face_value": 1000.0
 },
 {
  "symbol": "SBIMOMINAV",
  "company_name": "SBIAMC - SBIMOMINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000341",
  "face_value": 1000.0
 },
 {
  "symbol": "SBIN",
  "company_name": "STATE BANK OF INDIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE062A01020",
  "face_value": 100.0
 },
 {
  "symbol": "SBINEQINAV",
  "company_name": "SBIAMC - SBINEQINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000233",
  "face_value": 1000.0
 },
 {
  "symbol": "SBINEQWETF",
  "company_name": "SBIAMC - SBINEQWETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KB1282",
  "face_value": 1000.0
 },
 {
  "symbol": "SBINMID150",
  "company_name": "SBIAMC - SBINMID150",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KB1AK8",
  "face_value": 1000.0
 },
 {
  "symbol": "SBISILINAV",
  "company_name": "SBIAMC - SBISILINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000229",
  "face_value": 1000.0
 },
 {
  "symbol": "SBISILVER",
  "company_name": "SBIAMC - SBISILVER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KB1217",
  "face_value": 1000.0
 },
 {
  "symbol": "SBT",
  "company_name": "STATE BANK OF TRAVANCORE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE654A01024",
  "face_value": 1000.0
 },
 {
  "symbol": "SCANSTL",
  "company_name": "SCAN STEELS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE099G01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SCHAEFFLER",
  "company_name": "SCHAEFFLER INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE513A01022",
  "face_value": 200.0
 },
 {
  "symbol": "SCHAND",
  "company_name": "S CHAND AND COMPANY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE807K01035",
  "face_value": 500.0
 },
 {
  "symbol": "SCHNEIDER",
  "company_name": "SCHNEIDER ELECTRIC INFRA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE839M01018",
  "face_value": 200.0
 },
 {
  "symbol": "SCI",
  "company_name": "SHIPPING CORP OF INDIA LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE109A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SCILAL",
  "company_name": "SHIPPING CORP OF ILA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0PB301013",
  "face_value": 1000.0
 },
 {
  "symbol": "SCODATUBES",
  "company_name": "SCODA TUBES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE090501011",
  "face_value": 1000.0
 },
 {
  "symbol": "SCPL",
  "company_name": "SHEETAL COOL PRODUCTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE501Y01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SDBL",
  "company_name": "SOM DIST & BREW LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE480C01038",
  "face_value": 200.0
 },
 {
  "symbol": "SDBL-RE",
  "company_name": "SOM DISTILL & BREW LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE480C20012",
  "face_value": 500.0
 },
 {
  "symbol": "SDBL-RE1",
  "company_name": "SOM DIST & BREW LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE480C20020",
  "face_value": 500.0
 },
 {
  "symbol": "SDL24BEES",
  "company_name": "NIPPON INDIA- NIMFXX",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KB18W4",
  "face_value": 1000.0
 },
 {
  "symbol": "SDL24BINAV",
  "company_name": "SDL24BEES INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000128",
  "face_value": 100.0
 },
 {
  "symbol": "SDL26BEES",
  "company_name": "RELCAPAMC-NETFSDL26",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KC1022",
  "face_value": 1000.0
 },
 {
  "symbol": "SDL26BINAV",
  "company_name": "SDL26BEES INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000129",
  "face_value": 100.0
 },
 {
  "symbol": "SEAMECLTD",
  "company_name": "SEAMEC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE497B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "SECALS",
  "company_name": "SECALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE287901016",
  "face_value": 1000.0
 },
 {
  "symbol": "SECMARK",
  "company_name": "SECMARK CONSULTANCY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0BTM01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SECURCRED",
  "company_name": "SECUR CREDENTIALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE195Y01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SECURKLOUD",
  "company_name": "SECUREKLOUD TECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE650K01021",
  "face_value": 500.0
 },
 {
  "symbol": "SEDEMAC",
  "company_name": "SEDEMAC MECHATRONICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00XB01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SEIL",
  "company_name": "SHANTI EDU INITIATIVES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE440T01028",
  "face_value": 100.0
 },
 {
  "symbol": "SEJAL",
  "company_name": "SEJAL GLASS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE955I01036",
  "face_value": 1000.0
 },
 {
  "symbol": "SEJALLTD",
  "company_name": "SEJAL GLASS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE955I01044",
  "face_value": 1000.0
 },
 {
  "symbol": "SELECTIPO",
  "company_name": "MIRAEAMC - SELECTIPO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01ON4",
  "face_value": 1000.0
 },
 {
  "symbol": "SELIPOINAV",
  "company_name": "MIRAEAMC - SELIPOINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000263",
  "face_value": 1000.0
 },
 {
  "symbol": "SELMC",
  "company_name": "SEL MANUFACTURING CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE105I01020",
  "face_value": 1000.0
 },
 {
  "symbol": "SELMCL",
  "company_name": "SEL MANU. CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE105I01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SEMAC",
  "company_name": "SEMAC CONSTRUCTION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE617A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SENCO",
  "company_name": "SENCO GOLD LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE602W01027",
  "face_value": 500.0
 },
 {
  "symbol": "SENORES",
  "company_name": "SENORES PHARMACEUTICALS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0RB801010",
  "face_value": 1000.0
 },
 {
  "symbol": "SENSEXADD",
  "company_name": "DSPAMC - DSPSENXETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1SZ6",
  "face_value": 1000.0
 },
 {
  "symbol": "SENSEXBETA",
  "company_name": "UTIAMC-SENSEXBETA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF789FB1X58",
  "face_value": 1000.0
 },
 {
  "symbol": "SENSEXETF",
  "company_name": "MIRAEAMC - SENSEXETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01KT9",
  "face_value": 1000.0
 },
 {
  "symbol": "SENSEXIETF",
  "company_name": "ICICI PRUD SENSEX ETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF346A01034",
  "face_value": 1000.0
 },
 {
  "symbol": "SENSEXINAV",
  "company_name": "MIRAEAMC - SENSEXINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000199",
  "face_value": 1000.0
 },
 {
  "symbol": "SEPC",
  "company_name": "SEPC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE964H01014",
  "face_value": 1000.0
 },
 {
  "symbol": "SEPC-RE",
  "company_name": "SEPC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE964H20014",
  "face_value": 1000.0
 },
 {
  "symbol": "SEPC-RE1",
  "company_name": "SEPC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE964H20022",
  "face_value": 1000.0
 },
 {
  "symbol": "SEPC-RE2",
  "company_name": "SEPC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE964H20030",
  "face_value": 1000.0
 },
 {
  "symbol": "SEPC-RE3",
  "company_name": "SEPC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE964H20055",
  "face_value": 1000.0
 },
 {
  "symbol": "SERENDYSTF",
  "company_name": "SERENE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE576601012",
  "face_value": 1000.0
 },
 {
  "symbol": "SERVOTECH",
  "company_name": "SERVOTECH REN POW SYS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE782X01033",
  "face_value": 100.0
 },
 {
  "symbol": "SESHAPAPER",
  "company_name": "SESHASAYEE PAPER & BOARDS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE630A01024",
  "face_value": 200.0
 },
 {
  "symbol": "SETCO",
  "company_name": "SETCO AUTOMOTIVE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE878E01021",
  "face_value": 200.0
 },
 {
  "symbol": "SETF10GILT",
  "company_name": "SBIAMC - SETF10GILT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KA1JT1",
  "face_value": 1000.0
 },
 {
  "symbol": "SETF10INAV",
  "company_name": "SETF10GILT INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000137",
  "face_value": 100.0
 },
 {
  "symbol": "SETF50INAV",
  "company_name": "SETFNIF50 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000139",
  "face_value": 100.0
 },
 {
  "symbol": "SETFGOINAV",
  "company_name": "SETFGOLD NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000046",
  "face_value": 100.0
 },
 {
  "symbol": "SETFGOLD",
  "company_name": "SBI-ETF GOLD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KA16D8",
  "face_value": 100.0
 },
 {
  "symbol": "SETFNIF50",
  "company_name": "SBI-ETF NIFTY 50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KA1FS1",
  "face_value": 1000.0
 },
 {
  "symbol": "SETFNIFBK",
  "company_name": "SBI-ETF NIFTY BANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KA1580",
  "face_value": 1000.0
 },
 {
  "symbol": "SETFNIINAV",
  "company_name": "SETFNIFBK INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000140",
  "face_value": 100.0
 },
 {
  "symbol": "SETFNN50",
  "company_name": "SBI-ETF NIFTY NEXT 50",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF200KA1598",
  "face_value": 1000.0
 },
 {
  "symbol": "SETFNNINAV",
  "company_name": "SETFNN50 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000141",
  "face_value": 100.0
 },
 {
  "symbol": "SETL",
  "company_name": "STANDARD ENGNG TCNLGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0M4D01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SETUINFRA",
  "company_name": "SETUBANDHAN INFRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE023M01027",
  "face_value": 100.0
 },
 {
  "symbol": "SEYAIND",
  "company_name": "SEYA INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE573R01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SFHL-RE",
  "company_name": "SUNDARAM FINANCE RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE202Z20011",
  "face_value": 500.0
 },
 {
  "symbol": "SFL",
  "company_name": "SHEELA FOAM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE916U01025",
  "face_value": 500.0
 },
 {
  "symbol": "SGFIN",
  "company_name": "SG FINSERVE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE618R01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SGFL",
  "company_name": "SHREE GANESH FORG. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE883G01018",
  "face_value": 1000.0
 },
 {
  "symbol": "SGIL",
  "company_name": "SYNERGY GREEN IND. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00QT01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SGIL-RE",
  "company_name": "SYNERGY GREEN IND. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00QT20015",
  "face_value": 1000.0
 },
 {
  "symbol": "SGL",
  "company_name": "STL GLOBAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE353H01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SGMART",
  "company_name": "SG MART LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE385F01024",
  "face_value": 100.0
 },
 {
  "symbol": "SHAANINTER",
  "company_name": "SHAAN INTERWEL (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE465401011",
  "face_value": 1000.0
 },
 {
  "symbol": "SHADOWFAX",
  "company_name": "SHADOWFAX TECHNOLOGIES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE12UN01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SHAH",
  "company_name": "SHAH METACORP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE482J01021",
  "face_value": 100.0
 },
 {
  "symbol": "SHAHALLOYS",
  "company_name": "SHAH ALLOYS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE640C01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SHAILY",
  "company_name": "SHAILY ENG PLASTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE151G01028",
  "face_value": 200.0
 },
 {
  "symbol": "SHAKTIPUMP",
  "company_name": "SHAKTI PUMPS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE908D01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SHALBY",
  "company_name": "SHALBY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE597J01018",
  "face_value": 1000.0
 },
 {
  "symbol": "SHALMPAINT",
  "company_name": "SHALIMAR PAINTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE849C01026",
  "face_value": 1000.0
 },
 {
  "symbol": "SHALPAINTS",
  "company_name": "SHALIM PAINTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE849C01026",
  "face_value": 200.0
 },
 {
  "symbol": "SHAMKNFAB",
  "company_name": "SHAMKEN MULTIFAB LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE565B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SHAMKNSPIN",
  "company_name": "SHAMKEN SPINNERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE626B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SHANKARA",
  "company_name": "SHANKARA BLDG PRODUCT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE274V01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SHANTI",
  "company_name": "SHANTI OVERSEAS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE933X01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SHANTIGEAR",
  "company_name": "SHANTHI GEARS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE631A01022",
  "face_value": 100.0
 },
 {
  "symbol": "SHANTIGOLD",
  "company_name": "SHANTI GOLD INTERNATION L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE06ZD01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SHARDACROP",
  "company_name": "SHARDA CROPCHEM LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE221J01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SHARDAMOTR",
  "company_name": "SHARDA MOTOR INDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE597I01028",
  "face_value": 200.0
 },
 {
  "symbol": "SHARDATERY",
  "company_name": "SHARDA TERRY PRODUCTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE290801013",
  "face_value": 1000.0
 },
 {
  "symbol": "SHARDUL",
  "company_name": "SHARDUL SECURITIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE037B01020",
  "face_value": 200.0
 },
 {
  "symbol": "SHARE-RE",
  "company_name": "SHARE IND SEC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE932X20018",
  "face_value": 1000.0
 },
 {
  "symbol": "SHAREINDIA",
  "company_name": "SHARE IND. SECURITIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE932X01026",
  "face_value": 200.0
 },
 {
  "symbol": "SHARIABEES",
  "company_name": "NIP IND ETF SHARIAH BEES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF732E01128",
  "face_value": 1000.0
 },
 {
  "symbol": "SHARIBENAV",
  "company_name": "SHARIAH BEES NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000033",
  "face_value": 1000.0
 },
 {
  "symbol": "SHARONBIO",
  "company_name": "SHARON BIO-MEDI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE028B01029",
  "face_value": 200.0
 },
 {
  "symbol": "SHARTSEFOD",
  "company_name": "SHARAT INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE465501018",
  "face_value": 1000.0
 },
 {
  "symbol": "SHARYANRES",
  "company_name": "SHARYANS RESOURCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE559D01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SHAWALLACE",
  "company_name": "SHAW WALLACE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE291901010",
  "face_value": 1000.0
 },
 {
  "symbol": "SHAWGELTIN",
  "company_name": "SHAW WALLACE GELATINES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE869A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SHBAJRG",
  "company_name": "SHRI BAJRANG ALLIANCE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE402H01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SHEKHAWATI",
  "company_name": "SHEKHAWATI INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE268L01046",
  "face_value": 1000.0
 },
 {
  "symbol": "SHEMAROO",
  "company_name": "SHEMAROO ENTER. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE363M01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SHETRON",
  "company_name": "SHETRON LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE292401010",
  "face_value": 1000.0
 },
 {
  "symbol": "SHILCTECH",
  "company_name": "SHILCHAR TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE024F01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SHILPAMED",
  "company_name": "SHILPA MEDICARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE790G01031",
  "face_value": 100.0
 },
 {
  "symbol": "SHINDL",
  "company_name": "SHARAT INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE220Z01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SHIRPUR-G",
  "company_name": "SHIRPUR GOLD REFINERY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE196B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SHIVAJWORK",
  "company_name": "SHIVAJI WORKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE294001016",
  "face_value": 1000.0
 },
 {
  "symbol": "SHIVALIK",
  "company_name": "SHIVALIK RASAYAN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE788J01021",
  "face_value": 500.0
 },
 {
  "symbol": "SHIVAM-RE",
  "company_name": "SHIVAM AUTOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE637H20016",
  "face_value": 200.0
 },
 {
  "symbol": "SHIVAMAUTO",
  "company_name": "SHIVAM AUTO.LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE637H01024",
  "face_value": 200.0
 },
 {
  "symbol": "SHIVAMILLS",
  "company_name": "SHIVA MILLS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE644Y01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SHIVATEX",
  "company_name": "SHIVA TEXYARN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE705C01020",
  "face_value": 1000.0
 },
 {
  "symbol": "SHIVAUM",
  "company_name": "SHIV AUM STEELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE719F01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SHK",
  "company_name": "S H KELKAR AND CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE500L01026",
  "face_value": 1000.0
 },
 {
  "symbol": "SHLAKSHMI",
  "company_name": "SHRI LAKSHMI COTSYN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE851B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SHOPER-RE",
  "company_name": "SHOPPERS STOP RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE498B20016",
  "face_value": 500.0
 },
 {
  "symbol": "SHOPERSTOP",
  "company_name": "SHOPPERS STOP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE498B01024",
  "face_value": 500.0
 },
 {
  "symbol": "SHOPINVFIN",
  "company_name": "SHOPPERS  INV & FIN  CO.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE294301010",
  "face_value": 1000.0
 },
 {
  "symbol": "SHRADHA",
  "company_name": "SHRADHA REALTY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE715Y01031",
  "face_value": 200.0
 },
 {
  "symbol": "SHRADHA-RE",
  "company_name": "SHRADHA INFRAPROJECTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE715Y20015",
  "face_value": 200.0
 },
 {
  "symbol": "SHREAMBPPR",
  "company_name": "SHREE AMBESHWAR PPR MILLS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE294501015",
  "face_value": 1000.0
 },
 {
  "symbol": "SHREDIGCEM",
  "company_name": "SHREE DIGVIJAY CEM CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE232A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SHREECEM",
  "company_name": "SHREE CEMENT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE070A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SHREEJISPG",
  "company_name": "SHREEJI SHIPPING GLOBAL L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1B6101010",
  "face_value": 1000.0
 },
 {
  "symbol": "SHREEKRPET",
  "company_name": "ESKAY K  N  IT (INDIA) LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE220A01024",
  "face_value": 400.0
 },
 {
  "symbol": "SHREEKRPOL",
  "company_name": "KRISHNA LIFESTYLE TECHNOL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE218A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SHREEPUSHK",
  "company_name": "SHRE PUSH CHEM & FERT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE712K01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SHREERAMA",
  "company_name": "SHREE RAMA MULTI TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE879A01019",
  "face_value": 500.0
 },
 {
  "symbol": "SHREESYNTH",
  "company_name": "SHREE SYNTHETICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE296201010",
  "face_value": 1000.0
 },
 {
  "symbol": "SHRENIK",
  "company_name": "SHRENIK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE632X01030",
  "face_value": 100.0
 },
 {
  "symbol": "SHREPRECOT",
  "company_name": "SHREE PRECOATED STEELS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE295601012",
  "face_value": 1000.0
 },
 {
  "symbol": "SHRERA-RE",
  "company_name": "SHREE RAMA MULTI-TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE879A20019",
  "face_value": 500.0
 },
 {
  "symbol": "SHRERAJSYN",
  "company_name": "SHREE RAJASTHAN SYNTEX LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE295801018",
  "face_value": 1000.0
 },
 {
  "symbol": "SHREYANIND",
  "company_name": "SHREYANS INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE231C01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SHRIDINESH",
  "company_name": "SHRI DINESH MLLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE297701018",
  "face_value": 10000.0
 },
 {
  "symbol": "SHRIKRISH",
  "company_name": "SHRI KRISHNA DEVCON LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE997I01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SHRINGARMS",
  "company_name": "SHRINGAR HOU OF MANGALS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1B3L01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SHRIPISTON",
  "company_name": "SHRIRAM PIST. & RING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE526E01018",
  "face_value": 1000.0
 },
 {
  "symbol": "SHRIRAMCIT",
  "company_name": "SHRIRAM CITYUNI FIN.LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE722A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SHRIRAMFIN",
  "company_name": "SHRIRAM FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE721A01047",
  "face_value": 200.0
 },
 {
  "symbol": "SHRIRAMPPS",
  "company_name": "SHRIRAM PROPERTIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE217L01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SHRIYAMSEC",
  "company_name": "SHRIYAM SECURITIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE037B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SHUKRADIAM",
  "company_name": "SHUKRA DIAMONDS EXPORTS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE299701016",
  "face_value": 1000.0
 },
 {
  "symbol": "SHYAMCENT",
  "company_name": "SHYAM CENTURY FERROUS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE979R01011",
  "face_value": 100.0
 },
 {
  "symbol": "SHYAMMETL",
  "company_name": "SHYAM METALICS AND ENGY L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE810G01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SHYAMTEL",
  "company_name": "SHYAM TELECOM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE635A01023",
  "face_value": 1000.0
 },
 {
  "symbol": "SICAGEN",
  "company_name": "SICAGEN INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE176J01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SICAL",
  "company_name": "SICAL LOGISTICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE075B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SICAL-RE",
  "company_name": "SICAL LOGISTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE075B20012",
  "face_value": 1000.0
 },
 {
  "symbol": "SICALLOG",
  "company_name": "SICAL LOGISTICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE075B01020",
  "face_value": 1000.0
 },
 {
  "symbol": "SIDDHATUBE",
  "company_name": "SIDDHARTHA TUBES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE708B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "SIEL",
  "company_name": "SIEL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE636A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SIEMENS",
  "company_name": "SIEMENS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE003A01024",
  "face_value": 200.0
 },
 {
  "symbol": "SIGACHI",
  "company_name": "SIGACHI INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0D0K01022",
  "face_value": 100.0
 },
 {
  "symbol": "SIGIND",
  "company_name": "SIGNET INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE529F01035",
  "face_value": 1000.0
 },
 {
  "symbol": "SIGMA",
  "company_name": "SIGMA SOLVE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0A0S01028",
  "face_value": 100.0
 },
 {
  "symbol": "SIGMAADV",
  "company_name": "SIGMA ADVANCED SYSTEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE933B01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SIGNATURE",
  "company_name": "SIGNATUREGLOBAL INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE903U01023",
  "face_value": 100.0
 },
 {
  "symbol": "SIGNET",
  "company_name": "SIGNET INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE529F01027",
  "face_value": 100.0
 },
 {
  "symbol": "SIGNPOST",
  "company_name": "SIGNPOST INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0KGZ01021",
  "face_value": 200.0
 },
 {
  "symbol": "SIKA",
  "company_name": "SIKA INTERPLANT SYSTEMS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE438E01032",
  "face_value": 200.0
 },
 {
  "symbol": "SIKKO",
  "company_name": "SIKKO INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE112X01025",
  "face_value": 100.0
 },
 {
  "symbol": "SIKKO-RE",
  "company_name": "SIKKO INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE112X20017",
  "face_value": 1000.0
 },
 {
  "symbol": "SIL",
  "company_name": "STANDARD INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE173A01025",
  "face_value": 500.0
 },
 {
  "symbol": "SIL360INAV",
  "company_name": "360ONEAMC - SIL360INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000271",
  "face_value": 1000.0
 },
 {
  "symbol": "SILBNDINAV",
  "company_name": "BANDHANAMC - SILBNDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000322",
  "face_value": 1000.0
 },
 {
  "symbol": "SILCASINAV",
  "company_name": "ZERODHAAMC - SILCASINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000267",
  "face_value": 1000.0
 },
 {
  "symbol": "SILETFINAV",
  "company_name": "UTIAMC - SILETFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000185",
  "face_value": 7581.0
 },
 {
  "symbol": "SILGO",
  "company_name": "SILGO RETAIL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01II01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SILGO-RE",
  "company_name": "SILGO RETAIL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01II20013",
  "face_value": 1000.0
 },
 {
  "symbol": "SILGO-RE1",
  "company_name": "SILGO RETAIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01II20021",
  "face_value": 1000.0
 },
 {
  "symbol": "SILINV",
  "company_name": "SIL INVESTMENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE923A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SILLYMONKS",
  "company_name": "SILLY MONKS ENTERTAIN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE203Y01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SILVER",
  "company_name": "BIRLASLAMC - SILVER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KB19F6",
  "face_value": 100.0
 },
 {
  "symbol": "SILVER1",
  "company_name": "KOTAKMAMC - KOTAKSILVE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF174KA1ZD3",
  "face_value": 100.0
 },
 {
  "symbol": "SILVER360",
  "company_name": "360ONEAMC - SILVER360",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF579M01BC3",
  "face_value": 1000.0
 },
 {
  "symbol": "SILVERADD",
  "company_name": "DSPAMC - DSPSILVETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1RE3",
  "face_value": 1000.0
 },
 {
  "symbol": "SILVERAG",
  "company_name": "MIRAEAMC - MASILVER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01KG6",
  "face_value": 1000.0
 },
 {
  "symbol": "SILVERBEES",
  "company_name": "NIPPONAMC - NETFSILVER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KC1402",
  "face_value": 1000.0
 },
 {
  "symbol": "SILVERBETA",
  "company_name": "UTIAMC-SILVERBETA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF789F1AYK6",
  "face_value": 1000.0
 },
 {
  "symbol": "SILVERBND",
  "company_name": "BANDHANAMC - SILVERBND",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF194KB1KI9",
  "face_value": 1000.0
 },
 {
  "symbol": "SILVERCASE",
  "company_name": "ZERODHAAMC - SILVERCASE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF0R8F01091",
  "face_value": 1000.0
 },
 {
  "symbol": "SILVERIETF",
  "company_name": "ICICIPRAMC - ICICISILVE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC1Y56",
  "face_value": 1000.0
 },
 {
  "symbol": "SILVERINAV",
  "company_name": "SILVER NAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000047",
  "face_value": 100.0
 },
 {
  "symbol": "SILVERLINE",
  "company_name": "SILVERLINE TECHNOLOGIES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE368A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SILVERTUC",
  "company_name": "SILVER TOUCH TECHNO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE625X01026",
  "face_value": 200.0
 },
 {
  "symbol": "SIMBHALS",
  "company_name": "SIMBHAOLI SUGARS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE748T01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SIMBHALSUG",
  "company_name": "SIMBHAOLI SUGAR MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE380601018",
  "face_value": 1000.0
 },
 {
  "symbol": "SIMPLEX",
  "company_name": "SIMPLEX PROJECTS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE898F01018",
  "face_value": 1000.0
 },
 {
  "symbol": "SIMPLEXCAS",
  "company_name": "SIMPLEX CASTING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE658D01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SIMPLEXINF",
  "company_name": "SIMPLEX INFRASTRUCTURES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE059B01024",
  "face_value": 200.0
 },
 {
  "symbol": "SINCLAIR",
  "company_name": "SINCLAIRS HOTELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE985A01022",
  "face_value": 200.0
 },
 {
  "symbol": "SINDHUTRAD",
  "company_name": "SINDHU TRADE LINKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE325D01025",
  "face_value": 100.0
 },
 {
  "symbol": "SINGER",
  "company_name": "SINGER INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE381301014",
  "face_value": 1000.0
 },
 {
  "symbol": "SINGERIND",
  "company_name": "SINGER INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE638A01035",
  "face_value": 200.0
 },
 {
  "symbol": "SINTERCOM",
  "company_name": "SINTERCOM INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE129Z01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SINTEX",
  "company_name": "SINTEX INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE429C01035",
  "face_value": 100.0
 },
 {
  "symbol": "SIPAPER",
  "company_name": "SOUTH INDIA PAPER MILLS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE581501017",
  "face_value": 1000.0
 },
 {
  "symbol": "SIRCA",
  "company_name": "SIRCA PAINT INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE792Z01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SIRIS",
  "company_name": "SIRIS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE375301012",
  "face_value": 1000.0
 },
 {
  "symbol": "SIS",
  "company_name": "SIS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE285J01028",
  "face_value": 500.0
 },
 {
  "symbol": "SITASHREE",
  "company_name": "SITA SHREE FOOD PROD LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE686I01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SITINET",
  "company_name": "SITI NETWORKS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE965H01011",
  "face_value": 100.0
 },
 {
  "symbol": "SIYSIL",
  "company_name": "SIYARAM SILK MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE076B01028",
  "face_value": 200.0
 },
 {
  "symbol": "SJS",
  "company_name": "SJS ENTERPRISES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE284S01014",
  "face_value": 1000.0
 },
 {
  "symbol": "SJVN",
  "company_name": "SJVN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE002L01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SKFINDIA",
  "company_name": "SKF INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE640A01023",
  "face_value": 1000.0
 },
 {
  "symbol": "SKFINDUS",
  "company_name": "SKF IND (INDUSTRIAL) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE2J8701016",
  "face_value": 1000.0
 },
 {
  "symbol": "SKIL",
  "company_name": "SKIL INFRASTRUCTURE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE429F01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SKIPPER",
  "company_name": "SKIPPER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE439E01022",
  "face_value": 100.0
 },
 {
  "symbol": "SKIPPER-RE",
  "company_name": "SKIPPER LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE439E20014",
  "face_value": 100.0
 },
 {
  "symbol": "SKMEGGPROD",
  "company_name": "SKM EGG PROD EXPORT(I) LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE411D01023",
  "face_value": 500.0
 },
 {
  "symbol": "SKSIND",
  "company_name": "SKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE464901011",
  "face_value": 1000.0
 },
 {
  "symbol": "SKUMARSYNF",
  "company_name": "S KUMARS NATIONWIDE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE772A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SKYGOLD",
  "company_name": "SKY GOLD AND DIAMONDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01IU01018",
  "face_value": 1000.0
 },
 {
  "symbol": "SMAADDINAV",
  "company_name": "DSPAMC - SMAADDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000325",
  "face_value": 1000.0
 },
 {
  "symbol": "SMACAPINAV",
  "company_name": "MIRAEAMC - SMACAPINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000218",
  "face_value": 1000.0
 },
 {
  "symbol": "SMALL250",
  "company_name": "MIRAEAMC - SMALL250",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01PQ4",
  "face_value": 1000.0
 },
 {
  "symbol": "SMALL2INAV",
  "company_name": "MIRAEAMC - SMALL2INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000311",
  "face_value": 1000.0
 },
 {
  "symbol": "SMALLADD",
  "company_name": "DSPAMC - SMALLADD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1WX3",
  "face_value": 1000.0
 },
 {
  "symbol": "SMALLCAP",
  "company_name": "MIRAEAMC - SMALLCAP",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01LC3",
  "face_value": 1000.0
 },
 {
  "symbol": "SMARTLINK",
  "company_name": "SMARTLINK HOLDINGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE178C01020",
  "face_value": 200.0
 },
 {
  "symbol": "SMARTWORKS",
  "company_name": "SMARTWORKS COWORKING SP L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0NAZ01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SMCGLOBAL",
  "company_name": "SMC GLOBAL SECURITIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE103C01036",
  "face_value": 200.0
 },
 {
  "symbol": "SMDYECHEM",
  "company_name": "S M DYECHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE620A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SML100CASE",
  "company_name": "ZERODHAAMC - SML100CASE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF0R8F01141",
  "face_value": 1000.0
 },
 {
  "symbol": "SML100INAV",
  "company_name": "ZERODHAAMC - SML100INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000300",
  "face_value": 1000.0
 },
 {
  "symbol": "SMLMAH",
  "company_name": "SML MAHINDRA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE294B01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SMLT",
  "company_name": "SARTHAK METALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE017W01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SMPL",
  "company_name": "SPLENDID METAL PRODUCTS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE215G01021",
  "face_value": 500.0
 },
 {
  "symbol": "SMSPHARMA",
  "company_name": "SMS PHARMACEUTICALS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE812G01025",
  "face_value": 100.0
 },
 {
  "symbol": "SNEHAIND",
  "company_name": "SNEHADHARA INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE377601013",
  "face_value": 1000.0
 },
 {
  "symbol": "SNOWMAN",
  "company_name": "SNOWMAN LOGISTICS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE734N01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SNXT30BEES",
  "company_name": "NIPPONAMC - SNXT30BEES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF204KC1EZ3",
  "face_value": 1000.0
 },
 {
  "symbol": "SNXT30INAV",
  "company_name": "NIPPONAMC - SNXT30INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000283",
  "face_value": 1000.0
 },
 {
  "symbol": "SNXT50BETA",
  "company_name": "UTIAMC-SNXT50BETA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF789F1AUU3",
  "face_value": 100.0
 },
 {
  "symbol": "SOBHA",
  "company_name": "SOBHA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE671H01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SOBHA-RE",
  "company_name": "SOBHA LTD-RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE671H20015",
  "face_value": 1000.0
 },
 {
  "symbol": "SOFTTECH",
  "company_name": "SOFTTECH ENGINEERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE728Z01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SOLARA",
  "company_name": "SOLARA ACTIVE PHA SCI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE624Z01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SOLARA-RE",
  "company_name": "SOLARA ACTIVE PHA SCI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE624Z20016",
  "face_value": 1000.0
 },
 {
  "symbol": "SOLARINDS",
  "company_name": "SOLAR INDUSTRIES (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE343H01029",
  "face_value": 200.0
 },
 {
  "symbol": "SOLARSNIND",
  "company_name": "SOLARSON INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE378101013",
  "face_value": 1000.0
 },
 {
  "symbol": "SOLARWORLD",
  "company_name": "SOLARWORLD ENERGY SOL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0TY101024",
  "face_value": 500.0
 },
 {
  "symbol": "SOLEX",
  "company_name": "SOLEX ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE880Y01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SOLPHARMA",
  "company_name": "SOL PHARMACEUTICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE377901017",
  "face_value": 1000.0
 },
 {
  "symbol": "SOMANISWIS",
  "company_name": "SOMANI SWISS INDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE581001018",
  "face_value": 1000.0
 },
 {
  "symbol": "SOMANYCERA",
  "company_name": "SOMANY CERAMICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE355A01028",
  "face_value": 200.0
 },
 {
  "symbol": "SOMATEX",
  "company_name": "SOMA TEXTILES & INDUST LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE314C01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SOMDUTTFIN",
  "company_name": "SOM DUTT FIN. CORP. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE378501014",
  "face_value": 1000.0
 },
 {
  "symbol": "SOMICONVEY",
  "company_name": "SOMI CONVEYOR BELT. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE323J01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SOMKMARINE",
  "company_name": "SOMKAN MARINE FOODS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE373101018",
  "face_value": 1000.0
 },
 {
  "symbol": "SONACOMS",
  "company_name": "SONA BLW PRECISION FRGS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE073K01018",
  "face_value": 1000.0
 },
 {
  "symbol": "SONAL",
  "company_name": "SONAL MERCANTILE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE321M01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SONALCOSM",
  "company_name": "SONAL COSMETICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY9297",
  "face_value": 1000.0
 },
 {
  "symbol": "SONAMLTD",
  "company_name": "SONAM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00LM01029",
  "face_value": 500.0
 },
 {
  "symbol": "SONATSOFTW",
  "company_name": "SONATA SOFTWARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE269A01021",
  "face_value": 100.0
 },
 {
  "symbol": "SORILINFRA",
  "company_name": "SORIL INFRA RESOURCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE034H01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SOTL",
  "company_name": "SAVITA OIL TECHNOLO. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE035D01020",
  "face_value": 200.0
 },
 {
  "symbol": "SOUTH-RE",
  "company_name": "THE SOUTH INDIAN BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE683A20015",
  "face_value": 100.0
 },
 {
  "symbol": "SOUTHBANK",
  "company_name": "THE SOUTH INDIAN BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE683A01023",
  "face_value": 100.0
 },
 {
  "symbol": "SOUTHNHERB",
  "company_name": "SOUTHERN HERBALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE001C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SOUTHWEST",
  "company_name": "SOUTH WEST PINNACLE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE980Y01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SPAL",
  "company_name": "S. P. APPARELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE212I01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SPAND-RE",
  "company_name": "SPANDANA SPHOORTY FIN",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE572J20011",
  "face_value": 1000.0
 },
 {
  "symbol": "SPANDANA",
  "company_name": "SPANDANA SPHOORTY FIN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE572J01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SPARC",
  "company_name": "SUN PHARMA ADV.RES.CO.LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE232I01014",
  "face_value": 100.0
 },
 {
  "symbol": "SPARTEK",
  "company_name": "SPARTEK CERAMICS (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE370101011",
  "face_value": 1000.0
 },
 {
  "symbol": "SPCENET",
  "company_name": "SPACENET ENTERS IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE970N01027",
  "face_value": 100.0
 },
 {
  "symbol": "SPECIALITY",
  "company_name": "SPECIALITY REST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE247M01014",
  "face_value": 1000.0
 },
 {
  "symbol": "SPECIALSTL",
  "company_name": "TATA SSL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE675A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SPECTRUM",
  "company_name": "SPECTRUM ELECTRIC IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01EO01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SPENCER-RE",
  "company_name": "SPENCERS RETAIL RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE020820010",
  "face_value": 500.0
 },
 {
  "symbol": "SPENCERS",
  "company_name": "SPENCER S RETAIL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE020801028",
  "face_value": 500.0
 },
 {
  "symbol": "SPENTXIND",
  "company_name": "SPENTEX INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE376C01020",
  "face_value": 1000.0
 },
 {
  "symbol": "SPIC",
  "company_name": "SPIC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE147A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SPICEJET",
  "company_name": "SPICEJET LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE285B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SPICELEC",
  "company_name": "SPEL SEMICONDUCTOR LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE252A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SPICFINE",
  "company_name": "HENKEL SPIC INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE902A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SPLIL",
  "company_name": "SPL INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE978G01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SPLPETRO",
  "company_name": "SUPREME PETROCHEM LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE663A01033",
  "face_value": 200.0
 },
 {
  "symbol": "SPMLINFRA",
  "company_name": "SPML INFRA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE937A01023",
  "face_value": 200.0
 },
 {
  "symbol": "SPORTKING",
  "company_name": "SPORTKING INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE885H01029",
  "face_value": 100.0
 },
 {
  "symbol": "SPTL",
  "company_name": "SINTEX PLASTICS TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE501W01021",
  "face_value": 100.0
 },
 {
  "symbol": "SRD",
  "company_name": "SHANKAR LAL RAMPAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01NE01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SREEL",
  "company_name": "SREELEATHERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE099F01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SREERAYALK",
  "company_name": " SREE RAYALSEEMA ALKALIES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE284B01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SREINFRA",
  "company_name": "SREI INFRASTRUCTURE FINAN",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE872A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "SRF",
  "company_name": "SRF LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE647A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SRFFINANCE",
  "company_name": "GE CAPITAL TRANS. FIN SER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE366201015",
  "face_value": 1000.0
 },
 {
  "symbol": "SRGHFL",
  "company_name": "SRG HOUSING FINANCE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE559N01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SRHHYPOLTD",
  "company_name": "SREE RAYALSEEMA HHP LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE917H01012",
  "face_value": 1000.0
 },
 {
  "symbol": "SRIMANORG",
  "company_name": "SRIMAN ORGANIC CHEMICAL I",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE367801011",
  "face_value": 1000.0
 },
 {
  "symbol": "SRIPIPES",
  "company_name": "SRIKALAHASTHI PIPES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE943C01027",
  "face_value": 1000.0
 },
 {
  "symbol": "SRISARALOY",
  "company_name": "SHRI ISHAR ALLOY STEELS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE298001012",
  "face_value": 1000.0
 },
 {
  "symbol": "SRISHTIVID",
  "company_name": "SRISHTI VIDEOCORP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE368301011",
  "face_value": 1000.0
 },
 {
  "symbol": "SRIVISHCEM",
  "company_name": "SRI VISHNU CEMENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE286B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SRM",
  "company_name": "SRM CONTRACTORS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0R6Z01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SRPL",
  "company_name": "SHREE RAM PROTEINS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE008Z01020",
  "face_value": 100.0
 },
 {
  "symbol": "SRPL-RE",
  "company_name": "SHREE RAM PROTEINS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE008Z20012",
  "face_value": 100.0
 },
 {
  "symbol": "SRSLTD",
  "company_name": "SRS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE219H01039",
  "face_value": 1000.0
 },
 {
  "symbol": "SRTL",
  "company_name": "SHREE RAM TWISTEX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE19GK01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SRTRANS-RE",
  "company_name": "SHRIRAM TRANSPORT RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE721A20013",
  "face_value": 1000.0
 },
 {
  "symbol": "SSDL",
  "company_name": "SARASWATI SAREE DEPOT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0PQ101010",
  "face_value": 1000.0
 },
 {
  "symbol": "SSISPAT",
  "company_name": "SINGHAL SWAROOP ISPAT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE578901014",
  "face_value": 1000.0
 },
 {
  "symbol": "SSLFINANCE",
  "company_name": "ARCHANA SOFTWARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE149B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SSWL",
  "company_name": "STEEL STRIPS WHEELS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE802C01033",
  "face_value": 100.0
 },
 {
  "symbol": "STALL-RE",
  "company_name": "STALLION FLUOROCHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0RYC20010",
  "face_value": 1000.0
 },
 {
  "symbol": "STALLION",
  "company_name": "STALLION IND FLUOROCHEM L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0RYC01010",
  "face_value": 1000.0
 },
 {
  "symbol": "STANDRDBAT",
  "company_name": "STANDARD BATTERIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE466001018",
  "face_value": 1000.0
 },
 {
  "symbol": "STANLEY",
  "company_name": "STANLEY LIFESTYLES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01A001028",
  "face_value": 200.0
 },
 {
  "symbol": "STAR",
  "company_name": "STRIDES PHARMA SCI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE939A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "STARCEMENT",
  "company_name": "STAR CEMENT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE460H01021",
  "face_value": 100.0
 },
 {
  "symbol": "STARHEALTH",
  "company_name": "STAR HEALTH & AL INS CO L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE575P01011",
  "face_value": 1000.0
 },
 {
  "symbol": "STARPAPER",
  "company_name": "STAR PAPER MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE733A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "STARTECK",
  "company_name": "STARTECK FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE992I01013",
  "face_value": 1000.0
 },
 {
  "symbol": "STCINDIA",
  "company_name": "THE STATE TRADING CORPN",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE655A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "STEELCAS",
  "company_name": "STEELCAST LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE124E01038",
  "face_value": 100.0
 },
 {
  "symbol": "STEELCITY",
  "company_name": "STEEL CITY SECURITIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE395H01011",
  "face_value": 1000.0
 },
 {
  "symbol": "STEELCOGUJ",
  "company_name": "STEELCO GUJARAT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE365201016",
  "face_value": 1000.0
 },
 {
  "symbol": "STEELXIND",
  "company_name": "STEEL EXCHANGE INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE503B01021",
  "face_value": 100.0
 },
 {
  "symbol": "STEL",
  "company_name": "STEL HOLDINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE577L01016",
  "face_value": 1000.0
 },
 {
  "symbol": "STERLINBIO",
  "company_name": "STERLING BIOTECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE324C01038",
  "face_value": 100.0
 },
 {
  "symbol": "STERLINHOL",
  "company_name": "STERLING HOLIDAY RESORTS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE359901019",
  "face_value": 1000.0
 },
 {
  "symbol": "STERTOOLS",
  "company_name": "STERLING TOOLS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE334A01023",
  "face_value": 200.0
 },
 {
  "symbol": "STILBENCHM",
  "company_name": "STILBENE CHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE361301018",
  "face_value": 1000.0
 },
 {
  "symbol": "STINDIA",
  "company_name": "STI INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE090C01019",
  "face_value": 1000.0
 },
 {
  "symbol": "STLNETWORK",
  "company_name": "STL NETWORKS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1VXE01018",
  "face_value": 200.0
 },
 {
  "symbol": "STLTECH",
  "company_name": "STERLITE TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE089C01029",
  "face_value": 200.0
 },
 {
  "symbol": "STOVEKRAFT",
  "company_name": "STOVE KRAFT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00IN01015",
  "face_value": 1000.0
 },
 {
  "symbol": "STRAUSIND",
  "company_name": "STRAUS INDS & EXPORTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY9465",
  "face_value": 1000.0
 },
 {
  "symbol": "STUDDS",
  "company_name": "STUDDS ACCESSORIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00Q601028",
  "face_value": 500.0
 },
 {
  "symbol": "STYL",
  "company_name": "SESHAASAI TECHNOLOGIES L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE04VU01023",
  "face_value": 1000.0
 },
 {
  "symbol": "STYLAMIND",
  "company_name": "STYLAM INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE239C01020",
  "face_value": 500.0
 },
 {
  "symbol": "STYLEBAAZA",
  "company_name": "BAAZAR STYLE RETAIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01FR01028",
  "face_value": 500.0
 },
 {
  "symbol": "STYRENIX",
  "company_name": "STYRENIX PERFORMANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE189B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SUASHDIMON",
  "company_name": "SUASHISH DIAMONDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE658A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SUBCAPCITY",
  "company_name": "INTERNATIONAL CONST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE845C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SUBEX",
  "company_name": "SUBEX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE754A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "SUBEXLTD",
  "company_name": "SUBEX LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE754A01055",
  "face_value": 500.0
 },
 {
  "symbol": "SUBROS",
  "company_name": "SUBROS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE287B01021",
  "face_value": 200.0
 },
 {
  "symbol": "SUDARCOLOR",
  "company_name": "SUDARSHAN COLORNT IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE492A01029",
  "face_value": 1000.0
 },
 {
  "symbol": "SUDARSCHEM",
  "company_name": "SUDARSHAN CHEMICAL INDS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE659A01023",
  "face_value": 200.0
 },
 {
  "symbol": "SUDEEPPHRM",
  "company_name": "SUDEEP PHARMA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0QPI01025",
  "face_value": 100.0
 },
 {
  "symbol": "SUDITIND",
  "company_name": "SUDITI INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE583901017",
  "face_value": 1000.0
 },
 {
  "symbol": "SUJANAUNI",
  "company_name": "SUJANA UNI. INDS. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE216G01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SUKHJITS",
  "company_name": "SUKHJIT STARCH & CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE450E01029",
  "face_value": 500.0
 },
 {
  "symbol": "SULA",
  "company_name": "SULA VINEYARDS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE142Q01026",
  "face_value": 200.0
 },
 {
  "symbol": "SULZER",
  "company_name": "SULZER INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE297C01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SUMANMOTEL",
  "company_name": "SUMAN MOTELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE723A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SUMEETINDS",
  "company_name": "SUMEET IND LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE235C01036",
  "face_value": 200.0
 },
 {
  "symbol": "SUMEETMACH",
  "company_name": "SUMEET MACHINES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE466301012",
  "face_value": 1000.0
 },
 {
  "symbol": "SUMICHEM",
  "company_name": "SUMITOMO CHEM INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE258G01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SUMIT",
  "company_name": "SUMIT WOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE748Z01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SUMMITSEC",
  "company_name": "SUMMIT SECURITIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE519C01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SUNCLAY",
  "company_name": "SUNDARAM CLAYTON LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0Q3R01026",
  "face_value": 500.0
 },
 {
  "symbol": "SUNDARAM",
  "company_name": "SUNDARAM MULTI PAP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE108E01023",
  "face_value": 100.0
 },
 {
  "symbol": "SUNDARMFIN",
  "company_name": "SUNDARAM FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE660A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SUNDRMBRAK",
  "company_name": "SUNDARAM BRAK LININGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE073D01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SUNDRMFAST",
  "company_name": "SUNDRAM FASTENERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE387A01021",
  "face_value": 100.0
 },
 {
  "symbol": "SUNDROP",
  "company_name": "SUNDROP BRANDS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE209A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "SUNFLAG",
  "company_name": "SUNFLAG IRON AND STEEL CO",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE947A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "SUNILHITEC",
  "company_name": "SUNIL HITECH ENGR. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE305H01028",
  "face_value": 100.0
 },
 {
  "symbol": "SUNPHARMA",
  "company_name": "SUN PHARMACEUTICAL IND L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE044A01036",
  "face_value": 100.0
 },
 {
  "symbol": "SUNRISESEC",
  "company_name": "SUNRISE SECURITIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE358801012",
  "face_value": 1000.0
 },
 {
  "symbol": "SUNSTRCHEM",
  "company_name": "SUNSTAR CHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE387401016",
  "face_value": 1000.0
 },
 {
  "symbol": "SUNTECK",
  "company_name": "SUNTECK REALTY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE805D01034",
  "face_value": 100.0
 },
 {
  "symbol": "SUNTV",
  "company_name": "SUN TV NETWORK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE424H01027",
  "face_value": 500.0
 },
 {
  "symbol": "SUPERHOUSE",
  "company_name": "SUPERHOUSE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE712B01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SUPERSALES",
  "company_name": "SUPER SALES AGENCIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE359401010",
  "face_value": 1000.0
 },
 {
  "symbol": "SUPERSPIN",
  "company_name": "SUPER SPINNING MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE662A01027",
  "face_value": 100.0
 },
 {
  "symbol": "SUPPETRO",
  "company_name": "SUPREME PETROCHEMICALS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE663A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SUPRAJIT",
  "company_name": "SUPRAJIT ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE399C01030",
  "face_value": 100.0
 },
 {
  "symbol": "SUPREME",
  "company_name": "SUPREME HOLDIN N HOSP I L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE822E01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SUPREMEENG",
  "company_name": "SUPREME ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE319Z01021",
  "face_value": 100.0
 },
 {
  "symbol": "SUPREMEIND",
  "company_name": "SUPREME INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE195A01028",
  "face_value": 200.0
 },
 {
  "symbol": "SUPREMEINF",
  "company_name": "SUPREME INFRA. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE550H01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SUPRIYA",
  "company_name": "SUPRIYA LIFESCIENCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE07RO01027",
  "face_value": 200.0
 },
 {
  "symbol": "SURAJEST",
  "company_name": "SURAJ ESTATE DEVELOPERS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE843S01025",
  "face_value": 500.0
 },
 {
  "symbol": "SURAJLTD",
  "company_name": "SURAJ LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE713C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SURAKSHA",
  "company_name": "SURAKSHA DIAGNOSTIC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE877V01027",
  "face_value": 200.0
 },
 {
  "symbol": "SURANACORP",
  "company_name": "SURANA CORPORATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE357D01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SURANASOL",
  "company_name": "SURANA SOLAR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE272L01022",
  "face_value": 500.0
 },
 {
  "symbol": "SURANAT&P",
  "company_name": "SURANA TELECOM AND POW LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE130B01031",
  "face_value": 100.0
 },
 {
  "symbol": "SURYAGROIL",
  "company_name": "SURYA AGROILS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE780B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SURYALA",
  "company_name": "SURYALATA SPINNING MILL L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE132C01027",
  "face_value": 1000.0
 },
 {
  "symbol": "SURYALAXMI",
  "company_name": "SURYALAKSHMI COT MIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE713B01026",
  "face_value": 1000.0
 },
 {
  "symbol": "SURYAROSNI",
  "company_name": "SURYA ROSHNI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE335A01020",
  "face_value": 500.0
 },
 {
  "symbol": "SURYODAY",
  "company_name": "SURYODAY SMALL FIN BK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE428Q01011",
  "face_value": 1000.0
 },
 {
  "symbol": "SURYVANSPG",
  "company_name": "SURYAVANSHI SPG MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE350301011",
  "face_value": 1000.0
 },
 {
  "symbol": "SUTLEJTEX",
  "company_name": "SUTLEJ TEXT & INDUS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE645H01027",
  "face_value": 100.0
 },
 {
  "symbol": "SUULD",
  "company_name": "SUUMAYA INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE591Q01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SUVARNAQUA",
  "company_name": "SUVARNA AQUA FARMS AND EX",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE350901018",
  "face_value": 1000.0
 },
 {
  "symbol": "SUVEN",
  "company_name": "SUVEN LIFE SCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE495B01038",
  "face_value": 100.0
 },
 {
  "symbol": "SUVEN-RE",
  "company_name": "SUVEN LIFE SCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE495B20012",
  "face_value": 100.0
 },
 {
  "symbol": "SUVIDHAA",
  "company_name": "SUVIDHAA INFOSERVE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE018401013",
  "face_value": 100.0
 },
 {
  "symbol": "SUYOG",
  "company_name": "SUYOG TELEMATICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE442P01014",
  "face_value": 1000.0
 },
 {
  "symbol": "SUZLON",
  "company_name": "SUZLON ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE040H01021",
  "face_value": 200.0
 },
 {
  "symbol": "SUZLON-RE",
  "company_name": "SUZLON ENERGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE040H20013",
  "face_value": 200.0
 },
 {
  "symbol": "SUZLONFIBR",
  "company_name": "SUZLON FIBRES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE351201012",
  "face_value": 1000.0
 },
 {
  "symbol": "SVADMILLS",
  "company_name": "SVADESHI MILLS CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE466401010",
  "face_value": 1000.0
 },
 {
  "symbol": "SVLL",
  "company_name": "SHREE VASU LOGISTICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00CE01017",
  "face_value": 1000.0
 },
 {
  "symbol": "SVPGLOB",
  "company_name": "SVP GLOBAL TEXTILES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE308E01029",
  "face_value": 100.0
 },
 {
  "symbol": "SWANCORP",
  "company_name": "SWAN CORP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE665A01038",
  "face_value": 100.0
 },
 {
  "symbol": "SWANDEF",
  "company_name": "SWAN DEFENCE N HEVY IND L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE542F01020",
  "face_value": 1000.0
 },
 {
  "symbol": "SWARAJENG",
  "company_name": "SWARAJ ENGINES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE277A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "SWELECTES",
  "company_name": "SWELECT ENERGY SYS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE409B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "SWIGGY",
  "company_name": "SWIGGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00H001014",
  "face_value": 100.0
 },
 {
  "symbol": "SWIL",
  "company_name": "SWIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE666A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "SWSOLAR",
  "company_name": "STRLNG & WIL REN ENE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00M201021",
  "face_value": 100.0
 },
 {
  "symbol": "SYMPHONY",
  "company_name": "SYMPHONY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE225D01027",
  "face_value": 200.0
 },
 {
  "symbol": "SYNCOM",
  "company_name": "SYNCOM HEALTHCARE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE602K01014",
  "face_value": 1000.0
 },
 {
  "symbol": "SYNCOMF",
  "company_name": "SYNCOM FORMU (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE312C01025",
  "face_value": 100.0
 },
 {
  "symbol": "SYNGENE",
  "company_name": "SYNGENE INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE398R01022",
  "face_value": 1000.0
 },
 {
  "symbol": "SYRMA",
  "company_name": "SYRMA SGS TECHNOLOGY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0DYJ01015",
  "face_value": 1000.0
 },
 {
  "symbol": "SYSTMTXC",
  "company_name": "SYSTEMATIX CORP SERVICE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE356B01024",
  "face_value": 100.0
 },
 {
  "symbol": "TAALTECH",
  "company_name": "TAAL TECH LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE524T01011",
  "face_value": 1000.0
 },
 {
  "symbol": "TAGOLDINAV",
  "company_name": "TATAAML-TAGOLDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000207",
  "face_value": 100.0
 },
 {
  "symbol": "TAINWALCHM",
  "company_name": "TAINWALA CHEMICAL AND PLA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE123C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "TAJGVK",
  "company_name": "TAJ GVK HOTELS & RESORTS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE586B01026",
  "face_value": 200.0
 },
 {
  "symbol": "TAKE",
  "company_name": "TAKE SOLUTIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE142I01023",
  "face_value": 100.0
 },
 {
  "symbol": "TALBROAUTO",
  "company_name": "TALBROS AUTO. COMP. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE187D01029",
  "face_value": 200.0
 },
 {
  "symbol": "TALWALKARS",
  "company_name": "TALWALKAR FITNESS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE502K01016",
  "face_value": 1000.0
 },
 {
  "symbol": "TALWGYM",
  "company_name": "TALWALKARS HEALTHCLUB LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE627Z01019",
  "face_value": 1000.0
 },
 {
  "symbol": "TAMBOLIIN",
  "company_name": "TAMBOLI INDUSTRIES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE864J01012",
  "face_value": 1000.0
 },
 {
  "symbol": "TANEJAERO",
  "company_name": "TANEJA AEROSPACE AND AVIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE343301011",
  "face_value": 1000.0
 },
 {
  "symbol": "TANFAC",
  "company_name": "TANFAC INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE639B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "TANFACIND",
  "company_name": "TANFAC IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE639B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "TANLA",
  "company_name": "TANLA PLATFORMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE483C01032",
  "face_value": 100.0
 },
 {
  "symbol": "TANTIACONS",
  "company_name": "TANTIA CONST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE388G01018",
  "face_value": 1000.0
 },
 {
  "symbol": "TARACHAND",
  "company_name": "TARA CHAND INFRA SOLN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE555Z01020",
  "face_value": 200.0
 },
 {
  "symbol": "TARAJEWELS",
  "company_name": "TARA JEWELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE799L01016",
  "face_value": 1000.0
 },
 {
  "symbol": "TARAPUR",
  "company_name": "TARAPUR TRANSFORMERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE747K01017",
  "face_value": 1000.0
 },
 {
  "symbol": "TARC",
  "company_name": "TARC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0EK901012",
  "face_value": 200.0
 },
 {
  "symbol": "TARIL",
  "company_name": "TRANS & RECTI. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE763I01026",
  "face_value": 100.0
 },
 {
  "symbol": "TARMAT",
  "company_name": "TARMAT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE924H01018",
  "face_value": 1000.0
 },
 {
  "symbol": "TARSONS",
  "company_name": "TARSONS PRODUCTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE144Z01023",
  "face_value": 200.0
 },
 {
  "symbol": "TASILVINAV",
  "company_name": "TATAAML-TASILVINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000208",
  "face_value": 100.0
 },
 {
  "symbol": "TASTYBITE",
  "company_name": "TASTY BITE EATABLES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE488B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "TATACAP",
  "company_name": "TATA CAPITAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE976I01016",
  "face_value": 1000.0
 },
 {
  "symbol": "TATACHEM",
  "company_name": "TATA CHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE092A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "TATACOFFEE",
  "company_name": "TATA COFFEE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE493A01027",
  "face_value": 100.0
 },
 {
  "symbol": "TATACOMM",
  "company_name": "TATA COMMUNICATIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE151A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "TATACON-RE",
  "company_name": "TATA CONSUMER PRODUCT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE192A20017",
  "face_value": 100.0
 },
 {
  "symbol": "TATACONSUM",
  "company_name": "TATA CONSUMER PRODUCT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE192A01025",
  "face_value": 100.0
 },
 {
  "symbol": "TATADVMATL",
  "company_name": "TATA ADVANCED MATERIALS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE344101014",
  "face_value": 1000.0
 },
 {
  "symbol": "TATAELXSI",
  "company_name": "TATA ELXSI LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE670A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "TATAGOLD",
  "company_name": "TATAAML-TATAGOLD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF277KA1976",
  "face_value": 100.0
 },
 {
  "symbol": "TATAINVEST",
  "company_name": "TATA INVESTMENT CORP LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE672A01026",
  "face_value": 100.0
 },
 {
  "symbol": "TATAMETALI",
  "company_name": "TATA METALIKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE056C01010",
  "face_value": 1000.0
 },
 {
  "symbol": "TATAMTRDVR",
  "company_name": "TATA MOTORS DVR  A  ORD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "IN9155A01020",
  "face_value": 200.0
 },
 {
  "symbol": "TATAPOWER",
  "company_name": "TATA POWER CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE245A01021",
  "face_value": 100.0
 },
 {
  "symbol": "TATASTEEL",
  "company_name": "TATA STEEL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE081A01020",
  "face_value": 100.0
 },
 {
  "symbol": "TATASTLBSL",
  "company_name": "TATA STEEL BSL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE824B01021",
  "face_value": 200.0
 },
 {
  "symbol": "TATASTLLP",
  "company_name": "TATA STEEL LONG PRO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE674A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "TATATECH",
  "company_name": "TATA TECHNOLOGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE142M01025",
  "face_value": 200.0
 },
 {
  "symbol": "TATAUNISYS",
  "company_name": "TATA INFOTECH LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE194A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "TATAYODOGA",
  "company_name": "TATA YODOGAWA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE895C01011",
  "face_value": 1000.0
 },
 {
  "symbol": "TATIASKYLN",
  "company_name": "TATIA SKYLINES AND HEALTH",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE345601012",
  "face_value": 1000.0
 },
 {
  "symbol": "TATSILV",
  "company_name": "TATAAML-TATSILV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF277KA1984",
  "face_value": 100.0
 },
 {
  "symbol": "TATVA",
  "company_name": "TATVA CHIN PHARM CHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0GK401011",
  "face_value": 1000.0
 },
 {
  "symbol": "TBOTEK",
  "company_name": "TBO TEK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE673O01025",
  "face_value": 100.0
 },
 {
  "symbol": "TBZ",
  "company_name": "TRIB BHIMJI ZAVERI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE760L01018",
  "face_value": 1000.0
 },
 {
  "symbol": "TCC",
  "company_name": "TCC CONCEPT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE887D01016",
  "face_value": 1000.0
 },
 {
  "symbol": "TCI",
  "company_name": "TRANSPORT CORPN OF INDIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE688A01022",
  "face_value": 200.0
 },
 {
  "symbol": "TCIDEVELOP",
  "company_name": "TCI DEVELOPERS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE662L01016",
  "face_value": 1000.0
 },
 {
  "symbol": "TCIEXP",
  "company_name": "TCI EXPRESS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE586V01016",
  "face_value": 200.0
 },
 {
  "symbol": "TCIFINANCE",
  "company_name": "TCI FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE911B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "TCNSBRANDS",
  "company_name": "TCNS CLOTHING CO. LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE778U01029",
  "face_value": 200.0
 },
 {
  "symbol": "TCPLPACK",
  "company_name": "TCPL PACKAGING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE822C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "TCS",
  "company_name": "TATA CONSULTANCY SERV LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE467B01029",
  "face_value": 100.0
 },
 {
  "symbol": "TDPOWERSYS",
  "company_name": "TD POWER SYSTEMS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE419M01027",
  "face_value": 200.0
 },
 {
  "symbol": "TEAMGTY",
  "company_name": "TEAM INDIA GUARANTY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE289C01025",
  "face_value": 1000.0
 },
 {
  "symbol": "TEAMLEASE",
  "company_name": "TEAMLEASE SERVICES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE985S01024",
  "face_value": 1000.0
 },
 {
  "symbol": "TECH",
  "company_name": "BIRLASLAMC - TECH",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF209KB11D8",
  "face_value": 100.0
 },
 {
  "symbol": "TECHIN",
  "company_name": "TECHINDIA NIRMAN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE778A01021",
  "face_value": 1000.0
 },
 {
  "symbol": "TECHINAV",
  "company_name": "TECH INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000050",
  "face_value": 100.0
 },
 {
  "symbol": "TECHM",
  "company_name": "TECH MAHINDRA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE669C01036",
  "face_value": 500.0
 },
 {
  "symbol": "TECHNOE",
  "company_name": "TECHNO ELEC & ENG CO. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE285K01026",
  "face_value": 200.0
 },
 {
  "symbol": "TECHNOFAB",
  "company_name": "TECHNOFAB ENG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE509K01011",
  "face_value": 1000.0
 },
 {
  "symbol": "TECHNVISN",
  "company_name": "TECHNVISION VENTURES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE314H01012",
  "face_value": 1000.0
 },
 {
  "symbol": "TECILCHEM",
  "company_name": "TECIL CHEMICALS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE014B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "TEGA",
  "company_name": "TEGA INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE011K01018",
  "face_value": 1000.0
 },
 {
  "symbol": "TEJASNET",
  "company_name": "TEJAS NETWORKS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE010J01012",
  "face_value": 1000.0
 },
 {
  "symbol": "TELEPHNCAB",
  "company_name": "TELEPHONE CABLES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE745C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "TEMBO",
  "company_name": "TEMBO GLOBAL IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE869Y01010",
  "face_value": 1000.0
 },
 {
  "symbol": "TEMBO-RE",
  "company_name": "TEMBO GLOBAL IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE869Y20010",
  "face_value": 1000.0
 },
 {
  "symbol": "TENNIND",
  "company_name": "TENNECO CLEAN AIR INDIA L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE19RI01016",
  "face_value": 1000.0
 },
 {
  "symbol": "TERASOFT",
  "company_name": "TERA SOFTWARE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE482B01010",
  "face_value": 1000.0
 },
 {
  "symbol": "TEXINFRA",
  "company_name": "TEXMACO INFRA & HOLDG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE435C01024",
  "face_value": 100.0
 },
 {
  "symbol": "TEXMOPIPES",
  "company_name": "TEXMO PIPE & PRODUCTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE141K01013",
  "face_value": 1000.0
 },
 {
  "symbol": "TEXRAIL",
  "company_name": "TEXMACO RAIL & ENG. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE621L01012",
  "face_value": 100.0
 },
 {
  "symbol": "TEXTOOL",
  "company_name": "TEXTOOL CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE677A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "TFCILTD",
  "company_name": "TOURISM FINANCE CORP. OF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE305A01023",
  "face_value": 200.0
 },
 {
  "symbol": "TFL",
  "company_name": "TRANSWARRANTY FIN. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE804H01012",
  "face_value": 1000.0
 },
 {
  "symbol": "TFL-RE",
  "company_name": "TRANSWARRANTY FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE804H20012",
  "face_value": 1000.0
 },
 {
  "symbol": "TGBHOTELS",
  "company_name": "TGB BANQUETS&HOTELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE797H01018",
  "face_value": 1000.0
 },
 {
  "symbol": "THACKER",
  "company_name": "THACKER & CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE077P01034",
  "face_value": 100.0
 },
 {
  "symbol": "THAKDEV",
  "company_name": "THAKKERS DEVELOPERS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE403F01017",
  "face_value": 1000.0
 },
 {
  "symbol": "THANG-RE",
  "company_name": "THANGAMAYIL JEWELLERY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE085J20014",
  "face_value": 1000.0
 },
 {
  "symbol": "THANGAMAYL",
  "company_name": "THANGAMAYIL JEWELLERY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE085J01014",
  "face_value": 1000.0
 },
 {
  "symbol": "THAPARAGRO",
  "company_name": "THAPAR AGRO MILLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE341601016",
  "face_value": 1000.0
 },
 {
  "symbol": "THAPARMILK",
  "company_name": "THAPAR MILK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE342101016",
  "face_value": 1000.0
 },
 {
  "symbol": "THAPRISPAT",
  "company_name": "THAPAR ISPAT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE342001018",
  "face_value": 1000.0
 },
 {
  "symbol": "THEINVEST",
  "company_name": "THE INVEST TRUST OF IND L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE924D01017",
  "face_value": 1000.0
 },
 {
  "symbol": "THEJO",
  "company_name": "THEJO ENGINEERING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE121N01019",
  "face_value": 1000.0
 },
 {
  "symbol": "THELEELA",
  "company_name": "LEELA PALACES HOTEL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0AQ201015",
  "face_value": 1000.0
 },
 {
  "symbol": "THEMISMED",
  "company_name": "THEMIS MEDICARE LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE083B01024",
  "face_value": 100.0
 },
 {
  "symbol": "THERMAX",
  "company_name": "THERMAX LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE152A01029",
  "face_value": 200.0
 },
 {
  "symbol": "THIRUSUGAR",
  "company_name": "THIRU AROORAN SUGARS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE409A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "THOMASCOOK",
  "company_name": "THOMAS COOK (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE332A01027",
  "face_value": 100.0
 },
 {
  "symbol": "THOMASCOTT",
  "company_name": "THOMAS SCOTT (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE480M01011",
  "face_value": 1000.0
 },
 {
  "symbol": "THYROCARE",
  "company_name": "THYROCARE TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE594H01019",
  "face_value": 1000.0
 },
 {
  "symbol": "TI",
  "company_name": "TILAKNAGAR INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE133E01013",
  "face_value": 1000.0
 },
 {
  "symbol": "TICL",
  "company_name": "TWAMEV CONS AND INFRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE388G01026",
  "face_value": 100.0
 },
 {
  "symbol": "TIGERLOGS",
  "company_name": "TIGER LOGISTICS (INDIA) L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE906O01029",
  "face_value": 100.0
 },
 {
  "symbol": "TIIL",
  "company_name": "TECHNOCRAFT IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE545H01011",
  "face_value": 1000.0
 },
 {
  "symbol": "TIINDIA",
  "company_name": "TUBE INVEST OF INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE974X01010",
  "face_value": 100.0
 },
 {
  "symbol": "TIJARIA",
  "company_name": "TIJARIA POLYPIPES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE440L01017",
  "face_value": 1000.0
 },
 {
  "symbol": "TIL",
  "company_name": "TIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE806C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "TIL-RE",
  "company_name": "TIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE806C20018",
  "face_value": 1000.0
 },
 {
  "symbol": "TIL-RE1",
  "company_name": "TIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE806C20026",
  "face_value": 1000.0
 },
 {
  "symbol": "TIMETECHNO",
  "company_name": "TIME TECHNOPLAST LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE508G01029",
  "face_value": 100.0
 },
 {
  "symbol": "TIMEX",
  "company_name": "TIMEX GROUP INDIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE064A01026",
  "face_value": 100.0
 },
 {
  "symbol": "TIMEXWATCH",
  "company_name": "TIMEX WATCHES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE064A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "TIMKEN",
  "company_name": "TIMKEN INDIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE325A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "TINNARUBR",
  "company_name": "TINNA RUBBER AND INFR LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE015C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "TINPLATE",
  "company_name": "THE TINPLATE CO. (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE422C01014",
  "face_value": 1000.0
 },
 {
  "symbol": "TIPSFILMS",
  "company_name": "TIPS FILMS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0LQS01015",
  "face_value": 1000.0
 },
 {
  "symbol": "TIPSMUSIC",
  "company_name": "TIPS MUSIC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE716B01029",
  "face_value": 100.0
 },
 {
  "symbol": "TIRUMALCHM",
  "company_name": "THIRUMALAI CHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE338A01024",
  "face_value": 100.0
 },
 {
  "symbol": "TIRUPATIFL",
  "company_name": "TIRUPATI FORGE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE319Y01024",
  "face_value": 200.0
 },
 {
  "symbol": "TITAGARH",
  "company_name": "TITAGARH RAIL SYSTEMS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE615H01020",
  "face_value": 200.0
 },
 {
  "symbol": "TITAGRSTEL",
  "company_name": "TITAGARH INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE333501018",
  "face_value": 1000.0
 },
 {
  "symbol": "TITAN",
  "company_name": "TITAN COMPANY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE280A01028",
  "face_value": 100.0
 },
 {
  "symbol": "TMB",
  "company_name": "TAMILNAD MERCA BANK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE668A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "TMCV",
  "company_name": "TATA MOTORS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE1TAE01010",
  "face_value": 200.0
 },
 {
  "symbol": "TMPV",
  "company_name": "TATA MOTORS PASS VEH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE155A01022",
  "face_value": 200.0
 },
 {
  "symbol": "TMTINDIA",
  "company_name": "T M T (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY9320",
  "face_value": 1000.0
 },
 {
  "symbol": "TNIDETF",
  "company_name": "TATAAML - TNIDETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF277KA1364",
  "face_value": 1000.0
 },
 {
  "symbol": "TNIDETINAV",
  "company_name": "TNIDETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000143",
  "face_value": 100.0
 },
 {
  "symbol": "TNPETRO",
  "company_name": "TAMILNADU PETROPRODUCTS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE148A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "TNPL",
  "company_name": "TAMILNADU NEWSPRT & PAPER",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE107A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "TNTELE",
  "company_name": "TAMILNADU TELECOMMUNICATI",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE141D01018",
  "face_value": 1000.0
 },
 {
  "symbol": "TOKYOPLAST",
  "company_name": "TOKYO PLAST INTL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE932C01012",
  "face_value": 1000.0
 },
 {
  "symbol": "TOLANIBULK",
  "company_name": "TOLANI BULK CARRIERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE051C01011",
  "face_value": 1000.0
 },
 {
  "symbol": "TOLINS",
  "company_name": "TOLINS TYRES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0RWQ01014",
  "face_value": 500.0
 },
 {
  "symbol": "TOP100CASE",
  "company_name": "ZERODHAAMC - TOP100CASE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF0R8F01067",
  "face_value": 1000.0
 },
 {
  "symbol": "TOP100INAV",
  "company_name": "ZERODHAAMC - TOP100INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000226",
  "face_value": 1000.0
 },
 {
  "symbol": "TOP10ADD",
  "company_name": "DSPAMC - TOP10ADD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF740KA1UR9",
  "face_value": 1000.0
 },
 {
  "symbol": "TOP10AINAV",
  "company_name": "DSPAMC - TOP10AINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000240",
  "face_value": 1000.0
 },
 {
  "symbol": "TOP15IETF",
  "company_name": "ICICIPRAMC - TOP15IETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109K1A344",
  "face_value": 1000.0
 },
 {
  "symbol": "TOP20",
  "company_name": "MIRAEAMC - TOP20",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01PZ5",
  "face_value": 1000.0
 },
 {
  "symbol": "TOP20INAV",
  "company_name": "MIRAEAMC - TOP20INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000327",
  "face_value": 1000.0
 },
 {
  "symbol": "TOPETFINAV",
  "company_name": "ICICIPRAMC - TOPETFINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000285",
  "face_value": 1000.0
 },
 {
  "symbol": "TORNTPHARM",
  "company_name": "TORRENT PHARMACEUTICALS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE685A01028",
  "face_value": 500.0
 },
 {
  "symbol": "TORNTPOWER",
  "company_name": "TORRENT POWER LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE813H01021",
  "face_value": 1000.0
 },
 {
  "symbol": "TORRENGUJ",
  "company_name": "TORRENT GUJARAT BIOTECH L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE859B01019",
  "face_value": 1000.0
 },
 {
  "symbol": "TORRENTCAB",
  "company_name": "TORRENT CABLES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE334701013",
  "face_value": 1000.0
 },
 {
  "symbol": "TOTAL",
  "company_name": "TOTAL TRANSPORT SYS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE336X01012",
  "face_value": 1000.0
 },
 {
  "symbol": "TOUCHWOOD",
  "company_name": "TOUCHWOOD ENTERTAIN LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE486Y01013",
  "face_value": 1000.0
 },
 {
  "symbol": "TPHQ",
  "company_name": "TEAMO PRODUCTIONS HQ LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE065J01024",
  "face_value": 100.0
 },
 {
  "symbol": "TPINDIA",
  "company_name": "T P I INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE335601014",
  "face_value": 1000.0
 },
 {
  "symbol": "TPLPLASTEH",
  "company_name": "TPL PLASTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE413G01022",
  "face_value": 200.0
 },
 {
  "symbol": "TRACXN",
  "company_name": "TRACXN TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0HMF01019",
  "face_value": 100.0
 },
 {
  "symbol": "TRAIL-RE",
  "company_name": "TEXMACO RAIL & ENG. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE621L20012",
  "face_value": 100.0
 },
 {
  "symbol": "TRANSCHEM",
  "company_name": "TRANSCHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE019B01010",
  "face_value": 1000.0
 },
 {
  "symbol": "TRANSFREIT",
  "company_name": "TRANS-FREIGHT CONTAINERS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE467201013",
  "face_value": 1000.0
 },
 {
  "symbol": "TRANSPEK",
  "company_name": "TRANSPEK INDUSTRY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE687A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "TRANSRAILL",
  "company_name": "TRANSRAIL LIGHTING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE454P01035",
  "face_value": 200.0
 },
 {
  "symbol": "TRANSWORLD",
  "company_name": "TRANSWORLD SHIP LINES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE757B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "TRAVELFOOD",
  "company_name": "TRAVEL FOOD SERVICES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE103V01028",
  "face_value": 100.0
 },
 {
  "symbol": "TREEHOUSE",
  "company_name": "TREE HOUSE EDU LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE040M01013",
  "face_value": 1000.0
 },
 {
  "symbol": "TREJHARA",
  "company_name": "TREJHARA SOLUTIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00CA01015",
  "face_value": 1000.0
 },
 {
  "symbol": "TREL",
  "company_name": "TRANSINDIA REAL ESTATE L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0O3901029",
  "face_value": 200.0
 },
 {
  "symbol": "TRENT",
  "company_name": "TRENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE849A01020",
  "face_value": 100.0
 },
 {
  "symbol": "TRF",
  "company_name": "TRF LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE391D01019",
  "face_value": 1000.0
 },
 {
  "symbol": "TRIDENT",
  "company_name": "TRIDENT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE064C01022",
  "face_value": 100.0
 },
 {
  "symbol": "TRIGYN",
  "company_name": "TRIGYN TECHNOLOGIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE948A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "TRITURBINE",
  "company_name": "TRIVENI TURBINE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE152M01016",
  "face_value": 100.0
 },
 {
  "symbol": "TRIVENI",
  "company_name": "TRIVENI ENGG. & INDS. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE256C01024",
  "face_value": 100.0
 },
 {
  "symbol": "TRIVENSHET",
  "company_name": "TRIVENI GLASS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE332801013",
  "face_value": 1000.0
 },
 {
  "symbol": "TRU",
  "company_name": "TRUCAP FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE615R01029",
  "face_value": 200.0
 },
 {
  "symbol": "TRUALT",
  "company_name": "TRUALT BIOENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0MWH01014",
  "face_value": 1000.0
 },
 {
  "symbol": "TSFINV",
  "company_name": "TSF INVESTMENTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE202Z01029",
  "face_value": 500.0
 },
 {
  "symbol": "TTGIND",
  "company_name": "T T G INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE333001019",
  "face_value": 1000.0
 },
 {
  "symbol": "TTKHLTCARE",
  "company_name": "TTK HEALTHCARE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE910C01018",
  "face_value": 1000.0
 },
 {
  "symbol": "TTKPRESTIG",
  "company_name": "TTK PRESTIGE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE690A01028",
  "face_value": 100.0
 },
 {
  "symbol": "TTL",
  "company_name": "T T LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE592B01024",
  "face_value": 100.0
 },
 {
  "symbol": "TTL-RE",
  "company_name": "T T LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE592B20016",
  "face_value": 100.0
 },
 {
  "symbol": "TTML",
  "company_name": "TATA TELESERV(MAHARASTRA)",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE517B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "TULSI",
  "company_name": "TULSI EXTRUSION LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE474I01012",
  "face_value": 1000.0
 },
 {
  "symbol": "TULSYAN",
  "company_name": "TULSYAN NEC LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE463D01016",
  "face_value": 1000.0
 },
 {
  "symbol": "TUTICORALK",
  "company_name": "TUTICORIN ALKALI CHEMICAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE400A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "TV18BRDCST",
  "company_name": "TV18 BROADCAST LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE886H01027",
  "face_value": 200.0
 },
 {
  "symbol": "TVSELECT",
  "company_name": "TVS ELECTRONICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE236G01019",
  "face_value": 1000.0
 },
 {
  "symbol": "TVSHLTD",
  "company_name": "TVS HOLDINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE105A01035",
  "face_value": 500.0
 },
 {
  "symbol": "TVSMOTOR",
  "company_name": "TVS MOTOR COMPANY  LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE494B01023",
  "face_value": 100.0
 },
 {
  "symbol": "TVSSCS",
  "company_name": "TVS SUPPLY CHAIN SOL L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE395N01027",
  "face_value": 100.0
 },
 {
  "symbol": "TVSSRICHAK",
  "company_name": "TVS SRICHAKRA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE421C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "TVTODAY",
  "company_name": "TV TODAY NETWORK LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE038F01029",
  "face_value": 500.0
 },
 {
  "symbol": "TVVISION",
  "company_name": "TV VISION LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE871L01013",
  "face_value": 1000.0
 },
 {
  "symbol": "TWCGLDINAV",
  "company_name": "WEALTH - TWCGLDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000329",
  "face_value": 1000.0
 },
 {
  "symbol": "TWCGOLDETF",
  "company_name": "WEALTH - TWCGOLDETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF2F0001370",
  "face_value": 1000.0
 },
 {
  "symbol": "UBL",
  "company_name": "UNITED BREWERIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE686F01025",
  "face_value": 100.0
 },
 {
  "symbol": "UCAL",
  "company_name": "UCAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE139B01016",
  "face_value": 1000.0
 },
 {
  "symbol": "UCOBANK",
  "company_name": "UCO BANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE691A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "UDAICEMENT",
  "company_name": "UDAIPUR CEMENT WORKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE225C01029",
  "face_value": 400.0
 },
 {
  "symbol": "UDS",
  "company_name": "UPDATER SERVICES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE851I01011",
  "face_value": 1000.0
 },
 {
  "symbol": "UEL",
  "company_name": "UJAAS ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE899L01030",
  "face_value": 100.0
 },
 {
  "symbol": "UFBL",
  "company_name": "UNITED FOODBRANDS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE382M01027",
  "face_value": 500.0
 },
 {
  "symbol": "UFLEX",
  "company_name": "UFLEX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE516A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "UFO",
  "company_name": "UFO MOVIEZ INDIA LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE527H01019",
  "face_value": 1000.0
 },
 {
  "symbol": "UGARSUGAR",
  "company_name": "THE UGAR SUGAR WORKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE071E01023",
  "face_value": 100.0
 },
 {
  "symbol": "UGRO-RE",
  "company_name": "UGRO CAPITAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE583D20011",
  "face_value": 1000.0
 },
 {
  "symbol": "UGROCAP",
  "company_name": "UGRO CAPITAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE583D01011",
  "face_value": 1000.0
 },
 {
  "symbol": "UJAAS",
  "company_name": "UJAAS ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE899L01022",
  "face_value": 100.0
 },
 {
  "symbol": "UJJIVAN",
  "company_name": "UJJIVAN FIN. SERVC. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE334L01012",
  "face_value": 1000.0
 },
 {
  "symbol": "UJJIVANSFB",
  "company_name": "UJJIVAN SMALL FINANC BANK",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE551W01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ULTRACEMCO",
  "company_name": "ULTRATECH CEMENT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE481G01011",
  "face_value": 1000.0
 },
 {
  "symbol": "ULTRAMAR",
  "company_name": "ULTRAMARINE & PIGMENTS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE405A01021",
  "face_value": 200.0
 },
 {
  "symbol": "ULTRMARINE",
  "company_name": "ULTRAMARINE & PIGMENTS",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE405A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "UMAEXPORTS",
  "company_name": "UMA EXPORTS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0GIU01018",
  "face_value": 1000.0
 },
 {
  "symbol": "UMANGDAIRY",
  "company_name": "UMANG DAIRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE864B01027",
  "face_value": 500.0
 },
 {
  "symbol": "UMESLTD",
  "company_name": "USHA MARTIN EDU & SOL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE240C01028",
  "face_value": 100.0
 },
 {
  "symbol": "UMIYA-MRO",
  "company_name": "UMIYA BUILDCON LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE398B01018",
  "face_value": 500.0
 },
 {
  "symbol": "UNGOLDINAV",
  "company_name": "UNIONAMC - UNGOLDINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000256",
  "face_value": 100.0
 },
 {
  "symbol": "UNICHEMLAB",
  "company_name": "UNICHEM LABORATORIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE351A01035",
  "face_value": 200.0
 },
 {
  "symbol": "UNIDT",
  "company_name": "UNITED DRILLING TOOLS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE961D01019",
  "face_value": 1000.0
 },
 {
  "symbol": "UNIECOM",
  "company_name": "UNICOMMERCE ESOLUTIONS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE00U401027",
  "face_value": 100.0
 },
 {
  "symbol": "UNIENTER",
  "company_name": "UNIPHOS ENTERPRISES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE037A01022",
  "face_value": 200.0
 },
 {
  "symbol": "UNIFLEX",
  "company_name": "UNIFLEX CABLES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE146B01011",
  "face_value": 1000.0
 },
 {
  "symbol": "UNIINFO",
  "company_name": "UNIINFO TELECOM SERVI LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE481Z01011",
  "face_value": 1000.0
 },
 {
  "symbol": "UNIMECH",
  "company_name": "UNIMECH AEROSPACE N MFG L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0U3I01011",
  "face_value": 500.0
 },
 {
  "symbol": "UNIMIN",
  "company_name": "UNIMIN INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE467801010",
  "face_value": 1000.0
 },
 {
  "symbol": "UNIONBANK",
  "company_name": "UNION BANK OF INDIA",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE692A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "UNIONGOLD",
  "company_name": "UNIONAMC - UNIONGOLD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF582M01KS4",
  "face_value": 100.0
 },
 {
  "symbol": "UNIPARTS",
  "company_name": "UNIPARTS INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE244O01017",
  "face_value": 1000.0
 },
 {
  "symbol": "UNIPLAS",
  "company_name": "UNIPLAS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE324701015",
  "face_value": 1000.0
 },
 {
  "symbol": "UNIPLY",
  "company_name": "UNIPLY INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE950G01023",
  "face_value": 200.0
 },
 {
  "symbol": "UNITDSPR",
  "company_name": "UNITED SPIRITS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE854D01024",
  "face_value": 200.0
 },
 {
  "symbol": "UNITECH",
  "company_name": "UNITECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE694A01020",
  "face_value": 200.0
 },
 {
  "symbol": "UNITEDPOLY",
  "company_name": "UNITED POLYFAB GUJ. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE368U01029",
  "face_value": 100.0
 },
 {
  "symbol": "UNITEDTEA",
  "company_name": "UNITED NILGIRI TEA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE458F01011",
  "face_value": 1000.0
 },
 {
  "symbol": "UNITY",
  "company_name": "UNITY INFRAPROJECTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE466H01028",
  "face_value": 200.0
 },
 {
  "symbol": "UNIVAFOODS",
  "company_name": "UNIVA FOODS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE275F01019",
  "face_value": 1000.0
 },
 {
  "symbol": "UNIVASTU",
  "company_name": "UNIVASTU INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE562X01013",
  "face_value": 1000.0
 },
 {
  "symbol": "UNIVCABLES",
  "company_name": "UNIVERSAL CABLES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE279A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "UNIVPHOTO",
  "company_name": "UNIVERSUS IMAGINGS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE03V001013",
  "face_value": 1000.0
 },
 {
  "symbol": "UNOMINDA",
  "company_name": "UNO MINDA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE405E01023",
  "face_value": 200.0
 },
 {
  "symbol": "UPL",
  "company_name": "UPL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE628A01036",
  "face_value": 200.0
 },
 {
  "symbol": "UPL-RE",
  "company_name": "UPL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE628A20010",
  "face_value": 200.0
 },
 {
  "symbol": "URAVIDEF",
  "company_name": "URAVI DEFENCE &TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE568Z01015",
  "face_value": 1000.0
 },
 {
  "symbol": "URBANCO",
  "company_name": "URBAN COMPANY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0CAZ01013",
  "face_value": 100.0
 },
 {
  "symbol": "URJA",
  "company_name": "URJA GLOBAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE550C01020",
  "face_value": 100.0
 },
 {
  "symbol": "URJA-RE",
  "company_name": "URJA GLOBAL RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE550C20012",
  "face_value": 100.0
 },
 {
  "symbol": "USHAINDIA",
  "company_name": "USHA (INDIA) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE068A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "USHAISPAT",
  "company_name": "USHA ISPAT (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE150A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "USHAMART",
  "company_name": "USHA MARTIN LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE228A01035",
  "face_value": 100.0
 },
 {
  "symbol": "USHDEVINT",
  "company_name": "USHDEV INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY9448",
  "face_value": 1000.0
 },
 {
  "symbol": "USK",
  "company_name": "UDAYSHIVAKUMAR INFRA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0N0Y01013",
  "face_value": 1000.0
 },
 {
  "symbol": "UTIAMC",
  "company_name": "UTI ASSET MNGMT CO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE094J01016",
  "face_value": 1000.0
 },
 {
  "symbol": "UTIBANINAV",
  "company_name": "UTIBANKETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000145",
  "face_value": 100.0
 },
 {
  "symbol": "UTINEXINAV",
  "company_name": "UTINEXT50 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000146",
  "face_value": 100.0
 },
 {
  "symbol": "UTINIFINAV",
  "company_name": "UTINIFTETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000147",
  "face_value": 100.0
 },
 {
  "symbol": "UTISENINAV",
  "company_name": "UTISENSETF INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000148",
  "face_value": 100.0
 },
 {
  "symbol": "UTISXNINAV",
  "company_name": "UTISXN50 INAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000149",
  "face_value": 100.0
 },
 {
  "symbol": "UTIUS64-RI",
  "company_name": "UTI-US64(REINVESTMENT)",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF189A01020",
  "face_value": 1000.0
 },
 {
  "symbol": "UTKAR-RE",
  "company_name": "UTKARSH SMALL FIN BANK L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE735W20017",
  "face_value": 1000.0
 },
 {
  "symbol": "UTKARSHBNK",
  "company_name": "UTKARSH SMALL FIN BANK L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE735W01017",
  "face_value": 1000.0
 },
 {
  "symbol": "UTLSOLAR",
  "company_name": "FUJIYAMA POWER SYSTEMS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE12UR01024",
  "face_value": 100.0
 },
 {
  "symbol": "UTTAMSTL",
  "company_name": "UTTAM GALVA STEELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE699A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "UTTAMSUGAR",
  "company_name": "UTTAM SUGAR MILLS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE786F01031",
  "face_value": 1000.0
 },
 {
  "symbol": "UTTAMVALUE",
  "company_name": "UTTAM VALUE STEELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE292A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "UVSL",
  "company_name": "UTTAM VALUE STEELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE292A01023",
  "face_value": 100.0
 },
 {
  "symbol": "UYFINCORP",
  "company_name": "U. Y. FINCORP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE152C01025",
  "face_value": 500.0
 },
 {
  "symbol": "V1NSETEST",
  "company_name": "V1NSETEST",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMYSAN004",
  "face_value": 1000.0
 },
 {
  "symbol": "V2RETAIL",
  "company_name": "V2 RETAIL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE945H01021",
  "face_value": 100.0
 },
 {
  "symbol": "VADILALIND",
  "company_name": "VADILAL INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE694D01016",
  "face_value": 1000.0
 },
 {
  "symbol": "VAIBHAVGBL",
  "company_name": "VAIBHAV GLOBAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE884A01027",
  "face_value": 200.0
 },
 {
  "symbol": "VAISHALI",
  "company_name": "VAISHALI PHARMA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE972X01022",
  "face_value": 200.0
 },
 {
  "symbol": "VAKRANGEE",
  "company_name": "VAKRANGEE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE051B01021",
  "face_value": 100.0
 },
 {
  "symbol": "VAL30IETF",
  "company_name": "ICICIPRAMC - VAL30IETF",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF109KC16X5",
  "face_value": 1000.0
 },
 {
  "symbol": "VAL30IINAV",
  "company_name": "ICICIPRAMC - VAL30IINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000248",
  "face_value": 1000.0
 },
 {
  "symbol": "VALECHAENG",
  "company_name": "VALECHA ENG. LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE624C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "VALIANT-RE",
  "company_name": "VALIANT LABORATORIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0JWS20017",
  "face_value": 1000.0
 },
 {
  "symbol": "VALIANTLAB",
  "company_name": "VALIANT LABORATORIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0JWS01017",
  "face_value": 1000.0
 },
 {
  "symbol": "VALIANTORG",
  "company_name": "VALIANT ORGANICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE565V01010",
  "face_value": 1000.0
 },
 {
  "symbol": "VALUE",
  "company_name": "MIRAEAMC - VALUE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INF769K01QV2",
  "face_value": 1000.0
 },
 {
  "symbol": "VALUEINAV",
  "company_name": "MIRAEAMC - VALUEINAV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY0000345",
  "face_value": 1000.0
 },
 {
  "symbol": "VALUEIND",
  "company_name": "VALUE INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE352A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "VANADYCHEM",
  "company_name": "VANAVIL DYES AND CHEMICAL",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE204B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "VARDHACRLC",
  "company_name": "VARDHAMAN ACRYLICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE116G01013",
  "face_value": 1000.0
 },
 {
  "symbol": "VARDM-RE",
  "company_name": "VARDHMAN POLYTEX LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE835A20011",
  "face_value": 100.0
 },
 {
  "symbol": "VARDMNPOLY",
  "company_name": "VARDHMAN POLYTEX LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE835A01029",
  "face_value": 100.0
 },
 {
  "symbol": "VARROC",
  "company_name": "VARROC ENGINEERING LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE665L01035",
  "face_value": 100.0
 },
 {
  "symbol": "VARUNSEA",
  "company_name": "VARUN SEACON LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE319101015",
  "face_value": 1000.0
 },
 {
  "symbol": "VASCONEQ",
  "company_name": "VASCON ENGINEERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE893I01013",
  "face_value": 1000.0
 },
 {
  "symbol": "VASWANI",
  "company_name": "VASWANI IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE590L01019",
  "face_value": 1000.0
 },
 {
  "symbol": "VBDESAIFIN",
  "company_name": "V B DESAI FINANCIAL SERV",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "DUMMY9450",
  "face_value": 1000.0
 },
 {
  "symbol": "VBL",
  "company_name": "VARUN BEVERAGES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE200M01039",
  "face_value": 200.0
 },
 {
  "symbol": "VCL",
  "company_name": "VAXTEX COTFAB LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE098201036",
  "face_value": 100.0
 },
 {
  "symbol": "VCL-RE",
  "company_name": "VAXTEX COTFAB LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE098220010",
  "face_value": 100.0
 },
 {
  "symbol": "VECO-RE",
  "company_name": "VIKAS ECOTECH LTD - RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE806A20012",
  "face_value": 100.0
 },
 {
  "symbol": "VECO-RE1",
  "company_name": "VIKAS ECOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE806A20020",
  "face_value": 100.0
 },
 {
  "symbol": "VEDL",
  "company_name": "VEDANTA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE205A01025",
  "face_value": 100.0
 },
 {
  "symbol": "VEEDOL",
  "company_name": "VEEDOL CORPORATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE484C01030",
  "face_value": 200.0
 },
 {
  "symbol": "VEGPROFOOD",
  "company_name": "VEGEPRO FOODS AND FEEDS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE314301016",
  "face_value": 1000.0
 },
 {
  "symbol": "VELJAN",
  "company_name": "VELJAN DENISON LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE232E01013",
  "face_value": 1000.0
 },
 {
  "symbol": "VENKEYS",
  "company_name": "VENKY S (INDIA) LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE398A01010",
  "face_value": 1000.0
 },
 {
  "symbol": "VENLONPOLY",
  "company_name": "VENLON POLYSTER FILM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE314801015",
  "face_value": 1000.0
 },
 {
  "symbol": "VENTIVE",
  "company_name": "VENTIVE HOSPITALITY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE781S01027",
  "face_value": 100.0
 },
 {
  "symbol": "VENUSPIPES",
  "company_name": "VENUS PIPES & TUBES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0JA001018",
  "face_value": 1000.0
 },
 {
  "symbol": "VENUSREM",
  "company_name": "VENUS REMEDIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE411B01019",
  "face_value": 1000.0
 },
 {
  "symbol": "VENUSUGAR",
  "company_name": "VENUS SUGARS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE315101019",
  "face_value": 1000.0
 },
 {
  "symbol": "VERANDA",
  "company_name": "VERANDA LEARNING SOL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0IQ001011",
  "face_value": 1000.0
 },
 {
  "symbol": "VERTOZ",
  "company_name": "VERTOZ LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE188Y01031",
  "face_value": 1000.0
 },
 {
  "symbol": "VESUVIUS",
  "company_name": "VESUVIUS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE386A01023",
  "face_value": 100.0
 },
 {
  "symbol": "VETO",
  "company_name": "VETO SWITCHGEAR CABLE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE918N01018",
  "face_value": 1000.0
 },
 {
  "symbol": "VGL",
  "company_name": "VARVEE GLOBAL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE273D01027",
  "face_value": 500.0
 },
 {
  "symbol": "VGUARD",
  "company_name": "V-GUARD IND LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE951I01027",
  "face_value": 100.0
 },
 {
  "symbol": "VHL",
  "company_name": "VARDHMAN HOLDINGS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE701A01023",
  "face_value": 1000.0
 },
 {
  "symbol": "VHLTD",
  "company_name": "VICEROY HOTELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE048C01025",
  "face_value": 1000.0
 },
 {
  "symbol": "VHLTD-RE",
  "company_name": "VICEROY HOTELS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE048C20017",
  "face_value": 1000.0
 },
 {
  "symbol": "VICEROY",
  "company_name": "VICEROY HOTELS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE048C01017",
  "face_value": 1000.0
 },
 {
  "symbol": "VICKERSYS",
  "company_name": "VICKERS SYSTEMS INTL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE315701016",
  "face_value": 1000.0
 },
 {
  "symbol": "VICTGLASS",
  "company_name": "VICTORY GLASS & INDS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE315901012",
  "face_value": 1000.0
 },
 {
  "symbol": "VIDANIAGRO",
  "company_name": "VIDIANI AGROTECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE316801013",
  "face_value": 1000.0
 },
 {
  "symbol": "VIDEOIND",
  "company_name": "VIDEOCON INDUSTRIES LIMIT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE703A01011",
  "face_value": 1000.0
 },
 {
  "symbol": "VIDHIING",
  "company_name": "VIDHI SPCLTY F INGRDNTS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE632C01026",
  "face_value": 100.0
 },
 {
  "symbol": "VIDIANIENG",
  "company_name": "VIDIANI ENGINEERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE316901011",
  "face_value": 1000.0
 },
 {
  "symbol": "VIDYAWIRES",
  "company_name": "VIDYA WIRES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE14UN01029",
  "face_value": 100.0
 },
 {
  "symbol": "VIJAYA",
  "company_name": "VIJAYA DIAGNOSTIC CEN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE043W01024",
  "face_value": 100.0
 },
 {
  "symbol": "VIJIFI-RE",
  "company_name": "VIJI FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE159N20019",
  "face_value": 100.0
 },
 {
  "symbol": "VIJIFIN",
  "company_name": "VIJI FINANCE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE159N01027",
  "face_value": 100.0
 },
 {
  "symbol": "VIJSHAN",
  "company_name": "VIJAY SHANTHI BUILD LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE806F01011",
  "face_value": 1000.0
 },
 {
  "symbol": "VIKASECO",
  "company_name": "VIKAS ECOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE806A01020",
  "face_value": 100.0
 },
 {
  "symbol": "VIKASHYB",
  "company_name": "VHEL INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE311401017",
  "face_value": 1000.0
 },
 {
  "symbol": "VIKASLIFE",
  "company_name": "VIKAS LIFECARE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE161L01027",
  "face_value": 100.0
 },
 {
  "symbol": "VIKASPROP",
  "company_name": "VIKAS PROP & GRANITE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE767B01022",
  "face_value": 100.0
 },
 {
  "symbol": "VIKASWSP",
  "company_name": "VIKAS WSP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE706A01022",
  "face_value": 100.0
 },
 {
  "symbol": "VIKRAMPROJ",
  "company_name": "VIKRAM PROJECTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE311701010",
  "face_value": 1000.0
 },
 {
  "symbol": "VIKRAMSOLR",
  "company_name": "VIKRAM SOLAR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE078V01014",
  "face_value": 1000.0
 },
 {
  "symbol": "VIKRAN",
  "company_name": "VIKRAN ENGINEERING LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01R501028",
  "face_value": 100.0
 },
 {
  "symbol": "VIMALOIL",
  "company_name": "VIMAL O & F LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE067D01015",
  "face_value": 1000.0
 },
 {
  "symbol": "VIMTALABS",
  "company_name": "VIMTA LABS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE579C01029",
  "face_value": 200.0
 },
 {
  "symbol": "VINATIORGA",
  "company_name": "VINATI ORGANICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE410B01037",
  "face_value": 100.0
 },
 {
  "symbol": "VINCOFE",
  "company_name": "VINTAGE COFFEE N BVRGS L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE498Q01014",
  "face_value": 1000.0
 },
 {
  "symbol": "VINDHYATEL",
  "company_name": "VINDHYA TELELINKS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE707A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "VINEET-RE",
  "company_name": "VINEET LABORATORIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE505Y20010",
  "face_value": 1000.0
 },
 {
  "symbol": "VINEETLAB",
  "company_name": "VINEET LABORATORIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE505Y01010",
  "face_value": 1000.0
 },
 {
  "symbol": "VINNY",
  "company_name": "VINNY OVERSEAS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01KI01027",
  "face_value": 100.0
 },
 {
  "symbol": "VINNY-RE",
  "company_name": "VINNY OVERSEAS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01KI20019",
  "face_value": 100.0
 },
 {
  "symbol": "VINYLINDIA",
  "company_name": "VINYL CHEMICALS (I) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE250B01029",
  "face_value": 100.0
 },
 {
  "symbol": "VINYOGCLOT",
  "company_name": "VINIYOGA CLOTHEX LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE312601011",
  "face_value": 1000.0
 },
 {
  "symbol": "VIPCLOTHNG",
  "company_name": "VIP CLOTHING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE450G01024",
  "face_value": 200.0
 },
 {
  "symbol": "VIPIND",
  "company_name": "VIP INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE054A01027",
  "face_value": 200.0
 },
 {
  "symbol": "VIPPYSOLVX",
  "company_name": "VIPPY INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE313001013",
  "face_value": 1000.0
 },
 {
  "symbol": "VIPULLTD",
  "company_name": "VIPUL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE946H01037",
  "face_value": 100.0
 },
 {
  "symbol": "VIRAJALLOY",
  "company_name": "VIRAJ ALLOYS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE313301017",
  "face_value": 1000.0
 },
 {
  "symbol": "VIRALFILA",
  "company_name": "VIRAL FILAMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE313401015",
  "face_value": 1000.0
 },
 {
  "symbol": "VIRALSYNTX",
  "company_name": "VIRAL SYNTEX LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE313501012",
  "face_value": 1000.0
 },
 {
  "symbol": "VIRINCHI",
  "company_name": "VIRINCHI LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE539B01017",
  "face_value": 1000.0
 },
 {
  "symbol": "VISAKAIND",
  "company_name": "VISAKA INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE392A01021",
  "face_value": 200.0
 },
 {
  "symbol": "VISASTEEL",
  "company_name": "VISA STEEL LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE286H01012",
  "face_value": 1000.0
 },
 {
  "symbol": "VISESHINFO",
  "company_name": "VISESH INFOTECNICS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE861A01058",
  "face_value": 100.0
 },
 {
  "symbol": "VISHAL",
  "company_name": "VISHAL FABRICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE755Q01025",
  "face_value": 500.0
 },
 {
  "symbol": "VISHNU",
  "company_name": "VISHNU CHEMICALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE270I01022",
  "face_value": 200.0
 },
 {
  "symbol": "VISHWARAJ",
  "company_name": "VISHWARAJ SUGAR IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE430N01022",
  "face_value": 200.0
 },
 {
  "symbol": "VISUINTL",
  "company_name": "VISU INTERNATIONAL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE965A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "VITAL",
  "company_name": "VITAL CHEMTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0L4K01016",
  "face_value": 1000.0
 },
 {
  "symbol": "VITARACHEM",
  "company_name": "VITARA CHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE307501010",
  "face_value": 1000.0
 },
 {
  "symbol": "VIVIDHA",
  "company_name": "VISAGAR POLYTEX LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE370E01029",
  "face_value": 100.0
 },
 {
  "symbol": "VIVIMEDLAB",
  "company_name": "VIVIMED LABS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE526G01021",
  "face_value": 200.0
 },
 {
  "symbol": "VIYASH",
  "company_name": "VIYASH SCIENTIFIC LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE807F01027",
  "face_value": 200.0
 },
 {
  "symbol": "VLEGOV",
  "company_name": "VL E GOV AND IT SOL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE03HW01020",
  "face_value": 1000.0
 },
 {
  "symbol": "VLIFE-RE",
  "company_name": "VIKAS LIFECARE LTD-RE",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE161L20019",
  "face_value": 100.0
 },
 {
  "symbol": "VLIFE-RE1",
  "company_name": "VIKAS LIFECARE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE161L20027",
  "face_value": 100.0
 },
 {
  "symbol": "VLSFINANCE",
  "company_name": "VLS FINANCE LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE709A01018",
  "face_value": 1000.0
 },
 {
  "symbol": "VMART",
  "company_name": "VMART RETAIL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE665J01013",
  "face_value": 1000.0
 },
 {
  "symbol": "VMJOGENGG",
  "company_name": "V M JOG ENGG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE592701010",
  "face_value": 1000.0
 },
 {
  "symbol": "VMM",
  "company_name": "VISHAL MEGA MART LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01EA01019",
  "face_value": 1000.0
 },
 {
  "symbol": "VMSTMT",
  "company_name": "VMS TMT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0SJA01013",
  "face_value": 1000.0
 },
 {
  "symbol": "VOLTAMP",
  "company_name": "VOLTAMP TRANSFORMERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE540H01012",
  "face_value": 1000.0
 },
 {
  "symbol": "VOLTAS",
  "company_name": "VOLTAS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE226A01021",
  "face_value": 100.0
 },
 {
  "symbol": "VPRPL",
  "company_name": "VISHNU PRAKASH R PUNGLI L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0AE001013",
  "face_value": 1000.0
 },
 {
  "symbol": "VRAJ",
  "company_name": "VRAJ IRON AND STEEL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0S2V01010",
  "face_value": 1000.0
 },
 {
  "symbol": "VRLLOG",
  "company_name": "VRL LOGISTICS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE366I01010",
  "face_value": 1000.0
 },
 {
  "symbol": "VSSL",
  "company_name": "VARDHMAN SPC STEEL LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE050M01012",
  "face_value": 1000.0
 },
 {
  "symbol": "VSTIND",
  "company_name": "VST INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE710A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "VSTL",
  "company_name": "VIBHOR STEEL TUBES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0QTF01015",
  "face_value": 1000.0
 },
 {
  "symbol": "VSTTILLERS",
  "company_name": "VST TILLERS TRACTORS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE764D01017",
  "face_value": 1000.0
 },
 {
  "symbol": "VTCIND",
  "company_name": "V T C INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE308501019",
  "face_value": 1000.0
 },
 {
  "symbol": "VTL",
  "company_name": "VARDHMAN TEXTILES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE825A01020",
  "face_value": 200.0
 },
 {
  "symbol": "VULCANENG",
  "company_name": "VULCAN ENGINEERS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE308701015",
  "face_value": 1000.0
 },
 {
  "symbol": "VXLINSTR",
  "company_name": "VXL INSTRUMENTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE756A01019",
  "face_value": 1000.0
 },
 {
  "symbol": "WAAREEENER",
  "company_name": "WAAREE ENERGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE377N01017",
  "face_value": 1000.0
 },
 {
  "symbol": "WAAREEINDO",
  "company_name": "INDOSOLAR LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE866K01023",
  "face_value": 1000.0
 },
 {
  "symbol": "WAAREERTL",
  "company_name": "WAAREE RENEWABLE TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE299N01021",
  "face_value": 200.0
 },
 {
  "symbol": "WABAG",
  "company_name": "VA TECH WABAG LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE956G01038",
  "face_value": 200.0
 },
 {
  "symbol": "WAKEFIT",
  "company_name": "WAKEFIT INNOVATIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0E7301029",
  "face_value": 100.0
 },
 {
  "symbol": "WALCHANNAG",
  "company_name": "WALCHANDNAGAR INDUSTRIES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE711A01022",
  "face_value": 200.0
 },
 {
  "symbol": "WANBURY",
  "company_name": "WANBURY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE107F01022",
  "face_value": 1000.0
 },
 {
  "symbol": "WARRENTEA",
  "company_name": "WARREN TEA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE712A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "WATERBASE",
  "company_name": "WATERBASE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE054C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "WCIL",
  "company_name": "WESTERN CARRIERS (IND) L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0CJF01024",
  "face_value": 500.0
 },
 {
  "symbol": "WEALTH",
  "company_name": "WEALTH FRST PORT. MG. LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE658T01017",
  "face_value": 1000.0
 },
 {
  "symbol": "WEBELSOLAR",
  "company_name": "WEBSOL ENERGY SYSTEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE855C01023",
  "face_value": 100.0
 },
 {
  "symbol": "WEIZMANIND",
  "company_name": "WEIZMANN LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE080A01014",
  "face_value": 1000.0
 },
 {
  "symbol": "WEL",
  "company_name": "WONDER ELECTRICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE02WG01024",
  "face_value": 100.0
 },
 {
  "symbol": "WELCORP",
  "company_name": "WELSPUN CORP LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE191B01025",
  "face_value": 500.0
 },
 {
  "symbol": "WELDFLUX",
  "company_name": "UBE INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE303601012",
  "face_value": 1000.0
 },
 {
  "symbol": "WELENT",
  "company_name": "WELSPUN ENTERPRISES LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE625G01013",
  "face_value": 1000.0
 },
 {
  "symbol": "WELINV",
  "company_name": "WELSPUN INV & COMM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE389K01018",
  "face_value": 1000.0
 },
 {
  "symbol": "WELMANINCA",
  "company_name": "WELLMAN INCANDESCENT (I)",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE303701010",
  "face_value": 1000.0
 },
 {
  "symbol": "WELSPLSOL",
  "company_name": "WELSPUN SPECIALTY SOL L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE731F01037",
  "face_value": 600.0
 },
 {
  "symbol": "WELSPUNLIV",
  "company_name": "WELSPUN LIVING LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE192B01031",
  "face_value": 100.0
 },
 {
  "symbol": "WELSPUNPOL",
  "company_name": "WELSPUN INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE192B01015",
  "face_value": 1000.0
 },
 {
  "symbol": "WENDT",
  "company_name": "WENDT (INDIA) LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE274C01019",
  "face_value": 1000.0
 },
 {
  "symbol": "WESTERNBIO",
  "company_name": "ECOBOARD INDUSTRIES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE866A01016",
  "face_value": 1000.0
 },
 {
  "symbol": "WESTINDSEC",
  "company_name": "WESTERN INDIA SECURITIES",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE591701011",
  "face_value": 1000.0
 },
 {
  "symbol": "WESTLIFE",
  "company_name": "WESTLIFE FOODWORLD LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE274F01020",
  "face_value": 200.0
 },
 {
  "symbol": "WEWIN",
  "company_name": "WE WIN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE082W01014",
  "face_value": 1000.0
 },
 {
  "symbol": "WEWORK",
  "company_name": "WEWORK INDIA MANAGEMENT L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE085001019",
  "face_value": 1000.0
 },
 {
  "symbol": "WHEELS",
  "company_name": "WHEELS INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE715A01015",
  "face_value": 1000.0
 },
 {
  "symbol": "WHIRLPOOL",
  "company_name": "WHIRLPOOL OF INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE716A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "WILLAMAGOR",
  "company_name": "WILLIAMSON MAGOR",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE210A01017",
  "face_value": 1000.0
 },
 {
  "symbol": "WILLARDLTD",
  "company_name": "WILLARD INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE468501015",
  "face_value": 1000.0
 },
 {
  "symbol": "WIMPLAST",
  "company_name": "WIM PLAST LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE015B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "WINDLAS",
  "company_name": "WINDLAS BIOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0H5O01029",
  "face_value": 500.0
 },
 {
  "symbol": "WINDMACHIN",
  "company_name": "WINDSOR MACHINES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE052A01021",
  "face_value": 200.0
 },
 {
  "symbol": "WINPRO",
  "company_name": "WINPRO INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE974C01022",
  "face_value": 500.0
 },
 {
  "symbol": "WINSOME",
  "company_name": "WINSOME YARNS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE784B01035",
  "face_value": 1000.0
 },
 {
  "symbol": "WIPL",
  "company_name": "THE WESTERN INDIA PLY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE215F01023",
  "face_value": 1000.0
 },
 {
  "symbol": "WIPRO",
  "company_name": "WIPRO LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE075A01022",
  "face_value": 200.0
 },
 {
  "symbol": "WOCKH-RE",
  "company_name": "WOCKHARDT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE049B20017",
  "face_value": 500.0
 },
 {
  "symbol": "WOCKPHARMA",
  "company_name": "WOCKHARDT LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE049B01025",
  "face_value": 500.0
 },
 {
  "symbol": "WONDERLA",
  "company_name": "WONDERLA HOLIDAYS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE066O01014",
  "face_value": 1000.0
 },
 {
  "symbol": "WOOLWORTH",
  "company_name": "UNIWORTH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE207A01013",
  "face_value": 1000.0
 },
 {
  "symbol": "WORTHPERI",
  "company_name": "WORTH PERIPHERALS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE196Y01018",
  "face_value": 1000.0
 },
 {
  "symbol": "WPIL",
  "company_name": "W P I L LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE765D01022",
  "face_value": 100.0
 },
 {
  "symbol": "WSI",
  "company_name": "W.S.INDUSTRIES (I) LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE100D01014",
  "face_value": 1000.0
 },
 {
  "symbol": "WSIND",
  "company_name": "W S INDUSTRIES (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE100D01014",
  "face_value": 1000.0
 },
 {
  "symbol": "WSTCSTPAPR",
  "company_name": "WEST COAST PAPER MILLS LT",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE976A01021",
  "face_value": 200.0
 },
 {
  "symbol": "XCHANGING",
  "company_name": "XCHANGING SOLUTIONS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE692G01013",
  "face_value": 1000.0
 },
 {
  "symbol": "XELPMOC",
  "company_name": "XELPMOC DESIGN & TECH LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE01P501012",
  "face_value": 1000.0
 },
 {
  "symbol": "XLENERGY",
  "company_name": "XL ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE183H01011",
  "face_value": 1000.0
 },
 {
  "symbol": "XPROINDIA",
  "company_name": "XPRO INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE445C01015",
  "face_value": 1000.0
 },
 {
  "symbol": "XTGLOBAL",
  "company_name": "XTGLOBAL INFOTECH LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE547B01028",
  "face_value": 100.0
 },
 {
  "symbol": "YASHO",
  "company_name": "YASHO INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE616Z01012",
  "face_value": 1000.0
 },
 {
  "symbol": "YATHARTH",
  "company_name": "YATHARTH HOSP & TRA C S L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0JO301016",
  "face_value": 1000.0
 },
 {
  "symbol": "YATRA",
  "company_name": "YATRA ONLINE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE0JR601024",
  "face_value": 100.0
 },
 {
  "symbol": "YESBANK",
  "company_name": "YES BANK LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE528G01035",
  "face_value": 200.0
 },
 {
  "symbol": "YOGOPHARM",
  "company_name": "YOGI PHARMACY LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE302101014",
  "face_value": 1000.0
 },
 {
  "symbol": "YUKEN",
  "company_name": "YUKEN INDIA LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE384C01016",
  "face_value": 1000.0
 },
 {
  "symbol": "YUKENINDIA",
  "company_name": "YUKEN INDIA LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE302501015",
  "face_value": 1000.0
 },
 {
  "symbol": "ZAGGLE",
  "company_name": "ZAGGLE PREPA OCEAN SER L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE07K301024",
  "face_value": 100.0
 },
 {
  "symbol": "ZEEL",
  "company_name": "ZEE ENTERTAINMENT ENT LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE256A01028",
  "face_value": 100.0
 },
 {
  "symbol": "ZEELEARN",
  "company_name": "ZEE LEARN LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE565L01011",
  "face_value": 100.0
 },
 {
  "symbol": "ZEEMEDIA",
  "company_name": "ZEE MEDIA CORPORATION LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE966H01019",
  "face_value": 100.0
 },
 {
  "symbol": "ZENITHEXPO",
  "company_name": "ZENITH EXPORTS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE058B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ZENITHSTL",
  "company_name": "ZENITH STEEL PIP IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE318D01020",
  "face_value": 1000.0
 },
 {
  "symbol": "ZENSARTECH",
  "company_name": "ZENSAR TECHNOLOGIES  LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE520A01027",
  "face_value": 200.0
 },
 {
  "symbol": "ZENTEC",
  "company_name": "ZEN TECHNOLOGIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE251B01027",
  "face_value": 100.0
 },
 {
  "symbol": "ZFCVINDIA",
  "company_name": "ZF COM VE CTR SYS IND LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE342J01019",
  "face_value": 500.0
 },
 {
  "symbol": "ZFSTEERING",
  "company_name": "Z F STEERING GEAR (I) LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE116C01012",
  "face_value": 1000.0
 },
 {
  "symbol": "ZICOM",
  "company_name": "ZICOM ELECT SEC SYS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE871B01014",
  "face_value": 1000.0
 },
 {
  "symbol": "ZILONPHARM",
  "company_name": "ZILLION PHARMACHEM LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE303501014",
  "face_value": 1000.0
 },
 {
  "symbol": "ZIMLAB",
  "company_name": "ZIM LABORATORIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE518E01015",
  "face_value": 1000.0
 },
 {
  "symbol": "ZODIAC",
  "company_name": "ZODIAC ENERGY LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE761Y01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ZODIACLOTH",
  "company_name": "ZODIAC CLOTHING CO. LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE206B01013",
  "face_value": 1000.0
 },
 {
  "symbol": "ZODJRDMKJ",
  "company_name": "ZODIAC JRD-MKJ LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE077B01018",
  "face_value": 1000.0
 },
 {
  "symbol": "ZOTA",
  "company_name": "ZOTA HEALTH CARE LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE358U01012",
  "face_value": 1000.0
 },
 {
  "symbol": "ZSARACOM",
  "company_name": "SARASWATI COMM (INDIA) L",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE967G01019",
  "face_value": 1000.0
 },
 {
  "symbol": "ZUARI",
  "company_name": "ZUARI AGRO CHEMICALS LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE840M01016",
  "face_value": 1000.0
 },
 {
  "symbol": "ZUARIIND",
  "company_name": "ZUARI INDUSTRIES LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE217A01012",
  "face_value": 1000.0
 },
 {
  "symbol": "ZYDUSLIFE",
  "company_name": "ZYDUS LIFESCIENCES LTD",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE010B01027",
  "face_value": 100.0
 },
 {
  "symbol": "ZYDUSWELL",
  "company_name": "ZYDUS WELLNESS LIMITED",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE768C01028",
  "face_value": 200.0
 },
 {
  "symbol": "ZYLOG",
  "company_name": "ZYLOG SYSTEMS LTD.",
  "sector": "N/A",
  "industry": "N/A",
  "isin": "INE225I01026",
  "face_value": 500.0
 }
]


def _real_nifty50_seed() -> list[dict]:
    """Return only the genuine Nifty 50 constituents from ``NIFTY50_SEED``.

    The list at the top of this module accumulated duplicates over time —
    every real Nifty 50 symbol has a second entry later in the file with
    ``sector="N/A"`` (mistakenly inherited from the broader NSE universe
    seed). Because :func:`seed_dim_stock` runs ``ON CONFLICT DO UPDATE``,
    the duplicate would always overwrite the good row's sector with "N/A"
    and flip ``nifty50_member`` on for every symbol in the file (~6 000
    of them).

    This helper:
      * keeps **only** entries with a real sector (anything other than
        ``N/A``), which is the marker for hand-curated Nifty 50 rows.
      * dedupes on ``symbol``, keeping the first occurrence.
    """
    seen: set[str] = set()
    keep: list[dict] = []
    for row in NIFTY50_SEED:
        symbol = row.get("symbol")
        sector = (row.get("sector") or "").strip()
        if not symbol or sector in ("", "N/A"):
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        keep.append(row)
    return keep


def seed_dim_stock() -> int:
    """Insert Nifty 50 constituents into ``dim_stock``.

    Two-step procedure:

      1. Reset ``nifty50_member = FALSE`` across the whole table so that
         any stale flags from a previous bloated seed run are cleared.
      2. Upsert the real Nifty 50 rows with ``nifty50_member = TRUE`` and
         the curated sector / industry metadata.

    Idempotent: uses ``ON CONFLICT DO UPDATE`` to refresh metadata.

    Returns:
        Number of rows upserted.
    """
    engine = get_engine()
    now = datetime.now()

    reset_sql = text(
        "UPDATE dim_stock SET nifty50_member = FALSE "
        "WHERE nifty50_member = TRUE"
    )

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

    rows = _real_nifty50_seed()

    count = 0
    with engine.connect() as conn:
        reset = conn.execute(reset_sql)
        logger.info(
            "Reset nifty50_member=FALSE for %d previously-flagged rows",
            reset.rowcount or 0,
        )
        for stock in rows:
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
