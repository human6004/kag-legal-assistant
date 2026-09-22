# Restore graph FINAL tu dist/legalfinalcand.dump vao mot may khac.
#
# Chay o GOC REPO, sau khi da:
#   1. docker compose -f docker/docker-compose-west.yml up -d   (va doi container healthy)
#   2. copy kag/kag_config.example.yaml -> kag/kag_config.yaml va dien api_key/base_url
#   3. dat dist/legalfinalcand.dump (+ .sha256)
#
#   .\docker\restore-final-graph.ps1
#
# Script lam DUNG HAI viec, theo thu tu da test that:
#
#   BUOC 1 (metadata OpenSPG): dam bao co project namespace=LegalFinalCand.
#           Neo4j dump KHONG chua project metadata - project nam trong MySQL cua
#           OpenSPG. Neu thieu buoc nay, dump co nap xong thi solver van khong thay
#           graph, vi OpenSPG khong biet database nao thuoc project nao.
#
#   BUOC 2 (noi dung Neo4j): nap store bang neo4j-admin database load.
#
# Diem quan trong nhat ve anh xa project -> database:
#
#   OpenSPG KHONG doc `graph_store.database` trong config de quyet dinh database.
#   No lay `database = lowercase(namespace)` va TU TAO database rong khi tao project.
#   Da kiem chung bang thuc nghiem: tao project namespace `ZZProbeIso` voi
#   graph_store.database=`zzprobe_iso` -> OpenSPG tao database `zzprobeiso`. Vi vay
#   namespace `LegalFinalCand` LUON ung voi database `legalfinalcand`, bat ke may nao.
#   Do la ly do namespace duoc co dinh trong script nay con project id thi khong.
#
# Script KHONG chay builder, KHONG chay indexer, KHONG goi LLM extraction,
# KHONG embedding lai graph. No chi tao metadata project + chep store.
#
# ---------------------------------------------------------------------------
# VI SAO SCRIPT NAY DUNG FILE TAM, KHONG CO CONFIG/SCHEMA RIENG TRONG REPO
# ---------------------------------------------------------------------------
#
# Nguon DUY NHAT cua config la `kag/kag_config.example.yaml`; nguon DUY NHAT cua
# schema la `kag/schema/Legal.schema`. Script khong giu ban sao thu hai cua chung.
#
# Nhung `knext` doi hoi hai thu ma hai file nguon do khong co:
#
#   (a) NAMESPACE. Example config tro namespace `Legal` (project production). Tao
#       project bang file do se ghi vao namespace SAI.
#
#   (b) vectorize_model.name + provider. `knext project create` goi THAT vao
#       endpoint embedding (VectorizeModelConfigChecker -> vectorize("hello")) va
#       doc `name`/`provider` tu config. Thieu hai truong do thi project create
#       khong chay duoc. Example config khong khai chung.
#
# Nen script sinh HAI file tam trong %TEMP% cho moi lan chay:
#
#   %TEMP%\restore-final-graph-<guid>\LegalFinalCand.schema
#       = kag/schema/Legal.schema, chi doi dong `namespace`
#
#   %TEMP%\restore-final-graph-<guid>\kag_config.yaml
#       = kag/kag_config.yaml, chi doi namespace + them name/provider
#
# Khong file nao nam trong repo, nen khong co schema duplicate / config template
# thu hai de lech khoi ban goc. Sua ban goc thi lan restore sau tu dong an theo.
# Ca thu muc tam bi xoa trong finally.
#
# ---------------------------------------------------------------------------
# CANH BAO VE `knext project create` - da kiem chung bang thuc nghiem
# ---------------------------------------------------------------------------
#
#   Lenh do KHONG chi tao project. No con SCAFFOLD mot thu muc project demo day du
#   (schema/, builder/, solver/, ...) va ghi schema MAC DINH (Person, Organization,
#   Date, Event...) vao project cua ban. Schema mac dinh do KHONG phai schema phap ly
#   cua graph nay.
#
#   Vi vay thu tu bat buoc:
#     (1) knext project create   -> tao project + database rong (schema con sai)
#     (2) doc lai project id THUC TE ma may nay cap (id khong lien tuc, khong doan)
#     (3) knext schema commit    -> ghi de schema MAC DINH bang schema phap ly that
#   Buoc (3) la buoc quyet dinh. Bo no la solver chay tren ontology sai.
#
#   commit_schema() doc: env.project_path / "schema" / "<namespace>.schema", voi
#   env.project_path = thu muc chua file config ma _closest_config() tim thay - va
#   no di TU CWD NGUOC LEN, uu tien 'kag_config.yaml'.
#
#   Da kiem chung: chay `knext schema commit` tu mot CWD ma phia tren no con mot
#   thu muc scaffold chua kag_config.yaml -> _closest_config() bat nham file do,
#   doc schema MAC DINH, va bao "project namespace is not defined".
#
#   Cach lam dung (script nay lam): commit voi CWD = thu muc tam, la noi duy nhat
#   chua kag_config.yaml + schema/<ns>.schema cua ta. Khong co thu muc scaffold nao
#   trong cay do, nen khong the bat nham.
#
# File nay co tinh giu thuan ASCII (xem giai thich o xuat-final-graph.ps1).

[CmdletBinding()]
param(
    # Duong dan dump. Mac dinh dist/legalfinalcand.dump
    [string] $DumpPath,

    # Duong dan file checksum. Mac dinh <dump>.sha256
    [string] $Sha256Path,

    # Ghi de database da co du lieu KHAC. DAY LA HANH DONG PHA HUY.
    # Mac dinh KHONG bat: neu database da co du lieu khac fingerprint final, script DUNG.
    [switch] $ForceReplace,

    # Bo qua buoc tao project OpenSPG (chi nap Neo4j store).
    # Chi dung khi ban da chac project LegalFinalCand da ton tai dung.
    [switch] $SkipProject,

    # Bo qua verify fingerprint sau khi load.
    [switch] $SkipVerify,

    # Ten container Neo4j. Mac dinh container cua compose.
    [string] $Neo4jContainer = 'release-openspg-neo4j',

    # Namespace cua project. CO DINH la LegalFinalCand cho ban giao that.
    # Chi doi khi test cach ly - doi namespace la doi sang graph khac VA doi ca
    # schema tam lan database Neo4j.
    [string] $Namespace = 'LegalFinalCand'
)

$ErrorActionPreference = 'Stop'

$goc = Split-Path -Parent $PSScriptRoot

if (-not $DumpPath)   { $DumpPath   = Join-Path $goc 'dist\legalfinalcand.dump' }
if (-not $Sha256Path) { $Sha256Path = "$DumpPath.sha256" }

# Hai file nguon DUY NHAT. Khong co ban sao nao khac trong repo.
$schemaGoc = Join-Path $goc 'kag\schema\Legal.schema'
$cfgGoc    = Join-Path $goc 'kag\kag_config.yaml'
$cfgMau    = Join-Path $goc 'kag\kag_config.example.yaml'

$img = 'spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j@sha256:4bc5b7f6b83d333b1d2c8f60ac145c068d77d50bca65b3a07c927f9e2a541eb9'
$ct  = $Neo4jContainer
$ns  = $Namespace
# OpenSPG lay database = lowercase(namespace). Khong phai lua chon cua nguoi restore.
$db  = $ns.ToLower()

$mongNode = 15888
$mongRel  = 32655
$mongChunk = 1795

function Buoc($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function OK($t)   { Write-Host "  [OK] $t" -ForegroundColor Green }
function CanhBao($t) { Write-Host "  [!] $t" -ForegroundColor Yellow }

# Chay Cypher read-only va tra ve dong cuoi cung da Trim, hoac $null neu khong co
# ket qua. Tranh loi "You cannot call a method on a null-valued expression" khi
# database chua ton tai / cypher-shell tra ve rong.
function ChayCypher {
    param([string] $Container, [string] $Database, [string] $Query)
    $r = docker exec $Container cypher-shell -u neo4j -p 'neo4j@openspg' `
           -d $Database --format plain $Query 2>$null | Select-Object -Last 1
    if ($null -eq $r) { return $null }
    return "$r".Trim()
}

# Doc project id cua mot namespace. Tra ve $null neu khong co.
function LayProjectId {
    param([string] $Namespace)
    $r = docker exec release-openspg-mysql mysql -uroot -popenspg -N -B `
           -e "SELECT id FROM openspg.kg_project_info WHERE namespace='$Namespace' AND status='VALID';" 2>$null |
           Where-Object { $_ -notmatch 'Warning' } | Select-Object -First 1
    if ($null -eq $r) { return $null }
    return "$r".Trim()
}

# Chay mot lenh native (docker/neo4j-admin) ma khong de stderr cua no lam script
# dung giua chung. Voi $ErrorActionPreference='Stop', PowerShell 5.1 bien bat ky
# dong nao tren stderr thanh loi terminating - ma `docker run` in tien do
# ("Files: 3745/3745 ...", "Done: ...") ra stderr. Ket qua la script chet o buoc
# load/dump du lenh thuc ra thanh cong.
#
# Phai ha $ErrorActionPreference xuong 'Continue' BEN TRONG scope cua ham nay;
# chi bat 2>&1 la khong du. Tra ve exit code that de ben goi tu quyet dinh.
function ChayNative {
    param([scriptblock] $Lenh)
    $cu = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $Lenh 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $cu
    }
    return @{ Code = $code; Out = $out }
}

# In ket qua cua ChayNative. `locTienDo` bo cac dong tien do kieu
# "Files: 3745/3745, data: 100.0%" ma neo4j-admin in ra hang nghin dong - giu lai
# chi nhung dong that su noi dieu gi (Done:, WARN, ERROR, ket qua lenh).
function InKetQua {
    param($KetQua, [switch] $LocTienDo)
    foreach ($d in $KetQua.Out) {
        $s = "$d"
        if ($LocTienDo -and $s -match '^\s*Files:\s*\d+/\d+') { continue }
        # PowerShell boc stderr cua lenh native thanh ErrorRecord; khi noi chuoi no ra
        # thanh ten type vo nghia ("System.Management.Automation.RemoteException").
        # Dong do khong mang thong tin gi -> bo.
        if ($s -match '^System\.Management\.Automation\.RemoteException$') { continue }
        Write-Host "     $s"
    }
}

# Doi ten namespace trong schema, CHI o dong khai bao `namespace`.
#
# KHONG duoc dung .Replace() tren toan file: chuoi 'Legal' con nam trong TEN
# ENTITY va dich relation (LegalDocument, LegalTerm, ...). Thay bua se bien
# `LegalDocument` thanh `LegalFinalCandDocument` va lam vo moi relation tro toi no
# - da do duoc bang thuc nghiem: 8 relation + 2 entity bi doi ten sai.
#
# Dung regex co neo ^...$ nen chi dung mot dong khai bao bi cham.
function DoiNamespaceSchema {
    param([string] $DuongDan, [string] $TenMoi)
    $txt = [System.IO.File]::ReadAllText($DuongDan)
    $m = [regex]::Matches($txt, '(?m)^(\s*namespace\s+)(\S+)(\s*)$')
    if ($m.Count -ne 1) {
        throw "Mong doi dung 1 dong 'namespace' trong '$DuongDan', thay $($m.Count)."
    }
    $txt = [regex]::Replace($txt, '(?m)^(\s*namespace\s+)(\S+)(\s*)$', "`${1}$TenMoi`${3}")
    [System.IO.File]::WriteAllText($DuongDan, $txt, (New-Object System.Text.UTF8Encoding($false)))
    return $m[0].Groups[2].Value
}

# --- 0. Tien de --------------------------------------------------------------
Buoc '0. Kiem tra tien de'

if (-not (Test-Path $DumpPath)) {
    throw "Khong thay dump '$DumpPath'. Xem docs/RESTORE-FINAL-GRAPH.md muc D (tai dump)."
}
$dumpSize = (Get-Item $DumpPath).Length
if ($dumpSize -le 0) { throw "Dump '$DumpPath' rong." }
Write-Host ("Dump    : {0} ({1:N2} MB)" -f $DumpPath, ($dumpSize / 1MB))

if (-not (docker ps -a --filter "name=^/$ct$" --format '{{.Names}}')) {
    throw "Khong thay container '$ct'. Chay truoc: docker compose -f docker/docker-compose-west.yml up -d"
}

# Tim volume THUC SU dang chua /data - khong doan theo ten.
$raw = docker inspect $ct --format '{{json .Mounts}}' | ConvertFrom-Json
$vol = ($raw | Where-Object { $_.Destination -eq '/data' }).Name
if (-not $vol) { throw "Container '$ct' khong gan volume nao vao /data." }
Write-Host "Volume  : $vol"

# --- 1. Verify SHA256 --------------------------------------------------------
Buoc '1. Verify SHA256'

if (Test-Path $Sha256Path) {
    $line = (Get-Content $Sha256Path -Raw).Trim()
    # Ho tro ca "<hash>" va "<hash>  <ten file>" (dinh dang sha256sum).
    $mongHash = ($line -split '\s+')[0].ToLower()
    if ($mongHash -notmatch '^[0-9a-f]{64}$') {
        throw "File checksum '$Sha256Path' khong chua SHA256 hop le: '$line'"
    }
    Write-Host "  mong doi : $mongHash"
    Write-Host "  dang tinh: (co the mat vai chuc giay voi file ~1.3 GB)"
    $thucTe = (Get-FileHash -Path $DumpPath -Algorithm SHA256).Hash.ToLower()
    Write-Host "  thuc te  : $thucTe"
    if ($thucTe -ne $mongHash) {
        throw "SHA256 KHONG KHOP. Dump hong hoac bi thay doi khi truyen. DUNG restore, tai lai dump."
    }
    OK 'Checksum khop.'
} else {
    CanhBao "Khong thay '$Sha256Path' -> BO QUA verify checksum."
    CanhBao 'Van nen xin file .sha256 tu nguoi gui dump de verify.'
}

# --- 2. Trang thai database hien tai (truoc khi dong cham gi) ----------------
Buoc "2. Trang thai database '$db' hien tai"

# Database co the chua ton tai -> cypher-shell tra loi. Coi la "trong".
$dbExists = $false
try {
    $dbs = docker exec $ct cypher-shell -u neo4j -p 'neo4j@openspg' --format plain `
             'SHOW DATABASES YIELD name' 2>$null
    $dbExists = ($dbs | Where-Object { $_.Trim() -eq "`"$db`"" }) -ne $null
} catch { $dbExists = $false }

$daRestore = $false

if ($dbExists) {
    $curN = ChayCypher -Container $ct -Database $db -Query 'MATCH (n) RETURN count(n)'
    $curR = ChayCypher -Container $ct -Database $db -Query 'MATCH ()-[x]->() RETURN count(x)'
    Write-Host "  da ton tai: nodes=$curN relations=$curR"

    if ($curN -eq "$mongNode" -and $curR -eq "$mongRel") {
        Write-Host ''
        Write-Host '  ALREADY RESTORED - database da dung fingerprint final.' -ForegroundColor Green
        Write-Host '  Khong lam gi them. Bo qua nap lai.' -ForegroundColor Green
        $daRestore = $true
    } elseif ($curN -eq '0' -and $curR -eq '0') {
        Write-Host '  ton tai nhung rong -> se nap de len.' -ForegroundColor Yellow
    } elseif ($ForceReplace) {
        Write-Host ''
        Write-Host '  [!] -ForceReplace: SE GHI DE database dang co du lieu KHAC.' -ForegroundColor Red
        Write-Host "  [!] Du lieu hien tai (nodes=$curN relations=$curR) se MAT VINH VIEN." -ForegroundColor Red
    } else {
        Write-Host ''
        Write-Host "  DUNG: database '$db' da co du lieu KHAC fingerprint final:" -ForegroundColor Red
        Write-Host "      hien tai  : nodes=$curN relations=$curR" -ForegroundColor Red
        Write-Host "      mong doi  : nodes=$mongNode relations=$mongRel" -ForegroundColor Red
        Write-Host ''
        Write-Host '  Script tu choi ghi de de tranh mat du lieu. Neu chac chan muon thay the,' -ForegroundColor Yellow
        Write-Host '  chay lai voi -ForceReplace (PHA HUY, khong the hoan tac).' -ForegroundColor Yellow
        throw "Database '$db' da co du lieu khac. Dung lai."
    }
} else {
    Write-Host '  chua ton tai.'
}

# --- 3. BUOC 1: metadata OpenSPG (project + schema) --------------------------
# Thu muc tam chi tao khi thuc su can, va LUON duoc xoa trong finally.
$tamDir = $null

if (-not $daRestore -and -not $SkipProject) {
    Buoc "3. BUOC 1 - OpenSPG project/schema (metadata, KHONG nam trong Neo4j dump)"
    Write-Host "  namespace = $ns"
    Write-Host "  database  = $db  (= lowercase(namespace), OpenSPG tu quyet dinh)"

    # --- 3a. Chon config nguon ------------------------------------------------
    # kag/kag_config.yaml (ban nguoi dung da dien key) la dung nhat - no cung la
    # file solver dung sau nay, nen namespace/endpoint khong the lech nhau.
    # Chua copy thi lay example va canh bao ro: endpoint se khong song.
    if (Test-Path $cfgGoc) {
        $cfgNguon = $cfgGoc
        Write-Host "  config nguon: kag/kag_config.yaml"
    } else {
        $cfgNguon = $cfgMau
        CanhBao 'Chua co kag/kag_config.yaml -> dung kag/kag_config.example.yaml.'
        CanhBao 'File mau khong co api_key/base_url that, nen buoc knext se that bai.'
        CanhBao 'Copy truoc: copy kag\kag_config.example.yaml kag\kag_config.yaml'
    }
    if (-not (Test-Path $cfgNguon)) { throw "Khong thay config nguon '$cfgNguon'." }
    if (-not (Test-Path $schemaGoc)) { throw "Khong thay schema nguon '$schemaGoc'." }

    # --- 3b. Sinh schema tam + config tam trong %TEMP% ------------------------
    $tamDir = Join-Path ([System.IO.Path]::GetTempPath()) ("restore-final-graph-" + [System.Guid]::NewGuid().ToString('N').Substring(0, 8))
    New-Item -ItemType Directory -Path $tamDir -Force | Out-Null

    # Schema tam = Legal.schema voi dung dong namespace doi. Day la transform DUY
    # NHAT duoc phep: ban goc va ban namespace hoa chi khac nhau mot dong (da doi
    # chieu bang diff). Neu ban goc doi cau truc, ban tam an theo ngay.
    $tamSchemaDir = Join-Path $tamDir 'schema'
    New-Item -ItemType Directory -Path $tamSchemaDir -Force | Out-Null
    $tamSchema = Join-Path $tamSchemaDir "$ns.schema"

    Copy-Item -Path $schemaGoc -Destination $tamSchema -Force
    # Chi doi dong khai bao namespace; ten entity/relation giu nguyen.
    $dongNsGoc = DoiNamespaceSchema -DuongDan $tamSchema -TenMoi $ns
    Write-Host "  schema tam : $tamSchema  (namespace $dongNsGoc -> $ns)"

    # Config tam = config nguon voi namespace doi + name/provider cho vectorizer.
    #
    # Cung ly do nhu schema: doi namespace bang regex neo dong, KHONG .Replace()
    # toan file - chuoi 'Legal' con nam trong biz_scene (`legal` viet thuong nen
    # khong dinh) va trong duong dan/ghi chu khac.
    #
    # Xoa khoa `name:`/`provider:` cu (neu co) truoc khi chen, de khong thanh YAML
    # trung khoa khi nguoi dung da tu them.
    $tamCfg = Join-Path $tamDir 'kag_config.yaml'
    Copy-Item -Path $cfgNguon -Destination $tamCfg -Force

    $txt = [System.IO.File]::ReadAllText($tamCfg)
    $mNs = [regex]::Matches($txt, '(?m)^(\s*namespace:\s*)(\S+)(\s*)$')
    if ($mNs.Count -ne 1) {
        throw "Mong doi dung 1 dong 'namespace:' trong '$tamCfg', thay $($mNs.Count)."
    }
    $dongNsCfg = $mNs[0].Groups[2].Value
    $txt = [regex]::Replace($txt, '(?m)^(\s*namespace:\s*)(\S+)(\s*)$', "`${1}$ns`${3}")
    $txt = [regex]::Replace($txt, '(?m)^\s*(name|provider):.*\r?\n', '')
    $txt = [regex]::Replace($txt, '(?m)^(vectorize_model: &vectorize_model\r?\n)', "`$1  name: restore_vectorizer`r`n  provider: OpenAI`r`n")
    [System.IO.File]::WriteAllText($tamCfg, $txt, (New-Object System.Text.UTF8Encoding($false)))

    $soName = (Select-String -Path $tamCfg -Pattern '^\s*name:\s*restore_vectorizer\s*$').Count
    if ($soName -ne 1) { throw "Khong chen duoc 'name: restore_vectorizer' vao config tam (thay $soName lan)." }
    Write-Host "  config tam : $tamCfg  (namespace $dongNsCfg -> $ns, + name/provider)"

    if ($ns -eq 'Legal') {
        CanhBao 'Namespace = Legal: day la project PRODUCTION. Chi dung khi ban y thuc ro.'
    }

    $knext = Join-Path $goc '.venv\Scripts\knext.exe'
    if (-not (Test-Path $knext)) {
        throw "Khong thay '$knext'. Tao venv + pip install -r requirements.txt truoc."
    }

    # --- 3c. (1) Tao project neu chua co --------------------------------------
    if (LayProjectId -Namespace $ns) {
        Write-Host "  project '$ns' da ton tai tren server -> bo qua buoc tao."
    } else {
        Write-Host '  -> knext project create'
        Write-Host '     (Luu y: lenh nay goi THAT vao LLM + embedding de kiem tra config,'
        Write-Host '      va scaffold mot schema MAC DINH. Schema dung se commit o buoc sau.)'
        $env:PYTHONIOENCODING = 'utf-8'
        Push-Location $tamDir
        try {
            $kq = ChayNative { & $knext project create --config_path $tamCfg }
            InKetQua $kq
            if ($kq.Code -ne 0) {
                throw ("knext project create that bai (exit $($kq.Code)). Thuong gap: chua dien " +
                       "api_key, hoac endpoint LLM/embedding khong song. " +
                       "Xem docs/RESTORE-FINAL-GRAPH.md muc E.")
            }
        } finally {
            Pop-Location
        }
    }

    # --- 3d. (2) Doc lai project id THUC TE - khong bao gio hardcode ----------
    $projId = LayProjectId -Namespace $ns
    if (-not $projId) {
        throw ("Khong doc duoc project id cho namespace '$ns' sau khi tao. " +
               "Kiem tra lai buoc 'knext project create' o tren.")
    }
    Write-Host ''
    OK "Project '$ns' co id = $projId  (id nay KHAC may nguon, do la binh thuong)"

    # Ghi id THUC TE vao config tam TRUOC khi commit. Neu buoc scaffold khong chay
    # (project da ton tai tu truoc), config tam van con id cu chep tu example
    # (vi du "1" cua project production) - commit voi id do la ghi schema vao SAI
    # project. Sua o day mot lan cho ca hai nhanh.
    $txt = [System.IO.File]::ReadAllText($tamCfg)
    $txt = [regex]::Replace($txt, '(?m)^(  id:\s*).*$', "`${1}'$projId'")
    [System.IO.File]::WriteAllText($tamCfg, $txt, (New-Object System.Text.UTF8Encoding($false)))

    $idTrongCfg = (Select-String -Path $tamCfg -Pattern "(?m)^\s*id:\s*'?(\d+)'?\s*$" |
                     Select-Object -First 1).Matches.Groups[1].Value
    if ("$idTrongCfg" -ne "$projId") {
        throw "project.id trong config tam ($idTrongCfg) khac id thuc te ($projId). Dung lai."
    }

    # --- 3e. (3) Commit schema PHAP LY that -----------------------------------
    # `knext project create` vua scaffold mot thu muc project demo NGAY TRONG CWD
    # (tuc trong $tamDir) va ghi vao do schema MAC DINH + kag_config.yaml.
    # commit_schema() se doc chinh file config do, va id trong do la id vua duoc cap.
    #
    # Nen: ghi schema cua ta DE len schema mac dinh trong thu muc scaffold, roi
    # commit TAI thu muc scaffold do. CWD = thu muc scaffold la dung nhat, vi
    # _closest_config() di tu CWD nguoc len va se gap dung kag_config.yaml nay
    # truoc moi file khac.
    $scaffoldDir = Join-Path $tamDir $ns

    if (Test-Path $scaffoldDir) {
        $dstSchema = Join-Path $scaffoldDir "schema\$ns.schema"
        if (-not (Test-Path (Split-Path -Parent $dstSchema))) {
            New-Item -ItemType Directory -Path (Split-Path -Parent $dstSchema) -Force | Out-Null
        }
        Copy-Item -Path $tamSchema -Destination $dstSchema -Force
        Write-Host "  -> ghi schema phap ly de len schema mac dinh: $dstSchema"

        # Dong bo project.id trong config scaffold voi id THUC TE (phong khi lech).
        $cfgScaffold = Join-Path $scaffoldDir 'kag_config.yaml'
        if (Test-Path $cfgScaffold) {
            $txt = [System.IO.File]::ReadAllText($cfgScaffold)
            $txt = [regex]::Replace($txt, "(?m)^(  id:\s*).*$", "`${1}'$projId'")
            [System.IO.File]::WriteAllText($cfgScaffold, $txt, (New-Object System.Text.UTF8Encoding($false)))
        }

        $cwdCommit = $scaffoldDir
    } else {
        # Du phong: project da ton tai tu truoc nen khong co thu muc scaffold.
        # Commit tu $tamDir - noi chi co kag_config.yaml + schema cua ta.
        $txt = [System.IO.File]::ReadAllText($tamCfg)
        $txt = [regex]::Replace($txt, '(?m)^(  id:\s*).*$', "`${1}'$projId'")
        [System.IO.File]::WriteAllText($tamCfg, $txt, (New-Object System.Text.UTF8Encoding($false)))
        $cwdCommit = $tamDir
    }

    Write-Host "  -> knext schema commit (CWD=$cwdCommit, namespace=$ns, id=$projId)"
    $env:PYTHONIOENCODING = 'utf-8'
    Push-Location $cwdCommit
    try {
        $kq = ChayNative { & $knext schema commit }
        InKetQua $kq
        if ($kq.Code -ne 0) { throw "knext schema commit that bai (exit $($kq.Code))." }
    } finally {
        Pop-Location
    }

    # Verify schema that su len server: dem so type cua project.
    $soTypeRaw = docker exec release-openspg-mysql mysql -uroot -popenspg -N -B `
                   -e "SELECT COUNT(*) FROM openspg.kg_project_entity WHERE project_id=$projId;" 2>$null |
                   Where-Object { $_ -notmatch 'Warning' } | Select-Object -First 1
    $soType = if ($null -eq $soTypeRaw) { '' } else { "$soTypeRaw".Trim() }
    Write-Host "  so type trong schema cua project: $soType"
    if ($soType -match '^\d+$' -and [int]$soType -lt 15) {
        throw ("Schema tren server chi co $soType type, mong doi >= 15. " +
               "Nhieu kha nang da commit nham schema mac dinh. Kiem tra lai.")
    }
    OK "Schema da commit cho project id = $projId"

    Write-Host ''
    Write-Host "  -> Dat project.id trong kag/kag_config.yaml = $projId" -ForegroundColor Yellow
    Write-Host "     namespace = $ns ; dien api_key cua BAN." -ForegroundColor Yellow
}

if ($daRestore) {
    if ($SkipVerify) { return }
    # nhay thang xuong phan verify
} else {

# --- 4. BUOC 2: nap Neo4j store ---------------------------------------------
Buoc "4. BUOC 2 - nap Neo4j store tu dump"

# THU TU BAT BUOC, da test that (khong phai suy doan):
#
#   (a) neo4j-admin database load  -> chep store xuong dia
#   (b) CREATE DATABASE            -> dang ky database vao system catalog
#
# Ly do phai lam (b) SAU (a), va khong the bo (b):
#   `database load` chi ghi thu muc store vao /data/databases/<db>. No KHONG
#   dang ky database vao system catalog. Da kiem chung: sau khi load xong,
#   `SHOW DATABASES` van chi co neo4j + system, restart container cung vay.
#   Database chi xuat hien sau khi chay `CREATE DATABASE`.
#
#   Va (b) phai lam SAU (a) chu khong phai truoc: neu CREATE DATABASE chay truoc,
#   Neo4j tao mot store RONG, roi load de len van duoc nhung do la duong vong. Lam
#   (a) roi (b) thi Neo4j nhan dung store da co san tren dia
#   (da verify: 15888 nodes / 32655 relations hien ra ngay sau CREATE).
#
# Ca hai deu phai lam khi container DANG DUNG:
#   "It is not possible to replace a database that is mounted in a running
#    Neo4j server."
# Nen stop container, lam ca hai buoc offline, roi start lai trong finally.

$dumpDir = Split-Path -Parent $DumpPath
$dumpDirDocker = $dumpDir -replace '\\', '/'

# Neu database da duoc DANG KY trong catalog (truong hop -ForceReplace, hoac
# database rong co san), phai DROP truoc khi load. `database load` tu choi khi
# store dang duoc mot database chiem:
#   "Failed to load database 'x': The database is in use."
# DROP phai chay khi server con song, nen lam truoc khi stop.
if ($dbExists) {
    Write-Host "  go dang ky database '$db' trong catalog truoc khi load lai"
    $kq = ChayNative {
        docker exec $ct cypher-shell -u neo4j -p 'neo4j@openspg' "DROP DATABASE $db;"
    }
    InKetQua $kq
    if ($kq.Code -ne 0) { throw "DROP DATABASE $db that bai (exit $($kq.Code))." }
    # Cho store duoc giai phong han
    Start-Sleep -Seconds 10
}

docker stop $ct | Out-Null
try {
    Write-Host "  da stop $ct"

    Write-Host '  (a) neo4j-admin database load'
    $kq = ChayNative {
        docker run --rm `
            -v "${dumpDirDocker}:/dump" `
            -v "${vol}:/data" `
            $img `
            neo4j-admin database load $db --from-path=/dump --overwrite-destination=true
    }
    InKetQua $kq -LocTienDo
    if ($kq.Code -ne 0) { throw "neo4j-admin database load that bai (exit $($kq.Code))" }

    Write-Host '  (b) start tam de dang ky database vao system catalog'
    docker start $ct | Out-Null

    # Cho Neo4j len truoc khi CREATE DATABASE
    $up = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 3
        try {
            $s = docker exec $ct cypher-shell -u neo4j -p 'neo4j@openspg' --format plain `
                   'SHOW DATABASES YIELD name' 2>$null
            if ($s -match 'system') { $up = $true; break }
        } catch { }
    }
    if (-not $up) { throw "Neo4j khong len sau khi load (cho 180s)." }

    $dbs = docker exec $ct cypher-shell -u neo4j -p 'neo4j@openspg' --format plain `
             'SHOW DATABASES YIELD name' 2>$null
    if ($dbs | Where-Object { $_.Trim() -eq "`"$db`"" }) {
        Write-Host "  database '$db' da duoc dang ky tu truoc."
    } else {
        $kq = ChayNative {
            docker exec $ct cypher-shell -u neo4j -p 'neo4j@openspg' "CREATE DATABASE $db;"
        }
        InKetQua $kq
        if ($kq.Code -ne 0) { throw "CREATE DATABASE $db that bai (exit $($kq.Code))." }
    }
} finally {
    # Bat lai du thanh cong hay loi - khong de nguoi dung quen.
    if (-not (docker ps --filter "name=^/$ct$" --format '{{.Names}}')) {
        docker start $ct | Out-Null
    }
    Write-Host "  da dam bao $ct dang chay"
}

# Cho database online
Write-Host '  doi database online...'
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 3
    try {
        $s = docker exec $ct cypher-shell -u neo4j -p 'neo4j@openspg' --format plain `
               "SHOW DATABASES YIELD name, currentStatus WHERE name='$db'" 2>$null
        if ($s -match 'online') { $ready = $true; break }
    } catch { }
}
if (-not $ready) { throw "Database '$db' khong tro lai online sau khi load (cho 180s)." }
OK "Database '$db' online."

}  # het nhanh nap store

# --- 5. Verify ---------------------------------------------------------------
if ($SkipVerify) {
    CanhBao '-SkipVerify: bo qua verify fingerprint.'
    return
}

Buoc '5. Verify fingerprint sau restore'

# Label day du la "<namespace>.<Ten>" - vi du LegalFinalCand.Chunk. Dau cham la ky tu
# dac biet trong Cypher nen PHAI boc trong backtick.
#
# Dung chuoi PowerShell single-quoted roi ghep bang -f: trong chuoi single-quoted,
# backtick la ky tu thuong (khong phai escape char), nen backtick di nguyen ven sang
# Cypher. Chuoi double-quoted thi PowerShell an backtick va de lai label sai.
$qChunk  = 'MATCH (n:`{0}`) RETURN count(n)' -f "$ns.Chunk"
$qVecDim = 'MATCH (n:`{0}`) WHERE n._content_vector IS NOT NULL RETURN size(n._content_vector) LIMIT 1' -f "$ns.Chunk"

$n = ChayCypher -Container $ct -Database $db -Query 'MATCH (n) RETURN count(n)'
$r = ChayCypher -Container $ct -Database $db -Query 'MATCH ()-[x]->() RETURN count(x)'
$c = ChayCypher -Container $ct -Database $db -Query $qChunk

Write-Host "  nodes     = $n   (mong doi $mongNode)"
Write-Host "  relations = $r   (mong doi $mongRel)"
Write-Host "  chunks    = $c   (mong doi $mongChunk)"

$loi = @()
if ($n -ne "$mongNode")    { $loi += "nodes $n != $mongNode" }
if ($r -ne "$mongRel")     { $loi += "relations $r != $mongRel" }
if ($c -ne "$mongChunk")   { $loi += "chunks $c != $mongChunk" }

# Vector dimension: phai la 3072, neu khong retrieval vo.
# Ten property that la `_content_vector`, KHONG phai `content_vector`
# (da kiem chung bang keys(n) tren graph nguon).
$dim = ChayCypher -Container $ct -Database $db -Query $qVecDim
Write-Host "  vector dim= $dim   (mong doi 3072)"
if ($dim -ne '3072') { $loi += "vector dim $dim != 3072" }

if ($loi.Count -gt 0) {
    Write-Host ''
    Write-Host '  VERIFY THAT BAI:' -ForegroundColor Red
    $loi | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
    throw 'Restore khong dat fingerprint final.'
}

Write-Host ''
Write-Host 'RESTORE THANH CONG - fingerprint khop graph final candidate.' -ForegroundColor Green
Write-Host ''
Write-Host 'Buoc tiep theo:'
Write-Host "  1. Dat project.id trong kag/kag_config.yaml = id thuc te cua project '$ns'"
Write-Host "  2. namespace = $ns"
Write-Host '  3. Dien api_key cua BAN (LLM + embedding)'
Write-Host "  4. Verify day du: xem docs/RESTORE-FINAL-GRAPH.md muc G"
