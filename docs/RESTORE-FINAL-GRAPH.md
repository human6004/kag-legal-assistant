# RESTORE-FINAL-GRAPH — dựng lại graph final candidate trên máy nhận

Tài liệu này dành cho **người nhận bàn giao**. Mục tiêu: từ một bản clone sạch của repo
và một file dump, dựng lại đúng graph đã duyệt và chạy được solver — **không** chạy lại
LLM extraction, không embedding lại, không index lại.

Thời gian ước tính: 10–20 phút, phần lớn là chờ verify checksum (~1.3 GB) và chờ Neo4j.

---

## A. Máy nguồn — xuất dump

Chỉ chạy **một lần**, ở gốc repo, trên máy đang có graph final:

```powershell
.\docker\xuat-final-graph.ps1
```

Script từ chối chạy nếu fingerprint nguồn khác chuẩn (xem mục C), và từ chối ghi đè
dump cũ đang có. Kết quả:

```text
dist/legalfinalcand.dump           ~1.31 GB
dist/legalfinalcand.dump.sha256    <hash>  legalfinalcand.dump
```

Gửi **cả hai** file. `/dist` nằm trong `.gitignore` nên Git không mang chúng — phải
truyền tay (Drive, USB, scp...). Thiếu file `.sha256` thì máy nhận mất khả năng phát
hiện dump hỏng khi truyền.

---

## B. Máy người nhận — các bước

Chạy tuần tự, ở gốc repo:

```powershell
# 1. Lấy mã nguồn
git clone <repo-url>
cd kag-legal-assistant

# 2. Dựng hạ tầng (OpenSPG server + MySQL + Neo4j + MinIO)
docker compose -f docker/docker-compose-west.yml up -d

# 3. Tạo config làm việc và điền key CỦA BẠN
copy kag\kag_config.example.yaml kag\kag_config.yaml
#    -> mở kag/kag_config.yaml, điền 3 chỗ api_key và 3 chỗ base_url

# 4. Đặt dump vào dist/
#    dist/legalfinalcand.dump
#    dist/legalfinalcand.dump.sha256

# 5. Python cho knext (đã kiểm chứng trên 3.12.10)
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 6. Restore
.\docker\restore-final-graph.ps1
```

Đợi container healthy trước bước 6:

```powershell
docker compose -f docker/docker-compose-west.yml ps
```

### B.1 Cấu hình `kag_config.yaml`

`kag/kag_config.example.yaml` là **template duy nhất** của repo. Không có file config
thứ hai, không có `kag_config.restore.yaml`. Copy rồi điền:

| Trường | Điền gì |
|---|---|
| `openie_llm.base_url`, `.api_key`, `.model` | gateway LLM của bạn |
| `chat_llm.base_url`, `.api_key`, `.model` | gateway LLM của bạn |
| `vectorize_model.base_url`, `.api_key`, `.model` | dịch vụ embedding của bạn |

Hai điều **bắt buộc**:

- `vectorize_model.vector_dimensions` phải là **3072**. Index vector trong dump đã
  build ở 3072 chiều. Đổi số này mà không rebuild index là retrieval hỏng im lặng.
- Endpoint LLM và embedding phải **sống trước khi restore**. `knext project create`
  gọi thật vào cả hai để kiểm tra config; chết là `400 invalid vectorizer config`.
  Bạn không cần model mạnh — chỉ cần endpoint trả lời được. Extraction không chạy lại.

`project.namespace` để nguyên `Legal` trong file này cũng được: script restore tự
sinh bản config tạm với namespace đúng (xem mục E). Sau khi restore xong, sửa
`project.namespace` thành `LegalFinalCand` và `project.id` thành id thật để solver
trỏ đúng graph — script in ra cả hai giá trị ở cuối.

---

## C. Fingerprint chuẩn

Mọi lần restore phải khớp đúng bộ số này. Script tự verify và **dừng** nếu lệch.

```text
nodes      = 15888
relations  = 32655
chunks     = 1795
vector dim = 3072
```

Nguồn: `docs/HANDOFF.md`. Lệch một số là dừng và báo người gửi dump, không tự sửa.

---

## D. Script restore làm gì

`docker/restore-final-graph.ps1` làm **đúng hai việc**:

1. **Metadata OpenSPG (project + schema).** Neo4j dump **không** chứa project
   metadata — project nằm trong MySQL của OpenSPG. Thiếu bước này thì dump nạp xong
   solver vẫn không thấy graph.
2. **Nội dung Neo4j.** Nạp store bằng `neo4j-admin database load`.

Script **không** chạy builder, **không** chạy indexer, **không** gọi LLM extraction,
**không** embedding lại graph.

### D.1 Vì sao database luôn là `legalfinalcand`

OpenSPG **không** đọc `graph_store.database` trong config để quyết định database. Nó
lấy `database = lowercase(namespace)` và tự tạo database rỗng khi tạo project.

Đã kiểm chứng bằng thực nghiệm: tạo project namespace `ZZProbeIso` với
`graph_store.database=zzprobe_iso` → OpenSPG tạo database `zzprobeiso`, bỏ qua trường
kia. Nên namespace `LegalFinalCand` **luôn** ứng với database `legalfinalcand`, bất kể
máy nào. Đó là lý do namespace cố định trong script, còn project id thì không.

### D.2 Vì sao project id không copy được từ máy nguồn

Project id do **máy bạn** cấp khi tạo project. Nó không liên tục — trên máy nguồn đã
từng là 4, rồi lần tạo kế tiếp là 6. Script đọc lại id thật sau khi tạo và tự ghi vào
config, nên bạn không phải đoán.

---

## E. Vì sao script sinh file tạm trong `%TEMP%`

Nguồn **duy nhất** của config là `kag/kag_config.example.yaml`; nguồn **duy nhất** của
schema là `kag/schema/Legal.schema`. Repo không giữ bản sao thứ hai của chúng.

Nhưng `knext` cần hai thứ mà hai file nguồn không có:

- **Namespace.** Example trỏ `Legal` (project production). Tạo project bằng file đó
  là ghi vào **namespace sai**, đè lên graph production.
- **`vectorize_model.name` + `provider`.** `knext project create` gọi thật vào endpoint
  embedding và đọc hai trường này. Example không khai chúng.

Nên mỗi lần chạy, script sinh hai file tạm trong `%TEMP%\restore-final-graph-<guid>\`:

```text
LegalFinalCand.schema   = kag/schema/Legal.schema, chỉ đổi dòng `namespace`
kag_config.yaml         = kag/kag_config.yaml, chỉ đổi namespace + thêm name/provider
```

Cả thư mục tạm bị xoá trong `finally`. Không file nào nằm trong repo, nên không có
schema duplicate hay config template thứ hai để lệch khỏi bản gốc: sửa bản gốc thì
lần restore sau tự động ăn theo.

> **Chỉ đổi dòng `namespace`.** Không được `Replace("Legal", "LegalFinalCand")` trên
> toàn file schema: chuỗi `Legal` còn nằm trong **tên entity** và **đích relation**
> (`LegalDocument`, `LegalTerm`). Thay bừa sẽ biến `LegalDocument` thành
> `LegalFinalCandDocument` và làm vỡ mọi relation trỏ tới nó. Đã đo được: 8 relation
> và 2 entity bị đổi tên sai. Script dùng regex neo dòng `^...$` nên chỉ dòng khai báo
> bị chạm.

### E.1 `knext project create` không chỉ tạo project

**CẢNH BÁO — đây là cái bẫy nguy hiểm nhất của toàn bộ quy trình.**

`knext project create` **không chỉ tạo project rỗng**. Nó còn:

1. **scaffold một thư mục project demo đầy đủ** (`schema/`, `builder/`, `solver/`...), và
2. **commit luôn một schema MẶC ĐỊNH generic** vào project vừa tạo.

Schema mặc định đó là ontology demo của OpenSPG, **không liên quan gì tới pháp lý**:

```text
Person, Organization, Date, Event, Astronomy, Medicine, ...
```

Đã kiểm chứng thật trên stack cô lập: ngay sau `project create`, scaffold sinh ra thư mục
`LegalFinalCand/` chứa `schema/LegalFinalCand.schema` với đúng bộ type generic trên.

Vì vậy thứ tự **bắt buộc**:

```text
(1) knext project create   -> tạo project + database rỗng (schema ĐANG SAI)
(2) đọc lại project id THỰC TẾ mà máy này cấp
(3) GHI ĐÈ schema tạm bằng schema LegalFinalCand đã transform từ kag/schema/Legal.schema
(4) knext schema commit    -> đẩy schema pháp lý thật lên server
```

**Bước (3) không được bỏ.** Phải ghi đè file schema trong thư mục scaffold bằng schema
pháp lý đã transform namespace **trước khi** commit. Bỏ bước này thì bước (4) sẽ commit
ontology demo (`Person`, `Organization`, `Astronomy`...) lên project — và **solver sẽ chạy
với ontology sai**: không có `Chunk`, `Article`, `LegalDocument`, `Obligation`, `Sanction`,
nên retrieval theo logic-form trả rỗng hoặc trả rác, trong khi mọi lệnh đều exit 0 và
trông như thành công.

Script tự verify sau khi commit: đếm số type của project, **dừng nếu < 15** (dấu hiệu
đã commit nhầm schema mặc định).

Script tự verify sau khi commit: đếm số type của project, **dừng nếu < 15** (dấu hiệu
đã commit nhầm schema mặc định).

`commit_schema()` đọc `env.project_path/schema/<namespace>.schema`, với
`env.project_path` là thư mục chứa file config mà `_closest_config()` tìm thấy — và nó
đi **từ CWD ngược lên**, ưu tiên `kag_config.yaml`. Đã kiểm chứng: chạy
`knext schema commit` từ một CWD mà phía trên còn thư mục scaffold chứa
`kag_config.yaml` thì `_closest_config()` bắt nhầm file đó, đọc schema mặc định, và báo
`project namespace is not defined`. Script commit với CWD = thư mục tạm, nơi duy nhất
chứa đúng config + schema của ta.

---

## F. Thứ tự nạp Neo4j (bắt buộc, đã test thật)

```text
(a) neo4j-admin database load   -> chép store xuống đĩa
(b) CREATE DATABASE             -> chỉ khi runtime chưa tự đăng ký database
```

Cả hai phải làm khi container **đang dừng**:

```text
"It is not possible to replace a database that is mounted in a running Neo4j server."
```

Script stop container, load offline, rồi start lại trong `finally`.

**(a) là bước duy nhất bắt buộc cho fresh restore.** Đã đo thật trên volume mới tinh:
sau `database load` + start container, Neo4j **tự đăng ký** database vào system catalog và
database **online luôn** — đọc ra ngay 15888 nodes / 32655 relations, **không cần**
`CREATE DATABASE`.

`CREATE DATABASE` chỉ cần trong **nhánh replace/drop**: khi database đã tồn tại và bị
`DROP DATABASE` trước khi load, hoặc khi runtime không tự nhận store vừa chép vào. Đây là
bước **phòng ngừa**, không phải bước bắt buộc của fresh restore.

Thứ tự vẫn luôn là **(a) trước, (b) sau nếu cần**:

- Làm ngược lại (CREATE trước) thì Neo4j tạo một store **rỗng**, rồi load đè lên vẫn được
  nhưng là đường vòng.
- Làm (a) rồi (b) thì Neo4j nhận đúng store đã có sẵn trên đĩa.

Script xử lý **idempotent**: sau khi load và start, nó kiểm database đã đăng ký chưa, và
chỉ chạy `CREATE DATABASE` nếu còn thiếu — nên nhánh fresh restore không sinh lệnh thừa,
còn nhánh replace/drop vẫn an toàn.

Nếu database đã có dữ liệu **khác** fingerprint final, script **từ chối ghi đè** và
dừng. Muốn thay thế thật thì chạy `-ForceReplace` — hành động phá huỷ, không hoàn tác.

---

## G. Verify sau restore

Script tự chạy và **dừng** nếu lệch. Kiểm tay:

```powershell
docker exec release-openspg-neo4j cypher-shell -u neo4j -p 'neo4j@openspg' -d legalfinalcand `
  'MATCH (n) RETURN count(n)'
# 15888

docker exec release-openspg-neo4j cypher-shell -u neo4j -p 'neo4j@openspg' -d legalfinalcand `
  'MATCH ()-[x]->() RETURN count(x)'
# 32655

docker exec release-openspg-neo4j cypher-shell -u neo4j -p 'neo4j@openspg' -d legalfinalcand `
  'MATCH (n:`LegalFinalCand.Chunk`) WHERE n._content_vector IS NOT NULL RETURN size(n._content_vector) LIMIT 1'
# 3072
```

Tên property là `_content_vector`, **không phải** `content_vector`.

Kiểm schema đã lên server (phải ≥ 15, và là type pháp lý chứ không phải Person/Organization):

```powershell
docker exec release-openspg-mysql mysql -uroot -popenspg -N -B `
  -e "SELECT COUNT(*) FROM openspg.kg_project_entity WHERE project_id=<id-that>;"
```

---

## H. Chạy solver baseline

Sửa `kag/kag_config.yaml`:

```yaml
project:
  namespace: LegalFinalCand
  id: "<id thật, script in ra ở cuối>"
```

Rồi:

```powershell
cd kag
..\.venv\Scripts\python.exe solver\eval.py
```

Kết quả ghi vào `kag\solver\runs\`. Bộ câu hỏi: `kag\solver\data\questions_mo_rong.json`.

`biz_scene: legal` quyết định prefix prompt `legal_*`. Đổi thành `default` là quay về
prompt tiếng Anh của KAG, im lặng, không báo lỗi.

---

## I. Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| `knext project create` exit ≠ 0 | chưa điền `api_key`, hoặc endpoint LLM/embedding không sống |
| `400 invalid vectorizer config` | endpoint embedding chết lúc tạo project |
| `project namespace is not defined` | `knext schema commit` chạy ở CWD có `kag_config.yaml` lạ phía trên |
| schema lên server < 15 type | đã commit nhầm schema mặc định của scaffold |
| solver không thấy graph | thiếu project OpenSPG (bước 1), hoặc `project.namespace`/`id` trong `kag_config.yaml` chưa đúng |
| retrieval trả rỗng | `vector_dimensions` ≠ 3072 |
| `database is in use` khi load | còn database đăng ký trong catalog — script tự DROP trước |
| Neo4j OOM khi build lại | heap 4G + pagecache 1G trên Docker VM 7.62 GiB; hạ `num Chains`/threads, đừng nâng heap mà không cấp thêm RAM |

---

## J. Ranh giới — những gì KHÔNG được làm khi restore

```text
metadata_to_graph.py     không chạy
injection.py             không chạy
indexer.py               không chạy
checkpoint               không dùng
LLM extraction           không chạy lại
embedding graph          không chạy lại
```

Graph đến từ dump, không phải từ việc dựng lại. Chạy lại các bước trên sẽ tạo graph
**khác** với graph đã duyệt.
