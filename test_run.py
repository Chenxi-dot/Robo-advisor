import sys
import os
import pandas as pd
from unittest.mock import MagicMock

# Mock streamlit
sys.modules["streamlit"] = MagicMock()
import streamlit as st

# Mock st.cache_data to just return the function
def cache_data(*args, **kwargs):
    def decorator(func):
        return func
    return decorator
st.cache_data = cache_data
st.secrets = {}

# Add the project directory to sys.path
sys.path.append("/home/chenxi/Final Project")

try:
    print("Testing imports...")
    from investment_research import get_stock_list, get_market_indices, get_industry_peers
    print("Imports successful.")

    print("Testing data fetching functions...")
    
    # Test get_stock_list
    print("Fetching stock list...")
    stock_list = get_stock_list()
    if not stock_list.empty:
        print(f"Stock list fetched. {len(stock_list)} stocks found.")
    else:
        print("Stock list is empty (might be using fallback).")

    # Test get_market_indices
    print("Fetching market indices...")
    indices = get_market_indices()
    print(f"Market indices fetched: {len(indices)} rows.")

    # Test get_industry_peers for a known stock (e.g., Ping An Bank 000001)
    print("Fetching industry peers for 000001...")
    industry, peers, hist = get_industry_peers("000001", "平安银行")
    print(f"Industry: {industry}")
    print(f"Peers count: {len(peers)}")
    print(f"History length: {len(hist)}")

    print("Basic logic tests passed.")

except Exception as e:
    print(f"Test failed with error: {e}")
    import traceback
    traceback.print_exc()
