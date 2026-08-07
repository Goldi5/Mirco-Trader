Set oShell = CreateObject("WScript.Shell")
Set oExec = oShell.Exec("C:\Users\goldi\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe -B C:\Users\goldi\projects\micro-trader\dashboard.py 5200")
WScript.Sleep 1000
