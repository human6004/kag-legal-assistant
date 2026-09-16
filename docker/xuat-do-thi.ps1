# Xuat do thi ra legal.dump de dua cho nguoi khac
#
# Chay o GOC REPO:
#   .\docker\xuat-do-thi.ps1
#
# Script nay CHI DOC do thi. No khong xoa database, khong dung compose.
# Buoc duy nhat cham vao container dang chay la `docker stop` roi `docker start`
# lai ngay - dung nhu RESTORE-GRAPH.md van noi.
#
# Vi sao phai stop: Neo4j khong cho dump khi database dang mo. Ban DozerDB nay
# thieu `STOP DATABASE`, nen phai dung ca container roi dump ngoai tuyen.
#
# File nay co tinh giu thuan ASCII: PowerShell tren Windows doc .ps1 theo bang ma
# he thong, chu co dau se hong va script bao loi cu phap kho hieu.

$ErrorActionPreference = 'Stop'

$goc  = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $goc 'dist'
$img  = 'spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j:latest'
$ct   = 'release-openspg-neo4j'
$tam  = Join-Path $dist 'neo4j-data'
$dump = Join-Path $dist 'legal.dump'

function Buoc($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }

# --- 0. Kiem tra tien de -----------------------------------------------------
Buoc '0. Kiem tra'

if (-not (docker ps -a --filter "name=^/$ct$" --format '{{.Names}}')) {
    throw "Khong thay container '$ct'. Bat Docker Desktop roi thu lai."
}

# Tim volume THUC SU dang chua /data. Khong doan theo ten: may da dung tu truoc
# nam tren volume an danh ten hex, may dung compose moi nam tren volume co ten.
# Phai loc theo Destination, vi container con gan volume khac vao /logs.
$raw = docker inspect $ct --format '{{json .Mounts}}' | ConvertFrom-Json
$vol = ($raw | Where-Object { $_.Destination -eq '/data' }).Name
if (-not $vol) { throw "Container '$ct' khong gan volume nao vao /data." }

if ($vol -eq 'kag-legal-neo4j-data') {
    Write-Host "Volume /data : $vol  (volume co ten, dung nhu compose khai)"
} else {
    Write-Host "Volume /data : $vol" -ForegroundColor Yellow
    Write-Host "  -> Volume AN DANH. Khong sao: dump doc tu volume nay, con nguoi" -ForegroundColor Yellow
    Write-Host "     nhan nap vao volume cua ho. Ghi lai ten de doi chieu." -ForegroundColor Yellow
}

$n = (docker exec $ct cypher-shell -u neo4j -p 'neo4j@openspg' -d legal `
        'MATCH (n) RETURN count(n)' 2>$null | Select-Object -Last 1).Trim()
Write-Host "Node trong DB legal: $n"
if ($n -ne '7624') {
    Write-Host "  CANH BAO: mong doi 7624. Do thi da doi - cap nhat so trong" -ForegroundColor Yellow
    Write-Host "  docker/RESTORE-GRAPH.md va docker/kiem-chung-do-thi.ps1." -ForegroundColor Yellow
}

# --- 1. Don ban cu -----------------------------------------------------------
Buoc '1. Don lan chay truoc'

if (Test-Path $tam) { Remove-Item $tam -Recurse -Force; Write-Host "Da xoa thu muc tam cu" }
if (Test-Path $dump) {
    $cu = (Get-Item $dump).Length / 1GB
    Remove-Item $dump -Force
    Write-Host ("Da xoa legal.dump cu ({0:N2} GB)" -f $cu)
}
New-Item -ItemType Directory -Path $dist -Force | Out-Null

# --- 2. Chep thu muc du lieu ra ngoai ---------------------------------------
Buoc '2. Chep /data ra ngoai (2,9 GB, vai phut)'

docker stop $ct | Out-Null
try {
    docker cp "${ct}:/data" $tam
    if ($LASTEXITCODE -ne 0) { throw "docker cp that bai" }
} finally {
    # Bat lai du thanh cong hay loi - khong de nguoi dung quen.
    docker start $ct | Out-Null
    Write-Host "Da bat lai $ct"
}

# --- 3. Dump ngoai tuyen -----------------------------------------------------
Buoc '3. Dump ngoai tuyen'

docker run --rm -v "${tam}:/data" -v "${dist}:/dump" $img `
    neo4j-admin database dump legal --to-path=/dump --overwrite-destination=true
if ($LASTEXITCODE -ne 0) { throw "neo4j-admin dump that bai" }

# --- 4. Don thu muc tam ------------------------------------------------------
Buoc '4. Don thu muc tam'

Remove-Item $tam -Recurse -Force
Write-Host "Da xoa thu muc tam"

if (-not (Test-Path $dump)) { throw "Khong thay $dump sau khi dump." }
$gb = (Get-Item $dump).Length / 1GB

Write-Host ''
Write-Host ("XONG. dist\legal.dump = {0:N2} GB" -f $gb) -ForegroundColor Green
Write-Host ''
Write-Host 'Doi chieu voi con so trong docker\RESTORE-GRAPH.md truoc khi gui.'
Write-Host 'Gui qua Drive - /dist nam trong .gitignore nen Git khong nhan.'
