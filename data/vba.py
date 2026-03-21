# data/vba.py
import os
import sys
import subprocess
import shutil
import win32com.client
import path  # 你的 path.py，里面有 TARGET_PATH

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import BD

# ---------- 配置 ----------
# False: 增量更新（保留已有 html）
# True: 强制更新（先清理 data 下非 .dat/.xlsx 文件，再重建网页）
FORCE_UPDATE = False

# 仅这些“数据目录”会参与强制清理（其子目录会递归清理）
DATA_FOLDERS = {
    "BD",
    "BDI",
    "BDIKp",
    "BDIXL",
    "BDIXLKp",
    "BDKp",
    "BDXL",
    "BDXLKp",
}

def run_vba_macro(vba_code, macro_name):
    excel = win32com.client.DispatchEx("Excel.Application")
    wb = None
    try:
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.AskToUpdateLinks = False
        excel.AlertBeforeOverwriting = False
        excel.EnableEvents = False
        excel.ScreenUpdating = False
        wb = excel.Workbooks.Add()
        vb_module = wb.VBProject.VBComponents.Add(1)
        vb_module.CodeModule.AddFromString(vba_code)
        excel.Application.Run(macro_name)
    finally:
        # 结束自动化时保持静默，避免弹出“是否保存工作簿”提示
        try:
            excel.DisplayAlerts = False
        except Exception:
            pass
        if wb is not None:
            try:
                wb.Saved = True
                wb.Close(SaveChanges=False)
            except Exception:
                pass
        # 防止有残留工作簿触发关闭提示
        try:
            while excel.Workbooks.Count > 0:
                w = excel.Workbooks(1)
                w.Saved = True
                w.Close(SaveChanges=False)
        except Exception:
            pass
        try:
            excel.Quit()
        except Exception:
            pass

def run_bd_for_missing_xlsx():
    dat_dir = path.TARGET_PATH
    print("检查 dat 文件并生成缺失的 xlsx...")
    res = BD.process_all_dat_files(dat_dir)
    print("dat → xlsx 转换完成。")
    print("created:", len(res.get("created", [])), "skipped:", len(res.get("skipped", [])))
    print("statistics.md:", res.get("statistics_md"))
    return res


def cleanup_for_force_update(base_dir):
    """
    强制更新时执行：仅清理“数据目录”内除 .dat 外的文件（含 .xlsx）。
    不触碰其他目录（例如根目录脚本、summary、__pycache__ 等）。
    """
    keep_exts = {".dat"}
    deleted_files = 0
    deleted_dirs = 0

    print("FORCE_UPDATE=True: 仅清理数据目录中的旧网页与临时文件...")

    for folder in sorted(DATA_FOLDERS):
        folder_path = os.path.join(base_dir, folder)
        if not os.path.isdir(folder_path):
            continue

        for root, dirs, files in os.walk(folder_path, topdown=False):
            # 删除文件：仅保留 .dat（xlsx 也清理，后续由流程重建）
            for name in files:
                full = os.path.join(root, name)
                ext = os.path.splitext(name)[1].lower()
                if ext in keep_exts:
                    continue
                try:
                    os.remove(full)
                    deleted_files += 1
                except Exception as e:
                    print(f"删除文件失败: {full} -> {e}")

            # 删除 Excel 导出伴生目录 *.files
            for d in dirs:
                if not d.lower().endswith(".files"):
                    continue
                full_dir = os.path.join(root, d)
                try:
                    shutil.rmtree(full_dir, ignore_errors=False)
                    deleted_dirs += 1
                except Exception as e:
                    print(f"删除目录失败: {full_dir} -> {e}")

    print(f"清理完成: 删除文件 {deleted_files} 个, 删除目录 {deleted_dirs} 个")


def run_produce_outputs():
    script_path = os.path.join(os.path.dirname(__file__), "produce_outputs.py")
    print("生成 summary 汇总（调用 produce_outputs.py）...")
    result = subprocess.run([sys.executable, script_path], cwd=path.TARGET_PATH)
    if result.returncode != 0:
        raise RuntimeError(f"produce_outputs.py 执行失败，退出码: {result.returncode}")
    print("summary 汇总生成完成。")

if __name__ == "__main__":
    if FORCE_UPDATE:
        cleanup_for_force_update(path.TARGET_PATH)

    # 先生成缺失的 xlsx（如果需要）
    run_bd_for_missing_xlsx()
    # 再生成结论汇总 xlsx
    run_produce_outputs()

    vba_code = f"""
Sub BatchSaveAsHTMLRecursive()
    Dim fso As Object
    Dim folder As Object
    Dim dict As Object
    Dim indexPath As String
    Dim f As Integer
    Dim forceUpdate As Integer

    ' 关闭 Excel 弹窗与屏幕更新，避免提示框
    Application.DisplayAlerts = False
    Application.AskToUpdateLinks = False
    Application.AlertBeforeOverwriting = False
    Application.ScreenUpdating = False

    Dim rootPath As String
    rootPath = "{path.TARGET_PATH}"
    forceUpdate = {1 if FORCE_UPDATE else 0}

    Set fso = CreateObject("Scripting.FileSystemObject")
    Set folder = fso.GetFolder(rootPath)
    Set dict = CreateObject("Scripting.Dictionary")

    ProcessFolder folder, rootPath, dict, forceUpdate

    indexPath = rootPath & "\\index.html"
    f = FreeFile
    Open indexPath For Output As #f
    Print #f, "<html><head><meta charset='utf-8'><title>Excel 2 HTML</title></head><body>"
    Print #f, "<h1>Excel 2 HTML</h1>"
    If fso.FileExists(rootPath & "\\math\\math.html") Then
        Print #f, "<p><a href='math/math.html' target='_blank'>Math</a></p>"
        Print #f, "<hr/>"
    End If
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

    ' --- 先把 summary 下的 summary xlsx 转为 html（若 html 不存在则生成） ---
    Dim summaryFiles(3) As String
    summaryFiles(0) = "summary\\BD_summary.xlsx"
    summaryFiles(1) = "summary\\BDXL_summary.xlsx"
    summaryFiles(2) = "summary\\BDKp_summary.xlsx"
    summaryFiles(3) = "summary\\BDXLKp_summary.xlsx"

    Dim j As Integer
    For j = 0 To UBound(summaryFiles)
        Dim sXlsxRel As String
        Dim sXlsxFull As String
        Dim sHtmlFull As String
        Dim sHtmlRel As String

        sXlsxRel = summaryFiles(j)
        sXlsxFull = rootPath & "\\" & sXlsxRel
        sHtmlRel = Replace(sXlsxRel, ".xlsx", ".html")
        sHtmlFull = rootPath & "\\" & sHtmlRel

        If fso.FileExists(sXlsxFull) Then
            ' 增量模式：仅缺失时生成；强制模式：总是覆盖生成
            If (Not fso.FileExists(sHtmlFull)) Or forceUpdate = 1 Then
                On Error Resume Next
                Dim wbSum As Workbook
                Set wbSum = Workbooks.Open(sXlsxFull, UpdateLinks:=0, ReadOnly:=False, IgnoreReadOnlyRecommended:=True)
                If Not wbSum Is Nothing Then
                    Call AutoFitWorkbookColumns(wbSum)
                    wbSum.SaveAs sHtmlFull, FileFormat:=44
                    wbSum.Saved = True
                    wbSum.Close SaveChanges:=False
                    Call FixEncoding(sHtmlFull)
                End If
                On Error GoTo 0
            End If
        End If
    Next

    ' --- 在 index.html 末尾加入“有效结论”区块，链接指向 summary/*.html（仅存在时显示） ---
    Print #f, "<hr/>"
    Print #f, "<h1>Conclusions</h1>"
    Print #f, "<ul>"

    For j = 0 To UBound(summaryFiles)
        Dim htmlRel As String
        Dim htmlFull As String
        htmlRel = Replace(summaryFiles(j), ".xlsx", ".html")
        htmlFull = rootPath & "\\" & Replace(htmlRel, "/", "\\")
        If fso.FileExists(htmlFull) Then
            Dim hrefPath As String
            hrefPath = Replace(htmlRel, "\\", "/")  ' 浏览器友好路径
            Dim displayName As String
            displayName = Mid(htmlRel, Len("summary/") + 1) ' 去掉 summary/ 前缀（用于显示）
            Print #f, "<li><a href='" & hrefPath & "' target='_blank'>" & displayName & "</a></li>"
        End If
    Next

    Print #f, "</ul>"
    ' --- 有效结论区块结束 ---

    Print #f, "</body></html>"
    Close #f

    ' 恢复屏幕更新（提示由 Python 自动化层统一管理）
    Application.ScreenUpdating = True
End Sub

Sub ProcessFolder(f As Object, rootPath As String, dict As Object, forceUpdate As Integer)
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

    ' --- 新增：跳过 summary 目录（不处理 summary 及其子目录） ---
    Dim lowPath As String
    lowPath = LCase(f.Path)
    If InStr(lowPath, "\\summary") > 0 Or InStr(lowPath, "/summary") > 0 Then
        Exit Sub
    End If
    If LCase(folderName) = "summary" Then
        Exit Sub
    End If
    ' --- 新增结束 ---

    count = 0

    For Each file In f.Files
        If LCase(Right(file.Name, 5)) = ".xlsx" Then
            If Left(file.Name, 2) <> "~$" Then
                htmlPath = Replace(file.Path, ".xlsx", ".html")
                If Dir(htmlPath) = "" Or forceUpdate = 1 Then
                    Set wb = Workbooks.Open(file.Path, UpdateLinks:=0, ReadOnly:=False, IgnoreReadOnlyRecommended:=True)
                    Call AutoFitWorkbookColumns(wb)
                    wb.SaveAs htmlPath, FileFormat:=44
                    wb.Saved = True
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
        ProcessFolder subFolder, rootPath, dict, forceUpdate
    Next
End Sub

Sub AutoFitWorkbookColumns(wb As Workbook)
    Dim ws As Worksheet
    For Each ws In wb.Worksheets
        On Error Resume Next
        ws.Cells.WrapText = False
        ws.Cells.EntireColumn.AutoFit
        ws.Rows.AutoFit
        On Error GoTo 0
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
