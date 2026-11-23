# 注塑成型 Top 100 高影响因子论文批量下载工具

本仓库包含《注塑成型（Injection Molding）高影响因子权威论文 Top 100 精选集》的完整元数据、清洗校验后的 DOI 清单，以及一键批量下载并同步至本地 Google Drive 的 Python 脚本。

## 文件说明

- `download_from_scihub.py`：批量下载脚本（支持 Sci-Hub + Unpaywall OA 自动回退、断点续传、随机延时与未命中清单汇总）。
- `papers_metadata.csv`：全部 100 篇论文的结构化清单（保留原始 `#001`~`#100` 排名、IF、年份、期刊、标题、作者与 DOI）。
- `dois.txt`：清洗并校验通过的 **98 个唯一 DOI**（每行一个，可直接用于其他文献管理工具如 Zotero / EndNote）。
- `requirements.txt`：Python 依赖清单。
- `docs/注塑成型高影响因子权威论文_Top_100_精选集.md`：原始完整论文目录文档。

### DOI 校验与补全说明

- 原始文档中 96 篇自带 DOI，已全部提取并通过格式与去重校验。
- 已为您核实并补全 2 篇缺失的官方 DOI：
  - **#27** *IM-Chat (Journal of Manufacturing Systems, 2025)* → `10.1016/j.jmsy.2025.11.007`（另见 arXiv OA 预印本 `2507.15268`）
  - **#68** *Exploring and optimizing deep neural networks... (Journal of Intelligent Manufacturing, 2025)* → `10.1007/s10845-024-02394-3`
- 仍有 2 篇在原始文档中未提供 DOI 且未能精确匹配到唯一 DOI，脚本运行时会自动跳过并记录在 `_missing_papers.txt` 中供人工检索：
  - **#42** *A framework of collaborative design environment for injection molding* (Y. Lu, F.T.S. Chan, 2002)
  - **#54** *Injection Molded Segregated Carbon Nanotube/Polypropylene Composite for Efficient Electromagnetic Interference Shielding* (H.-Y. Wu et al., 2018)

---

## 快速开始（在您的本地电脑运行）

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行下载脚本

**macOS 示例**（直接同步到 Google Drive 桌面端目录）：

```bash
python3 download_from_scihub.py \
  --save-dir "$HOME/Library/CloudStorage/GoogleDrive-你的邮箱/My Drive/注塑成型Top100论文" \
  --email "你的真实邮箱@example.com"
```

**Windows (PowerShell) 示例**：

```powershell
python download_from_scihub.py `
  --save-dir "G:\My Drive\注塑成型Top100论文" `
  --email "你的真实邮箱@example.com"
```

### 3. 常用选项

- **只下载 250T 高速线盘项目必读核心论文（16 篇）**：
  ```bash
  python3 download_from_scihub.py --only-priority --email "你的真实邮箱@example.com"
  ```
- **断点续传**：如中途遇到网络波动或触发验证码，等待片刻后直接重新运行同一条命令即可，已下载且大于 10 KB 的 PDF 会自动跳过。
- **查看未命中清单**：运行结束后，所有未下载成功的论文会汇总在保存目录下的 `_missing_papers.txt`，内含 DOI 跳转链接与完整标题，便于通过机构库或 Google Scholar 补齐。
