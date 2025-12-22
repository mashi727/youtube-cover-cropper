#!/usr/bin/env python3
"""
YouTube Cover Image Cropper
- 16:9 aspect ratio cropping
- Rotation adjustment
- Compression preview (split view)
- Output: 1280x720 JPEG
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QTreeView, QFileSystemModel, QLabel, QPushButton, QSlider,
    QSpinBox, QGroupBox, QFileDialog, QMessageBox, QSplitter,
    QStatusBar, QCheckBox
)
from PySide6.QtCore import Qt, QDir, Signal, QRectF, QPointF, QBuffer, QIODevice
from PySide6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QImage, QTransform,
    QShortcut, QKeySequence, QBrush, QFont
)


class ImageCropWidget(QWidget):
    """Custom widget for image display with 16:9 crop selection and rotation."""

    cropChanged = Signal()
    compressionChanged = Signal(int)  # Estimated file size in bytes

    ASPECT_RATIO = 16 / 9
    OUTPUT_WIDTH = 1280
    OUTPUT_HEIGHT = 720

    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_image: QImage | None = None
        self.rotated_image: QImage | None = None
        self.rotation_angle = 0

        # Crop rectangle (in image coordinates)
        self.crop_rect: QRectF | None = None

        # Compression settings
        self.compression_quality = 85  # JPEG quality (1-100)
        self.show_compression_preview = False
        self.compressed_image: QImage | None = None
        self.original_preview_image: QImage | None = None  # High quality preview
        self.compressed_size = 0

        # Interaction state
        self.dragging = False
        self.resizing = False
        self.resize_corner = None
        self.drag_start = QPointF()
        self.crop_start = QRectF()

        # Display transform cache
        self.display_rect = QRectF()
        self.scale_factor = 1.0

        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def load_image(self, path: str) -> bool:
        """Load image from file path."""
        image = QImage(path)
        if image.isNull():
            return False
        self.original_image = image
        self.rotation_angle = 0
        self._apply_rotation()
        self._init_crop_rect()
        self._update_compressed_preview()
        self.update()
        return True

    def load_from_clipboard(self) -> bool:
        """Load image from clipboard."""
        clipboard = QApplication.clipboard()
        image = clipboard.image()
        if image.isNull():
            # Try to get from mimedata
            mimedata = clipboard.mimeData()
            if mimedata.hasUrls():
                for url in mimedata.urls():
                    if url.isLocalFile():
                        return self.load_image(url.toLocalFile())
            return False
        self.original_image = image
        self.rotation_angle = 0
        self._apply_rotation()
        self._init_crop_rect()
        self._update_compressed_preview()
        self.update()
        return True

    def set_rotation(self, angle: int):
        """Set rotation angle in degrees."""
        self.rotation_angle = angle % 360
        self._apply_rotation()
        self._init_crop_rect()
        self._update_compressed_preview()
        self.update()

    def set_compression_quality(self, quality: int):
        """Set JPEG compression quality (1-100)."""
        self.compression_quality = max(1, min(100, quality))
        if self.rotated_image is not None:
            self._update_compressed_preview()
            self.update()
        else:
            print("[DEBUG] No image loaded, skipping preview update")

    def set_compression_preview(self, enabled: bool):
        """Enable/disable compression preview."""
        print(f"[DEBUG] set_compression_preview called: {enabled}", flush=True)
        self.show_compression_preview = enabled
        self._update_compressed_preview()
        self.update()

    def _apply_rotation(self):
        """Apply rotation to original image."""
        if self.original_image is None:
            self.rotated_image = None
            return

        if self.rotation_angle == 0:
            self.rotated_image = self.original_image.copy()
        else:
            transform = QTransform()
            transform.rotate(self.rotation_angle)
            self.rotated_image = self.original_image.transformed(
                transform, Qt.SmoothTransformation
            )

    def _init_crop_rect(self):
        """Initialize crop rectangle to fit 16:9 in image."""
        if self.rotated_image is None:
            self.crop_rect = None
            return

        img_w = self.rotated_image.width()
        img_h = self.rotated_image.height()

        # Calculate largest 16:9 rectangle that fits
        if img_w / img_h > self.ASPECT_RATIO:
            # Image is wider than 16:9
            crop_h = img_h
            crop_w = crop_h * self.ASPECT_RATIO
        else:
            # Image is taller than 16:9
            crop_w = img_w
            crop_h = crop_w / self.ASPECT_RATIO

        # Center the crop rectangle
        x = (img_w - crop_w) / 2
        y = (img_h - crop_h) / 2

        self.crop_rect = QRectF(x, y, crop_w, crop_h)
        self.cropChanged.emit()

    def _update_compressed_preview(self):
        """Update compressed preview image."""
        if self.rotated_image is None or self.crop_rect is None:
            self.compressed_image = None
            self.original_preview_image = None
            self.compressed_size = 0
            return

        # Get cropped and scaled image
        cropped = self.rotated_image.copy(self.crop_rect.toRect())
        scaled = cropped.scaled(
            self.OUTPUT_WIDTH, self.OUTPUT_HEIGHT,
            Qt.IgnoreAspectRatio, Qt.SmoothTransformation
        )

        # Create original high-quality preview (PNG for lossless)
        orig_buffer = QBuffer()
        orig_buffer.open(QIODevice.WriteOnly)
        scaled.save(orig_buffer, "PNG")
        orig_buffer.close()
        orig_buffer.open(QIODevice.ReadOnly)
        self.original_preview_image = QImage()
        self.original_preview_image.loadFromData(orig_buffer.data())
        orig_buffer.close()

        # Compress to buffer to get size and preview (always JPEG)
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        scaled.save(buffer, "JPEG", self.compression_quality)

        self.compressed_size = buffer.size()
        print(f"[DEBUG] Compressed: JPEG quality={self.compression_quality}, size={self.compressed_size} bytes")

        # Load compressed image back for preview
        buffer.close()
        buffer.open(QIODevice.ReadOnly)
        self.compressed_image = QImage()
        self.compressed_image.loadFromData(buffer.data())
        buffer.close()

        self.compressionChanged.emit(self.compressed_size)

    def _calculate_display_transform(self):
        """Calculate transform from image coords to widget coords."""
        if self.rotated_image is None:
            return

        img_w = self.rotated_image.width()
        img_h = self.rotated_image.height()

        widget_w = self.width() - 20  # margin
        widget_h = self.height() - 20

        # Scale to fit
        scale_x = widget_w / img_w
        scale_y = widget_h / img_h
        self.scale_factor = min(scale_x, scale_y)

        # Calculate display rectangle (centered)
        disp_w = img_w * self.scale_factor
        disp_h = img_h * self.scale_factor
        disp_x = (self.width() - disp_w) / 2
        disp_y = (self.height() - disp_h) / 2

        self.display_rect = QRectF(disp_x, disp_y, disp_w, disp_h)

    def _image_to_widget(self, point: QPointF) -> QPointF:
        """Convert image coordinates to widget coordinates."""
        return QPointF(
            self.display_rect.x() + point.x() * self.scale_factor,
            self.display_rect.y() + point.y() * self.scale_factor
        )

    def _widget_to_image(self, point: QPointF) -> QPointF:
        """Convert widget coordinates to image coordinates."""
        return QPointF(
            (point.x() - self.display_rect.x()) / self.scale_factor,
            (point.y() - self.display_rect.y()) / self.scale_factor
        )

    def _get_crop_widget_rect(self) -> QRectF:
        """Get crop rectangle in widget coordinates."""
        if self.crop_rect is None:
            return QRectF()

        tl = self._image_to_widget(self.crop_rect.topLeft())
        br = self._image_to_widget(self.crop_rect.bottomRight())
        return QRectF(tl, br)

    def _get_resize_handle(self, pos: QPointF) -> str | None:
        """Check if position is on a resize handle."""
        if self.crop_rect is None:
            return None

        crop_widget = self._get_crop_widget_rect()
        handle_size = 12

        corners = {
            'tl': crop_widget.topLeft(),
            'tr': crop_widget.topRight(),
            'bl': crop_widget.bottomLeft(),
            'br': crop_widget.bottomRight(),
        }

        for name, corner in corners.items():
            rect = QRectF(
                corner.x() - handle_size / 2,
                corner.y() - handle_size / 2,
                handle_size, handle_size
            )
            if rect.contains(pos):
                return name

        return None

    def paintEvent(self, event):
        """Draw the image and crop overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor(40, 40, 40))

        if self.rotated_image is None:
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(
                self.rect(), Qt.AlignCenter,
                "Drop image here or paste from clipboard (Ctrl+V)"
            )
            return

        # Dot-by-dot preview mode: show 1280x720 at 1:1 pixel ratio
        if self.show_compression_preview and self.original_preview_image is not None and self.compressed_image is not None:
            self._draw_dot_by_dot_preview(painter)
            return

        self._calculate_display_transform()

        # Draw image
        pixmap = QPixmap.fromImage(self.rotated_image)
        painter.drawPixmap(self.display_rect.toRect(), pixmap)

        # Draw crop overlay (darken outside area)
        if self.crop_rect is not None:
            crop_widget = self._get_crop_widget_rect()

            # Semi-transparent overlay outside crop area
            overlay = QColor(0, 0, 0, 150)

            # Top
            painter.fillRect(QRectF(
                self.display_rect.left(), self.display_rect.top(),
                self.display_rect.width(), crop_widget.top() - self.display_rect.top()
            ), overlay)
            # Bottom
            painter.fillRect(QRectF(
                self.display_rect.left(), crop_widget.bottom(),
                self.display_rect.width(), self.display_rect.bottom() - crop_widget.bottom()
            ), overlay)
            # Left
            painter.fillRect(QRectF(
                self.display_rect.left(), crop_widget.top(),
                crop_widget.left() - self.display_rect.left(), crop_widget.height()
            ), overlay)
            # Right
            painter.fillRect(QRectF(
                crop_widget.right(), crop_widget.top(),
                self.display_rect.right() - crop_widget.right(), crop_widget.height()
            ), overlay)

            # Draw crop border
            painter.setPen(QPen(QColor(255, 200, 0), 2))
            painter.drawRect(crop_widget)

            # Draw corner handles
            handle_size = 10
            painter.setBrush(QBrush(QColor(255, 200, 0)))
            for corner in [crop_widget.topLeft(), crop_widget.topRight(),
                          crop_widget.bottomLeft(), crop_widget.bottomRight()]:
                painter.drawRect(QRectF(
                    corner.x() - handle_size / 2,
                    corner.y() - handle_size / 2,
                    handle_size, handle_size
                ))

            # Draw thirds grid
            painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
            third_w = crop_widget.width() / 3
            third_h = crop_widget.height() / 3
            for i in range(1, 3):
                painter.drawLine(
                    QPointF(crop_widget.left() + third_w * i, crop_widget.top()),
                    QPointF(crop_widget.left() + third_w * i, crop_widget.bottom())
                )
                painter.drawLine(
                    QPointF(crop_widget.left(), crop_widget.top() + third_h * i),
                    QPointF(crop_widget.right(), crop_widget.top() + third_h * i)
                )

    def _draw_dot_by_dot_preview(self, painter: QPainter):
        """Draw 1280x720 preview at 1:1 pixel ratio with split view."""
        # Calculate centered position for 1280x720 display
        preview_x = (self.width() - self.OUTPUT_WIDTH) / 2
        preview_y = (self.height() - self.OUTPUT_HEIGHT) / 2

        # Ensure preview fits in widget (scale down if necessary)
        scale = 1.0
        if self.width() < self.OUTPUT_WIDTH + 20 or self.height() < self.OUTPUT_HEIGHT + 20:
            scale_x = (self.width() - 20) / self.OUTPUT_WIDTH
            scale_y = (self.height() - 20) / self.OUTPUT_HEIGHT
            scale = min(scale_x, scale_y)
            display_w = int(self.OUTPUT_WIDTH * scale)
            display_h = int(self.OUTPUT_HEIGHT * scale)
            preview_x = (self.width() - display_w) / 2
            preview_y = (self.height() - display_h) / 2
        else:
            display_w = self.OUTPUT_WIDTH
            display_h = self.OUTPUT_HEIGHT

        half_width = display_w / 2

        # Draw left half: original high-quality image
        left_dest = QRectF(preview_x, preview_y, half_width, display_h)
        left_src = QRectF(0, 0, self.OUTPUT_WIDTH / 2, self.OUTPUT_HEIGHT)
        original_pixmap = QPixmap.fromImage(self.original_preview_image)
        painter.drawPixmap(left_dest.toRect(), original_pixmap, left_src.toRect())

        # Draw right half: compressed image
        right_dest = QRectF(preview_x + half_width, preview_y, half_width, display_h)
        right_src = QRectF(self.OUTPUT_WIDTH / 2, 0, self.OUTPUT_WIDTH / 2, self.OUTPUT_HEIGHT)
        compressed_pixmap = QPixmap.fromImage(self.compressed_image)
        painter.drawPixmap(right_dest.toRect(), compressed_pixmap, right_src.toRect())

        # Draw border around preview
        painter.setPen(QPen(QColor(255, 200, 0), 2))
        painter.drawRect(QRectF(preview_x, preview_y, display_w, display_h))

        # Draw center divider line
        mid_x = preview_x + half_width
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawLine(
            QPointF(mid_x, preview_y),
            QPointF(mid_x, preview_y + display_h)
        )

        # Draw labels with background for readability
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        painter.setFont(font)

        label_bg = QColor(0, 0, 0, 180)
        label_height = 28
        label_margin = 8

        # Original label (left side)
        left_label_rect = QRectF(preview_x + label_margin, preview_y + label_margin,
                                  half_width - label_margin * 2, label_height)
        painter.fillRect(left_label_rect, label_bg)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(left_label_rect, Qt.AlignCenter, "Original (PNG)")

        # Compressed label (right side) with file size
        size_str = self._format_size(self.compressed_size)
        right_label_rect = QRectF(mid_x + label_margin, preview_y + label_margin,
                                   half_width - label_margin * 2, label_height)
        painter.fillRect(right_label_rect, label_bg)
        painter.setPen(QColor(255, 255, 255))
        format_label = f"JPEG Q{self.compression_quality} ({size_str})"
        painter.drawText(right_label_rect, Qt.AlignCenter, format_label)

        # Draw resolution info at bottom
        info_rect = QRectF(preview_x, preview_y + display_h + 5, display_w, 20)
        painter.setPen(QColor(180, 180, 180))
        scale_info = f"1280x720 @ {int(scale * 100)}%" if scale < 1.0 else "1280x720 (1:1)"
        painter.drawText(info_rect, Qt.AlignCenter, scale_info)

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"

    def mousePressEvent(self, event):
        """Handle mouse press for crop manipulation."""
        if event.button() != Qt.LeftButton or self.crop_rect is None:
            return

        pos = QPointF(event.position())
        handle = self._get_resize_handle(pos)
        crop_widget = self._get_crop_widget_rect()

        if handle:
            self.resizing = True
            self.resize_corner = handle
            self.drag_start = pos
            self.crop_start = QRectF(self.crop_rect)
        elif crop_widget.contains(pos):
            self.dragging = True
            self.drag_start = pos
            self.crop_start = QRectF(self.crop_rect)

    def mouseMoveEvent(self, event):
        """Handle mouse move for crop manipulation."""
        pos = QPointF(event.position())

        # Update cursor
        if self.crop_rect is not None:
            handle = self._get_resize_handle(pos)
            crop_widget = self._get_crop_widget_rect()

            if handle in ('tl', 'br'):
                self.setCursor(Qt.SizeFDiagCursor)
            elif handle in ('tr', 'bl'):
                self.setCursor(Qt.SizeBDiagCursor)
            elif crop_widget.contains(pos):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

        if self.rotated_image is None or self.crop_rect is None:
            return

        img_w = self.rotated_image.width()
        img_h = self.rotated_image.height()

        if self.dragging:
            # Move crop rectangle
            delta = self._widget_to_image(pos) - self._widget_to_image(self.drag_start)
            new_rect = self.crop_start.translated(delta)

            # Clamp to image bounds
            if new_rect.left() < 0:
                new_rect.moveLeft(0)
            if new_rect.top() < 0:
                new_rect.moveTop(0)
            if new_rect.right() > img_w:
                new_rect.moveRight(img_w)
            if new_rect.bottom() > img_h:
                new_rect.moveBottom(img_h)

            self.crop_rect = new_rect
            self.cropChanged.emit()
            self.update()

        elif self.resizing:
            # Resize crop rectangle while maintaining aspect ratio
            img_pos = self._widget_to_image(pos)

            # Calculate new size based on which corner is being dragged
            if self.resize_corner == 'br':
                new_w = max(100, img_pos.x() - self.crop_rect.left())
                new_h = new_w / self.ASPECT_RATIO
                self.crop_rect.setWidth(new_w)
                self.crop_rect.setHeight(new_h)
            elif self.resize_corner == 'tl':
                anchor = self.crop_rect.bottomRight()
                new_w = max(100, anchor.x() - img_pos.x())
                new_h = new_w / self.ASPECT_RATIO
                self.crop_rect = QRectF(
                    anchor.x() - new_w, anchor.y() - new_h,
                    new_w, new_h
                )
            elif self.resize_corner == 'tr':
                anchor_x = self.crop_rect.left()
                anchor_y = self.crop_rect.bottom()
                new_w = max(100, img_pos.x() - anchor_x)
                new_h = new_w / self.ASPECT_RATIO
                self.crop_rect = QRectF(
                    anchor_x, anchor_y - new_h,
                    new_w, new_h
                )
            elif self.resize_corner == 'bl':
                anchor_x = self.crop_rect.right()
                anchor_y = self.crop_rect.top()
                new_w = max(100, anchor_x - img_pos.x())
                new_h = new_w / self.ASPECT_RATIO
                self.crop_rect = QRectF(
                    anchor_x - new_w, anchor_y,
                    new_w, new_h
                )

            # Clamp to image bounds
            if self.crop_rect.left() < 0:
                self.crop_rect.moveLeft(0)
            if self.crop_rect.top() < 0:
                self.crop_rect.moveTop(0)
            if self.crop_rect.right() > img_w:
                scale = (img_w - self.crop_rect.left()) / self.crop_rect.width()
                self.crop_rect.setWidth(self.crop_rect.width() * scale)
                self.crop_rect.setHeight(self.crop_rect.height() * scale)
            if self.crop_rect.bottom() > img_h:
                scale = (img_h - self.crop_rect.top()) / self.crop_rect.height()
                self.crop_rect.setWidth(self.crop_rect.width() * scale)
                self.crop_rect.setHeight(self.crop_rect.height() * scale)

            self.cropChanged.emit()
            self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if self.dragging or self.resizing:
            self._update_compressed_preview()
        self.dragging = False
        self.resizing = False
        self.resize_corner = None

    def export_cropped_image(self, output_path: str) -> tuple[bool, int]:
        """Export cropped image as JPEG. Returns (success, file_size)."""
        if self.rotated_image is None or self.crop_rect is None:
            return False, 0

        # Crop the image
        cropped = self.rotated_image.copy(self.crop_rect.toRect())

        # Scale to output size
        scaled = cropped.scaled(
            self.OUTPUT_WIDTH, self.OUTPUT_HEIGHT,
            Qt.IgnoreAspectRatio, Qt.SmoothTransformation
        )

        # Always save as JPEG
        success = scaled.save(output_path, "JPEG", self.compression_quality)

        if success:
            file_size = Path(output_path).stat().st_size
            return True, file_size
        return False, 0


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, start_dir: str | None = None):
        super().__init__()
        self.setWindowTitle("YouTube Cover Image Cropper")
        self.setMinimumSize(1100, 750)
        self.current_image_dir: str | None = start_dir  # Track current image directory

        self._setup_ui()
        self._setup_shortcuts()

        # Start in specified directory or home
        if start_dir and Path(start_dir).exists():
            self.file_model.setRootPath(start_dir)
            self.file_tree.setRootIndex(self.file_model.index(start_dir))
        else:
            self.file_model.setRootPath(QDir.homePath())
            self.file_tree.setRootIndex(self.file_model.index(QDir.homePath()))

    def _setup_ui(self):
        """Setup the user interface."""
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left panel: File tree
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_label = QLabel("Files")
        left_label.setStyleSheet("font-weight: bold; padding: 5px;")
        left_layout.addWidget(left_label)

        self.file_model = QFileSystemModel()
        self.file_model.setNameFilters(["*.png", "*.jpg", "*.jpeg", "*.bmp", "*.gif", "*.webp"])
        self.file_model.setNameFilterDisables(False)

        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setColumnWidth(0, 200)
        self.file_tree.hideColumn(1)  # Size
        self.file_tree.hideColumn(2)  # Type
        self.file_tree.doubleClicked.connect(self._on_file_double_clicked)
        left_layout.addWidget(self.file_tree)

        splitter.addWidget(left_panel)

        # Right panel: Image editor and controls
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Image crop widget
        self.crop_widget = ImageCropWidget()
        self.crop_widget.cropChanged.connect(self._update_status)
        self.crop_widget.compressionChanged.connect(self._on_compression_changed)
        right_layout.addWidget(self.crop_widget, 1)

        # Rotation Controls
        rotation_group = QGroupBox("Rotation")
        rotation_layout = QHBoxLayout(rotation_group)

        rotation_label = QLabel("Angle:")
        rotation_layout.addWidget(rotation_label)

        self.rotation_slider = QSlider(Qt.Horizontal)
        self.rotation_slider.setRange(0, 359)
        self.rotation_slider.setValue(0)
        self.rotation_slider.setTracking(True)
        self.rotation_slider.valueChanged.connect(self._on_rotation_changed)
        rotation_layout.addWidget(self.rotation_slider)
        print(f"[DEBUG] Rotation slider initialized, range: 0-359")

        self.rotation_spin = QSpinBox()
        self.rotation_spin.setRange(0, 359)
        self.rotation_spin.setSuffix(" deg")
        self.rotation_spin.valueChanged.connect(self._on_rotation_spin_changed)
        rotation_layout.addWidget(self.rotation_spin)

        btn_90cw = QPushButton("90 CW")
        btn_90cw.clicked.connect(lambda: self._rotate_by(90))
        rotation_layout.addWidget(btn_90cw)

        btn_90ccw = QPushButton("90 CCW")
        btn_90ccw.clicked.connect(lambda: self._rotate_by(-90))
        rotation_layout.addWidget(btn_90ccw)

        right_layout.addWidget(rotation_group)

        # Compression Controls (JPEG)
        compression_group = QGroupBox("JPEG Quality")
        compression_layout = QHBoxLayout(compression_group)

        quality_label = QLabel("Quality:")
        compression_layout.addWidget(quality_label)

        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(85)
        self.quality_slider.setFixedWidth(150)
        self.quality_slider.setTracking(True)
        self.quality_slider.valueChanged.connect(self._on_quality_changed)
        compression_layout.addWidget(self.quality_slider)
        print(f"[DEBUG] Quality slider initialized, range: 1-100")

        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(85)
        self.quality_spin.setSuffix("%")
        self.quality_spin.valueChanged.connect(self._on_quality_spin_changed)
        compression_layout.addWidget(self.quality_spin)

        # Preview toggle
        self.preview_check = QCheckBox("Preview (split)")
        self.preview_check.stateChanged.connect(self._on_preview_toggled)
        compression_layout.addWidget(self.preview_check)

        # File size label
        compression_layout.addStretch()
        self.size_label = QLabel("Size: --")
        self.size_label.setStyleSheet("color: #88ff88;")
        compression_layout.addWidget(self.size_label)

        right_layout.addWidget(compression_group)

        # Action buttons
        actions_layout = QHBoxLayout()

        btn_paste = QPushButton("Paste (Ctrl+V)")
        btn_paste.clicked.connect(self._paste_from_clipboard)
        actions_layout.addWidget(btn_paste)

        actions_layout.addStretch()

        btn_export = QPushButton("Export cover.jpg")
        btn_export.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 16px;")
        btn_export.clicked.connect(self._export_image)
        actions_layout.addWidget(btn_export)

        right_layout.addLayout(actions_layout)

        splitter.addWidget(right_panel)
        splitter.setSizes([250, 850])

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Load an image to begin")

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        paste_shortcut = QShortcut(QKeySequence.Paste, self)
        paste_shortcut.activated.connect(self._paste_from_clipboard)

    def _on_file_double_clicked(self, index):
        """Handle file tree double-click."""
        path = self.file_model.filePath(index)
        if Path(path).is_file():
            if self.crop_widget.load_image(path):
                self.current_image_dir = str(Path(path).parent)
                self.status_bar.showMessage(f"Loaded: {path}")
                self.rotation_slider.setValue(0)
                self.rotation_spin.setValue(0)
            else:
                QMessageBox.warning(self, "Error", f"Failed to load image: {path}")

    def _on_rotation_changed(self, value):
        """Handle rotation slider change."""
        print(f"[DEBUG] Rotation slider changed: {value}")
        self.rotation_spin.blockSignals(True)
        self.rotation_spin.setValue(value)
        self.rotation_spin.blockSignals(False)
        self.crop_widget.set_rotation(value)

    def _on_rotation_spin_changed(self, value):
        """Handle rotation spinbox change."""
        self.rotation_slider.blockSignals(True)
        self.rotation_slider.setValue(value)
        self.rotation_slider.blockSignals(False)
        self.crop_widget.set_rotation(value)

    def _rotate_by(self, degrees):
        """Rotate by specified degrees."""
        new_angle = (self.rotation_slider.value() + degrees) % 360
        self.rotation_slider.setValue(new_angle)

    def _on_quality_changed(self, value):
        """Handle quality slider change."""
        print(f"[DEBUG] Quality slider changed: {value}")
        self.quality_spin.blockSignals(True)
        self.quality_spin.setValue(value)
        self.quality_spin.blockSignals(False)
        self.crop_widget.set_compression_quality(value)

    def _on_quality_spin_changed(self, value):
        """Handle quality spinbox change."""
        self.quality_slider.blockSignals(True)
        self.quality_slider.setValue(value)
        self.quality_slider.blockSignals(False)
        self.crop_widget.set_compression_quality(value)

    def _on_preview_toggled(self, state):
        """Handle preview checkbox toggle."""
        # Use isChecked() instead of comparing state value for reliability
        enabled = self.preview_check.isChecked()
        print(f"[DEBUG] Preview toggled: {enabled} (state={state})", flush=True)
        self.crop_widget.set_compression_preview(enabled)

    def _on_compression_changed(self, size_bytes):
        """Handle compression size update."""
        self.size_label.setText(f"Size: {self._format_size(size_bytes)}")

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"

    def _paste_from_clipboard(self):
        """Paste image from clipboard."""
        if self.crop_widget.load_from_clipboard():
            self.status_bar.showMessage("Loaded image from clipboard")
            self.rotation_slider.setValue(0)
            self.rotation_spin.setValue(0)
        else:
            QMessageBox.information(self, "Clipboard", "No image found in clipboard")

    def _export_image(self):
        """Export cropped image as JPEG."""
        if self.crop_widget.rotated_image is None:
            QMessageBox.warning(self, "Error", "No image loaded")
            return

        # Use current image directory or cwd
        save_dir = Path(self.current_image_dir) if self.current_image_dir else Path.cwd()
        default_path = str(save_dir / "cover.jpg")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Cover Image", default_path, "JPEG Files (*.jpg *.jpeg);;All Files (*)"
        )

        if path:
            success, file_size = self.crop_widget.export_cropped_image(path)
            if success:
                size_str = self._format_size(file_size)
                self.status_bar.showMessage(f"Exported: {path} ({size_str})")
                QMessageBox.information(
                    self, "Success",
                    f"Image exported successfully!\n\n"
                    f"Size: 1280x720\n"
                    f"File size: {size_str}\n"
                    f"Path: {path}"
                )
            else:
                QMessageBox.warning(self, "Error", "Failed to export image")

    def _update_status(self):
        """Update status bar with crop info."""
        if self.crop_widget.crop_rect is not None:
            r = self.crop_widget.crop_rect
            self.status_bar.showMessage(
                f"Crop: {int(r.width())}x{int(r.height())} at ({int(r.x())}, {int(r.y())}) -> 1280x720"
            )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="YouTube Cover Image Cropper")
    parser.add_argument("directory", nargs="?", default=None,
                        help="Starting directory for file browser")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Dark theme
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(palette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(palette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(palette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(palette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    palette.setColor(palette.ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(palette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(palette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(palette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(palette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(palette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(palette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(palette.ColorRole.HighlightedText, QColor(35, 35, 35))
    app.setPalette(palette)

    window = MainWindow(start_dir=args.directory)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
