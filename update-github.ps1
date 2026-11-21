$ErrorActionPreference = "Continue"
$repo = $PSScriptRoot
Set-Location -LiteralPath $repo

$log = Join-Path $env:TEMP "xpbedwars-github-update.log"
$title = "GitHub 更新结果"

function Show-Result {
    param(
        [string]$Message,
        [string]$Kind = "Information"
    )

    try {
        Add-Type -AssemblyName PresentationFramework
        $icon = if ($Kind -eq "Error") {
            [System.Windows.MessageBoxImage]::Error
        } else {
            [System.Windows.MessageBoxImage]::Information
        }
        [void][System.Windows.MessageBox]::Show(
            $Message,
            $title,
            [System.Windows.MessageBoxButton]::OK,
            $icon
        )
    } catch {
        Write-Host ""
        Write-Host $title
        Write-Host $Message
        Read-Host "按回车关闭"
    }
}

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)

    $raw = & git @GitArgs 2>&1
    $code = $LASTEXITCODE
    $lines = @($raw | ForEach-Object { $_.ToString() })
    return [pscustomobject]@{
        Code = $code
        Lines = $lines
    }
}

function Write-GitOutput {
    param([string[]]$Lines)

    if ($null -eq $Lines -or $Lines.Count -eq 0) {
        return
    }
    $Lines | Tee-Object -FilePath $log -Append | Out-Host
}

function Get-Tail {
    $tail = Get-Content -LiteralPath $log -Tail 8 -ErrorAction SilentlyContinue | Out-String
    if ([string]::IsNullOrWhiteSpace($tail)) {
        return "详细日志：$log"
    }
    return $tail.Trim()
}

try {
    Set-Content -LiteralPath $log -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] update start" -Encoding utf8

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Show-Result -Message "没有找到 Git，请先安装 Git for Windows。" -Kind Error
        return
    }

    Write-Host "=========================================="
    Write-Host " xpbedwars-server-pack GitHub updater"
    Write-Host "=========================================="
    Write-Host ""

    $status = Invoke-Git status --short
    Write-GitOutput -Lines $status.Lines
    Write-Host ""

    $add = Invoke-Git add -A
    Write-GitOutput -Lines $add.Lines
    if ($add.Code -ne 0) {
        Show-Result -Message "git add 失败。`n`n$(Get-Tail)" -Kind Error
        return
    }

    $diff = Invoke-Git diff --cached --quiet

    if ($diff.Code -eq 1) {
        $msg = Read-Host "提交说明（直接回车自动生成）"
        if ([string]::IsNullOrWhiteSpace($msg)) {
            $msg = "update: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        }

        $commit = Invoke-Git commit -m $msg
        Write-GitOutput -Lines $commit.Lines
        if ($commit.Code -ne 0) {
            Show-Result -Message "git commit 失败。`n`n$(Get-Tail)" -Kind Error
            return
        }
        $detail = "已提交：$msg"
    } elseif ($diff.Code -eq 0) {
        $detail = "没有新的改动，仅检查远程状态。"
    } else {
        Show-Result -Message "检查改动失败，请检查当前目录是否为 Git 仓库。`n`n$(Get-Tail)" -Kind Error
        return
    }

    $rev = Invoke-Git rev-parse --short HEAD
    $hash = ""
    if ($rev.Lines.Count -gt 0) {
        $hash = ($rev.Lines[0] | Out-String).Trim()
    }

    Write-Host ""
    Write-Host "正在推送到 origin main ..."
    $push = Invoke-Git push origin main
    Write-GitOutput -Lines $push.Lines
    if ($push.Code -ne 0) {
        Show-Result -Message "推送失败。`n`n$(Get-Tail)" -Kind Error
        return
    }

    Show-Result -Message "提交 $hash 已推送到 origin main。`n`n$detail"
} catch {
    Show-Result -Message "脚本执行失败：`n$($_.Exception.Message)" -Kind Error
}
