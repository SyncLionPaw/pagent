"""绘制 JobBench 可视化（多语言：英 / 中 / 日）。

产出两组图：

1. Main split 排行榜（`jobbench_leaderboard_{en,zh,ja}.png`）
   视觉对齐官方榜 https://job-bench.github.io/#leaderboard —— 暖米色背景、
   淡出的名次序号、右对齐大分数、细分隔线；本仓库两条 harness 用橙色高亮。

2. harness 对比图（`jobbench_harness_compare_{en,zh,ja}.png`）
   OpenCode vs pagentv4 在 Easy / Main 两个 split 上的 micro / macro 分组对比。

官方榜 harness 统一 OpenCode、裁判 Grok 4.3；本仓库两条 harness 都用
deepseek-v4-flash 当选手、deepseek-v4-pro 当裁判（成本考虑），与官方 Grok 4.3
口径不同，用橙色和 * 标注：分数仅供参考，不能与官方榜直接横比。

分数从 jobbench_scores.json 读取（由 examples/eval/aggregate_scores.py 汇总后
快照到本目录），取 micro / macro。

用法:
    uv run python examples/eval/plot_jobbench_leaderboard.py

输出同时写入 examples/eval/ 与 docs/public/benchmarks/。
"""

import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).parent
SCORES_FILE = HERE / "jobbench_scores.json"
# VitePress serves docs/public/ at site root (/benchmarks/...).
DOCS_BENCH = HERE.parents[1] / "docs" / "public" / "benchmarks"

# Arial Unicode 覆盖中日英，统一用它避免缺字
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
if Path(FONT_PATH).exists():
    font_manager.fontManager.addfont(FONT_PATH)
    plt.rcParams["font.family"] = font_manager.FontProperties(
        fname=FONT_PATH
    ).get_name()
plt.rcParams["axes.unicode_minus"] = False

# 等宽字体给名次/分数数字用（ASCII），营造官方榜的终端质感；缺失则回退默认
MONO = None
for cand in ("/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf"):
    if Path(cand).exists():
        font_manager.fontManager.addfont(cand)
        MONO = font_manager.FontProperties(fname=cand)
        break

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

# 配色 —— 对齐官方站点的暖米色 + 橙色强调
BG = "#faf8f3"  # 暖米色背景
INK = "#1c1917"  # 近黑正文
MUTED = "#8a8175"  # 暖灰次要文字
FAINT = "#d9d3c7"  # 淡出的名次序号
DIV = "#ebe6dc"  # 细分隔线
BAR_OC = "#e8622e"  # OpenCode harness（橙红）
BAR_PG = "#f2a13d"  # pagentv4 harness（琥珀）


def load_main_micro():
    """两条 harness 的 main micro 分（%）。"""
    data = json.loads(SCORES_FILE.read_text())
    oc = data["main/OpenCode"]["summary"]["micro"] * 100
    pg = data["main/pagentv4"]["summary"]["micro"] * 100
    return oc, pg


def load_compare():
    """四组合的 macro / micro（%），供 harness 对比图用。"""
    data = json.loads(SCORES_FILE.read_text())
    out = {}
    for key in ("easy/OpenCode", "easy/pagentv4", "main/OpenCode", "main/pagentv4"):
        s = data[key]["summary"]
        out[key] = {"macro": s["macro"] * 100, "micro": s["micro"] * 100}
    return out


# ============================================================
# 一、Main split 排行榜（官方视觉风格）
# ============================================================

I18N = {
    "en": {
        "title": "JobBench — Main Split Leaderboard",
        "subtitle": "Official runs judged by Grok 4.3 · harness OpenCode · orange = ours",
        "player": "deepseek-v4-flash",
        "harness_official": "OpenCode",
        "harness_oc": "OpenCode *",
        "harness_pg": "pagentv4 *",
        "note": (
            "* Orange rows are deepseek-v4-flash judged by deepseek-v4-pro "
            "(same-vendor, lenient) — a different judge than the official Grok 4.3, "
            "so scores are indicative only and not directly comparable. "
            "Scores are micro (total / max)."
        ),
        "out": "jobbench_leaderboard_en.png",
    },
    "zh": {
        "title": "JobBench — Main split 排行榜",
        "subtitle": "官方成绩由 Grok 4.3 评判 · harness OpenCode · 橙色为本仓库",
        "player": "deepseek-v4-flash",
        "harness_official": "OpenCode",
        "harness_oc": "OpenCode *",
        "harness_pg": "pagentv4 *",
        "note": (
            "* 橙色两行都是 deepseek-v4-flash，裁判用 deepseek-v4-pro（同厂自评，偏松），"
            "与官方 Grok 4.3 口径不同，仅供参考、不能直接横比。"
            "分数取 micro（总分 / 满分）。"
        ),
        "out": "jobbench_leaderboard_zh.png",
    },
    "ja": {
        "title": "JobBench — Main split リーダーボード",
        "subtitle": "公式スコアは Grok 4.3 が採点 · harness OpenCode · オレンジは本リポジトリ",
        "player": "deepseek-v4-flash",
        "harness_official": "OpenCode",
        "harness_oc": "OpenCode *",
        "harness_pg": "pagentv4 *",
        "note": (
            "* オレンジの 2 行は deepseek-v4-flash。審査は deepseek-v4-pro（同一ベンダー・"
            "甘め）で公式の Grok 4.3 とは基準が異なるため、参考値であり直接比較はできない。"
            "スコアは micro（合計 / 満点）。"
        ),
        "out": "jobbench_leaderboard_ja.png",
    },
}


def build_rows(cfg, score_oc, score_pg):
    """官方名次 + 本仓库两行，按分数降序（榜首在顶部）。"""
    rows = [
        {"name": name, "score": s, "harness": cfg["harness_official"], "tag": None}
        for name, s in OFFICIAL
    ]
    rows.append(
        {
            "name": cfg["player"],
            "score": score_oc,
            "harness": cfg["harness_oc"],
            "tag": "oc",
        }
    )
    rows.append(
        {
            "name": cfg["player"],
            "score": score_pg,
            "harness": cfg["harness_pg"],
            "tag": "pg",
        }
    )
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def row_color(tag):
    """名次/名称/分数的文字颜色：本仓库两行橙色高亮。"""
    if tag == "oc":
        return BAR_OC
    if tag == "pg":
        return "#c07d1e"
    return None


def render_leaderboard(lang, cfg, score_oc, score_pg):
    """纯文字榜单，对齐官方 https://job-bench.github.io/#leaderboard 的排版。"""
    rows = build_rows(cfg, score_oc, score_pg)
    n = len(rows)

    fig, ax = plt.subplots(figsize=(11, 9.2))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, n)
    ax.invert_yaxis()  # 榜首（i=0）在顶部
    ax.axis("off")

    # 顶部粗分隔线（表头下沿）
    ax.plot([0, 1], [0, 0], color=MUTED, lw=1.2, zorder=2, clip_on=False)

    for i, r in enumerate(rows):
        tag = r["tag"]
        y = i + 0.5
        accent = row_color(tag)

        # 本仓库行：整行淡橙底 + 左侧竖条强调
        if tag:
            ax.axhspan(i + 0.04, i + 0.96, color=BAR_OC, alpha=0.09, zorder=0)
            ax.plot(
                [0.0, 0.0],
                [i + 0.16, i + 0.84],
                color=accent,
                lw=3.4,
                zorder=5,
                solid_capstyle="round",
                clip_on=False,
            )

        # 行分隔线
        ax.plot([0, 1], [i + 1, i + 1], color=DIV, lw=0.8, zorder=1)

        rank = i + 1
        ax.text(
            0.014,
            y,
            f"{rank:02d}",
            ha="left",
            va="center",
            fontsize=15,
            color=accent or FAINT,
            fontproperties=MONO,
            zorder=4,
        )
        ax.text(
            0.064,
            y,
            r["name"],
            ha="left",
            va="center",
            fontsize=12.5,
            color=accent or INK,
            fontweight="bold" if tag else "normal",
            zorder=4,
        )
        ax.text(
            0.86,
            y,
            f"{r['score']:.1f}",
            ha="right",
            va="center",
            fontsize=15,
            color=accent or INK,
            fontweight="bold",
            fontproperties=MONO,
            zorder=4,
        )
        ax.text(
            0.995,
            y,
            r["harness"],
            ha="right",
            va="center",
            fontsize=9.5,
            color=accent or MUTED,
            zorder=4,
        )

    # 标题 + 橙色下划线（下划线在标题基线下方，不穿字）
    ax.text(
        0,
        1.052,
        cfg["title"],
        transform=ax.transAxes,
        fontsize=19,
        fontweight="bold",
        color=INK,
        va="bottom",
    )
    ax.plot(
        [0, 0.12],
        [1.04, 1.04],
        transform=ax.transAxes,
        color=BAR_OC,
        lw=3.2,
        clip_on=False,
        solid_capstyle="round",
    )
    ax.text(
        0,
        1.006,
        cfg["subtitle"],
        transform=ax.transAxes,
        fontsize=10.5,
        color=MUTED,
        va="bottom",
    )

    fig.text(0.03, 0.02, cfg["note"], fontsize=8, color=MUTED, va="bottom", wrap=True)
    fig.subplots_adjust(top=0.9, bottom=0.075, left=0.03, right=0.97)

    out = HERE / cfg["out"]
    fig.savefig(out, dpi=170, facecolor=BG)
    plt.close(fig)
    DOCS_BENCH.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, DOCS_BENCH / out.name)
    print(
        f"[{lang}] leaderboard: {out.name}  (OpenCode={score_oc:.1f}, pagentv4={score_pg:.1f})"
    )


# ============================================================
# 二、harness 对比图（OpenCode vs pagentv4 · Easy / Main）
# ============================================================

CMP_I18N = {
    "en": {
        "title": "OpenCode vs pagentv4 — deepseek-v4-flash",
        "subtitle": "Same player & judge (deepseek-v4-pro); only the harness changes",
        "ylabel": "Weighted score (%)",
        "groups": ["Easy split", "Main split"],
        "legend_oc": "OpenCode harness",
        "legend_pg": "pagentv4 harness (inplace)",
        "macro_tag": "macro",
        "note": "Bar height = micro (total / max). macro = task-mean. Green tag = pagentv4 lead on micro.",
        "out": "jobbench_harness_compare_en.png",
    },
    "zh": {
        "title": "OpenCode vs pagentv4 — deepseek-v4-flash",
        "subtitle": "同选手、同裁判（deepseek-v4-pro），只换 harness",
        "ylabel": "加权得分（%）",
        "groups": ["Easy split", "Main split"],
        "legend_oc": "OpenCode harness",
        "legend_pg": "pagentv4 harness（inplace）",
        "macro_tag": "macro",
        "note": "柱高 = micro（总分 / 满分）。macro = 按任务平均。绿色标签 = pagentv4 在 micro 上的领先。",
        "out": "jobbench_harness_compare_zh.png",
    },
    "ja": {
        "title": "OpenCode vs pagentv4 — deepseek-v4-flash",
        "subtitle": "同一プレイヤー・審査（deepseek-v4-pro）、harness のみ変更",
        "ylabel": "加重スコア（%）",
        "groups": ["Easy split", "Main split"],
        "legend_oc": "OpenCode harness",
        "legend_pg": "pagentv4 harness（inplace）",
        "macro_tag": "macro",
        "note": "棒の高さ = micro（合計 / 満点）。macro = タスク平均。緑タグ = micro での pagentv4 の優位。",
        "out": "jobbench_harness_compare_ja.png",
    },
}

GREEN = "#2f8f5b"  # pagentv4 领先量的正向绿色


def render_compare(lang, cfg, data):
    splits = ["easy", "main"]
    oc_micro = [data[f"{s}/OpenCode"]["micro"] for s in splits]
    pg_micro = [data[f"{s}/pagentv4"]["micro"] for s in splits]
    oc_macro = [data[f"{s}/OpenCode"]["macro"] for s in splits]
    pg_macro = [data[f"{s}/pagentv4"]["macro"] for s in splits]

    x = [0, 1.35]
    w = 0.42
    fig, ax = plt.subplots(figsize=(8.8, 6.6))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    b_oc = ax.bar(
        [xi - w / 2 for xi in x],
        oc_micro,
        w,
        color=BAR_OC,
        label=cfg["legend_oc"],
        zorder=3,
    )
    b_pg = ax.bar(
        [xi + w / 2 for xi in x],
        pg_micro,
        w,
        color=BAR_PG,
        label=cfg["legend_pg"],
        zorder=3,
    )

    def annotate(bars, micros, macros):
        for bar, mi, ma in zip(bars, micros, macros):
            cx = bar.get_x() + bar.get_width() / 2
            # micro：柱顶上方粗体大字
            ax.text(
                cx,
                mi + 3.4,
                f"{mi:.1f}",
                ha="center",
                va="bottom",
                fontsize=15,
                fontweight="bold",
                color=INK,
                fontproperties=MONO,
            )
            # macro：micro 下方一行灰字，柱背景外，清晰可读
            ax.text(
                cx,
                mi + 1.2,
                f"{cfg['macro_tag']} {ma:.1f}",
                ha="center",
                va="bottom",
                fontsize=9,
                color=MUTED,
            )

    annotate(b_oc, oc_micro, oc_macro)
    annotate(b_pg, pg_micro, pg_macro)

    # pagentv4 相对 OpenCode 的 micro 领先量（绿色徽标，居于每组两柱之间上方）
    for xi, oc, pg in zip(x, oc_micro, pg_micro):
        delta = pg - oc
        top = max(oc, pg)
        ax.annotate(
            f"+{delta:.1f}",
            xy=(xi, top + 9),
            ha="center",
            va="center",
            fontsize=10.5,
            fontweight="bold",
            color="white",
            fontproperties=MONO,
            bbox=dict(boxstyle="round,pad=0.34", fc=GREEN, ec="none"),
            zorder=6,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(cfg["groups"], fontsize=12, color=INK, fontweight="bold")
    ax.set_ylim(0, 100)
    ax.set_ylabel(cfg["ylabel"], fontsize=10.5, color=MUTED)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=DIV, linewidth=1, zorder=0)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(DIV)
    ax.tick_params(axis="both", length=0, colors=MUTED, labelsize=9)
    ax.tick_params(axis="x", labelsize=12)

    # 标题 + 橙色下划线（在标题基线下方，不穿字）
    ax.text(
        0,
        1.10,
        cfg["title"],
        transform=ax.transAxes,
        fontsize=16,
        fontweight="bold",
        color=INK,
        va="bottom",
    )
    ax.plot(
        [0, 0.16],
        [1.085, 1.085],
        transform=ax.transAxes,
        color=BAR_OC,
        lw=3.2,
        clip_on=False,
        solid_capstyle="round",
    )
    ax.text(
        0,
        1.03,
        cfg["subtitle"],
        transform=ax.transAxes,
        fontsize=10,
        color=MUTED,
        va="bottom",
    )

    leg = ax.legend(loc="upper right", fontsize=10, frameon=True, edgecolor=DIV)
    leg.get_frame().set_facecolor(BG)

    fig.text(0.012, 0.014, cfg["note"], fontsize=8, color=MUTED, va="bottom")
    fig.subplots_adjust(top=0.84, bottom=0.09, left=0.08, right=0.97)

    out = HERE / cfg["out"]
    fig.savefig(out, dpi=170, facecolor=BG)
    plt.close(fig)
    DOCS_BENCH.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, DOCS_BENCH / out.name)
    print(
        f"[{lang}] compare: {out.name}  "
        f"easy(oc={oc_micro[0]:.1f},pg={pg_micro[0]:.1f}) "
        f"main(oc={oc_micro[1]:.1f},pg={pg_micro[1]:.1f})"
    )


def main():
    score_oc, score_pg = load_main_micro()
    for lang, cfg in I18N.items():
        render_leaderboard(lang, cfg, score_oc, score_pg)

    cmp_data = load_compare()
    for lang, cfg in CMP_I18N.items():
        render_compare(lang, cfg, cmp_data)


if __name__ == "__main__":
    main()
