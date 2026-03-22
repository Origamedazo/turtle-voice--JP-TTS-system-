# -*- coding: utf-8 -*-
import os
import csv

def convert_lab_to_csv():
    print("こんにちは！音素コンテキスト(Triphone)を含めた metadata.csv を作成します。")

    print(r"labファイルを選択してください。")
    file_path_input = input("ファイルパスを入力してください：")
    file_path = file_path_input.replace('"', '').strip()

    if not os.path.exists(file_path):
        print(f"エラー：ファイルが見つかりません。")
        return

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    wav_filename = f"{base_name}.wav"

    try:
        # 文字コード対応
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='cp932') as f:
                lines = f.readlines()

        # 一旦全データを読み込む（前後の参照用）
        raw_data = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 3:
                raw_data.append({
                    "start": int(parts[0]),
                    "end": int(parts[1]),
                    "p": parts[2]
                })

        results = []
        phoneme_counts = {}

        # コンテキスト（前後）を考慮しながらループ
        for i in range(len(raw_data)):
            current = raw_data[i]
            phoneme = current["p"]

            # 4. sil以外の音素を対象
            if phoneme != "sil":
                # 前後の音素を取得
                pre_p = raw_data[i-1]["p"] if i > 0 else "sil"
                post_p = raw_data[i+1]["p"] if i < len(raw_data)-1 else "sil"

                if phoneme not in phoneme_counts:
                    phoneme_counts[phoneme] = 1
                else:
                    phoneme_counts[phoneme] += 1
                
                display_id = f"{phoneme}_{phoneme_counts[phoneme]:03d}"

                # 100ns単位をミリ秒に変換
                duration_ms = (current["end"] - current["start"]) / 10000 

                results.append({
                    "id": display_id,
                    "phoneme": phoneme,
                    "pre_phoneme": pre_p,    # 🔥 追加
                    "post_phoneme": post_p,  # 🔥 追加
                    "start_time": current["start"],
                    "end_time": current["end"],
                    "duration_ms": f"{duration_ms:.2f}",
                    "file": wav_filename
                })

        # headers に pre_phoneme と post_phoneme を追加
        output_path = "metadata.csv"
        headers = ["id", "phoneme", "pre_phoneme", "post_phoneme", "start_time", "end_time", "duration_ms", "file"]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(results)

        print(f"\n✅ 完了！ '{output_path}' にコンテキスト情報を保存しました。")
        print(f"ℹ️ 解析された音素数: {len(results)}")

    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    convert_lab_to_csv()