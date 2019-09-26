import docx
import re
import bs4
import os
import csv
from zipfile import ZipFile, ZIP_STORED, ZipInfo
import xml.etree.ElementTree
import shutil
import tempfile

# Wczytanie bazy na samym początku programu
db_main = []

with open("db.csv", "r", encoding="utf-8", newline="") as readdb:
    reader = csv.reader(readdb, delimiter=',')
    for row in reader:
        db_main.append((row[0], row[1], eval(row[2])))

def file_analysis(path):

    master_path = path

    with open(master_path, "rb") as f:
        document = ZipFile(f)
        xml_content = document.read('word/document.xml')

    # xml_str = xml.etree.ElementTree.tostring(tree, encoding="unicode", method="html")
    xml_str = xml_content.decode("utf-8")

    # Wyszukiwanie wyników
    regex = r"PN(?: |-).{1,30}?(?:(?::\d{4})(?:-\d\d|))(?:[\S]+?(?:\d{4})|)(?:-\d{2}|)"
    normy = re.findall(regex, xml_str)

    # Wyszukiwanie notacji przed 1994
    regex94 = r"PN(?: |-)\d{2}/.(?:[\S]+)(?:\d)"
    normy94 = re.findall(regex94, xml_str)

    # Porównanie wyników wyszukiwania z bazą
    results = []
    found = 0

    for n in normy:
        mark = "Not found in db"
        state = "Unknown" # Up-to-date
        newest = None

        for d in db_main:
            if n == d[1]:
                mark = "Found in db"
                state = "Up-to-date"
                found += 1
                break

            elif n in d[2]:
                mark = "Found in db"
                state = "Out-of-date"
                newest = d[1]
                found += 1
                break

        results.append((n, mark, state, newest))

    for n94 in normy94:
        results.append((n94, "Not found in db", "Deprecated 1994", None))

    return results

# Podmiana stringow w xml_str

for positive_match in results:
    if positive_match[3] != None:
        xml_str = xml_str.replace(positive_match[0], positive_match[3], 1)

# with open('output_test.txt', 'w', encoding="utf-8") as f:
#     f.write(xml_str)

new_output = bytes(xml_str, 'utf-8')
len(new_output)

with open("test_bytes.xml", "wb") as f:
    f.write(new_output)

kopia = shutil.copy("test_data/opis.docx", "test_data/_ffnorma/opis_update.docx")

# Tworzenie kopii podmienionego docx
# Author: Or Weis https://stackoverflow.com/a/35435548

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

with UpdateableZipFile(r"F:\coding\ffnorma\test_data\_ffnorma\opis_update.docx", "a") as o:
    # Overwrite a file with a string
#     o.writestr(r"word/document.xml", xml_str.encode('utf-8'), compress_type=None)

    o.write(r"document.xml", "word/document.xml")
