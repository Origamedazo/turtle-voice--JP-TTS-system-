import numpy as np
import pyworld as pw
import librosa
import pandas as pd
import os
import sys

# =========================
# 設定
# =========================
SR = 44100

print("===================================")
print(" 音源のF0（音の高さ）を測定します")
print("===================================")


# =========================
# metadataパス取得（ユーザー入力）
# =========================
def get_metadata_path():
    # コマンドライン引数対応（ドラッグ＆ドロップ）
    if len(sys.argv) > 1:
        path = sys.argv[1]
        print("[INFO] 引数からmetadataを取得:", path)
    else:
        print("metadata.csv のパスを入力してください")
        path = input(">>> ").strip().strip('"')

    # 存在チェック
    if not os.path.exists(path):
        print("[ERROR] ファイルが見つかりません:", path)
        return None

    print("[SUCCESS] metadata.csv 確認OK")
    return path


# =========================
# F0抽出
# =========================
def extract_f0(wav_path):
    print("[INFO] 音声読み込み:", wav_path)

    x, _ = librosa.load(wav_path, sr=SR)
    x = x.astype(np.float64)

    print("F0抽出中...")
    f0, t = pw.dio(x, SR)
    f0 = pw.stonemask(x, f0, t, SR)

    print("[SUCCESS] F0抽出完了")
    return f0, t



# =========================
# metadata読み込み
# =========================
def load_metadata(csv_path):
    print("metadata.csv 読み込み中...")
    df = pd.read_csv(csv_path)

    print(f"[SUCCESS] {len(df)} 個の音素を読み込みました")
    return df


# =========================
# サンプル → フレーム変換
# =========================
def sample_to_frame(sample_index, t):
    time_sec = sample_index / 10_000_000

    frame_period = t[1] - t[0]  # WORLDのフレーム間隔
    frame_index = int(time_sec / frame_period)

    return frame_index


# =========================
# 各音素のF0取得
# =========================
def extract_phoneme_f0(df, f0, t):
    results = []

    print("音素ごとのF0を計算中...")

    for i, row in df.iterrows():
        phoneme = row["phoneme"]
        id_name = row["id"]
        start = int(row["start_time"])
        end = int(row["end_time"])

        # ns → 秒（あなたの環境）
        start_f = sample_to_frame(start, t)
        end_f = sample_to_frame(end, t)

        # 範囲補正
        start_f = max(0, start_f)
        end_f = min(len(f0), end_f)

        if end_f <= start_f:
            print(f"[WARN] 無効区間: {id_name}")
            continue

        segment = f0[start_f:end_f]
        valid = segment[segment > 0]

        if len(valid) > 0:
            mean_f0 = np.mean(valid)
        else:
            mean_f0 = 0

        print(f"  -> {id_name:<10} ({phoneme}) : {round(mean_f0, 2)} Hz")

        results.append({
            "id": id_name,
            "phoneme": phoneme,
            "f0": mean_f0
        })

    print("[SUCCESS] 音素F0計算完了")
    return results


# =========================
# CSV保存
# =========================
def save_f0_csv(results, output_path="F0Data.csv"):
    print("CSV書き込み中...")

    valid_f0 = [r["f0"] for r in results if r["f0"] > 0]
    avg_f0 = np.mean(valid_f0) if len(valid_f0) > 0 else 0

    data = []

    for r in results:
        ratio = r["f0"] / avg_f0 if avg_f0 > 0 else 0

        data.append({
            "id": r["id"],
            "phoneme": r["phoneme"],
            "f0": r["f0"],
            "ratio": ratio
        })

    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print("[SUCCESS] 保存完了:", output_path)
    print(f"全体平均F0: {round(avg_f0, 2)} Hz")


# =========================
# メイン処理
# =========================
def process():
    metadata_path = get_metadata_path()

    if metadata_path is None:
        print("[WARN] 処理を終了します")
        return

    print("===================================")
    print(" F0抽出処理開始")
    print("===================================")

    df = load_metadata(metadata_path)

    # 相対パス対策
    base_dir = os.path.dirname(metadata_path)
    wav_path = os.path.join(base_dir, df.iloc[0]["file"])

    if not os.path.exists(wav_path):
        print("[ERROR] 音声ファイルが見つかりません:", wav_path)
        return

    f0, t = extract_f0(wav_path)

    results = extract_phoneme_f0(df, f0, t)

    save_f0_csv(results)

    print("===================================")
    print(" すべての処理が完了しました")
    print("===================================")


# =========================
# 実行
# =========================
if __name__ == "__main__":
    process()