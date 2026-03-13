import math
import random

class Monster:
    def __init__(self, t_name, base_data, level=1):
        self.team = t_name # A, B, or C
        self.no = base_data['NO.']
        self.name = base_data['ペット名']
        self.element = base_data['属性']
        self.m_type = base_data['物魔'] # 物理 or 魔法
        self.range_type = base_data['レンジ'] if 'レンジ' in base_data else '近接'
        self.level = level
        
        # Calculate stats
        lv_multiplier = 1 + (self.level - 1) * 0.1
        self.vit = math.floor(base_data['VIT'] * lv_multiplier)
        self.hp = math.floor(self.vit * 18 + 100)
        self.max_hp = self.hp
        
        self.spd = math.floor(base_data['SPD'] * lv_multiplier)
        self.atk = math.floor(base_data['ATK'] * lv_multiplier)
        self.int_stat = math.floor(base_data['INT'] * lv_multiplier)
        
        base_def = math.floor(base_data['DEF'] * lv_multiplier)
        base_mdef = math.floor(base_data['MDEF'] * lv_multiplier)
        self.defense = math.floor(base_def + base_mdef / 10)
        self.mdefense = math.floor(base_mdef + base_def / 10)
        
        self.luck = math.floor(base_data['LUCK'] * lv_multiplier)
        self.mov = math.floor(base_data['MOV']) # Fixed value
        
        # Battle states
        self.x = 0.0
        self.y = 0.0
        self.cooldown = 0.0
        self.is_dead = False
        
        # Attack speed and range logic
        self.attack_interval, self.multi_hit, self.ultra_stages = self._calculate_attack_speed()
        
        # デフォルト射程の設定
        self.attack_range = 30.0 if self.range_type == "近接" else 150.0
        
        # 外部ファイルからの個別攻撃範囲の上書き（UI表示タイプとは独立して計算に使用）
        import json
        import os
        try:
            # 毎回読み込むと重いので、クラス変数等でキャッシュするのが理想ですが、
            # まずはシンプルに読み込み処理を入れます
            range_file = os.path.join(os.path.dirname(__file__), 'attack_range.json')
            if os.path.exists(range_file):
                with open(range_file, 'r', encoding='utf-8') as f:
                    ranges = json.load(f)
                    if self.name in ranges:
                        self.attack_range = float(ranges[self.name])
        except Exception as e:
            pass # jsonエラー等は無視してデフォルト値を使う
        
        # Target lock
        self.current_target = None

    def _calculate_attack_speed(self):
        # returns (interval_seconds, max_hits_per_interval)
        # Based on user data: SPD -> Attacks per Second
        points = [
            (0, 1.0),
            (100, 1.5),
            (200, 2.0),
            (300, 2.5),
            (400, 3.0),
            (500, 3.5),
            (600, 4.0),
            (700, 4.5),
            (800, 5.0),
            (3000, 20.0)
        ]
        
        # Calculate interpolated atk_spd
        if self.spd <= 0:
            atk_spd = 1.0
        elif self.spd >= 3000:
            # 3000以上は従来通りさらに多段ヒット強化
            base_hits = 20.0
            extra_multiplier = 1.0
            if self.spd >= 100000:
                extra_multiplier = 5.0
            elif self.spd >= 30000:
                extra_multiplier = 4.0
            elif self.spd >= 10000:
                extra_multiplier = 3.0
            elif self.spd >= 3001:
                extra_multiplier = 2.0
            atk_spd = base_hits * extra_multiplier
        else:
            # Piecewise linear interpolation (smooth curve approximation)
            atk_spd = 1.0
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i+1]
                if x1 <= self.spd <= x2:
                    # Linear interpolation
                    atk_spd = y1 + ((self.spd - x1) / (x2 - x1)) * (y2 - y1)
                    break
                    
        # 秒間攻撃回数を切り捨てで整数化（例: 1.7回/s → 1回, 2.0回/s → 2回）
        # SPD >= 3000 の場合、ベースは常に20回/s、超高速倍率は「段数」として分離
        if self.spd >= 3000:
            base_hits_per_second = 20
            # 超高速域の段数 (1～5)
            if self.spd >= 100000:
                ultra_stages = 5
            elif self.spd >= 30000:
                ultra_stages = 4
            elif self.spd >= 10000:
                ultra_stages = 3
            elif self.spd >= 3001:
                ultra_stages = 2
            else:
                ultra_stages = 1  # SPDがちょうど3000
        else:
            base_hits_per_second = max(1, int(atk_spd))
            ultra_stages = 1
        
        # アニメーション用のインターバルとヒット数
        if base_hits_per_second <= 4:
            # 4回/s以下は1回ずつ攻撃
            interval = 1.0 / base_hits_per_second
            base_multi_hit = 1
        else:
            # 5回/s以上は0.25s間隔でまとめて攻撃
            interval = 0.25
            actions_per_second = 4  # 1.0 / 0.25
            base_multi_hit = max(1, round(base_hits_per_second / actions_per_second))
            
        return interval, base_multi_hit, ultra_stages

    def distance_to(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)

    def move_towards(self, target, delta_time):
        if self.mov == 0:
            speed = 10.0 # Set tiny baseline to 10.0
        else:
            speed = 80.0 * (1 + self.mov * 0.10) # Set MOV scaling per point to 10%

        dist = self.distance_to(target)
        if dist > self.attack_range:
            step = speed * delta_time
            
            # 射程距離にピッタリ収まるように進む距離を調整（jitter & teleport 防止）
            if dist - step < self.attack_range:
                step = dist - self.attack_range
                
            # 直線距離が0になる異常事態を防ぐ
            safe_dist = max(0.001, dist)
            dx = (target.x - self.x) / safe_dist
            dy = (target.y - self.y) / safe_dist
            
            self.x += dx * step
            self.y += dy * step
            
    def attack(self, target):
        """攻撃を計算し、結果を返す（ダメージはまだ適用しない＝同時解決用）"""
        self.cooldown = self.attack_interval
        
        logs = []
        total_damage = 0
        
        # Accuracy: 命中率を算出（各ヒットで個別判定する）
        hit_chance = 1.0
        luck_ratio = target.luck / max(1, self.luck)
        
        # Piercewise linear interpolation for hit chance based on new data
        points = [
            (1.0, 0.99),
            (2.0, 0.434),
            (3.0, 0.046),
            (3.45, 0.023),
            (3.69, 0.021),
            (3.78, 0.019),
            (3.9, 0.0147),
            (4.0, 0.01)
        ]
        
        if luck_ratio >= 4.0:
            hit_chance = 0.01
        elif luck_ratio <= 1.0:
            hit_chance = 0.99
        else:
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i+1]
                if x1 <= luck_ratio <= x2:
                    hit_chance = y1 + ((luck_ratio - x1) / (x2 - x1)) * (y2 - y1)
                    break

        # Damage calculation
        # Elemental multiplier
        element_mult = 1.0
        attr = self.element
        t_attr = target.element
        if attr == '火':
            if t_attr == '木': element_mult = 1.2
            elif t_attr == '水': element_mult = 0.8
        elif attr == '水':
            if t_attr == '火': element_mult = 1.2
            elif t_attr == '木': element_mult = 0.8
        elif attr == '木':
            if t_attr == '水': element_mult = 1.2
            elif t_attr == '火': element_mult = 0.8
        elif attr == '光':
            if t_attr == '闇': element_mult = 1.2
            elif t_attr == '光': element_mult = 0.8
        elif attr == '闇':
            if t_attr == '光': element_mult = 1.2
            elif t_attr == '闇': element_mult = 0.8
            
        # Base raw stat vs Defense
        if self.m_type == '物理':
            base_dmg = (self.atk * 1.75) - target.defense
        else:
            base_dmg = (self.int_stat * 1.75) - target.mdefense
            
        if base_dmg < 0:
            base_dmg = 0
            
        # x4 multiplier
        base_dmg *= 4.0
        
        # RNG variance 0.9 ~ 1.1
        rng_mult = random.uniform(0.9, 1.1)
        
        # Critical hit check
        crit_mult = 1.0
        is_crit = False
        luck_diff_ratio = abs(self.luck - target.luck) / max(1, max(self.luck, target.luck))
        
        if luck_diff_ratio <= 0.2:
            if random.random() < 0.05:
                is_crit = True
                crit_mult = 2.5
                
        final_dmg_float = base_dmg * element_mult * rng_mult * crit_mult
        dmg = math.floor(final_dmg_float)
        
        if dmg <= 0:
            dmg = 1
            
        # 秒間攻撃回数分（multi_hit）の各攻撃ごとに命中判定を個別に行う
        hits_landed = 0
        for _ in range(self.multi_hit):
            if random.random() < hit_chance:
                hits_landed += 1
        
        # 命中した攻撃のダメージ合計に、段数ボーナスを掛ける
        base_damage = dmg * hits_landed
        total_damage = base_damage * self.ultra_stages
        
        crit_text = "【クリティカル！】" if is_crit else ""
        if hits_landed == 0:
            # 全弾回避
            hit_pct = hit_chance * 100
            logs.append(f"{self.name} の攻撃は {target.name} に回避された！ (命中率{hit_pct:.1f}%)")
        elif self.ultra_stages > 1:
            # SPD >= 3001: 段数ボーナスあり → "ダメージ×段数段=総ダメージ" 形式
            logs.append(f"{self.name} は {target.name} に {crit_text}{base_damage:,}×{self.ultra_stages}段={total_damage:,} のダメージ！")
        else:
            # SPD < 3000: 段数表記なし
            logs.append(f"{self.name} は {target.name} に {crit_text}{total_damage:,} のダメージ！")
            
        return {'target': target, 'total_damage': total_damage, 'logs': logs}

class Field:
    def __init__(self, teams):
        self.teams = teams  # dict of lists e.g. {'A': [monsters], 'B': [monsters], 'C': [monsters]}
        self.monsters = []
        for team, mons in self.teams.items():
            for i, m in enumerate(mons):
                self.monsters.append(m)
                
        self.time_elapsed = 0.0

    def step(self, delta_time=0.1):
        """同時解決型のステップ処理：全モンスターが同時に行動する"""
        logs = []
        if self.is_finished():
            return logs
            
        self.time_elapsed += delta_time
        
        living_monsters = [m for m in self.monsters if not m.is_dead]
        living_monsters.sort(key=lambda x: x.spd, reverse=True)
        
        # ===== Phase 1: 移動フェーズ =====
        # まず全モンスターのターゲット選定と移動先を確定させる
        for m in living_monsters:
            # ターゲットが死んだか、未設定なら新しいターゲットを探す
            if m.current_target is None or getattr(m.current_target, 'is_dead', True):
                nearest_enemy = None
                min_dist = float('inf')
                
                for enemy in living_monsters:
                    if enemy.team == m.team or m == enemy:
                        continue
                    dist = m.distance_to(enemy)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_enemy = enemy
                        
                m.current_target = nearest_enemy
                
            if not m.current_target:
                continue
                
            m.cooldown -= delta_time
            
            # ロックオンしたターゲットとの距離を測る
            dist = m.distance_to(m.current_target)
            
            # 射程外なら接近する
            if dist > m.attack_range:
                m.move_towards(m.current_target, delta_time)
                
        # ===== Phase 2: 攻撃フェーズ =====
        # 全員が移動を終えた後の「最終的な距離」をもとに攻撃判定を行う
        pending_attacks = []
        for m in living_monsters:
            if not m.current_target or getattr(m.current_target, 'is_dead', True):
                continue
                
            # 移動後の最新座標でロックオンしたターゲットとの距離を再計算
            dist = m.distance_to(m.current_target)
            
            # ターゲットが同じステップ内で移動した分を補正するバッファ
            # （追いかけ中に射程ギリギリでターゲットが逃げるのを防ぐ）
            t = m.current_target
            if t.mov == 0:
                target_speed = 10.0
            else:
                target_speed = 80.0 * (1 + t.mov * 0.10)
            chase_buffer = target_speed * delta_time
                
            # 射程内（＋追撃バッファ）で、かつクールダウン完了なら攻撃
            if dist <= m.attack_range + chase_buffer and m.cooldown <= 0:
                attack_result = m.attack(m.current_target)
                pending_attacks.append(attack_result)
        
        # ===== Phase 3: 全ダメージを一括適用 =====
        for result in pending_attacks:
            logs.extend(result['logs'])
            result['target'].hp -= result['total_damage']
        
        # ===== Phase 4: 戦闘不能判定 =====
        for m in living_monsters:
            if m.hp <= 0 and not m.is_dead:
                m.is_dead = True
                logs.append(f"{m.name} は倒れた！")
                
        return logs
        
    def is_finished(self):
        alive_teams = set()
        for m in self.monsters:
            if not m.is_dead:
                alive_teams.add(m.team)
        return len(alive_teams) <= 1
        
    def _get_team_avg_hp_percentage(self, team_name):
        team_mons = [m for m in self.monsters if m.team == team_name]
        if not team_mons:
            return 0.0
        # Calculate the average of each alive monster's HP percentage
        total_percentage = 0.0
        alive_count = 0
        for m in team_mons:
            if not m.is_dead:
                # 0.0 to 1.0 representation
                total_percentage += (m.hp / m.max_hp)
                alive_count += 1
        return total_percentage / len(team_mons) if len(team_mons) > 0 else 0.0
        
    def _get_team_avg_level(self, team_name):
        team_mons = [m for m in self.monsters if m.team == team_name]
        if not team_mons:
            return 0
        return sum(m.level for m in team_mons) / len(team_mons)
        
    def get_winner(self):
        # Gather alive teams
        alive_teams = set(m.team for m in self.monsters if not m.is_dead)
        
        # 1. Annihilation: Only one team remains
        if len(alive_teams) == 1:
            return list(alive_teams)[0]
            
        # If no teams alive (everyone died at the same time, rare but possible)
        if len(alive_teams) == 0:
            alive_teams = set(self.teams.keys())
            
        # Tie breakers for timeout or multiple alive teams
        # 2. Average Remaining HP Percentage
        best_hp_pct = -1.0
        hp_candidates = []
        for t in alive_teams:
            thp_pct = self._get_team_avg_hp_percentage(t)
            # Compare using a small tolerance for floats
            if thp_pct > best_hp_pct + 0.0001:
                best_hp_pct = thp_pct
                hp_candidates = [t]
            elif abs(thp_pct - best_hp_pct) <= 0.0001:
                hp_candidates.append(t)
                
        if len(hp_candidates) == 1:
            return hp_candidates[0]
            
        # 3. Lowest Average Level (among those tied for HP Pct)
        lowest_lv = float('inf')
        lv_candidates = []
        for t in hp_candidates:
            avg_lv = self._get_team_avg_level(t)
            if avg_lv < lowest_lv:
                lowest_lv = avg_lv
                lv_candidates = [t]
            elif avg_lv == lowest_lv:
                lv_candidates.append(t)
                
        # If still tied, just return the first one or "Draw"
        if len(lv_candidates) >= 1:
            return lv_candidates[0]
        return "Draw"
