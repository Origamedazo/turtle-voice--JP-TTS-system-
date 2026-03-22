# -*- coding: utf-8 -*-
import pyqtgraph as pg
from PyQt6.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox, QGroupBox, QHBoxLayout, 
                             QHeaderView, QLabel, QMessageBox, QPushButton, QSpinBox, 
                             QSplitter, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
import pyqtgraph as pg
import numpy as np
import os

class F0PlotWidget(pg.PlotWidget):
    def __init__(self, adv_tab, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.adv_tab = adv_tab
        self.drawing = False
        self.setMouseEnabled(x=False, y=False)
        
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            try:
                pos = self.mapToScene(ev.pos())
                self.draw_point(pos)
            except AttributeError:
                pass
        else:
            super().mousePressEvent(ev)
            
    def mouseMoveEvent(self, ev):
        if self.drawing:
            try:
                pos = self.mapToScene(ev.pos())
                self.draw_point(pos)
            except AttributeError:
                pass
        else:
            super().mouseMoveEvent(ev)
            
    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.drawing = False
            self.adv_tab.sync_f0_to_table()
        super().mouseReleaseEvent(ev)
        
    def draw_point(self, scene_pos):
        view_pos = self.getViewBox().mapSceneToView(scene_pos)
        x, y = view_pos.x(), view_pos.y()
        self.adv_tab.update_f0_at_time(x, y)


class AccentPlotWidget(pg.PlotWidget):
    def __init__(self, adv_tab, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.adv_tab = adv_tab
        self.dragging_idx = None
        self.setMouseEnabled(x=False, y=False)
        
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            try:
                view_pos = self.getViewBox().mapSceneToView(self.mapToScene(ev.pos()))
                self.dragging_idx = self.adv_tab.get_closest_accent_node(view_pos.x(), view_pos.y())
            except AttributeError:
                pass
        else:
            super().mousePressEvent(ev)
            
    def mouseMoveEvent(self, ev):
        if self.dragging_idx is not None:
            try:
                view_pos = self.getViewBox().mapSceneToView(self.mapToScene(ev.pos()))
                self.adv_tab.update_accent_node(self.dragging_idx, view_pos.y())
            except AttributeError:
                pass
        else:
            super().mouseMoveEvent(ev)
            
    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.dragging_idx = None
            self.adv_tab.sync_f0_to_table()
        super().mouseReleaseEvent(ev)


class AdvancedTabWidget(QWidget):
    def __init__(self, main_gui):
        super().__init__()
        self.main_gui = main_gui
        self.intermediate_data = []
        self.last_alignment = []
        
        # グラフが潰れないように最小高さを設定
        self.setMinimumHeight(550)
        
        self.v_lines = []
        self.pause_regions = []
        self.flat_indices = []
        self.init_ui()

    def init_ui(self):
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
        # メインの音源リストから項目をコピー
        self.combo_voice.addItems([self.main_gui.combo_voice.itemText(i) for i in range(self.main_gui.combo_voice.count()) if self.main_gui.combo_voice.itemText(i) != "(voicebanksフォルダ内が空です)"])
        
        self.combo_voice.currentTextChanged.connect(self.update_icon)
        
        # 初期選択とアイコン反映
        curr = self.main_gui.combo_voice.currentText()
        if curr: 
            self.combo_voice.setCurrentText(curr)
        self.update_icon(self.combo_voice.currentText())
        
        voice_layout.addWidget(self.combo_voice)
        voice_layout.addStretch()
        
        top_layout.addWidget(self.lbl_icon)
        top_layout.addLayout(voice_layout)
        
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("詳細モードで解析するテキストを入力")
        self.txt_input.setMaximumHeight(60)
        self.txt_input.setStyleSheet("background-color: #ffffff; color: #000000; border: 1px solid #aaa; border-radius: 4px; padding: 5px;")
        # フォーカス時（クリック時）に自動展開
        self.txt_input.installEventFilter(self)
        
        btn_analyze = QPushButton("テキスト解析＆波形生成")
        btn_analyze.setMinimumHeight(60)
        btn_analyze.clicked.connect(self.on_analyze)
        self.btn_analyze = btn_analyze
        
        self.btn_play_local = QPushButton("▶\n再生")
        self.btn_play_local.setMinimumWidth(55) # 固定幅を最小幅に変更
        self.btn_play_local.setMinimumHeight(60)
        self.btn_play_local.clicked.connect(self.play_local)
        
        self.btn_save_local = QPushButton("💾\n保存")
        self.btn_save_local.setMinimumWidth(55)
        self.btn_save_local.setMinimumHeight(60)
        self.btn_save_local.clicked.connect(self.save_local)
        
        btn_del = QPushButton("削除")
        btn_del.setMinimumWidth(60)
        btn_del.setMinimumHeight(60)
        btn_del.setStyleSheet("background-color: #ffebee; color: #c62828;")
        btn_del.clicked.connect(self.deleteLater)

        self.btn_fold = QPushButton("▼") # 最初は展開
        self.btn_fold.setToolTip("グラフエリアを折りたたむ/展開する")
        self.btn_fold.setFixedSize(35, 60)
        self.btn_fold.clicked.connect(self.toggle_fold)
        
        self.btn_expand = QPushButton("🔍\n拡大")
        self.btn_expand.setToolTip("別ウィンドウで大きく編集")
        self.btn_expand.setFixedSize(45, 60)
        self.btn_expand.clicked.connect(self.on_expand)
        
        self.lbl_h = QLabel("高さ:")
        self.spin_h = QSpinBox()
        self.spin_h.setRange(200, 1500)
        self.spin_h.setValue(550)
        self.spin_h.setFixedWidth(60)
        self.spin_h.setMinimumHeight(60)
        self.spin_h.valueChanged.connect(self.update_height)
        
        top_layout.addWidget(self.txt_input)
        top_layout.addWidget(btn_analyze)
        top_layout.addWidget(self.btn_play_local)
        top_layout.addWidget(self.btn_save_local)
        top_layout.addWidget(self.lbl_h)
        top_layout.addWidget(self.spin_h)
        top_layout.addWidget(self.btn_expand)
        top_layout.addWidget(self.btn_fold)
        top_layout.addWidget(btn_del)
        layout.addLayout(top_layout)

        self.splitter_v = QSplitter(Qt.Orientation.Vertical)
        
        # 1. Waveform Plot
        self.wf_plot = pg.PlotWidget(title="波形 ＆ タイミング調整 (ドラッグで境界を移動)")
        self.wf_plot.setBackground('#ffffff')
        self.wf_plot.setMouseEnabled(x=True, y=False)
        self.wf_curve = self.wf_plot.plot(pen=pg.mkPen(color='#555', width=1), alpha=0.8)
        self.wf_plot.getAxis('bottom').setPen('k')
        self.wf_plot.getAxis('bottom').setTextPen('k')
        self.wf_plot.getAxis('left').setPen('k')
        self.wf_plot.getAxis('left').setTextPen('k')
        self.splitter_v.addWidget(self.wf_plot)

        # 2. F0 Hand-drawn Plot
        self.f0_plot = F0PlotWidget(self, title="ピッチ補正曲線 (マウスドラッグで手書き編集)")
        self.f0_plot.setBackground('#ffffff')
        self.f0_plot.setLabel('left', 'Frequency (Hz)')
        self.f0_plot.getAxis('bottom').setPen('k')
        self.f0_plot.getAxis('bottom').setTextPen('k')
        self.f0_plot.getAxis('left').setPen('k')
        self.f0_plot.getAxis('left').setTextPen('k')
        self.f0_plot.showGrid(x=True, y=True, alpha=0.3)
        self.f0_curve = self.f0_plot.plot(pen=pg.mkPen(color='#4CAF50', width=2), symbol='o', symbolBrush='#4CAF50')
        self.splitter_v.addWidget(self.f0_plot)

        # 3. Accent Nodes Plot
        self.acc_plot = AccentPlotWidget(self, title="アクセント/ベースピッチ ノード (上下ドラッグで編集)")
        self.acc_plot.setBackground('#ffffff')
        self.acc_plot.getAxis('bottom').setPen('k')
        self.acc_plot.getAxis('bottom').setTextPen('k')
        self.acc_plot.getAxis('left').setPen('k')
        self.acc_plot.getAxis('left').setTextPen('k')
        self.acc_curve = self.acc_plot.plot(pen=pg.mkPen(color='#ff9800', width=2), symbol='s', symbolBrush='#ff9800', symbolSize=10)
        self.splitter_v.addWidget(self.acc_plot)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["音素", "Duration(ms)", "F0(Hz)", "TID(素材候補)", "フレーズID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setStyleSheet("QTableWidget { background-color: #ffffff; color: #000000; gridline-color: #ccc; } QHeaderView::section { background-color: #e0e0e0; color: #000; padding: 4px; border: 1px solid #ccc; }")
        
        splitter_main = QSplitter(Qt.Orientation.Horizontal)
        splitter_main.addWidget(self.table)
        splitter_main.addWidget(self.splitter_v)
        splitter_main.setSizes([350, 600])
        
        self.splitter_main = splitter_main
        layout.addWidget(splitter_main, stretch=1)

    def toggle_fold(self, force_open=None):
        if force_open is True:
            is_hidden = True # 隠れていると見なして show する
        elif force_open is False:
            is_hidden = False # 展開されていると見なして hide する
        else:
            is_hidden = self.splitter_main.isHidden()
            
        self.splitter_main.setHidden(not is_hidden)
        self.btn_fold.setText("▲" if is_hidden else "▼")
        if not is_hidden:
            self.setMinimumHeight(80) 
        else:
            self.update_height(self.spin_h.value())

    def mousePressEvent(self, event):
        # 選択（クリック）されたら自動展開
        if self.splitter_main.isHidden():
            self.toggle_fold(force_open=True)
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj == self.txt_input and event.type() == QEvent.Type.FocusIn:
            if self.splitter_main.isHidden():
                self.toggle_fold(force_open=True)
        return super().eventFilter(obj, event)

    def update_height(self, val):
        if not self.splitter_main.isHidden():
            self.setMinimumHeight(val)
        self.splitter_main.setMinimumHeight(val - 100) # ヘッダー分を引く感じ

    def on_expand(self):
        # 拡大ダイアログを開く
        from PyQt6.QtWidgets import QDialog, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle(f"グラフ詳細編集 - {self.txt_input.toPlainText()[:10]}...")
        dlg.resize(1000, 700)
        dlg_layout = QVBoxLayout(dlg)
        
        # 共有のプロットを表示（簡易的に元のウィジェットを移すか、同様のものを生成）
        # 完全な同期は複雑なので、今回はダイアログ専用のレイアウトを構築し、
        # 編集結果を確定時に反映させる方式を想定。
        # または、splitter_v 自体を一時的に dlg に移し、閉じるときに戻す。
        
        original_parent = self.splitter_v.parent()
        dlg_layout.addWidget(self.splitter_v)
        
        dlg.exec()
        
        # 戻す
        if original_parent:
            # splitter_main に戻す (index 1 が splitter_v だった)
            self.splitter_main.addWidget(self.splitter_v)

    def update_icon(self, text):
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

    def on_analyze(self):
        text = self.txt_input.toPlainText().strip()
        voice_name = self.combo_voice.currentText()
        if not text or not voice_name or voice_name == "(voicebanksフォルダ内が空です)": return
        
        core = self.main_gui.get_cached_core(voice_name)
        if not core.is_loaded: return
        
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("合成・解析中...")
        QApplication.processEvents()
        
        try:
            self.intermediate_data = core.text_to_intermediate(text)
            
            # Generate temporary waveform for visualization
            audio, sr, align = core.synthesize_from_intermediate(self.intermediate_data)
            self.last_alignment = align

            if audio is not None:
                # Downsample waveform for display performance
                target_sr = 2000
                ds_factor = max(1, sr // target_sr)
                audio_ds = audio[::ds_factor]
                time_axis = np.linspace(0, (len(audio_ds)/target_sr)*1000, len(audio_ds))
                self.wf_curve.setData(time_axis, audio_ds)
            else:
                self.wf_curve.setData([], [])
                
            self.update_ui_from_data()
        finally:
            self.btn_analyze.setEnabled(True)
            self.btn_analyze.setText("テキスト解析＆波形生成")

    def play_local(self):
        voice_name = self.combo_voice.currentText()
        if not voice_name or not self.intermediate_data: return
        core = self.main_gui.get_cached_core(voice_name)
        if not core.is_loaded: return
        
        self.btn_play_local.setEnabled(False)
        self.set_highlight(True)
        QApplication.processEvents()
        try:
            audio, sr, _ = core.synthesize_from_intermediate(self.intermediate_data)
            if audio is not None:
                import soundfile as sf
                import tempfile
                import winsound
                import os
                tmp_wav = os.path.join(tempfile.gettempdir(), "turtle_temp_adv_local.wav")
                sf.write(tmp_wav, audio, sr)
                winsound.PlaySound(tmp_wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
        finally:
            self.btn_play_local.setEnabled(True)
            self.set_highlight(False)

    def save_local(self):
        voice_name = self.combo_voice.currentText()
        if not voice_name or not self.intermediate_data: return
        core = self.main_gui.get_cached_core(voice_name)
        if not core.is_loaded: return
        
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        fpath, _ = QFileDialog.getSaveFileName(self, "音声を保存", f"{voice_name}_adv.wav", "WAV Files (*.wav)")
        if not fpath: return
        
        self.btn_save_local.setEnabled(False)
        self.set_highlight(True)
        QApplication.processEvents()
        try:
            audio, sr, _ = core.synthesize_from_intermediate(self.intermediate_data)
            if audio is not None:
                import soundfile as sf
                sf.write(fpath, audio, sr)
                QMessageBox.information(self, "保存完了", f"音声を保存しました:\n{fpath}")
        finally:
            self.btn_save_local.setEnabled(True)
            self.set_highlight(False)

    def set_highlight(self, active: bool):
        if active:
            # ハイライト色（処理中・再生中）
            self.setStyleSheet("""
                QGroupBox { border: 3px solid #4CAF50; background-color: #f1f8e9; }
                QTextEdit { background-color: #e8f5e9; border: 1px solid #4CAF50; color: #004d40; }
            """)
        else:
            self.setStyleSheet("")

    def reanalyze_waveform_silently(self):
        voice_name = self.combo_voice.currentText()
        if not voice_name or not self.intermediate_data: return
        core = self.main_gui.get_cached_core(voice_name)
        if not core.is_loaded: return
        try:
            audio, sr, align = core.synthesize_from_intermediate(self.intermediate_data)
            self.last_alignment = align
            if audio is not None:
                target_sr = 2000
                ds_factor = max(1, sr // target_sr)
                audio_ds = audio[::ds_factor]
                time_axis = np.linspace(0, (len(audio_ds)/target_sr)*1000, len(audio_ds))
                self.wf_curve.setData(time_axis, audio_ds)
            else:
                self.wf_curve.setData([], [])
                
            self.update_plot()
        except Exception as e:
            print("再合成エラー:", e)

    def rebuild_flat_indices(self):
        self.flat_indices = []
        for p_idx, phrase in enumerate(self.intermediate_data):
            for i in range(len(phrase["phonemes"])):
                self.flat_indices.append((p_idx, i))

    def get_closest_accent_node(self, x, y):
        self.rebuild_flat_indices()
        best_dist = float('inf')
        best_idx = None
        
        use_alignment = bool(self.last_alignment)
        
        for flat_i, (p_idx, i) in enumerate(self.flat_indices):
            f0 = self.intermediate_data[p_idx]["target_f0s"][i]
            
            if use_alignment and flat_i < len(self.last_alignment):
                x_pos = self.last_alignment[flat_i]['center_ms']
            else:
                x_pos = sum(self.intermediate_data[pi]["target_durs"][ii] for fi, (pi, ii) in enumerate(self.flat_indices) if fi < flat_i) + self.intermediate_data[p_idx]["target_durs"][i]/2.0
            
            dist = (x - x_pos)**2 + ((y - f0)/5.0)**2
            if dist < best_dist and dist < 10000:
                best_dist = dist
                best_idx = flat_i
                
        return best_idx

    def update_accent_node(self, flat_idx, y):
        p_idx, i = self.flat_indices[flat_idx]
        self.intermediate_data[p_idx]["target_f0s"][i] = max(50, min(1000, y))
        self.update_plot()

    def update_f0_at_time(self, x, y):
        use_alignment = bool(self.last_alignment)
        if use_alignment:
            for align in self.last_alignment:
                if align['start_ms'] <= x <= align['end_ms']:
                    p_idx, i = align['p_idx'], align['i']
                    self.intermediate_data[p_idx]["target_f0s"][i] = max(50, min(1000, y))
                    self.update_plot()
                    return
            return
            
        current_time = 0.0
        for p_idx, phrase in enumerate(self.intermediate_data):
            for i, dur in enumerate(phrase["target_durs"]):
                current_time += dur
                if x <= current_time:
                    phrase["target_f0s"][i] = max(50, min(1000, y))
                    self.update_plot()
                    return

    def sync_f0_to_table(self):
        self.table.blockSignals(True)
        row = 0
        for p_idx, phrase in enumerate(self.intermediate_data):
            for i in range(len(phrase["phonemes"])):
                dur = phrase["target_durs"][i]
                f0 = phrase["target_f0s"][i]
                
                # Assume column 1 is Duration, 2 is F0
                dur_spin = self.table.cellWidget(row, 1)
                if dur_spin: dur_spin.setValue(dur)
                
                f0_spin = self.table.cellWidget(row, 2)
                if f0_spin: f0_spin.setValue(f0)
                
                row += 1
        self.table.blockSignals(False)

    def on_timing_dragged(self, line, flat_idx):
        new_time = line.value()
        p_idx, i = self.flat_indices[flat_idx]
        
        if bool(self.last_alignment) and flat_idx < len(self.last_alignment):
            align = self.last_alignment[flat_idx]
            delta = new_time - align['end_ms']
            
            new_dur = max(10, self.intermediate_data[p_idx]["target_durs"][i] + delta)
            self.intermediate_data[p_idx]["target_durs"][i] = new_dur
            
            # Update visualization alignment to prevent snapping back
            align['end_ms'] += delta
            align['center_ms'] = (align['start_ms'] + align['end_ms']) / 2.0
            for fi in range(flat_idx + 1, len(self.last_alignment)):
                self.last_alignment[fi]['start_ms'] += delta
                self.last_alignment[fi]['end_ms'] += delta
                self.last_alignment[fi]['center_ms'] += delta
        else:
            start_time = 0.0
            for fi in range(flat_idx):
                pi, ii = self.flat_indices[fi]
                start_time += self.intermediate_data[pi]["target_durs"][ii]
            new_dur = max(10, new_time - start_time)
            self.intermediate_data[p_idx]["target_durs"][i] = new_dur
            
        self.sync_f0_to_table()
        self.update_plot()

    def update_ui_from_data(self):
        self.table.setRowCount(0)
        self.table.blockSignals(True)
        self.rebuild_flat_indices()

        for line in self.v_lines:
            self.wf_plot.removeItem(line)
        self.v_lines.clear()
        
        for r in self.pause_regions:
            self.wf_plot.removeItem(r)
        self.pause_regions.clear()

        row = 0
        current_time = 0.0
        
        for flat_idx, (p_idx, i) in enumerate(self.flat_indices):
            phonemes = self.intermediate_data[p_idx]["phonemes"]
            f0s = self.intermediate_data[p_idx]["target_f0s"]
            durs = self.intermediate_data[p_idx]["target_durs"]
            best_tids = self.intermediate_data[p_idx]["best_tids"]
            
            self.table.insertRow(row)
            
            item_ph = QTableWidgetItem(phonemes[i])
            item_ph.setFlags(item_ph.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item_ph)
            
            dur_spin = QDoubleSpinBox()
            dur_spin.setRange(10, 2000)
            dur_spin.setDecimals(1)
            dur_spin.setValue(durs[i])
            dur_spin.valueChanged.connect(lambda v, p=p_idx, idx=i: self.on_dur_change(p, idx, v))
            self.table.setCellWidget(row, 1, dur_spin)
            
            f0_spin = QDoubleSpinBox()
            f0_spin.setRange(0, 2000)
            f0_spin.setDecimals(1)
            f0_spin.setValue(f0s[i])
            f0_spin.valueChanged.connect(lambda v, p=p_idx, idx=i: self.on_f0_change(p, idx, v))
            self.table.setCellWidget(row, 2, f0_spin)
            
            combo = QComboBox()
            core = self.main_gui.get_cached_core(self.combo_voice.currentText())
            cands = core.phoneme_index.get(phonemes[i], [])
            if best_tids[i] not in cands and best_tids[i]:
                cands = [best_tids[i]] + cands
            combo.addItems(cands)
            combo.setCurrentText(best_tids[i])
            combo.currentTextChanged.connect(lambda text, p=p_idx, idx=i: self.on_tid_change(p, idx, text))
            self.table.setCellWidget(row, 3, combo)
            
            item_pid = QTableWidgetItem(f"Phr {p_idx+1}")
            item_pid.setFlags(item_pid.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 4, item_pid)
            
            current_time += durs[i]
            
            # Timing Line
            v_line = pg.InfiniteLine(pos=current_time, angle=90, movable=True, pen=pg.mkPen(color='#ff9800', style=Qt.PenStyle.DashLine))
            v_line.sigPositionChanged.connect(lambda line, fi=flat_idx: self.on_timing_dragged(line, fi))
            self.wf_plot.addItem(v_line)
            self.v_lines.append(v_line)
            
            row += 1

        # Draw pause regions between phrases if alignment is present
        if bool(self.last_alignment):
            for fi in range(len(self.last_alignment) - 1):
                curr = self.last_alignment[fi]
                nxt = self.last_alignment[fi+1]
                if curr['p_idx'] != nxt['p_idx']:
                    gap_start = curr['end_ms']
                    gap_end = nxt['start_ms']
                    if gap_end > gap_start:
                        region = pg.LinearRegionItem([gap_start, gap_end], movable=False, brush=pg.mkBrush(200, 200, 200, 80))
                        for line in region.lines:
                            line.setPen(pg.mkPen(color='#aaa', style=Qt.PenStyle.DashLine))
                        self.wf_plot.addItem(region)
                        self.pause_regions.append(region)

        self.table.blockSignals(False)
        self.update_plot()

    def on_dur_change(self, p_idx, i, val):
        old_dur = self.intermediate_data[p_idx]["target_durs"][i]
        delta = val - old_dur
        self.intermediate_data[p_idx]["target_durs"][i] = val
        
        if bool(self.last_alignment):
            try:
                flat_idx = self.flat_indices.index((p_idx, i))
                align = self.last_alignment[flat_idx]
                align['end_ms'] += delta
                align['center_ms'] = (align['start_ms'] + align['end_ms']) / 2.0
                for fi in range(flat_idx + 1, len(self.last_alignment)):
                    self.last_alignment[fi]['start_ms'] += delta
                    self.last_alignment[fi]['end_ms'] += delta
                    self.last_alignment[fi]['center_ms'] += delta
            except ValueError:
                pass
                
        self.update_plot()
        
    def on_f0_change(self, p_idx, i, val):
        self.intermediate_data[p_idx]["target_f0s"][i] = val
        self.update_plot()

    def on_tid_change(self, p_idx, i, text):
        self.intermediate_data[p_idx]["best_tids"][i] = text

    def update_plot(self):
        f0_values = []
        x_values = []
        ticks = []
        
        for line in self.v_lines:
            line.blockSignals(True)
            
        use_alignment = bool(self.last_alignment)
        line_idx = 0
        
        if use_alignment:
            for align in self.last_alignment:
                p_idx, i = align['p_idx'], align['i']
                if p_idx < len(self.intermediate_data) and i < len(self.intermediate_data[p_idx]["phonemes"]):
                    phrase = self.intermediate_data[p_idx]
                    f0 = phrase["target_f0s"][i]
                    phoneme = phrase["phonemes"][i]
                    
                    f0_values.append(f0)
                    center_x = align['center_ms']
                    x_values.append(center_x)
                    ticks.append((center_x, phoneme))
                    
                    if line_idx < len(self.v_lines):
                        self.v_lines[line_idx].setValue(align['end_ms'])
                    line_idx += 1
        else:
            current_time = 0.0
            for phrase in self.intermediate_data:
                for i in range(len(phrase["phonemes"])):
                    f0 = phrase["target_f0s"][i]
                    dur = phrase["target_durs"][i]
                    phoneme = phrase["phonemes"][i]
                    
                    f0_values.append(f0)
                    center_x = current_time + dur/2.0
                    x_values.append(center_x)
                    ticks.append((center_x, phoneme))
                    
                    current_time += dur
                    if line_idx < len(self.v_lines):
                        self.v_lines[line_idx].setValue(current_time)
                    line_idx += 1
                
        for line in self.v_lines:
            line.blockSignals(False)

        if len(x_values) > 0 and len(f0_values) > 0:
            self.f0_curve.setData(x_values, f0_values)
            self.acc_curve.setData(x_values, f0_values)
        
        # Update Axis Ticks for phoneme names
        for plot_widget in [self.wf_plot, self.f0_plot, self.acc_plot]:
            ax = plot_widget.getAxis('bottom')
            ax.setTicks([ticks])
