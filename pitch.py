# pitch.py
import numpy as np

def pitch_period(length):
    # 。：下降
    return np.linspace(1.1, 0.8, length)

def pitch_question(length):
    # ？：上昇
    return np.linspace(0.9, 1.2, length)

def pitch_exclamation(length):
    # ！：山型
    x = np.linspace(0, 1, length)
    return 1.0 + 0.3 * np.sin(np.pi * x)

def get_pitch_curve(symbol, length):
    if symbol == "。":
        return pitch_period(length)
    elif symbol == "？":
        return pitch_question(length)
    elif symbol == "！":
        return pitch_exclamation(length)
    else:
        return np.ones(length)
