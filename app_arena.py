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

# Hit Counter Badge (Tracking starts automatically based on the URL)
badge_url = "https://hits.sh/onceworld-arena.streamlit.app.svg?color=10b500"
st.markdown(f'<img src="{badge_url}" alt="Hits">', unsafe_allow_html=True)
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
    # 属性フィルタの定義（モバイル用に短縮）
    element_filters = {
        "全": None,
        "🔥": "火",
        "💧": "水",
        "🌿": "木",
        "✨": "光",
        "🌑": "闇",
    }
    
    # 漢字名へのよみがなマッピング（外部JSONから読み込み）
    import json
    kana_mapping = {}
    try:
        with open("kana_mapping.json", "r", encoding="utf-8") as f:
            kana_mapping = json.load(f)
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as e:
        st.error(f"⚠️ `kana_mapping.json` の書式にエラーがあります（カンマの抜け等）。修正してください。\nエラー内容: {e}")
        
    # 攻撃範囲（battle_logic.py側で使う）のJSONエラーも手動選出画面で検知して警告を出す
    try:
        with open("attack_range.json", "r", encoding="utf-8") as f:
            json.load(f)
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as e:
        st.error(f"⚠️ `attack_range.json` の書式にエラーがあります（カンマの抜け等）。修正してください。\nエラー内容: {e}")
    
    # ひらがな⇔カタカナ変換ヘルパー
    def to_katakana(text):
        return "".join(chr(ord(c) + 96) if 'ぁ' <= c <= 'ゖ' else c for c in text)
    def to_hiragana(text):
        return "".join(chr(ord(c) - 96) if 'ァ' <= c <= 'ヶ' else c for c in text)
    
    def fuzzy_match(search_term, option_text):
        """NO.検索・ひらがな/カタカナあいまい検索・よみがな検索"""
        search_lower = search_term.lower().strip()
        option_lower = option_text.lower()
        
        # 1. そのまま一致
        if search_lower in option_lower:
            return True
            
        # 2. カタカナに変換して検索
        search_kata = to_katakana(search_lower)
        if search_kata in option_lower:
            return True
            
        # 3. ひらがなに変換して検索
        search_hira = to_hiragana(search_lower)
        if search_hira in option_lower:
            return True
            
        # 4. よみがなマッピングによる検索（漢字を含むペット名にヒットさせる）
        # option_text は "NO - ペット名" の形式なので分割する
        parts = option_text.split(" - ")
        if len(parts) > 1:
            pet_name = parts[1]
            # ペット名に部分一致するマッピングを探す
            for kanji, readings in kana_mapping.items():
                if kanji in pet_name:
                    for reading in readings:
                        # 検索語がよみがなに含まれるかチェック
                        if search_lower in reading or search_kata in reading or search_hira in reading:
                            return True
        return False

    # コールバック関数群（ループ外で定義してargsで変数を渡すことでメモリリークや意図しない動作を防ぐ）
    def sync_slider_to_num(s_k, n_k):
        st.session_state[n_k] = st.session_state[s_k]
        
    def sync_num_to_slider(s_k, n_k):
        raw_val = st.session_state[n_k]
        if raw_val < 1:
            st.session_state[n_k] = 1
            st.session_state[s_k] = 1
        elif raw_val > 1100:
            st.session_state[n_k] = 1100
            st.session_state[s_k] = 1100
        else:
            st.session_state[s_k] = raw_val
            # n_k には再代入しない（フロント側の連打ステートが上書きされてカクつくのを防ぐため）

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
                    
                # スロットごとに枠（ボーダー）で囲んで視認性を高める
                with st.container(border=True):
                    st.markdown(f"**🔹 スロット {i+1}**")
                    
                    # 属性フィルタ（スロットごと）
                    filter_key = f"elem_filter_{team_letter}_{i}"
                    if filter_key not in st.session_state:
                        st.session_state[filter_key] = "全"
                        
                    selected_filter = st.radio(
                        "属性", 
                        options=list(element_filters.keys()), 
                        horizontal=True, 
                        key=filter_key,
                        label_visibility="collapsed"
                    )
                    
                    # 属性でフィルタリングされたオプションを生成
                    active_elem = element_filters[selected_filter]
                    if active_elem:
                        filtered_df = df[df['属性'] == active_elem]
                    else:
                        filtered_df = df
                    base_options = filtered_df['NO.'].astype(str) + " - " + filtered_df['ペット名']
                    
                    # 検索ボックス（プレースホルダーを短く）
                    search_term = st.text_input(
                        "検索", 
                        key=f"search_{team_letter}_{i}",
                        placeholder="🔍 名前 or NO. を入力",
                        label_visibility="collapsed"
                    )
                    
                    # Filter options based on fuzzy search
                    filtered_options = list(base_options)
                    if search_term:
                        filtered_options = [opt for opt in base_options if fuzzy_match(search_term, opt)]
                        if not filtered_options:
                            st.caption("⚠️ 該当なし")
                            filtered_options = list(base_options) # fallback if no match
                            
                    sel_m = st.selectbox(
                        "種類", 
                        filtered_options, 
                        key=f"m_{team_letter}_{i}", 
                        label_visibility="collapsed"
                    )
                    
                    # レベル入力（スライダーと数値入力の連動）
                    st.markdown("**🔸 Lv (レベル)**")
                    
                    sl_key = f"lv_slider_{team_letter}_{i}"
                    num_key = f"lv_num_{team_letter}_{i}"
                    
                    # 初期値のセット
                    if sl_key not in st.session_state:
                        st.session_state[sl_key] = 100
                    if num_key not in st.session_state:
                        st.session_state[num_key] = 100
                        
                    # 1. スライドバー
                    st.slider(
                        "レベルスライダー",
                        min_value=1,
                        max_value=1100,
                        step=1,
                        key=sl_key,
                        on_change=sync_slider_to_num,
                        args=(sl_key, num_key),
                        label_visibility="collapsed"
                    )
                    
                    # スライダーの目盛をさりげなく配置
                    st.markdown(
                        """
                        <div style='display: flex; justify-content: space-between; font-size: 0.7em; color: gray; margin-top: -15px; margin-bottom: 5px; padding: 0 5px;'>
                            <span>1</span>
                            <span>550</span>
                            <span>1100</span>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    
                    # 2. 直接数値入力（微調整用）
                    # min_value/max_valueを外すことでエラーブロックを回避し、コールバックで調整する
                    lv = st.number_input(
                        "レベル数値入力", 
                        step=1, 
                        key=num_key,
                        on_change=sync_num_to_slider,
                        args=(sl_key, num_key),
                        label_visibility="collapsed"
                    )
                
                # We instantiate and add right away, but prevent duplicates
                sel_no = int(sel_m.split(" - ")[0])
                lv = st.session_state[num_key]
                is_duplicate = any(existing_m.no == sel_no for existing_m in teams_dict[team_letter])
                if is_duplicate:
                    st.warning(f"⚠️ {sel_m} が重複しています他の種類を選んでください。")
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

# Attribute Colors for faint backgrounds
elem_bg_colors = {
    "火": "rgba(255, 69, 0, 0.15)",   # Orange-Red
    "水": "rgba(30, 144, 255, 0.15)", # Dodger Blue
    "木": "rgba(50, 205, 50, 0.15)",  # Lime Green
    "光": "rgba(255, 215, 0, 0.15)",  # Gold
    "闇": "rgba(138, 43, 226, 0.15)"  # Blue Violet
}
elem_icons = {
    "火": "🔥", "水": "💧", "木": "🌿", "光": "✨", "闇": "🌑"
}

# Display current teams
st.write("---")

# レスポンシブ用CSS: スマホ対応強化
st.markdown("""
<style>
/* スマホ幅での調整 */
@media (max-width: 768px) {
    .spacer-card {
        display: none !important;
    }
    /* スマホなどで画面が狭い時にテキストがはみ出さないように */
    div[data-testid="stMarkdownContainer"] {
        word-wrap: break-word;
    }
}
/* コンテナ全体の横幅はみ出し防止 */
.block-container {
    max-width: 100% !important;
    overflow-x: hidden;
}
</style>
""", unsafe_allow_html=True)
max_team_size = max([len(t) for t in teams_dict.values()] + [0])
all_m = [m for t_list in teams_dict.values() for m in t_list]

if all_m:
    v_hp = [m.hp for m in all_m]
    v_atk = [m.atk if m.m_type == "物理" else m.int_stat for m in all_m]
    v_def = [m.defense for m in all_m]
    v_mdef = [m.mdefense for m in all_m]
    v_luck = [m.luck for m in all_m]
    v_spd = [m.spd for m in all_m]
    v_mov = [m.mov for m in all_m]
    
    MIN_HP, MAX_HP = min(v_hp), max(v_hp)
    MIN_ATK, MAX_ATK = min(v_atk), max(v_atk)
    MIN_DEF, MAX_DEF = min(v_def), max(v_def)
    MIN_MDEF, MAX_MDEF = min(v_mdef), max(v_mdef)
    MIN_LUCK, MAX_LUCK = min(v_luck), max(v_luck)
    MIN_SPD, MAX_SPD = min(v_spd), max(v_spd)
    MIN_MOV, MAX_MOV = min(v_mov), max(v_mov)
else:
    MIN_HP=MAX_HP=MIN_ATK=MAX_ATK=MIN_DEF=MAX_DEF=MIN_MDEF=MAX_MDEF=MIN_LUCK=MAX_LUCK=MIN_SPD=MAX_SPD=MIN_MOV=MAX_MOV=0

def get_pct(val, vmin, vmax):
    if vmax == vmin: return 100
    return max(0, min(100, ((val - vmin) / (vmax - vmin)) * 100))

cols = st.columns(3)
for idx, (t_name, t_list) in enumerate(teams_dict.items()):
    with cols[idx]:
        color = team_colors_hex[t_name]
        st.markdown(f"<h3 style='color:{color};'>🛡️ チーム {t_name}</h3>", unsafe_allow_html=True)
        
        # 1. Card View
        for m in t_list:
            range_icon = "🗡️近接" if getattr(m, 'range_type', '近接') == '近接' else "🏹遠隔"
            type_icon = "⚔️物理" if m.m_type == "物理" else "🎇魔法"
            
            # 属性に応じたテキストカラー設定
            elem_text_colors = {
                "火": "#FF6347", # Tomato
                "水": "#00BFFF", # DeepSkyBlue
                "木": "#32CD32", # LimeGreen
                "光": "#FFD700", # Gold
                "闇": "#BA55D3"  # MediumOrchid
            }
            elem_color = elem_text_colors.get(m.element, "#ccc")
            
            # 魔法型は名前をピンク紫っぽく、物理型は白（少しシャドウをつけて見やすく）
            outline = "text-shadow: 1px 1px 3px rgba(0,0,0,0.9), 0px 0px 2px rgba(0,0,0,0.7);"
            name_display = f"<span style='color:#DDA0DD; {outline} font-size: 1.1em;'>{m.name}</span>" if m.m_type == "魔法" else f"<span style='color:white; {outline} font-size: 1.1em;'>{m.name}</span>"
            name_display += f" <span style='font-size: 0.85em; color: {elem_color}; font-weight: bold;'>({m.element}属性)</span>"

            # 各ステータス行をフォーマット統一（アイコン＋項目名＋英語数値）
            atk_stat = f"ATK: {m.atk:,}" if m.m_type == "物理" else f"INT: {m.int_stat:,}"
            atk_line = f"🗡️攻撃系 {atk_stat} &nbsp;|&nbsp; SPD: {m.spd:,}"
            def_line = f"🛡️防御系 VIT: {m.vit:,} &nbsp;|&nbsp; DEF: {m.defense:,} &nbsp;|&nbsp; MDEF: {m.mdefense:,}"
            luck_line = f"🍀運 LUCK: {m.luck:,}"
            mov_line = f"👟移動 MOV: {m.mov:,}"

            card_html = f"""
            <div style="
                border: 1px solid rgba(255,255,255,0.2); 
                border-radius: 8px; 
                padding: 10px; 
                margin-bottom: 10px;
                background-color: rgba(255,255,255,0.05); /* 背景色は統一 */
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            ">
                <div style="margin-bottom: 5px;">
                    <strong>Lv.{m.level:,}</strong> {name_display}
                </div>
                <div style="font-size: 0.85em; color: #ccc; margin-bottom: 8px;">
                    {range_icon} / {type_icon} &nbsp;|&nbsp; <strong>HP: {m.hp:,}</strong>
                </div>
                <div style="font-size: 0.8em; line-height: 1.4; color: white;">
                    <div>{atk_line}</div>
                    <div>{def_line}</div>
                    <div>{luck_line} &nbsp;|&nbsp; {mov_line}</div>
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            
        # 人数が少ないチームの場合、カードと同じ高さの透明なダミーを置いて高さを揃える
        # スマホ(768px以下)では .spacer-card クラスにより非表示になる
        for _ in range(max_team_size - len(t_list)):
            blank_html = """
            <div class="spacer-card" style="
                border: 1px solid transparent; 
                padding: 10px; 
                margin-bottom: 10px;
                visibility: hidden;
            ">
                <div style="margin-bottom: 5px;">&nbsp;</div>
                <div style="font-size: 0.85em; margin-bottom: 8px;">&nbsp;</div>
                <div style="font-size: 0.8em; line-height: 1.4;">
                    <div>&nbsp;</div><div>&nbsp;</div><div>&nbsp;</div>
                </div>
            </div>
            """
            st.markdown(blank_html, unsafe_allow_html=True)
            
        # 2. Data Table View (Removed from here. Combined below.)

# -------------------------------------------------------------
# 2. Single Data Table View for All Teams
# -------------------------------------------------------------
st.write("---")
if all_m:
    # チーム名もソートできるようにする
    table_html = f"""
    <style>
        .stats-container-all {{
            width: 100%;
            overflow-x: auto;
            padding-bottom: 10px;
        }}
        .sortable-table-all {{
            width: 100%;
            min-width: 700px;
            border-collapse: collapse;
            font-family: sans-serif;
            font-size: 0.85em;
            color: #eeeeee;
            text-align: left;
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
        }}
        .sortable-table-all th {{
            background-color: rgba(255, 255, 255, 0.15);
            color: white;
            padding: 8px;
            border-bottom: 2px solid rgba(255,255,255,0.4);
            cursor: pointer;
            user-select: none;
            font-weight: bold;
            transition: background-color 0.2s;
            text-align: left;
            white-space: nowrap;
        }}
        .sortable-table-all th:hover {{
            background-color: rgba(255, 255, 255, 0.25);
        }}
        .sortable-table-all td {{
            padding: 6px 8px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            vertical-align: middle;
        }}
        .sortable-table-all tr:hover {{
            background-color: rgba(255,255,255,0.1);
        }}
        .bar-bg {{
            width: 100%;
            background-color: rgba(255,255,255,0.1);
            border-radius: 4px;
            height: 8px;
            margin-top: 2px;
            overflow: hidden;
        }}
        .bar-fill {{
            height: 100%;
            border-radius: 4px;
        }}
        .sticky-col {{
            white-space: nowrap; 
            position: sticky; 
            left: 0; 
            background-color: #2b2b2b;
            border-right: 1px solid rgba(255,255,255,0.2); 
            z-index: 5;
            box-shadow: 2px 0 5px rgba(0,0,0,0.3);
        }}
        .sortable-table-all thead .sticky-col {{
            background-color: #333;
            z-index: 6;
        }}
    </style>
    <div class="stats-container-all">
        <table class="sortable-table-all" id="table-all">
            <thead>
                <tr>
                    <th onclick="sortTableAll(0, 'text')">チーム ↕</th>
                    <th class="sticky-col" onclick="sortTableAll(1, 'num')">名前(Lv順) ↕</th>
                    <th onclick="sortTableAll(2, 'num')">HP ↕</th>
                    <th onclick="sortTableAll(3, 'num')">ATK/INT ↕</th>
                    <th onclick="sortTableAll(4, 'num')">SPD ↕</th>
                    <th onclick="sortTableAll(5, 'num')">DEF ↕</th>
                    <th onclick="sortTableAll(6, 'num')">MDEF ↕</th>
                    <th onclick="sortTableAll(7, 'num')">LUCK ↕</th>
                    <th onclick="sortTableAll(8, 'num')">MOV ↕</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for m in all_m:
        atk_val = m.atk if m.m_type == "物理" else m.int_stat
        
        hp_pct = get_pct(m.hp, MIN_HP, MAX_HP)
        atk_pct = get_pct(atk_val, MIN_ATK, MAX_ATK)
        def_pct = get_pct(m.defense, MIN_DEF, MAX_DEF)
        mdef_pct = get_pct(m.mdefense, MIN_MDEF, MAX_MDEF)
        luck_pct = get_pct(m.luck, MIN_LUCK, MAX_LUCK)
        spd_pct = get_pct(m.spd, MIN_SPD, MAX_SPD)
        mov_pct = get_pct(m.mov, MIN_MOV, MAX_MOV)
        
        # 名前の色をチームカラーにする
        name_color = team_colors_hex.get(m.team, "white")
        
        table_html += f"""
                <tr>
                    <td style="font-weight:bold; color:{name_color};" data-value="{m.team}">
                        {m.team}
                    </td>
                    <td class="sticky-col" data-value="{m.level}">
                        <strong style="color: {name_color};">{m.name}</strong><br><span style="font-size: 0.8em; color: #aaa;">Lv.{m.level:,}</span>
                    </td>
                    <td>
                        <div style="color: white;">{m.hp:,}</div>
                        <div class="bar-bg"><div class="bar-fill" style="width: {hp_pct}%; background-color: #2ecc71;"></div></div>
                    </td>
                    <td>
                        <div style="color: #ff9999;">{atk_val:,}</div>
                        <div class="bar-bg"><div class="bar-fill" style="width: {atk_pct}%; background-color: #e74c3c;"></div></div>
                    </td>
                    <td>
                        <div style="color: #ff9999;">{m.spd:,}</div>
                        <div class="bar-bg"><div class="bar-fill" style="width: {spd_pct}%; background-color: #ff6b81;"></div></div>
                    </td>
                    <td>
                        <div style="color: #99ccff;">{m.defense:,}</div>
                        <div class="bar-bg"><div class="bar-fill" style="width: {def_pct}%; background-color: #54a0ff;"></div></div>
                    </td>
                    <td>
                        <div style="color: #99ccff;">{m.mdefense:,}</div>
                        <div class="bar-bg"><div class="bar-fill" style="width: {mdef_pct}%; background-color: #5f27cd;"></div></div>
                    </td>
                    <td>
                        <div style="color: #ffff99;">{m.luck:,}</div>
                        <div class="bar-bg"><div class="bar-fill" style="width: {luck_pct}%; background-color: #f1c40f;"></div></div>
                    </td>
                    <td>
                        <div style="color: #fff;">{m.mov:,}</div>
                        <div class="bar-bg"><div class="bar-fill" style="width: {mov_pct}%; background-color: #1dd1a1;"></div></div>
                    </td>
                </tr>
        """
    
    table_html += """
            </tbody>
        </table>
    </div>
    <script>
    function sortTableAll(colIndex, type) {
        var table = document.getElementById("table-all");
        if (!table) return;
        var tbody = table.tBodies[0];
        var rows = Array.from(tbody.rows);
        
        var header = table.tHead.rows[0].cells[colIndex];
        var currentSort = header.getAttribute('data-sort');
        var nextDirection = (currentSort === 'desc') ? 'asc' : 'desc';
        var isAscending = (nextDirection === 'asc');
        
        var allHeaders = table.tHead.rows[0].cells;
        for (var i = 0; i < allHeaders.length; i++) {
            allHeaders[i].removeAttribute('data-sort');
        }
        
        rows.sort(function(a, b) {
            var cellA, cellB;
            
            if (colIndex === 0 || colIndex === 1) {
                // チーム名やLvは data-value 属性を使用
                cellA = a.cells[colIndex].getAttribute('data-value');
                cellB = b.cells[colIndex].getAttribute('data-value');
                if(colIndex === 1) { // Lvは数値としてソート
                     return isAscending ? cellA - cellB : cellB - cellA;
                }
            } else {
                cellA = a.cells[colIndex].textContent.replace(/\\s+/g, '').replace(/,/g, '');
                cellB = b.cells[colIndex].textContent.replace(/\\s+/g, '').replace(/,/g, '');
            }
            
            if (type === 'num') {
                var matchA = cellA ? cellA.match(/\\d+/) : null;
                var matchB = cellB ? cellB.match(/\\d+/) : null;
                var valA = matchA ? parseFloat(matchA[0]) : 0;
                var valB = matchB ? parseFloat(matchB[0]) : 0;
                return isAscending ? valA - valB : valB - valA;
            } else {
                return isAscending ? cellA.localeCompare(cellB, 'ja') : cellB.localeCompare(cellA, 'ja');
            }
        });
        
        header.setAttribute('data-sort', nextDirection);
        rows.forEach(function(row) { tbody.appendChild(row); });
    }
    </script>
    """
    
    with st.expander("📊 全チーム ステータス一覧 (マッチアップ内偏差)", expanded=False):
        import streamlit.components.v1 as components
        # 全データが含まれるため、あまり長くなりすぎないようmax(900)等で制限すると良い
        estimated_height = min(900, 60 + (len(all_m) * 75) + 40)
        components.html(table_html, height=estimated_height, scrolling=True)

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
                try {
                    var parentDoc = window.parent.document;
                    var target = parentDoc.getElementById("battle-board-anchor");
                    
                    if (target) {
                        // 1. Scroll target into view
                        target.scrollIntoView({behavior: "smooth", block: "start"});
                        
                        // 2. Adjust for Streamlit's sticky header (approx 80px)
                        // By scrolling the main window up slightly after a tiny delay
                        setTimeout(function() {
                            var scrollingElement = parentDoc.scrollingElement || parentDoc.body || parentDoc.documentElement;
                            if (scrollingElement) {
                                // Since we used scrollIntoView('start'), it might be hidden under header.
                                // If the scrollingElement is the window, we can scrollBy
                                parent.window.scrollBy({top: -60, behavior: 'smooth'});
                            }
                        }, 100);
                    }
                } catch (e) {
                    // CORS Error (e.g., Streamlit Community Cloud without custom domain isolation disabled)
                    console.warn("Auto-scroll skipped due to iframe CORS policy:", e);
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
