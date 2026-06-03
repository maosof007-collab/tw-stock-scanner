"""
parse_report.py — 法人報告 PDF 萃取器（Claude API + Files API）

上傳 PDF 到 Anthropic Files API，用 Claude Opus 萃取：
  - 目標價（target_price）
  - 建議評等（rating）: Buy / Hold / Sell
  - 12 個月目標報酬（upside）
  - 核心論點（key_thesis）
  - 風險因素（risks）
  - 重要催化劑（catalysts）
  - 報告股票代號（tickers）

執行：
  python parse_report.py report.pdf              # 解析單一 PDF
  python parse_report.py reports/*.pdf           # 解析多個 PDF
  python parse_report.py --dir data/reports      # 解析整個目錄

輸出：data/reports/parsed_YYYYMMDD.json
"""

import sys, json, os, logging, argparse
from pathlib import Path
from datetime import datetime

import anthropic

REPORTS_DIR = Path("data/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# ────────────────────────────────────────
# 萃取 Schema
# ────────────────────────────────────────
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "tickers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "台股代碼清單（4位數字），如 ['2330', '2317']"
        },
        "company_name": {"type": "string", "description": "公司中文名稱"},
        "rating": {
            "type": "string",
            "enum": ["Buy", "Outperform", "Hold", "Underperform", "Sell", "NR"],
            "description": "投資建議評等"
        },
        "target_price": {"type": "number", "description": "12個月目標價（台幣）"},
        "current_price": {"type": "number", "description": "報告撰寫時的股價"},
        "upside_pct": {"type": "number", "description": "目標報酬率(%)，正值=上漲空間"},
        "key_thesis": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5個最重要的看多/看空理由"
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "主要風險因素"
        },
        "catalysts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "近期可能的股價催化劑（好或壞）"
        },
        "eps_estimates": {
            "type": "object",
            "description": "EPS 預估（年份→數值）",
            "additionalProperties": {"type": "number"}
        },
        "report_date": {"type": "string", "description": "報告日期 YYYY-MM-DD"},
        "institution": {"type": "string", "description": "發行機構（如摩根士丹利、花旗等）"},
        "summary": {"type": "string", "description": "100字內的報告摘要"},
    },
    "required": ["tickers", "rating", "key_thesis"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """你是專業的台股研究報告分析師。
分析法人研究報告時，請精確萃取結構化資訊，輸出為 JSON 格式。
若某欄位報告中未提及，填入 null。
所有數字請轉為純數字（不含 % 或 $ 符號）。
tickers 只填 4 位數字的台股代碼。"""


def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        cfg_path = Path("config.json")
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                key = cfg.get("anthropic_api_key", "")
            except:
                pass
    if not key:
        raise ValueError("找不到 ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=key)


def upload_pdf(client: anthropic.Anthropic, pdf_path: Path) -> str:
    """上傳 PDF 到 Files API，回傳 file_id"""
    log.info(f"  上傳 {pdf_path.name}...")
    with open(pdf_path, "rb") as f:
        result = client.beta.files.upload(
            file=(pdf_path.name, f, "application/pdf"),
        )
    log.info(f"  上傳成功：{result.id}")
    return result.id


def parse_one_report(
    client: anthropic.Anthropic,
    pdf_path: Path,
    file_id: str = None,
) -> dict:
    """
    解析單份法人報告
    file_id: 已上傳的 Files API ID（可重複使用）
    """
    # 上傳（如未提供 file_id）
    if not file_id:
        file_id = upload_pdf(client, pdf_path)

    log.info(f"  解析 {pdf_path.name}...")

    response = client.beta.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "請分析這份法人研究報告，萃取所有重要資訊，以 JSON 格式輸出：",
                },
                {
                    "type": "document",
                    "source": {"type": "file", "file_id": file_id},
                    "title": pdf_path.stem,
                },
            ],
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": EXTRACTION_SCHEMA,
            }
        },
        betas=["files-api-2025-04-14"],
    )

    # 取得結構化結果
    text = next(
        (b.text for b in response.content if b.type == "text"),
        "{}"
    )
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 嘗試從文字中提取 JSON
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        data = json.loads(m.group()) if m else {}

    data["file_id"]    = file_id
    data["source_pdf"] = str(pdf_path)
    data["parsed_at"]  = datetime.now().strftime("%Y-%m-%d %H:%M")

    log.info(
        f"  → {data.get('company_name','?')} "
        f"[{','.join(data.get('tickers',[]))}] "
        f"評等:{data.get('rating','?')} "
        f"目標價:{data.get('target_price','?')}"
    )
    return data


def parse_reports(pdf_paths: list[Path], cleanup: bool = False) -> list[dict]:
    """
    批次解析多份 PDF
    cleanup: 解析完是否刪除 Files API 的上傳檔案
    """
    client = get_client()
    results = []

    for pdf_path in pdf_paths:
        if not pdf_path.exists():
            log.warning(f"檔案不存在：{pdf_path}")
            continue
        try:
            file_id = upload_pdf(client, pdf_path)
            data = parse_one_report(client, pdf_path, file_id)
            results.append(data)
            if cleanup:
                client.beta.files.delete(file_id)
                log.info(f"  已清除 Files API 檔案：{file_id}")
        except Exception as e:
            log.error(f"解析失敗 {pdf_path}: {e}")

    # 存檔
    date_str = datetime.today().strftime("%Y%m%d")
    out = REPORTS_DIR / f"parsed_{date_str}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info(f"解析完成：{len(results)} 份報告 → {out}")
    return results


def load_latest_reports() -> list[dict]:
    """載入最新解析的法人報告"""
    jsons = sorted(REPORTS_DIR.glob("parsed_*.json"), reverse=True)
    if not jsons:
        return []
    with open(jsons[0], encoding="utf-8") as f:
        return json.load(f)


def get_ticker_report(ticker: str, reports: list[dict] = None) -> dict | None:
    """
    取得特定股票最新的法人評等
    """
    if reports is None:
        reports = load_latest_reports()
    if not reports:
        return None

    code = ticker.replace(".TW", "").replace(".TWO", "").strip()
    matches = [r for r in reports if code in (r.get("tickers") or [])]
    if not matches:
        return None

    # 回傳最新的
    return max(matches, key=lambda x: x.get("parsed_at", ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="法人報告 PDF 解析")
    parser.add_argument("pdfs",  nargs="*", help="PDF 檔案路徑")
    parser.add_argument("--dir", help="掃描整個目錄")
    parser.add_argument("--cleanup", action="store_true", help="解析後刪除上傳檔案")
    args = parser.parse_args()

    pdf_paths = []
    if args.dir:
        pdf_paths = list(Path(args.dir).glob("*.pdf"))
    elif args.pdfs:
        pdf_paths = [Path(p) for p in args.pdfs]

    if not pdf_paths:
        print("請提供 PDF 路徑，例如：python parse_report.py report.pdf")
        sys.exit(1)

    results = parse_reports(pdf_paths, cleanup=args.cleanup)
    for r in results:
        print(f"\n{'─'*50}")
        print(f"公司：{r.get('company_name')} ({','.join(r.get('tickers',[]))})")
        print(f"評等：{r.get('rating')}  目標價：{r.get('target_price')}  上漲空間：{r.get('upside_pct')}%")
        print(f"摘要：{r.get('summary','')}")
        for pt in (r.get('key_thesis') or [])[:3]:
            print(f"  • {pt}")
