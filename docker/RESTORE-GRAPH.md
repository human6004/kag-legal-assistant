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
$dist = "D:\study\HoiThao\kag-legal-assistant\dist"
$img  = "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j:latest"
mkdir $dist -Force

docker stop release-openspg-neo4j
docker cp release-openspg-neo4j:/data "$dist\neo4j-data"
docker start release-openspg-neo4j

docker run --rm -v "${dist}\neo4j-data:/data" -v "${dist}:/dump" $img `
  neo4j-admin database dump legal --to-path=/dump --overwrite-destination=true
```

Xong thì xoá thư mục tạm `dist\neo4j-data` (4,3 GB), chỉ giữ lại `legal.dump`.

`docker stop` chứ tuyệt đối không `docker compose down`. Container neo4j tạo
trước tháng 9/2026 không có volume, `down` xoá sạch đồ thị kể cả khi không có
cờ `-v`.

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

## Container cũ chưa có volume

`docker-compose-west.yml` giờ đã khai `neo4j-data:/data`, nên máy dựng mới sẽ
an toàn với `down`. Máy nào đang chạy container tạo từ trước thay đổi đó thì dữ
liệu vẫn nằm trong container: `docker compose up -d` lần tới sẽ tạo lại
container và đồ thị trong đó mất. Cách chuyển sang volume: tạo dump theo phần
trên, `up -d` cho compose dựng lại container kèm volume, rồi nạp dump vào.
