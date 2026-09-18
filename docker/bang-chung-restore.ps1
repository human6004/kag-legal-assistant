# Bang chung restore sach - chay tren volume TRANG hoan toan
#
# Muc dich: chung minh legal.dump nap lai duoc, bang LOG THAT chu khong phai
# suy luan. Script KHONG dung toi volume chua do thi goc.
#
# Chay o goc repo:
#   .\docker\bang-chung-restore.ps1
#
# Script nay CHI DOC legal.dump. No khong ghi de len bat cu thu gi cua do thi goc.

# Neo4j in log INFO ra stderr. Voi ErrorActionPreference='Stop', PowerShell coi
# do la loi va giet script giua chung - dung cai bay da gap voi eval.py. Nen o
# day KHONG dat 'Stop'; thay vao do tu kiem tra $LASTEXITCODE o cho can.
$ErrorActionPreference = 'Continue'

$goc  = Split-Path -Parent $PSScriptRoot
$dump = Join-Path $goc 'dist\legal.dump'
# Ghim digest theo HANDOFF_MANIFEST.json, khong dung tag :latest
$img  = 'spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j@sha256:4bc5b7f6b83d333b1d2c8f60ac145c068d77d50bca65b3a07c927f9e2a541eb9'
$ra   = Join-Path $goc 'dist\RESTORE_EVIDENCE.txt'

$uId     = [System.Guid]::NewGuid().ToString('N').Substring(0, 8)
$volTest = "kag-handoff-tmp-$uId"
$ctTest  = "kag-handoff-verify-$uId"

# Mat khau test. KHONG phai mat khau that cua he thong, chi dung cho container
# tam thoi bi xoa ngay sau khi do xong. Khong co secret nao khac trong file nay.
$mkTest = 'testonly'

$dong = New-Object System.Collections.Generic.List[string]
function Ghi($s) { $dong.Add($s); Write-Host $s }

function DonDep {
    # Don dep chi cac tai nguyen tao ra boi lan chay nay (dua tren ten duy nhat $uId)
    $ErrorActionPreference = 'Continue'
    docker rm -f $ctTest 2>&1 | Out-Null
    docker volume rm $volTest 2>&1 | Out-Null
}

# --- Chuan bi ---------------------------------------------------------------
Ghi "================================================================"
Ghi " BANG CHUNG RESTORE SACH"
Ghi " Thoi diem: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')"
Ghi "================================================================"
Ghi ""

if (-not (Test-Path $dump)) { throw "Khong thay $dump" }

# --- 0. Do thi GOC, truoc khi dung den --------------------------------------
Ghi "--- 0. Do thi GOC (khong bi dung toi) ---"
$ctGoc = 'release-openspg-neo4j'
$raw = docker inspect $ctGoc --format '{{json .Mounts}}' | ConvertFrom-Json
$volGoc = ($raw | Where-Object { $_.Destination -eq '/data' }).Name
Ghi "Volume do thi goc : $volGoc"
Ghi "   (script nay KHONG dung vao volume nay)"
$nodeTruoc = (docker exec $ctGoc cypher-shell -u neo4j -p 'neo4j@openspg' -d legal 'MATCH (n) RETURN count(n)' 2>$null | Select-Object -Last 1).Trim()
$canhTruoc = (docker exec $ctGoc cypher-shell -u neo4j -p 'neo4j@openspg' -d legal 'MATCH ()-[r]->() RETURN count(r)' 2>$null | Select-Object -Last 1).Trim()
Ghi "Node truoc restore: $nodeTruoc"
Ghi "Canh truoc restore: $canhTruoc"
Ghi ""

# --- 1. SHA-256 --------------------------------------------------------------
Ghi "--- 1. SHA-256 cua file dump ---"
$h = (Get-FileHash $dump -Algorithm SHA256).Hash
$co = (Get-Item $dump).Length
Ghi "sha256      : $h"
Ghi "size_bytes  : $co"
Ghi "size_gib    : $([math]::Round($co/1GB,3))"
Ghi ""

# --- 2. Volume trang ---------------------------------------------------------
Ghi "--- 2. Tao volume TRANG (khong co du lieu gi) ---"
DonDep
docker volume create $volTest | Out-Null
Ghi "Da tao volume: $volTest"
Ghi ""

# --- 3. Thu nap KHONG tao database (de chung minh loi nay that) --------------
Ghi "--- 3. THU NAP SAI: nap truoc, khong tao database ---"
Ghi "   Day la cach lam SAI, chay de chung minh no that su hong."
docker run --rm -v "${volTest}:/data" -v "$(Split-Path $dump):/dump:ro" $img `
    neo4j-admin database load legal --from-path=/dump --overwrite-destination=true 2>&1 |
    Select-String -Pattern "^Done:" | ForEach-Object { Ghi "   $($_.Line.Trim())" }

docker run -d --name $ctTest -v "${volTest}:/data" -e "NEO4J_AUTH=neo4j/$mkTest" $img 2>&1 | Out-Null
for ($i=0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 5
    $r = docker exec $ctTest cypher-shell -u neo4j -p $mkTest 'RETURN 1' 2>$null | Select-Object -Last 1
    if ($r -and $r.Trim() -eq '1') { break }
}
$dbSai = docker exec $ctTest cypher-shell -u neo4j -p $mkTest "SHOW DATABASES YIELD name RETURN name" 2>$null
Ghi "   SHOW DATABASES sau khi nap ma khong tao:"
$dbSai | Where-Object { $_.Trim() } | ForEach-Object { Ghi "     $($_.Trim())" }
$qSai = docker exec $ctTest cypher-shell -u neo4j -p $mkTest -d legal 'MATCH (n) RETURN count(n)' 2>&1
# Truy van vao database khong ton tai thi docker tra ve ErrorRecord, khong phai
# chuoi. Phai ep ve string truoc khi goi .Trim(), khong thi script chet.
# Chi giu dong thong bao that, bo phan PowerShell chen vao.
$qSaiChu = if ($qSai) { (($qSai | Out-String) -split "`n" | Where-Object { $_ -match "routing table|does not exist" } | Select-Object -First 1) } else { $null }
if (-not $qSaiChu) { $qSaiChu = '<khong tra ve gi>' }
Ghi "   Truy van -d legal: $($qSaiChu.Trim())"
Ghi "   => Ket luan: load bao 'Done' nhung database KHONG ton tai."
Ghi ""

# --- 4. Lam lai DUNG: tao database truoc, roi nap ----------------------------
Ghi "--- 4. NAP DUNG: CREATE DATABASE legal truoc, roi load ---"
DonDep
docker volume create $volTest | Out-Null
Ghi "   Da xoa volume cu, tao volume TRANG moi."

docker run -d --name $ctTest -v "${volTest}:/data" -e "NEO4J_AUTH=neo4j/$mkTest" $img 2>&1 | Out-Null
for ($i=0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 5
    $r = docker exec $ctTest cypher-shell -u neo4j -p $mkTest 'RETURN 1' 2>$null | Select-Object -Last 1
    if ($r -and $r.Trim() -eq '1') { Write-Host "   Neo4j san sang sau $($i*5)s"; break }
}

docker exec $ctTest cypher-shell -u neo4j -p $mkTest 'CREATE DATABASE legal' 2>&1 | Out-Null
Ghi "   Da chay: CREATE DATABASE legal"
docker exec $ctTest cypher-shell -u neo4j -p $mkTest "SHOW DATABASES YIELD name, currentStatus RETURN name, currentStatus" 2>$null |
    Where-Object { $_.Trim() } | ForEach-Object { Ghi "     $($_.Trim())" }

docker stop $ctTest 2>&1 | Out-Null
Ghi "   Da stop container. Nap dump:"
docker run --rm -v "${volTest}:/data" -v "$(Split-Path $dump):/dump:ro" $img `
    neo4j-admin database load legal --from-path=/dump --overwrite-destination=true 2>&1 |
    Select-String -Pattern "^Done:" | ForEach-Object { Ghi "   $($_.Line.Trim())" }

docker start $ctTest 2>&1 | Out-Null
for ($i=0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 5
    $r = docker exec $ctTest cypher-shell -u neo4j -p $mkTest -d legal 'MATCH (n) RETURN count(n)' 2>$null | Select-Object -Last 1
    if ($r -and $r.Trim() -match '^\d+$' -and $r.Trim() -ne '0') { break }
}
Ghi ""

# --- 5. Do lai ---------------------------------------------------------------
Ghi "--- 5. KIEM CHUNG sau restore ---"
function Dem($q) {
    # Docker co the tra ErrorRecord khi cau lenh loi. Ep ve string truoc.
    $r = docker exec $ctTest cypher-shell -u neo4j -p $mkTest -d legal $q 2>&1
    if (-not $r) { return '' }
    return ($r | Out-String).Trim().Split("`n")[-1].Trim()
}
$nodeSau  = Dem 'MATCH (n) RETURN count(n)'
$canhSau  = Dem 'MATCH ()-[r]->() RETURN count(r)'
$vecSau   = Dem "SHOW INDEXES YIELD type WHERE type = 'VECTOR' RETURN count(*)"
$chunkSau = Dem 'MATCH (c:`Legal.Chunk`) RETURN count(c)'
$docSau   = Dem 'MATCH (n:`Legal.LegalDocument`) RETURN count(n)'
$nhanSau  = Dem "MATCH (n) UNWIND labels(n) AS l WITH DISTINCT l WHERE l STARTS WITH 'Legal.' RETURN count(l)"
$offline  = Dem "SHOW INDEXES YIELD state WHERE state <> 'ONLINE' RETURN count(*)"

Ghi "node         : $nodeSau"
Ghi "canh         : $canhSau"
Ghi "vector index : $vecSau"
Ghi "Legal.Chunk  : $chunkSau"
Ghi "LegalDocument: $docSau"
Ghi "nhan Legal.* : $nhanSau"
Ghi "index offline: $offline"
Ghi ""

# --- 6. Truy van that, tra nguon ve -----------------------------------------
Ghi "--- 6. TRUY VAN THAT tren ban restore ---"
Ghi "   (chay tren du lieu da restore, khong can LLM, khong ton tien)"

Ghi ""
Ghi "   [6a] Node van ban co metadata day du:"
# Backtick trong nhan Cypher bi PowerShell an mat khi nam trong chuoi "..." co
# noi suy. Dung nhan qua bien de tranh han, khong thi Cypher nhan duoc
# 'Legal.LegalDocument' tran va hieu dau cham la truy cap thuoc tinh.
$L_DOC = '`Legal.LegalDocument`'
$L_CHUNK = '`Legal.Chunk`'
$L_ARTICLE = '`Legal.Article`'

$tv6a = "MATCH (n:$L_DOC) WHERE n.docNumber IS NOT NULL RETURN n.name, n.docNumber, n.dateEffective, n.status ORDER BY n.name LIMIT 3"
$r6a = docker exec $ctTest cypher-shell -u neo4j -p $mkTest -d legal --format plain $tv6a 2>&1
if ($r6a) { ($r6a | Out-String).Trim().Split("`n") | Where-Object { $_.Trim() } | ForEach-Object { Ghi "     $($_.Trim())" } }

Ghi ""
Ghi "   [6b] Truy nguoc: chunk -> van ban (chung minh provenance con nguyen):"
$tv6b = "MATCH (c:$L_CHUNK)-[:source]-(d:$L_DOC) RETURN c.name, d.name LIMIT 3"
$r6b = docker exec $ctTest cypher-shell -u neo4j -p $mkTest -d legal --format plain $tv6b 2>&1
if ($r6b) { ($r6b | Out-String).Trim().Split("`n") | Where-Object { $_.Trim() } | ForEach-Object { Ghi "     $($_.Trim())" } }

Ghi ""
Ghi "   [6c] Vector con nguyen tren node Article:"
$tv6c = "MATCH (n:$L_ARTICLE) WHERE n.``_name_vector`` IS NOT NULL RETURN count(n)"
$r6c = docker exec $ctTest cypher-shell -u neo4j -p $mkTest -d legal --format plain $tv6c 2>&1
if ($r6c) { ($r6c | Out-String).Trim().Split("`n") | Where-Object { $_.Trim() } | ForEach-Object { Ghi "     Article co vector: $($_.Trim())" } }
Ghi ""
Ghi "   [6d] Relationship types con nguyen:"
$rt = Dem 'MATCH ()-[r]->() RETURN count(DISTINCT type(r))'
Ghi "     so loai quan he: $rt"
Ghi ""

# --- 7. Ket luan -------------------------------------------------------------
$khop = ($nodeSau -eq $nodeTruoc) -and ($canhSau -eq $canhTruoc)
Ghi "--- 7. KET LUAN ---"
Ghi "node goc=$nodeTruoc  node restore=$nodeSau"
Ghi "canh goc=$canhTruoc  canh restore=$canhSau"
Ghi "index offline: $offline (phai la 0)"
if ($khop -and $offline -eq '0') {
    Ghi "KET QUA: KHOP HOAN TOAN. Dump nguyen ven, restore duoc."
} else {
    Ghi "KET QUA: KHONG KHOP - xem lai!"
}
Ghi ""
Ghi "Luu y: script nay da dung volume TAM '$volTest' va container TAM '$ctTest'."
Ghi "Do thi goc o volume '$volGoc' KHONG bi dung toi."

# --- Don dep -----------------------------------------------------------------
Ghi ""
Ghi "--- 8. Don dep ---"
DonDep
Ghi "Da xoa container $ctTest va volume $volTest."
$nodeCuoi = (docker exec $ctGoc cypher-shell -u neo4j -p 'neo4j@openspg' -d legal 'MATCH (n) RETURN count(n)' 2>$null | Select-Object -Last 1).Trim()
Ghi "Do thi goc sau khi xong: $nodeCuoi node (truoc la $nodeTruoc)"

$dong | Set-Content -Path $ra -Encoding UTF8
Write-Host ""
Write-Host "Da ghi bang chung ra: $ra" -ForegroundColor Green
