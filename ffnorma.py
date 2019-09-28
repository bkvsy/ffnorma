import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as mb
from tkinter import filedialog as fd
import re
import os
import csv
from zipfile import ZipFile, ZIP_STORED, ZipInfo
import shutil
import tempfile


class UpdateableZipFile(ZipFile):
    """
    Add delete (via remove_file) and update (via writestr and write methods)
    To enable update features use UpdateableZipFile with the 'with statement',
    Upon  __exit__ (if updates were applied) a new zip file will override the exiting one with the updates
    """

    class DeleteMarker(object):
        pass

    def __init__(self, file, mode="r", compression=ZIP_STORED, allowZip64=False):
        # Init base
        super(UpdateableZipFile, self).__init__(file, mode=mode,
                                                compression=compression,
                                                allowZip64=allowZip64)
        # track file to override in zip
        self._replace = {}
        # Whether the with statement was called
        self._allow_updates = False

    def writestr(self, zinfo_or_arcname, bytes, compress_type=None):
        if isinstance(zinfo_or_arcname, ZipInfo):
            name = zinfo_or_arcname.filename
        else:
            name = zinfo_or_arcname
        # If the file exits, and needs to be overridden,
        # mark the entry, and create a temp-file for it
        # we allow this only if the with statement is used
        if self._allow_updates and name in self.namelist():
            temp_file = self._replace[name] = self._replace.get(name,
                                                                tempfile.TemporaryFile())
            temp_file.write(bytes)
        # Otherwise just act normally
        else:
            super(UpdateableZipFile, self).writestr(zinfo_or_arcname,
                                                    bytes, compress_type=compress_type)

    def write(self, filename, arcname=None, compress_type=None):
        arcname = arcname or filename
        # If the file exits, and needs to be overridden,
        # mark the entry, and create a temp-file for it
        # we allow this only if the with statement is used
        if self._allow_updates and arcname in self.namelist():
            temp_file = self._replace[arcname] = self._replace.get(arcname,
                                                                   tempfile.TemporaryFile())
            with open(filename, "rb") as source:
                shutil.copyfileobj(source, temp_file)
        # Otherwise just act normally
        else:
            super(UpdateableZipFile, self).write(filename, 
                                                 arcname=arcname, compress_type=compress_type)

    def __enter__(self):
        # Allow updates
        self._allow_updates = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # call base to close zip file, organically
        try:
            super(UpdateableZipFile, self).__exit__(exc_type, exc_val, exc_tb)
            if len(self._replace) > 0:
                self._rebuild_zip()
        finally:
            # In case rebuild zip failed,
            # be sure to still release all the temp files
            self._close_all_temp_files()
            self._allow_updates = False

    def _close_all_temp_files(self):
        for temp_file in self._replace.values():
            if hasattr(temp_file, 'close'):
                temp_file.close()

    def remove_file(self, path):
        self._replace[path] = self.DeleteMarker()

    def _rebuild_zip(self):
        tempdir = tempfile.mkdtemp()
        try:
            temp_zip_path = os.path.join(tempdir, 'new.zip')
            with ZipFile(self.filename, 'r') as zip_read:
                # Create new zip with assigned properties
                with ZipFile(temp_zip_path, 'w', compression=self.compression,
                             allowZip64=self._allowZip64) as zip_write:
                    for item in zip_read.infolist():
                        # Check if the file should be replaced / or deleted
                        replacement = self._replace.get(item.filename, None)
                        # If marked for deletion, do not copy file to new zipfile
                        if isinstance(replacement, self.DeleteMarker):
                            del self._replace[item.filename]
                            continue
                        # If marked for replacement, copy temp_file, instead of old file
                        elif replacement is not None:
                            del self._replace[item.filename]
                            # Write replacement to archive,
                            # and then close it (deleting the temp file)
                            replacement.seek(0)
                            data = replacement.read()
                            replacement.close()
                        else:
                            data = zip_read.read(item.filename)
                        zip_write.writestr(item, data)
            # Override the archive with the updated one
            shutil.move(temp_zip_path, self.filename)
        finally:
            shutil.rmtree(tempdir)
            
            
class App(tk.Tk):
    
    def __init__(self, data):
        super().__init__()
        self.minsize(360, 200)
        self.maxsize(360, 200)

        self.db_main = data
        
        self.title("ffnorma")
        self.heading = tk.Label(text="ffnorma", padx=15, pady=15, font=("Arial Black", 24))
        self.desc = tk.Label(text="Wyszukuje i aktualizuje numery norm w dokumentach docx", padx=15, pady=25, font=("Arial", 9))
        self.findbtn = tk.Button(text="Znajdź plik", 
                                 padx=5, pady=5, width = 10,
                                 command=self.browse)
        self.updtbtn = tk.Button(text="Analizuj...", 
                                 padx=5, pady=5, width = 10, 
                                 state=tk.DISABLED,
                                 command=self.open_window)
        
        self.filepath = tk.StringVar()
        self.initaldir = r"C:"
        self.filetypes = (("Word Documents","*.docx"), ("All files", "*.*"))

        self.heading.grid(row=0, sticky = tk.NW, columnspan=2)
        self.desc.grid(row=1, columnspan=2)
        self.findbtn.grid(row=2, column=0, sticky=tk.E, padx=5)
        self.updtbtn.grid(row=2, column=1, sticky=tk.W, padx=5)
        self.grid_columnconfigure(0, minsize=240)
        
    def browse(self):
        self.filepath.set(fd.askopenfilename(initialdir=self.initaldir,
                                             filetypes=self.filetypes))
        if self.filepath.get().endswith('.docx'):
#             mb.showinfo("Info", f"Załatdowano plik {self.filepath.get()}")
            self.updtbtn.config(state=tk.NORMAL)

    def open_window(self):

        raport_window = Raport(self, self.filepath, self.db_main)
        raport_window.grab_set()

        
class Raport(tk.Toplevel):
    
    def __init__(self, parent, path, data):
        super().__init__(parent)
        self.label = tk.Label(self, text="Raport", padx=15, pady=15, font=("Arial", 12))

        self.result_headers = ["Wykryta nazwa", "Status bazy", "Status aktualności", "Aktualna nazwa"]
        self.filepath = path

        self.db_main = data
        self.xml_str = ""
        self.result_list = self.file_analysis()        
        
        self.tree = ttk.Treeview(self, columns=self.result_headers, show="headings")

        for col in self.result_headers:
            self.tree.heading(col, text=col.title(), 
                              command=lambda _col=col: self.treeview_sort_column(self.tree, _col, False))
        for item in self.result_list:
            self.tree.insert('', 'end', values=item)
            
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)      
        self.acceptbtn = tk.Button(self, text="Podmień na aktualne", command=self.final_docx, padx=5, pady=5, width = 20)
        self.cancelbtn = tk.Button(self, text="Anuluj", command=self.destroy, padx=5, pady=5, width = 10)

        self.label.grid(row=0, columnspan=3)
        self.tree.grid(row=1, columnspan=2, padx=10)
        self.sb.grid(row=1, column=2, sticky=tk.NSEW)
        self.tree.configure(yscrollcommand=self.sb.set)
        self.grid_columnconfigure(0, minsize=700)
        
        self.acceptbtn.grid(row=2, column=0, padx=10, pady=20, sticky=tk.SE)
        self.cancelbtn.grid(row=2, column=1, padx=10, pady=20, sticky=tk.SE)

        
#     def ffreplace(self):
        
#         final_docx(xmlstr, res, self.filepath.get())       
# #         print(self.new_path.get())
        
    
    def treeview_sort_column(self, tv, col, reverse):
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        l.sort(reverse=reverse)

        # rearrange items in sorted positions
        for index, (val, k) in enumerate(l):
            tv.move(k, '', index)

        # reverse sort next time
        tv.heading(col, command=lambda: self.treeview_sort_column(tv, col, not reverse))

        
    def xml_to_str(self):

        with open(self.filepath.get(), "rb") as f:
            document = ZipFile(f)
            xml_content = document.read('word/document.xml')

        # xml_str = xml.etree.ElementTree.tostring(tree, encoding="unicode", method="html")
        self.xml_str = xml_content.decode("utf-8")

        
       
    def file_analysis(self):

        self.xml_to_str()
        
        # Wyszukiwanie wyników
        regex = r"PN(?: |-).{1,30}?(?:(?::\d{4})(?:-\d\d|))(?:[\S]+?(?:\d{4})|)(?:-\d{2}|)"
        normy = re.findall(regex, self.xml_str)

        # Wyszukiwanie notacji przed 1994
        regex94 = r"PN(?: |-)\d{2}/.(?:[\S]+)(?:\d)"
        normy94 = re.findall(regex94, self.xml_str)

        # Porównanie wyników wyszukiwania z bazą
        results = []
        found = 0

        for n in normy:
            mark = "Brak w bazie"
            state = "Nieznany" # Up-to-date
            newest = None

            for d in self.db_main:
                if n == d[1]:
                    mark = "Znaleziono"
                    state = "Aktualny"
                    found += 1
                    break

                elif n in d[2]:
                    mark = "Znaleziono"
                    state = "Nieaktualny"
                    newest = d[1]
                    found += 1
                    break

            results.append((n, mark, state, newest))

        for n94 in normy94:
            results.append((n94, "Brak w bazie", "Notacja sprzed 1994", None))

        return results


    def final_docx(self):

        self.new_path_s = self.filepath.get()
        self.new_path_s = self.new_path_s[:-5]+"_FFNORMA"+self.new_path_s[-5:]
        self.new_path = tk.StringVar()
        self.new_path.set(self.new_path_s)    

        # Podmiana stringow w xml_str        
        for positive_match in self.result_list:
            if positive_match[3] != None:
                self.xml_str = self.xml_str.replace(positive_match[0], positive_match[3], 1)

        self.new_output = bytes(self.xml_str, 'utf-8')
        with open("document.xml", "wb") as f:
            f.write(self.new_output)
            
        kopia = shutil.copy(self.filepath.get(), self.new_path.get())
        # with open('output_test.txt', 'w', encoding="utf-8") as f:
        #     f.write(xml_str)
        
        with UpdateableZipFile(self.new_path.get(), "a") as o:
            o.write(r"document.xml", "word/document.xml")

        mb.showinfo("Info", f"Utworzono plik {self.new_path.get()}")


if __name__ == "__main__":

    # Wczytanie bazy na samym początku programu
    db_main = []

    with open(r"db\db.csv", "r", encoding="utf-8", newline="") as readdb:
        reader = csv.reader(readdb, delimiter=',')
        for row in reader:
            db_main.append((row[0], row[1], eval(row[2])))

    app = App(db_main)
    app.iconbitmap(r'ico\yellow-icon.ico')
    app.mainloop()