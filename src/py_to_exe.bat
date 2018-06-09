"E:\Program Files\Python\Python36-32\Scripts\pyinstaller" -w -F -i "assets\icon.ico" --specpath="./build" --distpath=. Autoposter.py
if not errorlevel 1 rmdir /S /Q "./build"