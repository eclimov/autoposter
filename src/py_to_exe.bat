"F:\Python\Python37\Scripts\pyinstaller" -w -F -i "C:\Users\klimo\PycharmProjects\autoposter\src\assets\icon.ico" --specpath="./build" --distpath=. Autoposter.py
if not errorlevel 1 rmdir /S /Q "./build"
