# kag-legal-assistant

Trợ lý hỏi đáp luật an ninh mạng và truyền thông Việt Nam, dựng bằng KAG
(Knowledge-Augmented Generation) của OpenSPG, so sánh với một nền HybridRAG.

## Thư mục

```
data/       kho văn bản luật, dùng chung cho cả hai bên
docker/     hạ tầng: file compose dựng OpenSPG server, Neo4j, MySQL, MinIO
kag/        dự án KAG, namespace Legal
vendor/KAG/ mã nguồn thư viện KAG, ghim commit fdab15b3
hybridRAG/  nền so sánh, chạy độc lập, không liên quan tới kag/
tests/builder/  bốn regression test và check_prompts.py, ngoài vùng runtime import
scripts/    secret_scan.py kiểm tra bí mật trong repo
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
├── raw/           bản gốc pdf, docx, html để đối chiếu; chưa có pipeline tái sinh
├── metadata/      JSON từng văn bản và file tổng hợp/template
├── trial/         bốn Markdown dùng thử
├── README.md    quy tắc đặt tên và cấu trúc dữ liệu
└── SOURCES.md   danh sách nguồn đã thẩm định
```

**Mã nguồn KAG nằm trong repo này, ở `vendor/KAG/`**, ghi nhận commit `fdab15b3`
của OpenSPG/KAG (phạm vi đã đối chiếu ở mục Pipeline). Thư mục `kag/` chỉ chứa cấu hình, schema, prompt và script của
dự án, không chứa mã của chính thư viện.

`vendor/KAG/` là cây mã nguồn trần: 1211 file, 170 MB, **đã gỡ `.git`**. Bản gốc
kèm lịch sử git nặng 360 MB; phần lịch sử 187 MB đó không cần thiết vì repo này
ghim cứng một commit duy nhất. Đừng `git add` một thư mục `vendor/KAG/` có `.git`
bên trong — git sẽ tạo gitlink rỗng, người clone về thấy thư mục trống mà git
không báo lỗi gì.

```
kag/
├── kag_config.example.yaml  cấu hình mẫu được track
├── kag_config.yaml        cấu hình local, bị ignore, chứa khóa riêng
├── schema/
│   ├── Legal.schema       khuôn node và cạnh, phải trùng tên namespace
│   └── check_schema.py    kiểm tra cú pháp offline
├── builder/
│   ├── indexer.py         dựng đồ thị, đọc từ data/processed
│   ├── metadata_to_graph.py  sinh data/graph/*.json từ data/metadata
│   ├── injection.py       nạp node/cạnh metadata thẳng vào đồ thị
│   ├── external_graph.py  kag/builder/external_graph.py, lớp legal_external_graph
│   ├── extractor.py       vá extractor KAG và lưu vị ngữ gốc
│   ├── chain.py           một chunk hỏng không kéo cả văn bản theo
│   ├── canon_id.py        quy tắc id node, dùng chung cho cả hai đường nạp
│   ├── __init__.py        bản vá áp dụng khi import builder
│   ├── reader.py          giữ số Khoản/Điểm và thứ tự Markdown
│   └── prompt/            prompt trích xuất: ner.py, std.py, triple.py
└── solver/
    ├── eval.py            chạy hỏi đáp và ghi benchmark.txt
    ├── gold_chunks.py     tạo tập chunk vàng từ checkpoint
    ├── recall_report.py   đánh giá truy xuất từ kết quả đã lưu
    ├── prompt/            prompt suy luận và sinh câu trả lời
    └── data/              questions.json, questions_mo_rong.json và gold_chunks*.json
```

Prompt tiếng Việt là phần đáng chú ý nhất trong `kag/`: cả `builder/prompt/` lẫn
`solver/prompt/` đều đăng ký tên `legal_*`, và `kag_config.yaml` trỏ vào chúng.

## Pipeline và đường gọi thực tế

```text
raw ──[chưa xác minh công cụ chuyển đổi/OCR]──> processed (đầu vào có sẵn)
processed/*.md (đệ quy)
  → indexer.py → BuilderChainRunner → dir_file_scanner
  → legal_md_reader → length_splitter → legal_schema_free_extractor
  → batch_vectorizer → kag_post_processor → kg_writer → graph

metadata/*.json → metadata_to_graph.py → data/graph/{nodes,edges}.json
  ├→ legal_external_graph.ner → bổ sung NER trong extractor
  └→ injection.py → domain_kg_inject_chain
       → legal_external_graph.dump → batch_vectorizer → kg_writer → graph
```

`raw → processed` không nằm trong pipeline đang chạy. `clean_corpus.py` cũ chỉ
hậu xử lý Markdown, đã bị xóa; chưa tìm được `build_processed.py` trong lịch sử
Git khả dụng. Lần cập nhật corpus `2d9ea1c` không kèm công cụ tái sinh. Xem
[data/README.md](data/README.md) để biết giới hạn xác minh; không tự khôi phục
script cũ hoặc ghi lại dữ liệu.

`indexer.py` và `injection.py` quét thư mục builder bằng
`import_modules_from_path`. Hàm upstream thêm thư mục cha vào `sys.path`, import
package theo tên cuối (`builder`, rồi các module con), đi đệ quy bằng `pkgutil`.
Do đó `builder/__init__.py` chạy và decorator `register(...)` đăng ký các type;
`from_config` chọn constructor theo `type` trong YAML. Không có import trực tiếp
từ entrypoint không có nghĩa module mồ côi. Test và `check_prompts.py` đã được
đưa sang `tests/builder/` vì trình quét cũng import chúng, kể cả mã cấp module.

- **CLI:** `indexer.py` gọi runner; `metadata_to_graph.py` sinh JSON (có ghi file);
  `injection.py` gọi chain nạp metadata. Runner, scanner, checkpoint và chain
  unstructured/domain injection kế thừa KAG; `indexer.py` bổ sung cờ dừng, cầu dao
  và đối số thư mục.
- **Custom luật qua registry/config:** `reader.py` (`legal_md_reader`) giữ thứ tự
  và số Khoản/Điểm; splitter `length_splitter` vẫn của KAG (4950/100 trong mẫu).
  `extractor.py` (`legal_schema_free_extractor`) kế thừa SchemaFreeExtractor,
  xử lý NER lỗi/tuple triple/rác và lưu vị ngữ gốc trên cạnh.
  `external_graph.py` (`legal_external_graph`) sửa kiểm tra properties của loader
  upstream và thay NER jieba bằng khớp chuỗi tên văn bản tiếng Việt.
- **Bản vá khi import:** `builder/__init__.py` thay `processing_phrases` tại module
  extractor và bọc `SubGraph.add_node/add_edge`. `canon_id.py` chứa quy tắc ID
  dùng tại đây, trong `metadata_to_graph.py` và khớp vị ngữ ở extractor; giữ ID
  của Chunk/Table và các nhãn trong `KEEP_ID`. Đây là code runtime cần giữ.
- **Bản vá chain qua registry:** `chain.py` (`legal_unstructured_builder_chain`)
  kế thừa `DefaultUnstructuredBuilderChain`, bọc extractor/vectorizer/
  post-processor/writer để bỏ chunk lỗi. Reader/splitter không được bọc ở đây.
  Không dùng log thành công của runner làm bằng chứng graph đầy đủ.
- **Ba prompt:** `ner.py` đăng ký `legal_ner` nhận diện thực thể theo schema;
  `std.py` đăng ký `legal_std` chuẩn hóa tên thực thể;
  `triple.py` đăng ký `legal_triple` trích xuất bộ ba. Config truyền cả ba cho
  extractor; không thay nội dung prompt trong bước A.
- **Công cụ kiểm tra/đánh giá:** `tests/builder/*`, `schema/check_schema.py`,
  `solver/eval.py`, `gold_chunks.py`, `recall_report.py`, `scripts/secret_scan.py`
  đều giữ lại. Chúng được chạy bằng CLI; eval gọi model/server, gold_chunks ghi
  tập vàng, recall_report đọc kết quả cũ. Không chạy chúng như ingestion.

Config mẫu `kag/kag_config.example.yaml` được track; config local
`kag/kag_config.yaml` bị ignore, không phải mặc định cho máy khác. Đối chiếu local
ở bước A: builder cùng type/prompt/đường graph, nhưng số chain × thread là `4×4`
so với mẫu `2×2`; khóa, endpoint và model không công bố. Cả hai bỏ
`similarity_threshold`, nên post-processor chỉ lọc invalid data, không chạy hai
nhánh nối mờ. Metadata chỉ ánh xạ các trường trong `PROP_MAP`/`REL_MAP`, thêm
`desc`, `semanticType` và node tham chiếu còn thiếu; không tự mang mọi trường
JSON (ví dụ `in_force`) sang graph.

**Đối chiếu upstream:** GitHub API đã xác minh `fdab15b3` thành
[`fdab15b3929d2ee40dfcdd388f90233096a6afc9`](https://github.com/OpenSPG/KAG/commit/fdab15b3929d2ee40dfcdd388f90233096a6afc9).
Đã so nội dung, bỏ khác biệt xuống dòng: `kag/common/registry/{utils,registrable}.py`,
`kag/builder/{runner,default_chain}.py`, external graph loader, KAG post-processor,
`examples/domain_kg/kag_config.yaml` và hai entrypoint builder của example khớp
vendor. Example dùng cấu trúc project domain gồm config/builder/schema/solver;
project này mở rộng bằng các type luật nêu trên, không cần ép giống toàn bộ example.
Hai file `kag/common/conf.py`, `knext/common/env.py` trong vendor khác ở bản vá
đọc config UTF-8 và chú thích. Chưa so toàn bộ cây vendor nên không khẳng định
chỉ có hai khác biệt trên toàn repo.

`requirements.txt` cài `./vendor/KAG` không editable; runtime thực tế trong `.venv`
là `site-packages/kag`. Đã so bản cài với vendor ở registry utils, runner, default
chain, Markdown reader, SchemaFreeExtractor, external loader và post-processor:
khớp nội dung. Không nâng phiên bản hay sửa vendor trong bước A.

## Kiểm tra source (từ gốc repo)

```powershell
.venv/Scripts/python.exe -X utf8 tests/builder/check_prompts.py
.venv/Scripts/python.exe -X utf8 kag/schema/check_schema.py
.venv/Scripts/python.exe -X utf8 tests/builder/test_reader_fixes.py
.venv/Scripts/python.exe -X utf8 tests/builder/test_predicate_binding.py
.venv/Scripts/python.exe -X utf8 tests/builder/test_stop_handler.py
.venv/Scripts/python.exe -X utf8 kag/builder/canon_id.py
.venv/Scripts/python.exe -X utf8 tests/builder/test_builder_fixes.py
```

Hai check prompt/schema chỉ cần stdlib. Reader dùng dữ liệu `processed` hiện có;
reader/predicate/stop cần KAG đã cài. `test_builder_fixes` dựng runner từ config
local, cần OpenSPG có schema và JSON graph; không gọi `runner.invoke` hoặc model.
Chạy mỗi test bằng tiến trình riêng vì chúng import/bọc module runtime. Lỗi test
phải báo nguyên trạng; không sửa thuật toán hoặc dữ liệu để làm xanh trong bước A.

Kết quả kiểm tra bước A (2026-09-18): reader 64/64, predicate 27/27,
stop-handler, builder-fixes, canon ID, ba prompt và schema 10 kiểu đều đạt.
Secret scan không phát hiện khóa; cú pháp năm file chuyển vị trí hợp lệ.
`.venv` hiện có protobuf 7.36.2, import KAG mặc định lỗi
`TypeError: Descriptors cannot be created directly.`
Các test cần KAG đã chạy với `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`
chỉ trong tiến trình con, không cài lại dependency. Có thể tái hiện cho từng test:

```powershell
.venv/Scripts/python.exe -X utf8 -c "import os,runpy; os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION']='python'; runpy.run_path('tests/builder/test_reader_fixes.py', run_name='__main__')"
```

Thay đường dẫn bằng test cần chạy. Đây là workaround kiểm tra, chưa phải xác nhận
môi trường mặc định chạy tốt. Không chạy build/eval/export trong bước A.

## Chạy

**1. Dựng hạ tầng.** Cần Docker Desktop đang chạy. Máy mới, chưa từng dựng:

```
docker compose -f docker/docker-compose-west.yml up -d
```

**Máy đã có dữ liệu:** kiểm tra container và mount trước khi dùng compose:

```powershell
docker ps -a --filter name=release-openspg
docker inspect release-openspg-neo4j --format '{{json .Mounts}}'
docker compose -f docker/docker-compose-west.yml config --volumes
```

Đối chiếu mount có `Destination=/data` (Type, Name, Source) với compose.
Volume có thể có tên, ẩn danh hoặc là bind mount; không suy từ trạng thái máy khác.
Nếu container cũ còn giữ đúng dữ liệu, bật lại bằng:

```
docker start release-openspg-neo4j release-openspg-server release-openspg-mysql release-openspg-minio
```

Sao lưu trước khi thay container/mount. Không chạy `down -v`, `volume prune`
hoặc tạo lại container khi chưa xác định nơi chứa dữ liệu.
`docker/xuat-do-thi.ps1` xuất `dist/legal.dump` (đã ignore), từ volume thực tế,
tạm dừng/bật lại Neo4j và từ chối ghi đè dump không rỗng. Script không hỗ trợ
bind mount tại `/data`; không chạy export trong bước kiểm tra source.

Mở `http://127.0.0.1:8887`, đăng nhập `openspg` / `openspg@kag`. Thấy giao diện
để kiểm tra dịch vụ; dữ liệu hiển thị phụ thuộc project/database hiện có.

**2. Cài KAG.** Python 3.10 trở lên. Cài dependency theo requirements của vendor.
Không suy phiên bản đang cài từ file yêu cầu: xem lưu ý protobuf ở mục kiểm tra source.

```
py -m venv .venv
```

```
.venv/Scripts/pip install -r requirements.txt
```

`requirements.txt` cài KAG thẳng từ `vendor/KAG` trong repo, không tải gì từ
GitHub, không trỏ vào thư mục nào trên máy ai cả. Nhờ vậy clone xong là cài được
dù máy không có mạng ra GitHub.

Ba lỗi của KAG 0.8.0 từng phải sửa thẳng trong mã nguồn thư viện — nay nằm trong
`kag/builder/extractor.py` và `kag/builder/chain.py` dưới dạng lớp con, nên
`vendor/KAG` **không** chứa bản vá đó. Trong hai file cấu hình đã đối chiếu với upstream `fdab15b3`, vendor thêm
chú thích và `encoding="utf-8"` vào lời gọi
`open()` đọc file cấu hình:

```
vendor/KAG/kag/common/conf.py
vendor/KAG/knext/common/env.py
```

Hai dòng đó là thứ cho phép `kag_config.yaml` viết tiếng Việt có dấu (xem bước 3).

Kiểm một câu, không tốn tiền LLM — cần hạ tầng ở bước 1 đã chạy:

```bash
.venv/Scripts/python.exe -X utf8 tests/builder/test_builder_fixes.py
```

Bản KAG trong `.venv` là bản **thực sự được import**, `vendor/KAG` chỉ là nguồn
cài. Sửa `vendor/KAG` xong phải cài lại (`pip install -r requirements.txt`) thì
thay đổi mới có tác dụng; `pip install ./vendor/KAG` cũng được nhưng đừng viết
`openspg-kag @ ./vendor/KAG` — pip 25.0.1 hiểu `./vendor/KAG` là URL và báo
`Invalid URL ... No scheme supplied`.

**3. Điền API key** trong `kag/kag_config.yaml`. `openie_llm` và `chat_llm`
là model sinh chữ; `vectorize_model` là model embedding. Điền khóa và endpoint
theo dịch vụ thực tế; không mặc định gateway LLM hỗ trợ embedding. File mẫu để
khóa rỗng và URL/model placeholder; config local có thể khác.
Không in hoặc commit khóa thật. Restore có thể kiểm tra dịch vụ model.

Mẫu dùng endpoint OpenAI-compatible có đuôi `/v1`; xác nhận URL gốc theo dịch vụ
và kiểm tra riêng cả ba khối, không suy từ việc một khối đã hoạt động.

`vendor/KAG/kag/common/conf.py` và `vendor/KAG/knext/common/env.py` đã được vá
thêm `encoding="utf-8"`, nên config **viết tiếng Việt có dấu được**. Đây là chỗ
khác trước: hồi KAG còn cài từ GitHub thì hai file đó là file pip quản lý, sửa
vào là mất ở lần cài sau, nên config buộc phải thuần ASCII. Giờ chúng nằm trong
repo và đi theo repo, nên ràng buộc đó hết.

Vẫn nên giữ config thuần ASCII nếu định chạy trên máy chưa cài lại `vendor/KAG`,
vì bản KAG trong `.venv` mới là bản thực sự được import. Mọi file khác cứ có dấu
thoải mái: `.py` thì Python đọc UTF-8 mặc định, còn `.md` và `.json` thì KAG mở
có khai `encoding="utf-8"` đàng hoàng.

`kag/kag_config.yaml` bị `.gitignore` chặn nên người clone mới không có file đó,
phải tự tạo từ `kag/kag_config.example.yaml`. File mẫu để thuần ASCII, nhưng từ
giờ **không bắt buộc** nữa: cứ mở `kag_config.yaml` lên và gõ dấu tiếng Việt bình
thường, miễn là file được lưu ở UTF-8 (mọi trình soạn thảo hiện đại đều mặc định
như vậy). Không cần chạy lệnh chuyển mã nào cả.

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

Chuẩn bị JSON graph trước indexer: extractor và post-processor đều khởi tạo
`legal_external_graph` từ `data/graph/nodes.json`, `edges.json`; thiếu file sẽ lỗi.
Injection nạp thuộc tính và quan hệ metadata qua vectorizer/writer; nên nạp trước
ingestion theo cách dùng `domain_kg` upstream. Với config mẫu hiện tại,
`similarity_threshold` không đặt nên post-processor **không chạy** similarity linking
hay external-graph linking; vẫn lọc dữ liệu không hợp lệ. Hai nhánh dùng chung
`canon_id` để gặp nhau khi ghi node, không dựa vào nối mờ.

Chạy trong thư mục `kag/`, không phải thư mục gốc: KAG dò `kag_config.yaml` bằng
cách đi ngược lên cây thư mục từ chỗ đang đứng, đứng ở gốc thì không bao giờ thấy
nó và config rỗng. Hai dòng `../data/graph/*.json` trong config cũng tính theo chỗ
đứng này, nên cả ba lệnh dưới đây đều chạy ở `kag/`.

```bash
cd kag
python builder/metadata_to_graph.py
# Chỉ tiếp tục nếu lệnh trên thành công.
python builder/injection.py
```

**6. Dựng đồ thị.** Vẫn đứng ở `kag/`. Lệnh này đọc 23 văn bản tiếng Việt trong
`data/processed/`.

Indexer nhận **thư mục** qua đối số đầu tiên; không cần sửa source.
`data/trial/` hiện có bốn Markdown. Muốn thử đúng một file, chuẩn bị một thư mục
riêng chứa bản sao file đó, rồi truyền đường dẫn thư mục:

```powershell
# Đứng ở kag/, đã kích hoạt .venv
python builder/indexer.py ../data/trial
# Hoặc thư mục thử do bạn chuẩn bị:
python builder/indexer.py <thu-muc-chua-mot-file-md>
# Toàn bộ corpus, chỉ chạy khi chủ động muốn ingestion:
python builder/indexer.py
```

Các lệnh này gọi LLM/embedding và ghi graph. Không chạy để kiểm tra source.
Giữ `kag/ckpt/`: xóa checkpoint có thể khiến chạy lại và phát sinh chi phí.
Checkpoint cũ không chứng minh graph khớp corpus/prompt hiện tại; sao lưu và đánh giá
trước khi tái sử dụng hoặc rebuild. Ctrl+C dừng hợp tác; request đang chạy cần
kết thúc/timeout, không bảo đảm dừng ngay. Log thành công không bảo đảm mọi chunk
được ghi vì chain có thể bỏ chunk lỗi.

Kiểm ngay trên giao diện web: văn bản vừa nạp phải là **một** node mang cả trạng
thái hiệu lực lẫn cạnh về chunk. Thấy hai node rời nhau nghĩa là id chưa trùng,
xem `canon_id.py` — hàm `canon_id` là quy tắc id duy nhất, `metadata_to_graph.py`
và bản vá `SubGraph.add_node` trong `builder/__init__.py` cùng gọi nó.

**7. Hỏi.** Bộ câu hỏi nằm ở `kag/solver/data/questions_mo_rong.json` (166 câu).
`eval.py` trỏ vào file đó ở hàm `load_data`. Chạy trong thư mục `solver/`.

```bash
python eval.py
```

Bốn file ra, trong thư mục `runs/`:

| File | Có gì |
| --- | --- |
| `legal_res_<timestamp>.json` | **Câu trả lời thật**, ở trường `prediction`, kèm `traceLog` cho biết lấy chunk nào ra để trả lời |
| `benchmark.txt` | Một dòng metric tổng, mở ở chế độ nối thêm nên mỗi lần chạy đẻ thêm một dòng. `processNum` là **số câu qua được**, không phải điểm — bằng `0` nghĩa là hỏng |
| `legal_metrics_<timestamp>.json` | Cùng nội dung `benchmark.txt` nhưng ở dạng JSON |
| `legal_ckpt/` | Sổ nhớ, khoá là nguyên văn câu hỏi. Hỏi lại y hệt thì trả bài cũ, không gọi mô hình. Muốn hỏi lại thật thì xoá thư mục này |

`main()` hiện để `thread_num=8` và `upper_limit=166`, mặc định chạy cả bộ.
Mốc 45 phút ở mục 12 là snapshot lịch sử, không phải thời gian bảo đảm.

Log INFO trên stderr không tự làm tiến trình thất bại. Nếu exit code khác 0,
kiểm tra exception/log và đối chiếu `processNum`; không mặc định coi là thành công.

Muốn có log để xem lại thì dùng `Tee-Object` (chạy trần thì không có file log nào):

```powershell
..\..\.venv\Scripts\python.exe -u eval.py 2>&1 | Tee-Object -FilePath ..\..\runs.log
```

**Nếu hai câu bị loại khỏi kết quả** (`processNum` ra 164 thay vì 166) thì đó là
timeout của `kg_fr_retriever`, không phải bug — câu hỏi về hiệu lực văn bản có thể
mất hơn 150 giây cho PageRank. Cứ chạy lại, hai câu đó không nằm trong cache nên sẽ
được thử lại. Chi tiết ở mục 12.

**Lưu ý về cache:** `legal_ckpt` chỉ chặn được lời gọi sinh chữ, **không** chặn
embedding. Chạy lại khi cache đã đầy vẫn tốn tiền, chỉ ít hơn. Xem mục 12.


`answers` là **danh sách các mốc phải xuất hiện trong câu trả lời** (số tiền, số
điều). `do_metrics_eval` so khớp bằng substring rồi trả `hit_rate` cùng `hit_all`.
Để nguyên chuỗi placeholder `<...>` thì nó bị lọc bỏ và không có điểm nào được tính.

Hàm `norm_text` ở đầu `eval.py` chuẩn hoá trước khi so khớp, làm ba việc: đưa về
NFC (tiếng Việt có hai cách mã hoá cùng một chữ), bỏ ký tự markdown, bỏ dấu chấm và
khoảng trắng. **Bỏ ký tự markdown là bắt buộc**: mô hình in đậm `**chậm nhất là 24
giờ**` và ranh giới `**` rơi vào giữa mốc, không bỏ thì mốc trượt oan dù câu trả lời
đúng hoàn toàn. Đã dính thật một lần, làm `hit_all` tụt từ 1,0 xuống 0,8.

**8. Đo truy xuất và trích dẫn.** Hai script, **không gọi LLM, không tốn tiền**,
chạy lại bao nhiêu lần cũng được. Đứng ở `solver/`:

```bash
python gold_chunks.py     # sinh tập chunk vàng, chạy một lần sau mỗi lần build
python recall_report.py   # đọc runs/legal_res_*.json mới nhất rồi in báo cáo
```

`gold_chunks.py` đọc chunk đã cắt từ `kag/ckpt/LengthSplitter` (1.121 chunk trong snapshot lịch sử;
không phải số đo lại trên corpus hiện tại), rồi tra ngược từng mốc trong `answers`
ra chunk chứa nó. Ghi ra hai file:

| File | Nghĩa |
| --- | --- |
| `data/gold_chunks.json` | Mọi chunk chứa bất kỳ mốc nào. Dùng cho `recall` |
| `data/gold_chunks_hep.json` | Tối đa 3 chunk/câu, lấy từ mốc **đặc trưng nhất**. Dùng cho `hit@k` và trích dẫn |

Bản hẹp cần thiết vì mốc là **cụm từ**, không phải định danh chunk: mốc `đánh giá sự
phù hợp` xuất hiện ở 25 chunk, gộp hết lại thì mẫu số phồng lên và mọi chỉ số bị đo
thấp giả tạo. Script tự bỏ mốc quá ngắn (tên mục lục như `Điều 45`) và quá chung
(`Chính phủ` ở 310 chunk).

`recall_report.py` in ra `hit@1/3/5/10/20`, `recall`, `MRR`, `nDCG@10`, và
`citation precision` / `citation recall` — tức trong các nguồn câu trả lời dẫn ra,
bao nhiêu thật sự chứa đáp án. Đây là chỗ làm sống lại `hit3`/`hit5`/`hitall` trong
`benchmark.txt`: ba chỉ số đó luôn bằng 0 vì lớp cha `do_recall_eval` trả
`{"recall": None}`, chứ không phải vì hệ thống hỏng.

Nó còn in hai danh sách đáng đọc: **12 câu khó nhất** (chunk vàng hoàn toàn không
được lấy về) và **12 câu dẫn sai nhiều nhất**. Mỗi dòng có nhãn nhóm câu hỏi
(`A-che-tai`, `F-thuat-ngu`, `B-dieu-van-ban`, `GOC`) — nhìn nhãn sẽ thấy hệ thống
hỏng **có hệ thống theo nhóm**, yếu ở câu hỏi định nghĩa và chế tài. Chi tiết ở mục 12.


**9. Bẫy trùng tên gói `prompt` (đã sửa).** `import_modules_from_path` trong
`vendor/KAG/kag/common/registry/utils.py:44` lấy **tên thư mục cuối** làm tên module.
`kag/solver/prompt` và `kag/builder/prompt` cùng tên `prompt`, nên lần gọi thứ hai bị
`sys.modules["prompt"]` chặn và trả về module cũ: `legal_std`, `legal_ner`,
`legal_triple` **không bao giờ được đăng ký**, `PromptABC` lặng lẽ rơi về bản tiếng Anh
`default_std` và chỉ ghi một dòng log INFO rất khó thấy.

`eval.py` vì vậy **không** dùng `import_modules_from_path` cho thư mục đó nữa, mà gọi
`_nap_prompt_theo_duong_dan()` — nạp thẳng từng file bằng
`importlib.util.spec_from_file_location` dưới tên riêng, không đụng
`sys.modules["prompt"]`. Đã đo lại: `std` → `LegalEntityStandardizationPrompt`,
`triple` → `LegalTriplePrompt`, `question_ner` → `LegalQuestionNERPrompt`.

**10. Prompt NER cho câu hỏi (đã viết, nhưng đang TẮT — xem mục 11).**
`kag/solver/prompt/question_ner.py` đăng ký `legal_question_ner_tat` — bản đối ứng
tiếng Việt của `default_question_ner` (bản gốc chỉ có ví dụ về tạp chí Mỹ). Khác với
`kag/builder/prompt/ner.py` chạy lúc build và đọc cả đoạn văn luật, file này chỉ nhận
**một câu hỏi ngắn** và rút ra vài cái tên làm điểm xuất phát cho PageRank.

Hậu tố `_tat` là cố ý: `init_prompt_with_fallback` tìm `legal_question_ner` không
thấy nên rơi về bản tiếng Anh. Muốn bật lại thì bỏ `_tat`.

Hai điều rút ra từ chính mã nguồn đang chạy, đừng sửa nhầm:

- **`category` không dùng để tra đồ thị.** `ppr_chunk_retriever.py:227-244` tìm node
  bằng **vector trên `entity_name`**, rồi dòng 242 ghi đè `type` bằng nhãn thật đọc từ
  `__labels__` của Neo4j. Nên thứ quyết định kết quả là `name`, không phải `category`.
- **Schema phải lấy qua `ReasonerClient.get_reason_schema()`**, không phải
  `SchemaClient.load()` như bên builder. Tên trả về có tiền tố (`Legal.Article`) nên
  phải cắt tiền tố trước khi nhúng vào template.
- Ở đường này `with_semantic` mặc định `False` (`ppr_chunk_retriever.py:63` không
  truyền), nên `std_prompt` **không được gọi**. Nó vẫn được nạp cho đúng, nhưng đừng
  trông vào nó để thấy khác biệt khi chạy eval.

**11. Snapshot lịch sử — đã đo tác động của prompt NER tiếng Việt (5 câu, ba lần chạy).** Kết quả
**ngược với dự đoán ban đầu**, ghi lại để lần sau khỏi suy diễn lại:

| Chỉ số (gold hẹp) | Prompt Anh | Việt, tối đa 6 | Việt, bỏ giới hạn |
| --- | --- | --- | --- |
| `hit@1` | **0.600** | 0.200 | 0.200 |
| `hit@3` | **0.800** | 0.600 | 0.600 |
| `MRR` | **0.711** | 0.461 | 0.461 |
| `hit@20` | 1.000 | 1.000 | 1.000 |
| `citation precision` (đầy đủ) | 0.581 | **0.686** | 0.567 |
| `nDCG@10` (đầy đủ) | **0.514** | 0.411 | 0.412 |

Ba điều đọc ra được:

1. `hit@20` luôn 1.000 ở cả ba lần — chunk đúng **chưa bao giờ mất**, chỉ bị đẩy
   xuống hạng thấp hơn. `hit_rate` cuối cùng cũng luôn 1.0, nên nhìn `benchmark.txt`
   sẽ không thấy khác biệt gì.
2. Bản tiếng Việt xếp hạng **kém hơn** nhưng dẫn nguồn **chính xác hơn**. Đây là
   đánh đổi thật, không phải nhiễu.
3. Bỏ giới hạn "tối đa 6 thực thể" **không cải thiện gì** — mọi chỉ số giữ nguyên
   (số thực thể có tăng, có câu lên 10, nhưng thứ hạng không đổi). Nguyên nhân nằm
   chỗ khác, không phải ở số lượng.

Chi phí ba lần gần như bằng nhau (51/53/53 request, 647.680/633.599/646.791 token),
nên prompt tiếng Việt **không đắt hơn**. Giới hạn 6 thực thể ban đầu là một suy luận
sai của người viết: cái làm loãng PageRank là thực thể **chung chung** khớp hàng trăm
node, chứ không phải **số lượng** thực thể.

**Quyết định (đã chốt): tắt prompt NER tiếng Việt, dùng lại bản tiếng Anh.** Vì
`hit@k` và `MRR` là chỉ số chính của bước truy hồi, mà bản Anh thắng ở cả ba.

Cách tắt: `@PromptABC.register("legal_question_ner_tat")` — thêm hậu tố `_tat` để
`init_prompt_with_fallback` không tìm thấy tên `legal_question_ner` nữa và rơi về
`default_question_ner`. **Không xoá file**: code còn nguyên, muốn bật lại chỉ cần bỏ
hậu tố `_tat` khỏi chuỗi đăng ký.

Lưu ý `legal_std` và `legal_triple` **vẫn đang bật** — chúng chạy lúc build nên
không ảnh hưởng gì tới eval (đường eval có `with_semantic=False`, xem mục 10).

⚠️ **Ba kết luận trên đo trên 5 câu, và mục 12 cho thấy chúng không đứng vững ở
mẫu lớn.** Đọc mục 12 trước khi trích dẫn bất cứ con số nào ở mục này. Riêng quyết
định tắt prompt tiếng Việt thì vẫn giữ, nhưng lý do không còn là "bản Anh thắng" —
xem mục 12.

**12. Snapshot lịch sử — chạy trọn 166 câu.**
Các số dưới đây không được đo lại trên source/corpus hiện tại trong bước A. Mục 11 đo trên 5 câu vì
`eval.py` để `upper_limit=5`. Đổi thành `166` rồi chạy hết, mất **45 phút**, và kết
quả khác hẳn:

| Chỉ số | 5 câu (mục 11) | **166 câu** |
| --- | --- | --- |
| `hit@1` (hẹp) | 0.600 | **0.295** |
| `hit@3` | 0.800 | **0.530** |
| `hit@5` | 1.000 | **0.620** |
| `hit@10` | 1.000 | **0.735** |
| `hit@20` | 1.000 | **0.861** |
| `MRR` (hẹp) | 0.711 | **0.448** |
| `nDCG@10` (đầy đủ) | 0.514 | **0.426** |
| `recall` (đầy đủ) | 0.499 | **0.693** |
| `citation precision` (hẹp) | 0.395 | **0.520** |
| `hit_rate` | 1.000 | **0.781** |
| `hit_all` | 1.000 | **0.578** |

Ba điều phải sửa lại so với mục 11:

1. **`hit@20` KHÔNG phải 1.000.** Ở mẫu lớn là **0.861**, tức **13,9% số câu mất
   chunk vàng hoàn toàn** — không phải "chỉ bị xếp thấp hơn" như mục 11 viết. Kết
   luận đó sai vì 5 câu quá ít để lộ ra ca trượt hẳn.
2. **`hit_all` rơi từ 1.0 xuống 0.578.** 5 câu đầu tình cờ dễ. Mọi con số ở mục 11
   đều lạc quan hơn thực tế.
3. **`citation precision` lại TĂNG** (0.395 → 0.520). Xu hướng ngược với `hit@k`:
   hệ thống dẫn nguồn chính xác hơn nhưng xếp hạng kém hơn.

**Quyết định tắt prompt NER tiếng Việt (mục 11) vẫn giữ, nhưng đổi lý do.** Lý do cũ
là "bản Anh thắng ở cả ba chỉ số" — đo trên 5 câu, không đủ tin. Lý do đúng để giữ
nguyên trạng: **166 câu đã chạy xong bằng bản tiếng Anh, và đó là bộ số liệu dùng cho
báo cáo.** Đổi prompt bây giờ thì phải chạy lại 166 câu (45 phút, tốn tiền) mới so
sánh được, mà lợi ích chưa chứng minh. Muốn đổi thì chạy lại trọn bộ rồi so.

**Phân loại câu hỏi — chỗ này mới là phát hiện đáng dùng.** `recall_report.py` in ra
câu hỏi có nhãn nhóm, và mô hình **hỏng có hệ thống theo nhóm**, không ngẫu nhiên:

| Nhóm | Nghĩa | Tình trạng |
| --- | --- | --- |
| `F-thuat-ngu` | Hỏi định nghĩa thuật ngữ | **Hỏng nặng nhất** — có câu `gold 1 | lấy 30 | dẫn 0 đúng` |
| `A-che-tai` | Hỏi chế tài, mức phạt | **Hỏng nặng** — `gold 3 | lấy 31 | dẫn 0 đúng` |
| `B-dieu-van-ban` | Hỏi kết cấu điều văn bản | Trung bình |
| `GOC` | 4 câu gốc | Câu AI rủi ro cao: `gold 25`, dẫn 6 nguồn chỉ 3 đúng |

Đọc được thành một câu cho báo cáo: **hệ thống yếu ở câu hỏi định nghĩa và chế tài,
mạnh ở câu hỏi tra điều khoản cụ thể.** Đây là hạn chế có thể đo và giải thích, hơn
là một con số tổng.

**Hai câu bị hỏng lần chạy đầu (164/166) — nguyên nhân là timeout, không phải bug.**
Câu [10] (hiệu lực Luật ANM 2018) và [11] (thời hạn gỡ bỏ thông tin) bị loại khỏi kết
quả. Log lần chạy lại cho thấy:

```
Retriever kg_fr_retriever executed in 158.28 seconds
```

Câu hỏi về **hiệu lực văn bản** kéo PageRank trên node `LegalDocument`, nơi tập trung
nhiều cạnh nhất, nên vượt giới hạn thời gian. Chạy lại thì qua và trả lời đúng hoàn
toàn. **Không cần sửa gì**, nhưng đây là hành vi không tất định — chạy lại 166 câu vẫn
có thể hỏng lại đúng hai câu đó.

**Về chi phí — cache KHÔNG miễn phí hoàn toàn.** Điều này dễ hiểu nhầm:

- `legal_ckpt` chỉ cache **câu trả lời cuối** (khoá là nguyên văn câu hỏi), tức chỉ
  chặn được lời gọi `chat/completions`.
- Phần **embedding không có cache**, chạy đủ mỗi lần. Log cho thấy tỉ lệ thật khoảng
  **10 lần `/v1/embeddings` : 1 lần `/v1/chat/completions`** — có câu hỏi gọi hơn 40
  lần embedding trong 52 giây.
- Nên chạy lại khi cache đã đầy vẫn **tốn tiền**, chỉ là tốn ít hơn. Muốn biết tốn bao
  nhiêu thì nhìn bảng "Lịch sử sử dụng LLM" của gateway: dòng `Embeddings` là phần
  không tránh được.

Chạy lại để lấy đủ 166 câu (sau khi 164 câu đã có cache) chỉ mất **3 phút 48 giây** vì
164 câu kia không chạy lại PageRank — chênh lệch 45 phút so với 3,8 phút là toàn bộ
chi phí truy hồi, không phải chi phí sinh chữ.



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
