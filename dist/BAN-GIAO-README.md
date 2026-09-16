# Bàn giao đồ thị KAG — nhóm nhận đọc file này trước

Snapshot: **2026-09-16**. Đồ thị luật Việt Nam (an ninh mạng + AI), 23 văn bản.

## Đối chiếu nhanh

| Thứ | Giá trị |
| --- | --- |
| `legal.dump` | **997.653.620 bytes** (0,93 GiB) |
| SHA-256 | `BB43903BAD89F2902F23406918DBF1E97331A302CCD8AF17086C8E74FA87E9E1` |
| node | **7.624** |
| cạnh | **26.029** |
| vector index | **36**, tất cả ONLINE |
| `Legal.Chunk` | 1.121 |
| embedding | `dg/text-embedding-3-large`, 3.072 chiều, COSINE |

Tính lại hash trước khi nạp:

```powershell
Get-FileHash legal.dump -Algorithm SHA256
```

⚠️ **Nếu tài liệu nào ghi 12.625 node / 42.452 cạnh thì đó là số sai** — chưa bao
giờ đúng. Đừng dùng nó làm tiêu chí kiểm tra.

## Thứ tự đọc

1. **`HANDOFF_MANIFEST.json`** — toàn bộ số liệu, hash, commit, image digest,
   danh sách 36 vector index, phần `unverified` ghi rõ cái gì chưa đo.
2. **`RESTORE-GRAPH.md`** — hướng dẫn nạp. **Đọc kỹ mục `CREATE DATABASE legal`**;
   bỏ bước đó thì `neo4j-admin` vẫn báo `Done ... 100.0%` nhưng database không
   tồn tại.
3. **`RESTORE_EVIDENCE.txt`** — bằng chứng nạp thử trên volume trắng, gồm cả
   việc chứng minh cách làm sai thật sự hỏng.
4. **`PROVENANCE_REPORT.txt`** — truy vết và các vấn đề đã biết của đồ thị.
5. **`CLEAN_ENV_TEST.txt`** — chứng minh MySQL/MinIO trắng là đủ cho phục hồi Neo4j graph.

## Ba bẫy phải tránh

**1. `CREATE DATABASE legal` là bắt buộc.** Dump chỉ chứa file dữ liệu của
database `legal`, không chứa database `system` — nơi Neo4j lưu danh mục database.
Nạp thẳng vào volume trắng thì `SHOW DATABASES` không có `legal`, và mọi truy vấn
trả `Unable to get a routing table for database 'legal' because this database does
not exist`.

**2. Tên volume phải hỏi Docker, đừng đoán.**

```powershell
docker inspect release-openspg-neo4j --format '{{json .Mounts}}'
```

Tìm phần tử có `"Destination":"/data"`. Nạp sai volume **không báo lỗi** — Neo4j
vẫn chạy, chỉ là database rỗng.

**3. Mọi truy vấn phải có `-d legal`.** Database mặc định tên `neo4j` và **luôn
rỗng**. Quên `-d legal` sẽ thấy `0` và tưởng nạp hỏng.

## Không gửi kèm

`kag/kag_config.yaml` (chứa API key), dump MySQL, dump MinIO. Mỗi người tự điền
khoá riêng theo `kag/kag_config.example.yaml`. Đồ thị đã dựng xong nên chỉ cần
`chat_llm` và `vectorize_model`; **không** cần `openie_llm`.

`vectorize_model` bắt buộc phải dùng **đúng model `dg/text-embedding-3-large` (3.072 chiều)**.
Tương thích embedding đòi hỏi **đúng model**, không chỉ đơn thuần là cùng số chiều vector.
Đổi sang model khác (dù cùng 3.072 chiều) sẽ làm lệch hoàn toàn không gian biểu diễn ngữ nghĩa,
khiến 36 vector index tìm kiếm sai âm thầm mà không có cảnh báo lỗi.

## Chưa đo được / Chưa kiểm chứng

Ghi `UNVERIFIED` hoặc `NOT YET VERIFIED`:

- **Phục hồi toàn diện OpenSPG/KAG trên môi trường mới** (`knext project restore`, `knext schema commit` và KAG retrieval): **NOT YET VERIFIED** (hiện chỉ mới kiểm chứng phục hồi dữ liệu đồ thị Neo4j trên volume trắng và truy vấn Cypher).
- Tỷ lệ truy vết đầy đủ `fact → chunk → doc_id → Điều/Khoản/Điểm`: **UNVERIFIED**
- Tỷ lệ chunk lỗi / bị bỏ qua khi build: **UNVERIFIED**
- Danh sách văn bản stub thiếu full text: **UNVERIFIED**

Đã đo được: **1.121/1.121 chunk (100%) nối tới văn bản** qua quan hệ `source`.

## Vấn đề đã biết của đồ thị

- **218/246** node `Legal.LegalDocument` thiếu `docNumber` (chỉ 28 node có).
- **91/1.055** node `Legal.Article` có tên "trần" (chỉ là số điều, không kèm tên
  văn bản); 964 node có tên đầy đủ.
- **554 loại quan hệ**, trong đó **342 loại chỉ xuất hiện 1 lần**. Tên quan hệ bị
  `to_camel_case` bóp méo: `quyNhNghAV`, `pDNgCho`, `thuCVNBN`, `nghiMCM`…
- Tên node bị dính ký tự escape: `\Điều 4\""` thay vì `Điều 4`.

Chi tiết và cách đo lại: `PROVENANCE_REPORT.txt`.

## Tái lập mọi số liệu

Các script sinh ra báo cáo trên, chạy ở gốc repo, Neo4j đang chạy:

```
.venv\Scripts\python.exe kag\solver\tao_manifest.py          -> HANDOFF_MANIFEST.json
.venv\Scripts\python.exe kag\solver\bao_cao_provenance.py    -> PROVENANCE_REPORT.txt
.venv\Scripts\python.exe kag\solver\thu_moi_truong_sach.py   -> CLEAN_ENV_TEST.txt
.\docker\bang-chung-restore.ps1                              -> RESTORE_EVIDENCE.txt
.\docker\kiem-chung-do-thi.ps1                               -> 7/7 OK
```

Bốn script đầu **chỉ đọc**. `thu_moi_truong_sach.py` và `bang-chung-restore.ps1`
tạo container/volume tạm rồi tự xoá; chúng **không** đụng vào volume đồ thị thật.
