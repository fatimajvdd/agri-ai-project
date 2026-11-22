"""Matplotlib helpers shared by the Streamlit pages (consistent agricultural colour theme)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PALETTE = ["#2e7d32", "#f9a825", "#6d4c41", "#0288d1", "#7cb342", "#ef6c00", "#8e24aa", "#00897b", "#c62828", "#546e7a"]


def _style(ax, title, xlabel="", ylabel=""):
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left")
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", alpha=.25)


def bar(labels, values, title, ylabel="", color=None, horizontal=False, figsize=(7, 3.8)):
    fig, ax = plt.subplots(figsize=figsize)
    (ax.barh if horizontal else ax.bar)(list(map(str, labels)), list(values), color=color or PALETTE[0])
    if horizontal:
        ax.invert_yaxis()
    else:
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    _style(ax, title, "", ylabel)
    fig.tight_layout()
    return fig


def lines(wide_df, title, ylabel="", figsize=(7.5, 3.8)):
    """wide_df: index = x (year), columns = series."""
    fig, ax = plt.subplots(figsize=figsize)
    for i, c in enumerate(wide_df.columns):
        ax.plot(wide_df.index, wide_df[c], marker="o", ms=3, lw=1.8, color=PALETTE[i % len(PALETTE)], label=str(c))
    if len(wide_df.columns) > 1:
        ax.legend(fontsize=8, frameon=False)
    _style(ax, title, "Year", ylabel)
    fig.tight_layout()
    return fig


def grouped(df, title, ylabel="", figsize=(7.5, 3.8)):
    """df: index = categories, columns = series."""
    fig, ax = plt.subplots(figsize=figsize)
    n = len(df.columns); w = 0.8 / max(n, 1)
    for i, c in enumerate(df.columns):
        ax.bar([k + i * w for k in range(len(df))], df[c], width=w, label=str(c), color=PALETTE[i % len(PALETTE)])
    ax.set_xticks([k + w * (n - 1) / 2 for k in range(len(df))])
    ax.set_xticklabels(list(map(str, df.index)), rotation=20, ha="right")
    ax.legend(fontsize=8, frameon=False)
    _style(ax, title, "", ylabel)
    fig.tight_layout()
    return fig
