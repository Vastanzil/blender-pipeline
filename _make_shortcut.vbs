
Set oWS = WScript.CreateObject("WScript.Shell")
Set oSC = oWS.CreateShortcut("C:\Users\Administrator\Desktop\BlenderCopilot.lnk")
oSC.TargetPath       = "C:\Python314\pythonw.exe"
oSC.Arguments        = """D:\PROJECTS\BLENDER PIPELINE\launch.pyw"""
oSC.WorkingDirectory = "D:\PROJECTS\BLENDER PIPELINE"
oSC.Description      = "BlenderCopilot"
oSC.IconLocation     = "C:\Python314\pythonw.exe, 0"
oSC.WindowStyle      = 1
oSC.Save
