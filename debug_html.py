import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('offline/ramayana.html', encoding='utf-8') as f:
    html = f.read()

# Find position of key elements
checks = [
    ('</body>', html.rfind('</body>')),
    ('</footer>', html.rfind('</footer>')),
    ('<script>window._RD', html.find('<script>window._RD')),
    ('second <script>', html.find('<script>', html.find('<script>') + 1)),
    ('id="kg"', html.find('id="kg"')),
    ('id="badge"', html.find('id="badge"')),
    ('id="wc"', html.find('id="wc"')),
]
for name, pos in sorted(checks, key=lambda x: x[1]):
    print(f'  pos {pos:7d}: {name}')

# Show last 300 chars of file to see script placement
print('\n--- Last 400 chars of file ---')
print(html[-400:].encode('ascii','replace').decode())
