Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d C:\ihsg-bot && python main.py > bot.log 2>&1", 0, False
