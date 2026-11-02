Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

If CreateObject("Scripting.FileSystemObject").FileExists("venv\Scripts\pythonw.exe") Then
    WshShell.Run "venv\Scripts\pythonw.exe app.py", 0, False
ElseIf CreateObject("Scripting.FileSystemObject").FileExists("venv\Scripts\python.exe") Then
    WshShell.Run "venv\Scripts\python.exe app.py", 0, False
Else
    WshShell.Run "pythonw.exe app.py", 0, False
End If
