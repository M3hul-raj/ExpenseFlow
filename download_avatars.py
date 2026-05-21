import os
import urllib.request
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

out_dir = os.path.join('static', 'avatars')
os.makedirs(out_dir, exist_ok=True)

# We use avataaars which provides high quality diverse professional human avatars
# Specific seeds that look professional and diverse
seeds = [
    'Felix', 'Aneka', 'Oliver', 'Jocelyn', 
    'Jack', 'Valentina', 'Adrian', 'Destiny'
]

for i, seed in enumerate(seeds, 1):
    url = f'https://api.dicebear.com/7.x/avataaars/svg?seed={seed}&backgroundColor=e2e8f0,d1fae5,dbeafe,fee2e2,fef3c7,ede9fe&style=circle'
    path = os.path.join(out_dir, f'avatar_{i}.svg')
    print(f'Downloading {url} to {path}')
    try:
        urllib.request.urlretrieve(url, path)
        print(f'Saved avatar_{i}.svg')
    except Exception as e:
        print(f'Error downloading avatar_{i}.svg: {e}')
