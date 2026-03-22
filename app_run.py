# -*- coding: utf-8 -*-
import os
import csv
import json
import numpy as np
import pandas as pd
import librosa
import soundfile as sf

try:
    from world_pitch_shift import apply_world_pitch
except ImportError:
    def apply_world_pitch(y, sr, ratio): return y

from text_processing import get_mora_pitch, mora_to_phoneme_dict
from viterbi_engine import ViterbiEngine 

# =========================
# 設定管理ロジック
# =========================
def load_or_create_config(folder_path):
    config_path = os.path.join(folder_path, "config.json")
    
    # デフォルト設定と各値の説明
    default_config = {
        "__instruction": "このファイルは音源ごとの接続設定です。値を変更して保存すると合成結果が変わります。",
        "pad_ms": 48,
        "__info_pad_ms": "切り出しの余裕(ms)。音が途切れるなら大きく、隣の音が混じるなら小さくしてください。",
        
        "stretch_ratio": 1.4,
        "__info_stretch_ratio": "ストレッチ係数。pad分をどれだけ重なりに回すか(通常1.2〜1.6)。",
        
        "overlap_ratio_vowel": 0.090,
        "__info_overlap_vowel": "母音の重なり量(秒)。0.090は90ms。滑らかにするには大きくします。",
        
        "overlap_ratio_consonant": 0.080,
        "__info_overlap_consonant": "子音の重なり量(秒)。母音より少し小さめが安定します。"
    }

    if not os.path.exists(config_path):
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        print(f" ✨ 新しい音源を検知しました。デフォルトの config.json を作成しました。")
        return default_config
    else:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

# =========================
# 補助関数群
# =========================
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

def get_target_durations(phonemes, avg_durations):
    durs = []
    for p in phonemes:
        base = avg_durations.get(p, 100)
        target = max(118.0, base) if any(v in p for v in ['a', 'i', 'u', 'e', 'o', 'N', 'wa', ':']) else max(48.0, base)
        durs.append(target)
    return durs

def load_f0_data(csv_path):
    if not os.path.exists(csv_path): return None, 0
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    df.columns = df.columns.str.strip()
    if 'f0' in df.columns:
        valid_f0 = df[df['f0'] > 0]['f0']
        avg_f0 = valid_f0.mean() if not valid_f0.empty else 0
        f0_dict = df.set_index('id')['f0'].to_dict()
    else:
        avg_f0, f0_dict = 0, {}
    return f0_dict, avg_f0

# =========================
# 合成コアエンジン
# =========================
def synthesize_sentence(text, engine, metadata_lookup, wav_cache, f0_dict, avg_f0, avg_durations, phoneme_index, config):
    sentences = []
    current = ""
    for char in text:
        if char in ["。", "？", "！", "、"]:
            sentences.append((current, char)); current = ""
        else: current += char
    if current: sentences.append((current, "。"))

    sentence_combined = []
    sr_internal = 44100
    
    # configからパラメータ取得
    pad_ms = config.get("pad_ms", 48)
    s_ratio = config.get("stretch_ratio", 1.4)
    ov_v = config.get("overlap_ratio_vowel", 0.090)
    ov_c = config.get("overlap_ratio_consonant", 0.080)

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
            decay = 1.0 - (i / num_mora) * 0.12
            onset = 1.05 if i < 2 else 1.0
            t_f0 = avg_f0 * base_scale * decay * onset
            if symbol == "？" and i == num_mora - 1: t_f0 *= 1.22
            target_f0s.append(t_f0)

        target_durs = get_target_durations(phonemes, avg_durations)
        best_tids = engine.find_best_path(phonemes, target_f0s, target_durs, phoneme_index)
        if not best_tids: continue

        phrase_audio = []
        for i, tid in enumerate(best_tids):
            target_p = phonemes[i]
            info = metadata_lookup[tid]
            y_full, sr_internal = wav_cache[info['file']]
            
            # config由来のpad_msを適用
            pad = int(sr_internal * (pad_ms / 1000))
            s = max(0, int((info['start']/10000000)*sr_internal) - pad)
            e = min(len(y_full), int((info['end']/10000000)*sr_internal) + pad)
            y = y_full[s:e].copy()

            is_dev = (target_p in 'iu') and ((i < len(phonemes)-1 and any(c in phonemes[i+1] for c in 'kstph')) or symbol in "。、")
            t_ms = target_durs[i] * (0.75 if is_dev else 1.0)
            
            if is_dev:
                y *= 0.45
            elif tid in f0_dict and f0_dict[tid] > 0:
                ratio = max(0.82, min(1.18, target_f0s[i]/f0_dict[tid]))
                if abs(ratio-1.0) > 0.02: y = apply_world_pitch(y, sr_internal, ratio)

            y = normalize_volume(y)
            c_ms = (len(y)/sr_internal)*1000
            if c_ms > 0:
                # s_ratioを使用してストレッチ
                y = librosa.effects.time_stretch(y, rate=1.0/max(0.7, min(1.5, (t_ms + pad_ms * s_ratio)/c_ms)))
            
            phrase_audio.append(y)

        if phrase_audio:
            combined = phrase_audio[0]
            for idx, next_seg in enumerate(phrase_audio[1:]):
                next_p = phonemes[idx+1]
                # config由来のoverlap_ratioを適用
                o_len = int(sr_internal * ov_v) if next_p[-1] in 'aiueo' else int(sr_internal * ov_c)
                combined = overlap_add(combined, next_seg, o_len)
            
            combined = apply_tiny_fade(combined)
            ps = 0.25 if symbol=="、" else 0.45 if symbol in "。！？" else 0.0
            if ps > 0: combined = np.concatenate([combined, np.zeros(int(sr_internal*ps))])
            sentence_combined.append(combined)

    return np.concatenate(sentence_combined) if sentence_combined else None, sr_internal

# =========================
# メイン処理
# =========================
def tts_main():
    print("--- Personal TTS System (Config Auto-Generation Mode) ---")
    folder_path = input("音源フォルダのパス：").strip('"')

    # 設定ファイルの読み込み（なければ作成）
    config = load_or_create_config(folder_path)

    with open(os.path.join(folder_path, "phoneme_index.json"), 'r', encoding='utf-8') as f:
        phoneme_index = json.load(f)
    f0_dict, avg_f0 = load_f0_data(os.path.join(folder_path, "F0Data.csv"))
    if avg_f0 == 0: avg_f0 = 1.0

    metadata_lookup, wav_cache = {}, {}
    with open(os.path.join(folder_path, "metadata.csv"), 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            w_p = os.path.join(folder_path, row['file'])
            metadata_lookup[row['id']] = {
                'phoneme': row['phoneme'], 'start': int(row['start_time']), 
                'end': int(row['end_time']), 'duration_ms': float(row.get('duration_ms',100)), 'file': w_p
            }
            if w_p not in wav_cache: wav_cache[w_p] = librosa.load(w_p, sr=None)

    avg_durs = pd.DataFrame.from_dict(metadata_lookup, orient='index').groupby('phoneme')['duration_ms'].mean().to_dict()
    engine = ViterbiEngine(f0_dict, metadata_lookup, avg_f0)

    mode = input("\n[1] 直接入力 [2] txtファイル読み込み : ")
    lines = []
    if mode == "2":
        t_path = input("txtファイルのパス：").strip('"')
        with open(t_path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip()]
    else:
        lines = [input("ひらがなで入力：").strip()]

    out_dir = "output_wavs"
    os.makedirs(out_dir, exist_ok=True)

    for i, line in enumerate(lines):
        audio, sr = synthesize_sentence(line, engine, metadata_lookup, wav_cache, f0_dict, avg_f0, avg_durs, phoneme_index, config)
        if audio is not None:
            safe_text = "".join([c for c in line[:10] if c.isalnum()])
            fname = f"{i+1:03d}_{safe_text}.wav"
            sf.write(os.path.join(out_dir, fname), audio, sr)
            print(f" ✅ 保存完了: {fname}")

if __name__ == "__main__":
    tts_main()