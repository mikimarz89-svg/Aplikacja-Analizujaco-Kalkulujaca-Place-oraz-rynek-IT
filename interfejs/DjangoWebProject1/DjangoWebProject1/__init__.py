"""Package for DjangoWebProject1."""

# Opcjonalnie: u¿yj PyMySQL jako zamiennika MySQLdb dla Django, jeœli zainstalowany.
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    # PyMySQL nie jest zainstalowany — zainstaluj w virtualenv:
    #   python -m venv env
    #   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
    #   .\env\Scripts\Activate.ps1
    #   pip install PyMySQL
    pass
