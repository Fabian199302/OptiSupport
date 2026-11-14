"""Figuras para las diapositivas, a partir del motor del repositorio (30 replicas, semillas 42..71)."""
import sys, dataclasses
repo, out = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import config.parametros as cfg, simulacion.main as sm
P0 = cfg.P
def correr(**kw):
    sm.P = dataclasses.replace(P0, **kw)
    try: return {p: sm.correr_escenario("real", p) for p in ("round_robin", "skill_based")}
    finally: sm.P = P0
RR, SB, INK, MUTED, RED = "#015583", "#B48AD6", "#201F4B", "#6B6B7B", "#D62728"
NOM = {"round_robin": "Round Robin", "skill_based": "Skill-Based"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 22, "axes.edgecolor": "#BBBBC6",
    "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": MUTED, "axes.spines.top": False,
    "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlesize": 24})
def m(r, k, s=1.0): return s * r[k]["media"], s * r[k]["ic95_semiancho"]

# ---------- Figura 1: KPIs por politica (c = 9) ----------
base = correr()
fig, axs = plt.subplots(1, 3, figsize=(17.5, 5.6), dpi=200)
paneles = [("W_p95_min", 1, "p95 del tiempo total (min)", "{:.1f}"),
           ("tasa_abandono", 100, "Abandono (%)", "{:.1f} %"),
           ("utilizacion", 100, "Utilización de técnicos (%)", "{:.1f} %")]
for ax, (k, s, tit, fmt) in zip(axs, paneles):
    for i, (pol, col) in zip((0, 1.3), (("round_robin", RR), ("skill_based", SB))):
        v, e = m(base[pol], k, s)
        ax.bar(i, v, width=0.9, color=col, yerr=e, capsize=9, error_kw={"ecolor": INK, "elinewidth": 2.2, "capthick": 2.2})
        if k == "utilizacion":
            ax.text(i, 35, fmt.format(v), ha="center", va="center", color="white" if pol == "round_robin" else INK, fontweight="bold")
        else:
            ax.text(i, v + e + 0.02 * ax.get_ylim()[1], fmt.format(v), ha="center", va="bottom", color=INK, fontweight="bold")
    ax.set_xticks([0, 1.3]); ax.set_xticklabels(["Round Robin", "Skill-Based"]); ax.set_title(tit, pad=14); ax.set_xlim(-0.6, 2.5)
    ax.grid(axis="y", color="#E6E6EC", lw=1); ax.set_axisbelow(True); ax.tick_params(length=0, pad=10)
axs[0].axhline(45, ls="--", color=RED, lw=2.5); axs[0].set_ylim(0, 56)
axs[0].text(2.48, 46, "SLA 45 min", color=RED, ha="right", va="bottom", fontsize=19)
axs[1].axhline(3, ls="--", color=RED, lw=2.5); axs[1].set_ylim(0, 19)
axs[1].text(2.48, 3.3, "SLA 3 %", color=RED, ha="right", va="bottom", fontsize=19)
axs[2].axhspan(70, 85, color="#2E9E5B", alpha=0.16, lw=0); axs[2].set_ylim(0, 108)
axs[2].axhline(70, ls="--", color="#2E9E5B", lw=2); axs[2].axhline(85, ls="--", color="#2E9E5B", lw=2)
axs[2].text(2.48, 87, "70–85 %", color="#1E7A3C", ha="right", va="bottom", fontsize=19)
fig.tight_layout(w_pad=3)
fig.savefig(f"{out}/slide_kpis_politicas.png", facecolor="white"); plt.close(fig)

# ---------- Figura 2: sensibilidad al numero de tecnicos ----------
cs = [9, 10, 11, 12]
res = {c: correr(c_tecnicos=c) for c in cs}
fig, axs = plt.subplots(1, 2, figsize=(17.5, 5.6), dpi=200)
for ax, (k, tit) in zip(axs, (("tasa_abandono", "Abandono (%)"), ("utilizacion", "Utilización de técnicos (%)"))):
    for pol, col, mk in (("round_robin", RR, "o"), ("skill_based", SB, "s")):
        v = [m(res[c][pol], k, 100)[0] for c in cs]; e = [m(res[c][pol], k, 100)[1] for c in cs]
        ax.errorbar(cs, v, yerr=e, color=col, lw=3, marker=mk, ms=12, capsize=8, ecolor=INK, elinewidth=2, label=NOM[pol],
                    markeredgecolor="white", markeredgewidth=2)
        if pol == "skill_based":
            for c, y, d in zip(cs, v, e):
                if k == "tasa_abandono": ax.text(c - 0.1, y - 0.5, f"{y:.1f}", color=INK, fontweight="bold", ha="right", va="top", fontsize=20)
                else: ax.text(c - 0.1, y - 2.2, f"{y:.1f}", color=INK, fontweight="bold", ha="right", va="top", fontsize=20)
    ax.set_xticks(cs); ax.set_xlabel("Número de técnicos (c)"); ax.set_title(tit, pad=14)
    ax.grid(axis="y", color="#E6E6EC", lw=1); ax.set_axisbelow(True); ax.tick_params(length=0, pad=10); ax.set_xlim(8.4, 13.3)
axs[0].axhline(3, ls="--", color=RED, lw=2.5); axs[0].set_ylim(-1.5, 17)
axs[0].text(13.25, 3.3, "SLA < 3 %", color=RED, ha="right", va="bottom", fontsize=19)
axs[0].legend(frameon=False, loc="upper right", fontsize=20)
axs[1].axhspan(70, 85, color="#2E9E5B", alpha=0.16, lw=0); axs[1].set_ylim(50, 95)
axs[1].axhline(70, ls="--", color="#2E9E5B", lw=2); axs[1].axhline(85, ls="--", color="#2E9E5B", lw=2)
axs[1].text(13.25, 85.6, "Banda 70–85 %", color="#1E7A3C", ha="right", va="bottom", fontsize=19)
fig.tight_layout(w_pad=3)
fig.savefig(f"{out}/slide_sensibilidad_tecnicos.png", facecolor="white"); plt.close(fig)
for c in cs: print(c, {p: (round(m(res[c][p],'tasa_abandono',100)[0],1), round(m(res[c][p],'utilizacion',100)[0],1)) for p in res[c]})
