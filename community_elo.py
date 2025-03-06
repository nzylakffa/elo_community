import streamlit as st
from supabase import create_client, Client
import pandas as pd
import random
import datetime

# 🔧 Supabase Setup
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

DEFAULT_IMAGE = "https://png.pngtree.com/element_our/png/20181205/question-mark-vector-icon-png_256683.jpg"

### ✅ **Fetch Players from Supabase**
def get_players():
    response = supabase.table("players").select("*").execute()
    data = response.data

    if not data:
        st.error("❌ No player data found in Supabase!")
        return pd.DataFrame(columns=["name", "elo", "image_url", "team", "pos", "Votes"])

    df = pd.DataFrame(data)
    df["elo"] = pd.to_numeric(df["elo"], errors="coerce")
    df["Votes"] = pd.to_numeric(df["Votes"], errors="coerce")
    
    # Compute rankings dynamically
    df["pos_rank"] = df.groupby("pos")["elo"].rank(method="min", ascending=False).astype(int)

    return df


### ✅ **Fetch User Vote Data from Supabase**
def get_user_data():
    response = supabase.table("user_votes").select("*").execute()
    data = response.data

    if not data:
        return pd.DataFrame(columns=["username", "total_votes", "weekly_votes", "last_voted"])

    df = pd.DataFrame(data)
    df["total_votes"] = df["total_votes"].astype(int)
    df["weekly_votes"] = df["weekly_votes"].astype(int)

    return df


### ✅ **Update User Vote Count**
def update_user_vote(username):
    today = datetime.date.today().strftime("%Y-%m-%d")

    response = supabase.table("user_votes").select("*").eq("username", username.lower()).execute()
    user = response.data

    if not user:
        # New user → Insert vote count
        supabase.table("user_votes").insert({
            "username": username.lower(),
            "total_votes": 1,
            "weekly_votes": 1,
            "last_voted": today
        }).execute()
    else:
        user = user[0]
        update_data = {
            "total_votes": user["total_votes"] + 1,
            "weekly_votes": user["weekly_votes"] + 1,
            "last_voted": today
        }

        # Reset weekly votes on Monday
        if datetime.datetime.today().weekday() == 0 and user["last_voted"] != today:
            update_data["weekly_votes"] = 1  # Reset to 1 (new vote)

        supabase.table("user_votes").update(update_data).eq("username", username.lower()).execute()


### ✅ **Update Player Elo Ratings in Supabase**
def update_player_elo(player1_name, new_elo1, player2_name, new_elo2):
    supabase.table("players").update({"elo": new_elo1}).eq("name", player1_name).execute()
    supabase.table("players").update({"elo": new_elo2}).eq("name", player2_name).execute()


### ✅ **Elo Calculation Logic**
def calculate_elo(winner_elo, loser_elo, k=24):
    expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_elo - loser_elo) / 400))
    new_winner_elo = winner_elo + k * (1 - expected_winner)
    new_loser_elo = loser_elo + k * (0 - expected_loser)
    return round(new_winner_elo), round(new_loser_elo)


### ✅ **Weighted Selection for Matchups**
def aggressive_weighted_selection(df, weight_col="elo", alpha=6):
    df = df.copy()
    df["normalized_elo"] = (df[weight_col] - df[weight_col].min()) / (df[weight_col].max() - df[weight_col].min())
    df["weight"] = df["normalized_elo"] ** alpha
    df["weight"] /= df["weight"].sum()
    
    return df.sample(weights=df["weight"]).iloc[0]


### 🔥 **Initialize Matchup (Pull Players & Select Randomly)**
players_df = get_players()

if players_df.empty:
    st.error("⚠️ No players available!")
else:
    # Select two players using weighted probability
    player1 = aggressive_weighted_selection(players_df)
    player2_candidates = players_df[(players_df["elo"] > player1["elo"] - 50) & (players_df["elo"] < player1["elo"] + 50)]

    player2 = aggressive_weighted_selection(player2_candidates) if not player2_candidates.empty else aggressive_weighted_selection(players_df)

    st.title("Who Would You Rather Draft?")

    col1, col2 = st.columns(2)

    with col1:
        img1 = player1["image_url"] if isinstance(player1["image_url"], str) and player1["image_url"].startswith("http") else DEFAULT_IMAGE
        st.image(img1, width=200)
        if st.button(player1["name"], use_container_width=True):
            new_elo1, new_elo2 = calculate_elo(player1["elo"], player2["elo"])
            update_player_elo(player1["name"], new_elo1, player2["name"], new_elo2)
            update_user_vote(st.session_state.get("username", "anonymous"))
            st.rerun()

    with col2:
        img2 = player2["image_url"] if isinstance(player2["image_url"], str) and player2["image_url"].startswith("http") else DEFAULT_IMAGE
        st.image(img2, width=200)
        if st.button(player2["name"], use_container_width=True):
            new_elo2, new_elo1 = calculate_elo(player2["elo"], player1["elo"])
            update_player_elo(player2["name"], new_elo2, player1["name"], new_elo1)
            update_user_vote(st.session_state.get("username", "anonymous"))
            st.rerun()


### 🏆 **Leaderboards (All-Time & Weekly)**
st.markdown("## 🏆 All-Time Leaderboard")
user_data = get_user_data()
user_data = user_data.sort_values(by="total_votes", ascending=False).head(5)

st.dataframe(user_data[["username", "total_votes", "last_voted"]], hide_index=True, use_container_width=True)

st.markdown("## ⏳ Weekly Leaderboard")
weekly_data = user_data.sort_values(by="weekly_votes", ascending=False).head(5)
st.dataframe(weekly_data[["username", "weekly_votes", "last_voted"]], hide_index=True, use_container_width=True)

# **Next Matchup Button**
if st.button("Next Matchup", key="next_matchup", use_container_width=True):
    st.rerun()
