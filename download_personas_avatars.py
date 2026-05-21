import os
import urllib.request
import ssl

ssl._create_default_https_context = ssl._create_unverified_context
out_dir = os.path.join('static', 'avatars')
os.makedirs(out_dir, exist_ok=True)

# Using 'personas' which gives flat geometric humans similar to Image 3.
base_url = "https://api.dicebear.com/7.x/personas/svg?backgroundColor=e2e8f0,d1fae5,dbeafe,fee2e2,fef3c7,ede9fe"

seeds = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", 
    "Michael", "Linda", "William", "Elizabeth", "David", "Barbara",
    "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah",
    "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa"
]

for i, seed in enumerate(seeds, 17):
    url = f"{base_url}&seed={seed}"
    path = os.path.join(out_dir, f'avatar_{i}.svg')
    print(f'Downloading to {path}')
    try:
        urllib.request.urlretrieve(url, path)
        print(f'Saved avatar_{i}.svg')
    except Exception as e:
        print(f'Error downloading avatar_{i}.svg: {e}')
