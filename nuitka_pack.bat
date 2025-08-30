python -m nuitka --onefile --windows-console-mode=disable --enable-plugin=tk-inter --lto=no --noinclude-dlls="*tencent*" --show-scons client.py ^
       --include-data-files=spritesheet.png=spritesheet.png

rem --windows-disable-console