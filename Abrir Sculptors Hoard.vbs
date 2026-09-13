Option Explicit
Dim shell, files, root, executable, entry, quote
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
executable = files.BuildPath(root, "node_modules\electron\dist\electron.exe")
entry = files.BuildPath(root, "desktop\main.cjs")
quote = Chr(34)
If Not files.FileExists(executable) Then
    MsgBox "Falta instalar el modo escritorio. Ejecuta npm ci y node node_modules/electron/install.js en la carpeta del programa.", vbExclamation, "Sculptor's Hoard"
    WScript.Quit 1
End If
If Not files.FileExists(files.BuildPath(root, "dist\index.html")) Then
    MsgBox "Falta compilar la interfaz. Ejecuta npm run build en la carpeta del programa.", vbExclamation, "Sculptor's Hoard"
    WScript.Quit 1
End If
shell.CurrentDirectory = root
shell.Environment("Process").Remove "ELECTRON_RUN_AS_NODE"
shell.Run quote & executable & quote & " " & quote & entry & quote, 1, False
