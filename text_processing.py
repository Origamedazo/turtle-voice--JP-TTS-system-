# -*- coding: utf-8 -*-
import numpy as np
import pyopenjtalk

import os
import json

ACTIVE_DICT_PATH = "user_dict.json"

def set_active_dict(path):
    global ACTIVE_DICT_PATH
    ACTIVE_DICT_PATH = path

def apply_user_dict(text):
    if not os.path.exists(ACTIVE_DICT_PATH):
        return text
    try:
        with open(ACTIVE_DICT_PATH, 'r', encoding='utf-8') as f:
            user_dict = json.load(f)
        # Sort by key length descending to prevent partial match issues
        for k in sorted(user_dict.keys(), key=len, reverse=True):
            text = text.replace(k, user_dict[k])
    except Exception as e:
        print(f"辞書読み込みエラー: {e}")
    return text

# =========================
# テキストからモーラとピッチを取得
# =========================
def get_mora_pitch(text):
    """
    pyopenjtalk の g2p を使用して、読み（ひらがな）を取得し、
    簡易的なアクセント（1モーラ目低、以降高）を付与します。
    """
    text = apply_user_dict(text)
    
    mora_list = []
    pitch_list = []

    try:
        # 確実に動く g2p (Graph-to-Phoneme) で「ひらがな」を取得
        # kana=True にすることで、カタカナではなくひらがなで返ってきます
        full_reading = pyopenjtalk.g2p(text, kana=True)
        
        # モーラ分解
        mora_list = hiragana_to_mora(full_reading)
        
        # 簡易アクセント生成（東京方言の基本：低-高-高...）
        # 1モーラ目だけ 0 (低)、2モーラ目以降は 1 (高)
        if len(mora_list) > 0:
            pitch_list = [0] + [1] * (len(mora_list) - 1)
        
    except Exception as e:
        print(f"⚠️ 解析に失敗しました: {e}")
        # 万が一失敗した場合は空リストを返す
        mora_list = []
        pitch_list = []

    return mora_list, pitch_list

# =========================
# モーラ分解
# =========================
def hiragana_to_mora(text):
    res = []
    # 外来語対応のため ぁぃぅぇぉ ャュョァィゥェォ ヴ も考慮
    small = "ゃゅょぁぃぅぇぉャュョァィゥェォ"
    i = 0
    while i < len(text):
        if i + 1 < len(text) and text[i+1] in small:
            res.append(text[i:i+2])
            i += 2
        else:
            res.append(text[i])
            i += 1
    return res

# =========================
# F0変換
# =========================
def pitch_to_f0(pitch_list, base_f0=120):
    """
    ピッチ 0/1 を実際の周波数(Hz)に変換します。
    """
    f0_list = []
    for p in pitch_list:
        if p == 1:
            f0_list.append(base_f0 * 1.1) # 高いところを10%アップ
        else:
            f0_list.append(base_f0 * 0.9) # 低いところを10%ダウン
    return f0_list

def smooth_f0(f0_list):
    if len(f0_list) < 3:
        return f0_list
    # 移動平均で滑らかにする
    return np.convolve(f0_list, np.ones(3)/3, mode='same').tolist()

# =========================
# モーラ→音素 マッピング
# =========================
mora_to_phoneme_dict = {
    # 五十音（清音）
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "を": "o", "ん": "N",

    # 濁音
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",

    # 半濁音
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",

    # 拗音（清音）
    "きゃ": "kya", "きゅ": "kyu", "きょ": "kyo",
    "しゃ": "sha", "しゅ": "shu", "しょ": "sho",
    "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho",
    "にゃ": "nya", "にゅ": "nyu", "にょ": "nyo",
    "ひゃ": "hya", "ひゅ": "hyu", "ひょ": "hyo",
    "みゃ": "mya", "みゅ": "myu", "みょ": "myo",
    "りゃ": "rya", "りゅ": "ryu", "りょ": "ryo",

    # 拗音（濁音・半濁音）
    "ぎゃ": "gya", "ぎゅ": "gyu", "ぎょ": "gyo",
    "じゃ": "ja", "じゅ": "ju", "じょ": "jo",
    "びゃ": "bya", "びゅ": "byu", "びょ": "byo",
    "ぴゃ": "pya", "ぴゅ": "pyu", "ぴょ": "pyo",

    # 外来語拡張
    "ふぁ": "fa", "ふぃ": "fi", "ふぇ": "fe", "ふぉ": "fo",
    "ゔぁ": "va", "ゔぃ": "vi", "ゔ": "vu", "ゔぇ": "ve", "ゔぉ": "vo",
    "てぃ": "ti", "でぃ": "di", 
    "とぅ": "tu", "どぅ": "du",
    "つぁ": "tsa", "つぃ": "tsi", "つぇ": "tse", "つぉ": "tso",
    "うぇ": "we", "うぉ": "wo",
    "ちぇ": "che", "しぇ": "she", "じぇ": "je",
    "きぇ": "kye", "ぎぇ": "gye", "ひぇ": "hye", "びぇ": "bye", "ぴぇ": "pye", 
    "にぇ": "nye", "みぇ": "mye", "りぇ": "rye",
    "てゅ": "tyu", "でゅ": "dyu", "ふゅ": "fyu",
    "うぃ": "wi", "うぁ": "ua",

    # 特殊音
    "っ": "pau", "ー": ":", " ": "pau"
}

def mora_to_phonemes(mora_list):
    return [mora_to_phoneme_dict.get(m, m) for m in mora_list]

def phoneme_list_from_moras(mora_list):
    """
    モーラリストから合成・ラベリング用の音素リストを生成します。
    長音や助詞の処理を含みます。
    """
    phonemes = []
    last_v = "a"
    for m in mora_list:
        # カタカナをひらがなに変換
        m_h = "".join([chr(ord(c)-0x60) if 0x30A1<=ord(c)<=0x30F6 else c for c in m])
        p = mora_to_phoneme_dict.get(m_h, m_h)
        
        # 長音処理 (ー, う, :) を前の母音に置き換え
        if p in [":", "ー", "う"]:
            p = last_v
        
        phonemes.append(p)
        
        # 最後の母音を記録 (a, i, u, e, o のいずれかで終わる場合)
        if p[-1] in 'aiueo':
            last_v = p[-1]
            
    return phonemes