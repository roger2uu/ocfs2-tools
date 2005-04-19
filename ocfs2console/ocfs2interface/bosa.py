# OCFS2Console - GUI frontend for OCFS2 management and debugging
# Copyright (C) 2002, 2005 Oracle.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 021110-1307, USA.

import gtk
import gobject
import pango

import ocfs2

import gidle

from guiutil import set_props

from ls import fields

INFO_LABEL_FONT = pango.FontDescription('monospace')

(
    COLUMN_NAME,
    COLUMN_INFO_OBJECT,
    COLUMN_ICON,
    COLUMN_ITALIC
) = range(4)

sample = ('-rw-r--r--', '1', 'manish', 'manish', '133194', '262144', 'Sep 29 12:46', 'closobo.c')

STOCK_LOADING = gtk.STOCK_REFRESH
STOCK_EMPTY = gtk.STOCK_STOP
STOCK_ERROR = gtk.STOCK_DIALOG_ERROR

try:
    STOCK_FILE = gtk.STOCK_FILE
except AttributeError:
    STOCK_FILE = gtk.STOCK_NEW

try:
    STOCK_DIRECTORY = gtk.STOCK_DIRECTORY
except AttributeError:
    STOCK_DIRECTORY = gtk.STOCK_OPEN

class InfoLabel(gtk.Label):
    def __init__(self, field_type):
        gtk.Label.__init__(self)

        self.field_type = field_type

        if field_type.right_justify:
             set_props(self, xalign=1.0)
        else:
             set_props(self, xalign=0.0)

        self.modify_font(INFO_LABEL_FONT)

    def update(self, dentry, dinode):
        field = self.field_type(dentry, dinode)
        self.set_text(field.text)

class Browser(gtk.VBox):
    def __init__(self, device=None):
        self.device = device

        gtk.VBox.__init__(self, spacing=4)

        label = gtk.Label('/')
        set_props(label, xalign=0.0)
        self.pack_start(label, expand=False)

        self.path_label = label

        self.scrl_win = gtk.ScrolledWindow()
        self.scrl_win.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.add(self.scrl_win)

        self.store = gtk.TreeStore(str, gobject.TYPE_PYOBJECT,
                                   str, gobject.TYPE_BOOLEAN)

        self.make_file_view()

        self.make_ls_fields()

        self.connect('destroy', self.destroy_handler)

        self.refresh()

    def make_file_view(self):
        tv = gtk.TreeView(self.store)
        self.scrl_win.add(tv)

        set_props(tv, headers_visible=False,
                      rules_hint=True)

        column = gtk.TreeViewColumn()

        renderer = gtk.CellRendererPixbuf()
        column.pack_start(renderer, expand=False)
        column.set_attributes(renderer, stock_id=COLUMN_ICON)

        renderer = gtk.CellRendererText()
        renderer.set_property('style', pango.STYLE_ITALIC)
        column.pack_start(renderer, expand=True)
        column.set_attributes(renderer, text=COLUMN_NAME,
                                        style_set=COLUMN_ITALIC)

        tv.append_column(column)

        tv.connect('test_expand_row', self.tree_expand_row)
        tv.connect('test_collapse_row', self.tree_collapse_row)
        #tv.connect('row_activated', self.tree_row_activated)

        #sel = tv.get_selection()
        #sel.connect('changed', self.select)

    def make_ls_fields(self):
        table = gtk.Table(rows=2, columns=7)
        set_props(table, row_spacing=4,
                         column_spacing=4,
                         border_width=4)
        self.pack_end(table, expand=False, fill=False)

        self.info_labels = []

        column = 0

        for field in fields:
            label = gtk.Label(field.label)
            set_props(label, xalign=0.0)
            table.attach(label, column, column + 1, 0, 1)

            label = InfoLabel(field)
            table.attach(label, column, column + 1, 1, 2)

            self.info_labels.append(label)

            column += 1

    def destroy_handler(self, obj):
        self.cleanup()

    def make_dentry_node(self, dentry, stock_id, parent=None):
        return self.store.append(parent, (dentry.name, dentry, stock_id, False))

    def make_file_node(self, dentry, parent=None):
        self.make_dentry_node(dentry, STOCK_FILE, parent)

    def make_dir_node(self, dentry, parent=None):
        iter = self.make_dentry_node(dentry, STOCK_DIRECTORY, parent)
        self.store.append(iter, ('.', dentry, None, False))

    def make_loading_node(self, parent=None):
        self.store.append(parent, ('Loading...', None, STOCK_LOADING, True))

    def make_empty_node(self, parent=None):
        self.store.append(parent, ('Empty', None, STOCK_EMPTY, True))

    def make_error_node(self, parent=None):
        self.store.append(parent, ('Error', None, STOCK_ERROR, True))

    def cleanup(self):
        if hasattr(self, 'levels'):
            for level in self.levels:
                level.destroy()

        self.levels = []

    def refresh(self):
        self.cleanup()

        self.store.clear()

        self.fs = None

        if self.device:
            try:
                self.fs = ocfs2.Filesystem(self.device)
            except ocfs2.error:
                self.make_error_node()

            if self.fs:
                self.add_level()
        else:
            self.make_empty_node()

        
    def add_level(self, dentry=None, parent=None):
        if parent:
            iter = self.store.iter_children(parent)

            name = self.store[iter][COLUMN_NAME]
            if name != '.':
                return

            del self.store[iter]

        try:
            diriter = self.fs.iterdir(dentry)
        except ocfs2.error:
            self.make_error_node(parent)
            return

        self.make_loading_node(parent)

        level = TreeLevel(diriter, dentry, parent)
        self.levels.append(level)

        if parent: 
            self.store[parent][COLUMN_INFO_OBJECT] = level
      
        level.set_callback(self.populate_level, level)
        level.attach()

    def populate_level(self, level):
        try:
            dentry = level.diriter.next()
        except (StopIteration, ocfs2.error), e:
             print e
             self.destroy_level(level, isinstance(e, ocfs2.error))
             return False

        print dentry

        if dentry.file_type == ocfs2.FT_DIR:
            self.make_dir_node(dentry, level.parent)
        else:
            self.make_file_node(dentry, level.parent)

        return True

    def destroy_level(self, level, error=False):
        if error:
            self.make_error_node(level.parent)
        else:
            children = self.store.iter_n_children(level.parent)

            if children < 2:
                self.make_empty_node(level.parent)

        if level.parent:
            self.store[level.parent][COLUMN_INFO_OBJECT] = level.dentry

        iter = self.store.iter_children(level.parent)
        self.store.remove(iter)

        self.levels.remove(level)

        del level.diriter

    def tree_expand_row(self, tv, iter, path):
        info_obj = self.store[iter][COLUMN_INFO_OBJECT]

        if isinstance(info_obj, TreeLevel):
            level.collapsed = False
            level.foreground(level)
        else:
            self.add_level(info_obj, iter)

    def tree_collapse_row(self, tv, iter, path):
        info_obj = self.store[iter][COLUMN_INFO_OBJECT]

        if isinstance(info_obj, TreeLevel):
            level = info_obj

            level.collapsed = True
            level.background()
        
class TreeLevel(gidle.Idle):
    def __init__(self, diriter, dentry=None, parent=None):
        gidle.Idle.__init__(self)

        self.diriter = diriter
        self.dentry = dentry

        if parent:
            self.parent = parent.copy()
        else:
            self.parent = None

        self.collapsed = False

    def foreground(self):
        if not self.collapsed:
            self.set_priority(gobject.PRIORITY_DEFAULT_IDLE)

    def background(self):
        level.set_priority(gobject.PRIORITY_LOW)

def main():
    import sys

    def dummy(*args):
        gtk.main_quit()

    window = gtk.Window()
    window.set_default_size(400, 300)
    window.connect('delete_event', dummy)

    browser = Browser(sys.argv[1])
    window.add(browser)

    window.show_all()

    gtk.main()

if __name__ == '__main__':
    main()
