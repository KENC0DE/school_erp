from app.main import create_app
from app.settings import get_settings

app = create_app(get_settings())
