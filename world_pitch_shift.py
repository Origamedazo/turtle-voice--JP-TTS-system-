import pyworld as pw
import numpy as np

def apply_world_pitch(y, sr, pitch_scale):
    # float64必須
    y = y.astype(np.float64)

    # WORLD分析
    _f0, t = pw.dio(y, sr)                     # 基本周波数
    f0 = pw.stonemask(y, _f0, t, sr)           # 精度向上
    sp = pw.cheaptrick(y, f0, t, sr)           # スペクトル
    ap = pw.d4c(y, f0, t, sr)                  # 非周期成分

    # ピッチ変更（ここが核心）
    f0_new = f0 * pitch_scale

    # 再合成
    y_new = pw.synthesize(f0_new, sp, ap, sr)

    return y_new.astype(np.float32)
