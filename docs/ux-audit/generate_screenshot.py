from html2image import Html2Image
import os

os.chdir(r'D:\verified-digital-twin-brains')

# Full page screenshot - longer height
hti = Html2Image(size=(1440, 4500), output_path='docs/ux-audit')
hti.screenshot(html_file='docs/ux-audit/landing-page-mockup.html', save_as='landing-page-full.png')
print('Full page screenshot saved to docs/ux-audit/landing-page-full.png')
