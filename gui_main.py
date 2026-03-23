# -*- coding: utf-8 -*-
import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QPushButton, QLabel, 
                             QFileDialog, QProgressBar, QMessageBox, QGroupBox,
                             QTextEdit, QSlider, QComboBox, QDialog, QTableWidget,
                             QTableWidgetItem, QHeaderView, QScrollArea)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
import json

from engine_core import TTSCore
from gui_advanced import AdvancedTabWidget
from text_processing import set_active_dict

def get_root_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(__file__))

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(get_root_path(), relative_path)

# Set OPEN_JTALK_DICT_DIR for pyopenjtalk before it's used
if getattr(sys, 'frozen', False):
    os.environ["OPEN_JTALK_DICT_DIR"] = get_resource_path(os.path.join("pyopenjtalk", "open_jtalk_dic_utf_8-1.11"))

class JsonEditorDialog(QDialog):
    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.setWindowTitle(f"エディタ: {os.path.basename(filepath)}")
        self.resize(500, 400)
        layout = QVBoxLayout(self)
        self.editor = QTextEdit()
        # JSON用の簡易等幅フォント設定
        font = self.editor.font()
        font.setFamily("Consolas")
        self.editor.setFont(font)
        layout.addWidget(self.editor)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存して閉じる")
        btn_save.clicked.connect(self.save_data)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        self.load_data()
        
    def load_data(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self.editor.setPlainText(f.read())
        else:
            self.editor.setPlainText("{\n    \n}")
            
    def save_data(self):
        try:
            val = self.editor.toPlainText().strip()
            if val:
                data = json.loads(val)
                with open(self.filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
            else:
                pass
            QMessageBox.information(self, "完了", "保存しました！")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"JSONの形式が正しくありません:\n{e}")

class UserDictEditorDialog(QDialog):
    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.setWindowTitle(f"辞書エディタ: {os.path.basename(filepath)}")
        self.resize(500, 500)
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["単語", "読み (ひらがな)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        row_layout = QHBoxLayout()
        btn_add = QPushButton("単語を追加")
        btn_add.clicked.connect(self.add_row)
        btn_del = QPushButton("選択した単語を削除")
        btn_del.clicked.connect(self.del_row)
        row_layout.addWidget(btn_add)
        row_layout.addWidget(btn_del)
        layout.addLayout(row_layout)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存して閉じる")
        btn_save.clicked.connect(self.save_data)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        self.load_data()
        
    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        
    def del_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            
    def load_data(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.table.setRowCount(len(data))
                for i, (k, v) in enumerate(data.items()):
                    self.table.setItem(i, 0, QTableWidgetItem(k))
                    self.table.setItem(i, 1, QTableWidgetItem(v))
            except Exception as e:
                pass
                
    def save_data(self):
        data = {}
        for row in range(self.table.rowCount()):
            k_item = self.table.item(row, 0)
            v_item = self.table.item(row, 1)
            if k_item and v_item:
                k = k_item.text().strip()
                v = v_item.text().strip()
                if k and v:
                    data[k] = v
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            QMessageBox.information(self, "完了", "辞書を保存しました！")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存失敗:\n{e}")
        


class DialogueBlockWidget(QGroupBox):
    def __init__(self, main_gui, parent=None):
        super().__init__("セリフブロック", parent)
        self.main_gui = main_gui
        layout = QVBoxLayout(self)
        
        top_layout = QHBoxLayout()
        
        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(60, 60)
        self.lbl_icon.setStyleSheet("border: 1px solid #ccc; background-color: #fff;")
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon.setText("No Icon")
        
        voice_layout = QVBoxLayout()
        voice_layout.addWidget(QLabel("担当音源:"))
        self.combo_voice = QComboBox()
        self.combo_voice.setMinimumWidth(150)
        self.combo_voice.addItems([self.main_gui.combo_voice.itemText(i) for i in range(self.main_gui.combo_voice.count()) if self.main_gui.combo_voice.itemText(i) != "(voicebanksフォルダ内が空です)"])
        
        self.combo_voice.currentTextChanged.connect(self.update_icon)
        
        curr = self.main_gui.combo_voice.currentText()
        if curr: 
            self.combo_voice.setCurrentText(curr)
        
        # 明示的にアイコンを初期更新
        self.update_icon(self.combo_voice.currentText())

        btn_del = QPushButton("削除")
        btn_del.setMinimumWidth(60)
        btn_del.setMinimumHeight(30)
        btn_del.clicked.connect(self.deleteLater)
        
        voice_layout.addWidget(self.combo_voice)
        voice_layout.addStretch()
        
        top_layout.addWidget(self.lbl_icon)
        top_layout.addLayout(voice_layout)
        top_layout.addStretch()
        top_layout.addWidget(btn_del)
        layout.addLayout(top_layout)
        
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("セリフを入力してください")
        self.txt_input.setMaximumHeight(60)
        
        btn_layout = QVBoxLayout()
        self.btn_play_local = QPushButton("▶")
        self.btn_play_local.setToolTip("このブロックだけを再生")
        self.btn_play_local.setMinimumSize(35, 27)
        self.btn_play_local.clicked.connect(self.play_local)
        
        self.btn_save_local = QPushButton("💾")
        self.btn_save_local.setToolTip("このブロックだけを音声ファイルとして保存")
        self.btn_save_local.setMinimumSize(35, 27)
        self.btn_save_local.clicked.connect(self.save_local)
        
        btn_layout.addWidget(self.btn_play_local)
        btn_layout.addWidget(self.btn_save_local)
        
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.addWidget(self.txt_input)
        input_layout.addLayout(btn_layout)
        
        layout.addLayout(input_layout)
        
        param_layout = QHBoxLayout()
        self.sl_speed, l_sp = self.create_slider_row("話速", 0.5, 2.0, 1.0, 0.05)
        self.sl_pitch, l_pi = self.create_slider_row("高さ", 0.5, 2.0, 1.0, 0.05)
        self.sl_int, l_in = self.create_slider_row("抑揚", 0.0, 2.0, 1.0, 0.05)
        
        param_layout.addLayout(l_sp)
        param_layout.addLayout(l_pi)
        param_layout.addLayout(l_in)
        layout.addLayout(param_layout)

    def update_icon(self, text):
        import os
        from PyQt6.QtGui import QPixmap
        if not text: return
        core = self.main_gui.get_cached_core(text)
        if hasattr(core, 'folder_path') and core.folder_path:
            icon_path = os.path.join(core.folder_path, "icon.png")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(core.folder_path, "icon.jpg")
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path)
                self.lbl_icon.setPixmap(pixmap.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                return
        self.lbl_icon.clear()
        self.lbl_icon.setText("No Icon")

    def play_local(self):
        text = self.txt_input.toPlainText().strip()
        voice_name = self.combo_voice.currentText()
        if not text or not voice_name or voice_name == "(voicebanksフォルダ内が空です)": return
        
        core = self.main_gui.get_cached_core(voice_name)
        if hasattr(core, "is_loaded") and not core.is_loaded: return
        
        # 個別パラメータの適用
        core.config["speed_scale"] = self.sl_speed.value() / 100.0
        core.config["pitch_scale"] = self.sl_pitch.value() / 100.0
        core.config["intonation_scale"] = self.sl_int.value() / 100.0
        
        self.btn_play_local.setEnabled(False)
        self.set_highlight(True)
        from PyQt6.QtWidgets import QApplication, QMessageBox
        QApplication.processEvents()
        try:
            audio, sr = core.synthesize_text(text)
            if audio is not None:
                import soundfile as sf
                import tempfile
                import winsound
                import os
                tmp_wav = os.path.join(tempfile.gettempdir(), "turtle_temp_local.wav")
                sf.write(tmp_wav, audio, sr)
                winsound.PlaySound(tmp_wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"合成中にエラーが発生しました:\n{str(e)}")
        finally:
            self.btn_play_local.setEnabled(True)
            self.set_highlight(False)

    def save_local(self):
        text = self.txt_input.toPlainText().strip()
        voice_name = self.combo_voice.currentText()
        if not text or not voice_name or voice_name == "(voicebanksフォルダ内が空です)": return
        
        core = self.main_gui.get_cached_core(voice_name)
        if hasattr(core, "is_loaded") and not core.is_loaded: return
        
        # 個別パラメータの適用
        core.config["speed_scale"] = self.sl_speed.value() / 100.0
        core.config["pitch_scale"] = self.sl_pitch.value() / 100.0
        core.config["intonation_scale"] = self.sl_int.value() / 100.0
        
        from PyQt6.QtWidgets import QFileDialog, QMessageBox, QApplication
        fpath, _ = QFileDialog.getSaveFileName(self, "音声を保存", f"{voice_name}_dialogue.wav", "WAV Files (*.wav)")
        if not fpath: return
        
        self.btn_save_local.setEnabled(False)
        self.set_highlight(True)
        QApplication.processEvents()
        try:
            audio, sr = core.synthesize_text(text)
            if audio is not None:
                import soundfile as sf
                sf.write(fpath, audio, sr)
                QMessageBox.information(self, "保存完了", f"音声を保存しました:\n{fpath}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存中にエラーが発生しました:\n{str(e)}")
        finally:
            self.btn_save_local.setEnabled(True)
            self.set_highlight(False)

    def set_highlight(self, active: bool):
        if active:
            self.setStyleSheet("""
                QGroupBox { border: 3px solid #4CAF50; background-color: #f1f8e9; }
                QTextEdit { background-color: #e8f5e9; border: 1px solid #4CAF50; color: #004d40; }
            """)
        else:
            self.setStyleSheet("")

    def create_slider_row(self, name, min_val, max_val, default_val, step=0.1):
        row = QHBoxLayout()
        lbl_name = QLabel(name)
        lbl_name.setFixedWidth(130)
        from PyQt6.QtWidgets import QSlider
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(int(min_val * 100))
        slider.setMaximum(int(max_val * 100))
        slider.setValue(int(default_val * 100))
        slider.setSingleStep(int(step * 100))
        lbl_val = QLabel(f"{default_val:.2f}")
        lbl_val.setFixedWidth(50)
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        slider.valueChanged.connect(lambda v, l=lbl_val: l.setText(f"{v/100:.2f}"))
        row.addWidget(lbl_name)
        row.addWidget(slider)
        row.addWidget(lbl_val)
        return slider, row

class VoiceLoadThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, core, path):
        super().__init__()
        self.core = core
        self.path = path

    def run(self):
        try:
            self.core.load_voicebank(self.path, callback=self.progress.emit)
            self.finished.emit(True, "ロード完了")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished.emit(False, str(e))


class TurtleVoiceGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.core = TTSCore()
        self.cores_cache = {} # {folder_path: TTSCore}
        
        self.init_ui()
        self.apply_styles()
        
        # Connect buttons
        self.btn_play.clicked.connect(self.play_audio)
        self.btn_export.clicked.connect(self.export_audio)

    def init_ui(self):
        self.setWindowTitle("turtle voice tts GUI")
        self.setMinimumSize(900, 650)

        main_layout = QVBoxLayout()
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # 1. Header (Voicebank Selection)
        header_group = QGroupBox("設定・音源管理")
        header_layout = QHBoxLayout(header_group)
        
        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(60, 60)
        self.lbl_icon.setStyleSheet("border: 1px solid #ccc; background-color: #fff;")
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon.setText("No Icon")
        
        self.lbl_vroot = QLabel("詳細モード用\nメイン音源:")
        self.combo_voice = QComboBox()
        self.combo_voice.setMinimumWidth(150)
        self.btn_reload_vlist = QPushButton("更新")
        self.btn_reload_vlist.clicked.connect(self.populate_voicebank_list)
        
        self.btn_load_voice = QPushButton("ロード")
        self.btn_load_voice.clicked.connect(self.select_voicebank)
        
        self.lbl_dict = QLabel("辞書:")
        self.combo_dict = QComboBox()
        self.combo_dict.setMinimumWidth(120)
        self.combo_dict.currentTextChanged.connect(self.on_dict_changed)
        self.btn_reload_dict = QPushButton("辞書更新")
        self.btn_reload_dict.clicked.connect(self.populate_dict_list)

        self.btn_import_txt = QPushButton("📄 テキスト読み込み")
        self.btn_import_txt.setToolTip("テキストファイルから一括で読み込みます")
        self.btn_import_txt.clicked.connect(self.import_text_file)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedWidth(150)

        header_layout.addWidget(self.lbl_icon)
        header_layout.addWidget(self.lbl_vroot)
        header_layout.addWidget(self.combo_voice)
        header_layout.addWidget(self.btn_reload_vlist)
        header_layout.addWidget(self.btn_load_voice)
        btn_save_proj = QPushButton("プロジェクト保存")
        btn_save_proj.clicked.connect(self.save_project)
        btn_load_proj = QPushButton("プロジェクトを開く")
        btn_load_proj.clicked.connect(self.load_project)
        
        header_layout.addWidget(btn_save_proj)
        header_layout.addWidget(btn_load_proj)
        header_layout.addSpacing(15)
        header_layout.addWidget(self.lbl_dict)
        header_layout.addWidget(self.combo_dict)
        header_layout.addWidget(self.btn_reload_dict)
        header_layout.addWidget(self.btn_import_txt)
        header_layout.addStretch(1)
        header_layout.addWidget(self.progress_bar)
        
        main_layout.addWidget(header_group)
        
        self.populate_voicebank_list()
        self.populate_dict_list()

        # 2. Tabs (Modes)
        self.tabs = QTabWidget()
        self.tab_beginner = QWidget()
        self.tab_advanced = QWidget()
        self.tab_tools = QWidget()

        self.tabs.addTab(self.tab_beginner, "簡単モード (Beginner)")
        self.tabs.addTab(self.tab_advanced, "詳細モード (Advanced)")
        self.tabs.addTab(self.tab_tools, "音源設定 (Setup)")
        
        self.setup_beginner_tab()
        self.setup_advanced_tab()
        self.setup_tools_tab()

        self.tabs.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.tabs, stretch=1)

        # 3. Footer (Playback Controls)
        footer_layout = QHBoxLayout()
        self.btn_play = QPushButton("▶ 再生 (Play)")
        self.btn_play.setMinimumHeight(45)
        self.btn_play.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.btn_export = QPushButton("💾 音声書き出し (Export WAV)")
        self.btn_export.setMinimumHeight(45)
        self.btn_export.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        footer_layout.addWidget(self.btn_play)
        footer_layout.addWidget(self.btn_export)
        
        main_layout.addLayout(footer_layout)

    def on_tab_changed(self, index):
        if index == 1: # Advanced tab
            # Sync ALL blocks from Beginner to Advanced Mode
            beg_blocks = []
            for i in range(self.blocks_layout.count()):
                w = self.blocks_layout.itemAt(i).widget()
                if isinstance(w, DialogueBlockWidget):
                    beg_blocks.append(w)
            
            # Clear current advanced blocks and recreate to match beginner blocks
            # Or ask user? For now, let's sync if advanced is currently empty or user confirms.
            # To be efficient, we just update existing ones and add/remove as needed.
            
            adv_blocks = []
            for i in range(self.adv_blocks_layout.count()):
                w = self.adv_blocks_layout.itemAt(i).widget()
                if isinstance(w, AdvancedTabWidget):
                    adv_blocks.append(w)
            
            # Adjust number of advanced blocks
            while len(adv_blocks) < len(beg_blocks):
                new_b = self.add_advanced_block()
                adv_blocks.append(new_b)
            while len(adv_blocks) > len(beg_blocks):
                b = adv_blocks.pop()
                b.deleteLater()
            
            # Update content
            for beg_w, adv_w in zip(beg_blocks, adv_blocks):
                txt = beg_w.txt_input.toPlainText().strip()
                voice = beg_w.combo_voice.currentText()
                
                # 同期判定: テキストまたは音源のいずれかが異なる、あるいは詳細データが未生成の場合
                needs_update = (adv_w.txt_input.toPlainText().strip() != txt or 
                                adv_w.combo_voice.currentText() != voice or
                                not adv_w.intermediate_data)
                
                if needs_update:
                    adv_w.txt_input.setPlainText(txt)
                    if voice and voice != "(voicebanksフォルダ内が空です)":
                        idx = adv_w.combo_voice.findText(voice)
                        if idx >= 0:
                            adv_w.combo_voice.setCurrentIndex(idx)
                        else:
                            # 選択肢にない場合は追加して選択
                            adv_w.combo_voice.addItem(voice)
                            adv_w.combo_voice.setCurrentText(voice)
                    
                    adv_w.on_analyze()

    def setup_beginner_tab(self):
        layout = QVBoxLayout(self.tab_beginner)
        
        self.blocks_area = QScrollArea()
        self.blocks_area.setWidgetResizable(True)
        self.blocks_container = QWidget()
        self.blocks_layout = QVBoxLayout(self.blocks_container)
        self.blocks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.blocks_area.setWidget(self.blocks_container)
        
        layout.addWidget(self.blocks_area)
        
        btn_add = QPushButton("＋ セリフブロックを追加")
        btn_add.setMinimumHeight(40)
        btn_add.clicked.connect(self.add_dialogue_block)
        layout.addWidget(btn_add)
        
        self.add_dialogue_block()

    def add_dialogue_block(self):
        block = DialogueBlockWidget(self)
        self.blocks_layout.addWidget(block)
        return block

    def setup_advanced_tab(self):
        layout = QVBoxLayout(self.tab_advanced)
        
        self.adv_blocks_area = QScrollArea()
        self.adv_blocks_area.setWidgetResizable(True)
        self.adv_blocks_container = QWidget()
        self.adv_blocks_layout = QVBoxLayout(self.adv_blocks_container)
        self.adv_blocks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.adv_blocks_area.setWidget(self.adv_blocks_container)
        
        layout.addWidget(self.adv_blocks_area)
        
        btn_add = QPushButton("＋ 詳細ブロックを追加")
        btn_add.setMinimumHeight(40)
        btn_add.clicked.connect(self.add_advanced_block)
        layout.addWidget(btn_add)
        
        self.add_advanced_block()

    def add_advanced_block(self):
        block = AdvancedTabWidget(self)
        self.adv_blocks_layout.addWidget(block)
        return block

    def import_text_file(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "テキストファイルを選択", "", "Text Files (*.txt);;All Files (*)")
        if not fpath: return
        
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Ask if split by line
            reply = QMessageBox.question(self, "インポート設定", 
                                       "改行ごとにブロックを分けて読み込みますか？",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.Yes)
            
            if reply == QMessageBox.StandardButton.Yes:
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                if not lines: return
                
                # Clear existing blocks? Let's ask.
                clear_reply = QMessageBox.question(self, "確認", "既存のブロックを削除してから読み込みますか？",
                                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if clear_reply == QMessageBox.StandardButton.Yes:
                    self.clear_all_blocks()
                
                for line in lines:
                    new_block = self.add_dialogue_block()
                    new_block.txt_input.setPlainText(line)
            else:
                new_block = self.add_dialogue_block()
                new_block.txt_input.setPlainText(content)
                
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ファイルの読み込みに失敗しました:\n{str(e)}")

    def clear_all_blocks(self):
        # Beginner blocks
        for i in reversed(range(self.blocks_layout.count())):
            w = self.blocks_layout.itemAt(i).widget()
            if w: w.deleteLater()
        # Advanced blocks
        for i in reversed(range(self.adv_blocks_layout.count())):
            w = self.adv_blocks_layout.itemAt(i).widget()
            if w: w.deleteLater()

    def create_slider_row(self, name, min_val, max_val, default_val, step=0.1):
        row = QHBoxLayout()
        lbl_name = QLabel(name)
        lbl_name.setFixedWidth(130)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(int(min_val * 100))
        slider.setMaximum(int(max_val * 100))
        slider.setValue(int(default_val * 100))
        slider.setSingleStep(int(step * 100))
        
        lbl_val = QLabel(f"{default_val:.2f}")
        lbl_val.setFixedWidth(50)
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        slider.valueChanged.connect(lambda v, l=lbl_val: l.setText(f"{v/100:.2f}"))
        
        row.addWidget(lbl_name)
        row.addWidget(slider)
        row.addWidget(lbl_val)
        
        return slider, row


    def setup_tools_tab(self):
        import subprocess
        layout = QVBoxLayout(self.tab_tools)
        
        lbl_info = QLabel("【音源設定ツール】\n"
                          "1. voicebanks フォルダ内に新しいフォルダを作成し、.labと.wavを入れます\n"
                          "2. ロードボタンで音源フォルダを選択してから以下のツールを実行します")
        lbl_info.setStyleSheet("font-weight: bold; font-size: 14px; color: #4CAF50;")
        layout.addWidget(lbl_info)

        def run_tool(script_name, req_file, require_metadata=False):
            if not self.core.folder_path:
                QMessageBox.warning(self, "エラー", "先に音源リストからフォルダを選んでロードしてください。")
                return
            tgt_path = os.path.join(self.core.folder_path, req_file)
            if not os.path.exists(tgt_path):
                QMessageBox.warning(self, "エラー", f"音源フォルダ内に {req_file} が見つかりません。")
                return

            try:
                # ツールは d:/0.turtle talk ver1.5 等にある想定
                script_path = os.path.abspath(script_name)
                # target_path のパスを文字列の後ろに入れて標準入力か引数で渡す
                # F0er.py は引数でもパスを受け取れるようになっているが、labConverter等は標準入力を待つ
                # 汎用的に Popen で渡す
                CREATE_NO_WINDOW = 0x08000000
                p = subprocess.Popen([sys.executable, script_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.core.folder_path, creationflags=CREATE_NO_WINDOW, text=True, encoding='utf-8')
                stdout, stderr = p.communicate(input=f'"{tgt_path}"\n')
                
                # ログ表示ダイアログ
                msg = QMessageBox(self)
                msg.setWindowTitle(f"{script_name} 実行結果")
                msg.setText(f"実行完了しました。\n[出力]\n{stdout[-300:]}")
                msg.exec()
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "エラー", f"ツールの実行に失敗しました:\n{str(e)}")

        btn_lab = QPushButton("STEP1: labConverter 実行 (.lab -> metadata.csv 作成)")
        btn_lab.setMinimumHeight(40)
        btn_lab.clicked.connect(lambda: run_tool("labConverter.py", os.listdir(self.core.folder_path)[0] if any(f.endswith('.lab') for f in os.listdir(self.core.folder_path)) else "error.lab"))

        btn_f0 = QPushButton("STEP2: F0er 実行 (metadata.csv -> F0Data.csv 作成)")
        btn_f0.setMinimumHeight(40)
        btn_f0.clicked.connect(lambda: run_tool("F0er.py", "metadata.csv"))

        btn_idx = QPushButton("STEP3: phoneme_indexCreater 実行 (metadata.csv -> phoneme_index.json 作成)")
        btn_idx.setMinimumHeight(40)
        btn_idx.clicked.connect(lambda: run_tool("phoneme_indexCreater.py", "metadata.csv"))

        layout.addWidget(btn_lab)
        layout.addWidget(btn_f0)
        layout.addWidget(btn_idx)
        
        layout.addSpacing(20)
        lbl_cfg = QLabel("【設定・辞書エディタ】")
        lbl_cfg.setStyleSheet("font-weight: bold; font-size: 14px; color: #4CAF50;")
        layout.addWidget(lbl_cfg)
        
        dict_layout = QHBoxLayout()
        self.txt_new_dict = QTextEdit()
        self.txt_new_dict.setMaximumHeight(35)
        self.txt_new_dict.setPlaceholderText("新しい辞書名 (例: custom_dict)")
        btn_new_dict = QPushButton("辞書を新規作成")
        btn_new_dict.setMinimumHeight(35)
        btn_new_dict.clicked.connect(self.create_new_dict)
        dict_layout.addWidget(self.txt_new_dict)
        dict_layout.addWidget(btn_new_dict)
        layout.addLayout(dict_layout)
        
        btn_cfg = QPushButton("選択中の音源の config.json を編集")
        btn_cfg.setMinimumHeight(40)
        btn_cfg.clicked.connect(self.open_config_editor)
        layout.addWidget(btn_cfg)
        
        btn_dict = QPushButton("現在選択中のユーザー辞書を編集")
        btn_dict.setMinimumHeight(40)
        btn_dict.clicked.connect(self.open_dict_editor)
        layout.addWidget(btn_dict)
        
        layout.addStretch()

    def open_config_editor(self):
        if not self.core.folder_path:
            QMessageBox.warning(self, "エラー", "先に音源をロードしてください。")
            return
        path = os.path.join(self.core.folder_path, "config.json")
        dlg = JsonEditorDialog(path, self)
        dlg.exec()

    def create_new_dict(self):
        name = self.txt_new_dict.toPlainText().strip()
        if not name:
            QMessageBox.warning(self, "エラー", "辞書名を入力してください。")
            return
        if not name.endswith(".json"):
            name += ".json"
            
        base_dir = "user_dicts"
        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)
            
        path = os.path.join(base_dir, name)
        if not os.path.exists(path):
            with open(path, 'w', encoding='utf-8') as f:
                f.write("{}")
            QMessageBox.information(self, "完了", f"{name} を作成しました。")
            self.txt_new_dict.clear()
            self.populate_dict_list()
        else:
            QMessageBox.warning(self, "エラー", "すでに同名の辞書が存在します。")

    def open_dict_editor(self):
        dict_name = self.combo_dict.currentText()
        if not dict_name or dict_name == "(辞書なし)":
            QMessageBox.warning(self, "エラー", "編集する辞書を選択してください。")
            return
        
        path = get_resource_path(os.path.join("user_dicts", dict_name))
        dlg = UserDictEditorDialog(path, self)
        if dlg.exec():
            # 辞書保存後に反映させるためコンボボックスの選択イベントを再発火させる
            self.on_dict_changed(self.combo_dict.currentText())

    def populate_dict_list(self):
        self.combo_dict.blockSignals(True)
        self.combo_dict.clear()
        base_dir = "user_dicts"
        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)
            # user_dict.jsonを初期辞書としてコピーするか移行する
            if os.path.exists(get_resource_path("user_dict.json")):
                import shutil
                shutil.move(get_resource_path("user_dict.json"), os.path.join(base_dir, "def_user_dict.json"))
            
        files = [f for f in os.listdir(base_dir) if f.endswith('.json')]
        if not files:
            self.combo_dict.addItem("(辞書なし)")
            set_active_dict("")
        else:
            self.combo_dict.addItems(files)
            # Default to first
            set_active_dict(get_resource_path(os.path.join(base_dir, files[0])))
        self.combo_dict.blockSignals(False)
        
    def on_dict_changed(self, text):
        if text and text != "(辞書なし)":
            set_active_dict(get_resource_path(os.path.join("user_dicts", text)))
        else:
            set_active_dict("")

    def apply_styles(self):
        # 視認性の高いライトテーマ（黒文字）の適用
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f0f0; }
            QWidget { color: #000000; font-family: 'Segoe UI', Meiryo, sans-serif; font-size: 14px;}
            QGroupBox { border: 1px solid #ccc; border-radius: 5px; margin-top: 10px; font-weight: bold;}
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }
            QPushButton { background-color: #e0e0e0; border: 1px solid #aaa; border-radius: 5px; padding: 5px 15px; color: #000;}
            QPushButton:hover { background-color: #d0d0d0; border-color: #888; }
            QPushButton:pressed { background-color: #c0c0c0; }
            QPushButton:disabled { background-color: #f5f5f5; color: #aaa; border-color: #ddd; }
            QTabWidget::pane { border: 1px solid #ccc; background: #f0f0f0; border-radius: 4px; }
            QTabBar::tab { background: #e0e0e0; border: 1px solid #ccc; padding: 8px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; color: #000;}
            QTabBar::tab:selected { background: #fff; border-bottom-color: #fff; font-weight: bold; }
            QProgressBar { border: 1px solid #ccc; border-radius: 3px; background-color: #fff; color: #000; }
            QProgressBar::chunk { background-color: #4CAF50; border-radius: 2px;}
        """)

    def populate_voicebank_list(self):
        self.combo_voice.clear()
        base_dir = get_resource_path("voicebanks")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)
            
        dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        if not dirs:
            self.combo_voice.addItem("(voicebanksフォルダ内が空です)")
            self.btn_load_voice.setEnabled(False)
        else:
            self.combo_voice.addItems(dirs)
            self.btn_load_voice.setEnabled(True)

    def select_voicebank(self):
        folder_name = self.combo_voice.currentText()
        folder = get_resource_path(os.path.join("voicebanks", folder_name))
        
        if folder in self.cores_cache:
            self.core = self.cores_cache[folder]
            self.on_voice_loaded(True, "Cache loaded")
            return
            
        if os.path.exists(folder):
            self.btn_load_voice.setEnabled(False)
            self.progress_bar.setValue(0)
            
            new_core = TTSCore()
            self.cores_cache[folder] = new_core
            self.core = new_core
            
            self.loader_thread = VoiceLoadThread(self.core, folder)
            self.loader_thread.progress.connect(self.update_progress)
            self.loader_thread.finished.connect(self.on_voice_loaded)
            self.loader_thread.start()

    def update_progress(self, val, msg):
        self.progress_bar.setValue(val)

    def on_voice_loaded(self, success, msg):
        self.btn_load_voice.setEnabled(True)
        self.progress_bar.setValue(100 if success else 0)
        if success:
            icon_path = os.path.join(self.core.folder_path, "icon.png")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(self.core.folder_path, "icon.jpg")
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path)
                self.lbl_icon.setPixmap(pixmap.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.lbl_icon.clear()
                self.lbl_icon.setText("No Icon")
                
            # Update combo_voice in Dialogue blocks to match
            for i in range(self.blocks_layout.count()):
                w = self.blocks_layout.itemAt(i).widget()
                if isinstance(w, DialogueBlockWidget):
                    if w.combo_voice.count() == 0:
                        w.combo_voice.addItems([self.combo_voice.itemText(k) for k in range(self.combo_voice.count()) if self.combo_voice.itemText(k) != "(voicebanksフォルダ内が空です)"])
            for i in range(self.adv_blocks_layout.count()):
                w = self.adv_blocks_layout.itemAt(i).widget()
                if isinstance(w, AdvancedTabWidget):
                    if w.combo_voice.count() == 0:
                        w.combo_voice.addItems([self.combo_voice.itemText(k) for k in range(self.combo_voice.count()) if self.combo_voice.itemText(k) != "(voicebanksフォルダ内が空です)"])
        else:
            QMessageBox.critical(self, "エラー", f"音源のロードに失敗しました:\n{msg}")

    def get_cached_core(self, folder_name):
        folder = get_resource_path(os.path.join("voicebanks", folder_name))
        if folder not in self.cores_cache:
            core = TTSCore()
            core.load_voicebank(folder)
            self.cores_cache[folder] = core
        return self.cores_cache[folder]

    def play_audio(self):
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:  # Beginner Mode (掛け合いブロック)
            blocks = []
            for i in range(self.blocks_layout.count()):
                w = self.blocks_layout.itemAt(i).widget()
                if isinstance(w, DialogueBlockWidget):
                    blocks.append(w)
            
            if not blocks: return
            
            try:
                self.btn_play.setEnabled(False)
                self.btn_play.setText("一括合成中...")
                QApplication.processEvents()
                
                audio_fragments = []
                final_sr = 44100
                import numpy as np
                
                for b in blocks:
                    text = b.txt_input.toPlainText().strip()
                    if not text: continue
                    
                    v_name = b.combo_voice.currentText()
                    b_core = self.get_cached_core(v_name)
                    
                    b_core.config["speed_scale"] = b.sl_speed.value() / 100.0
                    b_core.config["pitch_scale"] = b.sl_pitch.value() / 100.0
                    b_core.config["intonation_scale"] = b.sl_int.value() / 100.0
                    
                    audio, sr = b_core.synthesize_text(text)
                    if audio is not None:
                        final_sr = sr
                        audio_fragments.append(audio)
                        # Add 0.5s pause between blocks
                        audio_fragments.append(np.zeros(int(final_sr * 0.5)))
                
                if audio_fragments:
                    final_audio = np.concatenate(audio_fragments)
                    import soundfile as sf
                    import tempfile
                    import winsound
                    tmp_wav = os.path.join(tempfile.gettempdir(), "turtle_temp.wav")
                    sf.write(tmp_wav, final_audio, final_sr)
                    winsound.PlaySound(tmp_wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
                else:
                    QMessageBox.warning(self, "エラー", "読み上げるテキストがないか、合成に失敗しました。")
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "エラー", f"合成中にエラーが発生しました:\n{str(e)}")
            finally:
                self.btn_play.setEnabled(True)
                self.btn_play.setText("▶ 再生 (Play)")

        elif current_tab == 1:
            blocks = []
            for i in range(self.adv_blocks_layout.count()):
                w = self.adv_blocks_layout.itemAt(i).widget()
                if isinstance(w, AdvancedTabWidget):
                    blocks.append(w)
            
            if not blocks: return
            
            try:
                self.btn_play.setEnabled(False)
                self.btn_play.setText("一括合成中...")
                QApplication.processEvents()
                
                audio_fragments = []
                final_sr = 44100
                import numpy as np
                
                for b in blocks:
                    b.set_highlight(True)
                    QApplication.processEvents()
                    
                    data = b.intermediate_data
                    if not data:
                        b.set_highlight(False)
                        continue
                    v_name = b.combo_voice.currentText()
                    b_core = self.get_cached_core(v_name)
                    
                    audio, sr, align = b_core.synthesize_from_intermediate(data)
                    b.last_alignment = align
                    b.update_plot()
                    
                    if audio is not None:
                        final_sr = sr
                        audio_fragments.append(audio)
                        # Add 0.5s pause
                        audio_fragments.append(np.zeros(int(final_sr * 0.5)))
                    b.set_highlight(False)
                        
                if audio_fragments:
                    final_audio = np.concatenate(audio_fragments)
                    import soundfile as sf
                    import tempfile
                    import winsound
                    tmp_wav = os.path.join(tempfile.gettempdir(), "turtle_temp.wav")
                    sf.write(tmp_wav, final_audio, final_sr)
                    winsound.PlaySound(tmp_wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
                else:
                    QMessageBox.warning(self, "エラー", "合成に失敗しました。")
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "エラー", f"合成中にエラーが発生しました:\n{str(e)}")
            finally:
                self.btn_play.setEnabled(True)
                self.btn_play.setText("▶ 再生 (Play)")
                

    def save_project(self):
        import json
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        file_path, _ = QFileDialog.getSaveFileName(self, "プロジェクトを保存", "", "Turtle Project (*.ttprj)")
        if not file_path: return
        
        data = {"version": "1.5", "blocks": []}
        # 簡単モード
        for i in range(self.blocks_layout.count()):
            w = self.blocks_layout.itemAt(i).widget()
            if isinstance(w, DialogueBlockWidget):
                b_data = {
                    "tab": "beginner", "text": w.txt_input.toPlainText(),
                    "voice": w.combo_voice.currentText(),
                    "speed": w.sl_speed.value(), "pitch": w.sl_pitch.value(), "intonation": w.sl_int.value()
                }
                data["blocks"].append(b_data)
        # 詳細モード
        for i in range(self.adv_blocks_layout.count()):
            w = self.adv_blocks_layout.itemAt(i).widget()
            if isinstance(w, AdvancedTabWidget):
                b_data = {
                    "tab": "advanced", "text": w.txt_input.toPlainText(),
                    "voice": w.combo_voice.currentText(),
                    "intermediate_data": None
                }
                if w.intermediate_data:
                    idat = w.intermediate_data.copy()
                    if "f0_values" in idat: idat["f0_values"] = idat["f0_values"].tolist()
                    b_data["intermediate_data"] = idat
                data["blocks"].append(b_data)
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "完了", "プロジェクトを保存しました。")

    def load_project(self):
        import json
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        file_path, _ = QFileDialog.getOpenFileName(self, "プロジェクトを開く", "", "Turtle Project (*.ttprj)")
        if not file_path: return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.clear_all_blocks()
            for b in data.get("blocks", []):
                if b["tab"] == "beginner":
                    new_b = self.add_dialogue_block()
                    new_b.txt_input.setPlainText(b["text"])
                    new_b.combo_voice.setCurrentText(b["voice"])
                    new_b.sl_speed.setValue(b["speed"])
                    new_b.sl_pitch.setValue(b["pitch"])
                    new_b.sl_int.setValue(b["intonation"])
                else:
                    new_b = self.add_advanced_block()
                    new_b.txt_input.setPlainText(b["text"])
                    new_b.combo_voice.setCurrentText(b["voice"])
                    if b["intermediate_data"]:
                        import numpy as np
                        idat = b["intermediate_data"]
                        if "f0_values" in idat: idat["f0_values"] = np.array(idat["f0_values"])
                        new_b.intermediate_data = idat
                        new_b.update_ui_from_data()
                        new_b.update_plot()
            QMessageBox.information(self, "完了", "プロジェクトを読み込みました。")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"読込失敗: {str(e)}")

    def export_audio(self):
        from PyQt6.QtWidgets import QMessageBox
        current_tab = self.tabs.currentIndex()
        blocks = []
        if current_tab == 0:
            for i in range(self.blocks_layout.count()):
                w = self.blocks_layout.itemAt(i).widget()
                if isinstance(w, DialogueBlockWidget): blocks.append(w)
        elif current_tab == 1:
            for i in range(self.adv_blocks_layout.count()):
                w = self.adv_blocks_layout.itemAt(i).widget()
                if isinstance(w, AdvancedTabWidget): blocks.append(w)
        else: return

        if not blocks: return
        msg = QMessageBox(self)
        msg.setWindowTitle("音声書き出し")
        msg.setText("書き出し方法を選択してください。")
        btn_merge = msg.addButton("1つのファイルに結合", QMessageBox.ButtonRole.ActionRole)
        btn_sep = msg.addButton("ブロックごとに個別保存", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("キャンセル", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() == btn_merge:
            self._export_merged(blocks)
        elif msg.clickedButton() == btn_sep:
            self._export_separate(blocks)

    def _export_merged(self, blocks):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        file_path, _ = QFileDialog.getSaveFileName(self, "音声を保存 (結合)", "output.wav", "WAV Files (*.wav)")
        if not file_path: return
        try:
            import numpy as np
            import soundfile as sf
            audio_fragments = []
            sr = 44100
            for b in blocks:
                if hasattr(b, 'on_analyze'):
                    if not b.intermediate_data: b.on_analyze()
                    v_name = b.combo_voice.currentText()
                    core = self.get_cached_core(v_name)
                    audio, sr = core.synthesize_from_intermediate(b.intermediate_data)
                else:
                    v_name = b.combo_voice.currentText()
                    core = self.get_cached_core(v_name)
                    core.config["speed_scale"] = b.sl_speed.value() / 100.0
                    core.config["pitch_scale"] = b.sl_pitch.value() / 100.0
                    core.config["intonation_scale"] = b.sl_int.value() / 100.0
                    audio, sr = core.synthesize_text(b.txt_input.toPlainText())
                if audio is not None:
                    audio_fragments.append(audio)
                    audio_fragments.append(np.zeros(int(sr * 0.5)))
            if audio_fragments:
                final_audio = np.concatenate(audio_fragments)
                sf.write(file_path, final_audio, sr)
                QMessageBox.information(self, "完了", "結合保存が完了しました。")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存失敗: {str(e)}")

    def _export_separate(self, blocks):
        import os
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        dir_path = QFileDialog.getExistingDirectory(self, "保存先のフォルダを選択")
        if not dir_path: return
        try:
            import soundfile as sf
            for i, b in enumerate(blocks):
                if hasattr(b, 'on_analyze'):
                    if not b.intermediate_data: b.on_analyze()
                    v_name = b.combo_voice.currentText()
                    core = self.get_cached_core(v_name)
                    audio, sr = core.synthesize_from_intermediate(b.intermediate_data)
                else:
                    v_name = b.combo_voice.currentText()
                    core = self.get_cached_core(v_name)
                    core.config["speed_scale"] = b.sl_speed.value() / 100.0
                    core.config["pitch_scale"] = b.sl_pitch.value() / 100.0
                    core.config["intonation_scale"] = b.sl_int.value() / 100.0
                    audio, sr = core.synthesize_text(b.txt_input.toPlainText())
                if audio is not None:
                    sf.write(os.path.join(dir_path, f"block_{i+1:02d}.wav"), audio, sr)
            QMessageBox.information(self, "完了", "個別保存が完了しました。")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"個別保存失敗: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TurtleVoiceGUI()
    window.show()
    sys.exit(app.exec())
