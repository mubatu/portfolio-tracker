import os
import pandas as pd
import yfinance as yf
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert
from dotenv import load_dotenv
from datetime import date, datetime

# 1. Setup Database
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing in .env")

engine = create_engine(DATABASE_URL)
print("✅ Connected to Database")

# ---------------------------------------------------------
# HELPER: Safe Insert (Upsert)
# ---------------------------------------------------------
def insert_on_conflict_nothing(table, conn, keys, data_iter):
    data = [dict(zip(keys, row)) for row in data_iter]
    stmt = insert(table.table).values(data)
    stmt = stmt.on_conflict_do_nothing(index_elements=["ticker", "date"])
    conn.execute(stmt)

# ---------------------------------------------------------
# STEP 1: Get Portfolio & Transactions
# ---------------------------------------------------------
# We will target the portfolio named 'FirstPortf' for your user
target_portfolio_name = "FirstPortf"
target_user_id = "9d81edfe-1774-4ade-981f-5467cc306e31" # <--- IMPORTANT: Update this again if needed!

# If you want to grab the ID dynamically (Assuming you pasted the UUID above correctly):
# For this script, let's just query the transactions for that specific portfolio name.
sql_query = text("""
    SELECT t.ticker, t.operation, t.quantity, t.date 
    FROM transactions t
    JOIN portfolios p ON t.portfolio_id = p.id
    WHERE p.name = :p_name
    ORDER BY t.date ASC
""")

with engine.connect() as conn:
    transactions_df = pd.read_sql(sql_query, conn, params={"p_name": target_portfolio_name})

if transactions_df.empty:
    print(f"⚠️ No transactions found for portfolio '{target_portfolio_name}'")
    exit()

print(f"📋 Found {len(transactions_df)} transactions.")

# ---------------------------------------------------------
# STEP 2: Determine Date Ranges per Ticker
# ---------------------------------------------------------
# Logic:
# - Start Date: The very first transaction date (Buy).
# - End Date: 
#     - If currently holding (Quantity > 0): TODAY
#     - If fully sold (Quantity == 0): Last Transaction Date

ticker_plans = {}
today = date.today()

# Group by ticker to process history
for ticker, group in transactions_df.groupby("ticker"):
    start_date = group['date'].min() # First time we touched this stock
    
    # Calculate current holdings to see if we still own it
    buys = group[group['operation'] == 'BUY']['quantity'].sum()
    sells = group[group['operation'] == 'SELL']['quantity'].sum()
    current_qty = buys - sells
    
    if current_qty > 0.0001: # Allowing for tiny float errors
        end_date = today # We still own it, so we need data up to NOW
        status = "Active"
    else:
        end_date = group['date'].max() # We sold everything, stop fetching at last sell
        status = "Sold Out"
        
    ticker_plans[ticker] = {"start": start_date, "end": end_date, "status": status}
    print(f"   🔹 {ticker}: Need data from {start_date} -> {end_date} ({status})")

# ---------------------------------------------------------
# STEP 3: Download & Insert Data
# ---------------------------------------------------------
print("\n⬇️ Starting Batch Download...")

for ticker, plan in ticker_plans.items():
    start = plan["start"]
    end = plan["end"]
    
    # yfinance 'end' is exclusive, so if end is today, we usually want tomorrow's date 
    # to ensure we capture today's close (if market is over).
    # Simple trick: Add 1 day to end date for the API call
    yf_end = end + pd.Timedelta(days=1)
    
    try:
        # Fetch data
        df = yf.download(ticker, start=start, end=yf_end, progress=False)
        
        if df.empty:
            print(f"   ⚠️ No data for {ticker}")
            continue
            
        # Clean and Format
        formatted_prices = []
        
        # Handle MultiIndex column issue if it exists (yfinance update)
        # If columns are like ('Close', 'A1CAP.IS'), flatten them
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(ticker, level=1, axis=1) if ticker in df.columns.levels[1] else df
        
        # Reset index to get Date as a column
        df = df.reset_index()
        
        for _, row in df.iterrows():
            # Ensure we have a valid date and close price
            if pd.notna(row['Close']):
                formatted_prices.append({
                    "ticker": ticker,
                    "date": row['Date'].date(),
                    "close": round(float(row['Close']), 2)
                })
        
        # Bulk Insert for this ticker
        if formatted_prices:
            df_insert = pd.DataFrame(formatted_prices)
            df_insert.to_sql(
                "market_prices", 
                engine, 
                if_exists="append", 
                index=False, 
                method=insert_on_conflict_nothing # <--- The safe insert!
            )
            print(f"   ✅ {ticker}: Inserted {len(formatted_prices)} days.")
            
    except Exception as e:
        print(f"   ❌ Error processing {ticker}: {e}")

print("\n🚀 Backfill Complete!")