import os
import pickle as pkl
import pdb 

with open("readme_names.pkl", 'rb') as f:
	readme_names = pkl.load(f)

for readme_name in readme_names:
	readme_dir = os.path.split(readme_name)[0]
	if not os.path.exists(f'./{readme_dir}'):
		os.makedirs(readme_dir)
		print("Created", readme_dir)
	assert os.path.exists(f"../../CreoleMTData/{readme_name}")
	cp_str = f"cp ../../CreoleMTData/{readme_name} ./{readme_name}"
	print(f"\t{cp_str}", flush=True)
	os.system(cp_str)
print("=" * 70)
print("done")

