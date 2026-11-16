Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class CapP {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
'@
$p = Start-Process "$env:LOCALAPPDATA\Programs\FOXFall\FOXFall.exe" -PassThru
Start-Sleep 14
$proc = Get-Process FOXFall -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $proc) { Write-Host "no window"; exit 1 }
[CapP]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
Start-Sleep 2
$r = New-Object CapP+RECT
[CapP]::GetWindowRect($proc.MainWindowHandle, [ref]$r) | Out-Null
$w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$dc = $g.GetHdc()
[CapP]::PrintWindow($proc.MainWindowHandle, $dc, 2) | Out-Null   # PW_RENDERFULLCONTENT
$g.ReleaseHdc($dc)
$bmp.Save("D:\dsh-workflow\projects\FOXFall-repo\assets\app-screenshot.png")
Write-Host "PrintWindow capture ${w}x${h}"
Get-Process FOXFall -ErrorAction SilentlyContinue | Stop-Process -Force