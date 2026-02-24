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
        lv_multiplier = 1 + self.level * 0.1
        self.vit = int(base_data['VIT'] * lv_multiplier)
        self.hp = self.vit * 18 + 100
        self.max_hp = self.hp
        
        self.spd = int(base_data['SPD'] * lv_multiplier)
        self.atk = int(base_data['ATK'] * lv_multiplier)
        self.int_stat = int(base_data['INT'] * lv_multiplier)
        
        base_def = int(base_data['DEF'] * lv_multiplier)
        base_mdef = int(base_data['MDEF'] * lv_multiplier)
        self.defense = int(base_def + base_mdef / 10)
        self.mdefense = int(base_mdef + base_def / 10)
        
        self.luck = int(base_data['LUCK'] * lv_multiplier)
        self.mov = int(base_data['MOV']) # Fixed value
        
        # Battle states
        self.x = 0.0
        self.y = 0.0
        self.cooldown = 0.0
        self.is_dead = False
        
        # Attack speed logic
        self.attack_interval, self.multi_hit = self._calculate_attack_speed()
        self.attack_range = 30.0 if self.range_type == "近接" else 100.0
        
        # Target lock
        self.current_target = None

    def _calculate_attack_speed(self):
        # returns (interval_seconds, max_hits)
        hits = 1
        if self.spd >= 100000:
            hits = 5
            atk_spd = 20.0
        elif self.spd >= 30000:
            hits = 4
            atk_spd = 20.0
        elif self.spd >= 10000:
            hits = 3
            atk_spd = 20.0
        elif self.spd >= 3001:
            hits = 2
            atk_spd = 20.0
        else:
            # 1 to 3000 -> scales to 20 attacks per second
            spd_clamped = max(1, self.spd)
            atk_spd = (spd_clamped / 3000.0) * 20.0
            
        interval = max(0.05, 1.0 / atk_spd) if atk_spd > 0 else 1.0
        return interval, hits

    def distance_to(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)

    def move_towards(self, target, delta_time):
        if self.mov == 0:
            speed = 10.0 # Reduced from 25.0
        else:
            speed = 70.0 * (1 + self.mov * 0.15) # Reduced from 120.0

        dist = self.distance_to(target)
        if dist > self.attack_range:
            step = speed * delta_time
            if step > dist - self.attack_range:
                # 浮動小数点の誤差対策: ピタリと止まると誤差で「射程外」判定になるため 0.1 だけ食い込ませる
                step = (dist - self.attack_range) + 0.1
                
            # Prevent division by zero if they are exactly on top of each other
            safe_dist = max(1.0, dist)
            dx = (target.x - self.x) / safe_dist
            dy = (target.y - self.y) / safe_dist
            
            # If they are exactly on the same spot, just move them slightly apart
            if dist == 0:
                dx, dy = 1.0, 0.0
                
            self.x += dx * step
            self.y += dy * step
            
    def attack(self, target):
        """攻撃を計算し、結果を返す（ダメージはまだ適用しない＝同時解決用）"""
        self.cooldown = self.attack_interval
        
        logs = []
        total_damage = 0
        for hit in range(self.multi_hit):
            # Accuracy check
            hit_chance = 1.0
            luck_ratio = target.luck / max(1, self.luck)
            
            if luck_ratio >= 3.0:
                hit_chance = 0.01
            elif luck_ratio <= 0.5:
                hit_chance = 0.99
            else:
                # Linear scale between 0.5 (99%) and 3.0 (1%)
                # x goes from 0.5 to 3.0 (span 2.5)
                # y goes from 0.99 down to 0.01
                hit_chance = 0.99 - ((luck_ratio - 0.5) / 2.5) * 0.98

            if random.random() > hit_chance:
                logs.append(f"{self.name} の攻撃は {target.name} に回避された！")
                continue
                
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
            elif attr == '光' and t_attr == '闇':
                element_mult = 1.2
            elif attr == '闇' and t_attr == '光':
                element_mult = 1.2
                
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
            
            if luck_diff_ratio <= 0.2: # within 20%
                if random.random() < 0.05: # 5% chance
                    is_crit = True
                    crit_mult = 2.5
                    
            final_dmg_float = base_dmg * element_mult * rng_mult * crit_mult
            dmg = int(final_dmg_float)
            
            if dmg <= 0:
                dmg = 1
                
            total_damage += dmg
            
            crit_text = "【クリティカル！】" if is_crit else ""
            logs.append(f"{self.name} は {target.name} に {crit_text}{dmg} のダメージ！")
                
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
            if m.current_target is None or m.current_target.is_dead:
                nearest_enemy = None
                min_dist = float('inf')
                
                for enemy in living_monsters:
                    if enemy.team == m.team:
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
            
            # 射程外なら常に接近する（浮動小数点の誤差を考慮し +0.1 のバッファ）
            if dist > m.attack_range + 0.1:
                m.move_towards(m.current_target, delta_time)
                
        # ===== Phase 2: 攻撃フェーズ =====
        # 全員が移動を終えた後の「最終的な距離」をもとに攻撃判定を行う
        pending_attacks = []
        for m in living_monsters:
            if not m.current_target or m.current_target.is_dead:
                continue
                
            # 移動後の最新座標でロックオンしたターゲットとの距離を再計算
            dist = m.distance_to(m.current_target)
                
            # 新しい距離が射程内で、かつクールダウンが完了していれば攻撃
            # ※浮動小数点演算の誤差を許容するため +0.1 のバッファを設ける
            if dist <= m.attack_range + 0.1 and m.cooldown <= 0:
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
