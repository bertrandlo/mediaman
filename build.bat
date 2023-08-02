cd C:\Users\bertr\Documents\PycharmProjects\mediaman
CALL venv\Scripts\activate
copy .\dist\mediaman\files.db .\dist\files.db
pyinstaller mediaman.py  --icon=icon.ico
copy .\dist\files.db .\dist\mediaman\files.db