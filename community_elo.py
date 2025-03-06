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
    df["pos_rank"] = df.groupby("pos")["elo"].rank(method="min", ascending=False).astype(int)

    return df

### ✅ **Fetch User Vote Data**
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
        if datetime.datetime.today().weekday() == 0 and user["last_voted"] != today:
            update_data["weekly_votes"] = 1  # Reset to 1 on Monday

        supabase.table("user_votes").update(update_data).eq("username", username.lower()).execute()

### ✅ **Update Player Elo Ratings**
def update_player_elo(player1_name, new_elo1, player2_name, new_elo2):
    supabase.table("players").update({"elo": new_elo1}).eq("name", player1_name).execute()
    supabase.table("players").update({"elo": new_elo2}).eq("name", player2_name).execute()

### ✅ **Elo Calculation**
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

# 🔥 **Initialize Matchup**
players_df = get_players()

if players_df.empty:
    st.error("⚠️ No players available!")
else:
    # 🎯 **Username Input**
    st.markdown("<h3 style='text-align: center;'>📝 Add a Username to Compete on the Leaderboard!</h3>", unsafe_allow_html=True)
    username = st.text_input("Enter Username", value=st.session_state.get("username", ""), max_chars=15)

    if username:
        st.session_state["username"] = username.lower()
        update_user_vote(username)

    # 🎯 **Matchup Selection Logic**
    if "player1" not in st.session_state or "player2" not in st.session_state:
        st.session_state.player1 = aggressive_weighted_selection(players_df)
        st.session_state.player2_candidates = players_df[
            (players_df["elo"] > st.session_state.player1["elo"] - 50) & (players_df["elo"] < st.session_state.player1["elo"] + 50)
        ]
        st.session_state.player2 = aggressive_weighted_selection(st.session_state.player2_candidates) if not st.session_state.player2_candidates.empty else aggressive_weighted_selection(players_df)

    player1 = st.session_state.player1
    player2 = st.session_state.player2

    # 🎯 **Store Initial Elo Ratings**
    if "initial_elo" not in st.session_state:
        st.session_state["initial_elo"] = {}
    if player1["name"] not in st.session_state["initial_elo"]:
        st.session_state["initial_elo"][player1["name"]] = player1["elo"]
    if player2["name"] not in st.session_state["initial_elo"]:
        st.session_state["initial_elo"][player2["name"]] = player2["elo"]

    # 🎯 **Matchup Display**
    st.markdown("<h1 style='text-align: center;'>Who Would You Rather Draft?</h1>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    def display_player(player, col):
        with col:
            st.image(player["image_url"] if player["image_url"] else DEFAULT_IMAGE, width=200)
            if st.button(player["name"], use_container_width=True):
                new_elo1, new_elo2 = calculate_elo(player1["elo"], player2["elo"]) if player["name"] == player1["name"] else calculate_elo(player2["elo"], player1["elo"])
                update_player_elo(player1["name"], new_elo1, player2["name"], new_elo2)
                update_user_vote(st.session_state["username"])
                st.session_state["updated_elo"] = {player1["name"]: new_elo1, player2["name"]: new_elo2}
                st.session_state["selected_player"] = player["name"]

    display_player(player1, col1)
    display_player(player2, col2)

    # 🎯 **Show Elo Update**
    if "selected_player" in st.session_state and st.session_state["selected_player"]:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>📊 Elo Changes</h3>", unsafe_allow_html=True)

        for player in [player1, player2]:
            color = "yellow" if player["name"] == st.session_state["selected_player"] else "transparent"
            change = st.session_state["updated_elo"][player["name"]] - st.session_state["initial_elo"][player["name"]]
            st.markdown(f"<div style='background-color:{color}; padding: 10px; border-radius: 5px; text-align: center;'><b>{player['name']}</b>: {st.session_state['updated_elo'][player['name']]} ELO ({change:+})</div>", unsafe_allow_html=True)

    # 🎯 **Next Matchup Button**
    if st.button("Next Matchup", use_container_width=True):
        del st.session_state["selected_player"]
        st.rerun()
