# Kiem chung sau khi nap legal.dump
#
# Chay o GOC REPO, SAU khi da nap dump:
#   .\docker\kiem-chung-do-thi.ps1
#
# Chi doc, khong ghi gi. Chay lai bao nhieu lan cung duoc.

$ErrorActionPreference = 'Stop'

$ct  = 'release-openspg-neo4j'
# Ghim digest theo HANDOFF_MANIFEST.json, khong dung tag :latest
$img = 'spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j@sha256:4bc5b7f6b83d333b1d2c8f60ac145c068d77d50bca65b3a07c927f9e2a541eb9'

# So chuan lay tu lan do that tren may dung do thi 2026-09.
# Doi so o day thi phai doi ca README.md va RESTORE-GRAPH.md.
$mongDoi = @{
    Node    = 7624
    Canh    = 26029
    Vector  = 36
    Nhan    = 10   # so nhan Legal.* , khong tinh 'Entity'
}

function Hoi($q) {
    docker exec $ct cypher-shell -u neo4j -p 'neo4j@openspg' -d legal $q 2>$null |
        Select-Object -Last 1
}

$dat = 0; $tong = 0

function Kiem($ten, $q, $mong) {
    $script:tong++
    $thuc = (Hoi $q).Trim()
    if ($thuc -eq "$mong") {
        Write-Host ("  OK   {0,-16} {1}" -f $ten, $thuc) -ForegroundColor Green
        $script:dat++
    } else {
        Write-Host ("  FAIL {0,-16} duoc {1}, mong doi {2}" -f $ten, $thuc, $mong) -ForegroundColor Red
    }
}

Write-Host "`n=== Kiem chung do thi ===" -ForegroundColor Cyan

# 1. Volume: dump co the nam o volume khac voi volume dang chay.
$raw = docker inspect $ct --format '{{json .Mounts}}' | ConvertFrom-Json
$vol = ($raw | Where-Object { $_.Destination -eq '/data' }).Name
Write-Host "  Volume /data     : $vol"

# 2. Database 'legal' phai ton tai va ONLINE. Thieu no la nap sai cho.
#    Day la loi hay gap nhat: `neo4j-admin database load` bao "Done ... 100.0%"
#    nhung KHONG tu tao database. Phai chay `CREATE DATABASE legal` truoc khi nap.
$db = docker exec $ct cypher-shell -u neo4j -p 'neo4j@openspg' `
        "SHOW DATABASES YIELD name, currentStatus WHERE name = 'legal' RETURN currentStatus" 2>$null |
        Select-Object -Last 1
$tong++
if ($db -and $db.Trim() -eq '"online"') {
    Write-Host "  OK   database legal  online" -ForegroundColor Green; $dat++
} else {
    Write-Host "  FAIL database legal  KHONG TON TAI" -ForegroundColor Red
    Write-Host "       -> Da nap dump nhung chua tao database. Chay:" -ForegroundColor Red
    Write-Host "          docker start $ct" -ForegroundColor Red
    Write-Host "          docker exec $ct cypher-shell -u neo4j -p 'neo4j@openspg' `"CREATE DATABASE legal`"" -ForegroundColor Red
    Write-Host "          roi nap lai dump. Xem docker\RESTORE-GRAPH.md." -ForegroundColor Red
}

# 3. Cac chi so noi dung.
Kiem 'node'  'MATCH (n) RETURN count(n)'                                   $mongDoi.Node
Kiem 'canh'  'MATCH ()-[r]->() RETURN count(r)'                            $mongDoi.Canh
Kiem 'vector' 'SHOW INDEXES YIELD type WHERE type = ''VECTOR'' RETURN count(*)' $mongDoi.Vector
Kiem 'nhan'  'MATCH (n) UNWIND labels(n) AS l WITH DISTINCT l WHERE l STARTS WITH ''Legal.'' RETURN count(l)' $mongDoi.Nhan

# 4. Vector index phai ONLINE. Index OFFLINE thi eval chay nhung tra loi sai
#    am tham - khong bao loi, chi tra ve ket qua vo nghia.
$off = docker exec $ct cypher-shell -u neo4j -p 'neo4j@openspg' -d legal `
        "SHOW INDEXES YIELD state WHERE state <> 'ONLINE' RETURN count(*)" 2>$null |
        Select-Object -Last 1
$tong++
if ($off.Trim() -eq '0') {
    Write-Host "  OK   index         tat ca ONLINE" -ForegroundColor Green; $dat++
} else {
    Write-Host "  FAIL index         $off index chua ONLINE" -ForegroundColor Red
    Write-Host "       -> Cho Neo4j khoi dong xong vai phut roi chay lai." -ForegroundColor Red
}

# 5. Chunk phai tra cuu duoc - day la thu eval thuc su dung.
#    Nhan co dau cham phai boc backtick, khong thi Cypher hieu la truy cap thuoc tinh.
$chunk = (Hoi 'MATCH (c:`Legal.Chunk`) RETURN count(c)').Trim()
$tong++
if ($chunk -eq '1121') {
    Write-Host "  OK   Legal.Chunk    1121" -ForegroundColor Green; $dat++
} else {
    Write-Host "  FAIL Legal.Chunk    $chunk, mong doi 1121" -ForegroundColor Red
}

Write-Host ""
Write-Host ("Ket qua: {0}/{1} OK" -f $dat, $tong) -ForegroundColor $(if ($dat -eq $tong) { 'Green' } else { 'Red' })

if ($dat -eq $tong) {
    Write-Host "`nDo thi san sang. Chay tiep:" -ForegroundColor Green
    Write-Host "  cd kag\solver"
    Write-Host "  ..\..\.venv\Scripts\python.exe eval.py"
} else {
    Write-Host "`nChua dat. Xem lai phan 'Ben nhan' trong docker\RESTORE-GRAPH.md." -ForegroundColor Yellow
    exit 1
}
