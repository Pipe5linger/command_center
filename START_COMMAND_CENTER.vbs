Set WshShell = CreateObject("WScript.Shell")
Set objWMI   = GetObject("winmgmts:\\.\root\cimv2")
Set colProcs = objWMI.ExecQuery("SELECT ProcessId, CommandLine FROM Win32_Process WHERE Name='python.exe'")

Dim alreadyRunning : alreadyRunning = False
For Each proc In colProcs
    If Not IsNull(proc.CommandLine) Then
        If InStr(LCase(proc.CommandLine), "sanctuary_command_center.py") > 0 Then
            alreadyRunning = True
            Exit For
        End If
    End If
Next

If alreadyRunning Then
    WScript.Quit
End If

WshShell.CurrentDirectory = "D:\AI\Projects\command_center"
WshShell.Run "C:\Users\boben\AppData\Local\Programs\Python\Python311\python.exe D:\AI\Projects\command_center\sanctuary_command_center.py", 0, False
