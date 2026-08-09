# Python automatically imports sitecustomize when the project directory is on sys.path.
# Loading the theme here keeps the existing POS modules unchanged while giving
# every Tk root/window the premium visual system.
try:
    from modules.luxury_theme import install
    install()
except Exception:
    pass
