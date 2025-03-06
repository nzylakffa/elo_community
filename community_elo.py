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
    df["total_votes"] = df["total_votes"].astype(float)  # ✅ Now supports decimal votes
    df["weekly_votes"] = df["weekly_votes"].astype(float)

    return df

### ✅ **Update User Vote Count (Now Counts 0.25 Per Selection)**
def update_user_vote(username):
    today = datetime.date.today().strftime("%Y-%m-%d")

    response = supabase.table("user_votes").select("*").eq("username", username.lower()).execute()
    user = response.data

    if not user:
        supabase.table("user_votes").insert({
            "username": username.lower(),
            "total_votes": 0.25,  # ✅ Adjusted to count 0.25 per selection
            "weekly_votes": 0.25,
            "last_voted": today
        }).execute()
    else:
        user = user[0]
        update_data = {
            "total_votes": user["total_votes"] + 0.25,  # ✅ Now increments by 0.25
            "weekly_votes": user["weekly_votes"] + 0.25,
            "last_voted": today
        }
        if datetime.datetime.today().weekday() == 0 and user["last_voted"] != today:
            update_data["weekly_votes"] = 0.25  # Reset to 0.25 on Monday

        supabase.table("user_votes").update(update_data).eq("username", username.lower()).execute()

### ✅ **Update Player Elo Ratings**
def update_player_elo(player1_name, new_elo1, player2_name, new_elo2):
    supabase.table("players").update({"elo": new_elo1}).eq("name", player1_name).execute()
    supabase.table("players").update({"elo": new_elo2}).eq("name", player2_name).execute()

### ✅ **Elo Calculation**
def calculate_elo(winner_elo, loser_elo, k=24):
    """Properly adjust Elo ratings so the winner gains and loser drops correctly."""

    # Expected scores based on Elo ratings
    expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_elo - loser_elo) / 400))

    # New Elo ratings
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
    username = st.text_input("Enter Username", value=st.session_state.get("username", "").lower(), max_chars=15)

    if username:
        st.session_state["username"] = username.lower()  # ✅ Store as lowercase
        update_user_vote(st.session_state["username"])  # ✅ Track the vote

    # 🎯 **Matchup Selection Logic**
    # ✅ Ensure session state variables exist before accessing them
    if "player1" not in st.session_state or "player2" not in st.session_state:
        st.session_state["player1"] = aggressive_weighted_selection(players_df)
        st.session_state["player2_candidates"] = players_df[
            (players_df["elo"] > st.session_state["player1"]["elo"] - 50) & 
            (players_df["elo"] < st.session_state["player1"]["elo"] + 50)
        ]
        st.session_state["player2"] = aggressive_weighted_selection(st.session_state["player2_candidates"]) if not st.session_state["player2_candidates"].empty else aggressive_weighted_selection(players_df)
    
        # ✅ Ensure players are different
        while st.session_state["player2"]["name"] == st.session_state["player1"]["name"]:
            st.session_state["player2"] = aggressive_weighted_selection(players_df)
    
    # ✅ Assign local variables after ensuring session state is initialized
    player1 = st.session_state["player1"]
    player2 = st.session_state["player2"]
    
    # ✅ Generate a unique ID for the matchup
    matchup_id = f"{player1['name']}_vs_{player2['name']}"


    # 🎯 **Store Initial Elo Ratings**
    if "initial_elo" not in st.session_state:
        st.session_state["initial_elo"] = {}
    st.session_state["initial_elo"][player1["name"]] = player1["elo"]
    st.session_state["initial_elo"][player2["name"]] = player2["elo"]

    # 🎯 **Matchup Display**
    st.markdown("<h1 style='text-align: center;'>Who Would You Rather Draft?</h1>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

def display_player(player, col, matchup_id):
    with col:
        # ✅ Center image using HTML & CSS
        st.markdown(
            f"""
            <div style="display: flex; flex-direction: column; align-items: center; text-align: center;">
                <img src="{player['image_url'] if player['image_url'] else DEFAULT_IMAGE}" width="200" style="border-radius: 10px;">
                <div style="margin-top: 10px;">
                    {st.button(player["name"], use_container_width=True)}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
            if st.session_state.get("last_voted_matchup") != matchup_id and not st.session_state.get("vote_processed", False):  
                winner, loser = (player1, player2) if player["name"] == player1["name"] else (player2, player1)
                new_winner_elo, new_loser_elo = calculate_elo(winner["elo"], loser["elo"])
            
                update_player_elo(winner["name"], new_winner_elo, loser["name"], new_loser_elo)
                if not st.session_state.get("vote_processed", False):  
                    update_user_vote(st.session_state["username"])  
                    st.session_state["vote_processed"] = True  # ✅ Prevent extra votes
                
                # ✅ Track that this matchup has been voted on
                st.session_state["last_voted_matchup"] = matchup_id
                st.session_state["vote_registered"] = True  # ✅ Prevent further votes until reset

            
                st.session_state["updated_elo"] = {
                    winner["name"]: new_winner_elo,
                    loser["name"]: new_loser_elo
                }
                st.session_state["selected_player"] = player["name"]
            else:
                st.warning("⚠️ You already voted! Click 'Next Matchup' to vote again.")

    display_player(player1, col1, matchup_id)
    display_player(player2, col2, matchup_id)

    # 🎯 **Show Elo Update**
    if "selected_player" in st.session_state and st.session_state["selected_player"]:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>📊 Elo Changes</h3>", unsafe_allow_html=True)

        for player in [player1, player2]:
            color = "yellow" if player["name"] == st.session_state["selected_player"] else "transparent"
            change = st.session_state["updated_elo"][player["name"]] - st.session_state["initial_elo"][player["name"]]
            st.markdown(f"<div style='background-color:{color}; padding: 10px; border-radius: 5px; text-align: center;'>"
                        f"<b>{player['name']}</b>: {st.session_state['updated_elo'][player['name']]} ELO ({change:+})"
                        f"</div>", unsafe_allow_html=True)

    # 🎯 **Next Matchup Button**
    if st.button("Next Matchup", use_container_width=True):
        # ✅ Reset vote tracking for the new matchup
        st.session_state["last_voted_matchup"] = None  
        st.session_state["vote_processed"] = False  
        
        # ✅ Select new Player 1
        st.session_state["player1"] = aggressive_weighted_selection(players_df)
        
        # ✅ Keep selecting Player 2 until it's different from Player 1
        while True:
            st.session_state["player2_candidates"] = players_df[
                (players_df["elo"] > st.session_state["player1"]["elo"] - 50) & 
                (players_df["elo"] < st.session_state["player1"]["elo"] + 50)
            ]
            st.session_state["player2"] = aggressive_weighted_selection(st.session_state["player2_candidates"]) if not st.session_state["player2_candidates"].empty else aggressive_weighted_selection(players_df)
        
            if st.session_state["player2"]["name"] != st.session_state["player1"]["name"]:
                break  # ✅ Ensure players are different
        
        # ✅ Reset Elo tracking
        st.session_state["initial_elo"] = {
            st.session_state["player1"]["name"]: st.session_state["player1"]["elo"],
            st.session_state["player2"]["name"]: st.session_state["player2"]["elo"]
        }
        st.session_state["selected_player"] = None
        
        st.rerun()


# 🎯 **Always Show Leaderboards at the Bottom**
user_data = get_user_data()
user_data["username"] = user_data["username"].str.lower()
user_data = user_data.groupby("username", as_index=False).agg({
    "total_votes": "sum",
    "weekly_votes": "sum",
    "last_voted": "max"
})

# ✅ Ensure columns are numeric before sorting
user_data["total_votes"] = pd.to_numeric(user_data["total_votes"], errors="coerce").fillna(0).astype(int)
user_data["weekly_votes"] = pd.to_numeric(user_data["weekly_votes"], errors="coerce").fillna(0).astype(int)

# 🎖️ **All-Time Leaderboard**
st.markdown("<h2 style='text-align: center;'>🏆 All-Time Leaderboard</h2>", unsafe_allow_html=True)
df_all_time = user_data.sort_values(by="total_votes", ascending=False).head(5)
df_all_time["Rank"] = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][: len(df_all_time)]
df_all_time = df_all_time.rename(columns={"username": "Username", "total_votes": "Total Votes", "last_voted": "Last Voted"})
df_all_time = df_all_time[["Rank", "Username", "Total Votes", "Last Voted"]]
st.dataframe(df_all_time.set_index("Rank"), hide_index=False, use_container_width=True)

# ⏳ **Weekly Leaderboard**
st.markdown("<h2 style='text-align: center;'>⏳ Weekly Leaderboard</h2>", unsafe_allow_html=True)
df_weekly = user_data.sort_values(by="weekly_votes", ascending=False).head(5)
df_weekly["Rank"] = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][: len(df_weekly)]
df_weekly = df_weekly.rename(columns={"username": "Username", "weekly_votes": "Weekly Votes", "last_voted": "Last Voted"})
df_weekly = df_weekly[["Rank", "Username", "Weekly Votes", "Last Voted"]]
st.dataframe(df_weekly.set_index("Rank"), hide_index=False, use_container_width=True)
