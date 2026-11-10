' Script VBScript para lanzar VMO en segundo plano con registro de errores
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strCurDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strCurDir

strPython = strCurDir & "\.venv\Scripts\python.exe"
strScript = strCurDir & "\run_server.py"
strLog = strCurDir & "\server_log.txt"

If fso.FileExists(strPython) Then
    strCmd = "cmd /c """"" & strPython & """ """ & strScript & """ > """ & strLog & """ 2>&1"""
Else
    strCmd = "cmd /c ""python """ & strScript & """ > """ & strLog & """ 2>&1"""
End If

WshShell.Run strCmd, 0, False
