param(
  [Parameter(Mandatory=$true)][int]$Year,
  [string]$Date = "",
  [int]$MinHeight = 1000,
  [switch]$IncludeUnknownHeightPng,
  [string]$Language = "zh-Hans-CN"
)

$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sourceDir = Join-Path $repo "sources\jinri-jiujia-wechat-links"
$mdDir = Join-Path $sourceDir "$Year-md"
$outRoot = Join-Path $sourceDir "$Year-ocr"

if (!(Test-Path -LiteralPath $mdDir)) {
  throw "Markdown directory not found: $mdDir"
}

New-Item -ItemType Directory -Force -Path $outRoot | Out-Null

Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime] | Out-Null

$script:asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
  Where-Object { $_.Name -eq "AsTask" -and $_.IsGenericMethodDefinition -and $_.GetParameters().Count -eq 1 } |
  Select-Object -First 1

function Await($operation, [Type]$resultType) {
  $task = $script:asTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
  $task.GetAwaiter().GetResult()
}

function Get-Attr($tag, $name) {
  $match = [regex]::Match($tag, "$name=""([^""]+)""")
  if ($match.Success) { return $match.Groups[1].Value }
  return ""
}

function Get-OcrResult($imagePath, $engine) {
  $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync((Resolve-Path $imagePath).Path)) ([Windows.Storage.StorageFile])
  $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

  $words = @()
  foreach ($line in $result.Lines) {
    foreach ($word in $line.Words) {
      $words += [pscustomobject]@{
        text = $word.Text
        x = [int]$word.BoundingRect.X
        y = [int]$word.BoundingRect.Y
        w = [int]$word.BoundingRect.Width
        h = [int]$word.BoundingRect.Height
      }
    }
  }

  [pscustomobject]@{
    width = [int]$bitmap.PixelWidth
    height = [int]$bitmap.PixelHeight
    text = $result.Text
    words = $words
  }
}

$languageObj = [Windows.Globalization.Language]::new($Language)
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($languageObj)
if ($null -eq $engine) {
  throw "Windows OCR language not available: $Language"
}

$mdFiles = if ($Date) {
  @(Join-Path $mdDir "$Date.md")
} else {
  Get-ChildItem -LiteralPath $mdDir -Filter "*.md" | ForEach-Object { $_.FullName }
}

foreach ($mdPath in $mdFiles) {
  if (!(Test-Path -LiteralPath $mdPath)) {
    Write-Warning "Missing markdown: $mdPath"
    continue
  }

  $dateName = [IO.Path]::GetFileNameWithoutExtension($mdPath)
  $dateOut = Join-Path $outRoot $dateName
  $imageOut = Join-Path $dateOut "images"
  New-Item -ItemType Directory -Force -Path $imageOut | Out-Null

  $markdown = Get-Content -LiteralPath $mdPath -Raw
  $tags = [regex]::Matches($markdown, "<img\b[^>]*>") | ForEach-Object { $_.Value }
  $candidates = @()
  foreach ($tag in $tags) {
    $src = (Get-Attr $tag "src") -replace "#imgIndex=.*$", ""
    $idx = Get-Attr $tag "data-index"
    $height = Get-Attr $tag "data-cropsely2"
    $type = Get-Attr $tag "data-type"
    if (!$src) { continue }
    $isUnknownHeightPng = !$height -and $IncludeUnknownHeightPng -and $type -eq "png" -and $idx -match "^\d+$" -and [int]$idx -ge 5
    if (!$isUnknownHeightPng) {
      if (!$height) { continue }
      if ([int]$height -lt $MinHeight) { continue }
    }
    $candidates += [pscustomobject]@{
      index = $idx
      url = $src
      declaredHeight = if ($height) { [int]$height } else { 0 }
      type = $type
    }
  }

  Write-Host "$dateName candidates=$($candidates.Count)"
  $images = @()
  foreach ($candidate in $candidates) {
    $ext = if ($candidate.type -eq "jpeg" -or $candidate.url -match "wx_fmt=jpeg") { "jpg" } else { "png" }
    $imagePath = Join-Path $imageOut "img-$($candidate.index).$ext"
    $textPath = Join-Path $dateOut "img-$($candidate.index).txt"
    $wordsPath = Join-Path $dateOut "img-$($candidate.index).words.json"

    if (!(Test-Path -LiteralPath $imagePath)) {
      & curl.exe -L --silent --show-error --max-time 45 -A "Mozilla/5.0" -e "https://mp.weixin.qq.com/" $candidate.url -o $imagePath
    }

    $ocr = Get-OcrResult $imagePath $engine
    Set-Content -LiteralPath $textPath -Encoding UTF8 -Value $ocr.text
    $ocr.words | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $wordsPath -Encoding UTF8

    $images += [pscustomobject]@{
      index = $candidate.index
      url = $candidate.url
      declaredHeight = $candidate.declaredHeight
      type = $candidate.type
      image = (Resolve-Path -LiteralPath $imagePath).Path.Replace($repo + "\", "").Replace("\", "/")
      text = (Resolve-Path -LiteralPath $textPath).Path.Replace($repo + "\", "").Replace("\", "/")
      words = (Resolve-Path -LiteralPath $wordsPath).Path.Replace($repo + "\", "").Replace("\", "/")
      width = $ocr.width
      height = $ocr.height
      textLength = $ocr.text.Length
      wordCount = $ocr.words.Count
    }
    Write-Host "  img-$($candidate.index) $($ocr.width)x$($ocr.height) words=$($ocr.words.Count) text=$($ocr.text.Length)"
  }

  [pscustomobject]@{
    date = $dateName
    sourceMarkdown = $mdPath.Replace($repo + "\", "").Replace("\", "/")
    minHeight = $MinHeight
    language = $Language
    images = $images
  } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $dateOut "manifest.json") -Encoding UTF8
}
