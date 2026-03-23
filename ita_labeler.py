# -*- coding: utf-8 -*-
import os
import json
import re
import pyopenjtalk
import soundfile as sf
import numpy as np
from text_processing import hiragana_to_mora, phoneme_list_from_moras

class ITALabeler:
    def __init__(self, corpus_json_path):
        with open(corpus_json_path, 'r', encoding='utf-8') as f:
            self.corpus = json.load(f)
        
    def find_text_by_filename(self, filename, custom_prefix=None, num_position="last"):
        """
        ファイル名から対応するITAコーパスの文章を探します。
        custom_prefix: "EMO", "REC" または None (自動)
        num_position: "first" または "last" (例: RECITATION324_001 の 001 を取る場合は last)
        """
        base = os.path.splitext(filename)[0].upper()
        # すべての数字部分を抽出
        matches = re.findall(r'(\d+)', base)
        if not matches:
            return None
        
        # どの数字を使うかを選択
        num_str = matches[-1] if num_position == "last" else matches[0]
        num_str = num_str.zfill(3) # 001 形式にする
        
        # どのコーパス(EMO or REC)か
        prefix = custom_prefix
        if not prefix:
            if "EMO" in base or "EMOTION" in base:
                prefix = "EMO"
            elif "REC" in base or "RECITATION" in base:
                prefix = "REC"
            else:
                # どちらでもない場合は両方探す
                res = self.corpus["EMO"].get(num_str)
                if res: return res
                return self.corpus["REC"].get(num_str)
        
        return self.corpus.get(prefix, {}).get(num_str)

    def generate_lab_content(self, text, duration_sec):
        """
        テキストから音素列を取得し、線形アライメントで .lab 内容を生成します。
        100ns単位 (1s = 10,000,000)
        """
        # pyopenjtalk で「ひらがな」を取得してモーラ分解
        full_reading = pyopenjtalk.g2p(text, kana=True)
        mora_list = hiragana_to_mora(full_reading)
        
        # モーラから音素（CV単位等）に変換
        phonemes = phoneme_list_from_moras(mora_list)
        
        # 前後に sil を配置
        phonemes = ["pau"] + phonemes + ["pau"]
        
        # 合計時間 (100ns単位)
        total_units = int(duration_sec * 10000000)
        
        # 簡易的な時間配分
        # 無音(pau)は少し短めにして、残りを等分する
        # pau: 0.1s ずつ (もし足りれば)
        pau_duration = min(int(0.1 * 10000000), total_units // (len(phonemes) + 2))
        
        remaining_units = total_units - (pau_duration * 2)
        if remaining_units < 0:
            # 短すぎる場合は単純等分
            unit_per_p = total_units // len(phonemes)
            durations = [unit_per_p] * len(phonemes)
        else:
            unit_per_p = remaining_units // (len(phonemes) - 2)
            durations = [pau_duration] + [unit_per_p] * (len(phonemes) - 2) + [pau_duration]
            
        lines = []
        current_time = 0
        for i, p in enumerate(phonemes):
            start = current_time
            # 最後は端数調整で total_units に合わせる
            if i == len(phonemes) - 1:
                end = total_units
            else:
                end = start + durations[i]
            lines.append(f"{start} {end} {p}")
            current_time = end
            
        return "\n".join(lines)

    def process_folder(self, folder_path, callback=None, prefix=None, num_pos="last"):
        """
        フォルダ内のすべてのWAVファイルを処理します。
        """
        files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(".wav")])
        processed_count = 0
        error_count = 0
        
        for f in files:
            text = self.find_text_by_filename(f, custom_prefix=prefix, num_position=num_pos)
            if not text:
                if callback: callback(f"⚠️ スキップ: {f} (対応する文章が見つかりません)")
                continue
            
            try:
                wav_path = os.path.join(folder_path, f)
                data, sr = sf.read(wav_path)
                duration = len(data) / sr
                
                lab_content = self.generate_lab_content(text, duration)
                
                lab_name = os.path.splitext(f)[0] + ".lab"
                lab_path = os.path.join(folder_path, lab_name)
                
                with open(lab_path, 'w', encoding='utf-8') as lab_f:
                    lab_f.write(lab_content)
                
                processed_count += 1
                if callback: callback(f"✅ 完了: {f} -> {lab_name}")
            except Exception as e:
                error_count += 1
                if callback: callback(f"❌ エラー: {f} ({str(e)})")
        
        return processed_count, error_count

if __name__ == "__main__":
    # Test
    labeler = ITALabeler("ita_corpus.json")
    print(labeler.find_text_by_filename("EMO-001.wav"))
    print(labeler.generate_lab_content("えっ嘘でしょ。", 1.5))
