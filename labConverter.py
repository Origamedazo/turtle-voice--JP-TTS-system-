# -*- coding: utf-8 -*-
import os
import sys
import csv

def convert_lab_to_csv():
    print("こんにちは！音素コンテキスト(Triphone)を含めた metadata.csv を作成します。")

    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        print("labファイルまたはフォルダを選択してください。")
        input_path = input("パスを入力してください：").replace('"', '').strip()
    
    input_path = input_path.replace('"', '').strip()

    if not os.path.exists(input_path):
        print(f"エラー：パスが見つかりません。({input_path})")
        return

    # 処理対象ファイルのリストアップ
    target_files = []
    if os.path.isdir(input_path):
        target_files = [os.path.join(input_path, f) for f in os.listdir(input_path) if f.endswith(".lab")]
        print(f"フォルダ内の {len(target_files)} 個の lab ファイルを処理します。")
    else:
        target_files = [input_path]

    if not target_files:
        print("エラー：処理対象の .lab ファイルが見つかりません。")
        return

    results = []
    phoneme_counts = {}

    try:
        for file_path in target_files:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            wav_filename = f"{base_name}.wav"

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
                    try:
                        raw_data.append({
                            "start": int(parts[0]),
                            "end": int(parts[1]),
                            "p": parts[2]
                        })
                    except ValueError:
                        print(f"警告：不正な数値形式をスキップしました ({os.path.basename(file_path)}): {line.strip()}")

            # コンテキスト（前後）を考慮しながらループ
            for i in range(len(raw_data)):
                current = raw_data[i]
                phoneme = current["p"]

                # sil, pau, break以外の音素を対象
                if phoneme not in ["sil", "pau", "break"]:
                    # 前後の音素を取得
                    pre_p = raw_data[i-1]["p"] if i > 0 else "sil"
                    post_p = raw_data[i+1]["p"] if i < len(raw_data)-1 else "sil"

                    if phoneme not in phoneme_counts:
                        phoneme_counts[phoneme] = 1
                    else:
                        phoneme_counts[phoneme] += 1
                    
                    display_id = f"{phoneme}_{phoneme_counts[phoneme]:03d}"
                    duration_ms = (current["end"] - current["start"]) / 10000 

                    results.append({
                        "id": display_id,
                        "phoneme": phoneme,
                        "pre_phoneme": pre_p,
                        "post_phoneme": post_p,
                        "start_time": current["start"],
                        "end_time": current["end"],
                        "duration_ms": f"{duration_ms:.2f}",
                        "file": wav_filename
                    })

        # headers に pre_phoneme と post_phoneme を追加
        output_path = "metadata.csv"
        headers = ["id", "phoneme", "pre_phoneme", "post_phoneme", "start_time", "end_time", "duration_ms", "file"]
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(results)

        print(f"\n[完了] '{output_path}' に全 {len(results)} 件の情報を保存しました。")

    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    convert_lab_to_csv()