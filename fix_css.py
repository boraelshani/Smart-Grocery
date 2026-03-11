text = open('static/style.css').read()
old = ".nav-link:hover {\n  color: #667eea !important;\n  background: rgba(102, 126, 234, 0.05) !important;\n}"
text = text.replace(old, "/* hover replaced */")

if "Hover rules for premium nav" not in text:
    text += "\n.navbar-premium .nav-link:hover:not(.active) { color: white !important; background: rgba(255,255,255,0.1); border-radius: 12px; }"
    text += "\n.navbar-premium.scrolled .nav-link:hover:not(.active) { color: #7c3aed !important; background: rgba(124,58,237,0.05); border-radius: 12px; }"
    text += "\n.navbar-premium .nav-icon-btn.nav-link { color: #7c3aed !important; }"
    text += "\n.navbar-premium .nav-profile-btn.nav-link { color: white !important; }"
    text += "\n/* Hover rules for premium nav */"

open('static/style.css', 'w').write(text)
print("replaced!")
