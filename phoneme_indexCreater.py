# -*- coding: utf-8 -*-
import csv
import json
import os

def create_phoneme_index():
    print("こんにちは！metadata.csvから音素インデックス(JSON)を作成します。")

    # 1. ファイルパスの入力
    print(r"metadata.csvのパスを入力してください。")
    raw_input = input("パス：")
    file_path = raw_input.replace('"', '').strip()

    if not os.path.exists(file_path):
        print("エラー：ファイルが見つかりません。")
        return

    # 2. データの分類用辞書
    # 構造: {"a": ["a_001", "a_002"], "i": ["i_001"]}
    phoneme_dict = {}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                p_type = row['phoneme'].strip() # 親となる音素名 (a, i, u...)
                p_id = row['id'].strip()       # 個別のID (a, a_2, i...)

                # --- IDの整形ロジック ---
                # アンダーバーで分割（例: "a_2" -> ["a", "2"] / "a" -> ["a"]）
                parts = p_id.split('_')
                base_name = parts[0]
                
                if len(parts) > 1 and parts[1].isdigit():
                    # 数字がついている場合（a_2など）
                    num = int(parts[1])
                else:
                    # 数字がついていない場合（aなど）は1番とする
                    num = 1
                
                # 3桁のゼロ埋めで整形 (例: a_001, a_002)
                formatted_id = f"{base_name}_{num:03d}"

                # --- 辞書への格納 ---
                if p_type not in phoneme_dict:
                    phoneme_dict[p_type] = []
                
                # リストに追加
                phoneme_dict[p_type].append(formatted_id)

        # 3. JSONファイルとして出力
        output_path = "phoneme_index.json"
        with open(output_path, 'w', encoding='utf-8') as jf:
            # indent=4 で人間が読みやすい形式に
            json.dump(phoneme_dict, jf, ensure_ascii=False, indent=4)

        print("-" * 30)
        print(f"成功！ '{output_path}' を作成しました。")
        print("内容のプレビュー:")
        print(json.dumps(phoneme_dict, ensure_ascii=False, indent=4))
        print("-" * 30)

    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    create_phoneme_index()