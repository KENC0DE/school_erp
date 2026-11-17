from controller_api.main import create_controller_app
from controller_api.settings import get_controller_settings

app = create_controller_app(get_controller_settings())
