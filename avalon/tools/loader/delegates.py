import time
from datetime import datetime
import logging

from ...vendor.Qt import QtWidgets, QtGui, QtCore
from ..models import AssetModel

log = logging.getLogger(__name__)


def pretty_date(t, now=None, strftime="%b %d %Y %H:%M"):
    """Parse datetime to readable timestamp

    Within first ten seconds:
        - "just now",
    Within first minute ago:
        - "%S seconds ago"
    Within one hour ago:
        - "%M minutes ago".
    Within one day ago:
        - "%H:%M hours ago"
    Else:
        "%Y-%m-%d %H:%M:%S"

    """

    assert isinstance(t, datetime)
    if now is None:
        now = datetime.now()
    assert isinstance(now, datetime)
    diff = now - t

    second_diff = diff.seconds
    day_diff = diff.days

    # future (consider as just now)
    if day_diff < 0:
        return "just now"

    # history
    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + " seconds ago"
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return str(second_diff // 60) + " minutes ago"
        if second_diff < 86400:
            minutes = (second_diff % 3600) // 60
            hours = second_diff // 3600
            return "{0}:{1:02d} hours ago".format(hours, minutes)

    return t.strftime(strftime)


def pretty_timestamp(t, now=None):
    """Parse timestamp to user readable format

    >>> pretty_timestamp("20170614T151122Z", now="20170614T151123Z")
    'just now'

    >>> pretty_timestamp("20170614T151122Z", now="20170614T171222Z")
    '2:01 hours ago'

    Args:
        t (str): The time string to parse.
        now (str, optional)

    Returns:
        str: human readable "recent" date.

    """

    if now is not None:
        try:
            now = time.strptime(now, "%Y%m%dT%H%M%SZ")
            now = datetime.fromtimestamp(time.mktime(now))
        except ValueError as e:
            log.warning("Can't parse 'now' time format: {0} {1}".format(t, e))
            return None

    try:
        t = time.strptime(t, "%Y%m%dT%H%M%SZ")
    except ValueError as e:
        log.warning("Can't parse time format: {0} {1}".format(t, e))
        return None
    dt = datetime.fromtimestamp(time.mktime(t))

    # prettify
    return pretty_date(dt, now=now)


class PrettyTimeDelegate(QtWidgets.QStyledItemDelegate):
    """A delegate that displays a timestamp as a pretty date.

    This displays dates like `pretty_date`.

    """

    def displayText(self, value, locale):
        return pretty_timestamp(value)


class AssetDelegate(QtWidgets.QItemDelegate):
    bar_height = 3

    def sizeHint(self, option, index):
        result = super(AssetDelegate, self).sizeHint(option, index)
        height = result.height()
        result.setHeight(height + self.bar_height)

        return result

    def viewItemDrawText(self, painter, option, rect):
        widget = option.widget
        _style = widget.style()

        text_margin = _style.pixelMetric(
            _style.PM_FocusFrameHMargin, option, widget
        ) + 1

        text_rect = rect.adjusted(text_margin, 0, -text_margin, 0)

        if option.features & option.WrapText:
            wrap_text = QtGui.QTextOption.WordWrap
        else:
            wrap_text = QtGui.QTextOption.ManualWrap

        text_option = QtGui.QTextOption()
        text_option.setWrapMode(wrap_text)
        text_option.setTextDirection(option.direction)
        text_option.setAlignment(_style.visualAlignment(
            option.direction,
            option.displayAlignment
        ))

        text_layout = QtGui.QTextLayout()
        text_layout.setTextOption(text_option)
        text_layout.setFont(option.font)
        text_layout.setText(option.text)

        self.viewItemtextLayout(text_layout, text_rect.width())

        elided_text = ""
        height = float(0)
        width = float(0)
        elided_index = -1

        font_metrics = QtGui.QFontMetrics(option.font)

        line_count = text_layout.lineCount()
        for j_idx in range(line_count):
            line = text_layout.lineAt(j_idx)
            if j_idx + 1 <= line_count - 1:
                nextLine = text_layout.lineAt(j_idx + 1)
                if ((nextLine.y() + nextLine.height()) > text_rect.height()):
                    start = line.textStart()
                    length = line.textLength() + nextLine.textLength()
                    elided_text = font_metrics.elidedText(
                        text_layout.text().mid(start, length),
                        option.textElideMode,
                        text_rect.width()
                    )
                    height += line.height()
                    width = text_rect.width()
                    elided_index = j_idx
                    break

            if (line.naturalTextWidth() > text_rect.width()):
                start = line.textStart()
                length = line.textLength()
                elided_text = font_metrics.elidedText(
                    text_layout.text().mid(start, length),
                    option.textElideMode,
                    text_rect.width()
                )
                height += line.height()
                width = text_rect.width()
                elided_index = j_idx
                break

            width = max(width, line.width())
            height += line.height()

        layout_rect = _style.alignedRect(
            option.direction, option.displayAlignment,
            QtCore.QSize(int(width), int(height)), text_rect
        )
        position = layout_rect.topLeft()

        for idx in range(line_count):
            text_layout.lineAt(idx)
            if idx == elided_index:
                pos_x = position.x() + line.x()
                pos_y = position.y() + line.y() + line.ascent()
                painter.save()
                painter.setFont(option.font)
                painter.drawText(
                    QtCore.QPointF(pos_x, pos_y),
                    elided_text
                )
                painter.restore()
                break

            line.draw(painter, position)

    def viewItemtextLayout(
        self, text_layout, line_width, max_height=-1, last_visible_line=None
    ):
        if last_visible_line:
            last_visible_line = -1
        # These were real (qreal)
        height = float(0)
        width_used = float(0)
        text_layout.beginLayout()
        idx = 0
        while True:
            line = text_layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(line_width)
            line.setPosition(QtCore.QPointF(0, height))
            height += line.height()
            width_used = max(width_used, line.naturalTextWidth())
            if (
                max_height > 0 and
                last_visible_line and
                height + line.height() > max_height
            ):
                nextLine = text_layout.createLine()
                if nextLine.isValid():
                    last_visible_line = idx
                else:
                    last_visible_line = -1
                break

            idx += 1

        text_layout.endLayout()

        return QtCore.QSizeF(width_used, height)

    def paint(self, painter, option, index):
        painter.save()
        painter.setClipRect(option.rect)

        widget = option.widget
        _style = widget.style()

        # Draw background
        _style.drawPrimitive(
            _style.PE_PanelItemViewItem, option, painter, widget
        )

        # Set icon to option before setting rectangles
        icon_index = index.model().index(
            index.row(), index.column(), index.parent()
        )
        icon = index.model().data(icon_index, QtCore.Qt.DecorationRole)

        icon_mode = QtGui.QIcon.Normal
        if not (option.state & QtWidgets.QStyle.State_Enabled):
            icon_mode = QtGui.QIcon.Disabled
        elif option.state & QtWidgets.QStyle.State_Selected:
            icon_mode = QtGui.QIcon.Selected

        if option.state & QtWidgets.QStyle.State_Open:
            icon_state = QtGui.QIcon.On
        else:
            icon_state = QtGui.QIcon.Off

        if icon:
            if isinstance(icon, QtGui.QPixmap):
                icon = QtGui.QIcon(icon)
                option.decorationSize = icon.size() / icon.devicePixelRatio()

            elif isinstance(icon, QtGui.QColor):
                pixmap = QtGui.QPixmap(option.decorationSize)
                pixmap.fill(icon)
                icon = QtGui.QIcon(pixmap)

            elif isinstance(icon, QtGui.QImage):
                icon = QtGui.QIcon(QtGui.QPixmap.fromImage(icon))
                option.decorationSize = icon.size() / icon.devicePixelRatio()

            elif isinstance(icon, QtGui.QIcon):
                actualSize = icon.actualSize(
                    option.decorationSize, icon_mode, icon_state
                )
                option.decorationSize = QtCore.QSize(
                    min(option.decorationSize.width(), actualSize.width()),
                    min(option.decorationSize.height(), actualSize.height())
                )
            option.icon = icon
            option.features |= option.HasDecoration

        # Store original height
        origin_height = option.rect.height()
        item_height = origin_height - self.bar_height

        # Get rectangles
        check_rect = _style.subElementRect(
            _style.SE_ItemViewItemCheckIndicator, option, widget
        )
        icon_rect = _style.subElementRect(
            _style.SE_ItemViewItemDecoration, option, widget
        )
        text_rect = _style.subElementRect(
            _style.SE_ItemViewItemText, option, widget
        )

        subset_colors = index.data(AssetModel.subsetColorsRole)
        subset_colors_width = 0
        if subset_colors:
            subset_colors_width = option.rect.width() / len(subset_colors)

        subset_rects = []
        counter = 0
        for subset_c in subset_colors:
            new_color = None
            new_rect = None
            if subset_c:
                new_color = QtGui.QColor(*subset_c)

                new_rect = QtCore.QRect(
                    option.rect.left() + (counter * subset_colors_width),
                    option.rect.top() + (
                        option.rect.height() - self.bar_height
                    ),
                    subset_colors_width,
                    self.bar_height
                )
            subset_rects.append((new_color, new_rect))
            counter += 1

        if subset_rects and option.state & QtWidgets.QStyle.State_Selected:
            text_rect.setHeight(item_height)
            for color, subset_rect in subset_rects:
                if not color or not subset_rect:
                    continue
                painter.fillRect(subset_rect, QtGui.QBrush(color))

        if option.features & option.HasCheckIndicator:
            option.rect = check_rect
            option.state = option.state & _style.Stete_HasFocus

            if option.checkState is QtCore.Qt.Unchecked:
                option.state |= _style.State_Off
            elif option.checkState is QtCore.Qt.PartiallyChecked:
                option.state |= _style.State_NoChange
            elif option.checkState is QtCore.Qt.Checked:
                option.state |= _style.State_On

            _style.drawPrimitive(
                _style.PE_IndicatorViewItemCheck,
                option,
                painter,
                widget
            )

        view_options = widget.viewOptions()
        option.icon.paint(
            painter,
            icon_rect,
            view_options.decorationAlignment,
            icon_mode,
            icon_state
        )

        text = index.data(QtCore.Qt.DisplayRole)
        if text:
            option.text = text
            if not option.state & QtWidgets.QStyle.State_Enabled:
                color_group = QtGui.QPalette.Disabled
            elif not option.state & QtWidgets.QStyle.State_Active:
                color_group = QtGui.QPalette.Inactive
            else:
                color_group = QtGui.QPalette.Normal

            if option.state & QtWidgets.QStyle.State_Selected:
                painter.setPen(option.palette.color(
                    color_group, QtGui.QPalette.HighlightedText
                ))
            else:
                painter.setPen(option.palette.color(
                    color_group, QtGui.QPalette.Text
                ))

            if option.state & QtWidgets.QStyle.State_Editing:
                painter.setPen(option.palette.color(
                    color_group, QtGui.QPalette.HighlightedText
                ))
                painter.drawRect(text_rect.adjusted(0, 0, -1, -1))

            self.viewItemDrawText(painter, option, text_rect)

        if option.state & _style.State_HasFocus:
            rect_focus_opt = QtWidgets.QStyleOptionFocusRect()
            rect_focus_opt.state = option.state
            rect_focus_opt.direction = option.direction
            rect_focus_opt.rect = option.rect
            rect_focus_opt.fontMetrics = option.fontMetrics
            rect_focus_opt.palette = option.palette

            rect_focus_opt.state |= _style.State_KeyboardFocusChange
            rect_focus_opt.state |= _style.State_Item

            if (option.state & _style.State_Enabled):
                color_group = QtGui.QPalette.Normal
            else:
                color_group = QtGui.QPalette.Disabled

            if option.state & _style.State_Selected:
                _pallete = QtGui.QPalette.Highlight
            else:
                _pallete = QtGui.QPalette.Window
            rect_focus_opt.backgroundColor = option.palette.color(
                color_group, _pallete
            )

            _style.drawPrimitive(
                _style.PE_FrameFocusRect,
                rect_focus_opt,
                painter,
                widget
            )

        painter.restore()
