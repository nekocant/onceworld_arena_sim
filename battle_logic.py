import math
import random
from formulas import *

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
        lv_multiplier = LV_BASE + (self.level - 1) * LV_SCALE
        self.vit = math.floor(base_data['VIT'] * lv_multiplier)
        self.hp = math.floor(self.vit * HP_VIT_COEFFICIENT + HP_BASE)
        self.max_hp = self.hp
        
        self.spd = math.floor(base_data['SPD'] * lv_multiplier)
        self.atk = math.floor(base_data['ATK'] * lv_multiplier)
        self.int_stat = math.floor(base_data['INT'] * lv_multiplier)
        
        base_def = math.floor(base_data['DEF'] * lv_multiplier)
        base_mdef = math.floor(base_data['MDEF'] * lv_multiplier)
        self.defense = math.floor(base_def + base_mdef * DEF_CROSS_RATIO)
        self.mdefense = math.floor(base_mdef + base_def * MDEF_CROSS_RATIO)
        
        self.luck = math.floor(base_data['LUCK'] * lv_multiplier)
        self.mov = math.floor(base_data['MOV']) # Fixed value
        
        # Battle states
        self.x = 0.0
        self.y = 0.0
        self.cooldown = 0.0
        self.is_dead = False
        
        # Attack speed logic
        self.attack_interval, self.multi_hit = self._calculate_attack_speed()
        self.attack_range = RANGE_MELEE if self.range_type == "近接" else RANGE_RANGED
        
        # Target lock
        self.current_target = None

    def _calculate_attack_speed(self):
        # returns (interval_seconds, max_hits_per_interval)
        # Based on user data: SPD -> Attacks per Second
        points = ATK_SPEED_TABLE
        
        # Calculate interpolated atk_spd
        if self.spd <= 0:
            atk_spd = points[0][1]
        elif self.spd >= points[-1][0]:
            # 超高速域の追加倍率
            extra_multiplier = 1.0
            for threshold, mult in ATK_SPEED_ULTRA_TIERS:
                if self.spd >= threshold:
                    extra_multiplier = mult
                    break
            atk_spd = ATK_SPEED_ULTRA_BASE * extra_multiplier
        else:
            # Piecewise linear interpolation (smooth curve approximation)
            atk_spd = points[0][1]
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i+1]
                if x1 <= self.spd <= x2:
                    # Linear interpolation
                    atk_spd = y1 + ((self.spd - x1) / (x2 - x1)) * (y2 - y1)
                    break
                    
        # インターバル（モーション間隔）を自然に細かく分散させる
        interval_raw = 1.0 / atk_spd
        target_interval = min(ATK_INTERVAL_MAX, interval_raw)
        
        # 1回行動あたりの「期待ヒット数」
        hits_per_action = atk_spd * target_interval
        
        base_hits = int(hits_per_action)
        rem = hits_per_action - base_hits
        if random.random() < rem:
            hits = base_hits + 1
        else:
            hits = base_hits
            
        return target_interval, hits

    def distance_to(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)

    def move_towards(self, target, delta_time):
        if self.mov == 0:
            speed = MOV_ZERO_SPEED
        else:
            speed = MOV_BASE_SPEED * (1 + self.mov * MOV_SCALE_PER_POINT)

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
        
        # Accuracy check
        hit_chance = HIT_CHANCE_MAX
        luck_ratio = target.luck / max(1, self.luck)
        
        # Piercewise linear interpolation for hit chance
        points = HIT_CHANCE_TABLE
        
        if luck_ratio >= points[-1][0]:
            hit_chance = HIT_CHANCE_MIN
        elif luck_ratio <= points[0][0]:
            hit_chance = HIT_CHANCE_MAX
        else:
            # Interpolate smoothly between data points
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i+1]
                if x1 <= luck_ratio <= x2:
                    hit_chance = y1 + ((luck_ratio - x1) / (x2 - x1)) * (y2 - y1)
                    break

        if random.random() > hit_chance:
            logs.append(f"{self.name} の攻撃は {target.name} に回避された！")
            return {'target': target, 'total_damage': 0, 'logs': logs}
            
        # Damage calculation
        # Elemental multiplier
        element_mult = ELEMENT_TABLE.get(self.element, {}).get(target.element, ELEMENT_DEFAULT)
            
        # Base raw stat vs Defense
        if self.m_type == '物理':
            base_dmg = (self.atk * DMG_STAT_MULTIPLIER) - target.defense
        else:
            base_dmg = (self.int_stat * DMG_STAT_MULTIPLIER) - target.mdefense
            
        if base_dmg < 0:
            base_dmg = 0
            
        # Final multiplier
        base_dmg *= DMG_FINAL_MULTIPLIER
        
        # RNG variance
        rng_mult = random.uniform(DMG_RNG_MIN, DMG_RNG_MAX)
        
        # Critical hit check
        crit_mult = 1.0
        is_crit = False
        luck_diff_ratio = abs(self.luck - target.luck) / max(1, max(self.luck, target.luck))
        
        if luck_diff_ratio <= CRIT_LUCK_THRESHOLD:
            if random.random() < CRIT_CHANCE:
                is_crit = True
                crit_mult = CRIT_MULTIPLIER
                
        final_dmg_float = base_dmg * element_mult * rng_mult * crit_mult
        dmg = math.floor(final_dmg_float)
        
        if dmg <= 0:
            dmg = DMG_MINIMUM
            
        total_damage = dmg * self.multi_hit
        
        crit_text = "【クリティカル！】" if is_crit else ""
        if self.multi_hit > 1:
            logs.append(f"{self.name} は {target.name} に {crit_text}{dmg}×{self.multi_hit}段={total_damage} のダメージ！")
        else:
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
                
            # 新しい距離が射程内で、かつクールダウンが完了していれば攻撃
            # ※浮動小数点演算の極小の誤差を許容するため +0.001 のバッファ
            if dist <= m.attack_range + 0.001 and m.cooldown <= 0:
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
