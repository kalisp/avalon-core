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


        # class AssetDelegate(QtWidgets.QItemDelegate):
class AssetDelegate(QtWidgets.QStyledItemDelegate):
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

        view_options = widget.viewOptions()

        text_option = QtGui.QTextOption()
        text_option.setWrapMode(wrap_text)
        text_option.setTextDirection(option.direction)
        text_option.setAlignment(_style.visualAlignment(
            option.direction,
            option.displayAlignment
        ))

        text_layout = QtGui.Qtext_layout()
        text_layout.setTextOption(text_option)
        text_layout.setFont(option.font)
        text_layout.setText(option.text)

        self.viewItemtextLayout(text_layout, text_rect.width())

        elided_text = ""
        height = float(0)
        width = float(0)
        elidedIndex = -1

        line_count = text_layout.lineCount()
        for j_idx in range(line_count):
            line = text_layout.lineAt(j_idx)
            if j_idx + 1 <= line_count - 1:
                nextLine = text_layout.lineAt(j_idx + 1)
                if ((nextLine.y() + nextLine.height()) > text_rect.height()):
                    start = line.textStart()
                    length = line.textLength() + nextLine.textLength()
                    const QStackTextEngine engine(
                        text_layout.text().mid(start, length), option.font
                    )
                    elidedText = engine.elidedText(
                        option.textElideMode, text_rect.width()
                    )
                    height += line.height()
                    width = text_rect.width()
                    elidedIndex = j_idx
                    break

            if (line.naturalTextWidth() > text_rect.width()):
                start = line.textStart()
                length = line.textLength()
                engine = QtGui.QFontMetrics(option.font)
                const QStackTextEngine engine(
                    text_layout.text().mid(start, length), option.font
                )
                elidedText = engine.elidedText(
                    option.textElideMode, text_rect.width()
                )
                height += line.height()
                width = text_rect.width()
                elidedIndex = j_idx
                break

            width = max(width, line.width())
            height += line.height()

        # const int textMargin = proxyStyle->pixelMetric(QStyle::PM_FocusFrameHMargin, 0, widget) + 1;
        #
        # QRect textRect = rect.adjusted(textMargin, 0, -textMargin, 0); // remove width padding
        # const bool wrapText = option->features & QStyleOptionViewItemV2::WrapText;
        # QTextOption textOption;
        # textOption.setWrapMode(wrapText ? QTextOption::WordWrap : QTextOption::ManualWrap);
        # textOption.setTextDirection(option->direction);
        # textOption.setAlignment(QStyle::visualAlignment(option->direction, option->displayAlignment));
        # Qtext_layout text_layout;
        # text_layout.setTextOption(textOption);
        # text_layout.setFont(option->font);
        # text_layout.setText(option->text);
        #
        # viewItemtextLayout(text_layout, textRect.width());
        #
        # QString elidedText;
        # qreal height = 0;
        # qreal width = 0;
        # int elidedIndex = -1;
        # const int lineCount = text_layout.lineCount();
        # for (int j = 0; j < lineCount; ++j) {
        #     const QTextLine line = text_layout.lineAt(j);
        #     if (j + 1 <= lineCount - 1) {
        #         const QTextLine nextLine = text_layout.lineAt(j + 1);
        #         if ((nextLine.y() + nextLine.height()) > textRect.height()) {
        #             int start = line.textStart();
        #             int length = line.textLength() + nextLine.textLength();
        #             const QStackTextEngine engine(text_layout.text().mid(start, length), option->font);
        #             elidedText = engine.elidedText(option->textElideMode, textRect.width());
        #             height += line.height();
        #             width = textRect.width();
        #             elidedIndex = j;
        #             break;
        #         }
        #     }
        #     if (line.naturalTextWidth() > textRect.width()) {
        #         int start = line.textStart();
        #         int length = line.textLength();
        #         const QStackTextEngine engine(text_layout.text().mid(start, length), option->font);
        #         elidedText = engine.elidedText(option->textElideMode, textRect.width());
        #         height += line.height();
        #         width = textRect.width();
        #         elidedIndex = j;
        #         break;
        #     }
        #     width = qMax<qreal>(width, line.width());
        #     height += line.height();
        # }
        #
        # const QRect layoutRect = QStyle::alignedRect(option->direction, option->displayAlignment,
        #                                             QSize(int(width), int(height)), textRect);
        # const QPointF position = layoutRect.topLeft();
        # for (int i = 0; i < lineCount; ++i) {
        #     const QTextLine line = text_layout.lineAt(i);
        #     if (i == elidedIndex) {
        #         qreal x = position.x() + line.x();
        #         qreal y = position.y() + line.y() + line.ascent();
        #         p->save();
        #         p->setFont(option->font);
        #         p->drawText(QPointF(x, y), elidedText);
        #         p->restore();
        #         break;
        #     }
        #     line.draw(p, position);
        # }

    def viewItemtextLayout(
        text_layout, line_width, max_height=-1, last_visible_line=None
    ):
        if last_visible_line:
            last_visible_line = -1
        # These were real (qreal)
        height = float(0)
        widthUsed = float(0)
        text_layout.beginLayout()
        i = 0
        while True:
            line = text_layout.createLine()
            if not line.isValid():
                break
            line.setline_width(line_width)
            line.setPosition(QtCore.QPointF(0, height))
            height += line.height()
            widthUsed = max(widthUsed, line.naturalTextWidth())
            if (
                max_height > 0 and
                last_visible_line and
                height + line.height() > max_height
            ):
                nextLine = text_layout.createLine()
                if nextLine.isValid():
                    last_visible_line = i
                else:
                    last_visible_line = -1
                break

            i += 1

        text_layout.endLayout()
        return QtCore.QSizeF(widthUsed, height)

    def paint(self, painter, option, index):
        widget = option.widget
        _style = widget.style()
        # CE_ItemViewItem
        # PE_PanelItemViewItem
        _style.drawPrimitive(
            _style.PE_PanelItemViewItem, option, painter, widget
        )

        origin_height = option.rect.height()
        item_height = origin_height - self.bar_height
        option.rect.setHeight(item_height)

        check_rect = _style.subElementRect(
            _style.SE_ItemViewItemCheckIndicator, option, widget
        )
        icon_rect = _style.subElementRect(
            _style.SE_ItemViewItemDecoration, option, widget
        )
        text_rect = _style.subElementRect(
            _style.SE_ItemViewItemText, option, widget
        )
        subset_colors_rect = QtCore.QRect(
            text_rect.left(), origin_height - self.bar_height,
            text_rect.width(), self.bar_height
        )

        if option.features & option.HasCheckIndicator:
            pass
        # if (vopt->features & QStyleOptionViewItemV2::HasCheckIndicator) {
        #     QStyleOptionViewItemV4 option(*vopt);
        #     option.rect = checkRect;
        #     option.state = option.state & ~QStyle::State_HasFocus;
        #
        #     switch (vopt->checkState) {
        #     case Qt::Unchecked:
        #         option.state |= QStyle::State_Off;
        #         break;
        #     case Qt::PartiallyChecked:
        #         option.state |= QStyle::State_NoChange;
        #         break;
        #     case Qt::Checked:
        #         option.state |= QStyle::State_On;
        #         break;
        #     }
        #     proxy()->drawPrimitive(QStyle::PE_IndicatorViewItemCheck, &option, p, widget);
        # }

        icon_index = index.model().index(
            index.row(), index.column(), index.parent()
        )
        icon = index.model().data(icon_index, QtCore.Qt.DecorationRole)

        if icon:
            icon_mode = QtGui.QIcon.Normal

            if not (option.state & QtWidgets.QStyle.State_Enabled):
                icon_mode = QtGui.QIcon.Disabled
            elif option.state & QtWidgets.QStyle.State_Selected:
                icon_mode = QtGui.QIcon.Selected

            if option.state & QtWidgets.QStyle.State_Open:
                icon_state = QtGui.QIcon.On
            else:
                icon_state = QtGui.QIcon.Off

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
                actualSize = option.icon.actualSize(
                    option.decorationSize, icon_mode, icon_state
                )
                option.decorationSize = QtCore.QSize(
                    min(option.decorationSize.width(), actualSize.width()),
                    min(option.decorationSize.height(), actualSize.height())
                )

            view_options = widget.viewOptions()
            icon.paint(
                painter,
                icon_rect,
                view_options.decorationAlignment,
                icon_mode,
                icon_state
            )
        # // draw the icon
        # QIcon::Mode mode = QIcon::Normal;
        # if (!(vopt->state & QStyle::State_Enabled))
        #     mode = QIcon::Disabled;
        # else if (vopt->state & QStyle::State_Selected)
        #     mode = QIcon::Selected;
        # QIcon::State state = vopt->state & QStyle::State_Open ? QIcon::On : QIcon::Off;
        # vopt->icon.paint(p, iconRect, vopt->decorationAlignment, mode, state);

        text = index.data(QtCore.Qt.DisplayRole)
        if text:
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
            # painter.drawText(
            #     text_rect, QtCore.Qt.AlignVCenter, text
            # )

        # // draw the text
        # if (!vopt->text.isEmpty()) {
        #     QPalette::ColorGroup cg = vopt->state & QStyle::State_Enabled
        #                         ? QPalette::Normal : QPalette::Disabled;
        #     if (cg == QPalette::Normal && !(vopt->state & QStyle::State_Active))
        #       cg = QPalette::Inactive;
        #
        #     if (vopt->state & QStyle::State_Selected) {
        #       p->setPen(vopt->palette.color(cg, QPalette::HighlightedText));
        #     } else {
        #      p->setPen(vopt->palette.color(cg, QPalette::Text));
        #     }
        #     if (vopt->state & QStyle::State_Editing) {
        #       p->setPen(vopt->palette.color(cg, QPalette::Text));
        #       p->drawRect(textRect.adjusted(0, 0, -1, -1));
        #     }
        #
        #     d->viewItemDrawText(p, vopt, textRect);
        # }
        #
        # // draw the focus rect
        # if (vopt->state & QStyle::State_HasFocus) {
        #     QStyleOptionFocusRect o;
        #     o.QStyleOption::operator=(*vopt);
        #     o.rect = proxy()->subElementRect(SE_ItemViewItemFocusRect, vopt, widget);
        #     o.state |= QStyle::State_KeyboardFocusChange;
        #     o.state |= QStyle::State_Item;
        #     QPalette::ColorGroup cg = (vopt->state & QStyle::State_Enabled)
        #                 ? QPalette::Normal : QPalette::Disabled;
        #     o.backgroundColor = vopt->palette.color(cg, (vopt->state & QStyle::State_Selected)
        #                                ? QPalette::Highlight : QPalette::Window);
        #     proxy()->drawPrimitive(QStyle::PE_FrameFocusRect, &o, p, widget);
        # }
        #
        # p->restore();

        return

        painter.save()

        item_rect = QtCore.QRect(option.rect)
        item_rect.setHeight(option.rect.height() - self.bar_height)

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
                    option.rect.top() + (option.rect.height()-self.bar_height),
                    subset_colors_width,
                    self.bar_height
                )
            subset_rects.append((new_color, new_rect))
            counter += 1

        # Background
        bg_color = QtGui.QColor(60, 60, 60)
        if option.state & QtWidgets.QStyle.State_Selected:
            if len(subset_colors) == 0:
                item_rect.setTop(item_rect.top() + (self.bar_height / 2))
            if option.state & QtWidgets.QStyle.State_MouseOver:
                bg_color.setRgb(70, 70, 70)
        else:
            item_rect.setTop(item_rect.top() + (self.bar_height / 2))
            if option.state & QtWidgets.QStyle.State_MouseOver:
                bg_color.setAlpha(100)
            else:
                bg_color.setAlpha(0)

        # # -- When not needed to do a rounded corners (easier and without painter restore):
        # painter.fillRect(
        #     item_rect,
        #     QtGui.QBrush(bg_color)
        # )
        pen = painter.pen()
        pen.setStyle(QtCore.Qt.NoPen)
        pen.setWidth(0)
        painter.setPen(pen)
        painter.setBrush(QtGui.QBrush(bg_color))
        painter.drawRoundedRect(option.rect, 3, 3)

        if option.state & QtWidgets.QStyle.State_Selected:
            for color, subset_rect in subset_rects:
                if not color or not subset_rect:
                    continue
                painter.fillRect(subset_rect, QtGui.QBrush(color))

        painter.restore()
        painter.save()

        # Icon
        icon_index = index.model().index(
            index.row(), index.column(), index.parent()
        )
        # - Default icon_rect if not icon
        icon_rect = QtCore.QRect(
            item_rect.left(),
            item_rect.top(),
            # To make sure it's same size all the time
            option.rect.height() - self.bar_height,
            option.rect.height() - self.bar_height
        )
        icon = index.model().data(icon_index, QtCore.Qt.DecorationRole)

        if icon:
            margin = 0
            mode = QtGui.QIcon.Normal

            if not (option.state & QtWidgets.QStyle.State_Enabled):
                mode = QtGui.QIcon.Disabled
            elif option.state & QtWidgets.QStyle.State_Selected:
                mode = QtGui.QIcon.Selected

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
                state = QtGui.QIcon.Off
                if option.state & QtWidgets.QStyle.State_Open:
                    state = QtGui.QIcon.On
                actualSize = option.icon.actualSize(
                    option.decorationSize, mode, state
                )
                option.decorationSize = QtCore.QSize(
                    min(option.decorationSize.width(), actualSize.width()),
                    min(option.decorationSize.height(), actualSize.height())
                )

            state = QtGui.QIcon.Off
            if option.state & QtWidgets.QStyle.State_Open:
                state = QtGui.QIcon.On

            icon.paint(
                painter, icon_rect,
                QtCore.Qt.AlignLeft , mode, state
            )

        # Text
        text_rect = QtCore.QRect(
            icon_rect.left() + icon_rect.width() + 2,
            item_rect.top(),
            item_rect.width(),
            item_rect.height()
        )

        painter.drawText(
            text_rect, QtCore.Qt.AlignVCenter,
            index.data(QtCore.Qt.DisplayRole)
        )

        painter.restore()
