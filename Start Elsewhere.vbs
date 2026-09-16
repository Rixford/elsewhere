Option Explicit
Dim fs, shell, root, data, stream, command
Set fs = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fs.GetParentFolderName(WScript.ScriptFullName)
If Not fs.FileExists(root & "\runtime-path.txt") Then
  MsgBox "Run Setup Elsewhere.cmd first. Setup needs internet once; normal use is offline.", 64, "Elsewhere"
  WScript.Quit
End If
Set stream = fs.OpenTextFile(root & "\runtime-path.txt", 1)
data = Trim(stream.ReadAll)
stream.Close
command = Chr(34) & data & "\python\Scripts\pythonw.exe" & Chr(34) & " " & Chr(34) & root & "\app.py" & Chr(34)
shell.CurrentDirectory = root
shell.Run command, 0, False
