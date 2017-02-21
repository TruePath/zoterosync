from tkinter import *
from tkinter.ttk import *


class ScrollSelect(object):

    def __init__(self, master, list, onselect=None):
        self.master = master
        self.list = list
        self.scroll = Scrollbar(self.master, orient=VERTICAL)
        self.listbox = Listbox(self.master, listvariable=self.list, yscrollcommand=self.scroll.set, height=6)
        self.scroll.config(command=self.listbox.yview)
        self.scroll.pack(side=RIGHT, fill=Y)
        self.listbox.pack(side=LEFT,  fill=BOTH, expand=1)

        def interior_onselect(evt):
            w = evt.widget
            index = int(w.curselection()[0])
            if (onselect is not None):
                onselect(index)
        self.listbox.bind('<<ListboxSelect>>', interior_onselect)


class MergeDisplay(object):

    def __init__(self, master, merge_tuple, result):
        self.master = master
        self.merge_tuple = merge_tuple
        self.result = result
        self.outer_frame = Frame(self.master, padding=(5, 5, 12, 0), relief='groove')
        self.outer_frame.grid(column=0, row=0, sticky=(N, W, E, S))
        self.master.grid_columnconfigure(0, weight=1)
        self.master.grid_rowconfigure(0, weight=1)
        self.merge_frame = Frame(self.outer_frame)
        self.merge_frame.grid(column=0, row=0, rowspan=10, sticky=(N, W, E, S))
        self.from_frame = Frame(self.outer_frame)
        self.from_frame.grid(column=1, row=0, rowspan=10, sticky=(N, W, E, S))
        self.select_frame = Frame(self.outer_frame, padding=(5, 5, 0, 0))
        self.select_frame.grid(column=2, row=0, rowspan=7, sticky=(N, W, E, S))
        self.button_frame = Frame(self.outer_frame, padding=(5, 5, 0, 0))
        self.button_frame.grid(column=2, row=7, rowspan=3, sticky=(N, W, E, S))
        self.outer_frame.grid_columnconfigure(0, weight=3)
        self.outer_frame.grid_columnconfigure(1, weight=3)
        self.outer_frame.grid_columnconfigure(2, weight=1)
        for i in range(10):
            self.outer_frame.grid_rowconfigure(i, weight=1)
        selection_list = StringVar(value=tuple((str(i) for i in self.merge_tuple)))
        self.select = ScrollSelect(self.select_frame, selection_list)




class TestDisplay(object):

    def __init__(self, str, dict):
        self.str = str
        self.dict = dict

    def __iter__(self):
        return iter(self.dict)

    def __getitem__(self, i):
        return dict[i]



root = Tk()
merge = ("first", "second", "third", "fourth")
mergedisplay = MergeDisplay(root, merge, dict())
root.mainloop()
