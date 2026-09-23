# HANDOFF — KAG Legal Assistant, Final Candidate Graph

Trạng thái: **HANDOFF PACKAGE READY**
Ngày đóng gói: 2026-09-21
Tài liệu này KHÔNG chứa secret. Mọi API key được ghi dưới dạng placeholder.

---

## 1. HEAD hiện tại

```text
branch        = master
working tree  = clean
đồng bộ       = local master == origin/master, đã push, không còn gì pending
```

Các commit được tạo SAU giai đoạn smoke test — đều là handoff / docs / cleanup, không đụng
builder, solver, schema hay graph:

```text
9c9dc65  docs: add final graph handoff
c30ab91  feat: add portable final graph export and restore
         chore: clean repository handoff artifacts   (dọn artifact local, .gitignore, doc này)
```

Trạng thái "không có commit nào được tạo" là mô tả của giai đoạn smoke test / đóng gói,
ứng với HEAD `124c8e6`. Đó là lịch sử, không còn là trạng thái hiện tại.

## 2. Final graph

```text
project id = 4
namespace  = LegalFinalCand
database   = legalfinalcand
host_addr  = http://127.0.0.1:8887   (OpenSPG server, local)
```

Neo4j backing store: container `release-openspg-neo4j`, database `legalfinalcand`.

### 2.1 Portable handoff — đã versioned, export/restore validate end-to-end

Graph final không chỉ sống trong container trên máy nguồn. Dump portable và bộ script dựng
lại đã được commit ở `c30ab91`:

```text
dist/legalfinalcand.dump           1408579140 bytes (~1.31 GiB)
dist/legalfinalcand.dump.sha256    155c1e744b650dc5ac046d42bcb64aea5ed64c1aad14e34945b3d958c02ed50f

docker/xuat-final-graph.ps1        exporter, máy nguồn
docker/restore-final-graph.ps1     restore, máy nhận
docs/RESTORE-FINAL-GRAPH.md        quy trình đầy đủ + các bẫy
```

Vòng export → truyền → restore → verify đã chạy thật, không phải suy luận trên giấy:
database dựng lại đọc ra đúng 15888 nodes / 32655 relations / `vector_dimensions 3072`,
khớp fingerprint mục 3.

`dist/` bị ignore có chủ ý — 1.31 GiB không vào git. Dump truyền tay (Drive, USB, scp) và
**phải đi kèm file `.sha256`**; thiếu nó thì máy nhận mất khả năng phát hiện dump hỏng.

Chi tiết từng bước, thứ tự nạp Neo4j bắt buộc, và lý do database luôn phải là
`legalfinalcand`: xem `docs/RESTORE-FINAL-GRAPH.md`.

## 3. Fingerprint chuẩn

Đây là fingerprint tham chiếu. Mọi lần validate lại về sau phải khớp đúng bộ số này.

```text
nodes      = 15888
relations  = 32655
chunks     = 1795
documents  = 23/23   (distinct Chunk.source_path = 23)
```

### 3.1 Count per label

```text
Entity                          15888     (nhãn gốc, phủ toàn bộ node)
LegalFinalCand.Article           1349
LegalFinalCand.Authority         1342
LegalFinalCand.Chunk             1795
LegalFinalCand.LegalDocument      336
LegalFinalCand.LegalTerm         3417
LegalFinalCand.Obligation        3861
LegalFinalCand.Others              85
LegalFinalCand.ProhibitedAct      983
LegalFinalCand.RegulatedEntity   2132
LegalFinalCand.Sanction           588
```

Lưu ý `LegalDocument = 336` trong khi `documents = 23/23`. Không mâu thuẫn: 23 là số văn bản
thực sự được ingest (đếm theo `Chunk.source_path`), còn 336 là toàn bộ node LegalDocument gồm cả
các văn bản chỉ được **tham chiếu tới** (bị sửa đổi, bị thay thế, được viện dẫn) mà không nạp nội dung.

### 3.2 Count per relation type

```text
OfficialName      206      amends            168      appliesTo         894
basedOn          3306      belongsTo        1286      boundEntity      1519
definedIn         295      defines           382      enforcedBy        254
forAct           1412      implementsDoc      30      imposes           542
obliges          2779      prohibitedBy      130      prohibits         874
sanctionedBy       84      source          18480      supersededBy        7
supersedes          7
```

Tổng 19 relation type. `OfficialName` là system predicate của OpenSPG (cạnh alias, có chủ ý) —
không phải rác camel-case, đừng xoá khi audit relation contract.

## 4. Builder status

```text
D2.1 = PASS
D2.2 = PASS
```

- **D2.1** — giá trị định lượng quy phạm không còn rơi vào `Others`. Đã verify runtime, không chỉ
  ở tầng graph: 80% (333-2026-ND-CP Điều 28), 100/200/300% (329-2026-ND-CP Điều 16), 15%
  (116-2025-QH15 Điều 38) đều lấy được từ evidence thật khi chạy solver.
- **D2.2** — `Article --belongsTo--> LegalDocument` tất định cho Điều nguồn. 1286 cạnh `belongsTo`.
  Verify runtime qua control `article:53-2022-ND-CP:26` (resolve top-1).

Builder KHÔNG bị sửa trong giai đoạn này.

## 5. Solver status

```text
solver = baseline (nguyên kag/solver/** tại HEAD trên)
D2.3   = ABSENT (đã revert ở commit 03d39bf)
```

Pipeline đang cấu hình:

```text
pipeline   = kag_static_pipeline / KAGStaticPipeline
planner    = lf_kag_static_planner
             + legal_lf_static_planning
             + legal_rewrite_sub_task_query
executors  = hybrid-retrieval, py-math, deduce, output
generator  = llm_index_generator (enable_ref: true)
retrievers = kg_cs  threshold 0.9
             kg_fr  top_k 20, threshold 0.8
             rc     top_k 20, score_threshold 0.65
```

Solver KHÔNG bị sửa trong giai đoạn này.

## 6. Smoke test

```text
8/8 FINISH
0 exception
quote compatibility = PASS
graph write         = KHÔNG (fingerprint identical trước/sau)
```

Bộ 8 câu (smoke, KHÔNG phải benchmark — bộ chuẩn hiện tại có 150 câu):

| id | loại | mục tiêu | kết quả |
|---|---|---|---|
| C1 | control D2.1 **(bắt buộc)** | 333-2026-ND-CP Điều 28 / 80% | evidence ĐÚNG |
| C2 | control D2.1 **(bắt buộc)** | 329-2026-ND-CP Điều 16 / 100%, 200%, 300% | evidence ĐÚNG |
| C3 | control belongsTo **(bắt buộc)** | article:53-2022-ND-CP:26 | ĐÚNG, top-1 |
| C4 | probe thêm | article:331-2026-ND-CP:30 + multi-hop | MISS, xem mục 7 |
| B12 | control D2.1 phụ | 116-2025-QH15 Điều 38 / 15% | evidence ĐÚNG |
| B82 | fact thời hạn | 24 giờ / Điều 10 | ĐÚNG |
| B94 | fact thời hạn | 60 ngày / Điều 19 | ĐÚNG |
| B127 | fact hiệu lực | 19/8/2026 | ĐÚNG |

Số chunk retrieve mỗi câu: 27–41. Thời gian: 50.9s – 111.6s. Tất cả `status=FINISH`.

7/8 câu lấy đúng chunk ground-truth ở top hoặc gần top. C3 phân giải được 2 node "Điều 26"
cạnh tranh (53/2022 vs 13/2023) và xếp đúng 53/2022 hạng 1.

### 6.1 Quote compatibility — PASS

Hiện tượng còn nguyên, **KHÔNG được sửa** (tồn tại cả ở graph cũ): string property Cypher bị bọc
dấu nháy kép literal.

```text
name          = "\"Điều 30. Yêu cầu chung về bảo đảm an ninh mạng theo cấp độ\""
articleNumber = "\"30\""
```

Căn cứ kết luận PASS, dựa trên trace runtime thật:

- Mọi `name` bị bọc quote y như nhau, vậy mà 7/8 câu retrieval đúng chunk → quote không phải biến
  phân biệt thành–bại.
- C3 cùng hình dạng câu hỏi với C4, cùng là control `belongsTo`, resolve top-1 và còn phân giải
  được 2 Điều trùng tên.
- Ngay ở C4 (câu miss), rewriter vẫn **đọc được** `name` bọc quote của LegalDocument để bung
  "Nghị định 331/2026/NĐ-CP" thành tên chính thức "Nghị định về bảo vệ an ninh mạng đối với hệ
  thống thông tin". Đọc được nghĩa là quote không chặn entity linking ở tầng document.
- Không có failure nào quy được về dấu quote.

## 7. Known limitation — C4 retrieval recall/ranking miss

**Đây là limitation của solver, KHÔNG phải defect của graph.**

Câu C4 hỏi nội dung `article:331-2026-ND-CP:30`. Solver trả về một lời từ chối trung thực
("Không đủ thông tin trong dữ liệu để trả lời… dữ liệu chỉ cung cấp Điều 1, Điều 28, Điều 38,
Điều 40") thay vì bịa — đúng hành vi mong đợi khi D2.3 đã revert.

### 7.1 Graph có đủ dữ liệu — đã verify

```text
chunk e192bbc0a523f03f33f6f6ae5726634febf6736cb42b925b7bf30a07ff9bc7f3
      TỒN TẠI  ("Nghị định 331/2026/NĐ-CP — … / Chương V /
                 Điều 30. Yêu cầu chung về bảo đảm an ninh mạng theo cấp độ")
article:331-2026-ND-CP:30                              TỒN TẠI
article:331-2026-ND-CP:30 --belongsTo--> nghị định 331 2026 nđ cp   CÓ
article:331-2026-ND-CP:30 --source----> chunk e192bbc0…             CÓ
```

### 7.2 Solver không retrieve được — đã verify bằng trace

```text
chunk e192bbc0…            NOT in trace
article:331-2026-ND-CP:30  NOT in trace
331/2026 có 63 chunk, solver chỉ lấy 3 (doc-level, Điều 40/Bảng 1, Điều 1)
```

Ba lần tên "Điều 30" xuất hiện trong trace đều do **planner tự sinh**
(`Deduce(op=extract, target=\`Yêu cầu chung về bảo đảm an ninh mạng theo cấp độ là gì?\`)`),
KHÔNG phải dữ liệu graph trả về. Nên KHÔNG được khẳng định entity linking đã resolve Article node
cho câu này.

### 7.3 Nguyên nhân gốc

Planner phát ra `Step2: Retrieval(s=s1, p=p2:content, o=o2)`. Predicate `content` **không phải
cạnh** trong schema — cạnh từ LegalDocument chỉ có `source / amends / OfficialName /
implementsDoc / supersedes / supersededBy`; `content` là property của Chunk. Vì vậy Step2 rơi về
chunk-retrieval vector (`rc`, top_k 20, threshold 0.65), và 1 chunk đúng trong 63 chunk của văn
bản đó không lọt top-k.

### 7.4 Hướng xử lý (ngoài phạm vi phase này — đều là sửa solver)

- Nới `rc.top_k` hoặc hạ `score_threshold`, hoặc
- Cho planner đi qua cạnh `source` từ Article thay vì hop `p:content` không tồn tại.

Không tự patch. Cần reviewer quyết riêng.

### 7.5 Ghi chú minh bạch

Lần đầu C4 báo `hit_all=True` là **false positive do expect-string quá chung**
(`["Điều 30", "an ninh mạng"]`). Đã tự phát hiện và audit lại thay vì nhận kết quả xanh. Nếu tái
sử dụng bộ smoke này, siết expect-string của C4 lại (ví dụ đòi đúng chunk id `e192bbc0`).

## 8. Production safety

Ba graph production không bị chạm. Fingerprint trước/sau smoke IDENTICAL:

```text
legal           7624 nodes / 26029 relations    unchanged
legalc3test        93 nodes /   245 relations    unchanged
legalfullcand   14061 nodes / 29376 relations    unchanged
legalfinalcand  15888 nodes / 32655 relations    unchanged (chính nó)
```

Count per label và count per relation type của `legalfinalcand` cũng identical (11 label,
19 relation type).

Bảo đảm ở tầng code: grep `vendor/KAG/kag/solver/` tìm `upsert|write_graph|MERGE|CREATE|DELETE|
SET|.commit(` → **0 match**. `graph_api` ABC không expose method ghi, chỉ có `execute_dsl` làm
escape hatch mà pipeline đang cấu hình không bao giờ dùng để ghi. Đường đọc của solver về mặt code
không thể ghi graph.

```text
Chưa cutover production. Graph cũ chưa xoá. Config production chưa đổi.
```

## 9. Cách cấu hình runtime để trỏ solver sang project 4

### 9.1 Nguyên tắc

- **Không** ghi API key thật vào file được commit. Dùng placeholder, điền lúc chạy.
- **Chỉ** đổi đúng các field liệt kê dưới đây.
- **Không** sửa config production (`kag/kag_config.yaml`, hiện `id: '1'` / `namespace: Legal`)
  khi chưa cutover. Dùng config scratch đặt ngoài repo.

### 9.2 Field cần đổi

Chỉ duy nhất block `project:` quyết định graph nào được đọc:

```yaml
project:
  biz_scene: legal                      # giữ nguyên — quyết định prefix prompt legal_*
  host_addr: http://127.0.0.1:8887      # OpenSPG server
  id: '4'                               # ĐỔI: 1 -> 4
  language: en
  namespace: LegalFinalCand             # ĐỔI: Legal -> LegalFinalCand
```

Config **không** chứa Neo4j URI / user / database. Database được chọn **gián tiếp**: OpenSPG sở
hữu mapping `project.id -> Neo4j database`. Trỏ `id: '4'` là tự động đọc `legalfinalcand`. Đừng đi
tìm field database trong config — không có.

### 9.3 Các block còn lại (giữ nguyên, key để placeholder)

```yaml
chat_llm:                               # dòng ~16
  base_url: http://127.0.0.1:8317/v1
  model: gemini-3.8-flash-high
  api_key: <LLM_GATEWAY_KEY>            # KHÔNG commit giá trị thật
  type: maas

vectorize_model:                        # dòng ~36
  base_url: https://api.vilao.ai/v1
  model: dg/text-embedding-3-large
  api_key: <EMBEDDING_KEY>              # KHÔNG commit giá trị thật
  type: openai
  vector_dimensions: 3072               # phải khớp, đổi là phải reset index OpenSPG
```

`vector_dimensions: 3072` phải khớp với index đã build. Đổi số này mà không reset index trong
OpenSPG sẽ vỡ retrieval.

### 9.4 Quy tắc resolve config (dễ sập bẫy)

- `init_env(config_file=...)` → chạy **local YAML mode**. Chỉ vào production mode khi cả
  `KAG_PROJECT_ID` **và** `KAG_PROJECT_HOST_ADDR` được set **và** không có config_file hợp lệ.
- **Config file thắng env var.** Set env mà đã truyền config_file thì env bị bỏ qua.
- `_closest_cfg()` đi **NGƯỢC LÊN** từ CWD tìm `kag_config.yaml`. Chạy ở thư mục con trong repo là
  có thể vô tình bắt phải config production. Luôn truyền `config_file` tuyệt đối.

### 9.5 Cutover production (khi được duyệt — hiện CHƯA)

Đổi đúng 2 dòng trong `kag/kag_config.yaml`: `id: '1'` → `'4'`, `namespace: Legal` →
`LegalFinalCand`. Giữ graph `legal` cũ để rollback. Đây là hành động cần duyệt riêng, không nằm
trong package này.

## 10. Cách chạy lại smoke test / read-only validation

### 10.1 Artifact đã có (ngoài repo, cố ý)

```text
%TEMP%\kag-smoke-final\kag_config.yaml          config scratch project 4 (CÓ key thật, không commit)
%TEMP%\kag-smoke-final\smoke.py                 driver 8 câu
%TEMP%\kag-smoke-final\audit_c4.py              audit trace C4
%TEMP%\kag-smoke-final\smoke_20260921_093218.json   trace đầy đủ 8 câu
%TEMP%\kag-smoke-final\smoke_run2.log           log lần chạy thành công
```

Trace JSON là evidence của mục 6 và 7. Nếu cần lưu dài hạn thì copy ra nơi khác — `%TEMP%` có thể
bị dọn.

### 10.2 Gate 1 — verify LLM gateway TRƯỚC khi chạy

Bỏ bước này là mất 8 vòng vào `openai.APIConnectionError` rồi kết luận sai thành lỗi graph.

```bash
netstat -ano | grep 8317                 # phải thấy LISTENING
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8317/v1/models   # phải 200
# và model gemini-3.8-flash-high phải có trong danh sách trả về
```

Gateway không chạy → **DỪNG**, báo nguyên trạng. Không đi tìm cách sửa graph.

### 10.3 Fingerprint TRƯỚC

```bash
for db in legalfinalcand legal legalc3test legalfullcand; do
  docker exec release-openspg-neo4j cypher-shell -u neo4j -p <NEO4J_PASS> -d $db \
    --format plain "MATCH (n) RETURN count(n);"
  docker exec release-openspg-neo4j cypher-shell -u neo4j -p <NEO4J_PASS> -d $db \
    --format plain "MATCH ()-[x]->() RETURN count(x);"
done

docker exec release-openspg-neo4j cypher-shell -u neo4j -p <NEO4J_PASS> -d legalfinalcand \
  --format plain "MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) ORDER BY l;"
docker exec release-openspg-neo4j cypher-shell -u neo4j -p <NEO4J_PASS> -d legalfinalcand \
  --format plain "MATCH ()-[x]->() RETURN type(x) AS t, count(*) ORDER BY t;"
```

Lưu ra file để diff. Đối chiếu với mục 3.

### 10.4 Chạy smoke

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe "%TEMP%\kag-smoke-final\smoke.py"
```

`PYTHONIOENCODING=utf-8` là bắt buộc. Console Windows mặc định cp1252 → `UnicodeEncodeError:
'charmap' codec can't encode character 'ậ'` ngay khi in tiếng Việt.

### 10.5 Fingerprint SAU và diff

Chạy lại 10.3, diff với file trước. Phải **IDENTICAL**. Khác một dòng nào cũng là smoke đã ghi
graph → điều tra ngay, đừng bỏ qua.

### 10.6 Ba cái bẫy KHÔNG được sập

- **Đừng dùng `kag/solver/eval.py` để so sánh ba hệ thống.** Script này nay đọc
  bộ 150 câu chuẩn nhưng vẫn dùng metric và diskcache riêng của `EvalQa`.
  Diskcache `legal_ckpt` key theo **text câu hỏi**, có thể replay đáp án cũ.
  Dùng runner và evaluator chung trong `benchmark/` để lấy số liệu so sánh.
- **Prompt collision.** `import_modules_from_path` key theo tên thư mục CUỐI, nên
  `kag/solver/prompt` và `kag/builder/prompt` đụng nhau qua `sys.modules["prompt"]`. Lần gọi thứ
  hai bị nuốt im lặng, prompt `legal_*` không register, rơi về prompt tiếng Anh mặc định và **chỉ
  log INFO**. `smoke.py` đã xử lý bằng loader nạp từng file.
- **Assert target trước khi chạy.** `smoke.py` assert cứng `project_id == "4"` và
  `namespace == "LegalFinalCand"`. Giữ lại. Không assert là có ngày test nhầm graph mà không biết.

### 10.7 Sửa `vendor/KAG` thì phải reinstall

Runtime library là `.venv/Lib/site-packages/kag` (openspg_kag-0.8.0), cài **non-editable** từ
`vendor/KAG`. Sửa `vendor/KAG` mà không reinstall thì **không có tác dụng gì**. Repo overlay `kag/`
không có `__init__.py` — đó là script, không phải package.

## 11. Checklist nghiệm thu

```text
[x] graph final ready          project 4 / LegalFinalCand / legalfinalcand
                               15888 nodes, 32655 relations, 1795 chunks, 23/23 documents
[x] builder pass               D2.1 PASS, D2.2 PASS (verify cả runtime, không chỉ tầng graph)
[x] solver baseline works      8/8 FINISH, 0 exception, 3/3 control bắt buộc đúng evidence
[x] no graph write during smoke fingerprint IDENTICAL, 4 DB, 11 label, 19 relation type
[x] repo clean                 working tree clean, local == origin/master, không artifact
                               thí nghiệm nào còn tracked
[x] portable handoff versioned dump + 2 script + 2 doc đã commit (c30ab91); export → restore
                               → verify chạy thật, ra đúng 15888/32655, vector dim 3072
```

### Việc CHƯA làm (có chủ ý, cần reviewer duyệt riêng)

```text
[ ] cutover production         chưa đổi kag/kag_config.yaml (vẫn id 1 / Legal)
[ ] xoá graph cũ               legal / legalc3test / legalfullcand giữ nguyên để rollback
[ ] benchmark 150 câu          không chạy trong phase này
[ ] xử lý C4 recall gap        cần sửa solver, ngoài phạm vi
[ ] D2.3                       đã revert, giữ absent
```

---

## Verdict

**HANDOFF PACKAGE READY**

Graph final candidate dùng được thật: solver baseline chạy sạch, 3/3 control bắt buộc lấy đúng
evidence, quote compatibility PASS, không ghi graph, repo clean. Một limitation đã biết và đã truy
được nguyên nhân (C4, thuộc solver không thuộc graph), tài liệu hoá ở mục 7.
