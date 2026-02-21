#!/usr/bin/env python3
import os
import sys
import json
import time
import zipfile
from pathlib import Path
from typing import List, Dict, Optional
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
TOKEN = os.getenv("MINERU_API_KEY")
POLL_INTERVAL = 10
BATCH_SIZE = 200  # 新增：API限制单次200个文件

BASE_URL = "https://mineru.net/api/v4"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}

# 默认目录（当作为独立脚本运行时）
INPUT_DIR = Path("./PDFS")
OUTPUT_DIR = Path("./input")
OUTPUT_DIR.mkdir(exist_ok=True)

def _log(msg):
    """日志输出到stderr，避免污染stdout"""
    print(msg, file=sys.stderr)

def upload_batch(file_batch: List[Path], base_url: str = BASE_URL, 
                 headers: Dict = None, input_dir: Optional[Path] = None) -> str:
    """上传一批PDF文件，返回batch_id"""
    if headers is None:
        headers = HEADERS
    if input_dir is None:
        input_dir = INPUT_DIR
    
    files_data = [
        {"name": p.name, "is_ocr": True, "data_id": f"{p.stem}.pdf-id"}
        for p in file_batch
    ]
    
    payload = {
        "enable_formula": True,
        "language": "ch",
        "enable_table": True,
        "files": files_data
    }

    url = f"{base_url}/file-urls/batch"
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if r.status_code != 200:
        raise RuntimeError(f"HTTP错误: {r.status_code}")
    
    resp = r.json()
    if resp.get("code") != 0:
        error_msg = resp.get("msg", "未知错误")
        raise RuntimeError(f"获取上传地址失败: {error_msg}")

    data = resp["data"]
    batch_id = data["batch_id"]
    upload_urls: List[str] = data["file_urls"]

    _log(f"batch_id: {batch_id}")
    # 逐个PUT上传
    for pdf_path, upload_url in zip(file_batch, upload_urls):
        with open(pdf_path, "rb") as f:
            up_resp = requests.put(upload_url, data=f)
            if up_resp.status_code != 200:
                raise RuntimeError(f"上传 {pdf_path.name} 失败 {up_resp.status_code}")
        _log(f"✅ 已上传 {pdf_path.name}")

    return batch_id

def wait_until_done(batch_id: str, base_url: str = BASE_URL, 
                    headers: Dict = None, poll_interval: int = None) -> List[Dict]:
    """轮询直到所有任务结束，返回extract_result列表"""
    if headers is None:
        headers = HEADERS
    if poll_interval is None:
        poll_interval = POLL_INTERVAL
        
    url = f"{base_url}/extract-results/batch/{batch_id}"
    while True:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        resp = r.json()
        if resp.get("code") != 0:
            raise RuntimeError(f"查询结果失败: {resp}")

        results: List[Dict] = resp["data"]["extract_result"]
        states = {item["state"] for item in results}
        _log(f"当前状态 {states}")
        if states <= {"done", "failed", "error"}:
            return results
        time.sleep(poll_interval)

def download_zip(url: str, dst: Path) -> None:
    """下载并解压zip"""
    _log(f"⬇️ 下载 {url}")
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    zip_path = dst.with_suffix(".zip")
    with open(zip_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dst)
    zip_path.unlink()  # 删zip
    _log(f"✅ 解压到 {dst}")

def fetch_and_download(batch_id: str, results: List[Dict], output_dir: Optional[Path] = None,
                       skip_batch_dir: bool = True) -> None:
    """把成功的zip拉下来
    
    Args:
        batch_id: 批次ID
        results: 结果列表
        output_dir: 输出目录
        skip_batch_dir: 是否跳过 batch_id 目录层级（默认True，直接输出到output_dir）
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
        
    # 根据 skip_batch_dir 决定是否创建 batch_id 子目录
    if skip_batch_dir:
        batch_out = output_dir
    else:
        batch_out = output_dir / batch_id
    batch_out.mkdir(parents=True, exist_ok=True)

    for item in results:
        if item["state"] != "done":
            _log(f"⚠️ {item['file_name']} 处理失败: {item.get('err_msg', '无错误信息')}")
            continue
        zip_url = item["full_zip_url"].strip()
        data_id = item["data_id"]
        target_dir = batch_out / data_id
        download_zip(zip_url, target_dir)

def process_batch(file_batch: List[Path]):
    """处理单个文件批次"""
    _log(f"=== 开始上传批次 ({len(file_batch)} 个文件) ===")
    batch_id = upload_batch(file_batch)
    _log(f"=== 等待处理完成 (批次 ID: {batch_id}) ===")
    results = wait_until_done(batch_id)
    _log("=== 开始下载结果 ===")
    fetch_and_download(batch_id, results)
    _log(f"=== 批次 {batch_id} 完成 ===")

def main():
    if not TOKEN or TOKEN == "官网申请的api token":
        raise RuntimeError("请先设置MINERU_API_KEY环境变量")
    
    # 获取所有PDF文件
    all_pdf_files = list(INPUT_DIR.glob("*.pdf"))
    if not all_pdf_files:
        _log("❌ input目录里没有PDF文件")
        return
    
    _log(f"发现 {len(all_pdf_files)} 个PDF文件")
    
    # 分批处理文件 (每批最多200个)
    for i in range(0, len(all_pdf_files), BATCH_SIZE):
        file_batch = all_pdf_files[i:i+BATCH_SIZE]
        try:
            process_batch(file_batch)
        except Exception as e:
            _log(f"❌ 处理批次失败: {str(e)}")
            # 可选：记录失败的文件名以便重试
            with open("failed_batches.txt", "a") as f:
                f.write(f"批次 {i//BATCH_SIZE}: {[p.name for p in file_batch]}\n")
    
    _log("=== 全部处理完成 ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log(f"❌ 程序运行失败: {str(e)}")