"""
dail_preprocess.py — jalankan preprocessing DAIL-SQL sekali, hasilnya ke data/dail/.

Kode DAIL asli (external/dail_sql/) tidak diubah. Script ini menjalankan ulang isi
schema_linking_producer() di data_preprocess.py DAIL baris per baris dengan kelas DAIL yang sama
(load_tables, SpiderEncoderV2Preproc, compute_schema_linking, compute_cell_value_linking), dan satu
penggantian:

  GloVe(kind='42B', lemmatize=True) -> CoreNLPTokenizer (di bawah).

Alasannya, dari kode DAIL sendiri: SpiderEncoderV2Preproc hanya memanggil word_emb.tokenize() dan
word_emb.tokenize_for_copying() (utils/linking_process.py; vocab builder-nya dikomentari), dan kedua
method GloVe itu hanya memanggil CoreNLP (tokenize, ssplit, lemma). Vektor GloVe tidak pernah dibaca.
CoreNLPTokenizer menyalin kedua method itu apa adanya tanpa memuat vektor, jadi hasil linking sama,
tapi torchtext dan unduhan GloVe ~5 GB tidak dibutuhkan. Lihat IMPLEMENTATION_DECISIONS.md poin 44.

Langkah:
  1. Gabungkan train_spider.json + train_others.json -> data/dail/train_spider_and_others.json
     (sama dengan data_preprocess.py baris 114-124: pool contoh DAIL = kedua split train).
  2. Schema linking dev + train -> data/dail/enc/{test,train}_schema-linking.jsonl
  3. Cek jumlah baris linking = jumlah pertanyaan (DAIL mencocokkannya per posisi).

Kebutuhan: Java (dipasang lewat apt-get kalau belum ada), Stanford CoreNLP 3.9.2 = rilis 2018-10-05
(jar diunduh otomatis dari Maven Central, ~370 MB, ke --cache-dir kalau CORENLP_HOME belum ada), paket pip `stanford-corenlp`.
Di Kaggle cukup dipanggil dari notebooks/eval_dail.ipynb (otomatis kalau data/dail/ belum ada).

    python src/experiments/dail_preprocess.py --spider-dir data/spider_data --out-dir data/dail

Kode custom skripsi; lihat context/IMPLEMENTATION_DECISIONS.md poin 43 dan 44.
"""

import os

# corenlp-protobuf (dependensi stanford-corenlp) dibuat dengan protoc lama; protobuf >= 4 menolak
# memuatnya kecuali memakai implementasi Python. Harus di-set sebelum protobuf di-import.
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import argparse
import functools
import json
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAIN_SPLITS = ("train_spider.json", "train_others.json")
TRAIN_FILE = "train_spider_and_others.json"
# CoreNLP 3.9.2 = rilis stanford-corenlp-full-2018-10-05 yang diminta DAIL. Diambil dari Maven Central
# (jar CoreNLP, model, dan dependensinya), karena nlp.stanford.edu tidak bisa dijangkau dari Kaggle
# ("No route to host"). CoreNLPClient hanya butuh folder berisi jar-jar ini (java -cp "$CORENLP_HOME/*").
CORENLP_NAME = "stanford-corenlp-3.9.2-maven"
MAVEN_MIRRORS = ("https://repo1.maven.org/maven2", "https://repo.maven.apache.org/maven2")
CORENLP_JARS = [  # (group, artifact, version, classifier); daftar dari `mvn dependency:list` CoreNLP 3.9.2
    ("edu.stanford.nlp", "stanford-corenlp", "3.9.2", ""),
    ("edu.stanford.nlp", "stanford-corenlp", "3.9.2", "models"),
    ("com.apple", "AppleJavaExtensions", "1.4", ""),
    ("de.jollyday", "jollyday", "0.4.9", ""),
    ("org.apache.commons", "commons-lang3", "3.3.1", ""),
    ("org.apache.lucene", "lucene-queryparser", "4.10.3", ""),
    ("org.apache.lucene", "lucene-sandbox", "4.10.3", ""),
    ("org.apache.lucene", "lucene-analyzers-common", "4.10.3", ""),
    ("org.apache.lucene", "lucene-queries", "4.10.3", ""),
    ("org.apache.lucene", "lucene-core", "4.10.3", ""),
    ("javax.servlet", "javax.servlet-api", "3.0.1", ""),
    ("com.io7m.xom", "xom", "1.2.10", ""),
    ("xml-apis", "xml-apis", "1.3.03", ""),
    ("xerces", "xercesImpl", "2.8.0", ""),
    ("xalan", "xalan", "2.7.0", ""),
    ("joda-time", "joda-time", "2.9.4", ""),
    ("com.googlecode.efficient-java-matrix-library", "ejml", "0.23", ""),
    ("org.glassfish", "javax.json", "1.0.4", ""),
    ("org.slf4j", "slf4j-api", "1.7.12", ""),
    ("com.google.protobuf", "protobuf-java", "3.2.0", ""),
    ("javax.activation", "javax.activation-api", "1.2.0", ""),
    ("javax.xml.bind", "jaxb-api", "2.4.0-b180830.0359", ""),
    ("com.sun.xml.bind", "jaxb-core", "2.3.0.1", ""),
    ("com.sun.xml.bind", "jaxb-impl", "2.4.0-b180830.0438", ""),
]


def merge_train(spider_dir: Path, out_dir: Path) -> Path:
    """Langkah 1: sama dengan data_preprocess.py DAIL, tapi ditulis ke out_dir."""
    total = []
    for split in TRAIN_SPLITS:
        total += json.loads((spider_dir / split).read_text(encoding="utf-8"))
    out = out_dir / TRAIN_FILE
    out.write_text(json.dumps(total), encoding="utf-8")
    print(f"Train gabungan: {len(total)} pertanyaan -> {out}")
    return out


def count_lines(path: Path) -> int:
    with open(path, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def ensure_java() -> None:
    """CoreNLP adalah server Java. Kaggle biasanya belum punya Java, jadi pasang lewat apt-get."""
    if shutil.which("java"):
        return
    print("Java belum ada, memasang lewat apt-get ...")
    subprocess.run("apt-get update -qq && apt-get install -y -qq default-jre-headless > /dev/null",
                   shell=True, check=True)
    if not shutil.which("java"):
        raise RuntimeError("Java tetap tidak ditemukan setelah apt-get. Pasang Java manual lalu ulangi.")


def download(path: str, target: Path, attempts: int = 5) -> None:
    """Unduh satu jar dari Maven Central; coba lagi dengan jeda (Maven kadang membalas 429) dan mirror kedua."""
    partial = target.with_suffix(".part")
    for attempt in range(attempts):
        for mirror in MAVEN_MIRRORS:
            try:
                urllib.request.urlretrieve(f"{mirror}/{path}", partial)
                partial.rename(target)
                return
            except OSError as e:  # URLError/HTTPError turunan OSError
                error = e
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Gagal mengunduh {path}: {error}")


def ensure_corenlp(cache_dir: Path) -> Path:
    """Pakai CORENLP_HOME kalau sudah di-set; kalau belum, unduh jar CoreNLP 3.9.2 (= 2018-10-05) ke cache_dir."""
    if os.environ.get("CORENLP_HOME"):
        home = Path(os.environ["CORENLP_HOME"])
        if not home.is_dir():
            raise FileNotFoundError(f"CORENLP_HOME={home} tidak ada")
        return home
    home = cache_dir / CORENLP_NAME
    home.mkdir(parents=True, exist_ok=True)
    print(f"Mengunduh CoreNLP 3.9.2 dari Maven Central (~370 MB) ke {home} ...")
    for group, artifact, version, classifier in CORENLP_JARS:
        name = f"{artifact}-{version}{'-' + classifier if classifier else ''}.jar"
        target = home / name
        if target.exists():
            continue
        download(f"{group.replace('.', '/')}/{artifact}/{version}/{name}", target)
    os.environ["CORENLP_HOME"] = str(home)
    return home


class CoreNLPTokenizer:
    """
    Pengganti GloVe(kind='42B', lemmatize=True) dari utils/pretrained_embeddings.py DAIL: isi
    tokenize() dan tokenize_for_copying() disalin persis, tanpa memuat vektor GloVe (tidak dipakai
    SpiderEncoderV2Preproc). annotate() yang dipanggil adalah milik DAIL (utils/linking_utils/corenlp.py).
    """

    def __init__(self, annotate):
        self.annotate = annotate
        self.corenlp_annotators = ["tokenize", "ssplit", "lemma"]

    @functools.lru_cache(maxsize=1024)
    def tokenize(self, text):
        ann = self.annotate(text, self.corenlp_annotators)
        return [tok.lemma.lower() for sent in ann.sentence for tok in sent.token]

    @functools.lru_cache(maxsize=1024)
    def tokenize_for_copying(self, text):
        ann = self.annotate(text, self.corenlp_annotators)
        text_for_copying = [tok.originalText.lower() for sent in ann.sentence for tok in sent.token]
        text = [tok.lemma.lower() for sent in ann.sentence for tok in sent.token]
        return text, text_for_copying


class CachedConnection:
    """
    Salinan DB di memori (seperti DAIL) yang mengingat hasil tiap query. compute_cell_value_linking()
    DAIL menjalankan query LIKE (scan seluruh tabel) untuk setiap kata x setiap kolom, dan kata yang
    sama berulang di banyak pertanyaan pada DB yang sama. DB tidak pernah berubah, jadi hasil query
    yang sama selalu sama: cache tidak mengubah hasil, hanya menghindari scan ulang. Error query
    (mis. nama kolom yang bentrok dengan keyword SQL) juga diingat dan dilempar ulang, sehingga
    DAIL tetap menangkapnya seperti biasa.
    """

    def __init__(self, sqlite_path: Path):
        with sqlite3.connect(str(sqlite_path)) as source:
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
            source.backup(self.conn)
        self.cache = {}

    def cursor(self):
        return _CachedCursor(self)


class _CachedCursor:
    def __init__(self, owner: CachedConnection):
        self.owner, self.rows = owner, None

    def execute(self, sql):
        cache = self.owner.cache
        if sql not in cache:
            try:
                cache[sql] = (self.owner.conn.cursor().execute(sql).fetchall(), None)
            except Exception as e:
                cache[sql] = (None, e)
        self.rows, error = cache[sql]
        if error is not None:
            raise error
        return self

    def fetchall(self):
        return self.rows


# Diisi sebelum proses worker dibuat (fork), dibaca di worker
_CV = {"schemas": None, "db_dir": None, "fn": None, "conns": {}}


def _cell_value_link(task):
    """Worker: compute_cell_value_linking() DAIL untuk satu pertanyaan, dengan koneksi ber-cache per DB."""
    pos, db_id, tokens = task
    schema = _CV["schemas"][db_id]
    if db_id not in _CV["conns"]:
        _CV["conns"][db_id] = CachedConnection(_CV["db_dir"] / db_id / f"{db_id}.sqlite")
    schema.connection = _CV["conns"][db_id]
    return pos, _CV["fn"](tokens, schema)


def schema_linking(dev_path: Path, train_path: Path, tables_path: Path, db_dir: Path, out_dir: Path,
                   dail_dir: Path, workers: int) -> None:
    """
    Langkah 2: isi schema_linking_producer() DAIL (compute_cv_link=True), word_emb = CoreNLPTokenizer.

    preprocess_item() DAIL dijalankan dua tahap supaya bagian yang lambat bisa paralel:
      a. tokenisasi CoreNLP + sc_link + info schema: preprocess_item() dengan compute_cv_link=False
         (proses utama, satu server CoreNLP);
      b. cv_link: compute_cell_value_linking(question, schema), persis argumen yang dipakai
         preprocess_item() DAIL, di `workers` proses dengan koneksi ber-cache (CachedConnection).
    Hasil (b) dimasukkan ke field 'cv_link' tiap item, lalu item disimpan berurutan seperti
    add_item() + save() DAIL. Isi file keluaran sama dengan menjalankan schema_linking_producer().
    """
    import multiprocessing
    from tqdm import tqdm
    sys.path.insert(0, str(dail_dir.resolve()))
    from utils.datasets.spider import load_tables
    from utils.linking_process import SpiderEncoderV2Preproc
    from utils.linking_utils import corenlp
    from utils.linking_utils.spider_match_utils import compute_cell_value_linking

    test_data = json.loads(dev_path.read_text(encoding="utf-8"))
    train_data = json.loads(train_path.read_text(encoding="utf-8"))
    schemas, _ = load_tables([str(tables_path)])

    linking_processor = SpiderEncoderV2Preproc(str(out_dir),
                                               min_freq=4,
                                               max_count=5000,
                                               include_table_name_in_column=False,
                                               word_emb=CoreNLPTokenizer(corenlp.annotate),
                                               fix_issue_16_primary_keys=True,
                                               compute_sc_link=True,
                                               compute_cv_link=False)  # cv_link di tahap (b)

    # (a) tokenisasi + sc_link, berurutan
    entries = []  # (section, preprocessed item)
    for data, section in zip([test_data, train_data], ["test", "train"]):
        for item in tqdm(data, desc=f"{section} tokenize + schema linking", mininterval=30):
            schema = schemas[item["db_id"]]
            to_add, validation_info = linking_processor.validate_item(item, schema, section)
            if to_add:
                entries.append((section, linking_processor.preprocess_item(item, schema, validation_info)))

    # (b) cv_link paralel. Tugas diurutkan per DB supaya tiap worker banyak memakai ulang cache-nya.
    _CV.update(schemas=schemas, db_dir=db_dir, fn=compute_cell_value_linking, conns={})
    tasks = sorted(((pos, entry["db_id"], entry["question"]) for pos, (_, entry) in enumerate(entries)),
                   key=lambda t: (t[1], t[0]))
    print(f"Cell-value linking: {len(tasks)} pertanyaan, {workers} proses")
    with multiprocessing.get_context("fork").Pool(workers) as pool:
        for pos, cv_link in tqdm(pool.imap_unordered(_cell_value_link, tasks, chunksize=4),
                                 total=len(tasks), desc="cell-value linking", mininterval=30):
            entries[pos][1]["cv_link"] = cv_link

    for section, entry in entries:
        linking_processor.texts[section].append(entry)
    linking_processor.save()


def main() -> int:
    ap = argparse.ArgumentParser(description="Preprocessing DAIL-SQL (schema linking) untuk Spider dev + train.")
    ap.add_argument("--spider-dir", type=Path, required=True, help="Folder Spider: dev.json, tables.json, database/, train_*.json")
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "data" / "dail")
    ap.add_argument("--dail-dir", type=Path, default=REPO_ROOT / "external" / "dail_sql")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1,
                    help="Jumlah proses untuk cell-value linking (default: semua CPU)")
    ap.add_argument("--cache-dir", type=Path, default=REPO_ROOT / "data" / "dail_cache",
                    help="Tempat unduhan jar CoreNLP (~370 MB); jangan di-commit")
    args = ap.parse_args()

    spider_dir, out_dir = args.spider_dir.resolve(), args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        import corenlp  # noqa: F401  (paket pip stanford-corenlp)
    except ImportError:
        print("[ERROR] paket `stanford-corenlp` belum terpasang: pip install stanford-corenlp")
        return 1
    # spider_match_utils.py DAIL membaca stopwords nltk saat di-import
    import nltk
    try:
        nltk.corpus.stopwords.words("english")
    except LookupError:
        nltk.download("stopwords", quiet=True)
    ensure_java()
    print(f"CORENLP_HOME = {ensure_corenlp(args.cache_dir.resolve())}")

    start = time.perf_counter()
    train_path = merge_train(spider_dir, out_dir)
    schema_linking(spider_dir / "dev.json", train_path, spider_dir / "tables.json", spider_dir / "database",
                   out_dir, args.dail_dir, max(1, args.workers))

    # Langkah 3: data_builder.py DAIL memasangkan baris linking ke pertanyaan per posisi
    n_dev = len(json.loads((spider_dir / "dev.json").read_text(encoding="utf-8")))
    n_train = len(json.loads(train_path.read_text(encoding="utf-8")))
    n_test_link = count_lines(out_dir / "enc" / "test_schema-linking.jsonl")
    n_train_link = count_lines(out_dir / "enc" / "train_schema-linking.jsonl")
    print(f"dev {n_dev} / linking {n_test_link} | train {n_train} / linking {n_train_link}")
    print(f"Selesai dalam {time.perf_counter() - start:,.0f} detik -> {out_dir}")
    if (n_dev, n_train) != (n_test_link, n_train_link):
        print("[ERROR] jumlah baris linking tidak sama dengan jumlah pertanyaan")
        return 1
    # CoreNLP server (proses Java) dimatikan lewat __del__ milik DAIL saat proses selesai
    return 0


if __name__ == "__main__":
    sys.exit(main())
