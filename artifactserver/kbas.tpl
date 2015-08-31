<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
  <meta http-equiv="content-type"
 content="text/html; charset=ISO-8859-1">
  <title>index</title>
  <link rel="stylesheet" type="text/css" href="{{css}}"/>
</head>
<body>
%#template to generate a HTML table from a list 
<p>Available Artifacts:</p>
<table border="0">
%for row in rows:
  <tr>
  %for col in row:
    <td>{{col}}</td>
  %end
  </tr>
%end
</table>
</body>