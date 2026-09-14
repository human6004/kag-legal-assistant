# Đưa đồ thị đã dựng cho người khác chạy

Dựng lại đồ thị từ đầu tốn ~4 giờ và tiền gọi LLM cho 1121 chunk. Không ai
trong nhóm cần làm lại. Chép đồ thị sang là đủ.

## Cái được đóng gói

Chỉ một file: `legal.dump` (~1,4 GB) — toàn bộ database `legal` của Neo4j.
Trong đó có 12.625 node, 42.452 cạnh và 36 vector index (đã ONLINE, không phải
index lại).

MySQL và MinIO **không** đóng gói. MySQL chỉ giữ metadata dự án, dựng lại bằng
`knext project restore` mất một phút — và quan trọng hơn, bản dump MySQL sẽ
chứa API key đã lưu trên server. Đừng gửi nó đi.

## Bên gửi: tạo dump

Neo4j không cho dump khi database đang chạy, và bản DozerDB này không có lệnh
`STOP DATABASE`. Nên phải dừng cả container, bê thư mục dữ liệu ra ngoài, rồi
dump ngoại tuyến bằng một container tạm.

```powershell
$dist = "$PWD\dist"   # dung o goc repo
$img  = "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j:latest"
mkdir $dist -Force

docker stop release-openspg-neo4j
docker cp release-openspg-neo4j:/data "$dist\neo4j-data"
docker start release-openspg-neo4j

docker run --rm -v "${dist}\neo4j-data:/data" -v "${dist}:/dump" $img `
  neo4j-admin database dump legal --to-path=/dump --overwrite-destination=true
```

Xong thì xoá thư mục tạm `dist\neo4j-data` (4,3 GB), chỉ giữ lại `legal.dump`.

`docker stop` chứ đừng `docker compose down`. Xem mục cuối để biết vì sao.

Gửi `legal.dump` qua Drive. File to, Git không nhận (`/dist` đã nằm trong
`.gitignore`).

## Bên nhận: nạp dump

Làm **bước 1 đến 4** trong `README.md` như bình thường: dựng docker, tạo venv,
điền API key của chính mình vào `kag/kag_config.yaml`, rồi
`knext project restore` và `knext schema commit`.

Bỏ qua bước 5 và 6 (`metadata_to_graph.py`, `injection.py`, `indexer.py`).
Đó chính là phần mà dump thay thế.

Rồi nạp:

```powershell
$img = "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j:latest"

docker compose -f docker/docker-compose-west.yml stop neo4j

docker run --rm -v kag-legal-neo4j-data:/data -v "<thư-mục-chứa-legal.dump>:/dump" $img `
  neo4j-admin database load legal --from-path=/dump --overwrite-destination=true

docker compose -f docker/docker-compose-west.yml start neo4j
```

Kiểm tra:

```powershell
docker exec release-openspg-neo4j cypher-shell -u neo4j -p neo4j@openspg -d legal "MATCH (n) RETURN count(n)"
```

Phải ra `12625`. Ra `0` là nạp trượt — thường vì gõ sai tên volume, hoặc quên
`stop neo4j` trước khi nạp.

Xong thì chạy hỏi đáp luôn:

```powershell
cd kag/solver
../../.venv/Scripts/python.exe eval.py
```

## API key

`kag/kag_config.yaml` không nằm trong Git và không được gửi kèm dump. Mỗi người
tự điền khoá của mình theo `kag_config.example.yaml`. Đồ thị đã dựng xong nên
chỉ còn cần khoá `chat_llm` để trả lời; khoá `vectorize_model` vẫn phải có vì
mỗi câu hỏi đều phải nhúng thành vector trước khi tìm.

## Container cũ nằm trên volume ẩn danh

Chỉ liên quan tới máy đã chạy dự án từ trước khi `docker-compose-west.yml` khai
`neo4j-data:/data`. Máy dựng mới bỏ qua mục này.

Compose cũ không khai volume nào cho `/data`, nhưng image Neo4j có dòng
`VOLUME /data` trong Dockerfile, nên Docker tự tạo một volume **ẩn danh** — tên
là một chuỗi hex 64 ký tự. Đồ thị nằm trong đó, không nằm trong lớp ghi của
container. Xem tên thật bằng:

```powershell
docker inspect release-openspg-neo4j --format "{{range .Mounts}}{{.Name}} -> {{.Destination}}{{println}}{{end}}"
```

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
