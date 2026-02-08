import os
cats = {'visual-art': 'apps/visual-art/', 'generative-art': 'apps/generative-art/'}
results = []
for cat, path in cats.items():
    for f in sorted(os.listdir(path)):
        if f.endswith('.html'):
            fp = os.path.join(path, f)
            size = os.path.getsize(fp)
            results.append((size, cat, f))
results.sort()
for size, cat, f in results:
    flag = ''
    if size == 0: flag = ' [EMPTY]'
    elif size < 500: flag = ' [SKELETON]'
    elif size < 1000: flag = ' [TINY]'
    print(f'{size:>8} {cat:15} {f}{flag}')
print()
print(f'VA: {sum(1 for s,c,f in results if c=="visual-art")}')
print(f'GA: {sum(1 for s,c,f in results if c=="generative-art")}')
print(f'Empty: {sum(1 for s,c,f in results if s==0)}')
print(f'Skel: {sum(1 for s,c,f in results if 0<s<500)}')
