"""绘制 JobBench Main split 排行榜对比图（多语言：英 / 中 / 日）。

官方榜单数据来自 https://job-bench.github.io/#leaderboard
- harness: OpenCode（所有模型统一）
- judge: Grok 4.3

本仓库用 deepseek-v4-flash 跑了两种 harness：
- OpenCode（官方同款 harness）
- pagentv4（本仓库 inplace 模式）

两条都用 deepseek-v4-pro 当裁判（成本考虑），与官方 Grok 4.3 口径不同，用高亮色
和 * 标注：分数仅供参考，不能和官方榜直接横比。要严格对榜需换 Grok 4.3 重评。

本仓库两条 harness 的分数从 jobbench_scores.json 读取（由
examples/eval/aggregate_scores.py 汇总后快照到本目录），取 micro 分。

用法:
    uv run python examples/eval/plot_jobbench_leaderboard.py
输出:
    examples/eval/jobbench_leaderboard_en.png
    examples/eval/jobbench_leaderboard_zh.png
    examples/eval/jobbench_leaderboard_ja.png
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).parent
SCORES_FILE = HERE / "jobbench_scores.json"

# Arial Unicode 覆盖中日英，统一用它避免缺字
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
if Path(FONT_PATH).exists():
    font_manager.fontManager.addfont(FONT_PATH)
    plt.rcParams["font.family"] = font_manager.FontProperties(
        fname=FONT_PATH
    ).get_name()
plt.rcParams["axes.unicode_minus"] = False

# 官方 leaderboard（Main split, judge=Grok 4.3, harness=OpenCode）
OFFICIAL = [
    ("Muse Spark 1.2", 61.6),
    ("Claude Fable 5", 57.4),
    ("Muse Spark 1.1", 54.7),
    ("Kimi K3", 54.3),
    ("Qwen 3.8 Max", 52.7),
    ("Claude Opus 4.8", 48.4),
    ("GPT-5.6 SOL", 45.4),
    ("Claude Opus 4.7", 44.5),
    ("GLM 5.2", 43.4),
    ("GPT-5.5", 38.3),
    ("Claude Sonnet 4.6", 36.6),
    ("GPT-5.4", 32.2),
    ("Gemini 3.5 Flash", 31.5),
    ("GPT-5.2", 26.6),
    ("Claude Sonnet 4.5", 20.7),
    ("Gemini 3.1 Pro", 15.9),
]

# 配色
BAR_OFFICIAL = "#5B8FF9"
BAR_OFFICIAL_TOP = "#2E5FCC"  # 榜首更深，做出层次
BAR_OURS_OC = "#E8503A"  # OpenCode harness（暖红）
BAR_OURS_PG = "#F2A65A"  # pagentv4 harness（橙）
TXT_DARK = "#2b2b2b"
GRID = "#e6e6e6"


def load_ours():
    """从快照读取两条 harness 的 main micro 分（%）。"""
    data = json.loads(SCORES_FILE.read_text())
    oc = data["main/OpenCode"]["summary"]["micro"] * 100
    pg = data["main/pagentv4"]["summary"]["micro"] * 100
    return oc, pg


I18N = {
    "en": {
        "title": "JobBench — Main Split Leaderboard",
        "subtitle": "Official runs judged by Grok 4.3 · harness: OpenCode",
        "xlabel": "Weighted score (%)",
        "legend_official": "Official (judge: Grok 4.3)",
        "legend_oc": "Ours — OpenCode harness (judge: deepseek-v4-pro *)",
        "legend_pg": "Ours — pagentv4 harness (judge: deepseek-v4-pro *)",
        "name_oc": "deepseek-v4-flash · OpenCode *",
        "name_pg": "deepseek-v4-flash · pagentv4 *",
        "note": (
            "* Both bars are deepseek-v4-flash judged by deepseek-v4-pro "
            "(same-vendor, lenient) — a different judge than the official Grok "
            "4.3,\n"
            "  so scores are indicative only and NOT directly comparable to the "
            "official leaderboard. Scores shown are micro (total/max).\n"
            "  Two harnesses under the same judge: OpenCode vs pagentv4 (inplace)."
        ),
        "out": "jobbench_leaderboard_en.png",
    },
    "zh": {
        "title": "JobBench — Main split 排行榜对比",
        "subtitle": "官方成绩由 Grok 4.3 评判 · harness：OpenCode",
        "xlabel": "加权得分（%）",
        "legend_official": "官方（裁判：Grok 4.3）",
        "legend_oc": "本仓库 · OpenCode harness（裁判：deepseek-v4-pro *）",
        "legend_pg": "本仓库 · pagentv4 harness（裁判：deepseek-v4-pro *）",
        "name_oc": "deepseek-v4-flash · OpenCode *",
        "name_pg": "deepseek-v4-flash · pagentv4 *",
        "note": (
            "* 两条都是 deepseek-v4-flash，裁判用 deepseek-v4-pro（同厂自评，偏"
            "松），与官方 Grok 4.3 口径不同，\n"
            "  分数仅供参考、不能与官方榜直接横比。分数取 micro（总分 / 满分）。\n"
            "  同一裁判下对比两种 harness：OpenCode 与 pagentv4（inplace）。"
        ),
        "out": "jobbench_leaderboard_zh.png",
    },
    "ja": {
        "title": "JobBench — Main split リーダーボード比較",
        "subtitle": "公式スコアは Grok 4.3 が採点 · harness：OpenCode",
        "xlabel": "加重スコア（%）",
        "legend_official": "公式（審査：Grok 4.3）",
        "legend_oc": "本リポジトリ · OpenCode harness（審査：deepseek-v4-pro *）",
        "legend_pg": "本リポジトリ · pagentv4 harness（審査：deepseek-v4-pro *）",
        "name_oc": "deepseek-v4-flash · OpenCode *",
        "name_pg": "deepseek-v4-flash · pagentv4 *",
        "note": (
            "* いずれも deepseek-v4-flash。審査は deepseek-v4-pro（同一ベンダー・"
            "甘め）で、公式の Grok 4.3 とは基準が異なる。\n"
            "  スコアは参考値であり、公式ランキングとの直接比較はできない。スコアは "
            "micro（合計 / 満点）。\n"
            "  同一審査での 2 種類の harness 比較：OpenCode と pagentv4（inplace）。"
        ),
        "out": "jobbench_leaderboard_ja.png",
    },
}


def build_rows(cfg, score_oc, score_pg):
    rows = [(name, score, None) for name, score in OFFICIAL]
    rows.append((cfg["name_oc"], score_oc, "oc"))
    rows.append((cfg["name_pg"], score_pg, "pg"))
    rows.sort(key=lambda r: r[1])  # 升序，barh 从下往上
    return rows


def bar_color(score, tag, top_score):
    if tag == "oc":
        return BAR_OURS_OC
    if tag == "pg":
        return BAR_OURS_PG
    if score == top_score:
        return BAR_OFFICIAL_TOP
    return BAR_OFFICIAL


def render(lang, cfg, score_oc, score_pg):
    rows = build_rows(cfg, score_oc, score_pg)
    official_top = max(s for _, s, tag in rows if tag is None)
    names = [r[0] for r in rows]
    scores = [r[1] for r in rows]
    colors = [bar_color(s, tag, official_top) for _, s, tag in rows]

    fig, ax = plt.subplots(figsize=(11, 8.6))
    fig.patch.set_facecolor("white")
    bars = ax.barh(names, scores, color=colors, height=0.68, zorder=3)

    for bar, (_, _, tag) in zip(bars, rows):
        if tag:
            bar.set_edgecolor("#7a1e12")
            bar.set_linewidth(1.4)

    for bar, (_, score, tag) in zip(bars, rows):
        ax.text(
            score + 0.7,
            bar.get_y() + bar.get_height() / 2,
            f"{score:.1f}",
            va="center",
            fontsize=10.5 if tag else 9.5,
            fontweight="bold" if tag else "normal",
            color=(BAR_OURS_OC if tag else TXT_DARK),
            zorder=4,
        )

    for lbl, (_, _, tag) in zip(ax.get_yticklabels(), rows):
        if tag:
            lbl.set_color(BAR_OURS_OC if tag == "oc" else "#b8712f")
            lbl.set_fontweight("bold")

    ax.set_xlim(0, 70)
    ax.set_xlabel(cfg["xlabel"], fontsize=11, color=TXT_DARK)
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.yaxis.grid(False)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#cccccc")
    ax.tick_params(axis="y", length=0, labelsize=10)
    ax.tick_params(axis="x", colors="#888888")

    ax.set_title(
        cfg["title"],
        fontsize=15,
        fontweight="bold",
        color=TXT_DARK,
        pad=26,
        loc="left",
    )
    ax.text(
        0,
        1.012,
        cfg["subtitle"],
        transform=ax.transAxes,
        fontsize=10,
        color="#888888",
        va="bottom",
    )

    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=BAR_OFFICIAL),
        plt.Rectangle((0, 0), 1, 1, color=BAR_OURS_OC),
        plt.Rectangle((0, 0), 1, 1, color=BAR_OURS_PG),
    ]
    ax.legend(
        legend_handles,
        [cfg["legend_official"], cfg["legend_oc"], cfg["legend_pg"]],
        loc="lower right",
        fontsize=9,
        frameon=True,
        framealpha=0.95,
        edgecolor="#dddddd",
    )

    fig.text(0.012, 0.008, cfg["note"], fontsize=8, color="#666666", va="bottom")
    plt.tight_layout(rect=(0, 0.085, 1, 0.99))

    out = HERE / cfg["out"]
    fig.savefig(out, dpi=160, facecolor="white")
    plt.close(fig)
    print(f"[{lang}] saved: {out}  (OpenCode={score_oc:.1f}, pagentv4={score_pg:.1f})")


def main():
    score_oc, score_pg = load_ours()
    for lang, cfg in I18N.items():
        render(lang, cfg, score_oc, score_pg)


if __name__ == "__main__":
    main()
