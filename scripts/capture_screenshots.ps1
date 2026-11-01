param(
    [string]$Prefix = "before"
)

$outDir = "C:\Users\baotr\Downloads\trading\docs\audits\evidence\investintel_premium_desktop_ui_2026-10-28"
if (!(Test-Path $outDir)) {
    New-Item -ItemType Directory -Force -Path $outDir
}

$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"

$routes = @(
    @{ name = "overview"; path = "/" },
    @{ name = "ai"; path = "/ai" },
    @{ name = "market"; path = "/market" },
    @{ name = "opportunities"; path = "/opportunities" },
    @{ name = "portfolio"; path = "/portfolio" },
    @{ name = "research"; path = "/research" },
    @{ name = "data_center"; path = "/data-center" },
    @{ name = "watchlist"; path = "/watchlist" }
)

$resolutions = @(
    @{ label = "1440"; w = 1440; h = 900 }
)

foreach ($r in $routes) {
    foreach ($res in $resolutions) {
        $outFile = "$outDir\${Prefix}_$($r.name)_$($res.label).png"
        $url = "http://localhost:3000$($r.path)"
        Write-Host "Capturing $($r.name) at $($res.w)x$($res.h) -> $outFile"
        $args = @(
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--window-size=$($res.w),$($res.h)",
            "--screenshot=$outFile",
            $url
        )
        Start-Process -FilePath $chromePath -ArgumentList $args -Wait
        Start-Sleep -Milliseconds 400
    }
}

# Also capture 1280x800 and 1920x1080 for the primary pages (overview, ai, market)
$specialRes = @(
    @{ label = "1280"; w = 1280; h = 800 },
    @{ label = "1920"; w = 1920; h = 1080 }
)

$keyRoutes = @(
    @{ name = "overview"; path = "/" },
    @{ name = "ai"; path = "/ai" },
    @{ name = "market"; path = "/market" }
)

foreach ($r in $keyRoutes) {
    foreach ($res in $specialRes) {
        $outFile = "$outDir\${Prefix}_$($r.name)_$($res.label).png"
        $url = "http://localhost:3000$($r.path)"
        Write-Host "Capturing $($r.name) at $($res.w)x$($res.h) -> $outFile"
        $args = @(
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--window-size=$($res.w),$($res.h)",
            "--screenshot=$outFile",
            $url
        )
        Start-Process -FilePath $chromePath -ArgumentList $args -Wait
        Start-Sleep -Milliseconds 400
    }
}

Write-Host "Screenshot capture complete for prefix: $Prefix"
