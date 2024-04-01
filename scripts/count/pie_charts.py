import pandas as pd
import matplotlib.pyplot as plt

CSV = "genre.csv"

df = pd.read_csv(CSV, index_col="lang")

dy = df.to_dict(orient='index')

labels = ['Bible', 'Educational', 'Legal', 'Narrative', 'News', 'Religious', 'Wikipedia', 'Other/Mix']

# fig, axs = plt.subplots(5, 9)#, figsize=(15, 15))
fig = plt.figure()

idx = 1
for lang in dy:

    ax = plt.subplot(6, 9, idx)
    sizes = [dy[lang][lab] for lab in labels]
    ax.pie(sizes, labels=None)
    title = lang
    if lang == 'gcf':
        title = 'guad1243'
    if len(title) < 4:
        ax.set_title(title, fontsize='14.5')
    else:
        ax.set_title(title, fontsize='12.5')
    idx += 1

ax = plt.subplot(6, 9, idx)
sizes = [dy[lang][lab] for lab in labels[:-1]]
ax.pie(sizes, labels=None)
ax.set_title("- Oth/Mix", fontsize='12.5')

plt.axis('equal')
plt.tight_layout()
fig.legend(labels, loc="lower left", ncol=4, bbox_to_anchor=(0, 0.04), fontsize=12)
# plt.show()
plt.savefig("genre_pies")

# plt.clf()
# sizes = [0] * len(labels)
# plt.pie(sizes, labels=None)

# plt.savefig("genre_pies_legend")

