import os
import urllib.request
import ssl

ssl._create_default_https_context = ssl._create_unverified_context
out_dir = os.path.join('static', 'avatars')
os.makedirs(out_dir, exist_ok=True)

# Using 'micah' style for professional, clean, diverse headshots
# The micah style automatically handles diverse clothing and hairstyles.
base_url = "https://api.dicebear.com/7.x/micah/svg?backgroundColor=e2e8f0,d1fae5,dbeafe,fee2e2,fef3c7,ede9fe"

seeds = [
    "Alex", "Sophia", "David", "Emma",
    "Michael", "Isabella", "William", "Mia"
]

for i, seed in enumerate(seeds, 1):
    url = f"{base_url}&seed={seed}"
    path = os.path.join(out_dir, f'avatar_{i}.svg')
    print(f'Downloading to {path}')
    try:
        urllib.request.urlretrieve(url, path)
        print(f'Saved avatar_{i}.svg')
    except Exception as e:
        print(f'Error downloading avatar_{i}.svg: {e}')
