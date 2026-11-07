' Script VBScript para lanzar VMO en segundo plano sin ventana visible
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strCurDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strCurDir

' Ejecutar python directamente con ruta absoluta sin pasar por cmd.exe
strPython = strCurDir & "\.venv\Scripts\python.exe"
strScript = strCurDir & "\run_server.py"

If fso.FileExists(strPython) Then
    WshShell.Run """" & strPython & """ """ & strScript & """", 0, False
Else
    ' Si no hay .venv local, intentar con python del sistema
    WshShell.Run "python """ & strScript & """", 0, False
End If