#!/usr/bin/env python3
"""
批量下载《注塑成型高影响因子权威论文 Top 100 精选集》PDF 并同步至本地 Google Drive 目录。

特性：
- 优先读取 papers_metadata.csv（保留原始 #001~#100 排名编号），也兼容纯文本 dois.txt
- 支持 Sci-Hub 解析下载 + Unpaywall 合法 OA 自动回退
- 支持断点续传（已存在且大于 10KB 的 PDF 自动跳过）
- 支持命令行参数覆写保存目录、Unpaywall 邮箱、仅下载 Top 12 必读论文等
"""

import argparse
import csv
import os
import random
import re
import time
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

# ================= 默认配置区（可直接修改，也可通过命令行参数覆写） =================
SCIHUB_URL = "https://sci-hub.si"
METADATA_FILE = "papers_metadata.csv"
DOI_FILE = "dois.txt"
SAVE_DIR = "./GoogleDrive_Sync/注塑成型Top100论文"  # 改为本地 Google Drive 同步文件夹路径
UNPAYWALL_EMAIL = "your_email@example.com"         # 用于 2022-2025 论文的 OA 自动回退
# ==============================================================================

# 针对 250T 高速滑块线盘注塑项目的 15 篇核心必读论文编号（来自原文档第二节）
TOP_PRIORITY_RANKS = {21, 23, 31, 39, 48, 59, 64, 67, 78, 87, 92, 93, 94, 95, 96, 97}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
}


def normalize_url(url: str, base: str) -> str:
    url = url.replace("\\/", "/").strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return base.rstrip("/") + url
    return url


def fetch_pdf_from_scihub(
    session: requests.Session, scihub_url: str, doi: str
) -> Tuple[Optional[bytes], str]:
    """从 Sci-Hub 解析并下载 PDF 二进制内容"""
    page_url = f"{scihub_url.rstrip('/')}/{doi}"
    resp = session.get(page_url, timeout=20)
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"

    html = resp.text
    if "captcha" in html.lower():
        return None, "触发验证码，建议稍后重试或放慢频率"

    soup = BeautifulSoup(html, "html.parser")
    pdf_url = None

    # 1. 尝试从 embed / iframe / object 提取
    for tag_name, attr in [("embed", "src"), ("iframe", "src"), ("object", "data")]:
        tag = soup.find(tag_name, {attr: True})
        if tag and ".pdf" in tag[attr].lower():
            pdf_url = tag[attr].split("#")[0]
            break

    # 2. 尝试从下载按钮 onclick 提取
    if not pdf_url:
        match = re.search(
            r"location\.href\s*=\s*['\"]([^'\"]+\.pdf[^'\"]*)['\"]",
            html,
            re.IGNORECASE,
        )
        if match:
            pdf_url = match.group(1)

    if not pdf_url:
        return None, "Sci-Hub 未收录"

    pdf_url = normalize_url(pdf_url, scihub_url)
    pdf_resp = session.get(pdf_url, timeout=40)
    if pdf_resp.status_code == 200 and pdf_resp.content[:4] == b"%PDF":
        return pdf_resp.content, "Sci-Hub"
    return None, "PDF 链接无效或被拦截"


def fetch_pdf_from_unpaywall(
    session: requests.Session, email: str, doi: str
) -> Tuple[Optional[bytes], Optional[str]]:
    """Sci-Hub 未命中时，自动回退 Unpaywall 尝试合法 OA 版本"""
    if not email or email == "your_email@example.com":
        return None, None
    api_url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
    try:
        r = session.get(api_url, timeout=15).json()
        oa_loc = r.get("best_oa_location") or {}
        pdf_url = oa_loc.get("url_for_pdf")
        if pdf_url:
            pdf_resp = session.get(pdf_url, timeout=30)
            if pdf_resp.status_code == 200 and pdf_resp.content[:4] == b"%PDF":
                return pdf_resp.content, "Unpaywall OA"
    except Exception:
        pass
    return None, None


def load_entries(
    metadata_file: Optional[str], doi_file: Optional[str], only_priority: bool
) -> List[Tuple[int, str, str]]:
    """加载待下载条目，返回 [(rank, doi, title), ...]"""
    entries: List[Tuple[int, str, str]] = []

    if metadata_file and os.path.exists(metadata_file):
        with open(metadata_file, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rank = int(row["rank"])
                if only_priority and rank not in TOP_PRIORITY_RANKS:
                    continue
                entries.append((rank, row.get("doi", "").strip(), row.get("title", "").strip()))
        return entries

    if doi_file and os.path.exists(doi_file):
        with open(doi_file, "r", encoding="utf-8") as f:
            dois = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        for idx, doi in enumerate(dois, start=1):
            if only_priority and idx not in TOP_PRIORITY_RANKS:
                continue
            entries.append((idx, doi, ""))
        return entries

    raise FileNotFoundError(
        f"未找到论文清单文件：请确认 {metadata_file} 或 {doi_file} 存在于当前目录。"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量下载注塑成型 Top 100 论文 PDF 并保存至本地/Google Drive 同步目录"
    )
    parser.add_argument(
        "--save-dir",
        default=SAVE_DIR,
        help=f"PDF 保存目录（默认：{SAVE_DIR}）",
    )
    parser.add_argument(
        "--email",
        default=UNPAYWALL_EMAIL,
        help="用于 Unpaywall OA 自动回退的邮箱地址",
    )
    parser.add_argument(
        "--scihub-url",
        default=SCIHUB_URL,
        help=f"Sci-Hub 域名（默认：{SCIHUB_URL}）",
    )
    parser.add_argument(
        "--metadata-file",
        default=METADATA_FILE,
        help=f"含完整排名与标题的 CSV 清单（默认：{METADATA_FILE}）",
    )
    parser.add_argument(
        "--doi-file",
        default=DOI_FILE,
        help=f"纯 DOI 文本清单，仅在未找到 CSV 时回退使用（默认：{DOI_FILE}）",
    )
    parser.add_argument(
        "--only-priority",
        action="store_true",
        help="仅下载针对 250T 高速线盘项目的核心必读论文（16 篇）",
    )
    parser.add_argument(
        "--delay-min",
        type=float,
        default=2.0,
        help="每篇请求后的最小随机停顿秒数（默认：2.0）",
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=4.0,
        help="每篇请求后的最大随机停顿秒数（默认：4.0）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.makedirs(args.save_dir, exist_ok=True)

    entries = load_entries(args.metadata_file, args.doi_file, args.only_priority)
    session = requests.Session()
    session.headers.update(HEADERS)

    if args.email == "your_email@example.com":
        print("[提示] 未配置 --email，将跳过 Unpaywall OA 自动回退（建议传入真实邮箱以提高近3年论文命中率）。")

    missing = []
    success_count = 0

    for rank, doi, title in entries:
        if not doi:
            missing.append((rank, "", "原始清单缺失 DOI，需人工按标题检索", title))
            print(f"[跳过-无DOI] #{rank:03d} {title[:60]}")
            continue

        safe_name = f"{rank:03d}_{doi.replace('/', '_').replace(':', '_')}.pdf"
        filepath = os.path.join(args.save_dir, safe_name)

        # 断点续传：已下载的自动跳过
        if os.path.exists(filepath) and os.path.getsize(filepath) > 10_000:
            print(f"[跳过] #{rank:03d} 已存在")
            success_count += 1
            continue

        try:
            content, source = fetch_pdf_from_scihub(session, args.scihub_url, doi)
            if not content:
                oa_content, oa_source = fetch_pdf_from_unpaywall(session, args.email, doi)
                if oa_content and oa_source:
                    content, source = oa_content, oa_source

            if content:
                with open(filepath, "wb") as out:
                    out.write(content)
                success_count += 1
                print(f"[成功 - {source}] #{rank:03d} -> {safe_name}")
            else:
                missing.append((rank, doi, source, title))
                print(f"[失败] #{rank:03d} {doi} ({source})")
        except Exception as e:
            missing.append((rank, doi, str(e), title))
            print(f"[异常] #{rank:03d} {doi} ({e})")

        # 随机停顿，避免触发频率限制
        time.sleep(random.uniform(args.delay_min, args.delay_max))

    # 导出未下载成功的清单
    missing_file = os.path.join(args.save_dir, "_missing_papers.txt")
    with open(missing_file, "w", encoding="utf-8") as mf:
        for rank, doi, reason, title in missing:
            doi_link = f"https://doi.org/{doi}" if doi else "-"
            mf.write(f"#{rank:03d}\t{doi or 'NO_DOI'}\t{reason}\t{doi_link}\t{title}\n")

    print(f"\n全部处理完成！成功 {success_count}/{len(entries)} 篇。")
    print(f"未命中的 {len(missing)} 篇已汇总至：{missing_file}")


if __name__ == "__main__":
    main()
