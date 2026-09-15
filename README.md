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
├── raw/           bản gốc pdf, docx, html, 47MB, có trong git để dựng lại processed
├── metadata/      27 file json mô tả từng văn bản
├── README.md    quy tắc đặt tên và cấu trúc dữ liệu
└── SOURCES.md   danh sách nguồn đã thẩm định
```

**Mã nguồn KAG nằm trong repo này, ở `vendor/KAG/`**, ghim đúng commit `fdab15b3`
của OpenSPG/KAG. Thư mục `kag/` chỉ chứa cấu hình, schema, prompt và script của
dự án, không chứa mã của chính thư viện.

`vendor/KAG/` là cây mã nguồn trần: 1211 file, 170 MB, **đã gỡ `.git`**. Bản gốc
kèm lịch sử git nặng 360 MB; phần lịch sử 187 MB đó không cần thiết vì repo này
ghim cứng một commit duy nhất. Đừng `git add` một thư mục `vendor/KAG/` có `.git`
bên trong — git sẽ tạo gitlink rỗng, người clone về thấy thư mục trống mà git
không báo lỗi gì.

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
│   ├── extractor.py       vá 3 lỗi extractor của KAG 0.8.0 bằng lớp con
│   ├── chain.py           một chunk hỏng không kéo cả văn bản theo
│   ├── canon_id.py        quy tắc id node, dùng chung cho cả hai đường nạp
│   ├── test_builder_fixes.py  kiểm 5 bản vá, in 10 dòng OK, không gọi LLM
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

**1. Dựng hạ tầng.** Cần Docker Desktop đang chạy. Máy mới, chưa từng dựng:

```
docker compose -f docker/docker-compose-west.yml up -d
```

⚠️ **Lệnh trên chỉ dùng cho máy chưa có container `release-openspg-*` nào.** Máy
đang giữ đồ thị 12625 node trong một volume **ẩn danh**, trong khi compose khai
volume có tên `kag-legal-neo4j-data` đang rỗng. `docker compose up -d` sẽ tạo lại
container gắn vào volume rỗng và bỏ rơi volume ẩn danh — chạy lệnh đó trên máy
này là mất đồ thị.

Muốn dựng lại đồ thị từ đầu thì nạp `dist/legal.dump`, đừng compose lại.

Đồ thị đang chạy thì bật lại bằng:

```
docker start release-openspg-neo4j release-openspg-server release-openspg-mysql release-openspg-minio
```

Tuyệt đối **không** `docker compose up -d`, không `docker compose down`, không
`docker volume prune` trên máy này.

Mở `http://127.0.0.1:8887`, đăng nhập `openspg` / `openspg@kag`. Thấy giao diện
là xong bước này. Giao diện sẽ trống, đúng như vậy.

**2. Cài KAG.** Python 3.10 trở lên. KAG ghim `protobuf==3.20.1`, nghe như phải
dùng đúng 3.10, nhưng không: `.venv` của dự án đang chạy Python 3.12.10 với đúng
protobuf 3.20.1, cài sạch không cần cờ gì thêm.

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
`vendor/KAG` **không** chứa bản vá đó. Đổi lại, `vendor/KAG` có đúng hai dòng sửa
so với upstream `fdab15b3`, cả hai chỉ thêm `encoding="utf-8"` vào lời gọi
`open()` đọc file cấu hình:

```
vendor/KAG/kag/common/conf.py
vendor/KAG/knext/common/env.py
```

Hai dòng đó là thứ cho phép `kag_config.yaml` viết tiếng Việt có dấu (xem bước 3).

Kiểm một câu, không tốn tiền LLM — cần hạ tầng ở bước 1 đã chạy:

```bash
cd kag;
 ..\.venv\Scripts\python.exe builder\test_builder_fixes.py
```

Bản KAG trong `.venv` là bản **thực sự được import**, `vendor/KAG` chỉ là nguồn
cài. Sửa `vendor/KAG` xong phải cài lại (`pip install -r requirements.txt`) thì
thay đổi mới có tác dụng; `pip install ./vendor/KAG` cũng được nhưng đừng viết
`openspg-kag @ ./vendor/KAG` — pip 25.0.1 hiểu `./vendor/KAG` là URL và báo
`Invalid URL ... No scheme supplied`.

**3. Điền API key** trong `kag/kag_config.yaml`. Ba khối, hai khoá: `openie_llm`
và `chat_llm` là model sinh chữ và dùng chung một khoá, `vectorize_model` là model
nhúng vector và phải là khoá của gateway khác — gateway LLM thường trả 403 cho
endpoint embedding. Cả ba đang để `api_key: key`, là chỗ điền tạm. Thiếu key vector
thì bước 4 dừng ngay.

`base_url` của cả ba khối **phải có đuôi `/v1`**. SDK của OpenAI nối thẳng
`base_url` với `/chat/completions`, nên thiếu `/v1` là `404` — và nó nổ ở bước 7
chứ không nổ ở bước 6, vì hai bước dùng hai khối khác nhau. Viết đúng `openie_llm`
là đủ để tin nhầm rằng `chat_llm` cũng đúng.

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

⚠️ **Không chạy lệnh này để dựng lại đồ thị.** Nó tốn khoảng 4 tiếng và tiền gọi
LLM cho 1121 chunk, trong khi đồ thị 12625 node đã dựng xong rồi. Chỉ chạy khi
thực sự muốn dựng mới từ `data/processed/`, và nhớ `kag/ckpt/` là sổ nhớ 1121
chunk đã dựng — xoá nó là mất hết, phải trả tiền lại từ đầu.

```
cd kag
python builder/indexer.py
```

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

`main()` đang để `thread_num=8`. `upper_limit=5` nên chỉ chạy 5 câu đầu — đổi thành
`upper_limit=166` khi muốn chạy hết.

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

`gold_chunks.py` đọc chunk đã cắt từ `kag/ckpt/LengthSplitter` (1.121 chunk — nguồn
chân lý, không phải đoán lại thuật toán cắt), rồi tra ngược từng mốc trong `answers`
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

**11. Đã đo tác động của prompt NER tiếng Việt (5 câu, ba lần chạy).** Kết quả
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

Nhắc lại cho người đọc sau: **5 câu là mẫu quá nhỏ**. Chênh lệch `hit@1` 0,6 so với
0,2 chỉ là **2 câu trên 5**. Kết luận trên đủ để chọn mặc định, **không** đủ để nói
bản Việt kém thật. Muốn chắc phải chạy 40-50 câu (~430 request, ~1 giờ).


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
