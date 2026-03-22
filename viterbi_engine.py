# -*- coding: utf-8 -*-
import numpy as np

class ViterbiEngine:
    def __init__(self, f0_dict, metadata_lookup, avg_f0):
        self.f0_dict = f0_dict
        self.metadata = metadata_lookup
        self.avg_f0 = avg_f0

    def calc_target_cost(self, tid, target_p, pre_p, post_p, target_f0, target_dur):
        """
        Calculates how well a single unit (tid) fits the target phoneme and its context.
        """
        cost = 0.0
        info = self.metadata.get(tid)
        if not info: return 100.0

        # 1. Phoneme Context Cost (Triphone match)
        # Context match is important for natural transitions.
        if info.get('pre_phoneme') != pre_p:
            cost += 0.5
        if info.get('post_phoneme') != post_p:
            cost += 0.5

        # 2. Pitch Cost (Log scale)
        if tid in self.f0_dict and self.f0_dict[tid] > 0:
            pitch_diff = abs(np.log2(self.f0_dict[tid] + 1) - np.log2(target_f0 + 1))
            cost += pitch_diff * 2.0
        
        # 3. 🔥 Duration Cost (リズムの安定化)
        # 誤差を50ms単位で正規化し、二乗することで「大幅なズレ」を厳しく排除します。
        # 重みを 1.0 -> 3.5 に強化しました。
        dur_diff = abs(info['duration_ms'] - target_dur)
        cost += ((dur_diff / 50.0) ** 2) * 3.5
            
        return cost

    def calc_concat_cost(self, prev_tid, curr_tid):
        """
        Calculates the smoothness of the connection between two units.
        """
        if not prev_tid: return 0.0
        
        prev_info = self.metadata.get(prev_tid)
        curr_info = self.metadata.get(curr_tid)
        
        # 【最優先】元々連続して録音されたものなら強力なボーナス（-1.5）
        if prev_info['file'] == curr_info['file'] and \
           prev_info['end'] == curr_info['start']:
            return -1.5 
        
        # ピッチの連続性ペナルティ
        p_f0 = self.f0_dict.get(prev_tid, 0)
        c_f0 = self.f0_dict.get(curr_tid, 0)
        
        concat_penalty = 0.0
        if p_f0 > 0 and c_f0 > 0:
            diff = abs(np.log2(p_f0 + 1) - np.log2(c_f0 + 1))
            concat_penalty += diff * 5.0
            
        # 別のサンプルを繋ぐ場合のベースコスト
        return 2.5 + concat_penalty

    def find_best_path(self, phonemes, target_f0_list, target_dur_list, phoneme_index):
        if not phonemes: return []

        dp = []
        backtrack = []

        # --- Frame 0 ---
        first_p = phonemes[0]
        pre_p = "sil"
        post_p = phonemes[1] if len(phonemes) > 1 else "sil"
        
        first_cands = phoneme_index.get(first_p, [])
        if not first_cands: return []

        step_dp = {}
        for tid in first_cands:
            step_dp[tid] = self.calc_target_cost(tid, first_p, pre_p, post_p, 
                                                 target_f0_list[0], target_dur_list[0])
        dp.append(step_dp)

        # --- Frame 1 to N ---
        for i in range(1, len(phonemes)):
            curr_p = phonemes[i]
            pre_p = phonemes[i-1]
            post_p = phonemes[i+1] if i < len(phonemes)-1 else "sil"
            
            curr_cands = phoneme_index.get(curr_p, [])
            step_dp = {}
            step_back = {}

            for curr_tid in curr_cands:
                t_cost = self.calc_target_cost(curr_tid, curr_p, pre_p, post_p, 
                                               target_f0_list[i], target_dur_list[i])
                
                best_prev_cost = float('inf')
                best_prev_tid = None

                for prev_tid, prev_cum_cost in dp[i-1].items():
                    c_cost = self.calc_concat_cost(prev_tid, curr_tid)
                    total_cost = prev_cum_cost + c_cost + t_cost
                    
                    if total_cost < best_prev_cost:
                        best_prev_cost = total_cost
                        best_prev_tid = prev_tid
                
                step_dp[curr_tid] = best_prev_cost
                step_back[curr_tid] = best_prev_tid
            
            dp.append(step_dp)
            backtrack.append(step_back)

        # --- Backtracking ---
        path = []
        if not dp[-1]: return []
        curr_tid = min(dp[-1], key=dp[-1].get)
        path.append(curr_tid)

        for i in range(len(backtrack)-1, -1, -1):
            curr_tid = backtrack[i][curr_tid]
            path.insert(0, curr_tid)

        return path