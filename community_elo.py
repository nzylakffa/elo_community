import streamlit as st
from supabase import create_client, Client
import pandas as pd
import random
import datetime

# Load credentials from secrets
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_players():
    """Fetches all players from Supabase and returns a DataFrame."""
    response = supabase.table("players").select("*").order("id").execute()
       
    data = response.data

    if not isinstance(data, list):  # Ensure it's a list before making a DataFrame
        st.error("❌ Unexpected data format! Supabase response is not a list.")
        return pd.DataFrame()

    if not data:  # If list is empty
        st.error("❌ No player data found in Supabase! Ensure the table is populated.")
        return pd.DataFrame(columns=["name", "elo", "image_url", "team", "pos", "Pos Rank", "3/4 elo", "Votes", "Trend"])

    df = pd.DataFrame(data)  # Convert to DataFrame
    
    # Ensure correct data types
    df["elo"] = pd.to_numeric(df["elo"], errors="coerce")
    df["Votes"] = pd.to_numeric(df["Votes"], errors="coerce")
    df["Pos Rank"] = pd.to_numeric(df["Pos Rank"], errors="coerce")

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
    # Fetch two random players
    player1 = players_df.sample(1).iloc[0]
    player2 = players_df.sample(1).iloc[0]

    st.title("Who Would You Rather Draft?")

    # Create two columns for side-by-side layout
    col1, col2 = st.columns(2)

    with col1:
        st.image(player1["image_url"], width=200)  # Show player image
        if st.button(player1["name"], use_container_width=True):  # Button with player name only
            update_player_elo(player1["name"], player1["elo"] + 10, player2["name"], player2["elo"] - 10)

    with col2:
        st.image(player2["image_url"], width=200)
        if st.button(player2["name"], use_container_width=True):
            update_player_elo(player2["name"], player2["elo"] + 10, player1["name"], player1["elo"] - 10)
