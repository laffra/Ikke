On Error Resume Next

if WScript.Arguments.Count = 0 Then
    WScript.Echo "Usage: cscript search.vbs scope query"
    WScript.Quit
end if

SqlQuery = "SELECT Top 100000 System.ItemPathDisplay " & _
    "FROM SYSTEMINDEX WHERE FREETEXT('" & WScript.Arguments.Item(1) & "') AND " & _
    "SCOPE = '" & WScript.Arguments.Item(0) & "' AND " & _
    "System.DateCreated > '" & Wscript.Arguments.Item(2) & "'"

Set objConnection = CreateObject("ADODB.Connection")
Set objRecordSet = CreateObject("ADODB.Recordset")

objConnection.Open "Provider=Search.CollatorDSO;Extended Properties='Application=Windows';"

objRecordSet.Open SqlQuery, objConnection

objRecordSet.MoveFirst
Do Until objRecordset.EOF
    Wscript.Echo objRecordset.Fields.Item("System.ItemPathDisplay")
    objRecordset.MoveNext
Loop