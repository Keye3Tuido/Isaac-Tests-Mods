# data/vba.py
import os
import sys
import subprocess
import shutil
import re
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


def patch_exported_html(base_dir):
    # 只修复 Excel 导出文件的 charset 声明和移动端文字折行
    # 不强制添加表格线/宽度，不修改 index.html（VBA 已正确生成）
    marker = "id='bd-mobile-fix'"
    # 有文字表格时注入分隔线；纯图片页不注入分隔线
    css_with_border = (
        "<style id='bd-mobile-fix'>"
        "body{overflow-x:auto!important;}"
        "table{border-collapse:collapse!important;}"
        "th,td{border:1px solid #666!important;white-space:normal!important;word-break:break-word!important;"
        "overflow-wrap:anywhere!important;height:auto!important;}"
        "@media (max-width: 900px){body{overflow-x:auto!important;-webkit-overflow-scrolling:touch!important;}"
        "table{table-layout:auto!important;width:max-content!important;min-width:100%!important;}"
        "col{width:auto!important;}"
        "th,td{white-space:nowrap!important;word-break:normal!important;overflow-wrap:normal!important;font-size:12px!important;}}"
        "</style>"
    )
    css_without_border = (
        "<style id='bd-mobile-fix'>"
        "body{overflow-x:auto!important;}img{max-width:100%!important;height:auto!important;}"
        "@media (max-width: 900px){body{overflow-x:auto!important;-webkit-overflow-scrolling:touch!important;}img{max-width:100%!important;height:auto!important;}}"
        "</style>"
    )
    excluded_sheet_names = {"门概率图", "方向图"}

    def has_textual_table_cells(html_text):
        # 仅当 td/th 中存在可见文字时才认为是“文字表格”
        for m in re.finditer(r"<(?:td|th)\b[^>]*>(.*?)</(?:td|th)>", html_text, flags=re.IGNORECASE | re.DOTALL):
            inner = re.sub(r"<[^>]+>", "", m.group(1))
            inner = re.sub(r"&(nbsp|#160);", "", inner, flags=re.IGNORECASE)
            inner = re.sub(r"\s+", "", inner)
            if inner:
                return True
        return False

    def get_sheet_display_name_from_tabstrip(html_path):
        base = os.path.basename(html_path).lower()
        m = re.match(r"(sheet\d+\.html)$", base)
        if not m:
            return ""
        tabstrip_path = os.path.join(os.path.dirname(html_path), "tabstrip.html")
        if not os.path.exists(tabstrip_path):
            return ""
        try:
            tab = open(tabstrip_path, "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            return ""
        pat = r"href=\"" + re.escape(m.group(1)) + r"\"[^>]*><font[^>]*>(.*?)</font>"
        mm = re.search(pat, tab, flags=re.IGNORECASE | re.DOTALL)
        if not mm:
            return ""
        name = re.sub(r"<[^>]+>", "", mm.group(1)).strip()
        return name

    def patch_one(html_path):
        # 跳过 index.html，由 VBA 负责生成
        if os.path.basename(html_path).lower() == 'index.html':
            return
        try:
            text = open(html_path, "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            return

        original = text
        text = text.replace("charset=windows-1252", "charset=utf-8")
        text = text.replace("charset=gb2312", "charset=utf-8")

        if "viewport" not in text.lower():
            text = re.sub(r"<head>", "<head><meta name='viewport' content='width=device-width, initial-scale=1'>", text, count=1, flags=re.IGNORECASE)

        sheet_name = get_sheet_display_name_from_tabstrip(html_path)
        if sheet_name in excluded_sheet_names:
            css = css_without_border
        else:
            css = css_with_border if has_textual_table_cells(text) else css_without_border
        # 每次运行都刷新 bd-mobile-fix，避免旧样式残留
        text = re.sub(
            r"<style\s+id=['\"]bd-mobile-fix['\"]>.*?</style>",
            css,
            text,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if marker not in text.lower() and "</head>" in text.lower():
            text = re.sub(r"</head>", css + "</head>", text, count=1, flags=re.IGNORECASE)

        if text != original:
            open(html_path, "w", encoding="utf-8", newline="").write(text)

    for root, _dirs, files in os.walk(base_dir):
        for name in files:
            if name.lower().endswith(".html"):
                patch_one(os.path.join(root, name))

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
    Print #f, "<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Boss Direction Analysis</title><style>a,a:visited{{color:#06c;text-decoration:underline;}}table{{border-collapse:collapse;}}th,td{{border:1px solid #666;white-space:normal;word-break:break-word;overflow-wrap:anywhere;vertical-align:top;padding:4px;}}@media (max-width:900px){{th,td{{font-size:14px;}}}}</style></head><body>"
    Print #f, "<h1>Boss Direction Analysis</h1>"
    If fso.FileExists(rootPath & "\\math\\math.html") Then
        Print #f, "<p><a href='math/math.html' target='_blank'>Math</a></p>"
        Print #f, "<hr/>"
    End If
    Print #f, ParseMarkdownTables(rootPath & "\\statistics.md", rootPath)
    Print #f, "<hr/>"

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
                    Call FixWorkbookHtmlAssets(sHtmlFull)
                End If
                On Error GoTo 0
            End If
            If fso.FileExists(sHtmlFull) Then
                Call FixWorkbookHtmlAssets(sHtmlFull)
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
                End If
                If Dir(htmlPath) <> "" Then
                    Call FixWorkbookHtmlAssets(htmlPath)
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

Sub FixWorkbookHtmlAssets(mainHtmlPath As String)
    Dim fso As Object
    Dim filesFolderPath As String
    Dim folderObj As Object
    Dim fileObj As Object

    Set fso = CreateObject("Scripting.FileSystemObject")

    If fso.FileExists(mainHtmlPath) Then
        Call FixEncoding(mainHtmlPath)
    End If

    filesFolderPath = Replace(mainHtmlPath, ".html", ".files")
    If Not fso.FolderExists(filesFolderPath) Then
        Exit Sub
    End If

    Set folderObj = fso.GetFolder(filesFolderPath)
    For Each fileObj In folderObj.Files
        If LCase(Right(fileObj.Name, 5)) = ".html" Then
            Call FixEncoding(fileObj.Path)
        End If
    Next
End Sub

Sub FixEncoding(htmlPath As String)
    ' 已由 Python patch_exported_html 统一处理，此处不再修改文件
    ' 避免 VBA 以 GBK 读取 UTF-8 内容导致中文乱码
End Sub

Function ParseMarkdownTables(mdPath As String, rootPath As String) As String
    Dim fso As Object, ts As Object
    Dim line As String
    Dim html As String
    Dim inTable As Boolean
    Dim colGroup As Integer, colN As Integer, colRep As Integer, colRepPlus As Integer
    Dim currentGroup As String

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
                    colGroup = -1
                    colN = -1
                    colRep = -1
                    colRepPlus = -1
                    currentGroup = ""
                End If
                html = html & "<tr>"
                For i = LBound(cells) To UBound(cells)
                    Dim cellVal As String
                    cellVal = Trim(cells(i))

                    If LCase(Trim(cells(0))) = "#" Then
                        If LCase(cellVal) = "#" Then colGroup = i
                        If LCase(cellVal) = "n" Then colN = i
                        If LCase(cellVal) = "rep(w)" Then colRep = i
                        If LCase(cellVal) = "rep+(w)" Then colRepPlus = i
                        html = html & "<td>" & cellVal & "</td>"
                    Else
                        If colGroup >= 0 And i = colGroup Then
                            If cellVal <> "" Then
                                currentGroup = cellVal
                            End If
                        End If

                        If (i = colRep Or i = colRepPlus) And currentGroup <> "" And LCase(currentGroup) <> "total" Then
                            Dim nVal As String
                            nVal = ""
                            If colN >= 0 And colN <= UBound(cells) Then
                                nVal = Trim(cells(colN))
                            End If

                            Dim relHref As String
                            relHref = BuildStatisticsHref(currentGroup, nVal, (i = colRepPlus), cellVal)
                            If relHref <> "" Then
                                html = html & "<td><a href='" & relHref & "' target='_blank'>" & cellVal & "</a></td>"
                            Else
                                html = html & "<td>" & cellVal & "</td>"
                            End If
                        Else
                            html = html & "<td>" & cellVal & "</td>"
                        End If
                    End If
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

Function BuildStatisticsHref(groupName As String, nValue As String, isRepPlus As Boolean, scoreText As String) As String
    Dim prefix As String
    Dim safeGroup As String
    Dim safeScore As String

    safeGroup = Trim(groupName)
    safeScore = Trim(scoreText)
    If safeGroup = "" Or safeScore = "" Then
        BuildStatisticsHref = ""
        Exit Function
    End If

    If isRepPlus Then
        prefix = "r+_"
    Else
        prefix = "rep_"
    End If

    Select Case UCase(safeGroup)
        Case "BD", "BDXL", "BDKP", "BDXLKP"
            BuildStatisticsHref = safeGroup & "/" & prefix & safeGroup & "_" & safeScore & "w.html"
        Case "BDI", "BDIXL", "BDIKP", "BDIXLKP"
            If Trim(nValue) = "" Then
                BuildStatisticsHref = ""
            Else
                BuildStatisticsHref = safeGroup & "/" & Trim(nValue) & "/" & prefix & safeGroup & Trim(nValue) & "_" & safeScore & "w.html"
            End If
        Case Else
            BuildStatisticsHref = ""
    End Select
End Function
"""
    run_vba_macro(vba_code, "BatchSaveAsHTMLRecursive")
    patch_exported_html(path.TARGET_PATH)
