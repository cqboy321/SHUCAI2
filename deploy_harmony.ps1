# PowerShell script for HarmonyOS optimizations deployment
# Run this script as Administrator

# Display header
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   HarmonyOS Optimizations Deployment Tool  " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Ensure static directories exist
Write-Host "Creating necessary directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "static\css", "static\js" | Out-Null
Write-Host "✓ Directories created successfully" -ForegroundColor Green

# Copy favicon if it doesn't exist
if (-not (Test-Path "static\favicon.ico")) {
    Write-Host "Copying favicon..." -ForegroundColor Yellow
    Copy-Item -Path "vegetable.ico" -Destination "static\favicon.ico" -Force
    Write-Host "✓ Favicon copied to static directory" -ForegroundColor Green
} else {
    Write-Host "✓ Favicon already exists" -ForegroundColor Green
}

# Create test HTML file
Write-Host "Creating test HTML file..." -ForegroundColor Yellow
$testHtmlContent = @"
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>HarmonyOS Test Page</title>
  <link rel="icon" href="favicon.ico">
  <link rel="stylesheet" href="css/harmony.css">
</head>
<body>
  <h1>HarmonyOS 测试页面</h1>
  <p>如果您看到这个页面，说明静态资源服务正常。</p>
  <div class="test-area" style="padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
    <p>这个区域用于测试HarmonyOS特有的CSS和JS优化效果。</p>
  </div>
  <script src="js/harmony.js"></script>
  <script>
    document.addEventListener('DOMContentLoaded', function() {
      var isHarmonyOS = /HarmonyOS|EMUI|HUAWEI|HiSilicon/i.test(navigator.userAgent);
      document.querySelector('.test-area').innerHTML += '<p>当前设备: ' + (isHarmonyOS ? 'HarmonyOS/华为设备' : '非HarmonyOS设备') + '</p>';
      document.querySelector('.test-area').innerHTML += '<p>用户代理: ' + navigator.userAgent + '</p>';
    });
  </script>
</body>
</html>
"@
Set-Content -Path "static\test.html" -Value $testHtmlContent -Encoding UTF8
Write-Host "✓ Test HTML file created" -ForegroundColor Green

# Fix file encodings
Write-Host "Fixing file encodings..." -ForegroundColor Yellow
$filesToFix = @(
    "wsgi.py",
    "static\css\harmony.css",
    "static\js\harmony.js"
)

foreach ($filePath in $filesToFix) {
    if (Test-Path $filePath) {
        $content = Get-Content -Path $filePath -Raw -Encoding UTF8
        Set-Content -Path $filePath -Value $content -Encoding UTF8
        Write-Host "✓ Fixed encoding for $filePath" -ForegroundColor Green
    }
}

# Fix wsgi.py file if necessary
Write-Host "Checking wsgi.py file..." -ForegroundColor Yellow
$wsgiPath = "wsgi.py"

if (Test-Path $wsgiPath) {
    $wsgiContent = Get-Content -Path $wsgiPath -Raw -Encoding UTF8
    
    if ($wsgiContent -match "from flask import request") {
        Write-Host "✓ wsgi.py already has the correct import" -ForegroundColor Green
    } else {
        Write-Host "! wsgi.py needs to be fixed" -ForegroundColor Yellow
        
        # Create backup of original file
        Copy-Item -Path $wsgiPath -Destination "$wsgiPath.bak" -Force
        Write-Host "✓ Created backup at $wsgiPath.bak" -ForegroundColor Green
        
        # Run the fix_deployment.py script
        Write-Host "Running fix_deployment.py..." -ForegroundColor Yellow
        python fix_deployment.py
    }
} else {
    Write-Host "✗ wsgi.py file not found!" -ForegroundColor Red
}

# Check gunicorn_config.py if it exists
if (Test-Path "gunicorn_config.py") {
    Write-Host "Checking gunicorn_config.py..." -ForegroundColor Yellow
    $gunicornContent = Get-Content -Path "gunicorn_config.py" -Raw -Encoding UTF8
    
    if ($gunicornContent -match 'worker_class = "eventlet"') {
        Write-Host "✓ gunicorn_config.py already using eventlet" -ForegroundColor Green
    } else {
        $gunicornContent = $gunicornContent -replace 'worker_class = "sync"', 'worker_class = "eventlet"'
        Set-Content -Path "gunicorn_config.py" -Value $gunicornContent -Encoding UTF8
        Write-Host "✓ Updated gunicorn_config.py to use eventlet" -ForegroundColor Green
    }
}

# Run the test script
Write-Host "Running test script..." -ForegroundColor Yellow
python test_harmony.py

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   Deployment preparation completed!       " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Run 'flask run' to test locally" -ForegroundColor White
Write-Host "2. Check with a HarmonyOS device or emulator" -ForegroundColor White
Write-Host "3. Deploy to production server" -ForegroundColor White
Write-Host "4. See HARMONIZATION.md for more details" -ForegroundColor White 