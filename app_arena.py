import streamlit as st
import pandas as pd
import random
from battle_logic import Monster, Field
import math
import time

st.set_page_config(page_title="OnceWorld アリーナ勝敗予想", layout="wide")

# Custom CSS for white-outlined buttons and selectboxes
st.markdown("""
<style>
/* Make secondary buttons have a white outline */
button[kind="secondary"] {
    border: 1px solid white !important;
    background-color: transparent !important;
    color: white !important;
}
button[kind="secondary"]:hover {
    border: 1px solid #1E90FF !important;
    color: #1E90FF !important;
}

/* Style the Selectbox input to have a white outline */
div[data-baseweb="select"] > div {
    border: 1px solid white !important;
    background-color: transparent !important;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

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
    # 重複を防ぐため sample を使用
    chosen_nos = random.sample(df['NO.'].tolist(), num_monsters)
    for m_no in chosen_nos:
        level = random.randint(1, 1100)
        team.append(create_monster(team_name, m_no, level))
    return team


st.markdown("### ⚔️ OnceWorld アリーナ勝敗予想シミュレーター")

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
    monster_options = df['NO.'].astype(str) + " - " + df['ペット名']
    

    cols = st.columns(3)
    
    for idx, team_letter in enumerate(["A", "B", "C"]):
        if f"num_{team_letter}" not in st.session_state:
            st.session_state[f"num_{team_letter}"] = 1
            
        with cols[idx]:
            st.subheader(f"チーム {team_letter}")
            num_mons = st.number_input(f"チーム{team_letter}のモンスター数", min_value=1, max_value=4, key=f"num_{team_letter}")
            
            for i in range(num_mons):
                if f"lv_{team_letter}_{i}" not in st.session_state:
                    st.session_state[f"lv_{team_letter}_{i}"] = 100
                    
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
                lv = st.number_input("レベル", min_value=1, max_value=1100, step=1, key=f"lv_{team_letter}_{i}")
                
                # We instantiate and add right away, but prevent duplicates
                is_duplicate = any(existing_m.no == sel_no for existing_m in teams_dict[team_letter])
                if is_duplicate:
                    st.warning(f"同じチームに同じモンスター（{sel_m}）を複数入れることはできません。別の種類を選んでください。")
                else:
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
            # Softer, natural drop shadow for readability on light backgrounds
            outline = "text-shadow: 1px 1px 3px rgba(0,0,0,0.9), 0px 0px 2px rgba(0,0,0,0.7);"
            name_display = f"<span style='color:#DDA0DD; {outline}'>{m.name}</span>" if m.m_type == "魔法" else f"<span style='color:white; {outline}'>{m.name}</span>"
            st.markdown(f"- **Lv.{m.level:,} {name_display}** ({range_str}/{m.m_type} | {stats_str})", unsafe_allow_html=True)

# Bet and Speed
st.write("---")
col_bet, col_speed = st.columns(2)
with col_bet:
    bet = st.selectbox("賭けるチームを選んでください", ["A", "B", "C"])
with col_speed:
    speed_option = st.selectbox("観戦スピード", ["通常 (1.0x)", "ゆっくり (0.5x)", "スローモーション (0.25x)"])
    
speed_multiplier = 1.0
if "0.5x" in speed_option:
    speed_multiplier = 0.5
elif "0.25x" in speed_option:
    speed_multiplier = 0.25

# Execution
col1, col2, col3 = st.columns(3)
with col1:
    start_battle = st.button("💬 バトル開始！ (文字ログ中心)", type="primary")
with col2:
    visual_battle = st.button("🗺️ 盤面で観戦 (ビジュアルモード)", type="primary")
with col3:
    skip_battle = st.button("⏩ 即座に結果を見る (スキップ)", type="secondary")

if start_battle or visual_battle or skip_battle:
    
    st.write("---")
    
    # Countdown limits if live
    if start_battle or visual_battle:
        countdown_container = st.empty()
        for i in [3, 2, 1]:
            countdown_container.markdown(f"<h1 style='text-align: center; font-size: 80px;'>{i}</h1>", unsafe_allow_html=True)
            time.sleep(1)
        countdown_container.empty()
        st.toast("バトルスタート！", icon="⚔️")
    else:
        st.toast("シミュレーションを高速処理中...", icon="⏩")

    
    # これを盤面タイトルよりさらに上に配置し、スクロールの目標地点にする
    st.markdown("<div id='battle-board-anchor' style='height: 50px;'></div>", unsafe_allow_html=True)
    
    st.markdown("#### 🏁 バトルログ")
    
    # --- Auto-Scroll script (More robust version for Streamlit iframe) ---
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
            setTimeout(function() {
                var parentDoc = window.parent.document;
                
                // Streamlitの実際のスクロール可能コンテナを探す
                var scrollContainer = parentDoc.querySelector('[data-testid="stMain"]') || 
                                      parentDoc.querySelector('[data-testid="stAppViewContainer"]') || 
                                      parentDoc.querySelector('.main') || 
                                      parentDoc.body;
                                      
                // 対象のアンカーへスクロール
                var target = parentDoc.getElementById("battle-board-anchor");
                if (target && scrollContainer) {
                    // targetのトップ座標 - 画面上部から少し余裕を持たせる（100px）
                    var targetRect = target.getBoundingClientRect();
                    var containerRect = scrollContainer.getBoundingClientRect();
                    var scrollPos = scrollContainer.scrollTop + (targetRect.top - containerRect.top) - 80;
                    
                    scrollContainer.scrollTo({top: scrollPos, behavior: 'smooth'});
                } else if (target) {
                    target.scrollIntoView({behavior: "smooth", block: "start"});
                } else {
                    // 見つからない場合はコンテナを一番下へ
                    if (scrollContainer) {
                        scrollContainer.scrollTo({top: scrollContainer.scrollHeight, behavior: 'smooth'});
                    } else {
                        window.parent.window.scrollTo({top: parentDoc.body.scrollHeight, behavior: 'smooth'});
                    }
                }
            }, 100); // 描画直後に実行
        </script>
        """,
        height=0
    )
    
    import copy
    
    battle_teams = {"A": [], "B": [], "C": []}
    all_placed = []
    
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
            # Scatter coordinates slightly more and prevent overlapping
            for _ in range(100):
                nx = base_x + random.randint(-350, 350)
                ny = base_y + random.randint(-350, 350)
                
                # Keep within bounds (0-1000)
                nx = max(50, min(950, nx))
                ny = max(50, min(950, ny))
                
                overlap = False
                for placed_m in all_placed:
                    dist = math.hypot(nx - placed_m.x, ny - placed_m.y)
                    if dist < 80.0:
                        overlap = True
                        break
                
                if not overlap:
                    new_m.x = nx
                    new_m.y = ny
                    break
            else:
                new_m.x = nx
                new_m.y = ny
                
            battle_teams[t_name].append(new_m)
            all_placed.append(new_m)
            
    # Check if teams are valid before starting
    has_empty_team = any(len(t) == 0 for t in battle_teams.values())
    if has_empty_team and mode == "手動選出":
         st.error("エラー：重複によりモンスターが0体になっているチームがあります。重複を解消してください。")
         st.stop()
         
    field = Field(battle_teams)
    
    if visual_battle:
        board_container = st.empty()
        
    def render_board_html(monsters):
        # 1000x1000の仮想座標を%に変換して描画
        # 背景の土色を少し暗くし、すべて円形から角丸の正方形に変更
        board_html = (
            '<div style="position: relative; width: 100%; max-width: 800px; aspect-ratio: 1; '
            'background: radial-gradient(circle at center, #B8906B 20%, #8B4513 60%, #654321 100%); '
            'border: 8px solid #4A3326; '
            'box-shadow: inset 0 0 50px rgba(0,0,0,0.8), 0 0 20px rgba(0,0,0,0.5); '
            'margin: auto; overflow: hidden; border-radius: 10px;">'
            '<!-- 闘技場の内側の枠線 -->'
            '<div style="position: absolute; top: 2%; left: 2%; width: 96%; height: 96%; '
            'border: 2px dashed rgba(255,255,255,0.2); border-radius: 6px; pointer-events: none;"></div>'
            '<!-- 中央の高い質感の石タイル -->'
            '<div style="position: absolute; top: 30%; left: 30%; width: 40%; height: 40%; '
            'background-color: #696969; '
            'background-image: '
            'linear-gradient(335deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0) 80%), '
            'radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.2) 100%), '
            'linear-gradient(90deg, transparent 48px, rgba(0,0,0,0.3) 48px, rgba(0,0,0,0.3) 50px, transparent 50px), '
            'linear-gradient(0deg, transparent 48px, rgba(0,0,0,0.3) 48px, rgba(0,0,0,0.3) 50px, transparent 50px); '
            'background-size: 100% 100%, 100% 100%, 50px 50px, 50px 50px; '
            'border: 6px solid #4f4f4f; '
            'border-radius: 8px; '
            'box-shadow: inset 0 0 20px rgba(0,0,0,0.7), 0 0 30px rgba(0,0,0,0.4); '
            'pointer-events: none; opacity: 0.9;"></div>'
        )
        for m in monsters:
            opacity = "0" if m.is_dead else "1"
            pointer_ev = "none" if m.is_dead else "auto"
            
            x_pct = min(max((m.x) / 1000.0 * 100, 0), 100)
            y_pct = min(max((m.y) / 1000.0 * 100, 0), 100)
            
            color = team_colors_hex.get(m.team, "#FFFFFF")
            icon = "🗡️" if m.m_type == "物理" else "🎇"
            board_html += f'<div style="position: absolute; left: {x_pct}%; top: {y_pct}%; transform: translate(-50%, -50%); text-align: center; transition: left 0.1s linear, top 0.1s linear; opacity: {opacity}; pointer-events: {pointer_ev};">'
            board_html += f'<div style="font-size: 24px; text-shadow: 0 0 5px black;">{icon}</div>'
            board_html += f'<div style="background-color: {color}; color: white; padding: 2px 4px; border-radius: 4px; font-size: 10px; white-space: nowrap; border: 1px solid white; box-shadow: 1px 1px 3px rgba(0,0,0,0.5);">'
            board_html += f'{m.name}<br>{max(0, m.hp)}'
            board_html += '</div></div>'
        board_html += '</div>'
        return board_html

    log_container = st.empty()
    status_container = st.empty()
    
    all_logs = []
    
    # Run Simulation Loop
    DELTA_TIME = 0.02   # 0.02秒刻み（高速攻撃の精度を確保）
    BATTLE_DURATION = 40.0  # 現実時間（およびシミュ内時間）での40秒制限
    
    # ====== 初期の盤面とステータスを2秒間表示（非戦闘状態で配置確認） ======
    if not skip_battle:
        if visual_battle:
            board_container.markdown(render_board_html(field.monsters), unsafe_allow_html=True)
            
        status_text = f"<h4>🏁 バトル開始直前... 配置確認中</h4><br>"
        for m in field.monsters:
            m_color = team_colors_hex[m.team]
            state = f"❤️ {m.hp:,}/{m.max_hp:,}"
            status_text += f"<span style='color:{m_color};'>[{m.team}] Lv.{m.level:,} {m.name}</span> : {state} (x:{m.x:.0f}, y:{m.y:.0f})<br>"
        status_container.markdown(status_text, unsafe_allow_html=True)
        
        time.sleep(2.0) # 2秒間の配置確認タイム
    # =========================================================================

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
        elapsed_sim_time = field.time_elapsed  # Needed by the final status display block
        
    else:
        # Live battle viewer
        is_timeout = False
        last_progress_time = 0.0
        while not field.is_finished():
            current_real_time = time.time()
            elapsed_real_time = current_real_time - start_time
            elapsed_sim_time = elapsed_real_time * speed_multiplier
            
            if elapsed_sim_time >= BATTLE_DURATION:
                is_timeout = True
                break
                
            # Update progress bar based on simulation time
            if elapsed_real_time - last_progress_time >= 0.1:
                last_progress_time = elapsed_real_time
                p = min(1.0, elapsed_sim_time / BATTLE_DURATION)
                progress_bar.progress(p)
                
                # 盤面の更新 (10FPS)
                if visual_battle:
                    board_container.markdown(render_board_html(field.monsters), unsafe_allow_html=True)
            
            # Run simulation steps catch-up using simulation time factor
            new_logs_this_frame = []
            while field.time_elapsed < elapsed_sim_time:
                # バトル終了条件を満たしたらキャッチアップループを即座に抜ける（無限ループ防止）
                if field.is_finished():
                    break
                    
                logs = field.step(delta_time=DELTA_TIME)
                if logs:
                    new_logs_this_frame.extend(logs)
                
            # Colorize logs and accumulate
            if new_logs_this_frame:
                colored_logs = []
                for log in new_logs_this_frame:
                    for t, c in team_colors_hex.items():
                        log = log.replace(f"チーム{t}", colored_text(f"チーム{t}", c))
                    colored_logs.append(log)
                all_logs.extend(colored_logs)
            
            # Draw status every 1.0 second of real time (Throttling ST markdown updates)
            if elapsed_real_time - last_display_time >= 1.0:
                last_display_time = elapsed_real_time
                
                # Update visual logs (Only once a second to prevent UI freeze from evade spam)
                if all_logs:
                    display_logs = "\n".join(all_logs[-15:]) # 最新15行を表示
                    log_container.markdown(f"<div style='height: 200px; overflow-y: scroll; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background: #262730; color: white;'>{display_logs.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

                # Update visual stats
                time_left = BATTLE_DURATION - elapsed_sim_time
                time_color = "red" if time_left <= 10 else "white"
                status_text = f"<h4 style='color:{time_color}'>⏳ 残り時間: {max(0, time_left):.1f}s</h4><br>"
                
                for m in field.monsters:
                    m_color = team_colors_hex[m.team]
                    state = "💀" if m.is_dead else f"❤️ {m.hp:,}/{m.max_hp:,}"
                    status_text += f"<span style='color:{m_color};'>[{m.team}] Lv.{m.level:,} {m.name}</span> : {state} (x:{m.x:.0f}, y:{m.y:.0f})<br>"
                status_container.markdown(status_text, unsafe_allow_html=True)
                
            # Small sleep to prevent freezing the browser/app
            time.sleep(0.01)
            
    # ====== FINAL RENDER (Ensure last hits and surviving team HP are shown) ======
    if visual_battle:
        board_container.markdown(render_board_html(field.monsters), unsafe_allow_html=True)

    if all_logs:
        display_logs = "\n".join(all_logs[-15:])
        log_container.markdown(f"<div style='height: 200px; overflow-y: scroll; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background: #262730; color: white;'>{display_logs.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

    time_left = BATTLE_DURATION - elapsed_sim_time
    time_color = "red" if time_left <= 10 else "white"
    status_text = f"<h4 style='color:{time_color}'>⏳ 残り時間: {max(0, time_left):.1f}s (決着)</h4><br>"
    for m in field.monsters:
        m_color = team_colors_hex[m.team]
        state = "💀" if m.is_dead else f"❤️ {m.hp:,}/{m.max_hp:,}"
        status_text += f"<span style='color:{m_color};'>[{m.team}] Lv.{m.level:,} {m.name}</span> : {state} (x:{m.x:.0f}, y:{m.y:.0f})<br>"
    status_container.markdown(status_text, unsafe_allow_html=True)
    # ==============================================================================

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
