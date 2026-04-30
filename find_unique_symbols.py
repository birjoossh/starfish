#!/usr/bin/env python3
"""
NSE Universe Symbol Extractor
Reads all CSV files from a directory and extracts unique SYMBOLs from the first column.
Handles your sample format: "SYMBOL","SERIES",...
Saves unique symbols to symbols_universe.txt and symbols_universe.csv
"""

import os
import glob
import pandas as pd
from pathlib import Path

def extract_unique_symbols(directory_path):
    """
    Extract unique SYMBOLs from all CSV files in the directory.
    
    Args:
        directory_path (str): Path to directory containing CSV files
    
    Returns:
        set: Unique symbols
    """
    csv_files = glob.glob(os.path.join(directory_path, "*.csv"))
    unique_symbols = set()
    
    print(f"Found {len(csv_files)} CSV files")
    
    for file_path in csv_files:
        try:
            # Read CSV - assumes first column is SYMBOL
            df = pd.read_csv(file_path, skiprows=2, nrows=1000000)  # Limit rows for speed
            if 'SYMBOL' in df.columns:
                symbols = df['SYMBOL'].dropna().astype(str).unique()
            else:
                # Fallback: first column
                symbols = df.iloc[:, 0].dropna().astype(str).unique()
            
            unique_symbols.update(symbols)
            print(f"  {os.path.basename(file_path)}: {len(symbols)} symbols")
            
        except Exception as e:
            print(f"  Error reading {os.path.basename(file_path)}: {e}")
    
    return unique_symbols

def save_symbols(symbols, output_dir):
    """Save symbols to multiple formats"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Sorted list
    symbols_list = sorted(list(symbols))
    
    # TXT (one per line)
    with open(os.path.join(output_dir, "symbols_universe.txt"), 'w') as f:
        for sym in symbols_list:
            f.write(f"{sym}\n")
    
    # CSV
    df_symbols = pd.DataFrame({'SYMBOL': symbols_list})
    df_symbols.to_csv(os.path.join(output_dir, "symbols_universe.csv"), index=False)
    
    # JSON
    import json
    with open(os.path.join(output_dir, "symbols_universe.json"), 'w') as f:
        json.dump(symbols_list, f)
    
    print(f"\nSaved {len(symbols_list)} unique symbols to {output_dir}/")
    print("- symbols_universe.txt (one per line)")
    print("- symbols_universe.csv") 
    print("- symbols_universe.json")

if __name__ == "__main__":
    # Change this to your directory path
    DIRECTORY = "./data/raw/52wk"  # or r"C:\path\to\your\csvs"
    OUTPUT_DIR = "./nse_universe"
    
    print("=== NSE Universe Symbol Extractor ===")
    symbols = extract_unique_symbols(DIRECTORY)
    print(f"\nTotal unique SYMBOLs found: {len(symbols)}")
    
    save_symbols(symbols, OUTPUT_DIR)
    
    # Print first 20 for verification
    print("\nFirst 20 symbols:")
    for sym in sorted(list(symbols))[:20]:
        print(f"  {sym}")
