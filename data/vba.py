# data/vba.py
import os
import sys
import win32com.client
import path  # 你的 path.py，里面有 TARGET_PATH

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import BD

def run_vba_macro(vba_code, macro_name):
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    wb = excel.Workbooks.Add()
    vb_module = wb.VBProject.VBComponents.Add(1)
    vb_module.CodeModule.AddFromString(vba_code)
    excel.Application.Run(macro_name)
    wb.Close(SaveChanges=False)
    excel.Quit()

def run_bd_for_missing_xlsx():
    dat_dir = path.TARGET_PATH
    print("检查 dat 文件并生成缺失的 xlsx...")
    res = BD.process_all_dat_files(dat_dir)
    print("dat → xlsx 转换完成。")
    print("created:", len(res.get("created", [])), "skipped:", len(res.get("skipped", [])))
    print("statistics.md:", res.get("statistics_md"))
    return res

if __name__ == "__main__":
    run_bd_for_missing_xlsx()
    vba_code = f"""
Sub BatchSaveAsHTMLRecursive()
    Dim fso As Object
    Dim folder As Object
    Dim dict As Object
    Dim indexPath As String
    Dim f As Integer
    
    Dim rootPath As String
    rootPath = "{path.TARGET_PATH}"
    
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set folder = fso.GetFolder(rootPath)
    Set dict = CreateObject("Scripting.Dictionary")
    
    ProcessFolder folder, rootPath, dict
    
    indexPath = rootPath & "\\index.html"
    f = FreeFile
    Open indexPath For Output As #f
    Print #f, "<html><head><meta charset='utf-8'><title>Excel 2 HTML</title></head><body>"
    Print #f, "<h1>Excel 2 HTML</h1>"
    Print #f, ParseMarkdownTables(rootPath & "\\statistics.md")
    Print #f, "<hr/>"
    
    Dim key As Variant
    For Each key In dict.Keys
        Print #f, "<h2>" & key & "</h2><ul>"
        Dim files As Variant
        files = dict(key)
        Dim i As Integer
        For i = LBound(files) To UBound(files)
            Print #f, "<li><a href='" & files(i) & "' target='_blank'>" & files(i) & "</a></li>"
        Next
        Print #f, "</ul>"
    Next
    
    Print #f, "</body></html>"
    Close #f
    
    MsgBox "批量转换完成！索引文件已生成: " & indexPath
End Sub

Sub ProcessFolder(f As Object, rootPath As String, dict As Object)
    Dim file As Object
    Dim subFolder As Object
    Dim wb As Workbook
    Dim relPath As String
    Dim folderName As String
    Dim files() As String
    Dim count As Integer
    Dim htmlPath As String
    
    folderName = Replace(f.Path, rootPath & "\\", "")
    If folderName = "" Then folderName = "(根目录)"
    
    count = 0
    
    For Each file In f.Files
        If LCase(Right(file.Name, 5)) = ".xlsx" Then
            If Left(file.Name, 2) <> "~$" Then
                htmlPath = Replace(file.Path, ".xlsx", ".html")
                If Dir(htmlPath) = "" Then
                    Set wb = Workbooks.Open(file.Path)
                    wb.SaveAs htmlPath, FileFormat:=44
                    wb.Close SaveChanges:=False
                    Call FixEncoding(htmlPath)
                End If
                relPath = Replace(file.Path, rootPath & "\\", "")
                relPath = Replace(relPath, ".xlsx", ".html")
                relPath = Replace(relPath, "\\", "/")
                ReDim Preserve files(count)
                files(count) = relPath
                count = count + 1
            End If
        End If
    Next
    
    If count > 0 Then
        dict(folderName) = files
    End If
    
    For Each subFolder In f.SubFolders
        ProcessFolder subFolder, rootPath, dict
    Next
End Sub

Sub FixEncoding(htmlPath As String)
    Dim fileContent As String
    Dim fso As Object
    Dim ts As Object
    Dim stream As Object

    Set fso = CreateObject("Scripting.FileSystemObject")
    Set ts = fso.OpenTextFile(htmlPath, 1, False)
    fileContent = ts.ReadAll
    ts.Close

    fileContent = Replace(fileContent, "charset=windows-1252", "charset=utf-8")
    fileContent = Replace(fileContent, "charset=gb2312", "charset=utf-8")

    Set stream = CreateObject("ADODB.Stream")
    With stream
        .Type = 2
        .Charset = "utf-8"
        .Open
        .WriteText fileContent
        .SaveToFile htmlPath, 2
        .Close
    End With
End Sub

Function ParseMarkdownTables(mdPath As String) As String
    Dim fso As Object, ts As Object
    Dim line As String
    Dim html As String
    Dim inTable As Boolean
    
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(mdPath) Then
        ParseMarkdownTables = "<p>(statistics.md 文件不存在)</p>"
        Exit Function
    End If
    
    Set ts = fso.OpenTextFile(mdPath, 1, False)
    html = ""
    inTable = False
    
    Do Until ts.AtEndOfStream
        line = Trim(ts.ReadLine)
        If Left(line, 1) = "|" And Right(line, 1) = "|" Then
            Dim cells() As String
            Dim i As Integer
            line = Mid(line, 2, Len(line) - 2)
            cells = Split(line, "|")
            Dim isSeparator As Boolean
            isSeparator = True
            For i = LBound(cells) To UBound(cells)
                If InStr(cells(i), "-") = 0 Then
                    isSeparator = False
                    Exit For
                End If
            Next
            If isSeparator Then
            Else
                If Not inTable Then
                    html = html & "<table border='1' cellspacing='0' cellpadding='5'>"
                    inTable = True
                End If
                html = html & "<tr>"
                For i = LBound(cells) To UBound(cells)
                    html = html & "<td>" & Trim(cells(i)) & "</td>"
                Next
                html = html & "</tr>"
            End If
        Else
            If inTable Then
                html = html & "</table><br/>"
                inTable = False
            End If
        End If
    Loop
    
    If inTable Then
        html = html & "</table>"
    End If
    
    ts.Close
    ParseMarkdownTables = html
End Function
"""
    run_vba_macro(vba_code, "BatchSaveAsHTMLRecursive")
