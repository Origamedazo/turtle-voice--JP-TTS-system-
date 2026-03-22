# -*- coding: utf-8 -*-
import os
import csv
import json
import numpy as np
import pandas as pd
import librosa

try:
    from world_pitch_shift import apply_world_pitch
except ImportError:
    def apply_world_pitch(y, sr, ratio): return y

from text_processing import get_mora_pitch, mora_to_phoneme_dict
from viterbi_engine import ViterbiEngine

def normalize_volume(y, target_db=-20):
    rms = np.sqrt(np.mean(y**2))
    if rms == 0: return y
    current_db = 20 * np.log10(rms)
    gain = 10**((target_db - current_db) / 20)
    return y * gain

def apply_tiny_fade(y, fade_samples=100):
    if len(y) <= fade_samples * 2: return y
    fade = np.linspace(0, 1, fade_samples)
    y[:fade_samples] *= fade
    y[-fade_samples:] *= fade[::-1]
    return y

def overlap_add(a, b, overlap_len):
    if len(a) < overlap_len or len(b) < overlap_len:
        return np.concatenate([a, b])
    
    fade_out = np.cos(np.linspace(0, np.pi/2, overlap_len))**2
    fade_in = np.cos(np.linspace(np.pi/2, 0, overlap_len))**2
    
    overlap_part = a[-overlap_len:] * fade_out + b[:overlap_len] * fade_in
    return np.concatenate([a[:-overlap_len], overlap_part, b[overlap_len:]])


class TTSCore:
    def __init__(self):
        self.folder_path = None
        self.config = {}
        self.phoneme_index = {}
        self.f0_dict = {}
        self.avg_f0 = 1.0
        self.metadata_lookup = {}
        self.wav_cache = {}
        self.avg_durs = {}
        self.engine = None
        self.sr_internal = 44100
        self.is_loaded = False

    def load_or_create_config(self, folder_path):
        config_path = os.path.join(folder_path, "config.json")
        default_config = {
            "pad_ms": 48,
            "stretch_ratio": 1.4,
            "overlap_ratio_vowel": 0.090,
            "overlap_ratio_consonant": 0.080,
            "pitch_scale": 1.0,           # GUI向け: 全体のピッチ比
            "intonation_scale": 1.0,      # GUI向け: 抑揚（ピッチ変動）の比率
            "speed_scale": 1.0            # GUI向け: 速度（長さ）の比率
        }

        if not os.path.exists(config_path):
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            return default_config
        else:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Ensure missing defaults are populated
                for k, v in default_config.items():
                    if k not in loaded:
                        loaded[k] = v
                return loaded

    def save_config(self):
        if self.folder_path and self.config:
            config_path = os.path.join(self.folder_path, "config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)

    def load_f0_data(self, csv_path):
        if not os.path.exists(csv_path): return {}, 0
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        df.columns = df.columns.str.strip()
        if 'f0' in df.columns:
            valid_f0 = df[df['f0'] > 0]['f0']
            avg_f0 = valid_f0.mean() if not valid_f0.empty else 0
            f0_dict = df.set_index('id')['f0'].to_dict()
        else:
            avg_f0, f0_dict = 0, {}
        return f0_dict, avg_f0

    def load_voicebank(self, folder_path, callback=None):
        """音源フォルダを読み込む。GUI向けに進捗コールバック対応"""
        if callback: callback(0, "設定を読み込んでいます...")
        self.folder_path = folder_path
        self.config = self.load_or_create_config(folder_path)

        with open(os.path.join(folder_path, "phoneme_index.json"), 'r', encoding='utf-8') as f:
            self.phoneme_index = json.load(f)
            
        if callback: callback(20, "F0データを読み込んでいます...")
        self.f0_dict, self.avg_f0 = self.load_f0_data(os.path.join(folder_path, "F0Data.csv"))
        if self.avg_f0 == 0: self.avg_f0 = 1.0

        if callback: callback(40, "メタデータと音声をキャッシュしています...")
        self.metadata_lookup = {}
        self.wav_cache = {}
        
        # まず行数を数える（プログレスバー用）
        meta_path = os.path.join(folder_path, "metadata.csv")
        with open(meta_path, 'r', encoding='utf-8-sig') as f:
            total_rows = sum(1 for line in f) - 1 # header
            
        with open(meta_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                w_p = os.path.join(folder_path, row['file'])
                self.metadata_lookup[row['id']] = {
                    'phoneme': row['phoneme'], 'start': int(row['start_time']), 
                    'end': int(row['end_time']), 'duration_ms': float(row.get('duration_ms',100)), 'file': w_p
                }
                if w_p not in self.wav_cache: 
                    _y, _sr = librosa.load(w_p, sr=None)
                    self.wav_cache[w_p] = (_y, _sr)
                    
                if callback and idx % 50 == 0: 
                    # 40% ~ 90% の間で進捗させる
                    callback(40 + int(50 * (idx / max(1, total_rows))), "メタデータと音声をキャッシュしています...")

        if callback: callback(90, "Viterbiエンジンを初期化しています...")
        df = pd.DataFrame.from_dict(self.metadata_lookup, orient='index')
        self.avg_durs = df.groupby('phoneme')['duration_ms'].mean().to_dict()
        
        self.engine = ViterbiEngine(self.f0_dict, self.metadata_lookup, self.avg_f0)
        self.is_loaded = True
        if callback: callback(100, "ロード完了")

    def get_target_durations(self, phonemes):
        durs = []
        for p in phonemes:
            base = self.avg_durs.get(p, 100)
            target = max(118.0, base) if any(v in p for v in ['a', 'i', 'u', 'e', 'o', 'N', 'wa', ':']) else max(48.0, base)
            durs.append(target)
        return durs

    def text_to_intermediate(self, text):
        """
        GUI向け：文字列を受け取り、各フレーズの中間データ(音素、目標F0、目標長、予測TID)のリストを返す
        """
        if not self.is_loaded:
            raise ValueError("Voicebank not loaded")
            
        sentences = []
        current = ""
        for char in text:
            if char in ["。", "？", "！", "、", " ", "　"]:
                sentences.append((current, char)); current = ""
            else: current += char
        if current: sentences.append((current, "。"))

        intermediate_data = []

        pitch_scale = self.config.get("pitch_scale", 1.0)
        int_scale = self.config.get("intonation_scale", 1.0)
        speed_scale = self.config.get("speed_scale", 1.0)

        for phrase, symbol in sentences:
            if not phrase: continue
            raw_mora, pitch_list = get_mora_pitch(phrase)
            
            mora_list = []
            for char in raw_mora:
                if char in "ゃゅょぁぃぅぇぉ" and mora_list: mora_list[-1] += char
                else: mora_list.append(char)
            
            phonemes, last_v = [], "a"
            for m in mora_list:
                m_h = "".join([chr(ord(c)-0x60) if 0x30A1<=ord(c)<=0x30F6 else c for c in m])
                p = mora_to_phoneme_dict.get(m_h, m_h)
                if p in [":", "ー", "う"]: p = last_v
                phonemes.append(p)
                if p[-1] in 'aiueo': last_v = p[-1]

            target_f0s = []
            num_mora = len(pitch_list)
            for i, pv in enumerate(pitch_list):
                base_scale = 1.12 if pv == 1 else 0.88
                base_scale = 1.0 + (base_scale - 1.0) * int_scale
                decay = 1.0 - (i / num_mora) * 0.12 * int_scale
                onset = (1.05 if i < 2 else 1.0) * int_scale
                
                t_f0 = self.avg_f0 * base_scale * decay * onset * pitch_scale
                if symbol == "？" and i == num_mora - 1: t_f0 *= 1.22
                target_f0s.append(t_f0)

            target_durs = self.get_target_durations(phonemes)
            if speed_scale != 1.0:
                target_durs = [d / speed_scale for d in target_durs]

            best_tids = self.engine.find_best_path(phonemes, target_f0s, target_durs, self.phoneme_index)
            if not best_tids: continue

            intermediate_data.append({
                "phrase_text": phrase,
                "symbol": symbol,
                "phonemes": phonemes,
                "target_f0s": target_f0s,
                "target_durs": target_durs,
                "best_tids": best_tids
            })

        return intermediate_data

    def synthesize_from_intermediate(self, intermediate_data):
        """
        GUIから編集された可能性のある中間データリストを受け取り、音声を合成。
        """
        if not self.is_loaded:
            raise ValueError("Voicebank not loaded")
            
        last_alignment = []
        sentence_combined = []
        current_offset_samples = 0
        
        pad_ms = self.config.get("pad_ms", 48)
        s_ratio = self.config.get("stretch_ratio", 1.4)
        ov_v = self.config.get("overlap_ratio_vowel", 0.090)
        ov_c = self.config.get("overlap_ratio_consonant", 0.080)
        
        final_sr = self.sr_internal

        for phrase_idx, phrase_data in enumerate(intermediate_data):
            symbol = phrase_data.get("symbol", "。")
            phonemes = phrase_data["phonemes"]
            target_f0s = phrase_data["target_f0s"]
            target_durs = phrase_data["target_durs"]
            best_tids = phrase_data["best_tids"]

            phrase_audio = []
            for i, tid in enumerate(best_tids):
                target_p = phonemes[i]
                info = self.metadata_lookup.get(tid)
                if not info: continue
                
                y_full, sr_internal = self.wav_cache[info['file']]
                final_sr = sr_internal
                
                pad = int(sr_internal * (pad_ms / 1000))
                s = max(0, int((info['start']/10000000)*sr_internal) - pad)
                e = min(len(y_full), int((info['end']/10000000)*sr_internal) + pad)
                y = y_full[s:e].copy()

                is_dev = (target_p in 'iu') and ((i < len(phonemes)-1 and any(c in phonemes[i+1] for c in 'kstph')) or symbol in "。、")
                t_ms = target_durs[i] * (0.75 if is_dev else 1.0)
                
                if is_dev:
                    y *= 0.45
                elif tid in self.f0_dict and self.f0_dict[tid] > 0:
                    # ピッチ変更の制限を大幅に緩和（0.82-1.18 -> 0.5-2.1）
                    ratio = max(0.5, min(2.1, target_f0s[i]/self.f0_dict[tid]))
                    if abs(ratio-1.0) > 0.01: 
                        y = apply_world_pitch(y, sr_internal, ratio)

                y = normalize_volume(y)
                c_ms = (len(y)/sr_internal)*1000
                if c_ms > 0:
                    y = librosa.effects.time_stretch(y, rate=1.0/max(0.7, min(1.5, (t_ms + pad_ms * s_ratio)/c_ms)))
                
                phrase_audio.append(y)

            if phrase_audio:
                combined = phrase_audio[0]
                seg_starts = [0]
                
                for idx, next_seg in enumerate(phrase_audio[1:]):
                    if idx+1 < len(phonemes):
                        next_p = phonemes[idx+1]
                        o_len = int(final_sr * ov_v) if next_p[-1] in 'aiueo' else int(final_sr * ov_c)
                    else:
                        o_len = int(final_sr * ov_c)
                    seg_starts.append(len(combined) - o_len)
                    combined = overlap_add(combined, next_seg, o_len)
                
                for i in range(len(phrase_audio)):
                    start_ms = (current_offset_samples + seg_starts[i]) / final_sr * 1000.0
                    if i < len(phrase_audio) - 1:
                        next_p = phonemes[i+1]
                        o_len = int(final_sr * ov_v) if next_p[-1] in 'aiueo' else int(final_sr * ov_c)
                        end_ms = (current_offset_samples + seg_starts[i+1] + o_len/2) / final_sr * 1000.0
                    else:
                        end_ms = (current_offset_samples + len(combined)) / final_sr * 1000.0
                        
                    last_alignment.append({
                        'p_idx': phrase_idx,
                        'i': i,
                        'start_ms': start_ms,
                        'end_ms': end_ms,
                        'center_ms': (start_ms + end_ms) / 2.0
                    })
                
                combined = apply_tiny_fade(combined)
                ps = 0.25 if symbol in ["、", " ", "　"] else 0.45 if symbol in ["。", "！", "？"] else 0.0
                if ps > 0: combined = np.concatenate([combined, np.zeros(int(final_sr*ps))])
                sentence_combined.append(combined)
                current_offset_samples += len(combined)

        if not sentence_combined:
            return None, final_sr, []
        return np.concatenate(sentence_combined), final_sr, last_alignment

    def synthesize_text(self, text):
        """簡単モード向け・コンソール確認用"""
        intermediate = self.text_to_intermediate(text)
        audio, sr, _ = self.synthesize_from_intermediate(intermediate)
        return audio, sr

