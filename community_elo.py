import streamlit as st
from supabase import create_client, Client
import pandas as pd
import random
import datetime

from supabase import create_client, Client

SUPABASE_URL = "https://your-supabase-url.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InptbWJtd3NmbXptcm52aml1amN6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDEyMjk3NDUsImV4cCI6MjA1NjgwNTc0NX0.0XJEj-7RcVtwRZeokZyoGF4-6lh0LM37S_cj8m4zFM0"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

response = supabase.table("players").select("*").execute()

print(response)



def get_players():
    """Fetches all players from Supabase and returns a DataFrame."""
    response = supabase.table("players").select("*").execute()
    data = response.data

    if not data:
        st.error("❌ No player data found in Supabase! Ensure the table is populated.")
        return pd.DataFrame(columns=["name", "elo", "image_url", "team", "pos", "Pos Rank", "3/4 elo","Votes" , "Trend"])

    df = pd.DataFrame(data)
    df["elo"] = df["elo"].astype(float)
    df["votes"] = df["votes"].astype(int)
    df["pos_rank"] = df["pos_rank"].astype(int)
    
    return df



def get_user_data():
    """Fetches user vote data from Supabase."""
    response = supabase.table("user_votes").select("*").execute()
    data = response.data

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df["total_votes"] = df["total_votes"].astype(int)
    df["weekly_votes"] = df["weekly_votes"].astype(int)
    
    return df



def get_player_value(player_name):
    """Fetch player value from Supabase (if stored in a separate table)."""
    response = supabase.table("player_values").select("value").eq("name", player_name).execute()
    
    if response.data:
        return float(response.data[0]["value"])
    
    return None



def update_user_vote(username, count_vote=True):
    """Updates user vote count in Supabase."""
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # Check if user exists
    response = supabase.table("user_votes").select("*").eq("username", username.lower()).execute()
    user = response.data

    if not user:
        # Insert new user if not found
        supabase.table("user_votes").insert({
            "username": username.lower(),
            "total_votes": 1 if count_vote else 0,
            "weekly_votes": 1 if count_vote else 0,
            "last_voted": today
        }).execute()
    else:
        # Update existing user
        user = user[0]
        update_data = {}

        if count_vote:
            update_data["total_votes"] = user["total_votes"] + 1
            update_data["weekly_votes"] = user["weekly_votes"] + 1

        update_data["last_voted"] = today
        supabase.table("user_votes").update(update_data).eq("username", username.lower()).execute()

        
def update_player_elo(player1_name, new_elo1, player2_name, new_elo2):
    """Updates player Elo ratings in Supabase."""
    supabase.table("players").update({"elo": new_elo1}).eq("name", player1_name).execute()
    supabase.table("players").update({"elo": new_elo2}).eq("name", player2_name).execute()


# Load Data at Startup
players_df = get_players()
users_df = get_user_data()

if players_df.empty:
    st.error("⚠️ No players available! Check your database.")
else:
    # Fetch player data safely
    player1 = players_df.sample(1).iloc[0]  # Select random player
    player2 = players_df.sample(1).iloc[0]  # Select another random player

    st.title("Who Would You Rather Draft?")
    st.write(f"{player1['name']} (Elo: {player1['elo']}) vs {player2['name']} (Elo: {player2['elo']})")

    if st.button(f"Pick {player1['name']}"):
        update_player_elo(player1["name"], player1["elo"] + 10, player2["name"], player2["elo"] - 10)

    if st.button(f"Pick {player2['name']}"):
        update_player_elo(player2["name"], player2["elo"] + 10, player1["name"], player1["elo"] - 10)

