# kag-legal-assistant

Trợ lý hỏi đáp luật an ninh mạng và truyền thông Việt Nam, dựng bằng KAG
(Knowledge-Augmented Generation) của OpenSPG, so sánh với một nền HybridRAG.

## Thư mục

```
data/       kho văn bản luật, dùng chung cho cả hai bên
docker/     hạ tầng: file compose dựng OpenSPG server, Neo4j, MySQL, MinIO
kag/        dự án KAG, namespace Legal
hybridRAG/  nền so sánh, chạy độc lập, không liên quan tới kag/
```

Kho dữ liệu nằm một chỗ duy nhất và cả hai bên cùng đọc từ đó, nên không sợ lệch
bản. 23 văn bản tiếng Việt đã làm sạch nằm trong hai thư mục con
`data/processed/vn_ai/` (8 văn bản) và `data/processed/vn_an_ninh_mang/` (15 văn
bản), cả hai engine đọc đúng bộ đó.

Đề tài chỉ trả lời về luật Việt Nam nên toàn bộ phần quốc tế đã bỏ khỏi repo:
corpus tiếng Anh, phần metadata quốc tế, và thư mục `data/raw/quoc_te_*`. Lý do: câu
hỏi là tiếng Việt và đáp án phải là điều khoản Việt Nam, trong khi nửa tiếng Anh
từng chiếm 58% số ký tự mà không có một cạnh nào nối sang văn bản Việt — giữ lại
chỉ làm nhiễu vector search chứ không trả lời thêm được câu nào. Cần lại thì lấy
từ lịch sử git.

```
data/
├── processed/     23 file .md luật Việt Nam, chia theo thư mục con, đây là thứ cả hai engine đọc
├── graph/         nodes.json và edges.json sinh từ metadata, nạp thẳng vào đồ thị
├── raw/           bản gốc pdf, docx, html. Không đưa vào git vì nặng 47MB
├── metadata/      27 file json mô tả từng văn bản
├── README.md    quy tắc đặt tên và cấu trúc dữ liệu
└── SOURCES.md   danh sách nguồn đã thẩm định
```

**Mã nguồn KAG không nằm trong repo này.** Nó là thư viện Python cài riêng, xem
bước 2 dưới đây. Thư mục `kag/` chỉ chứa cấu hình, schema, prompt và script của
dự án — không chứa mã của chính KAG.

```
kag/
├── kag_config.yaml        khai API key, namespace, model, prompt
├── schema/
│   └── Legal.schema       khuôn node và cạnh, phải trùng tên namespace
├── builder/
│   ├── indexer.py         dựng đồ thị, đọc từ data/processed
│   ├── metadata_to_graph.py  sinh data/graph/*.json từ data/metadata
│   ├── injection.py       nạp node/cạnh metadata thẳng vào đồ thị
│   ├── external_graph.py  kag/builder/external_graph.py, lớp legal_external_graph
│   ├── clean_corpus.py    làm sạch bản gốc trước khi đưa vào processed
│   └── prompt/            prompt trích xuất: ner.py, std.py, triple.py
└── solver/
    ├── eval.py            chạy hỏi đáp và ghi benchmark.txt
    ├── prompt/            prompt suy luận và sinh câu trả lời, 8 file
    └── data/questions.json  bộ câu hỏi để chấm
```

Prompt tiếng Việt là phần đáng chú ý nhất trong `kag/`: cả `builder/prompt/` lẫn
`solver/prompt/` đều đăng ký tên `legal_*`, và `kag_config.yaml` trỏ vào chúng.

## Chạy

**1. Dựng hạ tầng.** Cần Docker Desktop đang chạy.

```bash
docker compose -f docker/docker-compose-west.yml up -d
```

Mở `http://127.0.0.1:8887`, đăng nhập `openspg` / `openspg@kag`. Thấy giao diện
là xong bước này. Giao diện sẽ trống, đúng như vậy.

**2. Cài KAG.** Cần Python 3.10, vì `requirements.txt` của KAG ghim
`protobuf==3.20.1` và bản đó không có sẵn cho Python mới hơn.

```bash
py -3.10 -m venv .venv
```

```bash
.venv/Scripts/pip install -e D:/study/học/KAG
```

**3. Điền API key** trong `kag/kag_config.yaml`. Ba khối, hai khoá: `openie_llm`
và `chat_llm` là model sinh chữ và dùng chung một khoá, `vectorize_model` là model
nhúng vector và phải là khoá của gateway khác — gateway LLM thường trả 403 cho
endpoint embedding. Cả ba đang để `api_key: key`, là chỗ điền tạm. Thiếu key vector
thì bước 4 dừng ngay.

`base_url` của cả ba khối **phải có đuôi `/v1`**. SDK của OpenAI nối thẳng
`base_url` với `/chat/completions`, nên thiếu `/v1` là `404` — và nó nổ ở bước 7
chứ không nổ ở bước 6, vì hai bước dùng hai khối khác nhau. Viết đúng `openie_llm`
là đủ để tin nhầm rằng `chat_llm` cũng đúng.

**4. Đăng ký dự án lên server.** Chạy trong thư mục `kag/`.

```bash
knext project restore --host_addr http://127.0.0.1:8887 --proj_path .
```

Lệnh này tự ghi lại số hiệu dự án vào `kag_config.yaml`, và thử gọi cả hai model
trước khi cho đi tiếp.

```bash
knext schema commit
```

**5. Nạp metadata vào đồ thị.** Bước này đưa ngày hiệu lực, trạng thái còn hay hết
hiệu lực, và chuỗi thay thế giữa các văn bản vào đồ thị. Scanner chỉ nhận `.md` nên
đây là đường duy nhất.

Phải làm TRƯỚC bước dựng đồ thị, vì hai lý do khác nhau cho hai lệnh:

- `metadata_to_graph.py` sinh ra `data/graph/nodes.json`. Cả `extractor` lẫn
  `post_processor` trong `kag_builder_pipeline` đều trỏ vào `external_graph_loader`,
  mà loader gọi `open()` trần lên hai đường dẫn đó
  (`kag/builder/component/external_graph/external_graph.py:206`). Thiếu file thì
  `indexer.py` nổ `FileNotFoundError` ngay lúc dựng pipeline.
- `injection.py` đẩy 30 node văn bản lên server. Post-processor nối thực thể trích
  được với node văn bản bằng cách tìm trên search engine, node chưa nằm sẵn ở đó
  thì không có gì để nối. Cái này **không** nổ: build vẫn xong, vẫn báo thành công,
  chỉ là mất sạch liên kết về văn bản gốc.

Ví dụ `domain_kg` của KAG cũng xếp đúng thứ tự này.

Chạy trong thư mục `kag/`, không phải thư mục gốc: KAG dò `kag_config.yaml` bằng
cách đi ngược lên cây thư mục từ chỗ đang đứng, đứng ở gốc thì không bao giờ thấy
nó và config rỗng. Hai dòng `../data/graph/*.json` trong config cũng tính theo chỗ
đứng này, nên cả ba lệnh dưới đây đều chạy ở `kag/`.

```bash
cd kag
python builder/metadata_to_graph.py && python builder/injection.py
```

**6. Dựng đồ thị.** Vẫn đứng ở `kag/`. Lệnh này đọc 23 văn bản tiếng Việt trong
`data/processed/`.

Chạy thử một file trước đã. Mỗi văn bản là một lần tốn tiền gọi AI: 23 văn bản là
hơn 1,7 triệu chữ, cắt ra 1121 chunk, mỗi chunk 3 lượt gọi LLM. Cách rẻ nhất để
thử: tạm đổi dòng cuối `indexer.py` trỏ vào một thư mục con chứa đúng một file,
thấy node hiện trên giao diện web rồi mới trỏ lại `data/processed`.

```bash
python builder/indexer.py
```

Kiểm ngay trên giao diện web: văn bản vừa nạp phải là **một** node mang cả trạng
thái hiệu lực lẫn cạnh về chunk. Thấy hai node rời nhau nghĩa là id chưa trùng,
xem `_norm_id` trong `builder/metadata_to_graph.py`.

**7. Hỏi.** Sửa `kag/solver/data/questions.json` theo bộ câu hỏi của bạn, rồi
chạy trong thư mục `solver/`.

```bash
python eval.py
```

Ba file ra, trong thư mục `solver/`:

| File | Có gì |
| --- | --- |
| `legal_res_<timestamp>.json` | **Câu trả lời thật**, ở trường `prediction`, kèm `traceLog` cho biết lấy chunk nào ra để trả lời |
| `benchmark.txt` | Một dòng metric tổng, mở ở chế độ nối thêm nên mỗi lần chạy đẻ thêm một dòng. `processNum` là **số câu qua được**, không phải điểm — bằng `0` nghĩa là hỏng |
| `legal_ckpt/` | Sổ nhớ, khoá là nguyên văn câu hỏi. Hỏi lại y hệt thì trả bài cũ, không gọi mô hình. Muốn hỏi lại thật thì xoá thư mục này |

`main()` đang để `upper_limit=5`, tức chỉ chạy 5 câu đầu trong `questions.json`, và
`thread_num=20`.

`answers` trong `questions.json` là **danh sách các mốc phải xuất hiện trong câu trả
lời** (số tiền, số điều). `do_metrics_eval` so khớp bằng substring sau khi bỏ dấu chấm
và khoảng trắng, rồi trả `hit_rate` cùng `hit_all` vào `benchmark.txt`. Để nguyên chuỗi
placeholder `<...>` thì nó bị lọc bỏ và không có điểm nào được tính.

## Ghi chú

- `docker compose stop` để tắt mà giữ đồ thị. `down -v` là xóa sạch, mất luôn số
  tiền AI đã tiêu để dựng.
- `kag_config.yaml` đang để `language: en`, nhưng prompt đang chạy là bộ tiếng Việt
  tự viết trong `kag/builder/prompt/` và `kag/solver/prompt/`, chọn qua
  `biz_scene: legal`. Đổi `biz_scene` về `default` là lặng lẽ quay về prompt tiếng
  Anh của KAG, không báo lỗi. Đây là chỗ đầu tiên đáng chỉnh khi muốn chất lượng
  trích xuất tốt hơn.
- Đổi schema thì phải chạy lại `knext schema commit`. Đổi prompt hay đổi cách
  cắt văn bản thì không cần, server không hề hay biết.
