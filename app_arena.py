import streamlit as st
import pandas as pd
import random
from battle_logic import Monster, Field
import math
import time

st.set_page_config(page_title="OnceWorld アリーナ勝敗予想", layout="wide")

# Load data (removed cache so edits to CSV are immediately reflected)
def load_data(filename):
    return pd.read_csv(filename)

df = load_data("monsters.csv")

# Helper to load a monster by NO.
def create_monster(team_name, m_no, level):
    base_data = df[df['NO.'] == m_no].iloc[0]
    return Monster(team_name, base_data, level)

def init_random_team(team_name):
    num_monsters = random.randint(1, 4)
    team = []
    for _ in range(num_monsters):
        m_no = random.choice(df['NO.'].tolist())
        level = random.randint(1, 1100)
        team.append(create_monster(team_name, m_no, level))
    return team

st.title("⚔️ OnceWorld アリーナ勝敗予想シミュレーター")

# --- UI Setup ---
mode = st.radio("選出モード", ["ランダム選出", "手動選出"], horizontal=True)

teams_dict = {"A": [], "B": [], "C": []}

if mode == "ランダム選出":
    if st.button("チームを再抽選🔄"):
        st.session_state['teams'] = {
            "A": init_random_team("A"),
            "B": init_random_team("B"),
            "C": init_random_team("C")
        }
    
    if 'teams' not in st.session_state:
        st.session_state['teams'] = {
            "A": init_random_team("A"),
            "B": init_random_team("B"),
            "C": init_random_team("C")
        }
        
    teams_dict = st.session_state['teams']
    
else:
    # Manual mode
    cols = st.columns(3)
    monster_options = df['NO.'].astype(str) + " - " + df['ペット名']
    
    for idx, team_letter in enumerate(["A", "B", "C"]):
        with cols[idx]:
            st.subheader(f"チーム {team_letter}")
            num_mons = st.number_input(f"チーム{team_letter}のモンスター数", min_value=1, max_value=4, value=1, key=f"num_{team_letter}")
            
            for i in range(num_mons):
                st.markdown(f"**モンスター {i+1}**")
                search_term = st.text_input("検索", key=f"search_{team_letter}_{i}")
                
                # Filter options based on search
                filtered_options = monster_options
                if search_term:
                    filtered_options = [opt for opt in monster_options if search_term in opt]
                    if not filtered_options:
                        filtered_options = monster_options # fallback if no match
                        
                sel_m = st.selectbox(f"種類", filtered_options, key=f"m_{team_letter}_{i}")
                sel_no = int(sel_m.split(" - ")[0])
                lv = st.number_input("レベル", min_value=1, max_value=1100, value=100, step=1, key=f"lv_{team_letter}_{i}")
                
                # We instantiate and add right away
                teams_dict[team_letter].append(create_monster(team_letter, sel_no, lv))

# Team Colors
team_colors_hex = {
    "A": "#FF4B4B", # Red
    "B": "#1E90FF", # Blue 
    "C": "#32CD32"  # Green
}

def colored_text(text, color):
    return f"<span style='color:{color}; font-weight:bold;'>{text}</span>"

# Display current teams
st.write("---")
cols = st.columns(3)
for idx, (t_name, t_list) in enumerate(teams_dict.items()):
    with cols[idx]:
        color = team_colors_hex[t_name]
        st.markdown(f"<h3 style='color:{color};'>🛡️ チーム {t_name}</h3>", unsafe_allow_html=True)
        for m in t_list:
            if m.m_type == "物理":
                stats_str = f"HP:{m.hp:,}, ATK:{m.atk:,}, DEF:{m.defense:,}, MDEF:{m.mdefense:,}, SPD:{m.spd:,}, LUCK:{m.luck:,}"
            else:
                stats_str = f"HP:{m.hp:,}, INT:{m.int_stat:,}, DEF:{m.defense:,}, MDEF:{m.mdefense:,}, SPD:{m.spd:,}, LUCK:{m.luck:,}"
                
            range_str = "🗡️近接" if getattr(m, 'range_type', '近接') == '近接' else "🏹遠隔"
            st.markdown(f"- **Lv.{m.level:,} {m.name}** ({range_str}/{m.m_type} | {stats_str})")

# Bet
st.write("---")
bet = st.selectbox("賭けるチームを選んでください", ["A", "B", "C"])

# Execution
col1, col2 = st.columns(2)
with col1:
    start_battle = st.button("⚔️ バトル開始！ (リアルタイム観戦)", type="primary")
with col2:
    skip_battle = st.button("⏩ 即座に結果を見る (スキップ)", type="secondary")

if start_battle or skip_battle:
    
    st.write("---")
    # Countdown limits if live
    if start_battle:
        countdown_container = st.empty()
        for i in [3, 2, 1]:
            countdown_container.markdown(f"<h1 style='text-align: center; font-size: 80px;'>{i}</h1>", unsafe_allow_html=True)
            time.sleep(1)
        countdown_container.empty()
        st.toast("バトルスタート！", icon="⚔️")
    else:
        st.toast("シミュレーションを高速処理中...", icon="⏩")

    
    st.subheader("🏁 バトルログ")
    
    import copy
    
    battle_teams = {"A": [], "B": [], "C": []}
    
    # Starting positions (shrunk to make field smaller)
    positions = {
        "A": (450, 450),
        "B": (550, 450),
        "C": (500, 500)
    }
    
    for t_name, t_list in teams_dict.items():
        base_x, base_y = positions[t_name]
        for i, m in enumerate(t_list):
            new_m = create_monster(t_name, m.no, m.level)
            new_m.x = base_x + random.randint(-50, 50)
            new_m.y = base_y + random.randint(-50, 50)
            battle_teams[t_name].append(new_m)
            
    field = Field(battle_teams)
    
    log_container = st.empty()
    status_container = st.empty()
    
    all_logs = []
    
    # Run Simulation Loop
    DELTA_TIME = 0.02   # 0.02秒刻み（高速攻撃の精度を確保）
    BATTLE_DURATION = 40.0  # 現実時間（およびシミュ内時間）での40秒制限
    
    start_time = time.time()
    last_display_time = 0.0
    
    progress_bar = st.progress(0)
    
    # If skipping, we just run the while loop mathematically until finish or 40s sim time
    if skip_battle:
        while not field.is_finished() and field.time_elapsed < BATTLE_DURATION:
            logs = field.step(delta_time=DELTA_TIME)
            if logs:
                for log in logs:
                    for t, c in team_colors_hex.items():
                        log = log.replace(f"チーム{t}", colored_text(f"チーム{t}", c))
                    all_logs.append(log)
        
        # Display the final log state
        display_logs = "\n".join(all_logs[-20:])
        log_container.markdown(f"<div style='height: 200px; overflow-y: scroll; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background: #262730; color: white;'>{display_logs.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
        progress_bar.progress(1.0)
        
        # Determine if it was a timeout in simulation
        is_timeout = field.time_elapsed >= BATTLE_DURATION
        elapsed_real_time = field.time_elapsed # For output logic later
        
    else:
        # Live battle viewer
        is_timeout = False
        while not field.is_finished():
            current_real_time = time.time()
            elapsed_real_time = current_real_time - start_time
            
            if elapsed_real_time >= BATTLE_DURATION:
                is_timeout = True
                break
                
            # Update progress bar
            p = min(1.0, elapsed_real_time / BATTLE_DURATION)
            progress_bar.progress(p)
            
            # Run simulation steps catch-up (if rendering took time)
            while field.time_elapsed < elapsed_real_time:
                logs = field.step(delta_time=DELTA_TIME)
                if logs:
                    # Colorize logs
                    colored_logs = []
                    for log in logs:
                        for t, c in team_colors_hex.items():
                            log = log.replace(f"チーム{t}", colored_text(f"チーム{t}", c))
                        colored_logs.append(log)
                    
                    all_logs.extend(colored_logs)
                    display_logs = "\n".join(all_logs[-10:])
                    # Wrap in HTML to render color spans
                    log_container.markdown(f"<div style='height: 200px; overflow-y: scroll; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background: #262730; color: white;'>{display_logs.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
                    
            # Draw status every 1.0 second of real time
            if elapsed_real_time - last_display_time >= 1.0:
                last_display_time = elapsed_real_time
                time_left = BATTLE_DURATION - elapsed_real_time
                time_color = "red" if time_left <= 10 else "white"
                status_text = f"<h4 style='color:{time_color}'>⏳ 残り時間: {max(0, time_left):.1f}s</h4><br>"
                
                for m in field.monsters:
                    m_color = team_colors_hex[m.team]
                    state = "💀" if m.is_dead else f"❤️ {m.hp:,}/{m.max_hp:,}"
                    status_text += f"<span style='color:{m_color};'>[{m.team}] Lv.{m.level:,} {m.name}</span> : {state} (x:{m.x:.0f}, y:{m.y:.0f})<br>"
                status_container.markdown(status_text, unsafe_allow_html=True)
                
            # Small sleep to prevent freezing the browser/app
            time.sleep(0.01)
            
    # Final Result
    progress_bar.empty()
    # 経過時間が設定時間を超えていればタイムアップ
    if is_timeout:
        st.warning(f"⏳ タイムアップ！ 残念ながら{BATTLE_DURATION:.1f}秒（シミュレーション時間）以内に決着がつきませんでした。")
        all_logs.append("タイムアップ！ 残りHP等による勝敗判定に入ります。")
        
    winner = field.get_winner()
    st.write("---")
    
    if winner in ["A", "B", "C"]:
        win_color = team_colors_hex[winner]
        if winner == bet:
            st.markdown(f"<h2 style='color:{win_color};'>🎉 おめでとうございます！チーム {winner} が勝利しました！！</h2>", unsafe_allow_html=True)
            st.balloons()
        else:
            st.markdown(f"<h2 style='color:{win_color};'>💀 残念... 勝利したのはチーム {winner} でした。</h2>", unsafe_allow_html=True)
    else:
        st.info("引き分けです！")
        
    st.info(f"総戦闘時間: {field.time_elapsed:.1f} 秒")
    
    with st.expander("全戦闘ログを見る"):
        # raw HTML join
        full_log_html = "<br>".join(all_logs)
        st.markdown(f"<div style='font-family: monospace;'>{full_log_html}</div>", unsafe_allow_html=True)
