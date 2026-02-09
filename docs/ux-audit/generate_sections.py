from html2image import Html2Image
import os

os.chdir(r'D:\verified-digital-twin-brains')

hti = Html2Image(size=(1440, 900), output_path='docs/ux-audit')

# Hero section only (top portion)
hti.screenshot(html_file='docs/ux-audit/landing-page-mockup.html', save_as='section-hero.png', 
               clip_box=(0, 0, 1440, 900))
print('Hero section saved')

# Features section (scroll position approx)
hti.screenshot(html_file='docs/ux-audit/landing-page-mockup.html', save_as='section-features.png',
               clip_box=(0, 1400, 1440, 2300))
print('Features section saved')

# Pricing section
hti.screenshot(html_file='docs/ux-audit/landing-page-mockup.html', save_as='section-pricing.png',
               clip_box=(0, 2300, 1440, 3200))
print('Pricing section saved')

# Footer section
hti.screenshot(html_file='docs/ux-audit/landing-page-mockup.html', save_as='section-footer.png',
               clip_box=(0, 3600, 1440, 4500))
print('Footer section saved')
