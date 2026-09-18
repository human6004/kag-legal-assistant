# Đưa đồ thị đã dựng cho người khác chạy

Dựng lại đồ thị từ đầu tốn ~2 giờ và tiền gọi LLM cho 1121 chunk. Không ai
trong nhóm cần làm lại. Chép đồ thị sang là đủ.

## Cái được đóng gói

Chỉ một file: `legal.dump` (**0,93 GB**). Số đo thật ngày 2026-09-16, lấy từ chính
máy đang chạy:

| Thứ | Số |
| --- | --- |
| node | **7.624** |
| cạnh | **26.029** |
| vector index | 36, tất cả ONLINE |
| nhãn `Legal.*` | 10 |
| `Legal.Chunk` | 1.121 |
| dung lượng `/data` | 2,9 GB (riêng DB `legal`: 940 MB) |
| `legal.dump` | 0,93 GB — **997.653.620 bytes** |

**SHA-256 của `legal.dump`:**

```
BB43903BAD89F2902F23406918DBF1E97331A302CCD8AF17086C8E74FA87E9E1
```

Tính lại sau khi tải về rồi mới nạp:

```powershell
Get-FileHash legal.dump -Algorithm SHA256
```

Dump đã được **nạp thử lại vào một volume trắng** để kiểm chứng, không phải chỉ
tin vào dòng `Done` của `neo4j-admin`: ra đúng 7.624 node / 26.029 cạnh / 36
vector index, và vector index thật sự trả kết quả (truy vấn
`db.index.vector.queryNodes` cho score 0,9997). Bằng chứng đầy đủ ở
`dist/RESTORE_EVIDENCE.txt`; tái lập bằng `docker/bang-chung-restore.ps1`.

Số liệu đầy đủ để đối chiếu: `HANDOFF_MANIFEST.json`.

⚠️ Tài liệu cũ từng ghi **12.625 node / 42.452 cạnh**. Đó là **số sai**, chưa bao
giờ đúng với đồ thị này. Dùng nó làm tiêu chí kiểm tra sẽ kết luận nhầm là restore
hỏng.

MySQL và MinIO **không** đóng gói. MySQL chỉ giữ metadata dự án và schema
ontology, dựng lại bằng `knext project restore` + `knext schema commit`. Đã kiểm
cột `params` trong `kg_model_detail` là `NULL`, tức **không có API key** — nhưng
vẫn đừng gửi dump MySQL, nó không cần thiết.

## Bên gửi: tạo dump

Chạy ở **gốc repo**:

```powershell
.\docker\xuat-do-thi.ps1
```

Script tự dò volume thật, dừng container, chép dữ liệu ra, dump ngoại tuyến, bật
container lại, rồi dọn thư mục tạm. Xong thì trong `dist/` chỉ còn `legal.dump`.

Neo4j không cho dump khi database đang chạy, và bản DozerDB này không có lệnh
`STOP DATABASE` — nên phải dừng cả container, bê thư mục dữ liệu ra ngoài, rồi
dump ngoại tuyến bằng một container tạm. Script làm đúng ba bước đó; muốn làm tay
thì xem lại lịch sử git của file này.

`docker stop` chứ đừng `docker compose down`. Xem mục cuối để biết vì sao.

Gửi `legal.dump` qua Drive. File to, Git không nhận (`/dist` đã nằm trong
`.gitignore`).

## Bên nhận: nạp dump

Làm **bước 1 đến 4** trong `README.md` như bình thường: dựng docker, tạo venv,
điền API key của chính mình vào `kag/kag_config.yaml`, rồi `knext project restore`
và `knext schema commit`.

Bỏ qua bước 5 và 6 (`metadata_to_graph.py`, `injection.py`, `indexer.py`).
Đó chính là phần mà dump thay thế.

### Trình tự đầy đủ — mức độ kiểm chứng thực tế

Bằng chứng hiện tại (`dist/CLEAN_ENV_TEST.txt`, `kag/solver/thu_moi_truong_sach.py`)
chứng minh: nạp dump vào Neo4j trên môi trường mới (MySQL trắng + MinIO trắng)
thành công và các truy vấn Cypher/vector trực tiếp trên Neo4j trả về đúng dữ liệu.

Tuy nhiên, **phục hồi toàn diện OpenSPG/KAG (gồm `knext project restore`, `knext schema commit` và KAG retrieval)**
được **đánh dấu rõ ràng là CHƯA ĐƯỢC KIỂM CHỨNG (NOT YET VERIFIED)** cho đến khi toàn bộ
chu trình từ khôi phục dự án, commit schema đến KAG retrieval được chạy thực tế.

| Bước | Việc | Tình trạng kiểm chứng |
| --- | --- | --- |
| 1 | `docker compose up -d` | Cần thiết |
| 2 | `knext project restore` | Cần thiết (NOT YET VERIFIED trên stack sạch) |
| 3 | `knext schema commit` | Cần thiết (NOT YET VERIFIED trên stack sạch) |
| 4 | `CREATE DATABASE legal` + nạp dump | **ĐÃ KIỂM CHỨNG** (Neo4j restore khớp 100%) |
| 5 | Điền API key vào `kag/kag_config.yaml` | Cần thiết |
| — | `metadata_to_graph.py`, `injection.py`, `indexer.py` | **Bỏ qua** |

**MySQL và MinIO đều không cần dữ liệu cũ.** Đã đo:

- **MySQL trắng** dùng được. Nó chỉ giữ metadata dự án (`kg_project_info`) và
  schema ontology (`kg_ontology_entity`, 26 bản ghi), dựng lại bằng bước 2-3.
  34 bảng có sẵn trong image là **schema rỗng**, không phải dữ liệu.
  Đã kiểm: cột `params` trong `kg_model_detail` là `NULL` — **không có API key**.
- **MinIO trắng** dùng được. `/data` chỉ có `.minio.sys`, không một bucket người
  dùng nào. Đồ thị không dùng MinIO.

Hai bước 2-3 **không thể bỏ qua** kể cả khi đã có dump: dump không chứa database
`system` của Neo4j, cũng không chứa metadata dự án trong MySQL.

### Nạp vào ĐÚNG volume đang được gắn

Đây là chỗ dễ trượt nhất, và trượt thì **không có thông báo lỗi nào** — Neo4j vẫn
chạy, chỉ là database rỗng. Nguyên nhân: dump nạp vào một volume, còn container
lại đang đọc một volume khác.

Tên volume **không đoán được**, phải hỏi Docker:

```powershell
docker inspect release-openspg-neo4j --format '{{json .Mounts}}'
```

Tìm phần tử có `"Destination":"/data"`, lấy `Name` của nó. **Dùng đúng tên đó** ở
lệnh dưới, đừng chép nguyên `kag-legal-neo4j-data`:

```powershell
$img = "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j@sha256:4bc5b7f6b83d333b1d2c8f60ac145c068d77d50bca65b3a07c927f9e2a541eb9"
$vol = "<Name vừa tìm được>"

# 1. Neo4j phải chạy để tạo database, rồi mới tắt đi mà nạp.
docker start release-openspg-neo4j
docker exec release-openspg-neo4j cypher-shell -u neo4j -p 'neo4j@openspg' "CREATE DATABASE legal"

# 2. Tắt rồi nạp đè.
docker stop release-openspg-neo4j

docker run --rm -v "${vol}:/data" -v "<thư-mục-chứa-legal.dump>:/dump" $img `
  neo4j-admin database load legal --from-path=/dump --overwrite-destination=true

docker start release-openspg-neo4j
```

⚠️ **Bước `CREATE DATABASE legal` là bắt buộc, đừng bỏ.** Dump chỉ chứa **file dữ
liệu** của database `legal`; nó không chứa database `system`, mà `system` mới là
nơi Neo4j lưu danh mục database. Nạp thẳng vào volume trắng thì `load` vẫn báo
`Done: 3739 files … 100.0%` — trông y hệt thành công — nhưng `SHOW DATABASES`
không có `legal`, và mọi truy vấn trả:

```
Unable to get a routing table for database 'legal' because this database does not exist
```

Đã dựng lại đúng tình huống đó và đo được: bỏ bước này thì `legal` **không** xuất
hiện; làm đủ thì ra đúng 7.624 node. Nếu `CREATE DATABASE` báo database đã tồn tại
thì máy đó đã có sẵn — cứ đi tiếp bước 2, `--overwrite-destination=true` lo phần
ghi đè.

Vì sao không dùng `docker compose stop neo4j` như bản tài liệu trước: lệnh đó
đòi đúng tên service và đúng thư mục, còn `docker stop` theo tên container thì
luôn đúng. Quan trọng hơn, compose không giúp gì cho việc chọn volume — mà đó
mới là chỗ sai.

### Kiểm tra

```powershell
.\docker\kiem-chung-do-thi.ps1
```

Script đối chiếu node, cạnh, vector index, nhãn, `Legal.Chunk`, và tình trạng
ONLINE của index. Phải ra **`7/7 OK`**. Ra số khác thì đọc dòng `FAIL` để biết
trượt ở đâu.

Kiểm tay một dòng, nếu muốn:

```powershell
docker exec release-openspg-neo4j cypher-shell -u neo4j -p 'neo4j@openspg' -d legal "MATCH (n) RETURN count(n)"
```

Phải ra `7624`. Ra `0` là nạp trượt.

⚠️ Nhớ `-d legal`. Database `legal` là database **phụ**; database mặc định của
Neo4j tên là `neo4j` và **luôn rỗng** trong dự án này. Quên `-d legal` sẽ thấy
`0` và tưởng nạp hỏng, trong khi thực ra nạp thành công.

Xong thì chạy hỏi đáp luôn:

```powershell
cd kag\solver
..\..\.venv\Scripts\python.exe eval.py
```

## API key

`kag/kag_config.yaml` không nằm trong Git và không được gửi kèm dump. Mỗi người
tự điền khoá của mình theo `kag_config.example.yaml`. Đồ thị đã dựng xong nên
chỉ còn cần khoá `chat_llm` để trả lời; khoá `vectorize_model` vẫn phải có vì
mỗi câu hỏi đều phải nhúng thành vector trước khi tìm.

Lưu ý quan trọng: tương thích embedding đòi hỏi **đúng model `dg/text-embedding-3-large` (3.072 chiều)**,
không chỉ đơn thuần là cùng số chiều vector. Đổi model khác sẽ làm lệch không gian vector và kết quả tìm kiếm.

## Container cũ nằm trên volume ẩn danh

Chỉ liên quan tới máy đã chạy dự án từ trước khi `docker-compose-west.yml` khai
`neo4j-data:/data`. Máy dựng mới bỏ qua mục này.

Compose cũ không khai volume nào cho `/data`, nhưng image Neo4j có dòng
`VOLUME /data` trong Dockerfile, nên Docker tự tạo một volume **ẩn danh** — tên
là một chuỗi hex 64 ký tự. Đồ thị nằm trong đó, không nằm trong lớp ghi của
container:

```powershell
docker inspect release-openspg-neo4j --format '{{json .Mounts}}'
```

Máy đang dựng đồ thị cho nhóm là một máy như vậy. Đó là lý do **không** được
chép nguyên `kag-legal-neo4j-data` khi nạp dump: tên đó là volume rỗng do compose
khai, không phải nơi đồ thị đang nằm.

Hệ quả, theo thứ tự đáng lo dần:

- `docker compose up -d` tạo lại container và gắn vào volume **có tên** đang
  rỗng. Đồ thị không mất, nhưng volume ẩn danh thành mồ côi — vẫn còn trên đĩa,
  chỉ là không container nào dùng nữa.
- `docker volume prune` xoá mọi volume không ai dùng. Sau bước trên, volume mồ
  côi đó nằm đúng tầm ngắm. Đây mới là lệnh làm mất đồ thị thật sự.
- `docker compose down -v` xoá luôn cả volume ẩn danh đang gắn. `down` không có
  `-v` thì không xoá, chỉ bỏ container lại và để volume mồ côi.

Nên trước khi đụng bất cứ lệnh nào ở trên: tạo dump theo phần đầu tài liệu này.
Có dump rồi thì `up -d` để compose dựng container kèm volume có tên, nạp dump
vào, xong mới dọn volume cũ.
